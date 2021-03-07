import edg_beacon
import edg_gps_parser
import bleson
import time


def test():
    i = 0
    adapter = bleson.get_provider().get_adapter()
    beacon = edg_beacon.EcoDroidGPSBeacon(adapter)
    while True:
        i += 1        
        lat = i * (1.0/10000000)
        lon = lat
        ba = edg_gps_parser.gen_ecodroidgps_gap_broadcast_buffer(lat, lon, time.time())
        beacon.eid = ba
        beacon.start()
        print("USE NRFCONNECT APP TO CHECK THIS ON PHONE NOW!")
        time.sleep(0.5)
        if i >= 60:
            break
        #beacon.stop()


if __name__ == "__main__":
    test()
