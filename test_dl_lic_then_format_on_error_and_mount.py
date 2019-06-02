import os
import edg_gps_reader
from dl_lic import dl_lic
import platform

RUN_CMD = "python format_on_error_and_mount.py --dev_to_dir_list /dev/mmcblk0p3:/config,/dev/mmcblk0p4:/data"


def test():

    if 'x86' in platform.processor():
        print 'x86 dev pc dont format on error and mount...'
        return 
    
    # stop using /config and /data
    os.system('sudo systemctl stop ecodroidgps')

    # make sure they are mounted
    ret = os.system(RUN_CMD)
    print "RUN_CMD ret:", ret
    assert ret == 0

    # dl lic if required
    mac_addr = edg_gps_reader.get_mac_addr()
    bdaddr = edg_gps_reader.get_bdaddr()

    if mac_addr is None:
        print "INVALID: failed to get mac_addr"
        exit(2)

    print "mac_addr:", mac_addr
    print "bdaddr:", bdaddr

    dl_lic(mac_addr, bdaddr, edg_gps_reader.LICENSE_PATH)

    lic_orignally_exists = os.path.isfile(edg_gps_reader.LICENSE_PATH)
    assert lic_orignally_exists
    print 'lic_orignally_exists before run test corrupt and restore partition:', lic_orignally_exists

    cmds = [
        RUN_CMD, # normal run
        "dd if=/dev/urandom bs=1 count=10000 of=/data/d0",
        "dd if=/dev/urandom bs=1 count=10000 of=/config/c0",

        # test /data first so lic restore would work
        "umount /data ; echo done", # unmount before try corrupt device - fine if unmount failed...
        "dd if=/dev/zero bs=4096 count=1 of=/dev/mmcblk0p4",  # try corrupt data device
        RUN_CMD,

        "umount /config ; echo done",  # unmount before try corrupt device...        
        "dd if=/dev/zero bs=4096 count=1 of=/dev/mmcblk0p3",  # try corrupt config device
        RUN_CMD,
    ]

    for cmd in cmds:
        print "test cmd:", "sudo "+cmd
        ret = os.system(cmd)
        print "cmd ret:", ret
        assert ret == 0

    lic_still_exists = os.path.isfile(edg_gps_reader.LICENSE_PATH)
    print 'lic_still_exists after run test corrupt and restore partition:', lic_still_exists

    assert lic_orignally_exists == lic_still_exists

    assert 0 == os.system("df -h | grep /data")
    assert 0 == os.system("df -h | grep /config")

    
if __name__ == "__main__":
    test()
