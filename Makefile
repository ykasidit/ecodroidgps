#####generic conf
SRC_FILTER = .c
LIBS  = 
CFLAGS = -I.
LDFLAGS = -lbluetooth -lpthread
CONF = .
#SOURCES := $(wildcard ./*${SRC_FILTER} )
SOURCES :=  $(shell find ./ -type f -maxdepth 1 -name '*${SRC_FILTER}')
################

#############config specific conf

ifeq ($(CONF),.)
#mkres := $(shell mkdir $(CONF))
CFLAGS += -g 
TARGET = ecodroidgps_server
CC = gcc
LD = gcc
endif


##################################

OBJS := $(patsubst ./%${SRC_FILTER}, ${CONF}/%.o, $(SOURCES))

all: $(TARGET)

$(TARGET): ${OBJS}
	$(LD) ${OBJS} ${LIBS} ${LDFLAGS} -o ${CONF}/"$(TARGET)"

${CONF}/%.o: %${SRC_FILTER}
	$(CC) $(CFLAGS) -o $@ -c $<

clean:
	rm -f ${CONF}/$(TARGET)
	rm -f $(OBJS)


