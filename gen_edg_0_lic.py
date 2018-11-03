import hashlib
import sys
import uuid

print "opening mac_addr_list file: ", sys.argv[1]
target_lic_fp = "/data/edg.lic"

print "generating license file: {}".format(target_lic_fp)
with open(sys.argv[1], "r") as rf:
    addrs = rf.readlines()
    with open(target_lic_fp, "w") as wf:
        for mac_addr_colon_bdaddr in addrs:
            mac_addr_colon_bdaddr = mac_addr_colon_bdaddr.strip()
            shaer = hashlib.sha1()
            shaer.update(str(uuid.uuid4()))
            random_sha = shaer.hexdigest()
            wf.write(random_sha+"\n")

            print "mac_addr:", mac_addr_colon_bdaddr
            shaer = hashlib.sha1()
            shaer.update("edg")
            shaer.update(mac_addr_colon_bdaddr+":edg_kub")
            shaer.update("edg")
            this_sha = shaer.hexdigest()
            wf.write(this_sha+"\n")
            print "this_sha:", this_sha

print "done"
