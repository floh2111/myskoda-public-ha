"""Sensoren."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfLength,
    UnitOfPower,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import SkodaConfigEntry
from .coordinator import SkodaCoordinator
from .entity import SkodaEntity, dig


def _meters_to_km(value: Any) -> float | None:
    return round(value / 1000, 1) if isinstance(value, (int, float)) else None


def _parse_dt(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    return dt_util.parse_datetime(value)


@dataclass(frozen=True, kw_only=True)
class SkodaSensorDescription(SensorEntityDescription):
    """Beschreibung: value_fn liest aus dem Fahrzeug-Dict, None = nicht vorhanden."""

    value_fn: Callable[[dict[str, Any]], Any]


SENSORS: tuple[SkodaSensorDescription, ...] = (
    SkodaSensorDescription(
        key="battery_level",
        translation_key="battery_level",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda v: dig(v, "charging", "status", "battery", "stateOfChargeInPercent"),
    ),
    SkodaSensorDescription(
        key="electric_range",
        translation_key="electric_range",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda v: _meters_to_km(
            dig(v, "charging", "status", "battery", "remainingCruisingRangeInMeters")
        ),
    ),
    SkodaSensorDescription(
        key="charging_power",
        translation_key="charging_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda v: dig(v, "charging", "status", "chargePowerInKw"),
    ),
    SkodaSensorDescription(
        key="charging_rate",
        translation_key="charging_rate",
        device_class=SensorDeviceClass.SPEED,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda v: dig(v, "charging", "status", "chargingRateInKilometersPerHour"),
    ),
    SkodaSensorDescription(
        key="remaining_charging_time",
        translation_key="remaining_charging_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda v: dig(v, "charging", "status", "remainingTimeToFullyChargedInMinutes"),
    ),
    SkodaSensorDescription(
        key="fully_charged_at",
        translation_key="fully_charged_at",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda v: _parse_dt(dig(v, "charging", "status", "fullyChargedAt")),
    ),
    SkodaSensorDescription(
        key="charging_state",
        translation_key="charging_state",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "connect_cable",
            "charging",
            "conserving",
            "ready_for_charging",
            "discharging",
            "charging_interrupted",
        ],
        # Unbekannte/neue Werte oder fehlendes Feld -> unbekannt (laut API-Doku nie als "getrennt" deuten)
        value_fn=lambda v: (
            s.lower()
            if isinstance(s := dig(v, "charging", "status", "state"), str)
            and s.lower()
            in (
                "connect_cable",
                "charging",
                "conserving",
                "ready_for_charging",
                "discharging",
                "charging_interrupted",
            )
            else None
        ),
    ),
    SkodaSensorDescription(
        key="charge_type",
        translation_key="charge_type",
        device_class=SensorDeviceClass.ENUM,
        options=["ac", "dc", "off"],
        value_fn=lambda v: (
            s.lower()
            if isinstance(s := dig(v, "charging", "status", "chargeType"), str)
            and s.lower() in ("ac", "dc", "off")
            else None
        ),
    ),
    SkodaSensorDescription(
        key="target_soc",
        translation_key="target_soc",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda v: dig(v, "charging", "settings", "targetStateOfChargeInPercent"),
    ),
    SkodaSensorDescription(
        key="max_charge_current",
        translation_key="max_charge_current",
        native_unit_of_measurement="A",
        device_class=SensorDeviceClass.CURRENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda v: dig(v, "charging", "settings", "maxChargeCurrentAcAmpere"),
    ),
    SkodaSensorDescription(
        key="charging_profile",
        translation_key="charging_profile",
        value_fn=lambda v: dig(v, "chargingProfiles", "currentVehiclePositionProfile", "name"),
    ),
    SkodaSensorDescription(
        key="odometer",
        translation_key="odometer",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda v: dig(v, "odometer", "mileageInKm"),
    ),
    SkodaSensorDescription(
        key="total_range",
        translation_key="total_range",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda v: dig(v, "fuelStatus", "totalRangeInKm"),
    ),
    SkodaSensorDescription(
        key="fuel_level",
        translation_key="fuel_level",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda v: _fuel_level(v),
    ),
    SkodaSensorDescription(
        key="adblue_range",
        translation_key="adblue_range",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda v: dig(v, "fuelStatus", "adBlueRange"),
    ),
    SkodaSensorDescription(
        key="air_conditioning_state",
        translation_key="air_conditioning_state",
        device_class=SensorDeviceClass.ENUM,
        options=["off", "cooling", "heating", "heating_auxiliary", "ventilation", "completed"],
        value_fn=lambda v: (
            s.lower()
            if isinstance(s := dig(v, "airConditioning", "state"), str)
            and s.lower()
            in ("off", "cooling", "heating", "heating_auxiliary", "ventilation", "completed")
            else None
        ),
    ),
    SkodaSensorDescription(
        key="air_conditioning_target",
        translation_key="air_conditioning_target",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda v: (
            dig(v, "airConditioning", "targetTemperature", "value")
            if dig(v, "airConditioning", "targetTemperature", "unit") == "CELSIUS"
            else None
        ),
    ),
    SkodaSensorDescription(
        key="parking_address",
        translation_key="parking_address",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda v: dig(v, "parkingPosition", "formattedAddress"),
    ),
)


def _fuel_level(vehicle: dict[str, Any]) -> float | None:
    """Tankfüllstand: Verbrenner-Motor (primary oder secondary) bevorzugen."""
    for engine in ("primaryEngineRange", "secondaryEngineRange"):
        data = dig(vehicle, "fuelStatus", engine)
        if isinstance(data, dict) and data.get("engineType") not in (None, "ELECTRIC"):
            level = data.get("currentFuelLevelInPercent")
            if level is not None:
                return level
    return None


async def async_setup_entry(
    hass: HomeAssistant, entry: SkodaConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [
        SkodaSensor(coordinator, desc)
        for desc in SENSORS
        # Nur Sensoren anlegen, für die das Fahrzeug beim Start Daten liefert
        if desc.value_fn(coordinator.data.vehicle) is not None
        # Zustand der Klimaanlage und Ziel auch ohne Wert anlegen, wenn unterstützt
        or (desc.key.startswith("air_conditioning") and "startAirConditioning" in coordinator.data.operations)
    ]
    entities.append(SkodaApiKeyExpirySensor(coordinator))
    entities.append(SkodaQuotaSensor(coordinator))
    async_add_entities(entities)


class SkodaSensor(SkodaEntity, SensorEntity):
    entity_description: SkodaSensorDescription

    def __init__(self, coordinator: SkodaCoordinator, description: SkodaSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.vehicle)


class SkodaApiKeyExpirySensor(SkodaEntity, SensorEntity):
    """Wann der API-Key abläuft (aus dem Header X-API-Key-Expires-At)."""

    _attr_translation_key = "api_key_expires"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: SkodaCoordinator) -> None:
        super().__init__(coordinator, "api_key_expires")

    @property
    def native_value(self) -> datetime | None:
        return self.coordinator.api.rate_limit.key_expires_at


class SkodaQuotaSensor(SkodaEntity, SensorEntity):
    """Verbleibende Anfragen im aktuellen Zeitfenster."""

    _attr_translation_key = "api_quota_remaining"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: SkodaCoordinator) -> None:
        super().__init__(coordinator, "api_quota_remaining")

    @property
    def native_value(self) -> int | None:
        return self.coordinator.api.rate_limit.remaining

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        rl = self.coordinator.api.rate_limit
        return {"limit": rl.limit, "reset_in_seconds": rl.reset_seconds}
