<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from "vue";
import { getSeasonStats, getDriverCareer } from "../api";
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
const loading = ref(true);
const error = ref(null);
const seasonData = ref(null);

const activeSection = ref("grid"); // 'grid' | 'h2h'
const searchQuery = ref("");

// Driver Profile Modal State
const selectedDriver = ref(null);
const careerLoading = ref(false);
const careerData = ref(null);
const careerError = ref(null);
let statsReqId = 0;

// --- Data Fetching ---
async function fetchSeasonStats(year) {
  const reqId = ++statsReqId;
  loading.value = true;
  error.value = null;
  try {
    const data = await getSeasonStats(year);
    if (reqId !== statsReqId) return;
    if (!data) {
      throw new Error(`No data returned for ${year}`);
    }
    seasonData.value = data;
  } catch (err) {
    if (reqId !== statsReqId) return;
    error.value = err.message || "Failed to load season statistics.";
  } finally {
    if (reqId === statsReqId) {
      loading.value = false;
    }
  }
}

watch(
  () => props.year,
  (newYear) => {
    fetchSeasonStats(newYear);
  },
  { immediate: true },
);

// --- Modal Handlers ---
async function openDriverModal(driver) {
  if (!driver) return;
  // If clicked from H2H where driver is a sub-object, lookup full driver in seasonData.drivers
  const fullDriver =
    seasonData.value?.drivers?.find((d) => d.driver_id === driver.driver_id) ||
    driver;

  const requestedDriverId = fullDriver.driver_id;
  selectedDriver.value = fullDriver;
  document.body.style.overflow = "hidden";
  careerLoading.value = true;
  careerError.value = null;
  careerData.value = null;

  try {
    const career = await getDriverCareer(requestedDriverId);
    if (selectedDriver.value?.driver_id !== requestedDriverId) return;
    careerData.value = career;
  } catch (err) {
    if (selectedDriver.value?.driver_id !== requestedDriverId) return;
    careerError.value = "Failed to load career statistics.";
  } finally {
    if (selectedDriver.value?.driver_id === requestedDriverId) {
      careerLoading.value = false;
    }
  }
}

function closeDriverModal() {
  selectedDriver.value = null;
  careerData.value = null;
  careerError.value = null;
  document.body.style.overflow = "";
}

function handleKeyDown(e) {
  if (e.key === "Escape" && selectedDriver.value) {
    closeDriverModal();
  }
}

onMounted(() => {
  window.addEventListener("keydown", handleKeyDown);
});

onUnmounted(() => {
  window.removeEventListener("keydown", handleKeyDown);
  document.body.style.overflow = "";
});

// --- Filtered Computeds ---
const filteredDrivers = computed(() => {
  const list = seasonData.value?.drivers || [];
  const q = searchQuery.value.trim().toLowerCase();
  if (!q) return list;
  return list.filter((d) => {
    return (
      d.driver_name.toLowerCase().includes(q) ||
      d.driver_code.toLowerCase().includes(q) ||
      d.team_name.toLowerCase().includes(q) ||
      String(d.driver_number).includes(q)
    );
  });
});

const filteredBattles = computed(() => {
  const list = seasonData.value?.teammate_battles || [];
  const q = searchQuery.value.trim().toLowerCase();
  if (!q) return list;
  return list.filter((b) => {
    return (
      b.constructor_name.toLowerCase().includes(q) ||
      b.driver1.driver_name.toLowerCase().includes(q) ||
      b.driver1.driver_code.toLowerCase().includes(q) ||
      b.driver2.driver_name.toLowerCase().includes(q) ||
      b.driver2.driver_code.toLowerCase().includes(q)
    );
  });
});

function formatDelta(delta) {
  if (delta === null || delta === undefined) return "—";
  if (delta > 0) return `+${delta}`;
  return `${delta}`;
}

function getDeltaClass(delta) {
  if (delta === null || delta === undefined) return "delta-neutral";
  if (delta > 0) return "delta-pos";
  if (delta < 0) return "delta-neg";
  return "delta-neutral";
}
</script>

<template>
  <div class="drivers-page">
    <!-- Page Header & Controls -->
    <header class="page-header">
      <div class="header-main">
        <div class="header-title-row">
          <div class="header-icon-wrap">
            <F1Icon name="helmet" :size="28" />
          </div>
          <div>
            <h1 class="page-title">Drivers &amp; Teammate Battles</h1>
            <p class="page-subtitle">
              {{ year }} Driver Standings, Form &amp; Teammate Head-to-Head
            </p>
          </div>
        </div>

        <!-- Section Switcher & Search Bar -->
        <div class="header-actions">
          <div class="section-toggle" role="tablist">
            <button
              class="toggle-btn"
              :class="{ active: activeSection === 'grid' }"
              role="tab"
              :aria-selected="activeSection === 'grid'"
              @click="activeSection = 'grid'"
            >
              <F1Icon name="users" :size="16" />
              <span>Driver Grid</span>
              <span class="count-pill" v-if="seasonData?.drivers?.length">
                {{ seasonData.drivers.length }}
              </span>
            </button>
            <button
              class="toggle-btn"
              :class="{ active: activeSection === 'h2h' }"
              role="tab"
              :aria-selected="activeSection === 'h2h'"
              @click="activeSection = 'h2h'"
            >
              <F1Icon name="target" :size="16" />
              <span>Teammate H2H</span>
              <span
                class="count-pill"
                v-if="seasonData?.teammate_battles?.length"
              >
                {{ seasonData.teammate_battles.length }}
              </span>
            </button>
          </div>

          <div class="search-box">
            <input
              type="text"
              v-model="searchQuery"
              placeholder="Search driver, team, or #..."
              class="search-input"
            />
            <button
              v-if="searchQuery"
              class="clear-search"
              @click="searchQuery = ''"
              title="Clear search"
            >
              <F1Icon name="close" :size="14" />
            </button>
          </div>
        </div>
      </div>
    </header>

    <!-- Loading State -->
    <div v-if="loading" class="state-container loading-state">
      <div class="spinner"></div>
      <p>Loading {{ year }} driver standings &amp; stats...</p>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="state-container error-state">
      <F1Icon name="alert" :size="36" />
      <p class="error-msg">{{ error }}</p>
      <button class="retry-btn" @click="fetchSeasonStats(year)">Retry</button>
    </div>

    <!-- Main Content -->
    <div v-else class="content-body">
      <!-- SECTION 1: Driver Grid -->
      <section v-if="activeSection === 'grid'" class="driver-grid-section">
        <div v-if="filteredDrivers.length === 0" class="empty-filter">
          <p v-if="searchQuery.trim()">
            No drivers found matching "{{ searchQuery }}".
          </p>
          <p v-else>No driver standings available for {{ year }}.</p>
          <button
            v-if="searchQuery.trim()"
            class="reset-filter-btn"
            @click="searchQuery = ''"
          >
            Reset Search
          </button>
        </div>

        <div v-else class="driver-cards-container">
          <article
            v-for="driver in filteredDrivers"
            :key="driver.driver_id"
            class="driver-card"
            :class="`pos-tier-${driver.position <= 3 ? driver.position : 'other'}`"
            @click="openDriverModal(driver)"
            tabindex="0"
            role="button"
            :aria-label="`Open profile for ${driver.driver_name}`"
            @keydown.enter="openDriverModal(driver)"
          >
            <!-- Card Team Accent Strip -->
            <div
              class="team-accent-bar"
              :style="{ backgroundColor: `#${driver.team_color}` }"
            ></div>

            <div class="card-inner">
              <!-- Top Header: Rank, Code, Name, Team, Points -->
              <header class="card-header">
                <div class="driver-id-col">
                  <div class="rank-badge" :class="`pos-${driver.position}`">
                    P{{ driver.position }}
                  </div>
                  <div class="driver-meta">
                    <div class="driver-code-row">
                      <span class="driver-code">{{ driver.driver_code }}</span>
                      <span class="driver-number"
                        >#{{ driver.driver_number }}</span
                      >
                    </div>
                    <h2 class="driver-name">{{ driver.driver_name }}</h2>
                    <span class="team-name">{{ driver.team_name }}</span>
                  </div>
                </div>

                <div class="points-col">
                  <div class="points-val">
                    {{ driver.points }} <span class="pts-label">pts</span>
                  </div>
                  <div
                    class="points-share"
                    title="Share of constructor's total championship points"
                  >
                    {{ driver.team_points_share_pct }}% of team
                  </div>
                  <div
                    class="gap-val"
                    :class="{ 'is-leader': driver.position === 1 }"
                  >
                    <template v-if="driver.position === 1"
                      >Championship Leader</template
                    >
                    <template v-else>-{{ driver.gap_to_leader }} pts</template>
                  </div>
                </div>
              </header>

              <!-- Zero-Suppressed Milestone Badges (Consistent Height Row) -->
              <div class="milestones-row">
                <template
                  v-if="
                    driver.wins > 0 ||
                    driver.podiums > 0 ||
                    driver.poles > 0 ||
                    driver.fastest_laps > 0
                  "
                >
                  <span v-if="driver.wins > 0" class="milestone-pill pill-wins">
                    <F1Icon name="trophy" :size="13" />
                    <span
                      >{{ driver.wins }}
                      {{ driver.wins === 1 ? "Win" : "Wins" }}</span
                    >
                  </span>
                  <span
                    v-if="driver.podiums > 0"
                    class="milestone-pill pill-podiums"
                  >
                    <F1Icon name="checkered-flag" :size="13" />
                    <span
                      >{{ driver.podiums }}
                      {{ driver.podiums === 1 ? "Podium" : "Podiums" }}</span
                    >
                  </span>
                  <span
                    v-if="driver.poles > 0"
                    class="milestone-pill pill-poles"
                  >
                    <F1Icon name="stopwatch" :size="13" />
                    <span
                      >{{ driver.poles }}
                      {{ driver.poles === 1 ? "Pole" : "Poles" }}</span
                    >
                  </span>
                  <span
                    v-if="driver.fastest_laps > 0"
                    class="milestone-pill pill-fl"
                  >
                    <F1Icon name="bolt" :size="13" />
                    <span>{{ driver.fastest_laps }} FL</span>
                  </span>
                </template>
                <span v-else class="milestone-pill pill-entries">
                  <F1Icon name="checkered-flag" :size="12" />
                  <span>
                    {{ driver.races_entered }}
                    {{ driver.races_entered === 1 ? "GP Entry" : "GP Entries" }}
                    · Best P{{ driver.best_finish ?? "—" }}
                  </span>
                </span>
              </div>

              <!-- Core 4 Metrics Grid -->
              <div class="metrics-grid">
                <!-- 1. Teammate H2H -->
                <div class="metric-box">
                  <span class="metric-label"
                    >H2H vs {{ driver.teammate_h2h.teammate_code }}</span
                  >
                  <div class="metric-val mono">
                    <span class="h2h-item" title="Grand Prix Race Head-to-Head">
                      R: {{ driver.teammate_h2h.race_wins }}-{{
                        driver.teammate_h2h.race_losses
                      }}
                    </span>
                    <span class="h2h-divider">/</span>
                    <span class="h2h-item" title="Qualifying Head-to-Head">
                      Q: {{ driver.teammate_h2h.quali_wins }}-{{
                        driver.teammate_h2h.quali_losses
                      }}
                    </span>
                  </div>
                  <span class="metric-subtext">Race / Quali vs Teammate</span>
                </div>

                <!-- 2. Avg Finish vs Grid -->
                <div class="metric-box">
                  <span class="metric-label">Avg Finish (Grid)</span>
                  <div class="metric-val mono">
                    <span class="finish-val"
                      >P{{ driver.avg_finish ?? "—" }}</span
                    >
                    <span class="grid-val"
                      >(P{{ driver.avg_grid ?? "—" }})</span
                    >
                    <span
                      class="delta-pill"
                      :class="getDeltaClass(driver.avg_positions_gained)"
                    >
                      {{ formatDelta(driver.avg_positions_gained) }}
                    </span>
                  </div>
                  <span class="metric-subtext">Net positions gained</span>
                </div>

                <!-- 3. Classified / Reliability -->
                <div class="metric-box">
                  <span class="metric-label">Reliability</span>
                  <div class="metric-val mono">
                    <span class="finish-rate"
                      >{{ driver.finish_rate_pct }}%</span
                    >
                  </div>
                  <span class="metric-subtext">
                    {{ driver.classified_finishes }}/{{ driver.races_entered }}
                    Finishes
                    <template v-if="driver.dnfs > 0">
                      ({{ driver.dnfs }} DNF{{ driver.dnfs > 1 ? "s" : "" }})
                    </template>
                  </span>
                </div>

                <!-- 4. Rule-Driven Spotlight Stat -->
                <div
                  class="metric-box spotlight-box"
                  :class="`spotlight-tier-${driver.spotlight_stat.tier}`"
                >
                  <span class="metric-label spotlight-label">
                    <F1Icon name="sparkles" :size="12" />
                    {{ driver.spotlight_stat.label }}
                  </span>
                  <div class="metric-val mono spotlight-val">
                    {{ driver.spotlight_stat.value }}
                  </div>
                  <span class="metric-subtext spotlight-sub">
                    {{ driver.spotlight_stat.subtext }}
                  </span>
                </div>
              </div>

              <!-- Season Form Strip -->
              <div class="form-strip-wrapper" v-if="driver.season_form?.length">
                <div class="form-strip-label">
                  <span>Season Form</span>
                  <span class="form-strip-hint">Click card for race log</span>
                </div>
                <div
                  class="form-strip"
                  :class="{
                    'is-two-rows': (seasonData?.completed_rounds || 0) > 12,
                  }"
                >
                  <div
                    v-for="item in driver.season_form"
                    :key="item.round"
                    class="form-pill"
                    :class="`form-${item.category}`"
                    :title="`${item.round_name}: ${item.grid ? 'Grid P' + item.grid + ' → ' : ''}${item.category === 'dnf' ? 'DNF (' + item.status + ')' : item.category === 'dns' ? 'DNS' : item.position ? 'P' + item.position : item.status} (${item.points} GP pts${item.sprint_points > 0 ? ' · +' + item.sprint_points + ' Sprint pts' : ''})`"
                  >
                    <span class="form-pos">
                      <template v-if="item.category === 'dnf'">R</template>
                      <template v-else-if="item.category === 'dns'">W</template>
                      <template v-else>{{ item.position }}</template>
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </article>
        </div>
      </section>

      <!-- SECTION 2: Teammate Head-to-Head -->
      <section v-else-if="activeSection === 'h2h'" class="h2h-matrix-section">
        <div v-if="filteredBattles.length === 0" class="empty-filter">
          <p v-if="searchQuery.trim()">
            No teammate battles found matching "{{ searchQuery }}".
          </p>
          <p v-else>No teammate battles available for {{ year }}.</p>
          <button
            v-if="searchQuery.trim()"
            class="reset-filter-btn"
            @click="searchQuery = ''"
          >
            Reset Search
          </button>
        </div>

        <div v-else class="h2h-cards-grid">
          <article
            v-for="battle in filteredBattles"
            :key="battle.constructor_id"
            class="h2h-card"
          >
            <!-- Card Team Top Banner -->
            <div
              class="h2h-team-strip"
              :style="{ backgroundColor: `#${battle.team_color}` }"
            ></div>

            <div class="h2h-card-inner">
              <!-- Constructor Title Header -->
              <header class="h2h-header">
                <div class="h2h-team-title">
                  <span class="wcc-rank">P{{ battle.position }}</span>
                  <h2 class="constructor-name">
                    {{ battle.constructor_name }}
                  </h2>
                </div>
                <div class="team-points-badge mono">
                  {{ battle.total_points }} <span class="pts-unit">pts</span>
                </div>
              </header>

              <!-- Driver 1 vs Driver 2 Hero Banners -->
              <div class="h2h-driver-pair">
                <!-- Driver 1 -->
                <div
                  class="h2h-driver-col driver-1"
                  @click="openDriverModal(battle.driver1)"
                  @keydown.enter="openDriverModal(battle.driver1)"
                  @keydown.space.prevent="openDriverModal(battle.driver1)"
                  role="button"
                  tabindex="0"
                  :title="`View profile for ${battle.driver1.driver_name}`"
                >
                  <div class="driver-code-tag">
                    <span class="code">{{ battle.driver1.driver_code }}</span>
                    <span class="num">#{{ battle.driver1.driver_number }}</span>
                  </div>
                  <div class="driver-full-name">
                    {{ battle.driver1.driver_name }}
                  </div>
                  <div class="driver-tally mono">
                    {{ battle.driver1.points }} pts
                    <span class="tally-share"
                      >({{ battle.driver1.points_pct }}%)</span
                    >
                  </div>
                </div>

                <div class="vs-badge">VS</div>

                <!-- Driver 2 -->
                <div
                  class="h2h-driver-col driver-2"
                  @click="openDriverModal(battle.driver2)"
                  @keydown.enter="openDriverModal(battle.driver2)"
                  @keydown.space.prevent="openDriverModal(battle.driver2)"
                  role="button"
                  tabindex="0"
                  :title="`View profile for ${battle.driver2.driver_name}`"
                >
                  <div class="driver-code-tag">
                    <span class="code">{{ battle.driver2.driver_code }}</span>
                    <span class="num">#{{ battle.driver2.driver_number }}</span>
                  </div>
                  <div class="driver-full-name">
                    {{ battle.driver2.driver_name }}
                  </div>
                  <div class="driver-tally mono">
                    {{ battle.driver2.points }} pts
                    <span class="tally-share"
                      >({{ battle.driver2.points_pct }}%)</span
                    >
                  </div>
                </div>
              </div>

              <!-- Comparison Rows -->
              <div class="h2h-comparisons">
                <!-- 1. Qualifying H2H -->
                <div class="comp-row">
                  <div class="comp-labels">
                    <span class="comp-score mono">{{
                      battle.quali_h2h.d1
                    }}</span>
                    <span class="comp-title">Qualifying Battle</span>
                    <span class="comp-score mono">{{
                      battle.quali_h2h.d2
                    }}</span>
                  </div>
                  <div class="comp-bar-track">
                    <div
                      class="comp-bar-fill fill-d1"
                      :style="{
                        width:
                          battle.quali_h2h.total > 0
                            ? `${(battle.quali_h2h.d1 / battle.quali_h2h.total) * 100}%`
                            : '50%',
                        backgroundColor: `#${battle.team_color}`,
                      }"
                    ></div>
                    <div
                      class="comp-bar-fill fill-d2"
                      :style="{
                        width:
                          battle.quali_h2h.total > 0
                            ? `${(battle.quali_h2h.d2 / battle.quali_h2h.total) * 100}%`
                            : '50%',
                      }"
                    ></div>
                  </div>
                </div>

                <!-- 2. Race H2H -->
                <div class="comp-row">
                  <div class="comp-labels">
                    <span class="comp-score mono">{{
                      battle.race_h2h.d1
                    }}</span>
                    <span class="comp-title">Grand Prix Battle</span>
                    <span class="comp-score mono">{{
                      battle.race_h2h.d2
                    }}</span>
                  </div>
                  <div class="comp-bar-track">
                    <div
                      class="comp-bar-fill fill-d1"
                      :style="{
                        width:
                          battle.race_h2h.total > 0
                            ? `${(battle.race_h2h.d1 / battle.race_h2h.total) * 100}%`
                            : '50%',
                        backgroundColor: `#${battle.team_color}`,
                      }"
                    ></div>
                    <div
                      class="comp-bar-fill fill-d2"
                      :style="{
                        width:
                          battle.race_h2h.total > 0
                            ? `${(battle.race_h2h.d2 / battle.race_h2h.total) * 100}%`
                            : '50%',
                      }"
                    ></div>
                  </div>
                </div>

                <!-- 3. Points Contribution Split -->
                <div class="comp-row">
                  <div class="comp-labels">
                    <span class="comp-score mono"
                      >{{ battle.driver1.points_pct }}%</span
                    >
                    <span class="comp-title">Points Contribution</span>
                    <span class="comp-score mono"
                      >{{ battle.driver2.points_pct }}%</span
                    >
                  </div>
                  <div class="comp-bar-track">
                    <div
                      class="comp-bar-fill fill-d1"
                      :style="{
                        width: `${battle.driver1.points_pct}%`,
                        backgroundColor: `#${battle.team_color}`,
                      }"
                    ></div>
                    <div
                      class="comp-bar-fill fill-d2"
                      :style="{
                        width: `${battle.driver2.points_pct}%`,
                      }"
                    ></div>
                  </div>
                </div>

                <!-- 4. Avg Finish Comparison -->
                <div class="comp-row comp-row-sub">
                  <div class="comp-labels">
                    <span class="comp-score mono"
                      >P{{ battle.driver1.avg_finish ?? "—" }}</span
                    >
                    <span class="comp-title">Average Finish</span>
                    <span class="comp-score mono"
                      >P{{ battle.driver2.avg_finish ?? "—" }}</span
                    >
                  </div>
                </div>
              </div>

              <!-- Reserve / Substitute Drivers -->
              <div
                v-if="
                  battle.reserve_drivers && battle.reserve_drivers.length > 0
                "
                class="reserve-drivers-tray"
              >
                <span class="reserve-title">Subs &amp; Reserves:</span>
                <div class="reserve-pills">
                  <span
                    v-for="sub in battle.reserve_drivers"
                    :key="sub.driver_id"
                    class="sub-pill"
                    @click="openDriverModal(sub)"
                    @keydown.enter="openDriverModal(sub)"
                    @keydown.space.prevent="openDriverModal(sub)"
                    role="button"
                    tabindex="0"
                  >
                    {{ sub.driver_name }} ({{ sub.driver_code }} #{{
                      sub.driver_number
                    }})
                    <span class="sub-stat mono"
                      >{{ sub.races_entered }} GP, {{ sub.points }} pts</span
                    >
                  </span>
                </div>
              </div>
            </div>
          </article>
        </div>
      </section>
    </div>

    <!-- DRIVER PROFILE MODAL -->
    <Teleport to="body">
      <div
        v-if="selectedDriver"
        class="modal-backdrop"
        @click.self="closeDriverModal"
      >
        <div
          class="modal-card"
          role="dialog"
          aria-modal="true"
          :aria-label="`${selectedDriver.driver_name} Driver Profile`"
        >
          <!-- Team Color Top Bar -->
          <div
            class="modal-team-accent"
            :style="{ backgroundColor: `#${selectedDriver.team_color}` }"
          ></div>

          <!-- Pinned Modal Header -->
          <header class="modal-header">
            <div class="modal-driver-bio">
              <span class="modal-pos" :class="`pos-${selectedDriver.position}`">
                P{{ selectedDriver.position }}
              </span>
              <div class="modal-names">
                <div class="modal-name-line">
                  <h2 class="modal-name">{{ selectedDriver.driver_name }}</h2>
                  <span class="modal-code">{{
                    selectedDriver.driver_code
                  }}</span>
                  <span class="modal-number"
                    >#{{ selectedDriver.driver_number }}</span
                  >
                </div>
                <div class="modal-team-row">
                  <span class="modal-team-name">{{
                    selectedDriver.team_name
                  }}</span>
                  <template v-if="selectedDriver.nationality">
                    <span class="modal-bullet">•</span>
                    <span class="modal-nationality">{{
                      selectedDriver.nationality
                    }}</span>
                  </template>
                  <template v-if="selectedDriver.date_of_birth">
                    <span class="modal-bullet">•</span>
                    <span class="modal-dob"
                      >Born {{ selectedDriver.date_of_birth }}</span
                    >
                  </template>
                </div>
              </div>
            </div>

            <button
              class="modal-close-btn"
              @click="closeDriverModal"
              aria-label="Close driver profile"
            >
              <F1Icon name="close" :size="20" />
            </button>
          </header>

          <!-- Scrollable Modal Body (Inside Rounded Frame) -->
          <div class="modal-body-content">
            <!-- All-Time Career Honours -->
            <section class="modal-section career-section">
              <div class="section-title-row">
                <F1Icon name="trophy" :size="16" />
                <h3 class="section-heading">
                  All-Time Formula 1 Career Honours
                </h3>
              </div>

              <!-- Loading Skeleton -->
              <div v-if="careerLoading" class="career-skeleton-grid">
                <div v-for="i in 6" :key="i" class="skeleton-box"></div>
              </div>

              <!-- Career Error -->
              <div v-else-if="careerError" class="career-error">
                <span>{{ careerError }}</span>
              </div>

              <!-- Career Loaded Data -->
              <div v-else-if="careerData" class="career-honours-grid">
                <div class="honour-box">
                  <span class="honour-label">Career Starts</span>
                  <span class="honour-val mono">{{
                    careerData.career_starts
                  }}</span>
                  <span class="honour-sub">Grand Prix Starts</span>
                </div>
                <div class="honour-box highlight-gold">
                  <span class="honour-label">Career Wins</span>
                  <span class="honour-val mono">{{
                    careerData.career_wins
                  }}</span>
                  <span class="honour-sub">Victories</span>
                </div>
                <div class="honour-box">
                  <span class="honour-label">Career Podiums</span>
                  <span class="honour-val mono">{{
                    careerData.career_podiums
                  }}</span>
                  <span class="honour-sub">Top 3 Finishes</span>
                </div>
                <div class="honour-box">
                  <span class="honour-label">Career Poles</span>
                  <span class="honour-val mono">{{
                    careerData.career_poles
                  }}</span>
                  <span class="honour-sub">Qualifying P1s</span>
                </div>
                <div class="honour-box">
                  <span class="honour-label">Fastest Laps</span>
                  <span class="honour-val mono">{{
                    careerData.career_fastest_laps
                  }}</span>
                  <span class="honour-sub">Race Lap Records</span>
                </div>
                <div class="honour-box">
                  <span class="honour-label">Active Span</span>
                  <span class="honour-val mono">
                    <template v-if="careerData.first_season">
                      {{ careerData.first_season }}–{{
                        careerData.latest_season
                      }}
                    </template>
                    <template v-else>—</template>
                  </span>
                  <span class="honour-sub"
                    >{{ careerData.seasons_count }} Seasons Active</span
                  >
                </div>
              </div>
            </section>

            <!-- Season Race-by-Race Log -->
            <section
              class="modal-section races-section"
              v-if="selectedDriver.season_form?.length"
            >
              <div class="section-title-row">
                <F1Icon name="chart" :size="16" />
                <h3 class="section-heading">{{ year }} Grand Prix Race Log</h3>
              </div>

              <div class="table-scroll-wrap">
                <table class="race-log-table">
                  <thead>
                    <tr>
                      <th class="col-round">Rnd</th>
                      <th class="col-gp">Grand Prix</th>
                      <th class="col-grid">Grid</th>
                      <th class="col-finish">Finish</th>
                      <th class="col-delta">Delta</th>
                      <th class="col-pts">Pts</th>
                      <th class="col-status">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="entry in selectedDriver.season_form"
                      :key="entry.round"
                      :class="`row-cat-${entry.category}`"
                    >
                      <td class="col-round mono">R{{ entry.round }}</td>
                      <td class="col-gp font-bold">{{ entry.round_name }}</td>
                      <td class="col-grid mono">
                        {{ entry.grid ? `P${entry.grid}` : "—" }}
                      </td>
                      <td class="col-finish mono">
                        <span
                          class="finish-badge"
                          :class="`badge-${entry.category}`"
                        >
                          {{
                            entry.category === "dnf"
                              ? "DNF"
                              : entry.category === "dns"
                                ? "DNS"
                                : entry.position
                                  ? "P" + entry.position
                                  : entry.position_text
                          }}
                        </span>
                      </td>
                      <td class="col-delta mono">
                        <span
                          v-if="entry.grid && entry.position"
                          class="delta-pill-sm"
                          :class="getDeltaClass(entry.grid - entry.position)"
                        >
                          {{ formatDelta(entry.grid - entry.position) }}
                        </span>
                        <span v-else class="text-muted">—</span>
                      </td>
                      <td class="col-pts mono font-bold">
                        <div>
                          {{ entry.points > 0 ? `+${entry.points}` : "0" }}
                        </div>
                        <div
                          v-if="entry.sprint_points > 0"
                          class="sprint-sub-pts"
                          style="font-size: 0.75rem; opacity: 0.8"
                        >
                          +{{ entry.sprint_points }} Sprint
                        </div>
                      </td>
                      <td class="col-status">
                        <span
                          class="status-tag"
                          :class="`status-${entry.category}`"
                        >
                          {{ entry.status }}
                        </span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </section>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
/* ==========================================================================
   DRIVERS VIEW ROOT & LAYOUT
   ========================================================================== */
.drivers-page {
  width: 100%;
  max-width: 100%;
  margin: 0;
  padding: 0 0 2rem;
  box-sizing: border-box;
}

.mono {
  font-family: "JetBrains Mono", monospace;
  font-variant-numeric: tabular-nums;
}

/* ==========================================================================
   PAGE HEADER & CONTROLS
   ========================================================================== */
.page-header {
  margin-bottom: 2rem;
  background: var(--card-bg-color);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 1.25rem 1.75rem;
  box-shadow: 0 4px 16px var(--shadow-color);
}

.header-main {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 1.25rem;
}

.header-title-row {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.header-icon-wrap {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: var(--accent-color);
  color: var(--primary-color);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.page-title {
  font-size: 1.5rem;
  font-weight: 800;
  color: var(--text-color);
  margin: 0;
  line-height: 1.2;
}

.page-subtitle {
  font-size: 0.88rem;
  color: var(--muted-text-color);
  margin: 0.25rem 0 0;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
}

/* Sub-Navigation Toggle */
.section-toggle {
  display: flex;
  background: var(--item-bg-color);
  padding: 0.25rem;
  border-radius: 10px;
  border: 1px solid var(--border-color);
  gap: 0.25rem;
}

.toggle-btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  border: none;
  background: transparent;
  color: var(--muted-text-color);
  font-family: inherit;
  font-size: 0.88rem;
  font-weight: 600;
  border-radius: 7px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.toggle-btn:hover {
  color: var(--text-color);
}

.toggle-btn:focus-visible {
  outline: 2px solid var(--primary-color);
  outline-offset: 2px;
}

.toggle-btn.active {
  background: var(--card-bg-color);
  color: var(--primary-color);
  box-shadow: 0 2px 8px var(--shadow-color);
}

.count-pill {
  font-size: 0.75rem;
  font-family: "JetBrains Mono", monospace;
  font-variant-numeric: tabular-nums;
  padding: 0.1rem 0.45rem;
  border-radius: 9999px;
  background: var(--accent-color);
  color: var(--primary-color);
  font-weight: 700;
}

/* Search Box */
.search-box {
  position: relative;
  display: flex;
  align-items: center;
}

.search-input {
  background: var(--input-bg-color);
  border: 1px solid var(--border-color);
  color: var(--text-color);
  padding: 0.55rem 2.2rem 0.55rem 0.85rem;
  border-radius: 8px;
  font-size: 0.88rem;
  width: 220px;
  transition: all 0.2s;
}

.search-input:focus {
  outline: none;
  border-color: var(--primary-color);
  box-shadow: 0 0 0 2px var(--accent-color);
}

.clear-search {
  position: absolute;
  right: 0.5rem;
  background: none;
  border: none;
  color: var(--muted-text-color);
  cursor: pointer;
  display: flex;
  align-items: center;
  padding: 0.2rem;
  border-radius: 4px;
}

.clear-search:hover {
  color: var(--text-color);
}

.clear-search:focus-visible {
  outline: 2px solid var(--primary-color);
  outline-offset: 2px;
}

/* ==========================================================================
   LOADING & ERROR STATES
   ========================================================================== */
.state-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 4rem 2rem;
  text-align: center;
  background: var(--card-bg-color);
  border: 1px solid var(--border-color);
  border-radius: 12px;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid var(--border-color);
  border-top-color: var(--primary-color);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin-bottom: 1rem;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.error-state {
  color: var(--primary-color);
}

.error-msg {
  color: var(--text-color);
  margin: 1rem 0 1.5rem;
  font-size: 1rem;
}

.retry-btn {
  background: var(--primary-color);
  color: #fff;
  border: none;
  padding: 0.6rem 1.4rem;
  font-family: inherit;
  font-weight: 700;
  border-radius: 8px;
  cursor: pointer;
}

.retry-btn:focus-visible {
  outline: 2px solid var(--primary-color);
  outline-offset: 2px;
}

.empty-filter {
  text-align: center;
  padding: 3rem;
  color: var(--muted-text-color);
  font-size: 1rem;
  background: var(--card-bg-color);
  border: 1px dashed var(--border-color);
  border-radius: 12px;
}

.reset-filter-btn {
  margin-top: 1rem;
  background: var(--item-bg-color);
  color: var(--text-color);
  border: 1px solid var(--border-color);
  padding: 0.45rem 1rem;
  border-radius: 6px;
  font-family: inherit;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  transition: border-color 0.15s ease;
}

.reset-filter-btn:hover {
  border-color: var(--primary-color);
}

.reset-filter-btn:focus-visible {
  outline: 2px solid var(--primary-color);
  outline-offset: 2px;
}

/* ==========================================================================
   DRIVER GRID & CARDS
   ========================================================================== */
.driver-cards-container {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
  gap: 1.25rem;
}

.driver-card {
  position: relative;
  background: var(--card-bg-color);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  cursor: pointer;
  box-shadow: 0 4px 12px var(--shadow-color);
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease,
    border-color 0.2s ease;
}

.driver-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px var(--shadow-color);
  border-color: rgba(225, 6, 0, 0.4);
}

.driver-card:focus-visible {
  outline: 2px solid var(--primary-color);
  outline-offset: 2px;
}

/* Team Accent Strip */
.team-accent-bar {
  height: 4px;
  width: 100%;
}

.card-inner {
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  flex: 1;
}

/* Header */
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
  min-height: 58px;
}

.driver-id-col {
  display: flex;
  align-items: center;
  gap: 0.85rem;
  min-width: 0;
  flex: 1;
}

.rank-badge {
  min-width: 44px;
  height: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 0.88rem;
  font-weight: 800;
  font-family: "JetBrains Mono", monospace;
  font-variant-numeric: tabular-nums;
  padding: 0 0.5rem;
  border-radius: 8px;
  background: var(--item-bg-color);
  color: var(--text-color);
  flex-shrink: 0;
  border: 1px solid var(--border-color);
}

.rank-badge.pos-1 {
  background: linear-gradient(135deg, #ffd700 0%, #b89700 100%);
  color: #000;
  border: none;
}

.rank-badge.pos-2 {
  background: linear-gradient(135deg, #e0e0e0 0%, #9e9e9e 100%);
  color: #000;
  border: none;
}

.rank-badge.pos-3 {
  background: linear-gradient(135deg, #cd7f32 0%, #8c4c10 100%);
  color: #fff;
  border: none;
}

.driver-meta {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 0.1rem;
  min-width: 0;
}

.driver-code-row {
  display: flex;
  align-items: baseline;
  gap: 0.45rem;
  line-height: 1.1;
}

.driver-code {
  font-size: 1.15rem;
  font-weight: 800;
  letter-spacing: 0.5px;
  color: var(--text-color);
}

.driver-number {
  font-size: 0.85rem;
  font-weight: 700;
  font-family: "JetBrains Mono", monospace;
  font-variant-numeric: tabular-nums;
  color: var(--muted-text-color);
}

.driver-name {
  font-size: 0.92rem;
  font-weight: 600;
  color: var(--text-color);
  margin: 0;
  line-height: 1.25;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.team-name {
  font-size: 0.8rem;
  color: var(--muted-text-color);
  line-height: 1.2;
}

.points-col {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  justify-content: center;
  gap: 0.15rem;
  text-align: right;
  flex-shrink: 0;
}

.points-val {
  font-size: 1.35rem;
  font-weight: 800;
  font-family: "JetBrains Mono", monospace;
  font-variant-numeric: tabular-nums;
  color: var(--text-color);
  line-height: 1.1;
}

.pts-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--muted-text-color);
}

.points-share {
  font-size: 0.74rem;
  color: var(--muted-text-color);
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
}

.gap-val {
  font-size: 0.74rem;
  font-family: "JetBrains Mono", monospace;
  font-variant-numeric: tabular-nums;
  color: #dc2626;
  line-height: 1.2;
}

:global(html[data-theme="dark"]) .gap-val {
  color: #f87171;
}

.gap-val.is-leader {
  color: #8a6800;
  font-weight: 700;
}

:global(html[data-theme="dark"]) .gap-val.is-leader {
  color: #facc15;
}

/* Milestones Row */
.milestones-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.45rem;
  min-height: 28px;
}

.milestone-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.75rem;
  font-weight: 700;
  line-height: 1;
  padding: 0.28rem 0.6rem;
  border-radius: 9999px;
  border: 1px solid transparent;
}

.pill-entries {
  background: var(--item-bg-color);
  color: var(--muted-text-color);
  border-color: var(--border-color);
  font-weight: 600;
}

.pill-wins {
  background: rgba(255, 215, 0, 0.16);
  color: #8a6800;
  border-color: rgba(255, 215, 0, 0.38);
}

:global(html[data-theme="dark"]) .pill-wins {
  color: #facc15;
}

.pill-podiums {
  background: rgba(16, 185, 129, 0.12);
  color: #047857;
  border-color: rgba(16, 185, 129, 0.3);
}

:global(html[data-theme="dark"]) .pill-podiums {
  color: #34d399;
}

.pill-poles {
  background: rgba(99, 102, 241, 0.12);
  color: #4f46e5;
  border-color: rgba(99, 102, 241, 0.3);
}

:global(html[data-theme="dark"]) .pill-poles {
  color: #818cf8;
}

.pill-fl {
  background: rgba(245, 158, 11, 0.14);
  color: #9a4e00;
  border-color: rgba(245, 158, 11, 0.3);
}

:global(html[data-theme="dark"]) .pill-fl {
  color: #fbbf24;
}

/* Metrics Grid (Core 4) */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0.65rem;
}

.metric-box {
  background: var(--item-bg-color);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 0.65rem 0.75rem;
  min-height: 78px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.metric-label {
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.4px;
  color: var(--muted-text-color);
  line-height: 1.1;
}

.metric-val {
  font-size: 0.92rem;
  font-weight: 700;
  color: var(--text-color);
  display: flex;
  align-items: center;
  gap: 0.35rem;
  white-space: nowrap;
  line-height: 1.2;
}

.metric-subtext {
  font-size: 0.72rem;
  color: var(--muted-text-color);
  line-height: 1.1;
}

.h2h-divider {
  color: var(--muted-text-color);
  opacity: 0.6;
}

.grid-val {
  font-size: 0.8rem;
  color: var(--muted-text-color);
}

.delta-pill {
  font-size: 0.75rem;
  font-weight: 800;
  padding: 0.1rem 0.35rem;
  border-radius: 4px;
}

.delta-pos {
  background: rgba(16, 185, 129, 0.15);
  color: #047857;
}

:global(html[data-theme="dark"]) .delta-pos {
  color: #34d399;
}

.delta-neg {
  background: rgba(239, 68, 68, 0.15);
  color: #dc2626;
}

:global(html[data-theme="dark"]) .delta-neg {
  color: #f87171;
}

.delta-neutral {
  background: var(--border-color);
  color: var(--muted-text-color);
}

/* Spotlight Stat */
.spotlight-box {
  background: linear-gradient(
    145deg,
    var(--item-bg-color) 0%,
    rgba(225, 6, 0, 0.05) 100%
  );
  border-color: rgba(225, 6, 0, 0.25);
}

.spotlight-label {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  color: var(--primary-color);
}

.spotlight-tier-contender {
  border-color: rgba(255, 215, 0, 0.4);
  background: linear-gradient(
    145deg,
    var(--item-bg-color) 0%,
    rgba(255, 215, 0, 0.08) 100%
  );
}

.spotlight-tier-contender .spotlight-label {
  color: #8a6800;
}

:global(html[data-theme="dark"]) .spotlight-tier-contender .spotlight-label {
  color: #facc15;
}

.spotlight-tier-midfield {
  border-color: rgba(16, 185, 129, 0.4);
  background: linear-gradient(
    145deg,
    var(--item-bg-color) 0%,
    rgba(16, 185, 129, 0.08) 100%
  );
}

.spotlight-tier-midfield .spotlight-label {
  color: #047857;
}

:global(html[data-theme="dark"]) .spotlight-tier-midfield .spotlight-label {
  color: #34d399;
}

/* Season Form Strip */
.form-strip-wrapper {
  margin-top: auto;
  padding-top: 0.4rem;
  border-top: 1px solid var(--border-color);
}

.form-strip-label {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.72rem;
  font-weight: 700;
  color: var(--muted-text-color);
  margin-bottom: 0.4rem;
  text-transform: uppercase;
}

.form-strip-hint {
  font-size: 0.68rem;
  text-transform: none;
  font-weight: normal;
  color: var(--muted-text-color);
}

.form-strip {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: 4px;
  align-content: start;
}

.form-strip.is-two-rows {
  min-height: 48px;
}

.form-pill {
  width: 100%;
  height: 22px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.7rem;
  font-weight: 800;
  font-family: "JetBrains Mono", monospace;
  font-variant-numeric: tabular-nums;
  cursor: pointer;
  overflow: hidden;
  transition: transform 0.15s ease;
}

.form-pill:hover {
  transform: scale(1.15);
}

.form-win {
  background: #ffd700;
  color: #000;
}

.form-podium {
  background: #10b981;
  color: #fff;
}

.form-points {
  background: rgba(16, 185, 129, 0.22);
  color: #047857;
  border: 1px solid rgba(16, 185, 129, 0.5);
}

:global(html[data-theme="dark"]) .form-points {
  color: #34d399;
}

.form-outside {
  background: var(--item-bg-color);
  color: var(--muted-text-color);
  border: 1px solid var(--border-color);
}

.form-dnf {
  background: #ef4444;
  color: #fff;
}

.form-dns {
  background: #64748b;
  color: #fff;
}

/* ==========================================================================
   TEAMMATE HEAD-TO-HEAD
   ========================================================================== */
.h2h-cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(440px, 1fr));
  gap: 1.5rem;
}

.h2h-card {
  background: var(--card-bg-color);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 16px var(--shadow-color);
}

.h2h-team-strip {
  height: 5px;
  width: 100%;
}

.h2h-card-inner {
  padding: 1.25rem 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.h2h-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.h2h-team-title {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.wcc-rank {
  font-size: 0.85rem;
  font-weight: 800;
  font-family: "JetBrains Mono", monospace;
  font-variant-numeric: tabular-nums;
  background: var(--item-bg-color);
  border: 1px solid var(--border-color);
  padding: 0.2rem 0.5rem;
  border-radius: 6px;
  color: var(--text-color);
}

.constructor-name {
  font-size: 1.15rem;
  font-weight: 800;
  color: var(--text-color);
  margin: 0;
}

.team-points-badge {
  font-size: 1rem;
  font-weight: 800;
  color: var(--text-color);
}

.pts-unit {
  font-size: 0.75rem;
  color: var(--muted-text-color);
  font-weight: normal;
}

/* Drivers Head-to-Head Pair */
.h2h-driver-pair {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  gap: 0.75rem;
  background: var(--item-bg-color);
  padding: 0.85rem 1rem;
  border-radius: 10px;
  border: 1px solid var(--border-color);
}

.h2h-driver-col {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: flex-start;
  text-align: left;
  gap: 0.2rem;
  min-width: 0;
  border-radius: 6px;
  padding: 0.2rem 0.25rem;
  cursor: pointer;
  transition: transform 0.15s;
}

.h2h-driver-col:hover {
  transform: translateY(-2px);
}

.h2h-driver-col:focus-visible {
  outline: 2px solid var(--primary-color);
  outline-offset: 2px;
}

.h2h-driver-col.driver-2 {
  align-items: flex-end;
  text-align: right;
}

.h2h-driver-col.driver-2 .driver-code-tag {
  justify-content: flex-end;
}

.driver-code-tag {
  display: inline-flex;
  align-items: baseline;
  gap: 0.35rem;
  line-height: 1.1;
}

.driver-code-tag .code {
  font-size: 1.1rem;
  font-weight: 800;
  color: var(--text-color);
}

.driver-code-tag .num {
  font-size: 0.8rem;
  font-family: "JetBrains Mono", monospace;
  color: var(--muted-text-color);
}

.driver-full-name {
  font-size: 0.85rem;
  color: var(--text-color);
  font-weight: 600;
  margin: 0.1rem 0;
  max-width: 100%;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.driver-tally {
  font-size: 0.82rem;
  font-weight: 700;
  color: var(--text-color);
}

.tally-share {
  font-size: 0.75rem;
  color: var(--muted-text-color);
  font-weight: normal;
}

.vs-badge {
  font-size: 0.75rem;
  font-weight: 800;
  color: var(--muted-text-color);
  background: var(--card-bg-color);
  border: 1px solid var(--border-color);
  padding: 0.25rem 0.5rem;
  border-radius: 9999px;
}

/* Comparison Bars */
.h2h-comparisons {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.comp-row {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.comp-labels {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.comp-title {
  font-size: 0.8rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.4px;
  color: var(--muted-text-color);
}

.comp-score {
  font-size: 0.92rem;
  font-weight: 800;
  color: var(--text-color);
}

.comp-bar-track {
  height: 10px;
  border-radius: 9999px;
  background: var(--item-bg-color);
  border: 1px solid var(--border-color);
  display: flex;
  overflow: hidden;
}

.comp-bar-fill {
  height: 100%;
  transition: width 0.3s ease;
}

.fill-d1 {
  background: var(--primary-color);
}

.fill-d2 {
  background: rgba(140, 140, 150, 0.6);
}

.comp-row-sub {
  padding-top: 0.5rem;
  border-top: 1px dashed var(--border-color);
}

/* Reserve Drivers Tray */
.reserve-drivers-tray {
  padding-top: 0.5rem;
  border-top: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.reserve-title {
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--muted-text-color);
  text-transform: uppercase;
}

.reserve-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.sub-pill {
  font-size: 0.78rem;
  background: var(--item-bg-color);
  border: 1px solid var(--border-color);
  padding: 0.25rem 0.6rem;
  border-radius: 6px;
  color: var(--text-color);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
}

.sub-pill:hover {
  border-color: var(--primary-color);
}

.sub-pill:focus-visible {
  outline: 2px solid var(--primary-color);
  outline-offset: 2px;
}

.sub-stat {
  font-size: 0.72rem;
  color: var(--muted-text-color);
}

/* ==========================================================================
   DRIVER PROFILE MODAL
   ========================================================================== */
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.75);
  backdrop-filter: blur(4px);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.5rem;
}

.modal-card {
  background: var(--card-bg-color);
  border: 1px solid var(--border-color);
  border-radius: 16px;
  width: 100%;
  max-width: 860px;
  max-height: 90vh;
  overflow: hidden;
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.5);
  display: flex;
  flex-direction: column;
}

.modal-team-accent {
  height: 6px;
  width: 100%;
  flex-shrink: 0;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  padding: 1.35rem 1.75rem;
  border-bottom: 1px solid var(--border-color);
  background: var(--item-bg-color);
  flex-shrink: 0;
}

.modal-body-content {
  padding: 1.5rem 1.75rem;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  overflow-y: auto;
  flex: 1;
  min-height: 0;
  scrollbar-width: thin;
}

.modal-driver-bio {
  display: flex;
  align-items: center;
  gap: 1.1rem;
  min-width: 0;
}

.modal-pos {
  min-width: 52px;
  height: 52px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 1.1rem;
  font-weight: 800;
  font-family: "JetBrains Mono", monospace;
  font-variant-numeric: tabular-nums;
  padding: 0 0.65rem;
  border-radius: 10px;
  background: var(--card-bg-color);
  color: var(--text-color);
  border: 1px solid var(--border-color);
  flex-shrink: 0;
}

.modal-pos.pos-1 {
  background: linear-gradient(135deg, #ffd700 0%, #b89700 100%);
  color: #000;
  border: none;
}

.modal-pos.pos-2 {
  background: linear-gradient(135deg, #e0e0e0 0%, #9e9e9e 100%);
  color: #000;
  border: none;
}

.modal-pos.pos-3 {
  background: linear-gradient(135deg, #cd7f32 0%, #8c4c10 100%);
  color: #fff;
  border: none;
}

.modal-names {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 0.3rem;
  min-width: 0;
}

.modal-name-line {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 0.55rem;
}

.modal-name {
  font-size: 1.55rem;
  font-weight: 800;
  color: var(--text-color);
  margin: 0;
  line-height: 1.15;
}

.modal-code {
  font-family: "JetBrains Mono", monospace;
  font-size: 0.9rem;
  font-weight: 800;
  color: var(--primary-color);
  background: var(--accent-color);
  padding: 0.15rem 0.5rem;
  border-radius: 5px;
}

.modal-number {
  font-size: 0.95rem;
  font-weight: 800;
  font-family: "JetBrains Mono", monospace;
  font-variant-numeric: tabular-nums;
  color: var(--muted-text-color);
}

.modal-team-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.45rem;
  font-size: 0.88rem;
  color: var(--muted-text-color);
  line-height: 1.2;
}

.modal-team-name {
  font-weight: 700;
  color: var(--text-color);
}

.modal-bullet {
  opacity: 0.5;
}

.modal-close-btn {
  background: var(--item-bg-color);
  border: 1px solid var(--border-color);
  color: var(--text-color);
  border-radius: 8px;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s;
  flex-shrink: 0;
}

.modal-close-btn:hover {
  background: var(--primary-color);
  color: #fff;
}

.modal-close-btn:focus-visible {
  outline: 2px solid var(--primary-color);
  outline-offset: 2px;
}

/* Modal Sections */
.modal-section {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.section-title-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--primary-color);
}

.section-heading {
  font-size: 1rem;
  font-weight: 800;
  color: var(--text-color);
  margin: 0;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

/* Career Honours Grid */
.career-honours-grid,
.career-skeleton-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.75rem;
}

.honour-box {
  background: var(--item-bg-color);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  padding: 0.85rem 1rem;
  min-height: 88px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  align-items: flex-start;
  text-align: left;
}

.honour-box.highlight-gold {
  border-color: rgba(255, 215, 0, 0.4);
  background: linear-gradient(
    145deg,
    var(--item-bg-color) 0%,
    rgba(255, 215, 0, 0.08) 100%
  );
}

.honour-box.highlight-gold .honour-val {
  color: #8a6800;
}

:global(html[data-theme="dark"]) .honour-box.highlight-gold .honour-val {
  color: #facc15;
}

.honour-label {
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  color: var(--muted-text-color);
  line-height: 1.1;
}

.honour-val {
  font-size: 1.35rem;
  font-weight: 800;
  color: var(--text-color);
  line-height: 1.15;
  white-space: nowrap;
}

.honour-sub {
  font-size: 0.72rem;
  color: var(--muted-text-color);
  line-height: 1.1;
}

/* Skeleton */
.skeleton-box {
  height: 80px;
  border-radius: 10px;
  background: linear-gradient(
    90deg,
    var(--item-bg-color) 25%,
    var(--border-color) 50%,
    var(--item-bg-color) 75%
  );
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}

@keyframes shimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}

.career-error {
  color: var(--primary-color);
  font-size: 0.88rem;
  padding: 1rem;
  background: var(--item-bg-color);
  border-radius: 8px;
}

/* Race Log Table */
.table-scroll-wrap {
  overflow-x: auto;
  border: 1px solid var(--border-color);
  border-radius: 10px;
  background: var(--card-bg-color);
}

.race-log-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
  text-align: left;
}

.race-log-table th {
  background: var(--item-bg-color);
  padding: 0.65rem 0.85rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.4px;
  color: var(--muted-text-color);
  font-size: 0.72rem;
  border-bottom: 1px solid var(--border-color);
  vertical-align: middle;
}

.race-log-table td {
  padding: 0.65rem 0.85rem;
  border-bottom: 1px solid var(--border-color);
  color: var(--text-color);
  vertical-align: middle;
}

.race-log-table .col-round,
.race-log-table .col-grid,
.race-log-table .col-finish,
.race-log-table .col-delta,
.race-log-table .col-pts {
  text-align: center;
  white-space: nowrap;
}

.race-log-table tr:last-child td {
  border-bottom: none;
}

.race-log-table tr:hover td {
  background: var(--item-bg-color);
}

.finish-badge {
  display: inline-block;
  padding: 0.15rem 0.45rem;
  border-radius: 4px;
  font-weight: 800;
}

.badge-win {
  background: #ffd700;
  color: #000;
}

.badge-podium {
  background: #10b981;
  color: #fff;
}

.badge-points {
  background: rgba(16, 185, 129, 0.2);
  color: #047857;
}

:global(html[data-theme="dark"]) .badge-points {
  color: #34d399;
}

.badge-outside {
  background: var(--item-bg-color);
  color: var(--muted-text-color);
}

.badge-dnf {
  background: #ef4444;
  color: #fff;
}

.badge-dns {
  background: #64748b;
  color: #fff;
}

.delta-pill-sm {
  font-size: 0.75rem;
  font-weight: 800;
  padding: 0.1rem 0.35rem;
  border-radius: 4px;
}

.status-tag {
  font-size: 0.75rem;
  color: var(--muted-text-color);
}

.status-dnf {
  color: #dc2626;
  font-weight: 600;
}

:global(html[data-theme="dark"]) .status-dnf {
  color: #f87171;
}

.status-dns {
  color: var(--muted-text-color);
  background: rgba(156, 163, 175, 0.15);
  border: 1px solid rgba(156, 163, 175, 0.3);
  padding: 0.1rem 0.4rem;
  border-radius: 4px;
  font-weight: 600;
}

.font-bold {
  font-weight: 700;
}

.text-muted {
  color: var(--muted-text-color);
}

/* ==========================================================================
   MOBILE RESPONSIVENESS (Stack-and-Scroll)
   ========================================================================== */
@media (max-width: 768px) {
  .drivers-page {
    padding: 0 0 1.5rem;
  }

  .page-header {
    padding: 1rem;
    border-radius: 10px;
  }

  .header-main {
    flex-direction: column;
    align-items: stretch;
  }

  .header-actions {
    flex-direction: column;
    align-items: stretch;
    width: 100%;
  }

  .section-toggle {
    width: 100%;
  }

  .toggle-btn {
    flex: 1;
    justify-content: center;
  }

  .search-box {
    width: 100%;
  }

  .search-input {
    width: 100%;
  }

  .driver-cards-container {
    grid-template-columns: 1fr;
  }

  .h2h-cards-grid {
    grid-template-columns: 1fr;
  }

  .modal-card {
    max-height: 95vh;
  }

  .modal-body-content {
    padding: 1.25rem;
    gap: 1.25rem;
  }

  .modal-header {
    flex-direction: column-reverse;
    align-items: stretch;
    gap: 0.75rem;
    padding: 1rem 1.25rem;
  }

  .modal-close-btn {
    align-self: flex-end;
  }

  .metrics-grid {
    grid-template-columns: 1fr;
  }

  .career-honours-grid,
  .career-skeleton-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .race-log-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 500px) {
  .form-pill {
    font-size: 0.65rem;
  }
}
</style>
