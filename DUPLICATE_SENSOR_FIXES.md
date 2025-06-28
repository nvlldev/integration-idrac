# Duplicate Sensor Fixes

## Issues Identified

From the Home Assistant screenshots, several problems were found:

1. **Duplicate sensors** appearing in both "Sensors" and "Diagnostic" sections
2. **"Unavailable" Redfish sensors** for chassis intrusion, power state, power redundancy, and system health
3. **Redundant entity types** for the same information

## Root Cause Analysis

### 1. Duplicate Sensor Creation
Both `sensor.py` and `binary_sensor.py` were creating entities for the same data:
- **Power State**: Regular sensor + Binary sensor
- **Chassis Intrusion**: Regular sensor + Binary sensor  
- **Power Redundancy**: Regular sensor + Binary sensor
- **System Health**: Regular sensor + Binary sensor

### 2. Data Format Mismatch
Binary sensors were designed for SNMP integer data but Redfish provides dictionary structures:
- **SNMP**: `system_health = 3` (integer)
- **Redfish**: `system_health = {"overall_status": "OK", "component_count": 5}` (dictionary)

## Fixes Applied

### 1. Removed Duplicate Regular Sensors
Eliminated redundant sensor classes from `sensor.py`:
- ❌ `IdracPowerStateSensor` (removed - binary sensor handles this)
- ❌ `IdracChassisIntrusionSensor` (removed - binary sensor handles this)
- ❌ `IdracPowerRedundancySensor` (removed - binary sensor handles this)
- ❌ `IdracSystemHealthSensor` (removed - binary sensor handles this)

### 2. Updated Binary Sensors for Dual Compatibility
Modified binary sensors to handle both SNMP and Redfish data formats:

#### System Health Binary Sensor
**Before (SNMP only)**:
```python
health_int = int(health_value)
return health_int != 3  # 3=OK, others=problem
```

**After (SNMP + Redfish)**:
```python
# Handle Redfish data format (dictionary)
if isinstance(health_data, dict):
    overall_status = health_data.get("overall_status")
    return overall_status in ["Critical", "Warning"]
# Handle SNMP data format (integer)
else:
    health_int = int(health_data)
    return health_int != 3
```

#### Power Redundancy Binary Sensor
**Before (SNMP only)**:
```python
redundancy_int = int(redundancy_value)
return redundancy_int != 3
```

**After (SNMP + Redfish)**:
```python
# Try Redfish data format first
redundancy_data = self.coordinator.data.get("power_redundancy")
if isinstance(redundancy_data, dict):
    status = redundancy_data.get("status")
    return status in ["Critical", "Warning"]
# Fallback to SNMP data format
```

#### Chassis Intrusion Binary Sensor
**Before (SNMP only)**:
```python
intrusion_int = int(intrusion_value)
return intrusion_int == 2  # 2=breach_detected
```

**After (SNMP + Redfish)**:
```python
# Try Redfish data format first
intrusion_data = self.coordinator.data.get("chassis_intrusion")
if isinstance(intrusion_data, dict):
    status = intrusion_data.get("status")
    return status in ["HardwareIntrusion", "TamperingDetected"]
# Fallback to SNMP data format
```

## Entity Organization After Fixes

### Diagnostic Section (Binary Sensors)
- ✅ **Power State**: On/Off binary sensor
- ✅ **Chassis Intrusion**: Normal/Detected binary sensor
- ✅ **Power Redundancy**: OK/Problem binary sensor  
- ✅ **System Health**: OK/Warning binary sensor

### Sensors Section (Regular Sensors)
- ✅ **Temperature sensors**: CPU1 Temp, CPU2 Temp, System Board temps
- ✅ **Fan sensors**: System Board Fan1-6 with RPM readings
- ✅ **Power sensors**: Consumption, PSU details, advanced metrics
- ✅ **Voltage sensors**: PSU voltages and system voltages
- ✅ **System info**: Total Memory, Processor Count

## Benefits

### 1. No More Duplicates
- Single entity per data point
- Clean organization between binary sensors (status) and regular sensors (measurements)

### 2. Proper Binary Sensor Functionality
- **"Unavailable"** status resolved for Redfish mode
- Binary sensors now work with both SNMP and Redfish data
- Proper true/false states for status monitoring

### 3. Correct Entity Types
- **Status information** → Binary sensors (problem/no problem)
- **Measurement data** → Regular sensors (temperatures, power, etc.)

## Expected Results After Restart

### Before Fixes:
- Duplicate "Power State" in both sections
- "Unavailable" chassis intrusion, power redundancy, system health
- Cluttered entity list with redundant information

### After Fixes:
- ✅ Single "Power State" binary sensor showing On/Off
- ✅ Working chassis intrusion detection
- ✅ Functional power redundancy monitoring
- ✅ System health status indication
- ✅ Clean separation of status vs measurement entities

The integration now provides comprehensive monitoring without duplicate entities while supporting both SNMP and Redfish data sources seamlessly.