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
        zabbix_user = config.get('zabbix', 'user')
        zabbix_password = config.get('zabbix', 'password')
        timeout = config.getint('zabbix', 'timeout', fallback=10)
        
        zapi = ZabbixAPI(zabbix_url)
        zapi.timeout = timeout
        zapi.login(zabbix_user, zabbix_password)
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
            filter={"status": 0}  # Somente hosts ativos
        )
        
        # Filtra hosts que possuem interface SNMP
        snmp_hosts = []
        for host in hosts:
            for interface in host["interfaces"]:
                if interface["type"] == "2":  # Tipo 2 é SNMP
                    host["snmp_interface"] = interface
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
        community = config.get('snmp', 'community', fallback='public')
        version = config.get('snmp', 'version', fallback='2c')
        timeout = config.getint('snmp', 'timeout', fallback=2)
        retries = config.getint('snmp', 'retries', fallback=3)
        
        ip = host["snmp_interface"]["ip"]
        port = int(host["snmp_interface"]["port"]) if host["snmp_interface"]["port"] else 161
        
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
            return False
        elif error_status:
            logging.debug(f"Host {host['host']} ({ip}): {error_status.prettyPrint()} at {var_binds[int(error_index)-1][0] if error_index else '?'}")
            return False
        else:
            logging.debug(f"Host {host['host']} ({ip}): SNMP OK")
            return True
            
    except Exception as e:
        logging.error(f"Erro ao verificar status SNMP do host {host['host']} ({ip}): {e}")
        return False

# Atualiza o status SNMP no Zabbix
def update_host_snmp_status(zapi, host, status):
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
        else:
            # Cria um novo item para status SNMP
            zapi.item.create({
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
                status = check_snmp_status(host, config)
                
                # Atualiza status no Zabbix
                update_host_snmp_status(zapi, host, status)
                
                if not status:
                    offline_hosts.append(host)
            
            # Registra resultados
            logger.info(f"Verificação concluída. {len(offline_hosts)} dispositivos offline de {len(hosts)} total.")
            if offline_hosts:
                logger.info("Dispositivos offline:")
                for host in offline_hosts:
                    logger.info(f"  - {host['name']} ({host['snmp_interface']['ip']})")
            
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