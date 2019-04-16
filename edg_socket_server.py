import sys
import traceback
import os
import ecodroidgps_server
import socket
import bt_spp_funcs
import time
import threading

# test with two concurrent terminal cmds: socat - tcp:localhost:8888

SOCKET_SERVER_PORT = 8888

# globals
global_gps_data_queues_dict = None


def socket_tx(queue, request):
    print 'socket_tx start for request:', request
    try:
        while True:
            nmea = queue.get()
            if nmea is not None:
                request.sendall(nmea)
    except:
        type_, value_, traceback_ = sys.exc_info()
        exstr = str(traceback.format_exception(type_, value_, traceback_))
        print "WARNING: socket_tx exception {}".format(exstr)
    print 'socket_tx end for request:', request

    
RX_BUF_MAX_SIZE = 256
def socket_rx(request, global_write_queue):
    print 'socket_rx start for request:', request
    try:
        while True:
            rbuf = request.recv(RX_BUF_MAX_SIZE)
            if rbuf is not None:
                global_write_queue.put_nowait(rbuf)
                print 'socket_rx read and put_nowait done for rbuf:', rbuf
    except:
        type_, value_, traceback_ = sys.exc_info()
        exstr = str(traceback.format_exception(type_, value_, traceback_))
        print "WARNING: socket_rx exception {}".format(exstr)
    print 'socket_rx end for request:', request


def handle(request):
    try:
        print 'edg_socket_server start accept request:', request
        q_list = global_gps_data_queues_dict["q_list"]
        global_write_queue = global_gps_data_queues_dict["global_write_queue"]

        q_list_index = None  # remove from q_list_used_indexes_mask on exception
        q_list_index = bt_spp_funcs.get_q_list_avail_index(global_gps_data_queues_dict)
        if q_list_index is None:
            raise Exception("ABORT: failed to get any unused queues in q_list")

        queue = q_list[q_list_index]

        stx_thread = threading.Thread(target=socket_tx, args=(queue, request,))
        stx_thread.daemon = True
        stx_thread.start()

        srx_thread = threading.Thread(target=socket_rx, args=(request, global_write_queue,))
        srx_thread.daemon = True
        srx_thread.start()            
    except:
        type_, value_, traceback_ = sys.exc_info()
        exstr = str(traceback.format_exception(type_, value_, traceback_))
        print "WARNING: tcp hadle exception {}".format(exstr)

    time.sleep(10)
    print 'edg_socket_server end accept request:', request



def start(shared_gps_data_queues_dict, port=8000):
    global q_list
    global global_write_queue
    global global_gps_data_queues_dict

    while True:
        try:
            print 'edg_socket_server try start...'
            global_gps_data_queues_dict = shared_gps_data_queues_dict
            

            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind(('', SOCKET_SERVER_PORT))
            s.listen(2)
            print 'edg_socket_server started'

            while True:
                conn, addr = s.accept()
                print 'edg_socket_server new connection accepted... conn:', conn

                handle(conn)

                print 'edg_socket_server new connection handle done... conn:', conn

        except (KeyboardInterrupt, SystemExit):
             print 'got KeyboardInterrupt or SystemExit - exit now'
             return
        except Exception as e:                
            type_, value_, traceback_ = sys.exc_info()
            exstr = str(traceback.format_exception(type_, value_, traceback_))
            print "WARNING: edg_socket_server exception {}".format(exstr)
            
        time.sleep(5.0)  # sleep before retry bind


    

