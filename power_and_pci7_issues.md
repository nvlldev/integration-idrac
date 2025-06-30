# Power Consumption and PCI7 Health Issues

## Issue 1: Power Consumption Not Showing

### Root Cause
The power consumption sensor requires discovery during the initial config flow. If the discovery failed or the integration was added before the fix, the sensor won't appear.

### Solution
1. **Check if power OID works:**
   ```bash
   python3 debug_power_consumption_issue.py YOUR_IDRAC_IP
   ```

2. **Re-add the integration:**
   - Remove the existing iDRAC integration
   - Add it again to trigger fresh discovery
   - The discovery now correctly checks OID .3 directly

3. **Verify in logs:**
   Look for:
   - "Starting power consumption sensor discovery"
   - "Found power consumption sensor at OID"
   - "Creating 1 power_consumption sensors using SNMPDataUpdateCoordinator"

### Why This Happens
- Power consumption uses a fixed OID (not indexed)
- Discovery must find it during config flow
- The data is stored in config entry as `discovered_power_consumption: [1]`
- If missing, no power sensor is created

## Issue 2: PCI7 Health Unavailable

### Root Cause
PCI7 Health is a system voltage binary sensor that was discovered but has no data. This happens when:
1. The voltage probe exists in the system
2. But returns no reading (None/null)
3. The sensor is created but shows as unavailable

### Solutions

#### Option 1: Disable the Sensor
If PCI7 is not relevant to your system:
1. Go to Settings > Devices & Services > Dell iDRAC
2. Find "PCI7 Health" entity
3. Click on it and disable it

#### Option 2: Check Why It's Unavailable
System voltage sensors are created with:
- Entity: `system_voltage_X` 
- Disabled by default: True
- Shows unavailable if reading is None

This is normal for voltage probes that:
- Are defined in the system but not populated
- Are for expansion slots not in use
- Have no actual sensor attached

### Expected Behavior
- Many system voltage sensors are discovered
- Most are disabled by default 
- Some may show as unavailable if not physically present
- This is normal and doesn't indicate a problem

## Testing Power Consumption

Run this to verify your iDRAC supports power via SNMP:
```bash
snmpget -v2c -c public YOUR_IDRAC_IP 1.3.6.1.4.1.674.10892.5.4.600.30.1.6.1.3
```

If this returns a number (watts), then re-adding the integration should make the power sensor appear.

## Summary

1. **Power Consumption**: Re-add integration to trigger proper discovery
2. **PCI7 Health**: Normal behavior - disable if not needed
3. Both issues are related to discovery and data availability