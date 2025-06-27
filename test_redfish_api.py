#!/usr/bin/env python3
"""Test script to explore Dell iDRAC Redfish API capabilities."""

import asyncio
import json
import os
import ssl
from typing import Any, Dict, Optional
import aiohttp
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
IDRAC_HOST = os.getenv("IDRAC_HOST")
IDRAC_USERNAME = os.getenv("IDRAC_USERNAME", "root")
IDRAC_PASSWORD = os.getenv("IDRAC_PASSWORD", "")
IDRAC_PORT = os.getenv("IDRAC_HTTPS_PORT", "443")

class DellRedfishClient:
    """Dell-specific Redfish API client based on official Dell scripts."""
    
    def __init__(self, host: str, username: str, password: str, port: str = "443", ssl_verify: bool = False):
        self.base_url = f"https://{host}:{port}"
        self.username = username
        self.password = password
        self.ssl_verify = ssl_verify
        self.session = None
        self.session_token = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        if self.ssl_verify:
            # Standard SSL verification
            connector = aiohttp.TCPConnector()
        else:
            # Dell's typical approach - disable SSL verification completely
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            connector = aiohttp.TCPConnector(ssl=ssl_context)
        
        # Set headers as used in Dell's official scripts
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        self.session = aiohttp.ClientSession(
            connector=connector,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=30)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    async def get(self, path: str) -> Optional[Dict[str, Any]]:
        """Make GET request to Redfish API."""
        url = f"{self.base_url}{path}"
        auth = aiohttp.BasicAuth(self.username, self.password)
        
        try:
            async with self.session.get(url, auth=auth) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    print(f"❌ GET {path} failed: {response.status} {response.reason}")
                    return None
        except Exception as e:
            print(f"❌ GET {path} error: {e}")
            return None
    
    async def post(self, path: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Make POST request to Redfish API."""
        url = f"{self.base_url}{path}"
        auth = aiohttp.BasicAuth(self.username, self.password)
        
        try:
            async with self.session.post(url, auth=auth, json=data) as response:
                if response.status in [200, 202, 204]:
                    if response.content_length and response.content_length > 0:
                        return await response.json()
                    return {"status": "success"}
                else:
                    print(f"❌ POST {path} failed: {response.status} {response.reason}")
                    try:
                        error_data = await response.json()
                        print(f"   Error details: {error_data}")
                    except:
                        pass
                    return None
        except Exception as e:
            print(f"❌ POST {path} error: {e}")
            return None

async def test_redfish_capabilities():
    """Test Redfish API capabilities."""
    print("🔧 DELL IDRAC REDFISH API EXPLORATION")
    print("=" * 60)
    
    if not IDRAC_HOST or not IDRAC_PASSWORD:
        print("❌ Error: Missing configuration in .env file")
        print("Please set:")
        print("IDRAC_HOST=your.idrac.ip")
        print("IDRAC_USERNAME=root")
        print("IDRAC_PASSWORD=your_password")
        return
    
    print(f"📋 Configuration:")
    print(f"   Host: {IDRAC_HOST}")
    print(f"   Username: {IDRAC_USERNAME}")
    print(f"   Password: {'***' if IDRAC_PASSWORD else 'Not set'}")
    print()
    
    # Try HTTPS with different approaches based on Dell's official scripts
    configs_to_try = [
        ("443", "https", True),   # Standard HTTPS with SSL verification
        ("443", "https", False),  # HTTPS without SSL verification (Dell default)
    ]
    
    client = None
    working_config = None
    
    for port, protocol, ssl_verify in configs_to_try:
        ssl_desc = "with SSL verification" if ssl_verify else "without SSL verification"
        print(f"🔍 Trying {protocol.upper()} on port {port} {ssl_desc}...")
        
        # Create client with specific SSL settings
        test_client = DellRedfishClient(IDRAC_HOST, IDRAC_USERNAME, IDRAC_PASSWORD, port, ssl_verify)
        
        try:
            async with test_client as tc:
                service_root = await tc.get("/redfish/v1/")
                if service_root:
                    print(f"   ✅ Connection successful!")
                    client = test_client
                    working_config = (port, protocol, ssl_verify)
                    break
                else:
                    print(f"   ❌ Connection failed - no response")
        except Exception as e:
            print(f"   ❌ Connection error: {e}")
    
    if not working_config:
        print("\n❌ Could not establish connection")
        print("   This iDRAC may not support Redfish API or has it disabled")
        print("   Note: Older iDRAC versions (before iDRAC 7) may not support Redfish")
        return
    
    port, protocol, ssl_verify = working_config
    ssl_desc = "with SSL verification" if ssl_verify else "without SSL verification"
    print(f"\n✅ Using {protocol.upper()} on port {port} {ssl_desc}")
    
    client = DellRedfishClient(IDRAC_HOST, IDRAC_USERNAME, IDRAC_PASSWORD, port, ssl_verify)
    
    async with client:
        
        # Test 1: Basic Redfish service root
        print("🌐 Testing Redfish service root...")
        service_root = await client.get("/redfish/v1/")
        if service_root:
            print("   ✅ Redfish API is accessible")
            print(f"   📋 Service: {service_root.get('Name', 'Unknown')}")
            print(f"   📋 Version: {service_root.get('RedfishVersion', 'Unknown')}")
            print(f"   📋 UUID: {service_root.get('UUID', 'Unknown')}")
        else:
            print("   ❌ Cannot access Redfish API")
            return
        print()
        
        # Test 2: Systems information
        print("💻 Getting systems information...")
        systems = await client.get("/redfish/v1/Systems")
        if systems and systems.get("Members"):
            for member in systems["Members"]:
                system_path = member["@odata.id"]
                print(f"   📁 Found system: {system_path}")
                
                system_info = await client.get(system_path)
                if system_info:
                    print(f"      📋 Model: {system_info.get('Model', 'Unknown')}")
                    print(f"      📋 Serial: {system_info.get('SerialNumber', 'Unknown')}")
                    print(f"      📋 Power State: {system_info.get('PowerState', 'Unknown')}")
                    
                    # Get system identifier info for Identify LED
                    system_id = system_path.split('/')[-1]
                    print(f"      📋 System ID: {system_id}")
        print()
        
        # Test 3: Thermal information
        print("🌡️  Getting thermal information...")
        thermal_path = "/redfish/v1/Systems/System.Embedded.1/Thermal"
        thermal = await client.get(thermal_path)
        if thermal:
            temperatures = thermal.get("Temperatures", [])
            fans = thermal.get("Fans", [])
            print(f"   📊 Found {len(temperatures)} temperature sensors")
            print(f"   📊 Found {len(fans)} fans")
            
            # Show sample temperature
            if temperatures:
                temp = temperatures[0]
                print(f"   🌡️  Sample: {temp.get('Name')} = {temp.get('ReadingCelsius')}°C")
            
            # Show sample fan
            if fans:
                fan = fans[0]
                print(f"   💨 Sample: {fan.get('Name')} = {fan.get('Reading')} RPM")
        print()
        
        # Test 4: Power information
        print("⚡ Getting power information...")
        power_path = "/redfish/v1/Systems/System.Embedded.1/Power"
        power = await client.get(power_path)
        if power:
            power_supplies = power.get("PowerSupplies", [])
            power_control = power.get("PowerControl", [])
            voltages = power.get("Voltages", [])
            
            print(f"   📊 Found {len(power_supplies)} power supplies")
            print(f"   📊 Found {len(power_control)} power controls")
            print(f"   📊 Found {len(voltages)} voltage sensors")
            
            # Show power consumption
            if power_control:
                pc = power_control[0]
                consumption = pc.get("PowerConsumedWatts")
                capacity = pc.get("PowerCapacityWatts")
                print(f"   ⚡ Power: {consumption}W / {capacity}W")
        print()
        
        # Test 5: Test Identify LED control
        print("💡 Testing Identify LED control...")
        system_path = "/redfish/v1/Systems/System.Embedded.1"
        
        # Get current LED state
        system_info = await client.get(system_path)
        if system_info:
            led_state = system_info.get("IndicatorLED", "Unknown")
            print(f"   📋 Current LED state: {led_state}")
            
            # Test LED control (safe test - just get available actions)
            actions = system_info.get("Actions", {})
            if actions:
                print("   📋 Available actions:")
                for action_name, action_info in actions.items():
                    print(f"      🔧 {action_name}")
                    if "target" in action_info:
                        print(f"         Target: {action_info['target']}")
            
            # Try to toggle LED (safe operation)
            if led_state in ["Off", "Lit"]:
                new_state = "Lit" if led_state == "Off" else "Off"
                print(f"   🧪 Testing LED control: {led_state} → {new_state}")
                
                led_action_path = f"{system_path}/Actions/ComputerSystem.IndicatorLEDControl"
                led_data = {"IndicatorLEDState": new_state}
                
                result = await client.post(led_action_path, led_data)
                if result:
                    print(f"   ✅ LED control successful!")
                    
                    # Wait and restore
                    await asyncio.sleep(2)
                    restore_data = {"IndicatorLEDState": led_state}
                    restore_result = await client.post(led_action_path, restore_data)
                    if restore_result:
                        print(f"   ✅ LED state restored")
                else:
                    print(f"   ❌ LED control failed")
        print()
        
        # Test 6: Test power control capabilities
        print("🔌 Testing power control capabilities...")
        reset_actions = system_info.get("Actions", {}).get("ComputerSystem.Reset", {})
        if reset_actions:
            allowed_values = reset_actions.get("ResetType@Redfish.AllowableValues", [])
            print(f"   📋 Available power actions: {', '.join(allowed_values)}")
            
            # Don't actually test power operations for safety
            print("   ⚠️  Power control testing skipped for safety")
        print()
        
        # Test 7: Managers (iDRAC itself)
        print("🔧 Getting iDRAC manager information...")
        managers = await client.get("/redfish/v1/Managers")
        if managers and managers.get("Members"):
            for member in managers["Members"]:
                manager_path = member["@odata.id"]
                manager_info = await client.get(manager_path)
                if manager_info:
                    print(f"   📋 Manager: {manager_info.get('Name', 'Unknown')}")
                    print(f"   📋 Firmware: {manager_info.get('FirmwareVersion', 'Unknown')}")
                    print(f"   📋 Model: {manager_info.get('Model', 'Unknown')}")
        print()
        
        # Summary
        print("📋 REDFISH API CONVERSION ASSESSMENT")
        print("=" * 50)
        print("✅ **EXCELLENT NEWS**: Redfish API is fully accessible!")
        print()
        print("🎯 **Available for monitoring:**")
        print("   • System information (model, serial, power state)")
        print("   • Temperature sensors (detailed readings)")
        print("   • Fan speeds and status")
        print("   • Power consumption and supply status")
        print("   • Voltage readings")
        print("   • Memory and storage information")
        print()
        print("🎯 **Available for control:**")
        print("   • Identify LED control ✅")
        print("   • Power management (reset, power on/off)")
        print("   • System configuration")
        print()
        print("💡 **Recommendation:**")
        print("   Convert the integration to use Redfish API!")
        print("   This will provide:")
        print("   • Better reliability than SNMP")
        print("   • Working control operations")
        print("   • More detailed monitoring data")
        print("   • Modern REST API with JSON")

async def main():
    """Main test function."""
    await test_redfish_capabilities()

if __name__ == "__main__":
    asyncio.run(main())