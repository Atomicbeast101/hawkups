#### Imports ####
import prometheus_client
import traceback
import slackweb
import requests
import smtplib
import socket
import email
import time
import yaml
import sys
import ssl
import os

#### Check for config file path ####
if not sys.argv[1]:
    print('[ERROR]: Missing config file path argument! Please include one.', flush=True)
    exit(0)

#### Attributes ####
# Config
cfg_data = None
cfg_hosts = list()
# Prometheus Exporter
promex_host = prometheus_client.Gauge('hawkups_host_status', 'Host is reachable via SSH (0=False/1=True)')
# Other
LEVEL = {
    0: 'INFO',
    1: 'WARN',
    2: 'ERROR'
}
TEXT_TEMPLATE = '''Systems Administrator,
{}
Thank You,
HawkUPS System'''
HTML_TEMPLATE = '''<html><head></head>
    <body>
        <p>Systems Administrator,</p>
        <p>{}</p>
        <p>
            Thank You,<br />
            <b>HawkUPS System</b>
        </p>
    </body>
</html>'''

#### Classes ####
# Host
class Host:
    def __init__(self, _host, _port, _typ, _user, _limit, _cmds):
        self.host = _host
        self.port = _port
        self.typ = _typ
        self.limit = _limit
        self.cmds = _cmds
    
    def is_alive(self):
        return True if os.system('ping -c 1 {}'.format(self.host)) is 0 else False

#### Functions ####
# Logging
# 0=info
# 1=warning
# 2=error
def log(_level, _message):
    if _level >= cfg_data['general']['log_level']:
        print('{:^5} | {}'.format(LEVEL[_level], _message), flush=True)

# Notification
def notify(_level, _type, _short_desc, _long_desc):
    cfg_notif = cfg_data['general']['alerts']

    if not cfg_notif['triggers'][_type]:
        return

    # SMTP
    if cfg_notif['smtp']['enabled']:
        # Generate email content
        smtp_host = cfg_notif['smtp']['host']
        smtp_port = cfg_notif['smtp']['port']
        user = cfg_notif['smtp']['user']
        password = cfg_notif['smtp']['password']
        to_addr = cfg_notif['smtp']['to_address']
        subject = '[{}]: {}'.format(LEVEL[_level], _short_desc)
        text_msg = TEXT_TEMPLATE.format(_long_desc)
        html_msg = HTML_TEMPLATE.format(_long_desc)

        try:
            smtp_msg = email.mime.multipart.MIMEMultipart('alternative')
            smtp_msg['Subject'] = subject
            smtp_msg['From'] = user
            smtp_msg['To'] = to_addr
            smtp_msg.attach(email.mime.text.MIMEText(text_msg, 'plain'))
            smtp_msg.attach(email.mime.text.MIMEText(html_msg, 'html'))
            with smtplib.SMTP_SSL(smtp_host, smtp_port, context=ssl.create_default_context()) as smtp_server:
                smtp_server.login(user, password)
                smtp_server.sendmail(user, to_addr, smtp_msg.as_string())
        except Exception:
            log(2, 'Unable to send email notification! Reason:\n{}'.format(traceback.print_exc()))

    # Pushover
    if cfg_notif['pushover']['enabled']:
        token = cfg_notif['pushover']['token']
        user = cfg_notif['pushover']['user']
        devices = cfg_notif['pushover']['devices']
        priority = cfg_notif['pushover']['priority']
        title = '[{}]: {}'.format(LEVEL[_level], _short_desc)
        message = _long_desc

        try:
            r = requests.post('https://api.pushover.net/1/messages.json', json={
                'token': token,
                'user': user,
                'devices': devices,
                'priority': priority,
                'title': title,
                'message': message
            })
            if r.status_code == 200:
                log(0, 'Pushover notification has been sent!')
            else:
                log(2, 'Unable to send Pushover notification! Reason: \n{}'.format(r.json()))
        except Exception:
            log(2, 'Unable to send Pushover notification! Reason:\n{}'.format(traceback.print_exc()))

    # Slack
    if cfg_notif['slack']['enabled']:
        url = cfg_notif['slack']['webhook_url']
        username = cfg_notif['slack']['username']
        channel = cfg_notif['slack']['channel']
        icon = cfg_notif['slack']['icon']
        attachments = [{
            'color': 'FF0000',
            'title': '[{}]: {}'.format(LEVEL[_level], _short_desc),
            'text': _long_desc
        }]

        try:
            slack = slackweb.Slack(url=url)
            slack.notify(
                channel=channel,
                username=username,
                icon_emoji=icon,
                attachments=attachments
            )
        except Exception:
            log(2, 'Unable to send Slack notification! Reason:\n{}'.format(traceback.print_exc()))

# Load Configuration
def load_config(_config_file):
    global cfg_data, cfg_hosts
    with open(_config_file, 'r') as f:
        cfg_data = yaml.safe_load(f)
        for host in cfg_data['hosts']:
            if ['type', 'runtime_limit'] in cfg_data['hosts'][host]:

                # SSH based connections (Linux/Nimble/Synology/etc.)
                if cfg_data['hosts'][host]['type'] == 'ssh':
                    if ['user', 'commands'] in cfg_data['hosts'][host]:
                        cfg_hosts.append(Host(
                            _host=host,
                            _port=cfg_data['hosts'][host]['port'],
                            _typ=cfg_data['hosts'][host]['type'],
                            _user=cfg_data['hosts'][host]['user'],
                            _limit=cfg_data['hosts'][host]['runtime_limit'],
                            _cmds=cfg_data['hosts'][host]['commands']
                        ))
                    else:
                        log('CONFIG_ERR', 'Unable to load {} host\'s configuration! Missing \'user\' and/or \'commands\' config values!'.format(host))

                # NET based connections (Windows)
                elif cfg_data['hosts'][host]['type'] == 'net':
                    log('CONFIG_WARN', 'net type connections feature is not ready yet.') # TODO Add net feature
                
                else:
                    log('CONFIG_ERR', 'Unknown \'type\' for {} host!'.format(host))
                
            else:
                log('CONFIG_ERR', 'Unable to load {} host! Missing \'type\' and/or \'runtime_limit\' config values!'.format(host))
        cfg_data['hosts'] = None

# Check Host Status
def check_host(_host):
    client = socket.socket()
    try:
        client.connect((_host.host, _host.port))
        client.close()
        return True
    except socket.error:
        log('SSH_ERR', 'Unable to access {} host! Reason:\n{}'.format(_host.host, traceback.print_exc()))
    except Exception:
        log('UNKNOWN_ERR', 'Unable to perform check_host() function on {} host! Reason:\n{}'.format(_host.host, traceback.print_exc()))
    return False

# Check All Host Status
def check_hosts():
    try:
        for host in cfg_hosts:
            if check_host(host):
                promex_host.labels(host=host.host).set(1)
            else:
                notify() # TODO
                promex_host.labels(host=host.host).set(0)
    except Exception:
        log('GEN_ERR', 'Unable to perform checks on all hosts! Reason:\n{}'.format(traceback.print_exc()))

# Check Battery Status
def on_battery_mode():
    print() # TODO

# Perform Host Shutdown
def shutdown_host(_host):
    # Checks if host is alive
    if not check_host(_host):
        notify() # TODO
        return False
    
    # Perform shutdown
    try:
        # TODO
        return True
    except Exception:
        log('SHUTDOWN_ERR', 'Unable to shutdown {} host! Reason:\n{}'.format(_host.host, traceback.print_exc()))

# Host Check Runner
def host_run(_interval):
    while True:
        # Checks all hosts' SSH status
        check_hosts()

        # Wait X seconds
        time.sleep(_interval)

# Battery Check Runner
def batt_run(_interval):
    while True:
        # Check battery status
        if on_battery_mode():
            # Notify user of the execution of shutdown task
            notify() # TODO
            
            # Perform shutdown
            for host in cfg_hosts:
                shutdown_host(host)
            
            # Notify user of completed shutdown task
            notify() # TODO
        else:
            log('INFO', 'Battery is in plugged-in mode, ignoring...')

        # Wait X seconds
        time.sleep(_interval)

#### Flask Calls?? ####
#### Main ####
if __name__ == '__main__':
    # Load config
    log('INFO', 'Loading configuration...')
    load_config(sys.argv[1])
    log('INFO', 'Configuration loaded!')
    # Start listening
