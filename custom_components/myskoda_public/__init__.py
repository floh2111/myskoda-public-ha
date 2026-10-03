"""MyŠkoda Public API – Home Assistant Integration."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import SkodaPublicApi
from .const import CARDS_URL, CONF_API_KEY, CONF_VIN, DOMAIN, INTEGRATION_VERSION
from .coordinator import SkodaCoordinator

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.DEVICE_TRACKER,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

type SkodaConfigEntry = ConfigEntry[SkodaCoordinator]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Dashboard-Karten (JavaScript) für alle Browser bereitstellen."""
    js_file = Path(__file__).parent / "frontend" / "skoda-cards.js"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARDS_URL, str(js_file), cache_headers=False)]
    )
    # Query-Parameter sorgt dafür, dass Browser nach Updates die neue Datei laden
    add_extra_js_url(hass, f"{CARDS_URL}?v={INTEGRATION_VERSION}")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: SkodaConfigEntry) -> bool:
    """Integration für ein Fahrzeug einrichten."""
    api = SkodaPublicApi(
        async_get_clientsession(hass), entry.data[CONF_API_KEY], entry.data[CONF_VIN]
    )
    coordinator = SkodaCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SkodaConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_options_updated(hass: HomeAssistant, entry: SkodaConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
