import sys
import os
import select
import multiprocessing as mp
import traceback

# just keep on reading to avoid target device write buffer full issues - read data not used
# remove q_list_index from q_list_used_indexes when done
# add the (fd*-1) to queue when done to signal the writer process that this fd has been closed (otherwise writer blocks on get() forever or until the queue is reused and writes to old fd then exits
def read_fd_until_closed(fd, q_list_index, q_list_used_indexes, queue_to_add_fd_on_close_as_signal_to_writer_proc):
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
        q_list_used_indexes.remove(q_list_index)
        print("read_fd_until_closed: fd {} - remove q_list_index from q_list_used_indexes done".format(fd))
    except Exception as dpe:
        print("read_fd_until_closed: fd {} - remove q_list_index from q_list_used_indexes got exception: {}".format(fd,
                                                                                                                    str(
                                                                                                                        dpe)))

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
            os.write(fd, nmea)
    except Exception as e:
        type_, value_, traceback_ = sys.exc_info()
        exstr = traceback.format_exception(type_, value_, traceback_)
        print("write_nmea_from_queue_to_fd: fd {} got exception: {}".format(fd, exstr))

    print("write_nmea_from_queue_to_fd: fd {} ending".format(fd))
    return


################## callbacks from bt_spp_profile dbus functions below

def on_new_connection(self, path, dbus_fd, properties):
    gps_data_queues_dict = self.vars_dict["gps_data_queues_dict"]
    q_list = gps_data_queues_dict["q_list"]
    q_list_used_indexes = gps_data_queues_dict["q_list_used_indexes"]

    fd = None  # os.close(fd) on exception
    q_list_index = None  # remove from gps_data_queues_dict on exception

    try:

        fd = dbus_fd.take()

        print("bt_spp: NewConnection({}, fd: {})".format(path, fd))

        try:
            for key in properties.keys():
                print("property: key:", key, "value:", properties[key])
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
            q_list_used_indexes.append(q_list_index)  # put it into the used index list...
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

        print("NewConnection() got exception: Cleaning up for exception: fd: " + str(fd))
        try:
            if fd is not None:
                os.close(fd)
        except Exception as fde:
            print("WARNING: Cleaning up for exception fd: " + str(fd) + " exception: " + str(fde))

        print("NewConnection() got exception: Cleaning up for exception: q_list_index: " + str(q_list_index))
        try:
            if q_list_index is not None:
                q_list_used_indexes.remove(q_list_index)
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