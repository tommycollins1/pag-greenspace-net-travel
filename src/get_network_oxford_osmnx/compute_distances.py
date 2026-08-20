"""
-------------------------------------------------------------------------------
Title: compute_distances
Description: End-to-end pipeline. Steps:

      1. Load or build the projected OSM graph for the active mode.
      2. Load origins (LSOA pop-weighted centroids) clipped to LAD_SELECTIONS.
      3. Load destinations: OX_GREENSPACE_ACCESS_UNION by default, or
         OX_ASSEMBLE_GREENSPACE when LEGACY_DESTINATIONS is set.
      4. Snap both to graph nodes (records snap distances).
      5. For each destination batch (CHECKPOINT_EVERY per batch), run
         Dijkstra with the mode-appropriate weight in parallel; write
         per-batch parquets; update progress CSV.
      6. Concat batch parquets into distances_final.parquet.

    Resumable: on rerun, dests already in progress.csv are skipped and
    only remaining batches are processed.
Created: 13/05/2026
Author: tommycollins1 (trc207)
Notes:
    input:  graph cache, origins, destinations, mode profile.
    output: DISTANCES_FINAL parquet.
-------------------------------------------------------------------------------
"""
from __future__ import annotations

import geopandas as gpd
import pandas as pd
from joblib import Parallel, delayed
from tqdm import tqdm

from main_config import LSOA_POP_WEIGHTED_CENTROIDS_2021
from src.get_geography.cfg import LAD_BFC_2024_BUFF
from src.get_greenspace.cfg import (
    OX_ASSEMBLE_GREENSPACE,
    OX_GREENSPACE_ACCESS_UNION, ALL_GREENSPACE_ACCESS_UNION,
)
from src.get_network_oxford_osmnx.cfg import (
    BATCHES_DIR,
    BNG_EPSG,
    CHECKPOINT_EVERY,
    DESTINATIONS_CACHE,
    DISTANCES_FINAL,
    GET_NETWORK_OXFORD_OSMNX,
    LAD_SELECTIONS,
    LEGACY_DESTINATIONS,
    MODE,
    N_JOBS,
    ORIGINS_CACHE,
    PROFILE,
    PROGRESS_FILE,
)
from src.get_network_oxford_osmnx.graph import load_or_fetch_graph
from src.get_network_oxford_osmnx.routing import (
    append_processed_ids,
    load_processed_ids,
    process_destination,
    save_parquet_batch,
)
from src.get_network_oxford_osmnx.snap import snap_points


# --------------------------------------------------------- INPUT LOADERS -

def _study_area_clip() -> gpd.GeoDataFrame:
    lads = gpd.read_file(LAD_BFC_2024_BUFF).to_crs(BNG_EPSG)
    codes = [cd for cds in LAD_SELECTIONS.values() for cd in cds]
    sel = lads[lads["LAD24CD"].isin(codes)].copy()
    if sel.empty:
        raise RuntimeError(
            f"Study-area LADs not found: {codes}. Update LAD_SELECTIONS."
        )
    return sel.dissolve()


def load_origins() -> gpd.GeoDataFrame:
    """LSOA 2021 population-weighted centroids clipped to LAD_SELECTIONS."""
    centroids = gpd.read_file(
        LSOA_POP_WEIGHTED_CENTROIDS_2021
    ).to_crs(BNG_EPSG)
    centroids = centroids[["LSOA21CD", "geometry"]].rename(
        columns={"LSOA21CD": "origin_id"}
    )
    clipped = gpd.clip(centroids, _study_area_clip())
    return clipped.reset_index(drop=True)


def load_destinations() -> gpd.GeoDataFrame:
    """Load destinations per LEGACY_DESTINATIONS toggle.

    Default: OX_GREENSPACE_ACCESS_UNION (access points with designation
    flags). dest_id = access_pt_id.

    Legacy: OX_ASSEMBLE_GREENSPACE (pre-union polygon points), dest_id
    generated from the row index; park_dataset / park_class carried
    forward for schema parity with the historical get_network/ outputs.
    """
    if LEGACY_DESTINATIONS:
        gs = gpd.read_parquet(OX_ASSEMBLE_GREENSPACE).to_crs(BNG_EPSG)
        # Use existing polygon_geom if present, else the row geometry
        if "polygon_geom" in gs.columns:
            gs["geometry"] = gs["polygon_geom"]
        gs = gs.reset_index(drop=True)
        gs["dest_id"] = [f"gs_{i:07d}" for i in range(len(gs))]
        keep = ["dest_id", "geometry"]
        for c in ("park_dataset", "park_class", "dataset"):
            if c in gs.columns:
                keep.append(c)
        # Fold `dataset` into park_dataset for consistency.
        if "dataset" in gs.columns and "park_dataset" not in gs.columns:
            gs["park_dataset"] = gs["dataset"]
            keep = [c for c in keep if c != "dataset"]
            keep.append("park_dataset")
        clip = _study_area_clip()
        gs = gpd.clip(gs[keep], clip)
        return gs.reset_index(drop=True)

    access = gpd.read_parquet(ALL_GREENSPACE_ACCESS_UNION).to_crs(BNG_EPSG) # <- changed to load all the data and subset later
    access = access.rename(columns={"access_pt_id": "dest_id"})
    # Discover designation flag columns dynamically so any upstream additions
    # (Ramsar, SPA, etc.) propagate through without a code change here.
    has_cols = [c for c in access.columns if c.startswith("has_")]
    keep = [c for c in (
        ["dest_id", "site_id"]
        + has_cols
        + ["is_protected", "designation_count", "geometry"]
    ) if c in access.columns]
    if "geometry" not in keep:
        keep.append("geometry")
    clip = _study_area_clip()
    access = gpd.clip(access[keep], clip)
    return access.reset_index(drop=True)


# ------------------------------------------------------------ MAIN PIPELINE -

def compute_distances(n_jobs: int = N_JOBS) -> pd.DataFrame:
    """Run the full osmnx pipeline for the active MODE.

    Idempotent + resumable: reuses the cached graph and skips destinations
    recorded in the progress CSV.
    """
    print(f"=== get_network_oxford_osmnx | MODE = {MODE} ===")
    print(f"Threshold: {PROFILE['threshold_s'] / 60:.1f} min")
    print(f"Weight: {PROFILE['weight']}; legacy = {LEGACY_DESTINATIONS}")

    GET_NETWORK_OXFORD_OSMNX.mkdir(parents=True, exist_ok=True)
    BATCHES_DIR.mkdir(parents=True, exist_ok=True)

    # ---- Graph -----------------------------------------------------------
    G = load_or_fetch_graph()

    # ---- Origins + destinations ------------------------------------------
    origins = load_origins()
    destinations = load_destinations()

    origins.to_parquet(ORIGINS_CACHE)
    destinations.to_parquet(DESTINATIONS_CACHE)
    print(f"Origins: {len(origins):,}; destinations: {len(destinations):,}")

    # ---- Snap to network -------------------------------------------------
    origin_nodes = snap_points(origins, G, "origin_id")
    dest_nodes = snap_points(destinations, G, "dest_id")

    # Carry destination metadata across so process_destination has it.
    dest_meta_cols = [c for c in destinations.columns if c not in ("geometry",)]
    dest_nodes = dest_nodes.merge(
        destinations[dest_meta_cols],
        on="dest_id",
        how="left",
        suffixes=("", "_meta"),
    )

    # ---- Loop batches with checkpointing --------------------------------
    completed = load_processed_ids(PROGRESS_FILE)
    remaining = dest_nodes[~dest_nodes["dest_id"].isin(completed)].copy()
    print(f"Dests to process: {len(remaining)} "
          f"(skipping {len(completed)} already done)")

    dest_items = remaining.to_dict(orient="records")
    for start in range(0, len(dest_items), CHECKPOINT_EVERY):
        batch = dest_items[start: start + CHECKPOINT_EVERY]
        batch_id = start // CHECKPOINT_EVERY

        batch_dfs = Parallel(n_jobs=n_jobs, backend="loky")(
            delayed(process_destination)(dr, origin_nodes, G)
            for dr in tqdm(
                batch,
                total=len(batch),
                desc=f"batch {batch_id + 1}",
            )
        )

        save_parquet_batch(batch_dfs, BATCHES_DIR, batch_id)
        append_processed_ids(
            PROGRESS_FILE, [dr["dest_id"] for dr in batch]
        )

    # ---- Concat batches into final parquet ------------------------------
    batch_files = sorted(BATCHES_DIR.glob("batch_*.parquet"))
    if not batch_files:
        empty_cols = [
            "origin_id", "dest_id", "travel_time_s", "dist_m", "mode",
            "origin_snap_m", "dest_snap_m",
        ]
        pd.DataFrame(columns=empty_cols).to_parquet(DISTANCES_FINAL, index=False)
        return pd.DataFrame(columns=empty_cols)

    df = pd.concat(
        [pd.read_parquet(f) for f in batch_files], ignore_index=True
    )

    # Stable column order (only include columns actually present).
    # Designation flags are whatever has_* columns arrived from the
    # destinations layer -- discovered dynamically so upstream additions
    # flow through without a code change here.
    has_cols = [c for c in df.columns if c.startswith("has_")]
    preferred = (
        ["origin_id", "dest_id", "site_id", "travel_time_s", "dist_m", "mode"]
        + has_cols
        + ["is_protected", "designation_count",
           "park_dataset", "park_class",
           "origin_snap_m", "dest_snap_m"]
    )
    df = df[[c for c in preferred if c in df.columns]]

    df.to_parquet(DISTANCES_FINAL, index=False)
    print(f"Wrote {len(df):,} rows -> {DISTANCES_FINAL}")
    return df
