import sqlite3

import pandas as pd


METRIC_COLUMNS = {
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
}

GEOMETRY_COLUMNS = {
    "codigo_comuna",
    "nombre_comuna",
    "codigo_region",
    "nombre_region",
    "geometry",
}


def test_required_final_files_exist(final_paths):
    for path in final_paths.values():
        assert path.exists(), f"Missing required final file: {path}"


def test_required_metric_columns_exist(metrics_df):
    assert METRIC_COLUMNS.issubset(metrics_df.columns)


def test_required_geometry_columns_exist(geometries_gdf):
    assert GEOMETRY_COLUMNS.issubset(geometries_gdf.columns)


def test_commune_codes_are_strings(metrics_df, geometries_gdf):
    assert pd.api.types.is_string_dtype(metrics_df["codigo_comuna"])
    assert pd.api.types.is_string_dtype(geometries_gdf["codigo_comuna"])


def test_no_duplicate_commune_year_metric_rows(metrics_df):
    duplicate_columns = ["codigo_comuna", "anio", "id_metrica"]
    duplicates = metrics_df[metrics_df.duplicated(duplicate_columns, keep=False)]
    assert duplicates.empty, (
        duplicates[duplicate_columns].drop_duplicates().to_dict("records")
    )


def test_population_values_are_non_negative(metrics_df):
    assert (metrics_df["valor"] >= 0).all()


def test_all_years_are_integers(metrics_df):
    assert pd.api.types.is_integer_dtype(metrics_df["anio"])


def test_final_period_is_approximately_30_years(metrics_df):
    year_count = metrics_df["anio"].nunique()
    assert 28 <= year_count <= 35


def test_geometry_file_contains_valid_geometries(geometries_gdf):
    assert geometries_gdf.crs is not None
    assert geometries_gdf.crs.to_epsg() == 4326
    assert (~geometries_gdf.geometry.isna()).all()
    assert (~geometries_gdf.geometry.is_empty).all()
    assert geometries_gdf.geometry.is_valid.all()


def test_all_final_metric_rows_match_known_commune_codes(metrics_df, geometries_gdf):
    metric_codes = set(metrics_df["codigo_comuna"].dropna().astype(str))
    geometry_codes = set(geometries_gdf["codigo_comuna"].dropna().astype(str))
    assert metric_codes <= geometry_codes


def test_every_geometry_commune_has_population_values(metrics_df, geometries_gdf):
    metric_codes = set(metrics_df["codigo_comuna"].dropna().astype(str))
    geometry_codes = set(geometries_gdf["codigo_comuna"].dropna().astype(str))
    assert geometry_codes <= metric_codes


def test_no_missing_commune_year_metric_combinations(metrics_df, geometries_gdf):
    years = sorted(metrics_df["anio"].dropna().astype(int).unique().tolist())
    metric_ids = sorted(metrics_df["id_metrica"].dropna().astype(str).unique().tolist())
    commune_codes = sorted(
        geometries_gdf["codigo_comuna"].dropna().astype(str).unique().tolist()
    )

    expected = pd.MultiIndex.from_product(
        [commune_codes, years, metric_ids],
        names=["codigo_comuna", "anio", "id_metrica"],
    ).to_frame(index=False)
    observed = metrics_df[["codigo_comuna", "anio", "id_metrica"]].drop_duplicates().copy()
    observed["codigo_comuna"] = observed["codigo_comuna"].astype(str)
    observed["id_metrica"] = observed["id_metrica"].astype(str)

    missing = expected.merge(
        observed,
        on=["codigo_comuna", "anio", "id_metrica"],
        how="left",
        indicator=True,
    )
    missing = missing[missing["_merge"] == "left_only"]
    assert missing.empty, missing.head(20).to_dict("records")


def test_sqlite_database_contains_expected_tables(final_paths):
    db_path = final_paths["sqlite_db"]
    assert db_path.exists(), f"Missing SQLite database: {db_path}"

    with sqlite3.connect(db_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

    assert {"comunas", "metricas", "valores_comunales_anuales", "fuentes"} <= tables
