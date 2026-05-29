from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FINAL_DIR = PROJECT_ROOT / "data" / "final"
METRICS_CSV = FINAL_DIR / "valores_comunales_anuales.csv"
METRICS_PARQUET = FINAL_DIR / "valores_comunales_anuales.parquet"
GEOMETRIES_GEOJSON = FINAL_DIR / "comunas_rm.geojson"
SQLITE_DB = FINAL_DIR / "mapas_chile.sqlite"


@pytest.fixture(scope="session")
def final_paths():
    return {
        "metrics_csv": METRICS_CSV,
        "metrics_parquet": METRICS_PARQUET,
        "geometries_geojson": GEOMETRIES_GEOJSON,
        "sqlite_db": SQLITE_DB,
    }


@pytest.fixture(scope="session")
def metrics_df():
    assert METRICS_CSV.exists(), f"Missing final metrics CSV: {METRICS_CSV}"
    metrics = pd.read_csv(
        METRICS_CSV,
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
    return metrics


@pytest.fixture(scope="session")
def geometries_gdf():
    assert GEOMETRIES_GEOJSON.exists(), (
        f"Missing final geometry GeoJSON: {GEOMETRIES_GEOJSON}"
    )
    geometries = gpd.read_file(GEOMETRIES_GEOJSON)
    for column in ["codigo_comuna", "nombre_comuna", "codigo_region", "nombre_region"]:
        if column in geometries.columns:
            geometries[column] = geometries[column].astype("string")
    return geometries
