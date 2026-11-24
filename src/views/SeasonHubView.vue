<script setup>
import { ref, computed, watch, nextTick, onBeforeUnmount } from "vue";
import { RouterLink } from "vue-router";
import Chart from "chart.js/auto";
import { getSeasonStats } from "../api";
import {
  formatOffsetLabel,
  formatSessionDateTime,
  getLocalTimezoneLabel,
  setTimeZoneMode,
  timeZoneMode,
} from "../utils";
import SeasonOverview from "../components/SeasonOverview.vue";
import F1Icon from "../components/F1Icon.vue";

const props = defineProps({
  year: {
    type: Number,
    required: true,
  },
  theme: {
    type: String,
    default: "light",
  },
});

// --- State ---
const seasonStats = ref(null);
const loadingStats = ref(true);
const chartMode = ref("drivers"); // 'drivers' | 'constructors'
const chartCanvas = ref(null);
const chartDatasetsMeta = ref([]);
let chartInstance = null;
let statsReqId = 0;

// --- Data Fetching ---
async function fetchStats(year) {
  const reqId = ++statsReqId;
  loadingStats.value = true;
  try {
    const data = await getSeasonStats(year);
    if (reqId !== statsReqId) return;
    seasonStats.value = data;
  } catch (err) {
    if (reqId !== statsReqId) return;
    console.error("Failed to load season stats:", err);
    seasonStats.value = null;
  } finally {
    if (reqId === statsReqId) {
      loadingStats.value = false;
      nextTick(() => {
        renderProgressionChart();
      });
    }
  }
}

watch(
  () => props.year,
  (newYear) => {
    fetchStats(newYear);
  },
  { immediate: true },
);

// --- Computeds ---
const canShowConstructors = computed(() => {
  if (Number(props.year) < 1958) return false;
  return Boolean(
    seasonStats.value?.points_progression?.constructors &&
    seasonStats.value.points_progression.constructors.length > 0,
  );
});

watch(canShowConstructors, (can) => {
  if (!can && chartMode.value === "constructors") {
    chartMode.value = "drivers";
  }
});

watch(chartMode, () => {
  nextTick(renderProgressionChart);
});

const hasProgression = computed(() => {
  return (
    seasonStats.value?.points_progression?.rounds &&
    seasonStats.value.points_progression.rounds.length > 1
  );
});

// --- Chart.js Rendering ---
function renderProgressionChart() {
  if (!chartCanvas.value) return;

  if (chartInstance) {
    chartInstance.destroy();
    chartInstance = null;
  }

  const progression = seasonStats.value?.points_progression;
  if (!progression?.rounds || progression.rounds.length <= 1) {
    return;
  }

  const isDark = props.theme === "dark";
  const textColor = isDark ? "#9898a6" : "#555560";
  const gridColor = isDark
    ? "rgba(255, 255, 255, 0.08)"
    : "rgba(0, 0, 0, 0.06)";
  const titleColor = isDark ? "#f1f1f6" : "#111116";
  const tooltipBg = isDark ? "#15151e" : "#ffffff";
  const tooltipBorder = isDark ? "#2a2a3c" : "#d0d0d7";

  const labels = progression.rounds.map((r) => r.short_name || `R${r.round}`);

  let datasets = [];
  if (chartMode.value === "drivers") {
    const drivers = progression.drivers || [];
    const colorSeenCounts = new Map();

    datasets = drivers.map((d) => {
      const rawHex = (d.team_color || "e10600").toLowerCase().replace("#", "");
      const count = colorSeenCounts.get(rawHex) || 0;
      colorSeenCounts.set(rawHex, count + 1);

      const isSecondTeammate = count > 0;
      const color = `#${rawHex}`;

      return {
        label: `${d.driver_code} (${d.driver_name})`,
        data: d.cumulative_points || [],
        borderColor: color,
        backgroundColor: color,
        borderDash: isSecondTeammate ? [5, 4] : [],
        borderWidth: 2.5,
        tension: 0.25,
        pointRadius: 3,
        pointHoverRadius: 6,
      };
    });
  } else {
    const constructors = progression.constructors || [];
    datasets = constructors.map((c) => {
      const rawHex = (c.team_color || "e10600").toLowerCase().replace("#", "");
      const color = `#${rawHex}`;
      return {
        label: c.constructor_name,
        data: c.cumulative_points || [],
        borderColor: color,
        backgroundColor: color,
        borderWidth: 2.5,
        tension: 0.25,
        pointRadius: 3,
        pointHoverRadius: 6,
      };
    });
  }

  chartDatasetsMeta.value = datasets.map((ds, idx) => ({
    index: idx,
    label: ds.label,
    color: ds.borderColor,
    isDashed: ds.borderDash && ds.borderDash.length > 0,
    visible: true,
  }));

  chartInstance = new Chart(chartCanvas.value, {
    type: "line",
    data: {
      labels,
      datasets,
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: {
        duration: 350,
      },
      interaction: {
        mode: "index",
        intersect: false,
      },
      plugins: {
        legend: {
          display: false,
        },
        tooltip: {
          backgroundColor: tooltipBg,
          titleColor: titleColor,
          bodyColor: titleColor,
          borderColor: tooltipBorder,
          borderWidth: 1,
          padding: 12,
          boxPadding: 6,
          titleFont: {
            family: "'Inter', sans-serif",
            size: 13,
            weight: "700",
          },
          bodyFont: {
            family: "'JetBrains Mono', monospace",
            size: 12,
          },
          callbacks: {
            title: (tooltipItems) => {
              if (!tooltipItems.length) return "";
              const idx = tooltipItems[0].dataIndex;
              const r = progression.rounds[idx];
              return r?.round_name
                ? `Round ${r.round}: ${r.round_name}`
                : tooltipItems[0].label;
            },
            label: (context) => {
              return ` ${context.dataset.label}: ${context.parsed.y} pts`;
            },
          },
        },
      },
      scales: {
        x: {
          ticks: {
            color: textColor,
            font: {
              family: "'JetBrains Mono', monospace",
              size: 11,
            },
          },
          grid: {
            color: gridColor,
            drawBorder: false,
          },
        },
        y: {
          beginAtZero: true,
          ticks: {
            color: textColor,
            font: {
              family: "'JetBrains Mono', monospace",
              size: 11,
            },
            callback: (val) => `${val} pts`,
          },
          grid: {
            color: gridColor,
            drawBorder: false,
          },
        },
      },
    },
  });
}

function setChartMode(mode) {
  chartMode.value = mode;
  nextTick(() => {
    renderProgressionChart();
  });
}

function toggleDataset(index) {
  if (!chartInstance) return;
  const isVisible = chartInstance.isDatasetVisible(index);
  chartInstance.setDatasetVisibility(index, !isVisible);
  chartInstance.update();

  const meta = chartDatasetsMeta.value.find((m) => m.index === index);
  if (meta) {
    meta.visible = !isVisible;
  }
}

watch(
  () => props.theme,
  () => {
    nextTick(() => {
      renderProgressionChart();
    });
  },
);

onBeforeUnmount(() => {
  if (chartInstance) {
    chartInstance.destroy();
    chartInstance = null;
  }
});

// --- Formatting Helpers ---
const localTzLabel = getLocalTimezoneLabel();

const nextRoundHasOffset = computed(() =>
  Boolean(seasonStats.value?.next_round?.gmt_offset),
);

const effectiveNextTzMode = computed(() =>
  timeZoneMode.value === "track" && nextRoundHasOffset.value
    ? "track"
    : "local",
);

const nextRoundPlaceLabel = computed(
  () => seasonStats.value?.next_round?.location || "Track Time",
);

const nextRoundTrackTzLabel = computed(
  () => formatOffsetLabel(seasonStats.value?.next_round?.gmt_offset) || "Track",
);

function formatNextSessionTime(sessionItem) {
  return formatSessionDateTime(sessionItem?.utc || sessionItem?.local, {
    mode: effectiveNextTzMode.value,
    gmtOffset: seasonStats.value?.next_round?.gmt_offset,
  });
}

function formatDate(dateStr) {
  if (!dateStr) return "";
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    return d.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      timeZone: "UTC",
    });
  } catch {
    return dateStr;
  }
}
</script>

<template>
  <div class="season-hub-view">
    <!-- Top Strip: Latest Grand Prix Podium & Next Round Summary Cards -->
    <section
      v-if="seasonStats && (seasonStats.latest_round || seasonStats.next_round)"
      class="season-pulse-section"
    >
      <div
        class="season-pulse-grid"
        :class="{ 'single-card': !seasonStats.next_round }"
      >
        <!-- 1. Latest Grand Prix Card -->
        <article
          v-if="seasonStats.latest_round"
          class="pulse-card latest-round-card"
        >
          <div class="latest-round-head">
            <div class="pulse-card-header">
              <div class="badge-row">
                <span class="round-badge">
                  LATEST COMPLETED ROUND · R{{ seasonStats.latest_round.round }}
                </span>
                <span class="event-date" v-if="seasonStats.latest_round.date">
                  {{ formatDate(seasonStats.latest_round.date) }}
                </span>
              </div>
              <RouterLink
                :to="{
                  path: '/race',
                  query: {
                    year: props.year,
                    round: seasonStats.latest_round.round,
                    event: seasonStats.latest_round.event_key,
                    session: 'Weekend Recap',
                  },
                }"
                class="pitwall-jump-btn"
              >
                <span>Inspect Race PitWall</span>
                <span class="arrow-glyph">→</span>
              </RouterLink>
            </div>

            <h2
              class="pulse-event-title"
              :title="seasonStats.latest_round.event_name"
            >
              {{ seasonStats.latest_round.event_name }}
            </h2>
          </div>

          <div
            class="podium-list"
            v-if="
              seasonStats.latest_round.podium &&
              seasonStats.latest_round.podium.length
            "
          >
            <div
              v-for="driver in seasonStats.latest_round.podium"
              :key="driver.position + driver.driver_code"
              class="podium-row"
              :class="`podium-row-${driver.position}`"
            >
              <div
                class="podium-pos-badge"
                :class="`pos-badge-${driver.position}`"
              >
                P{{ driver.position }}
              </div>
              <div class="podium-driver-main">
                <span
                  class="podium-team-dot"
                  :style="{
                    backgroundColor: `#${driver.team_color || 'e10600'}`,
                  }"
                ></span>
                <span class="podium-driver-name" :title="driver.driver_name">
                  {{ driver.driver_name }}
                </span>
              </div>
              <div class="podium-right-meta">
                <span class="podium-team-label" :title="driver.team_name">
                  {{ driver.team_name }}
                </span>
                <span class="podium-code-pill">{{ driver.driver_code }}</span>
              </div>
            </div>
          </div>
        </article>

        <!-- 2. Next Round Card (Shown when next_round is non-null) -->
        <article
          v-if="seasonStats.next_round"
          class="pulse-card next-round-card"
        >
          <div class="pulse-card-header">
            <div class="badge-row">
              <span class="round-badge up-next-badge">
                UP NEXT · ROUND {{ seasonStats.next_round.round }}
              </span>
              <span v-if="seasonStats.next_round.is_sprint" class="sprint-pill">
                <F1Icon name="bolt" :size="12" />
                <span>Sprint Weekend</span>
              </span>
            </div>
            <span
              v-if="seasonStats.remaining_rounds !== undefined"
              class="remaining-rounds-pill mono"
            >
              {{ seasonStats.remaining_rounds }} round{{
                seasonStats.remaining_rounds === 1 ? "" : "s"
              }}
              remaining in {{ year }}
            </span>
          </div>

          <h2
            class="pulse-event-title"
            :title="seasonStats.next_round.event_name"
          >
            {{ seasonStats.next_round.event_name }}
          </h2>

          <div class="next-round-info-box">
            <div
              class="next-info-item"
              v-if="
                seasonStats.next_round.location ||
                seasonStats.next_round.country
              "
            >
              <div class="item-icon-wrap">
                <F1Icon name="checkered-flag" :size="15" />
              </div>
              <div class="item-text-col">
                <span class="item-label">Circuit &amp; Country</span>
                <span class="item-value">
                  {{
                    [
                      seasonStats.next_round.location,
                      seasonStats.next_round.country,
                    ]
                      .filter(Boolean)
                      .join(", ")
                  }}
                </span>
              </div>
            </div>

            <div class="next-info-item" v-if="seasonStats.next_round.date">
              <div class="item-icon-wrap">
                <F1Icon name="stopwatch" :size="15" />
              </div>
              <div class="item-text-col">
                <span class="item-label">Scheduled Date</span>
                <span class="item-value mono">
                  {{ formatDate(seasonStats.next_round.date) }}
                </span>
              </div>
            </div>
          </div>

          <!-- Weekend Sessions Schedule with Local vs. Track Timezone Converter -->
          <div
            v-if="seasonStats.next_round.sessions?.length"
            class="weekend-schedule-box"
          >
            <div class="weekend-schedule-header">
              <span class="schedule-heading">Weekend Schedule</span>
              <div
                v-if="nextRoundHasOffset"
                class="tz-toggle"
                role="group"
                aria-label="Schedule timezone"
              >
                <button
                  type="button"
                  class="tz-btn"
                  :class="{ active: effectiveNextTzMode === 'local' }"
                  @click="setTimeZoneMode('local')"
                  :title="`Show schedule in your timezone (${localTzLabel})`"
                >
                  My Time
                </button>
                <button
                  type="button"
                  class="tz-btn"
                  :class="{ active: effectiveNextTzMode === 'track' }"
                  @click="setTimeZoneMode('track')"
                  :title="`Show schedule in ${nextRoundPlaceLabel} local time (${nextRoundTrackTzLabel})`"
                >
                  {{ nextRoundPlaceLabel }}
                </button>
              </div>
            </div>

            <div class="weekend-sessions-list">
              <div
                v-for="sess in seasonStats.next_round.sessions"
                :key="sess.name"
                class="weekend-session-row"
                :class="{
                  'is-key-session':
                    sess.name === 'Race' ||
                    sess.name === 'Qualifying' ||
                    sess.name === 'Sprint',
                }"
              >
                <span class="sess-name">{{ sess.name }}</span>
                <span class="sess-datetime mono">
                  {{ formatNextSessionTime(sess).day }} ·
                  {{ formatNextSessionTime(sess).time }}
                </span>
              </div>
            </div>
          </div>
        </article>
      </div>
    </section>

    <!-- Center Section: Season Overview (Existing Standings & Progress) -->
    <SeasonOverview :year="Number(year)" />

    <!-- Bottom Section: Round-by-Round Championship Points Progression Chart -->
    <section v-if="hasProgression" class="progression-section">
      <div class="progression-card">
        <header class="progression-header">
          <div class="progression-title-wrap">
            <div class="progression-icon">
              <F1Icon name="chart" :size="22" />
            </div>
            <div>
              <h2 class="progression-title">Championship Points Progression</h2>
              <p class="progression-subtitle">
                Round-by-Round Cumulative Points Accumulation
              </p>
            </div>
          </div>

          <!-- Toggle Button Group: Drivers (Top 10) vs Constructors -->
          <div class="chart-toggle-group" role="tablist">
            <button
              class="chart-toggle-btn"
              :class="{ active: chartMode === 'drivers' }"
              role="tab"
              :aria-selected="chartMode === 'drivers'"
              @click="setChartMode('drivers')"
            >
              <F1Icon name="helmet" :size="15" />
              <span>Drivers (Top 10)</span>
            </button>
            <button
              v-if="canShowConstructors"
              class="chart-toggle-btn"
              :class="{ active: chartMode === 'constructors' }"
              role="tab"
              :aria-selected="chartMode === 'constructors'"
              @click="setChartMode('constructors')"
            >
              <F1Icon name="wrench" :size="15" />
              <span>Constructors</span>
            </button>
          </div>
        </header>

        <div class="chart-canvas-container">
          <canvas ref="chartCanvas" id="progression-chart-canvas"></canvas>
        </div>

        <!-- Crisp Custom HTML Legend Pill Strip -->
        <div class="custom-chart-legend" v-if="chartDatasetsMeta.length > 0">
          <button
            v-for="item in chartDatasetsMeta"
            :key="item.index"
            class="legend-pill"
            :class="{ 'is-hidden': !item.visible }"
            @click="toggleDataset(item.index)"
            :title="`Click to ${item.visible ? 'hide' : 'show'} ${item.label}`"
          >
            <span
              class="legend-line-indicator"
              :class="{ dashed: item.isDashed }"
              :style="{
                backgroundColor: item.isDashed ? 'transparent' : item.color,
                color: item.color,
              }"
            ></span>
            <span class="legend-pill-label mono">{{ item.label }}</span>
          </button>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.season-hub-view {
  width: 100%;
  max-width: 1400px;
  margin: 0 auto;
  box-sizing: border-box;
}

/* --- Top Summary Cards Section --- */
.season-pulse-section {
  margin-bottom: 2rem;
  width: 100%;
}

.season-pulse-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.22fr) minmax(0, 1fr);
  gap: 1.25rem;
  width: 100%;
}

.season-pulse-grid.single-card {
  grid-template-columns: 1fr;
}

.pulse-card {
  background: var(--card-bg-color);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 1.25rem 1.4rem;
  box-shadow: 0 4px 16px var(--shadow-color);
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  gap: 1rem;
  overflow: hidden;
}

.pulse-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.badge-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.round-badge {
  font-family: "JetBrains Mono", monospace;
  font-variant-numeric: tabular-nums;
  font-size: 0.74rem;
  font-weight: 800;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  background: var(--item-bg-color);
  color: var(--text-color);
  border: 1px solid var(--border-color);
  padding: 0.25rem 0.65rem;
  border-radius: 4px;
}

.round-badge.up-next-badge {
  background: rgba(225, 6, 0, 0.08);
  color: var(--primary-color);
  border-color: rgba(225, 6, 0, 0.25);
}

.mono {
  font-family: "JetBrains Mono", monospace;
  font-variant-numeric: tabular-nums;
}

.event-date {
  font-size: 0.8rem;
  color: var(--muted-text-color);
  font-weight: 500;
  font-variant-numeric: tabular-nums;
}

.pitwall-jump-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  background: var(--accent-color);
  color: var(--primary-color);
  border: 1px solid rgba(225, 6, 0, 0.25);
  font-size: 0.82rem;
  font-weight: 700;
  padding: 0.35rem 0.85rem;
  border-radius: 6px;
  text-decoration: none;
  transition: all 0.2s ease;
  white-space: nowrap;
}

.pitwall-jump-btn:hover {
  background: var(--primary-color);
  color: #ffffff;
  border-color: var(--primary-color);
  box-shadow: 0 2px 8px rgba(225, 6, 0, 0.3);
}

.pitwall-jump-btn:focus-visible {
  outline: 2px solid var(--primary-color);
  outline-offset: 2px;
}

.arrow-glyph {
  font-weight: 800;
  transition: transform 0.15s ease;
}

.pitwall-jump-btn:hover .arrow-glyph {
  transform: translateX(2px);
}

.pulse-event-title {
  font-size: 1.35rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: var(--text-color);
  margin: 0;
  line-height: 1.25;
}

/* --- Podium Classification List --- */
.latest-round-card {
  height: 100%;
  box-sizing: border-box;
  gap: 0.9rem;
}

.latest-round-head {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.podium-list {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
  flex: 1;
  justify-content: space-between;
}

.podium-row {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 0.75rem;
  padding: 0.7rem 0.85rem;
  background: var(--item-bg-color);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  flex: 1;
}

.podium-row-1 {
  background: color-mix(in srgb, var(--primary-color) 6%, var(--item-bg-color));
  border-color: color-mix(
    in srgb,
    var(--primary-color) 28%,
    var(--border-color)
  );
}

.podium-pos-badge {
  width: 28px;
  height: 28px;
  min-width: 28px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 800;
  font-size: 0.78rem;
  font-family: "JetBrains Mono", monospace;
  font-variant-numeric: tabular-nums;
  box-sizing: border-box;
}

.pos-badge-1 {
  background: linear-gradient(135deg, #ffd700 0%, #b89700 100%);
  color: #000;
  border: none;
  box-shadow: 0 2px 8px rgba(255, 215, 0, 0.35);
}

.pos-badge-2 {
  background: linear-gradient(135deg, #e0e0e0 0%, #9e9e9e 100%);
  color: #000;
  border: none;
  box-shadow: 0 2px 8px rgba(192, 192, 192, 0.35);
}

.pos-badge-3 {
  background: linear-gradient(135deg, #cd7f32 0%, #8c4c10 100%);
  color: #fff;
  border: none;
  box-shadow: 0 2px 8px rgba(205, 127, 50, 0.35);
}

.podium-driver-main {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  min-width: 0;
}

.podium-team-dot {
  width: 9px;
  height: 9px;
  border-radius: 999px;
  flex-shrink: 0;
}

.podium-driver-name {
  font-size: 0.94rem;
  font-weight: 700;
  color: var(--text-color);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.podium-row-1 .podium-driver-name {
  font-size: 1rem;
  font-weight: 800;
}

.podium-right-meta {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  flex-shrink: 0;
}

.podium-team-label {
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--muted-text-color);
}

.podium-code-pill {
  font-family: "JetBrains Mono", monospace;
  font-variant-numeric: tabular-nums;
  font-size: 0.74rem;
  font-weight: 800;
  color: var(--text-color);
  background: var(--card-bg-color);
  border: 1px solid var(--border-color);
  padding: 0.18rem 0.45rem;
  border-radius: 5px;
}

/* --- Next Round Specifics --- */
.sprint-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  background: rgba(245, 158, 11, 0.14);
  color: #9a4e00;
  border: 1px solid rgba(245, 158, 11, 0.3);
  font-size: 0.74rem;
  font-weight: 700;
  padding: 0.2rem 0.55rem;
  border-radius: 4px;
}

:global(html[data-theme="dark"]) .sprint-pill {
  color: #fbbf24;
}

.remaining-rounds-pill {
  font-size: 0.76rem;
  font-weight: 600;
  color: var(--muted-text-color);
  background: var(--item-bg-color);
  border: 1px solid var(--border-color);
  padding: 0.2rem 0.55rem;
  border-radius: 4px;
}

.next-round-info-box {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(0, 1fr);
  gap: 0.65rem;
}

.next-info-item {
  background: var(--item-bg-color);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 0.65rem 0.75rem;
  display: flex;
  align-items: center;
  gap: 0.65rem;
  min-width: 0;
}

.item-icon-wrap {
  color: var(--primary-color);
  flex-shrink: 0;
}

.item-text-col {
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
}

.item-label {
  font-size: 0.7rem;
  font-weight: 700;
  color: var(--muted-text-color);
  text-transform: uppercase;
  letter-spacing: 0.4px;
}

.item-value {
  font-size: 0.85rem;
  font-weight: 700;
  color: var(--text-color);
  line-height: 1.25;
  overflow-wrap: break-word;
  margin-top: 0.15rem;
}

.weekend-schedule-box {
  margin-top: 0.75rem;
  background: var(--item-bg-color);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 0.65rem 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.weekend-schedule-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.schedule-heading {
  font-size: 0.72rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--muted-text-color);
}

.tz-toggle {
  display: inline-flex;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  background: var(--card-bg-color);
  padding: 2px;
  gap: 2px;
  flex-shrink: 0;
}

.tz-btn {
  border: none;
  background: transparent;
  color: var(--muted-text-color);
  font-family: inherit;
  font-size: 0.7rem;
  font-weight: 700;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
}

.tz-btn:hover {
  color: var(--text-color);
}

.tz-btn:focus-visible {
  outline: 2px solid var(--primary-color);
  outline-offset: 1px;
}

.tz-btn.active {
  background: var(--accent-color);
  color: var(--primary-color);
}

.weekend-sessions-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 0.35rem 0.75rem;
}

.weekend-session-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  font-size: 0.78rem;
  padding: 0.22rem 0;
  border-bottom: 1px dashed var(--border-color);
}

.weekend-session-row:last-child {
  border-bottom: none;
}

.weekend-session-row.is-key-session .sess-name {
  font-weight: 800;
  color: var(--text-color);
}

.sess-name {
  color: var(--muted-text-color);
  font-weight: 600;
}

.sess-datetime {
  color: var(--text-color);
  font-weight: 700;
  white-space: nowrap;
}

/* --- Championship Progression Section --- */
.progression-section {
  margin-top: 2rem;
  width: 100%;
}

.progression-card {
  background: var(--card-bg-color);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 1.5rem;
  box-shadow: 0 4px 16px var(--shadow-color);
  overflow: hidden;
}

.progression-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
  margin-bottom: 1.5rem;
}

.progression-title-wrap {
  display: flex;
  align-items: center;
  gap: 0.85rem;
}

.progression-icon {
  width: 44px;
  height: 44px;
  border-radius: 8px;
  background: var(--accent-color);
  color: var(--primary-color);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border: 1px solid rgba(225, 6, 0, 0.2);
}

.progression-title {
  font-size: 1.35rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: var(--text-color);
  margin: 0;
  line-height: 1.2;
}

.progression-subtitle {
  font-size: 0.88rem;
  color: var(--muted-text-color);
  margin: 0.2rem 0 0;
}

/* Chart Toggle Group */
.chart-toggle-group {
  display: inline-flex;
  align-items: center;
  background: var(--item-bg-color);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 0.25rem;
  gap: 0.25rem;
}

.chart-toggle-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  background: transparent;
  color: var(--muted-text-color);
  border: none;
  padding: 0.45rem 0.85rem;
  border-radius: 6px;
  font-family: inherit;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.chart-toggle-btn:hover {
  color: var(--text-color);
}

.chart-toggle-btn:focus-visible {
  outline: 2px solid var(--primary-color);
  outline-offset: 2px;
}

.chart-toggle-btn.active {
  background: var(--card-bg-color);
  color: var(--text-color);
  font-weight: 700;
  box-shadow: 0 1px 4px var(--shadow-color);
}

/* Canvas Container */
.chart-canvas-container {
  position: relative;
  width: 100%;
  height: 420px;
}

/* --- Custom HTML Legend Pill Strip --- */
.custom-chart-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  padding: 1rem 1.25rem 0.25rem 1.25rem;
  border-top: 1px solid var(--border-color);
  margin-top: 0.75rem;
  align-items: center;
}

.legend-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  background: var(--item-bg-color);
  border: 1px solid var(--border-color);
  padding: 0.3rem 0.65rem;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s ease;
  font-family: inherit;
  font-size: 0.8rem;
  color: var(--text-color);
}

.legend-pill:hover {
  background: var(--card-bg-color);
  border-color: var(--primary-color);
  transform: translateY(-1px);
}

.legend-pill:focus-visible {
  outline: 2px solid var(--primary-color);
  outline-offset: 2px;
}

.legend-pill.is-hidden {
  opacity: 0.4;
  text-decoration: line-through;
  background: transparent;
}

.legend-line-indicator {
  display: inline-block;
  width: 18px;
  height: 3px;
  border-radius: 2px;
  position: relative;
}

.legend-line-indicator.dashed {
  background: repeating-linear-gradient(
    90deg,
    currentColor,
    currentColor 4px,
    transparent 4px,
    transparent 8px
  ) !important;
}

@media (max-width: 1120px) {
  .season-pulse-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .season-pulse-grid {
    grid-template-columns: 1fr;
    gap: 1rem;
  }

  .podium-strip {
    grid-template-columns: 1fr;
    gap: 0.5rem;
  }

  .podium-box {
    min-height: 52px;
  }

  .next-round-info-box {
    grid-template-columns: 1fr;
    gap: 0.5rem;
  }

  .progression-header {
    flex-direction: column;
    align-items: stretch;
    gap: 1rem;
  }

  .chart-toggle-group {
    width: 100%;
  }

  .chart-toggle-btn {
    flex: 1;
    justify-content: center;
  }

  .chart-canvas-container {
    height: 320px;
  }

  .progression-card {
    padding: 1.1rem;
  }

  .pulse-card {
    padding: 1rem 1.1rem;
  }

  .custom-chart-legend {
    padding: 0.85rem 0 0.25rem;
  }
}
</style>
