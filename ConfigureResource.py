from thrift import Thrift
from thrift.transport import TSocket
from thrift.transport import TTransport
from thrift.protocol import TBinaryProtocol
import NeutronEventHandlerForMininet
from config import MaxinetConfigurationService
import logging


logging.basicConfig(filename="~/mininet_handler/mininet_handler.log", level=logging.DEBUG)
hostIP = "10.128.128.102"
hostPort = 9090
try:
	transport = TSocket.TSocket(hostIP, hostPort)
	logging.debug("Created Socket to Connect to " + str(hostIP) + " at port: " + str(hostPort))
	transport = TTransport.TBufferedTransport(transport)
	logging.debug("Created Buffer Transport")
	protocol = TBinaryProtocol.TBinaryProtocol(transport)
	logging.debug("Created Binary Protocol")
	client = MaxinetConfigurationService.Client(protocol)
	logging.debug("Created RPC Client")
	transport.open()
	eventhandler = NeutronEventHandlerForMininet(client)
	logging.debug("Created Neutron Event Handler")
except Thrift.TException as ts:
	logging.debug(str(ts.message))


