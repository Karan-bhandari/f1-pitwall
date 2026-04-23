import Dexie from "dexie";

export const db = new Dexie("F1TelemetryCache");

// Single schema version. Cache busting is handled by the CACHE_VERSION
// constant in api.js which appends a version param to every URL.
// Incrementing CACHE_VERSION there automatically invalidates stale entries
// without needing a new Dexie schema migration each time.
db.version(1).stores({
  api_cache: "&url, timestamp",
});
