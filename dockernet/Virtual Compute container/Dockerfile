FROM sofianinho/dind:latest
MAINTAINER ashvin213@gmail.com 
RUN apt-get update 
RUN apt-get install -y apt-transport-https ca-certificates curl gnupg-agent software-properties-common lxc iptables
#RUN curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt-key add -
#RUN add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
RUN apt-get install -y python3 python3-pip
RUN apt-get update
ADD CSS_packages/*.deb /
RUN apt-get install -y iputils-arping python2.7 python-six libnuma1 kmod python-argparse module-init-tools python:any
RUN dpkg -i *.deb
#RUN apt-get install -y docker-ce docker-ce-cli containerd.io
#RUN service docker start
#RUN docker run hello-world
RUN pip3 install docker
RUN apt-get install -y net-tools iputils-ping iproute2
RUN apt-get install -y vim
RUN pip3 install netifaces
VOLUME /var/lib/docker
ADD start_script.py /
ADD create_containers.py /
ENV PATH="/:${PATH}"
EXPOSE 32768
CMD ["/usr/bin/python3.5", "/start_script.py"] 
#CMD ["bash"] 
