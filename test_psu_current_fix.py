#!/usr/bin/env python3
"""Test script to verify PSU current fix works correctly."""

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

async def get_snmp_value(engine, community_data, transport_target, context_data, oid, divide_by=1):
    """Get a single SNMP value with optional scaling."""
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
            if value and "No Such" not in value and value.isdigit():
                return float(value) / divide_by
        return None
    except Exception:
        return None

async def test_psu_current_fix():
    """Test the PSU current fix matches expected values."""
    print("🔧 TESTING PSU CURRENT FIX")
    print("=" * 50)
    
    engine = SnmpEngine()
    community_data = CommunityData(COMMUNITY)
    transport_target = UdpTransportTarget((IDRAC_HOST, IDRAC_PORT), timeout=5, retries=1)
    context_data = ContextData()
    
    # Test PSU current values with and without scaling
    print("\n📊 PSU Current Values:")
    print("-" * 30)
    
    # PSU1 Current
    psu1_raw = await get_snmp_value(engine, community_data, transport_target, context_data, 
                                   "1.3.6.1.4.1.674.10892.5.4.600.30.1.6.1.1")
    psu1_scaled = await get_snmp_value(engine, community_data, transport_target, context_data, 
                                      "1.3.6.1.4.1.674.10892.5.4.600.30.1.6.1.1", divide_by=10)
    
    # PSU2 Current  
    psu2_raw = await get_snmp_value(engine, community_data, transport_target, context_data,
                                   "1.3.6.1.4.1.674.10892.5.4.600.30.1.6.1.2")
    psu2_scaled = await get_snmp_value(engine, community_data, transport_target, context_data,
                                      "1.3.6.1.4.1.674.10892.5.4.600.30.1.6.1.2", divide_by=10)
    
    print(f"   PSU1 Current: {psu1_raw}A (raw) → {psu1_scaled}A (scaled)")
    print(f"   PSU2 Current: {psu2_raw}A (raw) → {psu2_scaled}A (scaled)")
    
    # Verify fix is correct
    print("\n✅ VERIFICATION:")
    print("-" * 20)
    expected_psu1 = 1.2
    expected_psu2 = 0.2
    
    if psu1_scaled is not None and abs(psu1_scaled - expected_psu1) < 0.1:
        print(f"   ✅ PSU1 current is correct: {psu1_scaled}A (expected ~{expected_psu1}A)")
    else:
        print(f"   ❌ PSU1 current is wrong: {psu1_scaled}A (expected ~{expected_psu1}A)")
    
    if psu2_scaled is not None and abs(psu2_scaled - expected_psu2) < 0.1:
        print(f"   ✅ PSU2 current is correct: {psu2_scaled}A (expected ~{expected_psu2}A)")
    else:
        print(f"   ❌ PSU2 current is wrong: {psu2_scaled}A (expected ~{expected_psu2}A)")
    
    print(f"\n💡 The coordinator should now return {psu1_scaled}A and {psu2_scaled}A")
    print("   instead of the raw values, fixing the 10x error.")

async def main():
    """Main test function."""
    if not IDRAC_HOST:
        print("❌ Error: IDRAC_HOST not found in .env file")
        return
    
    await test_psu_current_fix()

if __name__ == "__main__":
    asyncio.run(main())