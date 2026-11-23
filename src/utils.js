/**
 * Centralized tyre color and icon utilities.
 * Replaces duplicated getTyreColor/getTyreIcon across RaceSummary, QualifyingSummary, SessionRecap.
 */

import { ref } from "vue";
import hardTyre from "@/assets/tyres/hard.svg";
import mediumTyre from "@/assets/tyres/medium.svg";
import softTyre from "@/assets/tyres/soft.svg";
import intermediateTyre from "@/assets/tyres/intermediate.svg";
import wetTyre from "@/assets/tyres/wet.svg";

export const TYRE_COLORS = {
  SOFT: "#ff3333",
  MEDIUM: "#ffff00",
  HARD: "#ffffff",
  INTERMEDIATE: "#00ff00",
  WET: "#0000ff",
};

export const TYRE_ICONS = {
  SOFT: softTyre,
  MEDIUM: mediumTyre,
  HARD: hardTyre,
  INTERMEDIATE: intermediateTyre,
  WET: wetTyre,
};

/**
 * Returns the hex color for a given tyre compound.
 * @param {string} compound - e.g. "SOFT", "medium"
 * @returns {string} Hex color string
 */
export function getTyreColor(compound) {
  return TYRE_COLORS[compound?.toUpperCase()] || "#777777";
}

/**
 * Returns the SVG icon path for a given tyre compound.
 * @param {string} compound - e.g. "SOFT", "medium"
 * @returns {string} SVG import path
 */
export function getTyreIcon(compound) {
  const c = (compound || "HARD").toUpperCase();
  if (c.includes("SOFT")) return TYRE_ICONS.SOFT;
  if (c.includes("MEDIUM")) return TYRE_ICONS.MEDIUM;
  if (c.includes("HARD")) return TYRE_ICONS.HARD;
  if (c.includes("INTERMEDIATE")) return TYRE_ICONS.INTERMEDIATE;
  if (c.includes("WET")) return TYRE_ICONS.WET;
  return TYRE_ICONS.HARD;
}

/**
 * Formats a lap time from seconds to "M:SS.mmm" format.
 * @param {number|null} seconds - Lap time in seconds
 * @returns {string} Formatted lap time or "N/A"
 */
export function formatLapTime(seconds) {
  if (seconds === null || seconds === undefined || isNaN(seconds)) return "N/A";
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = (seconds % 60).toFixed(3);
  return `${minutes}:${String(remainingSeconds).padStart(6, "0")}`;
}

/**
 * Formats a lap time string like "0:01:23.456" to "1:23.456".
 * @param {string|null} timeStr - Time string in HH:MM:SS.mmm format
 * @returns {string} Formatted time or "--"
 */
export function formatLapTimeString(timeStr) {
  if (!timeStr) return "--";
  const parts = timeStr.split(":");
  if (parts.length < 3) return timeStr;
  const mins = parseInt(parts[1]);
  const secs = parseFloat(parts[2]).toFixed(3);
  return `${mins}:${secs.padStart(6, "0")}`;
}

/**
 * Lightens or darkens a hex color by a given amount.
 * @param {string} color - Hex color (e.g. "#ff0000")
 * @param {number} amount - Positive to lighten, negative to darken
 * @returns {string} Adjusted hex color
 */
export function adjustColor(color, amount) {
  return (
    "#" +
    color
      .replace(/^#/, "")
      .replace(/../g, (color) =>
        (
          "0" +
          Math.min(255, Math.max(0, parseInt(color, 16) + amount)).toString(16)
        ).substr(-2),
      )
  );
}

const TZ_STORAGE_KEY = "f1_pitwall_tz_mode";

function readInitialTzMode() {
  try {
    if (typeof localStorage !== "undefined") {
      const saved = localStorage.getItem(TZ_STORAGE_KEY);
      if (saved === "local" || saved === "track") return saved;
    }
  } catch {
    // Ignore storage access restrictions
  }
  return "local";
}

export const timeZoneMode = ref(readInitialTzMode());

export function setTimeZoneMode(mode) {
  const normalized = mode === "track" ? "track" : "local";
  timeZoneMode.value = normalized;
  try {
    if (typeof localStorage !== "undefined") {
      localStorage.setItem(TZ_STORAGE_KEY, normalized);
    }
  } catch {
    // Ignore storage access restrictions
  }
}

/**
 * Parses an F1 GMT offset string like "-08:00:00", "+03:00", or "-0800" into signed minutes.
 */
export function parseGmtOffsetMinutes(offsetStr) {
  if (!offsetStr || typeof offsetStr !== "string") return null;
  const match = offsetStr.trim().match(/^([+-])(\d{2}):?(\d{2})(?::?\d{2})?$/);
  if (!match) return null;
  const sign = match[1] === "-" ? -1 : 1;
  const hours = parseInt(match[2], 10);
  const mins = parseInt(match[3], 10);
  if (Number.isNaN(hours) || Number.isNaN(mins)) return null;
  return sign * (hours * 60 + mins);
}

/**
 * Formats an F1 GMT offset string into a concise label like "UTC-8" or "UTC+5:30".
 */
export function formatOffsetLabel(offsetStr) {
  const totalMinutes = parseGmtOffsetMinutes(offsetStr);
  if (totalMinutes === null) return "";
  if (totalMinutes === 0) return "UTC";
  const sign = totalMinutes >= 0 ? "+" : "-";
  const absMins = Math.abs(totalMinutes);
  const hrs = Math.floor(absMins / 60);
  const mins = absMins % 60;
  return mins === 0
    ? `UTC${sign}${hrs}`
    : `UTC${sign}${hrs}:${String(mins).padStart(2, "0")}`;
}

/**
 * Returns the browser's short timezone label (e.g. "CST", "EST", "GMT+1").
 */
export function getLocalTimezoneLabel() {
  try {
    const parts = new Intl.DateTimeFormat(undefined, {
      timeZoneName: "short",
    }).formatToParts(new Date());
    const tzPart = parts.find((p) => p.type === "timeZoneName");
    if (tzPart?.value) return tzPart.value;
  } catch {
    // Ignore Intl errors
  }
  return "Local";
}

function normalizeUtcIso(utcStr) {
  if (!utcStr) return null;
  const s = String(utcStr).trim();
  if (!s) return null;
  const hasTz =
    s.endsWith("Z") ||
    s.endsWith("z") ||
    (s.length > 10 && /[+-]\d{2}:?\d{2}$/.test(s.slice(10)));
  const d = new Date(hasTz ? s : `${s}Z`);
  return Number.isNaN(d.getTime()) ? null : d;
}

/**
 * Formats a UTC timestamp into either the user's local timezone or the circuit's track timezone.
 */
export function formatTimeInZone(
  utcStr,
  { mode = "local", gmtOffset = null, includeSeconds = true } = {},
) {
  const d = normalizeUtcIso(utcStr);
  if (!d) return includeSeconds ? "--:--:--" : "--:--";

  const offsetMins = mode === "track" ? parseGmtOffsetMinutes(gmtOffset) : null;
  const target =
    offsetMins !== null ? new Date(d.getTime() + offsetMins * 60000) : d;
  const opts = {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    ...(includeSeconds ? { second: "2-digit" } : {}),
    ...(offsetMins !== null ? { timeZone: "UTC" } : {}),
  };
  return target.toLocaleTimeString([], opts);
}

/**
 * Formats an F1 session timestamp into { day, time } for Season Hub weekend schedules.
 */
export function formatSessionDateTime(
  utcStr,
  { mode = "local", gmtOffset = null } = {},
) {
  const d = normalizeUtcIso(utcStr);
  if (!d) return { day: "TBD", time: "--:--" };

  const offsetMins = mode === "track" ? parseGmtOffsetMinutes(gmtOffset) : null;
  const target =
    offsetMins !== null ? new Date(d.getTime() + offsetMins * 60000) : d;
  const tzOpt = offsetMins !== null ? { timeZone: "UTC" } : {};

  const day = target.toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    ...tzOpt,
  });
  const time = target.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    ...tzOpt,
  });
  return { day, time };
}

const UNIT_STORAGE_KEY = "f1_pitwall_units";

function readInitialUnitSystem() {
  try {
    if (typeof localStorage !== "undefined") {
      const saved = localStorage.getItem(UNIT_STORAGE_KEY);
      if (saved === "metric" || saved === "imperial") return saved;
    }
  } catch {
    // Ignore storage access restrictions
  }
  return "metric";
}

export const unitSystem = ref(readInitialUnitSystem());

export function setUnitSystem(system) {
  const normalized = system === "imperial" ? "imperial" : "metric";
  unitSystem.value = normalized;
  try {
    if (typeof localStorage !== "undefined") {
      localStorage.setItem(UNIT_STORAGE_KEY, normalized);
    }
  } catch {
    // Ignore storage access restrictions
  }
}

export function formatTemperature(celsius, system = unitSystem.value) {
  if (celsius === null || celsius === undefined || celsius === "") return "—";
  const num = Number(celsius);
  if (Number.isNaN(num)) return "—";
  if (system === "imperial") {
    return `${((num * 9) / 5 + 32).toFixed(1)}°F`;
  }
  return `${num.toFixed(1)}°C`;
}

export function formatWindSpeed(metersPerSec, system = unitSystem.value) {
  if (
    metersPerSec === null ||
    metersPerSec === undefined ||
    metersPerSec === ""
  )
    return "—";
  const num = Number(metersPerSec);
  if (Number.isNaN(num)) return "—";
  if (system === "imperial") {
    return `${(num * 2.23694).toFixed(1)} mph`;
  }
  return `${(num * 3.6).toFixed(1)} km/h`;
}

export function convertSpeedKmh(kmh, system = unitSystem.value) {
  if (kmh === null || kmh === undefined || kmh === "") return null;
  const num = Number(kmh);
  if (Number.isNaN(num)) return null;
  return system === "imperial" ? num * 0.621371 : num;
}

export function getSpeedUnitLabel(system = unitSystem.value) {
  return system === "imperial" ? "mph" : "km/h";
}

export function formatSpeedKmh(
  kmh,
  { system = unitSystem.value, decimals = 0, includeUnit = false } = {},
) {
  const converted = convertSpeedKmh(kmh, system);
  if (converted === null) return "—";
  const val = converted.toFixed(decimals);
  return includeUnit ? `${val} ${getSpeedUnitLabel(system)}` : val;
}
