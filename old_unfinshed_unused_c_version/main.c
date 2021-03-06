#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <unistd.h>
#include <pthread.h>
#include <sys/socket.h>
#include <sys/mman.h>
#include <libgen.h>

enum {MAX_SIZE_USB_GPS_READ_BUFF = 1024, max_fn_buf_len = 1024};

struct g_shared_data {
	char g_usb_gps_read_line[MAX_SIZE_USB_GPS_READ_BUFF];
	char g_usb_gps_read_line_gpgll[MAX_SIZE_USB_GPS_READ_BUFF]; //reader proc can use this if some N previous of its access to g_usb_gps_read_line didn't match $GPGLL cases...
	uint64_t g_usb_gps_read_line_id; //dont write g_usb_gps_read_line if the id hasn't changed
	char exec_dir[max_fn_buf_len];
	pthread_mutex_t mutex;
};

struct g_shared_data* g_shared = NULL;

int print_nmea = 0;

int usb_gps_reader_run(char* gps_dev_path)
{
	FILE* f;	

	char *usb_gps_read_line = NULL; //[MAX_SIZE_USB_GPS_READ_BUFF];
	size_t usb_gps_read_line_buf_len = 0;
	size_t usb_gps_read_line_len = 0;

	/*
	  getline() manual

	  If  *lineptr  is set to NULL and *n is set 0 before the call, then get‐
	  line() will allocate a buffer for storing the line.  This buffer should
	  be freed by the user program even if getline() failed.
	 */

	f = fopen(gps_dev_path,"r");
	
	if (!f) {
		printf("FATAL: failed to open gps_dev_path: %s\n", gps_dev_path);
		return -1;
	}

	while (1) {
		
		usb_gps_read_line_len = getline(&usb_gps_read_line, &usb_gps_read_line_buf_len, f);
		//printf("reader: usb_gps_read_line_len: %d\n", usb_gps_read_line_len);

		if (usb_gps_read_line_len > 1) {
			
			if (1) {
				printf("USB READ >> usb_gps_read_line: %s\n",usb_gps_read_line);
				printf("USB READ >> usb_gps_read_line_len: %lu\n",usb_gps_read_line_len);
			}

			pthread_mutex_lock(&g_shared->mutex);
			strncpy(g_shared->g_usb_gps_read_line, usb_gps_read_line, MAX_SIZE_USB_GPS_READ_BUFF);
			/*  Warning: If there is no null byte among the first n  bytes
			    of src, the string placed in dest will not be null-terminated.
			*/
			g_shared->g_usb_gps_read_line[MAX_SIZE_USB_GPS_READ_BUFF-1] = 0;
			printf("set usb_gps_read_line: [%s]\n", g_shared->g_usb_gps_read_line);
			pthread_mutex_unlock(&g_shared->mutex);

			if (strstr(usb_gps_read_line, "$GPGLL")) {
				pthread_mutex_lock(&g_shared->mutex);
				strncpy(g_shared->g_usb_gps_read_line_gpgll, usb_gps_read_line, MAX_SIZE_USB_GPS_READ_BUFF);
				g_shared->g_usb_gps_read_line_gpgll[MAX_SIZE_USB_GPS_READ_BUFF-1] = 0;
				pthread_mutex_unlock(&g_shared->mutex);
			}
				
			g_shared->g_usb_gps_read_line_id++;
			
		} else {
			printf("WARNING: got ! > 1 size buff read from gps_dev_file - skip saving it\n");
		}
	}

	fclose(f);

	return 0;
}

int bt_server_run(int instance)
{
	enum {buf_max_len = 1024};
		
	char buf[buf_max_len] = { 0 };
	int wret;
	char usb_gps_read_line[MAX_SIZE_USB_GPS_READ_BUFF];
	uint64_t usb_gps_read_line_id;
	uint64_t written_usb_gps_read_line_id = 0;
	FILE* subp;
	char bzc_rfcomm_cmd[buf_max_len] = { 0 };
	int microsecs_to_wait_if_id_hasnt_changed = 500*1000; //500ms

	// Open bluez-compassion rfcomm profile server
	
	printf("bt_server_run: pid %d, instance %d", getpid(), instance);

		
	printf("pre popen rfcomm server proc - exec_dir %s\n", g_shared->exec_dir);

	sprintf(bzc_rfcomm_cmd, "/bin/bash -c \"while true; do %s/bluez-compassion/rfcomm -p '/ecodroidgps_port_%d' -n 'EcoDroidGPS Serial Port %d' -s -C %d -u '0x1101' ; echo 'bluez-compassion/rfcomm%d has exit'; sleep 3; done\"", g_shared->exec_dir, instance, instance, instance, instance);
	printf("bzc_rfcomm_cmd: %s\n", bzc_rfcomm_cmd);
	subp = popen(bzc_rfcomm_cmd, "w");

	if (subp == NULL) {
		printf("FATAL: bt_server_run: pid %d, instance %d popen returned null - ABORT\n", getpid(), instance);
		return -1;
	}

	int fd = fileno(subp);	
		
	// Once connected, we can write to its tx pipe (or its stdin).

	// Make a reader to its rx pipe (or its stdout) too to avoid broken or blocked pipe cases.
	
	// write data to 
	while (1) {

		pthread_mutex_lock(&g_shared->mutex);
		usb_gps_read_line_id = g_shared->g_usb_gps_read_line_id;
		pthread_mutex_unlock(&g_shared->mutex);
		if (written_usb_gps_read_line_id == usb_gps_read_line_id) {
			if (print_nmea)
				printf("instance %d: usb_gps_read_line_id hasn't changed - wait...\n", instance);
			usleep(microsecs_to_wait_if_id_hasnt_changed);
			continue;
		}

		written_usb_gps_read_line_id = usb_gps_read_line_id;		

		pthread_mutex_lock(&g_shared->mutex);
		strncpy(usb_gps_read_line, g_shared->g_usb_gps_read_line, MAX_SIZE_USB_GPS_READ_BUFF);
		usb_gps_read_line[MAX_SIZE_USB_GPS_READ_BUFF - 1] = 0;
		pthread_mutex_unlock(&g_shared->mutex);
			
		int len = strlen(usb_gps_read_line);
		if (len) {
		  //write to stdin of bt server proc
			printf("bt_server_run: instance %d writing str len %d line: [%s]\n", instance, len, usb_gps_read_line);
			wret = write(fd, usb_gps_read_line, len);
			if (print_nmea) {
				printf("bt_server_run: instance %d: pre write usb_gps_read_line: %s\n", instance, usb_gps_read_line);
			}
			printf("bt_server_run: instance %d: wret %d\n", instance, wret);
			if (wret == 0) {
				printf("bt_server_run: WARNING: 0 bytes written - instance %d: wret %d\n", instance, wret);
			}
		} else {
			printf("bt_server_run: instance %d: found read_line len 0 - sleep 1 sec to retry\n", instance);
			sleep(1);
		}
	}

	printf("bt_server_run: instance %d closing subp\n", instance);
	
	pclose(subp);
	subp = NULL;

	printf("bt_server_run: instance %d exit\n", instance);

	return 0;
}

void prepare_bt_dev(char* dir)
{
	int ret;
	char cmd[512];
	char* bluez_compassion_folder_name = "bluez-compassion";
	
	sprintf(cmd, "%s/%s/hciconfig -a hci0 up", dir, bluez_compassion_folder_name);
	ret = system(cmd);
	printf("prepare_bt_dev: ret: %d for cmd: %s\n", ret, cmd);

	sprintf(cmd, "%s/%s/hciconfig -a hci0 piscan", dir, bluez_compassion_folder_name);
	ret = system(cmd);
	printf("prepare_bt_dev: ret: %d for cmd: %s\n", ret, cmd);
	
	sprintf(cmd, "%s/%s/hciconfig -a hci0 pairable 1", dir, bluez_compassion_folder_name);
	ret = system(cmd);
	printf("prepare_bt_dev: ret: %d for cmd: %s\n", ret, cmd);

	sprintf(cmd, "killall edl_agent ; %s/%s/edl_agent &", dir, bluez_compassion_folder_name);
	ret = system(cmd);
	printf("prepare_bt_dev: ret: %d for cmd: %s\n", ret, cmd);
}

int main(int argc, char **argv)
{
	enum{N_MAX_SERVERS = 1};
	enum{N_MAX_SUBPROCS = N_MAX_SERVERS+1};
	int pids[N_MAX_SUBPROCS];
	long usb_gps_read_ts = 0;
	int i;

	if (argc < 2) {
		if (argc == 1)
			printf("usage: %s <usb_gps_char_dev>\n", argv[0]);
		else
			printf("usage: this_binary <usb_gps_char_dev>\n");
		exit(1);
	}

	char exec_path[max_fn_buf_len] = { 0 };
	int rret = readlink("/proc/self/exe", exec_path, max_fn_buf_len);

	if (rret <= 0) {
		printf("FATAL: read exec_path failed %d - ABORT\n", rret);
		exit(rret);
	}

	char* dir = dirname(exec_path);
	if (dir == NULL) {
		printf("FATAL: get exec_dir failed got NULL from dirname() - ABORT\n");
		exit(rret);
	}

	prepare_bt_dev(dir);	

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

	printf("got exec dir: %s - copy to g_shared\n", dir);
	strcpy(g_shared->exec_dir, dir);

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
				int ret;
				while (1) {
					printf("usb_gps_reader_run: starting...\n");
					ret = usb_gps_reader_run(argv[1]);
					printf("WARNING: usb_gps_reader_run exit with code %d - restart it after 3 secs\n", ret);
					sleep(3);
				}
				
			} else {
				//take the read usb gps buffer and write to connected bt clients...
				int ret;
				while (1) {
					printf("bt_server_run: instance %d starting...\n", i);
					ret = bt_server_run(i);
					printf("WARNING: bt_server_run instance %d exit with code %d - restart it after 3 secs\n", i, ret);
					sleep(3);
				}
				
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
		strncpy(usb_gps_read_line, g_shared->g_usb_gps_read_line, MAX_SIZE_USB_GPS_READ_BUFF);
		usb_gps_read_line[MAX_SIZE_USB_GPS_READ_BUFF-1] = 0;
		pthread_mutex_unlock(&g_shared->mutex);
		if (1) {
			printf("father_proc: g_usb_gps_read_line: %s\n", usb_gps_read_line);
		}
	};

	return 0;
}
