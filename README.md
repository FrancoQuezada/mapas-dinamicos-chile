# Dynamic Maps of Chile

Reproducible data pipeline and lightweight static web app for commune-level indicators in Chile. The current milestone covers all communes in the Metropolitan Region of Santiago.

## Current Metrics

- `poblacion_total`: annual total population from INE commune-level estimates and projections, 2002-2035.
- `homicidios`: annual homicide police cases from a traceable CEAD-derived public source, 2018-2025.
- `tasa_homicidios_100k_hab`: homicide police cases per 100,000 inhabitants, derived from the two metrics above.

## Project Structure

```text
.
├── app/
├── data/
│   ├── raw/
│   ├── processed/
│   └── final/
├── docs/
├── notebooks/
├── scripts/
├── tests/
├── AGENTS.md
├── README.md
└── requirements.txt
```

## Pipeline

Run the full current pipeline after installing dependencies:

```bash
python scripts/01_download_sources.py --source all
python scripts/02_clean_population.py
python scripts/03_clean_geometries.py
python scripts/06_clean_insecurity.py
python scripts/07_build_derived_metrics.py
python scripts/04_build_database.py
python scripts/05_validate_database.py
pytest
```

`scripts/04_build_database.py` writes final outputs under `data/final/` and syncs the static app copies under `app/data/`.

## Final Outputs

```text
data/final/comunas_rm.geojson
data/final/valores_comunales_anuales.csv
data/final/valores_comunales_anuales.parquet
data/final/mapas_chile.sqlite
docs/sources.md
docs/data_dictionary.md
```

## Static Web App

The app in `app/` uses plain HTML, CSS, JavaScript, Leaflet, Chart.js, PapaParse, and static CSV/GeoJSON files. No frontend framework or backend is required.

Run it locally:

```bash
cd app
python -m http.server 8000
```

Then open:

```text
http://localhost:8000
```
