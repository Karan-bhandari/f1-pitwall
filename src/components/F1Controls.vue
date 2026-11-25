<script setup>
import { computed } from "vue";
import F1Icon from "./F1Icon.vue";
import PitwallSelect from "./PitwallSelect.vue";

const props = defineProps({
  // Data for dropdowns
  events: Array,
  sessions: Array,
  drivers: Array,
  lapsDriver1: Array,
  lapsDriver2: Array,

  // v-model values
  year: [String, Number],
  selectedEventKey: String,
  selectedSessionName: String,
  selectedDriver1: String,
  selectedDriver2: String,
  selectedLap1: [String, Number],
  selectedLap2: [String, Number],

  // Status indicators
  isLoadingEvents: Boolean,
  eventsError: String,
  isLoadingSessions: Boolean,
  sessionsError: String,
  isLoadingDrivers: Boolean,
  driversError: String,
  isLoadingComparison: Boolean,
  viewMode: String,
});

defineEmits([
  "update:selectedEventKey",
  "update:selectedSessionName",
  "update:selectedDriver1",
  "update:selectedDriver2",
  "update:selectedLap1",
  "update:selectedLap2",
  "update:viewMode",
  "select-preset",
]);

const eventOptions = computed(() =>
  (props.events || []).map((ev, idx) => {
    const round = ev.round_number ?? ev.round ?? idx + 1;
    return {
      value: ev.event_key,
      badge: `R${String(round).padStart(2, "0")}`,
      label: ev.event_name,
      meta: ev.country || "",
      triggerLabel: ev.country
        ? `${ev.event_name} (${ev.country})`
        : ev.event_name,
    };
  }),
);

const sessionOptions = computed(() =>
  (props.sessions || []).map((s) => ({
    value: s.name,
    label: s.name,
  })),
);

const formatTeamColor = (c) => {
  if (!c) return "";
  return c.startsWith("#") ? c : `#${c}`;
};

const driver1Options = computed(() =>
  (props.drivers || []).map((d) => ({
    value: d.driver_number,
    label: d.display_name,
    meta: d.team || "",
    color: formatTeamColor(d.team_color),
  })),
);

const driver2Options = computed(() => [
  { value: "", label: "None (Single Driver)" },
  ...driver1Options.value,
]);

const buildLapOptions = (laps) =>
  (laps || []).map((lap) => ({
    value: lap.lap_number,
    badge: `L${String(lap.lap_number).padStart(2, "0")}`,
    label: lap.lap_time || "No Time",
    triggerLabel: `Lap ${lap.lap_number} (${lap.lap_time || "N/A"})`,
    searchText: `lap ${lap.lap_number}`,
  }));

const lap1Options = computed(() => buildLapOptions(props.lapsDriver1));
const lap2Options = computed(() => buildLapOptions(props.lapsDriver2));

const driverSlots = computed(() => [
  {
    key: "d1",
    driverId: "driver1-select",
    driverLabel: "Driver 1:",
    driverValue: props.selectedDriver1,
    driverOptions: driver1Options.value,
    driverPlaceholder: "Select Driver 1",
    driverEvent: "update:selectedDriver1",
    lapId: "lap1-select",
    lapLabel: "Select Lap (Driver 1):",
    lapValue: props.selectedLap1,
    lapOptions: lap1Options.value,
    lapEvent: "update:selectedLap1",
  },
  {
    key: "d2",
    driverId: "driver2-select",
    driverLabel: "Compare Driver 2 (Optional):",
    driverValue: props.selectedDriver2,
    driverOptions: driver2Options.value,
    driverPlaceholder: "None (Single Driver)",
    driverEvent: "update:selectedDriver2",
    lapId: "lap2-select",
    lapLabel: "Select Lap (Driver 2):",
    lapValue: props.selectedLap2,
    lapOptions: lap2Options.value,
    lapEvent: "update:selectedLap2",
  },
]);
</script>

<template>
  <p v-if="isLoadingEvents" class="loading-text">Loading events...</p>
  <p v-if="eventsError" class="error-text">{{ eventsError }}</p>
  <div v-if="!isLoadingEvents && events.length > 0" class="form-group">
    <label for="event-select">Event:</label>
    <PitwallSelect
      id="event-select"
      :modelValue="selectedEventKey"
      :options="eventOptions"
      placeholder="Select Event"
      searchPlaceholder="Filter by Grand Prix, country, or round..."
      @update:modelValue="$emit('update:selectedEventKey', $event)"
    />
  </div>

  <p v-if="isLoadingSessions" class="loading-text">Loading sessions...</p>
  <p v-if="sessionsError" class="error-text">{{ sessionsError }}</p>
  <div v-if="!isLoadingSessions && sessions.length > 1" class="form-group">
    <label for="session-select">Session:</label>
    <PitwallSelect
      id="session-select"
      :modelValue="selectedSessionName"
      :options="sessionOptions"
      placeholder="Select Session"
      :searchable="false"
      @update:modelValue="$emit('update:selectedSessionName', $event)"
    />
  </div>

  <div
    v-if="selectedSessionName && selectedSessionName !== 'Weekend Recap'"
    class="view-button-container"
  >
    <button
      type="button"
      class="view-btn"
      :class="{ selected: viewMode === 'summary' }"
      @click="$emit('update:viewMode', 'summary')"
    >
      {{
        selectedSessionName === "Race" || selectedSessionName === "Sprint"
          ? "Race Summary"
          : "Session Summary"
      }}
    </button>
    <button
      v-if="Number(year) >= 2018"
      type="button"
      class="view-btn"
      :class="{ selected: viewMode === 'comparison' }"
      @click="$emit('update:viewMode', 'comparison')"
    >
      Driver Comparison
    </button>
  </div>

  <p v-if="isLoadingDrivers" class="loading-text">Loading drivers...</p>
  <p v-if="driversError" class="error-text">{{ driversError }}</p>
  <div
    v-if="!isLoadingDrivers && drivers.length > 0 && viewMode === 'comparison'"
  >
    <div class="preset-controls-bar">
      <span class="preset-label">Quick Matchups:</span>
      <div class="preset-buttons">
        <button
          type="button"
          class="preset-btn"
          @click="$emit('select-preset', 'p1_vs_p2')"
          title="Compare P1 and P2 Leaders"
        >
          <F1Icon name="trophy" :size="14" /> P1 vs P2 (Leaders)
        </button>
        <button
          type="button"
          class="preset-btn"
          @click="$emit('select-preset', 'teammate')"
          title="Compare Teammates in Identical Machinery"
        >
          <F1Icon name="users" :size="14" /> Teammate Battle (Same Car)
        </button>
        <button
          type="button"
          class="preset-btn"
          @click="$emit('select-preset', 'anchor_p1')"
          title="Benchmark Driver 2 against P1 Leader"
        >
          <F1Icon name="stopwatch" :size="14" /> Benchmark vs P1
        </button>
      </div>
    </div>

    <div class="driver-controls">
      <div v-for="slot in driverSlots" :key="slot.key" class="driver-group">
        <div class="form-group">
          <label :for="slot.driverId">{{ slot.driverLabel }}</label>
          <PitwallSelect
            :id="slot.driverId"
            :modelValue="slot.driverValue"
            :options="slot.driverOptions"
            :placeholder="slot.driverPlaceholder"
            searchPlaceholder="Filter driver or team..."
            @update:modelValue="$emit(slot.driverEvent, $event)"
          />
        </div>
        <div class="form-group" v-if="slot.driverValue">
          <label :for="slot.lapId">{{ slot.lapLabel }}</label>
          <PitwallSelect
            :id="slot.lapId"
            :modelValue="slot.lapValue"
            :options="slot.lapOptions"
            placeholder="Select Lap"
            searchPlaceholder="Jump to lap (e.g. 14)..."
            :disabled="isLoadingComparison"
            monoValue
            @update:modelValue="$emit(slot.lapEvent, $event)"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.form-group {
  margin-bottom: 1.15rem;
}

label {
  display: block;
  margin-bottom: 0.45rem;
  font-weight: 700;
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.6px;
  color: var(--muted-text-color);
}

.view-button-container {
  display: flex;
  justify-content: center;
  gap: 1rem;
  margin: 1.5rem 0;
  padding: 1.25rem 0;
  border-top: 1px solid var(--border-color);
  border-bottom: 1px solid var(--border-color);
}

.view-btn {
  padding: 0.75rem 2rem;
  border: 1px solid var(--border-color);
  background: var(--item-bg-color);
  color: var(--text-color);
  cursor: pointer;
  border-radius: 8px;
  font-weight: 700;
  font-size: 0.875rem;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  transition:
    border-color 0.2s ease,
    color 0.2s ease,
    background-color 0.2s ease,
    transform 0.2s cubic-bezier(0.4, 0, 0.2, 1),
    box-shadow 0.2s ease;
}

.view-btn:hover:not(.selected) {
  border-color: var(--primary-color);
  color: var(--primary-color);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px var(--shadow-color);
}

.view-btn:focus-visible {
  outline: 2px solid var(--primary-color);
  outline-offset: 2px;
}

.view-btn.selected {
  background: var(--primary-color);
  color: #ffffff;
  border-color: var(--primary-color);
  box-shadow: 0 4px 12px var(--shadow-color);
}

.preset-controls-bar {
  display: flex;
  align-items: center;
  gap: 0.85rem;
  margin-top: 1.25rem;
  padding: 0.85rem 1.25rem;
  background: var(--item-bg-color);
  border-radius: 10px;
  border: 1px solid var(--border-color);
  flex-wrap: wrap;
}

.preset-label {
  font-size: 0.78rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--muted-text-color);
  white-space: nowrap;
}

.preset-buttons {
  display: flex;
  gap: 0.65rem;
  flex-wrap: wrap;
  flex: 1;
}

.preset-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.45rem;
  padding: 0.5rem 0.85rem;
  font-size: 0.8rem;
  font-weight: 700;
  border-radius: 6px;
  background: var(--card-bg-color);
  border: 1px solid var(--border-color);
  color: var(--text-color);
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    color 0.2s ease,
    background-color 0.2s ease,
    transform 0.2s ease;
  white-space: nowrap;
}

.preset-btn:hover {
  border-color: var(--primary-color);
  color: var(--primary-color);
  background: var(--accent-color);
  transform: translateY(-1px);
}

.preset-btn:focus-visible {
  outline: 2px solid var(--primary-color);
  outline-offset: 2px;
}

.driver-controls {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
  margin-top: 1.25rem;
  padding: 1.25rem 1.5rem;
  background: var(--item-bg-color);
  border-radius: 12px;
  border: 1px solid var(--border-color);
}

.driver-group {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.driver-group .form-group {
  margin-bottom: 0;
}

.loading-text,
.error-text {
  text-align: center;
  padding: 1.5rem;
  font-size: 0.9rem;
  font-weight: 500;
}

.error-text {
  color: var(--primary-color);
  background: var(--accent-color);
  border-radius: 8px;
  margin: 1rem 0;
}

/* --- Mobile Responsiveness --- */
@media (max-width: 768px) {
  .preset-controls-bar {
    flex-direction: column;
    align-items: stretch;
    gap: 0.6rem;
    padding: 1rem;
  }

  .preset-buttons {
    flex-direction: column;
    gap: 0.5rem;
  }

  .preset-btn {
    width: 100%;
    text-align: center;
    padding: 0.65rem 0.75rem;
  }

  .driver-controls {
    grid-template-columns: 1fr;
    gap: 1rem;
    padding: 1rem;
  }

  .view-button-container {
    flex-direction: column;
    gap: 0.75rem;
    padding: 1.5rem 0;
  }

  .view-btn {
    width: 100%;
    padding: 0.8rem 1rem;
  }
}
</style>
