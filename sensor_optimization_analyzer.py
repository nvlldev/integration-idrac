#!/usr/bin/env python3
"""
Sensor Optimization Analyzer for Dell iDRAC Integration
This script compares current sensor sources with SNMP availability to identify optimization opportunities.
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Set, Tuple

# Mapping of Home Assistant sensor categories to SNMP categories
CATEGORY_MAPPING = {
    "temperatures": "temperatures",
    "fans": "fans", 
    "voltages": "voltages",
    "power_consumption": "power",
    "processors": "processors",
    "memory": "memory",
    "system_info": "processors",  # CPU info often comes from processor table
    "manager_info": None,  # Manager info typically only available via Redfish
    "diagnostics": None,   # Response time sensors are implementation-specific
}

# Known sensor name patterns that map to SNMP equivalents
SENSOR_NAME_PATTERNS = {
    "temperature": {
        "patterns": [r"temp", r"temperature", r"cpu.*temp", r"inlet", r"outlet", r"ambient"],
        "snmp_category": "temperatures"
    },
    "fan": {
        "patterns": [r"fan", r"cooling", r"rpm"],
        "snmp_category": "fans"
    },
    "voltage": {
        "patterns": [r"volt", r"v$", r"power.*volt", r"psu.*volt"],
        "snmp_category": "voltages"
    },
    "power": {
        "patterns": [r"power", r"watt", r"consumption", r"draw"],
        "snmp_category": "power"
    },
    "processor": {
        "patterns": [r"cpu", r"processor", r"core"],
        "snmp_category": "processors"
    },
    "memory": {
        "patterns": [r"memory", r"ram", r"dimm"],
        "snmp_category": "memory"
    }
}


class SensorOptimizationAnalyzer:
    """Analyze sensor sources and identify SNMP optimization opportunities."""
    
    def __init__(self):
        self.current_sensors = []
        self.snmp_discovery = {}
        self.analysis_results = {}
        
    def load_home_assistant_logs(self, log_file: str) -> bool:
        """Parse Home Assistant logs to extract sensor information."""
        try:
            with open(log_file, 'r') as f:
                log_content = f.read()
                
            # Look for our sensor summary logging
            sensor_pattern = r"=== SENSOR SOURCE SUMMARY ===(.*?)=== END SENSOR SUMMARY ==="
            matches = re.findall(sensor_pattern, log_content, re.DOTALL)
            
            if not matches:
                print("Could not find sensor summary in log file")
                print("Make sure the integration has been reloaded with the new logging")
                return False
                
            # Parse the latest sensor summary
            summary = matches[-1]  # Get the most recent one
            
            # Extract sensor information from debug logs
            debug_pattern = r"DEBUG.*?(\w+)\s+(\w+):\s+(.+)"
            debug_matches = re.findall(debug_pattern, summary)
            
            for protocol, category, sensors_str in debug_matches:
                sensors = [s.strip() for s in sensors_str.split(',')]
                for sensor_name in sensors:
                    self.current_sensors.append({
                        "name": sensor_name,
                        "category": category,
                        "source": protocol.lower(),
                        "original_line": f"{protocol} {category}: {sensors_str}"
                    })
                    
            if not self.current_sensors:
                print("No sensor information found in logs")
                return False
                
            print(f"Loaded {len(self.current_sensors)} sensors from logs")
            return True
            
        except Exception as e:
            print(f"Error reading log file: {e}")
            return False
    
    def load_snmp_discovery(self, discovery_file: str) -> bool:
        """Load SNMP discovery results."""
        try:
            with open(discovery_file, 'r') as f:
                self.snmp_discovery = json.load(f)
                
            categories_with_data = 0
            total_snmp_sensors = 0
            
            for category, data in self.snmp_discovery.get("categories", {}).items():
                if "error" not in data and data.get("sensors"):
                    categories_with_data += 1
                    for sensor_type, sensor_data in data["sensors"].items():
                        if isinstance(sensor_data, dict):
                            total_snmp_sensors += len(sensor_data)
                        else:
                            total_snmp_sensors += 1
                            
            print(f"Loaded SNMP discovery: {categories_with_data} categories, {total_snmp_sensors} sensors")
            return True
            
        except Exception as e:
            print(f"Error reading SNMP discovery file: {e}")
            return False
    
    def manually_add_sensors(self, sensors_input: str):
        """Manually add sensor information if logs aren't available."""
        lines = sensors_input.strip().split('\n')
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
                
            # Expected format: "sensor_name,category,source"
            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 3:
                self.current_sensors.append({
                    "name": parts[0],
                    "category": parts[1],
                    "source": parts[2].lower(),
                    "original_line": line
                })
        
        print(f"Manually added {len(self.current_sensors)} sensors")
    
    def match_sensor_to_snmp(self, sensor: Dict[str, str]) -> List[Dict[str, Any]]:
        """Try to match a sensor to available SNMP data."""
        matches = []
        
        sensor_name = sensor["name"].lower()
        sensor_category = sensor["category"]
        
        # Direct category mapping
        snmp_category = CATEGORY_MAPPING.get(sensor_category)
        if snmp_category and snmp_category in self.snmp_discovery.get("categories", {}):
            snmp_data = self.snmp_discovery["categories"][snmp_category]
            if "sensors" in snmp_data and snmp_data["sensors"]:
                matches.append({
                    "type": "direct_category",
                    "snmp_category": snmp_category,
                    "confidence": "high",
                    "snmp_sensors": snmp_data["sensors"]
                })
        
        # Pattern-based matching
        for pattern_type, pattern_info in SENSOR_NAME_PATTERNS.items():
            for pattern in pattern_info["patterns"]:
                if re.search(pattern, sensor_name, re.IGNORECASE):
                    snmp_cat = pattern_info["snmp_category"]
                    if snmp_cat in self.snmp_discovery.get("categories", {}):
                        snmp_data = self.snmp_discovery["categories"][snmp_cat]
                        if "sensors" in snmp_data and snmp_data["sensors"]:
                            matches.append({
                                "type": "pattern_match",
                                "pattern": pattern,
                                "snmp_category": snmp_cat,
                                "confidence": "medium",
                                "snmp_sensors": snmp_data["sensors"]
                            })
                            break
        
        return matches
    
    def analyze_optimization_opportunities(self) -> Dict[str, Any]:
        """Analyze all sensors and identify optimization opportunities."""
        analysis = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_sensors": len(self.current_sensors),
                "redfish_sensors": 0,
                "snmp_sensors": 0,
                "optimization_candidates": 0
            },
            "by_category": {},
            "recommendations": [],
            "detailed_analysis": []
        }
        
        # Count current sources
        for sensor in self.current_sensors:
            if sensor["source"] == "redfish":
                analysis["summary"]["redfish_sensors"] += 1
            elif sensor["source"] == "snmp":
                analysis["summary"]["snmp_sensors"] += 1
        
        # Analyze each sensor
        category_stats = {}
        
        for sensor in self.current_sensors:
            category = sensor["category"]
            if category not in category_stats:
                category_stats[category] = {
                    "total": 0,
                    "redfish": 0,
                    "snmp": 0,
                    "can_optimize": 0,
                    "sensors": []
                }
            
            category_stats[category]["total"] += 1
            category_stats[category]["sensors"].append(sensor["name"])
            
            if sensor["source"] == "redfish":
                category_stats[category]["redfish"] += 1
                
                # Check if this sensor could use SNMP
                matches = self.match_sensor_to_snmp(sensor)
                if matches:
                    category_stats[category]["can_optimize"] += 1
                    analysis["summary"]["optimization_candidates"] += 1
                    
                    analysis["detailed_analysis"].append({
                        "sensor": sensor,
                        "matches": matches,
                        "recommendation": "Consider switching to SNMP"
                    })
            elif sensor["source"] == "snmp":
                category_stats[category]["snmp"] += 1
                
        analysis["by_category"] = category_stats
        
        # Generate recommendations
        for category, stats in category_stats.items():
            if stats["can_optimize"] > 0:
                analysis["recommendations"].append(
                    f"{category.title()}: {stats['can_optimize']}/{stats['redfish']} Redfish sensors "
                    f"could potentially use SNMP"
                )
        
        # Overall recommendations
        if analysis["summary"]["optimization_candidates"] > 0:
            pct = (analysis["summary"]["optimization_candidates"] / 
                   analysis["summary"]["redfish_sensors"] * 100)
            analysis["recommendations"].insert(0, 
                f"Overall: {analysis['summary']['optimization_candidates']} sensors "
                f"({pct:.1f}% of Redfish sensors) could potentially use SNMP"
            )
        
        return analysis
    
    def generate_report(self, analysis: Dict[str, Any]) -> str:
        """Generate a human-readable report."""
        report = []
        report.append("SENSOR OPTIMIZATION ANALYSIS REPORT")
        report.append("=" * 50)
        report.append(f"Generated: {analysis['timestamp']}")
        report.append("")
        
        # Summary
        summary = analysis["summary"]
        report.append("SUMMARY:")
        report.append(f"  Total sensors: {summary['total_sensors']}")
        report.append(f"  SNMP sensors: {summary['snmp_sensors']}")
        report.append(f"  Redfish sensors: {summary['redfish_sensors']}")
        report.append(f"  Optimization candidates: {summary['optimization_candidates']}")
        report.append("")
        
        # By category
        report.append("BY CATEGORY:")
        for category, stats in analysis["by_category"].items():
            report.append(f"  {category.title()}:")
            report.append(f"    Total: {stats['total']}")
            report.append(f"    SNMP: {stats['snmp']}")
            report.append(f"    Redfish: {stats['redfish']}")
            if stats['can_optimize'] > 0:
                report.append(f"    Can optimize: {stats['can_optimize']} ⚡")
        report.append("")
        
        # Recommendations
        if analysis["recommendations"]:
            report.append("RECOMMENDATIONS:")
            for rec in analysis["recommendations"]:
                report.append(f"  • {rec}")
        else:
            report.append("No optimization opportunities found.")
        report.append("")
        
        # Detailed analysis
        if analysis["detailed_analysis"]:
            report.append("DETAILED ANALYSIS:")
            for item in analysis["detailed_analysis"]:
                sensor = item["sensor"]
                report.append(f"  Sensor: {sensor['name']} ({sensor['category']})")
                report.append(f"    Current source: {sensor['source']}")
                report.append(f"    Recommendation: {item['recommendation']}")
                
                for match in item["matches"]:
                    report.append(f"    SNMP match: {match['snmp_category']} "
                                f"({match['confidence']} confidence)")
                report.append("")
        
        return "\n".join(report)


def main():
    """Main analysis function."""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python sensor_optimization_analyzer.py <snmp_discovery.json> [ha_log_file]")
        print("  python sensor_optimization_analyzer.py <snmp_discovery.json> manual")
        print("")
        print("Examples:")
        print("  python sensor_optimization_analyzer.py snmp_discovery_192_168_1_100_20241230_143000.json home-assistant.log")
        print("  python sensor_optimization_analyzer.py snmp_discovery_192_168_1_100_20241230_143000.json manual")
        sys.exit(1)
    
    snmp_file = sys.argv[1]
    
    analyzer = SensorOptimizationAnalyzer()
    
    # Load SNMP discovery
    if not analyzer.load_snmp_discovery(snmp_file):
        sys.exit(1)
    
    # Load sensor information
    if len(sys.argv) > 2 and sys.argv[2] == "manual":
        print("\nEnter sensor information manually (format: name,category,source)")
        print("Example: CPU Temperature,temperatures,redfish")
        print("Enter 'done' when finished:")
        print("")
        
        sensor_lines = []
        while True:
            line = input("Sensor: ").strip()
            if line.lower() == 'done':
                break
            if line:
                sensor_lines.append(line)
        
        analyzer.manually_add_sensors('\n'.join(sensor_lines))
        
    elif len(sys.argv) > 2:
        log_file = sys.argv[2]
        if not analyzer.load_home_assistant_logs(log_file):
            sys.exit(1)
    else:
        print("Error: No sensor source specified")
        sys.exit(1)
    
    if not analyzer.current_sensors:
        print("No sensors loaded for analysis")
        sys.exit(1)
    
    # Perform analysis
    print("\nAnalyzing optimization opportunities...")
    analysis = analyzer.analyze_optimization_opportunities()
    
    # Generate and save report
    report = analyzer.generate_report(analysis)
    
    # Save detailed analysis
    analysis_file = f"sensor_optimization_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(analysis_file, 'w') as f:
        json.dump(analysis, f, indent=2)
    
    # Save report
    report_file = f"sensor_optimization_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(report_file, 'w') as f:
        f.write(report)
    
    # Display results
    print("\n" + report)
    print(f"\nDetailed analysis saved to: {analysis_file}")
    print(f"Report saved to: {report_file}")


if __name__ == "__main__":
    main()