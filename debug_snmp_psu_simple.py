#!/usr/bin/env python3
"""
Simple debug script to check specific PSU voltage indices via SNMP.
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

# Add the custom_components path to import our modules
sys.path.insert(0, 'custom_components')

from idrac.const import IDRAC_OIDS
from pysnmp.hlapi.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    getCmd,
)

# Load environment variables
load_dotenv('.env.local')

async def check_psu_voltages():
    """Check specific PSU voltage indices that we found in Redfish."""
    
    host = os.getenv('IDRAC_HOST')
    community = os.getenv('IDRAC_COMMUNITY', 'public')
    port = int(os.getenv('IDRAC_PORT', 161))
    
    print("\n" + "="*80)
    print("DELL iDRAC PSU VOLTAGE SNMP CHECK")
    print("="*80)
    print(f"Host: {host}:{port}, Community: {community}")
    
    # Known PSU voltage indices from Redfish debug + additional indices to check
    psu_indices = [
        (11, "System Board PS2 PG Fail"),
        (12, "System Board PS1 PG Fail"),
        (41, "PS1 Voltage 1"),
        (42, "PS2 Voltage 2"),
        (43, "Check for PS2"),
        (44, "Check for PS2"),
        (45, "Check for PS2"),
    ]
    
    # Also check the PSU table indices
    psu_table_indices = [1, 2, 3, 4, 5]  # Common PSU indices
    
    snmp_engine = SnmpEngine()
    
    print("\n1. CHECKING VOLTAGE PROBE TABLE (indices from Redfish):")
    print("-" * 50)
    
    for idx, expected_name in psu_indices:
        print(f"\nIndex {idx} (expected: {expected_name}):")
        
        # Get location name (voltage probes use system_voltage_location)
        location_oid = IDRAC_OIDS['system_voltage_location'].replace('{index}', str(idx))
        errorIndication, errorStatus, errorIndex, varBinds = await getCmd(
            snmp_engine,
            CommunityData(community),
            UdpTransportTarget((host, port), timeout=5.0, retries=2),
            ContextData(),
            ObjectType(ObjectIdentity(location_oid))
        )
        
        location = None
        if not errorIndication and not errorStatus:
            for varBind in varBinds:
                location = varBind[1].prettyPrint()
                print(f"  Location: {location}")
        else:
            print(f"  Location: Error - {errorIndication or errorStatus}")
        
        # Get voltage reading (voltage probes use system_voltage_reading)
        voltage_oid = IDRAC_OIDS['system_voltage_reading'].replace('{index}', str(idx))
        errorIndication, errorStatus, errorIndex, varBinds = await getCmd(
            snmp_engine,
            CommunityData(community),
            UdpTransportTarget((host, port), timeout=5.0, retries=2),
            ContextData(),
            ObjectType(ObjectIdentity(voltage_oid))
        )
        
        if not errorIndication and not errorStatus:
            for varBind in varBinds:
                voltage_raw = varBind[1].prettyPrint()
                try:
                    voltage_mv = int(voltage_raw)
                    voltage_v = voltage_mv / 1000.0 if voltage_mv > 1000 else voltage_mv
                    print(f"  Voltage: {voltage_raw} ({voltage_v} V)")
                except:
                    print(f"  Voltage: {voltage_raw}")
        else:
            print(f"  Voltage: Error - {errorIndication or errorStatus}")
    
    print("\n\n2. CHECKING PSU TABLE (common PSU indices):")
    print("-" * 50)
    
    for idx in psu_table_indices:
        print(f"\nPSU Table Index {idx}:")
        
        # Get PSU location/name
        location_oid = IDRAC_OIDS['psu_location'].replace('{index}', str(idx))
        errorIndication, errorStatus, errorIndex, varBinds = await getCmd(
            snmp_engine,
            CommunityData(community),
            UdpTransportTarget((host, port), timeout=5.0, retries=2),
            ContextData(),
            ObjectType(ObjectIdentity(location_oid))
        )
        
        if not errorIndication and not errorStatus:
            for varBind in varBinds:
                location = varBind[1].prettyPrint()
                if location and "Instance" not in location:
                    print(f"  Location: {location}")
                    
                    # Get PSU status
                    status_oid = IDRAC_OIDS['psu_status'].replace('{index}', str(idx))
                    errorIndication2, errorStatus2, errorIndex2, varBinds2 = await getCmd(
                        snmp_engine,
                        CommunityData(community),
                        UdpTransportTarget((host, port), timeout=5.0, retries=2),
                        ContextData(),
                        ObjectType(ObjectIdentity(status_oid))
                    )
                    
                    if not errorIndication2 and not errorStatus2:
                        for varBind2 in varBinds2:
                            print(f"  Status: {varBind2[1].prettyPrint()}")
                    
                    # Get PSU max output
                    max_oid = IDRAC_OIDS['psu_max_output'].replace('{index}', str(idx))
                    errorIndication3, errorStatus3, errorIndex3, varBinds3 = await getCmd(
                        snmp_engine,
                        CommunityData(community),
                        UdpTransportTarget((host, port), timeout=5.0, retries=2),
                        ContextData(),
                        ObjectType(ObjectIdentity(max_oid))
                    )
                    
                    if not errorIndication3 and not errorStatus3:
                        for varBind3 in varBinds3:
                            print(f"  Max Output: {varBind3[1].prettyPrint()} W")
    
    print("\n\n3. SUMMARY:")
    print("-" * 50)
    print("Redfish PowerSupplies.LineInputVoltage values:")
    print("  PSU 1: 118 V")
    print("  PSU 2: 124 V")
    print("\nCheck if SNMP voltage readings match these values.")
    
    # Test discovery OIDs
    print("\n\n4. TESTING DISCOVERY OIDS:")
    print("-" * 50)
    
    # Test if we can discover voltage probes
    discovery_oid = IDRAC_OIDS["psu_location"]
    print(f"Voltage probe discovery OID: {discovery_oid}")
    
    # Try index 1
    test_oid = f"{discovery_oid}.1"
    errorIndication, errorStatus, errorIndex, varBinds = await getCmd(
        snmp_engine,
        CommunityData(community),
        UdpTransportTarget((host, port), timeout=5.0, retries=2),
        ContextData(),
        ObjectType(ObjectIdentity(test_oid))
    )
    
    if not errorIndication and not errorStatus:
        for varBind in varBinds:
            print(f"  Index 1: {varBind[1].prettyPrint()}")
    else:
        print(f"  Index 1: Error - {errorIndication or errorStatus}")

asyncio.run(check_psu_voltages())