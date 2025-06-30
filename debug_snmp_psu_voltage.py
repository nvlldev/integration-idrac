#!/usr/bin/env python3
"""
Debug script to explore PSU voltage data sources in Dell iDRAC via SNMP.
This script will check all SNMP OIDs related to PSU voltage to find input voltage readings.
"""

import asyncio
import os
import sys
import logging
from typing import Dict, Any, List, Tuple

from dotenv import load_dotenv

# Add the custom_components path to import our modules
sys.path.insert(0, 'custom_components')

from idrac.const import IDRAC_OIDS

# Load environment variables
load_dotenv('.env.local')

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import pysnmp using the same style as the project
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

class SNMPPSUVoltageDebugger:
    """Debug PSU voltage data sources in iDRAC via SNMP."""
    
    def __init__(self):
        self.host = os.getenv('IDRAC_HOST')
        self.community = os.getenv('IDRAC_COMMUNITY', 'public')
        self.port = int(os.getenv('IDRAC_PORT', 161))
        
        if not self.host:
            raise ValueError("Missing IDRAC_HOST in .env.local file")
        
        logger.info(f"Connecting to iDRAC at {self.host}:{self.port} with community '{self.community}'")
        
    async def snmp_get(self, oid):
        """Perform SNMP GET operation."""
        snmp_engine = SnmpEngine()
        
        errorIndication, errorStatus, errorIndex, varBinds = await getCmd(
            snmp_engine,
            CommunityData(self.community),
            UdpTransportTarget((self.host, self.port), timeout=5.0, retries=2),
            ContextData(),
            ObjectType(ObjectIdentity(oid))
        )
        
        if errorIndication:
            logger.error(f"SNMP GET error: {errorIndication}")
            return None
        elif errorStatus:
            logger.error(f"SNMP GET error: {errorStatus.prettyPrint()} at {errorIndex}")
            return None
        else:
            for varBind in varBinds:
                return varBind[1].prettyPrint()
        
        return None
    
    async def walk_oid_tree(self, base_oid, max_items=100):
        """Walk an OID tree and return all results."""
        results = []
        count = 0
        
        snmp_engine = SnmpEngine()
        
        async for (errorIndication, errorStatus, errorIndex, varBinds) in nextCmd(
            snmp_engine,
            CommunityData(self.community),
            UdpTransportTarget((self.host, self.port), timeout=5.0, retries=2),
            ContextData(),
            ObjectType(ObjectIdentity(base_oid)),
            lexicographicMode=False
        ):
            if errorIndication:
                logger.error(f"SNMP WALK error: {errorIndication}")
                break
            elif errorStatus:
                logger.error(f"SNMP WALK error: {errorStatus.prettyPrint()} at {errorIndex}")
                break
            else:
                for varBind in varBinds:
                    oid = str(varBind[0])
                    value = varBind[1].prettyPrint()
                    results.append((oid, value))
                    count += 1
                    if count >= max_items:
                        return results
        
        return results
    
    async def debug_psu_voltages(self):
        """Explore all PSU and voltage data sources via SNMP."""
        
        print("\n" + "="*80)
        print("DELL iDRAC PSU VOLTAGE SNMP DEBUG SCRIPT")
        print("="*80)
        
        # 1. Test SNMP connectivity
        print("\n1. Testing SNMP connectivity...")
        # Using the system name OID from IDRAC_OIDS
        test_oid = "1.3.6.1.4.1.674.10892.5.1.3.1.1.0"  # System name
        test_result = await self.snmp_get(test_oid)
        if not test_result:
            print("❌ Failed to connect via SNMP")
            return
        print(f"✅ Connected via SNMP - System: {test_result}")
        
        # 2. Explore PSU Table
        print("\n2. EXPLORING PSU TABLE:")
        print("-" * 50)
        
        # Walk PSU location OID to find all PSUs
        print("\nPSU Locations:")
        psu_locations = await self.walk_oid_tree(IDRAC_OIDS["psu_location"], 20)
        psu_indices = []
        
        for oid, location in psu_locations:
            # Extract index from OID
            index = oid.split('.')[-1]
            psu_indices.append(index)
            print(f"  PSU Index {index}: {location}")
        
        # Get details for each PSU
        print("\nPSU Details:")
        for idx in psu_indices:
            print(f"\n  PSU {idx}:")
            
            # Get status
            status_oid = f"{IDRAC_OIDS['psu_status']}.{idx}"
            status = await self.snmp_get(status_oid)
            print(f"    Status: {status}")
            
            # Get max output
            max_output_oid = f"{IDRAC_OIDS['psu_max_output']}.{idx}"
            max_output = await self.snmp_get(max_output_oid)
            print(f"    Max Output: {max_output} W")
            
            # Get current output
            current_output_oid = f"{IDRAC_OIDS['psu_current_output']}.{idx}"
            current_output = await self.snmp_get(current_output_oid)
            print(f"    Current Output: {current_output} W")
        
        # 3. Explore Voltage Probe Table
        print("\n\n3. EXPLORING VOLTAGE PROBE TABLE:")
        print("-" * 50)
        
        # Walk voltage location OID to find all voltage probes
        print("\nVoltage Probe Locations:")
        voltage_locations = await self.walk_oid_tree(IDRAC_OIDS["psu_location"], 50)  # Note: using psu_location as it's the voltage probe location OID
        
        psu_voltage_indices = []
        other_voltage_indices = []
        
        for oid, location in voltage_locations:
            # Extract index from OID
            index = oid.split('.')[-1]
            location_lower = location.lower() if location else ""
            
            # Check if this is PSU-related
            if any(term in location_lower for term in ["ps1", "ps2", "ps3", "psu", "power supply"]):
                psu_voltage_indices.append((index, location))
                print(f"  [PSU] Index {index}: {location}")
            else:
                other_voltage_indices.append((index, location))
                if len(other_voltage_indices) <= 10:  # Show first 10 non-PSU
                    print(f"  [Other] Index {index}: {location}")
        
        if len(other_voltage_indices) > 10:
            print(f"  ... and {len(other_voltage_indices) - 10} more non-PSU voltage probes")
        
        # Get PSU voltage details
        print("\nPSU Voltage Probe Details:")
        for idx, location in psu_voltage_indices:
            print(f"\n  {location} (Index {idx}):")
            
            # Get voltage reading
            voltage_oid = f"{IDRAC_OIDS['psu_input_voltage']}.{idx}"
            voltage = await self.snmp_get(voltage_oid)
            
            # Convert voltage (often in millivolts)
            try:
                voltage_mv = int(voltage) if voltage else 0
                voltage_v = voltage_mv / 1000.0 if voltage_mv > 1000 else voltage_mv
                print(f"    Reading: {voltage} ({voltage_v} V)")
            except:
                print(f"    Reading: {voltage}")
            
            # Get status
            status_oid = f"{IDRAC_OIDS['psu_voltage_status']}.{idx}" if 'psu_voltage_status' in IDRAC_OIDS else f"1.3.6.1.4.1.674.10892.5.4.600.20.1.5.1.{idx}"
            status = await self.snmp_get(status_oid)
            print(f"    Status: {status}")
        
        # 4. Look for additional voltage data in system voltages
        print("\n\n4. CHECKING SYSTEM VOLTAGE SENSORS:")
        print("-" * 50)
        
        # Check if there are system voltage OIDs that might contain PSU voltages
        if "system_voltage_reading" in IDRAC_OIDS:
            system_voltages = await self.walk_oid_tree(IDRAC_OIDS["system_voltage_reading"], 30)
            print(f"\nFound {len(system_voltages)} system voltage readings")
            
            for oid, value in system_voltages[:10]:
                index = oid.split('.')[-1]
                # Get location name
                location_oid = f"{IDRAC_OIDS.get('system_voltage_location', '1.3.6.1.4.1.674.10892.5.4.600.30.1.8.1')}.{index}"
                location = await self.snmp_get(location_oid)
                
                if location and any(term in location.lower() for term in ["ps1", "ps2", "ps3", "psu"]):
                    print(f"  [PSU] {location}: {value}")
        
        # 5. Direct check for known PSU voltage probe indices
        print("\n\n5. CHECKING SPECIFIC PSU VOLTAGE INDICES:")
        print("-" * 50)
        
        # Based on the Redfish debug, we found PS1 Voltage at index 41 and PS2 Voltage at index 42
        # Let's check if these indices work in SNMP
        known_psu_indices = [
            (41, "PS1 Voltage 1"),
            (42, "PS2 Voltage 2"),
        ]
        
        for idx, expected_name in known_psu_indices:
            print(f"\nChecking index {idx} (expected: {expected_name}):")
            
            # Get location
            location_oid = f"{IDRAC_OIDS['psu_location']}.{idx}"
            location = await self.snmp_get(location_oid)
            print(f"  Location: {location}")
            
            # Get voltage
            voltage_oid = f"{IDRAC_OIDS['psu_input_voltage']}.{idx}"
            voltage = await self.snmp_get(voltage_oid)
            
            if voltage:
                try:
                    voltage_mv = int(voltage)
                    voltage_v = voltage_mv / 1000.0 if voltage_mv > 1000 else voltage_mv
                    print(f"  Voltage: {voltage} ({voltage_v} V)")
                except:
                    print(f"  Voltage: {voltage}")
        
        # 6. Summary
        print("\n\n6. SUMMARY:")
        print("-" * 50)
        
        print(f"PSUs found in PSU table: {len(psu_indices)}")
        print(f"PSU-related voltage probes: {len(psu_voltage_indices)}")
        
        if psu_voltage_indices:
            print("\nPSU Voltage Readings via SNMP:")
            for idx, location in psu_voltage_indices:
                voltage_oid = f"{IDRAC_OIDS['psu_input_voltage']}.{idx}"
                voltage = await self.snmp_get(voltage_oid)
                try:
                    voltage_mv = int(voltage) if voltage else 0
                    voltage_v = voltage_mv / 1000.0 if voltage_mv > 1000 else voltage_mv
                    print(f"  {location}: {voltage_v} V")
                except:
                    print(f"  {location}: {voltage}")
        
        print("\n7. COMPARISON WITH REDFISH:")
        print("-" * 50)
        print("Redfish PowerSupplies.LineInputVoltage:")
        print("  PSU 1: 118 V")
        print("  PSU 2: 124 V")
        
        if psu_voltage_indices:
            print("\n✅ SNMP appears to have PSU voltage data")
            print("   Check if the values match Redfish data above")
        else:
            print("\n⚠️  No PSU-specific voltage probes found via SNMP walk")
            print("   Checking specific indices 41 and 42 that work in Redfish...")


async def main():
    """Main entry point."""
    try:
        debugger = SNMPPSUVoltageDebugger()
        await debugger.debug_psu_voltages()
    except Exception as exc:
        logger.error(f"Failed to run debugger: {exc}", exc_info=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())