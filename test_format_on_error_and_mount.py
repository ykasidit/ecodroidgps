import os


def test():

    run_cmd = "python format_on_error_and_mount.py --dev_to_dir_list /dev/disk/by-label/config:/config,/dev/disk/by-label/data:/data"

    cmds = [
        run_cmd, # normal run
        "dd if=/dev/urandom bs=1 count=10000 of=/data/d0",
        "dd if=/dev/urandom bs=1 count=10000 of=/config/c0",
        "umount /data", # unmount before try corrupt device...
        "umount /config",  # unmount before try corrupt device...        
        "dd if=/dev/zero bs=4096 count=1 of=/dev/disk/by-label/config",  # try corrupt device
        "dd if=/dev/zero bs=4096 count=1 of=/dev/disk/by-label/data",  # try corrupt device
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
