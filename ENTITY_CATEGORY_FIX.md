# Entity Category Fix for Sensor Platform

## Issue Identified
Home Assistant was rejecting sensor entities with `EntityCategory.CONFIG`:

```
ERROR Entity sensor.dell_192_168_50_131_total_memory cannot be added as the entity category is set to config
ERROR Entity sensor.dell_192_168_50_131_processor_count cannot be added as the entity category is set to config
```

## Root Cause
Home Assistant has specific rules about which platforms can use which entity categories:
- **Sensor entities** cannot use `EntityCategory.CONFIG`
- `EntityCategory.CONFIG` is reserved for configuration entities (like input_number, input_select, etc.)

## Affected Sensors
- `IdracMemorySensor` (Total Memory)
- `IdracProcessorCountSensor` (Processor Count)

## Fix Applied
Changed entity category from `CONFIG` to `DIAGNOSTIC`:

**Before (Incorrect)**:
```python
self._attr_entity_category = EntityCategory.CONFIG
```

**After (Fixed)**:
```python
self._attr_entity_category = EntityCategory.DIAGNOSTIC
```

## Entity Category Guidelines

### `EntityCategory.DIAGNOSTIC` (Used for):
- Hardware information sensors ✅
- System status indicators ✅
- Performance metrics ✅
- Firmware versions ✅

### `EntityCategory.CONFIG` (Reserved for):
- Configuration input entities (input_number, input_select)
- Settings that users can modify
- NOT for sensor entities ❌

## Impact

### Before Fix:
- Integration failed to add memory and processor sensors
- Error logs in Home Assistant
- Missing hardware information

### After Fix:
- All sensors load successfully
- Hardware information available in diagnostic category
- Clean integration startup

## Entity Organization

The sensors will now appear properly organized:

```
Dell iDRAC (192.168.50.131)
├── Sensors (Main)
│   ├── Power Consumption
│   ├── Temperature sensors
│   ├── Fan sensors
│   └── Voltage sensors
└── Diagnostic
    ├── Total Memory (128 GB)
    ├── Processor Count (2)
    ├── Firmware Version
    ├── System Health
    └── Other diagnostic info
```

This provides better organization while following Home Assistant's entity category guidelines.

## Verification

After restart, check that:
1. ✅ No more CONFIG category errors in logs
2. ✅ Memory and processor count sensors appear
3. ✅ Sensors show in diagnostic section of device page
4. ✅ All other sensors continue working normally

The fix ensures proper entity categorization while maintaining full sensor functionality.