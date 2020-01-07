enum EVENT{
    CREATE=1       // 1
    UPDATE=2,   // 2
    DELETE=3,    // 3
    ATTACH=4, //Refers to Router events only
    DETACH=5  //Refers to Router events only
}

enum RESYNC_STATUS {
    IDLE=0,
    ONGOING=1,
    COMPLETED=2,
    FAILED=3
}

enum RESOURCE {
    NETWORK=1,
    SUBNET=2,
    PORT=3,
    ROUTER=4
}

struct resource {
    1: required RESOURCE type,
    2: required EVENT event,
    3: optional string data
}

service MaxinetConfigurationService {
    bool resource_configured(1: resource res)
    bool keepalive()
    RESYNC_STATUS can_start_resync()
    bool resync_completed()
}

