import subprocess
import socket
import os
def log_message(message, level):
	print(str(level) + ": " + message)

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

def get_eth1_ip():
	cmd = "ifconfig eth1 | grep \"inet\" | cut -f10 -d\" \""
	try:
		eth1_ip= subprocess.check_output(cmd, stdin=None, stderr=None, shell=True, universal_newlines=False).decode('utf-8')
		log_message("Identified eth1 bridge IP: " + str(eth1_ip), "DEBUG")
	except subprocess.CalledProcessError as ex:
		log_message("Creation of switch container failed " + str(ex.output), "ERROR")
		return (False, None)
	except Exception as ex:
		log_message("Encountered generic exception: " + str(ex.message), "ERROR")
		return (False, None)

	return (True, eth1_ip)

def start():
	cmd = "service openvswitch-switch start"
	_exec_command(cmd)
	cmd = "mkdir -p /etc/docker"
	_exec_command(cmd)
	cmd = "echo { \\\"insecure-registries\\\" : [\\\"172.17.0.1:5000\\\"]}  > /etc/docker/daemon.json"
	_exec_command(cmd)
	cmd = "service docker start"
	_exec_command(cmd)
	cmd = "ovs-vsctl --no-wait -- set Open_vSwitch . system-type=\"docker-ovs\""
	_exec_command(cmd)
	cmd = "ovs-vsctl --no-wait -- set Open_vSwitch . system-version=\"0.1\""
	_exec_command(cmd)

	cmd = "ovs-vsctl add-br br-int"
	_exec_command(cmd)
	result, br_ip = get_eth1_ip()

	if (not result and "BR_IP" in os.environ):
		br_ip = os.environ["BR_IP"]
	if (not result and "BR_IP" not in os.environ):
		br_ip = "10.0.0.1"

	cmd = "ovs-vsctl set Open_vSwitch . other_config:local_ip=" + str(br_ip)
	_exec_command(cmd)

	cmd = "ovs-vsctl set Open_vSwitch . other_config:stats-update-interval=50000"
	_exec_command(cmd)

	cmd = "ip link set dev br-int up"
	_exec_command(cmd)

	cmd = "ovs-vsctl set bridge br-int protocols=OpenFlow13"
	_exec_command(cmd)

	if "DP_ID" in os.environ:
		cmd = "ovs-vsctl set Bridge br-int other-config:datapath-id=0x" + str(os.environ["DP_ID"])
		_exec_command(cmd)
	else:
		log_message("No DP-ID configured. Generating DP-ID locally", "WARN")
	if "CONTROLLER_IP" in os.environ:
		cmd = "ovs-vsctl set-manager tcp:" + os.environ["CONTROLLER_IP"] + ":6640"
		_exec_command(cmd)
		cmd = "ovs-vsctl set-controller br-int tcp:" + os.environ["CONTROLLER_IP"] + ":6653"
		_exec_command(cmd)
	else:
		log_message("No Controller IP configured. Switch would be unconnected to CSC", "WARN")
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
	start()