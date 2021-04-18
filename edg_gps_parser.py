import bt_spp_funcs
import sys
import traceback
import os
import sys
import inspect
import data_logger
from datetime import datetime
import gpxpy
import gpxpy.gpx
import ecodroidgps_server
import bleson
import edg_beacon

import bit_utils
import ble_bit_offsets
import numpy as np
import math
import os
import pynmea2


ECODROIDGPS_EID_BROADCAST_HEADER_BYTE_VERSION1 = np.uint8(0xE1).tobytes()

############## micropyGPS/nmea consts
# Fix types can be: 1 = no fix, 2 = 2D fix, 3 = 3D fix
NMEA_FIX_NO = 1
NMEA_FIX_2D = 2
NMEA_FIX_3D = 3


def parse(shared_gps_data_queues_dict):
    print('parse() start...')
    q_list = shared_gps_data_queues_dict["q_list"]
    q_list_used_indexes_mask = shared_gps_data_queues_dict["q_list_used_indexes_mask"]
    q_list_used_indexes_mask_mutex = shared_gps_data_queues_dict["q_list_used_indexes_mask_mutex"]

    q_list_index = None  # remove from q_list_used_indexes_mask on exception

    q_list_index = bt_spp_funcs.get_q_list_avail_index(shared_gps_data_queues_dict)

    # zip_older_logs() - this timeouts then big nmea files are found, try move it else where

    if q_list_index is None:
        raise Exception("ABORT: failed to get any unused queues in q_list")

    logger_state_dict = data_logger.get_init_logger_state_dict()

    queue = q_list[q_list_index]
    
    try:
        while True:
            nmea = queue.get()
            nmea = nmea.decode('ascii')
            #print 'parser got nmea:', nmea
            if nmea is None:
                raise Exception("edg_gps_parser.parse: got None from queue.get() - ABORT")
            on_nmea(nmea, logger_state_dict)
                
    except Exception as e:
        type_, value_, traceback_ = sys.exc_info()
        exstr = traceback.format_exception(type_, value_, traceback_)
        print(("WARNING: edg_gps_parser.parse got exception:", exstr))


    # return the q_list_index to mask
    bt_spp_funcs.release_q_list_index(shared_gps_data_queues_dict, q_list_index)
    
    print("ABORT - invalid state - control should never reach here...")
    raise Exception("invalid state")


MIN_NMEA_LEN = 7


def on_nmea(nmea, logger_state_dict):
    # handle: TypeError: must be string or buffer, not int
    gga = None
    if isinstance(nmea, str):
        if len(nmea) > MIN_NMEA_LEN:
            nmea_type = nmea[3:6]
            if "GGA" == nmea_type:
                gga = pynmea2.parse(nmea)
                logger_state_dict['gga'] = gga
                on_gga(logger_state_dict)
            elif "RMC" == nmea_type:
                rmc = pynmea2.parse(nmea)
                logger_state_dict['rmc'] = rmc
                logger_state_dict['last_rmc_datetime'] = rmc.datetime
            elif "GSA" == nmea_type:
                gsa = pynmea2.parse(nmea)
                logger_state_dict['gsa'] = gsa
        else:
            pass
            #print("WARNING: edg_gps_parser.on_nmea() - supplied nmea str len is too short - ignoring: len: {} nmea: {}".format(len(nmea), nmea))

        # always log nmea even if too short
        try:
            data_logger.on_nmea(logger_state_dict, nmea)
            pass
        except:
            type_, value_, traceback_ = sys.exc_info()
            exstr = traceback.format_exception(type_, value_, traceback_)
            print(("WARNING: log nmea exception:", exstr))
    else:
        print(("WARNING: edg_gps_parser.on_nmea() - supplied nmea is not str! ignoring type: {}".format(type(nmea))))


def on_gga(logger_state_dict):
    gap_enabled = ecodroidgps_server.CONFIGS['gap']
    update_ble_chrc_enabled = ecodroidgps_server.CONFIGS['ble']
    try:
        if gap_enabled:
            # update once per GGA
            update_gap_buffer(logger_state_dict)
    except:
        type_, value_, traceback_ = sys.exc_info()
        exstr = traceback.format_exception(type_, value_, traceback_)
        print(("WARNING: gap_enabled update_gap_buffer exception:", exstr))
    try:
        if update_ble_chrc_enabled:
            # update once per GGA
            update_ble_chrc(logger_state_dict)
    except:
        type_, value_, traceback_ = sys.exc_info()
        exstr = traceback.format_exception(type_, value_, traceback_)
        print(("WARNING: update_ble_chrc_enabled update_ble_chrc exception:", exstr))

def update_gap_buffer(logger_state_dict):
    try:
        beacon = None
        if 'beacon' in logger_state_dict:
            beacon = logger_state_dict['beacon']
        else:
            adapter = bleson.get_provider().get_adapter()
            beacon = edg_beacon.EcoDroidGPSBeacon(adapter)
            logger_state_dict['beacon'] = beacon

        gga = logger_state_dict['gga']
        if gga is None:
            raise Exception('gga is still None')
        lat = gga.latitude
        lon = gga.longitude
        #print(logger_state_dict['last_rmc_datetime'])
        ts = logger_state_dict['last_rmc_datetime'].timestamp()
        #print("lat:", lat)
        #print("lat:", lon)
        #print("ts:", ts)
        gap_buffer = gen_ecodroidgps_gap_broadcast_buffer(lat, lon, ts)
        beacon.eid = gap_buffer
        beacon.start()
    except Exception:
        type_, value_, traceback_ = sys.exc_info()
        exstr = traceback.format_exception(type_, value_, traceback_)
        print(("WARNING: update_gap_buffer exception:", exstr))


def update_ble_chrc(logger_state_dict):
    try:
        ###### post parse hooks
        # populate ble location and speed chrc
        #print "parse_nmea called - call gen_ble_location_and_speed_chrc_bytes"
        chrc_bytes = gen_ble_location_and_speed_chrc_bytes(logger_state_dict)
        if chrc_bytes is not None:
            hexstr = str(chrc_bytes).encode("hex")
            #print "chrc_bytes valid: {}".format(hexstr)                
            # publish to mqtt topic
            ret = os.system("mosquitto_pub -t 'las' -m '{}'".format(hexstr))
            #print "mqtt pub ret:", ret
        else:
            print(("chrc_bytes none:", chrc_bytes))
    except Exception:
        type_, value_, traceback_ = sys.exc_info()
        exstr = traceback.format_exception(type_, value_, traceback_)
        print(("WARNING: parse_nmea_and_update_ble_chrc: update_ble_chrc exception:", exstr))


def gen_ble_location_and_speed_chrc_bytes(logger_state_dict):

    las_gen_funcs = [
        gen_inst_speed,
        gen_position_status_and_location,
        gen_elevation,
    ]
    
    flag_bit_list = []

    # see https://github.com/Knio/pynmea2 for examples
    # see spec at https://www.bluetooth.com/specifications/gatt/viewer?attributeXmlFile=org.bluetooth.characteristic.location_and_speed.xml

    payload_buffer = None

    #print "len(las_gen_funcs):", len(las_gen_funcs)

    payload_list = []

    for func in las_gen_funcs:
        #print "call func:", func
        try:
            ret = func(flag_bit_list, logger_state_dict)
            if ret is not None:
                payload_list.append(ret)
        except:
            type_, value_, traceback_ = sys.exc_info()
            exstr = traceback.format_exception(type_, value_, traceback_)
            print(("WARNING: las_gen_func exception:", exstr))

    if len(payload_list):
        payload_buffer = np.getbuffer(np.concatenate(payload_list))

    #print "payload_buffer:", payload_buffer
    
    if len(flag_bit_list) and payload_buffer is not None:

        #print "prepare chrc: flag_bit_list:", flag_bit_list

        # gen flags
        flags = np.uint16(0)
            
        for bit_offset in flag_bit_list:
            #print "las chrc flags turn on bit:", bit_offset
            flags = bit_utils.set_bit(flags, bit_offset)

        #print "flags val hex:  %02x" % flags
        # return buffer of flags and payload_buffer (payload)
        flag_buffer = np.getbuffer(np.uint16(flags))
        #print "flag_buffer:", str(flag_buffer).encode("hex")
        ret = np.getbuffer(np.concatenate([flag_buffer, payload_buffer]))
        return ret
    else:
        print("can't create return buffer")

    return None


def gen_elevation(flag_bit_list, logger_state_dict):
    gga = logger_state_dict['gga']
    if gga is None:
        raise Exception('gga is still None')

    altitude_m = gga.altitude

    # elevation 1/100 resolution
    altitude_m *= 100.0

    # sint24 so [0:3]
    ret = np.getbuffer(np.getbuffer(
        np.int32(altitude_m)
    )[0:3])
    

    flag_bit_list.append(ble_bit_offsets.location_and_speed.Elevation_Present)
    flag_bit_list.append(ble_bit_offsets.location_and_speed.Elevation_Source)  # set bit 0 of elevation_source is 'positioning system'
    
    return ret


def gen_inst_speed(flag_bit_list, logger_state_dict):
    rmc = logger_state_dict['rmc']
    if rmc is None:
        raise Exception('rmc is still None')

    ### instantaneous_speed
    # Current speed is stored in a tuple of values representing knots, miles per hours and kilometers per hour
    spd_over_grnd = rmc.spd_over_grnd
    # google calculator 1 knots = 1.85200 kilometers per hour (search google: knots to kph)
    kph = 1.85200 * spd_over_grnd

    #print "km/h:", kph
    
    meters_per_second = (float(kph)*1000.0)/3600.0
    #print "meters_per_second:", meters_per_second

    # Unit is in meters per second with a resolution of 1/100
    meters_per_second *= 100.0
    
    flag_bit_list.append(ble_bit_offsets.location_and_speed.Instantaneous_Speed_Present)
    ret = np.getbuffer(np.uint16(meters_per_second))
    return ret


LAT_LON_RESOLUTION_MULTIPLIER = math.pow(10.0, 7)


def gen_position_status_and_location(flag_bit_list, logger_state_dict):
    gga = logger_state_dict['gga']
    gsa = logger_state_dict['gsa']
    if gga is None:
        raise Exception('gga is still None')
    if gsa is None:
        raise Exception('gsa is still None')
    
    # Fix types can be: 1 = no fix, 2 = 2D fix, 3 = 3D fix
    fix_type = gsa.mode_fix_type

    # spec says position_status is a two bit len field in flag so no payload: 0 = no position, 1 = position ok
    if fix_type >= 2:

        # set value of position_status bit to 1
        flag_bit_list.append(ble_bit_offsets.location_and_speed.Position_Status)

        
        lat = gga.latitude
        lon = gga.longitude

        ret = gen_lat_lon_buffer(lat, lon)

        # set location_present flag
        flag_bit_list.append(ble_bit_offsets.location_and_speed.Location_Present)

        return ret
        
    else:
        # leave flags as 0
        pass
    
    return None


def gen_lat_lon_buffer(lat, lon):
    lat *= LAT_LON_RESOLUTION_MULTIPLIER
    lon *= LAT_LON_RESOLUTION_MULTIPLIER
    ret = np.int32(lat).tobytes() + np.int32(lon).tobytes()
    return ret


def gen_ecodroidgps_gap_broadcast_buffer(lat, lon, timestamp):
    """
    format:
    version: uint8: 0xE1
    lat: int32: this is latitude multiplied by LAT_LON_RESOLUTION_MULTIPLIER
    lon: int32: this is longitude multiplied by LAT_LON_RESOLUTION_MULTIPLIER
    """
    ret = ECODROIDGPS_EID_BROADCAST_HEADER_BYTE_VERSION1
    ret += gen_lat_lon_buffer(lat, lon)
    ret += np.uint32(timestamp).tobytes()
    return ret
    

def parse_ecodroidgps_gap_broadcast_buffer(ba):
    pos = 0
    ver = ba[pos]
    pos += 1
    print(("ver:", hex(ver)))
    assert ver == ECODROIDGPS_EID_BROADCAST_HEADER_BYTE_VERSION1[0]
    ret = {}

    # lat lon
    for float_param in ["lat", "lon"]:
        param_buffer = ba[pos:pos+4]
        pos += 4
        assert len(param_buffer) == 4
        val = np.frombuffer(param_buffer, dtype=np.int32)[0]
        val = float(val) / float(LAT_LON_RESOLUTION_MULTIPLIER)
        ret[float_param] = val

    # ts
    param_buffer = ba[pos:pos+4]
    pos += 4
    ts = np.frombuffer(param_buffer, dtype=np.uint32)[0]
    ret["ts"] = ts

    return ret
