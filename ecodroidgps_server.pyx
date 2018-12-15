#!/usr/bin/python

import subprocess
import sys
import time
import os
import logging.handlers
import argparse
import traceback
import multiprocessing
try:
    import gobject
except:
    from gi.repository import GObject as gobject
    
import dbus.mainloop.glib
import edg_gps_reader
import bt_spp_profile
import fcntl, socket, struct
import hashlib
import ctypes
import pandas as pd

import edg_utils
import edg_gps_parser

# make sure bluez-5.46 is in folder next to this folder


def get_bdaddr():
    pattern = None
    SERVICE_NAME = "org.bluez"
    ADAPTER_INTERFACE = SERVICE_NAME + ".Adapter1"
    DEVICE_INTERFACE = SERVICE_NAME + ".Device1"

    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    manager = dbus.Interface(
        bus.get_object("org.bluez", "/"),
	"org.freedesktop.DBus.ObjectManager"
    )
    objects = manager.GetManagedObjects()

    adapter_path = None
    for path, ifaces in objects.iteritems():
        adapter = ifaces.get(ADAPTER_INTERFACE)
        if adapter is None:
            continue
        if not pattern or pattern == adapter["Address"] or path.endswith(pattern):
            obj = bus.get_object(SERVICE_NAME, path)
            adapter_path = dbus.Interface(obj, ADAPTER_INTERFACE).object_path
            break

    if adapter_path is None:
        raise Exception("Bluetooth adapter not found")

    adapter = dbus.Interface(bus.get_object("org.bluez", adapter_path),
					"org.freedesktop.DBus.Properties")
    addr = adapter.Get("org.bluez.Adapter1", "Address").lower()
    return addr


def get_iface_addr(ifname):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    info = fcntl.ioctl(s.fileno(), 0x8927,  struct.pack('256s', ifname[:15]))
    return ':'.join(['%02x' % ord(char) for char in info[18:24]])


infostr = "EcoDroidGPS v1.1 Copyright (c) 2017 Kasidit Yusuf. All rights reserved.\nEcoDroidGPS 'Bluetooth GPS' devices are available at: www.ClearEvo.com"

"""
read input from gps chardev, keep at a central var, send input to each subprocess's tx pipe

"""


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

    parser.add_argument('--gps_chardev_prefix',
                        help="character device path like /dev/ttyACM - we will auto try all from ACM0 to ACM9 automatically", required=True)

    return vars(parser.parse_args())


##################

# will be removed MAX_GPS_DATA_QUEUE_LEN/4 when qsize() is MAX_GPS_DATA_QUEUE_LEN/2

def call_bash_cmd(cmd):
    #cmd = get_bash_cmdlist(cmd)
    printlog("call cmd:", cmd)
    #return subprocess.call(cmd, shell=True, executable='/bin/bash')
    return subprocess.call(["/bin/bash","-c",cmd], shell=False)


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


def power_on_bt_dev(args):
    cmd = os.path.join(
        args["bluez_compassion_path"]
        ,"hciconfig"
    ) + " -a hci0 up"
    ret = call_bash_cmd(cmd)
    return ret


def power_off_bt_dev(args):
    cmd = os.path.join(
        args["bluez_compassion_path"]
        ,"hciconfig"
    ) + " -a hci0 down"
    ret = call_bash_cmd(cmd)


g_prev_edl_agent_proc = None
def prepare_bt_device(args):
    global g_prev_edl_agent_proc

    ret = power_off_bt_dev(args)
    
    # power on the bt dev
    ret = power_on_bt_dev(args)
    if ret != 0:
        raise Exception("failed to prepare bt device")

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

    # **NOTE** it doesnt work in most cases - need to call it manually in terminal or in systemctl systemd service then it works
    ret = call_bash_cmd(os.path.join(edg_utils.get_module_path(), "set_class.sh"))
    print "set_class ret:", ret

    ############# start subprocess commands
    
    # start the auto-pair agent    
    edl_agent_cmd = os.path.join(
        args["bluez_compassion_path"]
        ,"edl_agent"
    )

    bluez_gatt_server_py_path = os.path.abspath(
        os.path.join(
            edg_utils.get_module_path(),
            os.pardir,
            "bluez-gatt-server",
            "bluez-gatt-server.py"
        )
    )

    
    ln_feature_mask_dump_str = edg_utils.gen_edg_ln_feature_bitmask_hex_dump_str()
    print "bitmask_str:", ln_feature_mask_dump_str

    chrc_df = pd.DataFrame(
        {
            "assigned_number": [
                "0x2A6A",
                "0x2A67"
            ],
            "mqtt_url": [
                "mqtt://localhost:1883/lnf",
                "mqtt://localhost:1883/las",                
            ],
            "default_val_hexdump": [
                ln_feature_mask_dump_str,
                "0000"
            ]
        }
    )

    chrc_csv_path = os.path.join(
        "/tmp",
        "ln_chrc.csv"
    )

    chrc_df.to_csv(chrc_csv_path, index=False)
    chmodret = os.system("chmod 644 {}".format(chrc_csv_path))
    
    ble_lnp_cmd = "python {} --service_assigned_number 0x1819 --characteristics_table_csv {}".format(
        bluez_gatt_server_py_path,
        chrc_csv_path
    )

    p = multiprocessing.Process( target=keep_cmds_running, args=([edl_agent_cmd, ble_lnp_cmd],) )
    p.start()

    # TODO start the ble service

    ############ done started subprocesses

    
    printlog("prepare_bt_device done...")
    return


def keep_cmds_running(cmds):
    running_cmd_to_proc_dict = {}
    while True:
        printlog("keep_cmds_running: checking cmds...")
        try:
            for cmd in cmds:
                old_proc = None
                old_proc_ret = None
                if cmd in running_cmd_to_proc_dict:
                    old_proc = running_cmd_to_proc_dict[cmd]
                    if old_proc is not None:
                        old_proc_ret = old_proc.poll()
                if old_proc is None or old_proc_ret is not None:
                    kill_popen_proc(old_proc)
                    if old_proc is not None:
                        printlog("WARNING: keep_cmds_running: old_proc for cmd {} died with ret code {} - restarting it...".format(cmd, old_proc_ret))
                    printlog("keep_cmds_running: starting new_proc for cmd {}".format(cmd))
                    new_proc = popen_bash_cmd(cmd)
                    running_cmd_to_proc_dict[cmd] = new_proc
                else:
                    printlog("keep_cmds_running: ok cmd still running: {}".format(cmd))
                        
        except:
            type_, value_, traceback_ = sys.exc_info()
            exstr = str(traceback.format_exception(type_, value_, traceback_))
            printlog("WARNING: keep_cmds_running got exception:", exstr)
        time.sleep(5)
        

def stage0_check(mac_addr, bdaddr):
    print "stage0 mac_addr:", mac_addr
    shaer = hashlib.sha1()
    shaer.update("edg")
    shaer.update(mac_addr+":"+bdaddr+":edg_kub")
    shaer.update("edg")
    this_sha = shaer.hexdigest()
    #print "this_sha:", this_sha
    licfp = "/data/edg.lic"
    lic_pass = False
    with open(licfp, "r") as f:        
        lic_lines = f.readlines()
        i_lic_lines = range(len(lic_lines))
        for i in i_lic_lines:
            if i % 2 == 1:
                if lic_lines[i].strip() == this_sha:
                    lic_pass = True

    if lic_pass:
        print "startup stage0 check ok"
        return 0
    else:
        print "startup stage0 check failed code: -3 - please contact or get a new EcoDroidGPS unit at www.ClearEvo.com"
        exit(-3)
        return -3

    
def register_bluez_dbus_profile(shared_gps_data_queues_dict):
    
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
    vars_for_bt_spp["shared_gps_data_queues_dict"] = shared_gps_data_queues_dict
    vars_for_bt_spp["gobject_main_loop"] = gobject_main_loop
    bt_spp.set_vars_dict(vars_for_bt_spp)

    bluez_register_profile_options = {
        "AutoConnect": True,
        "Name": "EcoDroidGPS Serial Port",
        "Role": "server",
        "Channel": dbus.UInt16(1)
    }
    serial_port_profile_uuid = "0x1101"

    bluez_profile_manager.RegisterProfile(edgps_dbus_path, serial_port_profile_uuid, bluez_register_profile_options)
    print "ecodroidgps bluetooth profile registered - waiting for incoming connections..."
    
    return gobject_main_loop


def alloc_gps_data_queues_dict():    
    q_list = [] # list of multiprocessing.Queue each holding nmea lines for a specific bt dev fd
    q_list_used_indexes_mask = multiprocessing.RawValue(ctypes.c_uint32, 0)
    q_list_used_indexes_mask_mutex = multiprocessing.Lock()

    MAX_N_GPS_DATAQUEUES = 32 # 32 bits in ctypes.c_uint32 mask above
    for i in range(MAX_N_GPS_DATAQUEUES):
        q_list.append(multiprocessing.Queue(maxsize=edg_gps_reader.MAX_GPS_DATA_QUEUE_LEN))

    return {
        "q_list":q_list,
        "q_list_used_indexes_mask":q_list_used_indexes_mask,
        "q_list_used_indexes_mask_mutex":q_list_used_indexes_mask_mutex,
    }


############### MAIN

def main():

    print "hello"

    print infostr

    args = parse_cmd_args()

    # clone/put bluez_compassion in folder next to this folder
    args["bluez_compassion_path"] = os.path.abspath(os.path.join(edg_utils.get_module_path(), os.pardir, "bluez-compassion"))
    if not os.path.isdir(args["bluez_compassion_path"]):
        printlog("ABORT: failed to find 'bluez-compassion' folder in current module path:", edg_utils.get_module_path(), "please clone from http://github.com/ykasidit/bluez-compassion")
        exit(-1)
    print "args['bluez_compassion_path']:", args["bluez_compassion_path"]


    # try not power on: power_on_bt_dev(args)  # need to power on before can get bt addr
    mac_addr = None
    bdaddr = get_bdaddr()
    try:
        mac_addr = get_iface_addr("eth0")
    except:
        mac_addr = get_iface_addr("wlp4s0")

    if mac_addr is None:
        print "INVALID: failed to get mac_addr"
        exit(2)

    print "mac_addr:", mac_addr
    print "bdaddr:", bdaddr

    ret = -1
    try:
        ret = stage0_check(mac_addr, bdaddr)
    except:
        type_, value_, traceback_ = sys.exc_info()
        exstr = str(traceback.format_exception(type_, value_, traceback_))
        print "WARNING: stage0 check exception:", exstr
        ret = -1
    if ret == 0:
        pass
    else:
        power_off_bt_dev(args)
        exit(ret)


    shared_gps_data_queues_dict = alloc_gps_data_queues_dict()

    prepare_bt_device(args)

    ### consumers
    gobject_main_loop = register_bluez_dbus_profile(shared_gps_data_queues_dict)

    gps_parser_proc = multiprocessing.Process(
        target=edg_gps_parser.parse,
        args=(shared_gps_data_queues_dict,)
    )
    gps_parser_proc.start()

    ###

    ### producer
    print "starting ecodroidgps_server main loop - gps_chardev_prefix:", args["gps_chardev_prefix"]
    gps_reader_proc = multiprocessing.Process(
        target=edg_gps_reader.read_gps,
        args=(args["gps_chardev_prefix"], shared_gps_data_queues_dict)
    )
    gps_reader_proc.start()

    gobject_main_loop.run()

    print("ecodroidgps_server - terminating")
    exit(0)
