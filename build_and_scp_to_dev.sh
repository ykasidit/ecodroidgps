#!/bin/bash

exit_if_failed() {
    if [ $? -ne 0 ]; then
	echo "ABORT: Previous step failed"
	exit 1
    fi
}

if [ -z $1 ]; then
    echo "please specify target ip as first arg"
    exit 1
fi

./build.sh
exit_if_failed

cp *.sh ../ecodroidgps_bin
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
rm -f ../edg_release*.tar.gz

DATE=$(date +%d%m%y)
DATED_TAR_NAME="edg_release_${DATE}.tar.gz"

cd ../ecodroidgps_bin
tar -czf ../$DATED_TAR_NAME *
cd ..
echo created $DATED_TAR_NAME done...

SSH_PASS="alarm"
SSH_USER="alarm"
echo "scp to dev: $1 password $SSH_PASS"
CMD="sshpass -p $SSH_PASS scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null $DATED_TAR_NAME $SSH_USER@$1:/overlay/lower/home/alarm"
echo "CMD: $CMD"
bash -c "$CMD"
exit_if_failed
echo "success - scp ret: $?"

sshpass -p "$SSH_PASS" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null $SSH_USER@$1 "cd /overlay/lower/home/alarm ; rm -rf edg ; mkdir edg && cd edg && tar -xzf ../$DATED_TAR_NAME ; rm -f edg_release*"
exit_if_failed
echo "success - ssh extract ret: $?"
