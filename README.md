PREPARE RASPBERRY PI ZERO W V1.1
---------

- install debian based os on pi via etcher gui app on linux
  - now we use: 2018-11-13-raspbian-stretch-lite.img
- make sure that it boots, connect pi zerow hdmi to tv, insert this sdcard power it up
  - it will show resized root file partition
  - *if this step is skipped then it wont boot*
- remove sdcard, put in pc, run gparted on the sdcard
  - expand root parition to 3500 MB
    - create a 'config' parition with size 200 MB.
    - create a 'data' parition till the end, leave 300 MB end buffer for sd card manufacturer size changes.
- setup wifi for rpi zero w for ssh:
  - run rpizerow_auto_wifi.sh (based on https://core-electronics.com.au/tutorials/raspberry-pi-zerow-headless-wifi-setup.html)
- connect pi zerow hdmi to tv, power it up - if wifi connect success it will show: my ip is: ...
- test ssh into that ip: user: pi pass: raspberry
- put that ip where you successfully ssh into ansible_scripts/hosts file under pi heading
- Go through ansible_scripts/README.md
- test the pi connect bt serial and ble from Android phone

---

DEV and build
-------------

- see also: https://github.com/alexellis/docker-arm/issues/19

- edit files here in host, git commit in host this repo
- to build enter docker container first:
  ./start_docker.sh
  cd ~/ecodroidgps
  ./build_and_cp_to_bin_repo.sh

- here in host another terminal in ../ecodroidgps_bin
  - git commit and push to master

- ssh to pi and git pull origin master (or ansible-playbook -s prepare_pi_step1.yml)
