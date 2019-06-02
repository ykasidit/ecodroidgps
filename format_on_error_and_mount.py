#!/usr/bin/python
import os
import sys
import argparse
import traceback
import platform


LICENSE_PATH="/config/edg.lic"

def run_cmd(cmd):
    print "run cmd:", cmd
    ret = os.system(cmd)
    print "run cmd ret:", ret
    return ret


def backup_and_restore_license_file():
    tandem_dir = "/data"
    license_backup_fp = os.path.join(tandem_dir, os.path.basename(LICENSE_PATH))
    if os.path.isfile(LICENSE_PATH):
        print 'license file exists - backup now'
        cp_to_bk_cmd = '''cp "{}" "{}" '''.format(LICENSE_PATH, license_backup_fp)
        cp_to_bk_ret = os.system(cp_to_bk_cmd)
        print 'cp_to_bk_ret:', cp_to_bk_ret
        return cp_to_bk_ret
    else:
        print 'license file NOT exists - try restore now'
        print 'start restore old license...'
        cp_from_bk_cmd = '''cp "{}" "{}" && sync '''.format(license_backup_fp, LICENSE_PATH)
        cp_from_bk_ret = os.system(cp_from_bk_cmd)
        print 'cp_from_bk_ret:', cp_from_bk_ret
        if cp_from_bk_ret == 0:
            print 'license restore from backup success'            
        else:
            print 'license restore from backup failed'
        return cp_from_bk_ret


def do(mlist):
    print "format_on_error_and_mount list:", mlist
    print "platform.processor()", platform.processor()
    if 'x86' in platform.processor():
        print 'x86 dev pc dont format on error and mount...'
        return 0
    
    for part in mlist:
        try:
            print "checking part:", part
            pdev, mdir = part.split(":")
            if not pdev:
                raise Exception("invalid empty pdev: {}".format(pdev))
            if not mdir:
                raise Exception("invalid empty mdir: {}".format(mdir))            

            os.system("SWAPFILE=/data/swapfile && swapoff $SWAPFILE")  # just in case its already used so umount wont fail
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
                print "mount failed - format it now..."
                cmd = "mkfs.ext4 -F {} -L {}".format(pdev, os.path.basename(mdir))
                ret = run_cmd(cmd)
                if ret != 0:
                    raise Exception("try fix partition by format failed ret: {}".format(ret))

                ret = run_cmd(mount_cmd)

            if ret == 0:
                print "mount success for part:", part
                if part.endswith("/config"):
                    print 'mkdir config bluetooth'
                    cbret = os.system("mkdir -p /config/bluetooth")  # for bluez to save pair info
                    print 'ret:', cbret
                if part.endswith("/data"):
                    swap_cmd = "SWAPFILE=/data/swapfile && fallocate -l 2G $SWAPFILE && sudo chmod 600 $SWAPFILE && mkswap $SWAPFILE && swapon $SWAPFILE"
                    print "swap_cmd:", swap_cmd
                    swap_ret = os.system(swap_cmd)  # for bluez to save pair info
                    print "swap_ret:", swap_ret
                backup_and_restore_license_file()
            else:
                raise Exception("mount failed")
            
        except:
            type_, value_, traceback_ = sys.exc_info()
            exstr = str(traceback.format_exception(type_, value_, traceback_))        
            print "WARNING: mount part: {} exception: {}".format(part, exstr)
            return 2

    
    return 0


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
    ret = do(mlist)
    print 'do func ret:', ret
    exit(ret)
    
