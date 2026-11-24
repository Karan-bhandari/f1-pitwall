<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from "vue";

const props = defineProps({
  modelValue: {
    type: Number,
    required: true,
  },
  years: {
    type: Array,
    required: true,
  },
});

const emit = defineEmits(["update:modelValue"]);

const isOpen = ref(false);
const searchQuery = ref("");
const activeDecade = ref(Math.floor(props.modelValue / 10) * 10);
const highlightedIndex = ref(-1);
const rootRef = ref(null);
const triggerRef = ref(null);
const searchInputRef = ref(null);

const decades = computed(() => {
  const set = new Set();
  for (const y of props.years) {
    set.add(Math.floor(y / 10) * 10);
  }
  return Array.from(set).sort((a, b) => b - a);
});

const normalizedQuery = computed(() => searchQuery.value.trim());

const displayedYears = computed(() => {
  if (normalizedQuery.value) {
    return props.years
      .filter((y) => String(y).includes(normalizedQuery.value))
      .slice(0, 12);
  }
  return props.years.filter(
    (y) => Math.floor(y / 10) * 10 === activeDecade.value,
  );
});

const openPopover = () => {
  activeDecade.value = Math.floor(props.modelValue / 10) * 10;
  searchQuery.value = "";
  isOpen.value = true;
  nextTick(() => {
    const idx = displayedYears.value.indexOf(props.modelValue);
    highlightedIndex.value = idx >= 0 ? idx : 0;
    searchInputRef.value?.focus();
  });
};

const closePopover = (restoreFocus = false) => {
  if (!isOpen.value) return;
  isOpen.value = false;
  searchQuery.value = "";
  highlightedIndex.value = -1;
  if (restoreFocus) {
    nextTick(() => triggerRef.value?.focus());
  }
};

const togglePopover = () => {
  if (isOpen.value) {
    closePopover(false);
  } else {
    openPopover();
  }
};

const selectYear = (y) => {
  emit("update:modelValue", y);
  closePopover(true);
};

const handleSearchEnter = () => {
  const exact = props.years.find((y) => String(y) === normalizedQuery.value);
  if (exact !== undefined) {
    selectYear(exact);
    return;
  }
  const list = displayedYears.value;
  if (list.length > 0) {
    const idx =
      highlightedIndex.value >= 0 && highlightedIndex.value < list.length
        ? highlightedIndex.value
        : 0;
    selectYear(list[idx]);
  }
};

watch([searchQuery, activeDecade], () => {
  highlightedIndex.value = displayedYears.value.length > 0 ? 0 : -1;
});

const handleDocumentClick = (e) => {
  if (isOpen.value && rootRef.value && !rootRef.value.contains(e.target)) {
    closePopover(false);
  }
};

const handleKeydown = (e) => {
  if (!isOpen.value) return;
  if (e.key === "Escape") {
    e.stopPropagation();
    closePopover(true);
    return;
  }
  const len = displayedYears.value.length;
  if (len === 0) return;
  if (e.key === "ArrowRight") {
    e.preventDefault();
    highlightedIndex.value = (highlightedIndex.value + 1 + len) % len;
  } else if (e.key === "ArrowLeft") {
    e.preventDefault();
    highlightedIndex.value = (highlightedIndex.value - 1 + len) % len;
  } else if (e.key === "ArrowDown") {
    e.preventDefault();
    highlightedIndex.value = Math.min(
      len - 1,
      Math.max(0, highlightedIndex.value) + 4,
    );
  } else if (e.key === "ArrowUp") {
    e.preventDefault();
    highlightedIndex.value = Math.max(0, highlightedIndex.value - 4);
  } else if (
    e.key === "Enter" &&
    document.activeElement !== searchInputRef.value
  ) {
    e.preventDefault();
    handleSearchEnter();
  }
};

watch(
  () => props.modelValue,
  (val) => {
    activeDecade.value = Math.floor(val / 10) * 10;
  },
);

onMounted(() => {
  document.addEventListener("mousedown", handleDocumentClick);
  document.addEventListener("keydown", handleKeydown);
});

onUnmounted(() => {
  document.removeEventListener("mousedown", handleDocumentClick);
  document.removeEventListener("keydown", handleKeydown);
});
</script>

<template>
  <div ref="rootRef" class="season-picker">
    <button
      id="global-year-select"
      ref="triggerRef"
      type="button"
      class="season-trigger"
      :class="{ open: isOpen }"
      :aria-expanded="isOpen"
      aria-haspopup="dialog"
      aria-label="Select F1 season"
      @click="togglePopover"
    >
      <span class="season-trigger-value mono">{{ modelValue }}</span>
      <svg
        class="season-chevron"
        width="14"
        height="14"
        viewBox="0 0 16 16"
        fill="none"
        aria-hidden="true"
      >
        <path
          d="M4 6L8 10L12 6"
          stroke="currentColor"
          stroke-width="1.75"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </svg>
    </button>

    <div
      v-if="isOpen"
      class="season-popover"
      role="dialog"
      aria-label="Choose season year"
    >
      <div class="season-search-row">
        <input
          ref="searchInputRef"
          v-model="searchQuery"
          type="text"
          inputmode="numeric"
          maxlength="4"
          class="season-search-input mono"
          placeholder="Jump to year (e.g. 2007)"
          aria-label="Filter season year"
          @keydown.enter.prevent="handleSearchEnter"
        />
      </div>

      <div
        v-if="!normalizedQuery"
        class="decade-grid"
        role="tablist"
        aria-label="Select decade"
      >
        <button
          v-for="dec in decades"
          :key="dec"
          type="button"
          role="tab"
          class="decade-btn mono"
          :class="{ active: activeDecade === dec }"
          :aria-selected="activeDecade === dec"
          @click="activeDecade = dec"
        >
          {{ dec }}s
        </button>
      </div>

      <div v-if="displayedYears.length" class="year-grid">
        <button
          v-for="(y, idx) in displayedYears"
          :key="y"
          type="button"
          class="year-btn mono"
          :class="{
            active: y === modelValue,
            highlighted: idx === highlightedIndex,
          }"
          :aria-pressed="y === modelValue"
          @mouseenter="highlightedIndex = idx"
          @click="selectYear(y)"
        >
          {{ y }}
        </button>
      </div>
      <div v-else class="season-empty">
        No season matching "{{ searchQuery }}"
      </div>
    </div>
  </div>
</template>

<style scoped>
.season-picker {
  position: relative;
  display: inline-flex;
}

.season-trigger {
  height: 38px;
  padding: 0 0.65rem 0 0.8rem;
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  font-size: 0.9rem;
  font-weight: 700;
  border-radius: 7px;
  border: 1px solid var(--border-color);
  background-color: var(--input-bg-color);
  color: var(--text-color);
  cursor: pointer;
  transition:
    border-color 0.18s ease,
    background-color 0.18s ease;
}

.season-trigger:hover {
  border-color: var(--muted-text-color);
}

.season-trigger.open,
.season-trigger:focus-visible {
  border-color: var(--primary-color);
  outline: 2px solid var(--accent-color);
  outline-offset: 1px;
}

.season-chevron {
  color: var(--muted-text-color);
  transition: transform 0.18s ease;
  flex-shrink: 0;
}

.season-trigger.open .season-chevron {
  transform: rotate(180deg);
  color: var(--primary-color);
}

.season-popover {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  width: 268px;
  background: var(--card-bg-color);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  box-shadow: 0 12px 32px rgba(17, 17, 22, 0.18);
  padding: 0.7rem;
  z-index: 200;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.season-search-row {
  display: flex;
}

.season-search-input {
  width: 100%;
  height: 34px;
  padding: 0 0.65rem;
  font-size: 0.82rem;
  font-weight: 600;
  border-radius: 6px;
  border: 1px solid var(--border-color);
  background: var(--item-bg-color);
  color: var(--text-color);
  box-sizing: border-box;
}

.season-search-input::placeholder {
  color: var(--muted-text-color);
  font-family: inherit;
  font-weight: 500;
}

.season-search-input:focus {
  outline: none;
  border-color: var(--primary-color);
  background: var(--input-bg-color);
}

.decade-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 4px;
  padding-bottom: 0.55rem;
  border-bottom: 1px solid var(--border-color);
}

.decade-btn {
  border: 1px solid transparent;
  background: var(--item-bg-color);
  color: var(--muted-text-color);
  font-size: 0.74rem;
  font-weight: 700;
  padding: 0.3rem 0.25rem;
  border-radius: 5px;
  cursor: pointer;
  transition:
    background-color 0.15s ease,
    color 0.15s ease,
    border-color 0.15s ease;
}

.decade-btn:hover {
  color: var(--text-color);
  border-color: var(--border-color);
}

.decade-btn.active {
  background: var(--accent-color);
  color: var(--primary-color);
  border-color: rgba(225, 6, 0, 0.28);
}

.year-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 5px;
}

.year-btn {
  border: 1px solid var(--border-color);
  background: var(--card-bg-color);
  color: var(--text-color);
  font-size: 0.82rem;
  font-weight: 700;
  padding: 0.42rem 0.25rem;
  border-radius: 6px;
  cursor: pointer;
  transition:
    background-color 0.15s ease,
    color 0.15s ease,
    border-color 0.15s ease;
}

.year-btn:hover,
.year-btn.highlighted {
  background: var(--accent-color);
  border-color: var(--primary-color);
  color: var(--primary-color);
}

.year-btn.active {
  background: var(--primary-color);
  border-color: var(--primary-color);
  color: #ffffff;
}

.season-empty {
  font-size: 0.8rem;
  color: var(--muted-text-color);
  text-align: center;
  padding: 0.6rem 0.25rem;
}

@media (max-width: 768px) {
  .season-trigger {
    height: 36px;
    padding: 0 0.55rem 0 0.65rem;
    font-size: 0.85rem;
  }

  .season-popover {
    left: 0;
    right: auto;
    width: min(268px, calc(100vw - 2rem));
  }
}
</style>
