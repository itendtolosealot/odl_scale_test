import time
import logging
import uuid
import math
import random

class Test():
	def __init__(self):
		self._setup_logger("mip-test", "/home/stack/mininet_handler/mip_test.log", level=logging.DEBUG)
		self._log_handler = logging.getLogger("mip-test")
		self._mininet_data = dict()
		self._mininet_data['subnet'] = dict()
		self._mininet_data['subnet_mips'] = dict()
		self._mininet_data['subnet_port_map']=dict()

	def _store_data(self, type, uuid, data):
		try:
			self._mininet_data[type][uuid] = data
			return True
		except KeyError as ke:
			self._log_handler.error("Obtained KeyError when storing data: " + str(data) + " of type: " + str(type) + " with uuid: " + str(uuid))
			self._log_handler.error("Error message: " + str(ke.message))
			return False
		except Exception as ex:
			template = "An exception of type {0} occurred. Arguments:\n{1!r}"
			message = template.format(type(ex).__name__, ex.args)
			self._log_handler.error(message)
			return False

	def _get_data(self, type, uuid):
		try:
			data = self._mininet_data[type][uuid]
			return (True, data)
		except KeyError as ke:
			self._log_handler.warning("Obtained KeyError when attempting to read data  of type: " + str(type) + " with uuid: " + str(uuid))
			self._log_handler.warning("Warning message: " + str(ke.message))
			return (False, None)
		except Exception as ex:
			template = "An exception of type {0} occurred. Arguments:\n{1!r}"
			message = template.format(type(ex).__name__, ex.args)
			self._log_handler.error(message)
			return (False, None)

	def _setup_logger(self,name, log_file, level=logging.INFO):
		log_handler = logging.getLogger(name)
		self._filehandler=logging.FileHandler(log_file, mode='w')
		self._filehandler.setFormatter(logging.Formatter('%(asctime)s %(processName)s %(levelname)s %(message)s'))
		log_handler.setLevel(level=level)
		log_handler.addHandler(self._filehandler)

	def get_prefix_for_ipv6(self,cidr):
		cidr_split = cidr.split("/")
		prefix_length = int(cidr_split[1])
		if (prefix_length % 16 != 0):
			self._log_handler.error("CIDR: " + str(cidr) + " has a prefix length that is not a multiple of 16.")
			return (False, None)
		actual_prefix = cidr_split[0].replace("::","")
		prefix_split = actual_prefix.split(":")
		actual_length = len(prefix_split)*16
		count = actual_length
		while(count < prefix_length):
			prefix_split.append("0000")
			count = count+ 16
		prefix = ":".join(prefix_split) + ":"
		
		return (True, prefix, prefix_length)

	def get_prefix_for_ipv4(self,cidr):
		cidr_split = cidr.split("/")
		return (True, cidr_split[0], cidr_split[1])

	def get_mip_list(self, prefix, prefix_length, ip_version, neutron_ips, num_mips):
		def get_ipv6_mip():
			mip_list = list()
			mip_count = 0
			while(mip_count < num_mips):
				eui_64 = str(uuid.uuid4()).replace("-", "")
				required_nibbles = (128-prefix_length)/4
				eui_actual = eui_64[0:required_nibbles]
				mip_ip_eui = [(eui_actual[i:i+4]) for i in range (0, len(eui_actual), 4)]
				mip = prefix +  ":".join(mip_ip_eui)
				if (mip not in neutron_ips) and (mip not in mip_list):
					mip_list.append(mip)
					mip_count=mip_count+1
			return (True, mip_list)
		def get_ipv4_mip():
			mip_list = list()
			prefix_split = prefix.split(".")
			self._log_handler.debug("Split prefix: " + str(prefix_split))
			start_index = 1
			count = 0
			mip_count = 0
			while mip_count < num_mips:
				while int(prefix_split[3]) + start_index + count < 255:
					mip_tail = str(int(prefix_split[3]) + start_index + count)
					mip_pieces = [prefix_split[x] for x in range(4)]
					mip_pieces[3]= mip_tail
					mip = ".".join(mip_pieces)
					self._log_handler.debug("mip : " + str(mip))
					count = count + 1
					if (mip not in neutron_ips) and (mip not in mip_list):
						mip_count = mip_count +1
						mip_list.append(mip)
						break
			if (mip_count == num_mips):
				return (True, mip_list)
			else:
				self._log_handler.error("Exhausted all IPs")
				return (False, mip_list)

		if (ip_version == "4"):
			return get_ipv4_mip()
		elif (ip_version=="6"):
			return get_ipv6_mip()
		else:
			self._log_handler.error("Unknown IP Version")
			return "Error! Unknown IP Version"

	def handle_mip_creation_for_subnet(self, num_of_mips, sub_uuid):
		_ip_version_dict = {
			"4": self.get_prefix_for_ipv4,
			"6": self.get_prefix_for_ipv6
		}
		(result, sub_info) = self._get_data("subnet", sub_uuid)
		cidr = sub_info['cidr']
		(result, port_uuid_ip_list) = self._get_data("subnet_port_map", sub_uuid)
		port_uuid_list = list()
		ip_addr_list = list()
		if result:
			self._log_handler.debug("Size of the array port_uuid_ip_list : " + str(len(port_uuid_ip_list)))
			self._log_handler.debug("port_uuid_ip_list: " + str(port_uuid_ip_list))
			(port_uuid_list, ip_addr_list) = list(zip(*port_uuid_ip_list))
		else:
			print("Unable to get any data for subnet: " + str(sub_uuid))
			self._log_handler.warning("Unable to get any data for subnet: " + str(sub_uuid))
			return
		self._mininet_data["subnet_mips"][sub_uuid] = list()
		prefix_info = _ip_version_dict[sub_info["ip_version"]](cidr)
		if(not prefix_info[0]):
			self._log_handler.warning("Unable to create MIPs for Subnet: " + str(sub_uuid))
			return
		prefix = prefix_info[1]
		prefix_length = prefix_info[2]
		(result, mip_list) = self.get_mip_list(prefix,prefix_length,sub_info["ip_version"], ip_addr_list, num_of_mips)
		if (result):
			for mip in mip_list:
				self._log_handler.debug("For subnet: " + str(sub_uuid) + " with IP version: " + sub_info["ip_version"] + " obtained MIP: " + str(mip))
			self._store_data("subnet_mips", sub_uuid, mip_list)
			return mip_list
		else:
			self._log_handler.error("Unable to process MIP creation. Exiting...")
			return


	def test_mip(self, num_of_mips, num_of_subnets):
		for i in range(0,num_of_subnets):
			sub_uuid = str(uuid.uuid4())
			data = dict()
			data['id'] = sub_uuid
			'''
			cidr = str(uuid.uuid4()).replace("-","")
			prefix_length = random.randint(1,7)*16			
			cidr = cidr[0:int(prefix_length/4)]
			cidr_split = [(cidr[i:i+4]) for i in range (0, len(cidr), 4)]
			cidr = ":".join(cidr_split) +"/"+str(prefix_length)
			'''
			init_value = 2001 + i
			cidr = str(init_value)+"::/48"
			data['cidr'] = cidr
			data['ip_version'] = "6"
			self._store_data("subnet", sub_uuid, data)
			self._log_handler.debug("Stored subnet: " + str(sub_uuid) + "with cidr: " + str(cidr))
			port_uuid_ip = (str(uuid.uuid4()), "Hello")
			port_uuid_ip_list = list()
			port_uuid_ip_list.append(port_uuid_ip)
			self._store_data("subnet_port_map", sub_uuid, port_uuid_ip_list)

		for key in self._mininet_data["subnet"].keys():
			self.handle_mip_creation_for_subnet(num_of_mips,key)

		for key in self._mininet_data["subnet_mips"].keys():
			(res,mips) = self._get_data("subnet_mips", key)
			self._log_handler.debug("MIPs for Subnet: " + str(key) + " are: " + str(mips))


if __name__ == '__main__':
	my_test = Test()
	my_test.test_mip(2,2)


