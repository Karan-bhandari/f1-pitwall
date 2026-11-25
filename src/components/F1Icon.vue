<template>
  <svg
    xmlns="http://www.w3.org/2000/svg"
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
    class="f1-icon"
    :class="`f1-icon-${name}`"
    aria-hidden="true"
  >
    <!-- Sun -->
    <template v-if="name === 'sun'">
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2" />
      <path d="M12 20v2" />
      <path d="M4.93 4.93l1.41 1.41" />
      <path d="M17.66 17.66l1.41 1.41" />
      <path d="M2 12h2" />
      <path d="M20 12h2" />
      <path d="M6.34 17.66l-1.41 1.41" />
      <path d="M19.07 4.93l-1.41 1.41" />
    </template>

    <!-- Moon -->
    <template v-else-if="name === 'moon'">
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </template>

    <!-- Trophy -->
    <template v-else-if="name === 'trophy'">
      <path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6" />
      <path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18" />
      <path d="M4 22h16" />
      <path d="M10 14.66V17h4v-2.34" />
      <path d="M12 2v12.66a4 4 0 0 0 4-4V6H8v3.34a4 4 0 0 0 4 4z" />
    </template>

    <!-- Crown -->
    <template v-else-if="name === 'crown'">
      <path d="M2 4l3 12h14l3-12-6 7-4-7-4 7-6-7z" />
      <path d="M5 20h14" />
    </template>

    <!-- Calculator -->
    <template v-else-if="name === 'calculator'">
      <rect x="4" y="2" width="16" height="20" rx="2" />
      <line x1="8" y1="6" x2="16" y2="6" />
      <line x1="8" y1="10" x2="8" y2="10" />
      <line x1="12" y1="10" x2="12" y2="10" />
      <line x1="16" y1="10" x2="16" y2="10" />
      <line x1="8" y1="14" x2="8" y2="14" />
      <line x1="12" y1="14" x2="12" y2="14" />
      <line x1="16" y1="14" x2="16" y2="14" />
      <line x1="8" y1="18" x2="8" y2="18" />
      <line x1="12" y1="18" x2="12" y2="18" />
      <line x1="16" y1="18" x2="16" y2="18" />
    </template>

    <!-- Checkered Racing Flag (Grand Prix Event) -->
    <template v-else-if="name === 'checkered-flag'">
      <path d="M4 22V4" stroke-width="2" />
      <path
        d="M4 4c3-1.2 6-1.2 8 0s5 1.2 8 0v11c-3 1.2-6 1.2-8 0s-5-1.2-8 0V4z"
      />
      <path d="M4 9.5c3-1.2 6-1.2 8 0s5 1.2 8 0" />
      <path d="M8 3.3v11" />
      <path d="M12 4v11" />
      <path d="M16 4.7v11" />
    </template>

    <!-- Driver Racing Helmet (WDC / Drivers) -->
    <template v-else-if="name === 'helmet'">
      <path d="M4 15v-2a8 8 0 0 1 15.5-2.8L21 14l-1.5 4H7a3 3 0 0 1-3-3z" />
      <path
        d="M13 10.5h6.5l1 2.8H13a1.4 1.4 0 0 1 0-2.8z"
        fill="currentColor"
        fill-opacity="0.2"
      />
      <path d="M7 18h10" />
    </template>

    <!-- Flag -->
    <template v-else-if="name === 'flag'">
      <path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z" />
      <line x1="4" y1="22" x2="4" y2="15" />
    </template>

    <!-- Diagonal Black & White Warning Flag -->
    <template v-else-if="name === 'bw-flag'">
      <rect
        x="4"
        y="4"
        width="17"
        height="12"
        rx="1.5"
        fill="#ffffff"
        stroke="none"
      />
      <polygon points="4,4 21,4 4,16" fill="#111116" stroke="none" />
      <rect
        x="4"
        y="4"
        width="17"
        height="12"
        rx="1.5"
        fill="none"
        stroke="currentColor"
        stroke-width="1.5"
      />
      <line
        x1="4"
        y1="3"
        x2="4"
        y2="21"
        stroke="currentColor"
        stroke-width="2"
      />
    </template>

    <!-- Stopwatch -->
    <template v-else-if="name === 'stopwatch'">
      <circle cx="12" cy="13" r="8" />
      <path d="M12 9v4l2 2" />
      <path d="M10 2h4" />
      <path d="M18.36 5.64l1.42-1.42" />
    </template>

    <!-- Alert -->
    <template v-else-if="name === 'alert'">
      <path
        d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"
      />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </template>

    <!-- Ban -->
    <template v-else-if="name === 'ban'">
      <circle cx="12" cy="12" r="10" />
      <line x1="4.93" y1="4.93" x2="19.07" y2="19.07" />
    </template>

    <!-- Sparkles -->
    <template v-else-if="name === 'sparkles'">
      <path
        d="M12 3l1.912 5.813a2 2 0 0 0 1.275 1.275L21 12l-5.813 1.912a2 2 0 0 0-1.275 1.275L12 21l-1.912-5.813a2 2 0 0 0-1.275-1.275L3 12l5.813-1.912a2 2 0 0 0 1.275-1.275L12 3z"
      />
      <path d="M5 3v4" />
      <path d="M3 5h4" />
      <path d="M19 17v4" />
      <path d="M17 19h4" />
    </template>

    <!-- Bolt -->
    <template v-else-if="name === 'bolt'">
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
    </template>

    <!-- Target -->
    <template v-else-if="name === 'target'">
      <circle cx="12" cy="12" r="10" />
      <circle cx="12" cy="12" r="6" />
      <circle cx="12" cy="12" r="2" />
    </template>

    <!-- Chart -->
    <template v-else-if="name === 'chart'">
      <line x1="18" y1="20" x2="18" y2="10" />
      <line x1="12" y1="20" x2="12" y2="4" />
      <line x1="6" y1="20" x2="6" y2="14" />
      <line x1="2" y1="20" x2="22" y2="20" />
    </template>

    <!-- Users -->
    <template v-else-if="name === 'users'">
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
      <path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </template>

    <!-- Wrench -->
    <template v-else-if="name === 'wrench'">
      <path
        d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"
      />
    </template>

    <!-- Close -->
    <template v-else-if="name === 'close'">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </template>
  </svg>
</template>

<script setup>
defineProps({
  name: {
    type: String,
    required: true,
  },
  size: {
    type: [Number, String],
    default: 18,
  },
});
</script>

<style scoped>
.f1-icon {
  display: inline-block;
  vertical-align: middle;
  flex-shrink: 0;
}
</style>
