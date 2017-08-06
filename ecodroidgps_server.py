#!/usr/bin/python

import subprocess
import sys
import time
import os
import logging
import logging.handlers
import argparse
import traceback

"""
read and broadcast like:

https://serverfault.com/questions/747980/simpliest-unix-non-blocking-broadcast-socket

Found solution at similar answer https://unix.stackexchange.com/questions/195880/socat-duplicate-stdin-to-each-connected-client. Socat seems can't work that way but ncat from nmap package does.

It works same for unix socket:

% mkfifo /tmp/messages-in
% exec 8<>/tmp/messages-in  # hold the fifo open
% ncat -l -U /tmp/messages-out -k --send-only < /tmp/messages-in

% echo "test" > /tmp/messages-in

% # every client connected to /tmp/messages-out will get "test"
message

---

sudo cat /dev/ttyACM0 > /tmp/messages-in
nc -U /tmp/messages-out | sudo python rfcomm.py -p "/my_serial_port" -n "Serial Port" -s -C 1 -u "0x1101"
"""

def get_module_path():
    return os.path.realpath(
        os.path.join(os.getcwd(), os.path.dirname(__file__))
    )

logger = logging.getLogger('ecodroidgps_server')
logger.setLevel(logging.DEBUG)
handler = logging.handlers.SysLogHandler(address = '/dev/log')
logger.addHandler(handler)


def printlog(*s):
    s = str(s)
    logger.info(s)
    print(s)


def parse_cmd_args():
    parser = argparse.ArgumentParser(#description=infostr, usage=usagestr,
    formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument('--gps_chardev',
                        help="character device path like /dev/ttyACM0", required=True)

    parser.add_argument('--max_bt_serial_port_count',
                        help="set number of max bt serial ports to create",
                        required=False,
                        default=7)

    return vars(parser.parse_args())


def maintain_nmea_broadcast_processes(args, nmea_in_pipe, bcast_nmea_out_pipe):

    # popen vars
    p_netcat = None
    p_nmea_in = None
    p_nmea_to_bt_list = []

    netcat_bcast_cmd = "ncat -l -U {} -k --send-only < {}".format(bcast_nmea_out_pipe, nmea_in_pipe)
    printlog("maintain_nmea_broadcast_processes: netcat_bcast_cmd:", netcat_bcast_cmd)
    
    nmea_in_cmd = "cat {} > {}".format(args["gps_chardev"], nmea_in_pipe)
    printlog("maintain_nmea_broadcast_processes: nmea_in_cmd:", nmea_in_cmd)

    nmea_to_bt_cmds = []
    for i in range(0, args["max_bt_serial_port_count"]):
        cmd = 'nc -U {} | python {} -p "/ecodroidgps_serial_port_{}" -n "EcoDroidGPS Serial Port {}" -s -C {} -u "0x1101"'.format(
            bcast_nmea_out_pipe,
            os.path.join(args["bluez_compassion_path"], "rfcomm.py"),
            i,
            i,
            i                
        )
        nmea_to_bt_cmds.append(cmd)
        p_nmea_to_bt_list.append(None) # add placeholder
        
    printlog("maintain_nmea_broadcast_processes: nmea_to_bt_cmds:", nmea_to_bt_cmds)

    while(True):
        printlog("maintain_nmea_broadcast_processes: main loop start")

        # kill all prev processes
        kill_popen_proc(p_netcat)
        kill_popen_proc(p_nmea_in)
        for i in range(0, args["max_bt_serial_port_count"]):
            kill_popen_proc(p_nmea_to_bt_list[i])

        prepare_bt_device(args)
        printlog("prepare bt device done...")

            
        # start netcat proc
        p_netcat = popen_bash_cmd(netcat_bcast_cmd)
        time.sleep(1)

        # start nmea cat proc
        p_nmea_in = popen_bash_cmd(nmea_in_cmd)
        time.sleep(1)
        
        watch_main_procs_and_maintain_bt_procs(args, [p_netcat, p_nmea_in], nmea_to_bt_cmds, p_nmea_to_bt_list)
        
        # end of while loop

    return


def watch_main_procs_and_maintain_bt_procs(args, p_main_list, nmea_to_bt_cmds, p_nmea_to_bt_list):
    
    while(True):
        
        for proc in p_main_list:
            if proc is None:
                printlog("watch_main_procs_and_maintain_bt_procs: one main proc is None return so caller can cleanup/restart")
                return -1
            pret = proc.poll()
            if pret is None:
                pass # ok proc running
            else:
                printlog("watch_main_procs_and_maintain_bt_procs: one main proc has exit:",proc,"- return so caller can cleanup/restart")
                return -2
            
        bt_list_len = len(p_nmea_to_bt_list)
        for i in range(0, bt_list_len):
            bt_proc = p_nmea_to_bt_list[i]
            if bt_proc is None:
                printlog("watch_main_procs_and_maintain_bt_procs: ok bt_proc i {} is None - start it".format(i))
                # start it
                cmd = nmea_to_bt_cmds[i]
                p_nmea_to_bt_list[i] = popen_bash_cmd(cmd)
                continue

            # bt_proc is not None - check the proc ret code
            bt_proc_ret = bt_proc.poll()
            if bt_proc_ret is None:
                printlog("watch_main_procs_and_maintain_bt_procs: ok bt_proc i {} is running".format(i))
                continue
            else:
                # bt_proc_ret is not None - means process has ended - start it
                printlog("watch_main_procs_and_maintain_bt_procs: ok bt_proc i {} ended - restart it".format(i))
                p_nmea_to_bt_list[i] = popen_bash_cmd(cmd)
                
            # end of for loop each bt_proc

        printlog("watch_main_procs_and_maintain_bt_procs: everything ok - sleep 5 secs...")
        time.sleep(5)
        # end of while loop

    raise Exception("ASSERTION FAILED: watch_main_procs_and_maintain_bt_procs end of func control should never reach here")
    return -3


def get_bash_cmdlist(cmd):
    return ['/bin/bash', '-c', cmd]


def call_bash_cmd(cmd):
    cmd = get_bash_cmdlist(cmd)
    printlog("call cmd:", cmd)
    return subprocess.call(cmd, shell=False)


def popen_bash_cmd(cmd):
    cmd = get_bash_cmdlist(cmd)
    printlog("popen cmd:", cmd)
    return subprocess.Popen(cmd, shell=False)


def kill_popen_proc(proc):
    if proc is None:
        pass
    else:
        try:
            proc.kill()
        except Exception as e:
            type_, value_, traceback_ = sys.exc_info()
            exstr = str(traceback.format_exception(type_, value_, traceback_))
            printlog("WARNING: kill_popen_proc proc ", proc, "got exception:", exstr)
    return


g_prev_edl_agent_proc = None
def prepare_bt_device(args):
    global g_prev_edl_agent_proc
    # power the bt dev
    cmd = os.path.join(
        args["bluez_compassion_path"]
        ,"hciconfig"
    ) + " -a hci0 up"
    ret = call_bash_cmd(cmd)
    if ret != 0:
        raise Exception("failed to prepare bt device: cmd failed: "+cmd)

    # set discov
    cmd = os.path.join(
        args["bluez_compassion_path"]
        ,"hciconfig"
    ) + " -a hci0 piscan"
    ret = call_bash_cmd(cmd)
    if ret != 0:
        raise Exception("failed to prepare bt device: cmd failed: "+cmd)

    # set paiarable
    cmd = os.path.join(
        args["bluez_compassion_path"]
        ,"hciconfig"
    ) + " -a hci0 pairable 1"
    ret = call_bash_cmd(cmd)
    if ret != 0:
        raise Exception("failed to prepare bt device: cmd failed: "+cmd)

    # start the auto-pair agent
    kill_popen_proc(g_prev_edl_agent_proc)
    cmd = os.path.join(
        args["bluez_compassion_path"]
        ,"edl_agent"
    )
    g_prev_edl_agent_proc = popen_bash_cmd(cmd)
    if g_prev_edl_agent_proc is None:
        printlog("WARNING: edl_agent proc is None! likely cannot pair devices now!")
    else:
        edl_agent_poll_ret = g_prev_edl_agent_proc.poll()
        printlog("NOTE: edl_agent proc poll() (None means good - it is running) ret:", edl_agent_poll_ret)

    return


    
############### MAIN

args = parse_cmd_args()
args["bluez_compassion_path"] = os.path.join(get_module_path(), "bluez-compassion")
if not os.path.isdir(args["bluez_compassion_path"]):
    printlog("ABORT: failed to find 'bluez-compassion' folder in current module path:", get_module_path(), "please clone from http://github.com/ykasidit/bluez-compassion")
    exit(-1)
    
nmea_in_pipe = "/tmp/edg_nmea_bcast_in"
bcast_nmea_out_pipe = "/tmp/edg_nmea_bcast_out"
tmp_fd = 33

while(True):
    print "starting ecodroidgps_server main loop - gps chardev:", args["gps_chardev"]

    tmp_fd += 1
    try:
        try:
            os.remove(nmea_in_pipe)
        except:
            pass
        try:
            os.remove(bcast_nmea_out_pipe)
        except:
            pass

        cmd = "mkfifo "+nmea_in_pipe
        ret = call_bash_cmd(cmd)
        if ret != 0:
            raise Exception("failed to prepare nmea broadcaster: cmd failed: "+cmd)

        cmd = "exec {}<>{}".format(tmp_fd, nmea_in_pipe)
        ret = call_bash_cmd(cmd)
        if ret != 0:
            raise Exception("failed to prepare nmea broadcaster: cmd failed: "+cmd)

        # now check if we can access the chardev
        if not os.path.exists(args["gps_chardev"]):
            raise Exception("WARNING: specified gps_chardev file does NOT exist: "+args["gps_chardev"])

        printlog("nmea broadcasters ready - starting nmea reader and bt serial processes...")
        maintain_nmea_broadcast_processes(args, nmea_in_pipe, bcast_nmea_out_pipe)

    except:
        type_, value_, traceback_ = sys.exc_info()
        exstr = str(traceback.format_exception(type_, value_, traceback_))
        printlog("WARNING: main loop got exception - retry after 5 secs - exception:", exstr)
        time.sleep(5)


exit(0)
