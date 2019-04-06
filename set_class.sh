#!/usr/bin/expect
set timeout 10

spawn btmgmt

expect "#"
sleep 1
send "add-uuid 1101 1\n"

expect "#"
sleep 1
send "class 0 0\n"

expect "#"
sleep 1
send "help\n"
sleep 1

expect "#"
sleep 1
send "exit\n"

