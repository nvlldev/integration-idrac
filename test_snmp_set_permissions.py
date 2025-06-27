#!/usr/bin/env python3
"""Test script to diagnose SNMP SET permissions on Dell iDRAC."""

import asyncio
import os
from typing import Any, Dict, List, Tuple
from dotenv import load_dotenv
from pysnmp.hlapi.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    UsmUserData,
    setCmd,
    getCmd,
)
from pysnmp.proto.rfc1902 import Integer as SnmpInteger

# Load environment variables
load_dotenv()

# Configuration
IDRAC_HOST = os.getenv("IDRAC_HOST")
IDRAC_PORT = int(os.getenv("IDRAC_PORT", "161"))
COMMUNITY = os.getenv("IDRAC_COMMUNITY", "public")
SNMP_VERSION = os.getenv("SNMP_VERSION", "v2c")  # v2c or v3
SNMP_USERNAME = os.getenv("SNMP_USERNAME", "")
SNMP_AUTH_PASSWORD = os.getenv("SNMP_AUTH_PASSWORD", "")
SNMP_PRIV_PASSWORD = os.getenv("SNMP_PRIV_PASSWORD", "")

# Test OIDs - various control OIDs to test write permissions
TEST_OIDS = {
    "identify_led_index1": "1.3.6.1.4.1.674.10892.5.4.300.70.1.10.1.1",
    "identify_led_index3": "1.3.6.1.4.1.674.10892.5.4.300.70.1.10.1.3", 
    "power_control_index1": "1.3.6.1.4.1.674.10892.5.4.300.70.1.5.1.1",
    "power_control_index3": "1.3.6.1.4.1.674.10892.5.4.300.70.1.5.1.3",
    "safe_mode_index1": "1.3.6.1.4.1.674.10892.5.4.300.70.1.11.1.1",
    "safe_mode_index3": "1.3.6.1.4.1.674.10892.5.4.300.70.1.11.1.3",
}

# Values to test
TEST_VALUES = [0, 1, 2, 3]

def create_auth_data() -> CommunityData | UsmUserData:
    """Create authentication data based on SNMP version."""
    if SNMP_VERSION == "v3":
        return UsmUserData(
            userName=SNMP_USERNAME,
            authKey=SNMP_AUTH_PASSWORD if SNMP_AUTH_PASSWORD else None,
            privKey=SNMP_PRIV_PASSWORD if SNMP_PRIV_PASSWORD else None,
        )
    else:
        return CommunityData(COMMUNITY)

async def test_snmp_get(oid: str) -> Tuple[bool, Any, str]:
    """Test SNMP GET operation."""
    try:
        engine = SnmpEngine()
        auth_data = create_auth_data()
        transport_target = UdpTransportTarget((IDRAC_HOST, IDRAC_PORT), timeout=10, retries=2)
        context_data = ContextData()

        error_indication, error_status, error_index, var_binds = await getCmd(
            engine,
            auth_data,
            transport_target,
            context_data,
            ObjectType(ObjectIdentity(oid)),
        )

        if error_indication:
            return False, None, f"Error indication: {error_indication}"
        elif error_status:
            return False, None, f"Error status: {error_status}"
        elif var_binds:
            return True, var_binds[0][1], "Success"
        else:
            return False, None, "No data returned"

    except Exception as exc:
        return False, None, f"Exception: {exc}"

async def test_snmp_set(oid: str, value: int) -> Tuple[bool, str]:
    """Test SNMP SET operation."""
    try:
        engine = SnmpEngine()
        auth_data = create_auth_data()
        transport_target = UdpTransportTarget((IDRAC_HOST, IDRAC_PORT), timeout=10, retries=2)
        context_data = ContextData()

        error_indication, error_status, error_index, var_binds = await setCmd(
            engine,
            auth_data,
            transport_target,
            context_data,
            ObjectType(ObjectIdentity(oid), SnmpInteger(value)),
        )

        if error_indication:
            return False, f"Error indication: {error_indication}"
        elif error_status:
            return False, f"Error status: {error_status}"
        else:
            return True, "Success"

    except Exception as exc:
        return False, f"Exception: {exc}"

async def comprehensive_test():
    """Run comprehensive SNMP SET permission tests."""
    print("🔧 DELL IDRAC SNMP SET PERMISSIONS TEST")
    print("=" * 60)
    
    if not IDRAC_HOST:
        print("❌ Error: IDRAC_HOST not found in .env file")
        print("Please create a .env file with:")
        print("IDRAC_HOST=your.idrac.ip")
        print("IDRAC_COMMUNITY=public")
        print("SNMP_VERSION=v2c  # or v3")
        print("# For v3:")
        print("SNMP_USERNAME=your_username")
        print("SNMP_AUTH_PASSWORD=your_auth_password")
        print("SNMP_PRIV_PASSWORD=your_priv_password")
        return

    print(f"📋 Configuration:")
    print(f"   Host: {IDRAC_HOST}:{IDRAC_PORT}")
    print(f"   SNMP Version: {SNMP_VERSION}")
    if SNMP_VERSION == "v3":
        print(f"   Username: {SNMP_USERNAME}")
        print(f"   Auth Password: {'***' if SNMP_AUTH_PASSWORD else 'None'}")
        print(f"   Priv Password: {'***' if SNMP_PRIV_PASSWORD else 'None'}")
    else:
        print(f"   Community: {COMMUNITY}")
    print()

    # Test 1: Basic connectivity with GET
    print("📡 Testing basic SNMP connectivity...")
    basic_oid = "1.3.6.1.4.1.674.10892.5.4.600.30.1.6.1.3"  # System power reading
    success, value, message = await test_snmp_get(basic_oid)
    if success:
        print(f"   ✅ SNMP GET successful: {value}")
    else:
        print(f"   ❌ SNMP GET failed: {message}")
        print("   Cannot proceed without basic connectivity")
        return
    print()

    # Test 2: Check current values of control OIDs
    print("📊 Checking current values of control OIDs...")
    current_values = {}
    for name, oid in TEST_OIDS.items():
        success, value, message = await test_snmp_get(oid)
        if success:
            current_values[name] = value
            print(f"   ✅ {name}: {value}")
        else:
            print(f"   ❌ {name}: {message}")
    print()

    # Test 3: SNMP SET permissions test
    print("🔐 Testing SNMP SET permissions...")
    print("   (Testing with safe values to avoid system disruption)")
    print()

    results = {}
    
    # Test identify LED operations (safest to test)
    safe_oids = {
        "identify_led_index1": TEST_OIDS["identify_led_index1"],
        "identify_led_index3": TEST_OIDS["identify_led_index3"],
    }
    
    for name, oid in safe_oids.items():
        print(f"🔍 Testing {name} ({oid}):")
        results[name] = {}
        
        # Get current value
        current_success, current_value, current_msg = await test_snmp_get(oid)
        if not current_success:
            print(f"   ❌ Cannot read current value: {current_msg}")
            continue
            
        print(f"   📖 Current value: {current_value} (type: {type(current_value)})")
        
        # Convert value to int, handle empty/invalid values
        try:
            if str(current_value).strip() == '' or current_value is None:
                print(f"   ⚠️  Empty value, trying with 0...")
                current_int = 0
            else:
                current_int = int(current_value)
        except (ValueError, TypeError):
            print(f"   ⚠️  Cannot convert '{current_value}' to int, trying with 0...")
            current_int = 0
        
        # Test SET with safe value
        print(f"   🧪 Testing SET with value ({current_int})...")
        set_success, set_message = await test_snmp_set(oid, current_int)
        results[name]['same_value'] = (set_success, set_message)
        
        if set_success:
            print(f"   ✅ SET successful: {set_message}")
        else:
            print(f"   ❌ SET failed: {set_message}")
            
        # Test with toggle value only if same value worked
        if set_success and current_int in [0, 1]:
            toggle_value = 1 if current_int == 0 else 0
            print(f"   🧪 Testing SET with toggle value ({toggle_value})...")
            
            # Set to toggle
            toggle_success, toggle_message = await test_snmp_set(oid, toggle_value)
            results[name]['toggle'] = (toggle_success, toggle_message)
            
            if toggle_success:
                print(f"   ✅ Toggle SET successful: {toggle_message}")
                
                # Wait a moment
                await asyncio.sleep(1)
                
                # Restore original value
                restore_success, restore_message = await test_snmp_set(oid, current_int)
                if restore_success:
                    print(f"   ✅ Restored original value")
                else:
                    print(f"   ⚠️  Could not restore original value: {restore_message}")
            else:
                print(f"   ❌ Toggle SET failed: {toggle_message}")
        
        print()

    # Test 4: Summary and recommendations
    print("📋 SUMMARY AND RECOMMENDATIONS")
    print("=" * 40)
    
    working_oids = []
    failed_oids = []
    
    for name, test_results in results.items():
        if test_results.get('same_value', (False, ''))[0]:
            working_oids.append(name)
            print(f"✅ {name}: SNMP SET operations ALLOWED")
        else:
            failed_oids.append(name)
            error_msg = test_results.get('same_value', (False, 'Unknown error'))[1]
            print(f"❌ {name}: SNMP SET operations BLOCKED - {error_msg}")
    
    print()
    
    if working_oids:
        print("🎉 GOOD NEWS: Some SNMP SET operations are working!")
        print(f"   Working OIDs: {', '.join(working_oids)}")
        print("   The Home Assistant integration should work with these OIDs.")
    else:
        print("⚠️  ISSUE: No SNMP SET operations are working")
        print("   Possible causes:")
        print("   1. iDRAC firmware has SNMP SET operations disabled")
        print("   2. User lacks sufficient privileges")
        print("   3. SNMP write access is disabled in security settings")
        print("   4. These specific OIDs don't support SET operations")
        
    print()
    print("💡 NEXT STEPS:")
    if failed_oids:
        print("   1. Check iDRAC Settings → System Security for SNMP write settings")
        print("   2. Verify user has Administrator role with System Control privilege") 
        print("   3. Try updating iDRAC firmware if very old")
        print("   4. Check Dell documentation for your specific iDRAC model")
        
    if working_oids:
        print("   5. Use the working OIDs in the Home Assistant integration")
        print("   6. Report working OIDs to the integration developer")

async def main():
    """Main test function."""
    await comprehensive_test()

if __name__ == "__main__":
    asyncio.run(main())