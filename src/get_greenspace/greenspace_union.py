"""
-------------------------------------------------------------------------------
Title: ""
Description: ""
Created: 18/03/2026
Author: tommycollins1 (trc207)
Notes:
    input:
    output:
-------------------------------------------------------------------------------
"""
from json import dumps
from shapely.geometry import box
from multiprocessing import Pool
from functools import partial
from shapely.wkt import loads, dumps
from shapely.validation import explain_validity, make_valid
from shapely.geometry import MultiPolygon, Polygon

import numpy as np
from shapely.ops import unary_union
from pathlib import Path
import geopandas as gpd
import pandas as pd

from src.get_greenspace.cfg import (
    OX_ASSEMBLE_GREENSPACE,
    GET_GREENSPACE,
    ALL_ASSEMBLE_GREENSPACE
)
# stripped for public repo: from src.get_visage.vi_config import GET_VISAGE  # todo remvo?


def clean_geometries(gdf, precision=1.0):
    gdf = gdf.copy()
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty]

    gdf["geometry"] = gdf.geometry.make_valid()
    gdf["geometry"] = gdf.geometry.set_precision(precision)
    gdf["geometry"] = gdf.geometry.make_valid()

    # Force re-noding
    gdf["geometry"] = gdf.geometry.buffer(0)
    gdf["geometry"] = gdf.geometry.make_valid()

    gdf = gdf.explode(index_parts=False, ignore_index=True)
    gdf = gdf[gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon"])]

    return gdf


def dissolve_dataset(gdf, dataset, i, precision=1.0):
    dataset_df = gdf[gdf["dataset"] == dataset].copy()
    dataset_df = clean_geometries(dataset_df, precision=precision)

    geom = unary_union(dataset_df.geometry.values)

    return gpd.GeoDataFrame(
        {f"dataset_{i}": [dataset], f"dest_id_{i}": [dataset],
         "geometry": [geom]},
        crs=gdf.crs
    )


def overlay_by_dataset(gs_polygons, datasets, precision=1.0):
    overlay_dfs = []

    for i, dataset in enumerate(datasets, start=1):
        dataset_df = dissolve_dataset(
            gs_polygons,
            dataset,
            i,
            precision=precision
        )

        if not dataset_df.empty and not dataset_df.geometry.iloc[0].is_empty:
            overlay_dfs.append(dataset_df)

    if not overlay_dfs:
        return gpd.GeoDataFrame(geometry=[], crs=gs_polygons.crs)

    if len(overlay_dfs) == 1:
        return overlay_dfs[0]

    greenspace = overlay_dfs[0]

    for next_gdf in overlay_dfs[1:]:
        for p in [precision, 10.0, 100.0]:
            try:
                greenspace = gpd.overlay(
                    clean_geometries(greenspace, precision=p),
                    clean_geometries(next_gdf, precision=p),
                    how="union",
                    keep_geom_type=True,
                    make_valid=True,
                )
                break
            except Exception as e:
                print(f"Overlay failed at precision={p}: {e}, retrying...")
        else:
            raise RuntimeError("Overlay failed at all precision levels")
    return greenspace


def overlay_by_dataset_tiled(gs_polygons, datasets, precision=1.0,
                             n_tiles=400, n_workers=6):
    bounds = gs_polygons.total_bounds
    minx, miny, maxx, maxy = bounds

    cols = int(np.sqrt(n_tiles))
    rows = int(np.ceil(n_tiles / cols))

    x_edges = np.linspace(minx, maxx, cols + 1)
    y_edges = np.linspace(miny, maxy, rows + 1)

    tiles = [
        box(x_edges[c], y_edges[r], x_edges[c + 1], y_edges[r + 1])
        for r in range(rows) for c in range(cols)
    ]

    fn = partial(process_tile, gs_polygons=gs_polygons,
                 datasets=datasets, precision=precision)

    print(f"Processing {len(tiles)} tiles with {n_workers} workers...")

    with Pool(n_workers) as pool:
        results = pool.map(fn, tiles)

    results = [r for r in results if r is not None and not r.empty]

    if not results:
        return gpd.GeoDataFrame(geometry=[], crs=gs_polygons.crs)

    return pd.concat(results, ignore_index=True)


def process_tile(tile_geom, gs_polygons, datasets, precision):
    import warnings
    warnings.filterwarnings('ignore', 'GeoSeries.notna', UserWarning)

    tile_gdf = gs_polygons[gs_polygons.intersects(tile_geom)].copy()
    if tile_gdf.empty:
        return None

    tile_gdf["geometry"] = tile_gdf.geometry.intersection(tile_geom)
    tile_gdf = tile_gdf[
        tile_gdf.geometry.notna() & ~tile_gdf.geometry.is_empty]

    if tile_gdf.empty:
        return None

    try:
        return overlay_by_dataset(tile_gdf, datasets, precision=precision)
    except Exception as e:
        print(f"Tile {tile_geom.bounds} failed entirely: {e}")
        return None


def diagnose_geometries(gs_polygons, datasets):
    for dataset in datasets:
        gdf = gs_polygons[gs_polygons["dataset"] == dataset].copy()

        print("\n", "=" * 60)
        print(dataset)
        print("=" * 60)

        print("rows:", len(gdf))
        print("CRS:", gdf.crs)

        print("\nGeometry types:")
        print(gdf.geometry.geom_type.value_counts(dropna=False))

        print("\nMissing geometries:", gdf.geometry.isna().sum())
        print("Empty geometries:", gdf.geometry.is_empty.sum())

        invalid = ~gdf.geometry.is_valid
        print("Invalid geometries:", invalid.sum())

        if invalid.any():
            print("\nInvalid reasons:")
            print(gdf.loc[invalid].geometry.is_valid_reason().value_counts().head(20))

            print("\nExample invalid rows:")
            print(gdf.loc[invalid, ["dataset", "dest_id", "geometry"]].head())


def main(assemble_greenspace: gpd.GeoDataFrame):
    # Strip trailing _england on designation names so downstream flag
    # columns are `has_sssi`, `has_sac`, `has_ramsar`, `has_spa`, `has_agi`
    # rather than the raw `has_sssi_england` etc. The whole dataset is
    # England-scale so the geographic scope suffix is redundant.
    assemble_greenspace = assemble_greenspace.copy()
    assemble_greenspace["dataset"] = (
        assemble_greenspace["dataset"].str.replace("_england", "", regex=False)
    )

    assemble_greenspace["dest_id"] = [
        f"gs_{i:04d}" for i in assemble_greenspace.index
    ]

    gs_polygons = (
        assemble_greenspace
        .drop_duplicates(subset=['dataset', 'dest_id'])
        [['dataset', 'dest_id', 'geometry']]
        .copy()
    )
    gs_polygons = gpd.GeoDataFrame(
        gs_polygons,
        geometry='geometry',
        crs=assemble_greenspace.crs
    )

    datasets = gs_polygons['dataset'].unique()

    diagnose_geometries(gs_polygons, datasets)

    greenspace = overlay_by_dataset_tiled(gs_polygons, datasets, n_workers=5)

    dataset_cols = [c for c in greenspace.columns if c.startswith('dataset')]

    # Dynamically flag whichever datasets are present
    for dataset in datasets:
        col = f"has_{dataset}"
        greenspace[col] = greenspace[dataset_cols].eq(dataset).any(axis=1)

    # Protected status — SSSI, SAC, Ramsar and SPA are all legally protected
    # designations under UK law. Only flag those that are present.
    protection_datasets = {'sssi', 'sac', 'ramsar', 'spa'}
    present_protection = protection_datasets & set(datasets)
    if present_protection:
        greenspace['is_protected'] = greenspace[
            [f"has_{d}" for d in present_protection]
        ].any(axis=1)
    else:
        greenspace['is_protected'] = False

    greenspace['designation_count'] = greenspace[
        [f"has_{d}" for d in datasets]
    ].sum(axis=1)

    greenspace["polygon_id"] = range(len(greenspace))
    cols = ["polygon_id"] + [c for c in greenspace.columns if c != "polygon_id"]
    greenspace = greenspace[cols]

    greenspace_surface = greenspace.dissolve()

    return greenspace_surface, greenspace


# ----------------------------------------------------------------------- Run -
if __name__ == '__main__':
    def debug_pause(msg): input(msg)  # inlined for public repo

    debug_pause("Paused. Press Enter to continue...")

    ox_assemble_greenspace = gpd.read_parquet(
        OX_ASSEMBLE_GREENSPACE
    )
    all_assemble_greenspace = gpd.read_parquet(
        ALL_ASSEMBLE_GREENSPACE
    )

    ox_greenspace_surface, ox_greenspace = (
        main(assemble_greenspace=ox_assemble_greenspace)
    )

    all_greenspace_surface, all_greenspace = (
        main(assemble_greenspace=all_assemble_greenspace)
    )

    filename = Path(str(__file__)).stem
    GET_GREENSPACE.mkdir(parents=True, exist_ok=True)

    ox_greenspace_surface.to_file(GET_GREENSPACE / f"ox_surface_{filename}.gpkg")
    ox_greenspace.to_file(GET_GREENSPACE / f"ox_{filename}.gpkg")
    # stripped for public repo:     ox_greenspace.to_csv(GET_VISAGE / 'ox_site_catalogue_polygons.csv')

    all_greenspace_surface.to_file(GET_GREENSPACE / f"all_surface_{filename}.gpkg")
    all_greenspace.to_file(GET_GREENSPACE / f"all_{filename}.gpkg")
    # stripped for public repo:     all_greenspace.to_csv(GET_VISAGE / 'all_site_catalogue_polygons.csv')
