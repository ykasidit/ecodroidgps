import edg_gps_parser
from micropyGPS import MicropyGPS


def test():
    my_gps = MicropyGPS()

    
    nmeas = ['$GPRMC,081836,A,3751.65,S,14507.36,E,000.0,360.0,130998,011.3,E*62\n',
            '$GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W*6A\n',
            '$GPRMC,225446,A,4916.45,N,12311.12,W,000.5,054.7,191194,020.3,E*68\n',
            '$GPRMC,180041.896,A,3749.1851,N,08338.7891,W,001.9,154.9,240911,,,A*7A\n',
            '$GPRMC,180049.896,A,3749.1808,N,08338.7869,W,001.8,156.3,240911,,,A*70\n',
            '$GPRMC,092751.000,A,5321.6802,N,00630.3371,W,0.06,31.66,280511,,,A*45\n']

    for nmea in nmeas:
        edg_gps_parser.parse_nmea(my_gps, nmea)
        
    attrs = vars(my_gps)

    # now dump this in some way or another
    print ', '.join("%s: %s" % item for item in attrs.items())
    
    print "lat: {}", my_gps.latitude
    print "lon: {}", my_gps.longitude


if __name__ == "__main__":
    test()
