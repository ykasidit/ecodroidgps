import time
import traceback
import sys

MAX_GPS_DATA_QUEUE_LEN = 100


def read_gps(gps_chardev_path, gps_data_queues_dict):

    print "read_gps: start"

    q_list = gps_data_queues_dict["q_list"]
    q_list_used_indexes = gps_data_queues_dict["q_list_used_indexes"]

    while True:

        f = None

        try:

            print("read_gps: opening gps chardev:"+gps_chardev_path)
            f = open(gps_chardev_path, "r")

            while True:

                gps_data = f.readline()
                #print("read_gps: read gps_data:", gps_data)
                if gps_data is None or gps_data == "":
                    raise Exception("gps_chardev likely disconnected - try connect again...")

                #print("read_gps: pre enter for write line: len(q_list_used_indexes):", len(q_list_used_indexes))
                for q_index in q_list_used_indexes:
                    print("read_gps: write line to q_index:", q_index)
                    try:
                        q = q_list[q_index]
                        qsize = q.qsize()
                        #print "read_gps: queue i {} q {} q.qsize() {}".format(i, q, qsize)
                        if qsize >= MAX_GPS_DATA_QUEUE_LEN/2:
                            for i in range(0, MAX_GPS_DATA_QUEUE_LEN/4):
                                try:
                                    q.get_nowait()
                                except Exception as e0:
                                    print("read_gps: append queue in q_list q_index {} get_nowait exception: {}".format(q_index, str(e)))
                        try:
                            q.put_nowait(gps_data)
                        except Exception as e1:
                            print("read_gps: append queue in q_list q_index {} put_nowait exception: {}".format(q_index, str(e)))
                    except Exception as e2:
                        type_, value_, traceback_ = sys.exc_info()
                        exstr = str(traceback.format_exception(type_, value_, traceback_))
                        print("read_gps: append queue in q_list q_index{} exception: {}".format(q_index, exstr))


        except Exception as e:
            print("read_gps: exception: "+str(e))
            time.sleep(3)
        finally:
            if not f is None:
                f.close()
