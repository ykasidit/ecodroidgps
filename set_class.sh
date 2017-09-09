#!/usr/bin/expect
set timeout 10

spawn ../bluez/tools/btmgmt

expect "#"

send "add-uuid 1101 1\n"

expect "#"

send "class 0 0\n"

expect "#"

send "exit\n"
