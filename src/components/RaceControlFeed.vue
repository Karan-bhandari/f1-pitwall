<script setup>
import { ref, computed } from "vue";
import {
  formatOffsetLabel,
  formatTimeInZone,
  getLocalTimezoneLabel,
} from "../utils.js";

const props = defineProps({
  messages: {
    type: Array,
    default: () => [],
  },
  timeMode: {
    type: String,
    default: "local",
  },
  gmtOffset: {
    type: String,
    default: "",
  },
  zoneLabel: {
    type: String,
    default: "",
  },
});

const activeFilter = ref("all");

const zoneBadgeLabel = computed(() => {
  if (props.zoneLabel) return props.zoneLabel;
  if (props.timeMode === "track" && props.gmtOffset) {
    return formatOffsetLabel(props.gmtOffset) || "Track";
  }
  return getLocalTimezoneLabel();
});

const filteredMessages = computed(() => {
  if (!Array.isArray(props.messages)) return [];
  if (activeFilter.value === "flags") {
    return props.messages.filter((m) => {
      const cat = (m.category || "").toLowerCase();
      const flag = (m.flag || "").toUpperCase();
      const msg = (m.message || "").toUpperCase();
      return (
        cat === "flag" ||
        cat === "safetycar" ||
        Boolean(flag) ||
        msg.includes("SAFETY CAR") ||
        msg.includes("VSC")
      );
    });
  }
  if (activeFilter.value === "incidents") {
    return props.messages.filter((m) => {
      const cat = (m.category || "").toLowerCase();
      const msg = (m.message || "").toUpperCase();
      return (
        cat === "other" ||
        cat === "carEvent".toLowerCase() ||
        msg.includes("INCIDENT") ||
        msg.includes("INVESTIGAT") ||
        msg.includes("PENALTY") ||
        msg.includes("TRACK LIMITS") ||
        msg.includes("NOTED")
      );
    });
  }
  return props.messages;
});

const formatTime = (utcStr) =>
  formatTimeInZone(utcStr, {
    mode: props.timeMode,
    gmtOffset: props.gmtOffset,
    includeSeconds: true,
  });

const getBadge = (msg) => {
  const flag = (msg.flag || "").toUpperCase();
  const text = (msg.message || "").toUpperCase();
  if (flag === "RED" || text.includes("RED FLAG"))
    return { label: "RED", cls: "rc-red" };
  if (text.includes("SAFETY CAR") && !text.includes("VIRTUAL"))
    return { label: "SC", cls: "rc-yellow" };
  if (text.includes("VIRTUAL SAFETY CAR") || text.includes("VSC"))
    return { label: "VSC", cls: "rc-yellow" };
  if (flag === "YELLOW" || flag === "DOUBLE YELLOW")
    return { label: "YELLOW", cls: "rc-yellow" };
  if (flag === "GREEN" || flag === "CLEAR")
    return { label: flag, cls: "rc-green" };
  if (flag === "CHEQUERED") return { label: "CHEQUERED", cls: "rc-chequered" };
  if (flag === "BLUE") return { label: "BLUE", cls: "rc-blue" };
  if (flag) return { label: flag, cls: "rc-neutral" };
  return { label: (msg.category || "FIA").toUpperCase(), cls: "rc-neutral" };
};
</script>

<template>
  <aside class="rc-card" aria-label="Race Control Feed">
    <div class="rc-header">
      <div class="rc-title-group">
        <h3 class="rc-title">Race Control</h3>
        <span
          class="rc-tz-badge mono"
          :title="`Timestamps shown in ${zoneBadgeLabel}`"
        >
          {{ zoneBadgeLabel }}
        </span>
      </div>
      <div
        class="rc-filters"
        role="group"
        aria-label="Filter Race Control Messages"
      >
        <button
          type="button"
          class="filter-chip"
          :class="{ active: activeFilter === 'all' }"
          :aria-pressed="activeFilter === 'all'"
          @click="activeFilter = 'all'"
        >
          All
        </button>
        <button
          type="button"
          class="filter-chip"
          :class="{ active: activeFilter === 'flags' }"
          :aria-pressed="activeFilter === 'flags'"
          @click="activeFilter = 'flags'"
        >
          Flags / SC
        </button>
        <button
          type="button"
          class="filter-chip"
          :class="{ active: activeFilter === 'incidents' }"
          :aria-pressed="activeFilter === 'incidents'"
          @click="activeFilter = 'incidents'"
        >
          Incidents
        </button>
      </div>
    </div>

    <div v-if="!filteredMessages.length" class="rc-empty">
      <p class="rc-empty-title">
        {{
          messages.length
            ? "No messages match this filter"
            : "No race control messages yet"
        }}
      </p>
      <p class="rc-empty-sub">
        {{
          messages.length
            ? "Try switching filters to view all FIA stewards and track notices."
            : "FIA flags, safety car deployments, and steward notices will appear here."
        }}
      </p>
      <button
        v-if="messages.length && activeFilter !== 'all'"
        type="button"
        class="rc-reset-btn"
        @click="activeFilter = 'all'"
      >
        Show all messages
      </button>
    </div>

    <ul v-else class="rc-list">
      <li
        v-for="(msg, index) in filteredMessages"
        :key="`${msg.utc}-${index}`"
        class="rc-item"
      >
        <div class="rc-meta">
          <span class="rc-badge" :class="getBadge(msg).cls">
            {{ getBadge(msg).label }}
          </span>
          <span v-if="msg.lap" class="rc-pill mono">LAP {{ msg.lap }}</span>
          <span v-else-if="msg.sector" class="rc-pill mono"
            >SEC {{ msg.sector }}</span
          >
          <span class="rc-time mono">{{ formatTime(msg.utc) }}</span>
        </div>
        <p class="rc-text">{{ msg.message }}</p>
      </li>
    </ul>
  </aside>
</template>

<style scoped>
.rc-card {
  background: var(--card-bg-color);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  content-visibility: auto;
  contain-intrinsic-size: auto 360px;
}

.rc-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  min-height: 52px;
  border-bottom: 1px solid var(--border-color);
  background: var(--item-bg-color);
  flex-wrap: wrap;
}

.rc-title-group {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
}

.rc-title {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.8px;
}

.rc-tz-badge {
  font-size: 0.68rem;
  font-weight: 700;
  padding: 0.12rem 0.4rem;
  border-radius: 4px;
  border: 1px solid var(--border-color);
  background: var(--card-bg-color);
  color: var(--muted-text-color);
}

.rc-filters {
  display: flex;
  gap: 0.35rem;
}

.filter-chip {
  border: 1px solid var(--border-color);
  background: var(--card-bg-color);
  color: var(--muted-text-color);
  font-size: 0.72rem;
  font-weight: 700;
  padding: 0.25rem 0.55rem;
  border-radius: 999px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.filter-chip:hover {
  color: var(--text-color);
  border-color: var(--primary-color);
}

.filter-chip:focus-visible,
.rc-reset-btn:focus-visible {
  outline: 2px solid var(--primary-color);
  outline-offset: 2px;
}

.filter-chip.active {
  background: var(--accent-color);
  color: #b91c1c;
  border-color: var(--primary-color);
}

html[data-theme="dark"] .filter-chip.active {
  color: #ff6b5b;
}

.rc-empty {
  padding: 2rem 1.25rem;
  text-align: center;
  color: var(--muted-text-color);
  font-size: 0.85rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.35rem;
}

.rc-empty-title {
  margin: 0;
  font-weight: 700;
  color: var(--text-color);
}

.rc-empty-sub {
  margin: 0;
  font-size: 0.8rem;
  max-width: 34ch;
}

.rc-reset-btn {
  margin-top: 0.35rem;
  border: 1px solid var(--border-color);
  background: var(--item-bg-color);
  color: var(--text-color);
  font-size: 0.76rem;
  font-weight: 700;
  padding: 0.32rem 0.7rem;
  border-radius: 6px;
  cursor: pointer;
  transition: border-color 0.15s ease;
}

.rc-reset-btn:hover {
  border-color: var(--primary-color);
}

.rc-list {
  list-style: none;
  margin: 0;
  padding: 0;
  flex: 1 1 0;
  min-height: 0;
  overflow-y: auto;
}

@media (max-width: 1280px) {
  .rc-card {
    height: auto;
  }

  .rc-list {
    flex: initial;
    max-height: 460px;
  }
}

.rc-item {
  padding: 0.7rem 1rem;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.rc-item:last-child {
  border-bottom: none;
}

.rc-meta {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-wrap: wrap;
}

.rc-badge {
  font-size: 0.65rem;
  font-weight: 800;
  padding: 0.12rem 0.4rem;
  border-radius: 4px;
  letter-spacing: 0.4px;
}
.rc-red {
  background: rgba(225, 6, 0, 0.16);
  color: #b91c1c;
}
.rc-yellow {
  background: rgba(234, 179, 8, 0.22);
  color: #854d0e;
}
.rc-green {
  background: rgba(34, 197, 94, 0.18);
  color: #15803d;
}
.rc-blue {
  background: rgba(56, 189, 248, 0.18);
  color: #0369a1;
}
.rc-chequered {
  background: var(--text-color);
  color: var(--card-bg-color);
}
.rc-neutral {
  background: var(--item-bg-color);
  color: var(--muted-text-color);
}

html[data-theme="dark"] .rc-red {
  color: #fca5a5;
}
html[data-theme="dark"] .rc-yellow {
  color: #facc15;
}
html[data-theme="dark"] .rc-green {
  color: #4ade80;
}
html[data-theme="dark"] .rc-blue {
  color: #38bdf8;
}

.rc-pill {
  font-size: 0.68rem;
  font-weight: 700;
  padding: 0.1rem 0.35rem;
  border-radius: 4px;
  background: var(--item-bg-color);
  color: var(--text-color);
}

.rc-time {
  margin-left: auto;
  font-size: 0.72rem;
  color: var(--muted-text-color);
}

.rc-text {
  margin: 0;
  font-size: 0.82rem;
  line-height: 1.4;
  color: var(--text-color);
}
</style>
