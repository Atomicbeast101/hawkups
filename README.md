# HawkUPS
Automated UPS management system where it will monitor UPS status using NUT and perform shutdown on Linux and Windows clients/servers based on runtime threshold. This was originally designed to run on Raspberry Pis with USB connection to the UPS, however it can pretty much run on any Linux based devices as long as NUT can run on it and has some connection to the UPS.

[Setup](https://github.com/Atomicbeast101/hawkups/) | [Configuration](https://github.com/Atomicbeast101/hawkups/) | [Prometheus](https://github.com/Atomicbeast101/hawkups/)

## Features
* Automatically shutdown hosts specified in simple config file.
* Can shutdown any hosts with SSH capability and Windows via Linux's `net` command.
* Configure specific runtime threshold for each host.
* Can specify shutdown commands for each host (ideal for different Linux/Unix OSs' shutdown command setup)

## Requirements
* Linux OS (tested with Rasbian lite)
* Python v3.6+
* Following Python packages: `prometheus_client pyyaml validators paramiko`
* Experience with YAML configuration. Check [here](https://gettaurus.org/docs/YAMLTutorial/) to learn on how to use YAML.

## Donate
I maintain this project during my free time and any donations would help me continue this project! I accept donations via PayPal through [here](https://paypal.me/adambro).
