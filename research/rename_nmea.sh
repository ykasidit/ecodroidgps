#!/bin/bash

for n in nmea/nmea*.xz ; do
    d=$(
	xzgrep GNRMC $n |
	    grep -v ,,,,,,,,,, |
	    fgrep '*' |
	    tail -1  |
	    awk -F, '{
		t=$2; d=$10; 
		if (t && d) printf "20%0s-%s-%s_%s.%s.%s\n", \
				substr(d,5,2),substr(d,3,2),substr(d,1,2), \
				substr(t,1,2),substr(t,3,2),substr(t,5,2)
	    }'
     )
    [ -n "$d" ] && mv -vi $n nmea/evo_$d.nmea.xz < /dev/null

done
