# MyŠkoda Public API für Home Assistant

Custom Integration für die **öffentliche MyŠkoda API** (`public.api.connect.skoda-auto.cz`).
Sie läuft ohne Login mit Benutzername/Passwort: Authentifiziert wird mit einem **API-Key** aus der MyŠkoda-App.

> Inoffizielles Projekt, nicht mit Škoda Auto verbunden. Nutzung auf eigene Gefahr.

## Installation

1. Ordner `custom_components/myskoda_public` nach `config/custom_components/` kopieren
   (oder dieses Repository in HACS als benutzerdefiniertes Repository vom Typ *Integration* hinzufügen).
2. Home Assistant neu starten.

## API-Key erstellen

1. MyŠkoda-App öffnen, **API-Keys verwalten** (Link: <https://go.skoda.eu/api-keys>).
2. Neuen Key anlegen und dein Fahrzeug auswählen. Der Key ist an die gewählten Fahrzeuge gebunden und **läuft ab**.

## Einrichtung

*Einstellungen → Geräte & Dienste → Integration hinzufügen → „MyŠkoda Public API“*

API-Key und die 17-stellige FIN eintragen. Pro Fahrzeug wird ein Eintrag angelegt.

Läuft der Key ab, zeigt Home Assistant eine Reparatur-Meldung („Neu authentifizieren“). Den Key kannst du jederzeit
über **Neu konfigurieren** am Integrationseintrag tauschen. Der Sensor *API-Key läuft ab* zeigt das Ablaufdatum.

## Entities

Es werden nur Entities angelegt, die dein Fahrzeug tatsächlich unterstützt.

| Plattform | Inhalt |
|---|---|
| `sensor` | Ladestand, elektrische Reichweite, Ladeleistung, Laderate, Restladezeit, Ladezustand, Ladeart, Ziel-Ladestand, Kilometerstand, Gesamtreichweite, Tankfüllung, AdBlue, Klima-Zustand, Parkadresse, verbleibende API-Anfragen, API-Key-Ablauf |
| `binary_sensor` | Türen, Fenster, Licht, Kofferraum, Motorhaube, Schiebedach, Zentralverriegelung, Lädt, Ladekabel, Stecker-Verriegelung, Heckscheiben-/Frontscheibenheizung |
| `device_tracker` | Letzte Parkposition |
| `climate` | Standklimatisierung (an/aus, Zieltemperatur) |
| `switch` | Laden, Standlüftung, Standheizung |
| `number` | Ladelimit (50–100 % in 10er-Schritten) |
| `select` | Lademodus |

Hinweise:

- **Zieltemperatur**: Die API übergibt die Temperatur nur beim Start der Klimatisierung. Ändert man sie bei laufender Klima, wird neu gestartet; im Ruhezustand wird der Wert für den nächsten Start gemerkt.
- **Standheizung** braucht die S-PIN (Optionen der Integration).
- Fehlende Felder in der API-Antwort bedeuten „unbekannt“, nie einen bestimmten Wert (z. B. „Kabel getrennt“).
- Der **Standort** ist während der Fahrt nicht verfügbar (die API liefert dann keine Koordinaten).

## Abfragelimit

Die API erlaubt aktuell **20 Anfragen pro Stunde und FIN** (Befehle zählen mit, der Wert kann sich ändern).

- Es wird pro Abfrage **eine** Anfrage gestellt. Standard-Intervall: 15 Minuten (4 Anfragen/h), Minimum 5 Minuten.
- Nach einem Befehl wird einmal nach 45 Sekunden nachgeladen.
- Bei `429` pausiert die Integration gemäß `Retry-After`.
- Der Sensor *Verbleibende API-Anfragen* (Diagnose) zeigt das Restkontingent.

## Dashboard-Karten

Die Integration bringt vier Karten mit, die du im Dashboard direkt über **Karte hinzufügen** auswählst
(Suche nach „Škoda“):

| Karte | Inhalt |
|---|---|
| Škoda – Laden | Ladestand, Reichweite, Ladezustand, Laden an/aus, Ladelimit, Lademodus |
| Škoda – Klimatisierung | Standklimatisierung mit Zieltemperatur |
| Škoda – Fahrzeugstatus | Verriegelung, Türen, Fenster, Kofferraum, Licht, Kilometerstand |
| Škoda – Standort | Letzte Parkposition auf der Karte |

Im Karteneditor wählst du nur das Fahrzeug aus; die Entities werden automatisch gefunden (kein Platzhalter-Austausch nötig).
Mit nur einem Fahrzeug musst du gar nichts auswählen. Die Karten bestehen aus Standardkarten von Home Assistant,
Funktionen, die dein Fahrzeug nicht hat, werden weggelassen.

In YAML: `type: custom:skoda-charging-card` (optional `device_id: …`).
Falls die Karten nach einem Update nicht erscheinen, Browser-Cache leeren bzw. die Seite hart neu laden.

Eine statische Beispielansicht (mit Platzhalter `my_skoda`) liegt zusätzlich in
[`dashboard/skoda_dashboard.yaml`](dashboard/skoda_dashboard.yaml).

## Entwicklung

Die API-Beschreibung (OpenAPI): <https://public.api.connect.skoda-auto.cz/v3/api-docs>
