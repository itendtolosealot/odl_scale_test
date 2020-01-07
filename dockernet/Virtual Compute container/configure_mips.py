import subprocess
import argparse

def log_message(message, level):
	print(str(level) + ": " + message)

def _exec_command(cmd):
	try:
		log_message("Executing command: " + cmd + "\n", "DEBUG")
		result = subprocess.check_output([cmd], shell=True)
	except subprocess.CalledProcessError as ex:
		log_message("Encountered process error address: " + str(ex.output), "ERROR")
		return "-1".encode("utf-8")
	except Exception as ex:
		log_message("Encountered generic exception: " + str(ex), "ERROR")
		return "-1".encode("utf-8")
	log_message("Cmd:" + str(cmd) +" provided output: " + str(result), "DEBUG")
	return result

def get_interface_ip(container_name, interface_name):
	command = 'docker exec ' + container_name + ' ifconfig ' + interface_name + ' | grep inet | cut -f2 -d\"i\" | cut -f2 -d\" \"'
	try:
		res = _exec_command(command)
		return res
	except Exception as ex:
		log_message("Received exception: " + str(ex.output), "ERROR")
		return ""

def get_max_loopbacks(container_name, vm_port_name):
	command = 'docker exec ' + container_name + ' ifconfig  | grep ' +  str(vm_port_name) + ' | wc -l'
	try:
		res = _exec_command(command)
		if(repr(res)=="b'\\n'" or res == '\\n'):
			result=0
		elif (res.decode() == "-1"):
			return -100
		else:
			result = int(res)-1
		return result
	except ValueError:
		log_message("Result from command: " + str(command) + " is not a number", "ERROR")
		log_message("Obtained: " + repr(str(res)), "INFO")
		return 0
	except Exception as ex:
		log_message("Received exception: " + str(ex.output), "ERROR")
		return -1

def configure_loopback_mip(container_name, lo_interface, mip, prefix_length):
	result = " ".encode("utf-8")
	if("dummy" in lo_interface):
		command = " docker exec " + container_name + " ip link add " + str(lo_interface) + " type dummy"
		result = _exec_command(command)
	if(result.decode() != "-1"):
		command = " docker exec " + container_name + " ifconfig " + str(lo_interface) + " " + str(mip) + "/" + str(prefix_length) + " up"
		result = str(result) + str(_exec_command(command))
	return result

def get_interface(container_name, mip_address, vm_port_name):
	command = "docker exec " + container_name + " ifconfig  | grep -B 1 \"" + str(mip_address) + " \" | grep " + str(vm_port_name) + " | cut -f1 -d \" \" | rev | cut -c 2- | rev"
	result = _exec_command(command)
	return result

def unconfigure_interface(container_name, interface):
	command =  "docker exec " + container_name + " ifconfig " + str(interface) + " down"
	result = _exec_command(cmd=command)
	if("dummy" in interface):
		command = "docker exec " + container_name + " ip link del " + str(interface) + " type dummy"
		result = result +  _exec_command(cmd=command)
	return result

def add_mip(args):
	def configure_interface(container_name, intf_name, ip_address, prefix_length, ip_name="MIP"):
		result = configure_loopback_mip(container_name, intf_name, ip_address, prefix_length)
		if ("-1" in str(result)):
			log_message(" Configuration of " + ip_name + ": " + ip_address + " in container: " + container_name + " failed", "ERROR")
			return False
		else:
			log_message(" Configuration of " + ip_name + ": " + ip_address + " in container: " + container_name + " succeeded", "INFO")
			return True
	if (args.next_hop_ip == None):
		max_interfaces = get_max_loopbacks(args.cont_name, args.vm_port_name)
		if (max_interfaces != -100):
			max_interfaces = max_interfaces + 1
			result = configure_interface(args.cont_name, args.vm_port_name + ":" + str(max_interfaces), args.mip_address, args.prefix_length)
			return result
		else:
			log_message("Unable to obtain the maximum number of MIP interfaces configured on vm_port: " + str(args.vm_port_name) + " in container: " + str(args.cont_name), "ERROR")
			return False
	else:
		max_interfaces_dest = get_max_loopbacks(args.cont_name, "dummy")
		max_interfaces_nh = get_max_loopbacks(args.cont_name, args.vm_port_name)
		interface_ip = str(get_interface_ip(args.cont_name, args.vm_port_name).decode()).replace(" ", "").replace("\n", "")
		log_message("Max-Interfaces-Dest: " + str(max_interfaces_dest) + " Max-Interfaces-Nexthop: " + str(max_interfaces_nh), "DEBUG")
		if(max_interfaces_dest != -100 and max_interfaces_nh != -100):
			max_interfaces_dest += 1
			result = configure_interface(args.cont_name, "dummy" + str(max_interfaces_dest), args.mip_address, "32")
			if (result and (interface_ip != args.next_hop_ip)):
				max_interfaces_nh += 1
				result = result and configure_interface(args.cont_name, args.vm_port_name + ":" + str(max_interfaces_nh), args.next_hop_ip, "32", "Nexthop")
				if (not result):
					result_unconfig = unconfigure_interface(args.cont_name, "dummy" + ":" + str(max_interfaces_dest))
					if(result_unconfig):
						log_message(" Rollback of MIP: " + str(args.mip_address) + " on container: " + args.cont_name + " successful", "INFO")
					else:
						log_message(" Rollback of MIP: " + str(args.mip_address) + " on container: " + args.cont_name + " failed ", "ERROR")
				return result
			else:
				return result
		else:
			log_message(" Unable to obtain the maximum number of interfaces with Extraroute IPs/NH IPs", "ERROR")
			return False

def del_mip(args):
	def unconfigure(container_name, ip_address, interface_name, ip_name="MIP"):
		interface = str(get_interface(container_name, ip_address, interface_name).decode()).replace("\n","")
		int_len = len(interface)
		#interface = str(interface[0:int_len-1])
		if(interface_name in str(interface)):
			log_message(" Deleting " + ip_name + ":" + ip_address + " from interface: " + str(interface) + " on VM: " + container_name, "DEBUG")
			unconfigure_interface(container_name, interface)
			return True
		else:
			log_message("Unable to delete " + ip_name + ":" + str(ip_address) + " on VM: " + str(container_name), "ERROR")
			return False
	if (args.next_hop_ip == None):
		return unconfigure(args.cont_name, args.mip_address, args.vm_port_name)
	else:
		interface_ip = str(get_interface_ip(args.cont_name, args.vm_port_name).decode()).replace(" ", "").replace("\n", "")
		result = unconfigure(args.cont_name, args.mip_address, "dummy")
		if(interface_ip != args.next_hop_ip):
			return result and unconfigure(args.cont_name, args.next_hop_ip, args.vm_port_name, "Nexthop")
		else:
			return result

def parse_arguments():
	parser = argparse.ArgumentParser(description="Create a container & attach it to the ovs switch")
	parser.add_argument("-op", "--operation", action='store', dest="operation",help="Action add or del a container " )
	parser.add_argument("-c", "--container-name", action='store', dest="cont_name", help="Name of the container")
	parser.add_argument("-i", "--ip-address", action="store",dest="mip_address", help="MIP address to be configured")
	parser.add_argument("-p", "--vm-port-name", action="store", dest="vm_port_name", help="Name of the vm port")
	parser.add_argument("-l", "--prefix-length", action="store", dest="prefix_length", help="Length of the Prefix")
	parser.add_argument("-n", "--next-hop", action="store", dest="next_hop_ip", help = " The IP address of the next-hop in case of extra route configuration" )
	args = parser.parse_args()
	return args

if __name__ == '__main__':
	args = parse_arguments()
	result = False
	if args.operation == "add":
		result = add_mip(args)
	elif args.operation=="del":
		result = del_mip(args)
	else:
		log_message("Unsupported Operation. resulting in no-op", "ERROR")
	if (result):
		log_message(str(args.operation) +  " Operation Successful", "DEBUG")
	else:
		log_message(str(args.operation) +  " Operation failed", "ERROR")
