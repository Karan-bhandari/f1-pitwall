<script setup>
defineProps({
  // Data for dropdowns
  years: Array,
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
  "update:year",
  "update:selectedEventKey",
  "update:selectedSessionName",
  "update:selectedDriver1",
  "update:selectedDriver2",
  "update:selectedLap1",
  "update:selectedLap2",
  "update:viewMode",
]);
</script>

<template>
  <div class="form-group">
    <label for="year-select">Year:</label>
    <select
      id="year-select"
      :value="year"
      @change="$emit('update:year', $event.target.value)"
    >
      <option v-for="y in years" :key="y" :value="y">{{ y }}</option>
    </select>
  </div>

  <p v-if="isLoadingEvents" class="loading-text">Loading events...</p>
  <p v-if="eventsError" class="error-text">{{ eventsError }}</p>
  <div v-if="!isLoadingEvents && events.length > 0" class="form-group">
    <label for="event-select">Event:</label>
    <select
      id="event-select"
      :value="selectedEventKey"
      @change="$emit('update:selectedEventKey', $event.target.value)"
    >
      <option value="">Select Event</option>
      <option v-for="ev in events" :key="ev.event_key" :value="ev.event_key">
        {{ ev.event_name }} ({{ ev.country }})
      </option>
    </select>
  </div>

  <p v-if="isLoadingSessions" class="loading-text">Loading sessions...</p>
  <p v-if="sessionsError" class="error-text">{{ sessionsError }}</p>
  <div v-if="!isLoadingSessions && sessions.length > 0" class="form-group">
    <label for="session-select">Session:</label>
    <select
      id="session-select"
      :value="selectedSessionName"
      @change="$emit('update:selectedSessionName', $event.target.value)"
    >
      <option value="">Select Session</option>
      <option v-for="s in sessions" :key="s.name" :value="s.name">
        {{ s.name }}
      </option>
    </select>
  </div>

  <div v-if="selectedSessionName" class="view-button-container">
    <button
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
    <div class="driver-controls">
      <div class="driver-group">
        <div class="form-group">
          <label for="driver1-select">Compare Driver 1:</label>
          <select
            id="driver1-select"
            :value="selectedDriver1"
            @change="$emit('update:selectedDriver1', $event.target.value)"
          >
            <option value="">Select Driver 1</option>
            <option
              v-for="d in drivers.filter(
                (d) => d.driver_number !== selectedDriver2,
              )"
              :key="d.driver_number"
              :value="d.driver_number"
            >
              {{ d.display_name }}
            </option>
          </select>
        </div>
        <div class="form-group" v-if="selectedDriver1">
          <label for="lap1-select">Select Lap (Driver 1):</label>
          <select
            id="lap1-select"
            :value="selectedLap1"
            @change="$emit('update:selectedLap1', $event.target.value)"
            :disabled="isLoadingComparison"
          >
            <option
              v-for="lap in lapsDriver1"
              :key="lap.lap_number"
              :value="lap.lap_number"
            >
              Lap {{ lap.lap_number }} ({{ lap.lap_time || "N/A" }})
            </option>
          </select>
        </div>
      </div>

      <div class="driver-group">
        <div class="form-group">
          <label for="driver2-select">Compare Driver 2:</label>
          <select
            id="driver2-select"
            :value="selectedDriver2"
            @change="$emit('update:selectedDriver2', $event.target.value)"
          >
            <option value="">Select Driver 2</option>
            <option
              v-for="d in drivers.filter(
                (d) => d.driver_number !== selectedDriver1,
              )"
              :key="d.driver_number"
              :value="d.driver_number"
            >
              {{ d.display_name }}
            </option>
          </select>
        </div>
        <div class="form-group" v-if="selectedDriver2">
          <label for="lap2-select">Select Lap (Driver 2):</label>
          <select
            id="lap2-select"
            :value="selectedLap2"
            @change="$emit('update:selectedLap2', $event.target.value)"
            :disabled="isLoadingComparison"
          >
            <option
              v-for="lap in lapsDriver2"
              :key="lap.lap_number"
              :value="lap.lap_number"
            >
              Lap {{ lap.lap_number }} ({{ lap.lap_time || "N/A" }})
            </option>
          </select>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.form-group {
  margin-bottom: 1.5rem;
}

label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 700;
  font-size: 0.85rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--muted-text-color);
}

select {
  width: 100%;
  padding: 0.75rem 1rem;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background-color: var(--input-bg-color);
  color: var(--text-color);
  font-size: 0.95rem;
  font-weight: 500;
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' fill='none' stroke='%236c757d' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m2 4 4 4 4-4'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 1rem center;
  transition: all 0.2s ease;
  cursor: pointer;
}

select:hover:not(:disabled) {
  border-color: var(--primary-color);
  background-color: var(--accent-color);
}

select:focus {
  outline: none;
  border-color: var(--primary-color);
  box-shadow: 0 0 0 3px var(--accent-color);
}

select:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.view-button-container {
  display: flex;
  justify-content: center;
  gap: 1.5rem;
  margin: 2rem 0;
  padding: 2rem 0;
  border-top: 1px solid var(--border-color);
  border-bottom: 1px solid var(--border-color);
}

.view-btn {
  padding: 0.8rem 2.5rem;
  border: 1px solid var(--border-color);
  background: var(--item-bg-color);
  color: var(--text-color);
  cursor: pointer;
  border-radius: 8px;
  font-weight: 700;
  font-size: 0.9rem;
  text-transform: uppercase;
  letter-spacing: 1px;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.view-btn:hover {
  border-color: var(--primary-color);
  color: var(--primary-color);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px var(--shadow-color);
}

.view-btn.selected {
  background: var(--primary-color);
  color: #ffffff;
  border-color: var(--primary-color);
  box-shadow: 0 4px 15px var(--accent-color);
}

.driver-controls {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 2rem;
  margin-top: 1.5rem;
  padding: 1.5rem;
  background: var(--item-bg-color);
  border-radius: 12px;
  border: 1px solid var(--border-color);
}

.driver-group {
  display: flex;
  flex-direction: column;
  gap: 1rem;
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
</style>
