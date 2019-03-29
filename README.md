PREPARE PI
---------

- install debian based os on pi via etcher gui app on linux
- setup wifi for rpi zero w for ssh:
  - https://core-electronics.com.au/tutorials/raspberry-pi-zerow-headless-wifi-setup.html
- run gparted on the disk
  - create a 'data' parition at the end - this will be rw while root and boot will be ro later
- connect pi zerow hdmi to tv, power it up - if wifi connect success it will show: my ip is: ...
- ssh into that ip

- add admin user:
sudo adduser admin
password: edl12345

- disable sudo password prompt:
sudo nano /etc/sudoers
then add this new line at the bottom:
admin ALL=(ALL) NOPASSWD: ALL

- Go through ansible_scripts/README.md

- test the pi from Android
