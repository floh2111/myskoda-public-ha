"""Binärsensoren."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SkodaConfigEntry
from .coordinator import SkodaCoordinator
from .entity import SkodaEntity, dig


def _eq(path: tuple[str, ...], value: str) -> Callable[[dict[str, Any]], bool | None]:
    """True, wenn Feld == value; None (unbekannt), wenn Feld fehlt oder UNKNOWN ist."""

    def fn(v: dict[str, Any]) -> bool | None:
        raw = dig(v, *path)
        if raw is None or raw in ("UNKNOWN", "UNSUPPORTED"):
            return None
        return raw == value

    return fn


@dataclass(frozen=True, kw_only=True)
class SkodaBinaryDescription(BinarySensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], bool | None]


BINARY_SENSORS: tuple[SkodaBinaryDescription, ...] = (
    SkodaBinaryDescription(
        key="doors",
        translation_key="doors",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=_eq(("status", "overall", "doors"), "OPEN"),
    ),
    SkodaBinaryDescription(
        key="windows",
        translation_key="windows",
        device_class=BinarySensorDeviceClass.WINDOW,
        value_fn=_eq(("status", "overall", "windows"), "OPEN"),
    ),
    SkodaBinaryDescription(
        key="lights",
        translation_key="lights",
        device_class=BinarySensorDeviceClass.LIGHT,
        value_fn=_eq(("status", "overall", "lights"), "ON"),
    ),
    SkodaBinaryDescription(
        key="trunk",
        translation_key="trunk",
        device_class=BinarySensorDeviceClass.OPENING,
        value_fn=_eq(("status", "detail", "trunk"), "OPEN"),
    ),
    SkodaBinaryDescription(
        key="bonnet",
        translation_key="bonnet",
        device_class=BinarySensorDeviceClass.OPENING,
        value_fn=_eq(("status", "detail", "bonnet"), "OPEN"),
    ),
    SkodaBinaryDescription(
        key="sunroof",
        translation_key="sunroof",
        device_class=BinarySensorDeviceClass.WINDOW,
        value_fn=_eq(("status", "detail", "sunroof"), "OPEN"),
    ),
    SkodaBinaryDescription(
        # device_class LOCK: on = entriegelt
        key="unlocked",
        translation_key="unlocked",
        device_class=BinarySensorDeviceClass.LOCK,
        value_fn=_eq(("status", "overall", "locked"), "NO"),
    ),
    SkodaBinaryDescription(
        key="charging",
        translation_key="charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        value_fn=_eq(("charging", "status", "state"), "CHARGING"),
    ),
    SkodaBinaryDescription(
        key="plug_connected",
        translation_key="plug_connected",
        device_class=BinarySensorDeviceClass.PLUG,
        value_fn=_eq(("charging", "status", "plugConnectionState"), "CONNECTED"),
    ),
    SkodaBinaryDescription(
        # device_class LOCK: on = entriegelt
        key="plug_unlocked",
        translation_key="plug_unlocked",
        device_class=BinarySensorDeviceClass.LOCK,
        value_fn=_eq(("charging", "status", "plugLockState"), "UNLOCKED"),
    ),
    SkodaBinaryDescription(
        key="at_saved_location",
        translation_key="at_saved_location",
        value_fn=lambda v: dig(v, "charging", "isVehicleInSavedLocation"),
    ),
    SkodaBinaryDescription(
        key="window_heating_front",
        translation_key="window_heating_front",
        device_class=BinarySensorDeviceClass.HEAT,
        value_fn=_eq(("airConditioning", "windowHeating", "front"), "ON"),
    ),
    SkodaBinaryDescription(
        key="window_heating_rear",
        translation_key="window_heating_rear",
        device_class=BinarySensorDeviceClass.HEAT,
        value_fn=_eq(("airConditioning", "windowHeating", "rear"), "ON"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: SkodaConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    vehicle = coordinator.data.vehicle
    # Anlegen, wenn der Teil der Antwort vom Fahrzeug unterstützt wird (Feld vorhanden)
    async_add_entities(
        SkodaBinarySensor(coordinator, desc)
        for desc in BINARY_SENSORS
        if _supported(desc, vehicle)
    )


_REQUIRED_PATH = {
    "doors": ("status", "overall", "doors"),
    "windows": ("status", "overall", "windows"),
    "lights": ("status", "overall", "lights"),
    "trunk": ("status", "detail", "trunk"),
    "bonnet": ("status", "detail", "bonnet"),
    "sunroof": ("status", "detail", "sunroof"),
    "unlocked": ("status", "overall", "locked"),
    "charging": ("charging", "status"),
    "plug_connected": ("charging", "status", "plugConnectionState"),
    "plug_unlocked": ("charging", "status", "plugLockState"),
    "at_saved_location": ("charging", "isVehicleInSavedLocation"),
    "window_heating_front": ("airConditioning", "windowHeating", "front"),
    "window_heating_rear": ("airConditioning", "windowHeating", "rear"),
}


def _supported(desc: SkodaBinaryDescription, vehicle: dict[str, Any]) -> bool:
    raw = dig(vehicle, *_REQUIRED_PATH[desc.key])
    return raw is not None and raw != "UNSUPPORTED"


class SkodaBinarySensor(SkodaEntity, BinarySensorEntity):
    entity_description: SkodaBinaryDescription

    def __init__(
        self, coordinator: SkodaCoordinator, description: SkodaBinaryDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self.vehicle)
