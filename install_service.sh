#!/bin/bash

exit_if_failed() {
    if [ $? -ne 0 ]; then
	echo "ABORT: Previous step failed with code $?"
	exit 1
    fi
}

systemctl stop ecodroidgps
systemctl disable ecodroidgps

rm -f /etc/systemd/system/ecodroidgps.service

cp ecodroidgps.service /etc/systemd/system/
exit_if_failed

systemctl daemon-reload
exit_if_failed

systemctl enable ecodroidgps
exit_if_failed

systemctl start ecodroidgps
exit_if_failed
