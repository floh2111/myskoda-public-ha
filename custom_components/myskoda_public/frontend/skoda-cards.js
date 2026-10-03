/*
 * MyŠkoda Public API – Dashboard-Karten
 *
 * Wird von der Integration automatisch geladen. Die Karten erscheinen im
 * Karten-Dialog ("Karte hinzufügen") unter "Škoda …". Im Editor wählst du nur
 * das Fahrzeug aus; die passenden Entities werden automatisch gefunden.
 *
 * Es werden ausschließlich Standardkarten von Home Assistant verwendet
 * (gauge, entities, thermostat, map).
 */

const PLATFORM = "myskoda_public";
const VERSION = "0.2.0";

const TEXT = {
  de: {
    battery: "Ladestand",
    fuel: "Tankfüllung",
    charging: "Laden",
    status: "Fahrzeugstatus",
    location: "Standort",
    vehicle: "Fahrzeug",
    no_vehicle:
      "Kein Fahrzeug der Integration „MyŠkoda Public API“ gefunden.",
    unknown_vehicle: "Das gewählte Fahrzeug wurde nicht gefunden.",
    no_entities: "Für dieses Fahrzeug sind keine passenden Entities vorhanden.",
  },
  en: {
    battery: "Battery level",
    fuel: "Fuel level",
    charging: "Charging",
    status: "Vehicle status",
    location: "Location",
    vehicle: "Vehicle",
    no_vehicle: "No vehicle of the “MyŠkoda Public API” integration found.",
    unknown_vehicle: "The selected vehicle was not found.",
    no_entities: "No matching entities exist for this vehicle.",
  },
};

function t(hass, key) {
  const lang = (hass && hass.language) || "en";
  return (TEXT[lang.startsWith("de") ? "de" : "en"] || TEXT.en)[key];
}

/* ------------------------------------------------------------------ */
/* Entity-Erkennung: Gerät -> Entities der Integration (translation_key) */
/* ------------------------------------------------------------------ */

function vehicleDevices(hass) {
  const ids = new Set();
  for (const ent of Object.values(hass.entities || {})) {
    if (ent.platform === PLATFORM && ent.device_id) ids.add(ent.device_id);
  }
  return [...ids];
}

/** Liefert { "sensor:battery_level": "sensor.xyz", ... } für ein Gerät. */
function resolveEntities(hass, deviceId) {
  const map = {};
  for (const ent of Object.values(hass.entities || {})) {
    if (ent.platform !== PLATFORM || ent.device_id !== deviceId) continue;
    if (!ent.translation_key) continue;
    if (!hass.states[ent.entity_id]) continue; // deaktiviert / nicht geladen
    const domain = ent.entity_id.split(".")[0];
    map[`${domain}:${ent.translation_key}`] = ent.entity_id;
  }
  return map;
}

function pick(ents, ...keys) {
  return keys.map((k) => ents[k]).filter(Boolean);
}

/* ------------------------------------------------------------------ */
/* Kartenkonfigurationen (reine Funktionen, leicht testbar)             */
/* ------------------------------------------------------------------ */

function chargingConfig(ents, hass) {
  const cards = [];
  if (ents["sensor:battery_level"]) {
    cards.push({
      type: "gauge",
      entity: ents["sensor:battery_level"],
      name: t(hass, "battery"),
      min: 0,
      max: 100,
      needle: false,
      severity: { red: 0, yellow: 20, green: 40 },
    });
  } else if (ents["sensor:fuel_level"]) {
    cards.push({
      type: "gauge",
      entity: ents["sensor:fuel_level"],
      name: t(hass, "fuel"),
      min: 0,
      max: 100,
      needle: false,
      severity: { red: 0, yellow: 15, green: 30 },
    });
  }
  const rows = pick(
    ents,
    "sensor:electric_range",
    "sensor:total_range",
    "sensor:charging_state",
    "sensor:charging_power",
    "sensor:remaining_charging_time",
    "sensor:fully_charged_at",
    "binary_sensor:plug_connected",
    "switch:charging_switch",
    "number:charge_limit",
    "select:charge_mode",
    "sensor:charging_profile",
  );
  if (rows.length) {
    cards.push({
      type: "entities",
      title: t(hass, "charging"),
      entities: rows,
    });
  }
  return cards;
}

function climateConfig(ents) {
  return ents["climate:air_conditioning"]
    ? [{ type: "thermostat", entity: ents["climate:air_conditioning"] }]
    : [];
}

function statusConfig(ents, hass) {
  const rows = pick(
    ents,
    "binary_sensor:unlocked",
    "binary_sensor:doors",
    "binary_sensor:windows",
    "binary_sensor:trunk",
    "binary_sensor:bonnet",
    "binary_sensor:sunroof",
    "binary_sensor:lights",
    "sensor:odometer",
    "switch:active_ventilation",
    "switch:auxiliary_heating",
  );
  return rows.length
    ? [{ type: "entities", title: t(hass, "status"), entities: rows }]
    : [];
}

function locationConfig(ents, hass) {
  const tracker = ents["device_tracker:location"];
  if (!tracker) return [];
  const cards = [
    {
      type: "map",
      title: t(hass, "location"),
      entities: [tracker],
      default_zoom: 15,
      aspect_ratio: "16:9",
    },
  ];
  if (ents["sensor:parking_address"]) {
    cards.push({
      type: "entities",
      entities: [ents["sensor:parking_address"]],
    });
  }
  return cards;
}

/* ------------------------------------------------------------------ */
/* Basisklasse                                                          */
/* ------------------------------------------------------------------ */

class SkodaBaseCard extends HTMLElement {
  setConfig(config) {
    this._config = { ...config };
    this._signature = null; // erzwingt Neuaufbau
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return this._size || 4;
  }

  /** Von Unterklassen überschrieben: Entity-Map -> Liste von Karten-Configs */
  buildCards(_ents, _hass) {
    return [];
  }

  _message(text) {
    if (!this._root) {
      this._root = document.createElement("ha-card");
      this.appendChild(this._root);
    }
    this._inner = null;
    this._signature = null;
    this._root.innerHTML = "";
    const div = document.createElement("div");
    div.style.padding = "16px";
    div.textContent = text;
    this._root.appendChild(div);
  }

  async _render() {
    const hass = this._hass;
    if (!hass || !this._config) return;

    const devices = vehicleDevices(hass);
    if (!devices.length) return this._message(t(hass, "no_vehicle"));

    const deviceId = this._config.device_id || devices[0];
    if (!devices.includes(deviceId)) {
      return this._message(t(hass, "unknown_vehicle"));
    }

    const ents = resolveEntities(hass, deviceId);
    const cards = this.buildCards(ents, hass);
    if (!cards.length) return this._message(t(hass, "no_entities"));

    const signature = JSON.stringify(cards);
    if (signature !== this._signature || !this._inner) {
      this._signature = signature;
      const token = (this._token = (this._token || 0) + 1);
      const helpers = await window.loadCardHelpers();
      if (token !== this._token) return; // veraltet
      const config =
        cards.length === 1 ? cards[0] : { type: "vertical-stack", cards };
      const el = helpers.createCardElement(config);
      this._size = cards.length === 1 ? 4 : cards.length * 4;
      this.innerHTML = "";
      this._root = null;
      this._inner = el;
      this.appendChild(el);
    }
    this._inner.hass = hass;
  }

  static getConfigElement() {
    return document.createElement("skoda-card-editor");
  }

  static getStubConfig() {
    return {};
  }
}

class SkodaChargingCard extends SkodaBaseCard {
  buildCards(ents, hass) {
    return chargingConfig(ents, hass);
  }
}
class SkodaClimateCard extends SkodaBaseCard {
  buildCards(ents) {
    return climateConfig(ents);
  }
}
class SkodaStatusCard extends SkodaBaseCard {
  buildCards(ents, hass) {
    return statusConfig(ents, hass);
  }
}
class SkodaLocationCard extends SkodaBaseCard {
  buildCards(ents, hass) {
    return locationConfig(ents, hass);
  }
}

/* ------------------------------------------------------------------ */
/* Visueller Editor: nur Fahrzeugauswahl                                */
/* ------------------------------------------------------------------ */

class SkodaCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = config || {};
    this._update();
  }

  set hass(hass) {
    this._hass = hass;
    this._update();
  }

  _update() {
    if (!this._hass || !this._config) return;
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.schema = [
        {
          name: "device_id",
          selector: { device: { integration: PLATFORM } },
        },
      ];
      this._form.computeLabel = () => t(this._hass, "vehicle");
      this._form.addEventListener("value-changed", (ev) => {
        ev.stopPropagation();
        const value = { ...this._config, ...ev.detail.value };
        if (!value.device_id) delete value.device_id;
        this.dispatchEvent(
          new CustomEvent("config-changed", {
            detail: { config: value },
            bubbles: true,
            composed: true,
          }),
        );
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.data = { device_id: this._config.device_id };
  }
}

/* ------------------------------------------------------------------ */
/* Registrierung                                                        */
/* ------------------------------------------------------------------ */

const CARDS = [
  ["skoda-charging-card", SkodaChargingCard, "Škoda – Laden", "Ladestand, Reichweite, Laden, Ladelimit und Lademodus."],
  ["skoda-climate-card", SkodaClimateCard, "Škoda – Klimatisierung", "Standklimatisierung mit Zieltemperatur."],
  ["skoda-status-card", SkodaStatusCard, "Škoda – Fahrzeugstatus", "Verriegelung, Türen, Fenster, Licht und Kilometerstand."],
  ["skoda-location-card", SkodaLocationCard, "Škoda – Standort", "Letzte Parkposition auf der Karte."],
];

if (!customElements.get("skoda-card-editor")) {
  customElements.define("skoda-card-editor", SkodaCardEditor);
}
window.customCards = window.customCards || [];
for (const [tag, cls, name, description] of CARDS) {
  if (!customElements.get(tag)) customElements.define(tag, cls);
  if (!window.customCards.some((c) => c.type === tag)) {
    window.customCards.push({ type: tag, name, description, preview: false });
  }
}

console.info(
  `%c MYSKODA-PUBLIC-CARDS %c ${VERSION} `,
  "color:white;background:#4ba82e;font-weight:bold",
  "color:#4ba82e;background:white;font-weight:bold",
);

// Für Tests (Node): reine Funktionen exportieren
if (typeof module !== "undefined") {
  module.exports = { resolveEntities, chargingConfig, climateConfig, statusConfig, locationConfig, vehicleDevices };
}
