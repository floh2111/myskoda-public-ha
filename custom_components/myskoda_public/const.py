"""Konstanten für die MyŠkoda Public API Integration."""

from __future__ import annotations

DOMAIN = "myskoda_public"

API_BASE_URL = "https://public.api.connect.skoda-auto.cz"

# Muss mit "version" in manifest.json übereinstimmen (wird für das Cache-Busting der Karten genutzt)
INTEGRATION_VERSION = "0.2.0"
CARDS_URL = "/myskoda_public/skoda-cards.js"

CONF_API_KEY = "api_key"
CONF_VIN = "vin"
CONF_SPIN = "spin"
CONF_SCAN_INTERVAL = "scan_interval"

# Die API erlaubt aktuell 20 Anfragen pro Stunde und VIN (Befehle zählen mit).
# 15 Minuten = 4 Abfragen/h, damit bleibt Platz für Befehle und Nachladen.
DEFAULT_SCAN_INTERVAL = 15  # Minuten
MIN_SCAN_INTERVAL = 5  # Minuten (12 Abfragen/h)
MAX_SCAN_INTERVAL = 240  # Minuten

# Nach einem Befehl einmal nachladen, um den neuen Zustand zu sehen.
REFRESH_DELAY_AFTER_COMMAND = 45  # Sekunden

# Fallback-Wartezeit, wenn die API bei 429 keinen Retry-After-Header liefert.
DEFAULT_RETRY_AFTER = 900  # Sekunden
MAX_RETRY_AFTER = 3600  # Sekunden

MIN_TARGET_TEMPERATURE = 15.5
MAX_TARGET_TEMPERATURE = 30.0
DEFAULT_TARGET_TEMPERATURE = 21.0
