"""
-------------------------------------------------------------------------------
Title: compute_distances
Description: End-to-end OSRM routing pipeline with per-batch checkpointing
    and thread-pool parallelism.

      1. Load origins (LSOA pop-weighted centroids) and destinations
         (greenspace access points).
      2. Load list of completed origins from PROGRESS_FILE; skip them.
      3. Loop remaining origins in batches of CHECKPOINT_EVERY. Each batch
         is dispatched to a ThreadPoolExecutor(N_WORKERS). OSRM /table
         calls release the GIL during HTTP I/O, so threading gives
         near-linear speedup up to OSRM's own worker limit.
      4. After each batch: write a partition parquet under BATCHES_DIR
         and append origin_ids to PROGRESS_FILE. If the process dies now,
         restart re-uses everything before this point.
      5. When all origins processed, concat batch parquets, attach
         designation metadata, cast dtypes, write DISTANCES_FINAL.

    Resumability + concurrency mean an England-scale drive run drops
    from ~3 days to ~4-8 hours on a typical laptop, and a crash costs
    at most CHECKPOINT_EVERY origins (default 500).
Created: 13/05/2026; refactored 22/07/2026 for checkpointing + threading.
Author: tommycollins1 (trc207)
Notes:
    input:  ALL_GREENSPACE_ACCESS_UNION parquet, LSOA pop-weighted centroids,
            a running OSRM server at OSRM_URL.
    output: DISTANCES_FINAL parquet (per access point).
-------------------------------------------------------------------------------
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import geopandas as gpd
import pandas as pd
from tqdm import tqdm

from src.get_network_england_osrm.loaders import (
    load_destinations,
    load_origins,
)
from src.get_network_england_osrm.cfg import (
    BATCHES_DIR,
    BNG_EPSG,
    CHECKPOINT_EVERY,
    DESTINATIONS_CACHE,
    DISTANCES_FINAL,
    GET_NETWORK_ENGLAND_OSRM,
    MODE,
    N_WORKERS,
    ORIGINS_CACHE,
    PROFILE,
    PROGRESS_FILE,
    WGS84_EPSG,
)
from src.get_network_england_osrm.osrm_client import one_to_many, ping


def _to_lonlat(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Project to WGS84 lon/lat for OSRM submission."""
    if gdf.crs is None:
        raise ValueError("GeoDataFrame has no CRS; can't reproject.")
    if gdf.crs.to_epsg() == WGS84_EPSG:
        return gdf.copy()
    return gdf.to_crs(WGS84_EPSG)


# ------------------------------------------------------- PROGRESS HELPERS -

def _load_completed_origins(path: Path) -> set[str]:
    if not Path(path).exists():
        return set()
    df = pd.read_csv(path)
    return set(df["origin_id"].astype(str).tolist())


def _append_completed_origins(path: Path, origin_ids: list[str]) -> None:
    new_df = pd.DataFrame({"origin_id": list(origin_ids)})
    path = Path(path)
    if path.exists():
        new_df.to_csv(path, mode="a", header=False, index=False)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        new_df.to_csv(path, index=False)


# ---------------------------------------------------------- PER-ORIGIN --

def _process_one_origin(
    origin_id: str,
    o_pt,                              # shapely Point (BNG)
    o_lonlat: tuple[float, float],     # (lon, lat) for OSRM
    destinations_bng: gpd.GeoDataFrame,
    destinations_ll: pd.DataFrame,
    dest_sindex,
    candidate_radius_m: float,
    threshold_s: float,
) -> pd.DataFrame:
    """Route one origin against reachable candidates. Thread-safe (pure).

    Returns a long DataFrame of (origin_id, dest_id, travel_time_s, dist_m,
    origin_snap_m, dest_snap_m). Empty DataFrame if no reachable pairs.
    """
    # Bounding-box pre-filter, then exact radius.
    bbox = o_pt.buffer(candidate_radius_m).bounds
    cand_idx = list(dest_sindex.intersection(bbox))
    if not cand_idx:
        return pd.DataFrame()

    cand = destinations_bng.iloc[cand_idx]
    mask = cand.distance(o_pt) <= candidate_radius_m
    cand = cand[mask]
    if cand.empty:
        return pd.DataFrame()

    # cand.index is the original destinations_bng row labels; translate to
    # positional indices to look up lon/lat in destinations_ll.
    positional = destinations_bng.index.get_indexer(cand.index)
    cand_ll = destinations_ll.iloc[positional]
    dest_lonlats = list(zip(cand_ll["lon"], cand_ll["lat"]))
    dest_ids = cand_ll["dest_id"].astype(str).tolist()

    routes = one_to_many(o_lonlat, dest_lonlats, dest_ids)
    if routes.empty:
        return pd.DataFrame()

    routes = routes[routes["travel_time_s"] <= threshold_s].copy()
    if routes.empty:
        return pd.DataFrame()

    routes["origin_id"] = origin_id
    return routes


# ---------------------------------------------------------- MAIN LOOP --

def compute_distances() -> pd.DataFrame:
    """Run the full OSRM pipeline for the active MODE.

    Idempotent + resumable: reads PROGRESS_FILE on entry, skips completed
    origins, and writes one batch parquet + progress-CSV append per
    CHECKPOINT_EVERY origins. On successful completion, concats all
    batch parquets into DISTANCES_FINAL.
    """
    print(f"=== get_network_england_osrm | MODE = {MODE} ===")
    print(f"Threshold:        {PROFILE['threshold_s'] / 60:.1f} min")
    print(f"Candidate radius: {PROFILE['candidate_radius_m'] / 1000:.1f} km")
    print(f"Workers:          {N_WORKERS}; checkpoint every {CHECKPOINT_EVERY} origins")

    if not ping():
        raise RuntimeError(
            "OSRM server not reachable. Start the matching server "
            f"(profile={PROFILE['osrm_profile']}, "
            f"port={PROFILE['osrm_port']}) before running this pipeline. "
            "See README.md for the Docker incantation."
        )

    GET_NETWORK_ENGLAND_OSRM.mkdir(parents=True, exist_ok=True)
    BATCHES_DIR.mkdir(parents=True, exist_ok=True)

    # ---- Origins + destinations ------------------------------------------
    origins_bng = load_origins().to_crs(BNG_EPSG)
    destinations_bng = load_destinations().to_crs(BNG_EPSG)

    print(f"Origins:      {len(origins_bng):,}")
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

    # O(1) origin_id -> (lon, lat) lookup. Avoids the per-origin
    # boolean-mask in the old code (which was O(N) per iteration).
    origins_ll_lookup: dict[str, tuple[float, float]] = {
        r.origin_id: (float(r.lon), float(r.lat))
        for r in origins_ll.itertuples(index=False)
    }

    dest_sindex = destinations_bng.sindex
    candidate_radius_m = PROFILE["candidate_radius_m"]
    threshold_s = PROFILE["threshold_s"]

    # ---- Resume ----------------------------------------------------------
    completed = _load_completed_origins(PROGRESS_FILE)
    todo = [
        r for r in origins_bng.itertuples(index=False)
        if r.origin_id not in completed
    ]
    print(
        f"Origins to process: {len(todo):,} "
        f"(skipping {len(completed):,} already completed)"
    )

    if not todo:
        print("Nothing to do; proceeding straight to concat step.")

    started = time.time()

    # Existing batch count so we can label new batches without collision.
    existing_batches = sorted(BATCHES_DIR.glob("batch_*.parquet"))
    batch_id_offset = len(existing_batches)

    # ---- Loop batches with ThreadPoolExecutor -----------------------------
    for start in range(0, len(todo), CHECKPOINT_EVERY):
        batch = todo[start:start + CHECKPOINT_EVERY]
        batch_id = batch_id_offset + (start // CHECKPOINT_EVERY)

        batch_rows: list[pd.DataFrame] = []

        with ThreadPoolExecutor(max_workers=N_WORKERS) as ex:
            futures = {}
            for o_row in batch:
                o_lonlat = origins_ll_lookup.get(o_row.origin_id)
                if o_lonlat is None:
                    continue
                fut = ex.submit(
                    _process_one_origin,
                    o_row.origin_id,
                    o_row.geometry,
                    o_lonlat,
                    destinations_bng,
                    destinations_ll,
                    dest_sindex,
                    candidate_radius_m,
                    threshold_s,
                )
                futures[fut] = o_row.origin_id

            for fut in tqdm(
                as_completed(futures),
                total=len(futures),
                desc=f"batch {batch_id + 1}/{batch_id_offset + (len(todo) + CHECKPOINT_EVERY - 1) // CHECKPOINT_EVERY}",
            ):
                origin_id = futures[fut]
                try:
                    routes = fut.result()
                except Exception as exc:
                    print(f"origin {origin_id} failed: {exc}")
                    continue
                if not routes.empty:
                    batch_rows.append(routes)

        # Persist this batch and record progress.
        if batch_rows:
            batch_df = pd.concat(batch_rows, ignore_index=True)
            batch_path = BATCHES_DIR / f"batch_{batch_id:05d}.parquet"
            batch_df.to_parquet(batch_path, index=False)

        _append_completed_origins(
            PROGRESS_FILE, [o_row.origin_id for o_row in batch]
        )

    elapsed = time.time() - started
    print(f"Routing loop finished in {elapsed:.1f} s.")

    # ---- Concat all batch parquets ---------------------------------------
    batch_files = sorted(BATCHES_DIR.glob("batch_*.parquet"))
    if not batch_files:
        empty_cols = [
            "origin_id", "dest_id", "site_id", "travel_time_s",
            "dist_m", "mode",
            "has_agi", "has_sssi", "has_sac", "has_spa", "has_ramsar",
            "is_protected", "designation_count",
            "origin_snap_m", "dest_snap_m",
        ]
        empty = pd.DataFrame(columns=empty_cols)
        empty.to_parquet(DISTANCES_FINAL, index=False)
        return empty

    print(f"Concatenating {len(batch_files):,} batch partitions ...")
    df = pd.concat(
        [pd.read_parquet(f) for f in batch_files], ignore_index=True
    )

    # ---- Attach destination metadata --------------------------------------
    has_cols = [
        c for c in destinations_bng.columns if c.startswith("has_")
    ]
    meta_cols = [
        c for c in (
            ["site_id"] + has_cols
            + ["is_protected", "designation_count"]
        ) if c in destinations_bng.columns
    ]
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

    preferred = (
        ["origin_id", "dest_id", "site_id", "travel_time_s", "dist_m",
         "mode"]
        + has_cols
        + ["is_protected", "designation_count",
           "origin_snap_m", "dest_snap_m"]
    )
    cols = [c for c in preferred if c in df.columns]
    df = df[cols]

    df.to_parquet(DISTANCES_FINAL, index=False)
    print(f"Wrote {len(df):,} rows -> {DISTANCES_FINAL}")
    return df
