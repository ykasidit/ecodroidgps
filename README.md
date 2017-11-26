how to gen license
------------------

Get bluetooth adapter address:
- go to bluez source code folder
- go to 'test' folder
- run command:
./test-adapter list | grep Address
- You'd see a list of all bluetooth device addresses - example:
kasidit@kasidit-thinkpad:/data/bluez-5.45/test$ ./test-adapter list | grep Address
    Address = E4:A4:71:69:06:49
    Address = 00:1A:7D:DA:71:13
    
- Copy and paste the one you want to add into the file: licensed_mac_addr_list.txt - example:
E4:A4:71:69:06:49
00:1A:7D:DA:71:13

- generate the license file with command:
python gen_edg_lic.py licensed_mac_addr_list.txt

example output:
opening mac_addr_list file:  licensed_mac_addr_list.txt
generating license file: /data/edg.lic
mac_addr: E4:A4:71:69:06:49
this_sha: e93c95c1224c5e7081726a6fddfcdb69210ba421
done

- This means it has saved the license file to: /data/edg.lic

- After flashing the sdcard for the Pi, put in PC and copy/paste this file into the 'data drive':/ - overwrite the existing 'edg.lic'. If it doesn't allow - try with sudo command below:
  - right click > copy to copy the path of the existing 'edg.lic' file.
  - in a terminal of the new edg.lic folder:
  sudo cp edg.lic <paste>

- Eject the sdcard well. (In 'Places' file browser, click on the 'eject' icon for both the '7.6 GB' drive and the 'data' drive.

- Put the sdcard into the pi and test using its bluetooth GPS features.