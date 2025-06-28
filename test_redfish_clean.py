#!/usr/bin/env python3
"""
Dell iDRAC Redfish API Comprehensive Test Script

This script tests and validates the Dell iDRAC Redfish API integration
based on official Dell documentation and best practices.

Usage:
    python test_redfish_clean.py --host <idrac_ip> --username <user> --password <pass>
    
Example:
    python test_redfish_clean.py --host 192.168.1.100 --username root --password calvin123
"""

import asyncio
import aiohttp
import argparse
import json
import logging
import ssl
import sys
import time
from typing import Any, Dict, List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class iDRACRedfishTester:
    """Test Dell iDRAC Redfish API endpoints and validate responses."""
    
    def __init__(self, host: str, username: str, password: str, port: int = 443, verify_ssl: bool = False):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl
        self.base_url = f"https://{host}:{port}"
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Known Dell iDRAC Redfish endpoints based on documentation
        self.test_endpoints = {
            "service_root": "/redfish/v1",
            "systems": "/redfish/v1/Systems",
            "system_info": "/redfish/v1/Systems/System.Embedded.1", 
            "chassis": "/redfish/v1/Chassis",
            "chassis_info": "/redfish/v1/Chassis/System.Embedded.1",
            "thermal": "/redfish/v1/Chassis/System.Embedded.1/Thermal",
            "power": "/redfish/v1/Chassis/System.Embedded.1/Power",
            "managers": "/redfish/v1/Managers",
            "manager_info": "/redfish/v1/Managers/iDRAC.Embedded.1",
            "power_subsystem": "/redfish/v1/Chassis/System.Embedded.1/PowerSubsystem",
            # Dell-specific endpoints
            "dell_thermal": "/redfish/v1/Dell/Chassis/System.Embedded.1/Thermal",
            "dell_power": "/redfish/v1/Dell/Chassis/System.Embedded.1/Power",
        }
        
        self.test_results = {}
        
    async def __aenter__(self):
        """Async context manager entry."""
        await self._create_session()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self._close_session()
        
    async def _create_session(self):
        """Create aiohttp session with proper SSL handling."""
        connector = None
        if not self.verify_ssl:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            connector = aiohttp.TCPConnector(ssl_context=ssl_context)
            
        timeout = aiohttp.ClientTimeout(total=20)
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={'User-Agent': 'iDRAC-Redfish-Tester/1.0'}
        )
        
    async def _close_session(self):
        """Close aiohttp session."""
        if self.session:
            await self.session.close()
            
    async def make_request(self, endpoint: str) -> Dict[str, Any]:
        """Make authenticated request to Redfish endpoint."""
        url = f"{self.base_url}{endpoint}"
        auth = aiohttp.BasicAuth(self.username, self.password)
        
        logger.debug(f"Testing endpoint: {endpoint}")
        start_time = time.time()
        
        try:
            async with self.session.get(url, auth=auth) as response:
                elapsed = time.time() - start_time
                
                result = {
                    "endpoint": endpoint,
                    "status_code": response.status,
                    "response_time": round(elapsed, 3),
                    "success": False,
                    "data": None,
                    "error": None
                }
                
                if response.status == 200:
                    try:
                        data = await response.json()
                        result["success"] = True
                        result["data"] = data
                        logger.info(f"✅ {endpoint} - {response.status} ({elapsed:.3f}s)")
                    except json.JSONDecodeError as e:
                        result["error"] = f"JSON decode error: {e}"
                        logger.error(f"❌ {endpoint} - JSON decode error: {e}")
                elif response.status == 401:
                    result["error"] = "Authentication failed"
                    logger.error(f"❌ {endpoint} - Authentication failed")
                elif response.status == 404:
                    result["error"] = "Endpoint not found"
                    logger.warning(f"⚠️  {endpoint} - Not found (404)")
                elif response.status == 403:
                    result["error"] = "Access forbidden"
                    logger.error(f"❌ {endpoint} - Access forbidden")
                else:
                    result["error"] = f"HTTP {response.status}: {response.reason}"
                    logger.error(f"❌ {endpoint} - HTTP {response.status}: {response.reason}")
                    
                return result
                
        except asyncio.TimeoutError:
            result = {
                "endpoint": endpoint,
                "status_code": None,
                "response_time": time.time() - start_time,
                "success": False,
                "error": "Request timeout"
            }
            logger.error(f"❌ {endpoint} - Timeout after {result['response_time']:.3f}s")
            return result
        except Exception as e:
            result = {
                "endpoint": endpoint, 
                "status_code": None,
                "response_time": time.time() - start_time,
                "success": False,
                "error": f"Connection error: {e}"
            }
            logger.error(f"❌ {endpoint} - Connection error: {e}")
            return result
    
    async def test_service_root(self) -> Dict[str, Any]:
        """Test Redfish service root endpoint."""
        logger.info("🔍 Testing Redfish Service Root...")
        result = await self.make_request("/redfish/v1")
        
        if result["success"] and result["data"]:
            data = result["data"]
            logger.info(f"Service Root Info:")
            logger.info(f"  - Redfish Version: {data.get('RedfishVersion', 'Unknown')}")
            logger.info(f"  - Product: {data.get('Product', 'Unknown')}")
            logger.info(f"  - UUID: {data.get('UUID', 'Unknown')}")
            
        return result
    
    async def test_system_info(self) -> Dict[str, Any]:
        """Test system information endpoint."""
        logger.info("🔍 Testing System Information...")
        result = await self.make_request("/redfish/v1/Systems/System.Embedded.1")
        
        if result["success"] and result["data"]:
            data = result["data"]
            logger.info(f"System Info:")
            logger.info(f"  - Model: {data.get('Model', 'Unknown')}")
            logger.info(f"  - Serial Number: {data.get('SerialNumber', 'Unknown')}")
            logger.info(f"  - Power State: {data.get('PowerState', 'Unknown')}")
            logger.info(f"  - BIOS Version: {data.get('BiosVersion', 'Unknown')}")
            logger.info(f"  - Memory (GB): {data.get('MemorySummary', {}).get('TotalSystemMemoryGiB', 'Unknown')}")
            logger.info(f"  - Processor Count: {data.get('ProcessorSummary', {}).get('Count', 'Unknown')}")
            
        return result
    
    async def test_thermal_data(self) -> Dict[str, Any]:
        """Test thermal information endpoint."""
        logger.info("🔍 Testing Thermal Data...")
        result = await self.make_request("/redfish/v1/Chassis/System.Embedded.1/Thermal")
        
        if result["success"] and result["data"]:
            data = result["data"]
            temperatures = data.get("Temperatures", [])
            fans = data.get("Fans", [])
            
            logger.info(f"Thermal Data:")
            logger.info(f"  - Temperature Sensors: {len(temperatures)}")
            for i, temp in enumerate(temperatures[:3]):  # Show first 3
                name = temp.get("Name", f"Temperature {i+1}")
                reading = temp.get("ReadingCelsius", "Unknown")
                status = temp.get("Status", {}).get("Health", "Unknown")
                logger.info(f"    • {name}: {reading}°C ({status})")
                
            logger.info(f"  - Fan Sensors: {len(fans)}")
            for i, fan in enumerate(fans[:3]):  # Show first 3
                name = fan.get("Name", f"Fan {i+1}")
                reading = fan.get("Reading", "Unknown")
                status = fan.get("Status", {}).get("Health", "Unknown")
                logger.info(f"    • {name}: {reading} RPM ({status})")
                
        return result
    
    async def test_power_data(self) -> Dict[str, Any]:
        """Test power information endpoint."""
        logger.info("🔍 Testing Power Data...")
        result = await self.make_request("/redfish/v1/Chassis/System.Embedded.1/Power")
        
        if result["success"] and result["data"]:
            data = result["data"]
            power_control = data.get("PowerControl", [])
            power_supplies = data.get("PowerSupplies", [])
            voltages = data.get("Voltages", [])
            
            logger.info(f"Power Data:")
            if power_control:
                pc = power_control[0]
                consumed = pc.get("PowerConsumedWatts", "Unknown")
                capacity = pc.get("PowerCapacityWatts", "Unknown")
                logger.info(f"  - Power Consumption: {consumed}W / {capacity}W")
                
            logger.info(f"  - Power Supplies: {len(power_supplies)}")
            for i, psu in enumerate(power_supplies):
                name = psu.get("Name", f"PSU {i+1}")
                status = psu.get("Status", {}).get("Health", "Unknown")
                capacity = psu.get("PowerCapacityWatts", "Unknown")
                logger.info(f"    • {name}: {capacity}W ({status})")
                
            logger.info(f"  - Voltage Sensors: {len(voltages)}")
            
        return result
    
    async def test_manager_info(self) -> Dict[str, Any]:
        """Test iDRAC manager information."""
        logger.info("🔍 Testing Manager Information...")
        result = await self.make_request("/redfish/v1/Managers/iDRAC.Embedded.1")
        
        if result["success"] and result["data"]:
            data = result["data"]
            logger.info(f"Manager Info:")
            logger.info(f"  - Firmware Version: {data.get('FirmwareVersion', 'Unknown')}")
            logger.info(f"  - Model: {data.get('Model', 'Unknown')}")
            logger.info(f"  - Status: {data.get('Status', {}).get('Health', 'Unknown')}")
            logger.info(f"  - Date/Time: {data.get('DateTime', 'Unknown')}")
            
        return result
    
    async def test_chassis_info(self) -> Dict[str, Any]:
        """Test chassis information."""
        logger.info("🔍 Testing Chassis Information...")
        result = await self.make_request("/redfish/v1/Chassis/System.Embedded.1")
        
        if result["success"] and result["data"]:
            data = result["data"]
            physical_security = data.get("PhysicalSecurity", {})
            logger.info(f"Chassis Info:")
            logger.info(f"  - Chassis Type: {data.get('ChassisType', 'Unknown')}")
            logger.info(f"  - Model: {data.get('Model', 'Unknown')}")
            logger.info(f"  - Serial Number: {data.get('SerialNumber', 'Unknown')}")
            logger.info(f"  - Intrusion Sensor: {physical_security.get('IntrusionSensor', 'Unknown')}")
            
        return result
    
    async def test_all_endpoints(self) -> Dict[str, Any]:
        """Test all available endpoints and return results."""
        logger.info("🚀 Starting comprehensive Dell iDRAC Redfish API test...\n")
        
        # Test core endpoints
        tests = [
            ("service_root", self.test_service_root),
            ("system_info", self.test_system_info),
            ("thermal_data", self.test_thermal_data),
            ("power_data", self.test_power_data),
            ("manager_info", self.test_manager_info),
            ("chassis_info", self.test_chassis_info),
        ]
        
        results = {}
        start_time = time.time()
        
        for test_name, test_func in tests:
            try:
                results[test_name] = await test_func()
                print()  # Add spacing between tests
            except Exception as e:
                logger.error(f"Test {test_name} failed with exception: {e}")
                results[test_name] = {
                    "endpoint": test_name,
                    "success": False,
                    "error": str(e)
                }
        
        # Test additional endpoints
        logger.info("🔍 Testing additional endpoints...")
        additional_endpoints = [
            "/redfish/v1/Chassis/System.Embedded.1/PowerSubsystem",
            "/redfish/v1/Dell/Chassis/System.Embedded.1/Thermal",
            "/redfish/v1/Dell/Chassis/System.Embedded.1/Power",
        ]
        
        for endpoint in additional_endpoints:
            test_name = endpoint.split("/")[-1].lower()
            results[f"additional_{test_name}"] = await self.make_request(endpoint)
        
        total_time = time.time() - start_time
        logger.info(f"\n📊 Test Summary:")
        logger.info(f"Total test time: {total_time:.3f}s")
        
        successful_tests = sum(1 for r in results.values() if r.get("success", False))
        total_tests = len(results)
        logger.info(f"Successful tests: {successful_tests}/{total_tests}")
        
        # Log failed tests
        failed_tests = [name for name, result in results.items() if not result.get("success", False)]
        if failed_tests:
            logger.warning(f"Failed tests: {', '.join(failed_tests)}")
        
        return results
    
    def generate_integration_improvements(self, results: Dict[str, Any]) -> List[str]:
        """Generate recommendations for improving the Redfish integration."""
        recommendations = []
        
        # Check response times
        slow_endpoints = [
            name for name, result in results.items() 
            if result.get("response_time", 0) > 5.0 and result.get("success", False)
        ]
        if slow_endpoints:
            recommendations.append(f"⚠️ Slow endpoints detected ({', '.join(slow_endpoints)}). Consider increasing timeouts or optimization.")
        
        # Check missing endpoints
        failed_endpoints = [
            name for name, result in results.items()
            if not result.get("success", False) and result.get("error") != "Endpoint not found"
        ]
        if failed_endpoints:
            recommendations.append(f"❌ Failed endpoints: {', '.join(failed_endpoints)}. Check authentication or network issues.")
        
        # Check data completeness
        if results.get("thermal_data", {}).get("success"):
            thermal_data = results["thermal_data"]["data"]
            temp_count = len(thermal_data.get("Temperatures", []))
            fan_count = len(thermal_data.get("Fans", []))
            recommendations.append(f"✅ Thermal data available: {temp_count} temperature sensors, {fan_count} fans")
        
        if results.get("power_data", {}).get("success"):
            power_data = results["power_data"]["data"]
            psu_count = len(power_data.get("PowerSupplies", []))
            voltage_count = len(power_data.get("Voltages", []))
            recommendations.append(f"✅ Power data available: {psu_count} power supplies, {voltage_count} voltage sensors")
        
        return recommendations


async def main():
    """Main test function."""
    parser = argparse.ArgumentParser(description='Test Dell iDRAC Redfish API')
    parser.add_argument('--host', required=True, help='iDRAC IP address or hostname')
    parser.add_argument('--username', required=True, help='iDRAC username')
    parser.add_argument('--password', required=True, help='iDRAC password')
    parser.add_argument('--port', type=int, default=443, help='iDRAC HTTPS port (default: 443)')
    parser.add_argument('--verify-ssl', action='store_true', help='Verify SSL certificates')
    parser.add_argument('--output', help='Save results to JSON file')
    
    args = parser.parse_args()
    
    async with iDRACRedfishTester(
        host=args.host,
        username=args.username, 
        password=args.password,
        port=args.port,
        verify_ssl=args.verify_ssl
    ) as tester:
        
        # Run all tests
        results = await tester.test_all_endpoints()
        
        # Generate recommendations
        recommendations = tester.generate_integration_improvements(results)
        
        print("\n" + "="*60)
        print("🎯 INTEGRATION IMPROVEMENT RECOMMENDATIONS")
        print("="*60)
        for rec in recommendations:
            print(rec)
        
        # Save results if requested
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2)
            logger.info(f"Results saved to {args.output}")
        
        return results


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n❌ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)