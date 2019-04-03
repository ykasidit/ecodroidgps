import os
import json

LIC_SERVER_URL = 'https://asia-northeast1-turing-terminus-229108.cloudfunctions.net/edg_lic'


def dl_lic(mac_addr, bdaddr, save_path):
    js = json.dumps({"message":mac_addr+":"+bdaddr})
    dlliccmd = ''' timeout 60 wget --header=Content-Type:application/json --post-data='{}' {} -O {} '''.format(js, LIC_SERVER_URL, save_path)
    print "dlliccmd:", dlliccmd
    cmdret = os.system(dlliccmd)
    print "cmdret:", cmdret
    return cmdret
