"""
-------------------------------------------------------------------------------
Title: routing
Description: Single-source Dijkstra per destination, plus checkpointing
    helpers. Preserved from src/data/get_network/network_ftns.py::
    process_park but:
      - renamed to process_destination and given a mode-aware weight
      - returns a pandas DataFrame with the OSRM-comparable schema
        (dest_id / site_id / designation flags / travel_time_s / dist_m)
      - dropped the unused `tobeadded()` scaffolding
      - dropped the postcode branch (this module is LSOA-only)

    The routing pattern: one nx.single_source_dijkstra_path_length call per
    destination (not per origin). For an Oxford + Cherwell graph with a
    few thousand access points and ~600 LSOAs, per-destination Dijkstra
    with joblib parallelism is the pattern used by the historical
    get_network/ code and it works well.
Created: 13/05/2026
Author: tommycollins1 (trc207)
Notes:
    input:  destination row (dest_id + node + metadata), origin nodes df,
            graph G, weight attribute, cutoff.
    output: DataFrame of reachable (origin, dest) pairs with the shared
            output schema.
-------------------------------------------------------------------------------
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import networkx as nx
import pandas as pd

from src.get_network_oxford_osmnx.cfg import (
    LEGACY_DESTINATIONS,
    MODE,
    PROFILE,
    WALK_SPEED_MPS,
)


# ------------------------------------------------------- CUTOFF DERIVATION -

def cutoff_for_dijkstra() -> float:
    """Return the cutoff value in the units of the active weight.

    walk: weight = 'length' (metres) so cutoff = threshold_s * WALK_SPEED_MPS
    drive: weight = 'travel_time' (seconds) so cutoff = threshold_s
    """
    if PROFILE["weight_is_time"]:
        return float(PROFILE["threshold_s"])
    return float(PROFILE["threshold_s"] * WALK_SPEED_MPS)


# ------------------------------------------------------------ PER-DEST DIJK -

def process_destination(
    dest_row: dict,
    origin_nodes: pd.DataFrame,
    G: nx.MultiDiGraph,
) -> pd.DataFrame:
    """Single-source Dijkstra from one destination, filter to origins.

    Parameters
    ----------
    dest_row : dict
        Row from the destinations DataFrame. Required keys: 'dest_id',
        'node'. Optional keys (present when LEGACY_DESTINATIONS = False):
        'site_id', any number of designation flag columns starting with
        `has_` (e.g. 'has_agi', 'has_sssi', 'has_sac', 'has_ramsar',
        'has_spa'), 'is_protected', 'designation_count', 'snap_m'. Legacy
        keys (when LEGACY_DESTINATIONS = True): 'park_dataset',
        'park_class'.
    origin_nodes : pd.DataFrame
        Columns: 'origin_id', 'node', 'snap_m'. One row per origin.
    G : nx.MultiDiGraph
        Projected graph with 'length' (walk) or 'travel_time' (drive)
        edge attribute populated.

    Returns
    -------
    pd.DataFrame
        Long-format rows: origin_id, dest_id, travel_time_s, dist_m,
        mode, origin_snap_m, dest_snap_m, plus dest metadata columns.
    """
    lengths = nx.single_source_dijkstra_path_length(
        G,
        dest_row["node"],
        cutoff=cutoff_for_dijkstra(),
        weight=PROFILE["weight"],
    )

    s = origin_nodes["node"].map(lengths)
    mask = s.notna()
    if not mask.any():
        return pd.DataFrame()

    reachable = origin_nodes.loc[mask].copy()
    weight_vals = s.loc[mask].astype("float32").to_numpy()

    if PROFILE["weight_is_time"]:
        travel_time_s = weight_vals
        # Approximate distance back-computed from travel time (drive routes
        # mix speeds; if exact distance is needed, swap the routing call to
        # nx.single_source_dijkstra which also returns paths, then sum
        # edge 'length'). Matches OSRM module's back-conversion.
        dist_m = (travel_time_s * 13.4).astype("float32")   # ~48 km/h avg
    else:
        dist_m = weight_vals
        travel_time_s = (dist_m / WALK_SPEED_MPS).astype("float32")

    out = pd.DataFrame(
        {
            "origin_id": reachable["origin_id"].to_numpy(),
            "dest_id": dest_row["dest_id"],
            "travel_time_s": travel_time_s,
            "dist_m": dist_m,
            "mode": MODE,
            "origin_snap_m": reachable["snap_m"].astype("float32").to_numpy(),
            "dest_snap_m": (
                float(dest_row.get("snap_m", 0.0))
            ),
        }
    )

    # Attach destination metadata. Different columns per LEGACY toggle.
    # Designation flag columns are discovered dynamically from dest_row so
    # any upstream additions (Ramsar, SPA, etc.) propagate automatically.
    if LEGACY_DESTINATIONS:
        for c in ("park_dataset", "park_class"):
            if c in dest_row:
                out[c] = dest_row[c]
    else:
        has_cols = [k for k in dest_row.keys() if k.startswith("has_")]
        for c in (["site_id"] + has_cols
                  + ["is_protected", "designation_count"]):
            if c in dest_row:
                out[c] = dest_row[c]

    return out


# ---------------------------------------------------------- BATCH I/O UTILS -

def save_parquet_batch(df_list: list[pd.DataFrame], out_dir: Path, batch_id: int) -> None:
    """Concat a list of DataFrames and persist as one batch parquet."""
    if not df_list:
        return
    out = pd.concat(df_list, ignore_index=True)
    if out.empty:
        return
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out.to_parquet(out_dir / f"batch_{batch_id:05d}.parquet")


def load_processed_ids(progress_file: Path) -> set[str]:
    """Read the progress CSV and return the set of already-done dest_ids."""
    progress_path = Path(progress_file)
    if not progress_path.exists():
        return set()
    df = pd.read_csv(progress_path)
    if "dest_id" not in df.columns:
        raise ValueError(f"'dest_id' column not found in {progress_file}")
    return set(df["dest_id"].astype(str).tolist())


def append_processed_ids(
    progress_file: Path,
    dest_ids: Iterable[str],
) -> None:
    """Append completed dest_ids to the progress CSV."""
    progress_path = Path(progress_file)
    new_df = pd.DataFrame({"dest_id": list(dest_ids)})
    if progress_path.exists():
        new_df.to_csv(progress_path, mode="a", header=False, index=False)
    else:
        progress_path.parent.mkdir(parents=True, exist_ok=True)
        new_df.to_csv(progress_path, index=False)
