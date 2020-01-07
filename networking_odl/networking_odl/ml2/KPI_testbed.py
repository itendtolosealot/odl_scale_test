
'''
from Frontend import maxinet
from tools import FatTree
from Mininet.mininet.node import OVSSwitch
from Mininet.mininet import topo
from Mininet.mininet import node
'''

import time
import yaml
import threading
import logging
from thrift import Thrift
from thrift.transport import TSocket
from thrift.transport import TTransport
from thrift.protocol import TBinaryProtocol
from thrift.server import TServer
from config import MaxinetConfigurationService
from config import ttypes
import gevent, gevent.server
from telnetsrv.green import TelnetHandler, command
from uuid import UUID


NODE_INFO="workers.yaml"
NUM_DCGWS=2
NUM_L2_SWITCH=1
ODL_IP="10.0.0.1"
ODL_PORT=6633

DCGW_CTRL_IP="20.0.0.1"
DCGW_CTRL_PORT=6633
THRTFT_PORT=9090
HOST_IP="10.128.128.103"
NEUTRONHANDLERPOINTER = None

logging.basicConfig(filename= "/home/stack/mininet_handler/mininet_handler.log",level=logging.DEBUG)

'''class Console(TelnetHandler):
	WELCOME = "Welcome to maxinet CLI. This software belongs to ERICSSON. If you have accidentally accessed this portal, exit immediately"
	PROMPT = "maxinet> "
	authNeedUser=False
	authNeedPassword=False

	def __init__(self):
		self._callback_handler = NEUTRONHANDLERPOINTER
		self._callback_handler._log_handler.debug("Starting Console")
		self._username = "maxinet"
		self._password = "maxinet1234"

	def writeerror(self, text):
		TelnetHandler.writeerror(self, "\x1b[91m%s\x1b[0m" % text )

	def authCallback(self, username,password):
		if(username != self._username) or (password != self._password):
			raise RuntimeError("Incorrect username or password. ")

	@command(['network','subnet','port','router'])
	def command_network(self, params):
		message=None
		if (len(params) != 1):
			self.writeerror("Incorrect number of arguments passed. Seek help")
			return
		if (params[0] != "all"):
			try:
				val = UUID(params[0], version=4)
			except ValueError:
				self.writeerror("UUID is invalid")
		try:
			message = self._callback_handler.handle_cli("network", params[0])
		except Exception as ex:
			self.writeerror("Encountered an exception when runnning the command: " + str(ex.message))
		if(message != None):
			self.writeresponse(message)

	@command('info')
	def command_info(self, params):
		self.writeresponse( "Username: %s, terminal type: %s" % (self.username, self.TERM) )
		self.writeresponse( "Command history:" )
		for c in self.history:
			self.writeresponse("  %r" % c)

	def _setup_logger(self,name, log_file, level=logging.INFO):
		self._log_handler = logging.getLogger(name)
		self._filehandler=logging.FileHandler(log_file, mode='w')
		self._filehandler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
		self._log_handler.setLevel(level=level)
		self._log_handler.addHandler(self._filehandler)



with open(NODE_INFO, 'r') as f:
	dataMap = yaml.safe_load(f)
cluster = maxinet.Cluster()
worker_info =dataMap['workers']
for key in worker_info:
	cluster.add_worker_by_hostname(dataMap[key])

NUM_DPNS = len(cluster.worker)-NUM_DCGWS-NUM_L2_SWITCH

for w1 in range(len(cluster.worker)-NUM_DCGWS-NUM_L2_SWITCH):
	for w2 in range(len(w1)):
		cluster.create_tunnel(cluster.worker(w1), cluster.worker(w2))
topology = topo()

odl_controller = node.RemoteController('master', ip=ODL_IP, port=ODL_PORT)
dcgw_pseudo_controller = node.RemoteController('dcgw', ip=DCGW_CTRL_IP, port=DCGW_CTRL_PORT)
exp = maxinet.Experiment(cluster, topology, controller=None, switch=OVSSwitch)
exp.setup()
""" Adding br-int and br-ext and connecting them """
for w1 in range(NUM_DPNS):
	name="br-int"+str(w1)
	exp.addSwitch(name, wid=w1)
	exp.get_node(name).cmd("start", [odl_controller])

for w in range(NUM_DCGWS):
	name="dcgw_" + str(w)
	exp.addSwitch(name, wid=NUM_DPNS+w)
	exp.get_node(name).cmd("start", [dcgw_pseudo_controller])

""" The underlay is a single L2 Switch with connections to all the DPNs. We do it this way so that every DPN has a single physical link on which all packets can be sent. 
There is no need to 'plugin' to underlay. Alternatively, each switch could be connected to every other switch via a physical link. In this case, it is not clear how to map 
all the vXLAN/MPLSoGRE tunnels to the different physical links. The central switch is expected to do L2 learning and forward the packets accordingly"""

for w in range(NUM_L2_SWITCH):
	name="underlay_" + str(w)
	exp.addSwitch(name, wid=NUM_DPNS+NUM_DCGWS+w)
	exp.get_node(name).cmd("start",[])

for w2 in range(NUM_L2_SWITCH):
	for w1 in range(NUM_DPNS):
		s1_name = "br-int" + str(w1)
		s2_name = "underlay_" + str(w2)
		s1 = exp.get_node(s1_name)
		s2 = exp.get_node(s2_name)
		exp.addLink(s1,s2)
	for w1 in range(NUM_DCGWS):
		s1_name = "dcgw_" + str(w1)
		s2_name = "underlay_" + str(w2)
		s1 = exp.get_node(s1_name)
		s2 = exp.get_node(s2_name)
		exp.addLink(s1,s2)

'''

class Console(TelnetHandler):
	WELCOME = "Welcome to maxinet CLI. This software belongs to ERICSSON. If you have accidentally accessed this portal, exit immediately"
	PROMPT = "maxinet> "
	authNeedUser=False
	authNeedPassword=False

	@command(['echo', 'copy', 'repeat'])
	def command_echo(self, params):
		'''<text to echo>
		Echo text back to the console.
		'''
		self.writeresponse( ' '.join(params) )

	def _validate_uuid(self, uid):
		try:
			val = UUID(uid, version=4)
		except ValueError:
			return False
		return True

	def __process_telnet_command(self,cmd, params):
		message=None
		if (len(params) != 1):
			self.writeerror("Incorrect number of arguments passed. Seek help")
			return
		if (params[0] != "all"):
			if( not self._validate_uuid(uid=params[0])):
				self.writeerror("UUID is Invalid")
				return

		try:
			message = self._callback_handler.handle_display_cli(cmd, params[0])
		except Exception as ex:
			self.writeerror("Encountered an exception when runnning the command: " + str(ex.message))
		if(message != None):
			self.writeresponse(message)

	@command('network')
	def command_network(self,params):
		'''<network_uuid/ 'all'>
		If keyword <'all'> is used, it results in displaying information about all known networks. if <network_uuid> is provided, it will display info about the Network with the passed UUID. It will return an error, if no such network is found.
		'''
		self._callback_handler = NEUTRONHANDLERPOINTER
		self.__process_telnet_command("network",params)

	@command('subnet')
	def command_subnet(self,params):
		'''<subnet_uuid/ 'all'>
		If keyword <'all'> is used, it results in displaying information about all known subnet. if <subnet_uuid> is provided, it will display info about the Subnet with the passed UUID. It will return an error, if no such subnet is found.
		'''
		self._callback_handler = NEUTRONHANDLERPOINTER
		self.__process_telnet_command("subnet",params)

	@command('port')
	def command_port(self,params):
		'''<port_uuid/ 'all'>
		If keyword <'all'> is used, it results in displaying information about all known port. if <port_uuid> is provided, it will display info about the Port with the passed UUID. It will return an error, if no such port is found.
		'''
		self._callback_handler = NEUTRONHANDLERPOINTER
		self.__process_telnet_command("port",params)

	@command('router')
	def command_router(self,params):
		'''<router_uuid/ 'all'>
		If keyword <'all'> is used, it results in displaying information about all known Router. if <router_uuid> is provided, it will display info about the router with the passed UUID. It will return an error, if no such router is found.
		'''
		self._callback_handler = NEUTRONHANDLERPOINTER
		self.__process_telnet_command("router",params)

	@command('clean')
	def command_clean(self,params):
		'''<resource/ 'all'> <uuid/'all'>
		If keyword <'all'> is used for first argument, all resources will be deleted. If a specific resource is requested and the seocnd option is 'all', all resources of that type will be deleted. Else, a resoruce with specific UUID is deleted.
		'''
		keyword_mapping={"all": ["network", "subnet", "port", "router"]}
		message = ""
		self._callback_handler = NEUTRONHANDLERPOINTER
		if (len(params)< 1 or len(params) > 2):
			self.writeerror("Incorrect number of Arguments: ")
			return
		if (len(params)==2):
			if (params[1] != "all"):
				if(not self._validate_uuid(uid=params[1])):
					self.writeerror("UUID is invalid")
					return
				if (params[0]=="all"):
					self.writeerror("Incorrect use of keyword all")
					return
		if (params[0] == "all"):
			for item in keyword_mapping["all"]:
				message += self._callback_handler._handle_cleanup([item, "all"])
		else:
			message += self._callback_handler._handle_cleanup(params)
		if ("Error" in message):
			self.writeerror(message)
		else:
			self.writeresponse(message)

class NeutronEventHandler():

	def __init__(self):
		self._subscribe()

	def _subscribe(self):
		self._subnets_info = dict()
		self._routers_info = dict()
		self._port_info = dict()
		self._network_info = dict()
		self._setup_logger("maxinet-server", "/home/stack/mininet_handler/mininet_handler.log", level=logging.DEBUG)
		global NEUTRONHANDLERPOINTER
		NEUTRONHANDLERPOINTER= self
		self._console = Console
		self._lock = dict()
		self._lock["network"] = threading.Lock()
		self._lock["subnet"] = threading.Lock()
		self._lock["port"] = threading.Lock()
		self._lock["router"] = threading.Lock()
		self._telnet_handler= threading.Thread(target=self._create_telnet_channel, args=(3,))
		self._telnet_handler.daemon=True
		self._telnet_handler.start()

	def _create_telnet_channel(self, val):
		self._log_handler.debug("Telnet server started")
		self._telnet_server =gevent.server.StreamServer(('127.0.0.1', 55555), self._console.streamserver_handle)
		try:
			self._telnet_server.serve_forever()
		except KeyboardInterrupt:
			self._telnet_server.stop(timeout=val)
			pass
		self._log_handler.info("Thread was terminated. Exiting the program")
		return

	def _handle_cleanup(self,params):
		message = ""
		param_dict = {
			"network": [self._network_info],
			"subnet": [self._subnets_info],
			"port": [self._port_info],
			"router": [self._routers_info],
		}
		if (len(params)==2):
				try:
					self._lock[params[0]].acquire()
					if (params[1]!="all"):
						param_dict[params[0]][0].pop(params[1])
					else:
						param_dict[params[0]][0].clear()
					self._lock[params[0]].release()
					message = str(params[0]) + ": " + str(params[1]) + " removed from the DS\n"
					return message
				except KeyError:
					message="Error! Unable to find " + str(params[0]) + " resource: " + str(params[1]) + ". No action taken"
					self._lock[params[0]].release()
					self._log_handler.error("Attempt to delete " + str(params[0]) + ": " + str(params[1]) + ". Resource not found")
					return message
				except Exception as ex:
					message += "Error! Received exception: " + str(ex.message)
					return message
		else:
			message+= "Error! Incorrect number of parameters passed"
			self._log_handler.error("_handle_cleanup expects a single array with length 2. Obtained array with length: " + str(len(params)))
			return message


	def handle_display_cli(self, cmd, uid):
		message = ""
		CLI_MAPPING = {
			"network": self._network_info,
			"subnet": self._subnets_info,
			"port": self._port_info,
			"router": self._routers_info
		}
		self._log_handler.debug("Received CLI command for: " + str(cmd) + " with uuid: " + str(uid))
		if uid == "all":
			if(len(CLI_MAPPING[cmd])==0):
				message += "No " + str(cmd) + "s found."
			for item in CLI_MAPPING[cmd].keys():
				net = CLI_MAPPING[cmd][item]
				message += str(net) + str("\n")
		else:
			try:
				net = CLI_MAPPING[cmd][uid]
				message += str(net)
			except KeyError:
				message += "Error: No network with the uuid: " + str(uid)  + " is available"
		return message

	def __network(self,res):
		try:
			self._lock["network"].acquire()
			if res.event in ("after_create", ttypes.EVENT.UPDATE):
				self._network_info[res.net.network_uuid] = res.net
			elif res.event == ttypes.EVENT.DELETE:
				try:
					self._network_info.pop(res.net.network_uuid)
				except KeyError:
					self._log_handler.error("Attempting to delete unknown Network: " + str(res.net.network_uuid) + "\n\n")
			else:
				self._log_handler.error("Unsupported operation on Network: " + str(res.net.network_uuid) + "\n\n")
			self._lock["network"].release()
		except Exception as ex:
			self._log_handler.error("Exception: " + str(ex.message))
			self._lock["network"].release()

	def __subnet(self,res):
		try:
			self._lock["subnet"].acquire()
			if res.event in ("after_create", ttypes.EVENT.UPDATE):
				self._subnets_info[res.sub.subnet_uuid] = res.sub
			elif res.event == ttypes.EVENT.DELETE:
				try:
					self._subnets_info.pop(res.sub.subnet_uuid)
				except KeyError:
					self._log_handler.error("Attempting to delete unknown Subnet: " + str(res.sub.subnet_uuid) + "\n\n")
			else:
				self._log_handler.error("Unsupported operation on Subnet: " + str(res.sub.subnet_uuid) + "\n\n")
			self._lock["subnet"].release()
		except Exception as ex:
			self._log_handler.error("Exception: " + str(ex.message))
			self._lock["subnet"].release()

	def __port(self,res):
		try:
			self._lock["port"].acquire()
			if res.event in ("after_create", ttypes.EVENT.UPDATE):
				self._port_info[res.pt.port_uuid] = res.pt
			elif res.event == ttypes.EVENT.DELETE:
				try:
					self._port_info.pop(res.pt.port_uuid)
				except KeyError:
					self._log_handler.error("Attempting to delete unknown Port: " + str(res.pt.port_uuid) + "\n\n")
			else:
				self._log_handler.error("Unsupported operation on Port: " + str(res.pt.port_uuid) + "\n\n")
			self._lock["port"].release()
		except Exception as ex:
			self._log_handler.error("Exception: " + str(ex.message))
			self._lock["port"].release()

	def __router(self,res):
		try:
			self._lock["router"].acquire()
			if res.event == "after_create":
				try:
					self._routers_info[res.rtr.router_uuid] = (list(), list(dict()))
				except Exception as ex:
					template = "An exception of type {0} occurred. Arguments:\n{1!r}"
					message = template.format(type(ex).__name__, ex.args)
					self._log_handler.error(message)
					self._lock["router"].release()
					return
			elif res.event==ttypes.EVENT.ATTACH:
				try:
					(old_router_subnets,routes) = self._routers_info[res.rtr.router_uuid]
					new_subnets = res.rtr.subnets
					delta = set(new_subnets).difference( set(old_router_subnets))
					self._log_handler.debug("Added new subnet: " + str(delta))
					self._routers_info[res.rtr.router_uuid] = (res.rtr.subnets, res.rtr.routes)
				except KeyError:
					self._log_handler.error("Received subnet attach for unknown router: " + str(res.rtr.router_uuid) + "\n\n")
					self._lock["router"].release()
					return
			elif res.event==ttypes.EVENT.DETACH:
				try:
					(old_router_subnets,routes) = self._routers_info[res.rtr.router_uuid]
					new_subnets = res.rtr.subnets
					delta = set(old_router_subnets).difference(set(new_subnets))
					self._log_handler.debug("Deleted a subnet: " + str(delta))
					self._routers_info[res.rtr.router_uuid] = (res.rtr.subnets, res.rtr.routes)
				except KeyError:
					self._log_handler.error("Received subnet detach for unknown router: " + str(res.rtr.router_uuid) + "\n\n")
					self._lock["router"].release()
					return
			elif res.event==ttypes.EVENT.UPDATE:
				try:
					(subnets,old_routes) = self._routers_info[res.rtr.router_uuid]
					new_routes = res.rtr.routes
					delta = set(new_routes).union(set(old_routes)) - set(new_routes).intersection(set(old_routes))
					self._routers_info[res.rtr.router_uuid]= (subnets,res.rtr.routes)
				except KeyError:
					self._log_handler.error("Received update event for unknown router: " + str(res.rtr.router_uuid) + "\n\n")
					self._lock["router"].release()
					return
			elif res.event==ttypes.EVENT.DELETE:
				try:
					self._routers_info.pop(res.rtr.router_uuid)
				except KeyError:
					self._log_handler.error("Attempting to delete unknown Router: " + str(res.rtr.router_uuid) + "\n\n")
					self._lock["router"].release()
					return
			else:
				self._log_handler.error("Unsupported operation on Router: " + str(res.rtr.router_uuid) + "\n\n")
			self._lock["router"].release()
		except Exception as ex:
			self._log_handler.error("Exception: " + str(ex.message))
			self._lock["router"].release()

	def __print(self, resourcetype, resource=None ):
		if (resource==None):
			if resourcetype==ttypes.RESOURCE.NETWORK:
				self.__print(resourcetype, self._network_info)
			elif resourcetype==ttypes.RESOURCE.SUBNET:
				self.__print(resourcetype,self._subnets_info)
			elif resourcetype==ttypes.RESOURCE.PORT:
				self.__print(resourcetype, self._port_info)
			elif resourcetype==ttypes.RESOURCE.ROUTER:
				self.__print(resourcetype,self._routers_info)
			else:
				self._log_handler.error("Unknown resource! Received resource: " + str(resourcetype) + "\n\n")
				return
		else:
			for item in resource.keys():
				self._log_handler.debug("Resource Type: " + str(ttypes.RESOURCE._VALUES_TO_NAMES[resourcetype]) + ":" + str(resource[item]))
		self._log_handler.debug("\n")

	def resource_configured(self, res):
		if isinstance(res,ttypes.resource):
			if res.type==ttypes.RESOURCE.NETWORK:
				self._log_handler.debug("Received Network Event")
				self.__network(res)
			elif res.type==ttypes.RESOURCE.SUBNET:
				self._log_handler.debug("Received Subnet Event")
				self.__subnet(res)
			elif res.type==ttypes.RESOURCE.PORT:
				self._log_handler.debug("Received Port Event")
				self.__port(res)
			elif res.type==ttypes.RESOURCE.ROUTER:
				self._log_handler.debug("Received Router Event")
				self.__router(res)
			else:
				self._log_handler.warning("Event received for an unknown event: " + str(res.type) + ". No processing necessary\n\n")
		else:
			self._log_handler.error("Unknown resource received. Error!\n\n")
			return False
		self.__print(res.type)
		return True

	def _setup_logger(self,name, log_file, level=logging.INFO):
		self._log_handler = logging.getLogger(name)
		self._filehandler=logging.FileHandler(log_file, mode='w')
		self._filehandler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
		self._log_handler.setLevel(level=level)
		self._log_handler.addHandler(self._filehandler)


if __name__ == '__main__':
	handler = NeutronEventHandler()
	processor = MaxinetConfigurationService.Processor(handler)
	transport = TSocket.TServerSocket(host=HOST_IP, port=THRTFT_PORT)
	tfactory = TTransport.TBufferedTransportFactory()
	pfactory = TBinaryProtocol.TBinaryProtocolFactory()
	server = TServer.TSimpleServer(processor, transport, tfactory, pfactory)
	handler._log_handler.debug("Starting server....")
	while (True):
		try:
			server.serve()
		except KeyboardInterrupt:
			handler._log_handler.info("Session Terminated by the User. Exitting")
			break
		except Exception as ex:
			handler._log_handler.error("Thrift Server Error:" + str(ex.message))
	handler._log_handler.debug('done.')












