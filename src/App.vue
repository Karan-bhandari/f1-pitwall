<script setup>
import { ref, watch, onMounted } from "vue";
import { RouterLink, RouterView, useRoute } from "vue-router";
import { Analytics } from "@vercel/analytics/vue";
import F1Icon from "@/components/F1Icon.vue";

const route = useRoute();

// --- Theme State ---
const theme = ref("light");
const toggleTheme = () => {
  theme.value = theme.value === "light" ? "dark" : "light";
  localStorage.setItem("f1_pitwall_theme", theme.value);
  document.documentElement.setAttribute("data-theme", theme.value);
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

watch(theme, (newTheme) => {
  document.documentElement.setAttribute("data-theme", newTheme);
});

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
        document.documentElement.setAttribute("data-theme", theme.value);
      }
    });
  }
  document.documentElement.setAttribute("data-theme", theme.value);
});
</script>

<template>
  <div id="app-container">
    <Analytics />

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
          <select
            id="global-year-select"
            :value="year"
            @change="year = Number($event.target.value)"
          >
            <option v-for="y in years" :key="y" :value="y">{{ y }}</option>
          </select>
        </div>

        <button
          class="theme-toggle"
          @click="toggleTheme"
          title="Toggle Theme"
          aria-label="Toggle Theme"
        >
          <F1Icon :name="theme === 'light' ? 'moon' : 'sun'" :size="18" />
        </button>
      </div>
    </header>

    <!-- Page Content View -->
    <main class="app-main">
      <RouterView v-slot="{ Component }">
        <component
          :is="Component"
          :year="Number(year)"
          :years="years"
          :theme="theme"
          @update:year="(val) => (year = Number(val))"
        />
      </RouterView>
    </main>
  </div>
</template>

<style>
:root,
html[data-theme="light"] {
  --bg-color: #f4f4f6;
  --card-bg-color: #ffffff;
  --text-color: #111116;
  --muted-text-color: #555560;
  --primary-color: #e10600;
  --accent-color: rgba(225, 6, 0, 0.08);
  --border-color: #d0d0d7;
  --input-bg-color: #ffffff;
  --item-bg-color: #eaeaef;
  --shadow-color: rgba(17, 17, 22, 0.07);
}

html[data-theme="dark"] {
  --bg-color: #0a0a0e;
  --card-bg-color: #15151e;
  --text-color: #f1f1f6;
  --muted-text-color: #9898a6;
  --primary-color: #ff1801;
  --accent-color: rgba(255, 24, 1, 0.15);
  --border-color: #2a2a3c;
  --input-bg-color: #1a1a24;
  --item-bg-color: #1e1e2a;
  --shadow-color: rgba(0, 0, 0, 0.55);
}

* {
  box-sizing: border-box;
}

.mono {
  font-family: "JetBrains Mono", monospace;
  font-variant-numeric: tabular-nums;
}

body {
  font-family:
    "Inter",
    -apple-system,
    BlinkMacSystemFont,
    "Segoe UI",
    Roboto,
    sans-serif;
  background-color: var(--bg-color);
  color: var(--text-color);
  margin: 0;
  padding: 1.5rem;
  line-height: 1.5;
  transition:
    background-color 0.3s ease,
    color 0.3s ease;
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
    background-color 0.3s ease,
    border-color 0.3s ease;
}

/* Header Bar */
.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1.5rem;
  padding-bottom: 1.5rem;
  margin-bottom: 2rem;
  border-bottom: 1px solid var(--border-color);
  flex-wrap: wrap;
}

.header-brand-nav {
  display: flex;
  align-items: center;
  gap: 2rem;
  flex-wrap: wrap;
}

.brand-link {
  text-decoration: none;
  padding: 0;
  background-color: transparent;
}

.brand-link:hover {
  background-color: transparent;
}

.brand-title {
  font-size: 1.6rem;
  font-weight: 900;
  margin: 0;
  color: var(--primary-color);
  text-transform: uppercase;
  letter-spacing: 2px;
}

.nav-tabs {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.nav-tab {
  text-decoration: none;
  color: var(--muted-text-color);
  font-weight: 600;
  font-size: 0.95rem;
  padding: 0.5rem 0.85rem;
  border-radius: 6px;
  border-bottom: 2px solid transparent;
  transition: all 0.2s ease;
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

.header-controls {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.global-year-wrapper {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.year-label {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--muted-text-color);
}

#global-year-select {
  padding: 0.45rem 0.85rem;
  font-size: 0.95rem;
  font-weight: 600;
  border-radius: 6px;
  border: 1px solid var(--border-color);
  background-color: var(--input-bg-color);
  color: var(--text-color);
  font-family: "JetBrains Mono", monospace;
  font-variant-numeric: tabular-nums;
  cursor: pointer;
  transition: border-color 0.2s ease;
}

#global-year-select:focus {
  outline: none;
  border-color: var(--primary-color);
}

.theme-toggle {
  background: var(--item-bg-color);
  border: 1px solid var(--border-color);
  color: var(--text-color);
  cursor: pointer;
  border-radius: 8px;
  width: 40px;
  height: 40px;
  font-size: 1.1rem;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.theme-toggle:hover {
  background-color: var(--accent-color);
  border-color: var(--primary-color);
  transform: scale(1.05);
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
    gap: 1rem;
    padding-bottom: 1rem;
    margin-bottom: 1.5rem;
  }

  .header-brand-nav {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.85rem;
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
    gap: 0.35rem;
  }

  .nav-tab {
    padding: 0.4rem 0.65rem;
    font-size: 0.875rem;
    flex-shrink: 0;
  }

  .header-controls {
    justify-content: space-between;
    width: 100%;
    padding-top: 0.5rem;
    border-top: 1px solid var(--border-color);
  }

  .theme-toggle {
    width: 36px;
    height: 36px;
    font-size: 1rem;
  }
}
</style>
