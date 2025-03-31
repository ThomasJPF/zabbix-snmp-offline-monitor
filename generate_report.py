#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para gerar relatórios de dispositivos SNMP offline no Zabbix.
"""

import os
import sys
import logging
import argparse
import configparser
from datetime import datetime, timedelta
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from jinja2 import Environment, FileSystemLoader
from pyzabbix import ZabbixAPI
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

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
    return logging.getLogger('generate_report')

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

# Obtém hosts com histórico de status SNMP
def get_snmp_history(zapi, days=7):
    """Retorna histórico de status SNMP para todos os hosts no período especificado"""
    try:
        # Calcula timestamp inicial
        time_from = int((datetime.now() - timedelta(days=days)).timestamp())
        
        # Busca todos os hosts com o item snmp.status
        items = zapi.item.get(
            output=["itemid", "hostid", "name", "key_"],
            search={"key_": "snmp.status"},
            filter={"value_type": 3}  # Tipo numérico inteiro
        )
        
        if not items:
            return {}, {}
        
        # Busca informações dos hosts
        hosts_data = zapi.host.get(
            output=["hostid", "host", "name", "status"],
            selectInterfaces=["interfaceid", "ip", "type", "main", "port"],
            itemids=[item["itemid"] for item in items]
        )
        
        # Cria dicionário de hosts para fácil acesso
        hosts = {}
        for host in hosts_data:
            # Encontra a interface SNMP
            for interface in host["interfaces"]:
                if interface["type"] == "2":  # Tipo 2 é SNMP
                    host["snmp_interface"] = interface
                    break
                    
            hosts[host["hostid"]] = host
        
        # Busca histórico para cada item
        history_data = {}
        for item in items:
            hostid = item["hostid"]
            history = zapi.history.get(
                itemids=item["itemid"],
                history=3,  # Tipo numérico inteiro
                sortfield="clock",
                sortorder="ASC",
                time_from=time_from
            )
            
            if history and hostid in hosts:
                history_data[hostid] = {
                    "host": hosts[hostid],
                    "history": [{
                        "timestamp": datetime.fromtimestamp(int(record["clock"])),
                        "value": int(record["value"])
                    } for record in history]
                }
        
        return hosts, history_data
    except Exception as e:
        logging.error(f"Erro ao obter histórico SNMP: {e}")
        return {}, {}

# Analisa os dados para gerar estatísticas
def analyze_data(history_data, days=7):
    """Analisa os dados de histórico para gerar estatísticas"""
    stats = {
        "total_hosts": len(history_data),
        "offline_count": 0,
        "availability_pct": {},
        "outage_duration": {},
        "outage_frequency": {},
        "hosts_by_availability": []
    }
    
    for hostid, data in history_data.items():
        host_name = data["host"]["name"]
        host_ip = data["host"].get("snmp_interface", {}).get("ip", "N/A")
        history = data["history"]
        
        # Se não há dados suficientes, pula
        if len(history) < 2:
            continue
        
        # Inicializa contadores
        total_time = (history[-1]["timestamp"] - history[0]["timestamp"]).total_seconds()
        if total_time <= 0:
            continue
            
        offline_time = 0
        outage_count = 0
        current_outage_start = None
        outages = []
        
        # Analisa o histórico de status
        for i, record in enumerate(history):
            if i == 0:
                # Se o primeiro registro é offline, considera como início de outage
                if record["value"] == 0:
                    current_outage_start = record["timestamp"]
                continue
                
            # Detecta transição para offline
            if record["value"] == 0 and history[i-1]["value"] == 1:
                current_outage_start = record["timestamp"]
                
            # Detecta transição para online
            elif record["value"] == 1 and history[i-1]["value"] == 0 and current_outage_start:
                outage_duration = (record["timestamp"] - current_outage_start).total_seconds()
                offline_time += outage_duration
                outages.append({
                    "start": current_outage_start,
                    "end": record["timestamp"],
                    "duration": outage_duration
                })
                current_outage_start = None
                outage_count += 1
                
        # Se o último estado é offline, adiciona o tempo até agora
        if history[-1]["value"] == 0 and current_outage_start:
            outage_duration = (datetime.now() - current_outage_start).total_seconds()
            offline_time += outage_duration
            outages.append({
                "start": current_outage_start,
                "end": datetime.now(),
                "duration": outage_duration
            })
            outage_count += 1
            
        # Calcula disponibilidade
        availability = 100 * (1 - (offline_time / total_time))
        availability = max(0, min(100, availability))  # Limita entre 0 e 100%
        
        # Armazena estatísticas
        stats["availability_pct"][hostid] = availability
        stats["outage_duration"][hostid] = offline_time
        stats["outage_frequency"][hostid] = outage_count
        
        # Se teve algum período offline, incrementa contador
        if outage_count > 0:
            stats["offline_count"] += 1
            
        # Adiciona host à lista ordenada por disponibilidade
        stats["hosts_by_availability"].append({
            "hostid": hostid,
            "name": host_name,
            "ip": host_ip,
            "availability": availability,
            "outage_count": outage_count,
            "outage_duration": offline_time,
            "outages": outages
        })
    
    # Ordena hosts por disponibilidade (crescente)
    stats["hosts_by_availability"].sort(key=lambda x: x["availability"])
    
    return stats

# Gera gráficos para o relatório
def generate_charts(history_data, stats, output_dir):
    """Gera gráficos para o relatório"""
    os.makedirs(output_dir, exist_ok=True)
    charts = {}
    
    # 1. Gráfico de pizza de disponibilidade
    try:
        plt.figure(figsize=(8, 8))
        availability_ranges = {
            "99% - 100%": 0,
            "95% - 99%": 0,
            "90% - 95%": 0,
            "80% - 90%": 0,
            "0% - 80%": 0
        }
        
        for hostid, availability in stats["availability_pct"].items():
            if availability >= 99:
                availability_ranges["99% - 100%"] += 1
            elif availability >= 95:
                availability_ranges["95% - 99%"] += 1
            elif availability >= 90:
                availability_ranges["90% - 95%"] += 1
            elif availability >= 80:
                availability_ranges["80% - 90%"] += 1
            else:
                availability_ranges["0% - 80%"] += 1
                
        # Remove faixas vazias
        availability_ranges = {k: v for k, v in availability_ranges.items() if v > 0}
        
        if availability_ranges:
            plt.pie(availability_ranges.values(), labels=availability_ranges.keys(), autopct='%1.1f%%')
            plt.title('Distribuição de Disponibilidade SNMP')
            chart_path = os.path.join(output_dir, 'availability_pie.png')
            plt.savefig(chart_path)
            plt.close()
            charts["availability_pie"] = chart_path
    except Exception as e:
        logging.error(f"Erro ao gerar gráfico de disponibilidade: {e}")
    
    # 2. Gráfico de barras dos 10 hosts com menor disponibilidade
    try:
        worst_hosts = stats["hosts_by_availability"][:10]
        if worst_hosts:
            plt.figure(figsize=(12, 6))
            hosts = [h["name"] for h in worst_hosts]
            availability = [h["availability"] for h in worst_hosts]
            
            plt.barh(hosts, availability, color='salmon')
            plt.xlabel('Disponibilidade (%)')
            plt.ylabel('Host')
            plt.title('10 Hosts com Menor Disponibilidade SNMP')
            plt.xlim(0, 100)
            plt.grid(axis='x', linestyle='--', alpha=0.6)
            
            chart_path = os.path.join(output_dir, 'worst_hosts.png')
            plt.savefig(chart_path)
            plt.close()
            charts["worst_hosts"] = chart_path
    except Exception as e:
        logging.error(f"Erro ao gerar gráfico de piores hosts: {e}")
    
    return charts

# Gera o relatório HTML
def generate_html_report(stats, charts, config, days):
    """Gera relatório HTML com os dados processados"""
    try:
        report_dir = config.get('reporting', 'report_dir', fallback='reports')
        template_dir = config.get('reporting', 'template_dir', fallback='templates/reports')
        
        # Cria diretórios se não existirem
        os.makedirs(report_dir, exist_ok=True)
        os.makedirs(template_dir, exist_ok=True)
        
        # Cria um template simples se não existir
        template_file = os.path.join(template_dir, 'report_template.html')
        if not os.path.exists(template_file):
            with open(template_file, 'w') as f:
                f.write("""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Relatório de Monitoramento SNMP - {{ date }}</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        h1, h2 { color: #2c3e50; }
        table { border-collapse: collapse; width: 100%; margin: 15px 0; }
        th, td { padding: 8px; text-align: left; border: 1px solid #ddd; }
        th { background-color: #f2f2f2; }
        tr:nth-child(even) { background-color: #f9f9f9; }
        .chart { margin: 30px 0; text-align: center; }
        .chart img { max-width: 100%; }
        .summary { background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0; }
        .warning { color: #e74c3c; }
    </style>
</head>
<body>
    <h1>Relatório de Monitoramento SNMP</h1>
    <p>Período: Últimos {{ days }} dias ({{ start_date }} a {{ end_date }})</p>
    
    <div class="summary">
        <h2>Resumo</h2>
        <p>Total de dispositivos: <strong>{{ stats.total_hosts }}</strong></p>
        <p>Dispositivos com incidentes: <strong>{{ stats.offline_count }}</strong></p>
        <p>Porcentagem de dispositivos afetados: <strong>{{ offline_percent }}%</strong></p>
    </div>
    
    {% if charts.availability_pie %}
    <div class="chart">
        <h2>Distribuição de Disponibilidade</h2>
        <img src="{{ charts.availability_pie }}" alt="Gráfico de Disponibilidade">
    </div>
    {% endif %}
    
    {% if charts.worst_hosts %}
    <div class="chart">
        <h2>Dispositivos com Menor Disponibilidade</h2>
        <img src="{{ charts.worst_hosts }}" alt="Dispositivos com Menor Disponibilidade">
    </div>
    {% endif %}
    
    {% if stats.hosts_by_availability %}
    <h2>Lista de Dispositivos com Problemas</h2>
    <table>
        <tr>
            <th>Nome</th>
            <th>IP</th>
            <th>Disponibilidade</th>
            <th>Qtd. Incidentes</th>
            <th>Tempo Total Offline</th>
        </tr>
        {% for host in stats.hosts_by_availability %}
        {% if host.availability < 100 %}
        <tr>
            <td>{{ host.name }}</td>
            <td>{{ host.ip }}</td>
            <td>{{ "%.2f"|format(host.availability) }}%</td>
            <td>{{ host.outage_count }}</td>
            <td>{{ outage_duration_str(host.outage_duration) }}</td>
        </tr>
        {% endif %}
        {% endfor %}
    </table>
    {% endif %}
    
    <p>Relatório gerado em {{ generated_at }}</p>
</body>
</html>""")
        
        # Carrega o template
        env = Environment(loader=FileSystemLoader(os.path.dirname(template_file)))
        
        # Adiciona função auxiliar para formatar duração
        def outage_duration_str(seconds):
            days = int(seconds // 86400)
            hours = int((seconds % 86400) // 3600)
            minutes = int((seconds % 3600) // 60)
            if days > 0:
                return f"{days}d {hours}h {minutes}m"
            elif hours > 0:
                return f"{hours}h {minutes}m"
            else:
                return f"{minutes}m"
                
        env.globals['outage_duration_str'] = outage_duration_str
        
        # Carrega o template
        template = env.get_template(os.path.basename(template_file))
        
        # Prepara dados para o template
        now = datetime.now()
        start_date = (now - timedelta(days=days)).strftime('%d/%m/%Y')
        end_date = now.strftime('%d/%m/%Y')
        
        # Calcula porcentagem de hosts offline
        offline_percent = 0
        if stats["total_hosts"] > 0:
            offline_percent = round(100 * stats["offline_count"] / stats["total_hosts"], 1)
        
        # Gera o relatório HTML
        html = template.render(
            stats=stats,
            charts=charts,
            date=now.strftime('%d/%m/%Y'),
            start_date=start_date,
            end_date=end_date,
            days=days,
            offline_percent=offline_percent,
            generated_at=now.strftime('%d/%m/%Y %H:%M:%S')
        )
        
        # Salva o relatório
        report_filename = f"snmp_report_{now.strftime('%Y%m%d_%H%M%S')}.html"
        report_path = os.path.join(report_dir, report_filename)
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html)
            
        return report_path
    except Exception as e:
        logging.error(f"Erro ao gerar relatório HTML: {e}")
        return None

# Envia relatório por email
def send_email_report(report_path, config):
    """Envia o relatório por email se configurado"""
    if not config.getboolean('alerts', 'email_enabled', fallback=False):
        return False
        
    try:
        smtp_server = config.get('alerts', 'smtp_server')
        smtp_port = config.getint('alerts', 'smtp_port', fallback=587)
        smtp_user = config.get('alerts', 'smtp_user')
        smtp_password = config.get('alerts', 'smtp_password')
        smtp_tls = config.getboolean('alerts', 'smtp_tls', fallback=True)
        
        email_from = config.get('alerts', 'email_from')
        email_to = config.get('alerts', 'email_to')
        email_subject = config.get('alerts', 'email_subject', fallback='Relatório de Monitoramento SNMP')
        
        # Cria a mensagem
        msg = MIMEMultipart()
        msg['From'] = email_from
        msg['To'] = email_to
        msg['Subject'] = email_subject
        
        # Corpo do email
        body = "Segue em anexo o relatório de monitoramento SNMP.\n\n"
        msg.attach(MIMEText(body, 'plain'))
        
        # Anexa o relatório
        with open(report_path, 'rb') as f:
            attachment = MIMEApplication(f.read(), _subtype='html')
            attachment.add_header('Content-Disposition', 'attachment', filename=os.path.basename(report_path))
            msg.attach(attachment)
        
        # Conecta e envia
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            if smtp_tls:
                server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
            
        return True
    except Exception as e:
        logging.error(f"Erro ao enviar relatório por email: {e}")
        return False

# Função principal
def main():
    """Função principal do script"""
    # Configura parser de argumentos
    parser = argparse.ArgumentParser(description='Gera relatório de dispositivos SNMP no Zabbix')
    parser.add_argument('--days', type=int, default=7, help='Período do relatório em dias (padrão: 7)')
    parser.add_argument('--email', action='store_true', help='Envia relatório por email se configurado')
    args = parser.parse_args()
    
    # Configuração inicial
    logger = setup_logging()
    config = load_config()
    
    # Conecta ao Zabbix
    logger.info("Conectando ao Zabbix API...")
    zapi = connect_zabbix(config)
    logger.info(f"Conectado ao Zabbix API v{zapi.api_version()}")
    
    # Obtém dados históricos
    logger.info(f"Obtendo histórico SNMP dos últimos {args.days} dias...")
    hosts, history_data = get_snmp_history(zapi, args.days)
    
    if not history_data:
        logger.warning("Nenhum dado de histórico SNMP encontrado!")
        return
        
    logger.info(f"Dados de {len(history_data)} hosts obtidos. Analisando...")
    
    # Analisa os dados
    stats = analyze_data(history_data, args.days)
    
    # Gera gráficos
    logger.info("Gerando gráficos...")
    output_dir = config.get('reporting', 'report_dir', fallback='reports')
    charts = generate_charts(history_data, stats, output_dir)
    
    # Gera relatório HTML
    logger.info("Gerando relatório HTML...")
    report_path = generate_html_report(stats, charts, config, args.days)
    
    if report_path:
        logger.info(f"Relatório gerado com sucesso: {report_path}")
        
        # Envia por email se solicitado
        if args.email:
            logger.info("Enviando relatório por email...")
            if send_email_report(report_path, config):
                logger.info("Relatório enviado por email com sucesso!")
            else:
                logger.warning("Não foi possível enviar o relatório por email.")
    else:
        logger.error("Falha ao gerar relatório!")

if __name__ == "__main__":
    main()