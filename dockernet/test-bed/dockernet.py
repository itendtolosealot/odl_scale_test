"""

# PRE-REQUISITES
1. docker platform must be installed.
2. Python 3.5.x must be installed
3. docker image must be present
4. ODL and docker containers must be running under same subnet same IP range.

"""
import os
import uuid
import sys
import subprocess
import re
import hashlib
from multiprocessing.pool import ThreadPool
import logging
import time
import plyvel
from prettytable import PrettyTable
from functools import reduce
import docker
import requests
from oslo_config import cfg
from neutronclient.v2_0 import client
from keystoneauth1 import identity
from keystoneauth1 import session
MAX_THREADS = 5

'''class DataBaseRestore():
	def __init__(self):
		self._databases = list()
		self._loghandler = ""
		self._db_loc = "/home/stack"
		self._locks = dict()

	def store_in_db(self):
		(res, _KEYS, db) = self._populate_db_handlers(destroy=True, create_if_missing=True)
		for key in _KEYS:
			if(res[key]):
				self._locks[key].acquire()
				wb = db[key].write_batch()
				for item in self._mininet_data[key].keys():
					try:
						wb.put(item, str.encode(str(self._mininet_data[key][item]).encode("ascii")))
						self._log_handler.debug("Wrote key: " + str(item) + " value: " + str(self._mininet_data[key][item]).encode("ascii") + " to " + str(key) +" DB" )
					except TypeError:
						self._log_handler.error("Obtained type error for DB: " + str(key) + " with key: " + str(item))
						continue
				wb.write()
				self._locks[key].release()
			else:
				self._log_handler.debug("For DB: " + str(key) + " handlers could not be created. Data will not be stored")
		self._dockernet.store_in_db()
		return True

	def _populate_db_handlers(self, destroy=False, create_if_missing=False):
		_KEYS = self._databases
		db = dict()
		res = dict()
		for key in _KEYS:
			try:
				file_loc = self._db_loc + str(key)
				self._log_handler.debug("Attempting to locate DB files at " + str(file_loc))
				if(destroy):
					try:
						plyvel.destroy_db(file_loc)
					except Exception as ex:
						self._log_handler.warning("Receiving and exception when deleting a DB: " + str(ex.message))
						pass
				if (create_if_missing):
					try:
						db[key]= plyvel.DB(file_loc, create_if_missing=True)
						res[key] = True
					except Exception as ex:
						self._log_handler.error("Received Exception when creating DB handler for : " + str(key) + " : " + str(ex.message))
						res[key]= False
				else:
					try:
						db[key]=plyvel.DB(file_loc, create_if_missing=False)
						res[key] = True
					except IOError:
						self._log_handler.info("DB not found. Cannot restore data")
						res[key] = False
			except Exception as ex:
				self._log_handler.exception("Encountered Exception in creating DB handlers: ")
				res[key] = False
		return (res, _KEYS, db)

	def restore_from_db(self):
		self._log_handler.debug("Starting restoration of data")
		(res, _KEYS, db) = self._populate_db_handlers(destroy=False, create_if_missing=True)
		try:
			for item in _KEYS:
				if(res[item]):
					for key,value in db[item]:
						try:
							self._mininet_data[item][key] = self._convert_to_dict(value.decode())
							self._log_handler.debug("Restored Key: "  + str(key)+" Value: "+ str(self._mininet_data[item][key]) + " from " + str(item) + " DB."	)
						except TypeError as tx:
							self._log_handler.error("Encountered error when decoding " + str(item) + " db data: " + str(tx.message))
						except Exception as ex:
							self._log_handler.exception("Encountered error when decoding " + str(item) + " db data: " + str(ex.message))
					self._log_handler.info("Restored data from DB: " + str(item))
				else:
					self._log_handler.warning("DB handler: " + str(item) + "could not be populated. Data from this DB is not restored")
			result=self._dockernet.restore_from_db()
			if (result):
				self._log_handler.info("All data restored")
				if(self._dockernet.get_num_computes()> 0):
					self._log_handler.debug("Found " + str(self._dockernet.get_num_computes()) + " computes. Starting simulation")
					self._SIMULATION_STARTED = True
			else:
				self._log_handler.error("Could not restore all data. System state inconsistent. Terminating the program")
				self._log_handler.error("Try deleting all the DBs by running rm -rf " + str(self._db_loc) + "* and restarting the program")
				sys.exit(1)
		except Exception as ex:
			self._log_handler.error("Encountered exception during restoration: " + str(ex.message))
			sys.exit(1)'''


class DockerHandler():
	def get_docker_client(self):
		return docker.APIClient

	def reset(self):
		self.delete_virtual_computes()
		for key in self._databases:
			self._dockernet_db[key] = dict()
		self._list_of_ovs= list()

	def read_config(self, file_location):
		grp = cfg.OptGroup('dockernet_properties')
		opts = [cfg.StrOpt("log_file", default="/home/stack/mininet_handler/Dockernet.log"),
		        cfg.StrOpt("db_loc", default="/home/stack/mininet_handler/db/"),
		        cfg.StrOpt("tep_subnet", default="10.173.77.0/24"),
		        cfg.StrOpt("neutron_ip", default="192.168.56.101"),
			        cfg.StrOpt("flow_dump_folder", default="/home/stack/mininet_handler/logs"),
		        cfg.IntOpt("docker_port", default=5000),
		        cfg.IntOpt("max_threads", default=5),
		        cfg.StrOpt("virtual_compute_image_name", default="dind:bionic"),
		        cfg.StrOpt("vm_image_name", default="base_image:bionic"),
		        cfg.StrOpt("partition_id", default=uuid.uuid4()),
		        cfg.StrOpt("neutron_user_name", default="admin"),
		        cfg.StrOpt("neutron_password", default="password"),
		        cfg.BoolOpt("TLS_enabled", default=False),
		        cfg.StrOpt("ca_cert_loc", default="./cacert.crt"),
		        cfg.StrOpt("auth_url", default="http://192.168.56.101/identity/"),
		        cfg.StrOpt("project_domain_id", default="default"),
		        cfg.StrOpt("user_domain_id", default="default"),
		        cfg.StrOpt("project_name", default="admin")]
		cfg.CONF.register_group(grp)
		cfg.CONF.register_opts(opts, group=grp)
		try:
			file_location= ['--config-file', str(file_location)]
			cfg.CONF(file_location)
		except Exception as ex:
			print("Error in processing configuration file. Exitting the program")
			print("Exception:" + str(ex.message))
			sys.exit(1)
		self._log_file = cfg.CONF.dockernet_properties.log_file
		self._db_loc = cfg.CONF.dockernet_properties.db_loc
		self._tep_ip_subnet=cfg.CONF.dockernet_properties.tep_subnet
		self._neutron_ip=cfg.CONF.dockernet_properties.neutron_ip
		self._flow_dump_folder=cfg.CONF.dockernet_properties.flow_dump_folder
		self._docker_port=cfg.CONF.dockernet_properties.docker_port
		global MAX_THREADS
		MAX_THREADS=cfg.CONF.dockernet_properties.max_threads
		self._ovs_docker_image=cfg.CONF.dockernet_properties.virtual_compute_image_name
		self._vm_image=cfg.CONF.dockernet_properties.vm_image_name
		self._partition_id= "1" #str(cfg.CONF.dockernet_properties.partition_id)[0:10]
		self._neutron_user_name = cfg.CONF.dockernet_properties.neutron_user_name
		self._neutron_password = cfg.CONF.dockernet_properties.neutron_password
		self._TLS_enabled = cfg.CONF.dockernet_properties.TLS_enabled
		self._ca_certificate=None
		self._project_domain_id =  cfg.CONF.dockernet_properties.project_domain_id
		self._project_name = cfg.CONF.dockernet_properties.project_name
		self._user_domain_id =  cfg.CONF.dockernet_properties.user_domain_id
		if(self._TLS_enabled):
			self._ca_certificate=cfg.CONF.dockernet_properties.ca_cert_loc
		self._keystone_auth_url=cfg.CONF.dockernet_properties.auth_url

	def _create_keystone_session(self):
		auth = identity.Password(auth_url=self._keystone_auth_url,
		                   username=self._neutron_user_name,
		                   password=self._neutron_password,
		                   project_name=self._project_name,
		                   user_domain_id=self._user_domain_id,
		                   project_domain_name=self._project_domain_id)
		self._sess = session.Session(auth=auth)

	def __init__(self, file_location="/home/stack/mininet_handler/config.ini"):
		self.read_config(file_location)
		self._setup_logger("Dockernet", self._log_file, level=logging.DEBUG)
		self._log_handler = logging.getLogger("Dockernet")
		self._databases = list(["ovs_to_port_mapping", "list_of_ovs", "mip_to_port_mapping", "extra_routes_to_port_mapping", "virtual_computes", "tenant_vm_to_compute_info"])
		self._dockernet_db= dict()
		self._list_of_ovs = list()
		for key in self._databases:
			self._dockernet_db[key] = dict()
		self._docker_ip = self._get_docker_ip()
		options = {
			'version': 'auto'
		}
		self.dc = self.get_docker_client()(**options)
		self.vdc = dict()
		try:
			network_info = self.dc.networks(names=["csc_underlay"])
			self._log_handler.debug("Received csc_underlay network info:" + str(network_info[0]["Id"]))
		except docker.errors.APIError as ex:
			self._log_handler.error("Received error : " + str(ex.message) + " When checking for csc_underlay network info")
		self._network_id = network_info[0]["Id"]
		self._create_keystone_session()
		self.restore_from_db()

	def get_partition_id(self):
		return self._partition_id

	def build_container_options(self, controller_ip, index):
		options = dict()
		options['host_config'] =self.dc.create_host_config(privileged=True)
		options['image'] = self._ovs_docker_image
		my_ip = self._tep_ip_subnet.split("/")[0].split(".")[0:3]
		my_ip = ".".join(my_ip) + "." + str(100+index)
		options['environment'] = ['CONTROLLER_IP=' + str(controller_ip), 'BR_IP='+str(my_ip), 'DP_ID=' + str(index), 'TERM=xterm','SHELL=/bin/bash', "DOCKER_IP=" + str(self._docker_ip)]
		options['name'] = self._partition_id + "_ovs" + str(index)
		options['hostname'] = self._partition_id + "_ovs" + str(index)
		options['image'] = self._ovs_docker_image
		options["detach"] = True
		return options

	def create_virtual_compute(self, controller_ip, index):
		options = self.build_container_options(controller_ip,index)
		try:
			result = self.dc.create_container(**options)
			container_id = result["Id"]
			warnings = result["Warnings"]
			if(warnings != []):
				self._log_handler.warning("Received warning : " + str(warnings) + " When creating container with index: " + str(index) + " ID: " + str(container_id))
			self._list_of_ovs.append(options["name"])
			self._dockernet_db['list_of_ovs'][options['name']] = options['name']
			self._dockernet_db["virtual_computes"][str(container_id)] = str(container_id)
			self.dc.connect_container_to_network(container_id, self._network_id)
			self.dc.start(container_id)
			self._log_handler.debug("Started container with Index:  " + str(index) + " Id: " + str(container_id) + " successfully")
			return True
		except Exception as ex:
			self._log_handler.error("Creating a container with Index: " + str(index) + " ctrl IP: " + str(controller_ip) + "failed with Message: " + str(ex.message))
			self._log_handler.exception("Exception")
			return False

	def delete_virtual_computes(self):
		result = True
		for container in self._dockernet_db["virtual_computes"].values():
			try:
				filter = dict()
				filter["id"] = container
				container_info = self.dc.containers(filters=filter)
				self.dc.stop(container,timeout=1)
				self.dc.remove_container(container)
				self._dockernet_db["virtual_computes"].pop(container)
				self._log_handler.debug("Attempting to remove container: " + str(container_info[0]["Names"][0]) + " from ovs")
				self._log_handler.debug("List of OVS: " + str(self._list_of_ovs))
				self._list_of_ovs.remove(container_info[0]["Names"][0].split("/")[1])
				try:
					self._dockernet_db['list_of_ovs'].pop(container_info[0]["Names"][0].split("/")[1])
				except Exception as ex:
					self._log_handler.error("Received error when removing from db['list_of_ovs'" + str(ex.message))
					pass
				self._log_handler.debug("Removed container: " + container + " Successfully")
			except Exception as ex:
				self._log_handler.error("Received exception " + str(ex.message) + " for deleting container: " + str(container))
				result=False
		return result

	def get_num_computes(self):
		return len(self._list_of_ovs)

	def get_list_of_computes(self):
		return str(self._list_of_ovs)

	def _populate_db_handlers(self, destroy=False, create_if_missing=False):
		_KEYS = self._databases
		db = dict()
		res = dict()
		for key in _KEYS:
			try:
				file_loc = self._db_loc + str(key)
				self._log_handler.debug("Attempting to locate DB files at " + str(file_loc))
				if(destroy):
					try:
						plyvel.destroy_db(file_loc)
					except Exception as ex:
						self._log_handler.warning("Receiving and exception when deleting a DB: " + str(ex.message))
						pass
				if (create_if_missing):
					try:
						db[key]= plyvel.DB(file_loc, create_if_missing=True)
						res[key] = True
					except Exception as ex:
						self._log_handler.error("Received Exception when creating DB handler for : " + str(key) + " : " + str(ex.message))
						res[key]= False
				else:
					try:
						db[key]=plyvel.DB(file_loc, create_if_missing=False)
						res[key] = True
					except IOError:
						self._log_handler.info("DB not found. Cannot restore data")
						res[key] = False
			except Exception as ex:
				self._log_handler.exception("Encountered Exception in creating DB handlers: ")
				res[key] = False
		return (res, _KEYS, db)

	def restore_from_db(self):
		self._log_handler.debug("Starting restoration of data")
		(res,keys,db) = self._populate_db_handlers(False, False)
		try:
			for item in keys:
				if res[item]:
					for key,value in db[item]:
						self._dockernet_db[item][key]=value
						if(item =="list_of_ovs"):
							self._list_of_ovs.append(key)
					self._log_handler.debug("Data from database: " + item + " restored")
					self._log_handler.debug("Restored item: " + str(self._dockernet_db[item]))
				else:
					self._log_handler.warning("Data from database: " + item + " not found")
			return True
		except Exception as ex:
			self._log_handler.error("Encountered exception during restoration: " + str(ex.message))
			return False

	def store_in_db(self):
		(res,keys,db) = self._populate_db_handlers(True,True)
		try:
			for item in keys:
				if res[item]:
					wb = db[item].write_batch()
					for key in self._dockernet_db[item].keys():
						wb.put(str(key), str(self._dockernet_db[item][key]))
					wb.write()
					self._log_handler.debug("Data from dict: " + item + " stored on the disk")
					self._log_handler.debug("Data stored: " + item + ": " + str(self._dockernet_db[item]))
			return True
		except Exception as ex:
			self._log_handler.error("Encountered Exception when wrting to DB: " + str(ex.message))
			return False

	def _setup_logger(self,name, log_file, level=logging.INFO):
		log_handler = logging.getLogger(name)
		filehandler=logging.FileHandler(log_file, mode='w')
		filehandler.setFormatter(logging.Formatter('%(asctime)s %(processName)s %(levelname)s %(message)s'))
		log_handler.setLevel(level=level)
		log_handler.addHandler(filehandler)

	def get_ovs_names_list(self):
		key = "name=" + self._partition_id + "_ovs"
		cmd='docker ps -a --filter' + key + ' --format "{{.Names}}" | sort'
		retval = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
		ovs_list=list(retval.split("\n"))
		ovs_list.remove('')
		return ovs_list

	def parallel_process_command(self, func, args):
		self._log_handler.info("Executing in parallel the function: " + str(func) + " with args_list: " + str(args))
		pool = ThreadPool(MAX_THREADS)
		try:
			result = pool.map(func, args)
			pool.close()
			pool.join()
			pool.terminate()
			return result
		except Exception as ex:
			self._log_handler.error("Encountered Exception during execution: " + str(ex.message))
			return None

	def _exec_command(self, args):
		def return_code(msg, bool_value, return_binary, ID):
			if (return_binary):
				return bool_value
			else:
				if(ID != None):
					return (ID, msg)
		try:
			(cmd, return_binary, suppress_output, command_ID) = args
		except Exception:
			cmd = args
			return_binary = True
			suppress_output= False
			command_ID = None

		output=""
		try:
			output = subprocess.check_output(cmd, stdin=None, stderr=None, shell=True, universal_newlines=False).decode('utf-8')
			if(not suppress_output):
				self._log_handler.debug("For cmd: " + str(cmd) + " got Output: " + str(output))
			return return_code(output, True, return_binary, command_ID)
		except subprocess.CalledProcessError as ex:
			if (not suppress_output):
				self._log_handler.error("Cmd: " + str(cmd)  + " failed with output: "+ str(ex.output))
			return return_code(output, False,return_binary, command_ID)
		except Exception as ex:
			if (not suppress_output):
				self._log_handler.error("Encountered generic exception: " + str(ex.message))
			return return_code(output, False, return_binary, command_ID)

	def _create_csc_underlay_network(self):
		cmd = "docker network create csc_underlay"
		result = self._exec_command(cmd)
		if (not result):
			return result

	def _get_docker_ip(self):
		cmd = "ifconfig docker0 | grep \"inet addr\" | cut -f2 -d\":\" | cut -f1 -d\" \""
		try:
			docker_ip = subprocess.check_output(cmd, stdin=None, stderr=None, shell=True, universal_newlines=False).decode('utf-8')
			self._log_handler.debug("Identified docker0 bridge IP: " + str(docker_ip))
		except subprocess.CalledProcessError as ex:
			self._log_handler.error("Creation of switch container failed " + str(ex.output))
			return False
		except Exception as ex:
			self._log_handler.error("Encountered generic exception: " + str(ex.message))
			return False
		return docker_ip

	def get_container_creation_command(self, image_port_tuple, gateway_cidr_tuple_list, action, mac_address, port_uuid):
		(cont_name, dind_name, dind_image, tapPortName, vm_port_name) = image_port_tuple
		executable = " python3.5 create_containers.py -op " + str(action) + " -c "
		options = str(dind_name) + " -i " + str(dind_image) + " -o " + str(tapPortName) + " -v " + str(vm_port_name) + " -m \"" + mac_address + "\" "
		ipconfig = ""
		if (gateway_cidr_tuple_list != None):
			for item in gateway_cidr_tuple_list:
				(ip, gateway, cidr, ip_version) = item
				ipconfig = ipconfig + " -ip " + "\"" + str(ip) + "\" "
				ipconfig = ipconfig + " -g " + "\"" + str(gateway) + "\" "
				ipconfig = ipconfig + " -ci " + "\"" + str(cidr) + "\" "
				ipconfig = ipconfig + " -ve " + "\"" + str(ip_version) + "\" "
		cmd = "docker exec " + str(cont_name) +  executable + options + ipconfig + " -u " + str(port_uuid)
		return cmd

	def get_image_port_tuple(self, ovs_switch_id, port_uuid):
		tapPortName = "tap" + str(port_uuid).replace("-","")[0:11]
		cont_name = self._list_of_ovs[ovs_switch_id]
		vm_port_name = "vm" + (port_uuid).replace("-","")[0:11]
		dind_name = cont_name+ port_uuid.replace("-","")[0:11]
		dind_image = str(self._docker_ip).replace("\n","") + ":" +str(self._docker_port) + "/" + self._vm_image
		image_port_tuple = (cont_name, dind_name, dind_image, tapPortName, vm_port_name)
		return image_port_tuple

	def does_port_exist_already(self, port_uuid):
		try:
			ovs_switch_id = self._dockernet_db["ovs_to_port_mapping"][port_uuid]
			self._log_handler.info("Port: " + port_uuid + " exists on " + str(ovs_switch_id))
			return True
		except KeyError:
			self._log_handler.info("Port: " + port_uuid + " does not exist. Will boot the VM")
			return False

	def populate_port_location_info(self, gateway_cidr_tuple_list, ovs_switch_id, port_uuid):
		data = dict()
		try:
			data["location"] = self._list_of_ovs[ovs_switch_id]
			for item in gateway_cidr_tuple_list:
				(ip,gateway, cidr, ip_version)=item
				data["ip_v"+str(ip_version)] =ip
				data["gateway_v"+str(ip_version)] = gateway
				data["subnet_v" + str(ip_version)] = cidr
			self._dockernet_db["tenant_vm_to_compute_info"][port_uuid]= data
			self._log_handler.debug("Stored information on port: " + port_uuid)
			return True
		except Exception as ex:
			self._log_handler.error("Encountered exception: " + str(ex.message) + " when storing data")

	def get_port_info(self):
		return self._dockernet_db["tenant_vm_to_compute_info"]

	def add_port_to_ovs(self, gateway_cidr_tuple_list, port_uuid, mac_address):
		does_port_exist = self.does_port_exist_already(port_uuid)
		if(does_port_exist):
			return True
		switch_count = len(self._list_of_ovs)
		hash = int(hashlib.sha512(str(port_uuid).encode()).hexdigest(),16)
		ovs_switch_id = hash % switch_count
		self._dockernet_db["ovs_to_port_mapping"][port_uuid] = ovs_switch_id
		port_update_result = self.send_port_update_to_neutron(self._list_of_ovs[ovs_switch_id], port_uuid)
		if(not port_update_result):
			self._log_handler.error("Port update to Neutron failed. Port will not be booted.")
			self._dockernet_db["ovs_to_port_mapping"].pop(port_uuid)
			return port_update_result
		image_port_tuple = self.get_image_port_tuple(ovs_switch_id,port_uuid)
		cmd = self.get_container_creation_command(image_port_tuple, gateway_cidr_tuple_list, "add", mac_address, port_uuid)
		self._log_handler.debug("Executing command: " + cmd)
		result = self._exec_command(cmd)
		return (result and self.populate_port_location_info(gateway_cidr_tuple_list, ovs_switch_id, port_uuid))


	def send_port_update_to_neutron(self, compute_hostname, port_uuid):
		neutron_client = client.Client(session=self._sess)
		port = dict()
		port["port"] = dict()
		port["port"]["binding:host_id"]=compute_hostname
		try:
			neutron_client.update_port(port_uuid,port)
			self._log_handler.debug("Neutron update for port: " + str(port_uuid) + " completed. VM will be hosted on virtual compute: " + str(compute_hostname))
			return True
		except Exception as ex:
			self._log_handler.error("When posting neutron update, received exception: " + str(ex.message))
			return False

	def del_port_from_ovs(self, port_uuid):
		try:
			ovs_switch_id = self._dockernet_db["ovs_to_port_mapping"][port_uuid]
		except KeyError:
			self._log_handler.error("Unknown port: " + str(port_uuid)  + " results in no op")
			return False
		image_port_tuple = self.get_image_port_tuple(ovs_switch_id, port_uuid)
		cmd = self.get_container_creation_command(image_port_tuple, None, "del", "", port_uuid)
		self._log_handler.debug("Executing command: " + cmd)
		result = self._exec_command(cmd)
		self._dockernet_db["ovs_to_port_mapping"].pop(port_uuid)
		return result

	def do_ping_test_for_port(self, args):
		(port_container, port_ip, compute_container, port_list) = args
		command_template = "docker exec " + compute_container + " docker exec " + port_container + " ping -c 5 "
		commands = map(lambda port : (command_template + str(port), False, True, port), port_list)
		pool = ThreadPool(MAX_THREADS)
		cmd_output = pool.map(self._exec_command, commands)
		pool.close()
		pool.join()
		pool.terminate()
		test_pass = True
		error_message = ""
		for item in range(0, len(port_list)):
			if ", 0% packet loss" not in cmd_output[item][1]:
				test_pass=False
				error_message = error_message + " On VM: " + port_container + " with IP: " + str(port_ip) + " located on compute " + str(compute_container) + " ping failed to ip: " + cmd_output[item][0] + "\n"
		if test_pass:
			error_message = "Pings from vm: " + str(port_container) + " on compute: " + str(compute_container) + " passed"
		return(test_pass, error_message)

	def do_ping_test(self, resource, resource_id, port_list):
		def get_port_info(uuid):
			compute = self._dockernet_db["ovs_to_port_mapping"][uuid]
			vm_name = self._list_of_ovs[compute] + uuid[0:10]
			return (vm_name, self._list_of_ovs[compute])
		try:
			args = list()
			(port_uuid, ip_list) = list(zip(*port_list))
			for item in port_list:
				(uid, ip_ad) = item
				(vm_name, compute_name) = get_port_info(uid)
				args.append((vm_name,ip_ad,compute_name, ip_list))
			pool = ThreadPool(MAX_THREADS)
			self._log_handler.debug("Executing ping test for. Args: " + str(args) )
			cmd_output = pool.map(self.do_ping_test_for_port, args)
			pool.close()
			pool.join()
			pool.terminate()
			test_pass = True
			error_message = ""
			cmd_output_message=""
			for item in range(0, len(cmd_output)):
				if (not cmd_output[item][0]):
					test_pass = False
					cmd_output_message = cmd_output_message + cmd_output[item][1]
			if(not test_pass):
				flow_dumps = self.get_ovs_dump(port_uuid)
				flow_dump_file = self._flow_dump_folder + "/flow_dump_" + str(time.strftime("%y_%m_%d_%H_%M_%S")) + ".log"
				self._setup_logger("PingTest" , flow_dump_file, logging.ERROR)
				flow_dump_logger = logging.getLogger("PingTest")
				try:
					flow_dump_logger.error("Ping test failed for " + resource + ":"+ str(resource_id))
					flow_dump_logger.error("Output of Ping test: \n")
					flow_dump_logger.error(cmd_output_message)
					flow_dump_logger.error("Flow dumps from various switches")
					flow_dump_logger.error("===============================================================================================================================")
					flow_dump_logger.error(flow_dumps)
					flow_dump_logger.error("================================================================================================================================")
				except Exception as ex:
					self._log_handler.error("Unable to dump flows when Ping test failed for " + resource + ": " + str(resource_id))
					self._log_handler.error("Encountered exception: " + str(ex.message))
				error_message = "ping test for " + resource + ": " + str(resource_id) + " failed. See flow dump logs for details"
			return(test_pass, error_message)
		except Exception as ex:
			self._log_handler.exception("When running test for " + str(resource) +": " + str(resource_id) + " encountered exception: " + str(ex))
			return(False, "Unable to execute test. See logs for more details")

	def get_ovs_dump(self, port_list):
		try:
			ovs_list = map(lambda x: self._list_of_ovs[self._dockernet_db["ovs_to_port_mapping"][x]], port_list)
		except KeyError as ex:
			self._log_handler.error("Error in obtaining computes for some ports" + str(ex.message))
			return (False, "Error! Unable to get flow dumps")
		ovs_set = list(set(ovs_list))
		ovs_dump_command = " ovs-ofctl -O OpenFlow13 dump-flows br-int "
		docker_cmd_template = "docker exec "
		cmds = map(lambda ovs_id: (docker_cmd_template + str(ovs_id) + ovs_dump_command, False,True, ovs_id), ovs_set)
		pool = ThreadPool(MAX_THREADS)
		cmd_output = pool.map(self._exec_command, cmds)
		pool.close()
		pool.join()
		pool.terminate()
		flow_dump_data = ""
		for item in range(0,len(cmd_output)):
			headers = ["Flow Dump for " + str(cmd_output[item][0])]
			message = PrettyTable(headers)
			message.add_row(cmd_output[item][1])
			flow_dump_data += str(message)
		return flow_dump_data

	def get_env_variables(self, controller_ip, switch_index):
		my_ip = self._tep_ip_subnet.split("/")[0].split(".")[0:3]
		my_ip = ".".join(my_ip) + "." + str(100+switch_index)
		message = " -e CONTROLLER_IP=" + controller_ip + " -e BR_IP=" +my_ip + " -e DP_ID=" + str(switch_index+1) + " -e TERM=xterm -e SHELL=/bin/bash"
		return message

	def docker_ovs_run_connect(self, switch_count, controller_ip):
		result = list()
		self.clean_old_setup()
		for compute_index in range(0,switch_count):
			result.append(self.create_virtual_compute(controller_ip, compute_index+1))
		success= reduce(lambda a,b:  a and b, result)
		if success:
			self._log_handler.debug("Creation of virtual computes successful")
		else:
			self._log_handler.error("Creation of virtual computes failed.")
		return success

	def docker_down(self):
		return (self.delete_virtual_computes())

	def clean_old_setup(self):
		cmd = "docker ps -a | grep ovs | cut -f1 -d \" \""
		try:
			output = subprocess.check_output(cmd, stdin=None, stderr=None, shell=True, universal_newlines=False).decode('utf-8').replace("\n", " ")
			self._log_handler.debug("Executed: " + str(cmd) + "Output: " + str(output))
		except subprocess.CalledProcessError as ex:
			self._log_handler.error("No containers found" + str(ex.output))
			return True
		except Exception as ex:
			self._log_handler.error("No containers found: " + str(ex.message) )
			return True
		pattern = r'\w'
		if (re.search(pattern, output) != None):
			cmd = "docker stop " + str(output)
			result = self._exec_command(cmd)
			if (not result):
				return result
			cmd = "docker rm " + str(output)
			result = self._exec_command(cmd)
			if (not result):
				return result
			self._list_of_ovs = list()
			self._dockernet_db["mip_to_port_mapping"] = dict()
			self._dockernet_db["ovs_to_port_mapping"] = dict()
		else:
			self._log_handler.info("No virtual computes exist")

		return True

	def status(self):
		message = list()
		cmd_template_1 = "docker exec "
		cmd_template_2 = " netstat -tanp | egrep -h \"6640|6653\""
		cmds = map(lambda cont_name: (cmd_template_1 + str(cont_name) + cmd_template_2, False, True, cont_name), self._list_of_ovs)
		self._log_handler.debug("Executed commands: " + str(cmds))
		results = self.parallel_process_command(self._exec_command, cmds)
		self._log_handler.debug("On executing: " + str(cmds) + " Obtained result: " + str(results))
		if (results==None):
			self._log_handler.error("Status of the DPNs could not be obtained")
			return ("Error! Encountered problems with DPN status")
		results_with_postprocessing = map(lambda connection_status: (connection_status[0], connection_status[1].replace("tcp",connection_status[0]).split("\n")), results)
		self._log_handler.debug("Post processing results: " + str(results_with_postprocessing))
		for row in results_with_postprocessing:
			if(len(row[1])==0 or (len(row[1])==1 and row[1][0]=='')):
				message.append(str(row[0]) + " Disconnected from OF and OVSDB")
			else:
				self._log_handler.debug("For " + str(row[0]) + " Connection status: " + str(row[1]))
				for item in row[1]:
					self._log_handler.debug(" Adding row: " + str(item))
					message.append(str(item))
		return message

	def get_mip_configuration_command(self, image_port_tuple, mip, action, prefix_length, next_hop=None):
		(cont_name, dind_name, dind_image, tapPortName, vm_port_name) = image_port_tuple
		if (next_hop==None):
			nh_string = ""
		else:
			nh_string= " -n " + str(next_hop)
		executable = " python3.5 /configure_mips.py -op " + str(action) + " -c " + str(dind_name) + " -p " + str(vm_port_name) + " -i " + mip + " -l " + prefix_length  + str(nh_string)
		cmd = "docker exec " + str(cont_name) +  executable
		return cmd

	def configure_mips(self, sub_uuid, port_uuid_list, mip_list, prefix_length):
		def identify_mip_location(mip):
			num_neutron_ports = len(port_uuid_list)
			hash = int(hashlib.sha512((str(sub_uuid) + str(mip)).encode()).hexdigest(),16)
			modded_val = hash % num_neutron_ports
			neutron_port = port_uuid_list[hash % num_neutron_ports]
			self._log_handler.debug("For mip: " + str(mip) + " port Index: " + str(modded_val) + " num_ports: " + str(num_neutron_ports))
			self._dockernet_db["mip_to_port_mapping"][str(sub_uuid) + str(mip)] = neutron_port
			try:
				ovs_switch_id = self._dockernet_db["ovs_to_port_mapping"][neutron_port]
			except KeyError:
				self._log_handler.error("Unable to obtain the location of the Neutorn port: " + str(neutron_port) + " Cannot configure MIP: " + str(mip))
				ovs_switch_id = None
			return (ovs_switch_id, neutron_port, mip, prefix_length)

		def generate_mipconfig_command(args):
			(ovs_switch_id, neutron_port, mip, prefix_length) = args
			return self.get_mip_configuration_command(self.get_image_port_tuple(ovs_switch_id,neutron_port), mip, "add", prefix_length)

		self._log_handler.debug("Attempting to Configure MIPs for subnet: " + str(sub_uuid) + " with port_list: " + str(port_uuid_list) + " MIP list: " + str(mip_list))
		ovs_and_port_location = self.parallel_process_command(identify_mip_location, mip_list)
		if (ovs_and_port_location == None):
			return False

		mip_config_commands = self.parallel_process_command(generate_mipconfig_command, ovs_and_port_location)
		if (mip_config_commands==None):
			return False
		mip_config_commands_tuple = map(lambda cmd: (cmd, True, False, None), mip_config_commands)
		mip_config_result = self.parallel_process_command(self._exec_command, mip_config_commands_tuple)
		if (mip_config_result==None):
			return False
		result = reduce(lambda x,y: x and y, mip_config_result)
		return result

	def unconfigure_mips(self,sub_uuid, mip_list, prefix_length):
		final_result = True
		def popping_with_try_catch(args):
			(db,key,remove_data) = args
			try:
				if(remove_data):
					value =self._dockernet_db[db].pop(key)
				else:
					value = self._dockernet_db[db][key]
			except KeyError:
				self._log_handler.warning("Unable to obtain the value associated with key: " + key + " in Subnet: " + sub_uuid)
				value = None
			return value
		def generate_mipconfig_command(args):
			(ovs_switch_id, neutron_port, mip, prefix_length) = args
			return self.get_mip_configuration_command(self.get_image_port_tuple(ovs_switch_id,neutron_port), mip, "del", prefix_length)

		self._log_handler.info("Attempting to get the Neutron port associated with each MIP")
		arg_list_for_ports = map(lambda mip: ("mip_to_port_mapping", mip, True), mip_list)
		neutron_ports = map(popping_with_try_catch, arg_list_for_ports)
		self._log_handler.info("Attempting to get the OVS switch for each port")
		arg_list_for_switches = map(lambda port: ("ovs_to_port_mapping", port, False), neutron_ports)
		ovs_switches = map(popping_with_try_catch, arg_list_for_switches)
		temp = zip(ovs_switches,neutron_ports, mip_list)
		ovs_and_port_location = map(lambda x: (x[0], x[1], x[2], prefix_length), temp)
		self._log_handler.info("Attempting to get the MIP unconfiguration command")
		unconfigure_mip_commands = self.parallel_process_command(generate_mipconfig_command, ovs_and_port_location)
		self._log_handler.info("Running MIP unconfiguration command")
		results = self.parallel_process_command(self._exec_command, unconfigure_mip_commands)
		return(reduce(lambda x,y: x and y, results))

	def get_mip_status(self, sub_uuid , mip_list):
		message = list()
		for mip in mip_list:
			port_uuid = self._dockernet_db["mip_to_port_mapping"][str(sub_uuid) + str(mip)]
			compute = self._list_of_ovs[self._dockernet_db["ovs_to_port_mapping"][port_uuid]]
			data = list([sub_uuid, mip, port_uuid , compute ,(compute + port_uuid[0:10])])
			message.append(data)
		return message

	def get_prefix_length(self, dest):
		split_data = dest.split("/")
		return (split_data[0], split_data[1])

	def configure_extra_routes(self, router_uuid, extra_route_list):
		self._log_handler.debug("Received extra_route_list: " + str(extra_route_list))
		def get_extra_route_configuration_command(item):
			(dest, nh,nh_ip, prefix_length, port_uuid_list) = item
			if (nh == None):
				self._log_handler.debug("For destination: " + dest + " no next-hop exists. Choosing one dynamically to enable dynamic discovery")
				hash = int(hashlib.sha512((str(router_uuid) + str(dest)).encode()).hexdigest(),16)
				num_neutron_ports = len(port_uuid_list)
				nh= port_uuid_list[hash % num_neutron_ports]
				self._dockernet_db["extra_routes_to_port_mapping"][str(router_uuid)+str(dest)] = nh
				self._log_handler.info(" For destination: " + dest + " chose the next-hop as neutron port:  " + str(nh))
			try:
				ovs_switch_id = self._dockernet_db["ovs_to_port_mapping"][nh]
			except KeyError:
				self._log_handler.error("Unable to obtain the location of the Neutorn port: " + str(nh) + " Cannot configure Extra Route: " + str(dest))
				ovs_switch_id = None
			(destination_ip, dest_prefix_length) = self.get_prefix_length(dest)
			' we still need to pass the NH IP so that we can create the interface dynamically'
			command = self.get_mip_configuration_command(self.get_image_port_tuple(ovs_switch_id,nh), destination_ip, "add", prefix_length, next_hop=nh_ip)
			return command
		temp = self.parallel_process_command(get_extra_route_configuration_command, extra_route_list)
		extra_route_config_commands = map(lambda x: (x, True, False, None), temp)
		results = self.parallel_process_command(self._exec_command, extra_route_config_commands)
		return(reduce(lambda a,b: a and b, results))

	def unconfigure_extra_routes(self, router_uuid, extra_route_list):
		final_result=True
		for item in extra_route_list:
			(dest, nh, nh_ip,prefix_length,port_uuid_list) = item
			if (nh == None):
				try:
					nh = self._dockernet_db["extra_routes_to_port_mapping"].pop(str(router_uuid)+str(dest))
				except KeyError:
					self._log_handler.warning("For destination: " + str(dest) + " no NH found. cannot proceed to unconfigure the IP")
			try:
				ovs_switch_id = self._dockernet_db["ovs_to_port_mapping"][nh]
			except KeyError:
				self._log_handler.error("Unable to obtain the location of the Neutorn port: " + str(nh) + " Cannot unconfigure Extra Route: " + str(dest))
				continue
			(destination_ip, prefix_length) = self.get_prefix_length(dest)
			command = self.get_mip_configuration_command(self.get_image_port_tuple(ovs_switch_id,nh), destination_ip, "del", prefix_length, next_hop=nh_ip)
			result = self._exec_command((command, True, False))
			final_result = final_result and result
			return final_result







