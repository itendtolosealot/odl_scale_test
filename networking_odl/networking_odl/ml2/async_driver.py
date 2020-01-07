# Copyright (c) 2019 OpenStack Foundation
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

import threading
import eventlet
import thread
import abc
import six
import netaddr
import requests

from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import excutils

from neutron.common import utils
from neutron import context as neutron_context
from neutron.common import constants as l3_constants
from neutron_lib import exceptions as nlib_ex
from neutron.extensions import allowedaddresspairs as addr_pair

from networking_odl.common import constants as odl_const
from networking_odl.common import utils as odl_utils
from networking_odl.common import client as _odl_client
from networking_odl.common import filters

from networking_odl._i18n import _LE
from networking_odl._i18n import _LW

LOG = logging.getLogger(__name__)


def call_thread_on_end(func):
	def new_func(obj, *args, **kwargs):
		return_value = func(obj, *args, **kwargs)
		obj.journal.set_sync_event()
		return return_value
	return new_func


@six.add_metaclass(abc.ABCMeta)
class ResourceODLFilterBase(object):
	@staticmethod
	@abc.abstractmethod
	def filter_create_attributes(resource):
		pass

	@staticmethod
	@abc.abstractmethod
	def filter_update_attributes(resource):
		pass

	@staticmethod
	@abc.abstractmethod
	def filter_create_attributes_with_plugin(resource, plugin, dbcontext):
		pass


class NetworkODLFilter(ResourceODLFilterBase):
	@staticmethod
	def filter_create_attributes(network):
		"""Filter out network attributes not required for a create."""
		odl_utils.try_del(network, ['status', 'subnets'])

	@staticmethod
	def filter_update_attributes(network):
		"""Filter out network attributes for an update operation."""
		odl_utils.try_del(network, ['id', 'status', 'subnets', 'tenant_id'])

	@classmethod
	def filter_create_attributes_with_plugin(cls, network):
		cls.filter_create_attributes(network)


class SubnetODLFilter(ResourceODLFilterBase):
	@staticmethod
	def filter_create_attributes(subnet):
		"""Filter out subnet attributes not required for a create."""
		pass

	@staticmethod
	def filter_update_attributes(subnet):
		"""Filter out subnet attributes for an update operation."""
		odl_utils.try_del(subnet, ['id', 'network_id', 'ip_version', 'cidr',
								   'allocation_pools', 'tenant_id'])

	@classmethod
	def filter_create_attributes_with_plugin(cls, subnet):
		cls.filter_create_attributes(subnet)


class PortODLFilter(ResourceODLFilterBase):

	@classmethod
	def _fixup_allowed_ipaddress_pairs(cls, allowed_address_pairs):
		"""unify (ip address or network address) into network address"""
		for address_pair in allowed_address_pairs:
			ip_address = address_pair['ip_address']
			network_address = str(netaddr.IPNetwork(ip_address))
			address_pair['ip_address'] = network_address

	@staticmethod
	def _filter_unmapped_null(port):
		# NOTE(yamahata): bug work around
		# https://bugs.eclipse.org/bugs/show_bug.cgi?id=475475
		#   Null-value for an unmapped element causes next mapped
		#   collection to contain a null value
		#   JSON: { "unmappedField": null, "mappedCollection": [ "a" ] }
		#
		#   Java Object:
		#   class Root {
		#     Collection<String> mappedCollection = new ArrayList<String>;
		#   }
		#
		#   Result:
		#   Field B contains one element; null
		#
		# TODO(yamahata): update along side with neutron and ODL
		#   add when neutron adds more extensions
		#   delete when ODL neutron northbound supports it
		# TODO(yamahata): do same thing for other resources
		unmapped_keys = ['dns_name', 'port_security_enabled',
						 'binding:profile']
		keys_to_del = [key for key in unmapped_keys if port.get(key) is None]
		if keys_to_del:
			odl_utils.try_del(port, keys_to_del)

	@classmethod
	def filter_create_attributes(cls, port):
		"""Filter out port attributes not required for a create."""
		cls._fixup_allowed_ipaddress_pairs(port[addr_pair.ADDRESS_PAIRS])
		cls._filter_unmapped_null(port)
		odl_utils.try_del(port, ['status'])

	@classmethod
	def filter_update_attributes(cls, port):
		"""Filter out port attributes for an update operation."""
		cls._fixup_allowed_ipaddress_pairs(port[addr_pair.ADDRESS_PAIRS])
		cls._filter_unmapped_null(port)
		odl_utils.try_del(port, ['network_id', 'id', 'status', 'tenant_id'])

	@classmethod
	def filter_create_attributes_with_plugin(cls, port):
		cls.filter_create_attributes(port)


class SecurityGroupODLFilter(ResourceODLFilterBase):
	@staticmethod
	def filter_create_attributes(sg):
		"""Filter out security-group attributes not required for a create."""
		pass

	@staticmethod
	def filter_update_attributes(sg):
		"""Filter out security-group attributes for an update operation."""
		pass

	@staticmethod
	def filter_create_attributes_with_plugin(sg):
		pass


class SecurityGroupRuleODLFilter(ResourceODLFilterBase):
	@staticmethod
	def filter_create_attributes(sg_rule):
		"""Filter out sg-rule attributes not required for a create."""
		filters.filter_security_group_rule(sg_rule)

	@staticmethod
	def filter_update_attributes(sg_rule):
		"""Filter out sg-rule attributes for an update operation."""
		filters.filter_security_group_rule(sg_rule)

	@staticmethod
	def filter_create_attributes_with_plugin(sg_rule):
		filters.filter_security_group_rule(sg_rule)


class OpendaylightPostCommitThread(object):
	"""Thread worker for the Opendaylight Post Commit Operations."""

	"""This code is the backend implementation for the OpenDaylight ML2
		MechanismDriver for OpenStack Neutron.
	"""
	FILTER_MAP = {
		odl_const.ODL_NETWORKS: NetworkODLFilter,
		odl_const.ODL_SUBNETS: SubnetODLFilter,
		odl_const.ODL_PORTS: PortODLFilter,
		odl_const.ODL_SGS: SecurityGroupODLFilter,
		odl_const.ODL_SG_RULES: SecurityGroupRuleODLFilter,
	}
	out_of_sync = False

	def __init__(self):
		LOG.debug("Initializing OpenDaylight Post Commit operation handler")
		self.client = _odl_client.OpenDaylightRestClient.create_client()
		self.queue = eventlet.Queue()
		self._odl_sync_timeout = cfg.CONF.ml2_odl.sync_timeout
		self._row_retry_count = cfg.CONF.ml2_odl.retry_count
		self.pool_size = cfg.CONF.ml2_odl.pool_size
		self.out_of_sync = cfg.CONF.ml2_odl.start_with_out_of_sync
		self.pool = eventlet.GreenPool(self.pool_size)
		self.event = threading.Event()
		self.lock = threading.Lock()
		self._odl_sync_thread = self.start_odl_sync_thread()
		self._start_sync_timer()

	def start_odl_sync_thread(self):
		# Start the sync thread
		LOG.debug("Starting a new odl sync thread")
		odl_sync_thread = threading.Thread(
			name='sync', target=self.run_sync_thread)
		odl_sync_thread.start()
		return odl_sync_thread

	def set_sync_event(self):
		# Prevent race when starting the timer
		with self.lock:
			LOG.debug("Resetting thread timer")
			self._timer.cancel()
			self._start_sync_timer()
		self.event.set()

	def put_postcommit_event_in_queue(self, opertion, object_type, id, resource, plugin, plugin_context):
		_size_check = self._check_poolsize_queuesize()
		if _size_check:
			self.queue.put((opertion, object_type, id,
							resource, plugin, plugin_context))

	def put_port_postcommit_event_in_queue(self, opertion, object_type, id, resource,
										   plugin, plugin_context, groups, tenant_id):
		_size_check = self._check_poolsize_queuesize()
		if _size_check:
			self.queue.put((opertion, object_type, id, resource,
							plugin, plugin_context, groups, tenant_id))

	def put_sync_callback_event_in_queue(self, operation, object_type, res_id, resource_dict, rules_ids):
		_size_check = self._check_poolsize_queuesize()
		if _size_check:
			self.queue.put((operation, object_type, res_id,
							resource_dict, rules_ids))

	def _check_poolsize_queuesize(self):
		size_check = True
		if self.pool_size < self.queue.qsize():
			LOG.error(
				"Post commit events in queue are more then configured pool size.")
			error_message = "503 Service Unavailable due to queue size exceeded"
			size_check = False
			raise nlib_ex.ServiceUnavailable(error_message=error_message)
		return size_check

	def _start_sync_timer(self):
		LOG.debug("start sync thread timer")
		self._timer = threading.Timer(self._odl_sync_timeout,
									  self.set_sync_event)
		self._timer.start()

	def run_sync_thread(self, exit_after_run=False):
		while True:
			try:
				self.event.wait()
				LOG.debug("In the  sync thread")
				self.event.clear()
				self._sync_entries(exit_after_run)
				LOG.debug("Clearing sync thread event")
				if exit_after_run:
					# Permanently waiting thread model breaks unit tests
					# Adding this arg to exit here only for unit tests
					break
			except Exception:
				# Catch exceptions to protect the thread while running
				LOG.exception(_LE("Error on run_sync_thread"))

	def _sync_entries(self, exit_after_run):
		while not self.queue.empty():
			free = self.pool.free()
			if free > 0:
				postCommit = self.queue.get()
				if postCommit:
					LOG.debug(
						"Start processing post commit entries %i" % (free))
					object_type = postCommit[odl_const.RESOURCE_TYPE]
					if object_type == odl_const.ODL_NETWORKS or object_type == odl_const.ODL_SUBNETS \
							or object_type == odl_const.ODL_PORTS:
						self.pool.spawn(self.synchronize, postCommit)
					else:
						self.pool.spawn(self.sync_from_callback, postCommit)
					LOG.debug("Finished post commit sync entries")
				else:
					LOG.error(" Error in fetching post commit sync entries")
			if exit_after_run:
				break

	def synchronize(self, postCommitData):
		"""Synchronize ODL with Neutron following a configuration change."""
		if self.out_of_sync:
			operation = postCommitData[odl_const.OPERATION]
			object_type = postCommitData[odl_const.RESOURCE_TYPE]
			obj_id = postCommitData[odl_const.OBJ_ID]
			object_type_url = object_type.replace('_', '-')
			method = operation
			url = object_type_url
			if operation == odl_const.ODL_DELETE:
				method = 'DELETE'
				url = object_type_url + '/' + obj_id
			elif operation == odl_const.ODL_CREATE:
				method = 'POST'
				url = object_type_url
			elif operation == odl_const.ODL_UPDATE:
				method = 'PUT'
				url = object_type_url + '/' + obj_id
			LOG.warning(_LW("Already Out of sync with ODL, failed to send"
							" %(method)s on %(url)s"
							" in thread %(tid)s"),
						{'method': method, 'url': url,
						 'tid': thread.get_ident()})
			_plugin = postCommitData[odl_const.PLUGIN]
			_plugin_context = postCommitData[odl_const.DBCONTEXT]
			LOG.debug('sync full called')
			self.sync_full(_plugin, _plugin_context)
		else:
			self.sync_single_resource(postCommitData)

	@utils.synchronized('odl-sync-full')
	def sync_full(self, plugin, _plugin_context):
		"""Resync the entire database to ODL.

		Transition to the in-sync state on success.
		Note: we only allow a single thread in here at a time.
		"""
		if not self.out_of_sync:
			return
		dbcontext = neutron_context.get_admin_context()
		for collection_name in [odl_const.ODL_SGS,
								odl_const.ODL_SG_RULES,
								odl_const.ODL_NETWORKS,
								odl_const.ODL_SUBNETS,
								odl_const.ODL_PORTS]:
			self.sync_resources(plugin, _plugin_context,
								dbcontext, collection_name)
		self.out_of_sync = False
		LOG.warning(_LW("Exited Out of sync with ODL in thread %(tid)s"),
					{'tid': thread.get_ident()})

	def sync_resources(self, plugin, _plugin_context, dbcontext, collection_name):
		"""Sync objects from Neutron over to OpenDaylight.

		This will handle syncing networks, subnets, and ports from Neutron to
		OpenDaylight. It also filters out the requisite items which are not
		valid for create API operations.
		"""
		filter_cls = self.FILTER_MAP[collection_name]
		to_be_synced = []
		obj_getter = getattr(plugin, 'get_%s' % collection_name)
		if collection_name == odl_const.ODL_SGS:
			resources = obj_getter(dbcontext, default_sg=True)
		else:
			resources = obj_getter(dbcontext)
		LOG.debug('sync full Resource : %s(resources)', resources)
		for resource in resources:
			try:
				# Convert underscores to dashes in the URL for ODL
				collection_name_url = collection_name.replace('_', '-')
				urlpath = collection_name_url + '/' + resource['id']
				LOG.debug('sync full urlpath : %s(urlpath)', urlpath)
				self.client.sendjson('get', urlpath, None)
			except requests.exceptions.HTTPError as e:
				with excutils.save_and_reraise_exception() as ctx:
					if e.response.status_code == requests.codes.not_found:
						filter_cls.filter_create_attributes_with_plugin(
							resource)
						# add security group if resource is port
						self._add_security_groups_with_plugin(
							resource, plugin, _plugin_context, collection_name)
						# add tenant id if resource is port and operation is CREATE
						self._add_tenant_in_port_with_plugin(
							resource, plugin, dbcontext, collection_name)
						LOG.debug('sync full added : %s(resource)', resource)
						to_be_synced.append(resource)
						ctx.reraise = False
			else:
				# TODO(yamahata): compare result with resource.
				# If they don't match, update it below
				pass

		if to_be_synced:
			key = collection_name[:-1] if len(to_be_synced) == 1 else (
				collection_name)
			# Convert underscores to dashes in the URL for ODL
			collection_name_url = collection_name.replace('_', '-')
			self.client.sendjson('post', collection_name_url,
								 {key: to_be_synced})

		# https://bugs.launchpad.net/networking-odl/+bug/1371115
		# TODO(yamahata): update resources with unsyned attributes
		# TODO(yamahata): find dangling ODL resouce that was deleted in
		# neutron db

	def sync_single_resource(self, postCommitData):
		"""Sync over a single resource from Neutron to OpenDaylight.

		Handle syncing a single operation over to OpenDaylight, and correctly
		filter attributes out which are not required for the requisite
		operation (create or update) being handled.
		"""
		# Convert underscores to dashes in the URL for ODL
		operation = postCommitData[odl_const.OPERATION]
		object_type = postCommitData[odl_const.RESOURCE_TYPE]
		obj_id = postCommitData[odl_const.OBJ_ID]
		resource = postCommitData[odl_const.RESOURCE]
		object_type_url = object_type.replace('_', '-')
		try:
			if operation == odl_const.ODL_DELETE:
				old_out_of_sync = self.out_of_sync
				self.out_of_sync |= not self.client.try_delete(
					object_type_url + '/' + obj_id)
				if self.out_of_sync and not old_out_of_sync:
					delete_url = object_type_url + '/' + obj_id
					LOG.warning(_LW("Entering Out of sync with ODL, failed to"
									" send %(method)s on %(url)s"
									" in thread %(tid)s"),
								{'method': 'DELETE', 'url': delete_url,
								 'tid': thread.get_ident()})
			else:
				filter_cls = self.FILTER_MAP[object_type]
				if operation == odl_const.ODL_CREATE:
					urlpath = object_type_url
					method = 'post'
					attr_filter = filter_cls.filter_create_attributes
				elif operation == odl_const.ODL_UPDATE:
					urlpath = object_type_url + '/' + obj_id
					method = 'put'
					attr_filter = filter_cls.filter_update_attributes
				attr_filter(resource)
				# add security group if resource is port
				self._add_security_groups(resource, postCommitData)
				# add tenant id if resource is port and operation is CREATE
				self._add_tenant_in_port(resource, postCommitData)
				self.client.sendjson(method, urlpath,
									 {object_type_url[:-1]: resource})
		except Exception:
			if operation == odl_const.ODL_CREATE and object_type == odl_const.ODL_PORTS:
				with excutils.save_and_reraise_exception() as ctx:
					port = resource
					if port.get('device_owner') in (
							l3_constants.DEVICE_OWNER_ROUTER_INTF,
							l3_constants.DEVICE_OWNER_ROUTER_GW,
							l3_constants.DEVICE_OWNER_DHCP):
						LOG.error(_LE("ODL: Silence error for port create: %(id)s"
									  " with device_owner: %(owner)s,"
									  " device_id: %(device_id)s"),
								  {'id': port['id'],
								   'owner': port.get('device_owner'),
								   'device_id': port.get('device_id')})
						ctx.reraise = False
					self.out_of_sync = True
					LOG.warning(_LW("Entering Out of sync with ODL on single"
									" resource in thread %(tid)s"),
								{'tid': thread.get_ident()})
			else:
				with excutils.save_and_reraise_exception():
					LOG.error(_LE("Unable to perform %(operation)s on "
								  "%(object_type)s %(object_id)s"),
							  {'operation': operation,
							   'object_type': object_type,
							   'object_id': obj_id})
					self.out_of_sync = True
					LOG.warning(_LW("Entering Out of sync with ODL on single"
									" resource in thread %(tid)s"),
								{'tid': thread.get_ident()})

	def _add_security_groups(self, port, postCommit):
		if postCommit[odl_const.RESOURCE_TYPE] == odl_const.ODL_PORTS:
			groups = postCommit[odl_const.SG_GROUPS]
			port['security_groups'] = groups

	def _add_tenant_in_port(self, port, postCommit):
		# NOTE(yamahata): work around for port creation for router
		# tenant_id=''(empty string) is passed when port is created
		# by l3 plugin internally for router.
		# On the other hand, ODL doesn't accept empty string for tenant_id.
		# In that case, deduce tenant_id from network_id for now.
		# Right fix: modify Neutron so that don't allow empty string
		# for tenant_id even for port for internal use.
		# TODO(yamahata): eliminate this work around when neutron side
		# is fixed
		# assert port['tenant_id'] != ''
		if postCommit[odl_const.RESOURCE_TYPE] == odl_const.ODL_PORTS \
				and postCommit[odl_const.OPERATION] == 'create' and port['tenant_id'] == '':
			LOG.debug('empty string was passed for tenant_id: %s(port)', port)
			port['tenant_id'] = postCommit[odl_const.TENANT_ID]

	def _add_security_groups_with_plugin(self, resource, plugin, plugin_context, type):
		if type == odl_const.ODL_PORTS:
			"""Populate the 'security_groups' field with entire records."""
			groups = [plugin.get_security_group(plugin_context, sg)
					  for sg in resource['security_groups']]
			resource['security_groups'] = groups

	def _add_tenant_in_port_with_plugin(self, resource, plugin, dbcontext, type):
		if type == odl_const.ODL_PORTS:
			if resource['tenant_id'] == '':
				LOG.debug(
					'empty string was passed for tenant_id: %s(port)', resource)
				network = plugin.get_network(dbcontext, resource['network_id'])
				if 'tenant_id' in network:
					resource['tenant_id'] = network['tenant_id']

	def sync_from_callback(self, postCommit):
		try:
			object_type = postCommit[odl_const.RESOURCE_TYPE]
			operation = postCommit[odl_const.OPERATION]
			res_id = postCommit[odl_const.OBJ_ID]
			resource_dict = postCommit[odl_const.RESOURCE_MAP]
			object_type_url = object_type.replace('-', '_')
			if operation == odl_const.ODL_DELETE:
				if (object_type_url == odl_const.ODL_SGS and
						operation == odl_const.ODL_DELETE):
					sg_rule_ids = postCommit[odl_const.SG_RULES_ID]
					for rule_id in sg_rule_ids:
						try:
							self.client.try_delete(
								odl_const.ODL_SG_RULES.replace('_', '-') +
								'/' + rule_id)
						except Exception:
							LOG.error('Failed to delete security group rule %s'
									  'for group %s' % (rule_id, res_id))
				old_out_of_sync = self.out_of_sync
				self.out_of_sync |= not self.client.try_delete(
					object_type + '/' + res_id)
				if self.out_of_sync and not old_out_of_sync:
					delete_url = object_type + '/' + res_id
					LOG.warning(_LW("Entering Out of sync with ODL on callback"
									", failed to send %(method)s on %(url)s"
									" in thread %(tid)s"),
								{'method': 'DELETE', 'url': delete_url,
								 'tid': thread.get_ident()})
			else:
				filter_cls = self.FILTER_MAP[object_type_url]
				if operation == odl_const.ODL_CREATE:
					urlpath = object_type
					method = 'post'
					attr_filter = filter_cls.filter_create_attributes
				elif operation == odl_const.ODL_UPDATE:
					urlpath = object_type + '/' + res_id
					method = 'put'
					attr_filter = filter_cls.filter_update_attributes
				if object_type_url == odl_const.ODL_SG_RULES:
					resource = resource_dict.get(odl_const.ODL_SG_RULE)
					attr_filter(resource)
					self.client.sendjson(method, urlpath,
										 {object_type_url[:-1]: resource})
					return
				self.client.sendjson(method, urlpath, resource_dict)
		except Exception:
			with excutils.save_and_reraise_exception():
				LOG.error(_LE("Unable to perform %(operation)s on "
							  "%(object_type)s %(res_id)s %(resource_dict)s"),
						  {'operation': operation,
						   'object_type': object_type,
						   'res_id': res_id,
						   'resource_dict': resource_dict})
				self.out_of_sync = True
				LOG.warning(_LW("Entering Out of sync with ODL on callback"
								" in thread %(tid)s"),
							{'tid': thread.get_ident()})
