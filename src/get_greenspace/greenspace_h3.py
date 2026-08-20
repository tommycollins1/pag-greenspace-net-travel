"""
-------------------------------------------------------------------------------
Title: ""
Description: ""
Created: 18/03/2026
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

from main_config import LAD_SELECTIONS, FIGURES
from src.get_geography.cfg import LAD_BFC_2024_BUFF
from src.get_greenspace.cfg import OX_GREENSPACE_UNION, GET_GREENSPACE
from src.visualization.empirical_analysis.emp_ftns import (
    save_fig,
    get_total_bounds_3857, generate_h3_grid_from_polygon,
    aggregate_greenspace_to_h3, plot_h3_greenspace_prop, plot_h3_protected,
    plot_h3_designation_count, plot_h3_greenspace_binary,
)


def main(out_dir):
    print("\n--- Greenspace H3 summary ---")
    print(
        greenspace_h3[
            ["greenspace_area_m2", "cell_area_m2", "greenspace_prop"]
        ].describe()
    )

    print("\n--- Boolean designation counts ---")
    print(greenspace_h3[["has_agi", "has_sssi", "has_sac", "is_protected"]].sum())

    print("\n--- Designation count frequencies ---")
    print(greenspace_h3["designation_count"].value_counts().sort_index())

    print("\n--- Greenspace binary ---")
    print(greenspace_h3["greenspace_binary"].value_counts())

    print("\n--- Max greenspace proportion ---")
    print(greenspace_h3["greenspace_prop"].max())

    print("\n--- SSSI vs SAC ---")
    print(pd.crosstab(greenspace_h3["has_sssi"], greenspace_h3["has_sac"]))

    bounds = get_total_bounds_3857(greenspace_h3)

    plot_jobs = [
        ("01_h3_greenspace_prop", plot_h3_greenspace_prop, (greenspace_h3,)),
        ("02_h3_protected", plot_h3_protected, (greenspace_h3,)),
        ("03_h3_designation_count", plot_h3_designation_count, (greenspace_h3,)),
        ("04_h3_greenspace_binary", plot_h3_greenspace_binary, (greenspace_h3,)),
    ]

    for name, func, args in plot_jobs:
        fig, ax = func(*args, bounds=bounds)
        save_fig(fig, name, out_dir, prefix=filename)
        plt.close(fig)

    # Optional histogram in the same style
    fig, ax = plt.subplots(figsize=(7, 4))
    greenspace_h3["greenspace_prop"].hist(ax=ax, bins=40)
    ax.set_title("Distribution of greenspace proportion")
    ax.set_xlabel("Greenspace proportion")
    ax.set_ylabel("Frequency")
    fig.tight_layout()
    save_fig(fig, "05_h3_greenspace_prop_hist", out_dir)
    plt.close(fig)

    return greenspace_h3

assfddv
# ----------------------------------------------------------------------- Run -
if __name__ == '__main__':
    def debug_pause(msg): input(msg)  # inlined for public repo

    debug_pause("Paused. Press Enter to continue...")

    greenspace_union = gpd.read_file(OX_GREENSPACE_UNION)
    eng_land = gpd.read_file(ENGLAND_BUFFER)

    lad_nm, lad_cds = next(iter(LAD_SELECTIONS.items()))
    lads = gpd.read_file(LAD_BFC_2024_BUFF)
    lad = lads[lads["LAD24CD"].isin(lad_cds)].copy()

    filename = Path(str(__file__)).stem
    OUT_DIR = Path(FIGURES) / "empirical_analysis"
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    h3_oxford = generate_h3_grid_from_polygon(polygon_gdf=lad, resolution=8)
    h3_eng_land = generate_h3_grid_from_polygon(polygon_gdf=eng_land, resolution=8)

    h3_oxford.to_file(GET_GREENSPACE / "h3_oxford.gpkg")
    h3_eng_land.to_file(GET_GREENSPACE / "h3_eng_land.gpkg")

    h3_eng_land['geometry_wkt'] = h3_eng_land['geometry'].apply(lambda g: g.wkt)

    (h3_eng_land[['h3', 'geometry_wkt']]
     .to_parquet(GET_GREENSPACE / "h3_eng_land.parquet"))

    greenspace_h3 = aggregate_greenspace_to_h3(
        h3_gdf=h3_oxford,
        greenspace=greenspace_union
    )

    main(OUT_DIR)
