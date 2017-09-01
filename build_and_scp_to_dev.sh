#!/bin/bash

exit_if_failed() {
    if [ $? -ne 0 ]; then
	echo "ABORT: Previous step failed"
	exit 1
    fi
}

./build.sh
exit_if_failed

rm -f edg_release*.tar.gz

DATE=$(date +%d%m%y)
DATED_TAR_NAME="edg_release_${DATE}.tar.gz"

tar -czf $DATED_TAR_NAME *.so ecodroidgps.py bt_spp_profile.py

echo created $DATED_TAR_NAME done...
