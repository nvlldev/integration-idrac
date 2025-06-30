#!/usr/bin/env python3
"""
SNMP-Only Mode Comprehensive Test
Test all sensor categories to map what's available for SNMP-only mode.
"""

import asyncio
import json
import sys
from datetime import datetime
from pysnmp.hlapi.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    getCmd,
)

# Status mappings from const.py
DELL_HEALTH_STATUS = {
    1: "other",
    2: "unknown",
    3: "ok",
    4: "non_critical",
    5: "critical",
    6: "non_recoverable"
}

DELL_TEMPERATURE_STATUS = {
    1: "other",
    2: "unknown",
    3: "ok",
    4: "non_critical_upper",
    5: "critical_upper", 
    6: "non_recoverable_upper",
    7: "non_critical_lower",
    8: "critical_lower",
    9: "non_recoverable_lower",
    10: "failed"
}

DELL_INTRUSION_STATUS = {
    1: "breach",
    2: "no_breach", 
    3: "ok",
    4: "unknown"
}

class SNMPOnlyModeTester:
    """Test comprehensive SNMP sensor coverage for SNMP-only mode."""
    
    def __init__(self, host, community="public"):
        self.host = host
        self.community = community
        self.engine = SnmpEngine()
        self.auth_data = CommunityData(community)
        self.transport_target = UdpTransportTarget((host, 161))
        self.context_data = ContextData()
        
        self.results = {
            "host": host,
            "timestamp": datetime.now().isoformat(),
            "categories": {}
        }
        
    async def get_oid(self, oid):
        """Get a single OID value."""
        try:
            error_indication, error_status, error_index, var_binds = await getCmd(
                self.engine, self.auth_data, self.transport_target, self.context_data,
                ObjectType(ObjectIdentity(oid))
            )
            
            if not error_indication and not error_status and var_binds:
                for name, val in var_binds:
                    if val is not None and str(val).strip():
                        return str(val).strip()
        except:
            pass
        return None
        
    async def test_system_info(self):
        """Test system information sensors."""
        print("Testing system information...")
        
        system_info = {}
        
        # Basic system info
        oids = {
            "manufacturer": "1.3.6.1.2.1.1.5.0",  # SNMPv2-MIB::sysName
            "model": "1.3.6.1.4.1.674.10892.5.1.3.12.0",
            "service_tag": "1.3.6.1.4.1.674.10892.5.1.3.2.0",
            "bios_version": "1.3.6.1.4.1.674.10892.5.1.3.6.0",
        }
        
        for name, oid in oids.items():
            value = await self.get_oid(oid)
            if value:
                system_info[name] = value
                
        self.results["categories"]["system_info"] = {
            "sensors": system_info,
            "count": len(system_info)
        }
        
        print(f"  Found {len(system_info)} system info sensors")
        
    async def test_temperatures(self):
        """Test temperature sensors."""
        print("Testing temperature sensors...")
        
        temps = {}
        for i in range(1, 21):  # Test indices 1-20
            name = await self.get_oid(f"1.3.6.1.4.1.674.10892.5.4.700.20.1.8.1.{i}")
            if name:
                reading = await self.get_oid(f"1.3.6.1.4.1.674.10892.5.4.700.20.1.6.1.{i}")
                status = await self.get_oid(f"1.3.6.1.4.1.674.10892.5.4.700.20.1.5.1.{i}")
                upper_critical = await self.get_oid(f"1.3.6.1.4.1.674.10892.5.4.700.20.1.10.1.{i}")
                upper_warning = await self.get_oid(f"1.3.6.1.4.1.674.10892.5.4.700.20.1.11.1.{i}")
                
                temps[i] = {
                    "name": name,
                    "reading": reading,
                    "status": DELL_TEMPERATURE_STATUS.get(int(status) if status else 0, status),
                    "upper_critical": upper_critical,
                    "upper_warning": upper_warning
                }
                
        self.results["categories"]["temperatures"] = {
            "sensors": temps,
            "count": len(temps)
        }
        
        print(f"  Found {len(temps)} temperature sensors")
        
    async def test_fans(self):
        """Test fan sensors.""" 
        print("Testing fan sensors...")
        
        fans = {}
        for i in range(1, 21):
            name = await self.get_oid(f"1.3.6.1.4.1.674.10892.5.4.700.12.1.8.1.{i}")
            if name:
                reading = await self.get_oid(f"1.3.6.1.4.1.674.10892.5.4.700.12.1.6.1.{i}")
                status = await self.get_oid(f"1.3.6.1.4.1.674.10892.5.4.700.12.1.5.1.{i}")
                warning_threshold = await self.get_oid(f"1.3.6.1.4.1.674.10892.5.4.700.12.1.10.1.{i}")
                
                fans[i] = {
                    "name": name,
                    "reading": reading,
                    "status": DELL_HEALTH_STATUS.get(int(status) if status else 0, status),
                    "warning_threshold": warning_threshold
                }
                
        self.results["categories"]["fans"] = {
            "sensors": fans,
            "count": len(fans)
        }
        
        print(f"  Found {len(fans)} fan sensors")
        
    async def test_voltages(self):
        """Test voltage sensors."""
        print("Testing voltage sensors...")
        
        voltages = {}
        for i in range(1, 21):
            name = await self.get_oid(f"1.3.6.1.4.1.674.10892.5.4.600.20.1.8.1.{i}")
            if name:
                reading = await self.get_oid(f"1.3.6.1.4.1.674.10892.5.4.600.20.1.6.1.{i}")
                status = await self.get_oid(f"1.3.6.1.4.1.674.10892.5.4.600.20.1.5.1.{i}")
                upper_critical = await self.get_oid(f"1.3.6.1.4.1.674.10892.5.4.600.20.1.10.1.{i}")
                lower_critical = await self.get_oid(f"1.3.6.1.4.1.674.10892.5.4.600.20.1.11.1.{i}")
                
                voltages[i] = {
                    "name": name,
                    "reading": reading,
                    "status": DELL_HEALTH_STATUS.get(int(status) if status else 0, status),
                    "upper_critical": upper_critical,
                    "lower_critical": lower_critical
                }
                
        self.results["categories"]["voltages"] = {
            "sensors": voltages,
            "count": len(voltages)
        }
        
        print(f"  Found {len(voltages)} voltage sensors")
        
    async def test_power_consumption(self):
        """Test power consumption sensors."""
        print("Testing power consumption...")
        
        power = {}
        for i in range(1, 11):
            name = await self.get_oid(f"1.3.6.1.4.1.674.10892.5.4.600.30.1.8.1.{i}")
            if name:
                reading = await self.get_oid(f"1.3.6.1.4.1.674.10892.5.4.600.30.1.6.1.{i}")
                status = await self.get_oid(f"1.3.6.1.4.1.674.10892.5.4.600.30.1.5.1.{i}")
                warning_threshold = await self.get_oid(f"1.3.6.1.4.1.674.10892.5.4.600.30.1.10.1.{i}")
                
                power[i] = {
                    "name": name,
                    "reading": reading,
                    "status": DELL_HEALTH_STATUS.get(int(status) if status else 0, status),
                    "warning_threshold": warning_threshold
                }
                
        self.results["categories"]["power_consumption"] = {
            "sensors": power,
            "count": len(power)
        }
        
        print(f"  Found {len(power)} power consumption sensors")
        
    async def test_power_supplies(self):
        """Test power supply sensors."""
        print("Testing power supplies...")
        
        psus = {}
        for i in range(1, 11):
            name = await self.get_oid(f"1.3.6.1.4.1.674.10892.5.4.600.12.1.8.1.{i}")
            if name:
                status = await self.get_oid(f"1.3.6.1.4.1.674.10892.5.4.600.12.1.5.1.{i}")
                max_output = await self.get_oid(f"1.3.6.1.4.1.674.10892.5.4.600.12.1.15.1.{i}")
                current_output = await self.get_oid(f"1.3.6.1.4.1.674.10892.5.4.600.12.1.16.1.{i}")
                
                psus[i] = {
                    "name": name,
                    "status": DELL_HEALTH_STATUS.get(int(status) if status else 0, status),
                    "max_output": max_output,
                    "current_output": current_output
                }
                
        self.results["categories"]["power_supplies"] = {
            "sensors": psus,
            "count": len(psus)
        }
        
        print(f"  Found {len(psus)} power supply sensors")
        
    async def test_memory(self):
        """Test memory sensors."""
        print("Testing memory sensors...")
        
        memory = {}
        for i in range(1, 25):  # Memory can have many slots
            name = await self.get_oid(f"1.3.6.1.4.1.674.10892.5.4.1100.50.1.8.1.{i}")
            if name:
                status = await self.get_oid(f"1.3.6.1.4.1.674.10892.5.4.1100.50.1.5.1.{i}")
                size = await self.get_oid(f"1.3.6.1.4.1.674.10892.5.4.1100.50.1.14.1.{i}")
                mem_type = await self.get_oid(f"1.3.6.1.4.1.674.10892.5.4.1100.50.1.7.1.{i}")
                speed = await self.get_oid(f"1.3.6.1.4.1.674.10892.5.4.1100.50.1.15.1.{i}")
                
                memory[i] = {
                    "name": name,
                    "status": DELL_HEALTH_STATUS.get(int(status) if status else 0, status),
                    "size": size,
                    "type": mem_type,
                    "speed": speed
                }
                
        self.results["categories"]["memory"] = {
            "sensors": memory,
            "count": len(memory)
        }
        
        print(f"  Found {len(memory)} memory sensors")
        
    async def test_processors(self):
        """Test processor sensors."""
        print("Testing processors...")
        
        processors = {}
        for i in range(1, 11):
            name = await self.get_oid(f"1.3.6.1.4.1.674.10892.5.4.1200.10.1.8.1.{i}")
            if name:
                reading = await self.get_oid(f"1.3.6.1.4.1.674.10892.5.4.1200.10.1.6.1.{i}")
                status = await self.get_oid(f"1.3.6.1.4.1.674.10892.5.4.1200.10.1.5.1.{i}")
                
                processors[i] = {
                    "name": name,
                    "reading": reading,
                    "status": DELL_HEALTH_STATUS.get(int(status) if status else 0, status)
                }
                
        self.results["categories"]["processors"] = {
            "sensors": processors,
            "count": len(processors)
        }
        
        print(f"  Found {len(processors)} processor sensors")
        
    async def test_intrusion(self):
        """Test intrusion detection."""
        print("Testing intrusion detection...")
        
        intrusion = {}
        for i in range(1, 6):
            name = await self.get_oid(f"1.3.6.1.4.1.674.10892.5.4.300.70.1.8.1.{i}")
            if name:
                reading = await self.get_oid(f"1.3.6.1.4.1.674.10892.5.4.300.70.1.6.1.{i}")
                status = await self.get_oid(f"1.3.6.1.4.1.674.10892.5.4.300.70.1.5.1.{i}")
                
                intrusion[i] = {
                    "name": name,
                    "reading": reading,
                    "status": DELL_INTRUSION_STATUS.get(int(status) if status else 0, status)
                }
                
        self.results["categories"]["intrusion"] = {
            "sensors": intrusion,
            "count": len(intrusion)
        }
        
        print(f"  Found {len(intrusion)} intrusion sensors")
        
    async def test_battery(self):
        """Test battery sensors."""
        print("Testing battery sensors...")
        
        battery = {}
        for i in range(1, 6):
            reading = await self.get_oid(f"1.3.6.1.4.1.674.10892.5.4.600.50.1.6.1.{i}")
            if reading:
                status = await self.get_oid(f"1.3.6.1.4.1.674.10892.5.4.600.50.1.5.1.{i}")
                
                battery[i] = {
                    "name": f"System Battery {i}",
                    "reading": reading,
                    "status": DELL_HEALTH_STATUS.get(int(status) if status else 0, status)
                }
                
        self.results["categories"]["battery"] = {
            "sensors": battery,
            "count": len(battery)
        }
        
        print(f"  Found {len(battery)} battery sensors")
        
    async def run_comprehensive_test(self):
        """Run all sensor tests."""
        print(f"SNMP-Only Mode Comprehensive Test for {self.host}")
        print("="*60)
        print()
        
        # Test all categories
        await self.test_system_info()
        await self.test_temperatures()
        await self.test_fans() 
        await self.test_voltages()
        await self.test_power_consumption()
        await self.test_power_supplies()
        await self.test_memory()
        await self.test_processors()
        await self.test_intrusion()
        await self.test_battery()
        
        # Calculate totals
        total_sensors = sum(cat["count"] for cat in self.results["categories"].values())
        self.results["summary"] = {
            "total_sensors": total_sensors,
            "categories_with_data": len([cat for cat in self.results["categories"].values() if cat["count"] > 0])
        }
        
        print()
        print("="*60)
        print("SNMP-ONLY MODE COVERAGE SUMMARY")
        print("="*60)
        
        for category, data in self.results["categories"].items():
            if data["count"] > 0:
                print(f"✅ {category.title().replace('_', ' ')}: {data['count']} sensors")
            else:
                print(f"❌ {category.title().replace('_', ' ')}: No sensors found")
                
        print()
        print(f"TOTAL: {total_sensors} sensors available via SNMP")
        print(f"Categories with data: {self.results['summary']['categories_with_data']}")
        
        return self.results
        
    def cleanup(self):
        """Clean up SNMP engine."""
        try:
            self.engine.observer.stop()
        except:
            pass

async def main():
    if len(sys.argv) < 2:
        print("Usage: python snmp_only_mode_test.py <host> [community]")
        sys.exit(1)
        
    host = sys.argv[1]
    community = sys.argv[2] if len(sys.argv) > 2 else "public"
    
    tester = SNMPOnlyModeTester(host, community)
    
    try:
        results = await tester.run_comprehensive_test()
        
        # Save results
        results_file = f"snmp_only_mode_test_{host.replace('.', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
            
        print(f"\nDetailed results saved to: {results_file}")
        
        # Generate recommendations
        print("\nSNMP-ONLY MODE RECOMMENDATIONS:")
        print("="*40)
        
        categories_with_data = [cat for cat, data in results["categories"].items() if data["count"] > 0]
        
        if len(categories_with_data) >= 6:
            print("🎉 EXCELLENT: SNMP provides comprehensive server monitoring")
        elif len(categories_with_data) >= 4:
            print("✅ GOOD: SNMP provides solid server monitoring coverage")
        else:
            print("⚠️  LIMITED: SNMP provides basic monitoring only")
            
        print(f"\nSNMP-only mode can provide {results['summary']['total_sensors']} sensors")
        print("This would support older iDRACs without Redfish!")
        
    finally:
        tester.cleanup()

if __name__ == "__main__":
    asyncio.run(main())