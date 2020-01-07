struct fixed_ip {
    1: string ip_address,
    2: string subnet_id
}

struct allowed_address_pair {
    1: string ip_address,
    2: string mac_address
}

struct external_fixed_ip{
    1: required string ip_address,
    2: required string subnet_id
}

enum EVENT{
    CREATE=1       // 1
    UPDATE=2, // 2
    DELETE=3,    // 3
    ATTACH=4, //Refers to Router events only
    DETACH=5  //Refers to Router events only
}

enum RESOURCE {
    NETWORK=1,
    SUBNET=2,
    PORT=3,
    ROUTER=4
}

struct extra_route {
    1: required string router_id,
    2: required string destination,
    3: required string nexthop
}

struct network {
    1: required string network_uuid,
    2: optional i16 mtu,
}

struct subnet {
    1: required string subnet_uuid,
    2: optional string network_uuid,
    3: optional string cidr,
    4: optional i8 ip_version,
    5: optional map<string,string> host_routes,
    6: optional string gateway
}

struct port {
    1: required string port_uuid,
    2: optional string network_uuid,
    3: optional list<fixed_ip> fixed_ips,
    4: optional string mac_address,
    5: optional list<allowed_address_pair> aaps
}

struct router {
   1: required string router_uuid,
   2: optional list<string> subnets,
   3: optional list<extra_route> routes
}

struct resource {
    1: required RESOURCE type,
    2: required EVENT event,
    3: optional network net,
    4: optional subnet sub,
    5: optional port pt,
    6: optional router rtr
}

service MaxinetConfigurationService {
    bool resource_configured(1: resource res)
}

