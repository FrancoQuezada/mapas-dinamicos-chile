"""Clean annual commune population data for the Metropolitan Region.

The script reads the raw INE population workbook downloaded by
``scripts/01_download_sources.py`` and writes a long-format CSV. It does not
download data and only aggregates when the raw table has age/sex/area detail
without an explicit total row.
"""

from __future__ import annotations

import argparse
import csv
import logging
import re
import sys
import unicodedata
from numbers import Number
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "estimaciones-y-proyecciones-2002-2035-comunas.xlsx"
)
DEFAULT_MANIFEST = PROJECT_ROOT / "data" / "raw" / "source_manifest.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "processed" / "poblacion_comunal_anual.csv"

SOURCE_ID = "population_communal_annual"
METRIC_ID = "poblacion_total"
METRIC_NAME = "Población total"
UNIT = "personas"
RM_REGION_CODE = "13"
RM_REGION_NAME = "Región Metropolitana de Santiago"

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

COLUMN_ALIASES = {
    "codigo_region": {
        "codigo_region",
        "cod_region",
        "codregion",
        "region_codigo",
        "codigo_de_region",
        "codigo_region_",
    },
    "nombre_region": {
        "nombre_region",
        "nom_region",
        "region_nombre",
        "region_name",
        "nombre_de_region",
    },
    "codigo_comuna": {
        "codigo_comuna",
        "cod_comuna",
        "codcomuna",
        "comuna_codigo",
        "codigo_de_comuna",
        "codigo_com",
        "cod_com",
    },
    "nombre_comuna": {
        "nombre_comuna",
        "nom_comuna",
        "comuna_nombre",
        "nombre_de_comuna",
    },
    "anio": {"anio", "ano", "year"},
    "valor": {
        "valor",
        "poblacion",
        "poblacion_total",
        "total_poblacion",
        "total",
    },
    "sexo": {"sexo", "sex"},
    "edad": {"edad", "age"},
    "area": {"area", "zona", "urbano_rural", "area_urbano_rural"},
}

TOTAL_LABELS = {
    "total",
    "todos",
    "todas",
    "ambos",
    "ambos_sexos",
    "todas_las_edades",
    "total_comunal",
    "total_region",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Clean raw INE commune population data into long format."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"Raw population file. Default: {DEFAULT_INPUT}",
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
        "--sheet",
        default=None,
        help="Optional Excel sheet name. Defaults to all sheets and keeps usable tables.",
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
    if isinstance(value, Number) and not isinstance(value, bool):
        value_float = float(value)
        text = str(int(value_float)) if value_float.is_integer() else str(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def standardize_columns(columns: list[object]) -> list[str]:
    seen: dict[str, int] = {}
    clean_columns: list[str] = []
    for index, column in enumerate(columns):
        base = normalize_text(column) or f"unnamed_{index}"
        count = seen.get(base, 0)
        seen[base] = count + 1
        clean_columns.append(base if count == 0 else f"{base}_{count + 1}")
    return clean_columns


def is_year_column(column: str) -> bool:
    return bool(re.fullmatch(r"(poblacion_)?(19|20)\d{2}", column))


def find_header_row(raw: pd.DataFrame) -> int:
    best_index = 0
    best_score = -1
    alias_values = set().union(*COLUMN_ALIASES.values())

    for index in range(min(len(raw), 40)):
        row_values = [normalize_text(value) for value in raw.iloc[index].tolist()]
        alias_score = sum(value in alias_values for value in row_values)
        year_score = sum(is_year_column(value) for value in row_values)
        score = alias_score + min(year_score, 6)
        if score > best_score:
            best_score = score
            best_index = index

    if best_score < 3:
        raise ValueError("Could not identify a header row in the population file.")
    return best_index


def read_table_from_sheet(input_path: Path, sheet_name: str | int) -> pd.DataFrame:
    raw = pd.read_excel(input_path, sheet_name=sheet_name, header=None, dtype=object)
    raw = raw.dropna(how="all").dropna(axis=1, how="all")
    header_index = find_header_row(raw)

    table = raw.iloc[header_index + 1 :].copy()
    table.columns = standardize_columns(raw.iloc[header_index].tolist())
    table = table.dropna(how="all").dropna(axis=1, how="all")
    table.columns = standardize_columns(table.columns.tolist())
    return table


def read_raw_population(input_path: Path, sheet: str | None = None) -> pd.DataFrame:
    if not input_path.exists():
        raise FileNotFoundError(
            f"Raw population file not found: {input_path}. "
            "Run scripts/01_download_sources.py first."
        )

    suffix = input_path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        excel = pd.ExcelFile(input_path)
        sheet_names = [sheet] if sheet else excel.sheet_names
        tables: list[pd.DataFrame] = []
        for sheet_name in sheet_names:
            try:
                table = read_table_from_sheet(input_path, sheet_name)
            except Exception as exc:  # noqa: BLE001 - keep scanning workbook sheets.
                logging.debug("Skipping sheet %s: %s", sheet_name, exc)
                continue
            if looks_like_population_table(table):
                table["_source_sheet"] = str(sheet_name)
                tables.append(table)

        if not tables:
            raise ValueError(f"No usable population table found in {input_path}.")
        return pd.concat(tables, ignore_index=True)

    if suffix == ".csv":
        table = pd.read_csv(input_path, dtype=object)
        table.columns = standardize_columns(table.columns.tolist())
        return table

    raise ValueError(f"Unsupported input format: {input_path.suffix}")


def looks_like_population_table(table: pd.DataFrame) -> bool:
    columns = set(table.columns)
    has_region = "region" in columns or bool(
        columns
        & (COLUMN_ALIASES["codigo_region"] | COLUMN_ALIASES["nombre_region"])
    )
    has_commune = "comuna" in columns or bool(
        columns
        & (COLUMN_ALIASES["codigo_comuna"] | COLUMN_ALIASES["nombre_comuna"])
    )
    has_year = any(is_year_column(column) for column in columns) or any(
        column in columns for column in COLUMN_ALIASES["anio"]
    )
    return has_region and has_commune and has_year


def get_candidate_columns(table: pd.DataFrame, semantic_name: str) -> list[str]:
    aliases = COLUMN_ALIASES[semantic_name]
    return [column for column in table.columns if column in aliases]


def mostly_numeric(series: pd.Series) -> bool:
    sample = series.dropna().astype(str).str.strip()
    sample = sample[sample != ""].head(100)
    if sample.empty:
        return False
    numeric = sample.str.fullmatch(r"\d+(\.0+)?")
    return numeric.mean() >= 0.8


def choose_code_and_name_columns(
    table: pd.DataFrame,
    *,
    generic_column: str,
    code_alias: str,
    name_alias: str,
) -> tuple[str | None, str | None]:
    code_candidates = get_candidate_columns(table, code_alias)
    name_candidates = get_candidate_columns(table, name_alias)

    code_column = next((column for column in code_candidates if mostly_numeric(table[column])), None)
    name_column = next((column for column in name_candidates if not mostly_numeric(table[column])), None)

    if generic_column in table.columns:
        if code_column is None and mostly_numeric(table[generic_column]):
            code_column = generic_column
        if name_column is None and not mostly_numeric(table[generic_column]):
            name_column = generic_column

    return code_column, name_column


def parse_code(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .str.strip()
        .str.replace(r"\.0+$", "", regex=True)
        .str.replace(r"\D", "", regex=True)
    )


def parse_number(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.map(normalize_number_value), errors="coerce")


def normalize_number_value(value: object) -> object:
    if pd.isna(value):
        return None
    if isinstance(value, Number) and not isinstance(value, bool):
        return value

    text = str(value).strip()
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[^0-9,.\-]", "", text)
    if not text:
        return None

    if re.fullmatch(r"-?\d+\.0+", text):
        return text.split(".", maxsplit=1)[0]
    if "." in text and "," in text:
        return text.replace(".", "").replace(",", ".")
    if "," in text:
        return text.replace(",", ".")
    if re.fullmatch(r"-?\d{1,3}(\.\d{3})+", text):
        return text.replace(".", "")
    return text


def parse_year(series: pd.Series) -> pd.Series:
    year = parse_number(series)
    return year.astype("Int64")


def is_total_label(value: object) -> bool:
    return normalize_text(value) in TOTAL_LABELS


def reshape_to_long(table: pd.DataFrame) -> pd.DataFrame:
    year_columns = [column for column in table.columns if is_year_column(column)]
    if year_columns:
        id_columns = [column for column in table.columns if column not in year_columns]
        long = table.melt(
            id_vars=id_columns,
            value_vars=year_columns,
            var_name="anio",
            value_name="valor",
        )
        logging.info("Reshaped %s year columns from wide to long format.", len(year_columns))
        return long

    year_column = first_existing_column(table, "anio")
    value_column = first_existing_column(table, "valor")
    if year_column is None:
        raise ValueError("Could not find a year column or year-valued wide columns.")

    if value_column is None:
        male_column = find_named_column(table, {"hombres", "hombre", "varones"})
        female_column = find_named_column(table, {"mujeres", "mujer"})
        if male_column and female_column:
            table = table.copy()
            table["valor"] = parse_number(table[male_column]) + parse_number(table[female_column])
            value_column = "valor"
            logging.info("Created total value by summing male and female columns.")
        else:
            raise ValueError("Could not find a population value column.")

    long = table.copy()
    if year_column != "anio":
        long = long.rename(columns={year_column: "anio"})
    if value_column != "valor":
        long = long.rename(columns={value_column: "valor"})
    return long


def first_existing_column(table: pd.DataFrame, semantic_name: str) -> str | None:
    candidates = get_candidate_columns(table, semantic_name)
    return candidates[0] if candidates else None


def find_named_column(table: pd.DataFrame, names: set[str]) -> str | None:
    return next((column for column in table.columns if column in names), None)


def filter_metropolitan_region(table: pd.DataFrame) -> pd.DataFrame:
    region_code_column, region_name_column = choose_code_and_name_columns(
        table,
        generic_column="region",
        code_alias="codigo_region",
        name_alias="nombre_region",
    )
    commune_code_column, commune_name_column = choose_code_and_name_columns(
        table,
        generic_column="comuna",
        code_alias="codigo_comuna",
        name_alias="nombre_comuna",
    )

    if commune_code_column is None:
        raise ValueError("Could not identify a numeric commune code column.")
    if commune_name_column is None:
        raise ValueError("Could not identify a commune name column.")

    clean = table.copy()
    clean["codigo_comuna"] = parse_code(clean[commune_code_column])
    clean["nombre_comuna"] = clean[commune_name_column].astype(str).str.strip()

    if region_code_column:
        clean["codigo_region"] = parse_code(clean[region_code_column])
        clean = clean[clean["codigo_region"] == RM_REGION_CODE]
    elif region_name_column:
        clean["nombre_region"] = clean[region_name_column].astype(str).str.strip()
        region_key = clean["nombre_region"].map(normalize_text)
        clean = clean[
            region_key.str.contains("metropolitana", na=False)
            & region_key.str.contains("santiago", na=False)
        ]
        clean["codigo_region"] = RM_REGION_CODE
    else:
        clean = clean[clean["codigo_comuna"].str.startswith(RM_REGION_CODE, na=False)]
        clean["codigo_region"] = RM_REGION_CODE

    if region_name_column and "nombre_region" not in clean.columns:
        clean["nombre_region"] = clean[region_name_column].astype(str).str.strip()
    else:
        clean["nombre_region"] = RM_REGION_NAME

    if clean.empty:
        raise ValueError("No Metropolitan Region rows were found in the raw population data.")
    return clean


def resolve_total_population(table: pd.DataFrame) -> pd.DataFrame:
    working = table.copy()
    group_columns = [
        "codigo_comuna",
        "nombre_comuna",
        "codigo_region",
        "nombre_region",
        "anio",
    ]

    for dimension in ("area", "sexo", "edad"):
        dimension_column = first_existing_column(working, dimension)
        if dimension_column is None:
            continue

        total_mask = working[dimension_column].map(is_total_label)
        if total_mask.any():
            working = working[total_mask].copy()
            logging.info("Selected explicit total rows for dimension: %s.", dimension)
            continue

        duplicate_count = working.duplicated(group_columns, keep=False).sum()
        if duplicate_count:
            logging.info(
                "No explicit total rows for %s; summing detailed rows to annual totals.",
                dimension,
            )
            working = aggregate_to_commune_year(working, group_columns)

    if working.duplicated(group_columns, keep=False).any():
        remaining_dimensions = [
            first_existing_column(working, dimension)
            for dimension in ("area", "sexo", "edad")
        ]
        remaining_dimensions = [column for column in remaining_dimensions if column]
        if remaining_dimensions:
            logging.info(
                "Summing remaining detailed rows across dimensions: %s.",
                ", ".join(remaining_dimensions),
            )
            working = aggregate_to_commune_year(working, group_columns)

    return working


def aggregate_to_commune_year(table: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    return (
        table.groupby(group_columns, as_index=False, dropna=False)["valor"]
        .sum(min_count=1)
        .reset_index(drop=True)
    )


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


def validate_clean_data(clean: pd.DataFrame) -> None:
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in clean.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")

    required_values = clean[REQUIRED_COLUMNS].replace("", pd.NA)
    missing_counts = required_values.isna().sum()
    missing_counts = missing_counts[missing_counts > 0]
    if not missing_counts.empty:
        raise ValueError(f"Missing values found: {missing_counts.to_dict()}")

    duplicate_columns = ["codigo_comuna", "anio", "id_metrica"]
    duplicates = clean[clean.duplicated(duplicate_columns, keep=False)]
    if not duplicates.empty:
        sample = duplicates[duplicate_columns].drop_duplicates().head(10).to_dict("records")
        raise ValueError(f"Duplicated commune-year-metric rows found: {sample}")

    if not pd.api.types.is_integer_dtype(clean["anio"]):
        raise ValueError("Column anio must be integer typed.")

    if (clean["valor"] < 0).any():
        raise ValueError("Population values must be non-negative.")


def clean_population(args: argparse.Namespace) -> pd.DataFrame:
    raw = read_raw_population(args.input, sheet=args.sheet)
    logging.info("Read %s raw rows from %s.", len(raw), args.input)

    long = reshape_to_long(raw)
    long["anio"] = parse_year(long["anio"])
    long["valor"] = parse_number(long["valor"])
    long = long.dropna(subset=["anio", "valor"]).copy()
    long["anio"] = long["anio"].astype(int)

    rm = filter_metropolitan_region(long)
    totals = resolve_total_population(rm)

    download_date = args.download_date or read_download_date(args.manifest, args.source_id)
    clean = totals[
        [
            "codigo_comuna",
            "nombre_comuna",
            "codigo_region",
            "nombre_region",
            "anio",
            "valor",
        ]
    ].copy()
    clean["id_metrica"] = METRIC_ID
    clean["nombre_metrica"] = METRIC_NAME
    clean["unidad"] = UNIT
    clean["fuente"] = args.source_id
    clean["fecha_descarga"] = download_date
    clean = clean[REQUIRED_COLUMNS].sort_values(["codigo_comuna", "anio"]).reset_index(drop=True)

    validate_clean_data(clean)
    return clean


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(levelname)s: %(message)s",
    )

    try:
        clean = clean_population(args)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        clean.to_csv(args.output, index=False, encoding="utf-8")
        logging.info("Wrote %s rows to %s.", len(clean), args.output)
    except Exception as exc:  # noqa: BLE001 - CLI should return a clear failure.
        logging.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
