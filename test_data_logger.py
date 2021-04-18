import os
import inspect
import sys
import data_logger
import time
import ecodroidgps_server
import pynmea2
import edg_gps_parser


def test():
    assert os.path.isfile('test_data_logger.ini')
    ecodroidgps_server.load_configs(config_path='test_data_logger_performance.ini')
    print(("configs:", ecodroidgps_server.CONFIGS))
    assert int(ecodroidgps_server.CONFIGS['gpx']) == 1
    assert int(ecodroidgps_server.CONFIGS['nmea']) == 1

    rmc = pynmea2.RMC('GN', 'RMC', ())
    logger_state_dict = data_logger.get_init_logger_state_dict()
    caught_invalid = False
    try:
        fnprefix_invalid = data_logger.get_utc_datetime_obj(logger_state_dict, ret_str=True)
        print(('fnprefix_invalid:', fnprefix_invalid))
    except Exception as e:
        print(('test invalid rmc datetime ok invalid rmc got exception:', e))
        caught_invalid = True

    assert caught_invalid

    os.system("rm -rf /data/2019-04-15_02-19-52.gpx")    
    os.system('rm -rf /data/2019-04-15_02-19-52_nmea.txt')

    prev_added_nmea = None
    with open("ex_nmea.txt", "rb") as f:
        print(('data_logger ecodroidgps_server.CONFIGS["nmea"]', ecodroidgps_server.CONFIGS["nmea"]))
        while True:
            nmea = f.readline().decode('ascii')
            if not nmea:
                break            
            edg_gps_parser.on_nmea(nmea, logger_state_dict)
            prev_added_nmea = nmea
            if 'GGA' in nmea:
                #print 'got gga so sleep'
                time.sleep(0.1)
            else:
                pass
                #print 'not gga'

            gga = logger_state_dict['gga']

        dstr = data_logger.get_last_date_str(logger_state_dict)
        print(('fn dstr:', dstr))
        dobj = data_logger.get_utc_datetime_obj(logger_state_dict)
        print(('fn dobj:', dobj ,'type:', type(dobj)))

    print(('last added nmea line:', prev_added_nmea))
    # flush gpx and nmea files
    data_logger.on_nmea(logger_state_dict, "", force_flush=True)
                
    assert os.path.isfile('/data/2019-04-15_02-19-52_nmea.txt')
    assert os.path.isfile("/data/2019-04-15_02-19-52.gpx")
    assert 0 == os.system("xmllint /data/2019-04-15_02-19-52.gpx --noout")
        



if __name__ == "__main__":
    test()
