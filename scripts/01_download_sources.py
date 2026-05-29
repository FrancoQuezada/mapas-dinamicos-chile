"""Download raw source files for the first mapping milestone.

This script only downloads source files and records metadata. It does not clean,
filter, reproject, unzip, or otherwise transform the raw data.
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Iterable

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DEFAULT_MANIFEST = DEFAULT_RAW_DIR / "source_manifest.csv"

MANIFEST_FIELDS = [
    "source_id",
    "source_name",
    "institution",
    "url",
    "local_filename",
    "download_date",
    "file_size_bytes",
]


@dataclass(frozen=True)
class Source:
    source_id: str
    source_name: str
    institution: str
    url: str
    filename: str
    expected_magic: bytes
    minimum_size_bytes: int


# Source assumptions:
# - INE's commune population file is kept as the raw Excel workbook published by
#   INE. Later scripts are responsible for selecting total population and RM
#   communes; this script intentionally avoids parsing or reshaping the workbook.
# - Geoportal's DPA 2023 endpoint returns a ZIP containing shapefile components.
#   Later scripts choose the commune layer, repair geometries, and reproject.
# - Both selected raw formats are ZIP-based binaries, so the small magic-byte
#   check below catches common failures such as an HTML error page saved as data.
SOURCES = {
    "population_communal_annual": Source(
        source_id="population_communal_annual",
        source_name=(
            "Estimaciones y proyecciones de la poblacion de Chile "
            "a nivel comunal 2002-2035, base Censo 2017"
        ),
        institution="Instituto Nacional de Estadisticas de Chile (INE)",
        url=(
            "https://www.ine.gob.cl/docs/default-source/proyecciones-de-poblacion/"
            "cuadros-estadisticos/base-2017/"
            "estimaciones-y-proyecciones-2002-2035-comunas.xlsx"
            "?sfvrsn=8c87fc3f_3"
        ),
        filename="estimaciones-y-proyecciones-2002-2035-comunas.xlsx",
        expected_magic=b"PK",
        minimum_size_bytes=100_000,
    ),
    "commune_geometries_primary": Source(
        source_id="commune_geometries_primary",
        source_name="Division Politica Administrativa 2023",
        institution="IDE Chile / SUBDERE",
        url=(
            "https://www.geoportal.cl/geoportal/catalog/download/"
            "912598ad-ac92-35f6-8045-098f214bd9c2"
        ),
        filename="division-politica-administrativa-2023.zip",
        expected_magic=b"PK",
        minimum_size_bytes=100_000,
    ),
    "insecurity_cead_delincuencia_chile": Source(
        source_id="insecurity_cead_delincuencia_chile",
        source_name=(
            "CEAD delinquency data for Chile, processed by "
            "bastianolea/delincuencia_chile"
        ),
        institution=(
            "Centro de Estudios y Analisis del Delito (CEAD), via "
            "bastianolea/delincuencia_chile"
        ),
        url=(
            "https://raw.githubusercontent.com/bastianolea/"
            "delincuencia_chile/main/datos/procesados/"
            "cead_delincuencia_chile.parquet"
        ),
        filename="cead_delincuencia_chile.parquet",
        expected_magic=b"PAR1",
        minimum_size_bytes=100_000,
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Download raw population and commune geometry sources into data/raw."
        )
    )
    parser.add_argument(
        "--source",
        choices=[*SOURCES.keys(), "all"],
        action="append",
        default=None,
        help=(
            "Source to download. May be passed multiple times. "
            "Defaults to all selected sources."
        ),
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=DEFAULT_RAW_DIR,
        help=f"Directory for raw downloads. Default: {DEFAULT_RAW_DIR}",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help=f"Manifest CSV path. Default: {DEFAULT_MANIFEST}",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="HTTP timeout in seconds. Default: 60.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity. Default: INFO.",
    )
    return parser.parse_args()


def selected_sources(source_args: list[str] | None) -> list[Source]:
    if not source_args or "all" in source_args:
        return list(SOURCES.values())

    seen: set[str] = set()
    result: list[Source] = []
    for source_id in source_args:
        if source_id in seen:
            continue
        seen.add(source_id)
        result.append(SOURCES[source_id])
    return result


def download_source(
    source: Source,
    raw_dir: Path,
    *,
    force: bool,
    timeout: int,
) -> Path:
    raw_dir.mkdir(parents=True, exist_ok=True)
    destination = raw_dir / source.filename

    if destination.exists() and not force:
        raise FileExistsError(
            f"{destination} already exists. Re-run with --force to overwrite it."
        )

    logging.info("Downloading %s", source.source_id)
    logging.debug("Source URL: %s", source.url)

    temp_path: Path | None = None
    try:
        with requests.get(source.url, stream=True, timeout=timeout) as response:
            response.raise_for_status()

            with NamedTemporaryFile(
                delete=False,
                dir=raw_dir,
                prefix=f".{source.filename}.",
                suffix=".tmp",
            ) as temp_file:
                temp_path = Path(temp_file.name)
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        temp_file.write(chunk)

        validate_downloaded_file(source, temp_path)

        temp_path.replace(destination)
        logging.info(
            "Saved %s (%s bytes)",
            destination,
            destination.stat().st_size,
        )
        return destination
    except requests.RequestException as exc:
        if temp_path and temp_path.exists():
            temp_path.unlink()
        raise RuntimeError(f"Failed to download {source.source_id}: {exc}") from exc
    except Exception:
        if temp_path and temp_path.exists():
            temp_path.unlink()
        raise


def validate_downloaded_file(source: Source, path: Path | None) -> None:
    if path is None:
        raise RuntimeError(f"No temporary file was created for {source.source_id}.")

    file_size = path.stat().st_size
    if file_size < source.minimum_size_bytes:
        raise RuntimeError(
            f"Downloaded file for {source.source_id} is unexpectedly small "
            f"({file_size} bytes)."
        )

    with path.open("rb") as downloaded_file:
        signature = downloaded_file.read(len(source.expected_magic))
    if signature != source.expected_magic:
        raise RuntimeError(
            f"Downloaded file for {source.source_id} does not match the expected "
            f"binary signature."
        )


def read_manifest(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []

    with path.open("r", newline="", encoding="utf-8") as manifest_file:
        reader = csv.DictReader(manifest_file)
        if reader.fieldnames != MANIFEST_FIELDS:
            raise ValueError(
                f"Unexpected manifest columns in {path}: {reader.fieldnames}. "
                f"Expected: {MANIFEST_FIELDS}."
            )
        return [dict(row) for row in reader]


def write_manifest(path: Path, rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as manifest_file:
        writer = csv.DictWriter(manifest_file, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def update_manifest(path: Path, source: Source, downloaded_path: Path) -> None:
    rows = read_manifest(path)
    download_date = datetime.now(timezone.utc).date().isoformat()
    file_size = str(downloaded_path.stat().st_size)

    new_row = {
        "source_id": source.source_id,
        "source_name": source.source_name,
        "institution": source.institution,
        "url": source.url,
        "local_filename": display_path(downloaded_path),
        "download_date": download_date,
        "file_size_bytes": file_size,
    }

    rows = [row for row in rows if row.get("source_id") != source.source_id]
    rows.append(new_row)
    rows.sort(key=lambda row: row["source_id"])
    write_manifest(path, rows)
    logging.info("Manifest source URL: %s", source.url)
    logging.info("Manifest local filename: %s", new_row["local_filename"])
    logging.info("Manifest download date: %s", download_date)
    logging.info("Manifest file size: %s bytes", file_size)
    logging.info("Updated manifest: %s", path)


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(levelname)s: %(message)s",
    )

    failures: list[str] = []
    for source in selected_sources(args.source):
        try:
            downloaded_path = download_source(
                source,
                args.raw_dir,
                force=args.force,
                timeout=args.timeout,
            )
            update_manifest(args.manifest, source, downloaded_path)
        except Exception as exc:  # noqa: BLE001 - CLI should report all failures.
            logging.error("%s", exc)
            failures.append(source.source_id)

    if failures:
        logging.error("Download failed for: %s", ", ".join(failures))
        return 1

    logging.info("All requested sources downloaded successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
