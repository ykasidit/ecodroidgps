FROM arm32v7/debian:testing

COPY qemu-arm-static /usr/bin

RUN apt-get -y update
RUN apt-get -y install python python-pip
RUN pip install cython

CMD bash