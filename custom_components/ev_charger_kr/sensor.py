"""Sensor platform for EV Charger KR."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import StationStatus
from .const import DOMAIN
from .coordinator import EvChargerCoordinator


@dataclass(frozen=True, kw_only=True)
class EvChargerSensorDescription(SensorEntityDescription):
    """Describes an EV Charger KR sensor entity."""

    value_fn: Callable[[StationStatus], int]
    attr_fn: Callable[[StationStatus], dict[str, Any]] | None = None


def _available_attributes(status: StationStatus) -> dict[str, Any]:
    return {
        "stat_id": status.stat_id,
        "station_name": status.station_name,
        "address": status.address,
        "total_chargers": status.total_count,
        "charging_chargers": status.charging_count,
        "unavailable_chargers": status.unavailable_count,
        "fast_available_chargers": status.fast_available_count,
        "slow_available_chargers": status.slow_available_count,
        "chargers": [
            {
                "charger_id": c.charger_id,
                "status": c.stat_label,
                "status_code": c.stat,
                "type": c.charger_type_label,
                "output_kw": c.output_kw,
                "updated_at": c.stat_updated_at,
            }
            for c in status.chargers
        ],
    }


SENSOR_DESCRIPTIONS: tuple[EvChargerSensorDescription, ...] = (
    EvChargerSensorDescription(
        key="available_chargers",
        translation_key="available_chargers",
        icon="mdi:ev-station",
        native_unit_of_measurement="대",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.available_count,
        attr_fn=_available_attributes,
    ),
    EvChargerSensorDescription(
        key="charging_chargers",
        translation_key="charging_chargers",
        icon="mdi:battery-charging",
        native_unit_of_measurement="대",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.charging_count,
    ),
    EvChargerSensorDescription(
        key="total_chargers",
        translation_key="total_chargers",
        icon="mdi:ev-plug-type2",
        native_unit_of_measurement="대",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.total_count,
    ),
    EvChargerSensorDescription(
        key="unavailable_chargers",
        translation_key="unavailable_chargers",
        icon="mdi:alert-circle-outline",
        native_unit_of_measurement="대",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.unavailable_count,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EV Charger KR sensor entities from a config entry."""
    coordinator: EvChargerCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        EvChargerSensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
    )


class EvChargerSensor(CoordinatorEntity[EvChargerCoordinator], SensorEntity):
    """Representation of an EV Charger KR sensor."""

    entity_description: EvChargerSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EvChargerCoordinator,
        description: EvChargerSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.stat_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.stat_id)},
            name=coordinator.station_name,
            manufacturer="한국환경공단 (무공해차 통합누리집)",
            model="전기차 충전소",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> int | None:
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.coordinator.data is None or self.entity_description.attr_fn is None:
            return None
        return self.entity_description.attr_fn(self.coordinator.data)
