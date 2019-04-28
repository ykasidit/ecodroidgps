import time
import traceback
import sys
import serial
import edg_utils
import io

MAX_GPS_DATA_QUEUE_LEN = 100
BAUD_RATE=230400
MAX_READ_BUFF_SIZE = 2048


def read_gps(gps_chardev_prefix, gps_data_queues_dict):

    print "read_gps: start"

    q_list = gps_data_queues_dict["q_list"]
    q_list_used_indexes_mask = gps_data_queues_dict["q_list_used_indexes_mask"]
    q_list_used_indexes_mask_mutex = gps_data_queues_dict["q_list_used_indexes_mask_mutex"]
    global_write_queue = gps_data_queues_dict["global_write_queue"]

    while True:

        serial_obj = None
        serial_buffer = None

        try:


            for acm in range(0, 10):
                dev = gps_chardev_prefix + str(acm)
                print("read_gps: opening gps chardev:"+dev)
                try:
                    serial_obj = serial.Serial(dev, timeout=3, baudrate=BAUD_RATE)
                    serial_buffer = io.BufferedReader(serial_obj, MAX_READ_BUFF_SIZE)
                    print("read_gps: opening gps chardev:"+dev+" success")
                    break
                except:
                    print("read_gps: opening gps chardev:"+dev+" failed - retry next acm number")
                    continue

            prev_n_connected_dev = 0
            prev_n_connected_dev_put_successfully = 0

            while True:
                gps_data = serial_buffer.readline(MAX_READ_BUFF_SIZE)  # put MAX_READ_BUFF_SIZE in case of working in binary/RAW mode with u-center or RTK solutions that ordered raw dumps
                # print("read_gps: read gps_data:", gps_data)
                if gps_data is None or gps_data == "":
                    raise Exception("gps_chardev likely disconnected - try connect again...")

                while True:
                    wqsize = global_write_queue.qsize()
                    if 0 == wqsize:
                        break
                    try:
                        wbuf = global_write_queue.get_nowait()
                        print "wqsize:", wqsize, "got wbuf:", wbuf
                        serial_obj.write(wbuf)
                        serial_obj.flush()
                        print "wbuf write to serial success"
                    except Exception as e0:
                        print("wbuf write to serial exception: {}".format(str(e0)))
                    

                n_connected_dev = 0
                n_connected_dev_put_successfully = 0

                q_list_used_indexes_mask_mutex.acquire()
                used_mask = q_list_used_indexes_mask.value
                q_list_used_indexes_mask_mutex.release()
                q_list_used_indexes = edg_utils.get_on_bit_offset_list(used_mask)
                
                # print "q_list_used_indexes:", q_list_used_indexes
                
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
                    except Exception:
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
            if not serial_obj is None:
                try:
                    serial_obj.close()
                except Exception as se:
                    print "WARNING: serial_obj close exception:", se
                serial_obj = None
            if not serial_buffer is None:
                try:
                    serial_buffer.close()
                except Exception as se:
                    print "WARNING: serial_buffer close exception:", se
                serial_buffer = None
