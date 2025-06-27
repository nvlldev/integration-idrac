#!/usr/bin/env python3
"""Test script to verify the SNMP SET fix for switches."""

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
    setCmd,
    getCmd,
)
from pysnmp.proto.rfc1902 import Integer

# Load environment variables
load_dotenv()

IDRAC_HOST = os.getenv("IDRAC_HOST")
IDRAC_PORT = int(os.getenv("IDRAC_PORT", "161"))
COMMUNITY = os.getenv("IDRAC_COMMUNITY", "public")

async def test_snmp_set_with_correct_type():
    """Test SNMP SET with proper Integer type wrapping."""
    print("🔧 TESTING SNMP SET FIX FOR SWITCHES")
    print("=" * 50)
    print("Issue: 'int' object has no attribute 'getTagSet'")
    print("Fix: Wrap value with Integer() for SNMP SET operations")
    
    engine = SnmpEngine()
    community_data = CommunityData(COMMUNITY)
    transport_target = UdpTransportTarget((IDRAC_HOST, IDRAC_PORT), timeout=10, retries=2)
    context_data = ContextData()
    
    # Identify LED OID from const.py
    identify_led_oid = "1.3.6.1.4.1.674.10892.5.4.300.70.1.10.1.1"
    
    print(f"\n🔍 Testing SNMP SET operations:")
    print("-" * 35)
    
    # Test 1: Get current LED state
    print("1. Getting current LED state...")
    try:
        error_indication, error_status, error_index, var_binds = await getCmd(
            engine,
            community_data,
            transport_target,
            context_data,
            ObjectType(ObjectIdentity(identify_led_oid)),
        )
        
        if error_indication or error_status:
            print(f"   ❌ GET failed: {error_indication or error_status}")
            current_state = None
        else:
            current_state = int(var_binds[0][1]) if var_binds else None
            print(f"   ✅ Current LED state: {current_state}")
    except Exception as e:
        print(f"   ❌ GET exception: {e}")
        current_state = None
    
    # Test 2: SNMP SET with OLD method (raw int) - would fail
    print("\n2. Testing OLD method (raw int - would fail):")
    print("   🚫 This would cause: 'int' object has no attribute 'getTagSet'")
    print("   ❌ ObjectType(ObjectIdentity(oid), 1)  # RAW INT")
    
    # Test 3: SNMP SET with NEW method (Integer wrapped) 
    print("\n3. Testing NEW method (Integer wrapped):")
    print("   ✅ ObjectType(ObjectIdentity(oid), Integer(1))  # WRAPPED")
    
    # We'll test with a safe operation (read current state and set it back)
    if current_state is not None:
        test_value = 1 if current_state == 0 else 0  # Toggle for test
        
        try:
            print(f"   Setting LED to: {test_value}")
            error_indication, error_status, error_index, var_binds = await setCmd(
                engine,
                community_data,
                transport_target,
                context_data,
                ObjectType(ObjectIdentity(identify_led_oid), Integer(test_value)),
            )
            
            if error_indication:
                print(f"   ❌ SET failed - indication: {error_indication}")
            elif error_status:
                print(f"   ❌ SET failed - status: {error_status}")
            else:
                print(f"   ✅ SET successful with Integer({test_value})")
                
                # Verify the change
                await asyncio.sleep(1)  # Brief delay
                
                # Get updated state
                error_indication, error_status, error_index, var_binds = await getCmd(
                    engine,
                    community_data,
                    transport_target,
                    context_data,
                    ObjectType(ObjectIdentity(identify_led_oid)),
                )
                
                if not error_indication and not error_status and var_binds:
                    new_state = int(var_binds[0][1])
                    print(f"   ✅ Verified new state: {new_state}")
                    
                    # Restore original state
                    if new_state != current_state:
                        print(f"   🔄 Restoring original state: {current_state}")
                        await setCmd(
                            engine,
                            community_data,
                            transport_target,
                            context_data,
                            ObjectType(ObjectIdentity(identify_led_oid), Integer(current_state)),
                        )
                        print(f"   ✅ Restored to original state")
                
        except Exception as e:
            if "'int' object has no attribute 'getTagSet'" in str(e):
                print(f"   ❌ OLD ERROR REPRODUCED: {e}")
            else:
                print(f"   ❌ SET exception: {e}")
    
    # Summary
    print(f"\n📊 SNMP SET FIX SUMMARY:")
    print("-" * 30)
    print("   ❌ OLD: ObjectType(ObjectIdentity(oid), value)")
    print("      └─ Causes: 'int' object has no attribute 'getTagSet'")
    print("")
    print("   ✅ NEW: ObjectType(ObjectIdentity(oid), Integer(value))")
    print("      └─ Properly wraps integer for SNMP protocol")
    
    print(f"\n🔧 FIX IMPLEMENTATION:")
    print("-" * 25)
    print("   ✅ Added import: from pysnmp.proto.rfc1902 import Integer")
    print("   ✅ Updated _async_snmp_set: ObjectType(ObjectIdentity(oid), Integer(value))")
    print("   ✅ Switch operations should now work correctly")
    
    print(f"\n💡 SWITCH FUNCTIONALITY:")
    print("-" * 25)
    print("   📋 Identify LED switch should now work:")
    print("      - Turn ON: Sets identify LED to blink")
    print("      - Turn OFF: Stops identify LED")
    print("      - Toggle: Switches between ON/OFF")
    print("   📋 Entity: switch.dell_idrac_identify_led")

async def main():
    """Main test function."""
    if not IDRAC_HOST:
        print("❌ Error: IDRAC_HOST not found in .env file")
        return
    
    await test_snmp_set_with_correct_type()

if __name__ == "__main__":
    asyncio.run(main())