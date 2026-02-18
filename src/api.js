import { db } from "./database";

const CACHE_DURATION_HOURS = 24; // Default cache duration for current data
const ETERNAL_CACHE_HOURS = 99999; // A very long duration for static, historical data
const CACHE_VERSION = 1; // Increment to invalidate all client-side caches

/**
 * Fetches data from a URL, with client-side caching in IndexedDB.
 * @param {string} url The URL to fetch.
 * @param {number} cacheHours The number of hours to cache the response.
 * @returns {Promise<any>} The JSON response data.
 */
async function fetchAndCache(url, cacheHours = CACHE_DURATION_HOURS) {
  // Append version to URL to force cache invalidation on version bump
  const separator = url.includes("?") ? "&" : "?";
  const versionedUrl = `${url}${separator}v=${CACHE_VERSION}`;

  const cacheMillis = cacheHours * 60 * 60 * 1000;

  // 1. Check for cached data using versioned URL
  const cached = await db.api_cache.get(versionedUrl);
  if (cached && Date.now() - cached.timestamp < cacheMillis) {
    console.log(`[Cache] HIT for ${versionedUrl}`);
    return cached.data;
  }

  console.log(`[Cache] MISS for ${versionedUrl}. Fetching from network...`);

  // 2. If not cached or expired, fetch from network
  // We fetch the original URL, but store it under the versioned key?
  // actually, let's fetch the original URL from network (backend ignores extra params usually)
  // or better, fetch the versioned URL so backend logs show version too.
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

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api";

/**
 * Gets the schedule for a given year. Caches data for past years indefinitely.
 */
export async function getEvents(year) {
  const url = `${API_BASE_URL}/events?year=${year}`;
  const cacheHours =
    year < new Date().getFullYear()
      ? ETERNAL_CACHE_HOURS
      : CACHE_DURATION_HOURS;
  return await fetchAndCache(url, cacheHours);
}

/**
 * Gets the sessions for a given event. Caches data for past years indefinitely.
 */
export async function getSessions(year, eventKey) {
  if (!year || !eventKey) return { sessions: [] };
  const url = `${API_BASE_URL}/sessions?year=${year}&event_key=${eventKey}`;
  const cacheHours =
    year < new Date().getFullYear()
      ? ETERNAL_CACHE_HOURS
      : CACHE_DURATION_HOURS;
  return await fetchAndCache(url, cacheHours);
}

/**
 * Gets the drivers for a given session. Caches data for past years indefinitely.
 */
export async function getDrivers(year, eventKey, sessionName) {
  if (!year || !eventKey || !sessionName) return { drivers: [] };
  const url = `${API_BASE_URL}/drivers?year=${year}&event_key=${eventKey}&session_name=${sessionName}`;
  const cacheHours =
    year < new Date().getFullYear()
      ? ETERNAL_CACHE_HOURS
      : CACHE_DURATION_HOURS;
  return await fetchAndCache(url, cacheHours);
}

/**
 * Gets the lap-by-lap comparison for two drivers. This data is static and cached indefinitely.
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
  return await fetchAndCache(url, ETERNAL_CACHE_HOURS);
}

/**
 * Gets the telemetry for specific laps for two drivers. This data is static and cached indefinitely.
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
  return await fetchAndCache(url, ETERNAL_CACHE_HOURS);
}

/**
 * Gets the race summary including standings and tyre stints.
 */
export async function getRaceSummary(year, eventKey, sessionName) {
  if (!year || !eventKey || !sessionName) return null;
  const url = `${API_BASE_URL}/race-summary?year=${year}&event_key=${eventKey}&session_name=${sessionName}`;
  const cacheHours =
    year < new Date().getFullYear()
      ? ETERNAL_CACHE_HOURS
      : CACHE_DURATION_HOURS;
  return await fetchAndCache(url, cacheHours);
}
