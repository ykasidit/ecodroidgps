import gpxpy
import gpxpy.gpx
from datetime import datetime
import gzip
import platform
import os

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
    
    nmea_list.append(nmea)

    # TODO: if too less space remain in /data, list all .gz /data and delete oldest one, one by one until space enough?
    
    # flush/update nmea gz when suitable
    now = datetime.now()
    seconds_since_last_flush = (now - logger_state_dict['last_flush_datetime']).total_seconds()
    if seconds_since_last_flush > LOG_FLUSH_EVERY_N_SECONDS:
        print 'data_logger flush now:', now, 'seconds_since_last_flush:', seconds_since_last_flush
        # get output file name /data/DD-MM-YY_nmea.txt.gz
        fn = "{}_nmea.txt.gz".format(logger_state_dict['log_name_prefix'])
        fp = os.path.join(logger_state_dict['log_dir'], fn)

        with gzip.open(fp, 'ab') as f:
            for nmea in nmea_list:
                f.write(nmea)
            
        # open gz in append mode with python gzip module, append all nmea lines
        # clear nmea_list
        del nmea_list[:]


        ################### TODO flush GPX now too
        #gpx_xml = logger_state_dict['gpx'].to_xml()
        #print 'gpx_xml:', gpx_xml
        

        # if .gpx.gz doest exist then
        # - write header and trk body in one gz chunk
        # - write footer in another gz chunk
        # else seek to last gz check header: B4 5C 02 FF - truncate file to there, and write new trak body and header content over it
        gpxfn = "{}.gpx.gz".format(logger_state_dict['log_name_prefix'])
        gpxfp = os.path.join(logger_state_dict['log_dir'], gpxfn)
        #########################
        
        # clear gpx list
        del logger_state_dict['gpx_segment'].points[:]
        
        logger_state_dict['last_flush_datetime'] = datetime.now()
    else:
        pass
        #print 'data_logger not flush now:', now, 'seconds_since_last_flush:', seconds_since_last_flush

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

                

        

       
        


def update_gpx(logger_dict):    
    gpx = gpxpy.gpx.GPX()

    # Create first track in our GPX:
    gpx_track = gpxpy.gpx.GPXTrack()
    gpx.tracks.append(gpx_track)

    # Create first segment in our GPX track:
    gpx_segment = gpxpy.gpx.GPXTrackSegment()
    gpx_track.segments.append(gpx_segment)

    # Create points:
    gpx_segment.points.append(gpxpy.gpx.GPXTrackPoint(2.1234, 5.1234, elevation=1234, time=dt))
    gpx_segment.points.append(gpxpy.gpx.GPXTrackPoint(2.1235, 5.1235, elevation=1235, time=dt))
    gpx_segment.points.append(gpxpy.gpx.GPXTrackPoint(2.1236, 5.1236, elevation=1236, time=dt))


