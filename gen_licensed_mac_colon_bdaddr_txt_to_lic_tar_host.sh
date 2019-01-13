#!/bin/bash

exit_if_failed() {
    if [ $? -ne 0 ]; then
	echo "ABORT: Previous step failed code $?"
	exit 1
    fi
}

rm edg.lic

python gen_edg_lic.py licensed_mac_colon_bdaddr_list.txt
exit_if_failed

rm edg_lic.tar.gz
tar -czf edg_lic.tar.gz edg.lic
exit_if_failed

cp edg_lic.tar.gz edg.lic ~/web_clearevo/ROOT/
exit_if_failed

cd ~/web_clearevo/ROOT
exit_if_failed

git add edg_lic.tar.gz
exit_if_failed

git commit -a -m "new edg_lic"
exit_if_failed

git push origin master
exit_if_failed

echo "SUCCESS - file now hosted at wget http://www.clearevo.com/edg_lic.tar.gz"

