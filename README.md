PREPARE RASPBERRY PI ZERO W V1.1
---------

- install debian based os on pi via etcher gui app on linux
  - now we use: 2018-11-13-raspbian-stretch-lite.img
- make sure that it boots, connect pi zerow hdmi to tv, insert this sdcard power it up
  - it will show resized root file partition
  - *if this step is skipped then it wont boot*
- remove sdcard, put in pc, run gparted on the sdcard
  - expand root parition to 3500 MB
  - create a 'config' partition, small say 200 MB.
  - create a 'data' parition till the end, leave 300MB end buffer for sd card manufacturer size changes.
- setup wifi for rpi zero w for ssh:
  - run rpizerow_auto_wifi.sh (based on https://core-electronics.com.au/tutorials/raspberry-pi-zerow-headless-wifi-setup.html)
- connect pi zerow hdmi to tv, power it up - if wifi connect success it will show: my ip is: ...
- ssh into that ip: user: pi pass: raspberry

- add admin user:
sudo adduser admin
password: edl12345

- disable sudo password prompt:
sudo nano /etc/sudoers
then add this new line at the bottom:
admin ALL=(ALL) NOPASSWD: ALL

- Go through ansible_scripts/README.md

- test the pi from Android

---

DEV and build
-------------

- see also: https://github.com/alexellis/docker-arm/issues/19

- edit files here in host, git commit in host this repo
- to build enter docker container first:
  ./start_docker.sh
  cd ecodroidgps
  ./build_and_scp_to_dev.sh 1

- here in host another terminal in ../ecodroidgps_bin
  - git commit and push to master

- ssh to pi and git pull origin master (or ansible-playbook -s prepare_pi_step1.yml)
