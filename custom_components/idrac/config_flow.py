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
    DEFAULT_COMMUNITY,
    DEFAULT_PORT,
    DOMAIN,
    SNMP_WALK_OIDS,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, description="Hostname or IP Address"): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT, description="SNMP Port"): int,
        vol.Optional(CONF_COMMUNITY, default=DEFAULT_COMMUNITY, description="SNMP Community String"): str,
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

        _LOGGER.info("Discovered %d fans and %d CPU temperature sensors", len(discovered_fans), len(discovered_cpus))

        return {
            "title": f"Dell iDRAC ({host})",
            CONF_DISCOVERED_FANS: discovered_fans,
            CONF_DISCOVERED_CPUS: discovered_cpus,
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
    """Discover available sensors by walking the SNMP tree."""
    results = []
    
    try:
        async for error_indication, error_status, error_index, var_binds in nextCmd(
            engine,
            community_data,
            transport_target,
            context_data,
            ObjectType(ObjectIdentity(base_oid)),
            lexicographicMode=False,
            maxRows=20,
        ):
            if error_indication or error_status:
                break
            
            for var_bind in var_binds:
                oid_str = str(var_bind[0])
                if oid_str.startswith(f"{base_oid}."):
                    try:
                        sensor_id = int(oid_str.split(".")[-1])
                        if var_bind[1] is not None:
                            results.append(sensor_id)
                    except (ValueError, IndexError):
                        continue

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


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Dell iDRAC."""

    VERSION = 1

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
                
                return self.async_create_entry(title=info["title"], data=config_data)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""