#!/usr/bin/python

import subprocess
import sys
import time
import os
import logging
import logging.handlers
import argparse
import traceback
import signal
import multiprocessing as mp

"""
read input from gps chardev, keep at a central var, send input to each subprocess's tx pipe

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


##################

g_gps_data_mutex = mp.Lock()
g_gps_data = ""

def read_gps(args):
    global g_gps_data
    global g_gps_data_mutex

    print "read_gps start"
    while True:
        f = None
        try:
            print("opening gps chardev:"+args["gps_chardev"])
            f = open(args["gps_chardev"], "r")
            while True:
                gps_data = f.readline()
                print("read gps_data:", gps_data)
                if gps_data is None or gps_data == "":
                    raise Exception("gps chardev likely disconnected - try connect again")
                with g_gps_data_mutex:
                    g_gps_data = gps_data
        except Exception as e:
            print("read_gps exception: "+str(e))
            time.sleep(1)
        finally:
            if not f is None:
                f.close()
            

def write_to_bt_processes(args):
    global g_gps_data

    pass



##################


def killall_rfcomm_py():
    cmd = 'pkill -f "rfcomm.py"'
    call_bash_cmd(cmd)
    cmd = 'killall "rfcomm.py"'
    call_bash_cmd(cmd)

    
def start_bt_processes(args):

    p_nmea_to_bt_list = [] # popen vars
    nmea_to_bt_cmds = []
    for itr in range(0, args["max_bt_serial_port_count"]):
        i = itr + 1 # start at 1 for channels
        cmd = '{} -p "/ecodroidgps_serial_port_{}" -n "EcoDroidGPS Serial Port {}" -s -C {} -u "0x1101" -N /dev/rfcomm{} -W'.format(
            os.path.join(args["bluez_compassion_path"], "rfcomm.py"),
            i,
            i,
            i,
            i
        )
        nmea_to_bt_cmds.append(cmd)
        p_nmea_to_bt_list.append(None) # add placeholder for prev cmd
        
    printlog("maintain_nmea_broadcast_processes: nmea_to_bt_cmds:", nmea_to_bt_cmds)

    while(True):

        printlog("maintain_nmea_broadcast_processes: main loop start")

        for i in range(0, args["max_bt_serial_port_count"]):
            printlog("killing bt proc i {}".format(i))
            kill_popen_proc(p_nmea_to_bt_list[i])
            p_nmea_to_bt_list[i] = None # dont re-kill same thing
            
        killall_rfcomm_py() # somehow some rfcomm.py still survive above

        maintain_bt_procs(args, nmea_to_bt_cmds, p_nmea_to_bt_list)
        
        # end of while loop

    return


def maintain_bt_procs(args, nmea_to_bt_cmds, p_nmea_to_bt_list):
    
    while(True):
        
        bt_list_len = len(p_nmea_to_bt_list)
        for i in range(0, bt_list_len):
            bt_proc = p_nmea_to_bt_list[i]
            if bt_proc is None:
                printlog("watch_main_procs_and_maintain_bt_procs: ok bt_proc i {} is None - start it".format(i))
                # start it
                cmd = nmea_to_bt_cmds[i]
                p_nmea_to_bt_list[i] = popen_bash_cmd(cmd)
                if not p_nmea_to_bt_list[i] is None:
                    printlog("started pid:"+str(p_nmea_to_bt_list[i].pid))
                continue

            # bt_proc is not None - check the proc ret code
            bt_proc_ret = bt_proc.poll()
            if bt_proc_ret is None:
                printlog("watch_main_procs_and_maintain_bt_procs: ok bt_proc i {} is running".format(i))
                continue
            else:
                # bt_proc_ret is not None - means process has ended - start it
                printlog("watch_main_procs_and_maintain_bt_procs: ok bt_proc i {} ended - restart it".format(i))
                cmd = nmea_to_bt_cmds[i]
                p_nmea_to_bt_list[i] = popen_bash_cmd(cmd)
                
            # end of for loop each bt_proc

        printlog("watch_main_procs_and_maintain_bt_procs: everything ok - sleep 5 secs...")
        time.sleep(5)
        # end of while loop

    raise Exception("ASSERTION FAILED: watch_main_procs_and_maintain_bt_procs end of func control should never reach here")
    return -3

"""
def get_bash_cmdlist(cmd):
    return ['/bin/bash', '-c', str(cmd)]
"""

def call_bash_cmd(cmd):
    #cmd = get_bash_cmdlist(cmd)
    printlog("call cmd:", cmd)
    return subprocess.call(cmd, shell=True, executable='/bin/bash')


def popen_bash_cmd(cmd):
    printlog("popen cmd:", cmd)
    return subprocess.Popen(cmd, shell=True, executable='/bin/bash')


def kill_popen_proc(proc):
    if proc is None:
        pass
    else:
        try:
            cmd = "pkill -INT -P {}".format(proc.pid) # sent INT to all with parent -P
            call_bash_cmd(cmd)
            time.sleep(0.2)
            proc.kill()
            proc.terminate()
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
args["max_bt_serial_port_count"] = int(args["max_bt_serial_port_count"]) # parse to int

args["bluez_compassion_path"] = os.path.join(get_module_path(), "bluez-compassion")
if not os.path.isdir(args["bluez_compassion_path"]):
    printlog("ABORT: failed to find 'bluez-compassion' folder in current module path:", get_module_path(), "please clone from http://github.com/ykasidit/bluez-compassion")
    exit(-1)

prepare_bt_device(args)
printlog("prepare_bt_device done...")

while(True):
    print "starting ecodroidgps_server main loop - gps chardev:", args["gps_chardev"]

    try:
        # now check if we can access the chardev
        if not os.path.exists(args["gps_chardev"]):
            raise Exception("WARNING: specified gps_chardev file does NOT exist: "+args["gps_chardev"])

        gps_reader_proc = None
        #bt_maintainer_proc = mp.Process(target=start_bt_processes, args=(args,) )
        #bt_writer_proc = mp.Process(target=write_to_bt_processes, args=(args,) )
        
        while (True):
            print("gps_reader_proc:", gps_reader_proc)
            if gps_reader_proc != None and gps_reader_proc.is_alive():
                print "gps_reader_proc check ok"
            else:
                print("gps_reader_proc is not alive - (re)start it")
                gps_reader_proc = mp.Process(target=read_gps, args=(args,) )
                gps_reader_proc.start()
                
            time.sleep(5)
            
    except:
        type_, value_, traceback_ = sys.exc_info()
        exstr = str(traceback.format_exception(type_, value_, traceback_))
        printlog("WARNING: main loop got exception - retry after 5 secs - exception:", exstr)
        time.sleep(5)

print("ecodroidgps_server - terminating")
exit(0)
