#!/usr/bin/env python3
"""Direct test using requests with very permissive SSL settings for older iDRACs."""

import requests
import json
import os
from urllib3.exceptions import InsecureRequestWarning
from dotenv import load_dotenv

# Disable SSL warnings
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# Load environment
load_dotenv()

IDRAC_HOST = os.getenv("IDRAC_HOST")
IDRAC_USERNAME = os.getenv("IDRAC_USERNAME", "root")
IDRAC_PASSWORD = os.getenv("IDRAC_PASSWORD", "")

def test_redfish_with_requests():
    """Test Redfish using requests library with maximum SSL compatibility."""
    print("🔧 DELL IDRAC REDFISH TEST (REQUESTS METHOD)")
    print("=" * 60)
    
    if not IDRAC_HOST or not IDRAC_PASSWORD:
        print("❌ Missing configuration")
        return
        
    print(f"📋 Testing: {IDRAC_HOST} with user '{IDRAC_USERNAME}'")
    print()
    
    # Create session with very permissive SSL settings
    session = requests.Session()
    session.verify = False  # Disable SSL verification entirely
    session.auth = (IDRAC_USERNAME, IDRAC_PASSWORD)
    session.headers.update({
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    })
    
    base_url = f"https://{IDRAC_HOST}"
    
    # Test URLs to try
    test_urls = [
        "/redfish/v1/",
        "/redfish/v1",
        "/api/redfish/v1/",
        "/rest/v1/",
    ]
    
    working_url = None
    
    for test_url in test_urls:
        full_url = base_url + test_url
        print(f"🔍 Trying: {full_url}")
        
        try:
            response = session.get(full_url, timeout=10)
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"   ✅ SUCCESS! Got JSON response")
                    print(f"   📋 Service: {data.get('Name', 'Unknown')}")
                    print(f"   📋 Version: {data.get('RedfishVersion', 'Unknown')}")
                    working_url = test_url
                    break
                except:
                    print(f"   ⚠️  Got 200 but not JSON")
            elif response.status_code == 401:
                print(f"   🔐 Authentication required (expected)")
            else:
                print(f"   ❌ HTTP {response.status_code}")
                
        except requests.exceptions.SSLError as e:
            print(f"   ❌ SSL Error: {e}")
        except requests.exceptions.ConnectionError as e:
            print(f"   ❌ Connection Error: {e}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    if not working_url:
        print()
        print("❌ No Redfish endpoints responded successfully")
        print()
        print("💡 Troubleshooting suggestions:")
        print("   1. Check if iDRAC web interface works at: https://{IDRAC_HOST}")
        print("   2. Verify Redfish is enabled in iDRAC Settings → Network → Redfish")
        print("   3. Check iDRAC firmware version (Redfish requires iDRAC 7+)")
        print("   4. Try different ports (8443, 443)")
        return
    
    print()
    print(f"✅ Found working Redfish endpoint: {working_url}")
    
    # Test basic system info
    systems_url = base_url + working_url.rstrip('/') + "/Systems"
    print(f"🔍 Testing systems endpoint: {systems_url}")
    
    try:
        response = session.get(systems_url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Systems endpoint working")
            
            members = data.get('Members', [])
            print(f"   📊 Found {len(members)} system(s)")
            
            # Test first system
            if members:
                system_path = members[0]['@odata.id']
                system_url = base_url + system_path
                print(f"   🔍 Testing system: {system_url}")
                
                response = session.get(system_url, timeout=10)
                if response.status_code == 200:
                    system_data = response.json()
                    print(f"   ✅ System data retrieved")
                    print(f"   📋 Model: {system_data.get('Model', 'Unknown')}")
                    print(f"   📋 Serial: {system_data.get('SerialNumber', 'Unknown')}")
                    print(f"   📋 Power State: {system_data.get('PowerState', 'Unknown')}")
                    print(f"   📋 LED State: {system_data.get('IndicatorLED', 'Unknown')}")
                    
                    # Check for LED control actions
                    actions = system_data.get('Actions', {})
                    if 'ComputerSystem.IndicatorLEDControl' in actions:
                        print(f"   🎯 LED Control: AVAILABLE!")
                    elif any('LED' in action for action in actions.keys()):
                        print(f"   🎯 LED Control: Possibly available (different action name)")
                    else:
                        print(f"   ❌ LED Control: Not found in actions")
        else:
            print(f"   ❌ Systems endpoint failed: {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Systems test error: {e}")
    
    print()
    print("🎯 CONCLUSION:")
    if working_url:
        print("   ✅ Your iDRAC DOES support Redfish API!")
        print("   ✅ Integration conversion to Redfish is possible")
        print("   ✅ This will solve the SNMP control issues")
    else:
        print("   ❌ Redfish API not accessible")
        print("   ❌ Stick with SNMP monitoring-only approach")

if __name__ == "__main__":
    test_redfish_with_requests()