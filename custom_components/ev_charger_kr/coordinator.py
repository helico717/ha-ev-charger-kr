"""DataUpdateCoordinator for EV Charger KR."""

from __future__ import annotations

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
    StationStatus,
)
from .const import (
    CONF_API_KEY,
    CONF_SCAN_INTERVAL,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class EvChargerCoordinator(DataUpdateCoordinator[StationStatus]):
    """Coordinator to poll EV charging station status."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.stat_id: str = entry.data[CONF_STATION_ID]
        self.station_name: str = entry.data.get(CONF_STATION_NAME, self.stat_id)
        scan_minutes = entry.options.get(
            CONF_SCAN_INTERVAL,
            DEFAULT_SCAN_INTERVAL_MINUTES,
        )

        self.client = EvChargerApiClient(
            session=async_get_clientsession(hass),
            api_key=entry.data[CONF_API_KEY],
        )

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{self.stat_id}",
            update_interval=timedelta(minutes=scan_minutes),
        )

    async def _async_update_data(self) -> StationStatus:
        try:
            return await self.client.async_get_station_status(
                stat_id=self.stat_id,
                station_name=self.station_name,
            )
        except EvChargerAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except EvChargerApiError as err:
            raise UpdateFailed(f"Error fetching EV charger status: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Unexpected error fetching EV charger status: {err}") from err
