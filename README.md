About
-----

Turns a GNU\Linux computer (or RPi, Orange Pi etc) into a Bluetooth GPS/GNSS device - supplying location from USB GPS device to mobile phones/tablets over Bluetooth.

The official ready-to-use device can be purchased from the [official EcoDroidGPS page](https://www.clearevo.com/ecodroidgps/) - its device ssh login is:
`ssh edl@<ip>`
(user: edl)
password:
`clearevoecodroidgps`

You can guess its IP from your server or something like below on GNU/Linux systems in case your PC's IP is 192.168.1.*
`nmap -sn 192.168.1.0/24`


Install from scratch
--------------------







Running
-------

`sudo ./start.sh`

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

LICENSE
-------

This project is released under the same license as 'BlueZ' - GNU GPL - Please see the LICENSE file.

AUTHORS
-------

Kasidit Yusuf
