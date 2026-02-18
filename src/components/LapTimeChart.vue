<script setup>
import { onMounted, ref, watch } from "vue";
import softTyre from "@/assets/tyres/soft.svg";
import mediumTyre from "@/assets/tyres/medium.svg";
import hardTyre from "@/assets/tyres/hard.svg";
import intermediateTyre from "@/assets/tyres/intermediate.svg";
import wetTyre from "@/assets/tyres/wet.svg";

// Chart.js is loaded from a CDN in index.html

const props = defineProps({
  raceComparison: Object,
  isLoading: Boolean,
  error: String,
});

const tyreIcons = {
  SOFT: softTyre,
  MEDIUM: mediumTyre,
  HARD: hardTyre,
  INTERMEDIATE: intermediateTyre,
  WET: wetTyre,
};

let chartInstance = null;

const formatLapTime = (seconds) => {
  if (seconds === null || isNaN(seconds)) return "N/A";
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = (seconds % 60).toFixed(3);
  return `${minutes}:${String(remainingSeconds).padStart(6, "0")}`;
};

const renderChart = (data) => {
  const ctx = document.getElementById("lap-time-chart-canvas");
  if (!ctx) return;
  if (chartInstance) {
    chartInstance.destroy();
  }

  const formatTeamColor = (color) => {
    if (!color || typeof color !== "string") return null;
    return `#${color.replace("#", "")}`;
  };

  const driver1Color = formatTeamColor(data.driver1.team_color) || "#ff0000";
  let driver2Color = formatTeamColor(data.driver2.team_color) || "#0000ff";

  // Simple same-team check
  if (driver1Color.toLowerCase() === driver2Color.toLowerCase()) {
    // Lighten the second driver's color
    driver2Color = adjustColor(driver1Color, 40);
  }

  const driver1Laps = data.driver1.laps;
  const driver2Laps = data.driver2.laps;

  const allLaps = [...driver1Laps, ...driver2Laps].filter(
    (l) => l.lap_time_seconds,
  );
  const maxLaps =
    allLaps.length > 0 ? Math.max(...allLaps.map((l) => l.lap_number)) : 0;
  const labels = Array.from({ length: maxLaps }, (_, i) => `Lap ${i + 1}`);

  const generateLapData = (laps, max) => {
    const lapData = new Array(max).fill(null);
    for (const lap of laps) {
      if (lap.lap_number > 0 && lap.lap_number <= max) {
        lapData[lap.lap_number - 1] = lap.lap_time_seconds;
      }
    }
    return lapData;
  };

  const driver1PitStops = driver1Laps
    .filter((l) => l.pit_in_time)
    .map((l) => l.lap_number);
  const driver2PitStops = driver2Laps
    .filter((l) => l.pit_in_time)
    .map((l) => l.lap_number);

  // Calculate Y-Axis Limits based on min lap time
  let yMin = undefined;
  let yMax = undefined;
  if (allLaps.length > 0) {
    const times = allLaps.map((l) => l.lap_time_seconds).sort((a, b) => a - b);
    const minLapTime = times[0];

    yMin = Math.max(0, minLapTime - 3); // 3 seconds below min lap time, but not below 0
    yMax = minLapTime + 10; // 10 seconds above min lap time
  }

  const pitStopLinePlugin = {
    id: "pitStopLines",
    afterDraw: (chart) => {
      const ctx = chart.ctx;
      const xAxis = chart.scales.x;
      const yAxis = chart.scales.y;

      const drawLines = (lapNumbers, color) => {
        ctx.save();
        ctx.beginPath();
        ctx.lineWidth = 2;
        ctx.strokeStyle = color;
        ctx.setLineDash([5, 5]);

        lapNumbers.forEach((lapNum) => {
          const index = lapNum - 1; // 0-based index for Chart.js
          const x = xAxis.getPixelForValue(index);

          if (x >= xAxis.left && x <= xAxis.right) {
            // Draw line even if it goes out of chart area vertically?
            // Yes, clip will handle it, or we draw from top to bottom of area
            ctx.moveTo(x, yAxis.top);
            ctx.lineTo(x, yAxis.bottom);
          }
        });
        ctx.stroke();
        ctx.restore();
      };

      drawLines(driver1PitStops, driver1Color);
      drawLines(driver2PitStops, driver2Color);
    },
  };

  // External Tooltip Handler
  const getOrCreateTooltip = (chart) => {
    let tooltipEl = chart.canvas.parentNode.querySelector(
      "div.chartjs-tooltip",
    );
    if (!tooltipEl) {
      tooltipEl = document.createElement("div");
      tooltipEl.classList.add("chartjs-tooltip");
      tooltipEl.style.opacity = 1;
      tooltipEl.style.pointerEvents = "none";
      tooltipEl.style.position = "absolute";
      tooltipEl.style.transform = "translate(-50%, 0)";
      tooltipEl.style.transition = "all .1s ease";
      tooltipEl.style.background = "rgba(0, 0, 0, 0.8)";
      tooltipEl.style.borderRadius = "3px";
      tooltipEl.style.color = "white";
      tooltipEl.style.padding = "6px";
      tooltipEl.style.zIndex = "100";

      const table = document.createElement("table");
      table.style.margin = "0px";
      tooltipEl.appendChild(table);
      chart.canvas.parentNode.appendChild(tooltipEl);
    }
    return tooltipEl;
  };

  const externalTooltipHandler = (context) => {
    // Tooltip Element
    const { chart, tooltip } = context;
    const tooltipEl = getOrCreateTooltip(chart);

    // Hide if no tooltip
    if (tooltip.opacity === 0) {
      tooltipEl.style.opacity = 0;
      return;
    }

    // Set Text
    if (tooltip.body) {
      const titleLines = tooltip.title || [];

      const tableHead = document.createElement("thead");

      titleLines.forEach((title) => {
        const tr = document.createElement("tr");
        tr.style.borderWidth = 0;
        const th = document.createElement("th");
        th.style.borderWidth = 0;
        const text = document.createTextNode(title);
        th.appendChild(text);
        tr.appendChild(th);
        tableHead.appendChild(tr);
      });

      const tableBody = document.createElement("tbody");
      tooltip.dataPoints.forEach((dataPoint, i) => {
        const colors = tooltip.labelColors[i];

        const driverKey = dataPoint.datasetIndex === 0 ? "driver1" : "driver2";
        const driverData = props.raceComparison[driverKey];
        const lapData = driverData.laps.find(
          (l) => l.lap_number === dataPoint.dataIndex + 1,
        );

        const lapTime = dataPoint.raw; // Raw seconds
        const formattedTime = formatLapTime(lapTime);

        let displayLabel = `${driverData.abbreviation}: ${formattedTime}`;
        if (lapData && lapData.pit_in_time) {
          displayLabel += " (Pit In)";
        }

        const tr = document.createElement("tr");
        tr.style.backgroundColor = "inherit";
        tr.style.borderWidth = 0;

        const td = document.createElement("td");
        td.style.borderWidth = 0;
        td.style.display = "flex";
        td.style.alignItems = "center";
        td.style.gap = "5px";

        const spanColor = document.createElement("span");
        spanColor.style.background = colors.backgroundColor;
        spanColor.style.borderColor = colors.borderColor;
        spanColor.style.borderWidth = "2px";
        spanColor.style.marginRight = "6px";
        spanColor.style.height = "10px";
        spanColor.style.width = "10px";
        spanColor.style.display = "inline-block";

        const textNode = document.createTextNode(displayLabel);

        td.appendChild(spanColor);
        td.appendChild(textNode);

        if (lapData && lapData.compound) {
          const compound = lapData.compound.toUpperCase();
          const iconSrc = tyreIcons[compound];
          if (iconSrc) {
            const img = document.createElement("img");
            img.src = iconSrc;
            img.style.height = "15px";
            img.style.width = "15px";
            img.style.marginLeft = "5px";
            td.appendChild(img);
          }
        }

        tr.appendChild(td);
        tableBody.appendChild(tr);
      });

      const tableRoot = tooltipEl.querySelector("table");
      while (tableRoot.firstChild) {
        tableRoot.firstChild.remove();
      }
      tableRoot.appendChild(tableHead);
      tableRoot.appendChild(tableBody);
    }

    const { offsetLeft: positionX, offsetTop: positionY } = chart.canvas;

    // Display, position, and set styles for font
    tooltipEl.style.opacity = 1;
    tooltipEl.style.left = positionX + tooltip.caretX + "px";
    tooltipEl.style.top = positionY + tooltip.caretY + "px";
    tooltipEl.style.font = tooltip.options.bodyFont.string;
    tooltipEl.style.padding =
      tooltip.options.padding + "px " + tooltip.options.padding + "px";
  };

  chartInstance = new Chart(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: [
        {
          label: data.driver1.full_name,
          data: generateLapData(driver1Laps, maxLaps),
          borderColor: driver1Color,
          backgroundColor: driver1Color,
          tension: 0.2,
          fill: false,
          pointRadius: 4,
          pointHoverRadius: 7,
        },
        {
          label: data.driver2.full_name,
          data: generateLapData(driver2Laps, maxLaps),
          borderColor: driver2Color,
          backgroundColor: driver2Color,
          tension: 0.2,
          fill: false,
          pointRadius: 4,
          pointHoverRadius: 7,
        },
      ],
    },
    plugins: [pitStopLinePlugin],
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        intersect: false,
        mode: "index",
      },
      scales: {
        x: {
          title: { display: true, text: "Lap Number" },
        },
        y: {
          title: { display: true, text: "Lap Time" },
          min: yMin, // Set Y-axis min
          max: yMax, // Set Y-axis max (clipping pit stops)
          ticks: {
            maxTicksLimit: 15, // Increase number of ticks for the taller 600px height
            callback: (value) => formatLapTime(value),
          },
        },
      },
      plugins: {
        tooltip: {
          enabled: false,
          external: externalTooltipHandler,
        },
      },
    },
  });
};

// Helper to lighten/darken color (reused from TelemetryChart)
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
  () => props.raceComparison,
  (newData) => {
    if (newData) {
      setTimeout(() => renderChart(newData), 0);
    } else if (chartInstance) {
      chartInstance.destroy();
      chartInstance = null;
    }
  },
  { deep: true },
);
</script>

<template>
  <div>
    <p v-if="isLoading" class="loading-text">Loading comparison data...</p>
    <p v-if="error" class="error-text">{{ error }}</p>
    <div v-if="raceComparison" class="chart-container">
      <canvas id="lap-time-chart-canvas"></canvas>
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
.chart-container {
  margin-top: 2rem;
  height: 600px;
  position: relative;
}
</style>
