#!/usr/bin/env python3
"""
Debug script to explore PSU voltage data sources in Dell iDRAC Redfish API.
This script will examine all voltage-related data to find the correct PSU input voltage readings.
"""

import asyncio
import json
import logging
import os
import sys
from typing import Any, Dict

from dotenv import load_dotenv

# Add the custom_components path to import our modules
sys.path.insert(0, 'custom_components')

from idrac.redfish.redfish_client import RedfishClient

# Load environment variables
load_dotenv('.env.local')

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PSUVoltageDebugger:
    """Debug PSU voltage data sources in iDRAC Redfish API."""
    
    def __init__(self):
        self.host = os.getenv('IDRAC_HOST')
        self.username = os.getenv('IDRAC_USERNAME')
        self.password = os.getenv('IDRAC_PASSWORD')
        self.port = int(os.getenv('IDRAC_HTTPS_PORT', 443))
        
        if not all([self.host, self.username, self.password]):
            raise ValueError("Missing required environment variables. Check .env.local file.")
        
        logger.info(f"Connecting to iDRAC at {self.host}:{self.port}")
        
    async def debug_psu_voltages(self):
        """Explore all PSU and voltage data sources."""
        
        # Create a mock Home Assistant instance for the client
        class MockHass:
            pass
        
        hass = MockHass()
        
        client = RedfishClient(
            hass, self.host, self.username, self.password, 
            self.port, verify_ssl=False, request_timeout=30, session_timeout=300
        )
        
        try:
            print("\n" + "="*80)
            print("DELL iDRAC PSU VOLTAGE DEBUG SCRIPT")
            print("="*80)
            
            # 1. Get service root to verify connection
            print("\n1. Testing Redfish connection...")
            service_root = await client.get_service_root()
            if not service_root:
                print("❌ Failed to connect to Redfish service")
                return
            print("✅ Connected to Redfish service successfully")
            
            # 2. Get power data
            print("\n2. Fetching power data...")
            power_data = await client.get_power_info()
            if not power_data:
                print("❌ Failed to get power data")
                return
            
            print("✅ Retrieved power data successfully")
            
            # 3. Analyze PowerSupplies array
            print("\n3. ANALYZING POWERSUPPLIES ARRAY:")
            print("-" * 50)
            power_supplies = power_data.get("PowerSupplies", [])
            
            if not power_supplies:
                print("❌ No PowerSupplies found in power data")
            else:
                for i, psu in enumerate(power_supplies):
                    print(f"\nPSU {i+1} ({psu.get('Name', 'Unknown')}):")
                    print(f"  Status: {psu.get('Status', {}).get('Health', 'Unknown')}")
                    print(f"  State: {psu.get('Status', {}).get('State', 'Unknown')}")
                    print(f"  LineInputVoltage: {psu.get('LineInputVoltage')} V")
                    print(f"  PowerInputWatts: {psu.get('PowerInputWatts')} W")
                    print(f"  PowerOutputWatts: {psu.get('PowerOutputWatts')} W")
                    print(f"  PowerCapacityWatts: {psu.get('PowerCapacityWatts')} W")
                    print(f"  Model: {psu.get('Model', 'Unknown')}")
                    print(f"  Manufacturer: {psu.get('Manufacturer', 'Unknown')}")
            
            # 4. Analyze Voltages array
            print("\n\n4. ANALYZING VOLTAGES ARRAY:")
            print("-" * 50)
            voltages = power_data.get("Voltages", [])
            
            if not voltages:
                print("❌ No Voltages found in power data")
            else:
                psu_voltages = []
                other_voltages = []
                
                for i, voltage in enumerate(voltages):
                    voltage_name = voltage.get("Name", f"Voltage {i+1}")
                    voltage_value = voltage.get("ReadingVolts")
                    voltage_status = voltage.get("Status", {}).get("Health", "Unknown")
                    
                    voltage_info = {
                        "index": i,
                        "name": voltage_name,
                        "value": voltage_value,
                        "status": voltage_status,
                        "raw_data": voltage
                    }
                    
                    # Check if this looks like a PSU voltage
                    name_lower = voltage_name.lower() if voltage_name else ""
                    if any(term in name_lower for term in ["ps1", "ps2", "ps3", "psu", "power supply"]):
                        psu_voltages.append(voltage_info)
                    else:
                        other_voltages.append(voltage_info)
                
                # Display PSU-related voltages
                print(f"\nPSU-RELATED VOLTAGES ({len(psu_voltages)} found):")
                if psu_voltages:
                    for v in psu_voltages:
                        print(f"  [{v['index']}] {v['name']}: {v['value']} V (Status: {v['status']})")
                        
                        # Show additional fields that might be relevant
                        extra_fields = {}
                        for key, value in v['raw_data'].items():
                            if key not in ['Name', 'ReadingVolts', 'Status'] and value is not None:
                                extra_fields[key] = value
                        
                        if extra_fields:
                            print(f"       Additional fields: {extra_fields}")
                else:
                    print("  No PSU-related voltages found")
                
                # Display other voltages for context
                print(f"\nOTHER VOLTAGES ({len(other_voltages)} found):")
                for v in other_voltages[:10]:  # Show first 10 to avoid spam
                    print(f"  [{v['index']}] {v['name']}: {v['value']} V (Status: {v['status']})")
                
                if len(other_voltages) > 10:
                    print(f"  ... and {len(other_voltages) - 10} more")
            
            # 5. Look for other potential voltage sources
            print("\n\n5. CHECKING FOR OTHER VOLTAGE SOURCES:")
            print("-" * 50)
            
            # Check if there are any other relevant fields in power data
            other_fields = {}
            for key, value in power_data.items():
                if key not in ['PowerSupplies', 'Voltages', 'PowerControl'] and value:
                    other_fields[key] = value
            
            if other_fields:
                print("Other fields in power data:")
                for key, value in other_fields.items():
                    print(f"  {key}: {type(value).__name__}")
                    if isinstance(value, (list, dict)) and len(str(value)) < 200:
                        print(f"    Content: {value}")
            else:
                print("No other relevant fields found in power data")
            
            # 6. Summary and recommendations
            print("\n\n6. ANALYSIS SUMMARY:")
            print("-" * 50)
            
            print(f"PowerSupplies found: {len(power_supplies)}")
            if power_supplies:
                for i, psu in enumerate(power_supplies):
                    line_voltage = psu.get('LineInputVoltage')
                    print(f"  PSU {i+1}: LineInputVoltage = {line_voltage} V")
            
            print(f"\nPSU-related voltage sensors: {len(psu_voltages) if 'psu_voltages' in locals() else 0}")
            if 'psu_voltages' in locals() and psu_voltages:
                for v in psu_voltages:
                    print(f"  {v['name']}: {v['value']} V")
            
            # Recommendations
            print("\n7. RECOMMENDATIONS:")
            print("-" * 50)
            
            if power_supplies and all(psu.get('LineInputVoltage') for psu in power_supplies):
                print("✅ RECOMMENDATION: Use PowerSupplies.LineInputVoltage")
                print("   This appears to be the authoritative source for PSU input voltage")
                for i, psu in enumerate(power_supplies):
                    voltage = psu.get('LineInputVoltage')
                    print(f"   PSU {i+1}: {voltage} V")
            
            elif 'psu_voltages' in locals() and psu_voltages:
                print("⚠️  RECOMMENDATION: Investigate Voltages array sensors")
                print("   PowerSupplies.LineInputVoltage not available, check these sensors:")
                for v in psu_voltages:
                    print(f"   {v['name']}: {v['value']} V")
            
            else:
                print("❌ PROBLEM: No reliable PSU input voltage source found")
                print("   Neither PowerSupplies.LineInputVoltage nor PSU voltage sensors found")
            
            # 8. Save raw data for further analysis
            debug_data = {
                "power_supplies": power_supplies,
                "voltages": voltages,
                "other_power_fields": other_fields,
                "timestamp": str(asyncio.get_event_loop().time())
            }
            
            with open("psu_voltage_debug.json", "w") as f:
                json.dump(debug_data, f, indent=2, default=str)
            
            print(f"\n📄 Raw data saved to: psu_voltage_debug.json")
            
        except Exception as exc:
            logger.error(f"Error during debugging: {exc}", exc_info=True)
            
        finally:
            await client.close()

async def main():
    """Main entry point."""
    try:
        debugger = PSUVoltageDebugger()
        await debugger.debug_psu_voltages()
    except Exception as exc:
        logger.error(f"Failed to run debugger: {exc}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())