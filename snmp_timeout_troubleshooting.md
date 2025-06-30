# SNMP Timeout Troubleshooting Guide

## Issue Description

When the SNMP timeout is set too low (default is often 1-3 seconds), several sensors may fail to appear or show incorrect names:

### Symptoms

1. **Missing Power Consumption Sensors**
   - Power (Watts) sensor doesn't appear despite the server supporting power monitoring
   - Energy (kWh) sensor is also missing (depends on power sensor)

2. **Generic Temperature Names**
   - Temperature sensors show as "Temperature 1", "Temperature 2" instead of descriptive names
   - Should show names like "Inlet Temp", "Outlet Temp", "CPU1 Temp", etc.

3. **Other Missing Sensors**
   - Various sensors may be missing if their discovery/data collection times out

## Root Cause

The iDRAC integration performs multiple SNMP operations during:

1. **Discovery Phase** (during integration setup)
   - Checks multiple OIDs to determine which sensors are available
   - Each sensor type requires separate SNMP queries
   - Power discovery checks specific indices that may take longer to respond

2. **Data Collection Phase** (ongoing updates)
   - Retrieves numeric values (temperatures, fan speeds, power consumption)
   - Retrieves string values (sensor names, locations, status descriptions)
   - String retrieval operations often take longer than numeric operations

When the timeout is too short, these operations fail, causing:
- Discovery to miss sensors entirely
- String retrieval to fail, resulting in fallback names

## Solution

### Increase SNMP Timeout

Set the SNMP timeout to at least **30 seconds** during integration setup:

1. When adding the iDRAC integration
2. In the configuration dialog, look for "SNMP Timeout"
3. Change from default (1-3 seconds) to 30 seconds

### Why 30 Seconds?

- Allows time for all discovery operations to complete
- Ensures string retrieval (sensor names) succeeds
- Provides buffer for slower network conditions or busy iDRACs
- After initial discovery, ongoing updates are typically faster

## Technical Details

### Affected Operations

1. **Power Sensor Discovery** (`snmp_discovery.py:discover_power_consumption_sensors`)
   - Checks OID `1.3.6.1.4.1.674.10892.5.4.600.30.1.6.1.3` (and others)
   - May timeout before discovering power sensors

2. **Temperature Name Retrieval** (`snmp_processor.py:_process_temperatures`)
   - Retrieves location strings from OID `1.3.6.1.4.1.674.10892.5.4.700.20.1.8.1.{index}`
   - Falls back to "Temperature {id}" when string retrieval times out

3. **Other String Retrievals**
   - Fan locations
   - PSU names
   - Memory module details
   - Various status descriptions

### Configuration Storage

The discovered sensors are stored in the Home Assistant config entry:
- `discovered_power_consumption`: List of discovered power sensor indices
- `discovered_temperatures`: List of discovered temperature sensor indices
- And similar for other sensor types

If discovery times out, these lists may be empty or incomplete, permanently affecting sensor availability until the integration is reconfigured.

## Verification

After increasing the timeout and reconfiguring:

1. Check for Power Consumption sensor (Watts)
2. Verify temperature sensors show descriptive names
3. Confirm all expected sensors are present

Enable debug logging to see discovery details:
```yaml
logger:
  default: info
  logs:
    custom_components.idrac: debug
```

Look for messages like:
- "Found power consumption sensor at OID..."
- "Discovered temperature sensors: [1, 2, 3, ...]"
- "Temperature sensor 1: name='Inlet Temp'"