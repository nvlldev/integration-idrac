#!/usr/bin/env python3
"""Test Redfish using the same approach as the Breina idrac_power_monitor project."""

import asyncio
import json
import ssl
import os
from typing import Any, Dict, Optional
import aiohttp
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

IDRAC_HOST = os.getenv("IDRAC_HOST")
IDRAC_USERNAME = os.getenv("IDRAC_USERNAME", "root")
IDRAC_PASSWORD = os.getenv("IDRAC_PASSWORD", "")

class IdracRedfishClient:
    """Redfish client based on Breina's idrac_power_monitor approach."""
    
    def __init__(self, host: str, username: str, password: str):
        self.host = host
        self.username = username
        self.password = password
        self.base_url = f"https://{host}"
        self.session = None
    
    async def __aenter__(self):
        """Create session with SSL settings similar to Breina's approach."""
        # Disable SSL verification completely (like the working project)
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        connector = aiohttp.TCPConnector(
            ssl=ssl_context,
            limit=10,
            limit_per_host=10
        )
        
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            auth=aiohttp.BasicAuth(self.username, self.password),
            headers={
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
        )
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close session."""
        if self.session:
            await self.session.close()
    
    async def get_path(self, path: str) -> Optional[Dict[str, Any]]:
        """Get data from a Redfish path (matches Breina's method name)."""
        url = f"{self.base_url}{path}"
        
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    print(f"❌ GET {path} failed: {response.status} {response.reason}")
                    return None
        except Exception as e:
            print(f"❌ GET {path} error: {e}")
            return None

async def test_breina_approach():
    """Test Redfish using Breina's approach."""
    print("🔧 TESTING REDFISH WITH BREINA'S APPROACH")
    print("=" * 60)
    
    if not IDRAC_HOST or not IDRAC_PASSWORD:
        print("❌ Missing configuration in .env file")
        return
    
    print(f"📋 Testing: {IDRAC_HOST} with user '{IDRAC_USERNAME}'")
    print()
    
    async with IdracRedfishClient(IDRAC_HOST, IDRAC_USERNAME, IDRAC_PASSWORD) as client:
        
        # Test endpoints used in Breina's project
        test_endpoints = [
            "/redfish/v1/",
            "/redfish/v1/Managers/iDRAC.Embedded.1",
            "/redfish/v1/Chassis/System.Embedded.1", 
            "/redfish/v1/Systems/System.Embedded.1",
            "/redfish/v1/Chassis/System.Embedded.1/Power",
            "/redfish/v1/Chassis/System.Embedded.1/Thermal",
        ]
        
        working_endpoints = []
        
        for endpoint in test_endpoints:
            print(f"🔍 Testing: {endpoint}")
            
            data = await client.get_path(endpoint)
            if data:
                print(f"   ✅ SUCCESS!")
                working_endpoints.append(endpoint)
                
                # Show key information
                if endpoint == "/redfish/v1/":
                    print(f"      📋 Service: {data.get('Name', 'Unknown')}")
                    print(f"      📋 Version: {data.get('RedfishVersion', 'Unknown')}")
                
                elif endpoint == "/redfish/v1/Managers/iDRAC.Embedded.1":
                    print(f"      📋 iDRAC Name: {data.get('Name', 'Unknown')}")
                    print(f"      📋 Firmware: {data.get('FirmwareVersion', 'Unknown')}")
                    print(f"      📋 Model: {data.get('Model', 'Unknown')}")
                
                elif endpoint == "/redfish/v1/Systems/System.Embedded.1":
                    print(f"      📋 System: {data.get('Name', 'Unknown')}")
                    print(f"      📋 Model: {data.get('Model', 'Unknown')}")
                    print(f"      📋 Power State: {data.get('PowerState', 'Unknown')}")
                    print(f"      📋 LED State: {data.get('IndicatorLED', 'Unknown')}")
                    
                    # Check for available actions
                    actions = data.get('Actions', {})
                    if actions:
                        print(f"      🎯 Available Actions: {list(actions.keys())}")
                        
                        # Check for LED control specifically
                        for action_name in actions.keys():
                            if 'LED' in action_name or 'Indicator' in action_name:
                                print(f"      💡 LED Control Action: {action_name}")
                
                elif endpoint == "/redfish/v1/Chassis/System.Embedded.1/Power":
                    power_control = data.get('PowerControl', [])
                    power_supplies = data.get('PowerSupplies', [])
                    voltages = data.get('Voltages', [])
                    
                    print(f"      ⚡ Power Controls: {len(power_control)}")
                    print(f"      🔋 Power Supplies: {len(power_supplies)}")
                    print(f"      📊 Voltages: {len(voltages)}")
                    
                    if power_control:
                        pc = power_control[0]
                        consumed = pc.get('PowerConsumedWatts')
                        capacity = pc.get('PowerCapacityWatts')
                        print(f"      ⚡ Current Power: {consumed}W / {capacity}W")
                
                elif endpoint == "/redfish/v1/Chassis/System.Embedded.1/Thermal":
                    temperatures = data.get('Temperatures', [])
                    fans = data.get('Fans', [])
                    
                    print(f"      🌡️  Temperatures: {len(temperatures)}")
                    print(f"      💨 Fans: {len(fans)}")
                    
                    if temperatures:
                        temp = temperatures[0]
                        print(f"      🌡️  Sample: {temp.get('Name')} = {temp.get('ReadingCelsius')}°C")
                    
                    if fans:
                        fan = fans[0]
                        print(f"      💨 Sample: {fan.get('Name')} = {fan.get('Reading')} RPM")
            else:
                print(f"   ❌ Failed")
            
            print()
        
        # Summary
        print("📋 SUMMARY")
        print("=" * 30)
        
        if working_endpoints:
            print(f"✅ SUCCESS! {len(working_endpoints)}/{len(test_endpoints)} endpoints working")
            print()
            print("🎯 Redfish API is accessible using Breina's approach!")
            print("🎯 Integration conversion to Redfish is possible!")
            print("🎯 This will solve the SNMP control issues!")
            print()
            print("Working endpoints:")
            for ep in working_endpoints:
                print(f"   ✅ {ep}")
            print()
            
            # Test LED control if system endpoint worked
            if "/redfish/v1/Systems/System.Embedded.1" in working_endpoints:
                print("💡 Testing LED Control...")
                system_data = await client.get_path("/redfish/v1/Systems/System.Embedded.1")
                if system_data:
                    current_led = system_data.get('IndicatorLED', 'Unknown')
                    print(f"   📋 Current LED state: {current_led}")
                    
                    actions = system_data.get('Actions', {})
                    led_actions = [action for action in actions.keys() if 'LED' in action or 'Indicator' in action]
                    
                    if led_actions:
                        print(f"   ✅ LED control available: {led_actions}")
                    else:
                        print(f"   ⚠️  LED control not found in actions")
                        print(f"   📋 Available actions: {list(actions.keys())}")
        else:
            print("❌ No endpoints working - Redfish API may be disabled")

async def main():
    """Main test function."""
    await test_breina_approach()

if __name__ == "__main__":
    asyncio.run(main())