"""Basisklasse für alle Entities."""

from __future__ import annotations

from typing import Any

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import SkodaApiError, SkodaOperationError
from .const import CONF_VIN, DOMAIN
from .coordinator import SkodaCoordinator


def dig(data: Any, *path: str) -> Any:
    """Sicher in verschachtelte Dicts greifen; fehlende Felder sind None (= unbekannt)."""
    for key in path:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
        if data is None:
            return None
    return data


class SkodaEntity(CoordinatorEntity[SkodaCoordinator]):
    """Gemeinsame Basis: ein Gerät pro Fahrzeug."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SkodaCoordinator, key: str) -> None:
        super().__init__(coordinator)
        vin = coordinator.config_entry.data[CONF_VIN]
        self._vin = vin
        self._attr_unique_id = f"{vin}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, vin)},
            manufacturer="Škoda",
            name=self.vehicle.get("name") or vin,
            serial_number=vin,
        )

    @property
    def vehicle(self) -> dict[str, Any]:
        return self.coordinator.data.vehicle if self.coordinator.data else {}

    @property
    def operations(self) -> set[str]:
        return self.coordinator.data.operations if self.coordinator.data else set()

    async def _run(self, coro) -> None:
        """Befehl ausführen, Fehler verständlich melden, danach einmal nachladen."""
        try:
            await coro
        except SkodaOperationError as err:
            raise HomeAssistantError(f"Das Fahrzeug lehnt den Befehl ab: {err}") from err
        except SkodaApiError as err:
            raise HomeAssistantError(f"Befehl fehlgeschlagen: {err}") from err
        self.coordinator.schedule_refresh_after_command()
