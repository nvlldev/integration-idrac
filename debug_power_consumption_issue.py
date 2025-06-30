#!/usr/bin/env python3
"""
Debug Power Consumption Sensor Issue
Check why power sensor is not appearing despite OID being available
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

async def debug_power_issue(host: str, community: str = "public"):
    """Debug power consumption sensor issues."""
    print(f"🔍 DEBUGGING POWER CONSUMPTION SENSOR on {host}")
    print("=" * 60)
    
    # Test the actual power OIDs
    power_oids = {
        "current_power": "1.3.6.1.4.1.674.10892.5.4.600.30.1.6.1.3",
        "peak_power": "1.3.6.1.4.1.674.10892.5.4.600.30.1.7.1.3",
    }
    
    engine = SnmpEngine()
    auth_data = CommunityData(community)
    transport = UdpTransportTarget((host, 161))
    context = ContextData()
    
    print("\n1️⃣ TESTING POWER OIDS:")
    power_available = False
    
    for name, oid in power_oids.items():
        print(f"\n  Testing {name}: {oid}")
        
        try:
            error_indication, error_status, error_index, var_binds = await getCmd(
                engine,
                auth_data,
                transport,
                context,
                ObjectType(ObjectIdentity(oid))
            )
            
            if error_indication:
                print(f"    ❌ Error: {error_indication}")
            elif error_status:
                print(f"    ❌ Error: {error_status}")
            else:
                for var_name, var_value in var_binds:
                    if str(var_value) == "No Such Object currently exists at this OID":
                        print(f"    ❌ OID not found")
                    else:
                        try:
                            watts = int(var_value)
                            print(f"    ✅ Power: {watts} W")
                            power_available = True
                        except:
                            print(f"    ⚠️ Non-numeric value: {var_value}")
        
        except Exception as e:
            print(f"    ❌ Exception: {e}")
    
    print("\n2️⃣ POWER DISCOVERY ANALYSIS:")
    if power_available:
        print("  ✅ Power OID returns valid data")
        print("\n  Possible issues:")
        print("  1. Discovery happens during config flow")
        print("     - Check if 'discovered_power_consumption' is in config entry data")
        print("  2. Discovery checks base_oid.3 (fixed in latest code)")
        print("  3. SNMP coordinator might not have the data")
        print("\n  Debug steps:")
        print("  a) Re-add the integration to trigger fresh discovery")
        print("  b) Check logs for 'Power consumption sensor discovery'")
        print("  c) Look for 'discovered_power_consumption' in .storage/core.config_entries")
    else:
        print("  ❌ Power OID not returning data")
        print("     This iDRAC may not support power monitoring via SNMP")
    
    # Test discovery OID that the config flow uses
    print("\n3️⃣ TESTING DISCOVERY OID:")
    discovery_oid = "1.3.6.1.4.1.674.10892.5.4.600.30.1.6.1.3"  # Same as current_power
    
    try:
        error_indication, error_status, error_index, var_binds = await getCmd(
            engine,
            auth_data,
            transport,
            context,
            ObjectType(ObjectIdentity(discovery_oid))
        )
        
        if not error_indication and not error_status:
            for var_name, var_value in var_binds:
                if str(var_value) != "No Such Object currently exists at this OID":
                    print(f"  ✅ Discovery OID works: {var_value} W")
                    print("     Power should be discovered during config flow")
    except:
        pass
    
    engine.close()
    
    print("\n4️⃣ CHECK HOME ASSISTANT LOGS FOR:")
    print("  - 'Starting power consumption sensor discovery'")
    print("  - 'Found power consumption sensor at OID'")
    print("  - 'Creating 1 power_consumption sensors using...'")
    print("  - Which coordinator name appears (SNMPDataUpdateCoordinator vs RedfishDataUpdateCoordinator)")
    
    print("\n5️⃣ CHECK CONFIG ENTRY:")
    print("  Look in .storage/core.config_entries for your iDRAC entry")
    print("  Check if 'discovered_power_consumption' exists in the data")
    print("  Should be: 'discovered_power_consumption': [1]")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        HOST = sys.argv[1]
    else:
        HOST = "192.168.50.131"
    
    print(f"Testing host: {HOST}")
    print("(Use: python3 debug_power_consumption_issue.py YOUR_IDRAC_IP)")
    print()
    
    asyncio.run(debug_power_issue(HOST))