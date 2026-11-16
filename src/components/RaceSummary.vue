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
});

const sortedResults = computed(() => {
  if (!props.summaryData?.results) return [];
  return [...props.summaryData.results].sort(
    (a, b) => (a.position || 99) - (b.position || 99),
  );
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
          <div class="col-status header-status" title="Race Status / Info">
            <span class="sr-only">RACE STATUS / INFO</span>
            <div
              class="status-header-grid"
              :class="{ 'no-stints': !hasStintData }"
            >
              <span class="header-col header-col-time">STATUS / GAP</span>
              <span v-if="hasStintData" class="header-col header-col-stops"
                >STOPS</span
              >
              <span class="header-col header-col-pts">PTS</span>
            </div>
          </div>
          <div class="col-stints" v-if="hasStintData">
            TYRE STRATEGY (LAPS PER STINT)
          </div>
        </div>

        <div
          v-for="driver in sortedResults"
          :key="driver.driver_number"
          class="driver-row"
        >
          <div class="col-pos">
            <span class="pos-num">{{ driver.position }}</span>
            <span
              v-if="
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
                  class="fl-pill fl-badge"
                  title="Fastest Lap of the Race"
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
              :class="{ 'no-stints': !hasStintData }"
            >
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
                  v-if="driver.pit_stops !== undefined && driver.pit_stops > 0"
                  class="stop-badge stops-badge"
                >
                  {{ driver.pit_stops }}
                  {{ driver.pit_stops === 1 ? "Stop" : "Stops" }}
                </span>
                <span
                  v-else-if="driver.pit_stops === 0 && !isRetired(driver)"
                  class="stop-badge stops-badge"
                >
                  0 Stops
                </span>
                <span v-else class="metric-empty" aria-hidden="true">—</span>
              </div>

              <!-- Points Slot -->
              <div class="status-col status-col-pts">
                <span v-if="driver.points > 0" class="pts-pill points-badge">
                  +{{ driver.points }}
                </span>
                <span v-else class="pts-zero metric-empty" aria-hidden="true"
                  >—</span
                >
              </div>
            </div>

            <!-- Retired Status Detail (e.g., Collision, Engine - Lap 42) -->
            <div
              v-if="isRetired(driver) && driver.status_detail"
              class="status-detail-row"
            >
              <span class="status-detail-text" :title="driver.status_detail">
                {{ driver.status_detail }}
              </span>
            </div>

            <!-- Steward Penalties & Track Limit Warnings (Dedicated vertical stack) -->
            <div
              v-if="driver.penalties && driver.penalties.length > 0"
              class="steward-pills-stack steward-pills-row"
            >
              <span
                v-for="(p, pIdx) in driver.penalties"
                :key="pIdx"
                class="steward-pill penalty-chip"
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

.historical-note {
  padding: 1rem 1.5rem;
  background: var(--accent-color);
  color: var(--primary-color);
  font-weight: 600;
  border-bottom: 1px solid var(--border-color);
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

.rows-container {
  position: relative;
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

.pos-delta {
  min-width: 34px;
  text-align: center;
  font-size: 0.7rem;
  font-weight: 800;
  padding: 1px 4px;
  border-radius: 4px;
  line-height: 1.2;
}

.pos-delta.gain {
  color: #00d200;
  background: rgba(0, 210, 0, 0.14);
}

.pos-delta.loss {
  color: #ff3b30;
  background: rgba(255, 59, 48, 0.14);
}

.pos-delta.even {
  color: var(--muted-text-color);
  background: rgba(128, 128, 128, 0.12);
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

.fl-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 0.68rem;
  font-weight: 800;
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(179, 90, 209, 0.2);
  color: #c468e2;
  border: 1px solid rgba(179, 90, 209, 0.4);
  line-height: 1.2;
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

.pts-pill {
  font-family: "JetBrains Mono", monospace;
  font-size: 0.68rem;
  font-weight: 800;
  padding: 2px 6px;
  border-radius: 3px;
  background: rgba(0, 210, 0, 0.15);
  color: #00d200;
  white-space: nowrap;
  line-height: 1.2;
}

.metric-empty {
  font-family: "JetBrains Mono", monospace;
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--muted-text-color);
  opacity: 0.45;
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

.steward-pills-stack {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 3px;
  margin-top: 4px;
  width: 100%;
}

.steward-pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 0.7rem;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 4px;
  cursor: help;
  line-height: 1.2;
  white-space: nowrap;
  letter-spacing: 0.01em;
  max-width: 100%;
}

.steward-pill.is-penalty {
  background: rgba(245, 158, 11, 0.16);
  color: #f59e0b;
  border: 1px solid rgba(245, 158, 11, 0.4);
}

.steward-pill.is-bw-flag {
  background: var(--item-bg-color);
  color: var(--text-color);
  border: 1px solid var(--border-color);
}

.status-badge {
  font-size: 0.68rem;
  font-weight: 800;
  padding: 2px 6px;
  border-radius: 4px;
  letter-spacing: 0.5px;
  font-family: "JetBrains Mono", monospace;
  line-height: 1.2;
  white-space: nowrap;
}

.status-dnf {
  background: rgba(235, 59, 53, 0.2);
  color: #eb3b35;
  border: 1px solid rgba(235, 59, 53, 0.4);
}

.status-dns {
  background: rgba(142, 142, 147, 0.2);
  color: #8e8e93;
  border: 1px solid rgba(142, 142, 147, 0.4);
}

.status-dsq {
  background: rgba(175, 82, 222, 0.2);
  color: #af52de;
  border: 1px solid rgba(175, 82, 222, 0.4);
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

.col-stints {
  flex: 1;
  padding-left: 1.5rem;
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

/* Stint background effects */
.stint-segment {
  background-image: linear-gradient(
    180deg,
    rgba(255, 255, 255, 0.15) 0%,
    rgba(0, 0, 0, 0.05) 100%
  );
}

.loading-state,
.error-state,
.no-data {
  padding: 4rem;
  text-align: center;
  color: var(--muted-text-color);
  font-weight: 500;
}

.no-data {
  padding: 4rem;
  text-align: center;
  color: var(--muted-text-color);
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
