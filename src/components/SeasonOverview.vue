<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from "vue";
import { getStandings } from "../api";
import F1Icon from "@/components/F1Icon.vue";

const props = defineProps({
  year: { type: Number, required: true },
});

const loading = ref(true);
const error = ref(null);
const data = ref(null);
const activeTab = ref("drivers");
const showScenariosModal = ref(false);
const scenarioTab = ref("wdc"); // 'wdc' or 'wcc'

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

const seasonProgressLabel = computed(() => {
  if (!data.value) return "";
  const parts = [];
  if (data.value.round && data.value.total_rounds) {
    parts.push(`Round ${data.value.round} of ${data.value.total_rounds}`);
  } else if (data.value.round) {
    parts.push(`Round ${data.value.round}`);
  }
  if (data.value.remaining_rounds && data.value.remaining_rounds > 0) {
    parts.push(
      `${data.value.remaining_rounds} round${data.value.remaining_rounds > 1 ? "s" : ""} remaining`,
    );
  }
  return parts.join(" • ");
});

const showScenariosButton = computed(() => {
  const currentYear = new Date().getFullYear();
  if (props.year !== currentYear) return false;
  if (!data.value?.scenarios?.is_second_half) return false;
  return (
    !data.value.wdc_champion ||
    (hasConstructors.value && !data.value.wcc_champion)
  );
});

const activeScenarioData = computed(() => {
  if (!data.value?.scenarios) return null;
  return scenarioTab.value === "wdc"
    ? data.value.scenarios.wdc
    : data.value.scenarios.wcc;
});

const maxPointsForActiveScenario = computed(() => {
  if (!data.value?.scenarios) return 0;
  return scenarioTab.value === "wdc"
    ? data.value.scenarios.max_driver_points_remaining
    : data.value.scenarios.max_constructor_points_remaining;
});

const leaderContender = computed(() => {
  const contenders = activeScenarioData.value?.contenders;
  return contenders && contenders.length > 0 ? contenders[0] : null;
});

const challengerContenders = computed(() => {
  const contenders = activeScenarioData.value?.contenders;
  if (!contenders || contenders.length <= 1) return [];
  return contenders.slice(1);
});

const openScenariosModal = () => {
  if (
    data.value?.wdc_champion &&
    !data.value?.wcc_champion &&
    data.value?.scenarios?.wcc
  ) {
    scenarioTab.value = "wcc";
  } else {
    scenarioTab.value = "wdc";
  }
  showScenariosModal.value = true;
};

const closeScenariosModal = () => {
  showScenariosModal.value = false;
};

const handleKeyDown = (e) => {
  if (e.key === "Escape" && showScenariosModal.value) {
    closeScenariosModal();
  }
};

const fetchData = async () => {
  if (!props.year) return;
  loading.value = true;
  error.value = null;
  try {
    data.value = await getStandings(props.year);
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

onMounted(() => {
  fetchData();
  window.addEventListener("keydown", handleKeyDown);
});

onUnmounted(() => {
  window.removeEventListener("keydown", handleKeyDown);
  document.body.style.overflow = "";
});

watch(showScenariosModal, (isOpen) => {
  document.body.style.overflow = isOpen ? "hidden" : "";
});

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
      <div class="header-left">
        <div class="header-title">
          <F1Icon name="trophy" :size="20" class="header-icon" />
          <h3>{{ year }} SEASON STANDINGS</h3>
        </div>
        <div class="header-sub">
          <span v-if="roundLabel" class="round-label">{{ roundLabel }}</span>
          <span v-if="seasonProgressLabel" class="season-progress-badge">
            {{ seasonProgressLabel }}
          </span>
        </div>
      </div>
      <div class="header-actions">
        <button
          v-if="showScenariosButton"
          class="scenarios-btn"
          @click="openScenariosModal"
          title="Explore Title Fight Clinch Scenarios"
        >
          <F1Icon name="calculator" :size="16" />
          <span class="btn-text">Championship Scenarios</span>
        </button>
      </div>
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
      <!-- World Champions Hero Banner (WDC & WCC) -->
      <div v-if="data.wdc_champion || data.wcc_champion" class="champions-hero">
        <!-- WDC Champion Card -->
        <div
          v-if="data.wdc_champion"
          class="champion-card wdc-card"
          :style="{
            '--champion-color':
              '#' + (data.wdc_champion.team_color || 'e10600'),
          }"
        >
          <div class="champion-ribbon">
            <F1Icon name="crown" :size="16" class="crown-svg" />
            <span class="ribbon-text">{{ year }} WORLD DRIVERS' CHAMPION</span>
          </div>
          <div class="champion-body">
            <div
              class="champion-avatar-bar"
              :style="{
                backgroundColor:
                  '#' + (data.wdc_champion.team_color || 'e10600'),
              }"
            ></div>
            <div class="champion-details">
              <div class="champion-name-row">
                <span class="champion-code">{{
                  data.wdc_champion.driver_code
                }}</span>
                <span class="champion-name">{{
                  data.wdc_champion.driver_name
                }}</span>
              </div>
              <div class="champion-team">{{ data.wdc_champion.team_name }}</div>
              <div v-if="data.wdc_champion.clinched_early" class="clinch-badge">
                <F1Icon name="sparkles" :size="14" /> Clinched with
                {{ data.wdc_champion.rounds_to_spare }} round{{
                  data.wdc_champion.rounds_to_spare > 1 ? "s" : ""
                }}
                remaining
              </div>
            </div>
            <div class="champion-stats">
              <div class="stat-box">
                <span class="stat-num">{{ data.wdc_champion.points }}</span>
                <span class="stat-lbl">PTS</span>
              </div>
              <div v-if="data.wdc_champion.wins > 0" class="stat-box wins">
                <span class="stat-num">{{ data.wdc_champion.wins }}</span>
                <span class="stat-lbl">WINS</span>
              </div>
            </div>
          </div>
        </div>

        <!-- WCC Champion Card -->
        <div
          v-if="data.wcc_champion"
          class="champion-card wcc-card"
          :style="{
            '--champion-color':
              '#' + (data.wcc_champion.team_color || 'e10600'),
          }"
        >
          <div class="champion-ribbon">
            <F1Icon name="crown" :size="16" class="crown-svg" />
            <span class="ribbon-text"
              >{{ year }} WORLD CONSTRUCTORS' CHAMPION</span
            >
          </div>
          <div class="champion-body">
            <div
              class="champion-avatar-bar"
              :style="{
                backgroundColor:
                  '#' + (data.wcc_champion.team_color || 'e10600'),
              }"
            ></div>
            <div class="champion-details">
              <div class="champion-name-row">
                <span class="champion-name constructor">{{
                  data.wcc_champion.constructor_name
                }}</span>
              </div>
              <div class="champion-team">Constructors' Championship</div>
              <div v-if="data.wcc_champion.clinched_early" class="clinch-badge">
                <F1Icon name="sparkles" :size="14" /> Clinched with
                {{ data.wcc_champion.rounds_to_spare }} round{{
                  data.wcc_champion.rounds_to_spare > 1 ? "s" : ""
                }}
                remaining
              </div>
            </div>
            <div class="champion-stats">
              <div class="stat-box">
                <span class="stat-num">{{ data.wcc_champion.points }}</span>
                <span class="stat-lbl">PTS</span>
              </div>
              <div v-if="data.wcc_champion.wins > 0" class="stat-box wins">
                <span class="stat-num">{{ data.wcc_champion.wins }}</span>
                <span class="stat-lbl">WINS</span>
              </div>
            </div>
          </div>
        </div>
      </div>

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
            <span v-if="driver.is_champion" class="champion-tag"
              ><F1Icon name="trophy" :size="12" /> CHAMPION</span
            >
          </div>
          <div class="points-bar-track">
            <div
              class="points-bar"
              :style="{
                width: barWidth(driver.points, maxDriverPoints),
                backgroundColor: '#' + driver.team_color,
              }"
            ></div>
          </div>
          <div class="points-area">
            <span
              v-if="driver.position > 1 && driver.gap_to_leader !== undefined"
              class="gap-value"
              title="Gap to Leader"
            >
              -{{ driver.gap_to_leader }}
            </span>
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
            <span v-if="team.is_champion" class="champion-tag"
              ><F1Icon name="trophy" :size="12" /> CHAMPION</span
            >
          </div>
          <div class="points-bar-track">
            <div
              class="points-bar"
              :style="{
                width: barWidth(team.points, maxConstructorPoints),
                backgroundColor: '#' + team.team_color,
              }"
            ></div>
          </div>
          <div class="points-area">
            <span
              v-if="team.position > 1 && team.gap_to_leader !== undefined"
              class="gap-value"
              title="Gap to Leader"
            >
              -{{ team.gap_to_leader }}
            </span>
            <span class="points-value">{{ team.points }}</span>
            <span class="wins-badge" :class="{ empty: team.wins <= 0 }">
              <template v-if="team.wins > 0">{{ team.wins }}W</template>
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- Championship Scenarios Modal -->
    <Teleport to="body">
      <Transition name="modal-fade">
        <div
          v-if="showScenariosModal"
          class="modal-backdrop"
          @click.self="closeScenariosModal"
        >
          <div class="scenarios-modal" role="dialog" aria-modal="true">
            <!-- Modal Header -->
            <div class="modal-header">
              <div class="modal-title-group">
                <F1Icon name="calculator" :size="24" class="modal-icon-svg" />
                <div class="modal-title-texts">
                  <h4>{{ year }} Championship Scenarios</h4>
                  <p class="modal-subtitle">
                    Mathematical clinch paths & challenger comeback math
                  </p>
                </div>
              </div>
              <button
                class="modal-close-btn"
                @click="closeScenariosModal"
                aria-label="Close modal"
              >
                <F1Icon name="close" :size="16" />
              </button>
            </div>

            <!-- WDC / WCC Toggle (if constructors exist) -->
            <div v-if="data?.scenarios?.wcc" class="scenario-toggle-bar">
              <button
                class="scenario-toggle-btn"
                :class="{ active: scenarioTab === 'wdc' }"
                @click="scenarioTab = 'wdc'"
              >
                <F1Icon name="helmet" :size="16" /> Drivers' Championship (WDC)
              </button>
              <button
                class="scenario-toggle-btn"
                :class="{ active: scenarioTab === 'wcc' }"
                @click="scenarioTab = 'wcc'"
              >
                <F1Icon name="wrench" :size="16" /> Constructors' Championship
                (WCC)
              </button>
            </div>

            <!-- Scenario Content -->
            <div v-if="activeScenarioData" class="modal-body">
              <!-- Summary Pills -->
              <div class="scenario-summary-pills">
                <div class="summary-pill">
                  <span class="pill-label">REMAINING ROUNDS</span>
                  <span class="pill-value">
                    {{ data.scenarios.remaining_rounds }} GP{{
                      data.scenarios.remaining_rounds > 1 ? "s" : ""
                    }}
                    <span
                      v-if="data.scenarios.remaining_sprints > 0"
                      class="sprint-sub"
                    >
                      + {{ data.scenarios.remaining_sprints }} Sprint{{
                        data.scenarios.remaining_sprints > 1 ? "s" : ""
                      }}
                    </span>
                  </span>
                </div>
                <div class="summary-pill">
                  <span class="pill-label">MAX POINTS ON TABLE</span>
                  <span class="pill-value highlight">
                    {{ maxPointsForActiveScenario }} pts
                  </span>
                </div>
                <div class="summary-pill">
                  <span class="pill-label">CONTENDERS ALIVE</span>
                  <span class="pill-value">
                    {{ activeScenarioData.contenders_count }} /
                    {{ activeScenarioData.total_competitors }}
                  </span>
                </div>
              </div>

              <!-- Clinched Banner -->
              <div v-if="activeScenarioData.clinched" class="clinched-card">
                <F1Icon name="trophy" :size="24" class="clinched-icon-svg" />
                <div>
                  <h5>Championship Mathematically Clinched</h5>
                  <p>
                    The title has already been secured and cannot be overturned.
                  </p>
                </div>
              </div>

              <div v-else class="scenarios-flow">
                <!-- Leader's Path to Clinch (P1) -->
                <div v-if="leaderContender" class="section-card leader-card">
                  <div class="section-card-header">
                    <span class="badge-p1">P1</span>
                    <span class="section-card-title"
                      >LEADER'S PATH TO CLINCH</span
                    >
                    <span
                      v-if="leaderContender.can_clinch_next_round"
                      class="clinch-alert-badge"
                    >
                      <F1Icon name="bolt" :size="14" /> Clinch Opportunity Next
                      Race ({{
                        data.scenarios.next_round_name || "Next Round"
                      }})
                    </span>
                  </div>

                  <div class="contender-profile">
                    <div class="profile-left">
                      <span
                        class="profile-color-bar"
                        :style="{
                          backgroundColor: '#' + leaderContender.team_color,
                        }"
                      ></span>
                      <div class="profile-identity">
                        <div class="code-and-name">
                          <span class="profile-code">{{
                            leaderContender.code
                          }}</span>
                          <span class="profile-name">{{
                            leaderContender.name
                          }}</span>
                        </div>
                        <span
                          v-if="
                            leaderContender.team_name &&
                            leaderContender.team_name !== leaderContender.name
                          "
                          class="profile-team"
                        >
                          {{ leaderContender.team_name }}
                        </span>
                      </div>
                    </div>
                    <div class="profile-stats">
                      <div class="stat-pill">
                        <span class="stat-pill-label">PTS</span>
                        <span class="stat-pill-val">{{
                          leaderContender.points
                        }}</span>
                      </div>
                      <div class="stat-pill">
                        <span class="stat-pill-label">WINS</span>
                        <span class="stat-pill-val"
                          >{{ leaderContender.wins }}W</span
                        >
                      </div>
                      <div class="stat-pill highlight">
                        <span class="stat-pill-label">PTS TO CLINCH</span>
                        <span class="stat-pill-val">{{
                          leaderContender.points_needed_to_clinch
                        }}</span>
                      </div>
                    </div>
                  </div>

                  <div class="scenario-callout leader-callout">
                    <F1Icon name="target" :size="18" class="callout-icon-svg" />
                    <span class="callout-text">{{
                      leaderContender.scenario_text
                    }}</span>
                  </div>
                </div>

                <!-- Challengers' Comeback Math (P2+) -->
                <div
                  v-if="challengerContenders.length > 0"
                  class="section-card challengers-card"
                >
                  <div class="section-card-header">
                    <span class="section-card-title">
                      CHALLENGERS' COMEBACK MATH ({{
                        challengerContenders.length
                      }})
                    </span>
                  </div>

                  <div class="challengers-list">
                    <div
                      v-for="challenger in challengerContenders"
                      :key="challenger.position"
                      class="challenger-row"
                    >
                      <div class="challenger-header">
                        <div class="challenger-id">
                          <span class="pos-badge"
                            >P{{ challenger.position }}</span
                          >
                          <span
                            class="challenger-bar"
                            :style="{
                              backgroundColor: '#' + challenger.team_color,
                            }"
                          ></span>
                          <div class="challenger-titles">
                            <span class="challenger-code">{{
                              challenger.code
                            }}</span>
                            <span class="challenger-name">{{
                              challenger.name
                            }}</span>
                          </div>
                        </div>
                        <div class="challenger-metrics">
                          <div class="metric-pill deficit">
                            <span class="metric-lbl">DEFICIT</span>
                            <span class="metric-val"
                              >-{{ challenger.gap_to_leader }} pts</span
                            >
                          </div>
                          <div class="metric-pill swing">
                            <span class="metric-lbl">REQ. SWING</span>
                            <span class="metric-val"
                              >+{{
                                challenger.avg_swing_needed_per_round
                              }}
                              pts/rd</span
                            >
                          </div>
                          <div class="metric-pill ceiling">
                            <span class="metric-lbl">MAX CEILING</span>
                            <span class="metric-val"
                              >{{ challenger.max_possible_points }} pts</span
                            >
                          </div>
                        </div>
                      </div>
                      <div class="scenario-callout challenger-callout">
                        <F1Icon
                          name="chart"
                          :size="18"
                          class="callout-icon-svg"
                        />
                        <span class="callout-text">{{
                          challenger.scenario_text
                        }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Modal Footer -->
            <div class="modal-footer">
              <p class="scenarios-disclaimer">
                * Calculations reflect official FIA points rules ({{
                  year >= 2025
                    ? "25 pts GP, FL point abolished"
                    : year >= 2019
                      ? "25 pts GP + 1 FL point"
                      : "25 pts GP"
                }}).
              </p>
              <button class="footer-close-btn" @click="closeScenariosModal">
                Close
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
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

/* Header */
.overview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1.5rem;
  gap: 1rem;
  flex-wrap: wrap;
}

.header-left {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
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
  font-size: 1.15rem;
  font-weight: 800;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--text-color);
}

.header-sub {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.round-label {
  margin: 0;
  font-size: 0.8rem;
  color: var(--muted-text-color);
  font-style: italic;
}

.season-progress-badge {
  font-family: "JetBrains Mono", monospace;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--primary-color);
  background-color: var(--accent-color);
  padding: 0.2rem 0.55rem;
  border-radius: 4px;
}

/* Scenarios Action Button */
.header-actions {
  display: flex;
  align-items: center;
}

.scenarios-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  background: linear-gradient(
    135deg,
    rgba(225, 6, 0, 0.12) 0%,
    rgba(225, 6, 0, 0.04) 100%
  );
  border: 1px solid var(--primary-color);
  color: var(--primary-color);
  font-weight: 700;
  font-size: 0.85rem;
  padding: 0.5rem 0.95rem;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 0 2px 8px rgba(225, 6, 0, 0.12);
}

.scenarios-btn:hover {
  background-color: var(--primary-color);
  color: #fff;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(225, 6, 0, 0.25);
}

.btn-icon {
  font-size: 1rem;
}

/* World Champions Hero Banner */
.champions-hero {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 1.25rem;
  margin-bottom: 1.75rem;
}

.champion-card {
  display: flex;
  flex-direction: column;
  background: var(--item-bg-color);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  overflow: hidden;
  position: relative;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease;
}

.champion-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.1);
}

.champion-ribbon {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  background: linear-gradient(
    90deg,
    rgba(255, 215, 0, 0.25) 0%,
    rgba(255, 215, 0, 0.05) 100%
  );
  padding: 0.45rem 0.85rem;
  border-bottom: 1px solid rgba(255, 215, 0, 0.3);
}

.crown-svg {
  color: #d4a800;
  flex-shrink: 0;
}

.ribbon-text {
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  color: #d4a800;
  text-transform: uppercase;
  line-height: 1;
}

.champion-body {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.15rem;
  gap: 1rem;
}

.champion-avatar-bar {
  align-self: stretch;
  min-height: 2.75rem;
  width: 5px;
  border-radius: 3px;
  flex-shrink: 0;
}

.champion-details {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 0.25rem;
  flex: 1;
  min-width: 0;
}

.champion-name-row {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.champion-code {
  font-family: "JetBrains Mono", monospace;
  font-size: 1.1rem;
  font-weight: 900;
  color: var(--text-color);
}

.champion-name {
  font-size: 1.05rem;
  font-weight: 800;
  color: var(--text-color);
  line-height: 1.25;
}

.champion-name.constructor {
  font-size: 1.15rem;
}

.champion-team {
  font-size: 0.8rem;
  color: var(--muted-text-color);
}

.clinch-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  align-self: flex-start;
  line-height: 1.2;
  font-family: "JetBrains Mono", monospace;
  font-size: 0.68rem;
  font-weight: 700;
  color: #d4a800;
  background: rgba(255, 215, 0, 0.12);
  border: 1px solid rgba(255, 215, 0, 0.3);
  padding: 0.15rem 0.45rem;
  border-radius: 4px;
}

.champion-stats {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-shrink: 0;
}

.stat-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: var(--card-bg-color, var(--bg-color));
  border: 1px solid var(--border-color);
  padding: 0.45rem 0.7rem;
  border-radius: 6px;
  min-width: 3.75rem;
}

.stat-box.wins {
  background: rgba(225, 6, 0, 0.08);
  border-color: rgba(225, 6, 0, 0.2);
}

.stat-num {
  font-family: "JetBrains Mono", monospace;
  font-size: 1.05rem;
  font-weight: 800;
  color: var(--text-color);
  line-height: 1.1;
}

.stat-lbl {
  font-size: 0.6rem;
  font-weight: 700;
  color: var(--muted-text-color);
  letter-spacing: 0.05em;
  margin-top: 0.15rem;
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
  /* Gradient tints below */
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
  background-color: rgba(255, 215, 0, 0.22);
  color: #9a6b00;
}
.pos-2 {
  background-color: rgba(148, 163, 184, 0.22);
  color: #475569;
}
.pos-3 {
  background-color: rgba(205, 127, 50, 0.22);
  color: #9a4e12;
}

:global(html[data-theme="dark"]) .pos-1 {
  color: #ffd700;
}
:global(html[data-theme="dark"]) .pos-2 {
  color: #cbd5e1;
}
:global(html[data-theme="dark"]) .pos-3 {
  color: #e09145;
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
  gap: 0.6rem;
  min-width: 0;
  flex-shrink: 0;
  width: clamp(300px, 36vw, 420px);
}

.driver-code {
  font-family: "JetBrains Mono", monospace;
  font-size: 0.8rem;
  font-weight: 800;
  white-space: nowrap;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}

.driver-name {
  font-size: 0.78rem;
  font-weight: 500;
  color: var(--text-color);
  white-space: nowrap;
  flex-shrink: 0;
}

.team-name {
  font-size: 0.65rem;
  color: var(--muted-text-color);
  opacity: 0.7;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.champion-tag {
  font-family: "JetBrains Mono", monospace;
  font-size: 0.62rem;
  font-weight: 800;
  background: linear-gradient(135deg, #ffd700 0%, #d4a800 100%);
  color: #000;
  padding: 0.12rem 0.45rem;
  border-radius: 3px;
  letter-spacing: 0.04em;
  white-space: nowrap;
  box-shadow: 0 1px 4px rgba(212, 168, 0, 0.35);
}

/* Points area */
.points-area {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-shrink: 0;
}

.gap-value {
  font-family: "JetBrains Mono", monospace;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--muted-text-color);
  min-width: 3.5rem;
  text-align: right;
  opacity: 0.85;
}

.points-bar-track {
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

/* --- Championship Scenarios Modal --- */
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.65);
  backdrop-filter: blur(4px);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.5rem;
}

.scenarios-modal {
  background: var(--card-bg-color, var(--item-bg-color));
  color: var(--text-color);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  width: 100%;
  max-width: 780px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.35);
  animation: modalScaleUp 0.25s ease;
}

@keyframes modalScaleUp {
  from {
    opacity: 0;
    transform: scale(0.96);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.2s ease;
}

.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}

/* Modal Header */
.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid var(--border-color);
  background: var(--item-bg-color);
}

.modal-title-group {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.modal-icon {
  font-size: 1.5rem;
}

.modal-title-texts h4 {
  margin: 0;
  font-size: 1.15rem;
  font-weight: 800;
  color: var(--text-color);
}

.modal-subtitle {
  margin: 0.15rem 0 0;
  font-size: 0.75rem;
  color: var(--muted-text-color);
}

.modal-close-btn {
  background: transparent;
  border: none;
  font-size: 1.25rem;
  color: var(--muted-text-color);
  cursor: pointer;
  padding: 0.4rem 0.6rem;
  border-radius: 6px;
  transition: all 0.15s ease;
}

.modal-close-btn:hover {
  color: var(--text-color);
  background: var(--accent-color);
}

/* Scenario Toggle Bar */
.scenario-toggle-bar {
  display: flex;
  background: var(--item-bg-color);
  border-bottom: 1px solid var(--border-color);
  padding: 0.35rem 1.5rem;
  gap: 0.5rem;
}

.scenario-toggle-btn {
  padding: 0.5rem 1rem;
  border: 1px solid transparent;
  background: transparent;
  color: var(--muted-text-color);
  font-weight: 700;
  font-size: 0.8rem;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.scenario-toggle-btn:hover {
  color: var(--text-color);
}

.scenario-toggle-btn.active {
  color: var(--primary-color);
  background: var(--card-bg-color, var(--bg-color));
  border-color: var(--border-color);
}

/* Modal Body */
.modal-body {
  padding: 1.25rem 1.5rem;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

/* Summary Pills */
.scenario-summary-pills {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 0.75rem;
}

.summary-pill {
  background: var(--item-bg-color);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 0.65rem 0.85rem;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.pill-label {
  font-size: 0.65rem;
  font-weight: 800;
  letter-spacing: 0.05em;
  color: var(--muted-text-color);
}

.pill-value {
  font-family: "JetBrains Mono", monospace;
  font-size: 1.05rem;
  font-weight: 800;
  color: var(--text-color);
}

.pill-value.highlight {
  color: var(--primary-color);
}

.sprint-sub {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--muted-text-color);
}

/* Clinched card */
.clinched-card {
  display: flex;
  align-items: center;
  gap: 1rem;
  background: rgba(255, 215, 0, 0.12);
  border: 1px solid rgba(255, 215, 0, 0.35);
  border-radius: 8px;
  padding: 1.25rem;
}

.clinched-icon {
  font-size: 2rem;
}

.clinched-card h5 {
  margin: 0;
  font-size: 1.05rem;
  color: #d4a800;
  font-weight: 800;
}

.clinched-card p {
  margin: 0.25rem 0 0;
  font-size: 0.82rem;
  color: var(--text-color);
}

/* Scenarios Flow */
.scenarios-flow {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.section-card {
  background: var(--item-bg-color);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  overflow: hidden;
}

.section-card-header {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.6rem 0.85rem;
  background: rgba(0, 0, 0, 0.03);
  border-bottom: 1px solid var(--border-color);
  flex-wrap: wrap;
}

.badge-p1 {
  background: #d4a800;
  color: #000;
  font-family: "JetBrains Mono", monospace;
  font-size: 0.65rem;
  font-weight: 900;
  padding: 0.15rem 0.4rem;
  border-radius: 3px;
}

.section-card-title {
  font-size: 0.75rem;
  font-weight: 800;
  letter-spacing: 0.05em;
  color: var(--text-color);
}

.clinch-alert-badge {
  font-family: "JetBrains Mono", monospace;
  font-size: 0.68rem;
  font-weight: 700;
  color: #fff;
  background: var(--primary-color);
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  margin-left: auto;
  box-shadow: 0 1px 6px rgba(225, 6, 0, 0.3);
}

/* Contender Profile */
.contender-profile {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.85rem;
  gap: 1rem;
  flex-wrap: wrap;
}

.profile-left {
  display: flex;
  align-items: center;
  gap: 0.65rem;
}

.profile-color-bar {
  width: 4px;
  height: 2.2rem;
  border-radius: 2px;
}

.code-and-name {
  display: flex;
  align-items: baseline;
  gap: 0.45rem;
}

.profile-code {
  font-family: "JetBrains Mono", monospace;
  font-weight: 800;
  font-size: 0.95rem;
  color: var(--text-color);
}

.profile-name {
  font-weight: 700;
  font-size: 0.9rem;
  color: var(--text-color);
}

.profile-team {
  font-size: 0.75rem;
  color: var(--muted-text-color);
}

.profile-stats {
  display: flex;
  gap: 0.5rem;
}

.stat-pill {
  display: flex;
  flex-direction: column;
  align-items: center;
  background: var(--card-bg-color, var(--bg-color));
  border: 1px solid var(--border-color);
  padding: 0.3rem 0.6rem;
  border-radius: 5px;
  min-width: 3.2rem;
}

.stat-pill.highlight {
  background: rgba(225, 6, 0, 0.08);
  border-color: rgba(225, 6, 0, 0.25);
}

.stat-pill-val {
  font-family: "JetBrains Mono", monospace;
  font-size: 0.9rem;
  font-weight: 800;
  color: var(--text-color);
}

.stat-pill.highlight .stat-pill-val {
  color: var(--primary-color);
}

.stat-pill-label {
  font-size: 0.55rem;
  font-weight: 700;
  color: var(--muted-text-color);
  letter-spacing: 0.04em;
}

/* Callouts */
.scenario-callout {
  display: flex;
  align-items: flex-start;
  gap: 0.55rem;
  margin: 0 0.85rem 0.85rem;
  padding: 0.65rem 0.85rem;
  border-radius: 6px;
  font-size: 0.82rem;
  line-height: 1.35;
}

.leader-callout {
  background: rgba(212, 168, 0, 0.1);
  border: 1px solid rgba(212, 168, 0, 0.25);
  color: var(--text-color);
}

.challenger-callout {
  background: var(--card-bg-color, var(--bg-color));
  border: 1px solid var(--border-color);
  color: var(--text-color);
  margin-top: 0.45rem;
}

.callout-icon {
  font-size: 0.95rem;
  flex-shrink: 0;
  margin-top: 0.05rem;
}

/* Challengers List */
.challengers-list {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  padding: 0.85rem;
}

.challenger-row {
  background: var(--card-bg-color, var(--bg-color));
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: 0.65rem 0.75rem;
}

.challenger-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.challenger-id {
  display: flex;
  align-items: center;
  gap: 0.55rem;
}

.pos-badge {
  font-family: "JetBrains Mono", monospace;
  font-size: 0.65rem;
  font-weight: 700;
  color: var(--muted-text-color);
  min-width: 1.6rem;
}

.challenger-bar {
  width: 3px;
  height: 1.5rem;
  border-radius: 2px;
}

.challenger-titles {
  display: flex;
  align-items: baseline;
  gap: 0.45rem;
}

.challenger-code {
  font-family: "JetBrains Mono", monospace;
  font-size: 0.85rem;
  font-weight: 800;
  color: var(--text-color);
}

.challenger-name {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--muted-text-color);
}

.challenger-metrics {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.metric-pill {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  background: var(--item-bg-color);
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
}

.metric-lbl {
  font-size: 0.55rem;
  font-weight: 700;
  color: var(--muted-text-color);
  letter-spacing: 0.04em;
}

.metric-val {
  font-family: "JetBrains Mono", monospace;
  font-size: 0.78rem;
  font-weight: 700;
  color: var(--text-color);
}

.metric-pill.deficit .metric-val {
  color: var(--primary-color);
}

/* Modal Footer */
.modal-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.85rem 1.5rem;
  border-top: 1px solid var(--border-color);
  background: var(--item-bg-color);
  gap: 1rem;
}

.scenarios-disclaimer {
  margin: 0;
  font-size: 0.7rem;
  color: var(--muted-text-color);
  font-style: italic;
}

.footer-close-btn {
  background: var(--card-bg-color, var(--bg-color));
  border: 1px solid var(--border-color);
  color: var(--text-color);
  font-weight: 600;
  font-size: 0.8rem;
  padding: 0.45rem 1rem;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.footer-close-btn:hover {
  background: var(--accent-color);
  border-color: var(--text-color);
}

/* Mobile Responsiveness */
@media (max-width: 768px) {
  .overview-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .header-actions {
    width: 100%;
  }

  .scenarios-btn {
    width: 100%;
    justify-content: center;
  }

  .champions-hero {
    grid-template-columns: 1fr;
  }

  .champion-body {
    flex-wrap: wrap;
    gap: 0.75rem;
  }

  .champion-stats {
    width: 100%;
    justify-content: flex-start;
  }

  .standing-row {
    flex-wrap: wrap;
    padding: 0.45rem 0.5rem;
    gap: 0.25rem 0.35rem;
  }

  .driver-info {
    width: auto;
    min-width: 0;
    flex: 1;
    overflow: hidden;
  }

  .driver-code {
    font-size: 0.72rem;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .driver-name,
  .team-name {
    display: none;
  }

  .points-area {
    flex: 0 0 auto;
    gap: 0.3rem;
  }

  .gap-value {
    font-size: 0.68rem;
    min-width: 2.5rem;
  }

  .points-bar-track {
    flex-basis: 100%;
    order: 10;
    height: 4px;
    margin-top: 0.1rem;
  }

  .points-value {
    font-size: 0.72rem;
    min-width: 2.2rem;
  }

  .wins-badge {
    font-size: 0.55rem;
    min-width: 1.5rem;
    padding: 0.05rem 0.25rem;
  }

  .pos {
    min-width: 1.3rem;
    height: 1.3rem;
    font-size: 0.6rem;
  }

  .team-indicator {
    height: 1.3rem;
    width: 3px;
  }

  .modal-backdrop {
    padding: 0.5rem;
  }

  .scenarios-modal {
    max-height: 96vh;
  }

  .contender-profile {
    flex-direction: column;
    align-items: flex-start;
  }

  .profile-stats {
    width: 100%;
    justify-content: space-between;
  }

  .challenger-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .challenger-metrics {
    width: 100%;
    justify-content: space-between;
  }
}
</style>
