"""Ladelimit (Ziel-Ladestand)."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SkodaConfigEntry
from .coordinator import SkodaCoordinator
from .entity import SkodaEntity, dig


async def async_setup_entry(
    hass: HomeAssistant, entry: SkodaConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    if "setChargingLimit" in coordinator.data.operations:
        async_add_entities([SkodaChargeLimit(coordinator)])


class SkodaChargeLimit(SkodaEntity, NumberEntity):
    _attr_translation_key = "charge_limit"
    _attr_native_unit_of_measurement = PERCENTAGE
    # Fahrzeuge akzeptieren typischerweise nur 50..100 in 10er-Schritten
    _attr_native_min_value = 50
    _attr_native_max_value = 100
    _attr_native_step = 10
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator: SkodaCoordinator) -> None:
        super().__init__(coordinator, "charge_limit")
        self._pending: float | None = None

    @property
    def native_value(self) -> float | None:
        if self._pending is not None:
            return self._pending
        return dig(self.vehicle, "charging", "settings", "targetStateOfChargeInPercent")

    def _handle_coordinator_update(self) -> None:
        self._pending = None
        super()._handle_coordinator_update()

    async def async_set_native_value(self, value: float) -> None:
        await self._run(self.coordinator.api.set_charging_limit(int(value)))
        self._pending = value
        self.async_write_ha_state()
