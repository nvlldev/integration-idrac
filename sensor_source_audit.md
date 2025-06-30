# Sensor Source Audit - SNMP vs Redfish in Hybrid Mode

## Summary
Most sensors are correctly configured to prefer SNMP. One issue was found and fixed.

## ✅ Correctly Using SNMP (when available)

### Regular Sensors (sensor.py)
- **Temperatures** - SNMP preferred ✅
- **Fans** - SNMP preferred ✅
- **Voltages** - SNMP preferred ✅ (FIXED - was Redfish)
- **Power Consumption** - SNMP preferred ✅
- **Memory Size** - SNMP preferred ✅
- **Processors** - SNMP preferred ✅
- **Energy Consumption** - Follows power source ✅
- **Temperature Aggregates** (CPU avg, delta) - SNMP preferred ✅

### Binary Sensors (binary_sensor.py)
- **PSU Health Status** - SNMP preferred ✅
- **Memory Health** - SNMP preferred ✅
- **Virtual Disk Health** - SNMP preferred ✅
- **Physical Disk Health** - SNMP preferred ✅
- **Storage Controller Health** - SNMP preferred ✅
- **Battery Health** - SNMP preferred ✅
- **System Voltage Status** - SNMP preferred ✅
- **Intrusion Detection** - SNMP preferred (falls back to Redfish) ✅

## ✅ Correctly Using Redfish

These sensors only exist in Redfish and cannot use SNMP:

### System Information
- **Total Processors Count** - Redfish only (with SNMP fallback added)
- **Processor Model** - Redfish only
- **Memory Mirroring** - Redfish only
- **Processor/Memory Status** - Redfish only (with SNMP aggregation fallback)
- **Memory Type** - Redfish only
- **Processor Speeds** - Redfish only

### Manager Information
- **Firmware Version** - Redfish only
- **iDRAC Date/Time** - Redfish only

### System Status
- **Overall System Health** - Redfish only
- **Power State** - Redfish only
- **PSU Redundancy** - Redfish only

## 🔧 Fixed Issues

1. **PSU Input Voltage** - Was hardcoded to Redfish, now prefers SNMP
2. **Total Processors** - Added fallback to count CPU temperature sensors
3. **Memory/Processor Status** - Added SNMP aggregation fallback

## How Preference Works

```python
coordinator = get_coordinator_for_category(category, snmp_coordinator, redfish_coordinator, "snmp")
```

1. Checks SNMP coordinator first (if preferred="snmp")
2. If SNMP has data for that category, uses SNMP
3. Otherwise falls back to Redfish
4. In SNMP-only mode, only SNMP is checked

## Verification

To verify which source is being used:
1. Enable debug logging
2. Look for: "Creating X sensors using SNMPDataUpdateCoordinator/RedfishDataUpdateCoordinator"
3. Check entity attributes in Developer Tools
4. Review the sensor registry log output

## SNMP Coverage

In hybrid mode with both protocols available:
- ~70% of sensors should come from SNMP
- ~30% from Redfish (system info, manager info, overall health)

This provides:
- Faster updates for environmental data (15s SNMP vs 45s Redfish)
- Lower network overhead for frequently changing values
- Redfish for complex system information
- Best of both protocols