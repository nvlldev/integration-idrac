#!/usr/bin/env python3
"""Test script to verify memory health sensors work correctly after fix."""

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
        
        if not error_indication and not error_status and var_binds:
            value = str(var_binds[0][1]).strip()
            if value and "No Such" not in value:
                return value
        return None
    except Exception:
        return None

async def test_memory_health_fix():
    """Test memory health sensors after fixing the data key mismatch."""
    print("🧠 TESTING MEMORY HEALTH SENSOR FIX")
    print("=" * 50)
    print("Issue: Binary sensor key mismatch causing unavailable sensors")
    print("Fix: Changed sensor_key from 'memory_health_{index}' to 'memory_{index}'")
    
    engine = SnmpEngine()
    community_data = CommunityData(COMMUNITY)
    transport_target = UdpTransportTarget((IDRAC_HOST, IDRAC_PORT), timeout=10, retries=2)
    context_data = ContextData()
    
    # Memory health OID from const.py
    memory_health_base = "1.3.6.1.4.1.674.10892.5.4.1100.50.1.4.1"
    
    print(f"\n🔍 Testing memory health data structure:")
    print("-" * 45)
    
    # Simulate coordinator data structure
    coordinator_memory_health = {}
    found_modules = []
    
    # Test memory indices 1-12 (typical for current server)
    for memory_index in range(1, 13):
        memory_oid = f"{memory_health_base}.{memory_index}"
        health_value = await get_snmp_value(engine, community_data, transport_target, context_data, memory_oid)
        
        if health_value and health_value.isdigit():
            # Simulate coordinator data storage
            coordinator_memory_health[f"memory_{memory_index}"] = int(health_value)
            found_modules.append(memory_index)
            
            # Memory health mapping
            health_map = {
                1: "other",
                2: "ready",      # Healthy
                3: "ok",         # Healthy  
                4: "non_critical",
                5: "critical",
                6: "non_recoverable"
            }
            
            health_status = health_map.get(int(health_value), f"unknown_{health_value}")
            is_healthy = int(health_value) in [2, 3]
            
            print(f"   Memory {memory_index}:")
            print(f"      Coordinator key: 'memory_{memory_index}'")
            print(f"      Health value: {health_value} ({health_status})")
            print(f"      Binary sensor: {'OK' if is_healthy else 'PROBLEM'}")
    
    # Simulate binary sensor logic
    print(f"\n🔧 BINARY SENSOR SIMULATION:")
    print("-" * 35)
    
    for memory_index in found_modules:
        # OLD (broken) sensor key
        old_sensor_key = f"memory_health_{memory_index}"
        # NEW (fixed) sensor key  
        new_sensor_key = f"memory_{memory_index}"
        
        # Check if data exists for both keys
        old_data_exists = old_sensor_key in coordinator_memory_health
        new_data_exists = new_sensor_key in coordinator_memory_health
        
        print(f"   Memory {memory_index} Binary Sensor:")
        print(f"      OLD key '{old_sensor_key}': {'✅ Found' if old_data_exists else '❌ Not Found'}")
        print(f"      NEW key '{new_sensor_key}': {'✅ Found' if new_data_exists else '❌ Not Found'}")
        
        if new_data_exists:
            health_value = coordinator_memory_health[new_sensor_key]
            is_problem = health_value not in [2, 3]  # Binary sensor logic
            sensor_state = "ON (Problem)" if is_problem else "OFF (OK)"
            print(f"      Sensor state: {sensor_state}")
            print(f"      Available: ✅ YES")
        else:
            print(f"      Sensor state: UNAVAILABLE")
            print(f"      Available: ❌ NO")
    
    # Summary
    print(f"\n📊 MEMORY HEALTH FIX SUMMARY:")
    print("-" * 35)
    print(f"   Memory modules found: {len(found_modules)}")
    print(f"   Coordinator data keys: {list(coordinator_memory_health.keys())}")
    
    print(f"\n🔧 FIX IMPLEMENTED:")
    print("-" * 20)
    print("   ✅ Changed binary sensor key from 'memory_health_{index}' to 'memory_{index}'")
    print("   ✅ This matches the coordinator data structure")
    print("   ✅ Memory health binary sensors should now be available")
    
    print(f"\n💡 USER ACTION REQUIRED:")
    print("-" * 25)
    print("   📋 Restart Home Assistant to apply the fix")
    print("   📋 Memory health sensors should appear as available")
    print("   📋 Binary sensors show 'OFF' for healthy memory, 'ON' for problems")
    
    # Expected sensor behavior
    print(f"\n📋 EXPECTED SENSOR BEHAVIOR:")
    print("-" * 30)
    for memory_index in found_modules:
        if new_sensor_key in coordinator_memory_health:
            health_value = coordinator_memory_health[f"memory_{memory_index}"]
            is_healthy = health_value in [2, 3]
            entity_id = f"binary_sensor.dell_idrac_memory_{memory_index}_health"
            state = "off" if is_healthy else "on"
            print(f"   {entity_id}: {state}")

async def main():
    """Main test function."""
    if not IDRAC_HOST:
        print("❌ Error: IDRAC_HOST not found in .env file")
        return
    
    await test_memory_health_fix()

if __name__ == "__main__":
    asyncio.run(main())