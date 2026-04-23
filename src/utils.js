/**
 * Centralized tyre color and icon utilities.
 * Replaces duplicated getTyreColor/getTyreIcon across RaceSummary, QualifyingSummary, SessionRecap.
 */

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
