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

time python format_on_error_and_mount.py --dev_to_dir_list /dev/mmcblk0p3:/config,/dev/mmcblk0p4:/data
exit_if_failed

mkdir -p /config/bluetooth

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

chmod 777 /data
exit_if_failed

cd /data
exit_if_failed
rm config
ln -s /config
exit_if_failed

cd $START_DIR
exit_if_failed
chmod 777 /config
exit_if_failed

date -u
python ecodroidgps.py --gps_chardev_prefix /dev/ttyACM
exit_if_failed

echo "IF CONTROL REACHES HERE MEANS PROGRAM HAS DIED/ENDED"
date -u
