import bt_spp_funcs
import sys
import traceback
from micropyGPS import MicropyGPS


def parse(shared_gps_data_queues_dict):
    q_list = shared_gps_data_queues_dict["q_list"]
    q_list_used_indexes_mask = shared_gps_data_queues_dict["q_list_used_indexes_mask"]
    q_list_used_indexes_mask_mutex = shared_gps_data_queues_dict["q_list_used_indexes_mask_mutex"]

    q_list_index = None  # remove from q_list_used_indexes_mask on exception

    q_list_index = bt_spp_funcs.get_q_list_avail_index(shared_gps_data_queues_dict)

    if q_list_index is None:
        raise Exception("ABORT: failed to get any unused queues in q_list")

    queue = q_list[q_list_index]
    
    try:
        my_gps = None
        
        while True:
            nmea = queue.get()
            if nmea is None:
                raise Exception("edg_gps_parser.parse: got None from queue.get() - ABORT")

            if my_gps is None:
                my_gps = MicropyGPS()

            # handle: TypeError: must be string or buffer, not int
            if isinstance(nmea, str):                
                
                try:
                    parse_nmea(my_gps, nmea)
                except:
                    type_, value_, traceback_ = sys.exc_info()
                    exstr = traceback.format_exception(type_, value_, traceback_)
                    print("WARNING: gps parse exception:", exstr)
                    my_gps = None  # so it will make new obj in next loop
                    
                
    except Exception as e:
        type_, value_, traceback_ = sys.exc_info()
        exstr = traceback.format_exception(type_, value_, traceback_)
        print("WARNING: edg_gps_parser.parse got exception:", exstr)


    # return the q_list_index to mask
    bt_spp_funcs.release_q_list_index(shared_gps_data_queues_dict, q_list_index)
    
    print "ABORT - invalid state - control should never reach here..."
    raise Exception("invalid state")


cpdef parse_nmea(my_gps, str nmea):
    # parse it
    for char in nmea:
        my_gps.update(char)

    # populate ble location and speed chrc
                    
    # send to mqtt topic
