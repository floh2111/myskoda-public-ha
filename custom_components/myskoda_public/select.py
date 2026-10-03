"""Lademodus."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SkodaConfigEntry
from .coordinator import SkodaCoordinator
from .entity import SkodaEntity, dig


async def async_setup_entry(
    hass: HomeAssistant, entry: SkodaConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    if "setChargeMode" in coordinator.data.operations:
        async_add_entities([SkodaChargeMode(coordinator)])


class SkodaChargeMode(SkodaEntity, SelectEntity):
    """Die API liefert die verfügbaren Modi selbst; neue Werte werden unverändert angeboten."""

    _attr_translation_key = "charge_mode"

    def __init__(self, coordinator: SkodaCoordinator) -> None:
        super().__init__(coordinator, "charge_mode")
        self._pending: str | None = None

    @property
    def options(self) -> list[str]:
        modes = dig(self.vehicle, "charging", "settings", "availableChargeModes") or []
        current = self.current_option
        opts = [m.lower() for m in modes if isinstance(m, str)]
        if current and current not in opts:
            opts.append(current)
        return opts

    @property
    def current_option(self) -> str | None:
        if self._pending is not None:
            return self._pending
        mode = dig(self.vehicle, "charging", "settings", "preferredChargeMode")
        return mode.lower() if isinstance(mode, str) else None

    def _handle_coordinator_update(self) -> None:
        self._pending = None
        super()._handle_coordinator_update()

    async def async_select_option(self, option: str) -> None:
        await self._run(self.coordinator.api.set_charge_mode(option.upper()))
        self._pending = option
        self.async_write_ha_state()
