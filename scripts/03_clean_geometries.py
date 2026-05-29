"""Clean raw commune geometries for the Metropolitan Region.

The script reads the raw political-administrative boundary file downloaded by
``scripts/01_download_sources.py`` and writes a web-ready GeoJSON. It does not
download data; it only extracts/reads the raw geometry source, standardizes
fields, filters Metropolitan Region communes, repairs geometries when possible,
and reprojects to EPSG:4326.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
import unicodedata
import zipfile
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterator

import geopandas as gpd
import pandas as pd
from shapely.validation import make_valid


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = PROJECT_ROOT / "data" / "raw" / "division-politica-administrativa-2023.zip"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "processed" / "comunas_rm.geojson"

RM_REGION_CODE = "13"
RM_REGION_NAME = "Regi\u00f3n Metropolitana de Santiago"
TARGET_CRS = "EPSG:4326"

REQUIRED_COLUMNS = [
    "codigo_comuna",
    "nombre_comuna",
    "codigo_region",
    "nombre_region",
    "geometry",
]

COLUMN_ALIASES = {
    "codigo_region": {
        "codigo_region",
        "cod_region",
        "codregion",
        "cod_reg",
        "cut_reg",
        "cut_region",
        "region_id",
        "codigo_re",
        "cod_regi",
        "reg",
    },
    "nombre_region": {
        "nombre_region",
        "nom_region",
        "nom_reg",
        "region",
        "region_nom",
        "nombre_reg",
        "nombre_re",
    },
    "codigo_comuna": {
        "codigo_comuna",
        "cod_comuna",
        "codcomuna",
        "cod_com",
        "cut_com",
        "cut_comuna",
        "comuna_id",
        "codigo_co",
        "cod_comu",
        "com",
    },
    "nombre_comuna": {
        "nombre_comuna",
        "nom_comuna",
        "nom_com",
        "comuna",
        "comuna_nom",
        "nombre_com",
        "nombre_co",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Clean raw commune geometries into an RM GeoJSON."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"Raw geometry file, ZIP, or directory. Default: {DEFAULT_INPUT}",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Processed GeoJSON path. Default: {DEFAULT_OUTPUT}",
    )
    parser.add_argument(
        "--source-crs",
        default=None,
        help="Optional CRS to assign if the raw file has no CRS metadata.",
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


def standardize_attribute_columns(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    geometry_column = gdf.geometry.name
    rename_map: dict[str, str] = {}
    seen: dict[str, int] = {}

    for column in gdf.columns:
        if column == geometry_column:
            continue
        base = normalize_text(column) or "unnamed"
        count = seen.get(base, 0)
        seen[base] = count + 1
        rename_map[column] = base if count == 0 else f"{base}_{count + 1}"

    return gdf.rename(columns=rename_map)


def parse_code(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .str.strip()
        .str.replace(r"\.0+$", "", regex=True)
        .str.replace(r"\D", "", regex=True)
    )


def mostly_numeric(series: pd.Series) -> bool:
    sample = series.dropna().astype(str).str.strip()
    sample = sample[sample != ""].head(100)
    if sample.empty:
        return False
    numeric = sample.str.fullmatch(r"\d+(\.0+)?")
    return numeric.mean() >= 0.8


def candidate_columns(gdf: gpd.GeoDataFrame, semantic_name: str) -> list[str]:
    aliases = COLUMN_ALIASES[semantic_name]
    return [column for column in gdf.columns if column in aliases]


def choose_column(
    gdf: gpd.GeoDataFrame,
    semantic_name: str,
    *,
    expect_numeric: bool,
) -> str | None:
    candidates = candidate_columns(gdf, semantic_name)
    for column in candidates:
        if mostly_numeric(gdf[column]) == expect_numeric:
            return column
    return candidates[0] if candidates else None


def shapefile_rank(path: Path) -> tuple[int, str]:
    normalized = normalize_text(path.stem)
    score = 0
    if "comuna" in normalized or "comunal" in normalized:
        score += 10
    if "limite" in normalized or "dpa" in normalized:
        score += 2
    if "prov" in normalized or "region" in normalized or "regional" in normalized:
        score -= 8
    return score, normalized


def choose_shapefile(paths: list[Path]) -> Path:
    if not paths:
        raise FileNotFoundError("No shapefile found in the raw geometry source.")
    ranked = sorted(paths, key=shapefile_rank, reverse=True)
    chosen = ranked[0]
    logging.info("Selected shapefile layer: %s", chosen)
    return chosen


@contextmanager
def geometry_source_path(input_path: Path) -> Iterator[Path]:
    if not input_path.exists():
        raise FileNotFoundError(
            f"Raw geometry file not found: {input_path}. "
            "Run scripts/01_download_sources.py first."
        )

    if input_path.is_dir():
        yield choose_shapefile(list(input_path.rglob("*.shp")))
        return

    if input_path.suffix.lower() == ".zip":
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            try:
                with zipfile.ZipFile(input_path) as archive:
                    safe_extract_zip(archive, temp_path)
            except zipfile.BadZipFile as exc:
                raise ValueError(f"Invalid ZIP file: {input_path}") from exc
            yield choose_shapefile(list(temp_path.rglob("*.shp")))
        return

    if input_path.suffix.lower() == ".shp":
        yield input_path
        return

    raise ValueError(
        f"Unsupported geometry input format: {input_path.suffix}. "
        "Expected a ZIP, directory, or .shp file."
    )


def safe_extract_zip(archive: zipfile.ZipFile, destination: Path) -> None:
    destination = destination.resolve()
    for member in archive.infolist():
        member_path = (destination / member.filename).resolve()
        if destination not in member_path.parents and member_path != destination:
            raise ValueError(f"Unsafe path found inside ZIP archive: {member.filename}")
    archive.extractall(destination)


def read_raw_geometries(input_path: Path, source_crs: str | None) -> gpd.GeoDataFrame:
    with geometry_source_path(input_path) as layer_path:
        gdf = gpd.read_file(layer_path)

    if gdf.empty:
        raise ValueError(f"No features found in {input_path}.")

    if gdf.crs is None:
        if source_crs is None:
            raise ValueError(
                "Raw geometry has no CRS metadata. Pass --source-crs to assign one."
            )
        logging.warning("Raw geometry has no CRS; assigning %s.", source_crs)
        gdf = gdf.set_crs(source_crs)

    logging.info("Read %s raw features with CRS %s.", len(gdf), gdf.crs)
    return standardize_attribute_columns(gdf)


def standardize_fields(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    region_code_column = choose_column(gdf, "codigo_region", expect_numeric=True)
    region_name_column = choose_column(gdf, "nombre_region", expect_numeric=False)
    commune_code_column = choose_column(gdf, "codigo_comuna", expect_numeric=True)
    commune_name_column = choose_column(gdf, "nombre_comuna", expect_numeric=False)

    if commune_code_column is None:
        raise ValueError("Could not identify a commune code column in raw geometries.")
    if commune_name_column is None:
        raise ValueError("Could not identify a commune name column in raw geometries.")

    clean = gdf.copy()
    clean["codigo_comuna"] = parse_code(clean[commune_code_column])
    clean["nombre_comuna"] = clean[commune_name_column].astype(str).str.strip()

    if region_code_column:
        clean["codigo_region"] = parse_code(clean[region_code_column])
    else:
        clean["codigo_region"] = clean["codigo_comuna"].str.slice(0, 2)
        logging.warning(
            "No region code column found; inferred codigo_region from codigo_comuna."
        )

    if region_name_column:
        clean["nombre_region"] = clean[region_name_column].astype(str).str.strip()
    else:
        clean["nombre_region"] = RM_REGION_NAME
        logging.warning("No region name column found; using standardized RM name.")

    return clean


def filter_metropolitan_region(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    by_code = gdf[gdf["codigo_region"] == RM_REGION_CODE].copy()
    if not by_code.empty:
        by_code["nombre_region"] = RM_REGION_NAME
        return by_code

    region_key = gdf["nombre_region"].map(normalize_text)
    by_name = gdf[
        region_key.str.contains("metropolitana", na=False)
        & region_key.str.contains("santiago", na=False)
    ].copy()
    if not by_name.empty:
        by_name["codigo_region"] = RM_REGION_CODE
        by_name["nombre_region"] = RM_REGION_NAME
        return by_name

    by_commune_code = gdf[gdf["codigo_comuna"].str.startswith(RM_REGION_CODE, na=False)].copy()
    if not by_commune_code.empty:
        by_commune_code["codigo_region"] = RM_REGION_CODE
        by_commune_code["nombre_region"] = RM_REGION_NAME
        logging.warning(
            "Filtered RM using codigo_comuna prefix because region attributes did not match."
        )
        return by_commune_code

    raise ValueError("No Metropolitan Region commune geometries were found.")


def fix_geometries(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    clean = gdf.copy()
    missing_mask = clean.geometry.isna() | clean.geometry.is_empty
    if missing_mask.any():
        names = clean.loc[missing_mask, "nombre_comuna"].tolist()
        logging.warning("Communes with missing or empty geometry: %s", names)

    invalid_mask = ~clean.geometry.is_valid.fillna(False)
    invalid_mask = invalid_mask & ~missing_mask
    if invalid_mask.any():
        names = clean.loc[invalid_mask, "nombre_comuna"].tolist()
        logging.warning("Invalid geometries before repair: %s", names)
        clean.loc[invalid_mask, "geometry"] = clean.loc[invalid_mask, "geometry"].map(
            make_valid
        )

    still_invalid = ~clean.geometry.is_valid.fillna(False)
    still_invalid = still_invalid & ~(clean.geometry.isna() | clean.geometry.is_empty)
    if still_invalid.any():
        names = clean.loc[still_invalid, "nombre_comuna"].tolist()
        logging.warning("Geometries still invalid after repair: %s", names)
    else:
        logging.info("All non-empty geometries are valid after repair.")

    return clean


def validate_output(gdf: gpd.GeoDataFrame) -> None:
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in gdf.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")

    required_values = gdf[["codigo_comuna", "nombre_comuna", "codigo_region", "nombre_region"]]
    required_values = required_values.replace("", pd.NA)
    missing_counts = required_values.isna().sum()
    missing_counts = missing_counts[missing_counts > 0]
    if not missing_counts.empty:
        raise ValueError(f"Missing required attribute values: {missing_counts.to_dict()}")

    duplicate_codes = gdf[gdf.duplicated("codigo_comuna", keep=False)]["codigo_comuna"]
    if not duplicate_codes.empty:
        raise ValueError(
            "Duplicated codigo_comuna values found: "
            f"{sorted(duplicate_codes.unique().tolist())}"
        )

    missing_geometry = gdf.geometry.isna() | gdf.geometry.is_empty
    if missing_geometry.any():
        names = gdf.loc[missing_geometry, "nombre_comuna"].tolist()
        logging.warning("Output contains missing or empty geometries: %s", names)

    invalid_geometry = ~gdf.geometry.is_valid.fillna(False)
    invalid_geometry = invalid_geometry & ~missing_geometry
    if invalid_geometry.any():
        names = gdf.loc[invalid_geometry, "nombre_comuna"].tolist()
        logging.warning("Output contains invalid geometries: %s", names)

    if gdf.crs is None or gdf.crs.to_epsg() != 4326:
        raise ValueError(f"Output CRS must be EPSG:4326, got {gdf.crs}.")


def clean_geometries(args: argparse.Namespace) -> gpd.GeoDataFrame:
    raw = read_raw_geometries(args.input, args.source_crs)
    standardized = standardize_fields(raw)
    rm = filter_metropolitan_region(standardized)
    rm = rm[REQUIRED_COLUMNS].copy()
    rm = fix_geometries(rm)
    rm = rm.to_crs(TARGET_CRS)
    rm = rm.sort_values("codigo_comuna").reset_index(drop=True)
    validate_output(rm)
    return rm


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(levelname)s: %(message)s",
    )

    try:
        clean = clean_geometries(args)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        clean.to_file(args.output, driver="GeoJSON")
        logging.info("Wrote %s commune geometries to %s.", len(clean), args.output)
    except Exception as exc:  # noqa: BLE001 - CLI should return clear failure.
        logging.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
