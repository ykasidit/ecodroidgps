FROM arm32v6/python:2.7.16-alpine3.9

COPY qemu-arm-static /usr/bin
RUN apk add --no-cache gcc musl-dev
RUN pip install cython
RUN apk add --no-cache bash