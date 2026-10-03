"""DataUpdateCoordinator für die MyŠkoda Public API."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    SkodaApiError,
    SkodaAuthError,
    SkodaPublicApi,
    SkodaRateLimitError,
    VehicleData,
)
from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_RETRY_AFTER,
    REFRESH_DELAY_AFTER_COMMAND,
)

_LOGGER = logging.getLogger(__name__)


class SkodaCoordinator(DataUpdateCoordinator[VehicleData]):
    """Holt den Fahrzeugzustand in einem einzigen Request pro Intervall."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, api: SkodaPublicApi
    ) -> None:
        interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {api.vin}",
            update_interval=timedelta(minutes=interval),
        )
        self.api = api
        self._base_interval = timedelta(minutes=interval)
        self._command_refresh_unsub = None

    def schedule_refresh_after_command(self) -> None:
        """Nach einem Befehl genau einmal verzögert nachladen (spart Kontingent)."""
        if self._command_refresh_unsub is not None:
            self._command_refresh_unsub()

        async def _refresh(_now) -> None:
            self._command_refresh_unsub = None
            await self.async_request_refresh()

        self._command_refresh_unsub = async_call_later(
            self.hass, REFRESH_DELAY_AFTER_COMMAND, _refresh
        )

    async def async_shutdown(self) -> None:
        if self._command_refresh_unsub is not None:
            self._command_refresh_unsub()
            self._command_refresh_unsub = None
        await super().async_shutdown()

    async def _async_update_data(self) -> VehicleData:
        try:
            data = await self.api.get_vehicle()
        except SkodaAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except SkodaRateLimitError as err:
            # Nicht beim nächsten Tick erneut anklopfen, sondern pausieren.
            wait = min(max(err.retry_after, int(self._base_interval.total_seconds())), MAX_RETRY_AFTER)
            self.update_interval = timedelta(seconds=wait)
            raise UpdateFailed(
                f"Rate-Limit erreicht, nächster Versuch in {wait // 60} Minuten"
            ) from err
        except SkodaApiError as err:
            raise UpdateFailed(str(err)) from err

        # Normales Intervall wiederherstellen, falls vorher pausiert wurde.
        if self.update_interval != self._base_interval:
            self.update_interval = self._base_interval

        for error in data.errors:
            _LOGGER.debug(
                "Teilweise Daten (%s): %s", error.get("type"), error.get("description")
            )
        return data
