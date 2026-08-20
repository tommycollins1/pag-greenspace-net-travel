"""
-------------------------------------------------------------------------------
Title: load_deposit
Description: End-to-end example showing how to load the deposited GreenRoute
    parquet files, join them together, and compute a few common derived
    quantities. Uses the public deposit archive layout -- see:

        https://doi.org/10.5281/zenodo.22013904

    Assumes you have unzipped `greenroute_v1.0.zip` into a directory whose
    path is passed via the DEPOSIT_ROOT environment variable, or edit the
    constant below.

Usage:
    export DEPOSIT_ROOT=/path/to/greenroute_v1.0
    python examples/load_deposit.py

Author: tommycollins1 (trc207)
-------------------------------------------------------------------------------
"""
from __future__ import annotations

import os
from pathlib import Path

import geopandas as gpd
import pandas as pd


DEPOSIT_ROOT = Path(os.environ.get(
    "DEPOSIT_ROOT",
    Path.home() / "Downloads" / "greenroute_v1.0",
))


def _load(name: str, spatial: bool = False) -> pd.DataFrame:
    """Read a file from the deposit; use GeoPandas for spatial layers."""
    path = DEPOSIT_ROOT / name
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Set DEPOSIT_ROOT to the unzipped deposit folder."
        )
    return gpd.read_parquet(path) if spatial else pd.read_parquet(path)


def main() -> None:
    # ----- Per-site walking travel times -------------------------------------
    walk = _load("distances/walk/distances_per_site.parquet")
    drive = _load("distances/drive/distances_per_site.parquet")

    print(f"Walk reachable pairs: {len(walk):,}")
    print(f"Drive reachable pairs: {len(drive):,}")
    print(f"LSOAs with any walk-reachable greenspace: "
          f"{walk['origin_id'].nunique():,}")
    print(f"LSOAs with any drive-reachable greenspace: "
          f"{drive['origin_id'].nunique():,}")

    # ----- Reachability summary ---------------------------------------------
    origins = _load("origins/lsoa_centroids.parquet", spatial=True)
    n_total = len(origins)
    n_walk_reachable = walk["origin_id"].nunique()
    n_drive_reachable = drive["origin_id"].nunique()
    print(
        f"\nReachability at 20 minutes ({n_total:,} LSOAs total):\n"
        f"  walk : {n_walk_reachable:,} reachable "
        f"({(1 - n_walk_reachable / n_total) * 100:.1f}% unreached)\n"
        f"  drive: {n_drive_reachable:,} reachable "
        f"({(1 - n_drive_reachable / n_total) * 100:.1f}% unreached)"
    )

    # ----- Walk-drive gap per LSOA (min per mode) ----------------------------
    walk_min = walk.groupby("origin_id")["travel_time_s"].min().rename("walk_min_s")
    drive_min = drive.groupby("origin_id")["travel_time_s"].min().rename("drive_min_s")
    gap = pd.concat([walk_min, drive_min], axis=1, join="inner")
    gap["gap_min"] = (gap["walk_min_s"] - gap["drive_min_s"]) / 60
    print(
        f"\nMedian walk-drive gap per LSOA "
        f"({len(gap):,} dual-reachable LSOAs): "
        f"{gap['gap_min'].median():.1f} min"
    )

    # ----- Protected-site accessibility --------------------------------------
    protected = walk[walk["is_protected"]]
    n_lsoa_with_protected = protected["origin_id"].nunique()
    print(
        f"\nLSOAs within 20 min walk of a protected site "
        f"(SSSI/SAC/SPA/Ramsar): {n_lsoa_with_protected:,} "
        f"({n_lsoa_with_protected / n_total * 100:.1f}%)"
    )

    # ----- Mappable output ---------------------------------------------------
    # Merge nearest-walk-time onto the LSOA centroids for a quick choropleth.
    lsoa_walk_min = walk.groupby("origin_id")["travel_time_s"].min().reset_index()
    mappable = origins.merge(lsoa_walk_min, on="origin_id", how="left")
    print(f"\nMappable GeoDataFrame ready with {len(mappable):,} LSOAs; "
          f"columns: {list(mappable.columns)}")


if __name__ == "__main__":
    main()
