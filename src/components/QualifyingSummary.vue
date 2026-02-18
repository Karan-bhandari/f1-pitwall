<script setup>
import { ref, computed, watch } from "vue";

// Import assets directly
import hardTyre from "../assets/tyres/hard.svg";
import mediumTyre from "../assets/tyres/medium.svg";
import softTyre from "../assets/tyres/soft.svg";
import interTyre from "../assets/tyres/intermediate.svg";
import wetTyre from "../assets/tyres/wet.svg";

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
  theme: {
    type: String,
    default: "dark",
  },
});

const selectedPhase = ref("");

// Dynamically get phases from backend
const availablePhases = computed(() => {
  if (
    props.summaryData?.available_phases &&
    props.summaryData.available_phases.length > 0
  ) {
    return props.summaryData.available_phases;
  }
  return ["Q1", "Q2", "Q3"];
});

// Watch for data load to set initial phase
watch(
  availablePhases,
  (newPhases) => {
    if (newPhases && newPhases.length > 0) {
      if (!selectedPhase.value || !newPhases.includes(selectedPhase.value)) {
        selectedPhase.value = newPhases[0];
      }
    }
  },
  { immediate: true },
);

const getTyreIcon = (compound) => {
  const c = compound?.toUpperCase() || "HARD";
  if (c.includes("SOFT")) return softTyre;
  if (c.includes("MEDIUM")) return mediumTyre;
  if (c.includes("HARD")) return hardTyre;
  if (c.includes("INTERMEDIATE")) return interTyre;
  if (c.includes("WET")) return wetTyre;
  return hardTyre;
};

const getBestTimeInPhase = (driver, phase) => {
  let best = Infinity;
  if (!driver.stints) return null;

  driver.stints.forEach((stint) => {
    if (!stint.laps) return;
    stint.laps.forEach((lap) => {
      if (lap.phase === phase && lap.type === "push" && lap.lap_time_seconds) {
        if (lap.lap_time_seconds < best) best = lap.lap_time_seconds;
      }
    });
  });
  return best === Infinity ? null : best;
};

const filteredResults = computed(() => {
  if (!props.summaryData?.results) return [];

  const phase = selectedPhase.value || availablePhases.value[0];
  const phaseNum = parseInt(phase.replace(/^\D+/g, "")) || 1;

  // Filter drivers who REACHED this phase
  const participating = props.summaryData.results.filter((d) => {
    // If backend provided max_phase, use it for qualifying
    if (d.max_phase && d.max_phase !== "Session") {
      const dMaxPhaseNum = parseInt(d.max_phase.replace(/^\D+/g, "")) || 1;
      return dMaxPhaseNum >= phaseNum;
    }

    // Fallback: Filter drivers who have at least one PUSH lap in this phase
    return d.stints?.some((s) =>
      s.laps?.some((l) => l.phase === phase && l.type === "push"),
    );
  });

  // Sort by best time in the SELECTED phase
  return participating.sort((a, b) => {
    const timeA = getBestTimeInPhase(a, phase) || 9999;
    const timeB = getBestTimeInPhase(b, phase) || 9999;
    return timeA - timeB;
  });
});

const formatLapTime = (timeStr) => {
  if (!timeStr) return "--";
  const parts = timeStr.split(":");
  if (parts.length < 3) return timeStr;
  const mins = parseInt(parts[1]);
  const secs = parseFloat(parts[2]).toFixed(3);
  return `${mins}:${secs.padStart(6, "0")}`;
};

const getSectorColor = (status) => {
  const isDark = props.theme === "dark";
  switch (status) {
    case "purple":
      return "#b35ad1";
    case "green":
      return isDark ? "#00d200" : "#008a00";
    case "yellow":
      return isDark ? "#ffff00" : "#d1bc00";
    default:
      return "rgba(128,128,128,0.2)";
  }
};
</script>

<template>
  <div class="qualifying-summary-container">
    <div class="summary-controls">
      <div class="phase-selector">
        <button
          v-for="phase in availablePhases"
          :key="phase"
          class="phase-btn"
          :class="{ active: selectedPhase === phase }"
          @click="selectedPhase = phase"
        >
          {{ phase }}
        </button>
      </div>
    </div>

    <div v-if="isLoading" class="loading-state">
      <p>Loading session data...</p>
    </div>

    <div v-else-if="error" class="error-state">
      <p>{{ error }}</p>
    </div>

    <div v-else-if="summaryData" class="summary-scroll-area">
      <div class="summary-table">
        <!-- Unified Header -->
        <div class="summary-header header-row">
          <div class="col-fixed header-cell">
            <div class="col-pos">POS</div>
            <div class="col-driver">DRIVER / TEAM</div>
          </div>
          <div class="col-scrollable header-cell">
            LAPS IN {{ selectedPhase }}
          </div>
        </div>

        <!-- Driver Rows -->
        <div
          v-for="(driver, index) in filteredResults"
          :key="driver.driver_number"
          class="driver-row"
        >
          <div class="col-fixed row-cell">
            <div class="col-pos">{{ index + 1 }}</div>
            <div class="col-driver">
              <div
                class="team-stripe"
                :style="{ backgroundColor: '#' + driver.team_color }"
              ></div>
              <div class="driver-info">
                <span class="driver-name">{{ driver.abbreviation }}</span>
                <span class="team-name">{{ driver.team_name }}</span>
              </div>
            </div>
          </div>

          <div class="col-scrollable row-cell">
            <div class="laps-row">
              <template v-for="stint in driver.stints" :key="stint.run_number">
                <template v-for="lap in stint.laps" :key="lap.lap_number">
                  <div
                    v-if="lap.phase === selectedPhase"
                    class="lap-pill"
                    :class="[lap.type, { 'is-pb': lap.is_pb }]"
                  >
                    <div class="lap-main">
                      <img
                        :src="getTyreIcon(lap.compound)"
                        class="tyre-icon"
                        :title="lap.compound"
                      />
                      <span class="lap-time">
                        {{
                          lap.type === "push"
                            ? formatLapTime(lap.lap_time)
                            : lap.type.toUpperCase()
                        }}
                      </span>
                    </div>
                    <div
                      v-if="
                        lap.sectors.s1.time ||
                        lap.sectors.s2.time ||
                        lap.sectors.s3.time
                      "
                      class="sector-times"
                    >
                      <div class="sector">
                        <span class="s-label">S1</span>
                        <span
                          class="s-val"
                          :style="{
                            color: getSectorColor(lap.sectors.s1.status),
                          }"
                          >{{ lap.sectors.s1.time?.toFixed(3) || "--" }}</span
                        >
                      </div>
                      <div class="sector">
                        <span class="s-label">S2</span>
                        <span
                          class="s-val"
                          :style="{
                            color: getSectorColor(lap.sectors.s2.status),
                          }"
                          >{{ lap.sectors.s2.time?.toFixed(3) || "--" }}</span
                        >
                      </div>
                      <div class="sector">
                        <span class="s-label">S3</span>
                        <span
                          class="s-val"
                          :style="{
                            color: getSectorColor(lap.sectors.s3.status),
                          }"
                          >{{ lap.sectors.s3.time?.toFixed(3) || "--" }}</span
                        >
                      </div>
                    </div>
                  </div>
                </template>
              </template>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.qualifying-summary-container {
  margin-top: 2rem;
  background: var(--card-bg-color);
  border-radius: 12px;
  border: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 4px 20px var(--shadow-color);
}

.summary-controls {
  padding: 1rem 1.5rem;
  border-bottom: 1px solid var(--border-color);
  background: var(--item-bg-color);
}

.phase-selector {
  display: flex;
  gap: 0.5rem;
}

.phase-btn {
  padding: 0.4rem 1.5rem;
  border-radius: 20px;
  border: 1px solid var(--border-color);
  background: var(--card-bg-color);
  color: var(--muted-text-color);
  font-weight: 800;
  font-size: 0.8rem;
  cursor: pointer;
  transition: all 0.2s;
  letter-spacing: 1px;
}

.phase-btn.active {
  background: var(--primary-color);
  color: white;
  border-color: var(--primary-color);
}

.summary-scroll-area {
  overflow-x: auto;
  width: 100%;
}

.summary-table {
  display: inline-block;
  min-width: 100%;
}

.header-row,
.driver-row {
  display: flex;
  border-bottom: 1px solid var(--border-color);
  min-width: max-content;
  width: 100%;
}

.driver-row:last-child {
  border-bottom: none;
}

.col-fixed {
  width: 260px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  padding: 0.75rem 1.5rem;
  background: var(--item-bg-color);
  position: sticky;
  left: 0;
  z-index: 10;
  border-right: 1px solid var(--border-color);
}

.driver-row .col-fixed {
  background: var(--card-bg-color);
}

.col-scrollable {
  flex: 1;
  padding: 0.75rem 1.5rem;
}

.header-cell {
  background: var(--item-bg-color);
  height: 44px;
  font-weight: 800;
  font-size: 0.75rem;
  color: var(--muted-text-color);
  text-transform: uppercase;
  letter-spacing: 1px;
}

.row-cell {
  min-height: 120px;
  display: flex;
  align-items: center;
}

.col-pos {
  width: 40px;
  font-family: "Roboto Mono", monospace;
  font-weight: 800;
  color: var(--muted-text-color);
  font-size: 1.1rem;
}

.col-driver {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex: 1;
}

.team-stripe {
  width: 4px;
  height: 40px;
  border-radius: 2px;
  flex-shrink: 0;
}

.driver-info {
  display: flex;
  flex-direction: column;
}

.driver-name {
  font-weight: 900;
  font-size: 1.35rem;
  line-height: 1.1;
  color: var(--text-color);
}

.team-name {
  font-size: 0.7rem;
  color: var(--muted-text-color);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  white-space: nowrap;
  font-weight: 600;
}

.laps-row {
  display: flex;
  gap: 1rem;
  align-items: center;
}

.lap-pill {
  display: flex;
  flex-direction: column;
  padding: 0.75rem 1.25rem;
  background: var(--item-bg-color);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  min-width: 190px;
  flex-shrink: 0;
  box-shadow: 0 2px 6px var(--shadow-color);
  transition: transform 0.2s ease;
}

.lap-pill:hover {
  transform: translateY(-2px);
}

.lap-main {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 8px;
}

.tyre-icon {
  width: 22px;
  height: 22px;
}

.lap-time {
  font-family: "Roboto Mono", monospace;
  font-size: 1.15rem;
  font-weight: 800;
  color: var(--text-color);
}

.sector-times {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.sector {
  display: flex;
  gap: 12px; /* Tight gap between label and value */
  font-size: 0.8rem;
  font-family: "Roboto Mono", monospace;
  font-weight: 700;
}

.s-label {
  color: var(--muted-text-color);
  font-weight: 500;
  width: 20px; /* Small fixed width just for the label to keep values aligned */
}

.s-val {
  /* Dynamic color from inline style */
}

.lap-pill.out,
.lap-pill.in,
.lap-pill.prep {
  min-width: 100px;
  opacity: 0.6;
  justify-content: center;
  border-style: dashed;
  background: transparent;
}

.loading-state,
.no-data,
.error-state {
  padding: 4rem;
  text-align: center;
  color: var(--muted-text-color);
}

.loading-state,
.no-data,
.error-state {
  padding: 4rem;
  text-align: center;
  color: var(--muted-text-color);
}

.summary-scroll-area::-webkit-scrollbar {
  height: 8px;
}
.summary-scroll-area::-webkit-scrollbar-track {
  background: var(--bg-color);
}
.summary-scroll-area::-webkit-scrollbar-thumb {
  background: var(--border-color);
  border-radius: 4px;
}
</style>
