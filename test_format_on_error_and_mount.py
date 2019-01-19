import os


def test():

    run_cmd = "python format_on_error_and_mount.py --dev_to_dir_list /dev/mmcblk0p2:/data,/dev/mmcblk0p3:/config"

    cmds = [
        run_cmd, # normal run
        "dd if=/dev/urandom bs=1 count=10000 of=/data/d0",
        "dd if=/dev/urandom bs=1 count=10000 of=/config/c0",
        "umount /data", # unmount before try corrupt device...
        "umount /config",  # unmount before try corrupt device...
        "dd if=/dev/zero bs=4096 count=1 of=/dev/mmcblk0p2",  # try corrupt device
        "dd if=/dev/zero bs=4096 count=1 of=/dev/mmcblk0p3",  # try corrupt device        
        run_cmd,
        run_cmd
    ]

    for cmd in cmds:
        print "test cmd:", "sudo "+cmd
        ret = os.system(cmd)
        print "cmd ret:", ret
        assert ret == 0

    
if __name__ == "__main__":
    test()
