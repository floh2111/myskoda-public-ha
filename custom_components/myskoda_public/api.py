"""Schlanker async-Client für die MyŠkoda Public API."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import logging
from typing import Any

import aiohttp

from .const import API_BASE_URL, DEFAULT_RETRY_AFTER, MAX_RETRY_AFTER

_LOGGER = logging.getLogger(__name__)

PROBLEM_PREFIX = f"{API_BASE_URL}/problems/"


class SkodaApiError(Exception):
    """Allgemeiner API-Fehler."""

    def __init__(self, message: str, problem: str | None = None) -> None:
        super().__init__(message)
        self.problem = problem


class SkodaAuthError(SkodaApiError):
    """API-Key abgelaufen oder für das Fahrzeug nicht berechtigt (401/403)."""


class SkodaVehicleNotFound(SkodaApiError):
    """Zur VIN wurde kein Fahrzeug gefunden (404)."""


class SkodaOperationError(SkodaApiError):
    """Das Fahrzeug kann/will den Befehl nicht ausführen (403/422)."""


class SkodaRateLimitError(SkodaApiError):
    """Limit erreicht oder Fahrzeug lehnt ab (429)."""

    def __init__(
        self, message: str, retry_after: int, problem: str | None = None
    ) -> None:
        super().__init__(message, problem)
        self.retry_after = retry_after


@dataclass
class RateLimitInfo:
    """Kontingent-Informationen aus den Antwort-Headern."""

    limit: int | None = None
    remaining: int | None = None
    reset_seconds: int | None = None
    key_expires_at: datetime | None = None


@dataclass
class VehicleData:
    """Antwort von GET /api/v1/vehicles/{vin}."""

    vehicle: dict[str, Any]
    errors: list[dict[str, Any]] = field(default_factory=list)
    rate_limit: RateLimitInfo = field(default_factory=RateLimitInfo)

    @property
    def operations(self) -> set[str]:
        return {
            op.get("name")
            for op in self.vehicle.get("operations", [])
            if isinstance(op, dict) and op.get("name")
        }


def _to_int(value: str | None) -> int | None:
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def _parse_rate_limit(headers: Any) -> RateLimitInfo:
    info = RateLimitInfo(
        limit=_to_int(headers.get("RateLimit-Limit")),
        remaining=_to_int(headers.get("RateLimit-Remaining")),
        reset_seconds=_to_int(headers.get("RateLimit-Reset")),
    )
    expires = headers.get("X-API-Key-Expires-At")
    if expires:
        try:
            info.key_expires_at = datetime.fromisoformat(expires.replace("Z", "+00:00"))
        except ValueError:
            _LOGGER.debug("Unlesbarer X-API-Key-Expires-At-Header: %s", expires)
    return info


class SkodaPublicApi:
    """Client für https://public.api.connect.skoda-auto.cz."""

    def __init__(
        self, session: aiohttp.ClientSession, api_key: str, vin: str
    ) -> None:
        self._session = session
        self._api_key = api_key
        self._vin = vin.strip().upper()
        self.rate_limit = RateLimitInfo()

    @property
    def vin(self) -> str:
        return self._vin

    # ------------------------------------------------------------------ #
    # Lesen
    # ------------------------------------------------------------------ #
    async def get_vehicle(self, include: list[str] | None = None) -> VehicleData:
        """Fahrzeug und aktuellen Zustand abrufen (zählt 1 Anfrage)."""
        params = {"include": ",".join(include)} if include else None
        data, headers = await self._request(
            "GET", f"/api/v1/vehicles/{self._vin}", params=params
        )
        rate = _parse_rate_limit(headers)
        self._merge_rate_limit(rate)
        return VehicleData(
            vehicle=(data or {}).get("vehicle", {}),
            errors=(data or {}).get("errors", []),
            rate_limit=self.rate_limit,
        )

    # ------------------------------------------------------------------ #
    # Befehle (jeweils 202 Accepted)
    # ------------------------------------------------------------------ #
    async def start_charging(self) -> None:
        await self._command("POST", "charging/start")

    async def stop_charging(self) -> None:
        await self._command("POST", "charging/stop")

    async def set_charging_limit(self, percent: int) -> None:
        await self._command(
            "PUT", "charging/limit", {"targetStateOfChargeInPercent": int(percent)}
        )

    async def set_charge_mode(self, mode: str) -> None:
        await self._command("PUT", "charging/mode", {"chargeMode": mode})

    async def start_air_conditioning(
        self,
        target_temperature: float | None = None,
        without_external_power: bool | None = None,
    ) -> None:
        body: dict[str, Any] = {}
        if target_temperature is not None:
            body["targetTemperature"] = {
                "value": float(target_temperature),
                "unit": "CELSIUS",
            }
        if without_external_power is not None:
            body["airConditioningWithoutExternalPower"] = without_external_power
        await self._command("POST", "air-conditioning/start", body)

    async def stop_air_conditioning(self) -> None:
        await self._command("POST", "air-conditioning/stop")

    async def start_auxiliary_heating(
        self,
        spin: str,
        target_temperature: float | None = None,
        duration_seconds: int | None = None,
        start_mode: str = "HEATING",
    ) -> None:
        body: dict[str, Any] = {"spin": spin, "startMode": start_mode}
        if target_temperature is not None:
            body["targetTemperature"] = {
                "value": float(target_temperature),
                "unit": "CELSIUS",
            }
        if duration_seconds is not None:
            body["durationInSeconds"] = int(duration_seconds)
        await self._command("POST", "auxiliary-heating/start", body)

    async def stop_auxiliary_heating(self) -> None:
        await self._command("POST", "auxiliary-heating/stop")

    async def start_active_ventilation(self) -> None:
        await self._command("POST", "active-ventilation/start")

    async def stop_active_ventilation(self) -> None:
        await self._command("POST", "active-ventilation/stop")

    # ------------------------------------------------------------------ #
    # Intern
    # ------------------------------------------------------------------ #
    async def _command(
        self, method: str, suffix: str, body: dict[str, Any] | None = None
    ) -> None:
        _, headers = await self._request(
            method, f"/api/v1/vehicles/{self._vin}/{suffix}", json=body
        )
        self._merge_rate_limit(_parse_rate_limit(headers))

    def _merge_rate_limit(self, new: RateLimitInfo) -> None:
        if new.limit is not None:
            self.rate_limit.limit = new.limit
        if new.remaining is not None:
            self.rate_limit.remaining = new.remaining
        if new.reset_seconds is not None:
            self.rate_limit.reset_seconds = new.reset_seconds
        if new.key_expires_at is not None:
            self.rate_limit.key_expires_at = new.key_expires_at

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any] | None, Any]:
        url = f"{API_BASE_URL}{path}"
        headers = {"X-API-Key": self._api_key, "Accept": "application/json"}
        try:
            async with self._session.request(
                method,
                url,
                headers=headers,
                params=params,
                json=json,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                # Rate-Limit-Infos auch bei Fehlern mitnehmen
                self._merge_rate_limit(_parse_rate_limit(resp.headers))

                if resp.status in (200, 202, 204):
                    if resp.status == 200 and resp.content_type in (
                        "application/json",
                        "application/problem+json",
                    ):
                        return await resp.json(), resp.headers
                    return None, resp.headers

                problem = await self._read_problem(resp)
                self._raise_for_problem(resp.status, resp.headers, problem)
        except aiohttp.ClientError as err:
            raise SkodaApiError(f"Verbindungsfehler: {err}") from err
        except TimeoutError as err:
            raise SkodaApiError("Zeitüberschreitung bei der Anfrage") from err
        raise SkodaApiError("Unerwartete Antwort")  # pragma: no cover

    @staticmethod
    async def _read_problem(resp: aiohttp.ClientResponse) -> dict[str, Any]:
        try:
            data = await resp.json(content_type=None)
            return data if isinstance(data, dict) else {}
        except (aiohttp.ClientError, ValueError):
            return {}

    @staticmethod
    def _raise_for_problem(status: int, headers: Any, problem: dict[str, Any]) -> None:
        ptype = str(problem.get("type", ""))
        short = ptype.removeprefix(PROBLEM_PREFIX) if ptype.startswith(PROBLEM_PREFIX) else None
        detail = problem.get("detail") or problem.get("title") or f"HTTP {status}"

        if status == 401:
            raise SkodaAuthError(detail, short or "unauthorized")
        if status == 403:
            if short == "operation-not-authorized":
                raise SkodaOperationError(detail, short)
            raise SkodaAuthError(detail, short or "forbidden")
        if status == 404:
            raise SkodaVehicleNotFound(detail, short)
        if status == 422:
            raise SkodaOperationError(detail, short)
        if status in (429, 503):
            retry_after = _to_int(headers.get("Retry-After")) or DEFAULT_RETRY_AFTER
            retry_after = min(max(retry_after, 1), MAX_RETRY_AFTER)
            if status == 429:
                raise SkodaRateLimitError(detail, retry_after, short)
            raise SkodaApiError(
                f"Dienst vorübergehend nicht verfügbar (Retry-After {retry_after}s)",
                short,
            )
        raise SkodaApiError(f"{status}: {detail}", short)
