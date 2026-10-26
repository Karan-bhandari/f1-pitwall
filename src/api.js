import { db } from "./database.js";

const CACHE_DURATION_HOURS = 24; // Default cache duration for current data
const LIVE_WEEKEND_CACHE_HOURS = 0.25; // 15-minute TTL for active/recent (<48h) or incomplete race weekend data
const ETERNAL_CACHE_HOURS = 99999; // A very long duration for static, historical data
const RECENT_WINDOW_MS = 48 * 60 * 60 * 1000; // 48 hours in milliseconds
const CACHE_VERSION = 7; // Increment to invalidate all client-side caches

const eventDatesCache = new Map();

function isWithinRecentWindow(dateStr, nowMs = Date.now()) {
  if (!dateStr) return false;
  const ts = new Date(dateStr).getTime();
  if (Number.isNaN(ts)) return false;
  return Math.abs(nowMs - ts) < RECENT_WINDOW_MS;
}

/**
 * Determines the effective cache duration in hours based on session/event recency
 * (< 48 hours) and payload completeness.
 */
export function getEffectiveCacheHours(
  data,
  defaultCacheHours = CACHE_DURATION_HOURS,
  eventDateIso = null,
  nowMs = Date.now(),
) {
  if (defaultCacheHours === ETERNAL_CACHE_HOURS) {
    return ETERNAL_CACHE_HOURS;
  }

  if (isWithinRecentWindow(eventDateIso, nowMs)) {
    return LIVE_WEEKEND_CACHE_HOURS;
  }

  if (!data || typeof data !== "object") {
    return defaultCacheHours;
  }

  if (Array.isArray(data.sessions)) {
    const hasRecentSession = data.sessions.some((s) =>
      isWithinRecentWindow(s?.session_date || s?.date, nowMs),
    );
    if (hasRecentSession) return LIVE_WEEKEND_CACHE_HOURS;

    if (
      data.event_name &&
      (data.sessions.length < 5 ||
        !data.sessions.some((s) => s?.session_name === "Race"))
    ) {
      return LIVE_WEEKEND_CACHE_HOURS;
    }
  }

  if (Array.isArray(data.results)) {
    if (!data.total_laps || data.results.length === 0) {
      return LIVE_WEEKEND_CACHE_HOURS;
    }
  }

  if (Array.isArray(data.events)) {
    if (data.events.some((e) => isWithinRecentWindow(e?.event_date, nowMs))) {
      return LIVE_WEEKEND_CACHE_HOURS;
    }
  }

  if (data.driver1 && data.driver2 && Array.isArray(data.driver1.laps)) {
    if (data.driver1.laps.length === 0 || data.driver2.laps.length === 0) {
      return LIVE_WEEKEND_CACHE_HOURS;
    }
  }

  return defaultCacheHours;
}

function getCacheHoursForYear(year) {
  return Number(year) < new Date().getFullYear()
    ? ETERNAL_CACHE_HOURS
    : CACHE_DURATION_HOURS;
}

function getEventDateIso(year, eventKey) {
  if (!year || !eventKey) return null;
  return eventDatesCache.get(`${year}:${eventKey}`) || null;
}

/**
 * Fetches data from a URL, with client-side caching in IndexedDB.
 * @param {string} url The URL to fetch.
 * @param {number} cacheHours The number of hours to cache the response.
 * @param {string|null} eventDateIso Optional ISO date of the event for dynamic TTL.
 * @returns {Promise<any>} The JSON response data.
 */
async function fetchAndCache(
  url,
  cacheHours = CACHE_DURATION_HOURS,
  eventDateIso = null,
) {
  // Append version to URL to force cache invalidation on version bump
  const separator = url.includes("?") ? "&" : "?";
  const versionedUrl = `${url}${separator}v=${CACHE_VERSION}`;

  // 1. Check for cached data using versioned URL
  const cached = await db.api_cache.get(versionedUrl);
  if (cached) {
    const effectiveHours = getEffectiveCacheHours(
      cached.data,
      cacheHours,
      eventDateIso,
    );
    const cacheMillis = effectiveHours * 60 * 60 * 1000;
    if (Date.now() - cached.timestamp < cacheMillis) {
      console.log(`[Cache] HIT for ${versionedUrl}`);
      return cached.data;
    }
  }

  console.log(`[Cache] MISS for ${versionedUrl}. Fetching from network...`);

  // 2. If not cached or expired, fetch from network
  const res = await fetch(versionedUrl);
  if (!res.ok) {
    throw new Error(`HTTP error! status: ${res.status}`);
  }
  const data = await res.json();

  // 3. Store the new data in the cache under versioned key
  await db.api_cache.put({
    url: versionedUrl,
    data,
    timestamp: Date.now(),
  });

  return data;
}

const API_BASE_URL = import.meta.env?.VITE_API_BASE_URL || "/api";

/**
 * Gets the schedule for a given year. Caches data for past years indefinitely.
 */
export async function getEvents(year) {
  const url = `${API_BASE_URL}/events?year=${year}`;
  const data = await fetchAndCache(url, getCacheHoursForYear(year));
  if (Array.isArray(data?.events)) {
    for (const ev of data.events) {
      if (ev?.event_key && ev?.event_date) {
        eventDatesCache.set(`${year}:${ev.event_key}`, ev.event_date);
      }
    }
  }
  return data;
}

/**
 * Gets the sessions for a given event. Caches data for past years indefinitely.
 */
export async function getSessions(year, eventKey) {
  if (!year || !eventKey) return { sessions: [] };
  const url = `${API_BASE_URL}/sessions?year=${year}&event_key=${eventKey}`;
  return await fetchAndCache(
    url,
    getCacheHoursForYear(year),
    getEventDateIso(year, eventKey),
  );
}

/**
 * Gets the drivers for a given session. Caches data for past years indefinitely.
 */
export async function getDrivers(year, eventKey, sessionName) {
  if (!year || !eventKey || !sessionName) return { drivers: [] };
  const url = `${API_BASE_URL}/drivers?year=${year}&event_key=${eventKey}&session_name=${sessionName}`;
  return await fetchAndCache(
    url,
    getCacheHoursForYear(year),
    getEventDateIso(year, eventKey),
  );
}

/**
 * Gets the lap-by-lap comparison for two drivers.
 */
export async function getRaceComparison(
  year,
  eventKey,
  sessionName,
  driver1,
  driver2,
) {
  if (!year || !eventKey || !sessionName || !driver1 || !driver2) return null;
  const url = `${API_BASE_URL}/race-comparison?year=${year}&event_key=${eventKey}&session_name=${sessionName}&driver1_number=${driver1}&driver2_number=${driver2}`;
  return await fetchAndCache(
    url,
    getCacheHoursForYear(year),
    getEventDateIso(year, eventKey),
  );
}

/**
 * Gets the telemetry for specific laps for two drivers.
 */
export async function getLapTelemetry(
  year,
  eventKey,
  sessionName,
  driver1,
  driver2,
  lap1,
  lap2,
) {
  if (
    !year ||
    !eventKey ||
    !sessionName ||
    !driver1 ||
    !driver2 ||
    !lap1 ||
    !lap2
  )
    return null;
  const url = `${API_BASE_URL}/lap-telemetry?year=${year}&event_key=${eventKey}&session_name=${sessionName}&driver1_number=${driver1}&driver2_number=${driver2}&lap1_number=${lap1}&lap2_number=${lap2}`;
  return await fetchAndCache(
    url,
    getCacheHoursForYear(year),
    getEventDateIso(year, eventKey),
  );
}

/**
 * Gets the race summary including standings and tyre stints.
 */
export async function getRaceSummary(year, eventKey, sessionName) {
  if (!year || !eventKey || !sessionName) return null;
  const url = `${API_BASE_URL}/race-summary?year=${year}&event_key=${eventKey}&session_name=${sessionName}`;
  return await fetchAndCache(
    url,
    getCacheHoursForYear(year),
    getEventDateIso(year, eventKey),
  );
}

/**
 * Gets the weekend summary (Recap) for all sessions.
 */
export async function getWeekendSummary(year, eventKey) {
  if (!year || !eventKey) return null;
  const url = `${API_BASE_URL}/weekend-summary?year=${year}&event_key=${eventKey}`;
  return await fetchAndCache(
    url,
    getCacheHoursForYear(year),
    getEventDateIso(year, eventKey),
  );
}

/**
 * Gets the driver and constructor championship standings for a given season.
 */
export async function getStandings(year) {
  if (!year) return null;
  const url = `${API_BASE_URL}/standings?year=${year}`;
  return await fetchAndCache(url, getCacheHoursForYear(year));
}
