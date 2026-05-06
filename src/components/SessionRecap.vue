<script setup>
import { ref, computed, onMounted, watch } from "vue";
import { getWeekendSummary } from "../api";
import { getTyreColor } from "../utils";

const props = defineProps({
  year: { type: Number, required: true },
  eventKey: { type: String, required: true },
});

const loading = ref(true);
const error = ref(null);
const recapData = ref(null);
const activeSessionId = ref("");

const sessions = computed(() => {
  const s = recapData.value?.sessions;
  if (!s) return [];
  const list = Array.isArray(s) ? s : Object.values(s);
  // Guarantee chronological order by index
  return [...list].sort(
    (a, b) => (a.session_index || 0) - (b.session_index || 0),
  );
});

// Sessions are already sorted by the backend index or the array order
const activeSession = computed(() => {
  return (
    sessions.value.find((s) => s.session_name === activeSessionId.value) || null
  );
});

const fetchData = async () => {
  if (!props.year || !props.eventKey) return;

  loading.value = true;
  error.value = null;
  try {
    const data = await getWeekendSummary(props.year, props.eventKey);
    recapData.value = data;

    const sessionList = data.sessions
      ? Array.isArray(data.sessions)
        ? data.sessions
        : Object.values(data.sessions)
      : [];

    if (sessionList.length > 0) {
      // Default to Race if available, else the last session in the weekend
      const race = sessionList.find(
        (s) =>
          s.session_name.toLowerCase().includes("race") &&
          !s.session_name.toLowerCase().includes("sprint"),
      );
      activeSessionId.value = race
        ? race.session_name
        : sessionList.at(-1)?.session_name || "";
    }
  } catch (e) {
    error.value = "Failed to load weekend recap.";
    console.error("[Recap] Fetch Error:", e);
  } finally {
    loading.value = false;
  }
};

onMounted(fetchData);
watch(() => [props.year, props.eventKey], fetchData);

const isQualifyingType = (name) => {
  const n = (name || "").toLowerCase();
  return n.includes("qualifying") || n.includes("shootout");
};

const isPracticeType = (name) => {
  const n = (name || "").toLowerCase();
  return n.includes("practice") || n.includes("fp");
};
</script>

<template>
  <div class="session-recap">
    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <p>Gathering pitwall data...</p>
    </div>

    <div v-else-if="error" class="error-state">
      <p>{{ error }}</p>
      <button class="retry-btn" @click="fetchData">Retry</button>
    </div>

    <div v-else-if="recapData" class="content">
      <header class="recap-header">
        <h1>
          {{ recapData.event_name }} Recap
          <span v-if="props.year < 2018" class="badge no-telemetry"
            >NO TELEMETRY</span
          >
        </h1>
        <div class="header-meta">
          <span>{{ props.year }} Season</span>
          <span class="divider">|</span>
          <span class="session-indicator">{{
            activeSession?.session_name
          }}</span>
        </div>
      </header>

      <nav class="session-tabs">
        <button
          v-for="s in sessions"
          :key="s.session_name"
          :class="{ active: activeSessionId === s.session_name }"
          @click="activeSessionId = s.session_name"
        >
          {{ s.session_name.toUpperCase() }}
        </button>
      </nav>

      <div class="recap-grid" v-if="activeSession">
        <section class="results-panel">
          <div class="panel-header">
            <h3>Classification</h3>
          </div>
          <div class="table-container">
            <table>
              <thead>
                <tr v-if="isPracticeType(activeSession.session_name)">
                  <th>Pos</th>
                  <th>Driver</th>
                  <th>Best Time</th>
                  <th>Laps</th>
                </tr>
                <tr v-else-if="isQualifyingType(activeSession.session_name)">
                  <th>Pos</th>
                  <th>Driver</th>
                  <th>Q1</th>
                  <th>Q2</th>
                  <th>Q3</th>
                </tr>
                <tr v-else>
                  <th>Pos</th>
                  <th>Driver</th>
                  <th>Status</th>
                  <th>Points</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="driver in activeSession.results"
                  :key="driver.driver_number"
                >
                  <td class="pos-cell">{{ driver.pos }}</td>
                  <td class="driver-cell">
                    <span
                      class="team-stripe"
                      :style="{ backgroundColor: '#' + driver.team_color }"
                    ></span>
                    <span class="abbr">{{ driver.abbreviation }}</span>
                    <span class="full-name">{{ driver.full_name }}</span>
                  </td>

                  <template v-if="isPracticeType(activeSession.session_name)">
                    <td class="time-cell">{{ driver.best_time || "N/A" }}</td>
                    <td class="laps-cell">{{ driver.laps }}</td>
                  </template>

                  <template
                    v-else-if="isQualifyingType(activeSession.session_name)"
                  >
                    <td class="time-cell">{{ driver.q1 || "-" }}</td>
                    <td class="time-cell">{{ driver.q2 || "-" }}</td>
                    <td class="time-cell">{{ driver.q3 || "-" }}</td>
                  </template>

                  <template v-else>
                    <td class="status-cell">{{ driver.status }}</td>
                    <td class="pts-cell">{{ driver.points }}</td>
                  </template>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <aside class="insights-panel">
          <div
            v-if="activeSession.insights.podium"
            class="insight-card podium-card"
          >
            <h4>Podium</h4>
            <div class="podium-list">
              <div
                v-for="p in activeSession.insights.podium"
                :key="p.pos"
                class="podium-item"
              >
                <span class="pos" :class="'pos-' + p.pos">{{ p.pos }}</span>
                <span
                  class="team-stripe-small"
                  :style="{ backgroundColor: '#' + p.color }"
                ></span>
                <span class="driver">{{ p.abbreviation }}</span>
                <span class="team">{{ p.team }}</span>
              </div>
            </div>
          </div>

          <div
            v-if="activeSession.insights.pole"
            class="insight-card pole-card"
          >
            <h4>Pole Position</h4>
            <div class="info-row">
              <span class="driver">{{
                activeSession.insights.pole.full_name
              }}</span>
              <span class="value-highlight">{{
                activeSession.insights.pole.time
              }}</span>
            </div>
          </div>

          <div
            v-if="activeSession.insights.mileage_king"
            class="insight-card highlight"
          >
            <h4>Mileage King</h4>
            <div class="info-row">
              <span class="driver">{{
                activeSession.insights.mileage_king.abbreviation
              }}</span>
              <span class="value-highlight"
                >{{ activeSession.insights.mileage_king.laps }} Laps</span
              >
            </div>
          </div>

          <div
            v-if="activeSession.insights.fastest_lap"
            class="insight-card fl-card"
          >
            <h4>Fastest Lap</h4>
            <div class="info-row">
              <span class="driver">{{
                activeSession.insights.fastest_lap.abbreviation
              }}</span>
              <span class="value-highlight">{{
                activeSession.insights.fastest_lap.time
              }}</span>
            </div>
          </div>

          <div
            v-if="activeSession.insights.speed_king"
            class="insight-card speed-card"
          >
            <h4>Speed King</h4>
            <div class="info-row">
              <span class="driver">{{
                activeSession.insights.speed_king.abbreviation
              }}</span>
              <span class="value-highlight"
                >{{
                  activeSession.insights.speed_king.value.toFixed(1)
                }}
                km/h</span
              >
            </div>
          </div>

          <div
            v-if="activeSession.insights.sector_kings"
            class="insight-card sector-kings-card"
          >
            <h4>Sector Kings</h4>
            <div class="sector-grid">
              <template
                v-for="(king, sector) in activeSession.insights.sector_kings"
                :key="sector"
              >
                <span class="sector-label">{{ sector.toUpperCase() }}</span>
                <span class="sector-driver">{{ king.abbreviation }}</span>
                <span class="sector-time">{{ king.time }}</span>
              </template>
            </div>
          </div>

          <div
            v-if="activeSession.insights.winning_strategy"
            class="insight-card strategy-card"
          >
            <h4>Winning Strategy</h4>
            <div class="strategy-timeline">
              <div
                v-for="(stint, idx) in activeSession.insights.winning_strategy"
                :key="idx"
                class="strategy-stint"
                :style="{
                  backgroundColor: getTyreColor(stint.compound),
                  flex: stint.laps,
                }"
                :title="`${stint.compound}: ${stint.laps} Laps`"
              >
                <span class="lap-count" v-if="stint.laps > 5">{{
                  stint.laps
                }}</span>
              </div>
            </div>
          </div>

          <div
            v-if="activeSession.insights.incidents?.length > 0"
            class="insight-card incident-card"
          >
            <h4>Incidents</h4>
            <ul class="incident-list">
              <li
                v-for="(inc, idx) in activeSession.insights.incidents"
                :key="idx"
              >
                <span
                  class="type"
                  :class="inc.type.toLowerCase().replace(' ', '-')"
                  >{{ inc.type }}</span
                >
                <span class="time">T+{{ Math.floor(inc.time / 60) }}m</span>
              </li>
            </ul>
          </div>
        </aside>
      </div>
    </div>
  </div>
</template>

<style scoped>
.session-recap {
  color: var(--text-color);
  background: var(--card-bg-color);
  border-radius: 12px;
  padding: 2rem;
  border: 1px solid var(--border-color);
}

.recap-header {
  margin-bottom: 2rem;
}

.recap-header h1 {
  margin: 0;
  font-size: 2rem;
  color: var(--primary-color);
  text-transform: uppercase;
  letter-spacing: 1px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.badge.no-telemetry {
  font-size: 0.8rem;
  background-color: var(--accent-color);
  color: var(--primary-color);
  padding: 4px 8px;
  border-radius: 4px;
  border: 1px solid var(--primary-color);
  font-weight: 800;
  letter-spacing: 1px;
}

.header-meta {
  font-size: 0.95rem;
  opacity: 0.7;
  margin-top: 0.5rem;
  display: flex;
  align-items: center;
  font-weight: 500;
}

.divider {
  margin: 0 12px;
  opacity: 0.3;
}
.session-indicator {
  color: var(--primary-color);
  font-weight: 700;
}

.session-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 2rem;
  background: var(--item-bg-color);
  padding: 8px;
  border-radius: 10px;
}

button {
  background: transparent;
  border: 1px solid transparent;
  color: var(--text-color);
  padding: 0.6rem 1.2rem;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 700;
  font-size: 0.8rem;
  transition: all 0.2s ease;
  white-space: nowrap;
}

button:hover {
  background: rgba(255, 255, 255, 0.05);
}

button.active {
  background: var(--primary-color);
  color: #fff;
}

.recap-grid {
  display: grid;
  grid-template-columns: 1fr 340px;
  gap: 2.5rem;
}

.results-panel {
  background: var(--item-bg-color);
  border-radius: 10px;
  border: 1px solid var(--border-color);
  overflow: hidden;
}

.panel-header {
  padding: 1.25rem;
  border-bottom: 1px solid var(--border-color);
  background: rgba(0, 0, 0, 0.05);
}

.panel-header h3 {
  margin: 0;
  font-size: 1.1rem;
  border: none;
  padding: 0;
}

.table-container {
  overflow-x: auto;
  width: 100%;
  -webkit-overflow-scrolling: touch;
}

table {
  width: 100%;
  border-collapse: collapse;
}

th {
  text-align: left;
  padding: 1rem;
  background: rgba(0, 0, 0, 0.02);
  border-bottom: 1px solid var(--border-color);
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 1px;
  opacity: 0.6;
}

td {
  padding: 1rem;
  border-bottom: 1px solid var(--border-color);
  font-size: 0.95rem;
}

.pos-cell {
  width: 60px;
  text-align: center;
  font-weight: 800;
  color: var(--muted-text-color);
  font-family: "JetBrains Mono", monospace;
}

.driver-cell {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 220px;
}

.team-stripe {
  width: 6px;
  height: 28px;
  border-radius: 3px;
  flex-shrink: 0;
}
.abbr {
  font-weight: 800;
}
.full-name {
  opacity: 0.5;
  font-size: 0.85rem;
}
.time-cell {
  font-family: "JetBrains Mono", monospace;
  font-weight: 600;
  white-space: nowrap;
}

.status-cell {
  white-space: nowrap;
}

.insights-panel {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.insight-card {
  background: var(--item-bg-color);
  padding: 1.5rem;
  border-radius: 10px;
  border: 1px solid var(--border-color);
}

.insight-card h4 {
  margin: 0 0 1rem 0;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 1.5px;
  color: var(--muted-text-color);
}

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.value-highlight {
  font-family: "JetBrains Mono", monospace;
  color: var(--primary-color);
  font-weight: 700;
}

.insight-card.highlight {
  border-color: var(--primary-color);
  background: var(--accent-color);
}

.podium-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.podium-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.sector-grid {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 12px 0;
}

.sector-label {
  font-weight: 800;
  opacity: 0.6;
  font-size: 0.8rem;
  min-width: 30px;
  padding-right: 12px;
}

.sector-driver {
  font-weight: 700;
  font-size: 0.9rem;
}

.sector-time {
  font-family: "JetBrains Mono", monospace;
  color: var(--primary-color);
  font-weight: 700;
  font-size: 0.9rem;
  text-align: right;
  padding-left: 12px;
}

.strategy-timeline {
  display: flex;
  height: 24px;
  border-radius: 4px;
  overflow: hidden;
  border: 1px solid var(--border-color);
  background: var(--bg-color);
}
.strategy-stint {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  border-right: 1px solid rgba(0, 0, 0, 0.1);
}
.strategy-stint:last-child {
  border-right: none;
}
.strategy-stint .lap-count {
  font-size: 0.65rem;
  font-weight: 900;
  color: #000;
}
.strategy-stint[style*="#0000ff"] .lap-count {
  color: #fff;
}

.pos-1 {
  color: #ffd700;
  font-weight: 900;
}
.pos-2 {
  color: #c0c0c0;
  font-weight: 900;
}
.pos-3 {
  color: #cd7f32;
  font-weight: 900;
}

.incident-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.incident-list li {
  display: flex;
  justify-content: space-between;
  font-size: 0.85rem;
}

.type {
  padding: 2px 6px;
  border-radius: 4px;
  font-weight: 800;
  font-size: 0.7rem;
}

.type.safety-car {
  background: #facc15;
  color: #000;
}
.type.red-flag {
  background: #ef4444;
  color: #fff;
}

.loading-state {
  text-align: center;
  padding: 5rem;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 4px solid var(--border-color);
  border-top-color: var(--primary-color);
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 1.5rem;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 1100px) {
  .recap-grid {
    grid-template-columns: 1fr;
  }
}

/* --- Mobile Responsiveness --- */
@media (max-width: 768px) {
  .recap-container {
    padding: 0;
  }

  .session-header h2 {
    font-size: 1.5rem;
  }

  .session-header h3 {
    font-size: 0.9rem;
  }

  .card-header h4 {
    font-size: 0.9rem;
  }

  .driver-name {
    font-size: 1.2rem;
  }

  .insight-value {
    font-size: 1.5rem;
  }
}
</style>
