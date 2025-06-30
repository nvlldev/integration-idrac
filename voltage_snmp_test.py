#!/usr/bin/env python3
"""
Test voltage sensors specifically using the exact OIDs from the integration.
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

async def test_voltage_sensors(host, community="public"):
    """Test the voltage sensors using exact OIDs from the integration."""
    engine = SnmpEngine()
    auth_data = CommunityData(community)
    transport_target = UdpTransportTarget((host, 161))
    context_data = ContextData()
    
    print(f"Testing voltage sensors on {host}")
    print("="*50)
    
    # Test voltage sensors 1-10 using the exact OID format from const.py
    voltage_names = {}
    voltage_readings = {}
    voltage_statuses = {}
    
    for i in range(1, 11):
        # Test voltage name
        name_oid = f"1.3.6.1.4.1.674.10892.5.4.600.20.1.8.1.{i}"
        reading_oid = f"1.3.6.1.4.1.674.10892.5.4.600.20.1.6.1.{i}"
        status_oid = f"1.3.6.1.4.1.674.10892.5.4.600.20.1.5.1.{i}"
        
        try:
            # Get voltage name
            error_indication, error_status, error_index, var_binds = await getCmd(
                engine, auth_data, transport_target, context_data,
                ObjectType(ObjectIdentity(name_oid))
            )
            
            if not error_indication and not error_status and var_binds:
                for name, val in var_binds:
                    if val is not None and str(val).strip():
                        voltage_names[i] = str(val).strip()
            
            # Get voltage reading  
            error_indication, error_status, error_index, var_binds = await getCmd(
                engine, auth_data, transport_target, context_data,
                ObjectType(ObjectIdentity(reading_oid))
            )
            
            if not error_indication and not error_status and var_binds:
                for name, val in var_binds:
                    if val is not None and str(val).strip():
                        voltage_readings[i] = str(val).strip()
            
            # Get voltage status
            error_indication, error_status, error_index, var_binds = await getCmd(
                engine, auth_data, transport_target, context_data,
                ObjectType(ObjectIdentity(status_oid))
            )
            
            if not error_indication and not error_status and var_binds:
                for name, val in var_binds:
                    if val is not None and str(val).strip():
                        voltage_statuses[i] = str(val).strip()
                        
        except Exception as e:
            print(f"Error testing voltage {i}: {e}")
    
    # Display results
    print(f"\nFound {len(voltage_names)} voltage sensors:")
    for i in sorted(voltage_names.keys()):
        name = voltage_names.get(i, "Unknown")
        reading = voltage_readings.get(i, "No reading")
        status = voltage_statuses.get(i, "No status")
        
        # Map status to human readable
        status_map = {
            "1": "other",
            "2": "unknown", 
            "3": "ok",
            "4": "non_critical",
            "5": "critical",
            "6": "non_recoverable"
        }
        status_text = status_map.get(status, status)
        
        print(f"  {i}: {name}")
        print(f"     Reading: {reading}")
        print(f"     Status: {status_text}")
        print()
    
    try:
        engine.observer.stop()
    except:
        pass
    
    return voltage_names, voltage_readings, voltage_statuses

async def main():
    if len(sys.argv) < 2:
        print("Usage: python voltage_snmp_test.py <host> [community]")
        sys.exit(1)
    
    host = sys.argv[1]
    community = sys.argv[2] if len(sys.argv) > 2 else "public"
    
    await test_voltage_sensors(host, community)

if __name__ == "__main__":
    asyncio.run(main())