import edg_gps_parser
from micropyGPS import MicropyGPS
import data_logger


def test():
    my_gps = MicropyGPS()

    fnprefix_invalid = data_logger.get_utc_datetime_objfor_my_gps(my_gps, ret_str=True)
    print 'fnprefix_invalid:', fnprefix_invalid
    
    nmeas = None
    with open("ex_nmea.txt", "r") as f:
        nmeas = f.read().replace("\r","").split("\n")
    
    for nmea in nmeas:
        edg_gps_parser.parse_nmea(my_gps, nmea)

    attrs = vars(my_gps)
    # now dump this in some way or another
    print ', '.join("%s: %s" % item for item in attrs.items())
    print "set {} lat: {} lon: {}".format(set, my_gps.latitude, my_gps.longitude)
    dstr = data_logger.get_date_str_for_my_gps(my_gps)
    print 'fn dstr:', dstr
    dobj = data_logger.get_utc_datetime_objfor_my_gps(my_gps)
    print 'fn dobj:', dobj ,'type:', type(dobj)



if __name__ == "__main__":
    test()
