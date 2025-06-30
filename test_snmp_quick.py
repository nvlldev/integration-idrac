#!/usr/bin/env python3
"""Quick SNMP test to find PSU voltages."""

import asyncio
import os
from dotenv import load_dotenv
from pysnmp.hlapi.asyncio import *

load_dotenv('.env.local')

async def test_snmp():
    host = os.getenv('IDRAC_HOST')
    community = os.getenv('IDRAC_COMMUNITY', 'public')
    
    # Voltage probe indices to check
    indices = [11, 12, 41, 42, 43, 44, 45, 46, 47, 48]
    
    snmp_engine = SnmpEngine()
    
    print("Testing SNMP voltage probes...")
    print("-" * 50)
    
    for idx in indices:
        # Get location
        location_oid = f"1.3.6.1.4.1.674.10892.5.4.600.20.1.8.1.{idx}"
        errorIndication, errorStatus, errorIndex, varBinds = await getCmd(
            snmp_engine,
            CommunityData(community),
            UdpTransportTarget((host, 161)),
            ContextData(),
            ObjectType(ObjectIdentity(location_oid))
        )
        
        if not errorIndication and not errorStatus:
            location = varBinds[0][1].prettyPrint()
            if "Instance" not in location:
                # Get voltage
                voltage_oid = f"1.3.6.1.4.1.674.10892.5.4.600.20.1.6.1.{idx}"
                errorIndication2, errorStatus2, errorIndex2, varBinds2 = await getCmd(
                    snmp_engine,
                    CommunityData(community),
                    UdpTransportTarget((host, 161)),
                    ContextData(),
                    ObjectType(ObjectIdentity(voltage_oid))
                )
                
                voltage_str = "No voltage reading"
                if not errorIndication2 and not errorStatus2:
                    voltage_raw = varBinds2[0][1].prettyPrint()
                    try:
                        voltage_mv = int(voltage_raw)
                        voltage_v = voltage_mv / 1000.0 if voltage_mv > 1000 else float(voltage_mv)
                        voltage_str = f"{voltage_v} V"
                    except:
                        voltage_str = voltage_raw
                
                print(f"Index {idx}: {location} = {voltage_str}")
                
                # Check if this is a PSU voltage
                if any(term in location.lower() for term in ["ps1", "ps2", "psu"]):
                    print(f"  ^^^ PSU VOLTAGE FOUND! ^^^")

asyncio.run(test_snmp())