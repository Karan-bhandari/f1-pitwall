/**
 * Centralized tyre color, icon, timezone, and unit utilities.
 */

import { ref } from "vue";
import hardTyre from "@/assets/tyres/hard.svg";
import mediumTyre from "@/assets/tyres/medium.svg";
import softTyre from "@/assets/tyres/soft.svg";
import intermediateTyre from "@/assets/tyres/intermediate.svg";
import wetTyre from "@/assets/tyres/wet.svg";

const TYRE_COLORS = {
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

export function getTyreColor(compound) {
  return TYRE_COLORS[compound?.toUpperCase()] || "#777777";
}

export function getTyreIcon(compound) {
  const c = (compound || "HARD").toUpperCase();
  return (
    Object.entries(TYRE_ICONS).find(([k]) => c.includes(k))?.[1] ||
    TYRE_ICONS.HARD
  );
}

export function formatLapTime(seconds) {
  if (seconds === null || seconds === undefined || isNaN(seconds)) return "N/A";
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = (seconds % 60).toFixed(3);
  return `${minutes}:${String(remainingSeconds).padStart(6, "0")}`;
}

export function formatLapTimeString(timeStr) {
  if (!timeStr) return "--";
  const parts = timeStr.split(":");
  if (parts.length < 3) return timeStr;
  return `${parseInt(parts[1], 10)}:${parseFloat(parts[2]).toFixed(3).padStart(6, "0")}`;
}

export function adjustColor(color, amount) {
  return `#${color.replace(/^#/, "").replace(/../g, (hex) =>
    Math.min(255, Math.max(0, parseInt(hex, 16) + amount))
      .toString(16)
      .padStart(2, "0"),
  )}`;
}

function persistedRef(key, allowed, fallback) {
  let initial = fallback;
  try {
    const saved = localStorage.getItem(key);
    if (allowed.includes(saved)) initial = saved;
  } catch {}
  const state = ref(initial);
  return [
    state,
    (val) => {
      state.value = allowed.includes(val) ? val : fallback;
      try {
        localStorage.setItem(key, state.value);
      } catch {}
    },
  ];
}

export const [timeZoneMode, setTimeZoneMode] = persistedRef(
  "f1_pitwall_tz_mode",
  ["local", "track"],
  "local",
);

function parseGmtOffsetMinutes(offsetStr) {
  if (!offsetStr || typeof offsetStr !== "string") return null;
  const match = offsetStr.trim().match(/^([+-])(\d{2}):?(\d{2})(?::?\d{2})?$/);
  if (!match) return null;
  const sign = match[1] === "-" ? -1 : 1;
  const hours = parseInt(match[2], 10);
  const mins = parseInt(match[3], 10);
  return Number.isNaN(hours) || Number.isNaN(mins)
    ? null
    : sign * (hours * 60 + mins);
}

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

function shiftToZone(utcStr, mode, gmtOffset) {
  if (!utcStr) return null;
  const s = String(utcStr).trim();
  if (!s) return null;
  const hasTz =
    s.endsWith("Z") ||
    s.endsWith("z") ||
    (s.length > 10 && /[+-]\d{2}:?\d{2}$/.test(s.slice(10)));
  const d = new Date(hasTz ? s : `${s}Z`);
  if (Number.isNaN(d.getTime())) return null;

  const offsetMins = mode === "track" ? parseGmtOffsetMinutes(gmtOffset) : null;
  return {
    target:
      offsetMins !== null ? new Date(d.getTime() + offsetMins * 60000) : d,
    tzOpt: offsetMins !== null ? { timeZone: "UTC" } : {},
  };
}

export function formatTimeInZone(
  utcStr,
  { mode = "local", gmtOffset = null, includeSeconds = true } = {},
) {
  const shifted = shiftToZone(utcStr, mode, gmtOffset);
  if (!shifted) return includeSeconds ? "--:--:--" : "--:--";
  return shifted.target.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    ...(includeSeconds ? { second: "2-digit" } : {}),
    ...shifted.tzOpt,
  });
}

export function formatSessionDateTime(
  utcStr,
  { mode = "local", gmtOffset = null } = {},
) {
  const shifted = shiftToZone(utcStr, mode, gmtOffset);
  if (!shifted) return { day: "TBD", time: "--:--" };
  return {
    day: shifted.target.toLocaleDateString("en-US", {
      weekday: "short",
      month: "short",
      day: "numeric",
      ...shifted.tzOpt,
    }),
    time: formatTimeInZone(utcStr, { mode, gmtOffset, includeSeconds: false }),
  };
}

export const [unitSystem, setUnitSystem] = persistedRef(
  "f1_pitwall_units",
  ["metric", "imperial"],
  "metric",
);

function toNum(val) {
  if (val === null || val === undefined || val === "") return null;
  const num = Number(val);
  return Number.isNaN(num) ? null : num;
}

export function formatTemperature(celsius, system = unitSystem.value) {
  const num = toNum(celsius);
  if (num === null) return "—";
  return system === "imperial"
    ? `${((num * 9) / 5 + 32).toFixed(1)}°F`
    : `${num.toFixed(1)}°C`;
}

export function formatWindSpeed(metersPerSec, system = unitSystem.value) {
  const num = toNum(metersPerSec);
  if (num === null) return "—";
  return system === "imperial"
    ? `${(num * 2.23694).toFixed(1)} mph`
    : `${(num * 3.6).toFixed(1)} km/h`;
}

export function convertSpeedKmh(kmh, system = unitSystem.value) {
  const num = toNum(kmh);
  if (num === null) return null;
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
