# Módulo Zabbix para Monitoramento SNMP Offline

Este módulo permite monitorar e filtrar dispositivos com SNMP offline no Zabbix, facilitando a identificação de equipamentos que não estão respondendo às requisições SNMP.

## Funcionalidades

- Detecta dispositivos SNMP não responsivos
- Gera alertas para dispositivos offline
- Possibilita a filtragem de dispositivos por status SNMP
- Dashboard personalizado para visualização rápida de dispositivos offline
- Relatórios periódicos de status SNMP

## Requisitos

- Zabbix Server 6.0+
- Python 3.8+
- Biblioteca pysnmp
- Acesso à API do Zabbix

## Instalação

1. Clone este repositório:
```bash
git clone https://github.com/ThomasJPF/zabbix-snmp-offline-monitor.git
```

2. Instale as dependências:
```bash
pip install -r requirements.txt
```

3. Configure o arquivo `config.ini` com suas credenciais do Zabbix:
```ini
[zabbix]
server = http://seu-servidor-zabbix/api_jsonrpc.php
user = seu_usuario
password = sua_senha
```

4. Importe o template para o Zabbix Server:
```bash
python import_template.py
```

## Uso

### Execução do monitor

```bash
python snmp_monitor.py
```

### Verificação de dispositivos offline

```bash
python check_offline.py
```

### Geração de relatórios

```bash
python generate_report.py --days 7
```

## Estrutura

- `snmp_monitor.py`: Script principal para monitoramento
- `check_offline.py`: Utilitário para verificação de dispositivos offline
- `generate_report.py`: Geração de relatórios de status
- `templates/`: Templates do Zabbix
- `dashboards/`: Dashboards personalizados
- `lib/`: Bibliotecas auxiliares

## Contribuição

Contribuições são bem-vindas! Sinta-se à vontade para abrir issues ou enviar pull requests.

## Licença

Este projeto está licenciado sob a [MIT License](LICENSE).