"""Build final app-ready files and a lightweight SQLite database.

This script combines processed population metrics and processed commune
geometries. It keeps geometries in GeoJSON and writes only non-spatial tables to
SQLite.
"""

from __future__ import annotations

import argparse
import csv
import logging
import shutil
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

import geopandas as gpd
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POPULATION = PROJECT_ROOT / "data" / "processed" / "poblacion_comunal_anual.csv"
DEFAULT_INSECURITY = (
    PROJECT_ROOT / "data" / "processed" / "inseguridad_comunal_anual.csv"
)
DEFAULT_DERIVED_METRICS = (
    PROJECT_ROOT / "data" / "processed" / "metricas_derivadas_comunales_anuales.csv"
)
DEFAULT_GEOMETRIES = PROJECT_ROOT / "data" / "processed" / "comunas_rm.geojson"
DEFAULT_MANIFEST = PROJECT_ROOT / "data" / "raw" / "source_manifest.csv"
DEFAULT_FINAL_DIR = PROJECT_ROOT / "data" / "final"
DEFAULT_APP_DATA_DIR = PROJECT_ROOT / "app" / "data"

METRICS_OUTPUT_NAME = "valores_comunales_anuales"
GEOMETRIES_OUTPUT_NAME = "comunas_rm.geojson"
SQLITE_OUTPUT_NAME = "mapas_chile.sqlite"

METRIC_COLUMNS = [
    "codigo_comuna",
    "nombre_comuna",
    "codigo_region",
    "nombre_region",
    "anio",
    "id_metrica",
    "nombre_metrica",
    "valor",
    "unidad",
    "fuente",
    "fecha_descarga",
]

GEOMETRY_COLUMNS = [
    "codigo_comuna",
    "nombre_comuna",
    "codigo_region",
    "nombre_region",
    "geometry",
]

OPTIONAL_GEOMETRY_COLUMNS = [
    "codigo_provincia",
    "nombre_provincia",
]

COMUNA_COLUMNS = [
    "codigo_comuna",
    "nombre_comuna",
    "codigo_region",
    "nombre_region",
    "codigo_provincia",
    "nombre_provincia",
]

SOURCE_COLUMNS = [
    "source_id",
    "source_name",
    "institution",
    "url",
    "data_format",
    "territorial_level",
    "temporal_coverage",
    "license_or_usage_notes",
    "download_date",
    "local_raw_file",
    "processing_script",
    "known_limitations",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build final metric files, GeoJSON, and SQLite database."
    )
    parser.add_argument(
        "--population",
        type=Path,
        default=DEFAULT_POPULATION,
        help=f"Processed population CSV. Default: {DEFAULT_POPULATION}",
    )
    parser.add_argument(
        "--insecurity",
        type=Path,
        default=DEFAULT_INSECURITY,
        help=(
            "Processed insecurity CSV. If missing, it is skipped. "
            f"Default: {DEFAULT_INSECURITY}"
        ),
    )
    parser.add_argument(
        "--derived-metrics",
        type=Path,
        default=DEFAULT_DERIVED_METRICS,
        help=(
            "Processed derived metrics CSV. If missing, it is skipped. "
            f"Default: {DEFAULT_DERIVED_METRICS}"
        ),
    )
    parser.add_argument(
        "--geometries",
        type=Path,
        default=DEFAULT_GEOMETRIES,
        help=f"Processed RM GeoJSON. Default: {DEFAULT_GEOMETRIES}",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help=f"Raw source manifest. Default: {DEFAULT_MANIFEST}",
    )
    parser.add_argument(
        "--final-dir",
        type=Path,
        default=DEFAULT_FINAL_DIR,
        help=f"Final output directory. Default: {DEFAULT_FINAL_DIR}",
    )
    parser.add_argument(
        "--app-data-dir",
        type=Path,
        default=DEFAULT_APP_DATA_DIR,
        help=f"Static app data directory to sync. Default: {DEFAULT_APP_DATA_DIR}",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity. Default: INFO.",
    )
    return parser.parse_args()


def read_metric_file(path: Path, *, label: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Processed {label} file not found: {path}.")

    metrics = pd.read_csv(
        path,
        dtype={
            "codigo_comuna": "string",
            "nombre_comuna": "string",
            "codigo_region": "string",
            "nombre_region": "string",
            "id_metrica": "string",
            "nombre_metrica": "string",
            "unidad": "string",
            "fuente": "string",
            "fecha_descarga": "string",
        },
    )
    metrics["anio"] = pd.to_numeric(metrics["anio"], errors="raise").astype(int)
    metrics["valor"] = pd.to_numeric(metrics["valor"], errors="raise")
    validate_metrics(metrics, label=label)
    return metrics[METRIC_COLUMNS].copy()


def read_optional_metric_file(path: Path, *, label: str) -> pd.DataFrame:
    if not path.exists():
        logging.warning("Processed %s file not found; skipping: %s", label, path)
        return pd.DataFrame(columns=METRIC_COLUMNS)
    return read_metric_file(path, label=label)


def read_geometries(path: Path) -> gpd.GeoDataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Processed geometry file not found: {path}. "
            "Run scripts/03_clean_geometries.py first."
        )

    geometries = gpd.read_file(path)
    for column in ["codigo_comuna", "nombre_comuna", "codigo_region", "nombre_region"]:
        if column in geometries.columns:
            geometries[column] = geometries[column].astype("string")

    validate_geometries(geometries)
    if geometries.crs is None or geometries.crs.to_epsg() != 4326:
        logging.info(
            "Reprojecting final geometries from %s to EPSG:4326.", geometries.crs
        )
        geometries = geometries.to_crs("EPSG:4326")
    return geometries


def validate_metrics(metrics: pd.DataFrame, *, label: str) -> None:
    missing_columns = [
        column for column in METRIC_COLUMNS if column not in metrics.columns
    ]
    if missing_columns:
        raise ValueError(f"{label} data is missing columns: {missing_columns}")

    missing_values = metrics[METRIC_COLUMNS].replace("", pd.NA).isna().sum()
    missing_values = missing_values[missing_values > 0]
    if not missing_values.empty:
        raise ValueError(f"{label} data has missing values: {missing_values.to_dict()}")

    duplicate_columns = ["codigo_comuna", "anio", "id_metrica"]
    duplicates = metrics[metrics.duplicated(duplicate_columns, keep=False)]
    if not duplicates.empty:
        sample = (
            duplicates[duplicate_columns].drop_duplicates().head(10).to_dict("records")
        )
        raise ValueError(f"Duplicated metric rows found: {sample}")

    if (metrics["valor"] < 0).any():
        raise ValueError(f"{label} values must be non-negative.")


def validate_geometries(geometries: gpd.GeoDataFrame) -> None:
    missing_columns = [
        column for column in GEOMETRY_COLUMNS if column not in geometries.columns
    ]
    if missing_columns:
        raise ValueError(f"Geometry data is missing columns: {missing_columns}")

    missing_attributes = (
        geometries[["codigo_comuna", "nombre_comuna", "codigo_region", "nombre_region"]]
        .replace("", pd.NA)
        .isna()
        .sum()
    )
    missing_attributes = missing_attributes[missing_attributes > 0]
    if not missing_attributes.empty:
        raise ValueError(
            f"Geometry data has missing attributes: {missing_attributes.to_dict()}"
        )

    duplicate_codes = geometries[geometries.duplicated("codigo_comuna", keep=False)][
        "codigo_comuna"
    ]
    if not duplicate_codes.empty:
        raise ValueError(
            "Duplicated geometry commune codes found: "
            f"{sorted(duplicate_codes.unique().tolist())}"
        )

    missing_geometry = geometries.geometry.isna() | geometries.geometry.is_empty
    if missing_geometry.any():
        names = geometries.loc[missing_geometry, "nombre_comuna"].tolist()
        raise ValueError(f"Missing or empty geometries found: {names}")

    invalid_geometry = ~geometries.geometry.is_valid.fillna(False)
    if invalid_geometry.any():
        names = geometries.loc[invalid_geometry, "nombre_comuna"].tolist()
        raise ValueError(f"Invalid geometries found: {names}")


def validate_key_coverage(metrics: pd.DataFrame, geometries: gpd.GeoDataFrame) -> None:
    metric_codes = set(metrics["codigo_comuna"].astype(str))
    geometry_codes = set(geometries["codigo_comuna"].astype(str))

    missing_in_metrics = sorted(geometry_codes - metric_codes)
    missing_in_geometries = sorted(metric_codes - geometry_codes)

    if missing_in_metrics:
        raise ValueError(
            "Communes present in geometries but missing metric rows: "
            f"{missing_in_metrics}"
        )
    if missing_in_geometries:
        raise ValueError(
            "Communes present in metrics but missing geometries: "
            f"{missing_in_geometries}"
        )

    for metric_id, metric_rows in metrics.groupby("id_metrica", dropna=False):
        missing_for_metric = sorted(
            geometry_codes - set(metric_rows["codigo_comuna"].astype(str))
        )
        if missing_for_metric:
            raise ValueError(
                f"Communes missing rows for metric {metric_id!r}: {missing_for_metric}"
            )


def build_comunas_table(geometries: gpd.GeoDataFrame) -> pd.DataFrame:
    comunas = geometries.drop(columns="geometry").copy()

    if "codigo_provincia" not in comunas.columns:
        comunas["codigo_provincia"] = pd.NA
        logging.warning(
            "codigo_provincia not present in processed geometries; leaving null in SQLite."
        )
    if "nombre_provincia" not in comunas.columns:
        comunas["nombre_provincia"] = pd.NA
        logging.warning(
            "nombre_provincia not present in processed geometries; leaving null in SQLite."
        )

    return (
        comunas[COMUNA_COLUMNS]
        .drop_duplicates("codigo_comuna")
        .sort_values("codigo_comuna")
        .reset_index(drop=True)
    )


def final_geometry_columns(geometries: gpd.GeoDataFrame) -> list[str]:
    optional_columns = [
        column for column in OPTIONAL_GEOMETRY_COLUMNS if column in geometries.columns
    ]
    return [*GEOMETRY_COLUMNS[:-1], *optional_columns, "geometry"]


def build_metricas_table(metrics: pd.DataFrame) -> pd.DataFrame:
    metricas = (
        metrics[["id_metrica", "nombre_metrica", "unidad"]]
        .drop_duplicates()
        .sort_values("id_metrica")
        .reset_index(drop=True)
    )
    metricas["descripcion"] = (
        metricas["id_metrica"]
        .map(
            {
                "poblacion_total": (
                    "Annual total population by commune from the selected INE "
                    "commune-level estimates and projections source."
                ),
                "homicidios": (
                    "Annual total police cases categorized as homicides in CEAD "
                    "commune-level crime data."
                ),
                "tasa_homicidios_100k_hab": (
                    "Annual homicide police cases per 100,000 inhabitants, derived "
                    "from homicide counts and INE total population."
                ),
            }
        )
        .fillna("")
    )
    return metricas[["id_metrica", "nombre_metrica", "unidad", "descripcion"]]


def read_manifest(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        logging.warning(
            "Source manifest not found: %s. fuentes table will use defaults.", path
        )
        return {}

    with path.open("r", newline="", encoding="utf-8") as manifest_file:
        return {
            row["source_id"]: row
            for row in csv.DictReader(manifest_file)
            if row.get("source_id")
        }


def build_fuentes_table(metrics: pd.DataFrame, manifest_path: Path) -> pd.DataFrame:
    manifest = read_manifest(manifest_path)
    source_ids = sorted(
        set(metrics["fuente"].astype(str)) | {"commune_geometries_primary"}
    )
    rows: list[dict[str, str]] = []

    for source_id in source_ids:
        manifest_row = manifest.get(source_id, {})
        rows.append(source_metadata(source_id, manifest_row))

    return pd.DataFrame(rows, columns=SOURCE_COLUMNS)


def source_metadata(source_id: str, manifest_row: dict[str, str]) -> dict[str, str]:
    defaults = {
        "population_communal_annual": {
            "source_name": (
                "Estimaciones y proyecciones de la poblacion de Chile "
                "a nivel comunal 2002-2035, base Censo 2017"
            ),
            "institution": "Instituto Nacional de Estadisticas de Chile (INE)",
            "url": (
                "https://www.ine.gob.cl/estadisticas-por-tema/"
                "demografia-y-poblacion/estimaciones-y-proyecciones-de-poblacion"
            ),
            "data_format": "xlsx",
            "territorial_level": "commune",
            "temporal_coverage": "2002-2035",
            "license_or_usage_notes": (
                "INE open data terms require attribution and identify site content "
                "under Creative Commons Attribution-ShareAlike 4.0 International."
            ),
            "processing_script": "scripts/02_clean_population.py",
            "known_limitations": (
                "Estimate/projection product, not observed annual census counts. "
                "2018-2035 values are projections."
            ),
        },
        "commune_geometries_primary": {
            "source_name": "Division Politica Administrativa 2023",
            "institution": "IDE Chile / SUBDERE",
            "url": (
                "https://geoportal.cl/geoportal/catalog/36391/"
                "Divisi%C3%B3n%20Pol%C3%ADtica%20Administrativa%202023"
            ),
            "data_format": "shapefile zip",
            "territorial_level": "commune",
            "temporal_coverage": "2023",
            "license_or_usage_notes": (
                "Cite the provider institution listed in Geoportal metadata; preserve "
                "official boundary disclaimers."
            ),
            "processing_script": "scripts/03_clean_geometries.py",
            "known_limitations": (
                "Boundary reference dataset; raw source CRS must be reprojected for web "
                "mapping and geometry validity must be checked after download."
            ),
        },
        "insecurity_cead_delincuencia_chile": {
            "source_name": (
                "CEAD delinquency data for Chile, processed by "
                "bastianolea/delincuencia_chile"
            ),
            "institution": (
                "Centro de Estudios y Analisis del Delito (CEAD), via "
                "bastianolea/delincuencia_chile"
            ),
            "url": ("https://github.com/bastianolea/delincuencia_chile"),
            "data_format": "parquet",
            "territorial_level": "commune",
            "temporal_coverage": "2018-2025",
            "license_or_usage_notes": (
                "Traceable public repository derived from CEAD public data. Cite "
                "both CEAD/SPD and the repository used for reproducible access."
            ),
            "processing_script": "scripts/06_clean_insecurity.py",
            "known_limitations": (
                "The official CEAD web endpoint was not directly downloadable in "
                "this environment, so the pipeline uses a public processed Parquet "
                "with source scripts. Values are police cases, not victim counts, "
                "and depend on CEAD category definitions."
            ),
        },
        "derived_homicidios_rate_100k": {
            "source_name": "Derived homicide rate per 100,000 inhabitants",
            "institution": "Computed by this repository from CEAD-derived counts and INE population",
            "url": (
                "data/processed/inseguridad_comunal_anual.csv; "
                "data/processed/poblacion_comunal_anual.csv"
            ),
            "data_format": "derived csv",
            "territorial_level": "commune",
            "temporal_coverage": "2018-2025",
            "license_or_usage_notes": (
                "Derived metric; retain attribution to both underlying sources."
            ),
            "processing_script": "scripts/07_build_derived_metrics.py",
            "known_limitations": (
                "Rates are calculated only where homicide counts and population "
                "denominators overlap. Population denominators are INE estimates or "
                "projections depending on year."
            ),
        },
    }

    default = defaults.get(source_id, {})
    return {
        "source_id": source_id,
        "source_name": manifest_row.get("source_name")
        or default.get("source_name", ""),
        "institution": manifest_row.get("institution")
        or default.get("institution", ""),
        "url": manifest_row.get("url") or default.get("url", ""),
        "data_format": default.get("data_format", ""),
        "territorial_level": default.get("territorial_level", ""),
        "temporal_coverage": default.get("temporal_coverage", ""),
        "license_or_usage_notes": default.get("license_or_usage_notes", ""),
        "download_date": manifest_row.get("download_date", ""),
        "local_raw_file": manifest_row.get("local_filename", ""),
        "processing_script": default.get("processing_script", ""),
        "known_limitations": default.get("known_limitations", ""),
    }


def write_sqlite(
    path: Path,
    *,
    comunas: pd.DataFrame,
    metricas: pd.DataFrame,
    valores: pd.DataFrame,
    fuentes: pd.DataFrame,
) -> None:
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    if temp_path.exists():
        temp_path.unlink()

    with closing(sqlite3.connect(temp_path)) as connection:
        with connection:
            comunas.to_sql("comunas", connection, index=False, if_exists="replace")
            metricas.to_sql("metricas", connection, index=False, if_exists="replace")
            valores.to_sql(
                "valores_comunales_anuales",
                connection,
                index=False,
                if_exists="replace",
            )
            fuentes.to_sql("fuentes", connection, index=False, if_exists="replace")

            connection.executescript("""
                CREATE UNIQUE INDEX idx_comunas_codigo
                    ON comunas (codigo_comuna);
                CREATE UNIQUE INDEX idx_metricas_id
                    ON metricas (id_metrica);
                CREATE INDEX idx_valores_comuna_anio
                    ON valores_comunales_anuales (codigo_comuna, anio);
                CREATE UNIQUE INDEX idx_valores_unique
                    ON valores_comunales_anuales (codigo_comuna, anio, id_metrica);
                CREATE UNIQUE INDEX idx_fuentes_id
                    ON fuentes (source_id);
                """)

    temp_path.replace(path)


def sync_app_data(app_data_dir: Path, *, metrics_csv: Path, geojson: Path) -> None:
    app_data_dir.mkdir(parents=True, exist_ok=True)
    metrics_destination = app_data_dir / metrics_csv.name
    geojson_destination = app_data_dir / geojson.name
    shutil.copy2(metrics_csv, metrics_destination)
    shutil.copy2(geojson, geojson_destination)
    logging.info("Synced app metric CSV: %s", metrics_destination)
    logging.info("Synced app GeoJSON: %s", geojson_destination)


def build_outputs(args: argparse.Namespace) -> None:
    metric_frames = [
        read_metric_file(args.population, label="population"),
        read_optional_metric_file(args.insecurity, label="insecurity"),
        read_optional_metric_file(args.derived_metrics, label="derived metrics"),
    ]
    metrics = (
        pd.concat(metric_frames, ignore_index=True)
        .sort_values(["id_metrica", "codigo_comuna", "anio"])
        .reset_index(drop=True)
    )
    validate_metrics(metrics, label="combined metrics")

    geometries = read_geometries(args.geometries)
    validate_key_coverage(metrics, geometries)

    args.final_dir.mkdir(parents=True, exist_ok=True)
    final_csv = args.final_dir / f"{METRICS_OUTPUT_NAME}.csv"
    final_parquet = args.final_dir / f"{METRICS_OUTPUT_NAME}.parquet"
    final_geojson = args.final_dir / GEOMETRIES_OUTPUT_NAME
    final_sqlite = args.final_dir / SQLITE_OUTPUT_NAME

    metrics.to_csv(final_csv, index=False, encoding="utf-8")
    metrics.to_parquet(final_parquet, index=False)
    geometries[final_geometry_columns(geometries)].to_file(
        final_geojson, driver="GeoJSON"
    )

    comunas = build_comunas_table(geometries)
    metricas = build_metricas_table(metrics)
    fuentes = build_fuentes_table(metrics, args.manifest)
    write_sqlite(
        final_sqlite,
        comunas=comunas,
        metricas=metricas,
        valores=metrics,
        fuentes=fuentes,
    )
    sync_app_data(args.app_data_dir, metrics_csv=final_csv, geojson=final_geojson)

    logging.info("Wrote final metric CSV: %s", final_csv)
    logging.info("Wrote final metric Parquet: %s", final_parquet)
    logging.info("Wrote final GeoJSON: %s", final_geojson)
    logging.info("Wrote SQLite database: %s", final_sqlite)


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(levelname)s: %(message)s",
    )

    try:
        build_outputs(args)
    except Exception as exc:  # noqa: BLE001 - CLI should return clear failure.
        logging.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
