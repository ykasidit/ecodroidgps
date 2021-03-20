import edg_gps_parser
import data_logger
import pynmea2
from datetime import datetime
import time
import os


def test():
    logger_state_dict = data_logger.get_init_logger_state_dict()    
    logger_state_dict['rmc'] = pynmea2.RMC('GN', 'RMC', ())
    logger_state_dict['last_rmc_datetime'] = datetime.utcfromtimestamp(0)
    caught_invalid = False
    try:
        fnprefix_invalid = data_logger.get_utc_datetime_obj(logger_state_dict, ret_str=True)
        print('fnprefix_invalid:', fnprefix_invalid)
    except Exception as e:
        print('got exception:', e)
        assert "must be not be less than DEV_YEAR" in str(e)
        caught_invalid = True

    assert caught_invalid
    
    nmeas = None
    with open("ex_nmea.txt", "r") as f:
        nmeas = f.read().replace("\r","").split("\n")

    loop_gap_broadcast_test = os.path.isfile('loop_gap_broadcast_test')
    while True:
        for nmea in nmeas:
            edg_gps_parser.on_nmea(nmea, logger_state_dict)
            if loop_gap_broadcast_test:
                if "GGA" in nmea:
                    time.sleep(1)
        if not loop_gap_broadcast_test:
            break



if __name__ == "__main__":
    test()
