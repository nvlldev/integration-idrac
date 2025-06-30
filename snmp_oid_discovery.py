#!/usr/bin/env python3
"""
SNMP OID Discovery Script for Dell iDRAC
This script walks the server for SNMP OIDs and discovers available sensors
to help optimize the integration by preferring SNMP where possible.
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional

from pysnmp.hlapi.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    UsmUserData,
    bulkCmd,
    getCmd,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Dell iDRAC MIB OIDs
DELL_MIBS = {
    # System Information
    "system_info": {
        "base_oid": "1.3.6.1.4.1.674.10892.5.1.1",
        "description": "System Information",
        "oids": {
            "chassis_model": "1.3.6.1.4.1.674.10892.5.1.1.1.0",
            "chassis_tag": "1.3.6.1.4.1.674.10892.5.1.1.2.0",
            "chassis_name": "1.3.6.1.4.1.674.10892.5.1.1.3.0",
            "system_revision": "1.3.6.1.4.1.674.10892.5.1.1.5.0",
        }
    },
    
    # Temperature Sensors
    "temperatures": {
        "base_oid": "1.3.6.1.4.1.674.10892.5.4.700.20.1",
        "description": "Temperature Sensors",
        "oids": {
            "temp_state": "1.3.6.1.4.1.674.10892.5.4.700.20.1.5",
            "temp_reading": "1.3.6.1.4.1.674.10892.5.4.700.20.1.6",
            "temp_type": "1.3.6.1.4.1.674.10892.5.4.700.20.1.7",
            "temp_name": "1.3.6.1.4.1.674.10892.5.4.700.20.1.8",
            "temp_upper_warning": "1.3.6.1.4.1.674.10892.5.4.700.20.1.10",
            "temp_upper_critical": "1.3.6.1.4.1.674.10892.5.4.700.20.1.11",
            "temp_lower_warning": "1.3.6.1.4.1.674.10892.5.4.700.20.1.12",
            "temp_lower_critical": "1.3.6.1.4.1.674.10892.5.4.700.20.1.13",
        }
    },
    
    # Fan Sensors
    "fans": {
        "base_oid": "1.3.6.1.4.1.674.10892.5.4.700.12.1",
        "description": "Fan Sensors",
        "oids": {
            "fan_state": "1.3.6.1.4.1.674.10892.5.4.700.12.1.5",
            "fan_reading": "1.3.6.1.4.1.674.10892.5.4.700.12.1.6",
            "fan_type": "1.3.6.1.4.1.674.10892.5.4.700.12.1.7",
            "fan_name": "1.3.6.1.4.1.674.10892.5.4.700.12.1.8",
            "fan_warning_threshold": "1.3.6.1.4.1.674.10892.5.4.700.12.1.10",
            "fan_failure_threshold": "1.3.6.1.4.1.674.10892.5.4.700.12.1.11",
        }
    },
    
    # Voltage Sensors
    "voltages": {
        "base_oid": "1.3.6.1.4.1.674.10892.5.4.600.20.1",
        "description": "Voltage Sensors",
        "oids": {
            "voltage_state": "1.3.6.1.4.1.674.10892.5.4.600.20.1.5",
            "voltage_reading": "1.3.6.1.4.1.674.10892.5.4.600.20.1.6",
            "voltage_type": "1.3.6.1.4.1.674.10892.5.4.600.20.1.7",
            "voltage_name": "1.3.6.1.4.1.674.10892.5.4.600.20.1.8",
            "voltage_upper_warning": "1.3.6.1.4.1.674.10892.5.4.600.20.1.10",
            "voltage_upper_critical": "1.3.6.1.4.1.674.10892.5.4.600.20.1.11",
            "voltage_lower_warning": "1.3.6.1.4.1.674.10892.5.4.600.20.1.12",
            "voltage_lower_critical": "1.3.6.1.4.1.674.10892.5.4.600.20.1.13",
        }
    },
    
    # Power Consumption
    "power": {
        "base_oid": "1.3.6.1.4.1.674.10892.5.4.600.30.1",
        "description": "Power Consumption",
        "oids": {
            "power_state": "1.3.6.1.4.1.674.10892.5.4.600.30.1.5",
            "power_reading": "1.3.6.1.4.1.674.10892.5.4.600.30.1.6",
            "power_type": "1.3.6.1.4.1.674.10892.5.4.600.30.1.7",
            "power_name": "1.3.6.1.4.1.674.10892.5.4.600.30.1.8",
            "power_warning_threshold": "1.3.6.1.4.1.674.10892.5.4.600.30.1.10",
            "power_failure_threshold": "1.3.6.1.4.1.674.10892.5.4.600.30.1.11",
        }
    },
    
    # Power Supply
    "power_supplies": {
        "base_oid": "1.3.6.1.4.1.674.10892.5.4.600.12.1",
        "description": "Power Supply Units",
        "oids": {
            "psu_state": "1.3.6.1.4.1.674.10892.5.4.600.12.1.5",
            "psu_type": "1.3.6.1.4.1.674.10892.5.4.600.12.1.7",
            "psu_name": "1.3.6.1.4.1.674.10892.5.4.600.12.1.8",
            "psu_input_voltage": "1.3.6.1.4.1.674.10892.5.4.600.12.1.16",
        }
    },
    
    # Memory Information
    "memory": {
        "base_oid": "1.3.6.1.4.1.674.10892.5.4.1100.50.1",
        "description": "Memory Information",
        "oids": {
            "memory_state": "1.3.6.1.4.1.674.10892.5.4.1100.50.1.5",
            "memory_type": "1.3.6.1.4.1.674.10892.5.4.1100.50.1.7",
            "memory_name": "1.3.6.1.4.1.674.10892.5.4.1100.50.1.8",
            "memory_size": "1.3.6.1.4.1.674.10892.5.4.1100.50.1.14",
            "memory_speed": "1.3.6.1.4.1.674.10892.5.4.1100.50.1.15",
        }
    },
    
    # Processor Information
    "processors": {
        "base_oid": "1.3.6.1.4.1.674.10892.5.4.1100.30.1",
        "description": "Processor Information",
        "oids": {
            "cpu_state": "1.3.6.1.4.1.674.10892.5.4.1100.30.1.5",
            "cpu_type": "1.3.6.1.4.1.674.10892.5.4.1100.30.1.7",
            "cpu_name": "1.3.6.1.4.1.674.10892.5.4.1100.30.1.8",
            "cpu_speed": "1.3.6.1.4.1.674.10892.5.4.1100.30.1.11",
            "cpu_max_speed": "1.3.6.1.4.1.674.10892.5.4.1100.30.1.12",
        }
    },
    
    # Intrusion Detection
    "intrusion": {
        "base_oid": "1.3.6.1.4.1.674.10892.5.4.300.70.1",
        "description": "Intrusion Detection",
        "oids": {
            "intrusion_state": "1.3.6.1.4.1.674.10892.5.4.300.70.1.5",
            "intrusion_type": "1.3.6.1.4.1.674.10892.5.4.300.70.1.7",
            "intrusion_name": "1.3.6.1.4.1.674.10892.5.4.300.70.1.8",
        }
    },
}


class SNMPDiscovery:
    """SNMP OID discovery class for Dell iDRAC servers."""
    
    def __init__(self, host: str, port: int = 161, community: str = "public"):
        """Initialize SNMP discovery."""
        self.host = host
        self.port = port
        self.community = community
        self.engine = SnmpEngine()
        self.auth_data = CommunityData(community)
        self.transport_target = UdpTransportTarget((host, port))
        self.context_data = ContextData()
        
        self.discovered_sensors = {}
        
    async def discover_single_oid(self, oid: str) -> Optional[Any]:
        """Discover a single OID value."""
        try:
            error_indication, error_status, error_index, var_binds = await getCmd(
                self.engine,
                self.auth_data,
                self.transport_target,
                self.context_data,
                ObjectType(ObjectIdentity(oid)),
            )
            
            if error_indication:
                logger.debug(f"Error indication for {oid}: {error_indication}")
                return None
            elif error_status:
                logger.debug(f"Error status for {oid}: {error_status.prettyPrint()}")
                return None
            else:
                for name, val in var_binds:
                    if val is not None and str(val) != "No Such Object currently exists at this OID":
                        return str(val).strip()
                        
        except Exception as e:
            logger.debug(f"Exception discovering {oid}: {e}")
            
        return None
        
    async def discover_table(self, base_oid: str, max_repetitions: int = 25) -> Dict[str, Any]:
        """Discover a table using SNMP bulk operations."""
        discovered = {}
        
        try:
            for (error_indication, error_status, error_index, var_binds) in await bulkCmd(
                self.engine,
                self.auth_data,
                self.transport_target,
                self.context_data,
                0, max_repetitions,
                ObjectType(ObjectIdentity(base_oid)),
                lexicographicMode=False
            ):
                if error_indication:
                    logger.debug(f"Bulk walk error indication: {error_indication}")
                    break
                elif error_status:
                    logger.debug(f"Bulk walk error status: {error_status.prettyPrint()}")
                    break
                else:
                    for name, val in var_binds:
                        oid_str = str(name)
                        # Only include OIDs that start with our base OID
                        if oid_str.startswith(base_oid):
                            if val is not None and str(val) != "No Such Object currently exists at this OID":
                                discovered[oid_str] = str(val).strip()
                        else:
                            # We've moved beyond our table
                            return discovered
                            
        except Exception as e:
            logger.debug(f"Exception during bulk walk of {base_oid}: {e}")
            
        return discovered
        
    async def discover_sensor_indices(self, base_oid: str) -> List[int]:
        """Discover available sensor indices for a given sensor type."""
        indices = []
        
        # Test indices from 1 to 50 (most systems won't have more)
        for index in range(1, 51):
            test_oid = f"{base_oid}.{index}"
            value = await self.discover_single_oid(test_oid)
            if value is not None:
                indices.append(index)
                
        return indices
        
    async def discover_category(self, category_name: str, category_info: Dict) -> Dict[str, Any]:
        """Discover all sensors for a specific category."""
        logger.info(f"Discovering {category_info['description']}...")
        
        category_results = {
            "description": category_info["description"],
            "sensors": {},
            "tables": {}
        }
        
        # Discover table data using bulk walk
        if "base_oid" in category_info:
            table_data = await self.discover_table(category_info["base_oid"])
            if table_data:
                category_results["tables"]["bulk_walk"] = table_data
                logger.info(f"  Found {len(table_data)} table entries")
        
        # Discover specific OIDs
        for oid_name, oid in category_info["oids"].items():
            # For table OIDs (ending with a number), discover indices
            if oid.count('.') > 8:  # Likely a table OID
                indices = await self.discover_sensor_indices(oid)
                if indices:
                    oid_data = {}
                    for index in indices:
                        value = await self.discover_single_oid(f"{oid}.{index}")
                        if value is not None:
                            oid_data[index] = value
                    if oid_data:
                        category_results["sensors"][oid_name] = oid_data
                        logger.info(f"  {oid_name}: {len(oid_data)} sensors")
            else:
                # Single value OID
                value = await self.discover_single_oid(oid)
                if value is not None:
                    category_results["sensors"][oid_name] = value
                    logger.info(f"  {oid_name}: {value}")
                    
        return category_results
        
    async def discover_all(self) -> Dict[str, Any]:
        """Discover all available SNMP sensors."""
        logger.info(f"Starting SNMP discovery for {self.host}")
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "host": self.host,
            "community": self.community,
            "categories": {}
        }
        
        for category_name, category_info in DELL_MIBS.items():
            try:
                category_results = await self.discover_category(category_name, category_info)
                results["categories"][category_name] = category_results
            except Exception as e:
                logger.error(f"Error discovering {category_name}: {e}")
                results["categories"][category_name] = {"error": str(e)}
                
        return results
        
    def analyze_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze discovery results and provide summary."""
        analysis = {
            "summary": {},
            "recommendations": [],
            "sensor_counts": {}
        }
        
        total_sensors = 0
        for category_name, category_data in results["categories"].items():
            if "error" in category_data:
                continue
                
            sensor_count = 0
            if "sensors" in category_data:
                for sensor_name, sensor_data in category_data["sensors"].items():
                    if isinstance(sensor_data, dict):
                        sensor_count += len(sensor_data)
                    else:
                        sensor_count += 1
                        
            analysis["sensor_counts"][category_name] = sensor_count
            total_sensors += sensor_count
            
        analysis["summary"]["total_sensors"] = total_sensors
        analysis["summary"]["categories_with_data"] = len([
            cat for cat in results["categories"].values() 
            if "error" not in cat and cat.get("sensors")
        ])
        
        # Generate recommendations
        if analysis["sensor_counts"].get("temperatures", 0) > 0:
            analysis["recommendations"].append("Temperature sensors available via SNMP")
        if analysis["sensor_counts"].get("fans", 0) > 0:
            analysis["recommendations"].append("Fan sensors available via SNMP")
        if analysis["sensor_counts"].get("voltages", 0) > 0:
            analysis["recommendations"].append("Voltage sensors available via SNMP")
        if analysis["sensor_counts"].get("power", 0) > 0:
            analysis["recommendations"].append("Power sensors available via SNMP")
            
        return analysis


async def main():
    """Main discovery function."""
    if len(sys.argv) < 2:
        print("Usage: python snmp_oid_discovery.py <host> [community]")
        print("Example: python snmp_oid_discovery.py 192.168.1.100 public")
        sys.exit(1)
        
    host = sys.argv[1]
    community = sys.argv[2] if len(sys.argv) > 2 else "public"
    
    # Create discovery instance
    discovery = SNMPDiscovery(host, community=community)
    
    try:
        # Perform discovery
        results = await discovery.discover_all()
        
        # Analyze results
        analysis = discovery.analyze_results(results)
        
        # Save detailed results
        results_file = f"snmp_discovery_{host.replace('.', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"Detailed results saved to {results_file}")
        
        # Save analysis
        analysis_file = f"snmp_analysis_{host.replace('.', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(analysis_file, 'w') as f:
            json.dump(analysis, f, indent=2)
        logger.info(f"Analysis saved to {analysis_file}")
        
        # Print summary
        print("\n" + "="*50)
        print("SNMP DISCOVERY SUMMARY")
        print("="*50)
        print(f"Host: {host}")
        print(f"Total sensors discovered: {analysis['summary']['total_sensors']}")
        print(f"Categories with data: {analysis['summary']['categories_with_data']}")
        
        print("\nSensor counts by category:")
        for category, count in analysis["sensor_counts"].items():
            if count > 0:
                print(f"  {category}: {count}")
                
        if analysis["recommendations"]:
            print("\nRecommendations:")
            for rec in analysis["recommendations"]:
                print(f"  • {rec}")
                
        print(f"\nDetailed results: {results_file}")
        print(f"Analysis file: {analysis_file}")
        
    except Exception as e:
        logger.error(f"Discovery failed: {e}")
        sys.exit(1)
    finally:
        # Clean up SNMP engine
        discovery.engine.observer.stop()


if __name__ == "__main__":
    asyncio.run(main())