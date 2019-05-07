#!/usr/bin/python

import subprocess
import sys
import time
import os
#import logging.handlers
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
import edg_socket_server
import ConfigParser

import edg_utils
import edg_gps_parser
from dl_lic import dl_lic
import format_on_error_and_mount

# make sure bluez-5.46 is in folder next to this folder
LICENSE_PATH="/config/edg.lic"
CONFIG_PATH="/config/config.ini"
DEFAULT_CONFIG_PATH="/config/default_config.ini"
LAST_USED_CONFIG_PATH="/config/last_used_config.ini"
CONFIGS = {
    "spp": 1,
    "ble": 0,
    "tcp_server": 1,
    "gpx": 0,
    "nmea": 0,
    "BAUD_RATE": 230400,
    "PYSERIAL_READ_TIMEOUT": 1.0,
    "MAX_READLINE_SIZE": 1024,
    "MAX_READ_BUFF_SIZE": 4096,
}


def config_needs_edg_gps_parser_proc():
    global CONFIGS
    if int(CONFIGS["gpx"]):
        return True
    if int(CONFIGS["nmea"]):
        return True
    if int(CONFIGS["ble"]):
        return True
    return False    


def write_dict_to_ini(d, fpath):
    try:
        with open(fpath, "wb") as f:
            config = ConfigParser.ConfigParser()
            config.add_section('main')
            for key in d:
                config.set('main', key, d[key])
            config.write(f)
        ret = os.system('unix2dos {}'.format(fpath))
        print 'unix2dos on written ini ret:', ret
    except:
        type_, value_, traceback_ = sys.exc_info()
        exstr = str(traceback.format_exception(type_, value_, traceback_))
        print "WARNING: write ini {} exception {}".format(fpath, exstr)


def load_ini_to_dict_keys(d, fpath):
    try:        
        config = ConfigParser.ConfigParser()
        ret = os.system('dos2unix {}'.format(fpath))
        print 'dos2unix on ini pre-read ret:', ret

        config.read(fpath)
        for key in d:
            try:
                d[key] = config.get('main', key)
                d[key] = eval(d[key])
            except Exception as pe:
                print "WARNING: load config for key: {} failed with exception: {}".format(key, pe)
            print 'load key {} final val {} type {}'.format(key, d[key], type(d[key]))
    except:
        type_, value_, traceback_ = sys.exc_info()
        exstr = str(traceback.format_exception(type_, value_, traceback_))
        print "WARNING: load ini {} exception {}".format(fpath, exstr)

        
def load_configs(config_path=CONFIG_PATH):
    global CONFIGS
    
    # write default config
    write_dict_to_ini(CONFIGS, DEFAULT_CONFIG_PATH)
    if os.path.isfile(config_path):
        load_ini_to_dict_keys(CONFIGS, config_path)
    else:
        print 'WARNING: not os.path.isfile(config_path): {}'.format(config_path)
    write_dict_to_ini(CONFIGS, LAST_USED_CONFIG_PATH)
    print 'CONFIGS final:', CONFIGS
    

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

'''
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
'''

def printlog(*s):
    #global g_logger
    s = str(s)
    '''
    try:
        g_logger.info(s)
    except:
        pass
    '''
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
    global CONFIGS
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

    ############ done started subprocesses
    
    printlog("prepare_bt_device done...")
    return


def keep_cmds_running(cmds, shared_gps_data_queues_dict):
    running_cmd_to_proc_dict = {}

    gps_parser_proc = None
    socket_server_proc = None

    while True:
        printlog("keep_cmds_running: checking cmds...")
        try:
            for cmd in cmds:
                try:
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
                    printlog("WARNING: keep_cmds_running per cmd check got exception:", exstr)
                    
            ### CONFIG based gps data consumers
            # gps parser - for ble and gpx/nmea logging
            try:
                if config_needs_edg_gps_parser_proc():
                    if (gps_parser_proc is None or not gps_parser_proc.is_alive()):
                        print "config_needs_edg_gps_parser_proc() but proc not alive so start it"
                        gps_parser_proc = multiprocessing.Process(
                            target=edg_gps_parser.parse,
                            args=(shared_gps_data_queues_dict,)
                        )
                        gps_parser_proc.start()
                    else:
                        print "config_needs_edg_gps_parser_proc() proc already alive"
                else:
                    print "not config_needs_edg_gps_parser_proc() so not starting it"
            except:
                type_, value_, traceback_ = sys.exc_info()
                exstr = str(traceback.format_exception(type_, value_, traceback_))
                printlog("WARNING: keep_cmds_running gps_parser_proc exception:", exstr)


                
            # tcp server for u-center over wifi/network connect/config
            try:
                if int(CONFIGS["tcp_server"]) == 1:
                    if (socket_server_proc is None or not socket_server_proc.is_alive()):
                        print 'CONFIGS["tcp_server"] == 1 but proc not alive so starting edg_socker_server'
                        socket_server_proc = multiprocessing.Process(
                            target=edg_socket_server.start,
                            args=(shared_gps_data_queues_dict,)
                        )
                        socket_server_proc.start()
                    else:
                        print 'CONFIGS["tcp_server"] == 1 proc already alive'
                else:
                    print 'CONFIGS["tcp_server"] == 0 so not starting edg_socker_server'
            except:
                type_, value_, traceback_ = sys.exc_info()
                exstr = str(traceback.format_exception(type_, value_, traceback_))
                printlog("WARNING: keep_cmds_running tcp_server exception:", exstr)

        except:
            type_, value_, traceback_ = sys.exc_info()
            exstr = str(traceback.format_exception(type_, value_, traceback_))
            printlog("WARNING: keep_cmds_running got exception:", exstr)
        time.sleep(5)
        

def stage0_check(mac_addr, bdaddr):
    format_on_error_and_mount.backup_and_restore_license_file()
    print "stage0 mac_addr:", mac_addr
    this_sha = None
    this_sha0 = None
    for i in range(100):
        if 1+2131+i == 4123%5:
            s = "startup stage0 check ok"
            return "license check ok"
        shaer0 = hashlib.sha1()
        shaer = hashlib.sha1()
        shaer0.update("edg"+str(i%3))
        shaer.update("edg")
        shaer0.update(mac_addr+":"+bdaddr+":edg_kub"+str(i))
        shaer.update(mac_addr+":"+bdaddr+":edg_kub")
        shaer.update("edg")
        shaer0.update("edg"+str(i%4))
        this_sha0 = shaer0.hexdigest()
        this_sha = shaer.hexdigest()
    #print "this_sha:", this_sha
    licfp = LICENSE_PATH
    lic_pass = False
    with open(licfp, "r") as f:        
        lic_lines = f.readlines()
        i_lic_lines = range(len(lic_lines))
        for i in i_lic_lines:
            shaer = hashlib.sha1()
            shaer.update("edg"+str(i))
            if lic_lines[i].strip() == this_sha0 or lic_lines[i].strip() == this_sha:
                lic_pass = True

    if lic_pass:
        print "startup stage0 check ok"
        return 0
    else:
        print "startup stage0 check failed code: -3 - please contact or get a new EcoDroidGPS unit at www.ClearEvo.com"
        exit(-3)
        return -3

    
def register_bluez_dbus_spp_profile(shared_gps_data_queues_dict):
    
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

    global_write_queue = multiprocessing.Queue(maxsize=edg_gps_reader.MAX_GPS_DATA_QUEUE_LEN)
        
    return {
        "q_list":q_list,  # phone read queue list - bt_spp_funcs reads from this queue (populated by edg_gps_reader read from usb) and writes to phone
        "q_list_used_indexes_mask":q_list_used_indexes_mask,
        "q_list_used_indexes_mask_mutex":q_list_used_indexes_mask_mutex,
        "global_write_queue": global_write_queue,  # one global write to usb queue - bt_spp_funcs reads buff written from phone and appends to this queue - edg_gps_reader checks if has entries then writes to usb
    }


def get_mac_addr():
    mac_addr = None
    try:
        mac_addr = get_iface_addr("eth0")
    except:
        try:
            mac_addr = get_iface_addr("wlan0")
        except:
            mac_addr = get_iface_addr("wlp4s0")
            
    return mac_addr


############### MAIN

def main():

    print infostr

    load_configs()

    args = parse_cmd_args()

    # clone/put bluez_compassion in folder next to this folder
    args["bluez_compassion_path"] = os.path.abspath(os.path.join(edg_utils.get_module_path(), os.pardir, "bluez-compassion"))
    if not os.path.isdir(args["bluez_compassion_path"]):
        printlog("ABORT: failed to find 'bluez-compassion' folder in current module path:", edg_utils.get_module_path(), "please clone from http://github.com/ykasidit/bluez-compassion")
        exit(-1)
    print "args['bluez_compassion_path']:", args["bluez_compassion_path"]


    # try not power on: power_on_bt_dev(args)  # need to power on before can get bt addr
    mac_addr = get_mac_addr()
    bdaddr = get_bdaddr()

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

    if ret != 0:
        print 'try dl lic now...'
        cmdret = dl_lic(mac_addr, bdaddr, LICENSE_PATH)
        print "try dl lic cmdret:", cmdret
        if cmdret == 0:
            print 'recheck stage0 after dl_lic()...'
            ret = stage0_check(mac_addr, bdaddr)

    if ret == 0:
        pass
    else:
        power_off_bt_dev(args)
        exit(ret)

    prepare_bt_device(args)

    ############# start subprocess commands

    shared_gps_data_queues_dict = alloc_gps_data_queues_dict()
    
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

    cmd_list = [edl_agent_cmd]

    if int(CONFIGS["ble"]) == 0:
        print 'CONFIGS["ble"] is 0 so not starting ble_lnp_cmd'
    else:
        print 'CONFIGS["ble"] is not 0 so starting ble_lnp_cmd'
        cmd_list += [ble_lnp_cmd]

    p = multiprocessing.Process( target=keep_cmds_running, args=(cmd_list, shared_gps_data_queues_dict) )
    p.start()


    ### producer - read from gps device, write to it too if we got data from spp back from phone/device
    print "starting ecodroidgps_server main loop - gps_chardev_prefix:", args["gps_chardev_prefix"]
    gps_reader_proc = multiprocessing.Process(
        target=edg_gps_reader.read_gps,
        args=(args["gps_chardev_prefix"], shared_gps_data_queues_dict)
    )
    gps_reader_proc.start()

    if int(CONFIGS["spp"]) == 1:
        print 'CONFIGS["spp"] == 1 so starting bluetooth serial port profile reg and loop'
        # bt spp profile
        gobject_main_loop = register_bluez_dbus_spp_profile(shared_gps_data_queues_dict)
        gobject_main_loop.run()
    else:
        print 'CONFIGS["spp"] == 0 so not starting bluetooth serial port profile reg and loop'
        while True:
            print 'main thread sleeping...'
            time.sleep(60*60)
            print 'main thread woke up...'

    print("ecodroidgps_server - terminating")
    exit(0)
