"""
-------------------------------------------------------------------------------
Title: ""
Description: ""
Created: 16/02/2026
Author: tommycollins1 (trc207)
Notes:
    input:
    output:
-------------------------------------------------------------------------------
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Mapping

import geopandas as gpd
import pandas as pd
from geopandas import GeoDataFrame
from matplotlib import pyplot as plt
from pandas import DataFrame


def fix_geoms(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    gdf = gdf.copy()

    # Drop null geometries
    gdf = gdf[gdf.geometry.notna()]

    # Fix invalid geometries
    gdf["geometry"] = gdf.geometry.buffer(0)

    # Remove empties / still-invalid
    gdf = gdf[~gdf.geometry.is_empty]
    gdf = gdf[gdf.is_valid]

    return gdf


# def process_gs(
#     pr_site_path: Mapping[str, Path],
#     lad_details: Mapping[str, object],
#     fp_in: str | Path,
#     crs_out: str = "EPSG:27700",
# ) -> tuple[DataFrame | GeoDataFrame, DataFrame]:
#
#     gdf_list: list[gpd.GeoDataFrame] = []
#     failed_layers: list[tuple[str, str]] = []
#
#     for d_nm, d_path in pr_site_path.items():
#         print(f"Dataset: {d_nm}")
#
#         for lad_nm in lad_details.keys():
#             layer_name = f"{lad_nm}_{d_nm}"
#             print(f"  → {layer_name}")
#
#             try:
#                 gdf = gpd.read_file(fp_in)
#
#                 if gdf.empty:
#                     print(f"    ⚠️ Empty layer: {layer_name}")
#                     continue
#
#                 gdf = gdf.to_crs(crs_out)
#
#             except Exception as e:
#                 print(f"    ❌ Failed to load {layer_name}: {e}")
#                 failed_layers.append((layer_name, str(e)))
#                 continue
#
#             rep = gdf.geometry.representative_point()
#
#             gdf["representative_point_long"] = rep.x
#             gdf["representative_point_lat"] = rep.y
#
#             gdf_list.append(gdf)
#
#     poly_point_df = (
#         pd.concat(gdf_list, ignore_index=True)
#         if gdf_list
#         else gpd.GeoDataFrame(columns=[], geometry="geo_polys", crs=crs_out)
#     )
#     failed_df = pd.DataFrame(failed_layers, columns=["layer", "error"])
#
#     if not failed_df.empty:
#         print(f"\n⚠️ {len(failed_df)} layers failed.")
#
#     return poly_point_df, failed_df

def process_gs(
    fp_in: str | Path,
    dataset: str,
    crs_out: str = "EPSG:27700",
) -> gpd.GeoDataFrame:

    print(f"Reading {dataset}")

    gdf = gpd.read_file(fp_in)

    if gdf.empty:
        print(f"⚠️ Empty file: {dataset}")
        return gpd.GeoDataFrame(columns=[], geometry="geometry", crs=crs_out)

    gdf = gdf.to_crs(crs_out)

    # rep = gdf.geometry.representative_point()

    # gdf["dataset"] = dataset
    # gdf["representative_point_long"] = rep.x
    # gdf["representative_point_lat"] = rep.y

    return gdf


def run_process_gs(
        prot_fp_in: Path, gs_fp_in: Path,
        protected_sites_raw: Mapping[str, Path],
        agi_gi_raw: Mapping[str, Path],
        lad_details: Mapping[str, Path]) -> DataFrame:

    all_poly_point_list = []
    all_failed_list = []

    for fp_in, pr_site_path, tag in zip(
            [prot_fp_in, gs_fp_in],
            [protected_sites_raw, agi_gi_raw],
            ['protected_sites', 'accessible_gs']
    ):
        print(tag)

        poly_point_df, failed_df = process_gs(
            pr_site_path,
            lad_details,
            fp_in
        )
        all_poly_point_list.append(poly_point_df)
        all_failed_list.append(failed_df)


    all_poly_point_df = pd.concat(all_poly_point_list)
    all_failed_df = pd.concat(all_failed_list)

    print(f"   →  Failed \n \n {all_failed_df}")

    return all_poly_point_df


def plot_counters_by_regions(joined, regions_27700, region_col: str = "region"):

    regions_list = joined[region_col].dropna().unique()

    n = len(regions_list)
    ncols = 3
    nrows = math.ceil(n / ncols)

    fig, axes = plt.subplots(nrows, ncols, figsize=(15, 5 * nrows))
    axes = axes.flatten()

    for i, r in enumerate(regions_list):
        ax = axes[i]

        region_sudf = regions_27700[regions_27700['RGN21NM'] == r]
        joined_sudf = joined[joined[region_col] == r]

        # plot region boundary
        region_sudf.boundary.plot(ax=ax, linewidth=1, color='g')

        # matched counters
        joined_sudf.plot(ax=ax, markersize=10)

        # unmatched counters (optional)
        # unmatched.plot(ax=ax, color="red", markersize=10)

        ax.set_title(r)
        ax.axis("off")

    # remove empty panels
    for j in range(i + 1, len(axes)):
        fig.delaxes(axes[j])

    plt.tight_layout()
    plt.show()
