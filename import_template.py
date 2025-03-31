#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para importar template SNMP Monitor para o Zabbix.
"""

import os
import sys
import logging
import argparse
from lib.zabbix_helper import ZabbixHelper

# Configura logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('import_template')

def main():
    """Função principal"""
    # Configura parser de argumentos
    parser = argparse.ArgumentParser(description='Importa template de monitoramento SNMP para o Zabbix')
    parser.add_argument('--template', type=str, default='templates/snmp_monitor_template.xml', 
                        help='Caminho para o arquivo XML do template (padrão: templates/snmp_monitor_template.xml)')
    args = parser.parse_args()
    
    # Verifica se o template existe
    if not os.path.exists(args.template):
        # Cria o diretório se não existir
        os.makedirs(os.path.dirname(args.template), exist_ok=True)
        
        # Cria um template básico
        logger.info(f"Template não encontrado. Criando template básico em {args.template}")
        template_xml = """<?xml version="1.0" encoding="UTF-8"?>
<zabbix_export>
    <version>5.0</version>
    <date>2023-01-01T00:00:00Z</date>
    <groups>
        <group>
            <name>Templates/Network Devices</name>
        </group>
    </groups>
    <templates>
        <template>
            <template>Template SNMP Monitor</template>
            <name>Template SNMP Monitor</name>
            <description>Template para monitoramento de dispositivos SNMP</description>
            <groups>
                <group>
                    <name>Templates/Network Devices</name>
                </group>
            </groups>
            <applications>
                <application>
                    <name>SNMP</name>
                </application>
            </applications>
            <items>
                <item>
                    <name>SNMP Status</name>
                    <key>snmp.status</key>
                    <delay>0</delay>
                    <history>90d</history>
                    <trends>365d</trends>
                    <type>TRAP</type>
                    <description>Status da comunicação SNMP (1 - Online, 0 - Offline)</description>
                    <applications>
                        <application>
                            <name>SNMP</name>
                        </application>
                    </applications>
                    <valuemap>
                        <name>SNMP Status</name>
                    </valuemap>
                </item>
            </items>
            <triggers>
                <trigger>
                    <expression>{Template SNMP Monitor:snmp.status.last()}=0</expression>
                    <name>SNMP Offline</name>
                    <priority>WARNING</priority>
                    <description>Dispositivo não está respondendo a requisições SNMP</description>
                    <manual_close>NO</manual_close>
                </trigger>
            </triggers>
            <valuemaps>
                <valuemap>
                    <name>SNMP Status</name>
                    <mappings>
                        <mapping>
                            <value>0</value>
                            <newvalue>Offline</newvalue>
                        </mapping>
                        <mapping>
                            <value>1</value>
                            <newvalue>Online</newvalue>
                        </mapping>
                    </mappings>
                </valuemap>
            </valuemaps>
        </template>
    </templates>
</zabbix_export>"""
        
        with open(args.template, 'w') as f:
            f.write(template_xml)
    
    # Importa o template
    logger.info(f"Importando template {args.template}...")
    
    try:
        helper = ZabbixHelper()
        zapi = helper.connect()
        
        if not zapi:
            logger.error("Não foi possível conectar ao Zabbix API. Verifique suas configurações.")
            sys.exit(1)
            
        logger.info(f"Conectado ao Zabbix API v{zapi.api_version()}")
        
        if helper.import_template(args.template):
            logger.info("Template importado com sucesso!")
        else:
            logger.error("Falha ao importar o template.")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Erro ao importar template: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()