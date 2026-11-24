<script setup>
import { ref, computed, watch } from "vue";
import { RouterLink } from "vue-router";
import { getSeasonStats } from "../api";
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
const seasonStats = ref(null);

const selectedTier = ref("all"); // 'all' | 'title' | 'midfield' | 'backmarker'
const searchQuery = ref("");
let statsReqId = 0;

// --- Data Fetching ---
async function fetchConstructorsData(year) {
  const reqId = ++statsReqId;
  loading.value = true;
  error.value = null;
  try {
    const data = await getSeasonStats(year);
    if (reqId !== statsReqId) return;
    if (!data) {
      throw new Error(`No data returned for ${year}`);
    }
    seasonStats.value = data;
  } catch (err) {
    if (reqId !== statsReqId) return;
    error.value = err.message || "Failed to load constructor statistics.";
  } finally {
    if (reqId === statsReqId) {
      loading.value = false;
    }
  }
}

watch(
  () => props.year,
  (newYear) => {
    fetchConstructorsData(newYear);
  },
  { immediate: true },
);

// --- Historical Pre-1958 Check ---
const isPre1958 = computed(() => {
  return (
    Number(props.year) < 1958 ||
    (!loading.value &&
      (!seasonStats.value?.constructors ||
        seasonStats.value.constructors.length === 0))
  );
});

// --- Tier & Search Filtering ---
const constructors = computed(() => {
  return seasonStats.value?.constructors || [];
});

const tierCounts = computed(() => {
  const list = constructors.value;
  return {
    all: list.length,
    title: list.filter((c) => c.position <= 3).length,
    midfield: list.filter((c) => c.position >= 4 && c.position <= 7).length,
    backmarker: list.filter((c) => c.position >= 8).length,
  };
});

const filteredConstructors = computed(() => {
  let list = constructors.value;

  // 1. Tier filtering
  if (selectedTier.value === "title") {
    list = list.filter((c) => c.position <= 3);
  } else if (selectedTier.value === "midfield") {
    list = list.filter((c) => c.position >= 4 && c.position <= 7);
  } else if (selectedTier.value === "backmarker") {
    list = list.filter((c) => c.position >= 8);
  }

  // 2. Search query filtering
  const q = searchQuery.value.trim().toLowerCase();
  if (!q) return list;

  return list.filter((team) => {
    if (team.constructor_name?.toLowerCase().includes(q)) return true;
    if (team.constructor_id?.toLowerCase().includes(q)) return true;
    if (Array.isArray(team.drivers)) {
      return team.drivers.some(
        (d) =>
          d.driver_name?.toLowerCase().includes(q) ||
          d.driver_code?.toLowerCase().includes(q) ||
          String(d.driver_number).includes(q),
      );
    }
    return false;
  });
});

// --- Helper Functions ---
function getTierSubtitle(position) {
  if (position <= 3) return "World Title Contender";
  if (position <= 7) return "Midfield Contender";
  return "Challenger";
}

function d1Share(team) {
  if (!team?.drivers || !team.drivers.length || (team.points || 0) <= 0) {
    return 0;
  }
  const share = Number(team.drivers[0]?.share_pct) || 0;
  return Math.min(100, Math.max(0, share));
}

function d2Share(team) {
  if (!team?.drivers || team.drivers.length < 2 || (team.points || 0) <= 0) {
    return 0;
  }
  const d1 = d1Share(team);
  const share = Number(team.drivers[1]?.share_pct) || 0;
  return Math.min(100 - d1, Math.max(0, share));
}
</script>

<template>
  <div class="constructors-page">
    <!-- Page Header & Filters -->
    <header class="page-header">
      <div class="header-main">
        <div class="header-title-row">
          <div class="header-icon-wrap">
            <F1Icon name="wrench" :size="28" />
          </div>
          <div>
            <h1 class="page-title">Constructors</h1>
            <p class="page-subtitle">
              {{ year }} World Constructors' Championship Tiers, Driver
              Contribution &amp; Reliability
            </p>
          </div>
        </div>

        <!-- Tier Filter Pills & Search Input (Hidden if Pre-1958) -->
        <div class="header-actions" v-if="!isPre1958 && !loading && !error">
          <div class="tier-pills-bar" role="tablist" aria-label="Battle Tiers">
            <button
              class="tier-pill-btn"
              :class="{ active: selectedTier === 'all' }"
              role="tab"
              :aria-selected="selectedTier === 'all'"
              @click="selectedTier = 'all'"
            >
              <span>All Teams</span>
              <span class="count-badge" v-if="tierCounts.all > 0">{{
                tierCounts.all
              }}</span>
            </button>
            <button
              class="tier-pill-btn"
              :class="{ active: selectedTier === 'title' }"
              role="tab"
              :aria-selected="selectedTier === 'title'"
              @click="selectedTier = 'title'"
            >
              <span>Title Fight (P1–P3)</span>
              <span class="count-badge" v-if="tierCounts.title > 0">{{
                tierCounts.title
              }}</span>
            </button>
            <button
              class="tier-pill-btn"
              :class="{ active: selectedTier === 'midfield' }"
              role="tab"
              :aria-selected="selectedTier === 'midfield'"
              @click="selectedTier = 'midfield'"
            >
              <span>Midfield (P4–P7)</span>
              <span class="count-badge" v-if="tierCounts.midfield > 0">{{
                tierCounts.midfield
              }}</span>
            </button>
            <button
              class="tier-pill-btn"
              :class="{ active: selectedTier === 'backmarker' }"
              role="tab"
              :aria-selected="selectedTier === 'backmarker'"
              @click="selectedTier = 'backmarker'"
            >
              <span>Backmarkers (P8+)</span>
              <span class="count-badge" v-if="tierCounts.backmarker > 0">{{
                tierCounts.backmarker
              }}</span>
            </button>
          </div>

          <div class="search-box">
            <input
              type="text"
              v-model="searchQuery"
              placeholder="Search team or driver..."
              class="search-input"
            />
            <button
              v-if="searchQuery"
              class="clear-search-btn"
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
      <p>
        Loading {{ year }} Constructors' Championship analytics &amp;
        reliability...
      </p>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="state-container error-state">
      <F1Icon name="alert" :size="36" />
      <p class="error-msg">{{ error }}</p>
      <button class="retry-btn" @click="fetchConstructorsData(year)">
        Retry
      </button>
    </div>

    <!-- Pre-1958 Historical State Card -->
    <div v-else-if="isPre1958" class="state-container historical-state">
      <div class="historical-card">
        <div class="historical-icon-wrap">
          <F1Icon name="wrench" :size="42" />
        </div>
        <div class="historical-badge">
          Historical Archive · {{ year }} Season
        </div>
        <h2 class="historical-title">
          World Constructors' Championship Inaugurated in 1958
        </h2>
        <p class="historical-description">
          The Formula 1 World Constructors' Championship (originally the
          International Cup for F1 Manufacturers) was inaugurated in the
          <strong>1958 season</strong>, won by Vanwall. In
          <strong>{{ year }}</strong>, World Championship standings and titles
          were awarded exclusively to individual drivers.
        </p>
        <RouterLink to="/drivers" class="historical-action-btn">
          <F1Icon name="helmet" :size="18" />
          <span>View {{ year }} Drivers' Championship Stats →</span>
        </RouterLink>
      </div>
    </div>

    <!-- Main Content: Constructor Cards Grid -->
    <main v-else class="content-body">
      <div v-if="filteredConstructors.length === 0" class="empty-filter-state">
        <p v-if="searchQuery.trim()">
          No constructors found matching "{{ searchQuery }}".
        </p>
        <p v-else>No constructors found in this tier.</p>
        <button
          class="reset-filter-btn"
          @click="
            searchQuery = '';
            selectedTier = 'all';
          "
        >
          Reset Filters
        </button>
      </div>

      <div v-else class="constructor-cards-grid">
        <article
          v-for="team in filteredConstructors"
          :key="team.constructor_id"
          class="constructor-card"
          :class="`pos-tier-${team.position <= 3 ? team.position : 'other'}`"
        >
          <!-- 1. Top Team Color Strip -->
          <div
            class="top-color-strip"
            :style="{ backgroundColor: `#${team.team_color || 'e10600'}` }"
          ></div>

          <div class="card-inner">
            <!-- 2. Card Header (min-height: 58px) -->
            <header class="card-header">
              <div class="header-left-col">
                <div
                  class="rank-badge"
                  :class="`rank-${team.position <= 3 ? team.position : 'other'}`"
                >
                  P{{ team.position }}
                </div>
                <div class="team-meta">
                  <h2 class="team-name" :title="team.constructor_name">
                    {{ team.constructor_name }}
                  </h2>
                  <div class="tier-subtitle">
                    {{ getTierSubtitle(team.position) }}
                  </div>
                </div>
              </div>

              <div class="points-col">
                <div class="points-total mono">{{ team.points }} pts</div>
                <div class="gap-subline">
                  <span v-if="team.position === 1" class="leader-text">
                    Championship Leader
                  </span>
                  <span v-else class="gap-text mono">
                    -{{ team.gap_to_leader }} pts
                  </span>
                </div>
              </div>
            </header>

            <!-- 3. Consistent-Height Milestones Row (min-height: 28px) -->
            <div class="milestones-row">
              <template
                v-if="
                  team.wins > 0 ||
                  team.one_two_finishes > 0 ||
                  team.podiums > 0 ||
                  team.poles > 0 ||
                  team.fastest_laps > 0
                "
              >
                <span v-if="team.wins > 0" class="milestone-pill win-pill">
                  {{ team.wins }} Win{{ team.wins > 1 ? "s" : "" }}
                </span>
                <span
                  v-if="team.one_two_finishes > 0"
                  class="milestone-pill onetwo-pill"
                >
                  {{ team.one_two_finishes }} 1-2 Finish{{
                    team.one_two_finishes > 1 ? "es" : ""
                  }}
                </span>
                <span
                  v-if="team.podiums > 0"
                  class="milestone-pill podium-pill"
                >
                  {{ team.podiums }} Podium{{ team.podiums > 1 ? "s" : "" }}
                </span>
                <span v-if="team.poles > 0" class="milestone-pill pole-pill">
                  {{ team.poles }} Pole{{ team.poles > 1 ? "s" : "" }}
                </span>
                <span
                  v-if="team.fastest_laps > 0"
                  class="milestone-pill fl-pill"
                >
                  {{ team.fastest_laps }} FL
                </span>
              </template>
              <span v-else class="milestone-pill fallback-pill">
                {{ team.total_entries }} Race Entries · Best P{{
                  team.best_finish ?? "—"
                }}
              </span>
            </div>

            <!-- 4. Intra-Team Driver Points Split & Lineup Block -->
            <section class="driver-split-box">
              <div class="split-header-row">
                <span class="split-title">Driver Points Contribution</span>
                <span
                  class="split-summary-share mono"
                  v-if="team.drivers && team.drivers.length"
                >
                  <template v-if="team.drivers.length >= 2">
                    {{ team.drivers[0].driver_code }}
                    {{ team.drivers[0].share_pct }}% ·
                    {{ team.drivers[1].driver_code }}
                    {{ team.drivers[1].share_pct }}%
                  </template>
                  <template v-else-if="team.drivers.length === 1">
                    {{ team.drivers[0].driver_code }}
                    {{ team.drivers[0].share_pct }}%
                  </template>
                </span>
              </div>

              <!-- Dual/multi-segment Progress Bar -->
              <div class="split-progress-bar" aria-hidden="true">
                <div
                  class="progress-seg seg-driver-1"
                  :style="{
                    width: `${d1Share(team)}%`,
                    backgroundColor: `#${team.team_color || 'e10600'}`,
                  }"
                  :title="`${team.drivers[0]?.driver_code || 'Driver 1'}: ${d1Share(team)}%`"
                ></div>
                <div
                  v-if="team.drivers && team.drivers.length > 1"
                  class="progress-seg seg-driver-2"
                  :style="{
                    width: `${d2Share(team)}%`,
                  }"
                  :title="`${team.drivers[1]?.driver_code || 'Driver 2'}: ${d2Share(team)}%`"
                ></div>
              </div>

              <!-- Driver Lineup Rows (Locked min-height for uniform alignment) -->
              <div class="lineup-list">
                <div
                  v-for="driver in (team.drivers || []).slice(0, 2)"
                  :key="driver.driver_id"
                  class="lineup-driver-row"
                >
                  <div class="driver-info-left">
                    <span class="driver-num mono"
                      >#{{ driver.driver_number }}</span
                    >
                    <span class="driver-code mono">{{
                      driver.driver_code
                    }}</span>
                    <span class="driver-name" :title="driver.driver_name">
                      {{ driver.driver_name }}
                    </span>
                  </div>
                  <div class="driver-stats-right">
                    <span class="stat-gp">{{ driver.races_entered }} GPs</span>
                    <span class="stat-pts mono">{{ driver.points }} pts</span>
                    <span class="stat-share mono">{{ driver.share_pct }}%</span>
                  </div>
                </div>

                <!-- Empty placeholder row if team only had 1 driver in season -->
                <div
                  v-if="!team.drivers || team.drivers.length === 0"
                  class="lineup-driver-row empty-row"
                >
                  <span class="empty-hint">No registered driver points</span>
                </div>
              </div>

              <!-- Sub / Reserve Drivers Pill (Always rendered for consistent cross-card vertical alignment) -->
              <div class="sub-drivers-container">
                <template v-if="team.drivers && team.drivers.length > 2">
                  <span class="sub-label">Sub:</span>
                  <span
                    v-for="sub in team.drivers.slice(2)"
                    :key="sub.driver_id"
                    class="sub-driver-pill mono"
                  >
                    #{{ sub.driver_number }} {{ sub.driver_code }} ({{
                      sub.races_entered
                    }}
                    GP{{ sub.races_entered === 1 ? "" : "s" }} ·
                    {{ sub.points }} pts · {{ sub.share_pct }}%)
                  </span>
                </template>
                <template v-else>
                  <span class="sub-label">Lineup:</span>
                  <span class="sub-driver-pill"
                    >Full-season 2-car pairing · {{ team.total_entries }} GP
                    starts</span
                  >
                </template>
              </div>
            </section>

            <!-- 5. Core 4 Metrics Grid (display: grid; repeat(2, 1fr)) -->
            <section class="metrics-grid">
              <!-- Metric 1: Best Finish & Podiums -->
              <div class="metric-box">
                <span class="metric-label">BEST FINISH</span>
                <div class="metric-val mono">
                  P{{ team.best_finish ?? "—" }} ({{ team.podiums }} Podium{{
                    team.podiums === 1 ? "" : "s"
                  }})
                </div>
                <span class="metric-subtext">Peak race classification</span>
              </div>

              <!-- Metric 2: 1-2s & Poles -->
              <div class="metric-box">
                <span class="metric-label">1-2S &amp; POLES</span>
                <div class="metric-val mono">
                  {{ team.one_two_finishes }} 1-2s / {{ team.poles }} Pole{{
                    team.poles === 1 ? "" : "s"
                  }}
                </div>
                <span class="metric-subtext">
                  {{ team.fastest_laps }} Fastest Lap{{
                    team.fastest_laps === 1 ? "" : "s"
                  }}
                </span>
              </div>

              <!-- Metric 3: Car Reliability -->
              <div class="metric-box">
                <span class="metric-label">CAR RELIABILITY</span>
                <div class="metric-val mono">{{ team.reliability_pct }}%</div>
                <span class="metric-subtext">
                  {{ team.classified_entries }}/{{
                    team.total_entries
                  }}
                  Finishes ({{ team.dnfs }} DNF{{ team.dnfs === 1 ? "" : "s" }})
                </span>
              </div>

              <!-- Metric 4: Rule-Driven Spotlight Stat -->
              <div class="metric-box spotlight-box">
                <span class="metric-label spotlight-label">
                  <F1Icon name="sparkles" :size="12" />
                  <span>{{ team.spotlight_stat?.label || "SPOTLIGHT" }}</span>
                </span>
                <div class="metric-val mono spotlight-val">
                  {{ team.spotlight_stat?.value || "—" }}
                </div>
                <span class="metric-subtext spotlight-sub">
                  {{ team.spotlight_stat?.subtext || "" }}
                </span>
              </div>
            </section>
          </div>
        </article>
      </div>
    </main>
  </div>
</template>

<style scoped>
.constructors-page {
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

/* --- Page Header --- */
.page-header {
  margin-bottom: 2rem;
  background: var(--card-bg-color);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 1.25rem 1.5rem;
  box-shadow: 0 4px 16px var(--shadow-color);
  overflow: hidden;
}

.header-main {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.header-title-row {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.header-icon-wrap {
  width: 50px;
  height: 50px;
  border-radius: 10px;
  background: var(--accent-color);
  color: var(--primary-color);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border: 1px solid rgba(225, 6, 0, 0.2);
}

.page-title {
  font-size: 1.65rem;
  font-weight: 800;
  color: var(--text-color);
  margin: 0;
  line-height: 1.2;
  letter-spacing: -0.5px;
}

.page-subtitle {
  font-size: 0.95rem;
  color: var(--muted-text-color);
  margin: 0.25rem 0 0;
}

/* --- Controls: Tier Filter & Search --- */
.header-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
  padding-top: 0.5rem;
  border-top: 1px solid var(--border-color);
}

.tier-pills-bar {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.tier-pill-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  background: var(--item-bg-color);
  color: var(--muted-text-color);
  border: 1px solid var(--border-color);
  padding: 0.45rem 0.85rem;
  border-radius: 9999px;
  font-family: inherit;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.tier-pill-btn:hover {
  color: var(--text-color);
  border-color: var(--text-color);
}

.tier-pill-btn:focus-visible {
  outline: 2px solid var(--primary-color);
  outline-offset: 2px;
}

.tier-pill-btn.active {
  background: var(--primary-color);
  color: #ffffff;
  border-color: var(--primary-color);
  box-shadow: 0 2px 8px rgba(225, 6, 0, 0.35);
}

.count-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--card-bg-color);
  color: var(--text-color);
  border: 1px solid var(--border-color);
  font-family: "JetBrains Mono", monospace;
  font-variant-numeric: tabular-nums;
  font-size: 0.72rem;
  font-weight: 700;
  padding: 0.1rem 0.45rem;
  border-radius: 9999px;
}

.tier-pill-btn.active .count-badge {
  background: rgba(255, 255, 255, 0.25);
  color: #ffffff;
  border-color: transparent;
}

.search-box {
  position: relative;
  display: flex;
  align-items: center;
  min-width: 260px;
  max-width: 340px;
  flex: 1;
}

.search-input {
  width: 100%;
  background: var(--item-bg-color);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 0.45rem 2rem 0.45rem 0.75rem;
  font-size: 0.85rem;
  color: var(--text-color);
  outline: none;
  transition: border-color 0.2s ease;
}

.search-input:focus {
  border-color: var(--primary-color);
  box-shadow: 0 0 0 2px var(--accent-color);
}

.search-input:focus-visible {
  outline: 2px solid var(--primary-color);
  outline-offset: 1px;
}

.clear-search-btn {
  position: absolute;
  right: 0.5rem;
  background: transparent;
  border: none;
  color: var(--muted-text-color);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0.2rem;
  border-radius: 4px;
}

.clear-search-btn:hover {
  color: var(--text-color);
}

.clear-search-btn:focus-visible {
  outline: 2px solid var(--primary-color);
  outline-offset: 2px;
}

/* --- State Containers (Loading, Error, Historical) --- */
.state-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3.5rem 1.5rem;
  text-align: center;
  background: var(--card-bg-color);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  box-shadow: 0 4px 16px var(--shadow-color);
  margin-top: 1.5rem;
  overflow: hidden;
}

.spinner {
  width: 44px;
  height: 44px;
  border: 4px solid var(--border-color);
  border-top-color: var(--primary-color);
  border-radius: 50%;
  animation: spin 0.85s linear infinite;
  margin-bottom: 1.25rem;
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
  font-size: 1.05rem;
  margin: 1rem 0 1.25rem;
  max-width: 500px;
}

.retry-btn {
  background: var(--primary-color);
  color: #ffffff;
  border: none;
  padding: 0.55rem 1.4rem;
  border-radius: 6px;
  font-family: inherit;
  font-weight: 700;
  font-size: 0.9rem;
  cursor: pointer;
  transition: opacity 0.2s ease;
}

.retry-btn:hover {
  opacity: 0.9;
}

.retry-btn:focus-visible {
  outline: 2px solid var(--primary-color);
  outline-offset: 2px;
}

/* Historical State Card */
.historical-card {
  max-width: 620px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.historical-icon-wrap {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  background: var(--item-bg-color);
  color: var(--primary-color);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 1.25rem;
  border: 1px solid var(--border-color);
}

.historical-badge {
  display: inline-block;
  background: var(--accent-color);
  color: var(--primary-color);
  font-size: 0.8rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.75px;
  padding: 0.3rem 0.85rem;
  border-radius: 9999px;
  margin-bottom: 1rem;
  border: 1px solid rgba(225, 6, 0, 0.2);
}

.historical-title {
  font-size: 1.4rem;
  font-weight: 800;
  color: var(--text-color);
  margin: 0 0 0.85rem;
}

.historical-description {
  color: var(--muted-text-color);
  font-size: 0.95rem;
  line-height: 1.6;
  margin: 0 0 1.75rem;
}

.historical-action-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.6rem;
  background: var(--primary-color);
  color: #ffffff;
  padding: 0.65rem 1.4rem;
  border-radius: 8px;
  font-size: 0.95rem;
  font-weight: 700;
  text-decoration: none;
  box-shadow: 0 3px 12px rgba(225, 6, 0, 0.3);
  transition:
    transform 0.15s ease,
    opacity 0.2s ease;
}

.historical-action-btn:hover {
  transform: translateY(-1px);
  opacity: 0.95;
}

.historical-action-btn:focus-visible {
  outline: 2px solid var(--primary-color);
  outline-offset: 2px;
}

/* --- Empty Filter --- */
.empty-filter-state {
  text-align: center;
  padding: 3rem 1.5rem;
  background: var(--card-bg-color);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  color: var(--muted-text-color);
  font-size: 1rem;
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

/* --- Constructor Cards Grid --- */
.constructor-cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(390px, 1fr));
  gap: 1.25rem;
  width: 100%;
}

/* Single Constructor Card */
.constructor-card {
  background: var(--card-bg-color);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  box-shadow: 0 3px 12px var(--shadow-color);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  transition:
    transform 0.15s ease,
    box-shadow 0.15s ease,
    border-color 0.15s ease;
}

.constructor-card:hover {
  border-color: rgba(225, 6, 0, 0.4);
  box-shadow: 0 6px 20px var(--shadow-color);
}

/* Top Accent Strip */
.top-color-strip {
  height: 5px;
  width: 100%;
  flex-shrink: 0;
}

.card-inner {
  padding: 1.1rem 1.25rem 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.95rem;
  flex: 1;
}

/* --- Card Header (min-height: 58px) --- */
.card-header {
  min-height: 58px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.header-left-col {
  display: flex;
  align-items: center;
  gap: 0.85rem;
  min-width: 0;
  flex: 1;
}

/* 44px x 44px Rank Badge */
.rank-badge {
  width: 44px;
  height: 44px;
  min-width: 44px;
  border-radius: 9px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 800;
  font-size: 1.15rem;
  font-family: "JetBrains Mono", monospace;
  font-variant-numeric: tabular-nums;
  box-sizing: border-box;
}

.rank-badge.rank-1 {
  background: linear-gradient(135deg, #ffd700 0%, #b89700 100%);
  color: #000;
  border: none;
  box-shadow: 0 2px 8px rgba(255, 215, 0, 0.35);
}

.rank-badge.rank-2 {
  background: linear-gradient(135deg, #e0e0e0 0%, #9e9e9e 100%);
  color: #000;
  border: none;
  box-shadow: 0 2px 8px rgba(192, 192, 192, 0.35);
}

.rank-badge.rank-3 {
  background: linear-gradient(135deg, #cd7f32 0%, #8c4c10 100%);
  color: #fff;
  border: none;
  box-shadow: 0 2px 8px rgba(205, 127, 50, 0.35);
}

.rank-badge.rank-other {
  background: var(--item-bg-color);
  border: 1px solid var(--border-color);
  color: var(--muted-text-color);
  font-size: 1rem;
}

.team-meta {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.team-name {
  font-size: 1.2rem;
  font-weight: 800;
  color: var(--text-color);
  margin: 0;
  line-height: 1.2;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tier-subtitle {
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--muted-text-color);
  margin-top: 0.2rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.points-col {
  text-align: right;
  flex-shrink: 0;
}

.points-total {
  font-size: 1.25rem;
  font-weight: 800;
  color: var(--text-color);
  line-height: 1.1;
}

.gap-subline {
  font-size: 0.78rem;
  font-weight: 600;
  margin-top: 0.2rem;
}

.leader-text {
  color: #8a6800;
  font-weight: 700;
}

:global(html[data-theme="dark"]) .leader-text {
  color: #facc15;
}

.gap-text {
  color: var(--primary-color);
}

/* --- Milestones Row (min-height: 28px) --- */
.milestones-row {
  min-height: 28px;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.45rem;
}

.milestone-pill {
  font-size: 0.74rem;
  font-weight: 700;
  padding: 0.2rem 0.55rem;
  border-radius: 4px;
  line-height: 1.2;
  display: inline-flex;
  align-items: center;
  border: 1px solid transparent;
}

.win-pill {
  background: rgba(255, 215, 0, 0.16);
  color: #8a6800;
  border-color: rgba(255, 215, 0, 0.38);
}

:global(html[data-theme="dark"]) .win-pill {
  color: #facc15;
}

.onetwo-pill {
  background: rgba(16, 185, 129, 0.12);
  color: #047857;
  border-color: rgba(16, 185, 129, 0.3);
}

:global(html[data-theme="dark"]) .onetwo-pill {
  color: #34d399;
}

.podium-pill {
  background: rgba(245, 158, 11, 0.14);
  color: #9a4e00;
  border-color: rgba(245, 158, 11, 0.28);
}

:global(html[data-theme="dark"]) .podium-pill {
  color: #fbbf24;
}

.pole-pill {
  background: rgba(99, 102, 241, 0.12);
  color: #4f46e5;
  border-color: rgba(99, 102, 241, 0.28);
}

:global(html[data-theme="dark"]) .pole-pill {
  color: #818cf8;
}

.fl-pill {
  background: rgba(236, 72, 153, 0.12);
  color: #be185d;
  border-color: rgba(236, 72, 153, 0.28);
}

:global(html[data-theme="dark"]) .fl-pill {
  color: #f472b6;
}

.fallback-pill {
  background: var(--item-bg-color);
  color: var(--muted-text-color);
  border-color: var(--border-color);
  font-weight: 500;
}

/* --- Intra-Team Driver Points Split Block --- */
.driver-split-box {
  background: var(--item-bg-color);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
  overflow: hidden;
}

.split-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  font-size: 0.78rem;
}

.split-title {
  font-weight: 700;
  color: var(--text-color);
  text-transform: uppercase;
  letter-spacing: 0.4px;
}

.split-summary-share {
  font-weight: 700;
  color: var(--muted-text-color);
}

/* Dual-segment Progress Bar */
.split-progress-bar {
  height: 10px;
  border-radius: 9999px;
  overflow: hidden;
  background: var(--border-color);
  display: flex;
  width: 100%;
}

.progress-seg {
  height: 100%;
  transition: width 0.35s ease;
}

.seg-driver-1 {
  /* Dynamic team color */
}

.seg-driver-2 {
  /* Contrasting muted/striped tone */
  background: repeating-linear-gradient(
    45deg,
    rgba(148, 163, 184, 0.8),
    rgba(148, 163, 184, 0.8) 4px,
    rgba(100, 116, 139, 0.95) 4px,
    rgba(100, 116, 139, 0.95) 8px
  );
}

/* Driver Lineup Rows */
.lineup-list {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  min-height: 52px;
  justify-content: center;
}

.lineup-driver-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  font-size: 0.82rem;
  padding: 0.15rem 0;
}

.driver-info-left {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  min-width: 0;
}

.driver-num {
  font-size: 0.72rem;
  font-weight: 700;
  color: var(--muted-text-color);
  width: 22px;
}

.driver-code {
  font-weight: 800;
  font-size: 0.82rem;
  color: var(--text-color);
  background: var(--card-bg-color);
  border: 1px solid var(--border-color);
  padding: 0.05rem 0.35rem;
  border-radius: 4px;
}

.driver-name {
  color: var(--text-color);
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 120px;
}

.driver-stats-right {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  flex-shrink: 0;
}

.stat-gp {
  color: var(--muted-text-color);
  font-size: 0.75rem;
  font-variant-numeric: tabular-nums;
}

.stat-pts {
  font-weight: 700;
  color: var(--text-color);
}

.stat-share {
  background: var(--card-bg-color);
  border: 1px solid var(--border-color);
  padding: 0.05rem 0.35rem;
  border-radius: 4px;
  font-weight: 700;
  font-size: 0.75rem;
  color: var(--text-color);
}

.empty-row {
  justify-content: center;
  color: var(--muted-text-color);
  font-style: italic;
  font-size: 0.8rem;
}

/* Sub / Reserve Drivers */
.sub-drivers-container {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.35rem;
  padding-top: 0.35rem;
  border-top: 1px dashed var(--border-color);
  font-size: 0.74rem;
  min-height: 26px;
}

.sub-label {
  font-weight: 700;
  color: var(--muted-text-color);
  text-transform: uppercase;
}

.sub-driver-pill {
  background: var(--card-bg-color);
  color: var(--muted-text-color);
  border: 1px solid var(--border-color);
  padding: 0.1rem 0.45rem;
  border-radius: 4px;
  font-size: 0.72rem;
  line-height: 1.2;
}

/* --- Core 4 Metrics Grid --- */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0.65rem;
}

.metric-box {
  min-height: 78px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 0.65rem 0.75rem;
  background: var(--item-bg-color);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  box-sizing: border-box;
  overflow: hidden;
}

.metric-label {
  font-size: 0.7rem;
  font-weight: 700;
  color: var(--muted-text-color);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  display: flex;
  align-items: center;
  gap: 0.3rem;
}

.metric-val {
  font-size: 0.92rem;
  font-weight: 700;
  color: var(--text-color);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin: 0.15rem 0;
}

.metric-subtext {
  font-size: 0.72rem;
  color: var(--muted-text-color);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.2;
}

/* Spotlight Card Accent */
.spotlight-box {
  background: linear-gradient(
    145deg,
    var(--item-bg-color) 0%,
    rgba(225, 6, 0, 0.05) 100%
  );
  border-color: rgba(225, 6, 0, 0.25);
}

.spotlight-label {
  color: var(--primary-color);
}

.spotlight-val {
  color: var(--primary-color);
  font-weight: 800;
}

.spotlight-sub {
  color: var(--text-color);
}

/* --- Responsive Stack-and-Scroll --- */
@media (max-width: 768px) {
  .constructors-page {
    padding: 0 0 1.5rem;
  }

  .page-header {
    padding: 1rem;
    margin-bottom: 1.25rem;
  }

  .header-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .tier-pills-bar {
    overflow-x: auto;
    flex-wrap: nowrap;
    padding-bottom: 0.25rem;
    -webkit-overflow-scrolling: touch;
  }

  .tier-pill-btn {
    white-space: nowrap;
    flex-shrink: 0;
  }

  .search-box {
    max-width: 100%;
    min-width: 100%;
  }

  .constructor-cards-grid {
    grid-template-columns: 1fr;
    gap: 1rem;
  }

  .card-inner {
    padding: 1rem;
  }

  .metrics-grid {
    grid-template-columns: 1fr;
    gap: 0.5rem;
  }

  .metric-box {
    min-height: 68px;
  }

  .driver-stats-right {
    gap: 0.45rem;
  }

  .driver-name {
    max-width: none;
    flex: 1;
  }
}
</style>
