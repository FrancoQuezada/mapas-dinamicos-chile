# Dynamic Maps of Chile

This repository will host a reproducible data pipeline and visualization system for commune-level indicators in Chile. The first milestone focuses on annual total population for all communes in the Metropolitan Region of Santiago, using official or traceable public sources.

No data has been downloaded yet. This initial setup only creates the project structure, documentation templates, and Python dependency list needed to build the pipeline.

## Initial Scope

- Country: Chile
- Region: Metropolitan Region of Santiago
- Spatial unit: communes
- First metric: annual total population
- Time period: latest 30-year period available from the selected official or traceable public source
- Geometry: commune polygons suitable for web mapping

## Project Structure

```text
.
├── app/
├── data/
│   ├── raw/
│   ├── processed/
│   └── final/
├── docs/
│   ├── sources.md
│   └── data_dictionary.md
├── notebooks/
├── scripts/
├── tests/
├── AGENTS.md
├── README.md
└── requirements.txt
```

## Data Pipeline Plan

The first milestone will be implemented with reproducible scripts:

1. Download raw population and geometry sources into `data/raw/`.
2. Clean annual commune-level population data into `data/processed/`.
3. Clean commune geometries into EPSG:4326 GeoJSON under `data/processed/`.
4. Build app-ready CSV, Parquet, GeoJSON, and SQLite outputs under `data/final/`.
5. Validate source coverage, commune-code joins, duplicates, missing values, geometry validity, and temporal coverage.

## Expected Final Outputs

```text
data/final/comunas_rm.geojson
data/final/valores_comunales_anuales.csv
data/final/valores_comunales_anuales.parquet
data/final/mapas_chile.sqlite
docs/sources.md
docs/data_dictionary.md
```

## Data Principles

- Use official or traceable public sources whenever possible.
- Do not manually copy data into final files.
- Preserve raw downloaded files under `data/raw/`.
- Write cleaned intermediate outputs under `data/processed/`.
- Write app-ready outputs under `data/final/`.
- Use `codigo_comuna` as the primary key.
- Document source information, assumptions, limitations, and data lineage.
- Validate data before considering any dataset complete.
- Never invent, fabricate, or infer values that are not present in the selected source data.

## Development

Install dependencies in a virtual environment:

```bash
python -m venv .venv
pip install -r requirements.txt
```

Run tests once pipeline scripts and final outputs exist:

```bash
pytest
```

## Status

Scaffold only. Data download, cleaning scripts, validation scripts, tests, and final datasets are intentionally not created in this first setup step.
