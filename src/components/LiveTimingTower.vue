<script setup>
import { computed } from "vue";
import {
  formatSpeedKmh,
  getSpeedUnitLabel,
  getTyreIcon,
  unitSystem,
} from "../utils.js";
import F1Icon from "./F1Icon.vue";

const props = defineProps({
  standings: {
    type: Array,
    default: () => [],
  },
  bestSectors: {
    type: Array,
    default: () => [],
  },
  sessionType: {
    type: String,
    default: "",
  },
  sessionPart: {
    type: Number,
    default: null,
  },
  isLive: {
    type: Boolean,
    default: false,
  },
});

const isQualifying = computed(() => {
  const t = (props.sessionType || "").toLowerCase();
  return t.includes("qualifying") || t.includes("shootout");
});

const leaderLabel = computed(() => (isQualifying.value ? "POLE" : "LEADER"));

const formatCompoundShort = (compound) => {
  const c = (compound || "").toUpperCase();
  if (c.startsWith("SOFT")) return "S";
  if (c.startsWith("MEDIUM")) return "M";
  if (c.startsWith("HARD")) return "H";
  if (c.startsWith("INTER")) return "I";
  if (c.startsWith("WET")) return "W";
  return "?";
};

const getSegmentClass = (code) => {
  if (code === 2051) return "seg-purple";
  if (code === 2049) return "seg-green";
  if (code === 2048 || code === 2052) return "seg-yellow";
  if (code === 2064) return "seg-pit";
  return "seg-empty";
};

const getSectorTimeClass = (sector) => {
  if (!sector || !sector.value) return "time-muted";
  if (sector.overall_fastest) return "time-purple";
  if (sector.personal_fastest) return "time-green";
  return "";
};

const getSectorDisplay = (sector) => {
  if (!sector) return "—";
  return sector.value || sector.previous_value || "—";
};

const getDriverBadge = (driver) => {
  if (driver.did_not_start) return { text: "DNS", cls: "badge-dns" };
  if (driver.retired) return { text: "DNF", cls: "badge-dnf" };
  if (driver.stopped) {
    return props.isLive
      ? { text: "STOP", cls: "badge-stop" }
      : { text: "DNF", cls: "badge-dnf" };
  }
  if (driver.in_pit) return { text: "PIT", cls: "badge-pit" };
  if (driver.pit_out) return { text: "OUT", cls: "badge-out" };
  if (driver.knocked_out) return { text: "KO", cls: "badge-ko" };
  return null;
};

const paddedSectors = (driver) => {
  const list = Array.isArray(driver.sectors) ? driver.sectors : [];
  return [list[0] || null, list[1] || null, list[2] || null];
};
</script>

<template>
  <section class="tower-card">
    <div class="tower-header">
      <h3 class="tower-title">
        {{ isLive ? "Live Classification" : "Classification" }}
      </h3>
      <div
        v-if="bestSectors.length"
        class="best-sectors-strip"
        title="Fastest overall sector times across the entire session"
      >
        <span class="bs-label">Session Best:</span>
        <span
          v-for="bs in bestSectors"
          :key="bs.sector"
          class="bs-chip"
          :title="`Fastest Sector ${bs.sector} of session: ${bs.abbreviation} (${bs.value})`"
        >
          <span class="bs-sec">S{{ bs.sector }}</span>
          <span
            class="bs-dot"
            :style="{ backgroundColor: '#' + (bs.team_color || '777777') }"
          ></span>
          <span class="bs-driver">{{ bs.abbreviation }}</span>
          <span class="bs-time mono">{{ bs.value }}</span>
        </span>
      </div>
    </div>

    <div v-if="!standings.length" class="tower-empty">
      <p class="tower-empty-title">No timing data yet</p>
      <p class="tower-empty-sub">
        {{
          isLive
            ? "Classification will populate once drivers complete a timed sector or leave the pit lane."
            : "Session standings are not yet available. Use Refresh to check for updates."
        }}
      </p>
    </div>

    <div
      v-else
      tabindex="0"
      role="region"
      aria-label="Live Classification"
      class="table-wrapper"
    >
      <table class="timing-table">
        <thead>
          <tr>
            <th scope="col" class="col-pos sticky-pos">POS</th>
            <th scope="col" class="col-driver sticky-driver">DRIVER</th>
            <th scope="col" class="col-gap" title="Gap to Leader / Pole">
              GAP
            </th>
            <th
              scope="col"
              class="col-int"
              title="Interval to Car Ahead (Green = Closing)"
            >
              INT
            </th>
            <th scope="col" class="col-lap">LAST LAP</th>
            <th scope="col" class="col-lap">BEST LAP</th>
            <th
              scope="col"
              class="col-sector"
              title="Sector 1 (Last Completed Lap)"
            >
              S1
            </th>
            <th
              scope="col"
              class="col-sector"
              title="Sector 2 (Last Completed Lap)"
            >
              S2
            </th>
            <th
              scope="col"
              class="col-sector"
              title="Sector 3 (Last Completed Lap)"
            >
              S3
            </th>
            <th
              scope="col"
              class="col-tyre"
              title="Compound, Tyre Age (Laps), New (N) / Used (U)"
            >
              TYRE
            </th>
            <th scope="col" class="col-pits" title="Completed Pit Stops">
              PITS
            </th>
            <th
              scope="col"
              class="col-speed"
              :title="`Speed Trap (${getSpeedUnitLabel(unitSystem)})`"
            >
              ST
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="driver in standings"
            :key="driver.driver_number"
            class="driver-row"
            :class="{
              'row-retired':
                driver.retired || driver.stopped || driver.did_not_start,
              'row-knocked-out': driver.knocked_out,
              'row-cutoff': driver.cutoff,
            }"
          >
            <td class="col-pos sticky-pos">
              <div class="pos-cell">
                <span class="pos-num mono">{{ driver.position ?? "—" }}</span>
                <span
                  v-if="getDriverBadge(driver)"
                  class="status-pill"
                  :class="getDriverBadge(driver).cls"
                >
                  {{ getDriverBadge(driver).text }}
                </span>
              </div>
            </td>

            <th scope="row" class="col-driver sticky-driver">
              <div class="driver-cell">
                <span
                  class="team-bar"
                  :style="{
                    backgroundColor: '#' + (driver.team_color || '777777'),
                  }"
                ></span>
                <div class="driver-identity">
                  <div class="driver-top">
                    <span class="driver-tla">{{ driver.abbreviation }}</span>
                    <span class="driver-num mono"
                      >#{{ driver.driver_number }}</span
                    >
                    <span
                      v-if="driver.has_fastest_lap"
                      class="fl-badge"
                      title="Fastest Lap of Session"
                    >
                      <F1Icon name="stopwatch" :size="11" /> FL
                    </span>
                  </div>
                  <div class="driver-sub">
                    <span class="driver-fullname">{{ driver.full_name }}</span>
                  </div>
                </div>
              </div>
            </th>

            <td class="col-gap mono">
              <span
                v-if="
                  driver.position === 1 &&
                  (!driver.gap || driver.gap === 'LEADER')
                "
                class="leader-pill"
              >
                {{ leaderLabel }}
              </span>
              <span v-else>{{ driver.gap || "—" }}</span>
            </td>

            <td class="col-int mono">
              <span
                :class="{ 'catching-gap': driver.catching }"
                :title="driver.catching ? 'Closing on car ahead' : ''"
              >
                {{ driver.interval || "—" }}
              </span>
            </td>

            <td class="col-lap mono">
              <span
                :class="{
                  'time-purple': driver.last_lap_overall_fastest,
                  'time-green':
                    !driver.last_lap_overall_fastest &&
                    driver.last_lap_personal_fastest,
                }"
              >
                {{ driver.last_lap_time || "—" }}
              </span>
            </td>

            <td class="col-lap mono">
              <span :class="{ 'time-purple': driver.has_fastest_lap }">
                {{ driver.best_lap_time || "—" }}
              </span>
            </td>

            <td
              v-for="(sec, idx) in paddedSectors(driver)"
              :key="idx"
              class="col-sector"
            >
              <div class="sector-cell">
                <span class="sector-time mono" :class="getSectorTimeClass(sec)">
                  {{ getSectorDisplay(sec) }}
                </span>
                <div
                  v-if="sec?.segments?.length"
                  class="mini-sectors"
                  title="Mini-sectors: Purple = Session Best, Green = Personal Best, Yellow = Slower, Blue = Pit Lane"
                  aria-hidden="true"
                >
                  <span
                    v-for="(seg, sIdx) in sec.segments"
                    :key="sIdx"
                    class="mini-seg"
                    :class="getSegmentClass(seg)"
                  ></span>
                </div>
              </div>
            </td>

            <td class="col-tyre">
              <div
                v-if="driver.compound && driver.compound !== 'UNKNOWN'"
                class="tyre-cell"
              >
                <img
                  :src="getTyreIcon(driver.compound)"
                  :alt="driver.compound"
                  class="tyre-img"
                />
                <span class="tyre-code mono">{{
                  formatCompoundShort(driver.compound)
                }}</span>
                <span class="tyre-age mono">{{ driver.tyre_age }}L</span>
                <span
                  class="tyre-fresh"
                  :class="driver.tyre_new ? 'fresh-new' : 'fresh-used'"
                  :title="driver.tyre_new ? 'New tyre set' : 'Used tyre set'"
                >
                  {{ driver.tyre_new ? "N" : "U" }}
                </span>
              </div>
              <span v-else class="time-muted mono">—</span>
            </td>

            <td class="col-pits mono">
              {{ driver.pit_stops ?? 0 }}
            </td>

            <td class="col-speed mono">
              {{
                formatSpeedKmh(driver.speeds?.st, {
                  system: unitSystem,
                  decimals: 0,
                })
              }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<style scoped>
.tower-card {
  background: var(--card-bg-color);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  overflow: hidden;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.tower-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.75rem 1rem;
  min-height: 52px;
  border-bottom: 1px solid var(--border-color);
  background: var(--item-bg-color);
  flex-wrap: wrap;
}

.tower-title {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.8px;
}

.best-sectors-strip {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  flex-wrap: wrap;
  font-size: 0.74rem;
}

.bs-label {
  color: var(--muted-text-color);
  font-weight: 700;
}

.bs-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.28rem;
  padding: 0.14rem 0.45rem;
  border-radius: 5px;
  border: 1px solid var(--border-color);
  background: var(--card-bg-color);
}

.bs-sec {
  font-weight: 800;
  color: var(--muted-text-color);
}

.bs-dot {
  width: 3px;
  height: 11px;
  border-radius: 2px;
}

.bs-driver {
  font-weight: 800;
}

.bs-time {
  color: #7e22ce;
  font-weight: 700;
}

html[data-theme="dark"] .bs-time {
  color: #c084fc;
}

.tower-empty {
  padding: 2.5rem 1.25rem;
  text-align: center;
  color: var(--muted-text-color);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.35rem;
}

.tower-empty-title {
  margin: 0;
  font-size: 0.92rem;
  font-weight: 700;
  color: var(--text-color);
}

.tower-empty-sub {
  margin: 0;
  font-size: 0.82rem;
  max-width: 44ch;
}

.table-wrapper {
  overflow: auto;
  max-inline-size: 100%;
  flex: 1 1 0;
  min-height: 0;
  background: var(--card-bg-color);
}

@media (max-width: 1280px) {
  .tower-card {
    height: auto;
  }

  .table-wrapper {
    flex: initial;
    max-block-size: 72vh;
  }
}

.table-wrapper:focus-visible {
  outline: 2px solid var(--primary-color);
  outline-offset: -2px;
}

.timing-table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  font-size: 0.8rem;
}

thead th {
  position: sticky;
  inset-block-start: 0;
  z-index: 3;
  background: var(--item-bg-color);
  color: var(--muted-text-color);
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.5px;
  text-align: left;
  padding: 0.48rem 0.42rem;
  border-bottom: 1px solid var(--border-color);
  white-space: nowrap;
}

tbody td,
tbody th {
  padding: 0.44rem 0.42rem;
  border-bottom: 1px solid var(--border-color);
  white-space: nowrap;
  vertical-align: middle;
  text-align: left;
  background: var(--card-bg-color);
  font-weight: 500;
}

tbody tr:hover td,
tbody tr:hover th {
  background: var(--item-bg-color);
}

.sticky-pos {
  position: sticky;
  inset-inline-start: 0;
  z-index: 2;
  width: 68px;
  min-width: 68px;
}

.sticky-driver {
  position: sticky;
  inset-inline-start: 68px;
  z-index: 2;
}

thead .sticky-pos,
thead .sticky-driver {
  z-index: 4;
}

.pos-cell {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.pos-num {
  font-weight: 800;
  font-size: 0.9rem;
  min-width: 1.4rem;
}

.status-pill {
  font-size: 0.64rem;
  font-weight: 800;
  padding: 0.1rem 0.32rem;
  border-radius: 4px;
  letter-spacing: 0.4px;
}
.badge-pit {
  background: rgba(56, 189, 248, 0.18);
  color: #0369a1;
}
.badge-out {
  background: rgba(34, 197, 94, 0.16);
  color: #15803d;
}
.badge-dnf,
.badge-stop {
  background: rgba(225, 6, 0, 0.16);
  color: #b91c1c;
}
.badge-dns,
.badge-ko {
  background: rgba(148, 163, 184, 0.22);
  color: var(--muted-text-color);
}

html[data-theme="dark"] .badge-pit {
  color: #38bdf8;
}
html[data-theme="dark"] .badge-out {
  color: #4ade80;
}
html[data-theme="dark"] .badge-dnf,
html[data-theme="dark"] .badge-stop {
  color: #fca5a5;
}

.driver-cell {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  min-width: 108px;
}

.team-bar {
  width: 4px;
  height: 26px;
  border-radius: 2px;
  flex-shrink: 0;
}

.driver-identity {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  line-height: 1.2;
}

.driver-top {
  display: flex;
  align-items: center;
  gap: 0.3rem;
}

.driver-tla {
  font-weight: 800;
  font-size: 0.85rem;
  letter-spacing: 0.4px;
}

.driver-num {
  font-size: 0.7rem;
  color: var(--muted-text-color);
}

.driver-fullname {
  font-size: 0.7rem;
  color: var(--muted-text-color);
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: block;
  text-align: left;
}

.fl-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.18rem;
  font-size: 0.64rem;
  font-weight: 800;
  padding: 0.08rem 0.3rem;
  border-radius: 4px;
  background: rgba(168, 85, 247, 0.16);
  color: #7e22ce;
}

html[data-theme="dark"] .fl-badge {
  color: #c084fc;
}

.leader-pill {
  font-size: 0.68rem;
  font-weight: 800;
  padding: 0.12rem 0.38rem;
  border-radius: 4px;
  background: var(--accent-color);
  color: #b91c1c;
  letter-spacing: 0.4px;
}

html[data-theme="dark"] .leader-pill {
  color: #ff6b5b;
}

.catching-gap {
  color: #15803d;
  font-weight: 700;
}

html[data-theme="dark"] .catching-gap {
  color: #4ade80;
}

.time-purple {
  color: #7e22ce;
  font-weight: 700;
}

html[data-theme="dark"] .time-purple {
  color: #c084fc;
}

.time-green {
  color: #15803d;
  font-weight: 700;
}
html[data-theme="dark"] .time-green {
  color: #4ade80;
}

.time-muted {
  color: var(--muted-text-color);
}

.sector-cell {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  min-width: 50px;
}

.sector-time {
  font-size: 0.78rem;
}

.mini-sectors {
  display: flex;
  gap: 1.5px;
  height: 4px;
}

.mini-seg {
  flex: 1;
  min-width: 3px;
  max-width: 6px;
  border-radius: 1px;
}

.seg-purple {
  background-color: #a855f7;
}
.seg-green {
  background-color: #22c55e;
}
.seg-yellow {
  background-color: #eab308;
}
.seg-pit {
  background-color: #38bdf8;
}
.seg-empty {
  background-color: var(--border-color);
}

.tyre-cell {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
}

.tyre-img {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.tyre-code {
  font-weight: 700;
  font-size: 0.8rem;
}

.tyre-age {
  font-size: 0.76rem;
  color: var(--muted-text-color);
}

.tyre-fresh {
  font-size: 0.64rem;
  font-weight: 800;
  padding: 0.05rem 0.26rem;
  border-radius: 3px;
}
.fresh-new {
  background: rgba(34, 197, 94, 0.16);
  color: #15803d;
}
.fresh-used {
  background: var(--item-bg-color);
  color: var(--muted-text-color);
}
html[data-theme="dark"] .fresh-new {
  color: #4ade80;
}

.row-retired td,
.row-retired th,
.row-knocked-out td,
.row-knocked-out th {
  opacity: 0.72;
}

.row-cutoff td,
.row-cutoff th {
  border-bottom: 2px dashed var(--primary-color);
}

@media (max-width: 1380px) {
  .col-speed {
    display: none;
  }
}

@media (max-width: 900px) {
  .sticky-driver {
    box-shadow: 2px 0 6px -3px var(--shadow-color);
  }
}

@media (max-width: 768px) {
  .sticky-pos {
    width: 62px;
    min-width: 62px;
  }

  .sticky-driver {
    inset-inline-start: 62px;
  }

  .driver-cell {
    min-width: 90px;
  }

  .driver-sub {
    display: none;
  }
}
</style>
