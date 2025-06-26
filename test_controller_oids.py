#!/usr/bin/env python3
"""
Test script to verify Dell iDRAC storage controller diagnostic OIDs.
This script will test the new OIDs we added to see if they provide additional information.
"""

import asyncio
import sys
from pysnmp.hlapi.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    getCmd,
)

# Configuration - update these values for your iDRAC
IDRAC_HOST = "your-idrac-ip"  # Replace with your iDRAC IP
IDRAC_PORT = 161
COMMUNITY = "public"
CONTROLLER_INDEX = 0  # Replace with your controller index from discovery

# OIDs to test
TEST_OIDS = {
    "controller_state": f"1.3.6.1.4.1.674.10892.5.5.1.20.130.1.1.38.{CONTROLLER_INDEX}",
    "controller_battery_state": f"1.3.6.1.4.1.674.10892.5.5.1.20.130.15.1.4.{CONTROLLER_INDEX}",
    "controller_rollup_status": f"1.3.6.1.4.1.674.10892.5.5.1.20.130.1.1.37.{CONTROLLER_INDEX}",
    "controller_name": f"1.3.6.1.4.1.674.10892.5.5.1.20.130.1.1.2.{CONTROLLER_INDEX}",
    "controller_firmware": f"1.3.6.1.4.1.674.10892.5.5.1.20.130.1.1.8.{CONTROLLER_INDEX}",
    "controller_cache_size": f"1.3.6.1.4.1.674.10892.5.5.1.20.130.1.1.33.{CONTROLLER_INDEX}",
    "controller_rebuild_rate": f"1.3.6.1.4.1.674.10892.5.5.1.20.130.1.1.43.{CONTROLLER_INDEX}",
}

# State mappings
STATE_MAPS = {
    "controller_state": {
        1: "unknown",
        2: "ready",
        3: "failed",
        4: "online",
        5: "offline",
        6: "degraded"
    },
    "controller_battery_state": {
        1: "unknown",
        2: "ready",
        3: "failed",
        4: "degraded",
        5: "missing",
        6: "charging",
        7: "below_threshold"
    },
    "controller_rollup_status": {
        1: "other",
        2: "unknown",
        3: "ok",
        4: "non_critical",
        5: "critical",
        6: "non_recoverable"
    }
}

async def get_snmp_value(engine, community_data, transport_target, context_data, oid):
    """Get a single SNMP value."""
    try:
        error_indication, error_status, error_index, var_binds = await getCmd(
            engine,
            community_data,
            transport_target,
            context_data,
            ObjectType(ObjectIdentity(oid)),
        )

        if error_indication or error_status:
            print(f"  SNMP error: {error_indication or error_status}")
            return None

        if var_binds:
            return var_binds[0][1]
        return None

    except Exception as exc:
        print(f"  Exception: {exc}")
        return None

async def test_controller_oids():
    """Test all controller OIDs and display results."""
    print(f"Testing Dell iDRAC Storage Controller OIDs")
    print(f"Host: {IDRAC_HOST}:{IDRAC_PORT}")
    print(f"Community: {COMMUNITY}")
    print(f"Controller Index: {CONTROLLER_INDEX}")
    print("=" * 60)
    
    # Create SNMP engine and connections
    engine = SnmpEngine()
    community_data = CommunityData(COMMUNITY)
    transport_target = UdpTransportTarget((IDRAC_HOST, IDRAC_PORT), timeout=5, retries=1)
    context_data = ContextData()
    
    for oid_name, oid in TEST_OIDS.items():
        print(f"\n{oid_name}:")
        print(f"  OID: {oid}")
        
        value = await get_snmp_value(engine, community_data, transport_target, context_data, oid)
        
        if value is not None:
            print(f"  Raw value: {value} (type: {type(value)})")
            
            # Try to map the value if it's a known state
            if oid_name in STATE_MAPS:
                try:
                    int_value = int(value)
                    mapped_value = STATE_MAPS[oid_name].get(int_value, f"unknown_{int_value}")
                    print(f"  Mapped value: {mapped_value}")
                except (ValueError, TypeError):
                    print(f"  Could not map value to integer")
            
            # For string values, try to clean them up
            if oid_name in ["controller_name", "controller_firmware"]:
                clean_value = str(value).strip()
                if clean_value and "No Such Object" not in clean_value:
                    print(f"  String value: '{clean_value}'")
        else:
            print(f"  No value returned (OID may not be supported)")

if __name__ == "__main__":
    print("Dell iDRAC Storage Controller OID Diagnostic Tool")
    print("=" * 50)
    
    if IDRAC_HOST == "your-idrac-ip":
        print("ERROR: Please update IDRAC_HOST, CONTROLLER_INDEX, and COMMUNITY in the script")
        print("Update the configuration section at the top of this file with your values.")
        sys.exit(1)
    
    try:
        asyncio.run(test_controller_oids())
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"\nError running test: {e}")