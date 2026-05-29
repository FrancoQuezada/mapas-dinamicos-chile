# Data Dictionary

This document defines the expected schema for the first milestone outputs. Final datasets have not been generated yet.

## `valores_comunales_anuales`

Long-format table containing annual commune-level metric values.

| column_name | description | data_type | example | required | notes |
|---|---|---|---|---|---|
| `codigo_comuna` | Unique commune code. | string | `13101` | yes | Primary join key. Preserve leading zeroes if present in source systems. |
| `nombre_comuna` | Commune name. | string | `Santiago` | yes | Standardized from the selected source. |
| `codigo_region` | Region code. | string | `13` | yes | Metropolitan Region of Santiago for the first milestone. |
| `nombre_region` | Region name. | string | `Región Metropolitana de Santiago` | yes | Use a consistent official or source-documented name. |
| `anio` | Calendar year for the metric value. | integer | `2024` | yes | Must be an integer. |
| `id_metrica` | Stable metric identifier. | string | `poblacion_total` | yes | First milestone uses only `poblacion_total`. |
| `nombre_metrica` | Human-readable metric name. | string | `Población total` | yes | First milestone metric label. |
| `valor` | Metric value. | numeric | `404495` | yes | Population values must be non-negative. |
| `unidad` | Measurement unit. | string | `personas` | yes | First milestone unit is `personas`. |
| `fuente` | Source identifier or citation reference. | string | `population_communal_annual` | yes | Must map to `docs/sources.md` and the `fuentes` table. |
| `fecha_descarga` | Date when the raw source was downloaded. | date | `2026-05-29` | yes | Use ISO `YYYY-MM-DD`. |

Expected final files:

- `data/final/valores_comunales_anuales.csv`
- `data/final/valores_comunales_anuales.parquet`

## `comunas`

Reference table for communes included in the pipeline.

| column_name | description | data_type | example | required | notes |
|---|---|---|---|---|---|
| `codigo_comuna` | Unique commune code. | string | `13101` | yes | Primary key. |
| `nombre_comuna` | Commune name. | string | `Santiago` | yes | Should match final metric table. |
| `codigo_region` | Region code. | string | `13` | yes | First milestone includes only the Metropolitan Region. |
| `nombre_region` | Region name. | string | `Región Metropolitana de Santiago` | yes | Standardized region name. |
| `codigo_provincia` | Province code. | string | `131` | yes | Source-dependent; must be documented. |
| `nombre_provincia` | Province name. | string | `Santiago` | yes | Source-dependent; must be documented. |

Expected SQLite table:

- `comunas`

## `comunas_rm.geojson`

Web-ready GeoJSON file containing commune polygons for the Metropolitan Region of Santiago.

| column_name | description | data_type | example | required | notes |
|---|---|---|---|---|---|
| `codigo_comuna` | Unique commune code. | string | `13101` | yes | Must match metric table commune codes. |
| `nombre_comuna` | Commune name. | string | `Santiago` | yes | Standardized commune name. |
| `codigo_region` | Region code. | string | `13` | yes | First milestone includes only Metropolitan Region communes. |
| `nombre_region` | Region name. | string | `Región Metropolitana de Santiago` | yes | Standardized region name. |
| `geometry` | Commune polygon or multipolygon geometry. | geometry | `MULTIPOLYGON (...)` | yes | Must be valid and exported as EPSG:4326. |

Expected final file:

- `data/final/comunas_rm.geojson`

## `metricas`

Metric reference table in SQLite.

| column_name | description | data_type | example | required | notes |
|---|---|---|---|---|---|
| `id_metrica` | Stable metric identifier. | string | `poblacion_total` | yes | Primary key. |
| `nombre_metrica` | Human-readable metric name. | string | `Población total` | yes | Display label. |
| `unidad` | Measurement unit. | string | `personas` | yes | Unit used in metric table. |
| `descripcion` | Brief metric description. | string | `Annual total population by commune.` | yes | Update with source methodology when selected. |

Expected SQLite table:

- `metricas`

## `fuentes`

Source metadata table in SQLite.

| column_name | description | data_type | example | required | notes |
|---|---|---|---|---|---|
| `source_id` | Stable source identifier. | string | `population_communal_annual` | yes | Primary key. |
| `source_name` | Dataset title. | string | `To be selected` | yes | Must match source registry. |
| `institution` | Publishing institution. | string | `INE` | yes | Use the official or traceable source institution. |
| `url` | Original source URL. | string | `https://...` | yes | Preserve original URL. |
| `data_format` | Source data format. | string | `xlsx` | yes | File or API format. |
| `territorial_level` | Territorial level represented by the source. | string | `commune` | yes | First milestone requires commune-level data. |
| `temporal_coverage` | Years or validity period covered. | string | `1995-2024` | yes | Confirm after source selection. |
| `license_or_usage_notes` | License, citation, or usage notes. | string | `To be confirmed` | yes | Must be documented before finalizing data. |
| `download_date` | Raw download date. | date | `2026-05-29` | yes | ISO `YYYY-MM-DD`. |
| `local_raw_file` | Path to raw source file. | string | `data/raw/source.xlsx` | yes | Must point under `data/raw/`. |
| `processing_script` | Script that processes the source. | string | `scripts/02_clean_population.py` | yes | Track lineage. |
| `known_limitations` | Source limitations or caveats. | string | `To be confirmed` | yes | Include coverage and methodology limitations. |

Expected SQLite table:

- `fuentes`

## SQLite Database

Expected final database:

- `data/final/mapas_chile.sqlite`

Expected tables:

- `comunas`
- `metricas`
- `valores_comunales_anuales`
- `fuentes`
