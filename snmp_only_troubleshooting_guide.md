# SNMP-Only Mode Troubleshooting Guide

## Issue: No Devices or Entities in SNMP-Only Mode

### Root Causes Fixed

1. **KeyError: 'port' in entity_base.py** ✅
   - Fixed by using `.get(CONF_PORT, 443)` with default value

2. **KeyError: 'redfish' in switch.py and button.py** ✅
   - Fixed by using `.get("redfish")` instead of direct access

### Debugging Steps

1. **Check Config Flow Discovery**
   - Look for log: `"Discovered 6 fans, 4 CPU temperature sensors..."`
   - This confirms sensors were discovered during setup

2. **Check SNMP Client Initialization**
   - Look for logs:
     ```
     "SNMPClient loading discovered sensors from config entry:"
     "  - CPUs: [1, 2]"
     "  - Temperatures: [1, 2, 3, 4]" 
     "  - Fans: [1, 2, 3, 4, 5, 6]"
     "Total discovered sensors loaded: 40+"
     ```

3. **Check SNMP Data Collection**
   - Look for log: `"SNMP get_sensor_data returning data with categories: [...]"`
   - Should show categories like: temperatures, fans, power_supplies, etc.

4. **Check Sensor Setup**
   - Look for logs:
     ```
     "SNMP-only mode detected in sensor setup"
     "SNMP coordinator data categories: ['temperatures', 'fans', ...]"
     "Creating 6 fans sensors using SNMPDataUpdateCoordinator"
     ```

### If Still No Entities

1. **Verify Connection Type**
   - Check that `connection_type` is set to `"snmp_only"` in config entry

2. **Check SNMP Connectivity**
   - Ensure iDRAC is reachable on UDP port 161
   - Verify SNMP community string is correct (default: "public")

3. **Runtime Discovery Fallback**
   - If no sensors discovered during config, client will attempt runtime discovery
   - Look for: `"No sensors discovered during setup, attempting runtime discovery..."`

4. **Check Coordinator Initialization**
   - Look for: `"Connection mode: snmp_only - Created 1 coordinators"`
   - Verify: `"SNMP coordinator: X categories"` (not "no data available")

### Expected Log Sequence (Successful SNMP-Only)

```
1. Config Flow:
   "Discovered 6 fans, 4 CPU temperature sensors, 2 PSU sensors..."

2. Integration Init:
   "Connection mode: snmp_only - Created 1 coordinators"
   "Coordinators initialized - SNMP: ✓"

3. SNMP Client:
   "SNMPClient loading discovered sensors from config entry:"
   "Total discovered sensors loaded: 46"

4. SNMP Data Collection:
   "SNMP data collection for 46 sensors from 192.168.50.131:161"
   "SNMP get_sensor_data returning data with categories: ['temperatures', 'fans', ...]"

5. Sensor Setup:
   "SNMP-only mode detected in sensor setup"
   "Creating 4 temperatures sensors using SNMPDataUpdateCoordinator"
   "Creating 6 fans sensors using SNMPDataUpdateCoordinator"

6. Binary Sensor Setup:
   "Creating PSU status binary sensors"
   "Creating memory health binary sensors"
```

### Manual Testing

1. **Restart Home Assistant** after applying fixes
2. **Check Logs** at startup for the sequence above
3. **Verify Entities** appear in Developer Tools > States
4. **Check Device** in Settings > Devices & Services > Dell iDRAC

### Common Issues

- **Empty discovered sensors**: Config flow didn't complete SNMP discovery
- **No coordinator data**: SNMP client returning empty dict
- **Missing categories**: Some sensor types not available on your iDRAC model

### Debug Commands

```bash
# Check if SNMP is accessible
snmpwalk -v2c -c public 192.168.50.131 1.3.6.1.4.1.674.10892.5

# Test specific OID (fan status)
snmpget -v2c -c public 192.168.50.131 1.3.6.1.4.1.674.10892.5.4.700.12.1.5.1.1
```