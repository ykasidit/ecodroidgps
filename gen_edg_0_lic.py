import hashlib
import sys
import uuid

print "opening mac_addr_list file: ", sys.argv[1]
target_lic_fp = "edg_0.lic"

print "generating license file: edg_0.lic"
with open(sys.argv[1], "r") as rf:
    addrs = rf.readlines()
    with open(target_lic_fp, "w") as wf:
        for mac_addr in addrs:
            mac_addr = mac_addr.strip()
            shaer = hashlib.sha1()
            shaer.update(str(uuid.uuid4()))
            random_sha = shaer.hexdigest()
            wf.write(random_sha+"\n")

            print "mac_addr:", mac_addr
            shaer = hashlib.sha1()
            shaer.update("edg")
            shaer.update(mac_addr+":edg")
            shaer.update("edg")
            this_sha = shaer.hexdigest()
            wf.write(this_sha+"\n")
            print "this_sha:", this_sha

print "done"
