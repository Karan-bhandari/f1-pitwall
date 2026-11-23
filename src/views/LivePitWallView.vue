<script setup>
import { ref, computed, onMounted, onUnmounted } from "vue";
import { getLiveSnapshot } from "../api.js";
import {
  formatOffsetLabel,
  formatTemperature,
  formatTimeInZone,
  formatWindSpeed,
  getLocalTimezoneLabel,
  getSpeedUnitLabel,
  setTimeZoneMode,
  timeZoneMode,
  unitSystem,
} from "../utils.js";
import LiveTimingTower from "../components/LiveTimingTower.vue";
import RaceControlFeed from "../components/RaceControlFeed.vue";
import F1Icon from "../components/F1Icon.vue";

const LIVE_POLL_MS = 5000;
const IDLE_POLL_MS = 30000;

const snapshot = ref(null);
const isLoading = ref(true);
const isRefreshing = ref(false);
const isPaused = ref(false);
const errorMsg = ref(null);
const lastUpdatedMs = ref(null);
const nowTickMs = ref(Date.now());

let pollTimer = null;
let ageTimer = null;
let activeController = null;
let inFlight = false;

const session = computed(() => snapshot.value?.session || null);
const trackStatus = computed(() => snapshot.value?.track_status || null);
const weather = computed(() => snapshot.value?.weather || null);
const standings = computed(() => snapshot.value?.standings || []);
const raceControl = computed(() => snapshot.value?.race_control || []);
const isLive = computed(() => Boolean(session.value?.is_live));

const secondsAgo = computed(() => {
  if (!lastUpdatedMs.value) return null;
  return Math.max(
    0,
    Math.floor((nowTickMs.value - lastUpdatedMs.value) / 1000),
  );
});

const trackBannerClass = computed(() => {
  const code = trackStatus.value?.code;
  if (code === "RED") return "flag-red";
  if (
    code === "YELLOW" ||
    code === "SC" ||
    code === "VSC" ||
    code === "VSC_ENDING"
  ) {
    return "flag-yellow";
  }
  return "flag-green";
});

const sessionBadgeLabel = computed(() => {
  if (!session.value) return "";
  const st = (session.value.session_status || "").trim();
  if (isLive.value) {
    return st === "Aborted" ? "LIVE • SUSPENDED" : "LIVE";
  }
  if (st === "Ends" || st === "Finalised" || st === "Finished") {
    return "SESSION ENDED";
  }
  if (st === "Inactive") {
    return "PRE-SESSION";
  }
  return "OFFLINE";
});

const hasTrackOffset = computed(() => Boolean(session.value?.gmt_offset));

const effectiveTimeMode = computed(() =>
  timeZoneMode.value === "track" && hasTrackOffset.value ? "track" : "local",
);

const localTzLabel = getLocalTimezoneLabel();

const trackPlaceLabel = computed(
  () => session.value?.circuit || session.value?.location || "Track Time",
);

const trackTzLabel = computed(
  () => formatOffsetLabel(session.value?.gmt_offset) || "Track",
);

const formattedClockTime = computed(() => {
  const refUtc =
    session.value?.clock?.utc || new Date(nowTickMs.value).toISOString();
  const formatted = formatTimeInZone(refUtc, {
    mode: effectiveTimeMode.value,
    gmtOffset: session.value?.gmt_offset,
    includeSeconds: false,
  });
  const zoneTag =
    effectiveTimeMode.value === "track" ? trackPlaceLabel.value : localTzLabel;
  return `${formatted} · ${zoneTag}`;
});

const clearPollTimer = () => {
  if (pollTimer) {
    clearTimeout(pollTimer);
    pollTimer = null;
  }
};

const scheduleNextPoll = () => {
  clearPollTimer();
  if (isPaused.value || (typeof document !== "undefined" && document.hidden)) {
    return;
  }
  const delay = isLive.value ? LIVE_POLL_MS : IDLE_POLL_MS;
  pollTimer = setTimeout(() => {
    loadSnapshot({ background: true });
  }, delay);
};

const loadSnapshot = async ({ background = false } = {}) => {
  if (inFlight) return;
  inFlight = true;

  if (!background && !snapshot.value) {
    isLoading.value = true;
  } else {
    isRefreshing.value = true;
  }

  activeController = new AbortController();
  try {
    const data = await getLiveSnapshot({ signal: activeController.signal });
    snapshot.value = data;
    errorMsg.value = null;
    lastUpdatedMs.value = Date.now();
    nowTickMs.value = Date.now();
  } catch (err) {
    if (err.name !== "AbortError") {
      errorMsg.value = err.message || "Unable to fetch live timing snapshot.";
    }
  } finally {
    inFlight = false;
    activeController = null;
    isLoading.value = false;
    isRefreshing.value = false;
    scheduleNextPoll();
  }
};

const togglePause = () => {
  isPaused.value = !isPaused.value;
  if (isPaused.value) {
    clearPollTimer();
  } else {
    loadSnapshot({ background: true });
  }
};

const handleVisibilityChange = () => {
  if (typeof document === "undefined") return;
  if (document.hidden) {
    clearPollTimer();
    if (activeController) {
      activeController.abort();
    }
  } else if (!isPaused.value) {
    loadSnapshot({ background: true });
  }
};

onMounted(() => {
  loadSnapshot();
  ageTimer = setInterval(() => {
    nowTickMs.value = Date.now();
  }, 1000);
  document.addEventListener("visibilitychange", handleVisibilityChange);
});

onUnmounted(() => {
  clearPollTimer();
  if (ageTimer) {
    clearInterval(ageTimer);
    ageTimer = null;
  }
  if (activeController) {
    activeController.abort();
  }
  document.removeEventListener("visibilitychange", handleVisibilityChange);
});
</script>

<template>
  <div class="live-view">
    <!-- Top Session & Control Hero -->
    <section class="live-hero" :class="trackBannerClass">
      <div class="hero-main">
        <div class="hero-badges">
          <span class="mode-pill" :class="isLive ? 'mode-live' : 'mode-recent'">
            <span v-if="isLive" class="pulse-dot"></span>
            {{ sessionBadgeLabel || "CONNECTING..." }}
          </span>
          <span v-if="session?.session_part" class="part-pill mono">
            Q{{ session.session_part }}
          </span>
          <span v-if="trackStatus" class="track-pill" :class="trackBannerClass">
            <F1Icon name="flag" :size="13" />
            {{ trackStatus.label }}
          </span>
        </div>

        <h2 class="event-title">
          {{ session?.meeting_name || "Live Timing Pit Wall" }}
          <span v-if="session?.session_name" class="session-subtitle">
            — {{ session.session_name }}
          </span>
        </h2>

        <p class="hero-caption">
          <template v-if="session">
            <span>{{ session.circuit || session.location }}</span>
            <span v-if="session.country"> · {{ session.country }}</span>
            <span class="mono"> · {{ formattedClockTime }}</span>
          </template>
          <template v-else> Fetching Formula 1 live timing feed... </template>
        </p>
      </div>

      <div class="hero-telemetry">
        <div
          v-if="hasTrackOffset"
          class="tz-toggle"
          role="group"
          aria-label="Timezone display"
        >
          <button
            type="button"
            class="tz-btn"
            :class="{ active: effectiveTimeMode === 'local' }"
            @click="setTimeZoneMode('local')"
            :title="`Show timestamps in your timezone (${localTzLabel})`"
          >
            My Time
          </button>
          <button
            type="button"
            class="tz-btn"
            :class="{ active: effectiveTimeMode === 'track' }"
            @click="setTimeZoneMode('track')"
            :title="`Show timestamps in ${trackPlaceLabel} local time (${trackTzLabel})`"
          >
            {{ trackPlaceLabel }}
          </button>
        </div>
        <div v-if="session?.lap_count" class="stat-box">
          <span class="stat-label">LAP</span>
          <span class="stat-value mono">
            {{ session.lap_count.current_lap ?? "—" }}
            <template v-if="session.lap_count.total_laps">
              / {{ session.lap_count.total_laps }}
            </template>
          </span>
        </div>

        <div
          v-if="
            session?.clock?.remaining && session.clock.remaining !== '00:00:00'
          "
          class="stat-box"
        >
          <span class="stat-label">TIME LEFT</span>
          <span class="stat-value mono">{{ session.clock.remaining }}</span>
        </div>

        <div class="controls-box">
          <span v-if="secondsAgo !== null" class="updated-label mono">
            Updated {{ secondsAgo }}s ago
          </span>
          <div class="control-buttons">
            <button
              type="button"
              class="ctrl-btn"
              @click="togglePause"
              :title="isPaused ? 'Resume auto-refresh' : 'Pause auto-refresh'"
            >
              {{ isPaused ? "Resume" : "Pause" }}
            </button>
            <button
              type="button"
              class="ctrl-btn ctrl-btn-primary"
              :disabled="isRefreshing"
              @click="loadSnapshot({ background: true })"
            >
              {{ isRefreshing ? "Syncing..." : "Refresh" }}
            </button>
          </div>
        </div>
      </div>
    </section>

    <!-- Weather Strip -->
    <section v-if="weather" class="weather-strip" aria-label="Track Weather">
      <div class="weather-item">
        <span class="w-label">AIR</span>
        <span class="w-val mono">{{
          formatTemperature(weather.air_temp, unitSystem)
        }}</span>
      </div>
      <div class="weather-item">
        <span class="w-label">TRACK</span>
        <span class="w-val mono">{{
          formatTemperature(weather.track_temp, unitSystem)
        }}</span>
      </div>
      <div class="weather-item">
        <span class="w-label">HUMIDITY</span>
        <span class="w-val mono">{{ weather.humidity ?? "—" }}%</span>
      </div>
      <div class="weather-item">
        <span class="w-label">WIND</span>
        <span class="w-val mono">{{
          formatWindSpeed(weather.wind_speed, unitSystem)
        }}</span>
      </div>
      <div class="weather-item">
        <span class="w-label">CONDITIONS</span>
        <span class="w-val" :class="weather.rainfall ? 'cond-wet' : 'cond-dry'">
          {{ weather.rainfall ? "WET / RAIN" : "DRY" }}
        </span>
      </div>
    </section>

    <!-- Error Banner (non-blocking if stale snapshot exists) -->
    <div v-if="errorMsg" class="error-banner" role="alert">
      <span>{{ errorMsg }}</span>
      <button
        type="button"
        class="ctrl-btn"
        @click="loadSnapshot({ background: false })"
      >
        Retry
      </button>
    </div>

    <!-- Loading Skeleton -->
    <div v-if="isLoading && !snapshot" class="loading-box">
      <p>Connecting to Formula 1 Live Timing...</p>
    </div>

    <!-- Main Pit Wall Grid + Collapsible Classification Key -->
    <template v-else-if="snapshot">
      <div class="pitwall-grid">
        <div class="tower-col">
          <LiveTimingTower
            :standings="standings"
            :best-sectors="snapshot?.best_sectors || []"
            :session-type="session?.session_type || ''"
            :session-part="session?.session_part ?? null"
            :is-live="isLive"
          />
        </div>
        <div class="rc-col">
          <RaceControlFeed
            :messages="raceControl"
            :time-mode="effectiveTimeMode"
            :gmt-offset="session?.gmt_offset || ''"
            :zone-label="
              effectiveTimeMode === 'track' ? trackPlaceLabel : localTzLabel
            "
          />
        </div>
      </div>

      <details open class="pitwall-key">
        <summary class="key-summary">
          <span class="key-summary-title">Classification Key</span>
        </summary>

        <div class="key-grid">
          <div class="key-col">
            <h4 class="key-col-title">Sectors &amp; Mini-Sectors</h4>
            <div class="key-list">
              <div class="key-entry">
                <span class="key-token"
                  ><span class="swatch swatch-purple"></span
                ></span>
                <span class="key-desc">Session Best</span>
              </div>
              <div class="key-entry">
                <span class="key-token"
                  ><span class="swatch swatch-green"></span
                ></span>
                <span class="key-desc">Personal Best</span>
              </div>
              <div class="key-entry">
                <span class="key-token"
                  ><span class="swatch swatch-yellow"></span
                ></span>
                <span class="key-desc">Slower / No Improvement</span>
              </div>
              <div class="key-entry">
                <span class="key-token"
                  ><span class="swatch swatch-blue"></span
                ></span>
                <span class="key-desc">Pit Lane</span>
              </div>
            </div>
          </div>

          <div class="key-col">
            <h4 class="key-col-title">Timing &amp; Tyres</h4>
            <div class="key-list">
              <div class="key-entry">
                <span class="key-token"
                  ><span class="token-pill token-green mono">INT</span></span
                >
                <span class="key-desc">Closing on car ahead</span>
              </div>
              <div class="key-entry">
                <span class="key-token"
                  ><span class="token-pill token-purple">FL</span></span
                >
                <span class="key-desc">Fastest Lap of Session</span>
              </div>
              <div class="key-entry">
                <span class="key-token">
                  <span class="token-pill token-green mono">N</span>
                  <span class="token-sep">/</span>
                  <span class="token-pill token-muted mono">U</span>
                </span>
                <span class="key-desc">New / Used tyre set</span>
              </div>
              <div class="key-entry">
                <span class="key-token"
                  ><span class="token-pill token-code mono">ST</span></span
                >
                <span class="key-desc"
                  >Speed Trap ({{ getSpeedUnitLabel(unitSystem) }})</span
                >
              </div>
            </div>
          </div>

          <div class="key-col">
            <h4 class="key-col-title">Driver Status</h4>
            <div class="key-list">
              <div class="key-entry">
                <span class="key-token"
                  ><span class="token-pill token-blue">PIT</span></span
                >
                <span class="key-desc">In Pit Lane</span>
              </div>
              <div class="key-entry">
                <span class="key-token"
                  ><span class="token-pill token-green">OUT</span></span
                >
                <span class="key-desc">Pit Exit / Out Lap</span>
              </div>
              <div class="key-entry">
                <span class="key-token"
                  ><span class="token-pill token-red">DNF</span></span
                >
                <span class="key-desc">Did Not Finish</span>
              </div>
              <div class="key-entry">
                <span class="key-token"
                  ><span class="token-pill token-muted">DNS</span></span
                >
                <span class="key-desc">Did Not Start</span>
              </div>
            </div>
          </div>
        </div>
      </details>
    </template>
  </div>
</template>

<style scoped>
.live-view {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.live-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 1.1rem 1.25rem;
  border-radius: 10px;
  border: 1px solid var(--border-color);
  border-left-width: 5px;
  background: var(--item-bg-color);
  flex-wrap: nowrap;
}

.live-hero.flag-green {
  border-left-color: #22c55e;
}
.live-hero.flag-yellow {
  border-left-color: #eab308;
}
.live-hero.flag-red {
  border-left-color: var(--primary-color);
}

.hero-main {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  flex: 1 1 auto;
  min-width: 0;
}

.hero-badges {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.mode-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.7px;
  padding: 0.2rem 0.6rem;
  border-radius: 999px;
}

.mode-live {
  background: var(--primary-color);
  color: #ffffff;
}

.mode-recent {
  background: var(--card-bg-color);
  color: var(--muted-text-color);
  border: 1px solid var(--border-color);
}

.pulse-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #ffffff;
  animation: pulse-white 1.5s infinite;
}

@keyframes pulse-white {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.3;
  }
}

.part-pill {
  font-size: 0.72rem;
  font-weight: 800;
  padding: 0.2rem 0.5rem;
  border-radius: 6px;
  background: var(--card-bg-color);
  border: 1px solid var(--border-color);
}

.track-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.72rem;
  font-weight: 800;
  padding: 0.2rem 0.55rem;
  border-radius: 6px;
}
.track-pill.flag-green {
  background: rgba(34, 197, 94, 0.16);
  color: #16a34a;
}
.track-pill.flag-yellow {
  background: rgba(234, 179, 8, 0.22);
  color: #a16207;
}
.track-pill.flag-red {
  background: rgba(225, 6, 0, 0.18);
  color: var(--primary-color);
}

html[data-theme="dark"] .track-pill.flag-green {
  color: #4ade80;
}
html[data-theme="dark"] .track-pill.flag-yellow {
  color: #facc15;
}

.event-title {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 900;
  letter-spacing: -0.2px;
}

.session-subtitle {
  font-weight: 600;
  color: var(--muted-text-color);
}

.hero-caption {
  margin: 0;
  font-size: 0.85rem;
  color: var(--muted-text-color);
}

.hero-telemetry {
  display: flex;
  align-items: center;
  gap: 0.85rem;
  flex-shrink: 0;
  flex-wrap: nowrap;
}

.stat-box {
  background: var(--card-bg-color);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 0.45rem 0.85rem;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

.stat-label {
  font-size: 0.65rem;
  font-weight: 800;
  letter-spacing: 0.6px;
  color: var(--muted-text-color);
}

.stat-value {
  font-size: 1.05rem;
  font-weight: 800;
}

.controls-box {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.35rem;
}

.updated-label {
  font-size: 0.72rem;
  color: var(--muted-text-color);
}

.control-buttons {
  display: flex;
  gap: 0.45rem;
}

.ctrl-btn {
  padding: 0.4rem 0.75rem;
  border-radius: 6px;
  border: 1px solid var(--border-color);
  background: var(--card-bg-color);
  color: var(--text-color);
  font-size: 0.8rem;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.15s ease;
}

.ctrl-btn:hover:not(:disabled) {
  border-color: var(--primary-color);
}

.ctrl-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.ctrl-btn-primary {
  background: var(--primary-color);
  border-color: var(--primary-color);
  color: #ffffff;
}

.tz-toggle {
  display: inline-flex;
  border: 1px solid var(--border-color);
  border-radius: 7px;
  background: var(--card-bg-color);
  padding: 2px;
  gap: 2px;
  flex-shrink: 0;
}

.tz-btn {
  border: none;
  background: transparent;
  color: var(--muted-text-color);
  font-size: 0.74rem;
  font-weight: 700;
  padding: 0.34rem 0.6rem;
  border-radius: 5px;
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
}

.tz-btn:hover {
  color: var(--text-color);
}

.tz-btn.active {
  background: var(--accent-color);
  color: var(--primary-color);
}

.weather-strip {
  display: flex;
  align-items: center;
  gap: 1.25rem;
  padding: 0.65rem 1rem;
  border-radius: 8px;
  border: 1px solid var(--border-color);
  background: var(--card-bg-color);
  flex-wrap: wrap;
}

.weather-item {
  display: inline-flex;
  align-items: baseline;
  gap: 0.4rem;
}

.w-label {
  font-size: 0.7rem;
  font-weight: 800;
  color: var(--muted-text-color);
  letter-spacing: 0.5px;
}

.w-val {
  font-size: 0.86rem;
  font-weight: 700;
}

.cond-wet {
  color: #38bdf8;
  font-weight: 800;
}
.cond-dry {
  color: var(--text-color);
}

.error-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.8rem 1rem;
  border-radius: 8px;
  border: 1px solid var(--primary-color);
  background: var(--accent-color);
  color: var(--text-color);
  font-size: 0.88rem;
}

.loading-box {
  padding: 3rem 1rem;
  text-align: center;
  border: 1px dashed var(--border-color);
  border-radius: 10px;
  color: var(--muted-text-color);
}

.pitwall-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: 1rem;
  align-items: stretch;
}

.tower-col,
.rc-col {
  min-width: 0;
  height: clamp(540px, 74vh, 860px);
  display: flex;
  flex-direction: column;
}

.pitwall-key {
  background: var(--card-bg-color);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  overflow: hidden;
}

.key-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.7rem 1rem;
  background: var(--item-bg-color);
  cursor: pointer;
  list-style: none;
  flex-wrap: wrap;
}

.key-summary::-webkit-details-marker {
  display: none;
}

.key-summary-title {
  font-size: 0.82rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.7px;
  color: var(--text-color);
}

.key-summary-title::before {
  content: "▸ ";
  color: var(--muted-text-color);
}

.pitwall-key[open] .key-summary-title::before {
  content: "▾ ";
}

.key-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1.25rem;
  padding: 0.9rem 1rem;
  border-top: 1px solid var(--border-color);
}

.key-col-title {
  margin: 0 0 0.55rem 0;
  font-size: 0.72rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.6px;
  color: var(--muted-text-color);
}

.key-list {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}

.key-entry {
  display: grid;
  grid-template-columns: 60px minmax(0, 1fr);
  align-items: center;
  gap: 0.6rem;
  font-size: 0.8rem;
}

.key-token {
  display: inline-flex;
  align-items: center;
  gap: 0.2rem;
}

.key-desc {
  color: var(--text-color);
}

.swatch {
  width: 24px;
  height: 8px;
  border-radius: 3px;
  display: inline-block;
}
.swatch-purple {
  background-color: #a855f7;
}
.swatch-green {
  background-color: #22c55e;
}
.swatch-yellow {
  background-color: #eab308;
}
.swatch-blue {
  background-color: #38bdf8;
}

.token-pill {
  font-size: 0.68rem;
  font-weight: 800;
  padding: 0.12rem 0.38rem;
  border-radius: 4px;
  letter-spacing: 0.4px;
}

.token-sep {
  font-size: 0.72rem;
  color: var(--muted-text-color);
}

.token-purple {
  background: rgba(168, 85, 247, 0.18);
  color: #a855f7;
}
.token-green {
  background: rgba(34, 197, 94, 0.16);
  color: #16a34a;
}
.token-blue {
  background: rgba(56, 189, 248, 0.18);
  color: #0284c7;
}
.token-red {
  background: rgba(225, 6, 0, 0.16);
  color: var(--primary-color);
}
.token-muted {
  background: rgba(148, 163, 184, 0.22);
  color: var(--muted-text-color);
}
.token-code {
  background: var(--item-bg-color);
  border: 1px solid var(--border-color);
  color: var(--text-color);
}

html[data-theme="dark"] .token-green {
  color: #4ade80;
}
html[data-theme="dark"] .token-blue {
  color: #38bdf8;
}

@media (max-width: 900px) {
  .key-grid {
    grid-template-columns: 1fr;
    gap: 1rem;
  }
}

@media (max-width: 1280px) {
  .pitwall-grid {
    grid-template-columns: 1fr;
  }

  .tower-col,
  .rc-col {
    height: auto;
  }
}

@media (max-width: 1024px) {
  .live-hero {
    flex-wrap: wrap;
  }

  .hero-telemetry {
    flex-wrap: wrap;
  }
}

@media (max-width: 768px) {
  .live-hero {
    padding: 0.9rem;
    gap: 0.85rem;
  }

  .event-title {
    font-size: 1.05rem;
  }

  .hero-telemetry {
    width: 100%;
    justify-content: space-between;
  }

  .controls-box {
    align-items: flex-start;
  }

  .weather-strip {
    gap: 0.75rem 1rem;
  }
}
</style>
