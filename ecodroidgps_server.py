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
import ctypes
import edg_socket_server
import edg_utils
import edg_gps_parser


__copyright__ = "EcoDroidGPS Copyright (c) 2019 Kasidit Yusuf. All rights reserved."
__author__ = "Kasidit Yusuf"
__email__ = "ykasidit@gmail.com"
__status__ = "Production"
__website__="www.ClearEvo.com"


# make sure bluez-5.46 is in folder next to this folder
CONFIG_PATH="/config/config.ini"
DEFAULT_CONFIG_PATH="/config/default_config.ini"
LAST_USED_CONFIG_PATH="/config/last_used_config.ini"
CONFIGS = {
    "spp": "1",
    "ble": "0",  # ble location and navigation profile - not well tested - dont use with gap option
    "gap": "1",  # ble gap (eddystone tlm) broadcast using our own custom format (containing lat/lon) to be parsed by bluetooth gnss android app...
    "tcp_server": "0",
    "gpx": "0",
    "nmea": "0",
    "BAUD_RATE": "230400",
    "PYSERIAL_READ_TIMEOUT": "1.0",
    "MAX_READLINE_SIZE": "4096",
    "MAX_READ_BUFF_SIZE": "20480",
}


def config_needs_edg_gps_parser_proc():
    global CONFIGS
    if int(CONFIGS["gap"]):
        return True
    if int(CONFIGS["gpx"]):
        return True
    if int(CONFIGS["nmea"]):
        return True
    if int(CONFIGS["ble"]):
        return True
    return False    


def write_dict_to_ini(d, fpath, re_raise=False):
    try:
        import configparser
        with open(fpath, "w") as f:
            config = configparser.ConfigParser()
            config.add_section('main')
            for key in d:
                config.set('main', key, str(d[key]))
            config.write(f)
        ret = os.system('unix2dos {}'.format(fpath))
        print(('unix2dos on written ini ret:', ret))
    except Exception as e:
        type_, value_, traceback_ = sys.exc_info()
        exstr = str(traceback.format_exception(type_, value_, traceback_))
        print(("WARNING: write ini {} exception {}".format(fpath, exstr)))
        if re_raise:
            raise e


def load_ini_to_dict_keys(d, fpath, re_raise=False):
    try:
        import configparser
        config = configparser.ConfigParser()
        ret = os.system('dos2unix {}'.format(fpath))
        print(('dos2unix on ini pre-read ret:', ret))
        ret = config.read(fpath)
        print(("ret", ret))
        for key in d:
            try:
                d[key] = config.get('main', key)
                d[key] = str(eval(d[key]))
            except Exception as pe:
                print(("WARNING: load config for key: {} failed with exception: {}".format(key, pe)))
            print(('load key {} final val {} type {}'.format(key, d[key], type(d[key]))))
    except Exception as e:
        if re_raise:
            raise e
        type_, value_, traceback_ = sys.exc_info()
        exstr = str(traceback.format_exception(type_, value_, traceback_))
        print(("WARNING: load ini {} exception {}".format(fpath, exstr)))

        
def load_configs(config_path=CONFIG_PATH, re_raise=False):
    global CONFIGS
    
    # write default config
    write_dict_to_ini(CONFIGS, DEFAULT_CONFIG_PATH, re_raise=re_raise)
    if os.path.isfile(config_path):
        load_ini_to_dict_keys(CONFIGS, config_path, re_raise=re_raise)
    else:
        print(('WARNING: not os.path.isfile(config_path): {}'.format(config_path)))
    write_dict_to_ini(CONFIGS, LAST_USED_CONFIG_PATH, re_raise=re_raise)
    print(('CONFIGS final:', CONFIGS))
    

def watch_configs_for_change(config_path=CONFIG_PATH, re_raise=False):
    global CONFIGS

    while True:
        d = CONFIGS.copy()
        if os.path.isfile(config_path):
            load_ini_to_dict_keys(d, config_path, re_raise=re_raise)
            print("compare config_path: ", config_path, " read dict:", d)
            print("VS current CONFIGS:", CONFIGS)            
            if d != CONFIGS:
                return True
        time.sleep(5)
    


infostr = "EcoDroidGPS v1.2 Copyright (c) 2017 Kasidit Yusuf. Released under the GNU GPL - please see LICENSE file for more info.\nOfficial ready-to-use EcoDroidGPS 'Bluetooth GPS' devices are available at: https://www.ClearEvo.com"

"""
read input from gps chardev, keep at a central var, send input to each subprocess's tx pipe

"""

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

def call_sh_cmd(cmd):
    #cmd = get_bash_cmdlist(cmd)
    print(("call cmd:", cmd))
    #return subprocess.call(["/bin/bash","-c",cmd], shell=False)
    return os.system(cmd)
    


def popen_bash_cmd(cmd):
    printlog("popen cmd:", cmd)
    return subprocess.Popen(cmd, shell=True, executable='/bin/bash')


def kill_popen_proc(proc):
    if proc is None:
        pass
    else:
        try:
            cmd = "pkill -INT -P {}".format(proc.pid) # sent INT to all with parent -P
            call_sh_cmd(cmd)
            time.sleep(0.2)
            proc.kill()
            proc.terminate()
        except Exception:
            type_, value_, traceback_ = sys.exc_info()
            exstr = str(traceback.format_exception(type_, value_, traceback_))
            printlog("WARNING: kill_popen_proc proc ", proc, "got exception:", exstr)
    return


def power_on_bt_dev(args):
    cmd = os.path.join(
        args["bluez_compassion_path"]
        ,"hciconfig"
    ) + " -a hci0 up"
    ret = call_sh_cmd(cmd)
    return ret


def power_off_bt_dev(args):
    cmd = os.path.join(
        args["bluez_compassion_path"]
        ,"hciconfig"
    ) + " -a hci0 down"
    ret = call_sh_cmd(cmd)
    return ret


g_prev_edl_agent_proc = None
def prepare_bt_device(args):
    global CONFIGS
    global g_prev_edl_agent_proc

    ret = power_off_bt_dev(args)
    
    # power on the bt dev
    ret = power_on_bt_dev(args)
    if ret != 0:
        raise Exception("failed to prepare bt device")

    ############ done started subprocesses
    
    printlog("prepare_bt_device done...")
    return


def keep_cmds_running(cmds, shared_gps_data_queues_dict):
    running_cmd_to_proc_dict = {}

    gps_parser_proc = None
    socket_server_proc = None

    while True:
        #printlog("keep_cmds_running: checking cmds...")
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
                        pass
                        #printlog("keep_cmds_running: ok cmd still running: {}".format(cmd))
                except:
                    type_, value_, traceback_ = sys.exc_info()
                    exstr = str(traceback.format_exception(type_, value_, traceback_))
                    printlog("WARNING: keep_cmds_running per cmd check got exception:", exstr)
                    
            ### CONFIG based gps data consumers
            # gps parser - for ble and gpx/nmea logging
            try:
                if config_needs_edg_gps_parser_proc():
                    if (gps_parser_proc is None or not gps_parser_proc.is_alive()):
                        print("config_needs_edg_gps_parser_proc() but proc not alive so start it")
                        gps_parser_proc = multiprocessing.Process(
                            target=edg_gps_parser.parse,
                            args=(shared_gps_data_queues_dict,)
                        )
                        gps_parser_proc.daemon=True
                        gps_parser_proc.start()
                    else:
                        pass
                        #print "config_needs_edg_gps_parser_proc() proc already alive"
                else:
                    pass
                    #print "not config_needs_edg_gps_parser_proc() so not starting it"
            except:
                type_, value_, traceback_ = sys.exc_info()
                exstr = str(traceback.format_exception(type_, value_, traceback_))
                printlog("WARNING: keep_cmds_running gps_parser_proc exception:", exstr)


                
            # tcp server for u-center over wifi/network connect/config
            try:
                if int(CONFIGS["tcp_server"]) == 1:
                    if (socket_server_proc is None or not socket_server_proc.is_alive()):
                        print('CONFIGS["tcp_server"] == 1 but proc not alive so starting edg_socker_server')
                        socket_server_proc = multiprocessing.Process(
                            target=edg_socket_server.start,
                            args=(shared_gps_data_queues_dict,)
                        )
                        socket_server_proc.daemon=True
                        socket_server_proc.start()
                    else:
                        pass
                        #print 'CONFIGS["tcp_server"] == 1 proc already alive'
                else:
                    pass
                    #print 'CONFIGS["tcp_server"] == 0 so not starting edg_socker_server'
            except:
                type_, value_, traceback_ = sys.exc_info()
                exstr = str(traceback.format_exception(type_, value_, traceback_))
                printlog("WARNING: keep_cmds_running tcp_server exception:", exstr)

        except:
            type_, value_, traceback_ = sys.exc_info()
            exstr = str(traceback.format_exception(type_, value_, traceback_))
            printlog("WARNING: keep_cmds_running got exception:", exstr)
        time.sleep(5)
        
    
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
    print("ecodroidgps bluetooth profile registered - waiting for incoming connections...")
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




############### MAIN

def main():

    print(infostr)

    load_configs()

    args = parse_cmd_args()

    # clone/put bluez_compassion in folder next to this folder
    args["bluez_compassion_path"] = os.path.abspath(os.path.join(edg_utils.get_module_path(), os.pardir, "bluez-compassion"))
    if not os.path.isdir(args["bluez_compassion_path"]):
        printlog("ABORT: failed to find 'bluez-compassion' folder in current module path:", edg_utils.get_module_path(), "please clone from http://github.com/ykasidit/bluez-compassion")
        exit(-1)
    print(("args['bluez_compassion_path']:", args["bluez_compassion_path"]))

    prepare_bt_device(args)

    ############# start subprocess commands

    print("alloc gps data queues")
    shared_gps_data_queues_dict = alloc_gps_data_queues_dict()
    
    # start the auto-pair agent
    edl_agent_cmd = "echo starting_edl_agent"
    # set discov
    edl_agent_cmd += " ; "  + os.path.join(
        args["bluez_compassion_path"]
        ,"hciconfig"
    ) + " -a hci0 piscan"
    
    # set paiarable
    edl_agent_cmd += " ; " + os.path.join(
        args["bluez_compassion_path"]
        ,"hciconfig"
    ) + " -a hci0 pairable 1"

    edl_agent_cmd += " ; " + os.path.join(
        args["bluez_compassion_path"]
        ,"edl_agent"
    )
    # **NOTE** it doesnt work in most cases - need to call it manually in terminal or in systemctl systemd service then it works
    #ret = call_sh_cmd(os.path.join(edg_utils.get_module_path(), "set_class.sh"))
    #print "set_class ret:", ret
    print(("edl_agent_cmd final:", edl_agent_cmd))

    cmd_list = [edl_agent_cmd]

    if int(CONFIGS["ble"]) == 0:
        print('CONFIGS["ble"] is 0 so not starting ble_lnp_cmd')
    else:
        print('CONFIGS["ble"] is not 0 so starting ble_lnp_cmd')

        import pandas as pd
        
        bluez_gatt_server_py_path = os.path.abspath(
            os.path.join(
                edg_utils.get_module_path(),
                os.pardir,
                "bluez-gatt-server",
                "bluez-gatt-server.py"
            )
        )

        print("gen ln feature mask dump")
        ln_feature_mask_dump_str = edg_utils.gen_edg_ln_feature_bitmask_hex_dump_str()
        print(("bitmask_str:", ln_feature_mask_dump_str))

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

        print("chmod chrc csv")
        chmodret = os.system("chmod 644 {}".format(chrc_csv_path))
        print(("chmodret:", chmodret))

        ble_lnp_cmd = "python3 {} --service_assigned_number 0x1819 --characteristics_table_csv {}".format(
            bluez_gatt_server_py_path,
            chrc_csv_path
        )
        cmd_list += [ble_lnp_cmd]

    p = multiprocessing.Process( target=keep_cmds_running, args=(cmd_list, shared_gps_data_queues_dict) )
    print("start keep_cmds_running start")
    # daemonic processes cannot have children: p.daemon=True
    p.start()
    print("start keep_cmds_running done")


    ### producer - read from gps device, write to it too if we got data from spp back from phone/device
    print(("starting ecodroidgps_server main loop - gps_chardev_prefix:", args["gps_chardev_prefix"]))
    gps_reader_proc = multiprocessing.Process(
        target=edg_gps_reader.read_gps,
        args=(args["gps_chardev_prefix"], shared_gps_data_queues_dict)
    )
    print("start gps_reader_proc start")
    gps_reader_proc.daemon=True
    gps_reader_proc.start()
    print("start gps_reader_proc done")

    if int(CONFIGS["spp"]) == 1:
        print('CONFIGS["spp"] == 1 so starting bluetooth serial port profile reg and loop')
        # bt spp profile
        print("======== register_bluez start")
        gobject_main_loop = register_bluez_dbus_spp_profile(shared_gps_data_queues_dict)
        print("======== register_bluez done === READY TO ACCEPT BT SPP CONNECTIONS")
        if os.path.isfile('debug_exit_on_spp_reg'):
            print('debug_exit_on_spp_reg so exit now')
            sys.exit(0)
        
        gobject_main_loop.run()
    else:
        print('CONFIGS["spp"] == 0 so not starting bluetooth serial port profile reg and loop')
        
    # watch config for changes - exit upon changes
    watch_configs_for_change()
    print("CONFIG CHANGED - exit now so systemctl would restart us and we'd load new configs")
    p.kill()  # keep_proc_running must be killed first as it is not daemonic thread and will still be alive even after we do system.exit next    
    sys.exit(1)

    print("ecodroidgps_server - terminating")
    exit(0)
