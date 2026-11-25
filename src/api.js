import { ref, watch } from "vue";

const DB_NAME = "F1PitWallCache";
const DB_STORE = "api_cache";
let dbPromise = null;

function openCacheDb() {
  if (typeof indexedDB === "undefined") return Promise.resolve(null);
  if (!dbPromise) {
    try {
      indexedDB.deleteDatabase("F1TelemetryCache");
    } catch {}
    dbPromise = new Promise((resolve, reject) => {
      let req;
      try {
        req = indexedDB.open(DB_NAME, 1);
      } catch {
        dbPromise = null;
        return resolve(null);
      }
      const reset = () => {
        dbPromise = null;
      };
      req.onupgradeneeded = () => {
        if (!req.result.objectStoreNames.contains(DB_STORE)) {
          req.result.createObjectStore(DB_STORE, { keyPath: "url" });
        }
      };
      req.onsuccess = () => {
        const db = req.result;
        db.onclose = reset;
        db.onversionchange = () => {
          db.close();
          reset();
        };
        resolve(db);
      };
      req.onerror = () => {
        reset();
        reject(req.error);
      };
      req.onblocked = () => {
        reset();
        resolve(null);
      };
    });
  }
  return dbPromise;
}

async function idbRun(mode, op) {
  const db = await openCacheDb();
  if (!db) return undefined;
  return new Promise((resolve, reject) => {
    let tx;
    try {
      tx = db.transaction(DB_STORE, mode);
    } catch (err) {
      dbPromise = null;
      return reject(err);
    }
    const req = op(tx.objectStore(DB_STORE));
    tx.oncomplete = () => resolve(req.result);
    tx.onerror = () => reject(tx.error || req.error);
    tx.onabort = () => reject(tx.error || new Error("IDB aborted"));
  });
}

const CACHE_DURATION_HOURS = 24;
const LIVE_WEEKEND_CACHE_HOURS = 0.25;
const ETERNAL_CACHE_HOURS = 99999;
const RECENT_WINDOW_MS = 48 * 60 * 60 * 1000;
const CACHE_VERSION = 15;

const API_BASE_URL = import.meta.env?.VITE_API_BASE_URL || "/api";
const eventDatesCache = new Map();

function isWithinRecentWindow(dateStr, nowMs = Date.now()) {
  if (!dateStr) return false;
  const ts = new Date(dateStr).getTime();
  return !Number.isNaN(ts) && Math.abs(nowMs - ts) < RECENT_WINDOW_MS;
}

function getEffectiveCacheHours(
  data,
  defaultCacheHours = CACHE_DURATION_HOURS,
  eventDateIso = null,
  nowMs = Date.now(),
) {
  if (defaultCacheHours === ETERNAL_CACHE_HOURS) return ETERNAL_CACHE_HOURS;
  if (isWithinRecentWindow(eventDateIso, nowMs))
    return LIVE_WEEKEND_CACHE_HOURS;
  if (!data || typeof data !== "object") return defaultCacheHours;

  if (Array.isArray(data.sessions)) {
    if (
      data.sessions.some((s) =>
        isWithinRecentWindow(s?.session_date || s?.date, nowMs),
      ) ||
      (data.event_name &&
        (data.sessions.length < 5 ||
          !data.sessions.some((s) => s?.session_name === "Race")))
    ) {
      return LIVE_WEEKEND_CACHE_HOURS;
    }
  }

  if (
    Array.isArray(data.results) &&
    (!data.total_laps || !data.results.length)
  ) {
    return LIVE_WEEKEND_CACHE_HOURS;
  }

  if (
    Array.isArray(data.events) &&
    data.events.some((e) => isWithinRecentWindow(e?.event_date, nowMs))
  ) {
    return LIVE_WEEKEND_CACHE_HOURS;
  }

  if (
    data.driver1 &&
    Array.isArray(data.driver1.laps) &&
    (!data.driver1.laps.length ||
      (Array.isArray(data.driver2?.laps) && !data.driver2.laps.length))
  ) {
    return LIVE_WEEKEND_CACHE_HOURS;
  }

  return defaultCacheHours;
}

const getCacheHoursForYear = (year) =>
  Number(year) < new Date().getFullYear()
    ? ETERNAL_CACHE_HOURS
    : CACHE_DURATION_HOURS;

const getEventDateIso = (year, eventKey) =>
  year && eventKey ? eventDatesCache.get(`${year}:${eventKey}`) || null : null;

async function fetchAndCache(
  url,
  cacheHours = CACHE_DURATION_HOURS,
  eventDateIso = null,
) {
  const versionedUrl = `${url}${url.includes("?") ? "&" : "?"}v=${CACHE_VERSION}`;

  try {
    const cached = await idbRun("readonly", (s) => s.get(versionedUrl));
    if (cached) {
      const effectiveHours = getEffectiveCacheHours(
        cached.data,
        cacheHours,
        eventDateIso,
      );
      if (Date.now() - cached.timestamp < effectiveHours * 3600_000) {
        return cached.data;
      }
    }
  } catch (err) {
    console.warn(
      `[Cache] Failed to read from IndexedDB for ${versionedUrl}:`,
      err,
    );
  }

  const res = await fetch(versionedUrl);
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  const data = await res.json();

  try {
    await idbRun("readwrite", (s) =>
      s.put({ url: versionedUrl, data, timestamp: Date.now() }),
    );
  } catch (err) {
    console.warn(
      `[Cache] Failed to write to IndexedDB for ${versionedUrl}:`,
      err,
    );
  }

  return data;
}

function apiGet(
  path,
  params,
  { year = null, eventKey = null, hours = null } = {},
) {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") qs.set(k, String(v));
  }
  return fetchAndCache(
    `${API_BASE_URL}/${path}?${qs.toString()}`,
    hours ?? getCacheHoursForYear(year),
    getEventDateIso(year, eventKey),
  );
}

export async function getEvents(year) {
  const data = await apiGet("events", { year }, { year });
  for (const ev of data?.events || []) {
    if (ev?.event_key && ev?.event_date) {
      eventDatesCache.set(`${year}:${ev.event_key}`, ev.event_date);
    }
  }
  return data;
}

export const getSessions = (year, eventKey) =>
  year && eventKey
    ? apiGet("sessions", { year, event_key: eventKey }, { year, eventKey })
    : Promise.resolve({ sessions: [] });

export const getDrivers = (year, eventKey, sessionName) =>
  year && eventKey && sessionName
    ? apiGet(
        "drivers",
        { year, event_key: eventKey, session_name: sessionName },
        { year, eventKey },
      )
    : Promise.resolve({ drivers: [] });

export const getRaceComparison = (
  year,
  eventKey,
  sessionName,
  driver1,
  driver2 = "",
) =>
  year && eventKey && sessionName && driver1
    ? apiGet(
        "race-comparison",
        {
          year,
          event_key: eventKey,
          session_name: sessionName,
          driver1_number: driver1,
          driver2_number: driver2,
        },
        { year, eventKey },
      )
    : Promise.resolve(null);

export const getLapTelemetry = (
  year,
  eventKey,
  sessionName,
  driver1,
  driver2,
  lap1,
  lap2,
) =>
  !year || !eventKey || !sessionName || !driver1 || !lap1 || (driver2 && !lap2)
    ? Promise.resolve(null)
    : apiGet(
        "lap-telemetry",
        {
          year,
          event_key: eventKey,
          session_name: sessionName,
          driver1_number: driver1,
          driver2_number: driver2 && lap2 ? driver2 : null,
          lap1_number: lap1,
          lap2_number: driver2 && lap2 ? lap2 : null,
        },
        { year, eventKey },
      );

export const getRaceSummary = (year, eventKey, sessionName) =>
  year && eventKey && sessionName
    ? apiGet(
        "race-summary",
        { year, event_key: eventKey, session_name: sessionName },
        { year, eventKey },
      )
    : Promise.resolve(null);

export const getWeekendSummary = (year, eventKey) =>
  year && eventKey
    ? apiGet(
        "weekend-summary",
        { year, event_key: eventKey },
        { year, eventKey },
      )
    : Promise.resolve(null);

export const getStandings = (year) =>
  year ? apiGet("standings", { year }, { year }) : Promise.resolve(null);

export const getSeasonStats = (year) =>
  year ? apiGet("season-stats", { year }, { year }) : Promise.resolve(null);

export const getDriverCareer = (driverId) =>
  driverId
    ? apiGet(
        "driver-career",
        { driver_id: driverId },
        { hours: CACHE_DURATION_HOURS },
      )
    : Promise.resolve(null);

export function useSeasonStats(getYear, { onLoaded } = {}) {
  const data = ref(null);
  const loading = ref(true);
  const error = ref(null);
  let reqId = 0;

  async function refresh(yr = getYear()) {
    if (!yr) return;
    const id = ++reqId;
    loading.value = true;
    error.value = null;
    try {
      const res = await getSeasonStats(yr);
      if (id !== reqId) return;
      if (!res) throw new Error(`No data returned for ${yr}`);
      data.value = res;
    } catch (err) {
      if (id !== reqId) return;
      data.value = null;
      error.value = err.message || "Failed to load season statistics.";
    } finally {
      if (id === reqId) {
        loading.value = false;
        onLoaded?.();
      }
    }
  }

  watch(getYear, (yr) => refresh(yr), { immediate: true });
  return { data, loading, error, refresh };
}

export async function getLiveStatus({ signal } = {}) {
  const res = await fetch(`${API_BASE_URL}/live/status`, {
    cache: "no-store",
    signal,
  });
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  return await res.json();
}

export async function getLiveSnapshot({ signal } = {}) {
  const res = await fetch(`${API_BASE_URL}/live/snapshot`, {
    cache: "no-store",
    signal,
  });
  if (!res.ok) {
    let errBody = null;
    try {
      errBody = await res.json();
    } catch {
      // Ignore JSON parse errors on non-JSON upstream failures
    }
    const err = new Error(
      errBody?.error || `HTTP error! status: ${res.status}`,
    );
    err.status = res.status;
    err.code = errBody?.code || "http_error";
    err.authConfigured = errBody?.auth_configured;
    throw err;
  }
  return await res.json();
}
