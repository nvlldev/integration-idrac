"""Config flow for Dell iDRAC integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from pysnmp.hlapi.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    getCmd,
    nextCmd,
)

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_COMMUNITY,
    CONF_DISCOVERED_CPUS,
    CONF_DISCOVERED_FANS,
    CONF_DISCOVERED_MEMORY,
    CONF_DISCOVERED_PSUS,
    CONF_DISCOVERED_VOLTAGE_PROBES,
    CONF_SCAN_INTERVAL,
    DEFAULT_COMMUNITY,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SNMP_WALK_OIDS,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_COMMUNITY, default=DEFAULT_COMMUNITY): str,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(int, vol.Range(min=10, max=300)),
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect and discover sensors."""
    host = data[CONF_HOST]
    port = data[CONF_PORT]
    community = data[CONF_COMMUNITY]

    try:
        engine = SnmpEngine()
        community_data = CommunityData(community)
        transport_target = UdpTransportTarget((host, port), timeout=10, retries=2)
        context_data = ContextData()

        test_oid = ObjectType(ObjectIdentity("1.3.6.1.4.1.674.10892.5.4.600.30.1.6.1.3"))

        error_indication, error_status, error_index, var_binds = await getCmd(
            engine,
            community_data,
            transport_target,
            context_data,
            test_oid,
        )

        if error_indication:
            raise CannotConnect(f"SNMP error indication: {error_indication}")
        
        if error_status:
            raise CannotConnect(f"SNMP error status: {error_status}")

        _LOGGER.info("Successfully connected to iDRAC, discovering sensors...")

        discovered_fans = await _discover_sensors(engine, community_data, transport_target, context_data, SNMP_WALK_OIDS["fans"])
        discovered_cpus = await _discover_cpu_sensors(engine, community_data, transport_target, context_data, SNMP_WALK_OIDS["cpu_temps"])
        discovered_psus = await _discover_psu_sensors(engine, community_data, transport_target, context_data, SNMP_WALK_OIDS["psu_status"])
        discovered_voltage_probes = await _discover_voltage_probes(engine, community_data, transport_target, context_data, SNMP_WALK_OIDS["psu_voltage"])
        # Try multiple memory health OID bases
        discovered_memory = []
        memory_oid_bases = [
            SNMP_WALK_OIDS["memory_health"],  # Current: 1.3.6.1.4.1.674.10892.5.4.1100.50.1.5
            "1.3.6.1.4.1.674.10892.5.4.1100.50.1.6",  # Alternative memory health status
            "1.3.6.1.4.1.674.10892.5.4.1100.50.1.20", # Memory device status
            "1.3.6.1.4.1.674.10892.5.4.1100.50.1.7",  # Memory operational status
            "1.3.6.1.4.1.674.10892.5.4.1100.50.1.8",  # Memory error status
            "1.3.6.1.4.1.674.10892.5.4.1100.50.1.3",  # Memory device type
            "1.3.6.1.4.1.674.10892.5.4.1100.50.1.14", # Memory device status
            "1.3.6.1.4.1.674.10892.5.4.1100.50.1.4",  # Memory device location
            "1.3.6.1.4.1.674.10892.1.1100.50.1.5",    # Legacy iDRAC memory health
            "1.3.6.1.4.1.674.10892.1.1100.50.1.6",    # Legacy memory status
            "1.3.6.1.4.1.674.10892.5.4.1100.50.1",    # Base memory table
        ]
        
        for oid_base in memory_oid_bases:
            _LOGGER.debug("Trying memory discovery with OID base: %s", oid_base)
            memory_results = await _discover_memory_sensors(engine, community_data, transport_target, context_data, oid_base)
            if memory_results:
                discovered_memory.extend(memory_results)
                _LOGGER.info("Found %d memory modules with OID base %s", len(memory_results), oid_base)
                break  # Use the first OID base that works
        
        # Remove duplicates and sort
        discovered_memory = sorted(list(set(discovered_memory)))
        
        # Discover storage components
        discovered_virtual_disks = await _discover_sensors(engine, community_data, transport_target, context_data, SNMP_WALK_OIDS["virtual_disks"])
        discovered_physical_disks = await _discover_sensors(engine, community_data, transport_target, context_data, SNMP_WALK_OIDS["physical_disks"])
        discovered_storage_controllers = await _discover_sensors(engine, community_data, transport_target, context_data, SNMP_WALK_OIDS["storage_controllers"])

        _LOGGER.info("Discovered %d fans, %d CPU temperature sensors, %d PSU sensors, %d voltage probes, %d memory modules, %d virtual disks, %d physical disks, %d storage controllers", 
                     len(discovered_fans), len(discovered_cpus), len(discovered_psus), len(discovered_voltage_probes), len(discovered_memory),
                     len(discovered_virtual_disks), len(discovered_physical_disks), len(discovered_storage_controllers))
        _LOGGER.debug("Fan sensor IDs: %s", discovered_fans)
        _LOGGER.debug("CPU sensor IDs: %s", discovered_cpus)
        _LOGGER.debug("PSU sensor IDs: %s", discovered_psus)
        _LOGGER.debug("Voltage probe IDs: %s", discovered_voltage_probes)
        _LOGGER.debug("Memory module IDs: %s", discovered_memory)
        _LOGGER.debug("Virtual disk IDs: %s", discovered_virtual_disks)
        _LOGGER.debug("Physical disk IDs: %s", discovered_physical_disks)
        _LOGGER.debug("Storage controller IDs: %s", discovered_storage_controllers)

        return {
            "title": f"Dell iDRAC ({host})",
            CONF_DISCOVERED_FANS: discovered_fans,
            CONF_DISCOVERED_CPUS: discovered_cpus,
            CONF_DISCOVERED_PSUS: discovered_psus,
            CONF_DISCOVERED_VOLTAGE_PROBES: discovered_voltage_probes,
            CONF_DISCOVERED_MEMORY: discovered_memory,
            CONF_DISCOVERED_VIRTUAL_DISKS: discovered_virtual_disks,
            CONF_DISCOVERED_PHYSICAL_DISKS: discovered_physical_disks,
            CONF_DISCOVERED_STORAGE_CONTROLLERS: discovered_storage_controllers,
        }

    except Exception as exc:
        raise CannotConnect(f"Cannot connect to iDRAC: {exc}") from exc


async def _discover_sensors(
    engine: SnmpEngine,
    community_data: CommunityData,
    transport_target: UdpTransportTarget,
    context_data: ContextData,
    base_oid: str,
) -> list[int]:
    """Discover available sensors by testing individual OIDs."""
    results = []
    
    try:
        _LOGGER.debug("Testing individual OIDs for base: %s", base_oid)
        
        # Test up to 20 sensor indices (should be more than enough for any server)
        for sensor_id in range(1, 21):
            test_oid = f"{base_oid}.{sensor_id}"
            try:
                error_indication, error_status, error_index, var_binds = await getCmd(
                    engine,
                    community_data,
                    transport_target,
                    context_data,
                    ObjectType(ObjectIdentity(test_oid)),
                )
                
                if not error_indication and not error_status and var_binds:
                    value = var_binds[0][1]
                    if (value is not None 
                        and str(value) != "No Such Object currently exists at this OID"
                        and str(value) != "No Such Instance currently exists at this OID"):
                        try:
                            # Try to convert to a numeric value to ensure it's a valid sensor reading
                            numeric_value = float(value)
                            if numeric_value > 0:  # Only include sensors with positive values
                                results.append(sensor_id)
                                _LOGGER.debug("Found sensor ID %d at OID %s with value: %s", sensor_id, test_oid, value)
                            else:
                                _LOGGER.debug("Sensor ID %d at OID %s has invalid value: %s", sensor_id, test_oid, value)
                        except (ValueError, TypeError):
                            _LOGGER.debug("Sensor ID %d at OID %s has non-numeric value: %s", sensor_id, test_oid, value)
                
            except Exception as exc:
                _LOGGER.debug("Error testing OID %s: %s", test_oid, exc)
                continue

        _LOGGER.info("Direct OID testing for %s found %d sensors: %s", base_oid, len(results), results)
        results.sort()
        
    except Exception as exc:
        _LOGGER.warning("Error discovering sensors for OID %s: %s", base_oid, exc)
    
    return results


async def _discover_cpu_sensors(
    engine: SnmpEngine,
    community_data: CommunityData,
    transport_target: UdpTransportTarget,
    context_data: ContextData,
    base_oid: str,
) -> list[int]:
    """Discover CPU temperature sensors, filtering out inlet/outlet temps."""
    all_temp_sensors = await _discover_sensors(
        engine, community_data, transport_target, context_data, base_oid
    )
    
    return [sensor_id for sensor_id in all_temp_sensors if sensor_id > 2]


async def _discover_psu_sensors(
    engine: SnmpEngine,
    community_data: CommunityData,
    transport_target: UdpTransportTarget,
    context_data: ContextData,
    base_oid: str,
) -> list[int]:
    """Discover PSU sensors by testing status OIDs."""
    results = []
    
    try:
        _LOGGER.debug("Testing PSU status OIDs for base: %s", base_oid)
        
        # Test up to 8 PSU indices (typical server configurations have 1-4 PSUs)
        for psu_id in range(1, 9):
            test_oid = f"{base_oid}.{psu_id}"
            try:
                error_indication, error_status, error_index, var_binds = await getCmd(
                    engine,
                    community_data,
                    transport_target,
                    context_data,
                    ObjectType(ObjectIdentity(test_oid)),
                )
                
                if not error_indication and not error_status and var_binds:
                    value = var_binds[0][1]
                    if (value is not None 
                        and str(value) != "No Such Object currently exists at this OID"
                        and str(value) != "No Such Instance currently exists at this OID"):
                        try:
                            # PSU status should be a valid integer (1-6 range typically)
                            status_value = int(value)
                            if 1 <= status_value <= 6:  # Valid Dell iDRAC status range
                                results.append(psu_id)
                                _LOGGER.debug("Found PSU ID %d at OID %s with status: %s", psu_id, test_oid, value)
                            else:
                                _LOGGER.debug("PSU ID %d at OID %s has invalid status: %s", psu_id, test_oid, value)
                        except (ValueError, TypeError):
                            _LOGGER.debug("PSU ID %d at OID %s has non-integer status: %s", psu_id, test_oid, value)
                
            except Exception as exc:
                _LOGGER.debug("Error testing PSU OID %s: %s", test_oid, exc)
                continue

        _LOGGER.info("PSU discovery for %s found %d PSU sensors: %s", base_oid, len(results), results)
        results.sort()
        
    except Exception as exc:
        _LOGGER.warning("Error discovering PSU sensors for OID %s: %s", base_oid, exc)
    
    return results


async def _discover_voltage_probes(
    engine: SnmpEngine,
    community_data: CommunityData,
    transport_target: UdpTransportTarget,
    context_data: ContextData,
    base_oid: str,
) -> list[int]:
    """Discover voltage probe sensors by testing voltage OIDs with focus on PSU voltage ranges."""
    results = []
    
    try:
        _LOGGER.debug("Testing voltage probe OIDs for base: %s", base_oid)
        
        # Test known PSU voltage probe ranges based on test results
        # Found working probes at indices 27, 28 on test system
        test_ranges = [
            range(25, 35),  # Primary PSU voltage range (includes working 27, 28)
            range(20, 25),  # Secondary range for other PSU configurations
            range(35, 45),  # Extended range for systems with more PSUs
            range(1, 20),   # Lower range for other voltage probes (less likely PSU)
        ]
        
        for test_range in test_ranges:
            for probe_id in test_range:
                test_oid = f"{base_oid}.{probe_id}"
                try:
                    error_indication, error_status, error_index, var_binds = await getCmd(
                        engine,
                        community_data,
                        transport_target,
                        context_data,
                        ObjectType(ObjectIdentity(test_oid)),
                    )
                    
                    if not error_indication and not error_status and var_binds:
                        value = var_binds[0][1]
                        if (value is not None 
                            and str(value) != "No Such Object currently exists at this OID"
                            and str(value) != "No Such Instance currently exists at this OID"
                            and str(value).strip() != ""):  # Handle empty string values
                            try:
                                # Voltage probe reading should be a valid integer (millivolts)
                                voltage_value = int(value)
                                # PSU voltages can range from 3V to 240V (3000-240000 mV)
                                # Expanded range based on test results showing 120V PSUs
                                if 3000 <= voltage_value <= 240000:  # 3V to 240V range for PSU voltages
                                    results.append(probe_id)
                                    voltage_v = voltage_value / 1000.0
                                    _LOGGER.debug("Found PSU voltage probe ID %d at OID %s with value: %s mV (%.3f V)", probe_id, test_oid, voltage_value, voltage_v)
                                elif voltage_value > 0:
                                    # Log other voltage probes for reference but don't include them
                                    voltage_v = voltage_value / 1000.0
                                    _LOGGER.debug("Found other voltage probe ID %d at OID %s with value: %s mV (%.3f V) - outside PSU voltage range", probe_id, test_oid, voltage_value, voltage_v)
                            except (ValueError, TypeError):
                                _LOGGER.debug("Voltage probe ID %d at OID %s has non-numeric value: %s", probe_id, test_oid, value)
                    
                except Exception as exc:
                    _LOGGER.debug("Error testing voltage probe OID %s: %s", test_oid, exc)
                    continue

        _LOGGER.info("Voltage probe discovery for %s found %d PSU voltage sensors: %s", base_oid, len(results), results)
        results.sort()
        
    except Exception as exc:
        _LOGGER.warning("Error discovering voltage probes for OID %s: %s", base_oid, exc)
    
    return results


async def _discover_memory_sensors(
    engine: SnmpEngine,
    community_data: CommunityData,
    transport_target: UdpTransportTarget,
    context_data: ContextData,
    base_oid: str,
) -> list[int]:
    """Discover memory module health sensors."""
    results = []
    
    try:
        _LOGGER.debug("Testing memory health OIDs for base: %s", base_oid)
        
        # Test up to 24 memory slots and also try some common indices
        # Some systems start at different indices
        test_indices = list(range(1, 25)) + [26, 27, 28, 29, 30, 31, 32]
        for memory_id in test_indices:
            test_oid = f"{base_oid}.{memory_id}"
            try:
                error_indication, error_status, error_index, var_binds = await getCmd(
                    engine,
                    community_data,
                    transport_target,
                    context_data,
                    ObjectType(ObjectIdentity(test_oid)),
                )
                
                if not error_indication and not error_status and var_binds:
                    value = var_binds[0][1]
                    value_str = str(value)
                    if (value is not None 
                        and "No Such Object" not in value_str
                        and "No Such Instance" not in value_str
                        and "noSuchObject" not in value_str
                        and "noSuchInstance" not in value_str):
                        try:
                            # Memory health status should be a valid integer
                            # Accept a very wide range as different iDRAC versions use different values
                            health_value = int(value)
                            if 0 <= health_value <= 255:  # Very broad range to catch any valid responses
                                results.append(memory_id)
                                _LOGGER.debug("Found memory module ID %d at OID %s with health: %s", memory_id, test_oid, value)
                            else:
                                _LOGGER.debug("Memory module ID %d at OID %s has out-of-range health: %s", memory_id, test_oid, value)
                        except (ValueError, TypeError):
                            # Some systems might return text values, so let's accept those too
                            value_str = str(value).strip()
                            if value_str and len(value_str) < 100 and not value_str.lower().startswith('no such'):  # Basic sanity check
                                results.append(memory_id)
                                _LOGGER.debug("Found memory module ID %d at OID %s with text health: %s", memory_id, test_oid, value)
                            else:
                                _LOGGER.debug("Memory module ID %d at OID %s has invalid health: %s", memory_id, test_oid, value)
                
            except Exception as exc:
                _LOGGER.debug("Error testing memory OID %s: %s", test_oid, exc)
                continue

        _LOGGER.info("Memory discovery for %s found %d memory modules: %s", base_oid, len(results), results)
        results.sort()
        
    except Exception as exc:
        _LOGGER.warning("Error discovering memory modules for OID %s: %s", base_oid, exc)
    
    return results


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Dell iDRAC."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return OptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                unique_id = f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                
                # Add discovered sensor info to the config data
                config_data = user_input.copy()
                config_data[CONF_DISCOVERED_FANS] = info[CONF_DISCOVERED_FANS]
                config_data[CONF_DISCOVERED_CPUS] = info[CONF_DISCOVERED_CPUS]
                config_data[CONF_DISCOVERED_PSUS] = info[CONF_DISCOVERED_PSUS]
                config_data[CONF_DISCOVERED_VOLTAGE_PROBES] = info[CONF_DISCOVERED_VOLTAGE_PROBES]
                config_data[CONF_DISCOVERED_MEMORY] = info[CONF_DISCOVERED_MEMORY]
                
                return self.async_create_entry(title=info["title"], data=config_data)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class OptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Dell iDRAC."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            if user_input.get("rediscover_sensors", False):
                # User wants to re-discover sensors
                return await self.async_step_rediscover()
            
            return self.async_create_entry(title="", data=user_input)

        current_scan_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, 
            self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=current_scan_interval
                    ): vol.All(int, vol.Range(min=10, max=300)),
                    vol.Optional("rediscover_sensors", default=False): bool,
                }
            ),
        )

    async def async_step_rediscover(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Re-discover sensors."""
        if user_input is not None:
            # User confirmed re-discovery
            try:
                # Re-run sensor discovery using existing connection info
                info = await validate_input(self.hass, self.config_entry.data)
                
                # Update the config entry with new discovery data
                new_data = self.config_entry.data.copy()
                new_data[CONF_DISCOVERED_FANS] = info[CONF_DISCOVERED_FANS]
                new_data[CONF_DISCOVERED_CPUS] = info[CONF_DISCOVERED_CPUS]
                new_data[CONF_DISCOVERED_PSUS] = info[CONF_DISCOVERED_PSUS]
                new_data[CONF_DISCOVERED_VOLTAGE_PROBES] = info[CONF_DISCOVERED_VOLTAGE_PROBES]
                new_data[CONF_DISCOVERED_MEMORY] = info[CONF_DISCOVERED_MEMORY]
                
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=new_data
                )
                
                # Get current options
                current_options = self.config_entry.options.copy()
                
                return self.async_create_entry(title="", data=current_options)
                
            except CannotConnect:
                return self.async_show_form(
                    step_id="rediscover",
                    errors={"base": "cannot_connect"},
                    description_placeholders={"error": "Failed to connect to iDRAC"},
                )
            except Exception as exc:
                _LOGGER.exception("Failed to re-discover sensors")
                return self.async_show_form(
                    step_id="rediscover",
                    errors={"base": "unknown"},
                    description_placeholders={"error": str(exc)},
                )

        return self.async_show_form(
            step_id="rediscover",
            data_schema=vol.Schema({}),
            description_placeholders={
                "host": self.config_entry.data[CONF_HOST],
                "fans": len(self.config_entry.data.get(CONF_DISCOVERED_FANS, [])),
                "cpus": len(self.config_entry.data.get(CONF_DISCOVERED_CPUS, [])),
                "psus": len(self.config_entry.data.get(CONF_DISCOVERED_PSUS, [])),
                "voltages": len(self.config_entry.data.get(CONF_DISCOVERED_VOLTAGE_PROBES, [])),
                "memory": len(self.config_entry.data.get(CONF_DISCOVERED_MEMORY, [])),
            },
        )