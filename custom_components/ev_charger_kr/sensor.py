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
from .coordinator import CoordinatorData, EvChargerCoordinator


@dataclass(frozen=True, kw_only=True)
class EvChargerSensorDescription(SensorEntityDescription):
    """Describes an EV Charger KR station sensor entity."""

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
    entities: list[SensorEntity] = [
        EvChargerSensor(coordinator, stat_id, station_name, description)
        for stat_id, station_name in coordinator.stations.items()
        for description in SENSOR_DESCRIPTIONS
    ]
    entities.append(EvChargerApiRateLimitSensor(coordinator, entry))
    async_add_entities(entities)


class EvChargerSensor(CoordinatorEntity[EvChargerCoordinator], SensorEntity):
    """Representation of an EV Charger KR station sensor."""

    entity_description: EvChargerSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EvChargerCoordinator,
        stat_id: str,
        station_name: str,
        description: EvChargerSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self._stat_id = stat_id
        self.entity_description = description
        self._attr_unique_id = f"{stat_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, stat_id)},
            name=station_name,
            manufacturer="한국환경공단 (무공해차 통합누리집)",
            model="전기차 충전소",
            entry_type=DeviceEntryType.SERVICE,
        )

    def _station_status(self) -> StationStatus | None:
        data: CoordinatorData | None = self.coordinator.data
        if data is None:
            return None
        return data.stations.get(self._stat_id)

    @property
    def native_value(self) -> int | None:
        status = self._station_status()
        if status is None:
            return None
        return self.entity_description.value_fn(status)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        status = self._station_status()
        if status is None or self.entity_description.attr_fn is None:
            return None
        return self.entity_description.attr_fn(status)


class EvChargerApiRateLimitSensor(CoordinatorEntity[EvChargerCoordinator], SensorEntity):
    """Sensor reporting remaining daily data.go.kr API quota."""

    _attr_has_entity_name = True
    _attr_translation_key = "api_rate_limit_remaining"
    _attr_icon = "mdi:api"
    _attr_native_unit_of_measurement = "건"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: EvChargerCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_api_rate_limit_remaining"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_api")},
            name="EV Charger KR API",
            manufacturer="공공데이터포털 (한국환경공단)",
            model="Open API 할당량",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> int | None:
        data: CoordinatorData | None = self.coordinator.data
        if data is None:
            return None
        return data.rate_limit.remaining

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        data: CoordinatorData | None = self.coordinator.data
        if data is None:
            return None
        limit = data.rate_limit.limit
        remaining = data.rate_limit.remaining
        used = (
            max(0, limit - remaining)
            if limit is not None and remaining is not None
            else None
        )
        usage_percent = (
            round((used / limit) * 100, 1)
            if used is not None and limit and limit > 0
            else None
        )
        interval_minutes = (
            int(self.coordinator.update_interval.total_seconds() // 60)
            if self.coordinator.update_interval
            else None
        )
        return {
            "daily_limit": limit,
            "used_today": used,
            "usage_percent": usage_percent,
            "polling_interval_minutes": interval_minutes,
            "auto_interval_enabled": self.coordinator.auto_interval,
            "registered_stations_count": len(self.coordinator.stations),
        }
