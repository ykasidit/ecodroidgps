from datetime import datetime
import time
import platform
import os
import sys
import traceback
import ecodroidgps_server
import pynmea2
import subprocess

LOG_FLUSH_EVERY_N_SECONDS = 1 if 'x86' in platform.processor() else 60
GPX_HEADER = '''<?xml version="1.0" encoding="UTF-8"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd" version="1.1" creator="Data logged by EcoDroidGPS Bluetooth GPS/GNSS Receiver -- http://www.ClearEvo.com -- GPX engine by gpx.py -- https://github.com/tkrajina/gpxpy">
  <trk>
    <trkseg>'''
GPX_TRK_FORMAT_STR = '''
      <trkpt lat="{}" lon="{}">
        <ele>{}</ele>
        <time>{}</time>
      </trkpt>'''
GPX_FOOTER = '''
    </trkseg>
  </trk>
</gpx>'''

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

def get_init_logger_state_dict():
    import gpxpy
    import gpxpy.gpx
    logger_state_dict = {}
    logger_state_dict['nmea_list'] = []
    logger_state_dict['log_dir'] = "/data"
    logger_state_dict['last_flush_time'] = time.time()
    logger_state_dict['last_rmc_datetime'] = None
    logger_state_dict['gga'] = None
    logger_state_dict['rmc'] = None
    logger_state_dict['gsa'] = None

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

    return logger_state_dict



def get_last_date_str(logger_state_dict):
    this_datetime =  logger_state_dict['last_rmc_datetime']
    if this_datetime is None:
        raise Exception("invalid date")
    return this_datetime.strftime("%Y-%m-%d")


DEV_YEAR = 2019


def get_utc_datetime_obj(logger_state_dict, ret_str=False):
    this_datetime = None
    this_datetime =  logger_state_dict['last_rmc_datetime']
    #print 'this_datetime:', this_datetime
    if this_datetime is None:
        raise Exception("no pynmea2 rmc time yet")
    #print 'this_datetime.year', this_datetime.year
    if this_datetime.year < DEV_YEAR:
        raise Exception("invalid rmc date: {} - must be not be less than DEV_YEAR of {}".format(this_datetime.year, DEV_YEAR))
    if ret_str:
        return this_datetime.strftime("%Y-%m-%d_%H-%M-%S")
    return this_datetime


def zip_older_logs_get_popen_list():
    zip_match_filters = [
        "*_nmea.txt",
        "*.gpx",
    ]

    ret_list = []
    for zip_match in zip_match_filters:
        # dont add a timeout as we want all to complete and get removed at end
        cmd = ''' cd /data && find . -maxdepth 1 -name "'''+zip_match+'''" -exec bash -c "echo 'zipping {}' && nice -n15 zip -r -1 - {} > {}.zip && rm -rf {}" \; '''
        print("zip_older_logs cmd:", cmd)
        ret = subprocess.Popen(cmd, shell=True)
        print('zip_older_logs() popen ret:', ret)
        ret_list.append(ret)

    return ret_list


g_zip_older_logs_ret_list = None  # run once


        
def on_nmea(logger_state_dict, nmea, static_gpx_formatstr_no_gpxpy=1, force_flush=False):
    import gpxpy
    import gpxpy.gpx
    global g_zip_older_logs_ret_list

    if g_zip_older_logs_ret_list is None:
        print('g_zip_older_logs_get_popen_list is None so run zip_older_logs_get_popen_list()')
        g_zip_older_logs_ret_list = zip_older_logs_get_popen_list()
    
    #print 'date_logger.on_nmea() start'
    nmea_list = logger_state_dict['nmea_list']

    if 'log_name_prefix' not in logger_state_dict:
        logger_state_dict['log_name_prefix'] = get_utc_datetime_obj(logger_state_dict, ret_str=True)
        #print "set logger_state_dict['log_name_prefix']:", logger_state_dict['log_name_prefix']

    flush_now = False
    now = time.time()
    #print "now {} logger_state_dict['last_flush_time'] {}".format(now, logger_state_dict['last_flush_time'])
    seconds_since_last_flush = (now - logger_state_dict['last_flush_time'])
    if seconds_since_last_flush > LOG_FLUSH_EVERY_N_SECONDS:
        print('data_logger flush now:', now, 'seconds_since_last_flush:', seconds_since_last_flush)
        logger_state_dict['last_flush_time'] = time.time()
        flush_now = True
    else:
        pass
        #print 'seconds_since_last_flush: {}', seconds_since_last_flush

    if force_flush:
        flush_now=True

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
                if force_flush:
                    print('WARNING: force flush now - nmea_list len after flush:', len(nmea_list))
        except:
            type_, value_, traceback_ = sys.exc_info()
            exstr = str(traceback.format_exception(type_, value_, traceback_))
            print("WARNING: data_loggger nmea exception {}".format(exstr))
            del nmea_list[:]  # it might raise during flush so list might eat ram more and more
    
    #### GPX
    if ecodroidgps_server.CONFIGS["gpx"] == 1:        
        try:
            # if is gga then append gpx track point list
            if "GGA" in nmea: #isinstance(my_gps, pynmea2.types.talker.GGA):
                gga = logger_state_dict['gga']
                if gga is not None:                    
                    lat = gga.latitude
                    lon = gga.longitude
                    altitude_m = gga.altitude
                    time_obj = get_utc_datetime_obj(logger_state_dict)
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

                header = None
                body = None
                footer = None
                if not static_gpx_formatstr_no_gpxpy:
                    gpx_buf = logger_state_dict['gpx'].to_xml()

                    search_str = "<trkseg>"
                    body_start_index = gpx_buf.index(search_str) + len(search_str)
                    search_str = "</trkseg>"
                    body_end_index = gpx_buf.index(search_str)

                    header = gpx_buf[:body_start_index]
                    body = gpx_buf[body_start_index:body_end_index]
                    footer = gpx_buf[body_end_index:]
                else:
                    header = GPX_HEADER
                    footer = GPX_FOOTER
                    body = ""
                    for point in logger_state_dict['gpx_segment'].points:
                        body_part = GPX_TRK_FORMAT_STR.format(point.latitude, point.longitude, point.elevation, point.time.strftime("%Y-%m-%dT%H:%M:%SZ"))
                        body += body_part

                #print "header:", header
                #print "body:", body
                #print "footer:", footer

                first_flush = 'last_gpx_footer_pos' not in logger_state_dict
                if first_flush:
                    open_mode = "wb"
                else:
                    open_mode = "r+b"  # if wb and seek then write then all bytes before seek becomes 0 raw data bytes.

                print("flush gpx to fp:", gpxfp)
                # file name/path is unique for a program run
                with open(gpxfp, open_mode) as f:
                    
                    if first_flush:  # empty file first flush case
                        f.write(header)                        
                        # dont rewind to write body over prev footer as this is the first time
                        print('not rewind')
                    else:
                        # rewind fpos to prev footer pos write body over prev footer
                        seekpos = logger_state_dict['last_gpx_footer_pos']
                        print("rewind to prev footer seekpos:", seekpos)
                        f.seek(seekpos, 0)

                    f.write(body)
                    footer_pos = f.tell()                    
                    print("set footer seekpos:", footer_pos)
                    logger_state_dict['last_gpx_footer_pos'] = footer_pos  # keep footer position to write over next time
                    f.write(footer)
                
                # clear gpx list
                del logger_state_dict['gpx_segment'].points[:]
        except:
            type_, value_, traceback_ = sys.exc_info()
            exstr = str(traceback.format_exception(type_, value_, traceback_))
            print("WARNING: data_loggger gpx exception {}".format(exstr))
            del logger_state_dict['gpx_segment'].points[:]  # it might raise during flush so list might eat ram more and more


    return


def append_list_content_to_file(dirpath, fn, list_of_data):
    if not isinstance(list_of_data, list):
        raise Exception("list_of_data must be a list - abort")
        
    fp = os.path.join(dirpath, fn)
    with open(fp, 'ab') as f:
        for data in list_of_data:
            f.write(data)
