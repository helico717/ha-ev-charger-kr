"""The EV Charger KR integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import EvChargerCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


def _sync_all_auto_intervals(hass: HomeAssistant) -> None:
    """Recompute auto polling intervals for all loaded coordinators."""
    for coord in hass.data.get(DOMAIN, {}).values():
        if isinstance(coord, EvChargerCoordinator):
            coord.sync_auto_interval()


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up EV Charger KR from a config entry."""
    coordinator = EvChargerCoordinator(hass, entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await coordinator.async_config_entry_first_refresh()
    _sync_all_auto_intervals(hass)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        _sync_all_auto_intervals(hass)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
