"""Dell iDRAC Redfish API client."""
from __future__ import annotations

import asyncio
import logging
import ssl
from typing import Any, Dict, Optional

import aiohttp

_LOGGER = logging.getLogger(__name__)


class RedfishError(Exception):
    """Redfish API error."""


class RedfishClient:
    """Dell iDRAC Redfish API client."""

    def __init__(
        self,
        hass,
        host: str,
        username: str,
        password: str,
        port: int = 443,
        verify_ssl: bool = False,
    ) -> None:
        """Initialize the Redfish client."""
        self.hass = hass
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl
        self.base_url = f"https://{host}:{port}"
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None:
            # Create our own session since we need custom SSL settings
            if self.verify_ssl:
                connector = aiohttp.TCPConnector()
            else:
                # Disable SSL verification for older iDRACs
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                connector = aiohttp.TCPConnector(ssl=ssl_context)

            self._session = aiohttp.ClientSession(
                connector=connector,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                timeout=aiohttp.ClientTimeout(total=30),
            )

        return self._session

    async def close(self) -> None:
        """Close the client session."""
        if self._session:
            await self._session.close()
            self._session = None

    async def get(self, path: str) -> Optional[Dict[str, Any]]:
        """Make GET request to Redfish API."""
        url = f"{self.base_url}{path}"
        auth = aiohttp.BasicAuth(self.username, self.password)

        try:
            session = await self._get_session()
            async with session.get(url, auth=auth, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 401:
                    raise RedfishError("Authentication failed - check credentials")
                else:
                    _LOGGER.warning("GET %s failed: %s %s", path, response.status, response.reason)
                    return None
        except asyncio.TimeoutError:
            _LOGGER.warning("GET %s timed out", path)
            return None
        except Exception as e:
            _LOGGER.error("GET %s error: %s", path, e)
            return None

    async def post(self, path: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Make POST request to Redfish API."""
        url = f"{self.base_url}{path}"
        auth = aiohttp.BasicAuth(self.username, self.password)

        try:
            session = await self._get_session()
            async with session.post(
                url, auth=auth, json=data, timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status in [200, 202, 204]:
                    if response.content_length and response.content_length > 0:
                        return await response.json()
                    return {"status": "success"}
                elif response.status == 401:
                    raise RedfishError("Authentication failed - check credentials")
                else:
                    _LOGGER.warning("POST %s failed: %s %s", path, response.status, response.reason)
                    try:
                        error_data = await response.json()
                        _LOGGER.warning("Error details: %s", error_data)
                    except:
                        pass
                    return None
        except asyncio.TimeoutError:
            _LOGGER.warning("POST %s timed out", path)
            return None
        except Exception as e:
            _LOGGER.error("POST %s error: %s", path, e)
            return None

    async def get_service_root(self) -> Optional[Dict[str, Any]]:
        """Get Redfish service root information."""
        return await self.get("/redfish/v1/")

    async def get_system_info(self, system_id: str = "System.Embedded.1") -> Optional[Dict[str, Any]]:
        """Get system information."""
        return await self.get(f"/redfish/v1/Systems/{system_id}")

    async def get_thermal_info(self, system_id: str = "System.Embedded.1") -> Optional[Dict[str, Any]]:
        """Get thermal information (temperatures and fans)."""
        return await self.get(f"/redfish/v1/Chassis/{system_id}/Thermal")

    async def get_power_info(self, system_id: str = "System.Embedded.1") -> Optional[Dict[str, Any]]:
        """Get power information."""
        return await self.get(f"/redfish/v1/Chassis/{system_id}/Power")

    async def get_manager_info(self, manager_id: str = "iDRAC.Embedded.1") -> Optional[Dict[str, Any]]:
        """Get iDRAC manager information."""
        return await self.get(f"/redfish/v1/Managers/{manager_id}")

    async def set_indicator_led(
        self, state: str, system_id: str = "System.Embedded.1"
    ) -> Optional[Dict[str, Any]]:
        """Set system indicator LED state."""
        data = {"IndicatorLEDState": state}
        return await self.post(
            f"/redfish/v1/Systems/{system_id}/Actions/ComputerSystem.IndicatorLEDControl", data
        )

    async def reset_system(
        self, reset_type: str, system_id: str = "System.Embedded.1"
    ) -> Optional[Dict[str, Any]]:
        """Reset system with specified type."""
        data = {"ResetType": reset_type}
        return await self.post(f"/redfish/v1/Systems/{system_id}/Actions/ComputerSystem.Reset", data)

    async def test_connection(self) -> bool:
        """Test connection to iDRAC Redfish API."""
        try:
            service_root = await self.get_service_root()
            return service_root is not None
        except Exception as e:
            _LOGGER.error("Connection test failed: %s", e)
            return False