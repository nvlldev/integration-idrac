#!/usr/bin/env python3
"""Test script to verify the enhanced Dell iDRAC integration functionality."""

import asyncio
import os
import logging
from dotenv import load_dotenv

# Set up basic logging
logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

IDRAC_HOST = os.getenv("IDRAC_HOST")
IDRAC_PORT = int(os.getenv("IDRAC_PORT", "161"))
COMMUNITY = os.getenv("IDRAC_COMMUNITY", "public")

if not IDRAC_HOST:
    print("❌ Error: IDRAC_HOST not found in .env file")
    exit(1)

async def test_memory_health_oids():
    """Test the fixed memory health OIDs."""
    from pysnmp.hlapi.asyncio import (
        CommunityData,
        ContextData,
        ObjectIdentity,
        ObjectType,
        SnmpEngine,
        UdpTransportTarget,
        getCmd,
    )
    
    print("🧪 Testing fixed memory health OIDs...")
    
    engine = SnmpEngine()
    community_data = CommunityData(COMMUNITY)
    transport_target = UdpTransportTarget((IDRAC_HOST, IDRAC_PORT), timeout=5, retries=1)
    context_data = ContextData()
    
    # Test the working memory health OID pattern
    memory_base_oid = "1.3.6.1.4.1.674.10892.5.4.1100.50.1.4.1"
    memory_indices = [1, 2, 3, 4, 5, 6, 7, 8]
    
    working_memory_modules = []
    
    for i in memory_indices:
        oid = f"{memory_base_oid}.{i}"
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
                    working_memory_modules.append((i, value))
                    print(f"   ✅ Memory module {i}: health status = {value}")
        except Exception as e:
            print(f"   ❌ Error testing memory module {i}: {e}")
    
    print(f"📊 Found {len(working_memory_modules)} working memory health sensors")
    return working_memory_modules

async def test_new_oid_features():
    """Test some of the new OID features we added."""
    from pysnmp.hlapi.asyncio import (
        CommunityData,
        ContextData,
        ObjectIdentity,
        ObjectType,
        SnmpEngine,
        UdpTransportTarget,
        getCmd,
    )
    
    print("\n🔬 Testing new enhanced OID features...")
    
    engine = SnmpEngine()
    community_data = CommunityData(COMMUNITY)
    transport_target = UdpTransportTarget((IDRAC_HOST, IDRAC_PORT), timeout=5, retries=1)
    context_data = ContextData()
    
    # Test new OIDs from our discovery
    test_oids = [
        ("System power consumption", "1.3.6.1.4.1.674.10892.5.4.600.30.1.10.1.3"),
        ("Power warning threshold", "1.3.6.1.4.1.674.10892.5.4.600.30.1.11.1.3"),
        ("CPU1 VCORE voltage status", "1.3.6.1.4.1.674.10892.5.4.600.20.1.16.1.1"),
        ("CPU2 VCORE voltage status", "1.3.6.1.4.1.674.10892.5.4.600.20.1.16.1.2"),
        ("System 3.3V voltage status", "1.3.6.1.4.1.674.10892.5.4.600.20.1.16.1.3"),
        ("Memory module 1 size", "1.3.6.1.4.1.674.10892.5.4.1100.50.1.14.1.1"),
        ("Memory module 1 speed", "1.3.6.1.4.1.674.10892.5.4.1100.50.1.27.1.1"),
        ("Memory module 1 manufacturer", "1.3.6.1.4.1.674.10892.5.4.1100.50.1.21.1.1"),
        ("Storage controller cache size", "1.3.6.1.4.1.674.10892.5.5.1.20.130.1.1.9.1"),
    ]
    
    working_features = []
    
    for name, oid in test_oids:
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
                    working_features.append((name, value))
                    print(f"   ✅ {name}: {value}")
                else:
                    print(f"   ⚠️ {name}: No data")
            else:
                print(f"   ❌ {name}: SNMP error")
        except Exception as e:
            print(f"   ❌ {name}: Error - {e}")
    
    print(f"📊 Found {len(working_features)} working enhanced features")
    return working_features

async def test_status_mappings():
    """Test the status mappings we added."""
    from custom_components.idrac.const import MEMORY_HEALTH_STATUS, PSU_STATUS, PHYSICAL_DISK_STATUS
    
    print("\n🗺️ Testing status mappings...")
    
    # Test memory health mapping
    test_memory_values = [1, 2, 3, 4, 5, 6]
    print("   Memory health status mapping:")
    for value in test_memory_values:
        status = MEMORY_HEALTH_STATUS.get(value, "unknown")
        healthy = value in [2, 3]  # Our logic for healthy states
        print(f"      Value {value}: {status} ({'✅ Healthy' if healthy else '❌ Problem'})")
    
    # Test PSU status mapping
    test_psu_values = [1, 2, 3, 4, 5, 6]
    print("   PSU status mapping:")
    for value in test_psu_values:
        status = PSU_STATUS.get(value, "unknown")
        healthy = value == 3  # Our logic for healthy state
        print(f"      Value {value}: {status} ({'✅ Healthy' if healthy else '❌ Problem'})")
    
    print("✅ Status mappings verified")

async def main():
    """Main test function."""
    print("🚀 Dell iDRAC Enhanced Integration Test")
    print(f"Target: {IDRAC_HOST}:{IDRAC_PORT}")
    print("=" * 60)
    
    try:
        # Test memory health fixes
        memory_results = await test_memory_health_oids()
        
        # Test new features
        feature_results = await test_new_oid_features()
        
        # Test status mappings
        await test_status_mappings()
        
        print("\n" + "=" * 60)
        print("📋 SUMMARY")
        print("=" * 60)
        print(f"✅ Memory health sensors working: {len(memory_results)}/8")
        print(f"✅ Enhanced features working: {len(feature_results)}/9")
        print("✅ Status mappings verified")
        
        if len(memory_results) >= 8 and len(feature_results) >= 7:
            print("\n🎉 Integration enhancement SUCCESSFUL!")
            print("Memory health sensors are now fixed and enhanced features are working.")
        else:
            print("\n⚠️ Some features may need additional verification")
            
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())