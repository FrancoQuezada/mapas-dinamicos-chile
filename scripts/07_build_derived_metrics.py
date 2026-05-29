"""Build derived annual commune metrics.

For the first derived metric, homicide counts are divided by INE total
population and scaled to rates per 100,000 inhabitants. Rows are only produced
where both numerator and denominator are available and population is positive.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POPULATION = PROJECT_ROOT / "data" / "processed" / "poblacion_comunal_anual.csv"
DEFAULT_INSECURITY = (
    PROJECT_ROOT / "data" / "processed" / "inseguridad_comunal_anual.csv"
)
DEFAULT_OUTPUT = (
    PROJECT_ROOT / "data" / "processed" / "metricas_derivadas_comunales_anuales.csv"
)

POPULATION_METRIC_ID = "poblacion_total"
HOMICIDE_METRIC_ID = "homicidios"
HOMICIDE_RATE_METRIC_ID = "tasa_homicidios_100k_hab"
HOMICIDE_RATE_METRIC_NAME = "Tasa de homicidios por 100.000 habitantes"
HOMICIDE_RATE_UNIT = "casos por 100.000 habitantes"
DERIVED_SOURCE_ID = "derived_homicidios_rate_100k"

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build derived rate metrics from processed source metrics."
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
        help=f"Processed insecurity CSV. Default: {DEFAULT_INSECURITY}",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Processed derived metrics CSV. Default: {DEFAULT_OUTPUT}",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity. Default: INFO.",
    )
    return parser.parse_args()


def read_metrics(path: Path, *, label: str) -> pd.DataFrame:
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
    missing_columns = [
        column for column in METRIC_COLUMNS if column not in metrics.columns
    ]
    if missing_columns:
        raise ValueError(f"{label} metrics are missing columns: {missing_columns}")

    metrics["anio"] = pd.to_numeric(metrics["anio"], errors="raise").astype(int)
    metrics["valor"] = pd.to_numeric(metrics["valor"], errors="raise")
    return metrics[METRIC_COLUMNS].copy()


def build_homicide_rate(
    population: pd.DataFrame, insecurity: pd.DataFrame
) -> pd.DataFrame:
    population = population[population["id_metrica"] == POPULATION_METRIC_ID].copy()
    homicides = insecurity[insecurity["id_metrica"] == HOMICIDE_METRIC_ID].copy()

    if population.empty:
        raise ValueError(f"No {POPULATION_METRIC_ID} rows found in population data.")
    if homicides.empty:
        raise ValueError(f"No {HOMICIDE_METRIC_ID} rows found in insecurity data.")

    joined = homicides.merge(
        population[["codigo_comuna", "anio", "valor", "fecha_descarga"]],
        on=["codigo_comuna", "anio"],
        how="inner",
        suffixes=("_numerador", "_poblacion"),
        validate="one_to_one",
    )

    unavailable_rows = len(homicides) - len(joined)
    if unavailable_rows:
        logging.warning(
            "Skipped %s homicide rows without matching population denominator.",
            unavailable_rows,
        )

    joined = joined[joined["valor_poblacion"] > 0].copy()
    skipped_zero = len(homicides) - unavailable_rows - len(joined)
    if skipped_zero:
        logging.warning(
            "Skipped %s homicide rows with zero or invalid population denominator.",
            skipped_zero,
        )

    joined["valor"] = joined["valor_numerador"] / joined["valor_poblacion"] * 100_000
    joined["id_metrica"] = HOMICIDE_RATE_METRIC_ID
    joined["nombre_metrica"] = HOMICIDE_RATE_METRIC_NAME
    joined["unidad"] = HOMICIDE_RATE_UNIT
    joined["fuente"] = DERIVED_SOURCE_ID
    joined["fecha_descarga"] = joined[
        ["fecha_descarga_numerador", "fecha_descarga_poblacion"]
    ].max(axis=1)

    derived = joined[
        [
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
    ].copy()
    return derived.sort_values(["codigo_comuna", "anio"]).reset_index(drop=True)


def validate_derived_metrics(metrics: pd.DataFrame) -> None:
    missing_values = metrics[METRIC_COLUMNS].replace("", pd.NA).isna().sum()
    missing_values = missing_values[missing_values > 0]
    if not missing_values.empty:
        raise ValueError(
            f"Derived metrics have missing values: {missing_values.to_dict()}"
        )

    duplicate_columns = ["codigo_comuna", "anio", "id_metrica"]
    duplicates = metrics[metrics.duplicated(duplicate_columns, keep=False)]
    if not duplicates.empty:
        sample = (
            duplicates[duplicate_columns].drop_duplicates().head(10).to_dict("records")
        )
        raise ValueError(f"Duplicated derived metric rows found: {sample}")

    if (metrics["valor"] < 0).any():
        raise ValueError("Derived metric values must be non-negative.")

    if not pd.api.types.is_integer_dtype(metrics["anio"]):
        raise ValueError("Column anio must be integer typed.")


def build_derived_metrics(args: argparse.Namespace) -> pd.DataFrame:
    population = read_metrics(args.population, label="population")
    insecurity = read_metrics(args.insecurity, label="insecurity")
    derived = build_homicide_rate(population, insecurity)
    validate_derived_metrics(derived)
    return derived


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(levelname)s: %(message)s",
    )

    try:
        derived = build_derived_metrics(args)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        derived.to_csv(args.output, index=False, encoding="utf-8")
        logging.info("Wrote %s rows to %s.", len(derived), args.output)
    except Exception as exc:  # noqa: BLE001 - CLI should return a clear failure.
        logging.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
