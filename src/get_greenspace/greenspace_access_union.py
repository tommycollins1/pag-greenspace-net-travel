"""
-------------------------------------------------------------------------------
Title: greenspace_access_union
Description: Join AGI access points to the decomposed union polygons produced
    by greenspace_union.py / eng_greenspace_union.py so each access point
    inherits the designation flags (has_agi, has_sssi, has_sac, is_protected,
    designation_count) of the unioned polygon unit it sits on.

    This is the destinations artefact for the get_network_england_osrm routing
    pipeline. Each row is one access point, with a stable access_pt_id and
    a site_id (= the decomposed union polygon_id). Multiple access points
    can share a site_id when one site has more than one entry on its
    boundary; downstream collapse-to-site logic uses that.

    Call via __main__ for the England pipeline (reads ALL_GREENSPACE_UNION,
    writes ALL_GREENSPACE_ACCESS_UNION). Call main() with explicit paths for the
    Oxford case-study pipeline (use OX_GREENSPACE_UNION + OX_GREENSPACE_ACCESS_UNION).

    Spatial join logic:
      - Filter union polygons to those containing AGI (has_agi == True),
        since access points are AGI-derived and would not attach to
        SSSI-only or SAC-only polygons.
      - sjoin_nearest on the access points; ties are broken by row order.
      - Optional sanity cap on max nearest-distance (default 50 m). Access
        points further than this from any AGI-containing polygon are
        dropped with a warning -- usually indicates a stray point or a
        coordinate-system bug upstream.
Created: 13/05/2026
Author: tommycollins1 (trc207)
Notes:
    input:  AGI_ACCESS_NODES_GI (raw access points), union_path
            (decomposed polygon units with designation flags).
    output: out_path parquet -- access_pt_id, site_id,
            has_agi, has_sssi, has_sac, is_protected, designation_count,
            geometry.
-------------------------------------------------------------------------------
"""
from pathlib import Path

import geopandas as gpd
from matplotlib import pyplot as plt

from main_config import AGI_ACCESS_NODES_GI
from src.get_greenspace.cfg import (
    ALL_GREENSPACE_UNION,
    GET_GREENSPACE,
    ALL_GREENSPACE_ACCESS_UNION,
    OX_GREENSPACE_ACCESS_UNION,
    OX_GREENSPACE_UNION,
)


# Access points further than this from any AGI-containing union polygon are
# dropped with a warning. Tolerance accounts for floating-point/round-trip
# mismatch between the access points and union polygon boundaries.
MAX_SNAP_DISTANCE_M = 50.0


def main(union_path: Path = ALL_GREENSPACE_UNION):
    access = gpd.read_file(AGI_ACCESS_NODES_GI).to_crs(27700)
    union = gpd.read_file(union_path).to_crs(27700)

    if "polygon_id" not in union.columns:
        raise RuntimeError(
            f"{union_path} has no 'polygon_id' column. Re-run "
            "greenspace_union.py (Oxford) or eng_greenspace_union.py (England) "
            "to regenerate with the polygon_id field."
        )

    # Derive designation columns dynamically from whatever datasets are present
    has_cols = [c for c in union.columns if c.startswith("has_")]

    agi_union = union[union["has_agi"]].copy()
    if agi_union.empty:
        raise RuntimeError(
            "No AGI-containing polygons in union file. Nothing to "
            "join access points to."
        )

    access = access.reset_index(drop=True).copy()
    access["access_pt_id"] = [f"ap_{i:07d}" for i in range(len(access))]

    keep_union_cols = (
        ["polygon_id"] + has_cols +
        ["is_protected", "designation_count", "geometry"]
    )
    agi_union = agi_union[keep_union_cols].rename(
        columns={"polygon_id": "site_id"}
    )

    joined = gpd.sjoin_nearest(
        access[["access_pt_id", "geometry"]],
        agi_union,
        how="left",
        max_distance=MAX_SNAP_DISTANCE_M,
        distance_col="snap_distance_m",
    )

    n_dropped = int(joined["site_id"].isna().sum())
    if n_dropped:
        print(
            f"WARNING: {n_dropped} access points further than "
            f"{MAX_SNAP_DISTANCE_M:.0f} m from any AGI-containing polygon "
            "-- these will be dropped."
        )
        joined = joined.dropna(subset=["site_id"])

    joined = (
        joined
        .sort_values(["access_pt_id", "snap_distance_m"])
        .drop_duplicates("access_pt_id", keep="first")
        .reset_index(drop=True)
    )

    out_cols = (
        ["access_pt_id", "site_id"] + has_cols +
        ["is_protected", "designation_count", "snap_distance_m", "geometry"]
    )
    result = gpd.GeoDataFrame(
        joined[out_cols], geometry="geometry", crs=27700
    )

    # Cast types
    result["site_id"] = result["site_id"].astype("int64")
    result["designation_count"] = result["designation_count"].astype("int32")
    for c in has_cols + ["is_protected"]:
        result[c] = result[c].astype("bool")

    return result

asfv
# ----------------------------------------------------------------------- Run -
if __name__ == '__main__':
    def debug_pause(msg): input(msg)  # inlined for public repo

    debug_pause("Paused. Press Enter to continue...")

    GET_GREENSPACE.mkdir(parents=True, exist_ok=True)

    for union_path, out_path in [
        (ALL_GREENSPACE_UNION, ALL_GREENSPACE_ACCESS_UNION),
        (OX_GREENSPACE_UNION,  OX_GREENSPACE_ACCESS_UNION),
    ]:
        print(f"\n--- {union_path.stem} -> {out_path.name} ---")

        access_union = main(union_path=union_path)

        access_union.to_parquet(out_path)
        access_union.to_csv(out_path.with_suffix(".csv"))

        print(f"Access points joined: {len(access_union):,}")
        print(f"Distinct sites:       {access_union['site_id'].nunique():,}")
        print(f"Wrote -> {out_path}")

        fig, ax = plt.subplots(figsize=(10, 10))
        access_union.plot(ax=ax, color="red", markersize=2)
        ax.set_axis_off()
        plt.show()

# import geopandas as gpd
# import matplotlib.pyplot as plt
# from src.get_greenspace.cfg import ALL_GREENSPACE_ACCESS_UNION
#
# gs = gpd.read_parquet(ALL_GREENSPACE_ACCESS_UNION)
#
# # Sanity: everything should have has_agi=True
# print(f"Total: {len(gs):,}")
# print(f"has_agi:    {gs['has_agi'].sum():,}")
# print(f"has_ramsar: {gs['has_ramsar'].sum():,}")
# print(f"has_sssi:   {gs['has_sssi'].sum():,}")
# print(f"has_sac:    {gs['has_sac'].sum():,}")
# print(f"has_spa:    {gs['has_spa'].sum():,}")
#
# fig, axes = plt.subplots(1, 3, figsize=(18, 6))
# gs.plot(ax=axes[0], color="grey", markersize=0.2, alpha=0.4)
# axes[0].set_title(f"All access points ({len(gs):,})")
#
# agi_only = gs[~gs["has_ramsar"] & ~gs["has_sssi"] & ~gs["has_sac"] & ~gs["has_spa"]]
# agi_only.plot(ax=axes[1], color="green", markersize=0.2, alpha=0.4)
# axes[1].set_title(f"AGI only ({len(agi_only):,})")
#
# ramsar = gs[gs["has_ramsar"]]
# ramsar.plot(ax=axes[2], color="blue", markersize=0.4, alpha=0.6)
# axes[2].set_title(f"AGI ∩ Ramsar ({len(ramsar):,})")
#
# for ax in axes:
#     ax.set_axis_off()
# plt.show()