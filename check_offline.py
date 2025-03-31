#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para verificar e listar dispositivos com SNMP offline no Zabbix.
"""

import os
import sys
import logging
import argparse
import configparser
from datetime import datetime, timedelta
from pyzabbix import ZabbixAPI
from tabulate import tabulate

# Configuração de logging
def setup_logging():
    """Configura o sistema de logs"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger('check_offline')

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

# Obtém hosts offline
def get_offline_hosts(zapi, hours=24):
    """Retorna lista de hosts com SNMP offline nas últimas 'hours' horas"""
    try:
        # Busca todos os hosts com o item snmp.status
        items = zapi.item.get(
            output=["itemid", "hostid", "name", "key_", "lastvalue"],
            search={"key_": "snmp.status"},
            filter={"value_type": 3}  # Tipo numérico inteiro
        )
        
        # Filtra por hosts offline (valor 0)
        offline_item_ids = [item["itemid"] for item in items if item["lastvalue"] == "0"]
        
        if not offline_item_ids:
            return []
        
        # Busca informações dos hosts
        hosts = zapi.host.get(
            output=["hostid", "host", "name", "status"],
            selectInterfaces=["interfaceid", "ip", "type", "main", "port"],
            itemids=offline_item_ids
        )
        
        # Adiciona informações adicionais para cada host
        for host in hosts:
            # Encontra a interface SNMP
            for interface in host["interfaces"]:
                if interface["type"] == "2":  # Tipo 2 é SNMP
                    host["snmp_interface"] = interface
                    break
            
            # Busca o histórico do item de status SNMP
            for item in items:
                if item["hostid"] == host["hostid"]:
                    host["snmp_item"] = item
                    
                    # Obtém histórico para saber quando ficou offline
                    history = zapi.history.get(
                        itemids=item["itemid"],
                        history=3,  # Tipo numérico inteiro
                        sortfield="clock",
                        sortorder="DESC",
                        limit=10,
                        time_from=int((datetime.now() - timedelta(hours=hours)).timestamp())
                    )
                    
                    if history:
                        # Encontra a última transição para offline (valor 0)
                        for i, record in enumerate(history):
                            if record["value"] == "0":
                                if i+1 < len(history) and history[i+1]["value"] == "1":
                                    # Encontrou a transição de 1 para 0
                                    host["offline_since"] = datetime.fromtimestamp(int(record["clock"]))
                                    break
                                elif i == 0:
                                    # Primeiro registro já é offline
                                    host["offline_since"] = datetime.fromtimestamp(int(record["clock"]))
                        
                        if "offline_since" not in host:
                            # Se não encontrou uma transição clara, usa o timestamp do primeiro registro offline
                            for record in history:
                                if record["value"] == "0":
                                    host["offline_since"] = datetime.fromtimestamp(int(record["clock"]))
                                    break
                    
                    break
        
        return hosts
    except Exception as e:
        logging.error(f"Erro ao obter hosts offline: {e}")
        return []

# Função principal
def main():
    """Função principal do script"""
    # Configura parser de argumentos
    parser = argparse.ArgumentParser(description='Verifica dispositivos SNMP offline no Zabbix')
    parser.add_argument('--hours', type=int, default=24, help='Considerar dispositivos offline nas últimas X horas (padrão: 24)')
    parser.add_argument('--csv', action='store_true', help='Exporta a saída em formato CSV')
    parser.add_argument('--output', type=str, help='Arquivo de saída (padrão: stdout)')
    args = parser.parse_args()
    
    # Configuração inicial
    logger = setup_logging()
    config = load_config()
    
    # Conecta ao Zabbix
    logger.info("Conectando ao Zabbix API...")
    zapi = connect_zabbix(config)
    logger.info(f"Conectado ao Zabbix API v{zapi.api_version()}")
    
    # Obtém hosts offline
    logger.info(f"Buscando dispositivos offline nas últimas {args.hours} horas...")
    offline_hosts = get_offline_hosts(zapi, args.hours)
    
    if not offline_hosts:
        logger.info("Nenhum dispositivo SNMP offline encontrado!")
        return
    
    # Prepara os dados para exibição
    table_data = []
    for host in offline_hosts:
        offline_since = host.get('offline_since', 'Desconhecido')
        if isinstance(offline_since, datetime):
            offline_duration = datetime.now() - offline_since
            offline_duration_str = f"{offline_duration.days}d {offline_duration.seconds//3600}h {(offline_duration.seconds//60)%60}m"
            offline_since = offline_since.strftime("%Y-%m-%d %H:%M:%S")
        else:
            offline_duration_str = "Desconhecido"
        
        ip = host.get('snmp_interface', {}).get('ip', 'N/A')
        
        table_data.append([
            host['name'],
            ip,
            offline_since,
            offline_duration_str
        ])
    
    # Ordenar por duração offline (do mais antigo para o mais recente)
    table_data.sort(key=lambda x: x[2], reverse=True)
    
    # Exibe os resultados
    headers = ["Nome do Host", "Endereço IP", "Offline Desde", "Duração"]
    
    if args.csv:
        # Formato CSV
        import csv
        output = sys.stdout if not args.output else open(args.output, 'w', newline='')
        writer = csv.writer(output)
        writer.writerow(headers)
        writer.writerows(table_data)
        if args.output:
            output.close()
            logger.info(f"Dados exportados para {args.output}")
    else:
        # Formato tabela
        table = tabulate(table_data, headers=headers, tablefmt="grid")
        if args.output:
            with open(args.output, 'w') as f:
                f.write(table)
            logger.info(f"Dados exportados para {args.output}")
        else:
            print(f"\nDispositivos SNMP Offline ({len(offline_hosts)}):\n")
            print(table)

    logger.info(f"Total de {len(offline_hosts)} dispositivos SNMP offline encontrados.")

if __name__ == "__main__":
    main()