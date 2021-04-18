import edg_gps_parser
import time
import numpy as np


def test():
    lat = 123.1234567
    lon = -1.0*lat
    ts = time.time()
    ba = edg_gps_parser.gen_ecodroidgps_gap_broadcast_buffer(lat, lon, ts)
    print("braodcast_buff: {}".format(ba))
    parsed = edg_gps_parser.parse_ecodroidgps_gap_broadcast_buffer(ba)
    print("parsed: {}".format(parsed))
    assert parsed["lat"] == lat
    assert parsed["lon"] == lon
    assert parsed["ts"] == np.int32(ts)

    
if __name__ == "__main__":
    test()
