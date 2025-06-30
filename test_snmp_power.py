#!/usr/bin/env python3
"""
Test SNMP Power Consumption OID
Verify that power consumption is available via SNMP
"""

import asyncio
from pysnmp.hlapi.asyncio import (
    getCmd,
    SnmpEngine,
    CommunityData,
    UdpTransportTarget,
    ContextData,
    ObjectType,
    ObjectIdentity,
)

async def test_power_oid(host: str, community: str = "public"):
    """Test the power consumption OID."""
    print(f"Testing SNMP power consumption on {host}")
    print("=" * 50)
    
    # Power consumption OIDs
    oids = {
        "current_power": "1.3.6.1.4.1.674.10892.5.4.600.30.1.6.1.3",
        "peak_power": "1.3.6.1.4.1.674.10892.5.4.600.30.1.7.1.3",
        "base_oid": "1.3.6.1.4.1.674.10892.5.4.600.30.1.6.1",
    }
    
    engine = SnmpEngine()
    auth_data = CommunityData(community)
    transport = UdpTransportTarget((host, 161))
    context = ContextData()
    
    for name, oid in oids.items():
        print(f"\nTesting {name}: {oid}")
        
        try:
            error_indication, error_status, error_index, var_binds = await getCmd(
                engine,
                auth_data,
                transport,
                context,
                ObjectType(ObjectIdentity(oid))
            )
            
            if error_indication:
                print(f"  Error: {error_indication}")
            elif error_status:
                print(f"  Error: {error_status}")
            else:
                for var_name, var_value in var_binds:
                    print(f"  Result: {var_value}")
                    if str(var_value) != "No Such Object currently exists at this OID":
                        try:
                            watts = int(var_value)
                            print(f"  ✓ Power: {watts} W")
                        except:
                            print(f"  Value type: {type(var_value)}")
        
        except Exception as e:
            print(f"  Exception: {e}")
    
    # Test indexed values too
    print("\nTesting indexed values under base OID:")
    for index in range(1, 6):
        test_oid = f"{oids['base_oid']}.{index}"
        try:
            error_indication, error_status, error_index, var_binds = await getCmd(
                engine,
                auth_data,
                transport,
                context,
                ObjectType(ObjectIdentity(test_oid))
            )
            
            if not error_indication and not error_status:
                for var_name, var_value in var_binds:
                    if str(var_value) != "No Such Object currently exists at this OID":
                        print(f"  Index {index}: {var_value}")
        except:
            pass
    
    engine.close()

if __name__ == "__main__":
    # Replace with your iDRAC IP
    HOST = "192.168.50.131"
    
    asyncio.run(test_power_oid(HOST))
    
    print("\n" + "=" * 50)
    print("If power values are shown above, SNMP power monitoring is working!")
    print("The integration should automatically use SNMP for power consumption.")