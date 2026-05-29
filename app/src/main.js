const DATA_PATHS = {
  geometries: "data/comunas_rm.geojson",
  metrics: "data/valores_comunales_anuales.csv",
};

const DEFAULT_METRIC_ID = "poblacion_total";
const DEFAULT_COMMUNE_NAME = "Santiago";
const PLAY_INTERVAL_MS = 850;

const METRIC_CONFIG = {
  poblacion_total: {
    label: "Población total",
    unit: "personas",
    stroke: "#0f766e",
    fill: "rgba(15, 118, 110, 0.14)",
    breaks: [
      { min: 0, max: 99999, color: "#edf8e9", label: "Menos de 100.000" },
      { min: 100000, max: 199999, color: "#bae4b3", label: "100.000 a 199.999" },
      { min: 200000, max: 399999, color: "#74c476", label: "200.000 a 399.999" },
      { min: 400000, max: 699999, color: "#31a354", label: "400.000 a 699.999" },
      { min: 700000, max: Infinity, color: "#006d2c", label: "700.000 o más" },
    ],
  },
  homicidios: {
    label: "Homicidios",
    unit: "casos policiales",
    stroke: "#b91c1c",
    fill: "rgba(185, 28, 28, 0.12)",
    breaks: [
      { min: 0, max: 0, color: "#fff7ec", label: "0" },
      { min: 1, max: 4, color: "#fee8c8", label: "1 a 4" },
      { min: 5, max: 9, color: "#fdbb84", label: "5 a 9" },
      { min: 10, max: 19, color: "#e34a33", label: "10 a 19" },
      { min: 20, max: Infinity, color: "#b30000", label: "20 o más" },
    ],
  },
  tasa_homicidios_100k_hab: {
    label: "Tasa de homicidios",
    unit: "casos por 100.000 habitantes",
    stroke: "#a16207",
    fill: "rgba(161, 98, 7, 0.13)",
    decimals: 2,
    breaks: [
      { min: 0, max: 0, color: "#ffffe5", label: "0" },
      { min: 0.000001, max: 2.49, color: "#fff7bc", label: "0,01 a 2,49" },
      { min: 2.5, max: 4.99, color: "#fec44f", label: "2,50 a 4,99" },
      { min: 5, max: 9.99, color: "#d95f0e", label: "5,00 a 9,99" },
      { min: 10, max: Infinity, color: "#993404", label: "10,00 o más" },
    ],
  },
};

const SOURCE_NOTES = {
  population_communal_annual:
    "INE, Estimaciones y proyecciones de población comunal 2002-2035, base Censo 2017.",
  insecurity_cead_delincuencia_chile:
    "CEAD / Subsecretaría de Prevención del Delito, vía repositorio público trazable delincuencia_chile.",
  derived_homicidios_rate_100k:
    "Cálculo propio: homicidios CEAD divididos por población total INE y multiplicados por 100.000.",
};

const DEFAULT_COLORS = ["#eff6ff", "#bfdbfe", "#60a5fa", "#2563eb", "#1e3a8a"];

const state = {
  selectedMetricId: null,
  years: [],
  selectedYear: null,
  selectedCommuneCode: null,
  geojsonLayer: null,
  chart: null,
  playTimer: null,
  metricsByCommuneYear: new Map(),
  seriesByMetricCommune: new Map(),
  yearsByMetric: new Map(),
  valuesByMetric: new Map(),
  metricMetadata: new Map(),
  dynamicBreaksByMetric: new Map(),
  featureByCommune: new Map(),
};

const elements = {
  metricSelect: document.querySelector("#metric-select"),
  yearSlider: document.querySelector("#year-slider"),
  yearLabel: document.querySelector("#year-label"),
  playToggle: document.querySelector("#play-toggle"),
  selectedYear: document.querySelector("#selected-year"),
  selectedMetricLabel: document.querySelector("#selected-metric-label"),
  selectedValue: document.querySelector("#selected-value"),
  communeName: document.querySelector("#commune-name"),
  legend: document.querySelector("#legend"),
  chartTitle: document.querySelector("#chart-title"),
  chartSubtitle: document.querySelector("#chart-subtitle"),
  sourceNote: document.querySelector("#source-note"),
  chartCanvas: document.querySelector("#metric-chart"),
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
    buildMetricSelector();
    wireControls();
    setSelectedMetric(state.selectedMetricId);
    drawMap(geojson);
    selectDefaultCommune(geojson);
  } catch (error) {
    console.error(error);
    elements.communeName.textContent = "Error de carga";
    elements.selectedValue.textContent = "--";
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
  const yearSets = new Map();

  for (const row of rows) {
    const metricId = String(row.id_metrica || "").trim();
    const code = String(row.codigo_comuna || "").trim();
    const year = Number(row.anio);
    const value = Number(row.valor);

    if (!metricId || !code || !Number.isFinite(year) || !Number.isFinite(value)) {
      continue;
    }

    const metadata = metadataForRow(metricId, row);
    metadata.sources.add(String(row.fuente || "").trim());

    state.metricsByCommuneYear.set(metricKey(metricId, code, year), value);

    const seriesKeyValue = seriesKey(metricId, code);
    if (!state.seriesByMetricCommune.has(seriesKeyValue)) {
      state.seriesByMetricCommune.set(seriesKeyValue, []);
    }
    state.seriesByMetricCommune.get(seriesKeyValue).push({
      codigo_comuna: code,
      nombre_comuna: row.nombre_comuna,
      anio: year,
      valor: value,
    });

    if (!yearSets.has(metricId)) {
      yearSets.set(metricId, new Set());
    }
    yearSets.get(metricId).add(year);

    if (!state.valuesByMetric.has(metricId)) {
      state.valuesByMetric.set(metricId, []);
    }
    state.valuesByMetric.get(metricId).push(value);
  }

  for (const [metricId, years] of yearSets.entries()) {
    state.yearsByMetric.set(metricId, [...years].sort((a, b) => a - b));
  }

  for (const series of state.seriesByMetricCommune.values()) {
    series.sort((a, b) => a.anio - b.anio);
  }

  for (const metadata of state.metricMetadata.values()) {
    metadata.sources = [...metadata.sources].filter(Boolean);
  }
}

function metadataForRow(metricId, row) {
  if (state.metricMetadata.has(metricId)) {
    return state.metricMetadata.get(metricId);
  }

  const config = METRIC_CONFIG[metricId] || {};
  const metadata = {
    id: metricId,
    label: row.nombre_metrica || config.label || metricId,
    unit: row.unidad || config.unit || "",
    decimals: config.decimals,
    sources: new Set(),
  };
  state.metricMetadata.set(metricId, metadata);
  return metadata;
}

function buildMetricSelector() {
  const metricIds = [...state.metricMetadata.keys()].sort((a, b) => {
    if (a === DEFAULT_METRIC_ID) return -1;
    if (b === DEFAULT_METRIC_ID) return 1;
    return labelForMetric(a).localeCompare(labelForMetric(b), "es");
  });

  elements.metricSelect.innerHTML = metricIds
    .map(
      (metricId) => `
        <option value="${metricId}">${labelForMetric(metricId)}</option>
      `,
    )
    .join("");

  state.selectedMetricId = metricIds.includes(DEFAULT_METRIC_ID)
    ? DEFAULT_METRIC_ID
    : metricIds[0];
  elements.metricSelect.value = state.selectedMetricId;
}

function wireControls() {
  elements.metricSelect.addEventListener("change", () => {
    stopPlayback();
    setSelectedMetric(elements.metricSelect.value);
  });

  elements.yearSlider.addEventListener("input", () => {
    setSelectedYear(Number(elements.yearSlider.value));
  });

  elements.playToggle.addEventListener("click", () => {
    if (state.playTimer) {
      stopPlayback();
      return;
    }
    startPlayback();
  });
}

function setSelectedMetric(metricId) {
  state.selectedMetricId = metricId;
  elements.metricSelect.value = metricId;
  state.years = state.yearsByMetric.get(metricId) || [];
  state.selectedYear = state.years[state.years.length - 1] || null;
  configureYearSlider();
  buildLegend();
  refreshMapStyles();
  refreshOpenTooltips();
  updateSelectedPanel();
}

function configureYearSlider() {
  const minYear = state.years[0] || "";
  const maxYear = state.years[state.years.length - 1] || "";

  elements.yearSlider.min = minYear;
  elements.yearSlider.max = maxYear;
  elements.yearSlider.value = state.selectedYear || minYear;
  elements.yearSlider.disabled = state.years.length <= 1;
  updateYearLabels();
}

function startPlayback() {
  if (state.playTimer || state.years.length <= 1) {
    return;
  }

  const lastYear = state.years[state.years.length - 1];
  if (state.selectedYear === lastYear) {
    setSelectedYear(state.years[0]);
  }

  elements.playToggle.textContent = "Pause";
  elements.playToggle.setAttribute("aria-label", "Pausar animación de años");
  state.playTimer = window.setInterval(advanceYear, PLAY_INTERVAL_MS);
}

function stopPlayback() {
  if (!state.playTimer) {
    return;
  }
  window.clearInterval(state.playTimer);
  state.playTimer = null;
  elements.playToggle.textContent = "Play";
  elements.playToggle.setAttribute("aria-label", "Reproducir años");
}

function advanceYear() {
  const currentIndex = state.years.indexOf(state.selectedYear);
  const nextYear = state.years[currentIndex + 1];
  if (!nextYear) {
    stopPlayback();
    return;
  }
  setSelectedYear(nextYear);
}

function setSelectedYear(year) {
  state.selectedYear = year;
  elements.yearSlider.value = year;
  updateYearLabels();
  refreshMapStyles();
  refreshOpenTooltips();
  updateSelectedPanel();
}

function buildLegend() {
  const metadata = currentMetadata();
  const breaks = breaksForMetric(state.selectedMetricId);

  elements.legend.innerHTML = `
    <div class="legend-title">${metadata.label}</div>
    <div class="legend-items">
      ${breaks
        .map(
          (item) => `
            <div class="legend-row">
              <span class="legend-swatch" style="background:${item.color}"></span>
              <span>${item.label}</span>
            </div>
          `,
        )
        .join("")}
    </div>
  `;
}

function drawMap(geojson) {
  state.geojsonLayer = L.geoJSON(geojson, {
    style: styleFeature,
    onEachFeature: (feature, layer) => {
      const code = String(feature.properties.codigo_comuna);
      state.featureByCommune.set(code, feature);

      layer.bindTooltip(tooltipHtml(feature), {
        sticky: true,
        className: "metric-tooltip",
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
  elements.yearLabel.textContent = state.selectedYear || "----";
  elements.selectedYear.textContent = state.selectedYear || "----";
}

function updateSelectedPanel() {
  const feature = state.featureByCommune.get(state.selectedCommuneCode);
  if (!feature || !state.selectedMetricId) {
    return;
  }

  const metadata = currentMetadata();
  const name = feature.properties.nombre_comuna;
  const value = valueFor(state.selectedCommuneCode, state.selectedYear);

  elements.communeName.textContent = name;
  elements.selectedMetricLabel.textContent = metadata.label;
  elements.selectedValue.textContent = formatMetricValue(value, metadata);
  elements.chartTitle.textContent = metadata.label;
  elements.chartSubtitle.textContent = `${name}, ${metadata.unit}`;
  elements.sourceNote.textContent = sourceNote(metadata);
  updateChart(state.selectedCommuneCode, name, metadata);
}

function updateChart(code, name, metadata) {
  const series = state.seriesByMetricCommune.get(
    seriesKey(state.selectedMetricId, code),
  ) || [];
  const labels = series.map((row) => row.anio);
  const values = series.map((row) => row.valor);
  const config = METRIC_CONFIG[state.selectedMetricId] || {};

  if (state.chart) {
    state.chart.data.labels = labels;
    state.chart.data.datasets[0].label = name;
    state.chart.data.datasets[0].data = values;
    state.chart.data.datasets[0].borderColor = config.stroke || "#2563eb";
    state.chart.data.datasets[0].backgroundColor = config.fill || "rgba(37, 99, 235, 0.12)";
    state.chart.options.plugins.tooltip.callbacks.label = (context) =>
      formatMetricValue(context.parsed.y, metadata);
    state.chart.options.scales.y.ticks.callback = (value) =>
      formatAxisValue(value, metadata);
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
          borderColor: config.stroke || "#2563eb",
          backgroundColor: config.fill || "rgba(37, 99, 235, 0.12)",
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
            label: (context) => formatMetricValue(context.parsed.y, metadata),
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
            callback: (value) => formatAxisValue(value, metadata),
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
  const code = String(feature.properties.codigo_comuna);
  const value = valueFor(code, state.selectedYear);
  const selected = code === state.selectedCommuneCode;

  return {
    color: selected ? "#111827" : "#6b7280",
    weight: selected ? 2.5 : 0.8,
    fillColor: colorForMetric(value),
    fillOpacity: selected ? 0.92 : 0.78,
    opacity: 1,
  };
}

function tooltipHtml(feature) {
  const code = String(feature.properties.codigo_comuna);
  const name = feature.properties.nombre_comuna;
  const value = valueFor(code, state.selectedYear);
  const metadata = currentMetadata();

  return `
    <span class="tooltip-name">${name}</span>
    <span class="tooltip-meta">${state.selectedYear || ""} - ${metadata.label}</span>
    <span class="tooltip-meta">${formatMetricValue(value, metadata)}</span>
  `;
}

function colorForMetric(value) {
  if (!Number.isFinite(value)) {
    return "#cbd5d1";
  }
  const breaks = breaksForMetric(state.selectedMetricId);
  const matchingBreak = breaks.find((item) => value >= item.min && value <= item.max);
  return (matchingBreak || breaks[breaks.length - 1]).color;
}

function breaksForMetric(metricId) {
  const config = METRIC_CONFIG[metricId] || {};
  if (config.breaks) {
    return config.breaks;
  }
  if (!state.dynamicBreaksByMetric.has(metricId)) {
    state.dynamicBreaksByMetric.set(metricId, buildDynamicBreaks(metricId));
  }
  return state.dynamicBreaksByMetric.get(metricId);
}

function buildDynamicBreaks(metricId) {
  const values = (state.valuesByMetric.get(metricId) || []).filter(Number.isFinite);
  if (!values.length) {
    return [{ min: 0, max: Infinity, color: DEFAULT_COLORS[0], label: "Sin datos" }];
  }

  const min = Math.min(...values);
  const max = Math.max(...values);
  if (min === max) {
    return [
      {
        min,
        max,
        color: DEFAULT_COLORS[2],
        label: formatLegendNumber(min, currentMetadata()),
      },
    ];
  }

  const breaks = [];
  const step = (max - min) / DEFAULT_COLORS.length;
  for (let index = 0; index < DEFAULT_COLORS.length; index += 1) {
    const start = min + step * index;
    const end = index === DEFAULT_COLORS.length - 1 ? Infinity : min + step * (index + 1);
    breaks.push({
      min: start,
      max: end,
      color: DEFAULT_COLORS[index],
      label:
        end === Infinity
          ? `${formatLegendNumber(start, currentMetadata())} o más`
          : `${formatLegendNumber(start, currentMetadata())} a ${formatLegendNumber(
              end,
              currentMetadata(),
            )}`,
    });
  }
  return breaks;
}

function valueFor(code, year) {
  return state.metricsByCommuneYear.get(
    metricKey(state.selectedMetricId, code, year),
  );
}

function metricKey(metricId, code, year) {
  return `${metricId}::${code}::${year}`;
}

function seriesKey(metricId, code) {
  return `${metricId}::${code}`;
}

function currentMetadata() {
  return (
    state.metricMetadata.get(state.selectedMetricId) || {
      id: state.selectedMetricId,
      label: state.selectedMetricId || "Indicador",
      unit: "",
      sources: [],
    }
  );
}

function labelForMetric(metricId) {
  return state.metricMetadata.get(metricId)?.label || METRIC_CONFIG[metricId]?.label || metricId;
}

function sourceNote(metadata) {
  const notes = (metadata.sources || []).map((sourceId) => SOURCE_NOTES[sourceId] || sourceId);
  return `Fuente: ${notes.join(" / ") || "fuente no especificada en el CSV"}`;
}

function formatMetricValue(value, metadata) {
  if (!Number.isFinite(value)) {
    return "Sin datos";
  }
  const decimals = decimalsForMetric(metadata);
  const formatted = new Intl.NumberFormat("es-CL", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
  return metadata.unit ? `${formatted} ${metadata.unit}` : formatted;
}

function formatAxisValue(value, metadata) {
  if (!Number.isFinite(value)) {
    return "";
  }
  if (decimalsForMetric(metadata) > 0) {
    return new Intl.NumberFormat("es-CL", {
      maximumFractionDigits: 1,
    }).format(value);
  }
  return new Intl.NumberFormat("es-CL", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}

function formatLegendNumber(value, metadata) {
  const decimals = decimalsForMetric(metadata);
  return new Intl.NumberFormat("es-CL", {
    maximumFractionDigits: decimals,
  }).format(value);
}

function decimalsForMetric(metadata) {
  if (Number.isInteger(metadata.decimals)) {
    return metadata.decimals;
  }
  return metadata.unit.includes("100.000") ? 2 : 0;
}
