import subprocess
import subprocess
import sys
import socket
import os
import logging
from netifaces import AF_INET, AF_INET6, AF_LINK, AF_PACKET, AF_BRIDGE
import netifaces as ni

def setup_logger(name, log_file, level=logging.INFO):
	log_handler = logging.getLogger(name)
	filehandler=logging.FileHandler(log_file, mode='w')
	filehandler.setFormatter(logging.Formatter('%(asctime)s %(processName)s %(levelname)s %(message)s'))
	log_handler.setLevel(level=level)
	log_handler.addHandler(filehandler)

def log_message(message, level):
	if(level=="ERROR"):
		log_handler.error(message)
	elif(level=="DEBUG"):
		log_handler.debug(message)
	elif(level=="WARN"):
		log_handler.warning(message)
	elif(level=="EXCEPTION"):
		log_handler.exception(message)
	else:
		log_handler.info(message)

def _exec_command(cmd):
	try:
		subprocess.call(cmd, stderr=subprocess.STDOUT, shell=True)
	except subprocess.CalledProcessError as ex:
		log_message("Encountered process error address: " + str(ex.output), "ERROR")
		return False
	except Exception as ex:
		log_message("Encountered generic exception: " + str(ex.message), "ERROR")
		return False
	log_message("Command: + " + str(cmd) +" successful", "DEBUG")
	return True

def get_data_from_host(cmd):
	try:
		output= subprocess.check_output(cmd, stdin=None, stderr=None, shell=True, universal_newlines=False).decode('utf-8')
		log_message("Command: " + str(cmd) + ": got output "  + str(output), "DEBUG")
	except subprocess.CalledProcessError as ex:
		log_message("Command: " + str(cmd) + ": got CalledProcessError " + str(ex.output), "ERROR")
		return (False, None)
	except NameError as ex:
		log_message(ex , "EXCEPTION")
		return(False, None)
	except Exception as ex:
		log_message(ex, "EXCEPTION")
		return (False, None)
	return (True, output)

def get_hostname():
	cmd = "hostname"
	output = os.popen(cmd).read()
	return output


def start():
	cmd = "service openvswitch-switch start"
	_exec_command(cmd)
	cmd = "mkdir -p /etc/docker"
	_exec_command(cmd)
	if(os.environ['DOCKER_IP']):
		cmd = "echo { \\\"insecure-registries\\\" : [\\\"" + os.environ['DOCKER_IP'] + "\\\"]}  > /etc/docker/daemon.json"
	else:
		cmd = "echo { \\\"insecure-registries\\\" : [\\\"172.17.0.1:5000\\\"]}  > /etc/docker/daemon.json"
	_exec_command(cmd)
	cmd = "service docker start"
	_exec_command(cmd)
	'''cmd = "ovs-vsctl --no-wait -- set Open_vSwitch . system-type=\"docker-ovs\""
	_exec_command(cmd)'''
	'''cmd = "ovs-vsctl --no-wait -- set Open_vSwitch . system-version=\"0.1\""
	_exec_command(cmd)'''

	cmd = "ovs-vsctl add-br br-int"
	_exec_command(cmd)
	br_ip='10.0.0.1'
	try:
		br_ip = ni.ifaddresses('eth0')[AF_INET][0]['addr']
		log_handler.info("using Bridge IP: " + str(br_ip))
	except KeyError:
		try:
			br_ip=os.environ['BR_IP']
			log_handler.info("using Bridge IP: " + str(br_ip))
		except KeyError:
			log_handler.error("Unable to identify the Bridge IP. Using default value: " + str(br_ip))
	cmd = "ovs-vsctl set Open_vSwitch . other_config:local_ip=" + str(br_ip)
	_exec_command(cmd)

	cmd = "ovs-vsctl set Open_vSwitch . other_config:stats-update-interval=50000"
	_exec_command(cmd)

	'''if "DP_ID" in os.environ:
		dp_id = '0x{0:0{1}X}'.format(int(os.environ['DP_ID']),16)
		cmd = "ovs-vsctl set Bridge br-int other-config:datapath-id=" + str(dp_id)
		_exec_command(cmd)
	else:
		log_message("No DP-ID configured. Generating DP-ID locally", "WARN")'''

	if "CONTROLLER_IP" in os.environ:
		cmd = "ovs-vsctl set-manager tcp:" + os.environ["CONTROLLER_IP"] + ":6640"
		_exec_command(cmd)
		cmd = "ovs-vsctl set-controller br-int tcp:" + os.environ["CONTROLLER_IP"] + ":6653"
		_exec_command(cmd)
	else:
		log_message("No Controller IP configured. Switch would be unconnected to CSC", "WARN")

	cmd = "ovs-vsctl set bridge br-int protocols=OpenFlow13"
	_exec_command(cmd)

	cmd = "ip link set dev br-int up"
	_exec_command(cmd)

	#cmd = "ovs-vsctl add-port br-int eth1"
	#_exec_command(cmd)
	log_message("OVS container started succesfully", "INFO")

	serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	serversocket.bind((socket.gethostname(), 32768))
	serversocket.listen(5)
	while 1:
		(clientsocket, address) = serversocket.accept()
		log_message("Received connection. Security breach", "ERROR")

if __name__ == '__main__':
	hostname = get_hostname()
	setup_logger(hostname,"/var/log/ovs-configuration.log" , level=logging.DEBUG)
	log_handler = logging.getLogger(hostname)
	start()