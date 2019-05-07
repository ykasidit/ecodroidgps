#!/usr/bin/expect
set timeout 4

spawn btmgmt

expect "#"
send "add-uuid 1101 1\n"

expect "#"
send "class 0 0\n"

expect "#"
send "help\n"

expect "#"
send "exit\n"

