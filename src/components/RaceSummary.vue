<script setup>
import { computed } from "vue";

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
});

const getTyreColor = (compound) => {
  const colors = {
    SOFT: "#ff3333",
    MEDIUM: "#ffff00",
    HARD: "#ffffff",
    INTERMEDIATE: "#00ff00",
    WET: "#0000ff",
  };
  return colors[compound.toUpperCase()] || "#777777";
};

const getTyreIcon = (compound) => {
  const c = compound.toUpperCase();
  let name = "hard";
  if (c.includes("SOFT")) name = "soft";
  else if (c.includes("MEDIUM")) name = "medium";
  else if (c.includes("HARD")) name = "hard";
  else if (c.includes("INTERMEDIATE")) name = "intermediate";
  else if (c.includes("WET")) name = "wet";

  return new URL(`../assets/tyres/${name}.svg`, import.meta.url).href;
};

const sortedResults = computed(() => {
  if (!props.summaryData?.results) return [];
  return [...props.summaryData.results].sort(
    (a, b) => (a.position || 99) - (b.position || 99),
  );
});

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
        <!-- Track Status Header Row -->
        <div
          v-if="summaryData.track_status_events?.length"
          class="track-status-row"
        >
          <div class="col-pos"></div>
          <div class="col-driver">TRACK STATUS</div>
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
          <div class="col-stints">TYRE STRATEGY (LAPS PER STINT)</div>
        </div>

        <div
          v-for="driver in sortedResults"
          :key="driver.driver_number"
          class="driver-row"
        >
          <div class="col-pos">{{ driver.position }}</div>

          <div class="col-driver">
            <div
              class="team-stripe"
              :style="{ backgroundColor: '#' + driver.team_color }"
            ></div>
            <div class="driver-info">
              <span class="driver-name">{{ driver.full_name }}</span>
              <span class="team-name">{{ driver.team_name }}</span>
            </div>
          </div>

          <div class="col-stints">
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
}

.track-status-row {
  display: flex;
  align-items: center;
  padding: 0.5rem 1.5rem;
  background: var(--card-bg-color);
  border-bottom: 1px solid var(--border-color);
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
}

.driver-row:last-child {
  border-bottom: none;
}

.driver-row:hover {
  background-color: var(--accent-color);
}

.col-pos {
  width: 50px;
  font-family: "Roboto Mono", monospace;
  font-weight: 800;
  font-size: 1.2rem;
  color: var(--text-color);
}

.col-driver {
  width: 280px;
  display: flex;
  align-items: center;
  gap: 1rem;
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
}

.team-name {
  font-size: 0.7rem;
  color: var(--muted-text-color);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-weight: 600;
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
  font-family: "Roboto Mono", monospace;
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
</style>
