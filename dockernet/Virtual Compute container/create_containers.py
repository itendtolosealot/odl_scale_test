import subprocess
import docker
import argparse

def log_message(message, level):
	print(str(level) + ": " + message)

def _exec_command(cmd):
	try:
		subprocess.call(cmd, stderr=subprocess.STDOUT, shell=True)
	except subprocess.CalledProcessError as ex:
		log_message("Encountered process error address: " + str(ex.output), "ERROR")
		return False
	except Exception as ex:
		log_message("Encountered generic exception: " + str(ex	), "ERROR")
		return False
	log_message("Command:" + str(cmd) +" successful", "DEBUG")
	return True

def manage_veth_pair(vm_port_name, ovs_port_name, action):
	cmd = "ip link " + str(action) + " " + vm_port_name + " type veth peer name " + ovs_port_name
	result = _exec_command(cmd)
	if (not result):
		return False
	log_message("Created veth pair: " + str(vm_port_name) + "," + str(ovs_port_name), "DEBUG")
	return True

def get_set_interface_action(action, port_name, port_uuid):
	message = ""
	if action=="add-port":
		message = " -- set Interface " + str(port_name) + " external_ids:iface-id=" + str(port_uuid)
	return message

def manage_veth_ovs(ovs_port_name, ovs_bridge_name, uuid, action):
	cmd = "ovs-vsctl " + str(action) + " "+ str(ovs_bridge_name) + " " + str(ovs_port_name) + get_set_interface_action(action, ovs_port_name, uuid)
	result = _exec_command(cmd)
	if (not result):
		return False
	cmd = "ifconfig " + str(ovs_port_name) + " up"
	result = _exec_command(cmd)
	if (not result):
		return False
	#log_message(str(action) + " veth port: " + str(ovs_port_name) + " to bridge: " + str(ovs_bridge_name), "DEBUG")
	return True

def create_docker_container(cont_name, image_name):
	try:
		client = docker.from_env()
		client.containers.run(image_name, detach=True, name=cont_name, privileged=True, network_mode="none")
	except Exception as ex:
		log_message("Encountered exception while running a container: " + str(ex.message), "ERROR")
	return client

def delete_docker_container(cont_name):
	cmd = "docker stop " + str(cont_name)
	log_message("Executing: " + cmd, "DEBUG")
	result = _exec_command(cmd)
	if (not result):
		return result
	cmd = "docker rm " + str(cont_name)
	log_message("Executing: " + cmd, "DEBUG")
	result = _exec_command(cmd)
	if (not result):
		return result
	return True

def get_pid(cont_name):
	cmd = 'docker inspect ' + str(cont_name) + ' | grep \"\\\"Pid\\\"\" | cut -f2 -d\":\" | cut -f2 -d\" \"| cut -f1 -d\",\" '
	#log_message("Executing: " + str(cmd),"DEBUG")
	try:
		pid = subprocess.check_output(cmd, stdin=None, stderr=None, shell=True, universal_newlines=False).decode('utf-8')
	except subprocess.CalledProcessError as ex:
		log_message("CMD: " + str(cmd) + " encountered subprocess error : " + str(ex.output), "ERROR")
		return -1
	pid = str(pid).replace("\n","").replace('\'','').replace('\"','')
	return pid

def detach_veth_from_container(cont_name, vm_port_name):
	pid = get_pid(cont_name)
	if (pid==-1):
		log_message("container: " + str(cont_name) + " PID is unavailable. The containter must have exitted.", "ERROR")
		return False
	cmd = "ip netns exec "  + str(pid) + " ip link set " + str(vm_port_name) + " netns 1"
	#log_message("Exec: " + str(cmd), "DEBUG")
	result = _exec_command(cmd)
	if (not result):
		return result
	return True

def attach_veth_to_container(client, cont_name, vm_port_name, gateway_cidr_tuple_list, mac_address):
	pid = get_pid(cont_name)
	if (pid == -1):
		return False
	log_message("Process ID: " + str(pid), "DEBUG")
	cmd = "mkdir -p /var/run/netns"
	result = _exec_command(cmd)
	if (not result):
		return result
	#log_message("Created /var/run/netns", "DEBUG")
	cmd = 'ln -s /proc/'+str(pid)+'/ns/net /var/run/netns/'+str(pid)
	#log_message("Exec: " + str(cmd), "DEBUG")
	result = _exec_command(cmd)
	if (not result):
		return result
	cmd = 'ip link set '+ str(vm_port_name) + ' netns ' + str(pid)
	#log_message("Exec: " + str(cmd), "DEBUG")
	_exec_command(cmd)
	if (not result):
		return result

	cmd = "ip netns exec " + str(pid) + " ifconfig " + str(vm_port_name) + " hw ether " + str(mac_address)
	#log_message("Exec: " + str(cmd), "DEBUG")
	_exec_command(cmd)
	if (not result):
		return result

	cmd = "ip netns exec " + str(pid) + " ip link set dev " +  str(vm_port_name) + " up"
	#log_message("Exec: " + str(cmd), "DEBUG")
	_exec_command(cmd)
	if (not result):
		return result
	for item in gateway_cidr_tuple_list:
		(ip, gateway, cidr, ip_version) = item
		if ip_version =="4":
			space = ""
		else:
			space = "-6"
		cmd = 'ip netns exec ' + str(pid) + ' ip ' + str(space) + ' route add ' + str(cidr) + ' dev ' + str(vm_port_name)
		#log_message("Exec: " + str(cmd), "DEBUG")
		_exec_command(cmd)
		if (not result):
			return result

		cmd = "ip netns exec " + str(pid) +  " ip " + str(space) + " route add default via " + str(gateway)
		#log_message("Exec: " + str(cmd), "DEBUG")
		_exec_command(cmd)
		if (not result):
			return result
		if ip_version == "4":
			cmd = "ip netns exec " + str(pid) + " ifconfig " + str(vm_port_name)  + " " + str(ip) + "/" + str(cidr).split("/")[1]
		else:
			cmd = "ip netns exec " + str(pid) + " ifconfig " + str(vm_port_name) + " inet6 add " + str(ip) + "/" + cidr.split("/")[1]
		#log_message("Exec: " + str(cmd), "DEBUG")
		_exec_command(cmd)
		if (not result):
			return result
	return True



def parse_arguments():
	parser = argparse.ArgumentParser(description="Create a container & attach it to the ovs switch")
	parser.add_argument("-op", "--operation", action='store', dest="operation",help="Action add or del a container ")
	parser.add_argument("-c", "--container-name", action='store', dest="cont_name", help="Name of the container")
	parser.add_argument("-i", "--image-name", action="store",dest="image_name", help="Name of the docker Image")
	parser.add_argument("-o", "--ovs-port-name", action="store", dest="ovs_port_name", help="Name of the ovs port")
	parser.add_argument("-v", "--vm-port-name", action="store", dest="vm_port_name", help="Name of the vm port")
	parser.add_argument("-u", "--uuid", action="store", dest="uuid", help="UUID for the Port Interface")
	parser.add_argument("-m", "--mac-address", action="store", dest="mac_address", help="MAC address of the VM port")
	parser.add_argument("-ip", "--ip-address", action="append", dest="ip_address", default=[], help="IP addresses of the VM port")
	parser.add_argument("-g", "--gateway", action="append", dest="gateway", default=[], help="Gateway IP for the subnet")
	parser.add_argument("-ci", "--cidr", action="append", dest="cidr", default=[], help="CIDR for the subnet")
	parser.add_argument("-ve", "--ip-version", action="append", dest="ip_version", default=[], help="IP Version for the subnet")
	args = parser.parse_args()
	return args

def add_container(args):
	tuple_list = list()
	for i in range(0,len(args.ip_address)):
		tuple = (args.ip_address[i], args.gateway[i], args.cidr[i], args.ip_version[i])
		tuple_list.append(tuple)
	if (args.cont_name != None and args.image_name != None):
		client = create_docker_container(args.cont_name, args.image_name)
	else:
		log_message("Missing container name or image name", "ERROR")
		exit(0)
	if (args.vm_port_name != None and  args.ovs_port_name!=None):
		manage_veth_pair(args.vm_port_name, args.ovs_port_name, "add")
	else:
		log_message("Missing VM port name or OVS port name", "ERROR")
		exit(0)
	manage_veth_ovs(args.ovs_port_name, "br-int", args.uuid, "add-port")
	if(len(tuple_list) > 0 and args.mac_address != None):
		attach_veth_to_container(client, args.cont_name, args.vm_port_name, tuple_list, args.mac_address)
	else:
		log_message("Missing Port configuration data", "ERROR")
		exit(0)
	return True

def del_container(args):
	if (args.cont_name != None and args.vm_port_name != None):
		result = detach_veth_from_container(args.cont_name, args.vm_port_name)
		if (not result):
			log_message("Detach_veth_from_container failed", "ERROR")
			return result
		result = delete_docker_container(cont_name=args.cont_name)
		if (not result):
			return result
	else:
		log_message("Missing container name or VM port name", "ERROR")
		return False

	if (args.ovs_port_name != None):
		result = manage_veth_ovs(args.ovs_port_name, "br-int", args.uuid, "del-port")
		if (not result):
			return result
	else:
		log_message("Missing OVS port name", "ERROR")
		return False
	result = manage_veth_pair(args.vm_port_name, args.ovs_port_name, "delete")
	if (not result):
		return result
	return True


if __name__ == '__main__':
	args = parse_arguments()
	result = False
	if args.operation == "add":
		result = add_container(args)
	elif args.operation=="del":
		result = del_container(args)
	else:
		log_message("Unsupported Operation. resulting in no-op", "ERROR")
	if (result):
		log_message(str(args.operation) +  " Operation Successful", "DEBUG")
	else:
		log_message(str(args.operation) +  " Operation failed", "ERROR")
