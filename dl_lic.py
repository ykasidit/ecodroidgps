import os
import json

__copyright__ = "EcoDroidGPS Copyright (c) 2019 Kasidit Yusuf. All rights reserved."
__author__ = "Kasidit Yusuf"
__email__ = "ykasidit@gmail.com"
__status__ = "Production"
__website__="www.ClearEvo.com"

# use http instead of https for early boot stage https connection setup fail when first lic dl
LIC_SERVER_URL = 'http://asia-northeast1-turing-terminus-229108.cloudfunctions.net/edg_lic'


def dl_lic(mac_addr, bdaddr, save_path):
    js = json.dumps({"message":mac_addr+":"+bdaddr})
    dlliccmd = ''' timeout 60 wget --header=Content-Type:application/json --post-data='{}' {} -O {} '''.format(js, LIC_SERVER_URL, save_path)
    print "dlliccmd:", dlliccmd
    cmdret = os.system(dlliccmd)
    print "cmdret:", cmdret
    return cmdret
