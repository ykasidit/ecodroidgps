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

Please go through README.md in ansible_scripts folder.

Testing
-------

`make clean`
`make`

If you get permission errors then you might have to:

`sudo make`


Running
-------

`sudo ./start.sh`

LICENSE
-------

This project is released under the same license as 'BlueZ' - GNU GPL - Please see the LICENSE file.

AUTHORS
-------

Kasidit Yusuf
