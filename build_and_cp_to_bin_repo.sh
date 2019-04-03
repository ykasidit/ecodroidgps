#!/bin/bash

exit_if_failed() {
    if [ $? -ne 0 ]; then
	echo "ABORT: Previous step failed"
	exit 1
    fi
}

./build.sh
exit_if_failed

cp ex_nmea.txt ../ecodroidgps_bin
cp ex_nmea2.txt ../ecodroidgps_bin
cp nmea.txt ../ecodroidgps_bin
exit_if_failed
rm ../ecodroidgps_bin/lic*.txt
cp *.service ../ecodroidgps_bin
exit_if_failed
cp install_service.sh ../ecodroidgps_bin
exit_if_failed
cp start.sh ../ecodroidgps_bin
exit_if_failed
cp set_class.sh ../ecodroidgps_bin
exit_if_failed
cp *.so ../ecodroidgps_bin
exit_if_failed
cp *.py ../ecodroidgps_bin
exit_if_failed
rm ../ecodroidgps_bin/gen_edg_lic.py
exit_if_failed
rm ../ecodroidgps_bin/gen_edg_0_lic.py
exit_if_failed
rm ../ecodroidgps_bin/setup.py
exit_if_failed
rm ../ecodroidgps_bin/*.pyc
