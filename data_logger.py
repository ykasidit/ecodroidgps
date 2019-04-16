import gpxpy
import gpxpy.gpx
from datetime import datetime
import platform
import os
import sys
import traceback
import ecodroidgps_server

LOG_FLUSH_EVERY_N_SECONDS = 5 if 'x86' in platform.processor() else 60
GPX_HEADER = '''<?xml version="1.0" encoding="UTF-8"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd" version="1.1" creator="Data logged by EcoDroidGPS Bluetooth GPS/GNSS Receiver -- http://www.ClearEvo.com -- GPX engine by gpx.py -- https://github.com/tkrajina/gpxpy">
  <trk>
    <trkseg>'''
GPX_TRK_FORMAT_STR = '''
      <trkpt lat="{}" lon="{}">
        <ele>{}</ele>
        <time>{}</time>
      </trkpt>
'''
GPX_FOOTER = '''
    </trkseg>
  </trk>
</gpx>
'''

GPX_EXAMPLE='''<?xml version="1.0" encoding="UTF-8"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd" version="1.1" creator="Data logged by EcoDroidGPS Bluetooth GPS/GNSS Receiver -- http://www.ClearEvo.com -- GPX engine by gpx.py -- https://github.com/tkrajina/gpxpy">
  <trk>
    <trkseg>
      <trkpt lat="6.69405566667" lon="101.617695">
        <ele>42.7</ele>
        <time>2019-04-15T09:43:32Z</time>
      </trkpt>
      <trkpt lat="6.69405583333" lon="101.617694833">
        <ele>42.5</ele>
        <time>2019-04-15T09:43:33Z</time>
      </trkpt>
      <trkpt lat="6.694056" lon="101.6176945">
        <ele>42.3</ele>
        <time>2019-04-15T09:43:34Z</time>
      </trkpt>
      <trkpt lat="6.69405616667" lon="101.6176945">
        <ele>42.2</ele>
        <time>2019-04-15T09:43:35Z</time>
      </trkpt>
      <trkpt lat="6.69405633333" lon="101.617694667">
        <ele>42.1</ele>
        <time>2019-04-15T09:43:36Z</time>
      </trkpt>
      <trkpt lat="6.69405633333" lon="101.6176945">
        <ele>41.9</ele>
        <time>2019-04-15T09:43:37Z</time>
      </trkpt>
    </trkseg>
  </trk>
</gpx>
'''


def get_date_str_for_my_gps(my_gps):
    print 'my_gps.date:', my_gps.date
    if my_gps.date is None or tuple(my_gps.date) == (0, 0, 0):
        raise Exception("invalid date")

    # yyyy-mm-dd
    dstr = "2%03d-%02d-%02d" % (my_gps.date[2], my_gps.date[1], my_gps.date[0])
    return dstr


def get_utc_datetime_objfor_my_gps(my_gps, ret_str=False):    
    if my_gps.timestamp is None or tuple(my_gps.timestamp) == (0, 0, 0):
        raise Exception("invalid time")

    # hh-mm-ss
    tstr = "%02d-%02d-%02d" % (my_gps.timestamp[0], my_gps.timestamp[1], my_gps.timestamp[2])
    dtstr = "{}_{}".format(get_date_str_for_my_gps(my_gps), tstr)

    if dtstr == "2000-00-00_00-00-00":
        raise Exception("invalid state - previous coded didnt detect invalid date and time and must have raised exceptions earlier")    
    
    if ret_str:
        return dtstr
    dobj = datetime.strptime(dtstr, '%Y-%m-%d_%H-%M-%S')
    return dobj
    


def on_nmea(logger_state_dict, nmea):
    
    my_gps = logger_state_dict['my_gps']
    nmea_list = logger_state_dict['nmea_list']

    if 'log_name_prefix' not in logger_state_dict:
        logger_state_dict['log_name_prefix'] = get_utc_datetime_objfor_my_gps(my_gps, ret_str=True)
        print "set logger_state_dict['log_name_prefix']:", logger_state_dict['log_name_prefix']

    flush_now = False
    now = datetime.now()
    seconds_since_last_flush = (now - logger_state_dict['last_flush_datetime']).total_seconds()
    if seconds_since_last_flush > LOG_FLUSH_EVERY_N_SECONDS:
        print 'data_logger flush now:', now, 'seconds_since_last_flush:', seconds_since_last_flush
        logger_state_dict['last_flush_datetime'] = datetime.now()
        flush_now = True

    #### NMEA
    if ecodroidgps_server.CONFIGS["nmea"] == 1:
        try:
            nmea_list.append(nmea)
            if flush_now:
                # get output file name /data/DD-MM-YY_nmea.txt.gz
                fn = "{}_nmea.txt".format(logger_state_dict['log_name_prefix'])
                append_list_content_to_file(logger_state_dict['log_dir'], fn, nmea_list)
                # clear nmea_list
                del nmea_list[:]
        except:
            type_, value_, traceback_ = sys.exc_info()
            exstr = str(traceback.format_exception(type_, value_, traceback_))
            print "WARNING: data_loggger nmea exception {}".format(exstr)
            del nmea_list[:]  # it might raise during flush so list might eat ram more and more
    
    #### GPX
    if ecodroidgps_server.CONFIGS["gpx"] == 1:
        try:
            # if is gga then append gpx track point list
            if "GGA" in nmea:
                lat = (my_gps.latitude[0] + (my_gps.latitude[1]/60.0)) * (1.0 if my_gps.latitude[2] == 'N' else -1.0)
                lon = (my_gps.longitude[0] + (my_gps.longitude[1]/60.0)) * (1.0 if my_gps.longitude[2] == 'E' else -1.0)
                altitude_m = my_gps.altitude
                time_obj = get_utc_datetime_objfor_my_gps(my_gps)

                logger_state_dict['gpx_segment'].points.append(
                    gpxpy.gpx.GPXTrackPoint(
                        latitude=lat,
                        longitude=lon,
                        elevation=altitude_m,
                        time=time_obj
                    )
                )                
            if flush_now:
                fn = "{}.gpx".format(logger_state_dict['log_name_prefix'])
                gpxfp = os.path.join(logger_state_dict['log_dir'], fn)

                gpx_buf = logger_state_dict['gpx'].to_xml()

                search_str = "<trkseg>"
                body_start_index = gpx_buf.index(search_str) + len(search_str)
                search_str = "</trkseg>"
                body_end_index = gpx_buf.index(search_str)

                header = gpx_buf[:body_start_index]
                body = gpx_buf[body_start_index:body_end_index]
                footer = gpx_buf[body_end_index:]

                #print "header:", header
                #print "body:", body
                #print "footer:", footer

                first_flush = 'last_gpx_footer_pos' not in logger_state_dict
                if first_flush:
                    open_mode = "wb"
                else:
                    open_mode = "r+b"  # if wb and seek then write then all bytes before seek becomes 0 raw data bytes.

                # file name/path is unique for a program run
                with open(gpxfp, open_mode) as f:
                    
                    if first_flush:  # empty file first flush case
                        f.write(header)                        
                        # dont rewind to write body over prev footer as this is the first time
                        print 'not rewind'
                    else:
                        # rewind fpos to prev footer pos write body over prev footer
                        seekpos = logger_state_dict['last_gpx_footer_pos']
                        print "rewind to prev footer seekpos:", seekpos
                        f.seek(seekpos, 0)

                    f.write(body)
                    footer_pos = f.tell()                    
                    print "set footer seekpos:", footer_pos
                    logger_state_dict['last_gpx_footer_pos'] = footer_pos  # keep footer position to write over next time
                    f.write(footer)
                
                # clear gpx list
                del logger_state_dict['gpx_segment'].points[:]
        except:
            type_, value_, traceback_ = sys.exc_info()
            exstr = str(traceback.format_exception(type_, value_, traceback_))
            print "WARNING: data_loggger gpx exception {}".format(exstr)
            del logger_state_dict['gpx_segment'].points[:]  # it might raise during flush so list might eat ram more and more


    return


def append_list_content_to_file(dirpath, fn, list_of_data):
    if not isinstance(list_of_data, list):
        raise Exception("list_of_data must be a list - abort")
        
    fp = os.path.join(dirpath, fn)
    with open(fp, 'ab') as f:
        for data in list_of_data:
            f.write(data)
