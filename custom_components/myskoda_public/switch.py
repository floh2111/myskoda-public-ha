"""Schalter: Laden, Standlüftung, Standheizung."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SkodaConfigEntry
from .const import CONF_SPIN
from .coordinator import SkodaCoordinator
from .entity import SkodaEntity, dig

_HEATING_ON = {"PREHEATING", "HEATING_AUXILIARY", "VENTILATION"}


async def async_setup_entry(
    hass: HomeAssistant, entry: SkodaConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    ops = coordinator.data.operations
    entities: list[SwitchEntity] = []
    if "startCharging" in ops:
        entities.append(SkodaChargingSwitch(coordinator))
    if "startActiveVentilation" in ops:
        entities.append(SkodaActiveVentilationSwitch(coordinator))
    if "startAuxiliaryHeating" in ops:
        entities.append(SkodaAuxiliaryHeatingSwitch(coordinator, entry.options.get(CONF_SPIN)))
    async_add_entities(entities)


class SkodaChargingSwitch(SkodaEntity, SwitchEntity):
    _attr_translation_key = "charging_switch"

    def __init__(self, coordinator: SkodaCoordinator) -> None:
        super().__init__(coordinator, "charging_switch")

    @property
    def is_on(self) -> bool | None:
        state = dig(self.vehicle, "charging", "status", "state")
        if state is None:
            return None
        return state == "CHARGING"

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._run(self.coordinator.api.start_charging())

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._run(self.coordinator.api.stop_charging())


class SkodaActiveVentilationSwitch(SkodaEntity, SwitchEntity):
    _attr_translation_key = "active_ventilation"

    def __init__(self, coordinator: SkodaCoordinator) -> None:
        super().__init__(coordinator, "active_ventilation")

    @property
    def is_on(self) -> bool | None:
        state = dig(self.vehicle, "activeVentilation", "state")
        if state in (None, "UNKNOWN", "UNSUPPORTED"):
            return None
        return state != "OFF"

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._run(self.coordinator.api.start_active_ventilation())

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._run(self.coordinator.api.stop_active_ventilation())


class SkodaAuxiliaryHeatingSwitch(SkodaEntity, SwitchEntity):
    """Standheizung. Braucht die S-PIN aus den Integrations-Optionen."""

    _attr_translation_key = "auxiliary_heating"

    def __init__(self, coordinator: SkodaCoordinator, spin: str | None) -> None:
        super().__init__(coordinator, "auxiliary_heating")
        self._spin = spin

    @property
    def is_on(self) -> bool | None:
        state = dig(self.vehicle, "auxiliaryHeating", "state")
        if state in (None, "UNKNOWN", "UNSUPPORTED"):
            return None
        return state in _HEATING_ON

    async def async_turn_on(self, **kwargs: Any) -> None:
        if not self._spin:
            raise HomeAssistantError(
                "Für die Standheizung wird die S-PIN benötigt. Bitte in den "
                "Optionen der Integration eintragen."
            )
        await self._run(self.coordinator.api.start_auxiliary_heating(self._spin))

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._run(self.coordinator.api.stop_auxiliary_heating())
