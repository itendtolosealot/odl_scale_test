from networking_odl.networking_odl.ml2 import NeutronEventDriverForMininet
from neutron_lib.callbacks import events


if __name__ == '__main__':
	driver = NeutronEventDriverForMininet()
	ev1 = events.AFTER_CREATE
	ev2 = events.BEFORE_DELETE
	vals1 = dict()
	vals1['mtu'] = 1450
	vals1['id'] = "ashvin lakshmikantha"
	driver._eventhandler._handle_network_event(ev1,vals1)


	ev = events.AFTER_CREATE
	vals2 = dict()
	vals2['id'] = "subnet1"
	vals2['network_id'] = "ashvin lakshmikantha"
	vals2['cidr'] = "192.168.20.0/24"
	vals2['host_routes'] = "none"
	vals2['ip_version'] = '4'
	vals2['gateway'] = "192.168.20.1"
	driver._eventhandler._handle_subnet_event(ev1,vals2)

	vals3 = dict()
	vals3['id'] = "subnet2"
	vals3['network_id'] = "ashvin lakshmikantha"
	vals3['cidr'] = "192.168.20.0/24"
	vals3['host_routes'] = "none"
	vals3['ip_version'] = '4'
	vals3['gateway'] = "192.168.20.1"
	driver._eventhandler._handle_subnet_event(ev1,vals3)

	vals4=dict()
	vals4['id'] = "device 007"
	driver._eventhandler._handle_router_event(ev1,vals4)

	vals5 = dict()
	vals5['id'] = "port1"
	vals5['device_id'] = "device 007"
	vals5['device_owner'] ="network:router_interface"
	ips = dict()
	ips['subnet_id'] = "subnet2"
	vals5['fixed_ips'] = ips
	driver._eventhandler._handle_port_event(ev1,vals5)

	vals6 = dict()
	vals6['id'] = "port2"
	vals6['network_id'] = "ashvin lakshmikantha"
	ips = dict()
	ips['subnet_id'] = "subnet1"
	vals6['fixed_ips'] =ips
	vals6['mac_address']="0B:AA:BB:CC:DD:EE"
	vals6['device_owner'] = "compute:nova"
	driver._eventhandler._handle_port_event(ev1,vals6)

	driver._eventhandler._handle_port_event(ev2,vals6)
	driver._eventhandler._handle_port_event(ev2,vals5)
	driver._eventhandler._handle_router_event(ev2,vals4)
	driver._eventhandler._handle_subnet_event(ev2,vals3)
	driver._eventhandler._handle_subnet_event(ev2,vals2)
	driver._eventhandler._handle_network_event(ev2,vals1)
