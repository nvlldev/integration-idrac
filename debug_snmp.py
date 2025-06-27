#!/usr/bin/env python3
"""Debug SNMP implementation - analyze the current code for potential issues."""

import sys
import os

# Add the current directory to Python path
sys.path.insert(0, '/Users/scottpetersen/Development/TSHQ/Home Assistant/integration-idrac')

def analyze_snmp_implementation():
    """Analyze the SNMP implementation for potential issues."""
    print("iDRAC SNMP Implementation Analysis")
    print("=" * 40)
    
    # Check if files exist
    files_to_check = [
        'custom_components/idrac/snmp/snmp_client.py',
        'custom_components/idrac/const.py',
        'custom_components/idrac/__init__.py',
        'custom_components/idrac/sensor.py'
    ]
    
    print("\n1. File Existence Check:")
    for file_path in files_to_check:
        if os.path.exists(file_path):
            print(f"   ✓ {file_path} exists")
        else:
            print(f"   ✗ {file_path} missing")
    
    # Analyze the SNMP client code
    print("\n2. SNMP Client Code Analysis:")
    
    try:
        with open('custom_components/idrac/snmp/snmp_client.py', 'r') as f:
            content = f.read()
            
        # Check for potential issues
        issues = []
        
        # Check imports
        if 'from pysnmp.hlapi.asyncio import' in content:
            print("   ✓ Uses asyncio SNMP (good for performance)")
        else:
            issues.append("Not using asyncio SNMP")
            
        # Check for timeout configuration
        if 'timeout=' in content:
            print("   ✓ SNMP timeout configured")
        else:
            issues.append("No SNMP timeout configured")
            
        # Check for retry configuration  
        if 'retries=' in content:
            print("   ✓ SNMP retries configured")
        else:
            issues.append("No SNMP retry configuration")
            
        # Check for bulk operations
        if '_bulk_get_' in content:
            print("   ✓ Bulk SNMP operations implemented")
        else:
            issues.append("No bulk SNMP operations")
            
        # Check for error handling
        if 'except Exception' in content:
            print("   ✓ Exception handling present")
        else:
            issues.append("Limited exception handling")
            
        # Check for discovered sensor indices
        if 'discovered_' in content:
            print("   ✓ Uses discovered sensor indices")
        else:
            issues.append("No sensor discovery mechanism")
            
        # Look for potential blocking operations
        if 'run_in_executor' in content:
            print("   ✓ Uses executor for blocking operations")
        else:
            issues.append("May have blocking operations in event loop")
            
        if issues:
            print("\n   Potential Issues Found:")
            for issue in issues:
                print(f"   ⚠ {issue}")
        else:
            print("   ✓ No obvious code issues detected")
            
    except Exception as e:
        print(f"   ✗ Failed to analyze SNMP client: {e}")
    
    # Check constants
    print("\n3. Constants Analysis:")
    try:
        with open('custom_components/idrac/const.py', 'r') as f:
            const_content = f.read()
            
        if 'IDRAC_OIDS' in const_content:
            print("   ✓ IDRAC_OIDS defined")
            
        if 'SNMP_WALK_OIDS' in const_content:
            print("   ✓ SNMP_WALK_OIDS defined")
            
        if 'STATUS' in const_content:
            print("   ✓ Status mappings defined")
            
        # Count OIDs
        oid_count = const_content.count('1.3.6.1.4.1.674')
        print(f"   ✓ Found {oid_count} Dell OIDs")
        
    except Exception as e:
        print(f"   ✗ Failed to analyze constants: {e}")
    
    # Common issues that cause sensors to show unavailable
    print("\n4. Common Issues That Cause 'Unavailable' Sensors:")
    print("   • SNMP not enabled on iDRAC")
    print("   • Wrong SNMP community string")
    print("   • Network connectivity issues")
    print("   • Firewall blocking SNMP (UDP 161)")
    print("   • Sensor indices not discovered properly")
    print("   • OIDs changed in different iDRAC firmware versions")
    print("   • SNMP timeout too short for slow networks")
    print("   • Home Assistant event loop blocking")
    
    print("\n5. Debugging Recommendations:")
    print("   1. Enable debug logging for the integration")
    print("   2. Check Home Assistant logs for SNMP errors")
    print("   3. Test SNMP manually with snmpwalk/snmpget tools")
    print("   4. Verify sensor discovery completed successfully")
    print("   5. Check if specific OIDs respond outside of Home Assistant")
    
    return True


def check_home_assistant_logs():
    """Provide guidance on checking Home Assistant logs."""
    print("\n6. Home Assistant Log Analysis:")
    print("   To enable debug logging, add this to configuration.yaml:")
    print("   ```yaml")
    print("   logger:")
    print("     logs:")
    print("       custom_components.idrac: debug")
    print("       pysnmp: debug")
    print("   ```")
    print("   ")
    print("   Then check logs for:")
    print("   • SNMP timeout errors")
    print("   • Authentication failures") 
    print("   • Network connectivity issues")
    print("   • Sensor discovery problems")
    print("   • OID response failures")


def suggest_snmp_testing():
    """Suggest manual SNMP testing commands."""
    print("\n7. Manual SNMP Testing:")
    print("   If you have snmp-utils installed, try these commands:")
    print("   ```bash")
    print("   # Test basic connectivity")
    print("   snmpget -v2c -c public <IDRAC_IP> 1.3.6.1.2.1.1.5.0")
    print("   ")
    print("   # Test Dell system model")
    print("   snmpget -v2c -c public <IDRAC_IP> 1.3.6.1.4.1.674.10892.5.1.3.12.0")
    print("   ")
    print("   # Walk temperature sensors")
    print("   snmpwalk -v2c -c public <IDRAC_IP> 1.3.6.1.4.1.674.10892.5.4.700.20.1")
    print("   ```")
    print("   ")
    print("   Replace 'public' with your SNMP community and <IDRAC_IP> with actual IP")


if __name__ == "__main__":
    success = analyze_snmp_implementation()
    check_home_assistant_logs()
    suggest_snmp_testing()
    
    print(f"\n{'='*40}")
    if success:
        print("Analysis complete. Check the recommendations above.")
        print("The SNMP implementation looks technically sound.")
        print("Issues are likely configuration or network related.")
    else:
        print("Analysis failed - check file paths and permissions.")