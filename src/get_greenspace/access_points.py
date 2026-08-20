"""
-------------------------------------------------------------------------------
Title: ""
Description: ""
Created: 05/03/2026
Author: tommycollins1 (trc207)
Notes:
    input:
    output:
-------------------------------------------------------------------------------
"""
from pathlib import Path

import geopandas as gpd
import pandas as pd
from matplotlib import pyplot as plt

from main_config import AGI_ACCESS_NODES_GI, LAD_SELECTIONS
from src.get_geography.cfg import OX_LAD_2024_BUFF
from src.get_greenspace.cfg import GET_GREENSPACE

sgb


def main():
    all_ag_access_gdf = (gpd.read_file(AGI_ACCESS_NODES_GI)
                         .to_crs(27700)
                         .assign(dataset='access points'))

    lad = gpd.read_file(OX_LAD_2024_BUFF)

    clipped = (gpd.clip(all_ag_access_gdf, lad)
               .copy()
               .assign(clip_area=lad['LAD24NM'][0]))

    return all_ag_access_gdf, clipped


# ----------------------------------------------------------------------- Run -
if __name__ == '__main__':
    def debug_pause(msg): input(msg)  # inlined for public repo

    debug_pause("Paused. Press Enter to continue...")

    all_ag_access_gdf_out, lad_clipped_gdf_out = main()

    filename = Path(str(__file__)).stem
    GET_GREENSPACE.mkdir(parents=True, exist_ok=True)

    all_ag_access_gdf_out.to_file(GET_GREENSPACE / f"all_{filename}.gpkg")
    lad_clipped_gdf_out.to_file(GET_GREENSPACE / f"ox_{filename}.gpkg")

    fig, ax = plt.subplots(figsize=(10, 10))

    lad_clipped_gdf_out.plot(
        ax=ax,
        color="red",
        markersize=2
    )

    ax.set_axis_off()
    plt.show()
