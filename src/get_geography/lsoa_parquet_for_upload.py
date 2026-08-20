"""
-------------------------------------------------------------------------------
Title: ""
Description: ""
Created: 06/05/2026
Author: tommycollins1 (trc207)
Notes:
    input:
    output:
-------------------------------------------------------------------------------
"""
import os
from pathlib import Path

import geopandas as gpd
from shapely.wkt import loads, dumps
from shapely.validation import make_valid, explain_validity
from shapely.geometry import Polygon, MultiPolygon
from matplotlib import pyplot as plt

from main_config import LSOA_POLYS_2024
from src.get_geography.cfg import GET_GEOGRAPHY


def fix_geometry(geom):
    try:
        g = make_valid(geom)
        g = g.buffer(0)
        g = loads(dumps(g, rounding_precision=6))
        g = make_valid(g)
        if not isinstance(g, (Polygon, MultiPolygon)):
            return None
        return g
    except Exception:
        return None


def main():
    lsoa_polys = gpd.read_file(
        LSOA_POLYS_2024,
    )
    lsoa_england = lsoa_polys[
        lsoa_polys["LSOA21CD"].str.startswith("E")
    ].copy()

    lsoa_england["geometry"] = lsoa_england.geometry.simplify(
        tolerance=1,
        preserve_topology=True
    )

    lsoa_4326 = lsoa_england.to_crs(4326).copy()

    lsoa_4326["geometry"] = lsoa_4326["geometry"].apply(fix_geometry)

    lsoa_4326 = lsoa_4326[lsoa_4326["geometry"].notna()].copy()
    lsoa_4326 = lsoa_4326[~lsoa_4326["geometry"].is_empty].copy()

    lsoa_4326 = lsoa_4326[
        lsoa_4326["geometry"].apply(
            lambda g: isinstance(g, (Polygon, MultiPolygon)) and not g.is_empty
        )
    ].copy()

    problems = lsoa_4326["geometry"].apply(explain_validity)

    print(f"Still invalid: {(problems != 'Valid Geometry').sum()}")
    print(f"Rows remaining: {len(lsoa_4326)}")

    lsoa_4326["geometry_wkt"] = lsoa_4326["geometry"].apply(
        lambda g: dumps(g, rounding_precision=6)
    )

    df_upload = lsoa_4326[["LSOA21CD", "geometry_wkt"]].copy()

    return df_upload, lsoa_polys, lsoa_4326


adfb
# ----------------------------------------------------------------------- Run -
if __name__ == '__main__':
    def debug_pause(msg): input(msg)  # inlined for public repo

    debug_pause("Paused. Press Enter to continue...")

    df_upload, lsoa_polys, lsoa_4326 = main()

    filename = Path(str(__file__)).stem
    GET_GEOGRAPHY.mkdir(parents=True, exist_ok=True)
    df_upload.to_parquet(GET_GEOGRAPHY / f"{filename}.parquet", index=False)


    size_mb = (os.path.getsize(GET_GEOGRAPHY / f"{filename}.parquet") /
               1_000_000)
    print(f"File size: {size_mb:.1f} MB")

    test_lsoa = "E01000001"  # example for testing

    original = lsoa_polys[lsoa_polys["LSOA21CD"] == test_lsoa].to_crs(4326)
    simplified = lsoa_4326[lsoa_4326["LSOA21CD"] == test_lsoa]

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    original.plot(ax=axes[0])
    axes[0].set_title("Original")
    simplified.plot(ax=axes[1])
    axes[1].set_title("Simplified (1m tolerance)")
    plt.show()
