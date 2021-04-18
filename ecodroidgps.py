import ecodroidgps_server

__copyright__ = "EcoDroidGPS Copyright (c) 2019 Kasidit Yusuf. All rights reserved."
__author__ = "Kasidit Yusuf"
__email__ = "ykasidit@gmail.com"
__status__ = "Production"
__website__="www.ClearEvo.com"


if __name__ == "__main__":
    ecodroidgps_server.CONFIGS['gap'] = 1
    ecodroidgps_server.main()

