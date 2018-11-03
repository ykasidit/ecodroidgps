import sys
import os
import select
import multiprocessing as mp
import traceback
import edg_utils
import math
import time
import socket


# just keep on reading to avoid target device write buffer full issues - read data not used
# remove q_list_index from q_list_used_indexes when done
# add the (fd*-1) to queue when done to signal the writer process that this fd has been closed (otherwise writer blocks on get() forever or until the queue is reused and writes to old fd then exits
def read_fd_until_closed(connected_dev_dbus_path, fd, q_list_index, q_list_used_indexes_mask, q_list_used_indexes_mask_mutex, queue_to_add_fd_on_close_as_signal_to_writer_proc):
    print("read_fd_until_closed: fd {} start".format(fd))
    READ_BUFF_SIZE = 2048
    try:
        while True:
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
        print("read_fd_until_closed: fd {} - os.close() fd done".format(fd))
    except Exception as ce:
        print("read_fd_until_closed: fd {}: outer os.close(fd) exception: {}".format(fd, str(ce)))

        
    # make sure target dev is disconnected
    try:
        disconnect_bt_dev(connected_dev_dbus_path)
        print "read_fd_until_closed: fd {} - disconnect_bt_dev done".format(fd)
    except Exception as cde:
        print "read_fd_until_closed: fd {} - disconnect_bt_dev exception {}".format(fd, str(cde))
    
    
    # remove from queues dict when disconnected
    try:
        print("read_fd_until_closed: fd {} - remove q_list_index from q_list_used_indexes_mask start".format(fd))
        
        q_list_used_indexes_mask_mutex.acquire()
        used_mask = q_list_used_indexes_mask.value
        print("read_fd_until_closed: fd {} - remove bit in mask - ori used_mask type: {} val: 0x{}".format(fd, type(used_mask), format(used_mask, '016x')))
        used_mask ^= long(math.pow(2, q_list_index)) # set the bit to 0
        q_list_used_indexes_mask.value = used_mask
        print("read_fd_until_closed: fd {} - remove bit in mask - new q_list_used_indexes_mask.value type: {} val: 0x{}".format(fd, type(q_list_used_indexes_mask.value), format(q_list_used_indexes_mask.value, '016x')))
        q_list_used_indexes_mask_mutex.release()

        print("read_fd_until_closed: fd {} - remove q_list_index from q_list_used_indexes_mask done".format(fd))
    except Exception as dpe:
        print("read_fd_until_closed: fd {} - remove q_list_index from q_list_used_indexes got exception: {}".format(fd, str(dpe)) )

        
    # add fd to queue_to_add_fd_on_close_as_signal_to_writer_proc
    try:
        queue_to_add_fd_on_close_as_signal_to_writer_proc.put(fd)
        print(
        "read_fd_until_closed: fd {} - add fd to queue_to_add_fd_on_close_as_signal_to_writer_proc done".format(fd))
    except Exception as nfdae:
        print(
        "read_fd_until_closed: fd {} - add fd to queue_to_add_fd_on_close_as_signal_to_writer_proc exception: {}".format(
            fd, str(nfdae)))


    print("read_fd_until_closed: fd {} end".format(fd))
    return



def write_nmea_from_queue_to_fd(connected_dev_dbus_path, queue, fd):
    print("write_nmea_from_queue_to_fd: fd {} start".format(fd))
    try:
        while True:
            nmea = queue.get()
            if nmea is None:
                raise Exception("write_nmea_from_queue_to_fd: got None from queue.get() - ABORT")
            if nmea == fd:
                print(
                "write_nmea_from_queue_to_fd: fd {} got same fd in queue means signal from reader proc that fd is closed - break now".format(
                    fd))
                break
            readable, writable, exceptional = select.select([], [fd], [])

            if isinstance(nmea, str): # handle: TypeError: must be string or buffer, not int
                # print "write bt dev {} nmea [{}]".format(connected_dev_dbus_path, nmea)
                os.write(fd, nmea)
                
    except Exception as e:
        type_, value_, traceback_ = sys.exc_info()
        exstr = traceback.format_exception(type_, value_, traceback_)
        print("write_nmea_from_queue_to_fd: fd {} got exception: {}".format(fd, exstr))


    # try close the fd here too, in case the writer ends before the reader
    try:
        os.close(fd)
        print("write_nmea_from_queue_to_fd: fd {} - os.close() fd done".format(fd))
    except Exception as ce:
        print("write_nmea_from_queue_to_fd: fd {}: outer os.close(fd) exception: {}".format(fd, str(ce)))

    
    # make sure target dev is disconnected
    try:
        disconnect_bt_dev(connected_dev_dbus_path)
        print "write_nmea_from_queue_to_fd: fd {} - disconnect_bt_dev done".format(fd)
    except Exception as cde:
        print "write_nmea_from_queue_to_fd: fd {} - disconnect_bt_dev exception {}".format(fd, str(cde))


    print("write_nmea_from_queue_to_fd: fd {} end".format(fd))
    return


def disconnect_bt_dev(connected_dev_dbus_path):
    bluez_test_device_cmd = os.path.join(edg_utils.get_module_path(), ".." ,"bluez", "test", "test-device")
    print "disconnect_bt_dev {} start".format(connected_dev_dbus_path)

    # gen bd_addr string
    # example dev dbus path str: /org/bluez/hci0/dev_9C_5C_F9_14_6C_14
    # we want 9C:5C:F9:14:6C:14
    parts = connected_dev_dbus_path.split('_')    
    bdaddr_str = ""
    first = True
    for i in range(6):
        if first:
            first = False
        else:
            bdaddr_str += ":"
        bdaddr_str += parts[i+1]        
    print "disconnect_bt_dev: bdaddr_str:", bdaddr_str
    
    ret = os.system("timeout 7 "+bluez_test_device_cmd +" disconnect " + bdaddr_str)
    print "disconnect_bt_dev {} done ret {}".format(connected_dev_dbus_path, ret)
    
    return ret


def get_q_list_avail_index(shared_gps_data_queues_dict):
    q_list = shared_gps_data_queues_dict["q_list"]
    q_list_used_indexes_mask = shared_gps_data_queues_dict["q_list_used_indexes_mask"]
    q_list_used_indexes_mask_mutex = shared_gps_data_queues_dict["q_list_used_indexes_mask_mutex"]

    q_list_index = None
    
    ############## critical section: START
    q_list_used_indexes_mask_mutex.acquire()

    # get currently used mask
    print "NewConnection: ori q_list_used_indexes_mask.value type: %s value: 0x%016x" % (type(q_list_used_indexes_mask.value), q_list_used_indexes_mask.value) 
    used_mask = q_list_used_indexes_mask.value
    used_mask_on_indexes_list = edg_utils.get_on_bit_offset_list(used_mask)

    # get a q_list_index that isn't used yet
    for i in range(len(q_list)):
        if i in used_mask_on_indexes_list:
            continue
        q_list_index = i
        print "NewConnection: got available q_list_index:", q_list_index
        # set this bit as on in the used_mask and set it back into the shared q_list_used_indexes_mask.value
        used_mask |= long(math.pow(2, q_list_index))
        print "NewConnection: new used_mask type: %s value: 0x%016x" % (type(used_mask), used_mask)
        q_list_used_indexes_mask.value = used_mask
        print "NewConnection: new q_list_used_indexes_mask.value type: %s value: 0x%016x" % (type(q_list_used_indexes_mask.value), q_list_used_indexes_mask.value) 
        break

    del used_mask_on_indexes_list # this is invalid now, avoid reusing - use the q_list_used_indexes_mask.value with a mutex where needed

    q_list_used_indexes_mask_mutex.release()
    ############## critical section: END

    return q_list_index


################## callbacks from bt_spp_profile dbus functions below

def on_new_connection(self, connected_dev_dbus_path, dbus_fd, properties):
    
    shared_gps_data_queues_dict = self.vars_dict["shared_gps_data_queues_dict"]
    q_list = shared_gps_data_queues_dict["q_list"]
    q_list_used_indexes_mask = shared_gps_data_queues_dict["q_list_used_indexes_mask"]
    q_list_used_indexes_mask_mutex = shared_gps_data_queues_dict["q_list_used_indexes_mask_mutex"]

    fd = None  # os.close(fd) on exception
    q_list_index = None  # remove from q_list_used_indexes_mask on exception

    try:

        fd = dbus_fd.take()

        print("bt_spp_funcs: NewConnection({}, fd: {})".format(connected_dev_dbus_path, fd))

        try:
            for key in properties.keys():
                print("property: key:", key, "value:", properties[key])
                if key == "Version" or key == "Features":
                    print("  %s = 0x%04x" % (key, properties[key]))
                else:
                    print("  %s = %s" % (key, properties[key]))
        except Exception as e:
            print("WARNING: read new connection property exception: ", str(e))

        q_list_index = get_q_list_avail_index(shared_gps_data_queues_dict)

        if q_list_index is None:
            raise Exception("ABORT: failed to get any unused queues in q_list - disconnect this new bt connection")

        queue = q_list[q_list_index]

        # the exception handler further below would remove/off the q_list_index bit in q_list_used_indexes_mask if we failed to start the writer proc to the fd - as the reader is the one who would normally unset the used bit in the mask

        print("starting writer_proc for fd {}", fd)
        writer_proc = mp.Process(target=write_nmea_from_queue_to_fd, args=(connected_dev_dbus_path, queue, fd))
        writer_proc.start()
        print("started writer_proc for fd {}", fd)

        print("starting reader_proc for fd {}", fd)
        reader_proc = mp.Process(target=read_fd_until_closed, args=(connected_dev_dbus_path, fd, q_list_index, q_list_used_indexes_mask, q_list_used_indexes_mask_mutex, queue))
        reader_proc.start()
        print("started reader_proc for fd {}", fd)

    except Exception as e:
        type_, value_, traceback_ = sys.exc_info()
        exstr = str(traceback.format_exception(type_, value_, traceback_))
        print("WARNING: NewConnection() got exception:", exstr)

        
        print("NewConnection() got exception: Cleaning up [1/3] fd: " + str(fd))
        try:
            if fd is not None:
                print("os.close() fd: {})".format(fd))
                os.close(fd)
        except Exception as fde:
            print("WARNING: Cleaning up fd got exception: " + str(fde))

        # calling os.close(fd) or even if converted to socket the socket.close() doesn't disconnect remote dev if still connected so force disconnection from bluez device api
        print("NewConnection() got exception: Cleaning up [2/3] connected_dev_dbus_path: " + str(connected_dev_dbus_path) )
        try:
            disconnect_bt_dev(connected_dev_dbus_path)
        except Exception as cde:
            print("WARNING: Cleaning up connected_dev_dbus_path got exception: " + str(cde) )


        print("NewConnection() got exception: Cleaning up [3/3] q_list_index: " + str(q_list_index))
        try:
            if q_list_index is not None:
                q_list_used_indexes_mask_mutex.acquire()
                used_mask = q_list_used_indexes_mask.value
                used_mask ^= long(math.pow(2, q_list_index)) # set the bit to 0
                q_list_used_indexes_mask.value = used_mask
                q_list_used_indexes_mask_mutex.release()
        except Exception as qle:
            print("WARNING: Cleaning up q_list_index got exception: " + str(qle))


    print "NewConnection() end"
    return  # end of NewConnection() func


def on_release(self):
    print("bt_spp: Release")
    try:
        self.vars_dict["mainloop"].quit()
    except Exception as e:
        print("bt_spp: Release exception: " + str(e))


def on_cancel(self):
    print("bt_spp: Cancel")


def on_req_disconnection(self, path):
    print("bt_spp: RequestDisconnection(%s)" % (path))
