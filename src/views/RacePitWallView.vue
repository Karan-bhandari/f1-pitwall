<script setup>
import { ref, watch, onMounted, shallowRef, computed, nextTick } from "vue";
import { useRoute, RouterLink } from "vue-router";
import F1Controls from "../components/F1Controls.vue";
import F1Icon from "../components/F1Icon.vue";
import TelemetryChart from "../components/TelemetryChart.vue";
import LapTimeChart from "../components/LapTimeChart.vue";
import RaceSummary from "../components/RaceSummary.vue";
import QualifyingSummary from "../components/QualifyingSummary.vue";
import SessionRecap from "../components/SessionRecap.vue";
import {
  getEvents,
  getSessions,
  getDrivers,
  getRaceComparison,
  getLapTelemetry,
  getRaceSummary,
} from "../api.js";

const props = defineProps({
  year: {
    type: Number,
    required: true,
  },
  years: {
    type: Array,
    default: () => [],
  },
  theme: {
    type: String,
    default: "light",
  },
});

const emit = defineEmits(["update:year"]);

const route = useRoute();

// --- Data State ---
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
const viewMode = ref("summary"); // 'summary', 'comparison', or 'recap'
const summaryData = shallowRef(null);
const isLoadingSummary = ref(false);
const summaryError = ref(null);

const isQualifyingSession = computed(() => {
  const name = selectedSessionName.value?.toLowerCase() || "";
  return (
    name.includes("qualifying") ||
    name.includes("shootout") ||
    name.includes("qualy")
  );
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

const handleDriver1Change = (val) => {
  selectedDriver1.value = val;
  selectedLap1.value = null;
};

const handleDriver2Change = (val) => {
  selectedDriver2.value = val;
  selectedLap2.value = null;
};

const handleQuickLapSelect = ({ driverNumber, lapNumber }) => {
  const dNum = String(driverNumber);
  const lNum = Number(lapNumber);
  const driverChanged =
    String(selectedDriver1.value) !== dNum || Boolean(selectedDriver2.value);
  const lapChanged = Number(selectedLap1.value) !== lNum;

  selectedDriver1.value = dNum;
  selectedLap1.value = lNum;
  selectedDriver2.value = "";
  selectedLap2.value = null;
  viewMode.value = "comparison";

  if (!driverChanged && !raceComparison.value) {
    fetchRaceComparison();
  } else if (!driverChanged && !lapChanged && !telemetryData.value) {
    fetchTelemetry();
  }
};

// --- API Fetching ---
const fetchRaceSummary = async () => {
  if (
    !selectedEventKey.value ||
    !selectedSessionName.value ||
    selectedSessionName.value === "Weekend Recap" ||
    viewMode.value !== "summary" ||
    isLoadingSummary.value
  ) {
    return;
  }
  isLoadingSummary.value = true;
  summaryError.value = null;
  try {
    const data = await getRaceSummary(
      props.year,
      selectedEventKey.value,
      selectedSessionName.value,
    );
    summaryData.value = data;
  } catch (e) {
    console.error("Failed to fetch race summary:", e);
    summaryError.value = "Could not load session summary.";
  } finally {
    isLoadingSummary.value = false;
  }
};

const pickDefaultSession = () => {
  if (!sessions.value || sessions.value.length === 0) return "";

  const querySession =
    route.query.session || route.query.session_name || route.params.session;

  if (querySession) {
    const queryStr = String(querySession).trim().toLowerCase();
    const found = sessions.value.find(
      (s) => s.name && s.name.toLowerCase() === queryStr,
    );
    if (found) return found.name;
  }

  // Default to "Weekend Recap"
  const recapSession = sessions.value.find((s) => s.name === "Weekend Recap");
  if (recapSession) {
    return "Weekend Recap";
  }

  // Fallback to "Race" if present
  const raceSession = sessions.value.find((s) => s.name === "Race");
  if (raceSession) {
    return "Race";
  }

  return sessions.value[0]?.name || "";
};

const syncEventFromQuery = () => {
  if (!events.value || events.value.length === 0) return;

  const targetEvent =
    route.query.event !== undefined && route.query.event !== null
      ? String(route.query.event).trim()
      : route.params.event
        ? String(route.params.event).trim()
        : null;

  const targetRound =
    route.query.round !== undefined &&
    route.query.round !== null &&
    route.query.round !== ""
      ? Number(route.query.round)
      : route.params.round !== undefined &&
          route.params.round !== null &&
          route.params.round !== ""
        ? Number(route.params.round)
        : null;

  if (!targetEvent && (targetRound === null || isNaN(targetRound))) {
    return;
  }

  let match = null;

  // 1. Match by event string (event_key or event_name)
  if (targetEvent) {
    match = events.value.find(
      (ev) =>
        String(ev.event_key) === targetEvent ||
        String(ev.event_name) === targetEvent,
    );
    if (!match) {
      const lower = targetEvent.toLowerCase();
      match = events.value.find(
        (ev) =>
          String(ev.event_key).toLowerCase() === lower ||
          String(ev.event_name).toLowerCase() === lower,
      );
    }
  }

  // 2. Fallback to round number match
  if (!match && targetRound !== null && !isNaN(targetRound)) {
    match = events.value.find((ev) => Number(ev.round_number) === targetRound);
  }

  if (match) {
    if (selectedEventKey.value !== match.event_key) {
      selectedEventKey.value = match.event_key;
    } else {
      // Event key is already matched; ensure sessions/session data are loaded
      if (sessions.value.length === 0 && !isLoadingSessions.value) {
        fetchSessions();
      } else {
        syncSessionFromQuery();
      }
    }
  }
};

const syncSessionFromQuery = () => {
  if (!sessions.value || sessions.value.length === 0) return;

  const targetSession = pickDefaultSession();
  if (targetSession && selectedSessionName.value !== targetSession) {
    selectedSessionName.value = targetSession;
    if (targetSession === "Weekend Recap") {
      viewMode.value = "recap";
    } else {
      viewMode.value = "summary";
    }
  } else if (targetSession && selectedSessionName.value === targetSession) {
    if (targetSession === "Weekend Recap") {
      viewMode.value = "recap";
    } else {
      viewMode.value = "summary";
      if (
        !summaryData.value &&
        !isLoadingSummary.value &&
        !inFlightFetchSession
      ) {
        fetchSessionDataSequentially();
      }
    }
  }
};

let eventsReqId = 0;
let sessionsReqId = 0;

const fetchEvents = async () => {
  const reqId = ++eventsReqId;
  isLoadingEvents.value = true;
  eventsError.value = null;
  resetState(0);

  try {
    const data = await getEvents(props.year);
    if (reqId !== eventsReqId) return;
    events.value = data.events || [];
    syncEventFromQuery();
  } catch (e) {
    if (reqId !== eventsReqId) return;
    console.error("Failed to fetch events:", e);
    eventsError.value = "Could not load events. Is the backend running?";
  } finally {
    if (reqId === eventsReqId) {
      isLoadingEvents.value = false;
    }
  }
};

const fetchSessions = async () => {
  const reqId = ++sessionsReqId;
  if (!selectedEventKey.value) {
    resetState(1);
    isLoadingSessions.value = false;
    return;
  }
  isLoadingSessions.value = true;
  sessionsError.value = null;
  resetState(1);
  try {
    const data = await getSessions(props.year, selectedEventKey.value);
    if (reqId !== sessionsReqId) return;
    const sessionList = data.sessions || [];
    // Add Weekend Recap as the default first option
    sessions.value = [{ name: "Weekend Recap" }, ...sessionList];

    // Default to the target session (Race if available, otherwise Weekend Recap)
    const targetSession = pickDefaultSession();
    selectedSessionName.value = targetSession;
    if (targetSession === "Weekend Recap") {
      viewMode.value = "recap";
    } else {
      viewMode.value = "summary";
    }
  } catch (e) {
    if (reqId !== sessionsReqId) return;
    console.error("Failed to fetch sessions:", e);
    sessionsError.value = "Could not load sessions.";
  } finally {
    if (reqId === sessionsReqId) {
      isLoadingSessions.value = false;
    }
  }
};

const fetchDrivers = async () => {
  if (
    !selectedSessionName.value ||
    selectedSessionName.value === "Weekend Recap"
  ) {
    resetState(2);
    return;
  }
  isLoadingDrivers.value = true;
  driversError.value = null;
  resetState(2);
  try {
    const data = await getDrivers(
      props.year,
      selectedEventKey.value,
      selectedSessionName.value,
    );
    drivers.value = data.drivers || [];
    if (
      viewMode.value === "comparison" &&
      drivers.value.length >= 2 &&
      !selectedDriver1.value
    ) {
      applyAutoComparePreset("p1_vs_p2");
    }
  } catch (e) {
    console.error("Failed to fetch drivers:", e);
    driversError.value = "Could not load drivers.";
  } finally {
    isLoadingDrivers.value = false;
  }
};

const applyAutoComparePreset = (mode = "p1_vs_p2") => {
  if (!drivers.value || drivers.value.length < 2) return;

  const prevD1 = selectedDriver1.value;
  const prevD2 = selectedDriver2.value;
  const p1 = drivers.value[0]?.driver_number;
  const p2 = drivers.value[1]?.driver_number;

  if (mode === "p1_vs_p2") {
    selectedDriver1.value = p1;
    selectedDriver2.value = p2;
  } else if (mode === "teammate") {
    const d1Num = selectedDriver1.value || p1;
    selectedDriver1.value = d1Num;
    const d1 = drivers.value.find(
      (d) => String(d.driver_number) === String(d1Num),
    );
    if (d1 && d1.team) {
      const tm = drivers.value.find(
        (d) => d.team === d1.team && String(d.driver_number) !== String(d1Num),
      );
      if (tm) {
        selectedDriver2.value = tm.driver_number;
      } else {
        selectedDriver2.value = String(d1Num) === String(p1) ? p2 : p1;
      }
    } else {
      selectedDriver2.value = String(d1Num) === String(p1) ? p2 : p1;
    }
  } else if (mode === "anchor_p1") {
    if (!selectedDriver2.value && selectedDriver1.value) {
      selectedDriver2.value =
        String(selectedDriver1.value) === String(p1) ? p2 : p1;
    } else {
      selectedDriver1.value = p1;
      if (
        !selectedDriver2.value ||
        String(selectedDriver2.value) === String(p1)
      ) {
        selectedDriver2.value = p2;
      }
    }
  }

  if (String(selectedDriver1.value) !== String(prevD1)) {
    selectedLap1.value = null;
  }
  if (String(selectedDriver2.value) !== String(prevD2)) {
    selectedLap2.value = null;
  }
};

let inFlightFetchSession = false;
const fetchSessionDataSequentially = async () => {
  if (inFlightFetchSession) return;
  if (!selectedEventKey.value || !selectedSessionName.value) return;
  if (selectedSessionName.value === "Weekend Recap") {
    return;
  }
  inFlightFetchSession = true;
  try {
    // Prevent fastf1 SQLite cache lock by fetching drivers then summary
    await fetchDrivers();
    if (viewMode.value === "summary") {
      await fetchRaceSummary();
    }
  } finally {
    inFlightFetchSession = false;
  }
};

let comparisonReqId = 0;
let telemetryReqId = 0;

const fetchRaceComparison = async () => {
  if (!selectedDriver1.value) {
    resetState(3);
    return;
  }
  const reqId = ++comparisonReqId;
  isLoadingComparison.value = true;
  comparisonError.value = null;
  telemetryData.value = null;

  try {
    const data = await getRaceComparison(
      props.year,
      selectedEventKey.value,
      selectedSessionName.value,
      selectedDriver1.value,
      selectedDriver2.value,
    );
    if (reqId !== comparisonReqId) return;
    raceComparison.value = data;

    // Resolve Lap 1 (keep existing valid selection or fall back to fastest/first)
    const allLaps1 = data?.driver1?.laps || [];
    const hasExistingLap1 =
      selectedLap1.value != null &&
      allLaps1.some((l) => Number(l.lap_number) === Number(selectedLap1.value));
    if (!hasExistingLap1) {
      const validLaps1 = allLaps1.filter((l) => l.lap_time_seconds !== null);
      if (validLaps1.length > 0) {
        const fastest1 = validLaps1.reduce((prev, curr) =>
          prev.lap_time_seconds < curr.lap_time_seconds ? prev : curr,
        );
        selectedLap1.value = fastest1.lap_number;
      } else {
        selectedLap1.value = allLaps1[0]?.lap_number ?? null;
      }
    }

    // Resolve Lap 2 (clear in single-driver mode, otherwise pick distinct lap when same driver)
    if (!selectedDriver2.value || !data?.driver2?.laps?.length) {
      selectedLap2.value = null;
    } else {
      const allLaps2 = data.driver2.laps;
      const hasExistingLap2 =
        selectedLap2.value != null &&
        allLaps2.some(
          (l) => Number(l.lap_number) === Number(selectedLap2.value),
        );
      if (!hasExistingLap2) {
        const sortedValid2 = allLaps2
          .filter((l) => l.lap_time_seconds !== null)
          .sort((a, b) => a.lap_time_seconds - b.lap_time_seconds);
        if (
          String(selectedDriver1.value) === String(selectedDriver2.value) &&
          sortedValid2.length > 1 &&
          Number(sortedValid2[0].lap_number) === Number(selectedLap1.value)
        ) {
          selectedLap2.value = sortedValid2[1].lap_number;
        } else {
          selectedLap2.value =
            sortedValid2[0]?.lap_number ?? allLaps2[0]?.lap_number ?? null;
        }
      }
    }

    await nextTick();
    if (reqId !== comparisonReqId) return;
    isLoadingComparison.value = false;
    await fetchTelemetry();
  } catch (e) {
    if (reqId !== comparisonReqId) return;
    console.error("Failed to fetch race comparison:", e);
    comparisonError.value = "Could not load race comparison data.";
  } finally {
    if (reqId === comparisonReqId) {
      isLoadingComparison.value = false;
    }
  }
};

const fetchTelemetry = async () => {
  if (isLoadingComparison.value) return;
  if (!selectedDriver1.value || !selectedLap1.value) return;
  if (selectedDriver2.value && !selectedLap2.value) return;

  const reqId = ++telemetryReqId;
  isLoadingTelemetry.value = true;
  telemetryError.value = null;

  try {
    const data = await getLapTelemetry(
      props.year,
      selectedEventKey.value,
      selectedSessionName.value,
      selectedDriver1.value,
      selectedDriver2.value || "",
      selectedLap1.value,
      selectedDriver2.value ? selectedLap2.value : null,
    );
    if (reqId !== telemetryReqId) return;
    telemetryData.value = data;
  } catch (e) {
    if (reqId !== telemetryReqId) return;
    console.error("Failed to fetch telemetry:", e);
    telemetryError.value = "Could not load telemetry data.";
  } finally {
    if (reqId === telemetryReqId) {
      isLoadingTelemetry.value = false;
    }
  }
};

// --- Watchers and Lifecycle ---
watch(
  () => props.year,
  () => {
    fetchEvents();
  },
);

watch(
  () => route.query.year,
  (newYear) => {
    if (newYear) {
      const parsed = Number(newYear);
      if (
        !isNaN(parsed) &&
        parsed !== props.year &&
        (!props.years.length || props.years.includes(parsed))
      ) {
        emit("update:year", parsed);
      }
    }
  },
  { immediate: true },
);

watch(
  () => [
    route.query.event,
    route.query.round,
    route.query.session,
    route.query.session_name,
    route.params.event,
    route.params.round,
    route.params.session,
  ],
  () => {
    if (events.value.length > 0) {
      syncEventFromQuery();
    }
  },
);

watch(selectedEventKey, fetchSessions);

watch(selectedSessionName, (newName) => {
  if (!newName) return;
  if (newName === "Weekend Recap") {
    viewMode.value = "recap";
  } else if (viewMode.value === "recap") {
    viewMode.value = "summary";
  }
  fetchSessionDataSequentially();
});

watch(viewMode, (newMode) => {
  if (
    newMode === "summary" &&
    selectedSessionName.value &&
    selectedSessionName.value !== "Weekend Recap"
  ) {
    // Only fetch if we don't already have it and no fetch sequence is in progress
    if (
      !summaryData.value &&
      !isLoadingSummary.value &&
      !inFlightFetchSession
    ) {
      fetchRaceSummary();
    }
  } else if (newMode === "comparison") {
    if (drivers.value.length >= 2 && !selectedDriver1.value) {
      applyAutoComparePreset("p1_vs_p2");
    }
  }
});

watch([selectedDriver1, selectedDriver2], fetchRaceComparison);
watch([selectedLap1, selectedLap2], fetchTelemetry);

onMounted(() => {
  if (route.query.year) {
    const parsed = Number(route.query.year);
    if (
      !isNaN(parsed) &&
      parsed !== props.year &&
      (!props.years.length || props.years.includes(parsed))
    ) {
      emit("update:year", parsed);
      return;
    }
  }
  fetchEvents();
});
</script>

<template>
  <div class="race-pitwall-view">
    <F1Controls
      :hideYearSelect="true"
      :years="years"
      :year="year"
      @update:year="$emit('update:year', $event)"
      :events="events"
      v-model:selectedEventKey="selectedEventKey"
      :isLoadingEvents="isLoadingEvents"
      :eventsError="eventsError"
      :sessions="sessions"
      v-model:selectedSessionName="selectedSessionName"
      :isLoadingSessions="isLoadingSessions"
      :sessionsError="sessionsError"
      :drivers="drivers"
      :selectedDriver1="selectedDriver1"
      @update:selectedDriver1="handleDriver1Change"
      :selectedDriver2="selectedDriver2"
      @update:selectedDriver2="handleDriver2Change"
      :isLoadingDrivers="isLoadingDrivers"
      :driversError="driversError"
      :lapsDriver1="raceComparison?.driver1?.laps || []"
      :lapsDriver2="raceComparison?.driver2?.laps || []"
      v-model:selectedLap1="selectedLap1"
      v-model:selectedLap2="selectedLap2"
      :isLoadingComparison="isLoadingComparison"
      v-model:viewMode="viewMode"
      @select-preset="applyAutoComparePreset"
    />

    <!-- Empty state card when no event is selected -->
    <div v-if="!selectedEventKey" class="empty-event-card">
      <div class="empty-icon"><F1Icon name="checkered-flag" :size="40" /></div>
      <h3>Select a Grand Prix Event</h3>
      <p class="empty-desc">
        Choose a race from the {{ year }} season calendar above to inspect
        Weekend Recap, Race &amp; Qualifying Summaries, tyre stint strategies,
        and side-by-side lap telemetry comparisons.
      </p>
      <div class="empty-actions">
        <RouterLink to="/" class="secondary-link">
          ← Return to Season Hub
        </RouterLink>
      </div>
    </div>

    <!-- Event-specific views: shown once an event is selected -->
    <template v-else-if="viewMode === 'recap'">
      <SessionRecap :year="Number(year)" :eventKey="selectedEventKey" />
    </template>

    <template v-else-if="viewMode === 'comparison'">
      <LapTimeChart
        :raceComparison="raceComparison"
        :isLoading="isLoadingComparison"
        :error="comparisonError"
        :theme="theme"
      />

      <h3 v-if="telemetryData" class="section-title">Telemetry Analysis</h3>
      <TelemetryChart
        :telemetryData="telemetryData"
        :isLoading="isLoadingTelemetry"
        :error="telemetryError"
        :year="Number(year)"
        :theme="theme"
      />
    </template>

    <template v-else-if="viewMode === 'summary'">
      <div v-if="isLoadingSummary" class="loading-state">
        <div class="spinner" aria-hidden="true"></div>
        <p>Loading session performance data...</p>
      </div>
      <div v-else-if="summaryError" class="error-state" role="alert">
        <p>{{ summaryError }}</p>
        <button type="button" class="retry-btn" @click="fetchRaceSummary">
          Retry
        </button>
      </div>
      <QualifyingSummary
        v-else-if="isQualifyingSession && summaryData"
        :summaryData="summaryData"
        :isLoading="isLoadingSummary"
        :error="summaryError"
        :theme="theme"
        :year="Number(year)"
        @select-lap="handleQuickLapSelect"
      />
      <RaceSummary
        v-else-if="summaryData"
        :summaryData="summaryData"
        :isLoading="isLoadingSummary"
        :error="summaryError"
        :year="Number(year)"
        :sessionName="selectedSessionName"
      />
    </template>
  </div>
</template>

<style scoped>
.race-pitwall-view {
  width: 100%;
}

.loading-state,
.error-state {
  text-align: center;
  padding: 3.5rem 1.5rem;
  color: var(--muted-text-color);
  font-size: 0.95rem;
  background: var(--card-bg-color);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  margin-top: 1.5rem;
}

.loading-state p,
.error-state p {
  margin: 0;
}

.spinner {
  width: 34px;
  height: 34px;
  border: 3px solid var(--border-color);
  border-top-color: var(--primary-color);
  border-radius: 50%;
  animation: spin 0.9s linear infinite;
  margin: 0 auto 1rem;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.error-state {
  color: var(--primary-color);
  background: var(--accent-color);
  border-color: rgba(225, 6, 0, 0.25);
  font-weight: 600;
}

.retry-btn {
  margin-top: 1rem;
  padding: 0.5rem 1.15rem;
  border-radius: 6px;
  border: 1px solid var(--primary-color);
  background: var(--primary-color);
  color: #fff;
  font-weight: 700;
  font-size: 0.85rem;
  cursor: pointer;
  transition:
    opacity 0.2s ease,
    transform 0.2s ease;
}

.retry-btn:hover {
  opacity: 0.9;
  transform: translateY(-1px);
}

.retry-btn:focus-visible {
  outline: 2px solid var(--primary-color);
  outline-offset: 2px;
}

.empty-event-card {
  margin: 2.5rem auto 1rem;
  max-width: 620px;
  background: var(--item-bg-color);
  border: 1px dashed var(--border-color);
  border-radius: 12px;
  padding: 3rem 2rem;
  text-align: center;
}

.empty-icon {
  font-size: 2.75rem;
  margin-bottom: 1rem;
  color: var(--primary-color);
}

.empty-event-card h3 {
  font-size: 1.35rem;
  font-weight: 700;
  margin-top: 0;
  margin-bottom: 0.75rem;
  color: var(--text-color);
  text-wrap: balance;
}

.empty-desc {
  color: var(--muted-text-color);
  font-size: 0.975rem;
  line-height: 1.6;
  margin: 0 auto 1.75rem;
  max-width: 480px;
}

.empty-actions {
  display: flex;
  justify-content: center;
}

.secondary-link {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--primary-color);
  font-weight: 600;
  font-size: 0.95rem;
  text-decoration: none;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  background: var(--card-bg-color);
  border: 1px solid var(--border-color);
  transition:
    border-color 0.2s ease,
    background-color 0.2s ease;
}

.secondary-link:hover {
  border-color: var(--primary-color);
  background: var(--accent-color);
}

.secondary-link:focus-visible {
  outline: 2px solid var(--primary-color);
  outline-offset: 2px;
}

.section-title {
  font-size: 1.25rem;
  font-weight: 700;
  margin-top: 2.5rem;
  margin-bottom: 1.25rem;
  padding-bottom: 0.6rem;
  color: var(--text-color);
  border-bottom: 1px solid var(--border-color);
}

@media (max-width: 768px) {
  .empty-event-card {
    padding: 2rem 1.25rem;
    margin-top: 1.5rem;
  }
}
</style>
