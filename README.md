# Zabbix SNMP Offline Monitor

Este é um módulo completo para monitoramento de dispositivos SNMP no Zabbix 7.0+, com detecção de falhas, teste de ping e interface gráfica integrada.

## Características

- Script Python que verifica dispositivos SNMP e atualiza seu status no Zabbix
- Suporte a macros {$SNMP_COMMUNITY} definidas nos hosts do Zabbix
- Autenticação por token API ou usuário/senha do Zabbix
- Módulo PHP para o frontend do Zabbix com:
  - Dashboard interativa com gráficos e estatísticas
  - Widgets para uso em dashboards personalizados
  - Filtros por grupo de host
  - Verificação de status de ping para dispositivos SNMP offline
  - Exportação de relatórios em CSV e XLSX

## Requisitos

- Zabbix 7.0 ou superior
- Python 3.6 ou superior
- Módulos Python: pyzabbix, pysnmp
- Permissões de administrador no Zabbix
- Git (para instalação direta do repositório)

## Instalação a partir do GitHub

Siga estas instruções para instalar o módulo diretamente do GitHub:

### 1. Clone o repositório

```bash
# Acesse o diretório onde deseja clonar o repositório
cd /tmp

# Clone o repositório do GitHub
git clone https://github.com/seu-usuario/zabbix-snmp-offline-monitor.git

# Acesse o diretório do projeto
cd zabbix-snmp-offline-monitor
```

### 2. Instalação do script Python

```bash
# Instale as dependências
pip3 install pyzabbix pysnmp

# Crie o diretório de scripts externos do Zabbix se não existir
mkdir -p /usr/lib/zabbix/externalscripts/

# Copie os arquivos para o diretório de scripts externos do Zabbix
cp snmp_monitor.py /usr/lib/zabbix/externalscripts/
cp config.ini.example /usr/lib/zabbix/externalscripts/config.ini

# Edite a configuração - IMPORTANTE: Substitua com suas credenciais
nano /usr/lib/zabbix/externalscripts/config.ini

# Ajuste as permissões
chown zabbix:zabbix /usr/lib/zabbix/externalscripts/snmp_monitor.py
chmod +x /usr/lib/zabbix/externalscripts/snmp_monitor.py
chown zabbix:zabbix /usr/lib/zabbix/externalscripts/config.ini
chmod 640 /usr/lib/zabbix/externalscripts/config.ini  # Restringe acesso ao arquivo de configuração
```

### 3. Configuração do serviço systemd

```bash
# Copie o arquivo de serviço
cp zabbix-snmp-monitor.service /etc/systemd/system/

# Habilite e inicie o serviço
systemctl daemon-reload
systemctl enable zabbix-snmp-monitor
systemctl start zabbix-snmp-monitor

# Verifique o status
systemctl status zabbix-snmp-monitor
```

### 4. Instalação do módulo de frontend

```bash
# Determine o diretório de módulos do Zabbix
# Para instalação padrão:
ZABBIX_MODULES_DIR="/usr/share/zabbix/modules"
# Para outras instalações, encontre o diretório correto:
# find /usr -name modules -path "*/zabbix*" 2>/dev/null

# Crie o diretório para o módulo
mkdir -p $ZABBIX_MODULES_DIR/SNMPMonitor

# Copie os arquivos para o diretório de módulos do Zabbix
cp -r ui/modules/SNMPMonitor/* $ZABBIX_MODULES_DIR/SNMPMonitor/

# Ajuste as permissões - substitua www-data pelo usuário do seu servidor web
WEB_USER=$(ps -ef | egrep '(apache|httpd|nginx)' | grep -v root | head -n1 | awk '{print $1}')
chown -R $WEB_USER:$WEB_USER $ZABBIX_MODULES_DIR/SNMPMonitor/
```

### 5. Ativação do módulo no Zabbix

1. Acesse o frontend do Zabbix como administrador
2. Vá para **Administração → Geral → Módulos**
3. Clique em **Scan directory**
4. Encontre o módulo "SNMP Monitor" e clique em **Enable**

## Community Strings SNMP e Autenticação por Token

### Configuração de Community Strings SNMP por host

Este módulo suporta o uso de community strings diferentes para cada host do Zabbix:

1. Para definir a community string para um host específico:
   - Vá para a configuração do host no Zabbix
   - Na aba "Macros", adicione uma macro `{$SNMP_COMMUNITY}` com o valor da community string
   - Por exemplo: `{$SNMP_COMMUNITY}` = `minhaSecretCommunity`

2. O script irá:
   - Automaticamente detectar e usar a macro `{$SNMP_COMMUNITY}` de cada host
   - Usar a community string padrão do config.ini apenas quando a macro não estiver definida
   - Registrar nos logs qual método foi usado para cada host

3. Dica de segurança:
   - Configure o tipo da macro como "Texto secreto" para que o valor não seja visível na interface do Zabbix

### Autenticação por Token API (Zabbix 7+)

Para usar tokens API em vez de usuário/senha:

1. Crie um token API no Zabbix:
   - Vá para **Administração → Usuários**
   - Selecione o usuário e acesse a aba "Tokens de API"
   - Crie um novo token com permissões adequadas 
   - Copie o valor do token

2. Configure o arquivo `config.ini`:
   - Comente as linhas `user` e `password`
   - Descomente a linha `token` e defina o valor do token

Exemplo:
```ini
[zabbix]
server = http://seu-servidor-zabbix/zabbix
# user = seu_usuario_zabbix
# password = sua_senha_zabbix
token = seu_token_api_zabbix
timeout = 10
```

## Configuração Segura (Importante)

O arquivo `config.ini` contém credenciais sensíveis. Para garantir a segurança do seu ambiente, siga estas práticas:

1. **Nunca faça upload do config.ini com credenciais para o GitHub**
   - No repositório, fornecemos apenas `config.ini.example`

2. **Restrinja o acesso ao arquivo de configuração**
   ```bash
   chmod 640 /usr/lib/zabbix/externalscripts/config.ini
   chown zabbix:zabbix /usr/lib/zabbix/externalscripts/config.ini
   ```

3. **Use um usuário com privilégios mínimos necessários**
   - Crie um usuário Zabbix específico para este script com permissões limitadas
   - Ative a autenticação baseada em token API quando possível

4. **Considere armazenar as credenciais em um cofre de senhas**
   - Para ambientes empresariais, considere ferramentas como HashiCorp Vault ou CyberArk

## Testes

### Teste do script Python

```bash
# Execute o script manualmente para verificar seu funcionamento
cd /usr/lib/zabbix/externalscripts/
python3 snmp_monitor.py
```

### Verificação do módulo

1. Após ativar o módulo, verifique se apareceu um novo item no menu principal em **Monitoring → SNMP Monitor**
2. Clique em "Dashboard" para visualizar a interface principal
3. Verifique se os hosts com SNMP são exibidos corretamente
4. Teste o filtro de grupos e as opções de exportação

### Simulando falhas SNMP para testes

1. Desative temporariamente o agente SNMP em um dispositivo
2. Configure um firewall para bloquear temporariamente o tráfego SNMP (porta 161/UDP)
3. Configure um dispositivo com community string incorreta

### Adicionando os widgets a um dashboard

1. Vá para **Monitoring → Dashboards**
2. Crie um novo dashboard ou edite um existente
3. Clique em **Add widget**
4. Na categoria de widgets, você encontrará:
   - "SNMP Status Graph" - Gráfico de pizza com status SNMP
   - "SNMP Offline Devices" - Lista de dispositivos offline

## Resolução de problemas

### Logs do script Python

```bash
# Verifique os logs do script
tail -f /usr/lib/zabbix/externalscripts/snmp_monitor.log

# Verifique os logs do serviço
journalctl -u zabbix-snmp-monitor -f
```

### Erros no módulo frontend

- Verifique os logs do servidor web:
  - Apache: `/var/log/apache2/error.log`
  - Nginx: `/var/log/nginx/error.log`
- Verifique o log frontend do Zabbix: `/var/log/zabbix/zabbix_server.log`

## Atualização

Para atualizar o módulo para uma nova versão:

```bash
# Acesse o diretório do repositório clonado
cd /caminho/para/zabbix-snmp-offline-monitor

# Faça backup das suas configurações
cp /usr/lib/zabbix/externalscripts/config.ini /usr/lib/zabbix/externalscripts/config.ini.bak

# Atualize o repositório
git pull

# Copie os arquivos atualizados
cp snmp_monitor.py /usr/lib/zabbix/externalscripts/
cp -r ui/modules/SNMPMonitor/* /usr/share/zabbix/modules/SNMPMonitor/

# Restaure suas configurações (se necessário)
# cp /usr/lib/zabbix/externalscripts/config.ini.bak /usr/lib/zabbix/externalscripts/config.ini

# Reinicie o serviço
systemctl restart zabbix-snmp-monitor
```

## Contribuições

Contribuições são bem-vindas! Sinta-se à vontade para abrir issues ou enviar pull requests. Certifique-se de não incluir credenciais ou informações sensíveis em seus commits.