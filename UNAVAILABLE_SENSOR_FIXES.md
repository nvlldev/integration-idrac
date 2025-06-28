# Unavailable Sensor Fixes

## Issues Identified

From the Home Assistant interface, these binary sensors were showing as "Unavailable":
- **Chassis Intrusion** 
- **Power State**
- **Power Supply Redundancy** (likely working after previous fixes)
- **System Health** (likely working after previous fixes)

## Root Cause Analysis

### 1. Data Format Mismatch
Binary sensors were designed for SNMP integer data but Redfish provides different formats:

**SNMP Expected:**
- Power State: `1` (integer - 1=on, 2=off)
- Chassis Intrusion: `2` (integer - 1=secure, 2=breach)

**Redfish Actual (from test results):**
- Power State: `"On"` (string - "On"/"Off")
- Chassis Intrusion: `"Unknown"` (string - status from PhysicalSecurity)

### 2. Missing Data Handling
Binary sensors didn't handle "Unknown" or null values properly, causing them to return `None` (unavailable).

## Fixes Applied

### 1. Power State Binary Sensor

**Before (SNMP only)**:
```python
power_int = int(power_state)
return power_int == 1  # 1=on, 2=off
```

**After (SNMP + Redfish)**:
```python
# Handle Redfish string format
if isinstance(power_state, str):
    return power_state.lower() == "on"
# Handle SNMP integer format
else:
    power_int = int(power_state)
    return power_int == 1
```

### 2. Chassis Intrusion Binary Sensor

**Before (SNMP only)**:
```python
intrusion_int = int(intrusion_value)
return intrusion_int == 2  # 2=breach_detected
```

**After (SNMP + Redfish with Unknown handling)**:
```python
# Try Redfish data format first
if isinstance(intrusion_data, dict):
    status = intrusion_data.get("status")
    if status and status != "Unknown":
        return status in ["HardwareIntrusion", "TamperingDetected"]
    elif status == "Unknown":
        # If intrusion sensor status is unknown, consider it as no intrusion (false)
        return False
# Fallback to SNMP data format
```

### 3. Enhanced State Attributes

Added better state attributes to show data source and format:

**Power State Attributes**:
```python
# Redfish format
{
    "power_state": "On",
    "format": "redfish"
}

# SNMP format  
{
    "power_code": 1,
    "power_text": "on",
    "format": "snmp"
}
```

## Expected Data Sources

Based on our test script results from `192.168.50.131`:

### Power State
- **Value**: `"On"` (from `/redfish/v1/Systems/System.Embedded.1`)
- **Expected Result**: `is_on = True`

### Chassis Intrusion  
- **Value**: `"Unknown"` (from `/redfish/v1/Chassis/System.Embedded.1` PhysicalSecurity)
- **Expected Result**: `is_on = False` (no intrusion detected, unknown treated as safe)

### System Health
- **Value**: `{"overall_status": "Warning", "component_count": 5}` (calculated from components)
- **Expected Result**: `is_on = True` (Warning indicates problem)

### Power Redundancy
- **Value**: `{"status": "OK", "total_psus": 2, "healthy_psus": 2}` (from PSU analysis)
- **Expected Result**: `is_on = False` (OK means no problem)

## Expected Results After Restart

### Before Fixes:
- Chassis Intrusion: **Unavailable** ❌
- Power State: **Unavailable** ❌  
- Power Supply Redundancy: **Unavailable** ❌
- System Health: **Unavailable** ❌

### After Fixes:
- Chassis Intrusion: **Normal** (Off) ✅
- Power State: **On** (On) ✅
- Power Supply Redundancy: **OK** (Off) ✅  
- System Health: **Warning** (On) ✅

## Verification Steps

1. **Check Entity States**: Binary sensors should show proper On/Off states
2. **Check Attributes**: State attributes should show data source and values
3. **Check Device Page**: All sensors should appear in diagnostic section
4. **Check Logs**: No more "unavailable" warnings for these entities

## Data Flow Validation

The integration now properly handles both protocols:
- **SNMP → Integer codes → Boolean states**
- **Redfish → String/Dict values → Boolean states**  
- **Unknown/Null values → Safe default states**

This ensures consistent binary sensor functionality regardless of the underlying data protocol.