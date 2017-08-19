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
import stat
import gobject
import select
import dbus
import dbus.service
import dbus.mainloop.glib

"""
read input from gps chardev, keep at a central var, send input to each subprocess's tx pipe

"""

# https://stackoverflow.com/questions/19225188/what-method-can-i-use-instead-of-file-in-python
import inspect
if not hasattr(sys.modules[__name__], '__file__'):
    __file__ = inspect.getfile(inspect.currentframe())

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

# will be removed MAX_GPS_DATA_QUEUE_LEN/4 when qsize() is MAX_GPS_DATA_QUEUE_LEN/2
MAX_GPS_DATA_QUEUE_LEN=100

def read_gps(args, queues_dict):

    print "read_gps: start"
    while True:
        f = None
        try:
            #print("read_gps: opening gps chardev:"+args["gps_chardev"])
            f = open(args["gps_chardev"], "r")
            while True:
                gps_data = f.readline()
                #print("read_gps: read gps_data:", gps_data)
                if gps_data is None or gps_data == "":
                    raise Exception("gps chardev likely disconnected - try connect again")
                for key, value in queues_dict.iteritems():
                    try:
                        q = value
                        qsize = q.qsize()
                        #print "read_gps: queue i {} q {} q.qsize() {}".format(i, q, qsize)
                        if qsize >= MAX_GPS_DATA_QUEUE_LEN/2:
                            for i in range(0, MAX_GPS_DATA_QUEUE_LEN/4):
                                try:
                                    q.get_nowait()
                                except:
                                    print("read_gps: append queue in queuesdict key {} get_nowait exception: {}".format(key, str(e)))
                        try:
                            q.put_nowait(gps_data)
                        except:
                            print("read_gps: append queue in queuesdict key {} put_nowait exception: {}".format(key, str(e)))
                    except Exception as e:
                        print("read_gps: append queue in queuesdict key {} exception: {}".format(key, str(e)))

        except Exception as e:
            print("read_gps: exception: "+str(e))
            time.sleep(1)
        finally:
            if not f is None:
                f.close()

                              
####### bt_spp

# just keep on reading to avoid target device write buffer full issues - read data not used
def read_fd_until_closed(fd):
    READ_BUFF_SIZE = 2048
    try:
        while (True):
            read = None
            readable, writable, exceptional = select.select([fd], [], [])
            read = os.read(fd, )
            if not read is None:
                print("read_fd_until_closed: fd {} read data: {}".format(fd, read))
            else:
                print("read_fd_until_closed: fd {} read data none so ABORT")
                break
    except Exception as e:
        type_, value_, traceback_ = sys.exc_info()
        exstr = traceback.format_exception(type_, value_, traceback_)
        print("read_fd_until_closed: fd {} got exception: {}".format(fd, exstr))
    
    print("read_fd_until_closed: fd {} proc ending")
    return


def write_nmea_from_queue_to_fd(queue, fd):
    try:
        while (True):
            nmea = queue.get()
            readable, writable, exceptional = select.select([], [fd], [])
            os.write(fd, nmea)
    except Exception as e:
        type_, value_, traceback_ = sys.exc_info()
        exstr = traceback.format_exception(type_, value_, traceback_)
        print("write_nmea_from_queue_to_fd: fd {} got exception: {}".format(fd, exstr))
    
    print("write_nmea_from_queue_to_fd: fd {} proc ending")
    return
    

class Profile(dbus.service.Object):
        
    @dbus.service.method("org.bluez.Profile1",
                         in_signature="", out_signature="")
    def Release(self):
        print("bt_spp: Release")
        self.mainloop.quit()
                              
    @dbus.service.method("org.bluez.Profile1",
                         in_signature="", out_signature="")
    def Cancel(self):
        print("bt_spp: Cancel")

    @dbus.service.method("org.bluez.Profile1",
                         in_signature="o", out_signature="")
    def RequestDisconnection(self, path):
        print("bt_spp: RequestDisconnection(%s)" % (path))
                              
    @dbus.service.method("org.bluez.Profile1",
                         in_signature="oha{sv}", out_signature="")
    def NewConnection(self, path, fd, properties):

        global g_srcfd
        global g_targetfd

        print("bt_spp: NewConnection({}, fd: {})".format(path, fd))

        this_fd = fd.take()
        self.fds.append(this_fd)        
        print("type fd", type(fd))
        print("this_fd", str(this_fd))

        try:
            for key in properties.keys():
                print("property: key:",key, "value:", properties[key])
                if key == "Version" or key == "Features":
                    print("  %s = 0x%04x" % (key, properties[key]))
                else:
                    print("  %s = %s" % (key, properties[key]))
        except Exception as e:
            print("WARNING: read new connection property exception: ", str(e))

        reader_proc = mp.Process(target=read_fd_until_closed, args=(this_fd))
        reader_proc.start()

        queue = mp.Queue(maxsize=MAX_GPS_DATA_QUEUE_LEN)
        self.gps_data_queues[this_fd] = queue # add new entry        
        writer_proc = mp.Process(target=write_nmea_from_queue_to_fd, args=(queue, this_fd))
        writer_proc.start()
    
    gps_data_queues = None
    gobject_main_loop = None
    
    def set_gps_data_queues(self, q):
        self.gps_data_queues = q

    def set_gobject_main_loop(self, goml):
        self.gobject_main_loop = goml
                              
                              
##################
    
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


    
############### MAIN

args = parse_cmd_args()
args["max_bt_serial_port_count"] = int(args["max_bt_serial_port_count"]) # parse to int

mp_manager = mp.Manager()
gps_data_queues = mp_manager.dict()

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
bt_spp = Profile(system_bus, edgps_dbus_path)
bt_spp.set_gps_data_queues(gps_data_queues)
gobject_main_loop = gobject.MainLoop()
bt_spp.set_gobject_main_loop(gobject_main_loop)

print "starting ecodroidgps_server main loop - gps chardev:", args["gps_chardev"]
gps_reader_proc = mp.Process(target=read_gps, args=(args, gps_data_queues) )

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
