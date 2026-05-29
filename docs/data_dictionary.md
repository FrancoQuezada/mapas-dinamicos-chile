# Data Dictionary

This document defines the schema for the current final outputs.

## `valores_comunales_anuales`

Long-format table containing annual commune-level metric values.

| column_name | description | data_type | example | required | notes |
|---|---|---|---|---|---|
| `codigo_comuna` | Unique commune code. | string | `13101` | yes | Primary join key. Preserve leading zeroes if present in source systems. |
| `nombre_comuna` | Commune name. | string | `Santiago` | yes | Standardized from the selected source or commune reference. |
| `codigo_region` | Region code. | string | `13` | yes | Metropolitan Region of Santiago for the current milestone. |
| `nombre_region` | Region name. | string | `Región Metropolitana de Santiago` | yes | Use a consistent official or source-documented name. |
| `anio` | Calendar year for the metric value. | integer | `2024` | yes | Must be an integer. |
| `id_metrica` | Stable metric identifier. | string | `poblacion_total` | yes | Current metric IDs are listed below. |
| `nombre_metrica` | Human-readable metric name. | string | `Población total` | yes | Display label from the processed source or derived metric script. |
| `valor` | Metric value. | numeric | `404495` | yes | Values must be non-negative. Rates use per 100,000 inhabitants, not percent. |
| `unidad` | Measurement unit. | string | `personas` | yes | Examples: `personas`, `casos policiales`, `casos por 100.000 habitantes`. |
| `fuente` | Source identifier or citation reference. | string | `population_communal_annual` | yes | Must map to `docs/sources.md` and the `fuentes` table. |
| `fecha_descarga` | Date when the raw source was downloaded. | date | `2026-05-29` | yes | Use ISO `YYYY-MM-DD`; derived metrics use the latest underlying source download date. |

Expected final files:

- `data/final/valores_comunales_anuales.csv`
- `data/final/valores_comunales_anuales.parquet`

Current metric IDs:

| id_metrica | nombre_metrica | unidad | source or derivation | current_years | notes |
|---|---|---|---|---|---|
| `poblacion_total` | `Población total` | `personas` | INE commune-level estimates and projections. | 2002-2035 | Includes estimates and projections when applicable. |
| `homicidios` | `Homicidios` | `casos policiales` | CEAD-derived public Parquet, aggregated from monthly rows to annual commune totals. | 2018-2025 | Police cases, not homicide victims or convictions. |
| `tasa_homicidios_100k_hab` | `Tasa de homicidios por 100.000 habitantes` | `casos por 100.000 habitantes` | `homicidios / poblacion_total * 100000`. | 2018-2025 | Generated only where numerator and positive population denominator are available. |

## `comunas`

Reference table for communes included in the pipeline.

| column_name | description | data_type | example | required | notes |
|---|---|---|---|---|---|
| `codigo_comuna` | Unique commune code. | string | `13101` | yes | Primary key. |
| `nombre_comuna` | Commune name. | string | `Santiago` | yes | Should match final metric table. |
| `codigo_region` | Region code. | string | `13` | yes | Current milestone includes only the Metropolitan Region. |
| `nombre_region` | Region name. | string | `Región Metropolitana de Santiago` | yes | Standardized region name. |
| `codigo_provincia` | Province code. | string | `131` | no | Source-dependent; currently left null if the geometry source lacks it. |
| `nombre_provincia` | Province name. | string | `Santiago` | no | Source-dependent; currently left null if the geometry source lacks it. |

Expected SQLite table:

- `comunas`

## `comunas_rm.geojson`

Web-ready GeoJSON file containing commune polygons for the Metropolitan Region of Santiago.

| column_name | description | data_type | example | required | notes |
|---|---|---|---|---|---|
| `codigo_comuna` | Unique commune code. | string | `13101` | yes | Must match metric table commune codes. |
| `nombre_comuna` | Commune name. | string | `Santiago` | yes | Standardized commune name. |
| `codigo_region` | Region code. | string | `13` | yes | Current milestone includes only Metropolitan Region communes. |
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
| `descripcion` | Brief metric description. | string | `Annual total population by commune.` | yes | Documents whether a metric is source-derived or calculated. |

Expected SQLite table:

- `metricas`

## `fuentes`

Source metadata table in SQLite.

| column_name | description | data_type | example | required | notes |
|---|---|---|---|---|---|
| `source_id` | Stable source identifier. | string | `population_communal_annual` | yes | Primary key. |
| `source_name` | Dataset title. | string | `Estimaciones y proyecciones...` | yes | Must match source registry. |
| `institution` | Publishing institution. | string | `INE` | yes | Use the official or traceable source institution. |
| `url` | Original source URL. | string | `https://...` | yes | Preserve original URL or derivation inputs. |
| `data_format` | Source data format. | string | `xlsx` | yes | File, API, or derived format. |
| `territorial_level` | Territorial level represented by the source. | string | `commune` | yes | Current milestone requires commune-level data. |
| `temporal_coverage` | Years or validity period covered. | string | `2002-2035` | yes | Confirm per source. |
| `license_or_usage_notes` | License, citation, or usage notes. | string | `Cite INE...` | yes | Must be documented before finalizing data. |
| `download_date` | Raw download date. | date | `2026-05-29` | yes | ISO `YYYY-MM-DD`; may be blank for static geometry defaults if manifest is unavailable. |
| `local_raw_file` | Path to raw source file. | string | `data/raw/source.xlsx` | yes | Must point under `data/raw/` for downloaded sources. |
| `processing_script` | Script that processes the source. | string | `scripts/02_clean_population.py` | yes | Track lineage. |
| `known_limitations` | Source limitations or caveats. | string | `Estimates/projections...` | yes | Include coverage and methodology limitations. |

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

## Processed Intermediate Files

| file | description | produced_by |
|---|---|---|
| `data/processed/poblacion_comunal_anual.csv` | Clean annual total population by commune. | `scripts/02_clean_population.py` |
| `data/processed/inseguridad_comunal_anual.csv` | Clean annual homicide police cases by commune. | `scripts/06_clean_insecurity.py` |
| `data/processed/metricas_derivadas_comunales_anuales.csv` | Derived homicide rates per 100,000 inhabitants. | `scripts/07_build_derived_metrics.py` |
