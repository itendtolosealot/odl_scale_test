
'''
from Frontend import maxinet
from tools import FatTree
from Mininet.mininet.node import OVSSwitch
from Mininet.mininet import topo
from Mininet.mininet import node
'''

import time
import json
import ast
import threading
import logging
import gevent, gevent.server
from telnetsrv.green import TelnetHandler, command
import uuid
import dockernet
import socket
import random
from multiprocessing import Queue
import plyvel
import ipaddress
import sys
import math
from prettytable import PrettyTable
from kafka import KafkaConsumer
from UI.webui import WebUIForSimulator
import argparse
from oslo_config import cfg

NEUTRONHANDLERPOINTER = None
DEFAULT_MTU = 1450
MAX_VIRTUAL_COMPUTES=150
MAX_MIPS_PER_SUBNET=10

class Console(TelnetHandler):
    WELCOME = "Welcome to Maxinet CLI. This software belongs to ERICSSON. If you have accidentally accessed this portal, exit immediately"
    PROMPT = "Maxinet> "
    authNeedUser=False
    authNeedPassword=False

    def _validate_uuid(self, uid):
        try:
            val = uuid.UUID(uid, version=4)
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
        Display Network Info. It will return an error, if no such network is found.
        '''
        self._callback_handler = NEUTRONHANDLERPOINTER
        self.__process_telnet_command("network",params)

    @command('subnet')
    def command_subnet(self,params):
        '''<subnet_uuid/ 'all'>
        Display Subnet Info. It will return an error, if no such subnet is found.
        '''
        self._callback_handler = NEUTRONHANDLERPOINTER
        self.__process_telnet_command("subnet",params)

    @command('port')
    def command_port(self,params):
        '''<port_uuid/ 'all'>
        Display Port Info. It will return an error, if no such port is found.
        '''
        self._callback_handler = NEUTRONHANDLERPOINTER
        self.__process_telnet_command("port",params)

    @command('router')
    def command_router(self,params):
        '''<router_uuid/ 'all'>
        Display Router Info. It will return an error, if no such router is found.
        '''
        self._callback_handler = NEUTRONHANDLERPOINTER
        self.__process_telnet_command("router",params)



    @command('start_computes')
    def command_start_computes(self,params):
        '''controller_ip num_virtual_computes
        The command will require the controller_ip and the number of virtual computes to be started. Provide a valid IPv4 address for controller_ip in X.X.X.X notation.
        '''
        if (len(params)<2):
            self.writeerror("Incorrect number of arguments passed. Seek help")
            return
        try:
            socket.inet_aton(params[0])
        except socket.error:
            self.writeerror("Controller IP invalid")
            return
        if(int(params[1]) > MAX_VIRTUAL_COMPUTES or int(params[1])<=0):
            self.writeerror("Number of virtual computes must be between 1 and 150")
            return
        self._callback_handler=NEUTRONHANDLERPOINTER
        message = self._callback_handler.handle_switch_creation("start", params[0],int(params[1]))
        if(message != None):
            self.writeresponse(message)

    @command('start_elan_test')
    def command_start_elan_test(self, params):
        '''
        The command will start ping tests for every Elan configured periodically. New ELANs configured will be added to this test.
        '''
        self._callback_handler=NEUTRONHANDLERPOINTER
        message = self._callback_handler.handle_test("subnet","Start")
        if(message != None):
            self.writeresponse(message)

    @command('elan_test_status')
    def command_elan_test_status(self, params):
        '''
        The command will start ping tests for every Elan configured periodically. New ELANs configured will be added to this test.
        '''
        self._callback_handler=NEUTRONHANDLERPOINTER
        message = self._callback_handler.report_test_status("subnet")
        if(message != None):
            self.writeresponse(message)

    @command('stop_elan_test')
    def command_stop_elan_test(self,params):
        '''
        The command will stop ping tests for the Elan.
        '''
        self._callback_handler=NEUTRONHANDLERPOINTER
        message = self._callback_handler.handle_test("subnet", "Stop")
        if(message != None):
            self.writeresponse(message)

    @command('start_router_test')
    def command_start_router_test(self, params):
        '''
        The command will start ping tests for every Elan configured periodically. New ELANs configured will be added to this test.
        '''
        self._callback_handler=NEUTRONHANDLERPOINTER
        message = self._callback_handler.handle_test("router","Start")
        if(message != None):
            self.writeresponse(message)

    @command('router_test_status')
    def command_router_test_status(self, params):
        '''
        The command will start ping tests for every Elan configured periodically. New ELANs configured will be added to this test.
        '''
        self._callback_handler=NEUTRONHANDLERPOINTER
        message = self._callback_handler.report_test_status("router")
        if(message != None):
            self.writeresponse(message)

    @command('stop_router_test')
    def command_stop_router_test(self,params):
        '''
        The command will stop ping tests for the Elan.
        '''
        self._callback_handler=NEUTRONHANDLERPOINTER
        message = self._callback_handler.handle_test("router","Stop")
        if(message != None):
            self.writeresponse(message)


    @command('stop_computes')
    def command_stop_computes(self, params):
        '''
        The command will stop all virtual computes and delete Neutron ports.
        '''
        self._callback_handler=NEUTRONHANDLERPOINTER
        message = self._callback_handler.handle_switch_creation("stop")
        if(message != None):
            self.writeresponse(message)

    @command('reset_computes')
    def command_reset_computes(self,params):
        '''
	   The command will reset the simulator and all the DBs. It will destroy all VMs
	   '''
        self._callback_handler=NEUTRONHANDLERPOINTER
        message = self._callback_handler.reset_simulation()
        if(message!= None):
            self.writeresponse(message)


    @command('get_compute_status')
    def command_get_compute_status(self, params):
        '''
        Provide status of all virtual computes
        '''
        self._callback_handler=NEUTRONHANDLERPOINTER
        message = self._callback_handler.compute_status()
        headers = ["Status of OF/OVSDB Connections"]
        table=PrettyTable(headers)
        try:
            for row in message:
                table.add_row(list([row]))
            self.writeresponse(str(table))
        except Exception as ex:
            self.writeresponse("Encountered Error during processing. See logs for details " + str(ex.message) + "\n Data: " + str(row))

    @command('get_port_status')
    def command_get_port_status(self, params):
        '''
        Provide Location/IP info for all ports
        '''
        self._callback_handler=NEUTRONHANDLERPOINTER
        message = self._callback_handler.get_neutronport_status()
        self.writeresponse(message)

    @command('create_mips')
    def command_create_mip(self, params):
        ''' subnet_UUID number_of_mips_per_subnet
        The command creates a number of MIPs in the subnet and assigns it to a collection of random Neutron Ports in that Subnet. The first parameter must be either "all"
        or must be a valid subnet UUID. If the first parameter is "all", then the MIPs would be created for all subnets configured.
        '''
        if(len(params) != 2):
            self.writeerror("Incorrect number of parameters passed. Seek help")
        else:
            self._callback_handler=NEUTRONHANDLERPOINTER
            subnet = params[0]
            if (not self._validate_uuid(subnet) and subnet != "all"):
                self.writeerror("Invalid subnet UUID")
            else:
                try:
                    num_mip = int(params[1])
                except ValueError:
                    self.writeerror("Number of MIPs is not an Integer")
                if (num_mip <= 0 or num_mip >MAX_MIPS_PER_SUBNET):
                    self.writeerror("The number of MIPs is outside the supported range. Choose a value between 1 and " + str(MAX_MIPS_PER_SUBNET))
                else:
                    message = self._callback_handler.handle_mip_creation(subnet, num_mip)
                    if(message != None):
                        self.writeresponse(message)

    @command('get_mip_status')
    def command_get_mip_status(self, params):
        ''' subnet_UUID
        The command deletes the MIPs configured in a Subnet with a given uuid. If keyword 'all' is used, then all MIPs would be unconfigured
        '''
        if(len(params)!= 1):
            self.writeerror("Incorrect number of parameters passed. Seek help")
        else:
            subnet = params[0]
            if (not self._validate_uuid(subnet) and subnet != "all"):
                self.writeerror("Invalid subnet UUID")
            else:
                self._callback_handler=NEUTRONHANDLERPOINTER
                message = self._callback_handler.get_mip_status(subnet)
                if (message!= None):
                    self.writeresponse(message)

    @command('delete_mips')
    def command_delete_mip(self, params):
        ''' subnet_UUID
        The command deletes the MIPs configured in a Subnet with a given uuid. If keyword 'all' is used, then all MIPs would be unconfigured
        '''
        if(len(params)!= 1):
            self.writeerror("Incorrect number of parameters passed. Seek help")
        else:
            self._callback_handler=NEUTRONHANDLERPOINTER
            subnet = params[0]
            if (not self._validate_uuid(subnet) and subnet != "all"):
                self.writeerror("Invalid subnet UUID")
            else:
                message = self._callback_handler.handle_mip_deletion(subnet)
                if(message != None):
                    self.writeresponse(message)

    @command("ovs_list")
    def command_ovs_list(self,params):
        ''' None
        The command returns the list of virtual computes that the simulator thinks are running. This is a troubleshooting command
        '''
        self._callback_handler=NEUTRONHANDLERPOINTER
        message = self._callback_handler.list_of_ovs()
        if(message != None):
            self.writeresponse(message)
        else:
            self.writeerror("Encountered Error while executing the command.")

    @command('clean')
    def command_clean(self,params):
        '''<resource/ 'all'> <uuid/'all'>
        Delete a resource. Used when Openstack and the KPI test-bed are out-of-sync.
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


class NeutronEventHandler(dockernet.DataBaseRestore):
    def __init__(self, file_location="/home/stack/mininet_handler/config.ini"):
        self._file_location=file_location
        self.read_config(file_location)
        self._initialize(file_location)

    def read_config(self, file_location):
        try:
            grp = cfg.OptGroup('testbed_properties')
            opts = [cfg.StrOpt("log_file", default="/home/stack/mininet_handler/mininet_handler.log"),
                    cfg.StrOpt("db_loc", default=" '/home/stack/mininet_handler/db/"),
                    cfg.IntOpt("queue_timeout", default=4),
                    cfg.IntOpt("elan_timer_interval", default=20),
                    cfg.IntOpt("router_timer_interval", default=20),
                    cfg.IntOpt("mip_timer_interval", default=20),
                    cfg.StrOpt("kafka_brokers", default="localhost:9092"),
                    cfg.IntOpt("telnet_port", default=55555),
                    cfg.IntOpt("num_computes", default=10 ),
                    cfg.StrOpt("controller_ip", default="localhost"),
                    cfg.BoolOpt("use_partitions", default=False)]
            cfg.CONF.register_group(grp)
            cfg.CONF.register_opts(opts, group=grp)
            file_location= ['--config-file', str(file_location)]
            print("Config file: " + str(file_location))
            cfg.CONF(file_location)
        except Exception as ex:
            print("Error in processing configuration file. Exitting the program")
            print("Exception:" + str(ex.message))
            sys.exit(1)
        self._log_file = cfg.CONF.testbed_properties.log_file
        self._db_loc = cfg.CONF.testbed_properties.db_loc
        self._queue_timeout = cfg.CONF.testbed_properties.queue_timeout
        self._elan_timer_interval = cfg.CONF.testbed_properties.elan_timer_interval
        self._router_timer_interval=cfg.CONF.testbed_properties.router_timer_interval
        self._mip_timer_interval=cfg.CONF.testbed_properties.mip_timer_interval
        self.kafka_brokers = cfg.CONF.testbed_properties.kafka_brokers
        self._telnet_port = cfg.CONF.testbed_properties.telnet_port
        self._controller_ip = cfg.CONF.testbed_properties.controller_ip
        self._num_virtual_computes = cfg.CONF.testbed_properties.num_computes
        self._use_partitions = cfg.CONF.testbed_properties.use_partitions
        #self._log_handler.info("Controller IP: " + str(self._controller_ip) + " Number of Computes: " + str(self._num_virtual_computes))

    def _initialize(self, file_location):
        self._mininet_data = dict()
        self._locks = dict()
        #self.webui = WebUIForSimulator(self)
        self._databases = list(['network', 'subnet', 'port', 'router', 'subnet_port_map', 'dhcp_server', 'port_to_ip_mapping', 'gateway_ip', 'subnet_mips', 'ip_to_port_mapping', 'subnet_to_router_map', 'elan_test_data', 'router_test_data'])
        for key in self._databases:
            self._mininet_data[key] = dict()
            self._locks[key] = threading.Lock()
        self._SIMULATION_STARTED=False
        self._setup_logger("Simulator", self._log_file, level=logging.DEBUG)
        self._log_handler = logging.getLogger("Simulator")
        self._tests_enabled = dict()
        global NEUTRONHANDLERPOINTER
        NEUTRONHANDLERPOINTER= self
        self._dockernet= dockernet.DockerHandler(file_location)
        self.restore_from_db()
        self._console = Console
        self._telnet_handler= threading.Thread(target=self._create_telnet_channel, args=(3,))
        #self._webui_handler = threading.Thread(target=self.start_web_ui, args=("192.168.56.101", 8000))
        self._telnet_handler.daemon=True
        #self._webui_handler.daemon=True
        self._tests_enabled["subnet"] = False
        self._tests_enabled["router"] = False
        self._mip_enabled = False
        self._num_of_mips = 0
        self._elan_test_timers = dict()
        self._router_test_timers=dict()
        self._mip_test_timers = dict()
        self._telnet_handler.start()
        #self._webui_handler.start()
        self._topic = "neutron_events_for_simulation"
        self.handle_switch_creation("start", controller_ip=self._controller_ip, num_switches=self._num_virtual_computes)
        self._partition_id = self._dockernet.get_partition_id()

    def list_of_ovs(self):
        return (self._dockernet.get_list_of_computes())

    '''def start_web_ui(self, hostname, port):
        self._log_handler.info("Starting WebUI")
        try:
            self.webui.run(hostname, port)
        except KeyboardInterrupt:
            self._log_handler.warning("Encountered Keyboard Interrupt. Terminating the WebUI")
        except Exception as ex:
            self._log_handler.error("Encountered exception: " + str(ex.message))'''

    def does_port_belong_to_my_partition(self, port):
        if(self._use_partitions==False):
            return True
        elif(self._partition_id == port['name'][0:10]):
            return True
        else:
            return False

    def get_neutronport_status(self):
        def get_data_in_list_form(headers, data):
            result=list()
            self._log_handler.debug("Received data: " + str(data) + "Type: " + str(type(data)))
            index = 0
            for key in headers:
                if(key in data):
                    self._log_handler.debug("Key: " + str(key) + "Value: " + str(data[key]))
                    result.append(str(data[key]))
                else:
                    result.append(" ")
                index=index+1
            return result

        port_status  = self._dockernet.get_port_info()
        self._log_handler.debug("Obtained port stats: " + str(port_status))
        if (len(port_status.keys())==0):
            return "No ports are configured. "
        else:
            Headers = ["Port UUID", "location", "ip_v4", "subnet_v4", "ip_v6", "subnet_v6"]
            message = PrettyTable(Headers)
            for uuid in port_status.keys():
                data = ast.literal_eval(str(port_status[uuid]))
                data['Port UUID']= uuid
                row = get_data_in_list_form(Headers, data)
                message.add_row(row)
        return str(message)

    def configure_resource(self,res):
        _HANDLERS = {
            'network': self._handle_network_event,
            'subnet': self._handle_subnet_event,
            'router':self._handle_router_event,
            'port':self._handle_port_event
        }
        if isinstance(res,dict):
            if ('event' in res) and ('resource' in res):
                self._log_handler.debug("Received event: " + str(res['event']) + " for resource: " + str(res['resource']))
                event = res['event']
                del res['event']
                resource = res['resource']
                del res['resource']
                try:
                    result = _HANDLERS[resource](event,**res)
                    return result
                except KeyError:
                    self._log_handler.warning("Event received for an unknown resource: " + str(resource) + ". Ignoring")
                    return False
                except Exception as ex:
                    self._log_handler.error("Obtained error when trying to process event: " + str(event) + "for resource type: " + str(resource))
                    self._log_handler.error("Exception: " + str(ex.message))
                    return False
            else:
                self._log_handler.warning("Received configuration with no event or resource:" + str(res) + ". Ignoring the config")
                return False
        else:
            self._log_handler.error("Error! Expecting JSON dict. However obtained resource of type: "  + str(type(res)))
            return False

    def _create_telnet_channel(self, val):
        self._log_handler.info("Telnet server started")
        self._telnet_server =gevent.server.StreamServer(('127.0.0.1', self._telnet_port), self._console.streamserver_handle)
        try:
            self._telnet_server.serve_forever()
        except KeyboardInterrupt:
            self._telnet_server.stop(timeout=val)
            pass
        except Exception as ex:
            self._log_handler.error("Exception: " + str(ex.message))
        self._log_handler.info("Thread was terminated. Exiting the program")
        return

    def get_current_configuration(self):
        try:
            db_list = ['network', 'subnet', 'port', 'router', 'subnet_mips']
            config = dict()
            config["Simulation Running"] = self._SIMULATION_STARTED
            config["Virtual Computes"] = self._num_virtual_computes
            for key in db_list:
                config["Configured " + str(key).title()] = len(self._mininet_data[key].keys())
        except Exception as ex:
            self._log_handler.error("Received exception :" + str(ex.message))
        return config

    def compute_status(self):
        self._log_handler.debug("Received command for status")
        try:
            message = self._dockernet.status()
        except Exception as ex:
            self._log_handler.error("Unable to obtain the status: Got exception: " + str(ex.message))
            message = "Encountered error during process. See logs for details."
        self._log_handler.debug("Returning message: " + str(message))
        return message

    def reset_simulation(self):
        self._dockernet.reset()
        for key in self._databases:
            self._mininet_data[key] = dict()
        self._tests_enabled["subnet"] = False
        self._tests_enabled["router"] = False
        self._mip_enabled = False
        self._num_of_mips = 0
        self._num_virtual_computes = 0
        self._elan_test_timers = dict()
        self._router_test_timers=dict()
        self._mip_test_timers = dict()
        self._SIMULATION_STARTED=False

    def _get_total_ips_available(self, sub_info, cidr):
        _version_dict = {
            "4" : 32,
            "6" : 128
        }
        mask = int(str(cidr).split('/')[1])
        ''' We subtract 2, assuming 1 IP would be used by GW and 1 IP by DHCP server '''
        total_ips_available = int(math.pow(2,_version_dict[str(sub_info['ip_version'])]-mask))-2
        return total_ips_available

    def _check_mip_configuration_possible(self, num_of_mips, uuid):
        def _check_mip_configuration_for_subnet(sub_uuid):
            message = ""
            (result, sub_info) = self._get_data("subnet", sub_uuid)
            if (not result):
                message = "Unable to find the Subnet"
                return message
            cidr = sub_info['cidr']
            total_ips_available = self._get_total_ips_available(sub_info,cidr)
            actual_ips = len(self._get_data("subnet_port_map", sub_uuid)[1])
            if(actual_ips==0):
                message = " For subnet: " + str(sub_uuid) + " no Neutron ports are configured. MIP configuration is not possible\n"
            elif (actual_ips + num_of_mips > total_ips_available):
                message = " In subnet: " + str(sub_uuid) + " only " + str(total_ips_available) + " are available and "  + \
                          str(actual_ips) + " are already used. It is not possible to configure additional " + \
                          str(num_of_mips) + " MIPs\n"
            return message

        message = ""
        if (uuid=="all"):
            for sub_uuid in self._mininet_data['subnet'].keys():
                message += _check_mip_configuration_for_subnet(sub_uuid)
        else:
            message += _check_mip_configuration_for_subnet(uuid)
        if (len(message) > 1):
            return (False, message)
        else:
            return (True, "")

    ''' Big Assumption: Prefix Lengths are multiples of 16 for IPv6'''

    def get_prefix_for_ipv6(self,cidr):
        cidr_split = cidr.split("/")
        prefix_length = int(cidr_split[1])
        if (prefix_length % 16 != 0):
            self._log_handler.error("CIDR: " + str(cidr) + " has a prefix length that is not a multiple of 16.")
            return (False, None, None)
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
                mip = prefix + ":".join(mip_ip_eui)
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
                self._log_handler.debug("MIP list: " + str(mip_list))
                return (True, mip_list)
            else:
                self._log_handler.error("Exhausted all IPs while testing for MIP creation. ")
                return (False, mip_list)
        if (ip_version == "4"):
            return get_ipv4_mip()
        elif (ip_version=="6"):
            return get_ipv6_mip()
        else:
            self._log_handler.error("Unknown IP Version")
            return (False, list())

    def handle_mip_creation_for_subnet(self, sub_uuid, num_of_mips):
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
            ip_addr_list = list(ip_addr_list)
            self._log_handler.debug("IP addr list: " + str(ip_addr_list))
            (result, gateway_ip) = self._get_data("gateway_ip", sub_uuid)
            if(result):
                ip_addr_list.append(gateway_ip)
            (result, dhcp_server) = self._get_data("dhcp_server", sub_uuid)
            if(result):
                ip_addr_list.append(dhcp_server)
        else:
            print("Unable to get any data for subnet: " + str(sub_uuid))
            self._log_handler.warning("Unable to get any data for subnet: " + str(sub_uuid))
            return False
        self._mininet_data["subnet_mips"][sub_uuid] = list()
        prefix_info = _ip_version_dict[str(sub_info["ip_version"])](cidr)
        if(not prefix_info[0]):
            self._log_handler.warning("Unable to create MIPs for Subnet: " + str(sub_uuid))
            return False
        prefix = prefix_info[1]
        prefix_length = prefix_info[2]
        (result, mip_list) = self.get_mip_list(prefix,prefix_length,str(sub_info["ip_version"]), ip_addr_list, num_of_mips)
        if (result):
            for mip in mip_list:
                self._log_handler.debug("For subnet: " + str(sub_uuid) + " with IP version: " + str(sub_info["ip_version"]) + " obtained MIP: " + str(mip))
            self._store_data("subnet_mips", sub_uuid, mip_list)
        else:
            self._log_handler.error("Unable to process MIP creation. Exiting...")
        return result

    def configure_mip_on_neutron_ports(self, sub_uuid):
        (result, port_uuid_ip_list) = self._get_data("subnet_port_map", sub_uuid)
        (port_uuid_list, ip_addr_list) = list(zip(*port_uuid_ip_list))
        (result, mip_list) = self._get_data("subnet_mips", sub_uuid)
        (result, subnet) = self._get_data("subnet", sub_uuid)
        prefix_length = subnet["cidr"].split("/")[1]
        result = self._dockernet.configure_mips(sub_uuid, port_uuid_list, mip_list, prefix_length)
        return result

    def get_mip_status(self, uuid):
        headers = ["Subnet UUID", " MIP address", " Port UUID", " Compute", " VM Name"]
        message = PrettyTable(headers)
        if (uuid == "all"):
            for subnet in self._mininet_data["subnet_mips"].keys():
                data = self._dockernet.get_mip_status(subnet, self._get_data("subnet_mips",subnet)[1])
                for row in data:
                    message.add_row(row)
        else:
            try:
                data = self._dockernet.get_mip_status(uuid, self._get_data("subnet_mips",uuid)[1])
                for row in data:
                    message.add_row(row)
            except KeyError:
                return "Error! Subnet: " + uuid + " is not known."
        return str(message)

    def _check_result_and_configure_mip(self, result, uuid):
        if(result):
            self._log_handler.debug("Starting MIP configuration")
            return self.configure_mip_on_neutron_ports(uuid)
        else:
            self._log_handler.warning("Unable to configure MIPs for subnet: " + str(uuid))

    def handle_mip_creation(self, uuid, num_of_mips):
        (possibility,message) = self._check_mip_configuration_possible(num_of_mips, uuid)
        if (not possibility):
            return ("Error. " + message + " \n No MIPs are configured")
        else:
            self._mip_enabled=True
            self._num_of_mips= num_of_mips
            self._log_handler.debug("Valid number of MIPs received")
        all_subnets_configured = True
        if (uuid != "all"):
            result_A = self.handle_mip_creation_for_subnet(uuid, num_of_mips)
            all_subnets_configured = result_A
            result_B = self._check_result_and_configure_mip(result_A, uuid)
            all_subnets_configured = all_subnets_configured and result_B
        else:
            for sub_uuid in self._mininet_data['subnet'].keys():
                result_A = self.handle_mip_creation_for_subnet(sub_uuid, num_of_mips)
                result_B = self._check_result_and_configure_mip(result_A, sub_uuid)
                all_subnets_configured = all_subnets_configured and (result_A and result_B)
        if (all_subnets_configured):
            return "MIP creation for " + str(uuid) + " subnet(s) completed succesfully"
        else:
            return "MIP creation for " + str(uuid) + " subnet(s) failed. Check logs for details"
        return all_subnets_configured

    def handle_mip_deletion(self, sub_uuid):
        def mip_deletion_for_subnet(subnet):
            (result,data) = self._get_data("subnet", subnet)
            if (not result):
                self._log_handler.warning("The subnet" + subnet + " was not found. Ignoring the event")
                return "The subnet " + subnet + " was not found. Ignoring the event"
            (result, mip_list) = self._delete_data("subnet_mips", subnet)
            if(not result):
                self._log_handler.warning("No Mips found for subnet" + subnet + " was not found. Ignoring the event")
                return "No Mips found for subnet"  + subnet + ". Ignoring the event"
            prefix_length = data["cidr"].split("/")[1]
            if len(mip_list)==0:
                self._log_handler.warning("Subnet " + subnet + " is configured with zero MIPs. Ignoring")
                return "Subnet " + subnet + " is configured with zero MIPs. Ignoring"
            self._log_handler.debug("Attempting to delete MIPs: " + str(mip_list) + " for subnet: " + str(subnet))
            result = self._dockernet.unconfigure_mips(subnet, mip_list, prefix_length)
            if (result):
                message = "MIP deletion for subnet: " + sub_uuid + " successful \n"
                self._log_handler.debug("MIPs: " + str(mip_list) + " for subnet: " + str(subnet) + " deleted")
            else:
                message = "MIP deletion for subnet: " + sub_uuid + " failed \n"
                self._log_handler.debug("MIPs: " + str(mip_list) + " for subnet: " + str(subnet) + " not deleted")
            return message
        self._mip_enabled=False
        self._num_of_mips=0
        message = ""
        self._log_handler.debug("MIP deletion command received")
        if (sub_uuid=="all"):
            for subnet in self._mininet_data["subnet_mips"].keys():
                message += mip_deletion_for_subnet(subnet)
        else:
            message = mip_deletion_for_subnet(sub_uuid)
        return message


    def handle_test(self, key, action):
        _type_dict={
            "subnet": [ "L2", "elan_test_data", self._elan_test_timers, self._elan_timer_interval, self._mininet_data['subnet']],
            "router": ["L3", "router_test_data", self._router_test_timers, self._router_timer_interval, self._mininet_data['router']]
        }
        message=""
        data = _type_dict[key]
        if (action == "Start"):
            self._tests_enabled[key] = True
            self._log_handler.debug("Enabled " + data[0] + " forwarding for all " + str(key)+ "s.")
            for item in data[4].keys():
                self._store_data(data[1], item, queue.Queue(5))
                jitter = (random.uniform(0,1) -0.5)*data[3]
                self._start_test_timers(key, item, jitter)
            message = data[0] + " forwarding test Started. Will test every " + str(key) + " once every " + str(data[3]) + " sec"
        elif(action == "Stop"):
            self._tests_enabled[key] = False
            self._log_handler.info("Disabled " + data[0] + " forwarding for all " + str(key)+ "s.")
            for item in data[2].keys():
                self._delete_data(data[1], item)
                self._log_handler.debug("Deleted data from DS _mininet[: \"" + data[1] + "\"]")
                data[2][item].cancel()
                self._log_handler.debug("Cancelled timer for " + str(key) + ": " + str(item))
                data[2].pop(item)
                self._log_handler.debug("Removed timer for " + str(key) + ": " + str(item))
            message = data[0] + " forwarding test Stopped for all " + str(key) + "s."
        else:
            self._log_handler.error("Unknown action. This results in no operation")
            message="Unknown action. This results in no operation"
        return message

    def _start_test_timers(self, resource, resource_id, jitter=0):
        if (self._tests_enabled[resource]):
            self._log_handler.debug("Starting timer for " + str(resource) + ": " + str(resource_id))
            _resource_dict={
                "subnet": [self._elan_test,self._elan_test_timers, self._elan_timer_interval],
                "router": [self._router_test, self._router_test_timers, self._router_timer_interval],
                "mip": [self._mip_test, self._mip_test_timers, self._mip_timer_interval]
            }
            test_resources = _resource_dict[resource]
            test_resources[1][resource_id] =threading.Timer(test_resources[2]+jitter, test_resources[0], args = (resource_id, ))
            test_resources[1][resource_id].daemon = True
            test_resources[1][resource_id].start()
        else:
            self._log_handler.info("The " + str(resource) + " test is disabled. Timer is NOT started for " + str(resource) + ": " + str(resource_id))

    def _do_test(self, resource, resource_id, port_list):
        (test_result, text) = self._dockernet.do_ping_test(resource, resource_id, port_list)
        test_pass = ""
        if(test_result):
            self._log_handler.info(" Test for " + str(resource) + ": " + str(resource_id) + " passed")
            test_pass = "PASS"
        else:
            self._log_handler.error("Test for " + str(resource) + ": " + str(resource_id) + " Failed")
            test_pass="FAIL"
            self._log_handler.error(text)
        return test_pass

    def _update_test_results(self, resource, resource_id, test_result ):
        (res, test_res_queue) = self._get_data(resource, resource_id)
        if(res):
            if (test_res_queue.full()):
                item = test_res_queue.get()
                self._log_handler.debug("Removing the earliest entry from the results queue")
            test_res_queue.put(test_result)
            self._log_handler.debug("Added the latest test case data: " + str(test_result))
            self._store_data(resource, resource_id, test_res_queue)

    def _router_test(self, router_id):
        self._router_test_timers[router_id].cancel()
        self._router_test_timers.pop(router_id)
        self._log_handler.info("Starting L3 test for Router:" + str(router_id))
        (result,data)=self._get_data("router", router_id)
        if (result):
            (subnet_list, extra_route_list)=data
            l3_domain = list()
            for subnet_id in subnet_list:
                (res,port_list) = self._get_data("subnet_port_map", subnet_id)
                if (res):
                    l3_domain += port_list
            if(len(l3_domain) > 0):
                self._log_handler.debug("In router: " + str(router_id) + " found ports: " + str(l3_domain))
                test_result = self._do_test("router", router_id, l3_domain)
                self._update_test_results("router_test_data", router_id, test_result)
            else:
                self._log_handler.warning("Router: " + str(router_id) + " has no ports. Retrying later...")
        else:
            self._log_handler.warning("Unknown router: " + str(router_id) + ". Unable to do tests")
            return
        self._start_test_timers("router",router_id)

    def _elan_test(self, subnet_id):
        self._elan_test_timers[subnet_id].cancel()
        self._elan_test_timers.pop(subnet_id)
        self._log_handler.info("Starting L2 test for subnet:" + str(subnet_id))
        (result, port_list) = self._get_data("subnet_port_map", subnet_id)
        if (result and len(port_list) > 0):
            self._log_handler.debug("In subnet: " + str(subnet_id) + " found ports: " + str(port_list))
            test_result = self._do_test("subnet",subnet_id,port_list)
            self._update_test_results("elan_test_data", subnet_id,test_result)
        else:
            self._log_handler.info("Subnet: " + str(subnet_id) + " has no ports. Retrying later." )
        if(self._tests_enabled["subnet"]):
            self._log_handler.debug(" L2 test for subnet: " + str(subnet_id) + " will begin in " + str(self._elan_timer_interval) + " seconds")
            self._start_test_timers("subnet", subnet_id)

    def report_test_status(self, resource):
        _res_dict = {
            "subnet": ["ELAN TEST STATUS", 'elan_test_data'],
            "router": ["ROUTER TEST STATUS", 'router_test_data']
        }
        try:
            data = _res_dict[resource]

            message  = "                                " + str(data[0])+ "\n"
            message += "=========================================================================================\n"
            if(not self._tests_enabled[resource]):
                message = "The tests are not enabled. Please enable " + str(resource) + " test by using start_" + str(resource).lower() + "_test command."
            elif (len(self._mininet_data[str(resource).lower()].keys()) == 0):
                message = "No " + str(resource) + "s are configured. "
            else:
                for resource_id in self._mininet_data[data[1]].keys():
                    (res, test_result) = self._get_data(data[1], resource_id)
                    if(res):
                        res_list = list(test_result.queue)
                        message = message + "\t\t" + str(resource_id) +" : " + str(res_list) + "\n"
                    else:
                        self._log_handler.error("Could not find latest test data for: " )
        except KeyError as kx:
            self._log_handler.error("Encountered KeyError when accessing test data: " + str(kx.message))
            message= "Encountered KeyError when accessing test data: " + str(kx.message)
        except Exception as kx:
            self._log_handler.error("Encountered exception when accessing test data: " + str(kx.message))
            message= "Encountered exception when accessing test data: " + str(kx.message)

        return message

    def _handle_cleanup(self,params):
        message = ""
        param_dict = {
            "network": [self._handle_network_event, "network_id"],
            "subnet": [self._handle_subnet_event, "subnet_id"],
            "port": [self._handle_port_event, "port_id"],
            "router": [self._handle_router_event, "router_id"],
        }
        if (len(params)==2):
            try:
                self._locks[params[0]].acquire()
                if (params[1]!="all"):
                    val = dict()
                    val[param_dict[params[0]][1]] = params[1]
                    param_dict[params[0]][0]("before_delete", val)
                else:
                    for item in self._mininet_data[params[0]].keys():
                        val = dict()
                        val[param_dict[params[0]][1]] = params[1]
                        param_dict[params[0]][0]("before_delete", val)
                self._locks[params[0]].release()
                message = str(params[0]) + ": " + str(params[1]) + " removed from the DS\n"
                return message
            except KeyError:
                message="Error! Unable to find " + str(params[0]) + " resource: " + str(params[1]) + ". No action taken"
                self._locks[params[0]].release()
                self._log_handler.error("Attempt to delete " + str(params[0]) + ": " + str(params[1]) + ". Resource not found")
                return message
            except Exception as ex:
                message += "Error! Received exception: " + str(ex.message)
                return message
        else:
            message+= "Error! Incorrect number of parameters passed"
            self._log_handler.error("_handle_cleanup expects a single array with length 2. Obtained array with length: " + str(len(params)))
            return message

    def handle_switch_creation(self, cmd='start',controller_ip=None, num_switches=10):
        message=""
        if cmd=='start' and controller_ip==None:
            message = "Incorrect parameters. Controller IP is missing"
        elif cmd=='start' and self._SIMULATION_STARTED:
            message="Virtual computes already created. Cleanup, before running the command again"
        elif cmd=='start':
            self._log_handler.debug("Starting creation of ovs containers")
            self._num_virtual_computes = num_switches
            result = self._dockernet.docker_ovs_run_connect(num_switches,controller_ip)
            if(result==False):
                message = "Virtual computes could not be started. See log for additional details"
            else:
                self._SIMULATION_STARTED=True
                message = str(num_switches) + " computes were started successfully. Use ovs_list command to get their names"
        if cmd=='stop' and self._SIMULATION_STARTED:
            result = self._dockernet.docker_down()
            self._num_virtual_computes = 0
            if(result):
                message = "All Virtual Computes destroyed"
            else:
                message = "Simulation could not be stopped. See log for additional details"
            self._SIMULATION_STARTED=False
        elif cmd=='stop' and (not self._SIMULATION_STARTED):
            message="No virtual computes are started. Cannot stop virtual computes"
        if cmd =='status'  and self._SIMULATION_STARTED:
            message = self.compute_status()
        elif cmd=="status" and (not self._SIMULATION_STARTED):
            message = "No Virtual Computes are Created."
        return message

    def _get_port_id_and_ip(self, subnet_id, **kwargs):
        port_uuid = None
        port_ip = None
        try:
            port_uuid = kwargs['id']
            try:
                for item in kwargs['fixed_ips']:
                    if (subnet_id == item['subnet_id']):
                        port_ip = item['ip_address']
            except KeyError as ex:
                self._log_handler.error("Encountered KeyError: " + str(ex.message))
        except KeyError as ex:
            self._log_handler.error("Encountered KeyError: " + str(ex.message))
        return (port_uuid,port_ip)

    def handle_display_cli(self, cmd, uid):
        message = ""
        CLI_MAPPING = {
            "network": self._mininet_data['network'],
            "subnet": self._mininet_data['subnet'],
            "port": self._mininet_data['port'],
            "router": self._mininet_data['router'],
            "subnet_port_map":self._mininet_data['subnet_port_map']
        }
        self._log_handler.debug("Received CLI command for: " + str(cmd) + " with uuid: " + str(uid))
        if uid == "all":
            try:
                for item in CLI_MAPPING[cmd].keys():
                    net = CLI_MAPPING[cmd][item]
                    message += str(net) + str("\n")
            except KeyError:
                message += "No " + str(cmd) + "s found."
        else:
            try:
                net = CLI_MAPPING[cmd][uid]
                message += str(net)
            except KeyError:
                message += "Error: No network with the uuid: " + str(uid)  + " is available"
        return message

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

    def _delete_data(self, type, uuid):
        try:
            self._locks[type].acquire()
            data = self._mininet_data[type].pop(uuid)
            self._locks[type].release()
            return (True, data)
        except KeyError as ke:
            self._log_handler.warning("Obtained KeyError when deleting data  of type: " + str(type) + " with uuid: " + str(uuid))
            self._locks[type].release()
            return (False, None)
        except Exception as ex:
            template = "An exception of type {0} occurred. Arguments:\n{1!r}"
            message = template.format(type(ex).__name__, ex.args)
            self._log_handler.error(message)
            self._locks[type].release()
            return (False, None)

    def _handle_network_event(self, event, **kwargs):
        try:
            network_uuid=None
            result = False
            if event in ("after_create", "after_update"):
                #kwargs = kwargs['network']
                network_uuid = kwargs['id']
                self._log_handler.debug("Received network event. Network UUID:" + str(kwargs['id']) + " Event: " + str(event))
                if 'mtu' in kwargs:
                    self._log_handler.debug("Received MTU: " + str(kwargs['mtu']) + " in Network: " + str(network_uuid))
                else:
                    kwargs['mtu'] = DEFAULT_MTU
                    self._log_handler.debug("Received no MTU, configuring default MTU :"  + str(DEFAULT_MTU) + " in Network: " + str(kwargs['id']))
                result = self._store_data("network", kwargs['id'], kwargs)
            elif event=="before_delete":
                network_uuid = kwargs['network_id']
                (result, data) = self._delete_data('network', kwargs['network_id'])
            else:
                self._log_handler.warning("Received unsubscribed Event: " + str(event) + "\n\n")
                result=False
            if (result):
                self._log_handler.debug("Network event for UUID: " + str(network_uuid) + " successful\n\n")
                return True
            else:
                self._log_handler.error("Network event for UUID: " + str(network_uuid) + " failed\n\n")
                return True
        except Exception as ex:
            self._log_handler.exception("Encountered exception: " + str(ex.message))
            return True

    def _handle_subnet_event(self, event, **kwargs):
        try:
            result = False
            subnet_uuid = None
            result_subnet = False
            if event in ("after_update", "after_create"):
                subnet_uuid = kwargs['id']
                self._log_handler.debug(" Create/Update subnet with Subnet UUID: " + str(subnet_uuid))
                if 'network_id' in kwargs:
                    self._log_handler.debug("Network: " + str(kwargs['network_id']))
                if 'cidr' in kwargs:
                    self._log_handler.debug("CIDR: " + str(kwargs['cidr']))
                if 'ip_version' in kwargs:
                    self._log_handler.debug("IP version: " + str(kwargs['ip_version']))
                if 'host_routes' in kwargs and len(kwargs['host_routes']) > 0:
                    self._log_handler.debug("host routes: " + str(kwargs['host_routes']))
                    for item in kwargs['host_routes']:
                        self._log_handler.debug("Host routes= Dest: " + str(item['destination']) + "-> " + str(item['nexthop']))
                if 'gateway_ip' in kwargs:
                    self._log_handler.debug(" Gateway:" + str(kwargs['gateway_ip']))
                    result = self._store_data("gateway_ip", subnet_uuid, kwargs['gateway_ip'])
                    if (not result):
                        self._log_handler.error("Storing gateway_ip: " + str(subnet_uuid) + " failed")
                    else:
                        self._log_handler.debug("Storing gateway_ip: " + str(subnet_uuid) + " successful")

                result = self._store_data('subnet', subnet_uuid, kwargs)
                if (not result):
                    self._log_handler.error("Storing subnet: " + str(subnet_uuid) + " failed")
                else:
                    self._log_handler.debug("Storing subnet: " + str(subnet_uuid) + " successful")
                result = self._store_data('subnet_port_map', subnet_uuid, list())
                if (not result):
                    self._log_handler.error("Creation of subnet: " + str(subnet_uuid) + " in subnet_port_map failed")
                else:
                    self._log_handler.debug("Creation of subnet: " + str(subnet_uuid) + " in subnet_port_map successful")
                    if (self._tests_enabled["subnet"]):
                        self._start_test_timers("subnet", subnet_uuid)
                        self._store_data('elan_test_data', subnet_uuid, queue.Queue(5))
                result_subnet = True
            elif event=="before_delete":
                subnet_uuid = kwargs['subnet_id']
                self._log_handler.debug("Received a Delete Event for Subnet: " + str(subnet_uuid))
                (result_subnet, data)= self._delete_data("subnet", subnet_uuid)
                if(result_subnet):
                    prefix_length = data["cidr"].split("/")[1]
                    (result, data)= self._delete_data("subnet_port_map", subnet_uuid)
                    (result, data)= self._delete_data("gateway_ip", subnet_uuid)
                    (result, data)=self._delete_data("dhcp_server", subnet_uuid)
                    (result, data) = self._delete_data("subnet_mips", subnet_uuid)
                    if(result):
                        self._dockernet.unconfigure_mips(subnet_uuid, data, prefix_length)
                    if (self._tests_enabled["subnet"]):
                        self._elan_test_timers[subnet_uuid].cancel()
                        self._elan_test_timers.pop(subnet_uuid)
                        self._delete_data('elan_test_data', subnet_uuid)
            else:
                self._log_handler.error("Unsubscribed Event " + str(event) + "\n\n")
                return True
            if(result_subnet):
                self._log_handler.info("Event " + str(event) + " for subnet : " + str(subnet_uuid) + " successful\n\n")
            else:
                self._log_handler.warning("Event " + str(event) + " for subnet : " + str(subnet_uuid) + " could have failed\n\n")
            return True
        except Exception as ex:
            self._log_handler.error("Subnet event Exception occured " + str(ex.message))
            return True

    def _handle_router_port_event(self, event, port_data, port_uuid, **kwargs):
        try:
            if event=="before_delete":
                try:
                    device_id=port_data['device_id']
                except KeyError:
                    self._log_handler.error("Port information does not contain device_id. Unable to process router interface add events. Ignoring...\n")
                    return True
                (result, data) = self._get_data('router', device_id)
                if (not result):
                    self._log_handler.error("Unable to find Router with ID: " + str(device_id) + ". Unable to handle the event")
                else:
                    (subnet_list, extra_route_list) = data
                if 'fixed_ips' in port_data:
                    for item in port_data['fixed_ips']:
                        try:
                            self._log_handler.debug("The port delete event translates to Router Detach for Subnet: " + str(item['subnet_id'])+ " from Router: " + str(device_id))
                            subnet_list.remove(item['subnet_id'])
                        except ValueError:
                            self._log_handler.warning("Detached subnet: " + str(item['subnet_id']) +" is not attached to router: " + str(device_id))
                else:
                    self._log_handler.error("Unable to find subnet associated with this detach event for Router: " + str(device_id) + "\n\n")
                    return True
            elif event in ("after_update", "after_create"):
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
                            if(not item['subnet_id'] in subnet_list):
                                subnet_list.append(item['subnet_id'])
                                self._log_handler.debug("Attaching Subnet: " + str(item['subnet_id']) + " to router: " + str(device_id))
                                self._log_handler.debug("Port's IP address: " + str(item['ip_address']))
                        except KeyError:
                            self._log_handler.error("While going through fixed_ips, could not find the key subnet_id OR ip_address")
                            return True
            else:
                self._log_handler.warning("Unsubscribed event: " + str(event) + ". Ignoring...")
                return True
            result = self._store_data('router', device_id, (subnet_list, extra_route_list))
            if (not result):
                self._log_handler.error("Encountered error during data storage/delete for router with UUID: " + str(device_id) + ". Ignoring the event\n\n")
                return True
            return True
        except Exception as ex:
            self._log_handler.error("Router Port Exception occured " + str(ex.message))
            return True

    def _convert_to_dict(self, data):
        try:
            jdata = ast.literal_eval(data)
            return jdata
        except Exception as ex:
            self._log_handler.error("Encountered exception: " + str(ex.message))
            return None


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

    def _calculate_routes_difference(self, routes_prev, routes_curr):
        s_route_curr = routes_curr
        routes_to_be_deleted = [x for x in routes_prev if x not in s_route_curr]
        self._log_handler.debug("Routes that need to be deleted: " + str(routes_to_be_deleted))
        s_route_prev = routes_prev
        routes_to_be_added = [x for x in routes_curr if x not in s_route_prev]
        self._log_handler.debug("Routes that need to be added: " + str(routes_to_be_added))
        return (routes_to_be_deleted, routes_to_be_added)

    def _handle_port_event(self, event, **kwargs):
        try:
            if event=="before_delete":
                try:
                    port_uuid=kwargs['port_id']
                except KeyError:
                    self._log_handler.error(" The field \'port_id\' does not exist in the arguments passed. Ignoring the event...\n\n")
                    return True
                self._log_handler.debug("Received a Delete Event for Port: " + str(port_uuid))
                (result, port_data) = self._delete_data('port', port_uuid)

                if(result):
                    if port_data['device_owner'] in "network:router_interface_distributed":
                        self._handle_router_port_event(event, port_data, port_uuid, **kwargs)
                    elif port_data['device_owner'] == "compute:nova":
                        if 'fixed_ips' in port_data:
                            for item in port_data['fixed_ips']:
                                (result, port_ip) = self._delete_data("port_to_ip_mapping", str(item['subnet_id'])+ str(port_uuid))
                                (result, router_uuid) = self._get_data("subnet_to_router_map", str(item['subnet_id']))
                                if (result):
                                    (result, port_info) = self._delete_data("ip_to_port_mapping", str(router_uuid)+ str(port_ip))
                                (result, data) = self._get_data('subnet_port_map', item['subnet_id'])
                                if (result):
                                    data.remove(self._get_port_id_and_ip(item['subnet_id'], **port_data))
                                    self._store_data('subnet_port_map', item['subnet_id'], data)
                                    result = self._dockernet.del_port_from_ovs(port_uuid)
                                else:
                                    self._log_handler.warning("Port: " + str(port_uuid) + " Not found in subnet: " + str(item['subnet_id']))
                    else:
                        self._log_handler.warning("Received a port with device owner: " + str(port_data['device_owner']) + ". No processing is required\n\n")
                else:
                    self._log_handler.warning("The port uuid: " + str(port_uuid) + " does not exist. Ignoring the event....")
                    return True
            elif event in ("after_create", "after_update"):
                if(not self.does_port_belong_to_my_partition(kwargs)):
                    self._log_handler.info("Received port with name: " + str(kwargs['name']) + ". My partition is: " + str(self._partition_id) + ". It doesn't match. Ignoring the event")
                    return True
                try:
                    port_uuid = kwargs['id']
                    self._log_handler.debug("Received port create/update event for port: " + str(port_uuid))
                except KeyError:
                    self._log_handler.error(" The field \'id\' does not exist in the arguments passed. Ignoring the event...\n\n")
                    return True
                result = self._store_data('port', port_uuid, kwargs)
                if(not result):
                    self._log_handler.error("Unable to store info for port: "+ str(port_uuid) )
                    return True
                if kwargs['device_owner'] in "network:router_interface_distributed":
                    result = self._handle_router_port_event(event, None, port_uuid, **kwargs)
                elif kwargs['device_owner']=="compute:nova":
                    if 'network_id' in kwargs:
                        self._log_handler.debug("Network id of port: " + str(kwargs['network_id']))
                    if 'device_id' in kwargs:
                        self._log_handler.debug("Device ID: " + str(kwargs['device_id']))
                    if 'fixed_ips' in kwargs :
                        gateway_ip_list = list()
                        self._log_handler.debug("Fixed IPs: " + str(kwargs['fixed_ips']))
                        for item in kwargs['fixed_ips']:
                            (result, data) = self._get_data('subnet_port_map', item['subnet_id'])
                            result_tuple = (port_uuid, item['ip_address'])
                            if (not result):
                                data = list(result_tuple)
                            else:
                                data.append(result_tuple)
                            self._store_data('subnet_port_map', item['subnet_id'], data)
                            (result,data) = self._get_data('subnet', item['subnet_id'])
                            subnet_cidr = data['cidr']
                            if (result):
                                tuple = (item['ip_address'], data['gateway_ip'], data['cidr'], data['ip_version'])
                                gateway_ip_list.append(tuple)
                            else:
                                self._log_handler.warning("Unknown subnet id: " + str(item['subnet_id']))
                            (result, router_uuid) = self._get_data("subnet_to_router_map", item['subnet_id'])
                            if(result):
                                self._log_handler.debug("subnet: " + str(item['subnet_id']) + " is attached to router: " + str(router_uuid))
                                self._store_data("ip_to_port_mapping", str(router_uuid) + str(result_tuple[1]), (str(result_tuple[0]), str(subnet_cidr)))
                                self._log_handler.debug("stored data- ip_address: " + str(router_uuid) + str(result_tuple[1]) + " port id: " + str(result_tuple[0]))
                            else:
                                self._log_handler.debug("subnet: " + str(item['subnet_id']) + " is not attached to any router" )
                            self._store_data("port_to_ip_mapping", str(item['subnet_id']) + str(port_uuid), str(result_tuple[1]))
                            self._log_handler.debug("Stored port: " + str(item['subnet_id']) + str(port_uuid)+ " with IP: " + str(result_tuple[1]) + " in port_to_ip_mapping")
                    mac_address=" "
                    if 'mac_address' in kwargs:
                        mac_address = kwargs['mac_address']
                        self._log_handler.debug("MAC address: " + str(kwargs['mac_address']))
                    else:
                        self._log_handler.warning("No MAC address found. L2/L3 forwarding will fail")
                    if 'allowed_address_pairs' in kwargs:
                        self._log_handler.debug("Allowed Address Pairs: " + str(kwargs['allowed_address_pairs']))
                    result=True
                    result = self._dockernet.add_port_to_ovs(gateway_ip_list, port_uuid, mac_address)
                elif kwargs['device_owner']=="network:dhcp":
                    self._log_handler.warning("Received a port with device owner: " + str(kwargs['device_owner']) )
                    for item in kwargs['fixed_ips']:
                        result=self._store_data("dhcp_server", item['subnet_id'], item['ip_address'])
                else:
                    self._log_handler.warning("Received a port with device owner: " + str(kwargs['device_owner']) + ". No processing is required\n\n")
                    result = True
            if (result):
                self._log_handler.debug("Port event for UUID: " + str(port_uuid) + " successful\n\n")
                return True
            else:
                self._log_handler.error("Port event for UUID: " + str(port_uuid) + " failed\n\n")
                return True
        except Exception as ex:
            self._log_handler.exception("Encountered exception: " + str(ex.message) + "\n\n")
            return True

    def _handle_router_event(self, event, **kwargs):
        try:
            if event in ("after_create", "after_update"):
                router_uuid = kwargs['id']
                (result, data) = self._get_data('router', router_uuid)
                if result:
                    (subnet_list, extra_route_list)=data
                else:
                    subnet_list = list()
                    extra_route_list = list()
                self._log_handler.debug("Router Create Event for Router: " + str(router_uuid))
                if 'routes' in kwargs:
                    (delete_routes, add_routes) = self._calculate_routes_difference(extra_route_list, kwargs['routes'])
                    if(len(delete_routes) != 0):
                        self.manage_extra_routes("del", router_uuid, delete_routes)
                    if(len(add_routes)!= 0):
                        self.manage_extra_routes("add", router_uuid, add_routes)
                    extra_route_list=kwargs['routes']
                result = self._store_data('router', router_uuid, (subnet_list, extra_route_list))
                for subnet in subnet_list:
                    result = self._store_data('subnet_to_router_map', subnet, router_uuid)
                    self._log_handler.debug("Stored the mapping Subnet: " + str(subnet) + " Router: " + router_uuid)
                    (result, port_list) = self._get_data("subnet_port_map", subnet)
                    (result, subnet_data) = self._get_data("subnet", subnet)
                    for port in port_list:
                        (result, port_ip) = self._get_data("port_to_ip_mapping", str(subnet)+ str(port))
                        (result, ip_map_data)=self._store_data("ip_to_port_mapping", str(router_uuid) + str(port_ip), (port, subnet_data['cidr']))
                if (self._tests_enabled["router"]):
                    self._start_test_timers("router", router_uuid)
                    self._store_data('router_test_data', router_uuid, queue.Queue(5))
            elif event=="before_delete":
                try:
                    router_uuid = kwargs['router_id']
                    (result, data) = self._delete_data('router', router_uuid)
                    if(self._tests_enabled["router"]):
                        self._router_test_timers[router_uuid].cancel()
                        self._router_test_timers.pop(router_uuid)
                    (subnet_list, extra_route_list) = data
                    for subnet in subnet_list:
                        self._delete_data("subnet_to_router_map", subnet)
                        (success, port_list) = self._get_data("subnet_port_map", subnet)
                        for port in port_list:
                            try:
                                (result, port_ip) = self._get_data("port_to_ip_mapping", str(subnet)+ str(port))
                                (result, ip_map_data)=self._delete_data("ip_to_port_mapping", str(router_uuid) + str(port_ip))
                                self._log_handler.debug("Deleted association of port: " + str(port) + " with router: " + router_uuid)
                            except KeyError as kx:
                                self._log_handler.error("Encountered KeyError when deleting port assoc: " + str(port) + " with router: " + str(router_uuid))
                                self._log_handler.error("Error message: " + str(kx.message))
                                continue
                except KeyError:
                    self._log_handler.warning("The field \'router_id\' is missing in the arguments. Ignoring the event ...\n\n")
                    return True

            if (result):
                self._log_handler.debug("Router event for UUID: " + str(router_uuid) + " successful\n\n")
                return True
            else:
                self._log_handler.error("Router event for UUID: " + str(router_uuid) + " failed\n\n")
                return True
        except Exception as ex:
            self._log_handler.exception("Encountered exception: " + str(ex.message) + "\n\n")
            return True

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
        except Exception as ex:
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


    def manage_extra_routes(self, action, router_uuid, extra_route_list):
        extra_route_pair = list()
        for item in extra_route_list:
            (result, data) = self._get_data("ip_to_port_mapping", str(router_uuid) + str(item['nexthop']))
            port_uuid_list = None
            if (result):
                (port_uuid, subnet_cidr)=data
                nh = port_uuid
                port_uuid_list = None
                try:
                    prefix_length=int(subnet_cidr.split("/")[1])
                except ValueError:
                    prefix_length=32
                    self._log_handler.warning("Could not obtain the prefix-length accurately. Using default value of 32")
                    continue
            else:
                nh = None
                (subnet_uuid, prefix_length) = self.get_subnet_for_nexthop(router_uuid, item['nexthop'])
                (result, port_uuid_ip_list) = self._get_data("subnet_port_map", subnet_uuid)
                (port_uuid_list, ip_addr_list) = list(zip(*port_uuid_ip_list))
                self._log_handler.warning("For prefix: " + str(item['destination']) + " next_hop: " + str(item['nexthop']) + " was not found on any neutron_port")
                self._log_handler.info(" Next_hop: " + str(item['nexthop']) + " will be hosted on one of the Neutron ports in subnet: " +str(subnet_uuid))
            extra_route_pair.append((item['destination'], nh, item['nexthop'], prefix_length, port_uuid_list))
        if (action == "add"):
            self._dockernet.configure_extra_routes(router_uuid, extra_route_pair)
        elif (action == "del"):
            self._dockernet.unconfigure_extra_routes(router_uuid, extra_route_pair)

    def _setup_logger(self,name, log_file, level=logging.INFO):
        log_handler = logging.getLogger(name)
        self._filehandler=logging.FileHandler(log_file, mode='w')
        self._filehandler.setFormatter(logging.Formatter('%(asctime)s %(processName)s %(levelname)s %(message)s'))
        log_handler.setLevel(level=level)
        log_handler.addHandler(self._filehandler)

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
            sys.exit(1)

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

if __name__ == '__main__':
    def handle_keyboard_interrupt(handler):
        handler._log_handler.info("Session Terminated by the User.")
        handler._log_handler.info("Storing data in the DB before exiting")
        handler.handle_test("subnet", "Stop")
        handler.handle_test("router","Stop")
        result = handler.store_in_db()
        if(result):
            print("Completed data storage")
            handler._log_handler.info("Completed data storage")
        else:
            print("Encountered error while storing data in DB")

    parser = argparse.ArgumentParser(description="Config File Location")
    parser.add_argument("-f", "--file-loc", action="store", dest="file_location", default="/home/stack/mininet_handler/config.ini")
    args = parser.parse_args()
    if args.file_location == None:
        print("File location was not processed correctly!")
        sys.exit(1)
    else:
        print("Looking for configurations in file: " + str(args.file_location))
    handler = NeutronEventHandler(args.file_location)
    topic = "neutron_events_for_simulation"
    consumer = KafkaConsumer(bootstrap_servers=handler.kafka_brokers, auto_offset_reset='earliest', value_deserializer=lambda m: json.loads(m.decode('utf-8')),group_id="simulator_consumer" )
    consumer.subscribe(topic)
    handler._log_handler.info("Subscribed for topic: " + str(topic))
    try:
        for msg in consumer:
            assert isinstance(msg.value, dict)
            data = msg.value
            handler._log_handler.debug("Received message with data: " + str(data))
            handler._log_handler.debug("Data is of type: " + str(type(data)))
            try:
                handler.configure_resource(data)
                consumer.commit()
            except KeyError as ex:
                handler._log_handler.error("Received KeyError in processing Message: " + str(ex.message))
                continue
            except Exception as ex:
                handler._log_handler.exception("Received exception when parsing msg: " + str(msg))
                continue
    except KeyboardInterrupt:
        print("Storing data in the DB. Do not press Ctrl+C again. Please wait....")
        handle_keyboard_interrupt(handler)
        print("Completed data storage. Exiting the program...")
    except Exception as ex:
        handler._log_handler.error("Received Exception in processing Message: " + str(ex.message))


