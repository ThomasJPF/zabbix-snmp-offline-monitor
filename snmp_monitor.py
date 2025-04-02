#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script principal para monitoramento de dispositivos SNMP no Zabbix.
Detecta e registra dispositivos que não estão respondendo às requisições SNMP.
"""

import os
import sys
import time
import logging
import configparser
import subprocess
import platform
from datetime import datetime
from pyzabbix import ZabbixAPI
from pysnmp.hlapi import (
    getCmd, SnmpEngine, CommunityData, UdpTransportTarget,
    ContextData, ObjectType, ObjectIdentity
)

# Configuração de logging
def setup_logging(config):
    """Configura o sistema de logs"""
    log_level = getattr(logging, config.get('monitor', 'log_level', fallback='INFO'))
    log_file = config.get('monitor', 'log_file', fallback='snmp_monitor.log')
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger('snmp_monitor')

# Carrega as configurações
def load_config():
    """Carrega as configurações do arquivo config.ini"""
    if not os.path.exists('config.ini'):
        raise FileNotFoundError("Arquivo config.ini não encontrado. Utilize config.ini.example como modelo.")
    
    config = configparser.ConfigParser()
    config.read('config.ini')
    return config

# Conecta ao Zabbix API
def connect_zabbix(config):
    """Estabelece conexão com a API do Zabbix"""
    try:
        zabbix_url = config.get('zabbix', 'server')
        timeout = config.getint('zabbix', 'timeout', fallback=10)
        
        zapi = ZabbixAPI(zabbix_url)
        zapi.timeout = timeout
        
        # Verifica se usa token ou usuário/senha
        if config.has_option('zabbix', 'token'):
            token = config.get('zabbix', 'token')
            zapi.login(api_token=token)
            logging.info("Autenticado no Zabbix API usando token")
        else:
            zabbix_user = config.get('zabbix', 'user')
            zabbix_password = config.get('zabbix', 'password')
            zapi.login(zabbix_user, zabbix_password)
            logging.info("Autenticado no Zabbix API usando usuário e senha")
            
        return zapi
    except Exception as e:
        logging.error(f"Erro ao conectar ao Zabbix API: {e}")
        sys.exit(1)

# Obtém hosts do Zabbix com interface SNMP
def get_snmp_hosts(zapi):
    """Retorna lista de hosts do Zabbix com interfaces SNMP configuradas"""
    try:
        # Busca hosts com interfaces SNMP
        hosts = zapi.host.get(
            output=["hostid", "host", "name", "status"],
            selectInterfaces=["interfaceid", "ip", "type", "main", "port"],
            selectMacros=["macro", "value"],  # Busca também as macros do host
            filter={"status": 0}  # Somente hosts ativos
        )
        
        # Filtra hosts que possuem interface SNMP
        snmp_hosts = []
        for host in hosts:
            for interface in host["interfaces"]:
                if interface["type"] == "2":  # Tipo 2 é SNMP
                    host["snmp_interface"] = interface
                    
                    # Procura por macro {$SNMP_COMMUNITY}
                    host["snmp_community"] = None
                    for macro in host["macros"]:
                        if macro["macro"] == "{$SNMP_COMMUNITY}":
                            host["snmp_community"] = macro["value"]
                            break
                    
                    snmp_hosts.append(host)
                    break
        
        return snmp_hosts
    except Exception as e:
        logging.error(f"Erro ao obter hosts SNMP do Zabbix: {e}")
        return []

# Verifica se um host está respondendo a SNMP
def check_snmp_status(host, config):
    """Verifica se um host responde a consultas SNMP"""
    try:
        # Obtém a community string da macro do host, ou usa o valor padrão
        community = host.get("snmp_community") or config.get('snmp', 'default_community', fallback='public')
        
        version = config.get('snmp', 'version', fallback='2c')
        timeout = config.getint('snmp', 'timeout', fallback=2)
        retries = config.getint('snmp', 'retries', fallback=3)
        
        ip = host["snmp_interface"]["ip"]
        port = int(host["snmp_interface"]["port"]) if host["snmp_interface"]["port"] else 161
        
        logging.debug(f"Verificando SNMP no host {host['host']} ({ip}) com community: {'*' * len(community)}")
        
        # Verifica se o dispositivo responde ao OID sysDescr
        error_indication, error_status, error_index, var_binds = next(
            getCmd(
                SnmpEngine(),
                CommunityData(community, mpModel=0 if version == '1' else 1),
                UdpTransportTarget((ip, port), timeout=timeout, retries=retries),
                ContextData(),
                ObjectType(ObjectIdentity('1.3.6.1.2.1.1.1.0'))  # sysDescr
            )
        )
        
        if error_indication:
            logging.debug(f"Host {host['host']} ({ip}): {error_indication}")
            return False, str(error_indication)
        elif error_status:
            error_msg = f"{error_status.prettyPrint()} at {var_binds[int(error_index)-1][0] if error_index else '?'}"
            logging.debug(f"Host {host['host']} ({ip}): {error_msg}")
            return False, error_msg
        else:
            logging.debug(f"Host {host['host']} ({ip}): SNMP OK")
            return True, ""
            
    except Exception as e:
        logging.error(f"Erro ao verificar status SNMP do host {host['host']} ({ip}): {e}")
        return False, str(e)

# Verifica se um host responde a ping
def check_ping_status(host, config):
    """Verifica se um host responde a ping"""
    try:
        ip = host["snmp_interface"]["ip"]
        count = config.getint('ping', 'count', fallback=3)
        timeout = config.getint('ping', 'timeout', fallback=2)
        
        # Comando de ping varia de acordo com o sistema operacional
        param = '-n' if platform.system().lower() == 'windows' else '-c'
        timeout_param = '-w' if platform.system().lower() == 'windows' else '-W'
        
        command = ['ping', param, str(count), timeout_param, str(timeout), ip]
        
        # Executa o ping
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        # Verifica o resultado
        if result.returncode == 0:
            logging.debug(f"Host {host['host']} ({ip}): PING OK")
            return True
        else:
            logging.debug(f"Host {host['host']} ({ip}): PING falhou")
            return False
            
    except Exception as e:
        logging.error(f"Erro ao verificar status PING do host {host['host']} ({ip}): {e}")
        return False

# Atualiza o status SNMP no Zabbix
def update_host_snmp_status(zapi, host, status, error_msg=""):
    """Atualiza o valor do item de status SNMP no Zabbix"""
    try:
        # Verifica se o item de status SNMP existe
        items = zapi.item.get(
            hostids=host["hostid"],
            search={"key_": "snmp.status"},
            output=["itemid"]
        )
        
        if items:
            # Atualiza o valor do item existente
            zapi.item.update(
                itemid=items[0]["itemid"],
                value_type=3,  # Tipo numérico inteiro
                status=0  # Ativo
            )
            
            # Envia o valor para o item
            zapi.history.add({
                "itemid": items[0]["itemid"],
                "clock": int(time.time()),
                "value": "1" if status else "0",
                "ns": 0
            })
            
            # Atualiza a mensagem de erro se disponível
            if not status and error_msg:
                zapi.item.update(
                    itemid=items[0]["itemid"],
                    error=error_msg[:255]  # Limita ao tamanho máximo
                )
        else:
            # Cria um novo item para status SNMP
            snmp_item = zapi.item.create({
                "name": "SNMP Status",
                "key_": "snmp.status",
                "hostid": host["hostid"],
                "type": 2,  # Tipo trapper
                "value_type": 3,  # Tipo numérico inteiro
                "description": "Status da comunicação SNMP (1 - Online, 0 - Offline)",
                "status": 0,  # Ativo
                "history": "90d"
            })
            
            # Aguarda um momento para o item ser criado
            time.sleep(1)
            
            # Busca novamente o item criado
            items = zapi.item.get(
                hostids=host["hostid"],
                search={"key_": "snmp.status"},
                output=["itemid"]
            )
            
            if items:
                # Envia o valor para o item
                zapi.history.add({
                    "itemid": items[0]["itemid"],
                    "clock": int(time.time()),
                    "value": "1" if status else "0",
                    "ns": 0
                })
                
                # Atualiza a mensagem de erro se disponível
                if not status and error_msg:
                    zapi.item.update(
                        itemid=items[0]["itemid"],
                        error=error_msg[:255]  # Limita ao tamanho máximo
                    )
                
        return True
    except Exception as e:
        logging.error(f"Erro ao atualizar status SNMP do host {host['host']}: {e}")
        return False

# Função principal
def main():
    """Função principal do script"""
    # Carrega configurações
    config = load_config()
    logger = setup_logging(config)
    
    # Conecta ao Zabbix
    logger.info("Iniciando monitoramento SNMP...")
    zapi = connect_zabbix(config)
    logger.info(f"Conectado ao Zabbix API v{zapi.api_version()}")
    
    interval = config.getint('monitor', 'interval', fallback=300)
    
    try:
        while True:
            start_time = time.time()
            logger.info("Iniciando verificação de dispositivos SNMP...")
            
            # Obtém hosts com SNMP
            hosts = get_snmp_hosts(zapi)
            logger.info(f"Encontrados {len(hosts)} hosts com interfaces SNMP.")
            
            offline_hosts = []
            for host in hosts:
                logger.debug(f"Verificando host {host['host']} ({host['snmp_interface']['ip']})")
                
                # Verifica status SNMP
                snmp_ok, error_msg = check_snmp_status(host, config)
                
                # Verifica status de ping se SNMP falhar
                ping_ok = False
                if not snmp_ok:
                    ping_ok = check_ping_status(host, config)
                    
                # Atualiza status no Zabbix
                update_host_snmp_status(zapi, host, snmp_ok, error_msg)
                
                if not snmp_ok:
                    community_info = ""
                    if host.get("snmp_community"):
                        community_info = " (Usando macro {$SNMP_COMMUNITY})"
                    else:
                        community_info = " (Usando community padrão)"
                    
                    offline_hosts.append({
                        'host': host,
                        'ping_ok': ping_ok,
                        'error': error_msg,
                        'community_info': community_info
                    })
            
            # Registra resultados
            logger.info(f"Verificação concluída. {len(offline_hosts)} dispositivos offline de {len(hosts)} total.")
            if offline_hosts:
                logger.info("Dispositivos offline:")
                for item in offline_hosts:
                    host = item['host']
                    ping_status = "Responde a ping" if item['ping_ok'] else "Não responde a ping"
                    logger.info(f"  - {host['name']} ({host['snmp_interface']['ip']}): {ping_status}, Erro: {item['error']}{item['community_info']}")
            
            # Calcula tempo para próxima execução
            execution_time = time.time() - start_time
            sleep_time = max(interval - execution_time, 1)
            
            logger.info(f"Próxima verificação em {int(sleep_time)} segundos.")
            time.sleep(sleep_time)
            
    except KeyboardInterrupt:
        logger.info("Monitoramento interrompido pelo usuário.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Erro no monitoramento: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()