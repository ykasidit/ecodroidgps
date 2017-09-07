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
def read_fd_until_closed(fd, q_list_index, q_list_used_indexes_mask, q_list_used_indexes_mask_mutex, queue_to_add_fd_on_close_as_signal_to_writer_proc):
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

    # remove from queues dict when disconnected
    try:
        print("read_fd_until_closed: fd {} - remove q_list_index from q_list_used_indexes_mask start".format(fd))
        
        q_list_used_indexes_mask_mutex.acquire()
        used_mask = q_list_used_indexes_mask.value
        print("read_fd_until_closed: fd {} - remove bit in mask - ori used_mask type: {} val: 0x{}".format(fd, type(used_mask), format(used_mask, '16x')))
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
        "read_fd_until_closed: fd {} - add fd to queue_to_add_fd_on_close_as_signal_to_writer_proc exception:".format(
            fd, str(nfdae)))

    print("read_fd_until_closed: fd {} end".format(fd))
    return


def write_nmea_from_queue_to_fd(queue, fd):
    print("write_nmea_from_queue_to_fd: fd {} start".format(fd))
    try:
        while True:
            nmea = queue.get()
            if nmea == fd:
                print(
                "write_nmea_from_queue_to_fd: fd {} got same fd in queue means signal from reader proc that fd is closed - break now".format(
                    fd))
                break
            readable, writable, exceptional = select.select([], [fd], [])

            if isinstance(nmea, str): # handle: TypeError: must be string or buffer, not int
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


    print("write_nmea_from_queue_to_fd: fd {} end".format(fd))
    return


################## callbacks from bt_spp_profile dbus functions below

def on_new_connection(self, path, dbus_fd, properties):
    
    shared_gps_data_queues_dict = self.vars_dict["shared_gps_data_queues_dict"]
    q_list = shared_gps_data_queues_dict["q_list"]
    q_list_used_indexes_mask = shared_gps_data_queues_dict["q_list_used_indexes_mask"]
    q_list_used_indexes_mask_mutex = shared_gps_data_queues_dict["q_list_used_indexes_mask_mutex"]

    fd = None  # os.close(fd) on exception
    q_list_index = None  # remove from q_list_used_indexes_mask on exception

    try:

        fd = dbus_fd.take()

        sock = socket.fromfd(fd, socket.AF_UNIX, socket.SOCK_STREAM)
        print "closing sock"
        sock.close()
        print "closing fd"
        os.close(fd)
        print "done close"
        raise Exception("closed")
        

        print("bt_spp_funcs: NewConnection({}, fd: {})".format(path, fd))

        try:
            for key in properties.keys():
                print("property: key:", key, "value:", properties[key])
                if key == "Version" or key == "Features":
                    print("  %s = 0x%04x" % (key, properties[key]))
                else:
                    print("  %s = %s" % (key, properties[key]))
        except Exception as e:
            print("WARNING: read new connection property exception: ", str(e))

        ############## critical section: START
        q_list_used_indexes_mask_mutex.acquire()

        # get currently used mask
        print "NewConnection: ori q_list_used_indexes_mask.value type: %s value: 0x%16x" % (type(q_list_used_indexes_mask.value), q_list_used_indexes_mask.value) 
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
            print "NewConnection: new used_mask type: %s value: 0x%16x" % (type(used_mask), used_mask)
            q_list_used_indexes_mask.value = used_mask
            print "NewConnection: new q_list_used_indexes_mask.value type: %s value: 0x%16x" % (type(q_list_used_indexes_mask.value), q_list_used_indexes_mask.value) 
            break

        del used_mask_on_indexes_list # this is invalid now, avoid reusing - use the q_list_used_indexes_mask.value with a mutex where needed

        q_list_used_indexes_mask_mutex.release()
        ############## critical section: END

        if q_list_index is None:
            raise Exception("ABORT: failed to get any unused queues in q_list - disconnect this new bt connection")

        queue = q_list[q_list_index]

        # the exception handler further below would remove/off the q_list_index bit in q_list_used_indexes_mask if we failed to start the writer proc to the fd - as the reader is the one who would normally unset the used bit in the mask

        print("starting writer_proc for fd {}", fd)
        writer_proc = mp.Process(target=write_nmea_from_queue_to_fd, args=(queue, os.dup(fd)))
        writer_proc.start()
        print("started writer_proc for fd {}", fd)

        print("starting reader_proc for fd {}", fd)
        reader_proc = mp.Process(target=read_fd_until_closed, args=(os.dup(fd), q_list_index, q_list_used_indexes_mask, q_list_used_indexes_mask_mutex, queue))
        reader_proc.start()
        print("started reader_proc for fd {}", fd)

    except Exception as e:
        type_, value_, traceback_ = sys.exc_info()
        exstr = str(traceback.format_exception(type_, value_, traceback_))
        print("WARNING: NewConnection() got exception:", exstr)

        print("NewConnection() got exception: Cleaning up for exception: fd: " + str(fd))
        try:
            if fd is not None:
                print("os.close() fd: {})".format(fd))
                os.close(fd)
        except Exception as fde:
            print("WARNING: Cleaning up for exception fd: " + str(fd) + " exception: " + str(fde))

        print("NewConnection() got exception: Cleaning up for exception: q_list_index: " + str(q_list_index))
        try:
            if q_list_index is not None:
                q_list_used_indexes_mask_mutex.acquire()
                used_mask = q_list_used_indexes_mask.value
                used_mask ^= long(math.pow(2, q_list_index)) # set the bit to 0
                q_list_used_indexes_mask.value = used_mask
                q_list_used_indexes_mask_mutex.release()
        except Exception as qle:
            print(
            "WARNING: Cleaning up for exception q_list_index: " + str(q_list_index) + " exception: " + str(qle))

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
