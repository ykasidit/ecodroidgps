#!/bin/bash

date -u

exit_if_failed() {
    if [ $? -ne 0 ]; then
	echo "ABORT: Previous step failed code $?"
	exit 1
    fi
}

START_DIR=$(pwd)

rm -f *.pyc

time systemctl restart bluetooth
exit_if_failed

time systemctl is-active bluetooth
exit_if_failed

#systemctl is-active mosquitto
#exit_if_failed

NAME=`cat /config/name.txt || echo 'EcoDroidGPS Bluetooth GPS'`
time cd ../bluez-compassion ; rm -f *.pyc ; ./hciconfig -a hci0 name "$NAME"

cd $START_DIR
exit_if_failed

date -u
python3 ecodroidgps.py --gps_chardev_prefix /dev/ttyACM
exit_if_failed

echo "IF CONTROL REACHES HERE MEANS PROGRAM HAS DIED/ENDED"
date -u
