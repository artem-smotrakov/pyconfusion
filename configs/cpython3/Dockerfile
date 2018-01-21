# the following command builds a docker image
# it should be run from the root of pyconfusion repository
#
# docker build --file configs/cpython3/Dockerfile --tag pyconfusion/cpython3 .
#
# the following commands run fuzzing for all available native modules
#
# mkdir -p results
# docker run -v `pwd`/results:/var/results pyconfusion/cpython3
#
# logs will be written to ./results directory
# ./results/fuzzed_modules will contain a list of fuzzed modules
# if the container rerun, the mofules from ./fuzzed_modules are going to be skipped
#
# use the following commands to rerun specific modules (for example, _io module)
#
# docker run -v `pwd`/results:/var/results -e MODULE=_io pyconfusion/python3
#
# if you want to do some debuging in the container,
# then use the following command to run an SSH server inside the container
#
# docker run -p 8022:22 -e DEBUG=yes pyconfusion/cpython3
#
# then you can connect to the SSH server with the following command
#
# ssh root@localhost -p 8022
#
# after you connect, you can run fuzzing in the container
#
# PYTHON=/var/python/bin/python3
# WS=/home/artem/projects/pyconfusion/ws
# ${PYTHON} ${WS}/pyconfusion.py --command fuzzer --modules _io --exclude ${WS}/configs/cpython3/exclude_list
#
# good luck!
#

FROM ubuntu:16.04

MAINTAINER artem.smotrakov@gmail.com

# install software
RUN apt-get update
RUN apt-get install -y git
RUN apt-get install -y make
RUN apt-get install -y gcc
RUN apt-get install -y mercurial
RUN apt-get install -y zlibc zlib1g-dev
RUN apt-get install -y libtcl8.6 libtclcl1-dev libtk8.6 tk-dev
RUN apt-get install -y libffi6 libffi-dev
RUN apt-get install -y libreadline5 libreadline-dev
RUN apt-get install -y libgdbm3 libgdbm-dev
RUN apt-get install -y libncurses5 libncurses-dev
RUN apt-get install -y liblzma5 liblzma-dev
RUN apt-get install -y libbz2-1.0 libbz2-dev
RUN apt-get install -y libsqlite3-0 libsqlite3-dev
RUN apt-get install -y openssl libssl1.0.0 libssl-dev

ENV RESULTS=/var/results

# prepare directories
RUN mkdir -p /var/src
RUN mkdir -p /var/python
RUN mkdir -p ${RESULTS}

# clone latest CPython
RUN hg clone https://hg.python.org/cpython /var/src/python
ENV SRC=/var/src/python
WORKDIR /var/src/python

# build CPython with AddressSanitizer
ENV ASAN_OPTIONS="detect_leaks=0 allocator_may_return_null=1"
RUN ./configure --prefix=/var/python --with-pydebug --with-address-sanitizer
RUN make -s -j2
RUN make install

ENV PYTHON=/var/python/bin/python3

# smoke test
RUN ${PYTHON} --version

# configure an SSH server in case we want to debug remotely
RUN apt-get install -y openssh-server
RUN mkdir /var/run/sshd
RUN echo 'root:changeme' | chpasswd
RUN sed -i 's/PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config
RUN sed 's@session\s*required\s*pam_loginuid.so@session optional pam_loginuid.so@g' -i /etc/pam.d/sshd
ENV NOTVISIBLE "in users profile"
RUN echo "export VISIBLE=now" >> /etc/profile
EXPOSE 22

# add pyconfusion
ADD . /var/src/pyconfusion
ENV WS=/var/src/pyconfusion

WORKDIR ${RESULTS}

# look for available native modules
RUN bash ${WS}/scripts/find_native_modules.sh > /var/all_native_modules

# fuzzing configuration
ENV EXCLUDE_LIST=${WS}/configs/cpython3/exclude_list
ENV FUZZED_MODULES=${RESULTS}/fuzzed_modules
ENV MODULES=/var/all_native_modules

CMD [ "bash", "/var/src/pyconfusion/configs/cpython3/wrapper.sh" ]
