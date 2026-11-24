<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from "vue";

const props = defineProps({
  id: {
    type: String,
    default: "",
  },
  modelValue: {
    type: [String, Number],
    default: "",
  },
  options: {
    type: Array,
    default: () => [],
  },
  placeholder: {
    type: String,
    default: "Select...",
  },
  searchPlaceholder: {
    type: String,
    default: "Filter...",
  },
  searchable: {
    type: Boolean,
    default: null,
  },
  disabled: {
    type: Boolean,
    default: false,
  },
  monoValue: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(["update:modelValue"]);

const isOpen = ref(false);
const searchQuery = ref("");
const highlightedIndex = ref(-1);
const rootRef = ref(null);
const triggerRef = ref(null);
const searchInputRef = ref(null);
const listRef = ref(null);

const showSearch = computed(() =>
  props.searchable !== null ? props.searchable : props.options.length > 8,
);

const isSameValue = (a, b) => {
  if (a === b) return true;
  if (a === null || a === undefined || b === null || b === undefined) {
    return false;
  }
  return String(a) === String(b);
};

const selectedOption = computed(
  () =>
    props.options.find((opt) => isSameValue(opt.value, props.modelValue)) ||
    null,
);

const triggerLabel = computed(() => {
  if (!selectedOption.value) return props.placeholder;
  return selectedOption.value.triggerLabel || selectedOption.value.label;
});

const filteredOptions = computed(() => {
  const q = searchQuery.value.trim().toLowerCase();
  if (!q) return props.options;
  return props.options.filter((opt) => {
    const haystack = [
      opt.label,
      opt.badge,
      opt.meta,
      opt.searchText,
      opt.value !== "" ? String(opt.value) : "",
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return haystack.includes(q);
  });
});

const scrollHighlightedIntoView = () => {
  nextTick(() => {
    const el = listRef.value?.querySelector(".pw-option.highlighted");
    if (el) el.scrollIntoView({ block: "nearest" });
  });
};

const openPopover = () => {
  if (props.disabled) return;
  searchQuery.value = "";
  isOpen.value = true;
  const activeIdx = props.options.findIndex((opt) =>
    isSameValue(opt.value, props.modelValue),
  );
  highlightedIndex.value = activeIdx >= 0 ? activeIdx : 0;
  nextTick(() => {
    if (showSearch.value) {
      searchInputRef.value?.focus();
    }
    const targetEl =
      listRef.value?.querySelector(".pw-option.active") ||
      listRef.value?.querySelector(".pw-option.highlighted");
    if (targetEl) {
      targetEl.scrollIntoView({ block: "nearest" });
    }
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

const selectOption = (opt) => {
  emit("update:modelValue", opt.value);
  closePopover(true);
};

const handleSearchEnter = () => {
  const list = filteredOptions.value;
  if (list.length === 0) return;
  const idx =
    highlightedIndex.value >= 0 && highlightedIndex.value < list.length
      ? highlightedIndex.value
      : 0;
  selectOption(list[idx]);
};

watch(searchQuery, () => {
  highlightedIndex.value = filteredOptions.value.length > 0 ? 0 : -1;
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
  const len = filteredOptions.value.length;
  if (len === 0) return;
  if (e.key === "ArrowDown") {
    e.preventDefault();
    highlightedIndex.value = (highlightedIndex.value + 1 + len) % len;
    scrollHighlightedIntoView();
  } else if (e.key === "ArrowUp") {
    e.preventDefault();
    highlightedIndex.value = (highlightedIndex.value - 1 + len) % len;
    scrollHighlightedIntoView();
  } else if (e.key === "Home") {
    e.preventDefault();
    highlightedIndex.value = 0;
    scrollHighlightedIntoView();
  } else if (e.key === "End") {
    e.preventDefault();
    highlightedIndex.value = len - 1;
    scrollHighlightedIntoView();
  } else if (
    e.key === "Enter" &&
    document.activeElement !== searchInputRef.value
  ) {
    e.preventDefault();
    handleSearchEnter();
  }
};

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
  <div ref="rootRef" class="pw-select">
    <button
      :id="id || undefined"
      ref="triggerRef"
      type="button"
      class="pw-trigger"
      :class="{
        open: isOpen,
        placeholder: !selectedOption || selectedOption.value === '',
      }"
      :disabled="disabled"
      :aria-expanded="isOpen"
      aria-haspopup="listbox"
      @click="togglePopover"
    >
      <span class="pw-trigger-main">
        <span
          v-if="selectedOption?.color"
          class="pw-color-dot"
          :style="{ backgroundColor: selectedOption.color }"
        ></span>
        <span class="pw-trigger-label" :class="{ mono: monoValue }">
          {{ triggerLabel }}
        </span>
      </span>
      <svg
        class="pw-chevron"
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
      class="pw-popover"
      role="dialog"
      :aria-label="placeholder"
    >
      <div v-if="showSearch" class="pw-search-row">
        <input
          ref="searchInputRef"
          v-model="searchQuery"
          type="text"
          class="pw-search-input"
          :placeholder="searchPlaceholder"
          :aria-label="searchPlaceholder"
          @keydown.enter.prevent="handleSearchEnter"
        />
      </div>

      <div
        v-if="filteredOptions.length"
        ref="listRef"
        class="pw-list"
        role="listbox"
      >
        <button
          v-for="(opt, idx) in filteredOptions"
          :key="String(opt.value)"
          type="button"
          role="option"
          class="pw-option"
          :class="{
            active: isSameValue(opt.value, modelValue),
            highlighted: idx === highlightedIndex,
          }"
          :aria-selected="isSameValue(opt.value, modelValue)"
          @mouseenter="highlightedIndex = idx"
          @click="selectOption(opt)"
        >
          <span v-if="opt.badge" class="pw-badge mono">{{ opt.badge }}</span>
          <span
            v-else-if="opt.color"
            class="pw-color-dot"
            :style="{ backgroundColor: opt.color }"
          ></span>
          <span class="pw-option-label" :class="{ mono: monoValue }">
            {{ opt.label }}
          </span>
          <span
            v-if="opt.meta"
            class="pw-option-meta"
            :class="{ mono: opt.metaMono }"
          >
            {{ opt.meta }}
          </span>
        </button>
      </div>
      <div v-else class="pw-empty">No matches for "{{ searchQuery }}"</div>
    </div>
  </div>
</template>

<style scoped>
.pw-select {
  position: relative;
  width: 100%;
}

.pw-trigger {
  width: 100%;
  padding: 0.72rem 1rem;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background-color: var(--input-bg-color);
  color: var(--text-color);
  font-family: inherit;
  font-size: 0.95rem;
  font-weight: 500;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  text-align: left;
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    background-color 0.2s ease,
    box-shadow 0.2s ease;
}

.pw-trigger.placeholder {
  color: var(--muted-text-color);
}

.pw-trigger:hover:not(:disabled) {
  border-color: var(--primary-color);
  background-color: var(--accent-color);
}

.pw-trigger.open,
.pw-trigger:focus-visible {
  outline: none;
  border-color: var(--primary-color);
  box-shadow: 0 0 0 3px var(--accent-color);
}

.pw-trigger:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.pw-trigger-main {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  min-width: 0;
  flex: 1;
}

.pw-trigger-label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pw-chevron {
  color: var(--muted-text-color);
  flex-shrink: 0;
  transition: transform 0.18s ease;
}

.pw-trigger.open .pw-chevron {
  transform: rotate(180deg);
  color: var(--primary-color);
}

.pw-popover {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  right: 0;
  background: var(--card-bg-color);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  box-shadow: 0 12px 32px rgba(17, 17, 22, 0.22);
  padding: 0.55rem;
  z-index: 180;
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}

.pw-search-input {
  width: 100%;
  height: 36px;
  padding: 0 0.75rem;
  font-family: inherit;
  font-size: 0.85rem;
  font-weight: 500;
  border-radius: 6px;
  border: 1px solid var(--border-color);
  background: var(--item-bg-color);
  color: var(--text-color);
  box-sizing: border-box;
}

.pw-search-input::placeholder {
  color: var(--muted-text-color);
}

.pw-search-input:focus {
  outline: none;
  border-color: var(--primary-color);
  background: var(--input-bg-color);
}

.pw-list {
  max-height: min(320px, 50vh);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding-right: 2px;
}

.pw-option {
  width: 100%;
  border: 1px solid transparent;
  background: transparent;
  color: var(--text-color);
  font-family: inherit;
  font-size: 0.88rem;
  padding: 0.48rem 0.65rem;
  border-radius: 6px;
  display: flex;
  align-items: center;
  gap: 0.6rem;
  text-align: left;
  cursor: pointer;
  transition:
    background-color 0.14s ease,
    border-color 0.14s ease;
}

.pw-option:hover,
.pw-option.highlighted {
  background: var(--item-bg-color);
}

.pw-option.active {
  background: var(--accent-color);
  border-color: rgba(225, 6, 0, 0.3);
}

.pw-badge {
  font-size: 0.72rem;
  font-weight: 700;
  color: var(--muted-text-color);
  background: var(--item-bg-color);
  border: 1px solid var(--border-color);
  border-radius: 4px;
  padding: 0.12rem 0.38rem;
  flex-shrink: 0;
}

.pw-option.active .pw-badge {
  background: var(--primary-color);
  border-color: var(--primary-color);
  color: #ffffff;
}

.pw-color-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  flex-shrink: 0;
}

.pw-option-label {
  font-weight: 600;
  min-width: 0;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pw-option-meta {
  font-size: 0.78rem;
  color: var(--muted-text-color);
  white-space: nowrap;
  flex-shrink: 0;
}

.pw-empty {
  font-size: 0.84rem;
  color: var(--muted-text-color);
  text-align: center;
  padding: 0.8rem 0.5rem;
}
</style>
