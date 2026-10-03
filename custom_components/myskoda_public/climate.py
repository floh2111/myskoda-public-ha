"""Standklimatisierung."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SkodaConfigEntry
from .const import (
    DEFAULT_TARGET_TEMPERATURE,
    MAX_TARGET_TEMPERATURE,
    MIN_TARGET_TEMPERATURE,
)
from .coordinator import SkodaCoordinator
from .entity import SkodaEntity, dig

_ACTIVE = {"COOLING", "HEATING", "HEATING_AUXILIARY", "VENTILATION"}


async def async_setup_entry(
    hass: HomeAssistant, entry: SkodaConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    if "startAirConditioning" in coordinator.data.operations:
        async_add_entities([SkodaClimate(coordinator)])


class SkodaClimate(SkodaEntity, ClimateEntity):
    _attr_translation_key = "air_conditioning"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT_COOL]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_min_temp = MIN_TARGET_TEMPERATURE
    _attr_max_temp = MAX_TARGET_TEMPERATURE
    _attr_target_temperature_step = 0.5

    def __init__(self, coordinator: SkodaCoordinator) -> None:
        super().__init__(coordinator, "air_conditioning")
        self._pending_target: float | None = None

    @property
    def _state(self) -> str | None:
        return dig(self.vehicle, "airConditioning", "state")

    @property
    def hvac_mode(self) -> HVACMode | None:
        if self._state is None or self._state == "UNKNOWN":
            return None
        return HVACMode.HEAT_COOL if self._state in _ACTIVE else HVACMode.OFF

    @property
    def hvac_action(self) -> HVACAction | None:
        return {
            "COOLING": HVACAction.COOLING,
            "HEATING": HVACAction.HEATING,
            "HEATING_AUXILIARY": HVACAction.HEATING,
            "VENTILATION": HVACAction.FAN,
            "OFF": HVACAction.OFF,
            "COMPLETED": HVACAction.IDLE,
        }.get(self._state or "")

    @property
    def target_temperature(self) -> float | None:
        if self._pending_target is not None:
            return self._pending_target
        target = dig(self.vehicle, "airConditioning", "targetTemperature")
        if isinstance(target, dict) and target.get("unit") == "CELSIUS":
            return target.get("value")
        return None

    def _handle_coordinator_update(self) -> None:
        self._pending_target = None
        super()._handle_coordinator_update()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {}
        eta = dig(self.vehicle, "airConditioning", "estimatedReachOfTargetTemperatureAt")
        if eta:
            attrs["target_reached_at"] = eta
        without_power = dig(self.vehicle, "airConditioning", "airConditioningWithoutExternalPower")
        if without_power is not None:
            attrs["without_external_power"] = without_power
        return attrs

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
        else:
            await self.async_turn_on()

    async def async_turn_on(self) -> None:
        await self._run(
            self.coordinator.api.start_air_conditioning(
                self.target_temperature or DEFAULT_TARGET_TEMPERATURE
            )
        )

    async def async_turn_off(self) -> None:
        await self._run(self.coordinator.api.stop_air_conditioning())

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        # Die API kennt keinen separaten "Zieltemperatur setzen"-Befehl: Temperatur
        # wird nur beim Start übergeben. Läuft die Klima, neu starten; sonst merken.
        if self.hvac_mode == HVACMode.HEAT_COOL:
            await self._run(self.coordinator.api.start_air_conditioning(temperature))
        self._pending_target = temperature
        self.async_write_ha_state()
