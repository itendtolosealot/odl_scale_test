FROM ubuntu:18.04
MAINTAINER ashvin213@gmail.com 

RUN apt-get update 
RUN apt-get install -y openvswitch-common openvswitch-switch openvswitch-dbg python3 python3-pip
RUN apt-get install -y apt-transport-https ca-certificates curl gnupg-agent software-properties-common
RUN curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt-key add -
RUN add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
RUN apt-get update
RUN apt-get install -y docker-ce docker-ce-cli containerd.io
RUN pip3 install docker
RUN apt-get install -y net-tools iputils-ping iproute2
RUN apt-get install -y vim
VOLUME /var/lib/docker
ADD start_script.py /
ADD create_containers.py /
ENV PATH="/:${PATH}"
EXPOSE 32768
CMD ["/usr/bin/python3.6", "/start_script.py"] 
#CMD ["bash"] 
