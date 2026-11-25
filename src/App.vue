<script setup>
import { ref, watch, onMounted, onUnmounted } from "vue";
import { RouterLink, RouterView, useRoute } from "vue-router";
import F1Icon from "@/components/F1Icon.vue";
import SeasonPicker from "@/components/SeasonPicker.vue";
import { getLiveStatus } from "./api.js";
import { setUnitSystem, unitSystem } from "./utils.js";

const route = useRoute();
const isLiveSession = ref(false);
let liveStatusTimer = null;

const refreshLiveBadge = async () => {
  if (typeof document !== "undefined" && document.hidden) return;
  try {
    const status = await getLiveStatus();
    isLiveSession.value = Boolean(status?.is_live);
  } catch {
    // Nav live badge polling should fail silently
  }
};

const handleVisibilityForBadge = () => {
  if (!document.hidden) {
    refreshLiveBadge();
  }
};

// --- Theme State ---
const theme = ref("light");
const toggleTheme = () => {
  theme.value = theme.value === "light" ? "dark" : "light";
  localStorage.setItem("f1_pitwall_theme", theme.value);
};

// --- Season State ---
const currentYear = new Date().getFullYear();
const year = ref(currentYear);
const years = Array.from(
  { length: currentYear - 1950 + 1 },
  (_, i) => currentYear - i,
);

watch(
  () => route.query.year,
  (newYear) => {
    if (newYear) {
      const parsed = Number(newYear);
      if (!isNaN(parsed) && years.includes(parsed) && parsed !== year.value) {
        year.value = parsed;
      }
    }
  },
  { immediate: true },
);

watch(
  theme,
  (newTheme) => {
    document.documentElement.setAttribute("data-theme", newTheme);
  },
  { immediate: true },
);

onMounted(() => {
  const savedTheme = localStorage.getItem("f1_pitwall_theme");
  if (savedTheme === "light" || savedTheme === "dark") {
    theme.value = savedTheme;
  } else {
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    theme.value = mediaQuery.matches ? "dark" : "light";
    mediaQuery.addEventListener("change", (e) => {
      if (!localStorage.getItem("f1_pitwall_theme")) {
        theme.value = e.matches ? "dark" : "light";
      }
    });
  }
  refreshLiveBadge();
  liveStatusTimer = setInterval(refreshLiveBadge, 60000);
  document.addEventListener("visibilitychange", handleVisibilityForBadge);
});

onUnmounted(() => {
  if (liveStatusTimer) {
    clearInterval(liveStatusTimer);
    liveStatusTimer = null;
  }
  document.removeEventListener("visibilitychange", handleVisibilityForBadge);
});
</script>

<template>
  <div id="app-container">
    <!-- App Shell Header Bar -->
    <header class="app-header">
      <div class="header-brand-nav">
        <RouterLink to="/" class="brand-link">
          <h1 class="brand-title">F1 PitWall</h1>
        </RouterLink>

        <nav class="nav-tabs" aria-label="Main Navigation">
          <RouterLink to="/" class="nav-tab" exact-active-class="active">
            Season Hub
          </RouterLink>
          <RouterLink to="/race" class="nav-tab" active-class="active">
            Race PitWall
          </RouterLink>
          <RouterLink
            to="/live"
            class="nav-tab nav-tab-live"
            active-class="active"
          >
            <span>Live</span>
            <span
              v-if="isLiveSession"
              class="live-nav-dot"
              title="Live F1 Session Active"
              aria-label="Session live"
            ></span>
          </RouterLink>
          <RouterLink to="/drivers" class="nav-tab" active-class="active">
            Drivers
          </RouterLink>
          <RouterLink to="/constructors" class="nav-tab" active-class="active">
            Constructors
          </RouterLink>
        </nav>
      </div>

      <div class="header-controls">
        <div class="global-year-wrapper">
          <label for="global-year-select" class="year-label">Season:</label>
          <SeasonPicker v-model="year" :years="years" />
        </div>

        <div class="unit-toggle" role="group" aria-label="Unit system">
          <button
            type="button"
            class="unit-btn"
            :class="{ active: unitSystem === 'metric' }"
            :aria-pressed="unitSystem === 'metric'"
            @click="setUnitSystem('metric')"
            title="Metric units (°C, km/h)"
          >
            Metric
          </button>
          <button
            type="button"
            class="unit-btn"
            :class="{ active: unitSystem === 'imperial' }"
            :aria-pressed="unitSystem === 'imperial'"
            @click="setUnitSystem('imperial')"
            title="Imperial units (°F, mph)"
          >
            Imperial
          </button>
        </div>

        <button
          type="button"
          class="theme-toggle"
          @click="toggleTheme"
          :title="
            theme === 'light' ? 'Switch to dark theme' : 'Switch to light theme'
          "
          :aria-label="
            theme === 'light' ? 'Switch to dark theme' : 'Switch to light theme'
          "
        >
          <F1Icon :name="theme === 'light' ? 'moon' : 'sun'" :size="18" />
        </button>
      </div>
    </header>

    <!-- Page Content View -->
    <main class="app-main">
      <RouterView v-slot="{ Component }">
        <component :is="Component" :year="Number(year)" :theme="theme" />
      </RouterView>
    </main>
  </div>
</template>

<style>
body {
  padding: 1.5rem;
}

#app-container {
  width: 100%;
  max-width: 1400px;
  margin: 0 auto;
  background: var(--card-bg-color);
  padding: 2rem 2.5rem;
  border-radius: 12px;
  box-shadow: 0 8px 30px var(--shadow-color);
  border: 1px solid var(--border-color);
  position: relative;
  transition:
    background-color 0.25s ease,
    border-color 0.25s ease;
}

/* Header Bar */
.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1.25rem;
  padding-bottom: 1.35rem;
  margin-bottom: 2rem;
  border-bottom: 1px solid var(--border-color);
  flex-wrap: wrap;
}

.header-brand-nav {
  display: flex;
  align-items: center;
  gap: 1.75rem;
  flex-wrap: wrap;
  min-width: 0;
}

.brand-link {
  text-decoration: none;
  padding: 0.15rem 0.25rem;
  margin: -0.15rem -0.25rem;
  border-radius: 6px;
  display: inline-flex;
  align-items: center;
}

.brand-title {
  font-size: 1.55rem;
  font-weight: 900;
  line-height: 1.1;
  margin: 0;
  color: var(--primary-color);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.nav-tabs {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.nav-tab {
  text-decoration: none;
  color: var(--muted-text-color);
  font-weight: 600;
  font-size: 0.925rem;
  line-height: 1.25;
  padding: 0.5rem 0.85rem;
  border-radius: 6px;
  border-bottom: 2px solid transparent;
  white-space: nowrap;
  transition:
    color 0.18s ease,
    background-color 0.18s ease,
    border-color 0.18s ease;
}

.nav-tab:hover {
  color: var(--text-color);
  background-color: var(--item-bg-color);
}

.nav-tab.active {
  color: var(--primary-color);
  border-bottom-color: var(--primary-color);
  background-color: var(--accent-color);
}

.nav-tab-live {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
}

.live-nav-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: var(--primary-color);
  box-shadow: 0 0 0 0 rgba(225, 6, 0, 0.7);
  animation: live-nav-pulse 1.8s infinite;
  flex-shrink: 0;
}

@keyframes live-nav-pulse {
  0% {
    box-shadow: 0 0 0 0 rgba(225, 6, 0, 0.7);
  }
  70% {
    box-shadow: 0 0 0 6px rgba(225, 6, 0, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(225, 6, 0, 0);
  }
}

.header-controls {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.global-year-wrapper {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.year-label {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--muted-text-color);
}

.unit-toggle {
  display: inline-flex;
  align-items: center;
  height: 38px;
  border: 1px solid var(--border-color);
  border-radius: 7px;
  background: var(--item-bg-color);
  padding: 3px;
  gap: 2px;
  flex-shrink: 0;
}

.unit-btn {
  border: none;
  background: transparent;
  color: var(--muted-text-color);
  font-family: inherit;
  font-size: 0.8rem;
  font-weight: 700;
  height: 100%;
  padding: 0 0.65rem;
  border-radius: 5px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition:
    color 0.15s ease,
    background-color 0.15s ease,
    box-shadow 0.15s ease;
  white-space: nowrap;
}

.unit-btn:hover {
  color: var(--text-color);
}

.unit-btn.active {
  background: var(--card-bg-color);
  color: var(--primary-color);
  box-shadow: 0 1px 2px var(--shadow-color);
}

.theme-toggle {
  background: var(--item-bg-color);
  border: 1px solid var(--border-color);
  color: var(--text-color);
  cursor: pointer;
  border-radius: 7px;
  width: 38px;
  height: 38px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition:
    background-color 0.18s ease,
    border-color 0.18s ease,
    color 0.18s ease,
    transform 0.15s ease;
  flex-shrink: 0;
}

.theme-toggle:hover {
  background-color: var(--accent-color);
  border-color: var(--primary-color);
  color: var(--primary-color);
}

.theme-toggle:active {
  transform: scale(0.95);
}

.app-main {
  width: 100%;
}

/* --- Mobile Responsiveness --- */
@media (max-width: 768px) {
  body {
    padding: 0.5rem;
  }

  #app-container {
    padding: 1.25rem 1rem;
    border-radius: 8px;
    box-shadow: none;
  }

  .app-header {
    flex-direction: column;
    align-items: stretch;
    gap: 0.85rem;
    padding-bottom: 1rem;
    margin-bottom: 1.5rem;
  }

  .header-brand-nav {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.75rem;
    width: 100%;
  }

  .brand-title {
    font-size: 1.35rem;
  }

  .nav-tabs {
    width: 100%;
    overflow-x: auto;
    white-space: nowrap;
    padding-bottom: 0.25rem;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
    gap: 0.35rem;
  }

  .nav-tabs::-webkit-scrollbar {
    display: none;
  }

  .nav-tab {
    padding: 0.45rem 0.7rem;
    font-size: 0.875rem;
    flex-shrink: 0;
  }

  .header-controls {
    justify-content: space-between;
    flex-wrap: nowrap;
    gap: 0.45rem;
    width: 100%;
    padding-top: 0.75rem;
    border-top: 1px solid var(--border-color);
  }

  .year-label {
    font-size: 0.8rem;
  }

  .unit-toggle {
    height: 36px;
  }

  .unit-btn {
    padding: 0.3rem 0.5rem;
    font-size: 0.75rem;
  }

  .theme-toggle {
    width: 36px;
    height: 36px;
  }
}
</style>
