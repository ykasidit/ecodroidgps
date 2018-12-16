import os


def test():
    cmd = "python format_on_error_and_mount.py --dev_to_dir_list /dev/mmcblk0p2:/data,/dev/mmcblk0p3:/config"
    print "test cmd:", cmd
    ret = os.system(cmd)
    print "cmd ret:", ret
    assert ret == 0

    
if __name__ == "__main__":
    test()
