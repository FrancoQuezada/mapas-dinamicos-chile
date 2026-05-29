# AGENTS.md

This project builds dynamic and interactive maps with Chilean territorial data.

## Main objective

Create a reproducible, AI-assisted data pipeline and visualization system for commune-level indicators in Chile, starting with all communes in the Metropolitan Region of Santiago.

The first milestone is to build a validated database for interactive maps that shows the evolution of annual commune-level metrics over time.

## Initial scope

The first dataset should cover:

- Country: Chile
- Region: Metropolitan Region of Santiago
- Spatial unit: communes
- First metric: annual total population
- Time period: latest 30-year period available from the selected official or traceable public source
- Geometry: commune polygons suitable for web mapping

## Data principles

- Use official or traceable public sources whenever possible.
- Do not manually copy data into final files.
- Always create reproducible scripts that download, clean, validate, and document data.
- Preserve raw downloaded files under `data/raw/`.
- Write intermediate cleaned outputs under `data/processed/`.
- Write app-ready outputs under `data/final/`.
- Use commune code as the primary key, not commune name.
- Keep source information and data lineage documented.
- Add validation checks before considering any dataset complete.
- Never invent, fabricate, or infer values that are not present in the source data.
- If a source has limitations, document them explicitly.

## Preferred sources

For the initial dataset, prioritize the following types of sources:

### Population data

Use official or traceable sources such as:

- Instituto Nacional de Estadísticas de Chile, INE
- Official population estimates and projections
- Commune-level annual population tables

### Commune geometries

Use official or traceable geospatial sources such as:

- IDE Chile / Geoportal Chile
- SUBDERE
- Biblioteca del Congreso Nacional, BCN
- Other public and documented commune boundary datasets

## Repository structure

Create and maintain the following structure:

```text
mapas-dinamicos-chile/
├── data/
│   ├── raw/
│   ├── processed/
│   └── final/
├── docs/
│   ├── sources.md
│   └── data_dictionary.md
├── scripts/
│   ├── 01_download_sources.py
│   ├── 02_clean_population.py
│   ├── 03_clean_geometries.py
│   ├── 04_build_database.py
│   └── 05_validate_database.py
├── notebooks/
├── app/
├── tests/
├── AGENTS.md
├── requirements.txt
└── README.md
```

## Expected final outputs

Generate the following files for the first milestone:

```text
data/final/comunas_rm.geojson
data/final/valores_comunales_anuales.csv
data/final/valores_comunales_anuales.parquet
data/final/mapas_chile.sqlite
docs/sources.md
docs/data_dictionary.md
```

## Data model

Use a long-format metric table.

The central table should follow this structure:

```text
codigo_comuna
nombre_comuna
codigo_region
nombre_region
anio
id_metrica
nombre_metrica
valor
unidad
fuente
fecha_descarga
```

For the first metric:

```text
id_metrica: poblacion_total
nombre_metrica: Población total
unidad: personas
```

## Commune table

Create a commune reference table with:

```text
codigo_comuna
nombre_comuna
codigo_region
nombre_region
codigo_provincia
nombre_provincia
```

Use `codigo_comuna` as the unique identifier.

## Geometry table or file

Create a web-ready GeoJSON file with:

```text
codigo_comuna
nombre_comuna
codigo_region
nombre_region
geometry
```

The geometry file should:

- Include only communes from the Metropolitan Region of Santiago for the first milestone.
- Use EPSG:4326.
- Have valid geometries.
- Use standardized column names.
- Match the same commune codes used in the metric table.

## Scripts

### `scripts/01_download_sources.py`

Create a script that downloads the selected raw data sources.

Requirements:

- Save all downloaded files under `data/raw/`.
- Do not overwrite files unless a `--force` flag is passed.
- Log the original URL, local filename, download date, and file size.
- Create or update `data/raw/source_manifest.csv`.
- Include clear error handling.
- Use `argparse`.
- Do not clean or transform the data in this script.

### `scripts/02_clean_population.py`

Create a script that reads the raw population data and produces:

```text
data/processed/poblacion_comunal_anual.csv
```

Requirements:

- Keep only communes from the Metropolitan Region of Santiago.
- Use commune codes as strings.
- Standardize year as integer.
- Use `poblacion_total` as `id_metrica`.
- Use `personas` as unit.
- Keep the data in long format.
- Add validation checks for duplicated commune-year rows and missing values.
- Document all assumptions in comments and in `docs/sources.md`.

### `scripts/03_clean_geometries.py`

Create a script that reads the raw commune geometries and produces:

```text
data/processed/comunas_rm.geojson
```

Requirements:

- Keep only communes from the Metropolitan Region of Santiago.
- Preserve commune code and commune name.
- Standardize fields to:
  - `codigo_comuna`
  - `nombre_comuna`
  - `codigo_region`
  - `nombre_region`
  - `geometry`
- Reproject to EPSG:4326.
- Validate geometries and fix invalid geometries when possible.
- Warn if any commune has missing or invalid geometry.

### `scripts/04_build_database.py`

Create a script that combines cleaned metrics and cleaned geometries.

Generate:

```text
data/final/valores_comunales_anuales.csv
data/final/valores_comunales_anuales.parquet
data/final/comunas_rm.geojson
data/final/mapas_chile.sqlite
```

The SQLite database should include:

- `comunas`
- `metricas`
- `valores_comunales_anuales`
- `fuentes`

For now, keep geometries as GeoJSON instead of storing them inside SQLite, unless a reliable and simple spatial setup is implemented.

### `scripts/05_validate_database.py`

Create a validation script.

Validation rules:

- Every Metropolitan Region commune in the geometry file must have population values.
- Every population row must match a known commune code.
- There must be no duplicated rows for:
  - `codigo_comuna`
  - `anio`
  - `id_metrica`
- All years must be integers.
- All population values must be non-negative.
- The final period should cover approximately 30 years.
- Missing commune-year combinations must be reported.
- The script should print a clear validation summary.

## Tests

Add tests under `tests/`.

Tests should be runnable with:

```bash
pytest
```

At minimum, test:

- Required files exist.
- Required columns exist.
- Commune codes are strings.
- No duplicated commune-year-metric rows exist.
- Population values are non-negative.
- Geometry file exists and contains valid geometries.
- All final metric rows match known commune codes.

## Documentation

### `docs/sources.md`

Document every source with:

```text
source_id
source_name
institution
url
data_format
territorial_level
temporal_coverage
license_or_usage_notes
download_date
local_raw_file
processing_script
known_limitations
```

### `docs/data_dictionary.md`

Document every final table and column.

For each column, include:

```text
column_name
description
data_type
example
required
notes
```

## Coding style

- Write clear, readable Python.
- Use functions instead of long monolithic scripts.
- Include useful logging.
- Prefer explicit column mappings over implicit assumptions.
- Avoid hardcoding values unless documented.
- Use `pathlib.Path` for file paths.
- Use `pandas` for tabular data.
- Use `geopandas` for geospatial data.
- Use `pytest` for tests.
- Use `black`-compatible formatting.

## AI workflow rules

When using AI agents such as Codex:

- Make small, reviewable changes.
- Prefer pull requests or commits with clear messages.
- Do not mix data download, cleaning, validation, and app development in one large task.
- Always inspect generated code before running it.
- Ask the AI to explain assumptions and source limitations.
- Ask the AI to add tests when it creates data-processing scripts.
- Do not accept final datasets unless validation passes.

## First milestone definition of done

The first milestone is complete only when:

- The raw sources are downloaded reproducibly.
- Source metadata is documented.
- Population data is cleaned for all Metropolitan Region communes.
- Commune geometries are cleaned and exported as GeoJSON.
- Final metric files are generated in CSV and Parquet.
- SQLite database is generated.
- Validation script passes.
- Tests pass.
- The data dictionary is updated.
- The source documentation is updated.

## Future extensions

After the first population dataset is complete, the same pipeline should support additional metrics such as:

- population density
- poverty
- income
- crime
- education
- health services
- green areas
- building permits
- municipal budget
- public transport access
- environmental indicators

Each new metric should be added through the same reproducible process:

```text
source documentation
download script
cleaning script
validation
final dataset update
data dictionary update
```
