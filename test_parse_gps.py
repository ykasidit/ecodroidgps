import edg_gps_parser
from micropyGPS import MicropyGPS


def test():
    my_gps = MicropyGPS()
    nmeas = None
    with open("ex_nmea.txt", "r") as f:
        nmeas = f.read().replace("\r","").split("\n")
        
    nmeas_no_fix = [
        "$GPVTG,,,,,,,,,N*30",
        "$GPGGA,,,,,,0,00,99.99,,,,,,*48",
        "$GPGS99,,,,,,*48",
        "$GPGSA,A,1,,,,,,,,,,,,,99.99,99.99,99.99*30",
        "$GPGSV,3,1,12,01,,,22,02,,",
        "$GPRMC,,V,,,,,,,,,,N*53"
        "$GPVTG,,,,,,,,,N*30",
        "braaaaaaeeeeee ",
        "$GPGGA,,,,,,0,00,99.99,,,,,,*48"]

    # $GPGGA,162254.00,3723.02837,N,12159.39853,W,1,03,2.36,525.6,M,-25.6,M,,*65
    # 'GPGGA', '162254.00', '3723.02837', 'N', '12159.39853', 'W', '1', '03', '2.36', '525.6', 'M', '-25.6', 'M', '', '', '65'

    # $GNGGA,132840.00,1346.88722,N,10040.46293,E,1,09,0.90,002.7,M,-27.4,M,,*6F
    # 'GPGGA', '132840.00', '1346.88722', 'N', '10040.46293', 'E', '1', '09', '0.90', '002.7', 'M', '-27.4', 'M', '', '', '6F\n'
    
    sets = [["$GNGGA,133717.00,1346.88458,N,10040.46074,E,2,12,0.91,-5.0,M,-27.4,M,,0000*43"]]
    
    for set in range(len(sets)):
        nmeas = sets[set]
        for nmea in nmeas:
            edg_gps_parser.parse_nmea(my_gps, nmea)

        attrs = vars(my_gps)
        # now dump this in some way or another
        print ', '.join("%s: %s" % item for item in attrs.items())
        print "set {} lat: {} lon: {}".format(set, my_gps.latitude, my_gps.longitude)

        



if __name__ == "__main__":
    test()
