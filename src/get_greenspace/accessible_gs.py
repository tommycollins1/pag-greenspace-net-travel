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
from pathlib import Path

import geopandas as gpd

from main_config import AGI_GI
from src.get_geography.cfg import OX_LAD_2024_BUFF
from src.get_greenspace.cfg import GET_GREENSPACE


def main():
    all_ag_gdf = (gpd.read_file(AGI_GI)
                  .to_crs(27700)
                  .assign(dataset='agi'))

    all_ag_gdf = all_ag_gdf[['dataset', 'geometry']].copy()

    lad = gpd.read_file(OX_LAD_2024_BUFF)

    clipped = (gpd.clip(all_ag_gdf, lad)
               .copy()
               .assign(clip_area=lad['LAD24NM'][0]))

    return all_ag_gdf, clipped


zvbsdgb
# ----------------------------------------------------------------------- Run -
if __name__ == '__main__':
    def debug_pause(msg): input(msg)  # inlined for public repo

    debug_pause("Paused. Press Enter to continue...")

    all_ag_gdf, lad_ag_gdf = main()

    filename = Path(str(__file__)).stem
    GET_GREENSPACE.mkdir(parents=True, exist_ok=True)

    all_ag_gdf.to_file(GET_GREENSPACE / f"all_{filename}.gpkg")
    lad_ag_gdf.to_file(GET_GREENSPACE / f"ox_{filename}.gpkg")
