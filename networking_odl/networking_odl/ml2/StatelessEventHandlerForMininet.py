from neutron_lib.callbacks import events
from neutron_lib.callbacks import registry
from neutron_lib.callbacks import resources
import threading
import time
import collections
import logging
import math
import json
from stateless import ttypes
from thrift import Thrift
from thrift.transport import TSocket
from thrift.transport import TTransport
from thrift.protocol import TBinaryProtocol
from stateless import MaxinetConfigurationService
from kafka import KafkaProducer, errors

import eventlet

ODLResource = collections.namedtuple('ODLResource', ('singular', 'plural'))
DEFAULT_MTU = 1450
SOCKET_TIMEOUT=20000
LOG = logging.getLogger("networking_odl.maxinet.")
hostIP = "192.168.56.101"
hostPort = 9090
kafka_server = "192.168.56.101"
kafka_port = 9092
MAX_RETRIES=5
DEQUEUE_THREAD_SLEEPTIME=5

class StatelessEventHandlerForMininet(object):
	# Creating various static variables for the class. Neutron creates one Object of this class per Neutron Server
	# process that is shared among several green-let threads. It is therefore necessary to ensure that the data
	# received from neutron is stored in a single queue.
	_channel_lock = threading.Lock()
	_queue_lock = threading.Lock()
	_maxinet_channel=None
	_socket = None
	_transport=None
	_protocol=None
	queue = dict()

	def __init__(self):
		#eventlet.Queue()
		self._subscribe()
		self._initialize()

	def _subscribe(self):
		self._event_mapping = {
			events.AFTER_CREATE:ttypes.EVENT.CREATE,
			events.AFTER_UPDATE:ttypes.EVENT.UPDATE,
			events.BEFORE_DELETE:ttypes.EVENT.DELETE
		}
		self._RESOURCE_MAPPING = {
			resources.NETWORK: ttypes.RESOURCE.NETWORK,
			resources.SUBNET: ttypes.RESOURCE.SUBNET,
			resources.PORT: ttypes.RESOURCE.PORT,
			resources.ROUTER: ttypes.RESOURCE.ROUTER
		}
		self._RESOURCE_KEYS={
			resources.ROUTER: "router",
			resources.PORT: "port",
			resources.SUBNET: "subnet",
			resources.NETWORK: "network"
		}
		for event in (events.AFTER_CREATE, events.BEFORE_DELETE, events.AFTER_UPDATE):
			registry.subscribe(self._callback, resources.NETWORK, event)
			registry.subscribe(self._callback, resources.SUBNET, event)
			registry.subscribe(self._callback, resources.PORT, event)
			registry.subscribe(self._callback, resources.ROUTER, event)


	def _initialize(self):
		#self._timeout = 3
		self._setup_logger("StatelessEventHandler", "/home/stack/mininet_handler/client.log", level=logging.DEBUG)
		self._USE_KAFKA=True
		if (self._USE_KAFKA):
			self._topic = "neutron_events_for_simulation"
		else:
			self._channel_creator = threading.Thread(target=self._create_thrift_channel, args=(self._log_handler,))
			self._channel_creator.start()
			self._monitor_thread = threading.Thread(target=self._monitor, args=(1.0,  ))
			self._monitor_thread.daemon=True
			self._monitor_count = 0
			self._monitor_thread.start()

	def _monitor(self, keepalive):
		while True:
			if(StatelessEventHandlerForMininet._maxinet_channel==None):
				self._log_handler.error("Thrift Channel is not established")
				self._create_thrift_channel(self._log_handler)
			else:
				try:
					StatelessEventHandlerForMininet._channel_lock.acquire()
					result = StatelessEventHandlerForMininet._maxinet_channel.keepalive()
					self._monitor_count = self._monitor_count+1
					StatelessEventHandlerForMininet._channel_lock.release()
					if result:
						if (self._monitor_count % 1000 ==0):
							self._log_handler.debug("Thrift connection is up")
					else:
						self._reset_connection(0, "Thrift connection is down. Recreating the channel")
				except Exception as ex:
					StatelessEventHandlerForMininet._channel_lock.release()
					self._reset_connection(0, "Thrift connection is down. Recreating the channel")
					self._log_handler.debug("Reconnection Successful")
			time.sleep(keepalive)

	def _callback(self, resource, event, trigger, **kwargs):
		neutronresource = ttypes.resource()
		neutronresource.event  = self._event_mapping[event]
		neutronresource.type = self._RESOURCE_MAPPING[resource]
		self._log_handler.debug("Received callback from Neutron for resource: " + str(resource) + " Event: " + str(event))
		if(resource not in self._RESOURCE_MAPPING.keys()):
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
		except Exception as ex:
			template = "An exception of type {0} occurred. Arguments:\n{1!r}"
			message = template.format(type(ex).__name__, ex.args)
			self._log_handler.error(message)
			for key in copy_kwargs.keys():
				self._log_handler.debug("Key: " + str(key) + " value: " + str(kwargs[key]) + "\n")
			return
		if event in (events.AFTER_UPDATE, events.AFTER_CREATE):
			copy_kwargs = copy_kwargs[self._RESOURCE_KEYS[resource]]
		copy_kwargs['resource'] = str(resource)
		copy_kwargs['event'] = str(event)
		neutronresource.data = str(copy_kwargs).encode("ascii")
		channel = "Thrift Channel\n\n"
		if(self._USE_KAFKA):
			'''Sending the dictionary copy_kwargs as a json object over the Kafka bus'''
			self._send_data_using_kafka(copy_kwargs)
			channel = "Kafka bus\n\n"
		else:
			self._send_data(neutronresource)
		self._log_handler.debug("Sent event: " + str(ttypes.EVENT._VALUES_TO_NAMES[neutronresource.event]) + " for resource: " + str(resource) + " on " + str(channel))

	def _send_data_using_kafka(self, data):
		try:
			self._kafka_bootstrap = str(kafka_server) +":" + str(kafka_port)
			self._log_handler.debug("Attempting to bootstrap to Server: " + str(self._kafka_bootstrap))
			_kafka_producer = 	KafkaProducer(bootstrap_servers= self._kafka_bootstrap, value_serializer=lambda v: json.dumps(v).encode('utf-8'))
			self._log_handler.debug("Sending data to the simulator: " + str(data))
			_kafka_producer.send(topic=self._topic, value=data)
			_kafka_producer.close()
		except errors.KafkaTimeoutError as ex:
			self._log_handler.error("Send failed as the producer timed out " + str(ex.message))
			self._log_handler.exception("Failed Send")
		except Exception as ex:
			self._log_handler.error("Received exception: " + str(ex.message) + " when sending " + str(data))
			return

	def _create_thrift_channel(self, handler):
		handler.debug("Creating Thrift Client")
		StatelessEventHandlerForMininet._channel_lock.acquire()
		while StatelessEventHandlerForMininet._maxinet_channel ==None:
			try:
				StatelessEventHandlerForMininet._socket = TSocket.TSocket(hostIP, hostPort)
				StatelessEventHandlerForMininet._socket.setTimeout(SOCKET_TIMEOUT)
				handler.debug("Created Socket to Connect to " + str(hostIP) + " at port: " + str(hostPort))
				StatelessEventHandlerForMininet._transport = TTransport.TBufferedTransport(StatelessEventHandlerForMininet._socket)
				handler.debug("Created Buffer Transport")
				StatelessEventHandlerForMininet._protocol = TBinaryProtocol.TBinaryProtocol(StatelessEventHandlerForMininet._transport)
				handler.debug("Created Binary Protocol")
				StatelessEventHandlerForMininet._maxinet_channel = MaxinetConfigurationService.Client(StatelessEventHandlerForMininet._protocol)
				handler.debug("Created RPC Client")
				StatelessEventHandlerForMininet._transport.open()
				StatelessEventHandlerForMininet._channel_lock.release()
			except Thrift.TException as ts:
				handler.error(str(ts.message))
				StatelessEventHandlerForMininet._transport.close()
				StatelessEventHandlerForMininet._maxinet_channel=None
				StatelessEventHandlerForMininet._channel_lock.release()
				time.sleep(1.0)
				pass
		if(StatelessEventHandlerForMininet._channel_lock.locked()):
			StatelessEventHandlerForMininet._channel_lock.release()
		handler.debug("Maxinet Channel: " + str(StatelessEventHandlerForMininet._maxinet_channel) + "\n\n")
		return

	def _reset_connection(self, _failures, reason):
		self._log_handler.error(str(reason) + ". Attempting to recreate the socket")
		StatelessEventHandlerForMininet._transport.flush()
		StatelessEventHandlerForMininet._transport.close()
		StatelessEventHandlerForMininet._maxinet_channel=None
		StatelessEventHandlerForMininet._channel_lock.release()
		self._create_thrift_channel(self._log_handler)
		time.sleep(math.pow(2,_failures+1)*0.5)
		self._log_handler.debug("Awake from sleep. Starting again...Failures: " + str(_failures))
		return _failures+1

	def _send_data(self, res):
		_data_sent = False
		_numFailures = 0
		if StatelessEventHandlerForMininet._maxinet_channel == None:
			self._create_thrift_channel(self._log_handler)
		while _data_sent != True and _numFailures < MAX_RETRIES:
			try:
				self._log_handler.debug("Attempting to get the lock")
				StatelessEventHandlerForMininet._channel_lock.acquire()
				self._log_handler.debug("Got the lock")
				_data_sent = StatelessEventHandlerForMininet._maxinet_channel.resource_configured(res)
				StatelessEventHandlerForMininet._channel_lock.release()
			except Thrift.TException as ts :
				_data_sent=False
				_numFailures=self._reset_connection(_numFailures, ts.message)
				continue
			except Thrift.TApplicationException as ts:
				self._log_handler.error(str(ts.message))
				self._log_handler.error("Unable to process the data. Ignoring the event")
				StatelessEventHandlerForMininet._channel_lock.release()
				return
			except Exception as ex:
				if 'Broken pipe' in (ex.args):
					_data_sent=False
					_numFailures=self._reset_connection(_numFailures, "Encountered a Broken connection")
					continue
				elif 'timed out' in str(ex.message):
					_data_sent=False
					self._log_handler.exception("Exception occured")
					_numFailures=self._reset_connection(_numFailures, ex.message)
					continue
				else:
					StatelessEventHandlerForMininet._channel_lock.release()
					self._log_handler.error("Encountered Exception: " + str(ex.message))
					return
		if not _data_sent and _numFailures < MAX_RETRIES:
			self._log_handler.debug("Exiting prior to retrying")
		return

	def _setup_logger(self,name, log_file, level=logging.INFO):
		self._log_handler = logging.getLogger(name)
		self._filehandler=logging.FileHandler(log_file, mode='w')
		self._filehandler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
		self._log_handler.setLevel(level=level)
		self._log_handler.addHandler(self._filehandler)






