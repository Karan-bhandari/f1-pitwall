<script setup>
import { computed } from "vue";
import { getTyreColor, getTyreIcon } from "../utils";
import F1Icon from "./F1Icon.vue";

const props = defineProps({
  summaryData: {
    type: Object,
    required: true,
  },
  isLoading: {
    type: Boolean,
    default: false,
  },
  error: {
    type: String,
    default: null,
  },
  year: {
    type: Number,
    required: false,
    default: 2024,
  },
  sessionName: {
    type: String,
    default: "",
  },
});

const isPracticeSession = computed(() => {
  const n = (props.sessionName || "").toLowerCase();
  return n.includes("practice") || /\bfp[123]\b/.test(n);
});

const getDriverBestLap = (driver) => {
  let best = null;
  let bestAny = null;
  for (const stint of driver?.stints || []) {
    for (const lap of stint?.laps || []) {
      const secs = lap?.lap_time_seconds;
      if (typeof secs === "number" && Number.isFinite(secs) && secs > 0) {
        if (!bestAny || secs < bestAny.seconds) {
          bestAny = { seconds: secs, formatted: lap.lap_time };
        }
        if (!lap.deleted && (!best || secs < best.seconds)) {
          best = { seconds: secs, formatted: lap.lap_time };
        }
      }
    }
  }
  return best || bestAny;
};

const getDriverLapCount = (driver) => {
  if (
    typeof driver?.completed_laps === "number" &&
    driver.completed_laps >= 0
  ) {
    return driver.completed_laps;
  }
  return (driver?.stints || []).reduce((sum, s) => sum + (s.lap_count || 0), 0);
};

const fastestPracticeSeconds = computed(() => {
  if (!isPracticeSession.value || !props.summaryData?.results) return null;
  let minSec = null;
  for (const d of props.summaryData.results) {
    const b = getDriverBestLap(d);
    if (b && (minSec === null || b.seconds < minSec)) {
      minSec = b.seconds;
    }
  }
  return minSec;
});

const getPracticeBestTime = (driver) => {
  const b = getDriverBestLap(driver);
  return b?.formatted || "No Time";
};

const getPracticeGap = (driver) => {
  const b = getDriverBestLap(driver);
  const leader = fastestPracticeSeconds.value;
  if (!b || leader === null) return "—";
  const diff = b.seconds - leader;
  if (diff <= 0.0005) return "—";
  return `+${diff.toFixed(3)}s`;
};

const sortedResults = computed(() => {
  if (!props.summaryData?.results) return [];
  const list = [...props.summaryData.results];
  if (isPracticeSession.value) {
    return list.sort((a, b) => {
      const ba = getDriverBestLap(a)?.seconds ?? Number.POSITIVE_INFINITY;
      const bb = getDriverBestLap(b)?.seconds ?? Number.POSITIVE_INFINITY;
      if (ba !== bb) return ba - bb;
      return getDriverLapCount(b) - getDriverLapCount(a);
    });
  }
  return list.sort((a, b) => (a.position || 99) - (b.position || 99));
});

const hasStintData = computed(
  () => props.year >= 2018 && (props.summaryData?.total_laps || 0) > 0,
);

const isRetired = (driver) =>
  Boolean(driver && ["dnf", "dns", "dsq"].includes(driver.status_category));

const getStatusColor = (type) => {
  if (type === "SC") return "#ffff00"; // Safety Car Yellow
  if (type === "VSC") return "#faff72"; // Lighter Lemon Yellow for VSC
  if (type === "Red Flag") return "#e10600"; // Official F1 Red
  return "#777777";
};

const getStatusLabel = (event) => {
  if (event.start_lap === event.end_lap)
    return `${event.type} (Lap ${event.start_lap})`;
  return `${event.type} (Laps ${event.start_lap}-${event.end_lap})`;
};

/**
 * Unified calculation for positioning elements on the race timeline.
 */
const calculatePosition = (startLap, lapCount = 1) => {
  const total = props.summaryData.total_laps || 1;
  return {
    left: ((startLap - 1) / total) * 100 + "%",
    width: (lapCount / total) * 100 + "%",
  };
};
</script>

<template>
  <div class="race-summary-container">
    <div v-if="isLoading" class="loading-state">
      <p>Loading race performance data...</p>
    </div>

    <div v-else-if="error" class="error-state">
      <p>{{ error }}</p>
    </div>

    <div v-else-if="summaryData" class="summary-content">
      <div v-if="sortedResults.length === 0" class="no-data">
        <p>No performance data available for this session.</p>
      </div>
      <template v-else>
        <div v-if="year < 2018" class="historical-note">
          <p>
            Note: Detailed lap and strategy data is not available for this era.
          </p>
        </div>
        <div v-else-if="!hasStintData" class="historical-note">
          <p>
            Note: Detailed lap and tyre strategy data is not yet available for
            this session.
          </p>
        </div>

        <!-- Track Status Header Row -->
        <div
          v-if="summaryData.track_status_events?.length && hasStintData"
          class="track-status-row"
        >
          <div class="col-pos"></div>
          <div class="col-driver">TRACK STATUS</div>
          <div class="col-status"></div>
          <div class="col-stints">
            <div class="status-timeline-container">
              <div
                v-for="(event, index) in summaryData.track_status_events"
                :key="index"
                class="status-segment"
                :class="{ 'red-flag': event.type === 'Red Flag' }"
                :style="{
                  ...calculatePosition(
                    event.start_lap,
                    event.end_lap - event.start_lap + 1,
                  ),
                  backgroundColor: getStatusColor(event.type),
                }"
                :title="getStatusLabel(event)"
              >
                <span v-if="event.type !== 'Red Flag'" class="status-text">{{
                  event.type
                }}</span>
              </div>
            </div>
          </div>
        </div>

        <div class="summary-header">
          <div class="col-pos">POS</div>
          <div class="col-driver">DRIVER</div>
          <div
            class="col-status header-status"
            :title="
              isPracticeSession
                ? 'Practice Best Lap / Gap / Laps'
                : 'Race Status / Info'
            "
          >
            <span class="sr-only">{{
              isPracticeSession
                ? "PRACTICE TIMING / LAPS"
                : "RACE STATUS / INFO"
            }}</span>
            <div
              class="status-header-grid"
              :class="{
                'no-stints': !hasStintData && !isPracticeSession,
                'practice-grid': isPracticeSession,
              }"
            >
              <template v-if="isPracticeSession">
                <span class="header-col header-col-time">BEST LAP</span>
                <span class="header-col header-col-stops">GAP</span>
                <span class="header-col header-col-pts">LAPS</span>
              </template>
              <template v-else>
                <span class="header-col header-col-time">STATUS / GAP</span>
                <span v-if="hasStintData" class="header-col header-col-stops"
                  >STOPS</span
                >
                <span class="header-col header-col-pts">PTS</span>
              </template>
            </div>
          </div>
          <div class="col-stints" v-if="hasStintData">
            {{
              isPracticeSession
                ? "TYRE RUNS (LAPS PER STINT)"
                : "TYRE STRATEGY (LAPS PER STINT)"
            }}
          </div>
        </div>

        <div
          v-for="(driver, index) in sortedResults"
          :key="driver.driver_number"
          class="driver-row"
        >
          <div class="col-pos">
            <span class="pos-num">{{
              isPracticeSession ? index + 1 : driver.position
            }}</span>
            <span
              v-if="
                !isPracticeSession &&
                driver.positions_gained !== null &&
                driver.positions_gained !== undefined
              "
              class="pos-delta"
              :class="{
                gain: driver.positions_gained > 0,
                loss: driver.positions_gained < 0,
                even: driver.positions_gained === 0,
              }"
              :title="
                driver.grid_position ? `Started P${driver.grid_position}` : ''
              "
            >
              {{
                driver.positions_gained > 0
                  ? `▲${driver.positions_gained}`
                  : driver.positions_gained < 0
                    ? `▼${Math.abs(driver.positions_gained)}`
                    : "="
              }}
            </span>
          </div>

          <div class="col-driver">
            <div
              class="team-stripe"
              :style="{ backgroundColor: '#' + driver.team_color }"
            ></div>
            <div class="driver-info">
              <div class="driver-name-row">
                <span class="driver-name">{{ driver.full_name }}</span>
                <span
                  v-if="driver.has_fastest_lap"
                  class="fl-pill"
                  :title="
                    isPracticeSession
                      ? 'Fastest Lap of the Session'
                      : 'Fastest Lap of the Race'
                  "
                >
                  <F1Icon name="stopwatch" :size="12" /> FL
                </span>
              </div>
              <span class="team-name">{{ driver.team_name }}</span>
            </div>
          </div>

          <div class="col-status status-cell">
            <div
              class="status-metrics-row"
              :class="{
                'no-stints': !hasStintData && !isPracticeSession,
                'practice-grid': isPracticeSession,
              }"
            >
              <template v-if="isPracticeSession">
                <div class="status-col status-col-time">
                  <span
                    class="finish-time"
                    :class="{
                      'metric-empty': getPracticeBestTime(driver) === 'No Time',
                    }"
                  >
                    {{ getPracticeBestTime(driver) }}
                  </span>
                </div>
                <div class="status-col status-col-stops">
                  <span
                    class="practice-gap"
                    :class="{
                      'metric-empty': getPracticeGap(driver) === '—',
                    }"
                  >
                    {{ getPracticeGap(driver) }}
                  </span>
                </div>
                <div class="status-col status-col-pts">
                  <span class="stop-badge">
                    {{ getDriverLapCount(driver) }}
                  </span>
                </div>
              </template>
              <template v-else>
                <!-- Primary Timing / Gap / Status Badge -->
                <div class="status-col status-col-time">
                  <span
                    v-if="isRetired(driver)"
                    class="status-badge"
                    :class="'status-' + driver.status_category"
                  >
                    {{ driver.status_badge }}
                  </span>
                  <span v-else class="finish-time">
                    {{ driver.finish_time || driver.status || "Finished" }}
                  </span>
                </div>

                <!-- Pit Stops Slot (shown when session has stint/lap data) -->
                <div v-if="hasStintData" class="status-col status-col-stops">
                  <span
                    v-if="
                      driver.pit_stops !== undefined && driver.pit_stops > 0
                    "
                    class="stop-badge"
                  >
                    {{ driver.pit_stops }}
                    {{ driver.pit_stops === 1 ? "Stop" : "Stops" }}
                  </span>
                  <span
                    v-else-if="driver.pit_stops === 0 && !isRetired(driver)"
                    class="stop-badge"
                  >
                    0 Stops
                  </span>
                  <span v-else class="metric-empty" aria-hidden="true">—</span>
                </div>

                <!-- Points Slot -->
                <div class="status-col status-col-pts">
                  <span v-if="driver.points > 0" class="pts-pill">
                    +{{ driver.points }}
                  </span>
                  <span v-else class="pts-zero metric-empty" aria-hidden="true"
                    >—</span
                  >
                </div>
              </template>
            </div>

            <!-- Retired Status Detail (e.g., Collision, Engine - Lap 42) -->
            <div
              v-if="
                !isPracticeSession && isRetired(driver) && driver.status_detail
              "
              class="status-detail-row"
            >
              <span class="status-detail-text" :title="driver.status_detail">
                {{ driver.status_detail }}
              </span>
            </div>

            <!-- Steward Penalties & Track Limit Warnings (Dedicated vertical stack) -->
            <div
              v-if="driver.penalties && driver.penalties.length > 0"
              class="steward-pills-stack"
            >
              <span
                v-for="(p, pIdx) in driver.penalties"
                :key="pIdx"
                class="steward-pill"
                :class="p.badge === 'B&W Flag' ? 'is-bw-flag' : 'is-penalty'"
                :title="
                  p.reason ? `${p.badge} — ${p.reason}` : p.message || p.badge
                "
              >
                <F1Icon
                  :name="p.badge === 'B&W Flag' ? 'bw-flag' : 'alert'"
                  :size="13"
                />
                <span class="steward-pill-badge">
                  {{
                    p.badge === "B&W Flag"
                      ? "Black & White Flag"
                      : `${p.badge} Penalty`
                  }}
                </span>
              </span>
            </div>
          </div>

          <div class="col-stints" v-if="hasStintData">
            <div class="stint-timeline">
              <div
                v-for="(stint, index) in driver.stints"
                :key="index"
                class="stint-segment"
                :style="{
                  ...calculatePosition(stint.start_lap, stint.lap_count),
                  backgroundColor: getTyreColor(stint.compound),
                }"
              >
                <div class="stint-info" v-if="stint.lap_count > 2">
                  <img
                    :src="getTyreIcon(stint.compound)"
                    :alt="stint.compound"
                    class="tyre-icon"
                  />
                  <span class="lap-count">{{ stint.lap_count }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.race-summary-container {
  margin-top: 2rem;
  background: var(--card-bg-color);
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid var(--border-color);
}

.summary-content {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.summary-content::-webkit-scrollbar {
  height: 8px;
}

.summary-content::-webkit-scrollbar-track {
  background: var(--bg-color);
}

.summary-content::-webkit-scrollbar-thumb {
  background: var(--border-color);
  border-radius: 4px;
}

.summary-header {
  display: flex;
  background: var(--item-bg-color);
  padding: 1rem 1.5rem;
  font-weight: 800;
  font-size: 0.75rem;
  color: var(--muted-text-color);
  border-bottom: 1px solid var(--border-color);
  text-transform: uppercase;
  letter-spacing: 1px;
  min-width: 950px;
}

.track-status-row {
  display: flex;
  align-items: center;
  padding: 0.5rem 1.5rem;
  background: var(--card-bg-color);
  border-bottom: 1px solid var(--border-color);
  min-width: 950px;
}

.track-status-row .col-driver {
  font-size: 0.7rem;
  font-weight: 800;
  color: var(--muted-text-color);
  letter-spacing: 1px;
}

.status-timeline-container {
  position: relative;
  height: 18px;
  width: 100%;
  background: var(--bg-color); /* Match stint background */
  border-radius: 4px;
  overflow: hidden;
  border: 1px solid var(--border-color);
}

.status-segment {
  position: absolute;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: help;
  transition: all 0.2s;
}

.status-segment.red-flag .status-text {
  color: #fff;
}

.status-text {
  font-size: 0.65rem;
  font-weight: 900;
  color: #000;
  pointer-events: none;
  white-space: nowrap;
}

/* Ensure the stint timeline container precisely matches the header width */
.col-stints {
  flex: 1;
  padding-left: 1.5rem;
  position: relative;
}

.driver-row {
  display: flex;
  align-items: center;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid var(--border-color);
  transition: all 0.2s ease;
  position: relative;
  background: transparent;
  z-index: 1;
  min-width: 950px;
}

.driver-row:last-child {
  border-bottom: none;
}

.driver-row:hover {
  background-color: var(--accent-color);
}

.col-pos {
  width: 75px;
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: "JetBrains Mono", monospace;
  font-variant-numeric: tabular-nums;
}

.pos-num {
  min-width: 24px;
  text-align: right;
  font-weight: 800;
  font-size: 1.15rem;
  color: var(--text-color);
}

.col-driver {
  width: 250px;
  display: flex;
  align-items: center;
  gap: 0.85rem;
}

.driver-name-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.col-status {
  width: 270px;
  padding: 0 0.75rem;
  display: flex;
  flex-direction: column;
  justify-content: center;
  box-sizing: border-box;
}

.header-status {
  justify-content: center;
}

.status-header-grid,
.status-metrics-row {
  display: grid;
  grid-template-columns: 118px 64px 54px;
  gap: 5px;
  align-items: center;
  width: 100%;
}

.status-header-grid.no-stints,
.status-metrics-row.no-stints {
  grid-template-columns: 1fr 54px;
}

.status-header-grid.practice-grid,
.status-metrics-row.practice-grid {
  grid-template-columns: 96px 84px 54px;
}

.practice-gap {
  font-family: "JetBrains Mono", monospace;
  font-variant-numeric: tabular-nums;
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--muted-text-color);
  white-space: nowrap;
}

.header-col {
  font-weight: 800;
  font-size: 0.72rem;
  color: var(--muted-text-color);
  letter-spacing: 0.8px;
  text-transform: uppercase;
}

.header-col-time {
  text-align: left;
}

.header-col-stops {
  text-align: center;
}

.header-col-pts {
  text-align: right;
}

.status-col {
  min-width: 0;
}

.status-col-time {
  display: flex;
  align-items: center;
  gap: 5px;
  justify-content: flex-start;
  min-width: 0;
}

.status-col-stops {
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 0;
}

.status-col-pts {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  min-width: 0;
}

.finish-time {
  font-family: "JetBrains Mono", monospace;
  font-size: 0.82rem;
  font-weight: 700;
  color: var(--text-color);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  letter-spacing: -0.2px;
}

.stop-badge {
  font-family: "JetBrains Mono", monospace;
  font-variant-numeric: tabular-nums;
  font-size: 0.66rem;
  font-weight: 600;
  padding: 2px 5px;
  border-radius: 3px;
  background: var(--item-bg-color);
  border: 1px solid var(--border-color);
  color: var(--muted-text-color);
  white-space: nowrap;
  line-height: 1.2;
}

.metric-empty {
  font-family: "JetBrains Mono", monospace;
  font-variant-numeric: tabular-nums;
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--muted-text-color);
  opacity: 0.65;
  user-select: none;
}

.status-detail-row {
  margin-top: 3px;
  display: flex;
  align-items: center;
}

.status-detail-text {
  font-size: 0.72rem;
  color: var(--muted-text-color);
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

.race-summary-container .steward-pills-stack {
  margin-top: 4px;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border-width: 0;
}

.team-stripe {
  width: 4px;
  height: 36px;
  border-radius: 4px;
}

.driver-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.driver-name {
  font-weight: 700;
  font-size: 1rem;
  color: var(--text-color);
  white-space: nowrap;
}

.team-name {
  font-size: 0.7rem;
  color: var(--muted-text-color);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-weight: 600;
  white-space: nowrap;
}

.stint-timeline {
  position: relative; /* CRITICAL: Must be relative for absolute segments */
  height: 34px;
  border-radius: 6px;
  overflow: hidden;
  background: var(--bg-color);
  border: 1px solid var(--border-color);
  width: 100%;
  box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.05);
}

.stint-segment {
  position: absolute; /* CRITICAL: absolute for overlap accuracy */
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  border-right: 1px solid rgba(0, 0, 0, 0.1);
  flex-shrink: 0;
  transition: transform 0.2s ease;
  background-image: linear-gradient(
    180deg,
    rgba(255, 255, 255, 0.15) 0%,
    rgba(0, 0, 0, 0.05) 100%
  );
}

.stint-segment:hover {
  transform: scaleY(1.1);
  z-index: 10;
  box-shadow: 0 0 10px rgba(0, 0, 0, 0.2);
}

.stint-info {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 8px;
}

.tyre-icon {
  width: 18px;
  height: 18px;
  object-fit: contain;
  flex-shrink: 0;
  filter: drop-shadow(0 1px 2px rgba(0, 0, 0, 0.3));
}

.lap-count {
  font-family: "JetBrains Mono", monospace;
  font-variant-numeric: tabular-nums;
  font-size: 0.85rem;
  font-weight: 800;
  letter-spacing: -0.5px;
  color: #000; /* Default to black for better contrast on bright F1 tyre colors */
  text-shadow: 0 0 1px rgba(255, 255, 255, 0.2);
}

/* Ensure white text for darker compounds like WET or unknown */
.stint-segment[style*="#0000ff"] .lap-count,
.stint-segment[style*="#777777"] .lap-count {
  color: #fff;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.5);
}

.loading-state,
.error-state,
.no-data {
  padding: 4rem;
  text-align: center;
  color: var(--muted-text-color);
  font-weight: 500;
}

.error-state p {
  color: var(--primary-color);
  font-weight: bold;
}

/* --- Mobile Responsiveness --- */
@media (max-width: 768px) {
  .col-pos {
    width: 65px;
  }
  .pos-num {
    font-size: 1rem;
  }
  .col-driver {
    width: 210px;
    gap: 0.5rem;
  }
  .driver-name {
    font-size: 0.9rem;
  }
  .team-name {
    font-size: 0.65rem;
  }
  .col-status {
    width: 250px;
    padding: 0 0.5rem;
  }
  .status-header-grid,
  .status-metrics-row {
    grid-template-columns: 106px 62px 48px;
    gap: 4px;
  }
  .status-header-grid.no-stints,
  .status-metrics-row.no-stints {
    grid-template-columns: 1fr 48px;
  }
  .finish-time {
    font-size: 0.76rem;
  }
  .stop-badge {
    font-size: 0.62rem;
    padding: 1px 4px;
  }
  .pts-pill {
    font-size: 0.62rem;
    padding: 1px 4px;
  }
  .header-col {
    font-size: 0.68rem;
  }
}
</style>
