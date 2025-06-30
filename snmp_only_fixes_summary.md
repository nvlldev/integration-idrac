# SNMP-Only Mode Fixes Summary

## Issues Fixed

### 1. **KeyError: 'port' in entity_base.py**
- **Problem**: Binary sensor entities failed to initialize because `port` key was missing from config data in SNMP-only mode
- **Solution**: Changed `config_entry.data[CONF_PORT]` to `config_entry.data.get(CONF_PORT, 443)` to use default port 443 when not present
- **File**: `custom_components/idrac/entity_base.py` line 34

### 2. **KeyError: 'redfish' in switch.py**
- **Problem**: Switch platform tried to access non-existent redfish coordinator in SNMP-only mode
- **Solution**: Changed `coordinators["redfish"]` to `coordinators.get("redfish")` to safely handle missing coordinator
- **File**: `custom_components/idrac/switch.py` line 28

### 3. **KeyError: 'redfish' in button.py**
- **Problem**: Button platform tried to access non-existent redfish coordinator in SNMP-only mode
- **Solution**: Changed `coordinators["redfish"]` to `coordinators.get("redfish")` to safely handle missing coordinator
- **File**: `custom_components/idrac/button.py` line 28

## Expected Behavior After Fixes

### SNMP-Only Mode:
- ✅ Binary sensors initialize properly without port information
- ✅ Switch platform skips creation (no switches in SNMP-only mode)
- ✅ Button platform skips creation (no control buttons in SNMP-only mode)
- ✅ Only monitoring sensors are created (no control entities)

### Hybrid/Redfish Modes:
- ✅ All entities continue to work as before
- ✅ Port defaults to 443 if not specified
- ✅ Switch and button entities created when Redfish coordinator exists

## Why These Entities Don't Work in SNMP-Only Mode

1. **Switches** (Identify LED): Require Redfish API for control operations
2. **Buttons** (Power control): Require Redfish API for system control commands
3. **Port**: Not needed for SNMP communication (uses UDP port 161)

## Testing Checklist

- [ ] Restart Home Assistant with the fixes
- [ ] Verify no more KeyError exceptions in the logs
- [ ] Confirm binary sensors load successfully
- [ ] Check that switches/buttons are skipped with debug log messages
- [ ] Verify all SNMP sensors (40+) appear and update correctly