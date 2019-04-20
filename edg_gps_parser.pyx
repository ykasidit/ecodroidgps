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

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
sys.path.insert(0, os.path.join(parentdir, "micropyGPS-python2"))
from micropyGPS import MicropyGPS

import bit_utils
import ble_bit_offsets
from libc.stdint cimport uint8_t, uint16_t, int32_t
import numpy as np
import math
import os


############## micropyGPS/nmea consts
# Fix types can be: 1 = no fix, 2 = 2D fix, 3 = 3D fix
NMEA_FIX_NO = 1
NMEA_FIX_2D = 2
NMEA_FIX_3D = 3


def parse(shared_gps_data_queues_dict):
    print 'parse() start...'
    q_list = shared_gps_data_queues_dict["q_list"]
    q_list_used_indexes_mask = shared_gps_data_queues_dict["q_list_used_indexes_mask"]
    q_list_used_indexes_mask_mutex = shared_gps_data_queues_dict["q_list_used_indexes_mask_mutex"]

    q_list_index = None  # remove from q_list_used_indexes_mask on exception

    q_list_index = bt_spp_funcs.get_q_list_avail_index(shared_gps_data_queues_dict)

    logger_state_dict = {}
    logger_state_dict['nmea_list'] = []
    logger_state_dict['log_dir'] = "/data"
    logger_state_dict['last_flush_datetime'] = datetime.now()

    zip_older_logs()

    gpx = gpxpy.gpx.GPX()
    gpx.creator = "Data logged by EcoDroidGPS Bluetooth GPS/GNSS Receiver -- http://www.ClearEvo.com -- GPX engine by gpx.py -- https://github.com/tkrajina/gpxpy"

    # Create first track in our GPX:
    gpx_track = gpxpy.gpx.GPXTrack()
    gpx.tracks.append(gpx_track)
    
    # Create first segment in our GPX track:
    gpx_segment = gpxpy.gpx.GPXTrackSegment()
    gpx_track.segments.append(gpx_segment)

    logger_state_dict['gpx'] = gpx
    logger_state_dict['gpx_segment'] = gpx_segment    

    if q_list_index is None:
        raise Exception("ABORT: failed to get any unused queues in q_list")

    queue = q_list[q_list_index]

    update_ble_chrc = ecodroidgps_server.CONFIGS['ble'] == 1
    
    try:
        my_gps = None
        led_on = False
        
        while True:
            nmea = queue.get()
            #print 'parser got nmea:', nmea
            if nmea is None:
                raise Exception("edg_gps_parser.parse: got None from queue.get() - ABORT")

            if my_gps is None:
                my_gps = MicropyGPS()

            # handle: TypeError: must be string or buffer, not int
            if isinstance(nmea, str):                

                if "GGA" in nmea:
                    os.system("timeout 1 echo 1 > /sys/class/leds/led0/brightness")
                    led_on = True
                else:
                    if led_on:
                        os.system("timeout 1 echo 0 > /sys/class/leds/led0/brightness")
                        led_on = False                        
                
                try:
                    parse_nmea_and_update_ble_chrc(my_gps, nmea, update_ble_chrc=update_ble_chrc)
                except:
                    type_, value_, traceback_ = sys.exc_info()
                    exstr = traceback.format_exception(type_, value_, traceback_)
                    print("WARNING: gps parse exception:", exstr)
                    my_gps = None  # so it will make new obj in next loop

                logger_state_dict['my_gps'] = my_gps  # so logger_state_dict can get parsed values                    
                try:
                    data_logger.on_nmea(logger_state_dict, nmea)
                except:
                    type_, value_, traceback_ = sys.exc_info()
                    exstr = traceback.format_exception(type_, value_, traceback_)
                    print("WARNING: log nmea exception:", exstr)
                    
                
    except Exception as e:
        type_, value_, traceback_ = sys.exc_info()
        exstr = traceback.format_exception(type_, value_, traceback_)
        print("WARNING: edg_gps_parser.parse got exception:", exstr)


    # return the q_list_index to mask
    bt_spp_funcs.release_q_list_index(shared_gps_data_queues_dict, q_list_index)
    
    print "ABORT - invalid state - control should never reach here..."
    raise Exception("invalid state")


def parse_nmea_and_update_ble_chrc(my_gps, str nmea, update_ble_chrc=True):
    #print "parse_nmea:", nmea
    # parse it
    for nmea_char in nmea:
        my_gps.update(nmea_char)

    if update_ble_chrc:
        try:
            ###### post parse hooks
            # populate ble location and speed chrc
            #print "parse_nmea called - call gen_ble_location_and_speed_chrc_bytes"
            chrc_bytes = gen_ble_location_and_speed_chrc_bytes(my_gps)
            if chrc_bytes is not None:
                hexstr = str(chrc_bytes).encode("hex")
                #print "chrc_bytes valid: {}".format(hexstr)
                if "GGA" in nmea:
                    # publish to mqtt topic
                    ret = os.system("mosquitto_pub -t 'las' -m '{}'".format(hexstr))
                    #print "mqtt pub ret:", ret
            else:
                print "chrc_bytes none:", chrc_bytes
        except Exception:
            type_, value_, traceback_ = sys.exc_info()
            exstr = traceback.format_exception(type_, value_, traceback_)
            print("WARNING: parse_nmea_and_update_ble_chrc: update_ble_chrc exception:", exstr)


def gen_ble_location_and_speed_chrc_bytes(my_gps):

    las_gen_funcs = [
        gen_inst_speed,
        gen_position_status_and_location,
        gen_elevation,
    ]
    
    flag_bit_list = []

    # see https://github.com/inmcm/micropyGPS for examples
    # see spec at https://www.bluetooth.com/specifications/gatt/viewer?attributeXmlFile=org.bluetooth.characteristic.location_and_speed.xml

    payload_buffer = None

    #print "len(las_gen_funcs):", len(las_gen_funcs)

    payload_list = []

    for func in las_gen_funcs:
        #print "call func:", func
        try:
            ret = func(flag_bit_list, my_gps)
            if ret is not None:
                payload_list.append(ret)
        except:
            type_, value_, traceback_ = sys.exc_info()
            exstr = traceback.format_exception(type_, value_, traceback_)
            print("WARNING: las_gen_func exception:", exstr)

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
        print "can't create return buffer"

    return None


def gen_elevation(flag_bit_list, my_gps):
    altitude_m = my_gps.altitude

    # elevation 1/100 resolution
    altitude_m *= 100.0

    # sint24 so [0:3]
    ret = np.getbuffer(np.getbuffer(
        np.int32(altitude_m)
    )[0:3])
    

    flag_bit_list.append(ble_bit_offsets.location_and_speed.Elevation_Present)
    flag_bit_list.append(ble_bit_offsets.location_and_speed.Elevation_Source)  # set bit 0 of elevation_source is 'positioning system'
    
    return ret


def gen_inst_speed(flag_bit_list, my_gps):
    ### instantaneous_speed
    # Current speed is stored in a tuple of values representing knots, miles per hours and kilometers per hour
    #print "my_gps.speed len:", len(my_gps.speed)
    kph = my_gps.speed[2]

    #print "km/h:", kph
    
    meters_per_second = (float(kph)*1000.0)/3600.0
    #print "meters_per_second:", meters_per_second

    # Unit is in meters per second with a resolution of 1/100
    meters_per_second *= 100.0
    
    flag_bit_list.append(ble_bit_offsets.location_and_speed.Instantaneous_Speed_Present)
    ret = np.getbuffer(np.uint16(meters_per_second))
    return ret


LAT_LON_RESOLUTION_MULTIPLIER = math.pow(10.0, 7)


def gen_position_status_and_location(flag_bit_list, my_gps):
    # Fix types can be: 1 = no fix, 2 = 2D fix, 3 = 3D fix
    fix_type = my_gps.fix_type

    # spec says position_status is a two bit len field in flag so no payload: 0 = no position, 1 = position ok
    if fix_type >= 2:

        # set value of position_status bit to 1
        flag_bit_list.append(ble_bit_offsets.location_and_speed.Position_Status)

        # TODO: prepare location buffer
        lat = (my_gps.latitude[0] + (my_gps.latitude[1]/60.0)) * (1.0 if my_gps.latitude[2] == 'N' else -1.0)
        lon = (my_gps.longitude[0] + (my_gps.longitude[1]/60.0)) * (1.0 if my_gps.longitude[2] == 'E' else -1.0)
        #print "deg lat:", lat
        #print "deg lon:", lon

        lat *= LAT_LON_RESOLUTION_MULTIPLIER
        lon *= LAT_LON_RESOLUTION_MULTIPLIER

        ret = np.getbuffer(
            np.concatenate(
                [
                    np.getbuffer(np.int32(lat)),
                    np.getbuffer(np.int32(lon))
                ]
            )
        )

        # set location_present flag
        flag_bit_list.append(ble_bit_offsets.location_and_speed.Location_Present)

        return ret
        
    else:
        # leave flags as 0
        pass
    
    return None
        
        
def zip_older_logs():

    cmds = [
        ''' timeout 30 cd /data && find . -maxdepth 1 -name "*_nmea.txt" -exec bash -c "echo 'zipping {}' && zip -r - {} > {}.zip && rm {}" \; ''',
        ''' timeout 30 cd /data && find . -maxdepth 1 -name "*.gpx" -exec bash -c "echo 'zipping {}' && zip -r - {} > {}.zip && rm {}" \; '''
    ]

    for cmd in cmds:
        ret = os.system(cmd)
        print 'zip_older_logs() cmd {} ret: {}'.format(cmd, ret)




