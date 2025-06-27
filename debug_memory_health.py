#!/usr/bin/env python3
"""Debug script to find the correct memory health OIDs."""

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

async def test_oid(engine, community_data, transport_target, context_data, oid):
    """Test a single OID and return result."""
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
    except:
        return None

async def comprehensive_memory_test():
    """Test various memory OID patterns comprehensively."""
    print(f"🧠 COMPREHENSIVE MEMORY HEALTH OID TESTING")
    print(f"Target: {IDRAC_HOST}:{IDRAC_PORT}")
    print("=" * 70)
    
    engine = SnmpEngine()
    community_data = CommunityData(COMMUNITY)
    transport_target = UdpTransportTarget((IDRAC_HOST, IDRAC_PORT), timeout=10, retries=2)
    context_data = ContextData()

    # Test different memory OID patterns
    memory_base_patterns = [
        # Original patterns
        "1.3.6.1.4.1.674.10892.5.4.1100.50.1.4",     # Column 4 (original)
        "1.3.6.1.4.1.674.10892.5.4.1100.50.1.5",     # Column 5 (our update)
        "1.3.6.1.4.1.674.10892.5.4.1100.50.1.6",     # Column 6
        "1.3.6.1.4.1.674.10892.5.4.1100.50.1.20",    # Column 20 (device status)
        "1.3.6.1.4.1.674.10892.5.4.1100.50.1.7",     # Column 7
        
        # Different indexing patterns we found working
        "1.3.6.1.4.1.674.10892.5.4.1100.50.1.4.1",   # With .1 suffix
        "1.3.6.1.4.1.674.10892.5.4.1100.50.1.5.1",   # With .1 suffix
        
        # Try other memory-related OIDs
        "1.3.6.1.4.1.674.10892.5.4.1100.50.1.3",     # Column 3
        "1.3.6.1.4.1.674.10892.5.4.1100.50.1.8",     # Column 8
        "1.3.6.1.4.1.674.10892.5.4.1100.50.1.21",    # Column 21
    ]
    
    print("🔍 Testing base OID patterns (without indices):")
    print("-" * 50)
    
    working_bases = []
    
    for base_oid in memory_base_patterns:
        # Test direct access first
        result = await test_oid(engine, community_data, transport_target, context_data, base_oid)
        if result:
            print(f"✅ {base_oid}: {result}")
            working_bases.append(base_oid)
        else:
            print(f"❌ {base_oid}: No response")
    
    print(f"\n🔍 Testing with memory module indices (1-20):")
    print("-" * 50)
    
    working_combinations = []
    
    for base_oid in memory_base_patterns:
        print(f"\nTesting {base_oid} with indices:")
        base_working = []
        
        for i in range(1, 21):  # Test indices 1-20
            test_oid_full = f"{base_oid}.{i}"
            result = await test_oid(engine, community_data, transport_target, context_data, test_oid_full)
            if result:
                print(f"   ✅ Index {i}: {result}")
                base_working.append((i, result))
                working_combinations.append((test_oid_full, result))
        
        if not base_working:
            print(f"   ❌ No working indices found")
    
    print(f"\n🔍 Testing double-indexed patterns (like .1.1, .1.2, etc.):")
    print("-" * 50)
    
    # Test patterns like the working ones we found: .1.1, .1.2, etc.
    double_index_bases = [
        "1.3.6.1.4.1.674.10892.5.4.1100.50.1.4.1",
        "1.3.6.1.4.1.674.10892.5.4.1100.50.1.5.1",
        "1.3.6.1.4.1.674.10892.5.4.1100.50.1.6.1",
        "1.3.6.1.4.1.674.10892.5.4.1100.50.1.20.1",
    ]
    
    double_working = []
    
    for base_oid in double_index_bases:
        print(f"\nTesting {base_oid} with second indices:")
        for i in range(1, 11):  # Test second indices 1-10
            test_oid_double = f"{base_oid}.{i}"
            result = await test_oid(engine, community_data, transport_target, context_data, test_oid_double)
            if result:
                print(f"   ✅ .{i}: {result}")
                double_working.append((test_oid_double, result))
    
    # Test the specific working patterns from our previous discovery
    print(f"\n🧪 Testing previously discovered working patterns:")
    print("-" * 50)
    
    known_working = [
        "1.3.6.1.4.1.674.10892.5.4.1100.50.1.4.1.1",
        "1.3.6.1.4.1.674.10892.5.4.1100.50.1.4.1.2", 
        "1.3.6.1.4.1.674.10892.5.4.1100.50.1.4.1.3",
        "1.3.6.1.4.1.674.10892.5.4.1100.50.1.4.1.4",
        "1.3.6.1.4.1.674.10892.5.4.1100.50.1.5.1.1",
        "1.3.6.1.4.1.674.10892.5.4.1100.50.1.5.1.2",
    ]
    
    confirmed_working = []
    
    for known_oid in known_working:
        result = await test_oid(engine, community_data, transport_target, context_data, known_oid)
        if result:
            print(f"✅ {known_oid}: {result}")
            confirmed_working.append((known_oid, result))
        else:
            print(f"❌ {known_oid}: No response")
    
    # Analyze the results
    print(f"\n" + "=" * 70)
    print("📊 ANALYSIS AND RECOMMENDATIONS")
    print("=" * 70)
    
    if confirmed_working:
        print(f"\n✅ CONFIRMED WORKING MEMORY OIDs ({len(confirmed_working)} found):")
        for oid, value in confirmed_working:
            print(f"   {oid}: {value}")
        
        # Determine the correct base pattern
        if confirmed_working:
            first_oid = confirmed_working[0][0]
            # Extract base pattern - remove last two indices
            parts = first_oid.split('.')
            if len(parts) >= 3:
                base_pattern = '.'.join(parts[:-2])  # Remove last 2 indices (.1.1 -> base)
                print(f"\n🔧 RECOMMENDED BASE PATTERN: {base_pattern}")
                print(f"   This should be used in const.py as 'memory_health_base'")
                
                # Test this pattern to confirm it works for discovery
                print(f"\n🧪 Testing recommended base for discovery:")
                for i in range(1, 9):  # Test first 8 modules
                    test_pattern_oid = f"{base_pattern}.{i}"
                    result = await test_oid(engine, community_data, transport_target, context_data, test_pattern_oid)
                    if result:
                        print(f"   ✅ Module {i}: {result}")
                    else:
                        print(f"   ❌ Module {i}: No response")
    
    if double_working:
        print(f"\n✅ OTHER WORKING DOUBLE-INDEXED OIDs:")
        for oid, value in double_working:
            print(f"   {oid}: {value}")
    
    if working_combinations:
        print(f"\n✅ SINGLE-INDEXED WORKING OIDs:")
        for oid, value in working_combinations[:10]:  # Show first 10
            print(f"   {oid}: {value}")
    
    # Check current const.py values
    print(f"\n🔍 CURRENT CONST.PY ANALYSIS:")
    current_memory_oids = [
        ("Current memory_health_base", "1.3.6.1.4.1.674.10892.5.4.1100.50.1.4.1"),
        ("Current memory_health in SNMP_WALK_OIDS", "1.3.6.1.4.1.674.10892.5.4.1100.50.1.4.1"),
    ]
    
    for name, oid in current_memory_oids:
        # Test the current OID
        result = await test_oid(engine, community_data, transport_target, context_data, oid)
        if result:
            print(f"✅ {name} ({oid}): WORKING - {result}")
        else:
            print(f"❌ {name} ({oid}): NOT WORKING")
            
        # Test with indices
        print(f"   Testing with indices 1-8:")
        for i in range(1, 9):
            test_oid_indexed = f"{oid}.{i}"
            result = await test_oid(engine, community_data, transport_target, context_data, test_oid_indexed)
            if result:
                print(f"     ✅ .{i}: {result}")

if __name__ == "__main__":
    asyncio.run(comprehensive_memory_test())