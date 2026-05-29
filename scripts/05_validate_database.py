"""Validate final outputs for the first mapping milestone."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path

import geopandas as gpd
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FINAL_DIR = PROJECT_ROOT / "data" / "final"

METRICS_FILE = "valores_comunales_anuales.csv"
METRICS_PARQUET_FILE = "valores_comunales_anuales.parquet"
GEOMETRY_FILE = "comunas_rm.geojson"
SQLITE_FILE = "mapas_chile.sqlite"

RM_REGION_CODE = "13"
PERIOD_MIN_YEARS = 28
PERIOD_MAX_YEARS = 35
POPULATION_METRIC_ID = "poblacion_total"

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


@dataclass
class ValidationSummary:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    details: dict[str, object] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return not self.errors

    def add_error(self, message: str) -> None:
        self.errors.append(message)

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate final mapping outputs.")
    parser.add_argument(
        "--final-dir",
        type=Path,
        default=DEFAULT_FINAL_DIR,
        help=f"Final output directory. Default: {DEFAULT_FINAL_DIR}",
    )
    parser.add_argument(
        "--max-missing-report",
        type=int,
        default=20,
        help="Maximum missing commune-year combinations to print. Default: 20.",
    )
    return parser.parse_args()


def require_file(path: Path, summary: ValidationSummary) -> bool:
    if path.exists():
        return True
    summary.add_error(f"Required file not found: {path}")
    return False


def read_metrics(path: Path) -> pd.DataFrame:
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
    return metrics


def read_geometries(path: Path) -> gpd.GeoDataFrame:
    geometries = gpd.read_file(path)
    for column in ["codigo_comuna", "nombre_comuna", "codigo_region", "nombre_region"]:
        if column in geometries.columns:
            geometries[column] = geometries[column].astype("string")
    return geometries


def validate_required_columns(
    frame: pd.DataFrame,
    required_columns: list[str],
    label: str,
    summary: ValidationSummary,
) -> bool:
    missing = [column for column in required_columns if column not in frame.columns]
    if missing:
        summary.add_error(f"{label} is missing required columns: {missing}")
        return False
    return True


def validate_metrics(metrics: pd.DataFrame, summary: ValidationSummary) -> pd.DataFrame:
    if not validate_required_columns(metrics, METRIC_COLUMNS, "Metric table", summary):
        return metrics

    missing_values = metrics[METRIC_COLUMNS].replace("", pd.NA).isna().sum()
    missing_values = missing_values[missing_values > 0]
    if not missing_values.empty:
        summary.add_error(
            f"Metric table has missing values: {missing_values.to_dict()}"
        )

    years = pd.to_numeric(metrics["anio"], errors="coerce")
    invalid_years = years.isna() | (years != years.round())
    if invalid_years.any():
        sample = metrics.loc[invalid_years, "anio"].head(10).tolist()
        summary.add_error(f"All years must be integers. Invalid examples: {sample}")
    else:
        metrics = metrics.copy()
        metrics["anio"] = years.astype(int)

    values = pd.to_numeric(metrics["valor"], errors="coerce")
    invalid_values = values.isna()
    if invalid_values.any():
        sample = metrics.loc[invalid_values, "valor"].head(10).tolist()
        summary.add_error(f"Metric values must be numeric. Invalid examples: {sample}")
    elif (values < 0).any():
        sample = metrics.loc[
            values < 0, ["codigo_comuna", "anio", "id_metrica", "valor"]
        ]
        summary.add_error(
            "Metric values must be non-negative. "
            f"Invalid examples: {sample.head(10).to_dict('records')}"
        )
    else:
        metrics = metrics.copy()
        metrics["valor"] = values

    duplicate_columns = ["codigo_comuna", "anio", "id_metrica"]
    duplicates = metrics[metrics.duplicated(duplicate_columns, keep=False)]
    if not duplicates.empty:
        sample = duplicates[duplicate_columns].drop_duplicates().head(10)
        summary.add_error(
            "Duplicated codigo_comuna, anio, id_metrica rows found: "
            f"{sample.to_dict('records')}"
        )

    if {"anio", "id_metrica"}.issubset(metrics.columns):
        metric_summaries = []
        for metric_id, metric_rows in metrics.groupby("id_metrica", dropna=False):
            unique_years = sorted(metric_rows["anio"].dropna().unique().tolist())
            metric_summaries.append(
                {
                    "id_metrica": str(metric_id),
                    "year_min": min(unique_years) if unique_years else None,
                    "year_max": max(unique_years) if unique_years else None,
                    "year_count": len(unique_years),
                    "row_count": int(len(metric_rows)),
                }
            )
        summary.details["metric_summaries"] = metric_summaries

        population_years = sorted(
            metrics.loc[
                metrics["id_metrica"] == POPULATION_METRIC_ID,
                "anio",
            ]
            .dropna()
            .unique()
            .tolist()
        )
        summary.details["year_count"] = len(population_years)
        summary.details["year_min"] = (
            min(population_years) if population_years else None
        )
        summary.details["year_max"] = (
            max(population_years) if population_years else None
        )
        if not population_years:
            summary.add_error(f"Required metric {POPULATION_METRIC_ID!r} is missing.")
        elif not PERIOD_MIN_YEARS <= len(population_years) <= PERIOD_MAX_YEARS:
            summary.add_error(
                "Population period should cover approximately 30 years. "
                f"Found {len(population_years)} unique years."
            )

    return metrics


def validate_geometries(
    geometries: gpd.GeoDataFrame,
    summary: ValidationSummary,
) -> gpd.GeoDataFrame:
    if not validate_required_columns(
        geometries, GEOMETRY_COLUMNS, "Geometry file", summary
    ):
        return geometries

    non_rm = geometries[geometries["codigo_region"].astype(str) != RM_REGION_CODE]
    if not non_rm.empty:
        summary.add_error(
            "Geometry file must contain only Metropolitan Region communes. "
            f"Non-RM region codes: {sorted(non_rm['codigo_region'].astype(str).unique())}"
        )

    missing_geometry = geometries.geometry.isna() | geometries.geometry.is_empty
    if missing_geometry.any():
        names = geometries.loc[missing_geometry, "nombre_comuna"].tolist()
        summary.add_error(f"Missing or empty geometries found: {names}")

    invalid_geometry = ~geometries.geometry.is_valid.fillna(False)
    invalid_geometry = invalid_geometry & ~missing_geometry
    if invalid_geometry.any():
        names = geometries.loc[invalid_geometry, "nombre_comuna"].tolist()
        summary.add_error(f"Invalid geometries found: {names}")

    if geometries.crs is None or geometries.crs.to_epsg() != 4326:
        summary.add_error(f"Geometry file must use EPSG:4326. Found: {geometries.crs}")

    duplicate_codes = geometries[geometries.duplicated("codigo_comuna", keep=False)][
        "codigo_comuna"
    ]
    if not duplicate_codes.empty:
        summary.add_error(
            "Geometry file has duplicated commune codes: "
            f"{sorted(duplicate_codes.astype(str).unique().tolist())}"
        )

    summary.details["commune_count"] = int(geometries["codigo_comuna"].nunique())
    return geometries


def validate_key_coverage(
    metrics: pd.DataFrame,
    geometries: gpd.GeoDataFrame,
    summary: ValidationSummary,
) -> None:
    if (
        "codigo_comuna" not in metrics.columns
        or "codigo_comuna" not in geometries.columns
    ):
        return

    metric_codes = set(metrics["codigo_comuna"].dropna().astype(str))
    geometry_codes = set(geometries["codigo_comuna"].dropna().astype(str))
    population_codes = set(
        metrics.loc[
            metrics["id_metrica"] == POPULATION_METRIC_ID,
            "codigo_comuna",
        ]
        .dropna()
        .astype(str)
    )

    missing_population = sorted(geometry_codes - population_codes)
    unknown_metrics = sorted(metric_codes - geometry_codes)

    if missing_population:
        summary.add_error(
            "Every RM commune in the geometry file must have population values. "
            f"Missing: {missing_population}"
        )
    if unknown_metrics:
        summary.add_error(
            "Every metric row must match a known commune code. "
            f"Unknown: {unknown_metrics}"
        )


def missing_commune_years(
    metrics: pd.DataFrame,
    geometries: gpd.GeoDataFrame,
) -> pd.DataFrame:
    if not {"codigo_comuna", "anio", "id_metrica"}.issubset(metrics.columns):
        return pd.DataFrame(columns=["codigo_comuna", "anio", "id_metrica"])
    if "codigo_comuna" not in geometries.columns:
        return pd.DataFrame(columns=["codigo_comuna", "anio", "id_metrica"])

    metric_ids = sorted(metrics["id_metrica"].dropna().astype(str).unique().tolist())
    commune_codes = sorted(
        geometries["codigo_comuna"].dropna().astype(str).unique().tolist()
    )
    if not metric_ids or not commune_codes:
        return pd.DataFrame(columns=["codigo_comuna", "anio", "id_metrica"])

    observed = metrics[["codigo_comuna", "anio", "id_metrica"]].drop_duplicates().copy()
    observed["codigo_comuna"] = observed["codigo_comuna"].astype(str)
    observed["id_metrica"] = observed["id_metrica"].astype(str)

    missing_frames: list[pd.DataFrame] = []
    for metric_id in metric_ids:
        metric_rows = observed[observed["id_metrica"] == metric_id]
        valid_years = pd.to_numeric(metric_rows["anio"], errors="coerce")
        valid_years = valid_years[
            valid_years.notna() & (valid_years == valid_years.round())
        ]
        years = sorted(valid_years.astype(int).unique().tolist())
        if not years:
            continue

        expected = pd.MultiIndex.from_product(
            [commune_codes, years, [metric_id]],
            names=["codigo_comuna", "anio", "id_metrica"],
        ).to_frame(index=False)
        merged = expected.merge(
            observed,
            on=["codigo_comuna", "anio", "id_metrica"],
            how="left",
            indicator=True,
        )
        missing_frames.append(
            merged.loc[
                merged["_merge"] == "left_only",
                ["codigo_comuna", "anio", "id_metrica"],
            ]
        )

    if not missing_frames:
        return pd.DataFrame(columns=["codigo_comuna", "anio", "id_metrica"])
    return pd.concat(missing_frames, ignore_index=True)


def validate_sqlite(path: Path, summary: ValidationSummary) -> None:
    required_tables = {"comunas", "metricas", "valores_comunales_anuales", "fuentes"}
    with sqlite3.connect(path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    missing_tables = sorted(required_tables - tables)
    if missing_tables:
        summary.add_error(f"SQLite database is missing tables: {missing_tables}")


def validate_final_outputs(
    final_dir: Path, max_missing_report: int = 20
) -> ValidationSummary:
    summary = ValidationSummary()
    metrics_path = final_dir / METRICS_FILE
    parquet_path = final_dir / METRICS_PARQUET_FILE
    geometry_path = final_dir / GEOMETRY_FILE
    sqlite_path = final_dir / SQLITE_FILE

    required_paths = [metrics_path, parquet_path, geometry_path, sqlite_path]
    files_exist = [require_file(path, summary) for path in required_paths]
    if not all(files_exist):
        return summary

    metrics = validate_metrics(read_metrics(metrics_path), summary)
    geometries = validate_geometries(read_geometries(geometry_path), summary)
    validate_key_coverage(metrics, geometries, summary)
    validate_sqlite(sqlite_path, summary)

    missing = missing_commune_years(metrics, geometries)
    summary.details["missing_commune_year_count"] = len(missing)
    summary.details["missing_commune_year_examples"] = missing.head(
        max_missing_report
    ).to_dict("records")
    if not missing.empty:
        summary.add_error(
            "Missing commune-year-metric combinations found. " f"Count: {len(missing)}."
        )

    return summary


def print_summary(summary: ValidationSummary) -> None:
    print("Validation summary")
    print("==================")
    print(f"Status: {'PASS' if summary.passed else 'FAIL'}")
    print(f"Communes: {summary.details.get('commune_count', 'not available')}")
    print(
        "Population years: "
        f"{summary.details.get('year_min', 'not available')} - "
        f"{summary.details.get('year_max', 'not available')} "
        f"({summary.details.get('year_count', 'not available')} unique years)"
    )
    metric_summaries = summary.details.get("metric_summaries") or []
    if metric_summaries:
        print("Metrics:")
        for metric in metric_summaries:
            print(
                "  - "
                f"{metric['id_metrica']}: "
                f"{metric['year_min']} - {metric['year_max']} "
                f"({metric['year_count']} years, {metric['row_count']} rows)"
            )
    print(
        "Missing commune-year-metric combinations: "
        f"{summary.details.get('missing_commune_year_count', 'not available')}"
    )

    examples = summary.details.get("missing_commune_year_examples") or []
    if examples:
        print("Missing examples:")
        for row in examples:
            print(f"  - {row}")

    if summary.warnings:
        print("Warnings:")
        for warning in summary.warnings:
            print(f"  - {warning}")

    if summary.errors:
        print("Errors:")
        for error in summary.errors:
            print(f"  - {error}")


def main() -> int:
    args = parse_args()
    try:
        summary = validate_final_outputs(args.final_dir, args.max_missing_report)
    except Exception as exc:  # noqa: BLE001 - CLI should always print a summary.
        summary = ValidationSummary()
        summary.add_error(f"Validation could not complete: {exc}")
    print_summary(summary)
    return 0 if summary.passed else 1


if __name__ == "__main__":
    sys.exit(main())
