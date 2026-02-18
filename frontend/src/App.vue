<script setup>
import { ref, watch, onMounted, shallowRef, computed } from "vue";
import F1Controls from "./components/F1Controls.vue";
import TelemetryChart from "./components/TelemetryChart.vue";
import LapTimeChart from "./components/LapTimeChart.vue";
import RaceSummary from "./components/RaceSummary.vue";
import QualifyingSummary from "./components/QualifyingSummary.vue";
import {
  getEvents,
  getSessions,
  getDrivers,
  getRaceComparison,
  getLapTelemetry,
  getRaceSummary,
} from "./api.js";

// --- Theme State ---
const theme = ref("light");
const toggleTheme = () => {
  theme.value = theme.value === "light" ? "dark" : "light";
};

// --- Data State ---
const year = ref(new Date().getFullYear());
const currentYear = new Date().getFullYear();
const years = Array.from(
  { length: currentYear - 2018 + 1 },
  (_, i) => currentYear - i,
);
const events = ref([]);
const selectedEventKey = ref("");
const isLoadingEvents = ref(false);
const eventsError = ref(null);
const sessions = ref([]);
const selectedSessionName = ref("");
const isLoadingSessions = ref(false);
const sessionsError = ref(null);
const drivers = ref([]);
const selectedDriver1 = ref("");
const selectedDriver2 = ref("");
const isLoadingDrivers = ref(false);
const driversError = ref(null);
const raceComparison = shallowRef(null);
const isLoadingComparison = ref(false);
const comparisonError = ref(null);

// --- View State ---
const viewMode = ref("summary"); // 'summary' or 'comparison'
const summaryData = shallowRef(null);
const isLoadingSummary = ref(false);
const summaryError = ref(null);

const isQualifyingSession = computed(() => {
  const name = selectedSessionName.value?.toLowerCase() || "";
  return name.includes("qualifying") || name.includes("practice");
});

// --- Telemetry State ---
const selectedLap1 = ref(null);
const selectedLap2 = ref(null);
const telemetryData = shallowRef(null);
const isLoadingTelemetry = ref(false);
const telemetryError = ref(null);

// --- State Management ---
const resetState = (level) => {
  // level 0: Reset everything (year change)
  if (level <= 0) {
    events.value = [];
    selectedEventKey.value = "";
  }
  // level 1: Reset from event down (event change)
  if (level <= 1) {
    sessions.value = [];
    selectedSessionName.value = "";
  }
  // level 2: Reset from session down (session change)
  if (level <= 2) {
    drivers.value = [];
    selectedDriver1.value = "";
    selectedDriver2.value = "";
  }
  // level 3: Reset comparison and telemetry (driver change)
  if (level <= 3) {
    raceComparison.value = null;
    selectedLap1.value = null;
    selectedLap2.value = null;
    telemetryData.value = null;
    summaryData.value = null;
  }
};

const handleQuickLapSelect = async ({ driverNumber, lapNumber }) => {
  // Switch to comparison mode to show telemetry
  viewMode.value = "comparison";

  // Set the first driver as the selected one from summary
  selectedDriver1.value = driverNumber;
  selectedLap1.value = lapNumber;

  // If driver 2 isn't set, set it to the same or leave it
  if (!selectedDriver2.value) {
    selectedDriver2.value = driverNumber;
    selectedLap2.value = lapNumber;
  }
};

// --- API Fetching ---
const fetchRaceSummary = async () => {
  console.log(
    "Fetching summary for:",
    selectedSessionName.value,
    "ViewMode:",
    viewMode.value,
  );
  if (!selectedSessionName.value || viewMode.value !== "summary") {
    console.log("Summary fetch skipped: missing session or wrong view mode");
    return;
  }
  isLoadingSummary.value = true;
  summaryError.value = null;
  try {
    const data = await getRaceSummary(
      year.value,
      selectedEventKey.value,
      selectedSessionName.value,
    );
    console.log("Summary data received:", data);
    summaryData.value = data;
  } catch (e) {
    console.error("Failed to fetch race summary:", e);
    summaryError.value = "Could not load session summary.";
  } finally {
    isLoadingSummary.value = false;
  }
};

const fetchEvents = async () => {
  isLoadingEvents.value = true;
  eventsError.value = null;
  resetState(0);

  try {
    const data = await getEvents(year.value);
    events.value = data.events || [];
  } catch (e) {
    console.error("Failed to fetch events:", e);
    eventsError.value = "Could not load events. Is the backend running?";
  } finally {
    isLoadingEvents.value = false;
  }
};

const fetchSessions = async () => {
  if (!selectedEventKey.value) {
    resetState(1);
    return;
  }
  isLoadingSessions.value = true;
  sessionsError.value = null;
  resetState(1);
  try {
    const data = await getSessions(year.value, selectedEventKey.value);
    sessions.value = data.sessions || [];
  } catch (e) {
    console.error("Failed to fetch sessions:", e);
    sessionsError.value = "Could not load sessions.";
  } finally {
    isLoadingSessions.value = false;
  }
};

const fetchDrivers = async () => {
  if (!selectedSessionName.value) {
    resetState(2);
    return;
  }
  isLoadingDrivers.value = true;
  driversError.value = null;
  resetState(2);
  try {
    const data = await getDrivers(
      year.value,
      selectedEventKey.value,
      selectedSessionName.value,
    );
    drivers.value = data.drivers || [];
  } catch (e) {
    console.error("Failed to fetch drivers:", e);
    driversError.value = "Could not load drivers.";
  } finally {
    isLoadingDrivers.value = false;
  }
};

const fetchRaceComparison = async () => {
  if (!selectedDriver1.value || !selectedDriver2.value) {
    resetState(3);
    return;
  }
  isLoadingComparison.value = true;
  comparisonError.value = null;
  // Reset telemetry only (keep raceComparison until new data arrives if preferred,
  // but following existing pattern of clearing it for now)
  telemetryData.value = null;

  try {
    const data = await getRaceComparison(
      year.value,
      selectedEventKey.value,
      selectedSessionName.value,
      selectedDriver1.value,
      selectedDriver2.value,
    );
    raceComparison.value = data;

    // Find fastest laps to set defaults
    if (data && data.driver1 && data.driver1.laps) {
      const validLaps1 = data.driver1.laps.filter(
        (l) => l.lap_time_seconds !== null,
      );
      if (validLaps1.length > 0) {
        const fastest1 = validLaps1.reduce((prev, curr) =>
          prev.lap_time_seconds < curr.lap_time_seconds ? prev : curr,
        );
        selectedLap1.value = fastest1.lap_number;
      }
    }
    if (data && data.driver2 && data.driver2.laps) {
      const validLaps2 = data.driver2.laps.filter(
        (l) => l.lap_time_seconds !== null,
      );
      if (validLaps2.length > 0) {
        const fastest2 = validLaps2.reduce((prev, curr) =>
          prev.lap_time_seconds < curr.lap_time_seconds ? prev : curr,
        );
        selectedLap2.value = fastest2.lap_number;
      }
    }
  } catch (e) {
    console.error("Failed to fetch race comparison:", e);
    comparisonError.value = "Could not load race comparison data.";
  } finally {
    isLoadingComparison.value = false;
  }
};

const fetchTelemetry = async () => {
  if (
    !selectedDriver1.value ||
    !selectedDriver2.value ||
    !selectedLap1.value ||
    !selectedLap2.value
  ) {
    return;
  }

  isLoadingTelemetry.value = true;
  telemetryError.value = null;

  try {
    const data = await getLapTelemetry(
      year.value,
      selectedEventKey.value,
      selectedSessionName.value,
      selectedDriver1.value,
      selectedDriver2.value,
      selectedLap1.value,
      selectedLap2.value,
    );
    telemetryData.value = data;
  } catch (e) {
    console.error("Failed to fetch telemetry:", e);
    telemetryError.value = "Could not load telemetry data.";
  } finally {
    isLoadingTelemetry.value = false;
  }
};

// --- Watchers and Lifecycle ---
watch(theme, (newTheme) => {
  document.documentElement.setAttribute("data-theme", newTheme);
});
watch(year, fetchEvents);
watch(selectedEventKey, fetchSessions);
watch(selectedSessionName, fetchDrivers);
watch([selectedDriver1, selectedDriver2], fetchRaceComparison);
watch([selectedLap1, selectedLap2], fetchTelemetry);
watch(
  [selectedSessionName, viewMode],
  () => {
    fetchRaceSummary();
  },
  { immediate: true },
);

onMounted(() => {
  const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
  theme.value = mediaQuery.matches ? "dark" : "light";
  mediaQuery.addEventListener("change", (e) => {
    theme.value = e.matches ? "dark" : "light";
  });
  document.documentElement.setAttribute("data-theme", theme.value);
  fetchEvents();
});
</script>

<template>
  <div id="app-container">
    <button class="theme-toggle" @click="toggleTheme" title="Toggle Theme">
      {{ theme === "light" ? "🌙" : "☀️" }}
    </button>
    <h2>F1 PitWall</h2>

    <F1Controls
      :years="years"
      v-model:year="year"
      :events="events"
      v-model:selectedEventKey="selectedEventKey"
      :isLoadingEvents="isLoadingEvents"
      :eventsError="eventsError"
      :sessions="sessions"
      v-model:selectedSessionName="selectedSessionName"
      :isLoadingSessions="isLoadingSessions"
      :sessionsError="sessionsError"
      :drivers="drivers"
      v-model:selectedDriver1="selectedDriver1"
      v-model:selectedDriver2="selectedDriver2"
      :isLoadingDrivers="isLoadingDrivers"
      :driversError="driversError"
      :lapsDriver1="raceComparison?.driver1?.laps || []"
      :lapsDriver2="raceComparison?.driver2?.laps || []"
      v-model:selectedLap1="selectedLap1"
      v-model:selectedLap2="selectedLap2"
      :isLoadingComparison="isLoadingComparison"
      v-model:viewMode="viewMode"
    />

    <template v-if="viewMode === 'comparison'">
      <LapTimeChart
        :raceComparison="raceComparison"
        :isLoading="isLoadingComparison"
        :error="comparisonError"
      />

      <h3 v-if="telemetryData">Telemetry Analysis</h3>
      <TelemetryChart
        :telemetryData="telemetryData"
        :isLoading="isLoadingTelemetry"
        :error="telemetryError"
      />
    </template>

    <template v-else-if="viewMode === 'summary'">
      <QualifyingSummary
        v-if="isQualifyingSession"
        :summaryData="summaryData"
        :isLoading="isLoadingSummary"
        :error="summaryError"
        :theme="theme"
        @select-lap="handleQuickLapSelect"
      />
      <RaceSummary
        v-else
        :summaryData="summaryData"
        :isLoading="isLoadingSummary"
        :error="summaryError"
      />
    </template>
  </div>
</template>

<style>
:root,
html[data-theme="light"] {
  --bg-color: #f8f9fa;
  --card-bg-color: #ffffff;
  --text-color: #0f1115;
  --muted-text-color: #5a636e;
  --primary-color: #e10600; /* Official F1 Red */
  --accent-color: rgba(225, 6, 0, 0.08);
  --border-color: #d1d5db;
  --input-bg-color: #ffffff;
  --item-bg-color: #f3f4f6;
  --shadow-color: rgba(0, 0, 0, 0.06);
}

html[data-theme="dark"] {
  --bg-color: #0b0b0b;
  --card-bg-color: #161616;
  --text-color: #f8f9fa;
  --muted-text-color: #adb5bd;
  --primary-color: #ff1801;
  --accent-color: rgba(255, 24, 1, 0.15);
  --border-color: #2c2c2c;
  --input-bg-color: #1f1f1f;
  --item-bg-color: #1a1a1a;
  --shadow-color: rgba(0, 0, 0, 0.5);
}

* {
  box-sizing: border-box;
}

body {
  font-family:
    "Inter",
    -apple-system,
    BlinkMacSystemFont,
    "Segoe UI",
    Roboto,
    sans-serif;
  background-color: var(--bg-color);
  color: var(--text-color);
  margin: 0;
  padding: 1.5rem;
  line-height: 1.5;
  transition:
    background-color 0.3s ease,
    color 0.3s ease;
}

#app-container {
  width: 100%;
  max-width: 1400px;
  margin: 0 auto;
  background: var(--card-bg-color);
  padding: 2.5rem;
  border-radius: 12px;
  box-shadow: 0 8px 30px var(--shadow-color);
  border: 1px solid var(--border-color);
  position: relative;
  transition:
    background-color 0.3s ease,
    border-color 0.3s ease;
}

.theme-toggle {
  position: absolute;
  top: 1.5rem;
  right: 1.5rem;
  background: var(--item-bg-color);
  border: 1px solid var(--border-color);
  color: var(--text-color);
  cursor: pointer;
  border-radius: 8px;
  width: 44px;
  height: 44px;
  font-size: 1.2rem;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.theme-toggle:hover {
  background-color: var(--accent-color);
  border-color: var(--primary-color);
  transform: scale(1.05);
}

h2 {
  font-weight: 800;
  margin-top: 0;
  color: var(--primary-color);
  text-align: center;
  margin-bottom: 3rem;
  text-transform: uppercase;
  letter-spacing: 2px;
}

h3 {
  font-size: 1.25rem;
  font-weight: 700;
  margin-top: 2.5rem;
  color: var(--text-color);
  border-left: 4px solid var(--primary-color);
  padding-left: 1rem;
  margin-bottom: 1.5rem;
}

.summary-placeholder {
  text-align: center;
  padding: 3rem;
  color: var(--muted-text-color);
}
</style>
