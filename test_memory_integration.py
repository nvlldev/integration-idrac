#!/usr/bin/env python3
"""Test script to simulate how memory health sensors will work in the integration."""

import asyncio
import os
import sys
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

# Import the memory health configuration
sys.path.append(os.path.join(os.path.dirname(__file__), "custom_components", "idrac"))
from const import IDRAC_OIDS

async def test_memory_like_coordinator():
    """Test memory health collection like the coordinator does."""
    print(f"🧠 Testing Memory Health Collection (Coordinator Simulation)")
    print(f"Target: {IDRAC_HOST}:{IDRAC_PORT}")
    print("=" * 70)
    
    engine = SnmpEngine()
    community_data = CommunityData(COMMUNITY)
    transport_target = UdpTransportTarget((IDRAC_HOST, IDRAC_PORT), timeout=10, retries=2)
    context_data = ContextData()

    async def _async_get_snmp_value(oid: str) -> float | None:
        """Simulate coordinator's SNMP value getter."""
        try:
            error_indication, error_status, error_index, var_binds = await getCmd(
                engine,
                community_data,
                transport_target,
                context_data,
                ObjectType(ObjectIdentity(oid)),
            )

            if error_indication or error_status:
                return None

            if var_binds:
                try:
                    value = float(var_binds[0][1])
                    return value
                except (ValueError, TypeError):
                    return None
            return None
        except:
            return None

    # Simulate discovered memory modules (from our test results)
    discovered_memory = [1, 2, 3, 4, 5, 6, 7, 8]
    
    print(f"📋 Simulating coordinator memory health collection:")
    print(f"Discovered memory modules: {discovered_memory}")
    print("-" * 50)
    
    memory_data = {}
    
    # Simulate the coordinator's memory health collection logic
    for memory_index in discovered_memory:
        print(f"\n🔍 Processing Memory Module {memory_index}:")
        
        # Try multiple memory health OID bases with correct double indexing
        memory_oid_bases = [
            IDRAC_OIDS['memory_health_base'],                 # Primary: 1.3.6.1.4.1.674.10892.5.4.1100.50.1.4.1
            IDRAC_OIDS['memory_health_base_alt'],             # Alternative: 1.3.6.1.4.1.674.10892.5.4.1100.50.1.5.1  
            "1.3.6.1.4.1.674.10892.5.4.1100.50.1.6.1",       # Alternative memory health status (double-indexed)
            "1.3.6.1.4.1.674.10892.5.4.1100.50.1.20.1",      # Memory device status (double-indexed)
        ]
        
        health_value = None
        working_oid = None
        
        for i, oid_base in enumerate(memory_oid_bases):
            # Memory OIDs use double indexing: base_oid.{memory_index} where base already includes .1
            memory_oid = f"{oid_base}.{memory_index}"
            health_value = await _async_get_snmp_value(memory_oid)
            
            if health_value is not None:
                working_oid = memory_oid
                print(f"   ✅ OID {i+1}: {memory_oid} -> {health_value}")
                break
            else:
                print(f"   ❌ OID {i+1}: {memory_oid} -> No response")
        
        if health_value is not None:
            memory_data[f"memory_{memory_index}"] = health_value
            print(f"   ✅ Memory {memory_index} health: {health_value} (using {working_oid})")
        else:
            print(f"   ❌ Memory {memory_index}: No valid health data from any OID")
    
    # Simulate how binary sensors would interpret the data
    print(f"\n" + "=" * 70)
    print("🔧 Binary Sensor Interpretation")
    print("=" * 70)
    
    # Memory health state mapping (updated from binary_sensor.py)
    memory_state_map = {
        1: "other",
        2: "ready", 
        3: "ok",
        4: "non_critical",
        5: "critical",
        6: "non_recoverable"
    }
    
    print(f"\nMemory Health Sensor States:")
    for key, value in memory_data.items():
        memory_index = key.split("_")[1]
        try:
            state_int = int(value)
            state_text = memory_state_map.get(state_int, f"unknown_{state_int}")
            
            # Determine if sensor would show as "on" (problem) or "off" (healthy)
            # Updated logic: 2=ready and 3=ok are both healthy (sensor off)
            is_healthy = state_int in [2, 3]
            status_icon = "🟢" if is_healthy else "🔴"
            
            print(f"   {status_icon} Memory Module {memory_index}: {state_text} (raw: {value})")
            
        except (ValueError, TypeError):
            print(f"   ❓ Memory Module {memory_index}: Invalid value ({value})")
    
    # Summary
    print(f"\n" + "=" * 70)
    print("📊 SUMMARY")
    print("=" * 70)
    
    total_modules = len(discovered_memory)
    working_modules = len(memory_data)
    healthy_modules = sum(1 for v in memory_data.values() if int(v) in [2, 3])
    
    print(f"Total memory modules discovered: {total_modules}")
    print(f"Memory modules with working health data: {working_modules}")
    print(f"Memory modules reporting healthy (state 2 or 3): {healthy_modules}")
    print(f"Success rate: {working_modules}/{total_modules} ({working_modules/total_modules*100:.1f}%)")
    
    if working_modules == total_modules:
        print(f"🎉 SUCCESS: All memory health sensors should now work in Home Assistant!")
    else:
        print(f"⚠️  PARTIAL: {total_modules - working_modules} sensors may still show as unavailable")
    
    return memory_data

if __name__ == "__main__":
    asyncio.run(test_memory_like_coordinator())