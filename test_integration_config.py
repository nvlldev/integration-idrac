#!/usr/bin/env python3
"""Test script to check what sensors are actually configured in the integration."""

import asyncio
import os
from dotenv import load_dotenv
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
load_dotenv()

IDRAC_HOST = os.getenv("IDRAC_HOST")
IDRAC_PORT = int(os.getenv("IDRAC_PORT", "161"))
COMMUNITY = os.getenv("IDRAC_COMMUNITY", "public")

async def test_integration_behavior():
    """Test what the integration should see."""
    print("🔧 TESTING INTEGRATION BEHAVIOR")
    print("=" * 50)
    
    engine = SnmpEngine()
    community_data = CommunityData(COMMUNITY)
    transport_target = UdpTransportTarget((IDRAC_HOST, IDRAC_PORT), timeout=10, retries=2)
    context_data = ContextData()
    
    # Simulate what the coordinator would do for CPU temperatures
    print("\n🌡️ CPU Temperature Sensors:")
    print("-" * 35)
    
    # Based on our discovery, CPU sensors should be at indices 3 and 4
    discovered_cpus = [3, 4]  # This is what discovery should return
    
    temp_cpu_base = "1.3.6.1.4.1.674.10892.5.4.700.20.1.6.1"
    
    for cpu_index in discovered_cpus:
        cpu_oid = f"{temp_cpu_base}.{cpu_index}"
        
        try:
            error_indication, error_status, error_index, var_binds = await getCmd(
                engine,
                community_data,
                transport_target,
                context_data,
                ObjectType(ObjectIdentity(cpu_oid)),
            )
            
            if not error_indication and not error_status and var_binds:
                raw_value = float(var_binds[0][1])
                cpu_value = raw_value / 10  # Same as coordinator logic
                
                if cpu_value > 0:
                    print(f"   CPU {cpu_index}: {cpu_value}°C (raw: {raw_value})")
                    print(f"      → Would create sensor: cpu_{cpu_index}")
                    print(f"      → Entity ID: sensor.dell_idrac_cpu_{cpu_index}_temperature")
                else:
                    print(f"   CPU {cpu_index}: Invalid value {cpu_value}°C")
        except Exception as e:
            print(f"   CPU {cpu_index}: Error - {e}")
    
    print(f"\n📊 SUMMARY:")
    print("-" * 15)
    print(f"   Expected CPU sensors: {len(discovered_cpus)}")
    print(f"   CPU indices: {discovered_cpus}")
    
    print(f"\n💡 TROUBLESHOOTING:")
    print("-" * 20)
    print("   If you only see one CPU sensor in Home Assistant:")
    print("   1. The integration may have been added before discovery was fixed")
    print("   2. Delete the iDRAC integration from Settings → Devices & Services")
    print("   3. Re-add the integration to trigger fresh discovery")
    print("   4. Both CPU sensors should then appear")
    
    # Check temperature names for context
    print(f"\n📋 Temperature Sensor Names:")
    print("-" * 35)
    
    temp_name_base = "1.3.6.1.4.1.674.10892.5.4.700.20.1.8.1"
    
    for i in range(1, 5):
        name_oid = f"{temp_name_base}.{i}"
        try:
            error_indication, error_status, error_index, var_binds = await getCmd(
                engine,
                community_data,
                transport_target,
                context_data,
                ObjectType(ObjectIdentity(name_oid)),
            )
            
            if not error_indication and not error_status and var_binds:
                name = str(var_binds[0][1]).strip()
                if name and "No Such" not in name:
                    sensor_type = "Other"
                    if i in discovered_cpus:
                        sensor_type = "CPU (should be discovered)"
                    elif i <= 2:
                        sensor_type = "System (inlet/exhaust)"
                    
                    print(f"   Index {i}: {name} [{sensor_type}]")
        except Exception:
            pass

async def main():
    """Main test function."""
    if not IDRAC_HOST:
        print("❌ Error: IDRAC_HOST not found in .env file")
        return
    
    await test_integration_behavior()

if __name__ == "__main__":
    asyncio.run(main())