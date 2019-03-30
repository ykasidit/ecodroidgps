#!/usr/bin/python
import os
import sys
import argparse
import traceback


def run_cmd(cmd):
    print "run cmd:", cmd
    ret = os.system(cmd)
    print "run cmd ret:", ret
    return ret


def do(mlist):
    print "format_on_error_and_mount list:", mlist
    for part in mlist:
        try:
            print "checking part:", part
            pdev, mdir = part.split(":")
            if not pdev:
                raise Exception("invalid empty pdev: {}".format(pdev))
            if not mdir:
                raise Exception("invalid empty mdir: {}".format(mdir))            

            info_cmd_required_tuple_list = [
                ("umount just in case already mounted...", "umount "+mdir, False),
                ("make sure target dir exists", "mkdir -p "+mdir, True),                
            ]

            for info_cmd_required_tuple in info_cmd_required_tuple_list:
                info, cmd, required = info_cmd_required_tuple
                print "info:", info
                print "required:", required
                ret = run_cmd(cmd)
                if ret != 0 and required:
                    raise Exception("cmd required and ret !=0")
                    
            print "try mounting..."
            mount_cmd = "mount -t ext4 {} {}".format(pdev, mdir)
            ret = run_cmd(mount_cmd)
            
            if ret != 0:
                print "mount failed - try format:"                
                cmd = "mkfs.ext4 -F {} -L {}".format(pdev, os.path.basename(mdir))
                ret = run_cmd(cmd)
                if ret != 0:
                    raise Exception("try fix partition by format failed ret: {}".format(ret))

                ret = run_cmd(mount_cmd)

            if ret == 0:
                print "mount success for part:", part
            else:
                raise Exception("mount failed")
        except:
            type_, value_, traceback_ = sys.exc_info()
            exstr = str(traceback.format_exception(type_, value_, traceback_))        
            print "WARNING: mount part: {} exception: {}".format(part, exstr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="format_on_error_and_mount",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        '--dev_to_dir_list',
	    help="provide partition list: <dev0>:<mount_dir0>,<dev1>:<mount_dir1>",
        required=True
    )
    args = vars(parser.parse_args())
    mlist = args["dev_to_dir_list"].split(",")
    do(mlist)
    
