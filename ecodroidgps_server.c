#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/socket.h>
#include <sys/mman.h>

#include <bluetooth/bluetooth.h>
#include <bluetooth/rfcomm.h>
#include <pthread.h>

#include <bluetooth/sdp.h>
#include <bluetooth/sdp_lib.h>

enum {MAX_SIZE_USB_GPS_READ_BUFF = 2048};

struct g_shared_data {
	char g_usb_gps_read_line[MAX_SIZE_USB_GPS_READ_BUFF];
	char g_usb_gps_read_line_gpgll[MAX_SIZE_USB_GPS_READ_BUFF]; //reader proc can use this if some N previous of its access to g_usb_gps_read_line didn't match $GPGLL cases...
	pthread_mutex_t mutex;
};

struct g_shared_data* g_shared = NULL;

int print_nmea = 0;

int usb_gps_reader_run()
{
	FILE* f;
	char* gps_dev_path = "/dev/ttyACM0";
	char* ret_fgets;

	char usb_gps_read_line[MAX_SIZE_USB_GPS_READ_BUFF];
	int usb_gps_read_line_len = 0;

	f = fopen(gps_dev_path,"r");
	if (!f) {
		printf("FATAL: failed to open gps_dev_path: %s\n", gps_dev_path);
		return -1;
	}

	while (1) {
		usb_gps_read_line[0] = 0;
		ret_fgets = fgets(usb_gps_read_line, MAX_SIZE_USB_GPS_READ_BUFF, f);
		usb_gps_read_line_len = strlen(usb_gps_read_line);

		if (usb_gps_read_line_len) {
			if (usb_gps_read_line_len > 1) {
				if (print_nmea) {
					printf("usb_gps_read_line: %s\n",usb_gps_read_line);
					printf("usb_gps_read_line_len: %d\n",usb_gps_read_line_len);
				}

				pthread_mutex_lock(&g_shared->mutex);
				strcpy(g_shared->g_usb_gps_read_line, usb_gps_read_line);
				pthread_mutex_unlock(&g_shared->mutex);

				if (strstr(usb_gps_read_line, "$GPGLL")) {
					pthread_mutex_lock(&g_shared->mutex);
					strcpy(g_shared->g_usb_gps_read_line_gpgll, usb_gps_read_line);
					pthread_mutex_unlock(&g_shared->mutex);
				}

			}
		} else {
			printf("FATAL: got 0 size buff read from gps_dev_file - ABORT\n");
			return -2;
		}
	}

	fclose(f);

	return 0;
}

sdp_session_t* register_service(int channel);
	
int bt_server_run(int instance)
{
	struct sockaddr_rc loc_addr = { 0 }, rem_addr = { 0 };
	char buf[1024] = { 0 };
	int s, client, bytes_read;
	socklen_t opt = sizeof(rem_addr);
	int wret;
	char usb_gps_read_line[MAX_SIZE_USB_GPS_READ_BUFF];

	sdp_session_t* sdp_session = register_service(instance);

	printf("bt_server_run: pid %d, instance %d", getpid(), instance);

	// allocate socket
	s = socket(AF_BLUETOOTH, SOCK_STREAM, BTPROTO_RFCOMM);

	// bind socket to port 1 of the first available 
	// local bluetooth adapter
	loc_addr.rc_family = AF_BLUETOOTH;
	loc_addr.rc_bdaddr = *BDADDR_LOCAL;
	loc_addr.rc_channel = (uint8_t) instance;

	printf("pre bind to channel %d\n", loc_addr.rc_channel);
	bind(s, (struct sockaddr *)&loc_addr, sizeof(loc_addr));

	printf("pre listen\n");
	// put socket into listening mode
	listen(s, 1);

	printf("pre accept\n");
	// accept one connection
	client = accept(s, (struct sockaddr *)&rem_addr, &opt);

	ba2str( &rem_addr.rc_bdaddr, buf );
	fprintf(stderr, "accepted connection from %s\n", buf);
	memset(buf, 0, sizeof(buf));

	// write data to client
	while (1) {

		pthread_mutex_lock(&g_shared->mutex);
		strcpy(usb_gps_read_line, g_shared->g_usb_gps_read_line);
		pthread_mutex_unlock(&g_shared->mutex);

		int len = strlen(usb_gps_read_line);
		if (len) {
			wret = write(client, usb_gps_read_line, len);
			printf("instance %d: wret %d\n", instance, wret);
		} else {
			printf("instance %d: found read_line len 0 - sleep 1 sec to retry\n", instance);
			sleep(1);
		}
	}

	/*
	bytes_read = read(client, buf, sizeof(buf));
	if( bytes_read > 0 ) {
		printf("received [%s]\n", buf);
	}
	*/

	// close connection
	close(client);
	close(s);

	return 0;
}


sdp_session_t* register_service(int target_channel)
{
    uint32_t service_uuid_int[] = { 0, 0, 0, 0xABCD };
    uint8_t rfcomm_channel = target_channel;

    char service_name[256];
    sprintf(service_name, "COM%d", target_channel);

    char service_desc[256];
    sprintf(service_desc,"NMEA GPS SERIAL PORT %d", target_channel);

    char* service_prov = "ClearEvo.com DynGPS";

    uuid_t root_uuid, l2cap_uuid, rfcomm_uuid, svc_uuid, service_class_uuid;
    sdp_list_t *l2cap_list = 0, 
               *rfcomm_list = 0,
               *root_list = 0,
               *proto_list = 0, 
	    *access_proto_list = 0,
	    *service_class_list = 0;
    
    sdp_data_t *channel = 0, *psm = 0;

    sdp_record_t *record = sdp_record_alloc();

    printf("rs0\n");
    
    // set the general service ID
    sdp_uuid128_create( &svc_uuid, &service_uuid_int );
    sdp_set_service_id( record, svc_uuid );

    sdp_uuid16_create(&service_class_uuid, SERIAL_PORT_SVCLASS_ID);
    service_class_list = sdp_list_append( 0, &service_class_uuid);
    sdp_set_service_classes( record,  service_class_list);

    printf("rs1\n");

    // make the service record publicly browsable
    sdp_uuid16_create(&root_uuid, PUBLIC_BROWSE_GROUP);
    root_list = sdp_list_append(0, &root_uuid);
    sdp_set_browse_groups( record, root_list );

    printf("rs2\n");
    
    // set l2cap information
    sdp_uuid16_create(&l2cap_uuid, L2CAP_UUID);
    l2cap_list = sdp_list_append( 0, &l2cap_uuid );
    proto_list = sdp_list_append( 0, l2cap_list );

    printf("rs3\n");

    // set rfcomm information
    sdp_uuid16_create(&rfcomm_uuid, RFCOMM_UUID);
    channel = sdp_data_alloc(SDP_UINT8, &rfcomm_channel);
    rfcomm_list = sdp_list_append( 0, &rfcomm_uuid );
    sdp_list_append( rfcomm_list, channel );
    sdp_list_append( proto_list, rfcomm_list );

    printf("rs4\n");
    
    // attach protocol information to service record
    access_proto_list = sdp_list_append( 0, proto_list );
    sdp_set_access_protos( record, access_proto_list );

    printf("rs5\n");
    
    // set the name, provider, and description
    sdp_set_info_attr(record, service_name, service_prov, service_desc);

    printf("rs6\n");

    //////////////////////

    int err = 0;
    sdp_session_t *session = 0;

    // connect to the local SDP server, register the service record, and 
    // disconnect
    printf("sdpconnect start\n");
    session = sdp_connect( BDADDR_LOCAL, BDADDR_LOCAL, SDP_RETRY_IF_BUSY );
    printf("sdpconnect ret %ld\n", (long) session);
    err = sdp_record_register(session, record, 0);

    printf("rs7\n");
    
    // cleanup
    sdp_data_free( channel );
    sdp_list_free( l2cap_list, 0 );
    sdp_list_free( rfcomm_list, 0 );
    sdp_list_free( root_list, 0 );
    sdp_list_free( access_proto_list, 0 );

    printf("rs8\n");
    
    return session;
}

int main(int argc, char **argv)
{
	enum{N_MAX_SERVERS = 7};
	enum{N_MAX_SUBPROCS = N_MAX_SERVERS+1};
	int pids[N_MAX_SUBPROCS];
	long usb_gps_read_ts = 0;
	int i;

	g_shared = mmap(
		NULL,
		sizeof(struct g_shared_data),
		PROT_READ | PROT_WRITE, 
		MAP_SHARED | MAP_ANONYMOUS,
		-1,
		0);

	if (g_shared == NULL) {
		printf("FATAL: failed to mmap mem for g_usb_gps_read_line\n");
		exit(-9);
	}
	pthread_mutexattr_t attr;
	pthread_mutexattr_init(&attr);
	pthread_mutexattr_setpshared(&attr, PTHREAD_PROCESS_SHARED);
	pthread_mutex_init(&g_shared->mutex, &attr);

	for (i = 0; i < N_MAX_SUBPROCS; i++) {
		int pid;
		pid = fork();
		if (pid == -1) {
			perror("fork() failed");
			exit(1);
		}


		if (pid == 0) {

			//child proc

			if (i == 0) {
				//read from usb gps into buffer
				usb_gps_reader_run();
			} else {
				//take the read usb gps buffer and write to connected bt clients...
				bt_server_run(i);
			}
			break;
		} else {
			printf("forked instance %d got pid %d\n",i , pid);
			pids[i] = pid;
			continue;
		}
	}

	char usb_gps_read_line[MAX_SIZE_USB_GPS_READ_BUFF];
	while (1) {
		sleep(1);

		pthread_mutex_lock(&g_shared->mutex);
		strcpy(usb_gps_read_line, g_shared->g_usb_gps_read_line);
		pthread_mutex_unlock(&g_shared->mutex);
		if (print_nmea) {
			printf("father_proc: g_usb_gps_read_line: %s\n", usb_gps_read_line);
		}
	};

	return 0;
}
