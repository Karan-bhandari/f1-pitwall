import Dexie from "dexie";

export const db = new Dexie("F1TelemetryCache");

// Define the database schema.
// 'url' is the primary key (the API endpoint URL).
// 'timestamp' is an index to allow for cache invalidation.
db.version(1).stores({
  api_cache: "&url, timestamp",
});

// Version 2: Clear cache to ensure users get the new turn data
db.version(2)
  .stores({
    api_cache: "&url, timestamp",
  })
  .upgrade((trans) => {
    return trans.table("api_cache").clear();
  });

// Version 3: Clear cache to ensure users get the new lap time formatting
db.version(3)
  .stores({
    api_cache: "&url, timestamp",
  })
  .upgrade((trans) => {
    return trans.table("api_cache").clear();
  });
