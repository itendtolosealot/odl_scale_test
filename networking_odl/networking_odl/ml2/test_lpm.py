import time
import yaml
import ast
import threading
import logging
import uuid
import socket
import random
import queue
import plyvel
import sys
import math
import ipaddress

class test_lpm():
	def __init__(self):
		self._mininet_data = dict()
		self._locks = dict()
		self._databases = list(['network', 'subnet', 'port', 'router', 'subnet_port_map', 'dhcp_server', 'port_to_ip_mapping', 'gateway_ip', 'subnet_mips', 'ip_to_port_mapping', 'subnet_to_router_map'])
		for key in self._databases:
			self._mininet_data[key] = dict()
			self._locks[key] = threading.Lock()
		self._setup_logger("Thrift-Server", "/home/stack/mininet_handler/mininet_handler.log", level=logging.DEBUG)
		self._db_loc = '/home/stack/mininet_handler/db/'
		self._log_handler = logging.getLogger("Thrift-Server")

	def _setup_logger(self,name, log_file, level=logging.INFO):
		log_handler = logging.getLogger(name)
		self._filehandler=logging.FileHandler(log_file, mode='w')
		self._filehandler.setFormatter(logging.Formatter('%(asctime)s %(processName)s %(levelname)s %(message)s'))
		log_handler.setLevel(level=level)
		log_handler.addHandler(self._filehandler)

	def get_prefix_for_ipv6(self,address, type='subnet'):
		address_type = {
			"subnet" : ipaddress.ip_network,
			"address" : ipaddress.ip_address
		}
		unicode_address = unicode(address,'utf-8')
		try:
			addr = address_type[type](unicode_address)
			if(type=='subnet'):
				return (True, addr.exploded, addr.prefixlen)
			else:
				return (True, addr.exploded, 128)
		except ipaddress.AddressValueError as ex:
			self._log_handler.error("Could not convert " + str(address) + " to an ipaddress")
			return (False, None, None)

	def get_prefix_for_ipv4(self,cidr):
		cidr_split = cidr.split("/")
		return (True, cidr_split[0], cidr_split[1])

	def _store_data(self, type, uuid, data):
		try:
			self._locks[type].acquire()
			self._mininet_data[type][uuid] = data
			self._locks[type].release()
			return True
		except KeyError as ke:
			self._log_handler.error("Obtained KeyError when storing data: " + str(data) + " of type: " + str(type) + " with uuid: " + str(uuid))
			self._log_handler.error("Error message: " + str(ke.message))
			self._locks[type].release()
			return False
		except Exception as ex:
			template = "An exception of type {0} occurred. Arguments:\n{1!r}"
			self._log_handler.exception(ex)
			self._locks[type].release()
			return False

	def _get_data(self, type, uuid):
		try:
			self._locks[type].acquire()
			data = self._mininet_data[type][uuid]
			self._locks[type].release()
			return (True, data)
		except KeyError as ke:
			self._log_handler.warning("Obtained KeyError when attempting to read data  of type: " + str(type) + " with uuid: " + str(uuid))
			self._log_handler.warning("Warning message: " + str(ke.message))
			self._locks[type].release()
			return (False, None)
		except Exception as ex:
			template = "An exception of type {0} occurred. Arguments:\n{1!r}"
			message = template.format(type(ex).__name__, ex.args)
			self._log_handler.error(message)
			self._locks[type].release()
			return (False, None)

	def get_subnet_for_nexthop(self, router_uuid, nexthop):
		def match_length(cidr, nexthop_ip):
			subnet = ipaddress.ip_network(unicode(cidr,'utf-8'))
			interface = ipaddress.ip_interface(unicode(nexthop_ip,'utf-8'))
			if (interface in subnet):
				return cidr.split("/")[1]
			else:
				return 0
		version = "None"
		try:
			addr = ipaddress.ip_address(unicode(nexthop,"utf-8"))
			version = str(addr.version)
		except exception as ex:
			self._log_handler.error("Received NH: " + str(nexthop)+ " could not be correctly identified")
			return(None, 0)

		(result, (subnet_list, extra_route_list)) = self._get_data("router", router_uuid)
		if(not result):
			self._log_handler.warning("Router UUID: " + router_uuid + " not found in the router DB. Ignoring subnet match")
			return (None,0)
		else:
			best_match = (None, 0)
			for subnet in subnet_list:
				(result,data) = self._get_data("subnet", subnet)
				if (not result):
					self._log_handler.warning("Subnet uuid: " + subnet + " not found in the subnet DB. Ignoring this subnet ")
					continue
				else:
					ip_ver= data['ip_version']
					'''self._log_handler.debug("For subnet: " + data['cidr'] + " IP version:" + str(ip_ver))'''
					if(str(ip_ver) == version):
						prefix_match_len =  match_length(data['cidr'], nexthop)
						self._log_handler.debug("Sub: " + str(data['cidr']) + " NH: " + str(nexthop) + " match: " + str(prefix_match_len))
						if (best_match[1] < prefix_match_len):
							best_match = (subnet, prefix_match_len)
		return best_match

	def test(self):
		sub1 = uuid.uuid4()
		sub2 = uuid.uuid4()
		sub3 = uuid.uuid4()
		sub4 = uuid.uuid4()

		sub_data1 = dict()
		sub_data1['id'] = sub1
		sub_data1['cidr'] = "192.168.11.0/25"
		sub_data1['ip_version'] = "4"
		self._store_data('subnet', sub1, sub_data1)
		self._log_handler.debug("Stored sub: " + str(sub1) + " with data: " + str(sub_data1))

		sub_data2 = dict()
		sub_data2['id'] = sub2
		sub_data2['cidr'] = "192.168.11.0/24"
		sub_data2['ip_version'] = "4"
		self._store_data('subnet', sub2, sub_data2)
		self._log_handler.debug("Stored sub: " + str(sub2) + " with data: " + str(sub_data2))

		sub_data3 = dict()
		sub_data3['id'] = sub3
		sub_data3['cidr'] = "2001:abcd:5678::/64"
		sub_data3['ip_version'] = "6"
		self._store_data('subnet', sub3, sub_data3)
		self._log_handler.debug("Stored sub: " + str(sub3) + " with data: " + str(sub_data3))

		sub_data4 = dict()
		sub_data4['id'] = sub4
		sub_data4['cidr'] = "2001:abcd:5678:0000:0000:0000::/96"
		sub_data4['ip_version'] = "6"
		self._store_data('subnet', sub4, sub_data4)
		self._log_handler.debug("Stored sub: " + str(sub4) + " with data: " + str(sub_data4))

		router_id = uuid.uuid4()
		subnet_list = (sub1, sub2, sub3, sub4)
		extra_route_list = []
		self._store_data('router', router_id, (subnet_list,extra_route_list))
		self._log_handler.debug("Stored router: " + str(router_id) + " with data: " + str((subnet_list,extra_route_list)))
		addr = ipaddress.ip_address(u"192.168.11.127")
		nexthop = str(addr.exploded)
		best_match = self.get_subnet_for_nexthop(router_id,nexthop)
		print ("Bestmatch = " + str(best_match))

if __name__ == '__main__':
	handler = test_lpm()
	handler.test()
