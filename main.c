#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <pthread.h>
#include <sys/socket.h>
#include <sys/mman.h>
#include <libgen.h>

enum {MAX_SIZE_USB_GPS_READ_BUFF = 2048, max_fn_buf_len = 1024};

struct g_shared_data {
	char g_usb_gps_read_line[MAX_SIZE_USB_GPS_READ_BUFF];
	char g_usb_gps_read_line_gpgll[MAX_SIZE_USB_GPS_READ_BUFF]; //reader proc can use this if some N previous of its access to g_usb_gps_read_line didn't match $GPGLL cases...
	char exec_dir[max_fn_buf_len];
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

int bt_server_run(int instance)
{
	enum {buf_max_len = 1024};
		
	char buf[buf_max_len] = { 0 };
	int wret;
	char usb_gps_read_line[MAX_SIZE_USB_GPS_READ_BUFF];
	FILE* p;
	char bzc_rfcomm_cmd[buf_max_len] = { 0 };

	// Open bluez-compassion rfcomm profile server
	
	printf("bt_server_run: pid %d, instance %d", getpid(), instance);

		
	printf("pre popen rfcomm server proc - exec_dir %s\n", g_shared->exec_dir);

	sprintf(bzc_rfcomm_cmd, "%s/bluez-compassion/rfcomm -p '/ecodroidgps_port_%d' -n 'spp' -s -C %d -u '0x1101'", g_shared->exec_dir, instance, instance);
	printf("bzc_rfcomm_cmd: %s\n", bzc_rfcomm_cmd);
	exit(0);
	p = popen("", "w");

	// Once connected, we can write to its tx pipe (or its stdin).

	// Make a reader to its rx pipe (or its stdout) too to avoid broken or blocked pipe cases.
	
	// write data to 
	while (1) {

		pthread_mutex_lock(&g_shared->mutex);
		strcpy(usb_gps_read_line, g_shared->g_usb_gps_read_line);
		pthread_mutex_unlock(&g_shared->mutex);

		int len = strlen(usb_gps_read_line);
		if (len) {
		  //TODO write to stdin of bt server proc - wret = write(client, usb_gps_read_line, len);
		  printf("instance %d: wret %d\n", instance, wret);
		} else {
			printf("instance %d: found read_line len 0 - sleep 1 sec to retry\n", instance);
			sleep(1);
		}
	}

	//TODO: cleanup/close the proc

	return 0;
}

int main(int argc, char **argv)
{
	enum{N_MAX_SERVERS = 7};
	enum{N_MAX_SUBPROCS = N_MAX_SERVERS+1};
	int pids[N_MAX_SUBPROCS];
	long usb_gps_read_ts = 0;
	int i;

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
