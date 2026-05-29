const DATA_PATHS = {
  geometries: "data/comunas_rm.geojson",
  metrics: "data/valores_comunales_anuales.csv",
};

const METRIC_ID = "poblacion_total";
const DEFAULT_COMMUNE_NAME = "Santiago";

// Fixed breaks keep colors comparable as the slider moves through time.
const POPULATION_BREAKS = [
  { min: 0, max: 99999, color: "#edf8e9", label: "< 100,000" },
  { min: 100000, max: 199999, color: "#bae4b3", label: "100,000 - 199,999" },
  { min: 200000, max: 399999, color: "#74c476", label: "200,000 - 399,999" },
  { min: 400000, max: 699999, color: "#31a354", label: "400,000 - 699,999" },
  { min: 700000, max: Infinity, color: "#006d2c", label: "700,000+" },
];

const state = {
  years: [],
  selectedYear: null,
  selectedCommuneCode: null,
  geojsonLayer: null,
  chart: null,
  metricsByCommuneYear: new Map(),
  seriesByCommune: new Map(),
  featureByCommune: new Map(),
};

const elements = {
  yearSlider: document.querySelector("#year-slider"),
  yearLabel: document.querySelector("#year-label"),
  selectedYear: document.querySelector("#selected-year"),
  selectedPopulation: document.querySelector("#selected-population"),
  communeName: document.querySelector("#commune-name"),
  legend: document.querySelector("#legend"),
  chartCanvas: document.querySelector("#population-chart"),
};

const map = L.map("map", {
  zoomControl: false,
  scrollWheelZoom: true,
}).setView([-33.48, -70.66], 9);

L.control.zoom({ position: "topright" }).addTo(map);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 18,
  attribution: "&copy; OpenStreetMap contributors",
}).addTo(map);

init();

async function init() {
  try {
    const [geojson, metrics] = await Promise.all([
      loadGeojson(DATA_PATHS.geometries),
      loadMetrics(DATA_PATHS.metrics),
    ]);

    prepareMetricIndexes(metrics);
    buildYearSlider();
    buildLegend();
    drawMap(geojson);
    selectDefaultCommune(geojson);
  } catch (error) {
    console.error(error);
    elements.communeName.textContent = "Data load error";
    elements.selectedPopulation.textContent = "--";
  }
}

async function loadGeojson(path) {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`Could not load ${path}: ${response.status}`);
  }
  return response.json();
}

function loadMetrics(path) {
  return new Promise((resolve, reject) => {
    Papa.parse(path, {
      download: true,
      header: true,
      skipEmptyLines: true,
      complete: (result) => resolve(result.data),
      error: (error) => reject(error),
    });
  });
}

function prepareMetricIndexes(rows) {
  // Keep lookup maps small and direct for instant map redraws when the year changes.
  const filteredRows = rows
    .filter((row) => row.id_metrica === METRIC_ID)
    .map((row) => ({
      codigo_comuna: String(row.codigo_comuna),
      nombre_comuna: row.nombre_comuna,
      anio: Number(row.anio),
      valor: Number(row.valor),
    }))
    .filter((row) => Number.isFinite(row.anio) && Number.isFinite(row.valor));

  state.years = [...new Set(filteredRows.map((row) => row.anio))].sort(
    (a, b) => a - b,
  );
  state.selectedYear = state.years[state.years.length - 1];

  for (const row of filteredRows) {
    const key = metricKey(row.codigo_comuna, row.anio);
    state.metricsByCommuneYear.set(key, row.valor);

    if (!state.seriesByCommune.has(row.codigo_comuna)) {
      state.seriesByCommune.set(row.codigo_comuna, []);
    }
    state.seriesByCommune.get(row.codigo_comuna).push(row);
  }

  for (const series of state.seriesByCommune.values()) {
    series.sort((a, b) => a.anio - b.anio);
  }
}

function buildYearSlider() {
  const minYear = state.years[0];
  const maxYear = state.years[state.years.length - 1];

  elements.yearSlider.min = minYear;
  elements.yearSlider.max = maxYear;
  elements.yearSlider.value = state.selectedYear;
  updateYearLabels();

  elements.yearSlider.addEventListener("input", () => {
    state.selectedYear = Number(elements.yearSlider.value);
    updateYearLabels();
    refreshMapStyles();
    refreshOpenTooltips();
    updateSelectedPanel();
  });
}

function buildLegend() {
  elements.legend.innerHTML = `
    <div class="legend-title">Population</div>
    <div class="legend-items">
      ${POPULATION_BREAKS.map(
        (item) => `
          <div class="legend-row">
            <span class="legend-swatch" style="background:${item.color}"></span>
            <span>${item.label}</span>
          </div>
        `,
      ).join("")}
    </div>
  `;
}

function drawMap(geojson) {
  // The GeoJSON properties already use the pipeline-standard commune keys.
  state.geojsonLayer = L.geoJSON(geojson, {
    style: styleFeature,
    onEachFeature: (feature, layer) => {
      const code = String(feature.properties.codigo_comuna);
      state.featureByCommune.set(code, feature);

      layer.bindTooltip(tooltipHtml(feature), {
        sticky: true,
        className: "population-tooltip",
      });

      layer.on({
        click: () => selectCommune(code),
        mouseover: () => layer.setStyle({ weight: 2.5, color: "#111827" }),
        mouseout: () => state.geojsonLayer.resetStyle(layer),
      });
    },
  }).addTo(map);

  map.fitBounds(state.geojsonLayer.getBounds(), { padding: [24, 24] });
}

function selectDefaultCommune(geojson) {
  const defaultFeature = geojson.features.find(
    (feature) => feature.properties.nombre_comuna === DEFAULT_COMMUNE_NAME,
  );
  const firstFeature = geojson.features[0];
  const selectedFeature = defaultFeature || firstFeature;
  selectCommune(String(selectedFeature.properties.codigo_comuna));
}

function selectCommune(code) {
  state.selectedCommuneCode = code;
  refreshMapStyles();
  updateSelectedPanel();
}

function updateYearLabels() {
  elements.yearLabel.textContent = state.selectedYear;
  elements.selectedYear.textContent = state.selectedYear;
}

function updateSelectedPanel() {
  // The side panel and chart are both driven by the selected commune/year state.
  const feature = state.featureByCommune.get(state.selectedCommuneCode);
  if (!feature) {
    return;
  }

  const name = feature.properties.nombre_comuna;
  const value = valueFor(state.selectedCommuneCode, state.selectedYear);

  elements.communeName.textContent = name;
  elements.selectedPopulation.textContent = formatPopulation(value);
  updateChart(state.selectedCommuneCode, name);
}

function updateChart(code, name) {
  const series = state.seriesByCommune.get(code) || [];
  const labels = series.map((row) => row.anio);
  const values = series.map((row) => row.valor);

  if (state.chart) {
    state.chart.data.labels = labels;
    state.chart.data.datasets[0].label = name;
    state.chart.data.datasets[0].data = values;
    state.chart.update();
    return;
  }

  state.chart = new Chart(elements.chartCanvas, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: name,
          data: values,
          borderColor: "#0f766e",
          backgroundColor: "rgba(15, 118, 110, 0.14)",
          pointRadius: 0,
          pointHoverRadius: 4,
          borderWidth: 2,
          tension: 0.25,
          fill: true,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        intersect: false,
        mode: "index",
      },
      plugins: {
        legend: {
          display: false,
        },
        tooltip: {
          callbacks: {
            label: (context) => formatPopulation(context.parsed.y),
          },
        },
      },
      scales: {
        x: {
          ticks: {
            maxTicksLimit: 7,
          },
          grid: {
            display: false,
          },
        },
        y: {
          ticks: {
            callback: (value) => compactNumber(value),
          },
        },
      },
    },
  });
}

function refreshMapStyles() {
  if (!state.geojsonLayer) {
    return;
  }
  state.geojsonLayer.setStyle(styleFeature);
}

function refreshOpenTooltips() {
  if (!state.geojsonLayer) {
    return;
  }
  state.geojsonLayer.eachLayer((layer) => {
    layer.setTooltipContent(tooltipHtml(layer.feature));
  });
}

function styleFeature(feature) {
  // Leaflet calls this whenever styles are reset, so it always reflects the
  // current slider year and selected commune.
  const code = String(feature.properties.codigo_comuna);
  const value = valueFor(code, state.selectedYear);
  const selected = code === state.selectedCommuneCode;

  return {
    color: selected ? "#111827" : "#6b7280",
    weight: selected ? 2.5 : 0.8,
    fillColor: colorForPopulation(value),
    fillOpacity: selected ? 0.92 : 0.78,
    opacity: 1,
  };
}

function tooltipHtml(feature) {
  const code = String(feature.properties.codigo_comuna);
  const name = feature.properties.nombre_comuna;
  const value = valueFor(code, state.selectedYear);

  return `
    <span class="tooltip-name">${name}</span>
    <span class="tooltip-meta">${state.selectedYear} · ${formatPopulation(value)}</span>
  `;
}

function colorForPopulation(value) {
  if (!Number.isFinite(value)) {
    return "#cbd5d1";
  }
  return POPULATION_BREAKS.find(
    (item) => value >= item.min && value <= item.max,
  ).color;
}

function valueFor(code, year) {
  return state.metricsByCommuneYear.get(metricKey(code, year));
}

function metricKey(code, year) {
  return `${code}::${year}`;
}

function formatPopulation(value) {
  if (!Number.isFinite(value)) {
    return "No data";
  }
  return new Intl.NumberFormat("es-CL").format(value);
}

function compactNumber(value) {
  return new Intl.NumberFormat("en", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}
