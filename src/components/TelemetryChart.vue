<script setup>
import { onMounted, onBeforeUnmount, ref, watch, computed } from "vue";
import Chart from "chart.js/auto";
import {
  adjustColor,
  convertSpeedKmh,
  getSpeedUnitLabel,
  unitSystem,
} from "../utils";
import F1Icon from "./F1Icon.vue";

const props = defineProps({
  telemetryData: Object,
  isLoading: Boolean,
  error: String,
  year: Number,
  theme: {
    type: String,
    default: "dark",
  },
});

// DRS was introduced in 2011 and is currently planned to be replaced by
// active aero in the 2026 regulations.
const hasDRS = computed(() => props.year >= 2011 && props.year <= 2025);

let chartInstances = [];

const createChart = (
  canvasId,
  label,
  datasets,
  yAxisLabel,
  yMin = null,
  yMax = null,
  turnData = null,
) => {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return null;

  const isSpeedChart = canvasId === "speed-chart";
  const isDark = props.theme === "dark";
  const tickColor = isDark ? "#9898a6" : "#555560";
  const titleColor = isDark ? "#e2e2e8" : "#1e1e24";
  const gridColor = isDark
    ? "rgba(255, 255, 255, 0.08)"
    : "rgba(0, 0, 0, 0.08)";
  const turnLineColor = isDark
    ? "rgba(195, 195, 215, 0.28)"
    : "rgba(60, 60, 75, 0.24)";
  const pillBg = isDark ? "#1e1e2a" : "#eaeaef";
  const pillBorder = isDark ? "#343448" : "#d0d0d7";

  const plugins = [
    {
      title: {
        display: true,
        text: label,
        color: titleColor,
        font: { size: 14, weight: "700" },
        align: "start",
        padding: { top: 8, bottom: 8 },
      },
      tooltip: {
        enabled: true,
        mode: "index",
        intersect: false,
        backgroundColor: "rgba(15, 15, 20, 0.92)",
        titleFont: { family: "'JetBrains Mono', monospace", size: 12 },
        bodyFont: { family: "'JetBrains Mono', monospace", size: 12 },
        padding: 10,
        cornerRadius: 8,
      },
      legend: {
        display: isSpeedChart,
        labels: {
          color: titleColor,
          usePointStyle: true,
          pointStyle: "circle",
          padding: 14,
          font: { weight: "600", size: 12 },
        },
        weight: 3000,
        onClick: (e, legendItem, legend) => {
          if (datasets.length <= 1) return;
          const index = legendItem.datasetIndex;
          const isCurrentlyVisible = legend.chart.isDatasetVisible(index);
          const visibleCount = datasets.filter((_, i) =>
            legend.chart.isDatasetVisible(i),
          ).length;
          if (isCurrentlyVisible && visibleCount <= 1) return;

          chartInstances.forEach((chart) => {
            if (chart) {
              const meta = chart.getDatasetMeta(index);
              meta.hidden =
                meta.hidden === null
                  ? !chart.data.datasets[index].hidden
                  : null;
              chart.update();
            }
          });
        },
      },
    },
  ];

  if (turnData && turnData.length > 0) {
    plugins.push({
      id: "turnMarkers",
      beforeDraw: (chart) => {
        const ctx = chart.ctx;
        const xAxis = chart.scales.x;
        const { top, bottom } = chart.chartArea;

        ctx.save();
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.font = "600 10px 'JetBrains Mono', monospace";
        ctx.fillStyle = tickColor;
        ctx.strokeStyle = turnLineColor;
        ctx.lineWidth = 1;
        ctx.setLineDash([4, 4]);

        const visibleTurns = turnData
          .map((turn) => ({
            number: turn.number,
            distance: turn.distance,
            x: xAxis.getPixelForValue(turn.distance),
          }))
          .filter((t) => t.x >= xAxis.left && t.x <= xAxis.right)
          .sort((a, b) => a.x - b.x);

        visibleTurns.forEach((turn) => {
          const px = Math.round(turn.x) + 0.5;
          ctx.beginPath();
          if (isSpeedChart) {
            ctx.moveTo(px, top);
            ctx.lineTo(px, chart.height);
          } else if (
            canvasId === "rpm-chart" ||
            (canvasId === "drs-chart" && hasDRS.value)
          ) {
            ctx.moveTo(px, 0);
            ctx.lineTo(px, bottom);
          } else {
            ctx.moveTo(px, 0);
            ctx.lineTo(px, chart.height);
          }
          ctx.stroke();
        });

        if (isSpeedChart && visibleTurns.length > 0) {
          ctx.setLineDash([]);
          const items = visibleTurns.map((turn) => {
            const text = `T${turn.number}`;
            const w = Math.ceil(ctx.measureText(text).width) + 8;
            return { ...turn, text, w, drawX: turn.x };
          });
          const gap = 3;
          for (let pass = 0; pass < 8; pass++) {
            for (let i = 1; i < items.length; i++) {
              const prev = items[i - 1];
              const curr = items[i];
              const minDist = (prev.w + curr.w) / 2 + gap;
              const overlap = minDist - (curr.drawX - prev.drawX);
              if (overlap > 0) {
                prev.drawX -= overlap / 2;
                curr.drawX += overlap / 2;
              }
            }
            for (const item of items) {
              item.drawX = Math.max(
                xAxis.left + item.w / 2,
                Math.min(xAxis.right - item.w / 2, item.drawX),
              );
            }
          }

          const pillH = 15;
          const y = top - 14;
          items.forEach((item) => {
            ctx.beginPath();
            ctx.strokeStyle = tickColor;
            ctx.globalAlpha = 0.65;
            ctx.moveTo(Math.round(item.x) + 0.5, top);
            ctx.lineTo(item.drawX, y + pillH / 2);
            ctx.stroke();
            ctx.globalAlpha = 1;

            const rx = item.drawX - item.w / 2;
            const ry = y - pillH / 2;
            ctx.fillStyle = pillBg;
            ctx.strokeStyle = pillBorder;
            ctx.beginPath();
            ctx.roundRect(rx, ry, item.w, pillH, 4);
            ctx.fill();
            ctx.stroke();

            ctx.fillStyle = titleColor;
            ctx.fillText(item.text, item.drawX, y + 0.5);
          });
        }
        ctx.restore();
      },
    });
  }

  const yTicks = {
    color: tickColor,
    font: { family: "'JetBrains Mono', monospace", size: 11 },
  };
  if (canvasId === "rpm-chart") {
    yTicks.callback = function (value) {
      return value / 1000 + "k";
    };
  }

  return new Chart(ctx, {
    type: "line",
    data: {
      labels: datasets[0]?.data.map((d) => d.x) || [],
      datasets: datasets,
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      layout: {
        padding: { top: isSpeedChart ? 38 : 30, right: 20 },
      },
      interaction: {
        mode: "index",
        intersect: false,
      },
      plugins: {
        title: plugins[0].title,
        tooltip: plugins[0].tooltip,
        legend: plugins[0].legend,
      },
      scales: {
        x: {
          type: "linear",
          min: 0,
          display:
            (canvasId === "rpm-chart" && !hasDRS.value) ||
            canvasId === "drs-chart",
          title: { display: true, text: "Distance (m)", color: titleColor },
          ticks: { maxTicksLimit: 10, color: tickColor },
          grid: { display: false },
        },
        y: {
          title: { display: true, text: yAxisLabel, color: titleColor },
          min: yMin,
          suggestedMax: yMax,
          ticks: yTicks,
          grace: "10%",
          afterFit: (scale) => {
            scale.width = 60;
          },
          grid: { color: gridColor },
        },
      },
      elements: { point: { radius: 0 } },
    },
    plugins: plugins,
  });
};

const renderCharts = (data) => {
  chartInstances.forEach((chart) => chart.destroy());
  chartInstances = [];

  if (!data || !data.driver1) return;

  const d1 = data.driver1;
  const d2 = data.driver2 || null;
  const turns = data.circuit_info?.turns || [];

  let c1 = d1.team_color ? `#${d1.team_color.replace("#", "")}` : "#ff0000";
  let c2 = d2
    ? d2.team_color
      ? `#${d2.team_color.replace("#", "")}`
      : "#0000ff"
    : null;

  if (d2 && c1.toLowerCase() === c2.toLowerCase()) {
    c2 = adjustColor(c1, 40);
  }

  const buildDatasets = (key, isDrs = false) =>
    [d1, d2].filter(Boolean).map((d, idx) => ({
      label: `${d.abbreviation} (Lap ${d.lap_number})`,
      data: d.telemetry.map((t) => ({
        x: t.distance,
        y: isDrs
          ? t.drs
            ? 1
            : 0
          : key === "speed"
            ? convertSpeedKmh(t[key], unitSystem.value)
            : t[key],
      })),
      borderColor: idx === 0 ? c1 : c2,
      backgroundColor: idx === 0 ? c1 : c2,
      borderWidth: 1.5,
      fill: false,
      tension: 0,
      stepped: isDrs ? "before" : false,
    }));

  const channels = [
    [
      "speed-chart",
      "Speed",
      "speed",
      getSpeedUnitLabel(unitSystem.value),
      null,
      null,
      false,
    ],
    ["throttle-chart", "Throttle", "throttle", "%", 0, 100, false],
    ["brake-chart", "Brake", "brake", "On/Off", 0, 1, false],
    ["gear-chart", "Gear", "n_gear", "Gear", null, null, false],
    ["rpm-chart", "RPM", "rpm", "RPM", null, null, false],
    ...(hasDRS.value
      ? [["drs-chart", "DRS", "drs", "On/Off", 0, 1, true]]
      : []),
  ];

  chartInstances = channels
    .map(([id, title, key, unit, min, max, isDrs]) =>
      createChart(id, title, buildDatasets(key, isDrs), unit, min, max, turns),
    )
    .filter(Boolean);
};

const destroyCharts = () => {
  chartInstances.forEach((chart) => chart.destroy());
  chartInstances = [];
};

const scheduleRender = (data = props.telemetryData) => {
  if (data) {
    setTimeout(() => renderCharts(data), 0);
  } else {
    destroyCharts();
  }
};

watch(() => props.telemetryData, scheduleRender, { deep: true });
watch([() => props.theme, unitSystem], () => {
  if (props.telemetryData) scheduleRender();
});
onMounted(() => {
  if (props.telemetryData) scheduleRender();
});
onBeforeUnmount(destroyCharts);
</script>

<template>
  <div>
    <div v-if="year < 2018" class="no-telemetry-state">
      <h3>
        <F1Icon name="alert" :size="20" />
        <span>TELEMETRY NOT AVAILABLE</span>
      </h3>
      <p>
        High-resolution telemetry data is only available for seasons from 2018
        onwards.
      </p>
      <p>
        Please select a modern season to view speed, throttle, and braking
        traces.
      </p>
    </div>

    <template v-else>
      <p v-if="isLoading" class="loading-text">Loading telemetry data...</p>
      <p v-if="error" class="error-text" role="alert">{{ error }}</p>

      <div v-if="telemetryData" class="telemetry-card">
        <div
          class="telemetry-container"
          :style="{ height: hasDRS ? '1800px' : '1500px' }"
        >
          <div class="chart-row"><canvas id="speed-chart"></canvas></div>
          <div class="chart-row"><canvas id="throttle-chart"></canvas></div>
          <div class="chart-row"><canvas id="brake-chart"></canvas></div>
          <div class="chart-row"><canvas id="gear-chart"></canvas></div>
          <div class="chart-row"><canvas id="rpm-chart"></canvas></div>
          <div v-if="hasDRS" class="chart-row">
            <canvas id="drs-chart"></canvas>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.no-telemetry-state {
  text-align: center;
  padding: 4rem 2rem;
  background: var(--item-bg-color);
  border-radius: 12px;
  border: 1px dashed var(--border-color);
  margin-top: 1rem;
}
.no-telemetry-state h3 {
  margin-top: 0;
  margin-bottom: 0.75rem;
  border: none;
  color: var(--text-color);
  justify-content: center;
  align-items: center;
  gap: 0.5rem;
  display: flex;
}
.no-telemetry-state p {
  color: var(--muted-text-color);
  margin: 0.5rem auto;
  max-width: 520px;
  line-height: 1.55;
}
.loading-text,
.error-text {
  text-align: center;
  padding: 2rem 1.5rem;
  color: var(--muted-text-color);
  background: var(--card-bg-color);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  margin-top: 1rem;
}
.error-text {
  color: var(--primary-color);
  background: var(--accent-color);
  border-color: rgba(225, 6, 0, 0.25);
  font-weight: 600;
}
.telemetry-card {
  background: var(--card-bg-color);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 1.25rem 1.5rem;
}
.telemetry-container {
  display: flex;
  flex-direction: column;
  transition: height 0.3s ease;
}
.chart-row {
  flex: 1;
  position: relative;
  min-height: 0;
}

@media (max-width: 768px) {
  .telemetry-card {
    padding: 0.85rem 0.75rem;
  }
}
</style>
