"""
-------------------------------------------------------------------------------
Title: ""
Description: ""
Created: 12/01/2026
Author: tommycollins1 (trc207)
Notes:
    input:
    output:
-------------------------------------------------------------------------------
"""
from pathlib import Path

import pandas as pd
import geopandas as gpd
from shapely.ops import unary_union

from main_config import (
    PROTECTED_SITES_DICT,
    UK_COUNTRIES_BFE_2023
)
from src.get_geography.cfg import OX_LAD_2024_BUFF
from src.get_greenspace.cfg import GET_GREENSPACE
from src.get_greenspace.greenspace_ftns import fix_geoms


def main():
    uk_land_buffer = gpd.read_file(UK_COUNTRIES_BFE_2023).to_crs(27700)
    uk_land_buffer = fix_geoms(uk_land_buffer)

    eng_land_buffer = uk_land_buffer[uk_land_buffer["CTRY23NM"] == "England"]
    mask = unary_union(eng_land_buffer.geometry)
    mask = mask.buffer(2000).buffer(0)

    protected_sites_list = []

    for d_nm, d_path in PROTECTED_SITES_DICT.items():
        print(d_nm)

        prot_land = gpd.read_file(d_path).to_crs(27700)
        prot_land = fix_geoms(prot_land)

        prot_clip = prot_land[prot_land.intersects(mask)].copy()

        prot_clip["geometry"] = prot_clip.geometry.intersection(mask)

        prot_clip = fix_geoms(prot_clip)

        prot_clip["dataset"] = d_nm

        protected_sites_list.append(prot_clip)

    protected_sites = pd.concat(protected_sites_list)

    protected_sites_gdf = gpd.GeoDataFrame(
        protected_sites[['NAME', 'dataset', 'geometry']]
        .reset_index(drop=True)
    )

    lad = gpd.read_file(OX_LAD_2024_BUFF)

    clipped = (gpd.clip(protected_sites_gdf, lad)
               .copy()
               .assign(clip_area=lad['LAD24NM'][0]))

    return eng_land_buffer, protected_sites_gdf, clipped


zvbsdgb
# ----------------------------------------------------------------------- Run -
if __name__ == '__main__':
    def debug_pause(msg): input(msg)  # inlined for public repo

    debug_pause("Paused. Press Enter to continue...")

    eng_land_buffer, all_ps_gdf, lad_ps_gdf = main()

    filename = Path(str(__file__)).stem
    GET_GREENSPACE.mkdir(parents=True, exist_ok=True)

    all_ps_gdf.to_file(GET_GREENSPACE / f"all_{filename}.gpkg")
    lad_ps_gdf.to_file(GET_GREENSPACE / f"ox_{filename}.gpkg")
    eng_land_buffer.to_file(GET_GREENSPACE / "eng_land.gpkg")
