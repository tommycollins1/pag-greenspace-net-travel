"""
-------------------------------------------------------------------------------
Title: ""
Description: ""
Created: 11/03/2026
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

from main_config import LAD_BFC_2024, LAD_SELECTIONS, COUNTIES_2021
from src.get_geography.cfg import GET_GEOGRAPHY


def main():
    lads_original = gpd.read_file(LAD_BFC_2024)
    lads = lads_original.copy()

    _, lad_cds = next(iter(LAD_SELECTIONS.items()))

    original_gdf = lads_original[lads_original["LAD24CD"].isin(lad_cds)].copy()
    buffered_gdf = (
        lads[lads["LAD24CD"].isin(lad_cds)]
        .copy()
        .assign(geometry=lambda df: df.buffer(16093))
    )

    counties = gpd.read_file(COUNTIES_2021).to_crs(lads.crs)

    intersecting_counties = gpd.sjoin(
        counties[["CTYUA21NM", "CTYUA21CD", "geometry"]],
        buffered_gdf[["geometry", "LAD24CD"]],
        predicate="intersects",
        how="inner"
    ).drop(columns=["index_right"])

    print(intersecting_counties[["CTYUA21NM", "CTYUA21CD"]])

    county_list = (
        intersecting_counties
        .groupby("LAD24CD")["CTYUA21NM"]
        .apply(list)
        .reset_index()
        .rename(columns={"CTYUA21NM": "intersecting_counties"})
    )

    buffered_gdf = buffered_gdf.merge(county_list, on="LAD24CD", how="left")

    return lads, original_gdf, buffered_gdf

sgnsrgn
# ----------------------------------------------------------------------- Run -
if __name__ == '__main__':
    def debug_pause(msg): input(msg)  # inlined for public repo

    debug_pause("Paused. Press Enter to continue...")

    lads, original_gdf, buffered_gdf = main()

    filename = Path(str(__file__)).stem
    GET_GEOGRAPHY.mkdir(parents=True, exist_ok=True)

    original_gdf.to_file(GET_GEOGRAPHY / f"ox_{filename}_original.gpkg")
    buffered_gdf.to_file(GET_GEOGRAPHY / f"ox_{filename}.gpkg")

    buffered_gdf_4326 = buffered_gdf.to_crs(4326).copy()
    buffered_gdf_4326["geometry_wkt"] = buffered_gdf_4326.geometry.to_wkt()

    df_upload = pd.DataFrame(buffered_gdf_4326.drop(columns="geometry"))
    df_upload.to_parquet(GET_GEOGRAPHY / f"ox_{filename}.parquet")

    fig, ax = plt.subplots(figsize=(10, 10))

    buffered_gdf.plot(ax=ax, color='red', alpha=0.2, edgecolor='red',
                      label='10 mile buffer')
    original_gdf.plot(ax=ax, color='blue', alpha=0.5, edgecolor='blue',
                      label='Oxford')

    # Label using LAD24NM
    for idx, row in original_gdf.iterrows():
        ax.annotate(row['LAD24NM'],
                    xy=(row.geometry.centroid.x, row.geometry.centroid.y),
                    ha='center', fontsize=10, fontweight='bold', color='blue')

    ax.legend()
    ax.set_title('Oxford LAD with 10 Mile Buffer')
    plt.show()
