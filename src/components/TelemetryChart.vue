<script setup>
import { onMounted, onBeforeUnmount, ref, watch, computed } from "vue";
// Chart.js is loaded from a CDN in index.html, so it's globally available.

const props = defineProps({
  telemetryData: Object,
  isLoading: Boolean,
  error: String,
  year: Number,
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

  const plugins = [
    {
      title: {
        display: true,
        text: label,
        font: { size: 16 },
        align: "start",
        padding: { top: 10, bottom: 10 },
      },
      tooltip: {
        enabled: true,
        mode: "index",
        intersect: false,
      },
      legend: {
        display: canvasId === "speed-chart",
        weight: 3000,
        onClick: (e, legendItem, legend) => {
          const index = legendItem.datasetIndex;
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
        ctx.fillStyle = "gray";
        ctx.strokeStyle = "gray";
        ctx.lineWidth = 1;
        ctx.setLineDash([2, 2]);

        turnData.forEach((turn) => {
          const x = xAxis.getPixelForValue(turn.distance);
          if (x >= xAxis.left && x <= xAxis.right) {
            ctx.beginPath();
            if (canvasId === "speed-chart") {
              ctx.moveTo(x, top);
              ctx.lineTo(x, chart.height);
            } else if (
              canvasId === "rpm-chart" ||
              (canvasId === "drs-chart" && hasDRS.value)
            ) {
              // The bottom-most chart stops at the X-axis
              ctx.moveTo(x, 0);
              ctx.lineTo(x, bottom);
            } else {
              ctx.moveTo(x, 0);
              ctx.lineTo(x, chart.height);
            }
            ctx.stroke();
            if (canvasId === "speed-chart") {
              ctx.fillText(`T${turn.number}`, x, top - 10);
            }
          }
        });
        ctx.restore();
      },
    });
  }

  const yTicks = {};
  if (canvasId === "rpm-chart") {
    yTicks.callback = function (value) {
      return value / 1000 + "k";
    };
  }

  return new Chart(ctx, {
    type: "line",
    data: {
      labels: datasets[0].data.map((d) => d.x),
      datasets: datasets,
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      layout: {
        padding: { top: 30, right: 20 },
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
          title: { display: true, text: "Distance (m)" },
          ticks: { maxTicksLimit: 10 },
          grid: { display: false },
        },
        y: {
          title: { display: true, text: yAxisLabel },
          min: yMin,
          suggestedMax: yMax,
          ticks: yTicks,
          grace: "10%",
          afterFit: (scale) => {
            scale.width = 60;
          },
          grid: { color: "rgba(200, 200, 200, 0.2)" },
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

  if (!data || !data.driver1 || !data.driver2) return;

  const d1 = data.driver1;
  const d2 = data.driver2;
  const turns = data.circuit_info?.turns || [];

  let c1 = d1.team_color ? `#${d1.team_color}` : "#ff0000";
  let c2 = d2.team_color ? `#${d2.team_color}` : "#0000ff";

  if (c1.toLowerCase() === c2.toLowerCase()) {
    c2 = adjustColor(c1, 40);
  }

  const createDataset = (driverData, label, color, key, isDrs = false) => ({
    label: `${driverData.abbreviation} (Lap ${driverData.lap_number})`,
    data: driverData.telemetry.map((t) => ({
      x: t.distance,
      y: isDrs ? (t.drs ? 1 : 0) : t[key],
    })),
    borderColor: color,
    backgroundColor: color,
    borderWidth: 1.5,
    fill: false,
    tension: 0,
    stepped: isDrs ? "before" : false,
  });

  // Speed
  chartInstances.push(
    createChart(
      "speed-chart",
      "Speed",
      [
        createDataset(d1, "Speed", c1, "speed"),
        createDataset(d2, "Speed", c2, "speed"),
      ],
      "km/h",
      null,
      null,
      turns,
    ),
  );
  // Throttle
  chartInstances.push(
    createChart(
      "throttle-chart",
      "Throttle",
      [
        createDataset(d1, "Throttle", c1, "throttle"),
        createDataset(d2, "Throttle", c2, "throttle"),
      ],
      "%",
      0,
      100,
      turns,
    ),
  );
  // Brake
  chartInstances.push(
    createChart(
      "brake-chart",
      "Brake",
      [
        createDataset(d1, "Brake", c1, "brake"),
        createDataset(d2, "Brake", c2, "brake"),
      ],
      "On/Off",
      0,
      1,
      turns,
    ),
  );
  // Gear
  chartInstances.push(
    createChart(
      "gear-chart",
      "Gear",
      [
        createDataset(d1, "Gear", c1, "n_gear"),
        createDataset(d2, "Gear", c2, "n_gear"),
      ],
      "Gear",
      null,
      null,
      turns,
    ),
  );
  // RPM
  chartInstances.push(
    createChart(
      "rpm-chart",
      "RPM",
      [
        createDataset(d1, "RPM", c1, "rpm"),
        createDataset(d2, "RPM", c2, "rpm"),
      ],
      "RPM",
      null,
      null,
      turns,
    ),
  );

  // DRS (Conditional)
  if (hasDRS.value) {
    chartInstances.push(
      createChart(
        "drs-chart",
        "DRS",
        [
          createDataset(d1, "DRS", c1, "drs", true),
          createDataset(d2, "DRS", c2, "drs", true),
        ],
        "On/Off",
        0,
        1,
        turns,
      ),
    );
  }
};

function adjustColor(color, amount) {
  return (
    "#" +
    color
      .replace(/^#/, "")
      .replace(/../g, (color) =>
        (
          "0" +
          Math.min(255, Math.max(0, parseInt(color, 16) + amount)).toString(16)
        ).substr(-2),
      )
  );
}

watch(
  () => props.telemetryData,
  (newData) => {
    if (newData) {
      setTimeout(() => renderCharts(newData), 0);
    } else {
      chartInstances.forEach((chart) => chart.destroy());
      chartInstances = [];
    }
  },
  { deep: true },
);

onBeforeUnmount(() => {
  chartInstances.forEach((chart) => chart.destroy());
  chartInstances = [];
});
</script>

<template>
  <div>
    <div v-if="year < 2018" class="no-telemetry-state">
      <h3>⚠️ TELEMETRY NOT AVAILABLE</h3>
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
      <p v-if="error" class="error-text">{{ error }}</p>

      <div
        v-if="telemetryData"
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
  border: none;
  justify-content: center;
  display: flex;
}
.no-telemetry-state p {
  color: var(--muted-text-color);
  margin: 0.5rem 0;
}
.loading-text,
.error-text {
  text-align: center;
  padding: 1rem;
  color: var(--muted-text-color);
}
.error-text {
  color: var(--primary-color);
  font-weight: bold;
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
</style>
