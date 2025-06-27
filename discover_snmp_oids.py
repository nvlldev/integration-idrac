#!/usr/bin/env python3
"""
Comprehensive SNMP OID discovery script for Dell iDRAC R820.
This script walks through Dell's SNMP MIB to discover available sensors and data.
"""

import asyncio
import json
from typing import Dict, List, Any, Optional
from pysnmp.hlapi.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    getCmd,
    nextCmd,
    bulkCmd,
)

# Dell Enterprise OID base: 1.3.6.1.4.1.674
DELL_BASE_OID = "1.3.6.1.4.1.674"

# Known Dell iDRAC OID prefixes to explore
DELL_IDRAC_PREFIXES = [
    "1.3.6.1.4.1.674.10892.5.1",      # System Information
    "1.3.6.1.4.1.674.10892.5.4.200",  # System Control
    "1.3.6.1.4.1.674.10892.5.4.300",  # Intrusion Detection
    "1.3.6.1.4.1.674.10892.5.4.600",  # Power/Voltage
    "1.3.6.1.4.1.674.10892.5.4.700",  # Thermal/Cooling
    "1.3.6.1.4.1.674.10892.5.4.1100", # Memory
    "1.3.6.1.4.1.674.10892.5.4.1200", # Processor
    "1.3.6.1.4.1.674.10892.5.5.1.20", # Storage
]

class SNMPDiscoverer:
    def __init__(self, host: str, community: str = "public", port: int = 161):
        self.host = host
        self.community = community
        self.port = port
        self.engine = SnmpEngine()
        self.auth_data = CommunityData(community)
        self.transport_target = UdpTransportTarget((host, port), timeout=10, retries=2)
        self.context_data = ContextData()
        self.discovered_oids: Dict[str, Dict[str, Any]] = {}
        
    async def discover_single_oid(self, oid: str, max_results: int = 50) -> List[Dict[str, Any]]:
        """Discover OIDs under a specific prefix using SNMP walk."""
        results = []
        try:
            count = 0
            async for error_indication, error_status, error_index, var_binds in nextCmd(
                self.engine,
                self.auth_data,
                self.transport_target,
                self.context_data,
                ObjectType(ObjectIdentity(oid)),
                lexicographicMode=False,
                ignoreNonIncreasingOid=True,
                maxRows=max_results
            ):
                if error_indication:
                    print(f"Error indication for {oid}: {error_indication}")
                    break
                elif error_status:
                    print(f"Error status for {oid}: {error_status.prettyPrint()}")
                    break
                
                for name, val in var_binds:
                    oid_str = str(name)
                    # Only include OIDs that start with our target prefix
                    if oid_str.startswith(oid):
                        val_str = str(val).strip()
                        if val_str and val_str != "No Such Object currently exists at this OID":
                            results.append({
                                "oid": oid_str,
                                "value": val_str,
                                "type": str(type(val).__name__)
                            })
                            count += 1
                            if count >= max_results:
                                break
                
                if count >= max_results:
                    break
                    
        except Exception as e:
            print(f"Exception discovering {oid}: {e}")
        
        return results

    async def discover_indexed_sensors(self, base_oid: str, max_index: int = 20) -> Dict[str, List[Dict[str, Any]]]:
        """Discover indexed sensors (like temperatures, fans, etc)."""
        sensor_types = {}
        
        # Common sensor attribute suffixes for Dell iDRAC
        suffixes = {
            "location": ".8.1",      # Sensor location/name
            "reading": ".6.1",       # Current reading
            "status": ".5.1",        # Status value
            "type": ".7.1",          # Sensor type
            "upper_critical": ".10.1", # Upper critical threshold
            "upper_warning": ".11.1",  # Upper warning threshold
            "lower_critical": ".12.1", # Lower critical threshold
            "lower_warning": ".13.1",  # Lower warning threshold
            "units": ".16.1",        # Units
            "max_reading": ".15.1",  # Maximum reading
        }
        
        for suffix_name, suffix in suffixes.items():
            test_oid = f"{base_oid}{suffix}"
            sensor_types[suffix_name] = []
            
            for index in range(1, max_index + 1):
                full_oid = f"{test_oid}.{index}"
                try:
                    error_indication, error_status, error_index, var_binds = await getCmd(
                        self.engine,
                        self.auth_data,
                        self.transport_target,
                        self.context_data,
                        ObjectType(ObjectIdentity(full_oid))
                    )
                    
                    if not error_indication and not error_status and var_binds:
                        for name, val in var_binds:
                            val_str = str(val).strip()
                            if val_str and val_str != "No Such Object currently exists at this OID":
                                sensor_types[suffix_name].append({
                                    "index": index,
                                    "oid": str(name),
                                    "value": val_str,
                                    "type": str(type(val).__name__)
                                })
                except Exception as e:
                    continue  # Skip failed indices
        
        # Filter out empty sensor types
        return {k: v for k, v in sensor_types.items() if v}

    async def discover_system_info(self) -> Dict[str, Any]:
        """Discover system information OIDs."""
        system_oids = {
            "manufacturer": "1.3.6.1.4.1.674.10892.5.1.1.1.0",
            "model": "1.3.6.1.4.1.674.10892.5.1.3.12.0",
            "service_tag": "1.3.6.1.4.1.674.10892.5.1.3.2.0",
            "bios_version": "1.3.6.1.4.1.674.10892.5.1.3.6.0",
            "firmware_version": "1.3.6.1.4.1.674.10892.5.1.3.14.0",
            "hostname": "1.3.6.1.2.1.1.5.0",
            "system_description": "1.3.6.1.2.1.1.1.0",
            "uptime": "1.3.6.1.2.1.1.3.0",
        }
        
        results = {}
        for name, oid in system_oids.items():
            try:
                error_indication, error_status, error_index, var_binds = await getCmd(
                    self.engine,
                    self.auth_data,
                    self.transport_target,
                    self.context_data,
                    ObjectType(ObjectIdentity(oid))
                )
                
                if not error_indication and not error_status and var_binds:
                    for _, val in var_binds:
                        val_str = str(val).strip()
                        if val_str and val_str != "No Such Object currently exists at this OID":
                            results[name] = {
                                "oid": oid,
                                "value": val_str,
                                "type": str(type(val).__name__)
                            }
            except Exception as e:
                print(f"Failed to get {name}: {e}")
        
        return results

    async def discover_all(self) -> Dict[str, Any]:
        """Run comprehensive discovery of all Dell iDRAC OIDs."""
        print(f"Starting comprehensive SNMP discovery for {self.host}...")
        
        discovery_results = {
            "host": self.host,
            "system_info": {},
            "sensors": {},
            "raw_walks": {}
        }
        
        # Discover system information
        print("Discovering system information...")
        discovery_results["system_info"] = await self.discover_system_info()
        
        # Discover sensor categories
        sensor_categories = {
            "thermal_sensors": "1.3.6.1.4.1.674.10892.5.4.700.20.1",
            "cooling_devices": "1.3.6.1.4.1.674.10892.5.4.700.12.1", 
            "power_supplies": "1.3.6.1.4.1.674.10892.5.4.600.12.1",
            "voltage_sensors": "1.3.6.1.4.1.674.10892.5.4.600.30.1",
            "memory_modules": "1.3.6.1.4.1.674.10892.5.4.1100.50.1",
            "processors": "1.3.6.1.4.1.674.10892.5.4.1200.10.1",
            "system_voltages": "1.3.6.1.4.1.674.10892.5.4.600.20.1",
            "intrusion_detection": "1.3.6.1.4.1.674.10892.5.4.300.70.1",
            "system_battery": "1.3.6.1.4.1.674.10892.5.4.600.50.1",
        }
        
        for category, base_oid in sensor_categories.items():
            print(f"Discovering {category}...")
            discovery_results["sensors"][category] = await self.discover_indexed_sensors(base_oid)
        
        # Walk specific OID trees to find additional data
        walk_targets = [
            ("dell_base", "1.3.6.1.4.1.674.10892.5.1.3"),     # System info
            ("power_management", "1.3.6.1.4.1.674.10892.5.4.600"), # Power
            ("thermal_management", "1.3.6.1.4.1.674.10892.5.4.700"), # Thermal
            ("storage_management", "1.3.6.1.4.1.674.10892.5.5.1.20"), # Storage
            ("system_control", "1.3.6.1.4.1.674.10892.5.4.200"),    # Control
        ]
        
        for name, oid in walk_targets:
            print(f"Walking {name} ({oid})...")
            discovery_results["raw_walks"][name] = await self.discover_single_oid(oid, max_results=100)
        
        return discovery_results

    def analyze_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze discovery results to identify useful OIDs for integration."""
        analysis = {
            "recommended_additions": {},
            "sensor_counts": {},
            "potential_thresholds": [],
            "control_oids": [],
            "status_mappings": {}
        }
        
        # Analyze sensor data
        for category, sensors in results["sensors"].items():
            if not sensors:
                continue
                
            analysis["sensor_counts"][category] = {}
            for sensor_type, data in sensors.items():
                analysis["sensor_counts"][category][sensor_type] = len(data)
                
                # Look for patterns in the data
                if sensor_type == "location" and data:
                    # These are sensor names - good for discovery
                    analysis["recommended_additions"][f"{category}_names"] = {
                        "base_oid": data[0]["oid"].rsplit(".", 1)[0],
                        "sample_values": [item["value"] for item in data[:5]],
                        "total_count": len(data)
                    }
                elif sensor_type == "reading" and data:
                    # These are sensor readings
                    analysis["recommended_additions"][f"{category}_readings"] = {
                        "base_oid": data[0]["oid"].rsplit(".", 1)[0],
                        "sample_values": [item["value"] for item in data[:5]],
                        "total_count": len(data)
                    }
                elif sensor_type == "status" and data:
                    # These are status values - good for health monitoring
                    status_values = list(set(item["value"] for item in data))
                    analysis["status_mappings"][category] = status_values
                    analysis["recommended_additions"][f"{category}_status"] = {
                        "base_oid": data[0]["oid"].rsplit(".", 1)[0],
                        "status_values": status_values,
                        "total_count": len(data)
                    }
        
        # Look for threshold OIDs
        for category, sensors in results["sensors"].items():
            for threshold_type in ["upper_critical", "upper_warning", "lower_critical", "lower_warning"]:
                if threshold_type in sensors and sensors[threshold_type]:
                    analysis["potential_thresholds"].append({
                        "category": category,
                        "type": threshold_type,
                        "oid": sensors[threshold_type][0]["oid"].rsplit(".", 1)[0],
                        "sample_values": [item["value"] for item in sensors[threshold_type][:3]]
                    })
        
        # Look for control OIDs in raw walks
        for walk_name, walk_data in results["raw_walks"].items():
            if "control" in walk_name.lower():
                for item in walk_data:
                    if any(keyword in item["oid"].lower() or keyword in item["value"].lower() 
                          for keyword in ["power", "reset", "button", "led", "control"]):
                        analysis["control_oids"].append({
                            "oid": item["oid"],
                            "value": item["value"],
                            "description": f"Potential control OID from {walk_name}"
                        })
        
        return analysis

async def main():
    """Main discovery function."""
    host = "liberator.tshq.local"
    community = "public"
    
    discoverer = SNMPDiscoverer(host, community)
    
    print("=" * 80)
    print(f"DELL iDRAC SNMP DISCOVERY for {host}")
    print("=" * 80)
    
    # Run discovery
    results = await discoverer.discover_all()
    
    # Analyze results
    analysis = discoverer.analyze_results(results)
    
    # Save raw results
    with open("snmp_discovery_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    # Save analysis
    with open("snmp_analysis.json", "w") as f:
        json.dump(analysis, f, indent=2)
    
    # Print summary
    print("\n" + "=" * 80)
    print("DISCOVERY SUMMARY")
    print("=" * 80)
    
    # System info
    print("\nSYSTEM INFORMATION:")
    for name, data in results["system_info"].items():
        print(f"  {name}: {data['value']}")
    
    # Sensor counts
    print("\nSENSOR DISCOVERY SUMMARY:")
    for category, counts in analysis["sensor_counts"].items():
        total_sensors = sum(counts.values())
        if total_sensors > 0:
            print(f"  {category}: {total_sensors} total sensors")
            for sensor_type, count in counts.items():
                if count > 0:
                    print(f"    - {sensor_type}: {count}")
    
    # Recommended additions
    print("\nRECOMMENDED OID ADDITIONS:")
    for name, data in analysis["recommended_additions"].items():
        print(f"  {name}:")
        print(f"    Base OID: {data['base_oid']}")
        if "sample_values" in data:
            print(f"    Sample values: {data['sample_values']}")
        print(f"    Total found: {data.get('total_count', 'unknown')}")
        print()
    
    # Status mappings
    print("STATUS VALUE MAPPINGS:")
    for category, values in analysis["status_mappings"].items():
        print(f"  {category}: {values}")
    
    # Thresholds
    print(f"\nTHRESHOLD SENSORS FOUND: {len(analysis['potential_thresholds'])}")
    for threshold in analysis["potential_thresholds"][:5]:  # Show first 5
        print(f"  {threshold['category']} {threshold['type']}: {threshold['oid']}")
    
    # Control OIDs
    print(f"\nCONTROL OIDS FOUND: {len(analysis['control_oids'])}")
    for control in analysis["control_oids"][:5]:  # Show first 5
        print(f"  {control['oid']}: {control['value']}")
    
    print(f"\nDetailed results saved to:")
    print(f"  - snmp_discovery_results.json (raw data)")
    print(f"  - snmp_analysis.json (analysis)")
    
    return results, analysis

if __name__ == "__main__":
    results, analysis = asyncio.run(main())