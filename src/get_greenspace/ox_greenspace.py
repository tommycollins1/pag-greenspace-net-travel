"""
-------------------------------------------------------------------------------
Title: ""
Description: ""
Created: 28/01/2026
Author: tommycollins1 (trc207)
Notes:
    input:
    output:
-------------------------------------------------------------------------------
"""
from __future__ import annotations
from pathlib import Path
import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd

from main_config import ALL_AGI_GI, PROTECTED_SITES_DICT, LAD_SELECTIONS
from src.get_greenspace.cfg import OX_PROTECTED_SITES, \
    OX_AGI, GET_GREENSPACE, OX_ACCESS_POINTS
from src.get_greenspace.greenspace_ftns import process_gs


def main(
        prot_fp_in, gs_fp_in, protected_sites_raw, agi_gi_raw,
        lad_details
):
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

    return (
        all_poly_point_df[['dataset', 'representative_point_long',
                           'representative_point_lat', 'geometry']]
        .copy()
        .reset_index(drop=True))


sfgb

# ----------------------------------------------------------------------- Run -
if __name__ == '__main__':
    def debug_pause(msg): input(msg)  # inlined for public repo

    debug_pause("Paused. Press Enter to continue...")

    ox_poly_point_gdf = main(
        # select each (at start), copy and run all in console!
        prot_fp_in=OX_PROTECTED_SITES,
        gs_fp_in=OX_AGI,
        protected_sites_raw=ALL_AGI_GI,
        agi_gi_raw=ALL_PROTECTED_SITES,
        lad_details=LAD_SELECTIONS,
    )
    lad_clipped_gdf_out = gpd.read_file(OX_ACCESS_POINTS)

    ox_poly_point_gdf_buffer = ox_poly_point_gdf.copy()

    ox_poly_point_gdf_buffer['geometry'] = ox_poly_point_gdf_buffer.buffer(50)
    lad_clipped_gdf_out["polygon_geom"] = lad_clipped_gdf_out.geometry

    joined = ox_poly_point_gdf_buffer.sjoin(lad_clipped_gdf_out)

    ox_poly_point_gdf.nunique()
    ox_poly_point_gdf_buffer.nunique()
    joined.nunique()

    filename = Path(str(__file__)).stem
    GET_GREENSPACE.mkdir(parents=True, exist_ok=True)

    joined.to_parquet(GET_GREENSPACE / f"poly_point_{filename}.parquet")

    r_pts = gpd.GeoSeries(
        gpd.points_from_xy(
            ox_poly_point_gdf["representative_point_long"],
            ox_poly_point_gdf["representative_point_lat"]),
        crs=ox_poly_point_gdf.crs
    )
    a_pts = gpd.GeoSeries(
        joined["polygon_geom"],
        crs=ox_poly_point_gdf.crs
    )

    fig, ax = plt.subplots(figsize=(10, 10))

    ox_poly_point_gdf.plot(
        ax=ax,
        column="dataset",
        legend=True,
        linewidth=0.5
    )

    r_pts.plot(
        ax=ax,
        color="red",
        markersize=2
    )
    a_pts.plot(
        ax=ax,
        color="pink",
        markersize=2
    )

    ax.set_axis_off()
    plt.show()
