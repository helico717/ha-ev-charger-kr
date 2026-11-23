"""Config flow for EV Charger KR integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api import (
    EvChargerApiClient,
    EvChargerApiError,
    EvChargerAuthError,
    EvChargerNotFoundError,
    StationSummary,
)
from .const import (
    CONF_API_KEY,
    CONF_AUTO_INTERVAL,
    CONF_SCAN_INTERVAL,
    CONF_STATIONS,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
    MAX_SCAN_INTERVAL_MINUTES,
    MIN_SCAN_INTERVAL_MINUTES,
    ZCODE_OPTIONS,
)
from .coordinator import extract_entry_stations

_LOGGER = logging.getLogger(__name__)

CONF_ZCODE = "zcode"
CONF_KEYWORD = "keyword"


def _build_entry_title(stations: list[dict[str, str]]) -> str:
    """Build a concise config entry title from one or more stations."""
    if not stations:
        return "EV Charger KR"
    first_name = stations[0].get(CONF_STATION_NAME) or stations[0][CONF_STATION_ID]
    if len(stations) == 1:
        return first_name
    return f"{first_name} 외 {len(stations) - 1}곳"


def _station_checkbox_selector(results: list[StationSummary]) -> SelectSelector:
    """Build a multi-select checkbox selector for station search results."""
    options = [
        SelectOptionDict(
            value=s.stat_id,
            label=(
                f"{s.station_name} ({s.busi_name or '기타'}, {s.charger_count}대)"
                f" - {s.address or s.stat_id}"
            ),
        )
        for s in results
    ]
    return SelectSelector(
        SelectSelectorConfig(
            options=options,
            multiple=True,
            mode=SelectSelectorMode.LIST,
        )
    )


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
                    stations = [
                        {
                            CONF_STATION_ID: stat_id,
                            CONF_STATION_NAME: station.station_name,
                        }
                    ]
                    return self.async_create_entry(
                        title=_build_entry_title(stations),
                        data={
                            CONF_API_KEY: api_key,
                            CONF_STATIONS: stations,
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
        """Let the user choose one or more charging stations via checkboxes."""
        errors: dict[str, str] = {}
        summary_map = {s.stat_id: s for s in self._search_results}

        if user_input is not None:
            selected_ids = [
                str(sid).strip()
                for sid in (user_input.get(CONF_STATIONS) or [])
                if str(sid).strip()
            ]
            if not selected_ids:
                errors["base"] = "no_station_selected"
            else:
                stations = [
                    {
                        CONF_STATION_ID: sid,
                        CONF_STATION_NAME: (
                            summary_map[sid].station_name
                            if sid in summary_map
                            else sid
                        ),
                    }
                    for sid in selected_ids
                ]
                return self.async_create_entry(
                    title=_build_entry_title(stations),
                    data={
                        CONF_API_KEY: self._api_key,
                        CONF_STATIONS: stations,
                    },
                )

        return self.async_show_form(
            step_id="select_station",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_STATIONS): _station_checkbox_selector(
                        self._search_results
                    )
                }
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
        self._search_results: list[StationSummary] = []

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show options menu."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["interval", "add_station", "manage_stations"],
        )

    async def async_step_interval(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure automatic or manual polling interval."""
        if user_input is not None:
            new_options = {
                **self._config_entry.options,
                CONF_AUTO_INTERVAL: bool(user_input[CONF_AUTO_INTERVAL]),
                CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
            }
            return self.async_create_entry(title="", data=new_options)

        auto_enabled = bool(self._config_entry.options.get(CONF_AUTO_INTERVAL, True))
        current_interval = int(
            self._config_entry.options.get(
                CONF_SCAN_INTERVAL,
                DEFAULT_SCAN_INTERVAL_MINUTES,
            )
        )

        return self.async_show_form(
            step_id="interval",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_AUTO_INTERVAL, default=auto_enabled): bool,
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

    async def async_step_add_station(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Search and add more stations from any region."""
        errors: dict[str, str] = {}

        if user_input is not None:
            zcode = str(user_input.get(CONF_ZCODE, "11")).strip()
            keyword = str(user_input.get(CONF_KEYWORD, "")).strip()
            stat_id = str(user_input.get(CONF_STATION_ID, "")).strip()

            client = EvChargerApiClient(
                session=async_get_clientsession(self.hass),
                api_key=self._config_entry.data[CONF_API_KEY],
            )

            if stat_id:
                try:
                    station = await client.async_get_station_info(stat_id)
                except EvChargerAuthError:
                    errors["base"] = "invalid_auth"
                except EvChargerNotFoundError:
                    errors["base"] = "station_not_found"
                except EvChargerApiError:
                    errors["base"] = "cannot_connect"
                except Exception:  # noqa: BLE001
                    _LOGGER.exception("Unexpected exception adding station")
                    errors["base"] = "unknown"
                else:
                    existing = extract_entry_stations(self._config_entry)
                    existing[stat_id] = station.station_name
                    stations = [
                        {CONF_STATION_ID: sid, CONF_STATION_NAME: sname}
                        for sid, sname in existing.items()
                    ]
                    return self.async_create_entry(
                        title="",
                        data={**self._config_entry.options, CONF_STATIONS: stations},
                    )
            elif keyword:
                try:
                    results = await client.async_search_stations(zcode, keyword)
                except EvChargerAuthError:
                    errors["base"] = "invalid_auth"
                except EvChargerApiError:
                    errors["base"] = "cannot_connect"
                except Exception:  # noqa: BLE001
                    _LOGGER.exception("Unexpected exception searching stations")
                    errors["base"] = "unknown"
                else:
                    if not results:
                        errors["base"] = "no_stations_found"
                    else:
                        self._search_results = results
                        return await self.async_step_add_station_select()
            else:
                errors["base"] = "missing_search_or_id"

        return self.async_show_form(
            step_id="add_station",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_ZCODE, default="11"): vol.In(ZCODE_OPTIONS),
                    vol.Optional(CONF_KEYWORD, default=""): str,
                    vol.Optional(CONF_STATION_ID, default=""): str,
                }
            ),
            errors=errors,
        )

    async def async_step_add_station_select(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select one or more stations to append to this entry."""
        errors: dict[str, str] = {}
        summary_map = {s.stat_id: s for s in self._search_results}

        if user_input is not None:
            selected_ids = [
                str(sid).strip()
                for sid in (user_input.get(CONF_STATIONS) or [])
                if str(sid).strip()
            ]
            if not selected_ids:
                errors["base"] = "no_station_selected"
            else:
                existing = extract_entry_stations(self._config_entry)
                for sid in selected_ids:
                    existing[sid] = (
                        summary_map[sid].station_name
                        if sid in summary_map
                        else sid
                    )
                stations = [
                    {CONF_STATION_ID: sid, CONF_STATION_NAME: sname}
                    for sid, sname in existing.items()
                ]
                return self.async_create_entry(
                    title="",
                    data={**self._config_entry.options, CONF_STATIONS: stations},
                )

        return self.async_show_form(
            step_id="add_station_select",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_STATIONS): _station_checkbox_selector(
                        self._search_results
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_manage_stations(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Keep or remove currently registered stations."""
        errors: dict[str, str] = {}
        existing = extract_entry_stations(self._config_entry)

        if user_input is not None:
            kept_ids = [
                str(sid).strip()
                for sid in (user_input.get(CONF_STATIONS) or [])
                if str(sid).strip()
            ]
            if not kept_ids:
                errors["base"] = "no_station_selected"
            else:
                stations = [
                    {CONF_STATION_ID: sid, CONF_STATION_NAME: existing[sid]}
                    for sid in kept_ids
                    if sid in existing
                ]
                return self.async_create_entry(
                    title="",
                    data={**self._config_entry.options, CONF_STATIONS: stations},
                )

        options = [
            SelectOptionDict(value=sid, label=f"{sname} ({sid})")
            for sid, sname in existing.items()
        ]
        selector = SelectSelector(
            SelectSelectorConfig(
                options=options,
                multiple=True,
                mode=SelectSelectorMode.LIST,
            )
        )

        return self.async_show_form(
            step_id="manage_stations",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_STATIONS, default=list(existing.keys())
                    ): selector
                }
            ),
            errors=errors,
        )
