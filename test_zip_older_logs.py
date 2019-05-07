import os
import data_logger


def test():
    target_nmea_zip = "/data/t0_nmea.txt.zip"
    target_gpx_zip = "/data/t0.gpx.zip"
    
    cmd = "rm -f {} && echo nmea > /data/t0_nmea.txt && rm -f {} && echo gpx > /data/t0.gpx".format(target_nmea_zip, target_gpx_zip)

    assert os.system(cmd) == 0
    
    plist = data_logger.zip_older_logs_get_popen_list()
    assert plist is not None
    for p in plist:
        assert 0 == p.wait()

    assert os.path.isfile(target_nmea_zip)
    assert os.path.isfile(target_gpx_zip)

    
if __name__ == "__main__":
    test()
