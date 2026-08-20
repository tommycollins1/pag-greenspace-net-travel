"""
-------------------------------------------------------------------------------
Title: ""
Description: ""
Created: 08/01/2026
Author: tommycollins1 (trc207)
Notes:
    input:
    output:
-------------------------------------------------------------------------------
"""
from pathlib import Path

import geopandas as gpd
from matplotlib import pyplot as plt

from main_config import LSOA_POP_WEIGHTED_CENTROIDS_2021
from src.get_geography.cfg import GET_GEOGRAPHY, OX_LAD_2024_BUFF


def main():
    lad = gpd.read_file(OX_LAD_2024_BUFF)

    lsoa_pw_centroids_gdf = gpd.read_file(
        LSOA_POP_WEIGHTED_CENTROIDS_2021
    )

    ls_cent_lad_gdf = gpd.sjoin(
        lsoa_pw_centroids_gdf, lad,
        how="inner", predicate="within"
    )

    lsoa_pw_centroids_gdf_c = (
        lsoa_pw_centroids_gdf[['LSOA21CD', 'geometry']]
        .copy()
        .reset_index(drop=True)
    )
    ls_cent_lad_gdf_c = (
        ls_cent_lad_gdf[['LSOA21CD', 'LAD24CD', 'LAD24NM',
                         'LONG', 'LAT', 'geometry',]]
        .copy()
        .reset_index(drop=True)
    )

    return lsoa_pw_centroids_gdf_c, ls_cent_lad_gdf_c
sgbs


# ----------------------------------------------------------------------- Run -
if __name__ == '__main__':
    def debug_pause(msg): input(msg)  # inlined for public repo

    debug_pause("Paused. Press Enter to continue...")

    lsoa_pw_centroids_gdf_o, ls_cent_lad_gdf_o = main()

    filename = Path(str(__file__)).stem
    GET_GEOGRAPHY.mkdir(parents=True, exist_ok=True)

    lsoa_pw_centroids_gdf_o.to_file(GET_GEOGRAPHY / f"all_{filename}.gpkg")
    ls_cent_lad_gdf_o.to_file(GET_GEOGRAPHY / f"oxford_{filename}.gpkg")

    for df in [lsoa_pw_centroids_gdf_o, ls_cent_lad_gdf_o]:
        print(0)
        fig, ax = plt.subplots(figsize=(10, 10))

        df.plot(
            ax=ax,
            color="red",
            markersize=2
        )

        ax.set_axis_off()
        plt.show()
