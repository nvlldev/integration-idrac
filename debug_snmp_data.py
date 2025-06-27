#!/usr/bin/env python3
"""Debug script to test SNMP data collection from Dell R820."""

import asyncio
from pysnmp.hlapi.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    getCmd,
)

async def test_memory_status():
    """Test memory status OIDs for Dell R820."""
    host = "liberator.tshq.local"
    port = 161
    community = "public"
    
    engine = SnmpEngine()
    auth_data = CommunityData(community)
    transport_target = UdpTransportTarget((host, port), timeout=10, retries=2)
    context_data = ContextData()
    
    # Test memory status for index 1
    memory_location_oid = "1.3.6.1.4.1.674.10892.5.4.1100.50.1.8.1.1"
    memory_status_oid = "1.3.6.1.4.1.674.10892.5.4.1100.50.1.5.1.1"
    memory_size_oid = "1.3.6.1.4.1.674.10892.5.4.1100.50.1.14.1.1"
    
    print("Testing memory SNMP OIDs for Dell R820...")
    
    # Test location name
    print(f"\nTesting memory location OID: {memory_location_oid}")
    try:
        error_indication, error_status, error_index, var_binds = await getCmd(
            engine, auth_data, transport_target, context_data,
            ObjectType(ObjectIdentity(memory_location_oid))
        )
        
        if error_indication:
            print(f"Error indication: {error_indication}")
        elif error_status:
            print(f"Error status: {error_status}")
        else:
            for name, val in var_binds:
                print(f"Location: {name} = {val} (type: {type(val)})")
    except Exception as e:
        print(f"Exception: {e}")
    
    # Test status
    print(f"\nTesting memory status OID: {memory_status_oid}")
    try:
        error_indication, error_status, error_index, var_binds = await getCmd(
            engine, auth_data, transport_target, context_data,
            ObjectType(ObjectIdentity(memory_status_oid))
        )
        
        if error_indication:
            print(f"Error indication: {error_indication}")
        elif error_status:
            print(f"Error status: {error_status}")
        else:
            for name, val in var_binds:
                print(f"Status: {name} = {val} (type: {type(val)})")
                try:
                    int_val = int(val)
                    print(f"Status as int: {int_val}")
                except:
                    print(f"Cannot convert '{val}' to int")
    except Exception as e:
        print(f"Exception: {e}")
    
    # Test size
    print(f"\nTesting memory size OID: {memory_size_oid}")
    try:
        error_indication, error_status, error_index, var_binds = await getCmd(
            engine, auth_data, transport_target, context_data,
            ObjectType(ObjectIdentity(memory_size_oid))
        )
        
        if error_indication:
            print(f"Error indication: {error_indication}")
        elif error_status:
            print(f"Error status: {error_status}")
        else:
            for name, val in var_binds:
                print(f"Size: {name} = {val} (type: {type(val)})")
                try:
                    int_val = int(val)
                    print(f"Size as int: {int_val}")
                except:
                    print(f"Cannot convert '{val}' to int")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_memory_status())