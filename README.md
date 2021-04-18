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

Manual test
-----------

- connect from bluetooth gnss app > serial mode must work
- connect from bluetooth gnss app > broadcast mode must work
- disconnect usb gps, reconnect - must still work - no need reconnect from app and time must move again
- disconnect usb bluetooth, reconnect - must still work - needs reconnect from app - auto reconnect from app must work
- test long duration logging must have no skips/freezes in nmea/gpx time
- ublox fix type, accuracay must show in app if using ublox usb gps
- rtk ntrip mode must work from app to over this sw through to ardusimple ublox f9

LICENSE
-------

This project is released under the same license as 'BlueZ' - GNU GPL - Please see the LICENSE file.

AUTHORS
-------

Kasidit Yusuf

TODO
----

- patch belson always printing during spp: 2021-04-18 12:19:55,404 WARNING -         linux_adapter.py:276 -                 _on_data(): TODO: Unhandled HCI packet, type=2

