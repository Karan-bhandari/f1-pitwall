<script setup>
import { ref, computed, onMounted, watch } from "vue";
import { getStandings } from "../api";

const props = defineProps({
  year: { type: Number, required: true },
});

const loading = ref(true);
const error = ref(null);
const data = ref(null);
const activeTab = ref("drivers");

const hasConstructors = computed(() => {
  return data.value?.constructors?.length > 0;
});

const maxDriverPoints = computed(() => {
  if (!data.value?.drivers?.length) return 1;
  return Math.max(...data.value.drivers.map((d) => d.points), 1);
});

const maxConstructorPoints = computed(() => {
  if (!data.value?.constructors?.length) return 1;
  return Math.max(...data.value.constructors.map((c) => c.points), 1);
});

const roundLabel = computed(() => {
  if (!data.value) return "";
  const parts = [];
  if (data.value.round) parts.push(`Round ${data.value.round}`);
  if (data.value.round_name) parts.push(data.value.round_name);
  return parts.length ? `After ${parts.join(" — ")}` : "";
});

const fetchData = async () => {
  if (!props.year) return;
  loading.value = true;
  error.value = null;
  try {
    data.value = await getStandings(props.year);
    // Default to drivers tab; if no constructors, stay on drivers
    if (!data.value?.constructors?.length) {
      activeTab.value = "drivers";
    }
  } catch (e) {
    console.error("[SeasonOverview] Fetch Error:", e);
    error.value = "Failed to load standings.";
  } finally {
    loading.value = false;
  }
};

onMounted(fetchData);
watch(() => props.year, fetchData);

const barWidth = (points, max) => {
  if (max <= 0) return "0%";
  return `${Math.max((points / max) * 100, 2)}%`;
};
</script>

<template>
  <div class="season-overview">
    <!-- Header -->
    <div class="overview-header">
      <div class="header-title">
        <span class="trophy">🏆</span>
        <h3>{{ year }} SEASON STANDINGS</h3>
      </div>
      <p v-if="roundLabel" class="round-label">{{ roundLabel }}</p>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <p>Loading standings...</p>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="error-state">
      <p>{{ error }}</p>
    </div>

    <!-- Content -->
    <div v-else-if="data" class="standings-content">
      <!-- Tabs -->
      <div class="tab-bar">
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'drivers' }"
          @click="activeTab = 'drivers'"
        >
          DRIVERS
        </button>
        <button
          v-if="hasConstructors"
          class="tab-btn"
          :class="{ active: activeTab === 'constructors' }"
          @click="activeTab = 'constructors'"
        >
          CONSTRUCTORS
        </button>
      </div>

      <!-- Driver Standings -->
      <div v-if="activeTab === 'drivers'" class="standings-list">
        <div
          v-for="driver in data.drivers"
          :key="driver.position"
          class="standing-row"
          :class="{
            podium: driver.position <= 3,
            'pos-gold': driver.position === 1,
            'pos-silver': driver.position === 2,
            'pos-bronze': driver.position === 3,
          }"
        >
          <span class="pos" :class="'pos-' + driver.position">{{
            driver.position
          }}</span>
          <span
            class="team-indicator"
            :style="{ backgroundColor: '#' + driver.team_color }"
          ></span>
          <div class="driver-info">
            <span class="driver-code">{{ driver.driver_code }}</span>
            <span class="driver-name">{{ driver.driver_name }}</span>
            <span class="team-name">{{ driver.team_name }}</span>
          </div>
          <div class="points-area">
            <div class="points-bar-container">
              <div
                class="points-bar"
                :style="{
                  width: barWidth(driver.points, maxDriverPoints),
                  backgroundColor: '#' + driver.team_color,
                }"
              ></div>
            </div>
            <span class="points-value">{{ driver.points }}</span>
            <span class="wins-badge" :class="{ empty: driver.wins <= 0 }">
              <template v-if="driver.wins > 0">{{ driver.wins }}W</template>
            </span>
          </div>
        </div>
      </div>

      <!-- Constructor Standings -->
      <div v-if="activeTab === 'constructors'" class="standings-list">
        <div
          v-for="team in data.constructors"
          :key="team.position"
          class="standing-row"
          :class="{
            podium: team.position <= 3,
            'pos-gold': team.position === 1,
            'pos-silver': team.position === 2,
            'pos-bronze': team.position === 3,
          }"
        >
          <span class="pos" :class="'pos-' + team.position">{{
            team.position
          }}</span>
          <span
            class="team-indicator"
            :style="{ backgroundColor: '#' + team.team_color }"
          ></span>
          <div class="driver-info">
            <span class="driver-code">{{ team.constructor_name }}</span>
          </div>
          <div class="points-area">
            <div class="points-bar-container">
              <div
                class="points-bar"
                :style="{
                  width: barWidth(team.points, maxConstructorPoints),
                  backgroundColor: '#' + team.team_color,
                }"
              ></div>
            </div>
            <span class="points-value">{{ team.points }}</span>
            <span class="wins-badge" :class="{ empty: team.wins <= 0 }">
              <template v-if="team.wins > 0">{{ team.wins }}W</template>
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.season-overview {
  margin-top: 1.5rem;
  animation: fadeIn 0.4s ease;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.overview-header {
  margin-bottom: 1.25rem;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.header-title .trophy {
  font-size: 1.4rem;
}

.header-title h3 {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--text-color);
}

.round-label {
  margin: 0.25rem 0 0 2rem;
  font-size: 0.8rem;
  color: var(--muted-text-color);
  font-style: italic;
}

/* Tabs */
.tab-bar {
  display: flex;
  gap: 0;
  margin-bottom: 1rem;
  border-bottom: 2px solid var(--border-color);
}

.tab-btn {
  padding: 0.6rem 1.5rem;
  border: none;
  background: transparent;
  color: var(--muted-text-color);
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  cursor: pointer;
  position: relative;
  transition: color 0.2s ease;
}

.tab-btn:hover {
  color: var(--text-color);
}

.tab-btn.active {
  color: var(--primary-color);
}

.tab-btn.active::after {
  content: "";
  position: absolute;
  bottom: -2px;
  left: 0;
  right: 0;
  height: 2px;
  background-color: var(--primary-color);
}

/* Standings List */
.standings-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.standing-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.55rem 0.75rem;
  border-radius: 6px;
  background-color: var(--item-bg-color);
  transition: background-color 0.15s ease;
}

.standing-row:hover {
  background-color: var(--accent-color);
}

.standing-row.podium {
  /* No extra background — individual podium positions use gradient tints */
}

/* Position */
.pos {
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 1.6rem;
  height: 1.6rem;
  border-radius: 4px;
  font-family: "JetBrains Mono", monospace;
  font-size: 0.7rem;
  font-weight: 800;
  color: var(--muted-text-color);
}

/*
 * Podium rows: extend the medal color from the position badge into
 * a faint left-to-right gradient on the row background. The tint
 * fades to transparent so it doesn't fight the team-colored bars.
 */
.standing-row.pos-gold {
  background: linear-gradient(
    90deg,
    rgba(255, 215, 0, 0.12) 0%,
    transparent 50%
  );
}
.standing-row.pos-silver {
  background: linear-gradient(
    90deg,
    rgba(192, 192, 192, 0.12) 0%,
    transparent 50%
  );
}
.standing-row.pos-bronze {
  background: linear-gradient(
    90deg,
    rgba(205, 127, 50, 0.1) 0%,
    transparent 50%
  );
}

.pos-1 {
  background-color: rgba(255, 215, 0, 0.2);
  color: #d4a800;
}
.pos-2 {
  background-color: rgba(192, 192, 192, 0.2);
  color: #9a9a9a;
}
.pos-3 {
  background-color: rgba(205, 127, 50, 0.2);
  color: #b87333;
}

/* Team color indicator */
.team-indicator {
  width: 4px;
  height: 1.6rem;
  border-radius: 2px;
  flex-shrink: 0;
}

/* Driver info */
.driver-info {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  min-width: 0;
  flex-shrink: 0;
  width: 280px;
}

.driver-code {
  font-family: "JetBrains Mono", monospace;
  font-size: 0.8rem;
  font-weight: 800;
  white-space: nowrap;
}

.driver-name {
  font-size: 0.75rem;
  color: var(--muted-text-color);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.team-name {
  font-size: 0.65rem;
  color: var(--muted-text-color);
  opacity: 0.7;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Points area */
.points-area {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex: 1;
  min-width: 0;
}

.points-bar-container {
  flex: 1;
  height: 6px;
  background: var(--border-color);
  border-radius: 3px;
  overflow: hidden;
}

.points-bar {
  height: 100%;
  border-radius: 3px;
  transition: width 0.6s cubic-bezier(0.25, 0.46, 0.45, 0.94);
  opacity: 0.85;
}

.points-value {
  font-family: "JetBrains Mono", monospace;
  font-size: 0.8rem;
  font-weight: 700;
  min-width: 3rem;
  text-align: right;
}

.wins-badge {
  font-family: "JetBrains Mono", monospace;
  font-size: 0.6rem;
  font-weight: 700;
  background: var(--primary-color);
  color: #fff;
  padding: 0.1rem 0.35rem;
  border-radius: 3px;
  min-width: 1.8rem;
  text-align: center;
  visibility: visible;
}

.wins-badge.empty {
  visibility: hidden;
}

/* Loading & Error */
.loading-state,
.error-state {
  text-align: center;
  padding: 3rem 1rem;
  color: var(--muted-text-color);
}

.spinner {
  width: 24px;
  height: 24px;
  border: 3px solid var(--border-color);
  border-top-color: var(--primary-color);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin: 0 auto 1rem;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.error-state p {
  color: var(--primary-color);
}

/* Mobile */
@media (max-width: 768px) {
  .driver-info {
    width: auto;
    flex-shrink: 1;
  }

  .driver-name,
  .team-name {
    display: none;
  }

  .driver-code {
    font-size: 0.75rem;
  }

  .points-bar-container {
    display: none;
  }

  .standing-row {
    padding: 0.45rem 0.5rem;
  }
}
</style>
