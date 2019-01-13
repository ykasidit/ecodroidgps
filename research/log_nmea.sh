#!/bin/bash

cd /ecodroidlink_data/hk || exit 1

( xz nmea/*.nmea ; ./rename_nmea.sh ) &

while sleep 10 ; do sync ; done &

while sleep 1 ; do
    [ -r /dev/ttyACM0 ] || continue
    pid=$( ps hlp $( pgrep -f ecodroidgps ) | awk '$4==1{next}{print $3}' )
    kill -0 $pid || exit 2
done

N=$( cat N )
let N++
echo $N > N

strace -fp $pid -e read 2>&1  |
    awk -F\" '
{
sub("\\\\n","\n",$2) 
sub("\\\\r","",$2)
printf $2
}' > nmea/nmea-$N.nmea
