import os
import inspect
import sys
import pynmea2
import timeit
import data_logger
import time
import ecodroidgps_server
import edg_gps_parser
import timeit


def parse(nmeas, logger_state_dict, line_count):
    for nmea in nmeas:
        if isinstance(nmea, bytes):
            nmea = nmea.decode('ascii')        
        line_count += 1        
        edg_gps_parser.on_nmea(nmea, logger_state_dict)

    return line_count

    

def test():
    ecodroidgps_server.CONFIGS['gap'] = "0"
    assert os.path.isfile('test_data_logger_performance.ini')
    ecodroidgps_server.load_configs(config_path='test_data_logger_performance.ini')
    print(("configs:", ecodroidgps_server.CONFIGS))
    assert ecodroidgps_server.CONFIGS['gpx'] == "1"
    assert ecodroidgps_server.CONFIGS['nmea'] == "1"

    os.system("rm -rf /data/2019-04-15_02-19-52.gpx")    
    os.system('rm -rf /data/2019-04-15_02-19-52_nmea.txt')

    n_test_rounds = 100
    start = time.time()
    logger_state_dict = data_logger.get_init_logger_state_dict()
    n_parsed_nmea_lines = 0
    nmeas = None
    with open("ex_nmea.txt", "rb") as f:
        nmeas = f.readlines()
    EX_NMEA_LINES = 324
    assert len(nmeas) == EX_NMEA_LINES
    for i in range(n_test_rounds):
        n_parsed_nmea_lines = parse(nmeas, logger_state_dict, n_parsed_nmea_lines)

    assert EX_NMEA_LINES*n_test_rounds == n_parsed_nmea_lines
    now = time.time()

    print(('total_duration for {} rounds of parse and log of "ex_nmea.txt": {} seconds (n_parsed_nmea_lines: {})'.format(n_test_rounds, now - start, n_parsed_nmea_lines)))



if __name__ == "__main__":
    test()

# test cmd: ./build.sh && ./profile.sh test_data_logger_performance.py
