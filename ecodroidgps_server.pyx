#!/usr/bin/python

import subprocess
import sys
import time
import os
import logging.handlers
import argparse
import traceback
import multiprocessing as mp
import gobject
import dbus.mainloop.glib
import edg_gps_reader
import bt_spp_profile
import fcntl, socket, struct
import hashlib


def getHwAddr(ifname):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    info = fcntl.ioctl(s.fileno(), 0x8927,  struct.pack('256s', ifname[:15]))
    return ':'.join(['%02x' % ord(char) for char in info[18:24]])

infostr = "EcoDroidGPS v1.1 Copyright (c) 2017 Kasidit Yusuf. All rights reserved.\nEcoDroidGPS 'Bluetooth GPS' devices are available at: www.ClearEvo.com"

"""
read input from gps chardev, keep at a central var, send input to each subprocess's tx pipe

"""

# https://stackoverflow.com/questions/19225188/what-method-can-i-use-instead-of-file-in-python
import inspect
if not hasattr(sys.modules[__name__], '__file__'):
    __file__ = inspect.getfile(inspect.currentframe())

###    

def get_module_path():
    return os.path.realpath(
        os.path.join(os.getcwd(), os.path.dirname(__file__))
    )

g_logger = None
def init_logger():
    global g_logger

    try:
        g_logger = logging.getLogger('ecodroidgps_server')
        g_logger.setLevel(logging.DEBUG)
        handler = logging.handlers.SysLogHandler(address = '/dev/log')
        g_logger.addHandler(handler)
    except Exception as e:
        print "WARNING: init_logger() exception: ", str(e)

init_logger()
        
def printlog(*s):
    global g_logger
    s = str(s)
    try:
        g_logger.info(s)
    except:
        pass
    print(s)


def parse_cmd_args():
    parser = argparse.ArgumentParser(description=infostr,# usage=usagestr,
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

# will be removed MAX_GPS_DATA_QUEUE_LEN/4 when qsize() is MAX_GPS_DATA_QUEUE_LEN/2

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

    cmd = os.path.join(
        args["bluez_compassion_path"]
        ,"hciconfig"
    ) + " -a hci0 down"
    ret = call_bash_cmd(cmd)

    
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


def check_lic(mac_addr):
    print "check_lic: mac_addr:", mac_addr
    shaer = hashlib.sha1()
    shaer.update("edg")
    shaer.update(mac_addr+":edg")
    shaer.update("edg")
    this_sha = shaer.hexdigest()
    #print "this_sha:", this_sha
    licfp = os.path.join(get_module_path(), "edg_0.lic")
    lic_pass = False
    with open(licfp, "r") as f:        
        lic_lines = f.readlines()
        i_lic_lines = range(len(lic_lines))
        for i in i_lic_lines:
            if i % 2 == 1:
                if lic_lines[i].strip() == this_sha:
                    lic_pass = True

    if lic_pass:
        print "lic ok"
        return 0
    else:
        print "INVALID LICENSE - ABORT"
        exit(-3)
        return -3
    
    
############### MAIN

print infostr

mac_addr = None
try:
    mac_addr = getHwAddr("eth0")
except:
    mac_addr = getHwAddr("wlp4s0")

if mac_addr is None:
    print "INVALID: failed to get mac_addr"
    exit(2)

ret = check_lic(mac_addr)
if ret == 0:
    pass
else:
    exit(ret)

args = parse_cmd_args()
args["max_bt_serial_port_count"] = int(args["max_bt_serial_port_count"]) # parse to int

mp_manager = mp.Manager()
q_list = [] # list of mp.Queue each holding nmea lines for a specific bt dev fd
q_list_used_indexes = mp_manager.list() # list of indices of used queues in above q_list
MAX_N_GPS_DATAQUEUES = 100
for i in range(MAX_N_GPS_DATAQUEUES):
    q_list.append(mp.Queue(maxsize=edg_gps_reader.MAX_GPS_DATA_QUEUE_LEN))

gps_data_queues_dict = {
    "q_list":q_list,
    "q_list_used_indexes":q_list_used_indexes
}

for k in gps_data_queues_dict:
    print("gps_data_queues_dict key: {} valtype {}".format(k, type(gps_data_queues_dict[k])))

args["bluez_compassion_path"] = os.path.join(get_module_path(), "bluez-compassion")
if not os.path.isdir(args["bluez_compassion_path"]):
    printlog("ABORT: failed to find 'bluez-compassion' folder in current module path:", get_module_path(), "please clone from http://github.com/ykasidit/bluez-compassion")
    exit(-1)

prepare_bt_device(args)
printlog("prepare_bt_device done...")
dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
system_bus = dbus.SystemBus()
bluez_profile_manager = dbus.Interface(
    system_bus.get_object("org.bluez",
                   "/org/bluez"
    )
    ,
    "org.bluez.ProfileManager1"
)
edgps_dbus_path = "/ecodroidgps"
bt_spp = bt_spp_profile.Profile(system_bus, edgps_dbus_path)
gobject_main_loop = gobject.MainLoop()
vars_for_bt_spp = {}
vars_for_bt_spp["gps_data_queues_dict"] = gps_data_queues_dict
vars_for_bt_spp["gobject_main_loop"] = gobject_main_loop
bt_spp.set_vars_dict(vars_for_bt_spp)

print "starting ecodroidgps_server main loop - gps chardev:", args["gps_chardev"]
gps_reader_proc = mp.Process(
    target=edg_gps_reader.read_gps,
    args=(args["gps_chardev"], gps_data_queues_dict)
)
gps_reader_proc.start()

bluez_register_profile_options = {
    "AutoConnect": True,
    "Name": "EcoDroidGPS Serial Port",
    "Role": "server",
    "Channel": dbus.UInt16(1)
}
serial_port_profile_uuid = "0x1101"

bluez_profile_manager.RegisterProfile(edgps_dbus_path, serial_port_profile_uuid, bluez_register_profile_options)
print "ecodroidgps bluetooth profile registered - waiting for incoming connections..."
gobject_main_loop.run()

print("ecodroidgps_server - terminating")
exit(0)
