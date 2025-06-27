#!/usr/bin/env python3
"""Test what the current CPU discovery actually finds."""

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

async def _discover_sensors(
    engine: SnmpEngine,
    community_data: CommunityData,
    transport_target: UdpTransportTarget,
    context_data: ContextData,
    base_oid: str,
) -> list[int]:
    """Copy of the config flow sensor discovery function."""
    results = []
    
    try:
        print(f"🔍 Testing individual OIDs for base: {base_oid}")
        
        # Test up to 20 sensor indices (should be more than enough for any server)
        for sensor_id in range(1, 21):
            test_oid = f"{base_oid}.{sensor_id}"
            try:
                error_indication, error_status, error_index, var_binds = await getCmd(
                    engine,
                    community_data,
                    transport_target,
                    context_data,
                    ObjectType(ObjectIdentity(test_oid)),
                )
                
                if not error_indication and not error_status and var_binds:
                    value = var_binds[0][1]
                    if (value is not None 
                        and str(value) != "No Such Object currently exists at this OID"
                        and str(value) != "No Such Instance currently exists at this OID"):
                        try:
                            # Try to convert to a numeric value to ensure it's a valid sensor reading
                            numeric_value = float(value)
                            if numeric_value > 0:  # Only include sensors with positive values
                                results.append(sensor_id)
                                print(f"   ✅ Found sensor ID {sensor_id} at OID {test_oid} with value: {value}")
                            else:
                                print(f"   ❌ Sensor ID {sensor_id} at OID {test_oid} has invalid value: {value}")
                        except (ValueError, TypeError):
                            print(f"   ⚠️  Sensor ID {sensor_id} at OID {test_oid} has non-numeric value: {value}")
                
            except Exception as exc:
                print(f"   ❌ Error testing OID {test_oid}: {exc}")
                continue

        print(f"📊 Discovery for {base_oid} found {len(results)} sensors: {results}")
        results.sort()
        
    except Exception as exc:
        print(f"❌ Error discovering sensors for OID {base_oid}: {exc}")
    
    return results

async def _discover_cpu_sensors(
    engine: SnmpEngine,
    community_data: CommunityData,
    transport_target: UdpTransportTarget,
    context_data: ContextData,
    base_oid: str,
) -> list[int]:
    """Copy of the config flow CPU discovery function."""
    all_temp_sensors = await _discover_sensors(
        engine, community_data, transport_target, context_data, base_oid
    )
    
    cpu_sensors = [sensor_id for sensor_id in all_temp_sensors if sensor_id > 2]
    print(f"🌡️ CPU sensors (filtered to index > 2): {cpu_sensors}")
    return cpu_sensors

async def test_current_discovery():
    """Test what the current discovery logic finds."""
    print("🧪 TESTING CURRENT CPU DISCOVERY LOGIC")
    print("=" * 60)
    
    engine = SnmpEngine()
    community_data = CommunityData(COMMUNITY)
    transport_target = UdpTransportTarget((IDRAC_HOST, IDRAC_PORT), timeout=10, retries=2)
    context_data = ContextData()
    
    # Use the same OID base as config_flow
    cpu_temp_base_oid = "1.3.6.1.4.1.674.10892.5.4.700.20.1.6.1"  # SNMP_WALK_OIDS["cpu_temps"]
    
    print(f"\n🔍 Running discovery on base OID: {cpu_temp_base_oid}")
    print("-" * 60)
    
    discovered_cpus = await _discover_cpu_sensors(
        engine, community_data, transport_target, context_data, cpu_temp_base_oid
    )
    
    print(f"\n📋 FINAL RESULTS:")
    print("-" * 20)
    print(f"   Discovered CPU sensors: {discovered_cpus}")
    
    if len(discovered_cpus) >= 2:
        print("   ✅ Multiple CPU sensors found - discovery working correctly!")
    elif len(discovered_cpus) == 1:
        print("   ⚠️  Only one CPU sensor found - may need to expand range")
    else:
        print("   ❌ No CPU sensors found - discovery problem")

async def main():
    """Main test function."""
    if not IDRAC_HOST:
        print("❌ Error: IDRAC_HOST not found in .env file")
        return
    
    await test_current_discovery()

if __name__ == "__main__":
    asyncio.run(main())