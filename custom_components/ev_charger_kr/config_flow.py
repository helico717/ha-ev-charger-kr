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
    StationSummary,
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
    ZCODE_OPTIONS,
)

_LOGGER = logging.getLogger(__name__)

CONF_ZCODE = "zcode"
CONF_KEYWORD = "keyword"


class EvChargerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for EV Charger KR."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow state."""
        self._api_key: str = ""
        self._search_results: list[StationSummary] = []

    def _get_existing_api_key(self) -> str:
        """Return an API key from an already configured entry if available."""
        for entry in self._async_current_entries():
            key = entry.data.get(CONF_API_KEY)
            if isinstance(key, str) and key.strip():
                return key.strip()
        return ""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step: search by region/keyword or enter statId."""
        errors: dict[str, str] = {}

        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            zcode = str(user_input.get(CONF_ZCODE, "11")).strip()
            keyword = str(user_input.get(CONF_KEYWORD, "")).strip()
            stat_id = str(user_input.get(CONF_STATION_ID, "")).strip()

            client = EvChargerApiClient(
                session=async_get_clientsession(self.hass),
                api_key=api_key,
            )

            if stat_id:
                await self.async_set_unique_id(stat_id)
                self._abort_if_unique_id_configured()

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
            elif keyword:
                try:
                    results = await client.async_search_stations(zcode, keyword)
                except EvChargerAuthError:
                    errors["base"] = "invalid_auth"
                except EvChargerApiError:
                    errors["base"] = "cannot_connect"
                except Exception:  # noqa: BLE001
                    _LOGGER.exception("Unexpected exception during station search")
                    errors["base"] = "unknown"
                else:
                    if not results:
                        errors["base"] = "no_stations_found"
                    else:
                        self._api_key = api_key
                        self._search_results = results
                        return await self.async_step_select_station()
            else:
                errors["base"] = "missing_search_or_id"

        default_key = self._get_existing_api_key()
        schema = vol.Schema(
            {
                vol.Required(CONF_API_KEY, default=default_key): str,
                vol.Optional(CONF_ZCODE, default="11"): vol.In(ZCODE_OPTIONS),
                vol.Optional(CONF_KEYWORD, default=""): str,
                vol.Optional(CONF_STATION_ID, default=""): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_select_station(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Let the user choose a charging station from search results."""
        errors: dict[str, str] = {}

        if user_input is not None:
            stat_id = str(user_input[CONF_STATION_ID]).strip()
            await self.async_set_unique_id(stat_id)
            self._abort_if_unique_id_configured()

            client = EvChargerApiClient(
                session=async_get_clientsession(self.hass),
                api_key=self._api_key,
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
                _LOGGER.exception("Unexpected exception during station selection")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=station.station_name,
                    data={
                        CONF_API_KEY: self._api_key,
                        CONF_STATION_ID: stat_id,
                        CONF_STATION_NAME: station.station_name,
                    },
                )

        station_options = {
            s.stat_id: (
                f"{s.station_name} ({s.busi_name or '기타'}, {s.charger_count}대)"
                f" - {s.address or s.stat_id}"
            )
            for s in self._search_results
        }

        return self.async_show_form(
            step_id="select_station",
            data_schema=vol.Schema(
                {vol.Required(CONF_STATION_ID): vol.In(station_options)}
            ),
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
