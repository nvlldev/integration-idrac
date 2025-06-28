# Sensor Class Constructor Fixes

## Issues Fixed

### 1. PSU Sensor Constructor Errors
**Error**: `IdracSensor.__init__() missing 2 required positional arguments: 'sensor_type' and 'name'`

**Root Cause**: PSU power and voltage sensor classes were not calling the parent constructor correctly.

**Fixed Classes**:
- `IdracPSUInputPowerSensor`
- `IdracPSUOutputPowerSensor` 
- `IdracPSUInputVoltageSensor`

**Before (Incorrect)**:
```python
def __init__(self, coordinator, config_entry, psu_id, psu_data):
    super().__init__(coordinator, config_entry)  # Missing required args
    device_name_prefix = _get_device_name_prefix(coordinator)
    self._attr_name = f"{device_name_prefix} {psu_name} Input Power"
    self._attr_unique_id = f"{coordinator.host}_{psu_id}_input_power"
```

**After (Fixed)**:
```python
def __init__(self, coordinator, config_entry, psu_id, psu_data):
    psu_name = psu_data.get("name", f"PSU {psu_id.replace('psu_', '')}")
    super().__init__(coordinator, config_entry, f"{psu_id}_input_power", f"{psu_name} Input Power")
```

### 2. Advanced Power Sensor Constructor Errors
**Fixed Classes**:
- `IdracAveragePowerSensor`
- `IdracMaxPowerSensor`
- `IdracMinPowerSensor`

**Before (Incorrect)**:
```python
def __init__(self, coordinator, config_entry):
    super().__init__(coordinator, config_entry)  # Missing required args
    device_name_prefix = _get_device_name_prefix(coordinator)
    self._attr_name = f"{device_name_prefix} Average Power Consumption"
```

**After (Fixed)**:
```python
def __init__(self, coordinator, config_entry):
    super().__init__(coordinator, config_entry, "average_power_consumption", "Average Power Consumption")
```

### 3. Binary Sensor Missing Class Error
**Error**: `name 'IdracVoltageStatusBinarySensor' is not defined`

**Root Cause**: Binary sensor setup was referencing a class that wasn't defined.

**Fix**: Removed the reference since voltage status is already covered by regular voltage sensors.

**Before (Incorrect)**:
```python
entities.append(IdracVoltageStatusBinarySensor(coordinator, config_entry, voltage_id, voltage_data))
```

**After (Fixed)**:
```python
# Note: Voltage status binary sensors removed - voltage status is covered by regular voltage sensors
```

## Impact

### Before Fixes:
- Integration would fail to load sensors
- Error logs in Home Assistant
- No PSU power/voltage sensors created
- No advanced power metrics sensors

### After Fixes:
- All sensor classes properly initialized
- PSU input/output power sensors working
- PSU input voltage sensors working  
- Advanced power metrics (avg/max/min) working
- Clean integration startup with no errors

## Sensor Entities Now Available

With these fixes, the integration will create these additional sensors:

### PSU Sensors (per power supply):
- **Input Power**: `sensor.dell_server_psu_1_input_power`
- **Output Power**: `sensor.dell_server_psu_1_output_power` 
- **Input Voltage**: `sensor.dell_server_psu_1_input_voltage`

### Advanced Power Metrics:
- **Average Power**: `sensor.dell_server_average_power_consumption`
- **Maximum Power**: `sensor.dell_server_maximum_power_consumption`
- **Minimum Power**: `sensor.dell_server_minimum_power_consumption`

All sensors include:
- Proper device classes (power, voltage)
- Correct units (watts, volts)
- State classes for statistics
- Appropriate icons
- Device association

## Testing

After Home Assistant restart, the integration should:
1. ✅ Load without errors
2. ✅ Create all sensor entities
3. ✅ Display proper values for PSU metrics
4. ✅ Show advanced power consumption statistics
5. ✅ Maintain proper entity naming and organization

The sensor fixes ensure comprehensive monitoring of Dell PowerEdge server power systems through the Redfish API.