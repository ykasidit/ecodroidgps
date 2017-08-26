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
import select
import dbus
import dbus.service
import dbus.mainloop.glib

import edg_gps_reader

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


####### bt_spp

# just keep on reading to avoid target device write buffer full issues - read data not used
# remove q_list_index from q_list_used_indexes when done
# add the (fd*-1) to queue when done to signal the writer process that this fd has been closed (otherwise writer blocks on get() forever or until the queue is reused and writes to old fd then exits
def read_fd_until_closed(fd, q_list_index, q_list_used_indexes, queue_to_add_fd_on_close_as_signal_to_writer_proc):
    print("read_fd_until_closed: fd {} start".format(fd))
    READ_BUFF_SIZE = 2048
    try:
        while (True):
            read = None
            readable, writable, exceptional = select.select([fd], [], [])
            read = os.read(fd, READ_BUFF_SIZE)
            if not read is None:
                print("read_fd_until_closed: fd {} read data: {}".format(fd, read))
            else:
                print("read_fd_until_closed: fd {} read data none so ABORT")
                break
    except Exception as e:
        type_, value_, traceback_ = sys.exc_info()
        exstr = traceback.format_exception(type_, value_, traceback_)
        print("read_fd_until_closed: fd {} got exception: {}".format(fd, exstr))

    # close the fd
    try:
        os.close(fd)
        print("read_fd_until_closed: fd {} - os.close() fd done".format(fd) )
    except Exception as ce:
        print("read_fd_until_closed: fd {}: outer os.close(fd) exception: {}".format(fd, str(ce)) )

    # remove from queues dict when disconnected
    try:
        q_list_used_indexes.remove(q_list_index)
        print("read_fd_until_closed: fd {} - remove q_list_index from q_list_used_indexes done".format(fd) )
    except Exception as dpe:
        print("read_fd_until_closed: fd {} - remove q_list_index from q_list_used_indexes got exception: {}".format(fd, str(dpe)) )

    # add fd to queue_to_add_fd_on_close_as_signal_to_writer_proc
    try:
        queue_to_add_fd_on_close_as_signal_to_writer_proc.put( fd )
        print("read_fd_until_closed: fd {} - add fd to queue_to_add_fd_on_close_as_signal_to_writer_proc done".format(fd) )
    except Exception as nfdae:
        print("read_fd_until_closed: fd {} - add fd to queue_to_add_fd_on_close_as_signal_to_writer_proc exception:".format(fd, str(nfdae)) )

    
    print("read_fd_until_closed: fd {} end".format(fd))
    return


def write_nmea_from_queue_to_fd(queue, fd):
    print("write_nmea_from_queue_to_fd: fd {} start".format(fd))
    try:
        while (True):
            nmea = queue.get()
            if nmea == fd:
                print("write_nmea_from_queue_to_fd: fd {} got same fd in queue means signal from reader proc that fd is closed - break now".format(fd))
                break
            readable, writable, exceptional = select.select([], [fd], [])
            os.write(fd, nmea)
    except Exception as e:
        type_, value_, traceback_ = sys.exc_info()
        exstr = traceback.format_exception(type_, value_, traceback_)
        print("write_nmea_from_queue_to_fd: fd {} got exception: {}".format(fd, exstr))
    
    print("write_nmea_from_queue_to_fd: fd {} ending".format(fd))
    return
    

class Profile(dbus.service.Object):
        
    @dbus.service.method("org.bluez.Profile1",
                         in_signature="", out_signature="")
    def Release(self):
        print("bt_spp: Release")
        try:
            self.vars_dict["mainloop"].quit()
        except Exception as e:
            printlog("bt_spp: Release exception: "+str(e))
                              
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
    def NewConnection(self, path, dbus_fd, properties):

        gps_data_queues_dict = self.vars_dict["gps_data_queues_dict"]
        q_list = gps_data_queues_dict["q_list"]
        q_list_used_indexes = gps_data_queues_dict["q_list_used_indexes"]

        fd = None # os.close(fd) on exception
        q_list_index = None # remove from gps_data_queues_dict on exception

        try:

            fd = dbus_fd.take()

            print("bt_spp: NewConnection({}, fd: {})".format(path, fd))


            try:
                for key in properties.keys():
                    print("property: key:",key, "value:", properties[key])
                    if key == "Version" or key == "Features":
                        print("  %s = 0x%04x" % (key, properties[key]))
                    else:
                        print("  %s = %s" % (key, properties[key]))
            except Exception as e:
                print("WARNING: read new connection property exception: ", str(e))

            print("NewConnection: gps_data_queues_dict type:", type(gps_data_queues_dict))
            print("NewConnection: q_list type:", type(q_list))
            print("NewConnection: q_list_used_indexes type:", type(q_list_used_indexes))

            # get a q_list_index that isn't used yet
            for i in range(len(q_list)):
                if i in q_list_used_indexes:
                    continue
                q_list_index = i
                q_list_used_indexes.append(q_list_index) # put it into the used index list...
                break

            if q_list_index is None:
                raise Exception("ABORT: failed to get any unused queues in q_list - disconnect this new bt connection")

            queue = q_list[q_list_index]

            # remove q_list_index from q_list_used_indexes if we failed to start the reader/writer procs to the fd as the reader is the one who would return it
            print("starting reader_proc for fd {}", fd)
            reader_proc = mp.Process(target=read_fd_until_closed, args=(fd, q_list_index, q_list_used_indexes, queue))
            reader_proc.start()
            print("started reader_proc for fd {}", fd)

            print("starting writer_proc for fd {}", fd)
            writer_proc = mp.Process(target=write_nmea_from_queue_to_fd, args=(queue, fd))
            writer_proc.start()
            print("started writer_proc for fd {}", fd)
        
        except Exception as e:
            type_, value_, traceback_ = sys.exc_info()
            exstr = str(traceback.format_exception(type_, value_, traceback_))
            print("WARNING: NewConnection() got exception:", exstr)

            print("NewConnection() got exception: Cleaning up for exception: fd: "+str(fd))
            try:
                if fd is not None:
                    os.close(fd)
            except Exception as fde:
                print("WARNING: Cleaning up for exception fd: " + str(fd) +" exception: "+str(fde))

            print("NewConnection() got exception: Cleaning up for exception: q_list_index: " + str(q_list_index))
            try:
                if q_list_index is not None:
                    q_list_used_indexes.remove(q_list_index)
            except Exception as qle:
                print("WARNING: Cleaning up for exception q_list_index: " + str(q_list_index) + " exception: " + str(qle))


        return # end of NewConnection() func

    vars_dict = None
    
    def set_vars_dict(self, vd):
        self.vars_dict = vd
   
                              
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
q_list = [] # list of mp.Queue each holding nmea lines for a specific bt dev fd
q_list_used_indexes = mp_manager.list() # list of indices of used queues in above q_list
MAX_N_GPS_DATAQUEUES = 1
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
bt_spp = Profile(system_bus, edgps_dbus_path)
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
