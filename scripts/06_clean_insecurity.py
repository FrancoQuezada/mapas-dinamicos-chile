"""Clean commune-level insecurity metrics for the Metropolitan Region.

The selected traceable source republishes CEAD police-case data as a Parquet
file. This script extracts the annual total for the homicide category and joins
the existing commune reference from the processed geometry file so names and
codes stay aligned across metrics.
"""

from __future__ import annotations

import argparse
import csv
import logging
import re
import sys
import unicodedata
from pathlib import Path

import geopandas as gpd
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = PROJECT_ROOT / "data" / "raw" / "cead_delincuencia_chile.parquet"
DEFAULT_COMMUNES = PROJECT_ROOT / "data" / "processed" / "comunas_rm.geojson"
DEFAULT_MANIFEST = PROJECT_ROOT / "data" / "raw" / "source_manifest.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "processed" / "inseguridad_comunal_anual.csv"

SOURCE_ID = "insecurity_cead_delincuencia_chile"
METRIC_ID = "homicidios"
METRIC_NAME = "Homicidios"
UNIT = "casos policiales"
RM_REGION_CODE = "13"
RM_REGION_NAME = "Región Metropolitana de Santiago"

SOURCE_COLUMNS = {
    "comuna",
    "cut_comuna",
    "region",
    "cut_region",
    "fecha",
    "delito",
    "delito_n",
}

REQUIRED_COLUMNS = [
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
        description="Clean CEAD homicide data into annual RM commune metrics."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"Raw CEAD-derived Parquet. Default: {DEFAULT_INPUT}",
    )
    parser.add_argument(
        "--communes",
        type=Path,
        default=DEFAULT_COMMUNES,
        help=f"Processed RM commune GeoJSON. Default: {DEFAULT_COMMUNES}",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Processed CSV path. Default: {DEFAULT_OUTPUT}",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help=f"Download manifest from 01_download_sources.py. Default: {DEFAULT_MANIFEST}",
    )
    parser.add_argument(
        "--source-id",
        default=SOURCE_ID,
        help=f"Source id to read from the manifest. Default: {SOURCE_ID}",
    )
    parser.add_argument(
        "--download-date",
        default=None,
        help="Override fecha_descarga. Defaults to the source manifest date.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity. Default: INFO.",
    )
    return parser.parse_args()


def normalize_text(value: object) -> str:
    text = "" if pd.isna(value) else str(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def parse_code(series: pd.Series) -> pd.Series:
    return (
        pd.to_numeric(series, errors="coerce")
        .astype("Int64")
        .astype("string")
        .str.replace("<NA>", "", regex=False)
    )


def read_raw_insecurity(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Raw insecurity file not found: {path}. "
            "Run scripts/01_download_sources.py --source insecurity_cead_delincuencia_chile first."
        )

    if path.suffix.lower() != ".parquet":
        raise ValueError(f"Unsupported insecurity input format: {path.suffix}")

    raw = pd.read_parquet(path)
    missing_columns = sorted(SOURCE_COLUMNS - set(raw.columns))
    if missing_columns:
        raise ValueError(f"Raw insecurity data is missing columns: {missing_columns}")
    return raw


def read_communes(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Processed commune reference not found: {path}. "
            "Run scripts/03_clean_geometries.py first."
        )

    communes = gpd.read_file(path).drop(columns="geometry")
    required = ["codigo_comuna", "nombre_comuna", "codigo_region", "nombre_region"]
    missing_columns = [column for column in required if column not in communes.columns]
    if missing_columns:
        raise ValueError(f"Commune reference is missing columns: {missing_columns}")

    communes = communes[required].copy()
    communes["codigo_comuna"] = communes["codigo_comuna"].astype("string")
    communes["codigo_region"] = communes["codigo_region"].astype("string")
    return communes.drop_duplicates("codigo_comuna")


def read_download_date(manifest_path: Path, source_id: str) -> str:
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Manifest not found: {manifest_path}. "
            "Run scripts/01_download_sources.py first or pass --download-date."
        )

    with manifest_path.open("r", newline="", encoding="utf-8") as manifest_file:
        for row in csv.DictReader(manifest_file):
            if row.get("source_id") == source_id:
                download_date = row.get("download_date")
                if download_date:
                    return download_date

    raise ValueError(f"Source id {source_id!r} not found in {manifest_path}.")


def clean_insecurity(args: argparse.Namespace) -> pd.DataFrame:
    raw = read_raw_insecurity(args.input)
    communes = read_communes(args.communes)

    working = raw.copy()
    working["codigo_comuna"] = parse_code(working["cut_comuna"])
    working["codigo_region"] = parse_code(working["cut_region"])
    working["anio"] = pd.to_datetime(working["fecha"], errors="coerce").dt.year
    working["valor"] = pd.to_numeric(working["delito_n"], errors="coerce")
    working["delito_key"] = working["delito"].map(normalize_text)

    filtered = working[
        (working["codigo_region"] == RM_REGION_CODE)
        & (working["delito_key"] == "homicidios")
    ].copy()
    filtered = filtered.dropna(subset=["codigo_comuna", "anio", "valor"])
    filtered["anio"] = filtered["anio"].astype(int)

    if filtered.empty:
        raise ValueError("No RM homicide rows were found in the raw insecurity data.")

    annual = (
        filtered.groupby(["codigo_comuna", "anio"], as_index=False)["valor"]
        .sum(min_count=1)
        .reset_index(drop=True)
    )

    if annual["valor"].dropna().mod(1).eq(0).all():
        annual["valor"] = annual["valor"].astype(int)

    clean = annual.merge(
        communes, on="codigo_comuna", how="left", validate="many_to_one"
    )
    clean["codigo_region"] = clean["codigo_region"].fillna(RM_REGION_CODE)
    clean["nombre_region"] = clean["nombre_region"].fillna(RM_REGION_NAME)
    clean["id_metrica"] = METRIC_ID
    clean["nombre_metrica"] = METRIC_NAME
    clean["unidad"] = UNIT
    clean["fuente"] = args.source_id
    clean["fecha_descarga"] = args.download_date or read_download_date(
        args.manifest,
        args.source_id,
    )
    clean = (
        clean[REQUIRED_COLUMNS]
        .sort_values(["codigo_comuna", "anio"])
        .reset_index(drop=True)
    )

    validate_clean_data(clean, communes)
    return clean


def validate_clean_data(clean: pd.DataFrame, communes: pd.DataFrame) -> None:
    missing_values = clean[REQUIRED_COLUMNS].replace("", pd.NA).isna().sum()
    missing_values = missing_values[missing_values > 0]
    if not missing_values.empty:
        raise ValueError(f"Missing values found: {missing_values.to_dict()}")

    duplicate_columns = ["codigo_comuna", "anio", "id_metrica"]
    duplicates = clean[clean.duplicated(duplicate_columns, keep=False)]
    if not duplicates.empty:
        sample = (
            duplicates[duplicate_columns].drop_duplicates().head(10).to_dict("records")
        )
        raise ValueError(f"Duplicated commune-year-metric rows found: {sample}")

    if not pd.api.types.is_integer_dtype(clean["anio"]):
        raise ValueError("Column anio must be integer typed.")

    if (clean["valor"] < 0).any():
        raise ValueError("Insecurity values must be non-negative.")

    metric_codes = set(clean["codigo_comuna"].astype(str))
    commune_codes = set(communes["codigo_comuna"].astype(str))
    missing_codes = sorted(commune_codes - metric_codes)
    unknown_codes = sorted(metric_codes - commune_codes)
    if missing_codes:
        raise ValueError(f"RM communes missing homicide rows: {missing_codes}")
    if unknown_codes:
        raise ValueError(f"Homicide rows with unknown commune codes: {unknown_codes}")

    expected = pd.MultiIndex.from_product(
        [
            sorted(commune_codes),
            sorted(clean["anio"].unique().tolist()),
            [METRIC_ID],
        ],
        names=["codigo_comuna", "anio", "id_metrica"],
    ).to_frame(index=False)
    observed = clean[["codigo_comuna", "anio", "id_metrica"]].drop_duplicates()
    missing = expected.merge(
        observed,
        on=["codigo_comuna", "anio", "id_metrica"],
        how="left",
        indicator=True,
    )
    missing = missing[missing["_merge"] == "left_only"]
    if not missing.empty:
        raise ValueError(
            "Missing homicide commune-year combinations: "
            f"{missing.head(10).to_dict('records')}"
        )


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(levelname)s: %(message)s",
    )

    try:
        clean = clean_insecurity(args)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        clean.to_csv(args.output, index=False, encoding="utf-8")
        logging.info("Wrote %s rows to %s.", len(clean), args.output)
    except Exception as exc:  # noqa: BLE001 - CLI should return a clear failure.
        logging.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
