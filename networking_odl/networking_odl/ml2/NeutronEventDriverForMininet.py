# Copyright (c) 2013-2014 OpenStack Foundation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import NeutronEventHandlerForMininet
from oslo_log import helpers as log_helpers
from oslo_config import cfg
import logging
from neutron_lib.plugins.ml2 import api
import  networking_odl.journal

from thrift import Thrift
from thrift.transport import TSocket
from thrift.transport import TTransport
from thrift.protocol import TBinaryProtocol
from config import MaxinetConfigurationService

LOG = logging.getLogger(__name__)
hostIP = "10.128.128.103"
hostPort = 9090

class NeutronEventDriverForMininet(api.MechanismDriver):
	"""Mininet Driver for Neutron."""
	def __init__(self):
		self.initialize()
	def initialize(self):
		logging.basicConfig(filename="/home/stack/mininet_handler/mininet_handler.log", level=logging.DEBUG)
		logging.info("Initializing the Neutron Event Driver for Mininet")
		try:
			transport = TSocket.TSocket(hostIP, hostPort)
			logging.debug("Created Socket to Connect to " + str(hostIP) + " at port: " + str(hostPort))
			transport = TTransport.TBufferedTransport(transport)
			logging.debug("Created Buffer Transport")
			protocol = TBinaryProtocol.TBinaryProtocol(transport)
			logging.debug("Created Binary Protocol")
			self._client = MaxinetConfigurationService.Client(protocol)
			logging.debug("Created RPC Client")
			transport.open()
			self._eventhandler = NeutronEventHandlerForMininet.NeutronEventHandlerForMininet(self._client)
			logging.debug("Created Neutron Event Handler")
		except Thrift.TException as ts:
			logging.debug(str(ts.message))

	def get_event_handler(self):
		return self._eventhandler

	@log_helpers.log_method_call
	def create_network_precommit(self, context):
		pass

	@log_helpers.log_method_call
	def create_subnet_precommit(self, context):
		OpenDaylightMechanismDriver._record_in_journal(
			context, odl_const.ODL_SUBNET, odl_const.ODL_CREATE)

	@log_helpers.log_method_call
	def create_port_precommit(self, context):
		pass

	@log_helpers.log_method_call
	def update_network_precommit(self, context):
		pass

	@log_helpers.log_method_call
	def update_subnet_precommit(self, context):
		pass

	@log_helpers.log_method_call
	def update_port_precommit(self, context):
		pass

	@log_helpers.log_method_call
	def delete_network_precommit(self, context):
		pass

	@log_helpers.log_method_call
	def delete_subnet_precommit(self, context):
		# Use the journal row's data field to store parent object
		# uuids. This information is required for validation checking
		# when deleting parent objects.
		pass

	@log_helpers.log_method_call
	def delete_port_precommit(self, context):
		# Use the journal row's data field to store parent object
		# uuids. This information is required for validation checking
		# when deleting parent objects.
		pass

	def _sync_security_group_create_precommit(
			self, context, operation, object_type, res_id, sg_dict):
		pass

	# NOTE(yamahata): when security group is created, default rules
	# are also created.



	def sync_from_callback_precommit(self, context, operation, res_type,
									 res_id, resource_dict, **kwargs):
		pass

	def sync_from_callback_postcommit(self, context, operation, res_type,
									  res_id, resource_dict, **kwargs):
		pass

	def _postcommit(self, context):
		pass


	def bind_port(self, port_context):
		pass

	def check_vlan_transparency(self, context):
		pass



