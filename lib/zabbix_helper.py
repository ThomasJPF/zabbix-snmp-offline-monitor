#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Biblioteca auxiliar para operações com o Zabbix API.
"""

import os
import sys
import logging
import configparser
from datetime import datetime, timedelta
from pyzabbix import ZabbixAPI

class ZabbixHelper:
    """Classe auxiliar para interações com o Zabbix"""
    
    def __init__(self, config_file='config.ini'):
        """Inicializa o helper com as configurações do arquivo"""
        self.config = self._load_config(config_file)
        self.zapi = None
        self.logger = logging.getLogger('zabbix_helper')
    
    def _load_config(self, config_file):
        """Carrega as configurações do arquivo"""
        if not os.path.exists(config_file):
            raise FileNotFoundError(f"Arquivo {config_file} não encontrado.")
        
        config = configparser.ConfigParser()
        config.read(config_file)
        return config
    
    def connect(self):
        """Estabelece conexão com a API do Zabbix"""
        try:
            zabbix_url = self.config.get('zabbix', 'server')
            zabbix_user = self.config.get('zabbix', 'user')
            zabbix_password = self.config.get('zabbix', 'password')
            timeout = self.config.getint('zabbix', 'timeout', fallback=10)
            
            self.zapi = ZabbixAPI(zabbix_url)
            self.zapi.timeout = timeout
            self.zapi.login(zabbix_user, zabbix_password)
            return self.zapi
        except Exception as e:
            self.logger.error(f"Erro ao conectar ao Zabbix API: {e}")
            return None
    
    def get_snmp_hosts(self):
        """Retorna lista de hosts do Zabbix com interfaces SNMP configuradas"""
        if not self.zapi:
            raise ConnectionError("Não conectado ao Zabbix API. Chame connect() primeiro.")
            
        try:
            # Busca hosts com interfaces SNMP
            hosts = self.zapi.host.get(
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
            self.logger.error(f"Erro ao obter hosts SNMP do Zabbix: {e}")
            return []
    
    def get_host_groups(self):
        """Retorna lista de grupos de hosts do Zabbix"""
        if not self.zapi:
            raise ConnectionError("Não conectado ao Zabbix API. Chame connect() primeiro.")
            
        try:
            groups = self.zapi.hostgroup.get(
                output=["groupid", "name"]
            )
            return groups
        except Exception as e:
            self.logger.error(f"Erro ao obter grupos de hosts: {e}")
            return []
    
    def get_templates(self):
        """Retorna lista de templates do Zabbix"""
        if not self.zapi:
            raise ConnectionError("Não conectado ao Zabbix API. Chame connect() primeiro.")
            
        try:
            templates = self.zapi.template.get(
                output=["templateid", "host", "name"]
            )
            return templates
        except Exception as e:
            self.logger.error(f"Erro ao obter templates: {e}")
            return []
    
    def create_snmp_status_item(self, host):
        """Cria item de status SNMP para o host especificado"""
        if not self.zapi:
            raise ConnectionError("Não conectado ao Zabbix API. Chame connect() primeiro.")
            
        try:
            # Verifica se o item já existe
            items = self.zapi.item.get(
                hostids=host["hostid"],
                search={"key_": "snmp.status"},
                output=["itemid"]
            )
            
            if items:
                self.logger.info(f"Item SNMP Status já existe para o host {host['name']}")
                return items[0]["itemid"]
            
            # Cria novo item
            result = self.zapi.item.create({
                "name": "SNMP Status",
                "key_": "snmp.status",
                "hostid": host["hostid"],
                "type": 2,  # Tipo trapper
                "value_type": 3,  # Tipo numérico inteiro
                "description": "Status da comunicação SNMP (1 - Online, 0 - Offline)",
                "status": 0,  # Ativo
                "history": "90d"
            })
            
            self.logger.info(f"Item SNMP Status criado para o host {host['name']}")
            return result["itemids"][0]
        except Exception as e:
            self.logger.error(f"Erro ao criar item SNMP Status para o host {host['name']}: {e}")
            return None
    
    def create_trigger(self, host, item_id):
        """Cria trigger para alertar quando o status SNMP ficar offline"""
        if not self.zapi:
            raise ConnectionError("Não conectado ao Zabbix API. Chame connect() primeiro.")
            
        try:
            # Verifica se a trigger já existe
            triggers = self.zapi.trigger.get(
                hostids=host["hostid"],
                search={"description": "SNMP Offline"},
                output=["triggerid"]
            )
            
            if triggers:
                self.logger.info(f"Trigger SNMP Offline já existe para o host {host['name']}")
                return triggers[0]["triggerid"]
            
            # Cria nova trigger
            expression = f"{{#{host['host']}:snmp.status.last()}}=0"
            
            result = self.zapi.trigger.create({
                "description": "SNMP Offline",
                "expression": expression,
                "priority": 3,  # Média severidade
                "status": 0,  # Ativo
                "type": 0,  # Problema quando expressão = true
                "recovery_mode": 0,  # Expressão
                "manual_close": 0  # Não permitir fechamento manual
            })
            
            self.logger.info(f"Trigger SNMP Offline criada para o host {host['name']}")
            return result["triggerids"][0]
        except Exception as e:
            self.logger.error(f"Erro ao criar trigger para o host {host['name']}: {e}")
            return None
    
    def update_snmp_status(self, host, status):
        """Atualiza o status SNMP de um host"""
        if not self.zapi:
            raise ConnectionError("Não conectado ao Zabbix API. Chame connect() primeiro.")
            
        try:
            # Busca o item de status SNMP
            items = self.zapi.item.get(
                hostids=host["hostid"],
                search={"key_": "snmp.status"},
                output=["itemid"]
            )
            
            if not items:
                # Cria o item se não existir
                item_id = self.create_snmp_status_item(host)
            else:
                item_id = items[0]["itemid"]
                
            # Envia o valor para o item
            self.zapi.history.add({
                "itemid": item_id,
                "clock": int(datetime.now().timestamp()),
                "value": "1" if status else "0",
                "ns": 0
            })
            
            return True
        except Exception as e:
            self.logger.error(f"Erro ao atualizar status SNMP do host {host['name']}: {e}")
            return False
    
    def get_hosts_with_snmp_status(self):
        """Retorna lista de hosts com status SNMP configurado"""
        if not self.zapi:
            raise ConnectionError("Não conectado ao Zabbix API. Chame connect() primeiro.")
            
        try:
            # Busca todos os hosts com o item snmp.status
            items = self.zapi.item.get(
                output=["itemid", "hostid", "lastvalue"],
                search={"key_": "snmp.status"},
                filter={"value_type": 3}  # Tipo numérico inteiro
            )
            
            if not items:
                return []
                
            # Obtém informações dos hosts
            host_ids = [item["hostid"] for item in items]
            hosts = self.zapi.host.get(
                output=["hostid", "host", "name", "status"],
                selectInterfaces=["interfaceid", "ip", "type", "main", "port"],
                hostids=host_ids
            )
            
            # Combina as informações
            for host in hosts:
                for item in items:
                    if item["hostid"] == host["hostid"]:
                        host["snmp_status"] = {
                            "itemid": item["itemid"],
                            "value": int(item["lastvalue"]) if item["lastvalue"] else 0
                        }
                        break
                        
                # Encontra a interface SNMP
                for interface in host["interfaces"]:
                    if interface["type"] == "2":  # Tipo 2 é SNMP
                        host["snmp_interface"] = interface
                        break
            
            return hosts
        except Exception as e:
            self.logger.error(f"Erro ao obter hosts com status SNMP: {e}")
            return []
    
    def get_offline_hosts(self):
        """Retorna lista de hosts com SNMP offline"""
        hosts = self.get_hosts_with_snmp_status()
        return [host for host in hosts if host.get("snmp_status", {}).get("value", 1) == 0]
    
    def import_template(self, template_file):
        """Importa um template do Zabbix a partir de um arquivo XML"""
        if not self.zapi:
            raise ConnectionError("Não conectado ao Zabbix API. Chame connect() primeiro.")
            
        try:
            if not os.path.exists(template_file):
                raise FileNotFoundError(f"Arquivo de template não encontrado: {template_file}")
                
            with open(template_file, 'r') as f:
                template_data = f.read()
                
            result = self.zapi.configuration.import_({
                "format": "xml",
                "rules": {
                    "applications": {
                        "createMissing": True,
                        "updateExisting": True
                    },
                    "valueMaps": {
                        "createMissing": True,
                        "updateExisting": True
                    },
                    "templates": {
                        "createMissing": True,
                        "updateExisting": True
                    },
                    "templateScreens": {
                        "createMissing": True,
                        "updateExisting": True
                    },
                    "templateLinkage": {
                        "createMissing": True
                    },
                    "items": {
                        "createMissing": True,
                        "updateExisting": True,
                        "deleteMissing": False
                    },
                    "triggers": {
                        "createMissing": True,
                        "updateExisting": True,
                        "deleteMissing": False
                    },
                    "graphs": {
                        "createMissing": True,
                        "updateExisting": True,
                        "deleteMissing": False
                    },
                    "discoveryRules": {
                        "createMissing": True,
                        "updateExisting": True,
                        "deleteMissing": False
                    }
                },
                "source": template_data
            })
            
            self.logger.info(f"Template importado com sucesso: {template_file}")
            return True
        except Exception as e:
            self.logger.error(f"Erro ao importar template {template_file}: {e}")
            return False