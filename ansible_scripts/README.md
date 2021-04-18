HOWTO RUN ANSIBLE SCRIPTS TO SETUP ECODROIDGPS ON A REMOTE SINGLE BOARD LINUX COMPUTER
------------------------------------------------------------------------

- install your os (we use armbian on orange pi zero lts)
- ssh to it for the first time, setup defaul ssh user/pass
- get ip of device (you can get all local device ips with something like `nmap -sn 192.168.1.0/24`), replace ip under `[pi]` section in `hosts` file, and also ssh user, password under `[all:vars]` section 
- run through each step like:
ansible-playbook prepare_pi_step0.yml
<skip step1 if you dont need mqtt and ble location and navigation profile>
ansible-playbook prepare_pi_step2.yml
...
