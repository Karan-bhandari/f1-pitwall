<script setup>
import { onMounted, ref, watch } from "vue";
// Chart.js is loaded from a CDN in index.html, so it's globally available.

const props = defineProps({
  telemetryData: Object,
  isLoading: Boolean,
  error: String,
});

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
        font: { size: 16 }, // Increased font size
        align: "start", // Align title to the left
        padding: { top: 10, bottom: 10 }, // Reduced bottom padding as we align start
      },
      tooltip: {
        enabled: true,
        mode: "index",
        intersect: false,
      },
      legend: {
        display: canvasId === "speed-chart", // Only show legend on top chart
        weight: 3000, // Push legend to the very top, above the title
      },
    },
  ];

  if (turnData && turnData.length > 0) {
    plugins.push({
      id: "turnMarkers",
      beforeDraw: (chart) => {
        const ctx = chart.ctx;
        const xAxis = chart.scales.x;
        const yAxis = chart.scales.y;
        const { top, bottom } = chart.chartArea;

        ctx.save();
        ctx.textAlign = "center";
        ctx.fillStyle = "gray";
        ctx.strokeStyle = "gray";
        ctx.lineWidth = 1;
        ctx.setLineDash([2, 2]); // Dotted line

        turnData.forEach((turn) => {
          const x = xAxis.getPixelForValue(turn.distance);

          // Only draw if within chart area
          if (x >= xAxis.left && x <= xAxis.right) {
            ctx.beginPath();

            // Continuous Line Logic
            if (canvasId === "speed-chart") {
              // Top chart: Start below legend/title, go to bottom edge
              ctx.moveTo(x, top);
              ctx.lineTo(x, chart.height);
            } else if (canvasId === "rpm-chart") {
              // Bottom chart: Start at top edge, stop at X-axis
              ctx.moveTo(x, 0);
              ctx.lineTo(x, bottom);
            } else {
              // Middle charts: Span entire height
              ctx.moveTo(x, 0);
              ctx.lineTo(x, chart.height);
            }

            ctx.stroke();

            // Draw Label only on the top chart
            if (canvasId === "speed-chart") {
              ctx.fillText(`T${turn.number}`, x, top - 10);
            }
          }
        });

        ctx.restore();
      },
    });
  }

  // Y-Axis Ticks configuration
  const yTicks = {};
  if (canvasId === "rpm-chart") {
    yTicks.callback = function (value) {
      return value / 1000 + "k";
    };
  }

  return new Chart(ctx, {
    type: "line",
    data: {
      labels: datasets[0].data.map((d) => d.x), // Use distance from first dataset
      datasets: datasets,
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      layout: {
        padding: {
          top: 30, // Increased padding for markers
          right: 20, // Ensure consistent right padding for alignment
        },
      },
      interaction: {
        mode: "index",
        intersect: false,
      },
      plugins: {
        // Merge the title/tooltip/legend config with our custom plugin
        title: plugins[0].title,
        tooltip: plugins[0].tooltip,
        legend: plugins[0].legend,
      },
      scales: {
        x: {
          type: "linear",
          min: 0, // Ensure the lap always starts at 0m on the chart
          display: canvasId === "rpm-chart", // Only show x-axis on bottom chart
          title: { display: true, text: "Distance (m)" },
          ticks: { maxTicksLimit: 10 },
          grid: {
            display: false, // Remove standard vertical grid lines
          },
        },
        y: {
          title: { display: true, text: yAxisLabel },
          min: yMin,
          suggestedMax: yMax, // Use suggestedMax to allow grace to work
          ticks: yTicks, // Apply custom ticks if defined
          grace: "10%", // Add breathing room at top/bottom
          afterFit: (scale) => {
            scale.width = 60; // Fixed width for alignment
          },
          grid: {
            color: "rgba(200, 200, 200, 0.2)", // A light, semi-transparent color for dark mode
          },
        },
      },
      elements: {
        point: { radius: 0 }, // Hide points for performance
      },
    },
    plugins: plugins, // Register the plugins array
  });
};

const renderCharts = (data) => {
  // Destroy existing charts
  chartInstances.forEach((chart) => chart.destroy());
  chartInstances = [];

  if (!data || !data.driver1 || !data.driver2) return;

  const d1 = data.driver1;
  const d2 = data.driver2;
  const turns = data.circuit_info?.turns || [];

  // Color Logic
  let c1 = d1.team_color ? `#${d1.team_color}` : "#ff0000";
  let c2 = d2.team_color ? `#${d2.team_color}` : "#0000ff";

  // Differentiate same team colors
  if (c1.toLowerCase() === c2.toLowerCase()) {
    // Make driver 2 lighter/different
    c2 = adjustColor(c1, 40);
  }

  const createDataset = (driverData, label, color, key) => ({
    label: `${driverData.abbreviation} (Lap ${driverData.lap_number})`,
    data: driverData.telemetry.map((t) => ({ x: t.distance, y: t[key] })),
    borderColor: color,
    backgroundColor: color, // Added to ensure filled rectangles in legend
    borderWidth: 1.5,
    fill: false,
    tension: 0,
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
};

// Helper to lighten/darken color
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
      // Use setTimeout to ensure DOM elements exist
      setTimeout(() => renderCharts(newData), 0);
    } else {
      chartInstances.forEach((chart) => chart.destroy());
      chartInstances = [];
    }
  },
  { deep: true },
);
</script>

<template>
  <div>
    <p v-if="isLoading" class="loading-text">Loading telemetry data...</p>
    <p v-if="error" class="error-text">{{ error }}</p>

    <div v-if="telemetryData" class="telemetry-container">
      <div class="chart-row"><canvas id="speed-chart"></canvas></div>
      <div class="chart-row"><canvas id="throttle-chart"></canvas></div>
      <div class="chart-row"><canvas id="brake-chart"></canvas></div>
      <div class="chart-row"><canvas id="gear-chart"></canvas></div>
      <div class="chart-row"><canvas id="rpm-chart"></canvas></div>
    </div>
  </div>
</template>

<style scoped>
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
  height: 1500px; /* Total height for all charts */
  /* gap: 10px; Removed to allow continuous lines */
}
.chart-row {
  flex: 1;
  position: relative;
  min-height: 0; /* Important for flexbox resizing */
}
</style>
