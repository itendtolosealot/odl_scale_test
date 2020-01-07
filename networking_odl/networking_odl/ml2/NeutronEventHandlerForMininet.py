from neutron_lib.callbacks import events
from neutron_lib.callbacks import registry
from neutron_lib.callbacks import resources
import threading
import time
import queue
import collections
import logging
import math
from config import ttypes
from thrift import Thrift
from thrift.transport import TSocket
from thrift.transport import TTransport
from thrift.protocol import TBinaryProtocol
from config import MaxinetConfigurationService

ODLResource = collections.namedtuple('ODLResource', ('singular', 'plural'))
DEFAULT_MTU = 1450
LOG = logging.getLogger("networking_odl.maxinet.")
hostIP = "10.128.128.103"
hostPort = 9090
MAX_RETRIES=5

class NeutronEventHandlerForMininet(object):
	_mininet_data = dict()
	_mininet_data['network'] = dict()
	_mininet_data['subnet'] = dict()
	_mininet_data['port'] = dict()
	_mininet_data['router'] = dict()
	_locks = dict()
	_locks['network'] = threading.Lock()
	_locks['subnet'] = threading.Lock()
	_locks['port'] = threading.Lock()
	_locks['router'] = threading.Lock()

	def __init__(self):
		self._subscribe()
		self._initialize()

	def _subscribe(self):
		self._event_mapping = {
			events.AFTER_CREATE:ttypes.EVENT.CREATE,
			events.AFTER_UPDATE:ttypes.EVENT.UPDATE,
			events.BEFORE_DELETE:ttypes.EVENT.DELETE
		}
		for event in (events.AFTER_CREATE, events.BEFORE_DELETE, events.AFTER_UPDATE):
			registry.subscribe(self._callback, resources.NETWORK, event)
			registry.subscribe(self._callback, resources.SUBNET, event)
			registry.subscribe(self._callback, resources.PORT, event)
			registry.subscribe(self._callback, resources.ROUTER, event)

	def _initialize(self):
		self._queue = queue.Queue(maxsize=0)
		self._setup_logger("NeutronEventHandler", "/home/stack/mininet_handler/client.log", level=logging.DEBUG)
		self._maxinet_channel=None
		self._channel_creator = threading.Thread(target=self._create_thrift_channel, args=(self._log_handler,))
		self._channel_creator.start()

	def _deque(self):
		self._log_handler.debug("Starting dequeue mechanism")
		while True:
			if self._queue.empty() or self._maxinet_channel==None:
				self._log_handler.debug("Inside sleep of dequeue")
				self._log_handler.debug("Maxinet Channel: " + str(self._maxinet_channel))
				self._log_handler.debug("Size of queue: " + str(self._queue.qsize()))
				time.sleep(3)
			else:
				(resource, event, trigger, kwargs )=self._queue.get()
				self._log_handler.debug("Inside the dequeue event")
				self._callback(resource,event,trigger,kwargs)
		self._log_handler.debug("Exitting the dequeue thread. This should probably not happen")

	def _enqueue(self,resource, event, trigger, **kwargs ):
		self._log_handler.debug("Received a callback from Neutron. Enqueing the callback")
		tuple = (resource,event,trigger,kwargs)
		self._queue.put(tuple)
		time.sleep(5)
		self._log_handler.debug("queue size after the put: " + str(self._queue.qsize()))

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
			message = template.format(type(ex).__name__, ex.args)
			self._log_handler.error(message)
			self._locks[type].release()
			return False

	def _get_data(self, type, uuid):
		try:
			self._locks[type].acquire()
			data = self._mininet_data[type][uuid]
			self._locks[type].release()
			return (True, data)
		except KeyError as ke:
			self._log_handler.error("Obtained KeyError when attempting to read data  of type: " + str(type) + " with uuid: " + str(uuid))
			self._log_handler.error("Error message: " + str(ke.message))
			self._locks[type].release()
			return (False, None)
		except Exception as ex:
			template = "An exception of type {0} occurred. Arguments:\n{1!r}"
			message = template.format(type(ex).__name__, ex.args)
			self._log_handler.error(message)
			self._locks[type].release()
			return (False, None)

	def _delete_data(self, type, uuid):
		try:
			self._locks[type].acquire()
			data = self._mininet_data[type].pop(uuid)
			self._locks[type].release()
			return (True, data)
		except KeyError as ke:
			self._log_handler.error("Obtained KeyError when deleting data  of type: " + str(type) + " with uuid: " + str(uuid))
			self._log_handler.error("Error message: " + str(ke.message))
			self._locks[type].release()
			return (False, None)
		except Exception as ex:
			template = "An exception of type {0} occurred. Arguments:\n{1!r}"
			message = template.format(type(ex).__name__, ex.args)
			self._log_handler.error(message)
			self._locks[type].release()
			return (False, None)

	def _handle_network_event(self, event, **kwargs):
		res = ttypes.resource()
		net = ttypes.network()
		result = False
		res.event=self._event_mapping[event]
		res.type = ttypes.RESOURCE.NETWORK
		if event in (events.AFTER_CREATE, events.AFTER_UPDATE):
			kwargs = kwargs['network']
			net.network_uuid = kwargs['id']
			self._log_handler.debug("Received network event. Network UUID:" + str(net.network_uuid) + " Event: " + str(event))
			if 'mtu' in kwargs:
				net.mtu = int(kwargs['mtu'])
				self._log_handler.debug("Received MTU: " + str(net.mtu) + " in Network: " + str(net.network_uuid))
			else:
				net.mtu = DEFAULT_MTU
				self._log_handler.debug("Received no MTU, configuring default MTU :"  + str(DEFAULT_MTU) + " in Network: " + str(net.network_uuid))
			result = self._store_data("network", net.network_uuid, kwargs)
		elif event==events.BEFORE_DELETE:
			net.network_uuid = kwargs['network_id']
			(result, data) = self._delete_data('network', net.network_uuid)
		else:
			self._log_handler.warning("Received unsubscribed Event: " + str(event) + "\n\n")
			return
		res.net = net
		if (result):
			self._send_data(res)
			self._log_handler.debug("Sent Network event on Thrift\n\n")
		else:
			self._log_handler.debug("Encountered error during data storage/delete for network with UUID: " + str(net.network_uuid) + ". Ignoring the event\n\n")
		return

	def _handle_subnet_event(self, event, **kwargs):
		sub = ttypes.subnet()
		res = ttypes.resource()
		result = False
		if event in (events.AFTER_UPDATE, events.AFTER_CREATE):
			kwargs = kwargs['subnet']
			sub.subnet_uuid = kwargs['id']
			self._log_handler.debug(" Create subnet with Subnet UUID: " + str(sub.subnet_uuid))
			if 'network_id' in kwargs:
				sub.network_uuid = kwargs['network_id']
				self._log_handler.debug("Subnet in Network: " + str(sub.network_uuid))
			if 'cidr' in kwargs:
				sub.cidr = kwargs['cidr']
				self._log_handler.debug("CIDR: " + str(sub.cidr))
			if 'ip_version' in kwargs:
				sub.ip_version=int(kwargs['ip_version'])
				self._log_handler.debug("IP version: " + str(sub.ip_version))
			if 'host_routes' in kwargs and len(kwargs['host_routes']) > 0:
				sub.host_routes = dict()
				for item in kwargs['host_routes']:
					sub.host_routes[item['destination']] = item['nexthop']
				self._log_handler.debug("Host Routes: " + str(sub.host_routes))
			else:
				sub.host_routes=None
			if 'gateway_ip' in kwargs:
				sub.gateway=kwargs['gateway_ip']
				self._log_handler.debug(" Gateway:" + str(sub.gateway))
			res.type = ttypes.RESOURCE.SUBNET
			result = self._store_data('subnet', sub.subnet_uuid, kwargs)
			res.event=self._event_mapping[event]
		elif event==events.BEFORE_DELETE:
			sub.subnet_uuid = kwargs['subnet_id']
			(result, data)= self._delete_data("subnet", sub.subnet_uuid)
			res.type = ttypes.RESOURCE.SUBNET
			res.event=ttypes.EVENT.DELETE
			self._log_handler.debug("Received a Delete Event for Subnet: " + str(sub.subnet_uuid))
		else:
			self._log_handler.error("Unsubscribed Event " + str(event) + "\n\n")
			return
		res.sub = sub
		if(result):
			self._send_data(res)
			self._log_handler.debug("Sent subnet event on Thrift\n\n")
		else:
			self._log_handler.debug("Encountered error during data storage/delete for subnet with UUID: " + str(sub.subnet_uuid) + ". Ignoring the event\n\n")


	def _handle_router_port_event(self, event, port_data, res, pt, **kwargs):
		res.type=ttypes.RESOURCE.ROUTER
		if event==events.BEFORE_DELETE:
			try:
				res.event=ttypes.EVENT.DETACH
				pt.port_uuid=kwargs['port_id']
			except KeyError:
				self._log_handler.warning("Received a Delete Event for Port: " + str(kwargs['port_id']) + ". This port does not exist\n\n")
				return False
			try:
				device_id=port_data['device_id']
			except KeyError:
				self._log_handler.error("Port information does not contain device_id. Unable to process router interface add events. Ignoring...\n")
				return False
			(result, data) = self._get_data('router', device_id)
			if (not result):
				self._log_handler.error("Unable to find Router with ID: " + str(device_id) + ". Unable to handle the event")
				return False
			else:
				(subnet_list, extra_route_list) = data
			if 'fixed_ips' in port_data:
				for item in port_data['fixed_ips']:
					try:
						self._log_handler.debug("The port delete event translates to Router Detach for Subnet: " + str(item['subnet_id'])+ " from Router: " + str(device_id))
						subnet_list.remove(item['subnet_id'])
					except KeyError:
						self._log_handler.debug("The subnet ID corresponding to the detached subnet is unavailable for device: " + str(device_id))
						return False
			else:
				self._log_handler.error("Unable to find subnet associated with this detach event for Router: " + str(device_id) + "\n\n")
				return False
		elif event in (events.AFTER_CREATE, events.AFTER_UPDATE):
			pt.port_uuid = kwargs['id']
			result = self._store_data('port', pt.port_uuid, kwargs)
			if (not result):
				self._log_handler.error("Unable to store port data for port: " + str(pt.port_uuid) + " and data: " + str(kwargs) + ". Ignoring the event..\n")
				return False
			res.event = ttypes.EVENT.ATTACH
			device_id=kwargs['device_id']
			(result, data) = self._get_data('router', device_id)
			if(result):
				(subnet_list, extra_route_list) = data
			else:
				subnet_list = list()
				extra_route_list = list()
			if 'fixed_ips' in kwargs:
				for item in kwargs['fixed_ips']:
					try:
						subnet_list.append(item['subnet_id'])
						self._log_handler.debug("Attaching Subnet: " + str(item['subnet_id']) + " to router: " + str(device_id))
						self._log_handler.debug("Port's IP address: " + str(item['ip_address']))
					except KeyError:
						self._log_handler.error("While going through fixed_ips, could not find the key subnet_id OR ip_address")
						return False
		else:
			self._log_handler.warning("Unsubscribed event: " + str(event) + ". Ignoring...")
			return False
		result = self._store_data('router', device_id, (subnet_list, extra_route_list))
		if (not result):
			self._log_handler.error("Encountered error during data storage/delete for router with UUID: " + str(device_id) + ". Ignoring the event\n\n")
			return False
		rtr = ttypes.router()
		rtr.router_uuid = device_id
		rtr.routes=extra_route_list
		rtr.subnets=subnet_list
		res.rtr=rtr
		return True

	def _print_resource_info(self, type):
		try:
			self._locks[type].acquire()
			for uuid in self._mininet_data[type].keys():
				data = self._mininet_data[type][uuid]
				self._log_handler.debug("Available resources: Obtained " + str(type) + " uuid: " + uuid)
			self._locks[type].release()
		except Exception as ex:
			template = "An exception of type {0} occurred. Arguments:\n{1!r}"
			message = template.format(type(ex).__name__, ex.args)
			self._log_handler.error(message)
			self._locks[type].release()

	def _handle_port_event(self, event, **kwargs):
			pt = ttypes.port()
			res = ttypes.resource()
			self._print_resource_info('port')
			if event==events.BEFORE_DELETE:
				try:
					pt.port_uuid=kwargs['port_id']
				except KeyError:
					self._log_handler.error(" The field \'port_id\' does not exist in the arguments passed. Ignoring the event...\n\n")
					return
				(result, port_data) = self._delete_data('port', pt.port_uuid)
				if (not result):
					self._log_handler.error("Encountered error in retriving data for port: " + str(pt.port_uuid) + "Ignoring the event...\n\n")
					return
				self._log_handler.debug("Received a Delete Event for Port: " + str(pt.port_uuid))
				if port_data['device_owner'] in "network:router_interface_distributed":
					self._handle_router_port_event(event, port_data, res, pt, **kwargs)
				elif port_data['device_owner'] == "compute:nova":
					self._log_handler.debug("Port delete event for Port: " + str(pt.port_uuid))
					res.event = ttypes.EVENT.DELETE
					res.type = ttypes.RESOURCE.PORT
					res.pt = pt
				else:
					self._log_handler.warning("Received a port with device owner: " + str(kwargs['device_owner']) + ". No processing is required\n\n")
					return
			elif event in (events.AFTER_CREATE, events.AFTER_UPDATE):
				kwargs=kwargs['port']
				try:
					pt.port_uuid = kwargs['id']
				except KeyError:
					self._log_handler.error(" The field \'id\' does not exist in the arguments passed. Ignoring the event...\n\n")
					return
				result = self._store_data('port',pt.port_uuid, kwargs)
				if(not result):
					self._log_handler.error("Unable to store port data for port: " + str(pt.port_uuid) + " and data: " + str(kwargs) + ". Ignoring the event..\n")
					return
				self._log_handler.debug("Received port create/update event for port: " + str(pt.port_uuid))
				if kwargs['device_owner'] in "network:router_interface_distributed":
					result = self._handle_router_port_event(event, None, res, pt, **kwargs)
					if(not result):
						self._log_handler.error("Router port event was not handled correctly for port: " + str(pt.port_uuid) + ". Ignoring the event")
						return
				elif kwargs['device_owner']=="compute:nova":
					res.type=ttypes.RESOURCE.PORT
					res.event=self._event_mapping[event]
					self._log_handler.debug("port add/update event")
					if 'network_id' in kwargs:
						pt.network_uuid = kwargs['network_id']
						self._log_handler.debug("Network id of port: " + str(kwargs['network_id']))
					if 'device_id' in kwargs:
						device_id = kwargs['device_id']
						self._log_handler.debug("Device ID: " + str(device_id))
					if 'fixed_ips' in kwargs and len(kwargs['fixed_ips']) > 0:
						fixed_ip_list=list()
						for item in kwargs['fixed_ips']:
							try:
								a = ttypes.fixed_ip()
								a.ip_address = item['ip_address']
								a.subnet_id = item['subnet_id']
								fixed_ip_list.append(a)
								self._log_handler.debug("Found IP: " + str(item['ip_address']) + " Subnet: " + item['subnet_id'])
							except KeyError:
								self._log_handler.error("While going through fixed_ips, could not find the key subnet_id OR ip_address")
						pt.fixed_ips = fixed_ip_list
					if 'mac_address' in kwargs:
						pt.mac_address=kwargs['mac_address']
						self._log_handler.debug("MAC address: " + str(pt.mac_address))
					if 'allowed_address_pairs' in kwargs:
						aap_list = list()
						for item in kwargs['allowed_address_pairs']:
							try:
								aap_list.append((item['ip_address'], item['mac_address']))
								self._log_handler.debug("AAP config: Allow IP: " + str(item['ip_address']) + " with mac: " + str(item['mac_address']))
							except KeyError:
								self._log_handler.error("While going through AAPs, could not find the key mac OR ip_address")
						pt.allowed_address_pairs = aap_list
						self._log_handler.debug("Allowed Address Pairs: " + str(pt.allowed_address_pairs))
					res.pt=pt
				else:
					self._log_handler.warning("Received a port with device owner: " + str(kwargs['device_owner']) + ". No processing is required\n\n")
					return
			self._send_data(res)
			self._log_handler.debug("Sent Port/Router-subnet event on Thrift \n\n")

	def _handle_router_event(self, event, **kwargs):
		rtr = ttypes.router()
		res = ttypes.resource()
		res.type=ttypes.RESOURCE.ROUTER
		res.event = self._event_mapping[event]
		if event in (events.AFTER_CREATE, events.AFTER_UPDATE):
			kwargs=kwargs['router']
			rtr.router_uuid=kwargs['id']
			(result, data) = self._get_data('router', rtr.router_uuid)
			if result:
				(subnet_list, extra_route_list)=data
			else:
				subnet_list = list()
				extra_route_list = list()
			self._log_handler.debug("Router Create Event for Router: " + str(rtr.router_uuid))
			if 'routes' in kwargs:
				rtr.extra_routes=kwargs['routes']
				extra_route_list=kwargs['routes']
				self._log_handler.debug("Extra Routes: " + str(rtr.extra_routes))
			result = self._store_data('router', rtr.router_uuid, (subnet_list, extra_route_list))
			if(not result):
				self._log_handler.error("Encountered error while storing router: " + str(rtr.router_uuid) + ". Ignoring the event")
				return
		elif event==events.BEFORE_DELETE:
			try:
				rtr.router_uuid = kwargs['router_id']
			except KeyError:
				self._log_handler.warning("The field \'router_id\' is missing in the arguments. Ignoring the event ...\n\n")
				return
			(result, data) = self._delete_data('router', rtr.router_uuid)
			if(not result):
				self._log_handler.error("Encountered error while deleting router: " + str(rtr.router_uuid) + ". Ignoring the event...\n\n")
				return
		res.rtr = rtr
		self._send_data(res)
		self._log_handler.debug("Sent Router event on Thrift\n\n")

	def _callback(self, resource, event, trigger, **kwargs):
		_RESOURCE_MAPPING = {
			resources.NETWORK: 'network',
			resources.SUBNET: 'subnet',
			resources.PORT: 'port',
			resources.ROUTER: 'router'
		}
		self._log_handler.debug("Received callback from Neutron for resource: " + str(resource) + " Event: " + str(event))
		assert resource is not None
		if(resource not in _RESOURCE_MAPPING.keys()):
			self._log_handler.error("Received resource event for : " + str(resource) + ". This is unsupported. Returning the call")
			return
		try:
			if 'payload' in kwargs:
				self._log_handler.debug("Event with payload as key received")
				context = kwargs['payload'].context
				res = kwargs['payload'].desired_state
				res_id = kwargs['payload'].resource_id
				copy_kwargs = kwargs
			else:
				context = kwargs['context']
				res = kwargs.get(resource)
				res_id = kwargs.get("%s_id" % resource, None)
				copy_kwargs = kwargs.copy()
				copy_kwargs.pop('context')
			if res_id is None:
				res_id = res.get('id')
			if resource==resources.NETWORK:
				self._handle_network_event(event,**copy_kwargs)
			elif  resource==resources.SUBNET:
				self._handle_subnet_event(event,**copy_kwargs)
			elif resource==resources.PORT:
				self._handle_port_event(event, **copy_kwargs)
			elif resource==resources.ROUTER:
				self._handle_router_event(event,**copy_kwargs)
		except Exception as ex:
			template = "An exception of type {0} occurred. Arguments:\n{1!r}"
			message = template.format(type(ex).__name__, ex.args)
			self._log_handler.error(message)
			for key in copy_kwargs.keys():
				self._log_handler.debug("NeutronEventHandler Key: " + str(key) + " value: " + str(kwargs[key]) + "\n")
			return

	def _create_thrift_channel(self, handler):
		handler.debug("NeutronEventHandler: Creating Thrift Client")
		while self._maxinet_channel ==None:
			try:
				transport = TSocket.TSocket(hostIP, hostPort)
				handler.debug("Created Socket to Connect to " + str(hostIP) + " at port: " + str(hostPort))
				transport = TTransport.TBufferedTransport(transport)
				handler.debug("Created Buffer Transport")
				protocol = TBinaryProtocol.TBinaryProtocol(transport)
				handler.debug("Created Binary Protocol")
				self._maxinet_channel = MaxinetConfigurationService.Client(protocol)
				handler.debug("Created RPC Client")
				transport.open()
			except Thrift.TException as ts:
				handler.error(str(ts.message))
				self._maxinet_channel=None
				time.sleep(1.0)
				pass
		handler.debug("Maxinet Channel: " + str(self._maxinet_channel) + "\n\n")

	def _send_data(self, res):
		_data_sent = False
		_numFailures = 0
		if self._maxinet_channel == None:
			self._create_thrift_channel(self._log_handler)
		while _data_sent != True and _numFailures <= MAX_RETRIES:
			try:
				_data_sent = self._maxinet_channel.resource_configured(res)
			except Thrift.TException as ts :
				self._log_handler.error(str(ts.message) + ". Attempting to recreate the socket")
				self._maxinet_channel=None
				self._create_thrift_channel(self._log_handler)
				_numFailures = _numFailures+1
				time.sleep(math.pow(2,_numFailures)*0.05)
			except Thrift.TApplicationException as ts:
				self._log_handler.error(str(ts.message))
				self._log_handler.error("Unable to process the data. Ignoring the event")
				return
			except Exception as ex:
				if 'Broken pipe' in (ex.args):
					self._log_handler.warning("Encountered a Broken connection. Retrying again")
					self._maxinet_channel=None
					self._create_thrift_channel(self._log_handler)
					_numFailures = _numFailures+1
					time.sleep(math.pow(2,_numFailures)*0.05)
				else:
					self._log_handler.error("Encountered Exception: " + str(ex.message))
					self._log_handler.warning("Ignoring the event from Neutron....")
					return
		return

	def _setup_logger(self,name, log_file, level=logging.INFO):
		self._log_handler = logging.getLogger(name)
		self._filehandler=logging.FileHandler(log_file, mode='w')
		self._filehandler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
		self._log_handler.setLevel(level=level)
		self._log_handler.addHandler(self._filehandler)






