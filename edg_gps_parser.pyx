import bt_spp_funcs


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
        while True:
            nmea = queue.get()
            if nmea is None:
                raise Exception("edg_gps_parser.parse: got None from queue.get() - ABORT")

            # handle: TypeError: must be string or buffer, not int
            if isinstance(nmea, str):
                # TODO - parse it and populate ble location and speed chrc, send to mqtt topic
                pass
    
            
                
    except Exception as e:
        type_, value_, traceback_ = sys.exc_info()
        exstr = traceback.format_exception(type_, value_, traceback_)
        print("WARNING: edg_gps_parser.parse got exception:", exstr)


    # TODO: return the q_list_index to mask
    
    print "ABORT - invalid state - control should never reach here..."
    raise Exception("invalid state")
