"""DataUpdateCoordinator for EV Charger KR."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    EvChargerApiClient,
    EvChargerApiError,
    EvChargerAuthError,
    RateLimitInfo,
    StationStatus,
    calculate_auto_scan_interval,
)
from .const import (
    CONF_API_KEY,
    CONF_AUTO_INTERVAL,
    CONF_SCAN_INTERVAL,
    CONF_STATIONS,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    DEFAULT_DAILY_LIMIT,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class CoordinatorData:
    """Combined coordinator payload for all stations and API rate limit."""

    stations: dict[str, StationStatus]
    rate_limit: RateLimitInfo


def extract_entry_stations(entry: ConfigEntry) -> dict[str, str]:
    """Return a mapping of stat_id -> station_name from entry options or data."""
    raw_list = entry.options.get(CONF_STATIONS) or entry.data.get(CONF_STATIONS)
    stations: dict[str, str] = {}
    if isinstance(raw_list, list):
        for item in raw_list:
            if isinstance(item, dict) and item.get(CONF_STATION_ID):
                sid = str(item[CONF_STATION_ID]).strip()
                sname = str(item.get(CONF_STATION_NAME) or sid).strip()
                if sid:
                    stations[sid] = sname

    if not stations and entry.data.get(CONF_STATION_ID):
        sid = str(entry.data[CONF_STATION_ID]).strip()
        sname = str(entry.data.get(CONF_STATION_NAME) or sid).strip()
        stations[sid] = sname

    return stations


class EvChargerCoordinator(DataUpdateCoordinator[CoordinatorData]):
    """Coordinator to poll one or more EV charging stations."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.stations: dict[str, str] = extract_entry_stations(entry)
        self.auto_interval: bool = bool(entry.options.get(CONF_AUTO_INTERVAL, True))
        self.manual_scan_minutes: int = int(
            entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES)
        )

        initial_minutes = (
            calculate_auto_scan_interval(len(self.stations), DEFAULT_DAILY_LIMIT)
            if self.auto_interval
            else self.manual_scan_minutes
        )

        self.client = EvChargerApiClient(
            session=async_get_clientsession(hass),
            api_key=entry.data[CONF_API_KEY],
        )

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(minutes=initial_minutes),
        )

    def _total_registered_stations(self) -> int:
        """Count all stations across loaded EV Charger KR entries."""
        entries = self.hass.data.get(DOMAIN, {})
        total = sum(
            len(coord.stations)
            for coord in entries.values()
            if isinstance(coord, EvChargerCoordinator)
        )
        return max(total, len(self.stations), 1)

    def sync_auto_interval(self) -> None:
        """Recalculate update_interval if automatic interval adjustment is enabled."""
        if not self.auto_interval:
            return
        daily_limit = self.client.rate_limit.limit or DEFAULT_DAILY_LIMIT
        target_minutes = calculate_auto_scan_interval(
            self._total_registered_stations(),
            daily_limit,
        )
        target_delta = timedelta(minutes=target_minutes)
        if self.update_interval != target_delta:
            _LOGGER.debug(
                "Auto-adjusting EV Charger KR polling interval to %s min",
                target_minutes,
            )
            self.update_interval = target_delta

    async def _async_update_data(self) -> CoordinatorData:
        try:
            results: dict[str, StationStatus] = {}
            for stat_id, station_name in self.stations.items():
                results[stat_id] = await self.client.async_get_station_status(
                    stat_id=stat_id,
                    station_name=station_name,
                )
            self.sync_auto_interval()
            return CoordinatorData(
                stations=results,
                rate_limit=RateLimitInfo(
                    remaining=self.client.rate_limit.remaining,
                    limit=self.client.rate_limit.limit,
                ),
            )
        except EvChargerAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except EvChargerApiError as err:
            raise UpdateFailed(f"Error fetching EV charger status: {err}") from err
        except Exception as err:
            raise UpdateFailed(
                f"Unexpected error fetching EV charger status: {err}"
            ) from err
