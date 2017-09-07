import time
import traceback
import sys
import serial
import math
import edg_utils

MAX_GPS_DATA_QUEUE_LEN = 100


def read_gps(gps_chardev_prefix, gps_data_queues_dict):

    print "read_gps: start"

    q_list = gps_data_queues_dict["q_list"]
    q_list_used_indexes_mask = gps_data_queues_dict["q_list_used_indexes_mask"]
    q_list_used_indexes_mask_mutex = gps_data_queues_dict["q_list_used_indexes_mask_mutex"]

    while True:

        f = None

        try:


            for acm in range(0, 10):
                dev = gps_chardev_prefix + str(acm)
                print("read_gps: opening gps chardev:"+dev)
                try:
                    f = serial.Serial(dev, timeout=3)
                    print("read_gps: opening gps chardev:"+dev+" success")
                    break
                except:
                    print("read_gps: opening gps chardev:"+dev+" failed - retry next acm number")
                    continue

            prev_n_connected_dev = 0
            prev_n_connected_dev_put_successfully = 0

            while True:

                gps_data = f.readline()
                # print("read_gps: read gps_data:", gps_data)
                if gps_data is None or gps_data == "":
                    raise Exception("gps_chardev likely disconnected - try connect again...")

                n_connected_dev = 0
                n_connected_dev_put_successfully = 0

                q_list_used_indexes_mask_mutex.acquire()
                used_mask = q_list_used_indexes_mask.value
                q_list_used_indexes_mask_mutex.release()
                q_list_used_indexes = edg_utils.get_on_bit_offset_list(used_mask)
                
                print "q_list_used_indexes:", q_list_used_indexes
                
                for q_index in q_list_used_indexes:
                    n_connected_dev += 1
                    #print("read_gps: write line to q_index:", q_index)
                    try:
                        q = q_list[q_index]
                        qsize = q.qsize()
                        #print "read_gps: q_index {} q {} q.qsize() {}".format(q_index, q, qsize)
                        if qsize >= MAX_GPS_DATA_QUEUE_LEN/2:
                            #print "read_gps: q_index {} q {} q.qsize() {} clearing...".format(q_index, q, qsize)
                            for i in range(0, MAX_GPS_DATA_QUEUE_LEN/4):
                                try:
                                    q.get_nowait()
                                except Exception as e0:
                                    print("read_gps: append queue in q_list q_index {} get_nowait exception: {}".format(q_index, str(e0)))
                        try:
                            #print "read_gps: q_index {} q {} q.qsize() {} putting...".format(q_index, q, qsize)
                            q.put_nowait(gps_data)
                            n_connected_dev_put_successfully += 1
                        except Exception as e1:
                            print("read_gps: append queue in q_list q_index {} put_nowait exception: {}".format(q_index, str(e1)))
                    except Exception as e2:
                        type_, value_, traceback_ = sys.exc_info()
                        exstr = str(traceback.format_exception(type_, value_, traceback_))
                        print("read_gps: append queue in q_list q_index{} exception: {}".format(q_index, exstr))

                if n_connected_dev != prev_n_connected_dev or n_connected_dev_put_successfully != prev_n_connected_dev_put_successfully:
                    print("read_gps: n_connected_dev {} n_connected_dev_put_successfully {}".format(n_connected_dev, n_connected_dev_put_successfully))
                    prev_n_connected_dev = n_connected_dev
                    prev_n_connected_dev_put_successfully = n_connected_dev_put_successfully



        except Exception as e:
            print("read_gps: exception: "+str(e))
            time.sleep(3)
        finally:
            if not f is None:
                f.close()
