#### Imports ####
import prometheus_client
import subprocess
import threading
import traceback
import slackweb
import requests
import paramiko
import smtplib
import socket
import email
import time
import yaml
import sys
import ssl
import wmi
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
prometheus_metrics = {
    'hawkups_host_status': prometheus_client.Gauge('hawkups_host_status', 'Host is reachable (0=False/1=True/2=PoweredOff)', ['host']),
    'hawkups_ups_charge': prometheus_client.Gauge('hawkups_ups_charge', 'Current battery charge in percentage (%).'),
    'hawkups_ups_runtime': prometheus_client.Gauge('hawkups_ups_runtime', 'Current battery runtime in seconds.'),
    'hawkups_ups_input_voltage': prometheus_client.Gauge('hawkups_ups_input_voltage', 'Current voltage input in volts.'),
    'hawkups_ups_load': prometheus_client.Gauge('hawkups_ups_load', 'Current UPS load in percentage (%).'),
    'hawkups_ups_realpower': prometheus_client.Gauge('hawkups_ups_realpower', 'UPS\'s realpower nominal. Used to calculate watts usage ((hawkups_ups_load / 100) * hawkups_ups_realpower) = watts'),
    'hawkups_ups_status': prometheus_client.Gauge('hawkups_ups_status', 'Current status of the UPS (0=On Power Grid,1=On Battery Mode).'),
    'hawkups_ups_brand': prometheus_client.Gauge('hawkups_ups_brand', 'Brand of the UPS', ['manufacturer']),
    'hawkups_ups_model': prometheus_client.Gauge('hawkups_ups_model', 'Model of the UPS', ['model'])
}
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

#### Functions ####
# Logging
# 0=info
# 1=warning
# 2=error
def log(_level, _message):
    if _level >= cfg_data['general']['log_level']:
        print('{:^5} | {}'.format(LEVEL[_level], _message), flush=True)

# Load Configuration
def load_config(_config_file):
    global cfg_data, cfg_hosts
    with open(_config_file, 'r') as f:
        cfg_data = yaml.safe_load(f)
        for host in cfg_data['hosts']:
            if ['type', 'runtime_limit'] in cfg_data['hosts'][host]:
                # SSH based connections (Linux/Nimble/ESXi/Synology/etc...)
                if cfg_data['hosts'][host]['type'].lower() == 'unix':
                    if ['port', 'username', 'commands'] in cfg_data['hosts'][host]:
                        cfg_hosts.append(Host(
                            _host=host,
                            _port=cfg_data['hosts'][host]['port'],
                            _typ=cfg_data['hosts'][host]['type'].lower(),
                            _user=cfg_data['hosts'][host]['username'],
                            _password=None,
                            _limit=cfg_data['hosts'][host]['runtime_limit'],
                            _cmds=cfg_data['hosts'][host]['commands']
                        ))
                    else:
                        log(2, 'Unable to load {} host\'s configuration! Missing \'port\', \'username\' and/or \'commands\' config values!'.format(host))

                # WMI based connections (Windows ONLY)
                elif cfg_data['hosts'][host]['type'].lower() == 'windows':
                    if ['username', 'password'] in cfg_data['hosts'][host]:
                        cfg_hosts.append(Host(
                            _host=host,
                            _port=None,
                            _typ=cfg_data['hosts'][host]['type'].lower(),
                            _user=cfg_data['hosts'][host]['username'],
                            _password=cfg_data['hosts'][host]['password'],
                            _limit=cfg_data['hosts'][host]['runtime_limit'],
                            _cmds=None
                        ))
                    else:
                        log(2, 'Unable to load {} host\'s configuration! Missing \'username\' and/or \'password\' config values!'.format(host))

                # Report any unrecognized types
                else:
                    log(2, 'Unable to load {} host\'s configuration! {} is not \'unix\' or \'windows\'.'.format(host, cfg_data['hosts'][host]['type'].lower()))

            else:
                log(2, 'Unable to load {} host! Missing \'type\' and/or \'runtime_limit\' config values!'.format(host))
        cfg_data['hosts'] = None

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

#### Classes ####
# Host
class Host:
    def __init__(self, _host, _port, _typ, _user, _password, _limit, _cmds):
        self.host = _host
        self.port = _port
        self.typ = _typ
        self.user = _user
        self.password = _password
        self.limit = _limit
        self.cmds = _cmds
        self.turned_off = False
    
    def is_alive(self):
        try:
            subprocess.check_output(
                'ping -c 2 {}'.format(self.host).split(' '),
                stderr=subprocess.STDOUT
            )
            return True
        except Exception:
            notify(1, 'host_unreachable', '{} unreachable!'.format(self.host), 'There is no ping response from {} host! Perhaps it is offline?'.format(self.host))
            log(1, 'There is no ping response from {} host! Perhaps it is offline?'.format(self.host))
        return False

    def is_accessible(self):
        if self.typ == 'linux':
            try:
                ssh = paramiko.SSHClient()
                ssh.connect(self.host, username=self.user, key_filename=cfg_data['general']['ssh_private_key'])
                return True
            except Exception:
                notify(1, 'host_connection_fail', 'Unable to access {} host!'.format(self.host), 'Unable to access {} host via SSH! Please check to make sure the host is reachable from the host running HawkUPS system. Please check logs for more info.'.format(self.host))
                log(1, 'Unable to access {} host via SSH! Reason:\n{}'.format(self.host, traceback.print_exc()))
            return False
        elif self.typ == 'windows':
            try:
                wmi.WMI(self.host, user=self.user, password=self.password)
                return True
            except Exception:
                notify(1, 'host_connection_fail', 'Unable to access {} host!'.format(self.host), 'Unable to access {} host via WMI! Please check to make sure the host is reachable from the host running HawkUPS system. Please check logs for more info.'.format(self.host))
                log(1, 'Unable to access {} host via WMI! Reason:\n{}'.format(self.host, traceback.print_exc()))
            return False
        else:
            log(2, 'Unrecognized host type for {}!'.format(self.host))

    def perform_shutdown(self):
        if self.typ == 'linux':
            try:
                ssh = paramiko.SSHClient()
                ssh.connect(self.host, username=self.user, key_filename=cfg_data['general']['ssh_private_key'])
                ssh.exec_command('; '.join(self.cmds))
                ssh.close()
                notify(0, 'host_turned_off', 'Host {} has been turned off!'.format(self.host), 'Host {} has been powered down due to UPS\'s current runtime.'.format(self.host))
                log(0, 'Host {} has been powered down due to UPS\'s current runtime'.format(self.host))
            except Exception:
                notify(1, 'host_turned_off', 'Unable to shutdown {} host!'.format(self.host), 'Unable to shutdown {} host due to unexpected error! Please see logs for more info.'.format(self.host))
                log(1, 'Unable to shutdown {} host due to unexpected error! Reason\n{}'.format(self.host, traceback.print_exc()))
        if self.typ == 'windows':
            try:
                con = wmi.WMI(self.host, user=self.user, password=self.password)
                for cmd in self.cmds:
                    con.Win32_Process.Create(CommandLine=cmd)
                con.close()
                notify(0, 'host_turned_off', 'Host {} has been turned off!'.format(self.host), 'Host {} has been powered down due to UPS\'s current runtime.'.format(self.host))
                log(0, 'Host {} has been powered down due to UPS\'s current runtime'.format(self.host))
            except Exception:
                notify(1, 'host_turned_off', 'Unable to shutdown {} host!'.format(self.host), 'Unable to shutdown {} host due to unexpected error! Please see logs for more info.'.format(self.host))
                log(1, 'Unable to shutdown {} host due to unexpected error! Reason\n{}'.format(self.host, traceback.print_exc()))
        self.turned_off = True

# HostCheckup
class HostCheckup(threading.Thread):
    def __init__(self, _interval):
        threading.Thread.__init__(self)
        self.interval = _interval
    
    def run(self):
        while True:
            # Check all hosts
            log(0, 'Performing connection tests on all hosts...')
            all_hosts_reachable = True
            try:
                for host in cfg_hosts:
                    if not host.is_alive():
                        all_hosts_reachable = False
                        prometheus_metrics['hawkups_host_status'].labels(host=host.host).set(0)
                    else:
                        if not host.is_accessible():
                            all_hosts_reachable = False
                            prometheus_metrics['hawkups_host_status'].labels(host=host.host).set(0)
                        else:
                            prometheus_metrics['hawkups_host_status'].labels(host=host.host).set(1)
                if all_hosts_reachable:
                    notify(2, 'unexpected_error', 'Error while trying check all hosts\' connection status!', 'Unexpected error while trying to check all hosts\' connection status! Please see logs for more info.')
                    log(0, 'All hosts has been checked and all of them are reachable!')
                else:
                    log(1, 'One or more host(s) is/are unreachable!')
            except Exception:
                notify(2, 'unexpected_error', 'Error while trying check all hosts\' connection status!', 'Unexpected error while trying to check all hosts\' connection status! Please see logs for more info.')
                log(2, 'Unable to perform checks on all hosts! Reason:\n{}'.format(traceback.print_exc()))

            # Wait till next interval
            time.sleep(self.interval)

# UPSChecker
class UPSChecker(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.interval = 1 # Interval every second
        self.notify_of_ups_status = False
        self.get_brand_model = False
    
    def _is_ups_online(self):
        try:
            process = subprocess.Popen(
                'upsc {} ups.status'.format(cfg_data['general']['nut_name']).split(' '), 
                stdin=subprocess.PIPE, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE
            )
            output = process.stdout.readline().decode().strip()
            if output == 'OL':
                prometheus_metrics['hawkups_ups_charge'].set(0)
                return True, True
            else:
                prometheus_metrics['hawkups_ups_charge'].set(1)
                return True, False
        except Exception:
            notify(2, 'unexpected_error', 'Error on retrieving UPS status!', 'Unexpected error while trying to retrieve status from UPS via upsc! Please see logs for more info.')
            log(2, 'Unexpected error while trying to retrieve status from UPS via upsc! Reason:\n{}'.format(traceback.print_exc()))
        return False, False
    
    def _get_current_runtime(self):
        try:
            process = subprocess.Popen(
                'upsc {} battery.runtime'.format(cfg_data['general']['nut_name']).split(' '), 
                stdin=subprocess.PIPE, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE
            )
            output = int(process.stdout.readline().decode().strip())
            prometheus_metrics['hawkups_ups_runtime'].set(output)
            return output
        except Exception:
            notify(2, 'unexpected_error', 'Error while retrieving UPS runtime status!', 'Unexpected error while trying to retrieve runtime from the UPS via upsc! Please see logs for more info.')
            log(2, 'Unexpected error while trying to retrieve runtime from the UPS via upsc! Reason:\n{}'.format(traceback.print_exc()))
        return -1

    def _update_other_ups_statistics(self):
        try:
            process = subprocess.Popen(
                'upsc {}'.format(cfg_data['general']['nut_name']).split(' '), 
                stdin=subprocess.PIPE, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE
            )
            for line in process.stdout.readline().decode().strip():
                if line.startswith('ups.load'):
                    output = int(line.replace('ups.load: '))
                    prometheus_metrics['hawkups_ups_load'].set(output)
                elif line.startswith('ups.realpower.nominal'):
                    output = int(line.replace('ups.realpower.nominal: '))
                    prometheus_metrics['hawkups_ups_realpower'].set(output)
                elif line.startswith('battery.charge'):
                    output = int(line.replace('battery.charge: '))
                    prometheus_metrics['hawkups_ups_charge'].set(output)
                elif line.startswith('input.voltage'):
                    output = float(line.replace('input.voltage: '))
                    prometheus_metrics['hawkups_ups_input_voltage'].set(output)
                if not self.get_brand_model:
                    if line.startswith('ups.mfr'):
                        output = line.replace('ups.mfr: ')
                        prometheus_metrics['hawkups_ups_brand'].labels(brand=output).set(1)
                    elif line.startswith('ups.model'):
                        output = line.replace('ups.model: ')
                        prometheus_metrics['hawkups_ups_model'].labels(model=output).set(1)
                    self.get_brand_model = True
        except Exception:
            notify(2, 'unexpected_error', 'Error while retrieving other UPS statistics!', 'Unexpected error while trying to retrieve other statistics from UPS via upsc! Please see logs for more info.')
            log(2, 'Unexpected error while trying to retrieve other statistics from UPS via upsc! Reason:\n{}'.format(traceback.print_exc()))

    def run(self):
        while True:
            # Update other UPS statistics
            self._update_other_ups_statistics()

            # Check its UPS status
            success, status = self._is_ups_online()
            if success and status:
                if self.notify_of_ups_status:
                    notify(0, 'ups_status_change', 'UPS back on power grid mode!', 'Power has been detected from the grid. The UPS has changed back to power grid mode and the battery will be charged whenever needed.')
                    log(0, 'Power has been detected from the grid. The UPS has changed back to power grid mode and the battery will be charged whenever needed.')
                    self.notify_of_ups_status = False
                log(0, 'UPS is on power grid mode, ignoring...')
            elif success and not status:
                # Notify admin of UPS status change
                if not self.notify_of_ups_status:
                    notify(1, 'ups_status_change', 'UPS on battery mode!', 'Power outage has been detected! The UPS has changed to battery mode, proceeding to watch battery\'s runtime...')
                    log(1, 'Power outage has been detected! The UPS has changed to battery mode, proceeding to watch battery\'s runtime...')
                    self.notify_of_ups_status = True
                
                # Check if any hosts' runtime limit is higher than the UPS's current runtime
                current_runtime = self._get_current_runtime()
                if current_runtime > -1:
                    for host in cfg_hosts:
                        if not host.turned_off:
                            if host.limit > current_runtime:
                                host.perform_shutdown()

            # Wait till next interval
            time.sleep(self.interval)

#### Main ####
if __name__ == '__main__':
    # Load config
    print('INFO | Loading configuration...', flush=True)
    load_config(sys.argv[1])
    log(0, 'Configuration loaded!')
    log(0, 'Starting auto host checker...')
    HostCheckup(int(cfg_data['general']['host_checkup']['interval'])).start()
    log(0, 'Auto host checker started!')
    log(0, 'Starting auto UPS checker...')
    UPSChecker().start()
    log(0, 'Auto UPS checker started!')
    if cfg_data['general']['promtheus_exporter']['enable']:
        log(0, 'Starting Prometheus listener...')
        log(0, 'Running...')
        prometheus_client.start_http_server(int(cfg_data['general']['promtheus_exporter']['port']), addr='0.0.0.0')
    else:
        log(0, 'Running...')
