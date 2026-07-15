"""
-------------------------------------------------------------------------------
Title: compute_distances
Description: End-to-end OSRM routing pipeline. No tiling.

      1. Load origins (LSOA pop-weighted centroids) and destinations
         (greenspace access points) via get_network_england_osrm.loaders.
      2. For each origin, find candidate destinations within
         PROFILE['candidate_radius_m'] via a spatial index.
      3. Batch /table queries to OSRM, 1 source x <=99 destinations per call.
      4. Filter to travel_time_s <= PROFILE['threshold_s'].
      5. Attach site_id + designation flags from the destinations gdf.
      6. Write distances_final.parquet.

    The candidate radius is a generous Euclidean upper bound, not a soft
    filter -- it must be larger than threshold_s * peak_network_speed.
    For drive that means peak motorway speeds; 30 km comfortably covers
    a 20-min drive at any plausible UK speed.
Created: 13/05/2026
Author: tommycollins1 (trc207)
Notes:
    input:  ALL_GREENSPACE_ACCESS_UNION parquet, LSOA pop-weighted centroids,
            a running OSRM server at OSRM_URL.
    output: DISTANCES_FINAL parquet (per access point).
-------------------------------------------------------------------------------
"""
from __future__ import annotations

import time

import geopandas as gpd
import pandas as pd
from tqdm import tqdm

from src.data.get_network_england_osrm.loaders import (
    load_destinations,
    load_origins,
)
from src.data.get_network_england_osrm.cfg import (
    BNG_EPSG,
    DESTINATIONS_CACHE,
    DISTANCES_FINAL,
    GET_NETWORK_ENGLAND_OSRM,
    MODE,
    ORIGINS_CACHE,
    PROFILE,
    WGS84_EPSG,
)
from src.data.get_network_england_osrm.osrm_client import one_to_many, ping


def _to_lonlat(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Project to WGS84 lon/lat for OSRM submission."""
    if gdf.crs is None:
        raise ValueError("GeoDataFrame has no CRS; can't reproject.")
    if gdf.crs.to_epsg() == WGS84_EPSG:
        return gdf.copy()
    return gdf.to_crs(WGS84_EPSG)


def compute_distances() -> pd.DataFrame:
    """Run the full OSRM pipeline for the active MODE.

    Returns the merged DataFrame. Also writes DISTANCES_FINAL.
    """
    print(f"=== get_network_england_osrm | MODE = {MODE} ===")
    print(f"Threshold: {PROFILE['threshold_s'] / 60:.1f} min")
    print(f"Candidate radius: {PROFILE['candidate_radius_m'] / 1000:.1f} km")

    if not ping():
        raise RuntimeError(
            "OSRM server not reachable. Start the matching server "
            f"(profile={PROFILE['osrm_profile']}, "
            f"port={PROFILE['osrm_port']}) before running this pipeline. "
            "See README.md for the Docker incantation."
        )

    GET_NETWORK_ENGLAND_OSRM.mkdir(parents=True, exist_ok=True)

    # ---- Origins + destinations ------------------------------------------
    # BNG geometry for spatial filtering (metric), then convert to lon/lat
    # for OSRM submission separately.
    origins_bng = load_origins().to_crs(BNG_EPSG)
    destinations_bng = load_destinations().to_crs(BNG_EPSG)

    print(f"Origins: {len(origins_bng):,}")
    print(f"Destinations: {len(destinations_bng):,}")

    origins_bng.to_parquet(ORIGINS_CACHE)
    destinations_bng.to_parquet(DESTINATIONS_CACHE)

    # Pre-compute lon/lat once so the inner loop doesn't reproject per call.
    destinations_ll = _to_lonlat(destinations_bng)
    destinations_ll["lon"] = destinations_ll.geometry.x
    destinations_ll["lat"] = destinations_ll.geometry.y

    origins_ll = _to_lonlat(origins_bng)
    origins_ll["lon"] = origins_ll.geometry.x
    origins_ll["lat"] = origins_ll.geometry.y

    # Spatial index on destinations (in BNG metric space) for the radius
    # filter.
    dest_sindex = destinations_bng.sindex
    candidate_radius_m = PROFILE["candidate_radius_m"]
    threshold_s = PROFILE["threshold_s"]

    # ---- Loop: one OSRM call set per origin ------------------------------
    all_rows = []
    started = time.time()

    for o_row in tqdm(
        origins_bng.itertuples(index=False),
        total=len(origins_bng),
        desc=f"origins ({MODE})",
    ):
        o_pt = o_row.geometry
        # Bounding-box pre-filter, then exact radius check.
        bbox = o_pt.buffer(candidate_radius_m).bounds
        cand_idx = list(dest_sindex.intersection(bbox))
        if not cand_idx:
            continue
        cand = destinations_bng.iloc[cand_idx]
        mask = cand.distance(o_pt) <= candidate_radius_m
        cand = cand[mask]
        if cand.empty:
            continue

        # Look up lon/lat in destinations_ll using the cand index.
        cand_ll = destinations_ll.iloc[cand.index]
        dest_lonlats = list(zip(cand_ll["lon"], cand_ll["lat"]))
        dest_ids = cand_ll["dest_id"].astype(str).tolist()

        # Find this origin's lon/lat (same row index).
        o_ll = origins_ll.iloc[origins_bng.index.get_loc(o_row.Index)] \
            if hasattr(o_row, "Index") else None
        # itertuples without index=True drops .Index, so look up by origin_id:
        o_match = origins_ll[origins_ll["origin_id"] == o_row.origin_id]
        o_lon, o_lat = float(o_match.iloc[0]["lon"]), float(
            o_match.iloc[0]["lat"]
        )

        routes = one_to_many((o_lon, o_lat), dest_lonlats, dest_ids)
        if routes.empty:
            continue

        routes = routes[routes["travel_time_s"] <= threshold_s].copy()
        if routes.empty:
            continue

        routes["origin_id"] = o_row.origin_id
        all_rows.append(routes)

    elapsed = time.time() - started
    print(f"Routing finished in {elapsed:.1f} s.")

    if not all_rows:
        empty = pd.DataFrame(
            columns=[
                "origin_id", "dest_id", "site_id", "travel_time_s",
                "dist_m", "mode", "has_agi", "has_sssi", "has_sac",
                "is_protected", "designation_count",
                "origin_snap_m", "dest_snap_m",
            ]
        )
        empty.to_parquet(DISTANCES_FINAL, index=False)
        return empty

    df = pd.concat(all_rows, ignore_index=True)

    # Attach destination metadata (site_id, flags). Use destinations_bng
    # because it carries the project's typed columns.
    meta_cols = [c for c in (
        "site_id", "has_agi", "has_sssi", "has_sac",
        "is_protected", "designation_count",
    ) if c in destinations_bng.columns]
    if meta_cols:
        meta = (
            destinations_bng[["dest_id", *meta_cols]]
            .drop_duplicates("dest_id")
        )
        df = df.merge(meta, on="dest_id", how="left")

    df["mode"] = MODE
    df["travel_time_s"] = df["travel_time_s"].astype("float32")
    df["dist_m"] = df["dist_m"].astype("float32")
    df["origin_snap_m"] = df["origin_snap_m"].astype("float32")
    df["dest_snap_m"] = df["dest_snap_m"].astype("float32")

    preferred = [
        "origin_id", "dest_id", "site_id", "travel_time_s", "dist_m",
        "mode",
        "has_agi", "has_sssi", "has_sac",
        "is_protected", "designation_count",
        "origin_snap_m", "dest_snap_m",
    ]
    cols = [c for c in preferred if c in df.columns]
    df = df[cols]

    df.to_parquet(DISTANCES_FINAL, index=False)
    print(f"Wrote {len(df):,} rows -> {DISTANCES_FINAL}")
    return df
