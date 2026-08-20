"""
-------------------------------------------------------------------------------
Title: ""
Description: ""
Created: 17/02/2026
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

from main_config import (
    ALL_AGI_GI,
    PROTECTED_SITES_DICT,
    LAD_SELECTIONS
)
from src.get_geography.cfg import OX_LAD_2024_BUFF
from src.get_greenspace.cfg import (
    ALL_PROTECTED_SITES,
    ALL_AGI, \
    GET_GREENSPACE
)
from src.get_greenspace.greenspace_ftns import process_gs


def main(prot_fp_in, gs_fp_in):

    protected_sites = process_gs(
        fp_in=prot_fp_in,
        dataset="protected_sites",
    )

    accessible_gs = process_gs(
        fp_in=gs_fp_in,
        dataset="accessible_gs",
    )

    all_poly_point_gdf = pd.concat(
        [protected_sites, accessible_gs],
        ignore_index=True,
    )

    lad = gpd.read_file(OX_LAD_2024_BUFF)

    clipped = (gpd.clip(all_poly_point_gdf, lad)
               .copy()
               .assign(clip_area=lad['LAD24NM'][0]))


    return all_poly_point_gdf[
        [
            "dataset",
            # "representative_point_long",
            # "representative_point_lat",
            "geometry",
        ]
    ].copy(), clipped


# def main(
#         prot_fp_in, gs_fp_in, protected_sites_raw, agi_gi_raw,
#         lad_details
# ):
#     all_poly_point_list = []
#     all_failed_list = []
#
#     for fp_in, pr_site_path in zip(
#             [prot_fp_in, gs_fp_in],
#             [protected_sites_raw, agi_gi_raw]
#     ):
#
#         poly_point_df, failed_df = process_gs(
#             pr_site_path,
#             lad_details,
#             fp_in
#         )
#         all_poly_point_list.append(poly_point_df)
#         all_failed_list.append(failed_df)
#
#
#     all_poly_point_df_2 = pd.concat(all_poly_point_list)
#     all_failed_df = pd.concat(all_failed_list)
#
#     print(f"   →  Failed \n \n {all_failed_df}")
#
#     return (
#         all_poly_point_df[['dataset', 'representative_point_long',
#                            'representative_point_lat', 'geometry']]
#         .copy()
#         .reset_index(drop=True))


sgb
# ----------------------------------------------------------------------- Run -
if __name__ == '__main__':
    def debug_pause(msg): input(msg)  # inlined for public repo

    debug_pause("Paused. Press Enter to continue...")

    all_assembled_gs, ox_assembled_gs = main(
        prot_fp_in=ALL_PROTECTED_SITES,
        gs_fp_in=ALL_AGI,
    )

    # all_poly_point_gdf = main(
    #     # note: select each, copy and run all in console!
    #     prot_fp_in=ALL_PROTECTED_SITES,
    #     gs_fp_in=ALL_AGI,
    #     protected_sites_raw=PROTECTED_SITES_DICT,  # todo wrong way round?
    #     agi_gi_raw=ALL_AGI_GI,
    #     lad_details=LAD_SELECTIONS,
    # )

    # ---------------------------------------------------------------- saving -
    filename = Path(str(__file__)).stem
    GET_GREENSPACE.mkdir(parents=True, exist_ok=True)

    all_assembled_gs.to_parquet(GET_GREENSPACE / f"all_{filename}.parquet")
    ox_assembled_gs.to_parquet(GET_GREENSPACE / f"ox_{filename}.parquet")

    # -------------------------------------------------------------- plotting -
    centre = all_assembled_gs.iloc[25].geometry
    test_area = centre.buffer(1000)

    subset = all_assembled_gs[all_assembled_gs.intersects(test_area)]

    pts = gpd.GeoSeries(
        gpd.points_from_xy(subset.geometry.representative_point().x,
                           subset.geometry.representative_point().y),
        crs=subset.crs
    )
    fig, ax = plt.subplots(figsize=(10, 10))

    subset.plot(
        ax=ax,
        column="dataset",
        legend=True,
        linewidth=0.5
    )

    pts.plot(
        ax=ax,
        color="red",
        markersize=2
    )

    ax.set_axis_off()
    plt.show()
