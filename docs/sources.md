# Source Registry

This file documents researched source options and data lineage decisions for the first milestone. No sources have been downloaded yet.

Research date: 2026-05-29

## Selected Sources For First Milestone

| source_id | source_name | institution | URL | data_format | territorial_level | temporal_coverage | license_or_usage_notes | why_the_source_is_appropriate | known_limitations |
|---|---|---|---|---|---|---|---|---|---|
| `population_communal_annual` | Estimaciones y proyecciones de la poblacion de Chile a nivel comunal 2002-2035, base Censo 2017 | Instituto Nacional de Estadisticas de Chile (INE) | Main portal: <https://www.ine.gob.cl/estadisticas-por-tema/demografia-y-poblacion/estimaciones-y-proyecciones-de-poblacion>. Methodology PDF: <https://www.ine.gob.cl/docs/default-source/proyecciones-de-poblacion/metodologia/proyecci%C3%B3n-base-2017/estimaciones-y-proyecciones-2002-2035-comunas-metodolog%C3%ADa.pdf?sfvrsn=9459d1b0_4> | Excel and CSV, according to the INE methodology document. | Commune; disaggregated by sex and age in the source, from which annual total population can be aggregated. | 2002-2035. For a 30-year milestone window, use the latest available 30-year span from this source, likely 2006-2035 inclusive, unless the pipeline intentionally restricts to observed or past years. | INE open data terms indicate Creative Commons Attribution-ShareAlike 4.0 International for site content, with attribution required and derived analyses not to be presented as INE products. Citation should include INE, product name, and update/download date. | Official national statistics office source; commune-level annual population estimates/projections; explicitly designed as an input for public and private planning; covers more than 30 annual observations; provides standardized national coverage including the Metropolitan Region of Santiago. | This is an estimates/projections product, not observed annual census counts. 2002-2017 are revised/interpolated estimates based on Census 2002 and Census 2017 inputs; 2018-2035 are projections and may differ from later demographic reality. INE has begun publishing base-2024 projections, but as of this research pass no commune-level 30-year base-2024 table was confirmed; the download script should re-check before implementation. |
| `commune_geometries_primary` | Division Politica Administrativa 2023 | IDE Chile / Geoportal de Chile; provider listed as Subsecretaria de Desarrollo Regional y Administrativo (SUBDERE), with DPA working group participation from SUBDERE, IGM, DIFROL, and INE | Metadata page: <https://geoportal.cl/geoportal/catalog/36391/Divisi%C3%B3n%20Pol%C3%ADtica%20Administrativa%202023>. Download endpoint: <https://www.geoportal.cl/geoportal/catalog/download/912598ad-ac92-35f6-8045-098f214bd9c2>. SUBDERE page: <https://ide.subdere.gov.cl/project/division-politico-administrativa-2023/> | Shapefile download; SUBDERE page also lists SHP and KML. | Commune, province, and region polygons for Chile; the milestone will filter communes to the Metropolitan Region of Santiago. | Published 2023-09-29 in Geoportal metadata; SUBDERE page lists creation date 2022-11-14 and update date 2023-08-03. | Geoportal asks users to cite the provider institution identified in the metadata. Metadata includes DIFROL circulation/disclaimer language for boundary publications. Specific open license terms were not clearly stated on the metadata page, so downstream docs should preserve provider citation and disclaimer text. | Best primary geometry source because it is a public government geospatial catalog record for the national political-administrative division, coordinated by the relevant boundary/statistical institutions. It includes national commune polygons and is suitable for deriving a web-ready EPSG:4326 GeoJSON for RM communes. | Source CRS is SIRGAS Chile / EPSG:5360 according to SUBDERE metadata, so geometries must be reprojected to EPSG:4326. Geoportal metadata states the layer does not include the Chilean Antarctic Territory / comuna Antartica. Boundary data is legal/cartographic reference material and must not be treated as resolving boundary disputes. Geometry validity and attribute code fields must be validated after download. |

## Traceable Fallback / Cross-Check Sources

| source_id | source_name | institution | URL | data_format | territorial_level | temporal_coverage | license_or_usage_notes | why_the_source_is_appropriate | known_limitations |
|---|---|---|---|---|---|---|---|---|---|
| `commune_geometries_fallback_bcn` | Mapas vectoriales - Division comunal: poligonos de las comunas de Chile | Biblioteca del Congreso Nacional de Chile (BCN), Sistema Integrado de Informacion Territorial (SIIT) | <https://www.bcn.cl/siit/mapas_vectoriales> | ZIP containing ESRI Shapefile components. | Commune polygons for Chile. | BCN states that the vector material synthesizes official sources with mixed temporal states, including editions from 2014, 2017, and December 2018. | BCN states the information can be used freely if BCN is cited as the source. It also says the material is referential and should not be used for work requiring geodetic precision. | Useful traceable fallback and QA comparison source if the IDE/SUBDERE DPA 2023 download is unavailable or if commune-code/name matching needs independent comparison. | Less current than DPA 2023 and explicitly mixed-vintage. BCN warns there is no permanent release schedule and that the material is referential, not suitable for high-precision geodetic work. Prefer IDE/SUBDERE DPA 2023 for the first production pipeline. |
| `population_context_base_2024` | Estimaciones y Proyecciones de Poblacion, base 2024 | Instituto Nacional de Estadisticas de Chile (INE) | Portal: <https://www.ine.gob.cl/estadisticas-por-tema/demografia-y-poblacion/estimaciones-y-proyecciones-de-poblacion>. Example announcement: <https://www.ine.gob.cl/sala-de-prensa/prensa/general/noticia/2026/01/28/el-ine-proyecta-que-en-2026-la-poblaci%C3%B3n-de-chile-alcanzar%C3%A1-las-20.150.948-personas-llegando-a-su-nivel-m%C3%A1ximo-a-mediados-de-la-pr%C3%B3xima-d%C3%A9cada> | Public INE publications/tabulations; exact commune-level downloadable format not confirmed in this research pass. | Confirmed in public material at national level; commune-level 30-year table not confirmed. | Base 2024 materials refer to long-run projections such as 1992-2070 for Chile. | Same INE open data terms as above, subject to the specific product metadata. | Important context because it may supersede base-2017 projections for some levels. The download script should check this source family again before implementing population extraction. | Not selected for this milestone because commune-level annual coverage sufficient for approximately 30 years was not confirmed during this research pass. Do not mix base-2024 national/regional projections with base-2017 commune projections unless INE provides a consistent commune-level table. |

## Processing Notes For Future Scripts

- `scripts/01_download_sources.py` should download the selected INE population tabulation only after resolving the direct Excel/CSV file URL from the INE portal.
- `scripts/02_clean_population.py` should aggregate source sex/age detail to total annual population by `codigo_comuna` and `anio`, preserving INE source metadata.
- `scripts/03_clean_geometries.py` should download the DPA 2023 shapefile, select the commune layer, filter `codigo_region == "13"` or the documented equivalent, validate/fix geometries where possible, and reproject to EPSG:4326.
- Commune-code compatibility between INE population tabulations and DPA 2023 geometry attributes must be validated before final outputs are accepted.
- If INE publishes a newer commune-level base-2024 projection table before implementation, prefer the newer official commune-level source only if it provides enough annual commune-level coverage for the milestone.

## Required Source Fields

Each source entry must include:

- `source_id`: stable identifier used in processing logs and final metadata.
- `source_name`: human-readable dataset title.
- `institution`: publishing institution or traceable data maintainer.
- `url`: original source URL.
- `data_format`: file or API format.
- `territorial_level`: commune, province, region, or other unit.
- `temporal_coverage`: years or validity period covered by the source.
- `license_or_usage_notes`: license, terms, citation guidance, or access notes.
- `download_date`: ISO date when the raw file was downloaded. Use `Not downloaded yet` until implemented.
- `local_raw_file`: path under `data/raw/`. Use `Not downloaded yet` until implemented.
- `processing_script`: script responsible for cleaning or transforming the source.
- `known_limitations`: caveats, coverage gaps, methodological notes, or boundary vintage issues.

## Assumptions Log

- The first population milestone will treat INE's `2002-2035` commune-level product as the selected source unless a newer commune-level base-2024 series is confirmed before the download script is written.
- The milestone metric `poblacion_total` will be produced by summing or selecting the total population across all sex and age categories from the INE commune-level source, without inventing values.
- The primary geometry source will be IDE Chile / SUBDERE DPA 2023, converted from source CRS to EPSG:4326 for web mapping.
