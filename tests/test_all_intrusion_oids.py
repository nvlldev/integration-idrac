#!/usr/bin/env python3
"""
Purpose: Comprehensive test of all intrusion-related OIDs to debug sensor availability
Usage: python tests/test_all_intrusion_oids.py <idrac_ip> <community_string>
Author: Claude Code Assistant
Date: 2025-01-28
"""
import asyncio
import logging
from pysnmp.hlapi.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    getCmd,
    nextCmd,
)

logging.basicConfig(level=logging.INFO)
_LOGGER = logging.getLogger(__name__)

# All intrusion-related OIDs
INTRUSION_OIDS = {
    # Individual sensor OIDs (indexed)
    "location": "1.3.6.1.4.1.674.10892.5.4.300.70.1.8.1",
    "reading": "1.3.6.1.4.1.674.10892.5.4.300.70.1.6.1", 
    "status": "1.3.6.1.4.1.674.10892.5.4.300.70.1.5.1",
    
    # Parent OIDs for walking
    "intrusion_table": "1.3.6.1.4.1.674.10892.5.4.300.70.1",
    
    # System-level intrusion OID (if exists)
    "system_intrusion": "1.3.6.1.4.1.674.10892.5.4.300.10.1.8.1",
}

async def walk_oid(engine, auth_data, transport_target, context_data, base_oid):
    """Walk an OID tree and return all values."""
    results = []
    
    async for error_indication, error_status, error_index, var_binds in nextCmd(
        engine,
        auth_data,
        transport_target,
        context_data,
        ObjectType(ObjectIdentity(base_oid)),
        lexicographicMode=False
    ):
        if error_indication:
            _LOGGER.error("Walk error: %s", error_indication)
            break
        elif error_status:
            _LOGGER.error("Walk error status: %s", error_status.prettyPrint())
            break
        else:
            for var_bind in var_binds:
                oid = str(var_bind[0])
                value = var_bind[1]
                # Stop if we've walked past our base OID
                if not oid.startswith(base_oid):
                    return results
                results.append((oid, value))
    
    return results

async def test_intrusion_comprehensive(host: str, community: str = "public", port: int = 161):
    """Comprehensive test of intrusion sensors."""
    engine = SnmpEngine()
    auth_data = CommunityData(community)
    transport_target = UdpTransportTarget((host, port))
    context_data = ContextData()
    
    print(f"\nComprehensive intrusion sensor test on {host}:{port}")
    print("=" * 80)
    
    # First, walk the intrusion table to see all available data
    print("\n1. Walking entire intrusion table...")
    table_results = await walk_oid(engine, auth_data, transport_target, context_data, INTRUSION_OIDS["intrusion_table"])
    
    if table_results:
        print(f"Found {len(table_results)} OIDs in intrusion table:")
        for oid, value in table_results:
            print(f"  {oid} = {value}")
    else:
        print("  No data found in intrusion table")
    
    # Test specific indices
    print("\n2. Testing specific sensor indices (1-5)...")
    found_sensors = {}
    
    for index in range(1, 6):
        sensor_data = {}
        found_any = False
        
        for oid_name, base_oid in [("location", INTRUSION_OIDS["location"]), 
                                   ("reading", INTRUSION_OIDS["reading"]), 
                                   ("status", INTRUSION_OIDS["status"])]:
            test_oid = f"{base_oid}.{index}"
            
            try:
                error_indication, error_status, error_index, var_binds = await getCmd(
                    engine,
                    auth_data,
                    transport_target,
                    context_data,
                    ObjectType(ObjectIdentity(test_oid)),
                )
                
                if not error_indication and not error_status and var_binds:
                    for name, val in var_binds:
                        if val is not None and str(val) != "No Such Object currently exists at this OID":
                            sensor_data[oid_name] = str(val)
                            found_any = True
                            
            except Exception as exc:
                _LOGGER.error("Exception testing %s: %s", test_oid, exc)
        
        if found_any:
            found_sensors[index] = sensor_data
            print(f"\nSensor {index}:")
            for key, value in sensor_data.items():
                print(f"  {key}: {value}")
                if key == "reading":
                    try:
                        reading_int = int(value)
                        status_map = {1: "breach", 2: "no_breach", 3: "ok", 4: "unknown"}
                        print(f"    -> Interpreted as: {status_map.get(reading_int, 'unknown')}")
                    except:
                        pass
    
    if not found_sensors:
        print("\nNo intrusion sensors found at indices 1-5")
    
    # Test system-level intrusion OID
    print("\n3. Testing system-level intrusion OID...")
    try:
        error_indication, error_status, error_index, var_binds = await getCmd(
            engine,
            auth_data,
            transport_target,
            context_data,
            ObjectType(ObjectIdentity(INTRUSION_OIDS["system_intrusion"])),
        )
        
        if not error_indication and not error_status and var_binds:
            for name, val in var_binds:
                if val is not None and str(val) != "No Such Object currently exists at this OID":
                    print(f"  System intrusion: {val}")
                else:
                    print("  System intrusion OID not found")
        else:
            print("  Could not read system intrusion OID")
    except Exception as exc:
        print(f"  Exception: {exc}")
    
    # Summary
    print("\n4. Summary:")
    print(f"  - Found {len(found_sensors)} intrusion sensors")
    if found_sensors:
        print("  - Sensor indices:", list(found_sensors.keys()))
        print("  - Would be discovered by Home Assistant:", 
              any('location' in data and data['location'] for data in found_sensors.values()))
    
    engine.close()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        HOST = sys.argv[1]
    else:
        HOST = "10.0.1.17"  # Default iDRAC IP
    
    COMMUNITY = sys.argv[2] if len(sys.argv) > 2 else "public"
    PORT = int(sys.argv[3]) if len(sys.argv) > 3 else 161
    
    print(f"Usage: {sys.argv[0]} [host] [community] [port]")
    
    asyncio.run(test_intrusion_comprehensive(HOST, COMMUNITY, PORT))