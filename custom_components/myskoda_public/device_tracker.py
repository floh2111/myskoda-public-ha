"""Standort des Fahrzeugs."""

from __future__ import annotations

from homeassistant.components.device_tracker import TrackerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SkodaConfigEntry
from .coordinator import SkodaCoordinator
from .entity import SkodaEntity, dig


async def async_setup_entry(
    hass: HomeAssistant, entry: SkodaConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    if dig(coordinator.data.vehicle, "parkingPosition") is not None:
        async_add_entities([SkodaTracker(coordinator)])


class SkodaTracker(SkodaEntity, TrackerEntity):
    _attr_translation_key = "location"

    def __init__(self, coordinator: SkodaCoordinator) -> None:
        super().__init__(coordinator, "location")

    @property
    def _coords(self) -> dict | None:
        return dig(self.vehicle, "parkingPosition", "gpsCoordinates")

    @property
    def latitude(self) -> float | None:
        return self._coords.get("latitude") if self._coords else None

    @property
    def longitude(self) -> float | None:
        return self._coords.get("longitude") if self._coords else None

    @property
    def available(self) -> bool:
        # Während der Fahrt (IN_MOTION) gibt es keine Koordinaten; letzten Stand nicht erfinden
        return super().available and self._coords is not None
