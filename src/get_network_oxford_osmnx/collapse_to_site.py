"""
-------------------------------------------------------------------------------
Title: collapse_to_site
Description: Collapse the per-access-point distances to one row per
    (origin_id, site_id) by keeping the shortest travel_time_s. dest_id is
    preserved on the kept row so you can still recover which access point
    won the min.

    Mirrors get_network_england_osrm/collapse_to_site.py. When
    LEGACY_DESTINATIONS = True the destinations lack a site_id column;
    this step becomes a no-op and returns the input unchanged (with a
    warning).
Created: 13/05/2026
Author: tommycollins1 (trc207)
Notes:
    input:  DISTANCES_FINAL parquet.
    output: DISTANCES_PER_SITE parquet.
-------------------------------------------------------------------------------
"""
from pathlib import Path

import pandas as pd

from src.get_network_oxford_osmnx.cfg import (
    DISTANCES_FINAL,
    DISTANCES_PER_SITE,
    LEGACY_DESTINATIONS,
    MODE,
)


def collapse_to_site(
    per_access_point_path: Path = DISTANCES_FINAL,
    out_path: Path = DISTANCES_PER_SITE,
) -> pd.DataFrame:
    df = pd.read_parquet(per_access_point_path)
    if df.empty:
        df.to_parquet(out_path, index=False)
        return df

    if "site_id" not in df.columns:
        if LEGACY_DESTINATIONS:
            print(
                "[collapse_to_site] LEGACY mode has no site_id -- skipping."
            )
        else:
            raise RuntimeError(
                "DISTANCES_FINAL has no 'site_id' column but not in "
                "LEGACY mode. Rerun compute_distances to ensure site_id "
                "is attached."
            )
        return df

    idx = df.groupby(["origin_id", "site_id"])["travel_time_s"].idxmin()
    collapsed = df.loc[idx].reset_index(drop=True)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    collapsed.to_parquet(out_path, index=False)
    print(
        f"[collapse_to_site] MODE={MODE}; per-site rows: {len(collapsed):,}; "
        f"wrote -> {out_path}"
    )
    return collapsed


if __name__ == "__main__":
    collapse_to_site()
