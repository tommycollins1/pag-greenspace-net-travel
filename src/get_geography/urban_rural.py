"""
-------------------------------------------------------------------------------
Title: ""
Description: ""
Created: 26/05/2026
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

from main_config import URBAN_RURAL_CLASS_2021, LSOA_POLYS_2024
from src.get_geography.cfg import OX_LAD_2024_BUFF, GET_GEOGRAPHY


# todo: add england
def main():
    lsoas = gpd.read_file(LSOA_POLYS_2024)
    urban_rural_2021 = pd.read_csv(URBAN_RURAL_CLASS_2021)
    lad = gpd.read_file(OX_LAD_2024_BUFF)

    gdf = lsoas[['LSOA21CD', 'LSOA21NM', 'geometry']].merge(
        urban_rural_2021[['LSOA21CD', 'LSOA21NM', 'Urban_rura']],
        how='left', on=['LSOA21CD', 'LSOA21NM']
    )
    ox_class = gpd.clip(gdf, lad)

    return ox_class, gdf


fghm
# ----------------------------------------------------------------------- Run -
if __name__ == '__main__':
    def debug_pause(msg): input(msg)  # inlined for public repo

    debug_pause("Paused. Press Enter to continue...")

    ox_class, all_class = main()

    filename = Path(str(__file__)).stem
    GET_GEOGRAPHY.mkdir(parents=True, exist_ok=True)

    ox_class.to_file(GET_GEOGRAPHY / f"ox_{filename}.gpkg")
    all_class.to_parquet(GET_GEOGRAPHY / f"all_{filename}.parquet")

    ox_class.plot('Urban_rura')
    plt.show()
