"""
-------------------------------------------------------------------------------
Title: collapse_to_site
Description: Mirror of get_network_england/collapse_to_site.py but reading
    and writing the OSRM module's paths. Takes distances_final.parquet
    (per access point) and collapses to one row per (origin_id, site_id)
    by keeping the access point with the shortest travel_time_s.

    Why the duplicate file rather than reusing the existing module's
    function: paths differ (DISTANCES_FINAL vs OSRM module's
    DISTANCES_FINAL), and the existing module hard-codes its own cfg.
    Keeping a separate copy here keeps both modules self-contained.
Created: 13/05/2026
Author: tommycollins1 (trc207)
Notes:
    input:  DISTANCES_FINAL (per access point).
    output: DISTANCES_PER_SITE (per site).
-------------------------------------------------------------------------------
"""
from pathlib import Path

import pandas as pd

from src.data.get_network_england_osrm.cfg import (
    DISTANCES_FINAL,
    DISTANCES_PER_SITE,
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
        raise RuntimeError(
            "DISTANCES_FINAL has no 'site_id' column. Rerun "
            "compute_distances after confirming ALL_GREENSPACE_ACCESS_UNION "
            "carries site_id."
        )

    idx = df.groupby(["origin_id", "site_id"])["travel_time_s"].idxmin()
    collapsed = df.loc[idx].reset_index(drop=True)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    collapsed.to_parquet(out_path, index=False)
    print(
        f"MODE: {MODE}; per-site rows: {len(collapsed):,}; "
        f"wrote -> {out_path}"
    )
    return collapsed


if __name__ == "__main__":
    collapse_to_site()
