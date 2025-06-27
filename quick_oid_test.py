#!/usr/bin/env python3
"""Quick test of candidate OIDs found in the discovery."""

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

async def test_oid(engine, community_data, transport_target, context_data, name, oid):
    """Test a single OID."""
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
                print(f"✅ {name}: {value} (OID: {oid})")
                return oid, value
            else:
                print(f"❌ {name}: No valid data")
                return None, None
        else:
            print(f"❌ {name}: SNMP error")
            return None, None
    except Exception as e:
        print(f"❌ {name}: Exception {e}")
        return None, None

async def test_with_indices(engine, community_data, transport_target, context_data, name, base_oid, max_index=10):
    """Test an OID with different indices."""
    print(f"\n🔍 Testing {name} with indices:")
    working_oids = []
    
    for i in range(1, max_index + 1):
        oid = f"{base_oid}.{i}"
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
                    print(f"   ✅ Index {i}: {value}")
                    working_oids.append((oid, value))
        except:
            continue
    
    return working_oids

async def main():
    """Test promising candidate OIDs."""
    print(f"🧪 Testing Candidate OIDs on {IDRAC_HOST}:{IDRAC_PORT}")
    print("=" * 70)
    
    engine = SnmpEngine()
    community_data = CommunityData(COMMUNITY)
    transport_target = UdpTransportTarget((IDRAC_HOST, IDRAC_PORT), timeout=10, retries=2)
    context_data = ContextData()

    # Test the discovered working OIDs with variations
    candidates = {
        "System Model/Chassis Names": [
            "1.3.6.1.4.1.674.10892.5.4.300.10.1.7.1",      # Found: Main System Chassis
            "1.3.6.1.4.1.674.10892.5.4.300.10.1.9.1.1",    # Original alt 1
            "1.3.6.1.4.1.674.10892.5.4.300.10.1.8.1.1",    # Try different column
            "1.3.6.1.4.1.674.10892.5.4.300.10.1.11.1.1",   # Try different column
        ],
        "BIOS/System Version": [
            "1.3.6.1.4.1.674.10892.5.1.3.7.0",             # Found: 4
            "1.3.6.1.4.1.674.10892.5.1.3.5.0",             # Try different index
            "1.3.6.1.4.1.674.10892.5.1.3.8.0",             # Try different index
            "1.3.6.1.4.1.674.10892.5.1.3.6.0",             # Original BIOS version
        ],
        "Power State": [
            "1.3.6.1.4.1.674.10892.5.4.300.70.1.6.1.1",    # Found: 1
            "1.3.6.1.4.1.674.10892.5.4.200.10.1.6.1",      # Found: 3
            "1.3.6.1.4.1.674.10892.5.4.300.70.1.6.1.2",    # Try different index
            "1.3.6.1.4.1.674.10892.5.4.300.70.1.6.1.3",    # Original failing OID
        ],
        "Memory Health": [
            "1.3.6.1.4.1.674.10892.5.4.1100.50.1.4.1.1",   # Found: 2
            "1.3.6.1.4.1.674.10892.5.4.1100.50.1.5.1.1",   # Try our updated OID
            "1.3.6.1.4.1.674.10892.5.4.1100.50.1.6.1.1",   # Try another column
        ],
        "Voltage Sensors": [
            "1.3.6.1.4.1.674.10892.5.4.600.20.1.5.1.1",    # Found: 3 (status)
            "1.3.6.1.4.1.674.10892.5.4.600.20.1.6.1.1",    # Reading (voltage value)
            "1.3.6.1.4.1.674.10892.5.4.700.10.1.6.1.1",    # Found: 0
        ],
        "System Intrusion": [
            "1.3.6.1.4.1.674.10892.5.4.300.70.1.25.1.1",   # Original failing
            "1.3.6.1.4.1.674.10892.5.4.300.70.1.24.1.1",   # Alternative
            "1.3.6.1.4.1.674.10892.5.4.300.70.1.26.1.1",   # Try different column
        ],
        "PSU Redundancy": [
            "1.3.6.1.4.1.674.10892.5.4.600.10.1.9.1.1",    # Original failing
            "1.3.6.1.4.1.674.10892.5.4.600.10.1.8.1.1",    # Alternative
            "1.3.6.1.4.1.674.10892.5.4.600.10.1.10.1.1",   # Try different column
        ],
        "Control OIDs": [
            "1.3.6.1.4.1.674.10892.5.4.300.70.1.5.1.1",    # Try different index
            "1.3.6.1.4.1.674.10892.5.4.300.70.1.10.1.1",   # Try different index
            "1.3.6.1.4.1.674.10892.5.4.300.70.1.11.1.1",   # Try different index
        ]
    }
    
    working_oids = {}
    
    for category, test_oids in candidates.items():
        print(f"\n🧪 {category}:")
        category_working = []
        
        for oid in test_oids:
            name = f"Test {oid.split('.')[-1]}"
            result_oid, value = await test_oid(engine, community_data, transport_target, context_data, name, oid)
            if result_oid:
                category_working.append((result_oid, value))
        
        working_oids[category] = category_working
    
    # Test memory health with multiple indices
    memory_working = await test_with_indices(engine, community_data, transport_target, context_data, 
                                           "Memory Health", "1.3.6.1.4.1.674.10892.5.4.1100.50.1.4.1", 20)
    
    # Test voltage sensors with multiple indices  
    voltage_working = await test_with_indices(engine, community_data, transport_target, context_data,
                                            "Voltage Sensors", "1.3.6.1.4.1.674.10892.5.4.600.20.1.6.1", 10)
    
    # Print summary of discoveries
    print(f"\n" + "=" * 70)
    print("📊 WORKING OID SUMMARY")
    print("=" * 70)
    
    for category, oids in working_oids.items():
        if oids:
            print(f"\n✅ {category}:")
            for oid, value in oids:
                print(f"   {oid}: {value}")
        else:
            print(f"\n❌ {category}: No working OIDs found")
    
    if memory_working:
        print(f"\n✅ Memory Health (with indices):")
        for oid, value in memory_working:
            print(f"   {oid}: {value}")
    
    if voltage_working:
        print(f"\n✅ Voltage Sensors (with indices):")
        for oid, value in voltage_working:
            print(f"   {oid}: {value}")
    
    # Generate updated const.py suggestions
    print(f"\n" + "=" * 70)
    print("🔧 SUGGESTED CONST.PY UPDATES")
    print("=" * 70)
    
    suggestions = []
    
    # Find best model name OID
    for oid, value in working_oids.get("System Model/Chassis Names", []):
        if "chassis" in value.lower() and "main" in value.lower():
            suggestions.append(f'    "system_model_name": "{oid}",  # {value}')
            break
    
    # Find best power state OID
    for oid, value in working_oids.get("Power State", []):
        if oid.endswith(".1.1") and value == "1":  # Likely power on state
            suggestions.append(f'    "system_power_state": "{oid}",  # Power state: {value}')
            break
    
    # Find memory health base
    if memory_working:
        base_oid = memory_working[0][0].rsplit('.', 1)[0]  # Remove last index
        suggestions.append(f'    "memory_health_base": "{base_oid}",  # Memory device status')
    
    # Find voltage sensor base
    if voltage_working:
        base_oid = voltage_working[0][0].rsplit('.', 1)[0]  # Remove last index
        suggestions.append(f'    "psu_voltage_base": "{base_oid}",  # Voltage readings')
    
    if suggestions:
        print("Recommended updates:")
        for suggestion in suggestions:
            print(suggestion)
    else:
        print("No clear improvements found for const.py")

if __name__ == "__main__":
    asyncio.run(main())