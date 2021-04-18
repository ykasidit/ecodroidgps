import time
import traceback
import sys
import serial
import edg_utils
import io
import ecodroidgps_server
import hashlib
import fcntl, socket, struct
import dbus.mainloop.glib


MAX_GPS_DATA_QUEUE_LEN = 100

LED_WRITE_PATH = "/sys/class/leds/led0/brightness"
LED_LEAVE_ON_SECS = 0.100  # 100 ms

SEND_LED_ENABLED = False

def send_led(val):
    if not SEND_LED_ENABLED:
        return
    try:
        with open(LED_WRITE_PATH, "wb") as fptr:
            fptr.write(str(val))
    except:
        type_, value_, traceback_ = sys.exc_info()
        exstr = str(traceback.format_exception(type_, value_, traceback_))
        print(("WARNING: toggle_led() exception:", exstr))
    return
    


def read_gps(gps_chardev_prefix, gps_data_queues_dict):

    print("read_gps: start")

    q_list = gps_data_queues_dict["q_list"]
    q_list_used_indexes_mask = gps_data_queues_dict["q_list_used_indexes_mask"]
    q_list_used_indexes_mask_mutex = gps_data_queues_dict["q_list_used_indexes_mask_mutex"]
    global_write_queue = gps_data_queues_dict["global_write_queue"]

    while True:

        serial_obj = None
        serial_buffer = None

        try:


            for acm in range(0, 10):
                dev = gps_chardev_prefix + str(acm)
                print(("read_gps: opening gps chardev: "+dev))
                print(("read_gps: using CONFIGS: {}".format(ecodroidgps_server.CONFIGS)))
                try:
                    serial_obj = serial.Serial(dev, timeout=float(ecodroidgps_server.CONFIGS["PYSERIAL_READ_TIMEOUT"]), baudrate=int(ecodroidgps_server.CONFIGS["BAUD_RATE"]))
                    serial_buffer = io.BufferedReader(serial_obj, buffer_size=int(ecodroidgps_server.CONFIGS["MAX_READ_BUFF_SIZE"]))
                    print(("read_gps: opening gps chardev:"+dev+" success"))
                    break
                except:
                    type_, value_, traceback_ = sys.exc_info()
                    exstr = str(traceback.format_exception(type_, value_, traceback_))
                    print(("read_gps: opening gps chardev:"+dev+" failed - retry next acm number - exception: "+exstr))
                    continue

            prev_n_connected_dev = 0
            prev_n_connected_dev_put_successfully = 0
            last_led_on = False

            
            while True:
                gps_data = serial_buffer.readline(int(ecodroidgps_server.CONFIGS["MAX_READLINE_SIZE"]))  # put MAX_READ_BUFF_SIZE in case of working in binary/RAW mode with u-center or RTK solutions that ordered raw dumps
                    
                if gps_data is None or gps_data == "":
                    raise Exception("gps_chardev likely disconnected - try connect again...")

                try:
                    if len(gps_data) > 7:
                        if gps_data[3:6] == "RMC":
                            last_led_on = not last_led_on
                            if last_led_on:
                                #print('led on')
                                send_led(0)
                            else:
                                #print('led off')
                                send_led(1)
                                
                except Exception as ledex:
                    print(("WARNING: call toggle_led() exception:", ledex))

                while True:
                    wqsize = global_write_queue.qsize()
                    if 0 == wqsize:
                        break
                    try:
                        wbuf = global_write_queue.get_nowait()
                        #print(("wqsize:", wqsize, "got wbuf:", wbuf))
                        serial_obj.write(wbuf)
                        serial_obj.flush()
                        #print "wbuf write to serial success"
                    except Exception as e0:
                        print(("wbuf write to serial exception: {}".format(str(e0))))
                    

                n_connected_dev = 0
                n_connected_dev_put_successfully = 0

                q_list_used_indexes_mask_mutex.acquire()
                used_mask = q_list_used_indexes_mask.value
                q_list_used_indexes_mask_mutex.release()
                q_list_used_indexes = edg_utils.get_on_bit_offset_list(used_mask)
                
                # print "q_list_used_indexes:", q_list_used_indexes
                
                for q_index in q_list_used_indexes:
                    n_connected_dev += 1
                    #print("read_gps: write line to q_index:", q_index)
                    try:
                        q = q_list[q_index]
                        qsize = q.qsize()
                        #print "read_gps: q_index {} q {} q.qsize() {}".format(q_index, q, qsize)
                        if qsize >= MAX_GPS_DATA_QUEUE_LEN/2:
                            #print "read_gps: q_index {} q {} q.qsize() {} clearing...".format(q_index, q, qsize)
                            for i in range(0, MAX_GPS_DATA_QUEUE_LEN/4):
                                try:
                                    q.get_nowait()
                                except Exception as e0:
                                    print(("read_gps: append queue in q_list q_index {} get_nowait exception: {}".format(q_index, str(e0))))
                        try:
                            #print "read_gps: q_index {} q {} q.qsize() {} putting...".format(q_index, q, qsize)
                            q.put_nowait(gps_data)
                            n_connected_dev_put_successfully += 1
                        except Exception as e1:
                            print(("read_gps: append queue in q_list q_index {} put_nowait exception: {}".format(q_index, str(e1))))
                    except Exception:
                        type_, value_, traceback_ = sys.exc_info()
                        exstr = str(traceback.format_exception(type_, value_, traceback_))
                        print(("read_gps: append queue in q_list q_index{} exception: {}".format(q_index, exstr)))

                if n_connected_dev != prev_n_connected_dev or n_connected_dev_put_successfully != prev_n_connected_dev_put_successfully:
                    print(("read_gps: n_connected_dev {} n_connected_dev_put_successfully {}".format(n_connected_dev, n_connected_dev_put_successfully)))
                    prev_n_connected_dev = n_connected_dev
                    prev_n_connected_dev_put_successfully = n_connected_dev_put_successfully



        except Exception as e:
            print(("read_gps: exception: "+str(e)))
            time.sleep(3)
        finally:            
            if not serial_obj is None:
                try:
                    serial_obj.close()
                except Exception as se:
                    print(("WARNING: serial_obj close exception:", se))
                serial_obj = None
            if not serial_buffer is None:
                try:
                    serial_buffer.close()
                except Exception as se:
                    print(("WARNING: serial_buffer close exception:", se))
                serial_buffer = None



def get_bdaddr():
    pattern = None
    SERVICE_NAME = "org.bluez"
    ADAPTER_INTERFACE = SERVICE_NAME + ".Adapter1"
    DEVICE_INTERFACE = SERVICE_NAME + ".Device1"

    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    manager = dbus.Interface(
        bus.get_object("org.bluez", "/"),
	"org.freedesktop.DBus.ObjectManager"
    )
    objects = manager.GetManagedObjects()

    adapter_path = None
    for path, ifaces in list(objects.items()):
        adapter = ifaces.get(ADAPTER_INTERFACE)
        if adapter is None:
            continue
        if not pattern or pattern == adapter["Address"] or path.endswith(pattern):
            obj = bus.get_object(SERVICE_NAME, path)
            adapter_path = dbus.Interface(obj, ADAPTER_INTERFACE).object_path
            break

    if adapter_path is None:
        raise Exception("Bluetooth adapter not found")

    adapter = dbus.Interface(bus.get_object("org.bluez", adapter_path),
					"org.freedesktop.DBus.Properties")
    addr = adapter.Get("org.bluez.Adapter1", "Address").lower()
    return addr


def get_iface_addr(ifname):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    info = fcntl.ioctl(s.fileno(), 0x8927,  struct.pack('256s', ifname[:15]))
    return ':'.join(['%02x' % ord(char) for char in info[18:24]])


def get_mac_addr():
    mac_addr = None
    try:
        mac_addr = get_iface_addr("eth0")
    except:
        try:
            mac_addr = get_iface_addr("wlan0")
        except:
            mac_addr = get_iface_addr("wlp4s0")
            
    return mac_addr
