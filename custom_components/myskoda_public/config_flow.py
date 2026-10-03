"""Config Flow: API-Key + VIN, Reauth und Optionen."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    SkodaApiError,
    SkodaAuthError,
    SkodaPublicApi,
    SkodaRateLimitError,
    SkodaVehicleNotFound,
)
from .const import (
    CONF_API_KEY,
    CONF_SCAN_INTERVAL,
    CONF_SPIN,
    CONF_VIN,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class SkodaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Einrichtung pro Fahrzeug (ein API-Key ist an ausgewählte Fahrzeuge gebunden)."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return SkodaOptionsFlow()

    async def _validate(
        self, api_key: str, vin: str
    ) -> tuple[dict[str, str], str | None]:
        """Key gegen die API prüfen. Gibt (Fehler, Fahrzeugname) zurück."""
        api = SkodaPublicApi(async_get_clientsession(self.hass), api_key, vin)
        try:
            data = await api.get_vehicle(include=["info"])
        except SkodaAuthError:
            return {"base": "invalid_auth"}, None
        except SkodaVehicleNotFound:
            return {CONF_VIN: "vehicle_not_found"}, None
        except SkodaRateLimitError:
            return {"base": "rate_limited"}, None
        except SkodaApiError as err:
            _LOGGER.warning("Verbindung zur MyŠkoda Public API fehlgeschlagen: %s", err)
            return {"base": "cannot_connect"}, None
        return {}, data.vehicle.get("name") or vin

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            vin = user_input[CONF_VIN].strip().upper()
            api_key = user_input[CONF_API_KEY].strip()
            if len(vin) != 17:
                errors[CONF_VIN] = "invalid_vin"
            else:
                await self.async_set_unique_id(vin)
                self._abort_if_unique_id_configured()
                errors, name = await self._validate(api_key, vin)
                if not errors:
                    return self.async_create_entry(
                        title=name or vin,
                        data={CONF_API_KEY: api_key, CONF_VIN: vin},
                    )

        schema = vol.Schema(
            {vol.Required(CONF_API_KEY): str, vol.Required(CONF_VIN): str}
        )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Neuen API-Key eintragen, wenn der alte abgelaufen ist."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            errors, _ = await self._validate(api_key, entry.data[CONF_VIN])
            if not errors:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_API_KEY: api_key}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            description_placeholders={"vin": entry.data[CONF_VIN]},
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """API-Key jederzeit tauschen (z. B. vor Ablauf)."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            errors, _ = await self._validate(api_key, entry.data[CONF_VIN])
            if not errors:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_API_KEY: api_key}
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )


class SkodaOptionsFlow(OptionsFlow):
    """Abfrageintervall und S-PIN."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        opts = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=opts.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): vol.All(
                    vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)
                ),
                vol.Optional(
                    CONF_SPIN, description={"suggested_value": opts.get(CONF_SPIN, "")}
                ): str,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
