"""Config flow for EV Charger KR integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    EvChargerApiClient,
    EvChargerApiError,
    EvChargerAuthError,
    EvChargerNotFoundError,
)
from .const import (
    CONF_API_KEY,
    CONF_SCAN_INTERVAL,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
    MAX_SCAN_INTERVAL_MINUTES,
    MIN_SCAN_INTERVAL_MINUTES,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
        vol.Required(CONF_STATION_ID): str,
    }
)


class EvChargerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for EV Charger KR."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            stat_id = user_input[CONF_STATION_ID].strip()

            await self.async_set_unique_id(stat_id)
            self._abort_if_unique_id_configured()

            client = EvChargerApiClient(
                session=async_get_clientsession(self.hass),
                api_key=api_key,
            )

            try:
                station = await client.async_get_station_info(stat_id)
            except EvChargerAuthError:
                errors["base"] = "invalid_auth"
            except EvChargerNotFoundError:
                errors["base"] = "station_not_found"
            except EvChargerApiError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected exception during EV charger setup")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=station.station_name,
                    data={
                        CONF_API_KEY: api_key,
                        CONF_STATION_ID: stat_id,
                        CONF_STATION_NAME: station.station_name,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return EvChargerOptionsFlow(config_entry)


class EvChargerOptionsFlow(OptionsFlow):
    """Handle options flow for EV Charger KR."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_interval = self._config_entry.options.get(
            CONF_SCAN_INTERVAL,
            DEFAULT_SCAN_INTERVAL_MINUTES,
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=current_interval,
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(
                            min=MIN_SCAN_INTERVAL_MINUTES,
                            max=MAX_SCAN_INTERVAL_MINUTES,
                        ),
                    ),
                }
            ),
        )
