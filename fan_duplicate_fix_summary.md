# Fan Duplicate Name Fix Summary

## Issue
Servers with dual-fan assemblies (1A/1B, 2A/2B, etc.) were showing duplicate fan names because SNMP reports the same location string for both fans in an assembly (e.g., both Fan 1A and Fan 1B report as "System Board Fan1").

## Solution

### SNMP Mode Fix
In `snmp_processor.py`:
- Added logic to append the fan index to names that contain "fan"
- Format: "System Board Fan1 #3" where 3 is the SNMP index
- This ensures each fan has a unique name even if they share the same location

### Sensor Display Fix  
In `sensor.py`:
- Updated `IdracFanSpeedSensor` to handle the new naming format
- Converts "System Board Fan1 #3" to "System Fan 1.3 Speed" for cleaner display
- Maintains backward compatibility with old format

### Redfish Mode Fix
In `redfish_coordinator.py`:
- Added duplicate name detection using a counter
- Appends "#index" to duplicate names
- Less common in Redfish since it typically provides unique names

## Expected Results

### Before Fix:
```
System Fan 1 Speed (3000 RPM)
System Fan 1 Speed (3000 RPM)  <- Duplicate!
System Fan 2 Speed (3000 RPM)
System Fan 2 Speed (3000 RPM)  <- Duplicate!
```

### After Fix:
```
System Fan 1.1 Speed (3000 RPM)  <- Fan assembly 1, first fan
System Fan 1.2 Speed (3000 RPM)  <- Fan assembly 1, second fan  
System Fan 2.3 Speed (3000 RPM)  <- Fan assembly 2, first fan
System Fan 2.4 Speed (3000 RPM)  <- Fan assembly 2, second fan
```

## Implementation Details

1. **SNMP Discovery**: Fan indices are discovered sequentially (1, 2, 3, 4...)
2. **Name Generation**: Location string + index creates unique identifier
3. **Display Format**: Clean naming pattern "System Fan X.Y Speed"
4. **Entity IDs**: Remain unique using fan_1, fan_2, etc.

## Testing Notes

- Restart Home Assistant after applying the fix
- Check that all fans now have unique names
- Verify fan speeds are still reporting correctly
- Confirm no "duplicate entity" warnings in logs