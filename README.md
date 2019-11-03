# HawkUPS
Automated UPS management system where it will monitor UPS status using NUT and perform shutdown on Linux and Windows clients/servers based on runtime threshold. This was originally designed to run on Raspberry Pis with USB connection to the UPS, however it can pretty much run on any Linux based devices as long as NUT can run on it and has some connection to the UPS.

[Ansible Setup](https://github.com/Atomicbeast101/hawkups/wiki/Ansible-Setup) | [Manual Setup](https://github.com/Atomicbeast101/hawkups/wiki/Manual-Setup) | [Configuration](https://github.com/Atomicbeast101/hawkups/wiki/Configuration)

## Features
* Automatically shutdown hosts specified in simple YAML config file.
* Can shutdown any host with SSH capability and Windows via Linux's `net` command.
* Configure specific runtime threshold for each host.
* Can specify shutdown commands for each host (ideal for different Linux/Unix OSs' shutdown command setup)
* Built-in exporter for Prometheus/InfluxDB to scrap status of the HawkUPS system

## Requirements
* Linux OS (tested with Rasbian lite)
* Python v3.6+
* Following Python packages: `prometheus_client pyyaml validators paramiko`
* Experience with YAML configuration. Check [here](https://gettaurus.org/docs/YAMLTutorial/) to learn on how to use YAML.

## Example Output of HawkUPS Exporter
```
# HELP python_info Python platform information
# TYPE python_info gauge
python_info{implementation="CPython",major="3",minor="5",patchlevel="3",version="3.5.3"} 1.0
# HELP hawkups_host_status Host is reachable (0=False/1=True/2=PoweredOff)
# TYPE hawkups_host_status gauge
hawkups_host_status{host="modb.potato.lab"} 1.0
# HELP hawkups_ups_status Current status of the UPS (0=On Power Grid,1=On Battery Mode).
# TYPE hawkups_ups_status gauge
hawkups_ups_status 0.0
# HELP hawkups_ups_input_voltage Current voltage input in volts.
# TYPE hawkups_ups_input_voltage gauge
hawkups_ups_input_voltage 120.0
# HELP python_gc_objects_collected_total Objects collected during gc
# TYPE python_gc_objects_collected_total counter
python_gc_objects_collected_total{generation="0"} 3140.0
python_gc_objects_collected_total{generation="1"} 787.0
python_gc_objects_collected_total{generation="2"} 0.0
# HELP python_gc_objects_uncollectable_total Uncollectable object found during GC
# TYPE python_gc_objects_uncollectable_total counter
python_gc_objects_uncollectable_total{generation="0"} 0.0
python_gc_objects_uncollectable_total{generation="1"} 0.0
python_gc_objects_uncollectable_total{generation="2"} 0.0
# HELP python_gc_collections_total Number of times this generation was collected
# TYPE python_gc_collections_total counter
python_gc_collections_total{generation="0"} 100.0
python_gc_collections_total{generation="1"} 9.0
python_gc_collections_total{generation="2"} 0.0
# HELP hawkups_ups_load Current UPS load in percentage (%).
# TYPE hawkups_ups_load gauge
hawkups_ups_load 30.0
# HELP hawkups_ups_charge Current UPS's battery charge in percentage (%)
# TYPE hawkups_ups_charge gauge
hawkups_ups_charge 0.0
# HELP hawkups_ups_realpower UPS's realpower nominal. Used to calculate watts usage ((hawkups_ups_load / 100) * hawkups_ups_realpower) = watts
# TYPE hawkups_ups_realpower gauge
hawkups_ups_realpower 865.0
# HELP process_virtual_memory_bytes Virtual memory size in bytes.
# TYPE process_virtual_memory_bytes gauge
process_virtual_memory_bytes 4.13507584e+08
# HELP process_resident_memory_bytes Resident memory size in bytes.
# TYPE process_resident_memory_bytes gauge
process_resident_memory_bytes 2.4612864e+07
# HELP process_start_time_seconds Start time of the process since unix epoch in seconds.
# TYPE process_start_time_seconds gauge
process_start_time_seconds 1.57280829897e+09
# HELP process_cpu_seconds_total Total user and system CPU time spent in seconds.
# TYPE process_cpu_seconds_total counter
process_cpu_seconds_total 72.28
# HELP process_open_fds Number of open file descriptors.
# TYPE process_open_fds gauge
process_open_fds 53.0
# HELP process_max_fds Maximum number of open file descriptors.
# TYPE process_max_fds gauge
process_max_fds 1024.0
# HELP hawkups_ups_brand Brand of the UPS
# TYPE hawkups_ups_brand gauge
hawkups_ups_brand{brand="American Power Conversion"} 1.0
# HELP hawkups_ups_runtime Current battery runtime in seconds.
# TYPE hawkups_ups_runtime gauge
hawkups_ups_runtime 5220.0
# HELP hawkups_ups_model Model of the UPS
# TYPE hawkups_ups_model gauge
hawkups_ups_model{model="Back-UPS RS 1500G"} 1.0
```

## Donate
I maintain this project during my free time and any donations would help me continue this project! I accept donations via PayPal through [here](https://paypal.me/adambro).
