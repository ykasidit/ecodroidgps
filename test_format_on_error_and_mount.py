import os


def test():

    run_cmd = "python format_on_error_and_mount.py --dev_to_dir_list /dev/mmcblk0p2:/data,/dev/mmcblk0p3:/config"

    cmds = [
        run_cmd, # normal run
        "umount /data && umount /config",  # unmount before try corrupt device...        
        "dd if=/dev/zero bs=1 count=10 of=/dev/mmcplk0p2 seek=10000",  # try corrupt device
        "dd if=/dev/zero bs=1 count=10 of=/dev/mmcplk0p3 seek=10000",  # try corrupt device        
        run_cmd,
        run_cmd
    ]

    for cmd in cmds:
        print "test cmd:", cmd
        ret = os.system(cmd)
        print "cmd ret:", ret
        assert ret == 0

    
if __name__ == "__main__":
    test()
