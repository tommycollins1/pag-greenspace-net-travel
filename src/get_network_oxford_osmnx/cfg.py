"""
-------------------------------------------------------------------------------
Title: get_network_oxford_osmnx cfg
Description: Configuration for the Oxford osmnx routing pipeline. Mirrors
    the cfg.py pattern used in get_network_england_osrm and elsewhere in
    src/data/.

    MODE selects walk or drive. LEGACY_DESTINATIONS switches the input
    destinations file back to the pre-union OX_ASSEMBLE_GREENSPACE for
    reproducing the historical get_network/ outputs verbatim; default is
    the new designation-aware access-point layer.
Created: 13/05/2026
Author: tommycollins1 (trc207)
Notes:
    input:  PROCESSED root from main_config.
    output: paths for graph cache, distances outputs, checkpointing.
-------------------------------------------------------------------------------
"""
import os
from pathlib import Path
from typing import Final, Literal, TypedDict

from main_config import PROCESSED


# =============================================================================
# MODE PROFILE
# =============================================================================
# walk: osmnx network_type='walk'. Dijkstra weight is edge 'length' in metres.
#       Cutoff in metres = threshold_s * walk_speed_mps. Uniform pedestrian
#       speed (WALK_SPEED_KPH) matches OSRM's foot.lua conceptually so the
#       two engines are directly comparable.
# drive: osmnx network_type='drive'. osmnx.add_edge_speeds + add_edge_
#        travel_times populate a 'travel_time' attribute per edge from OSM
#        maxspeed tags with fallbacks. Dijkstra weight is 'travel_time'
#        in seconds; cutoff is threshold_s.

Mode = Literal["walk", "drive"]


class ModeProfile(TypedDict):
    network_type: str          # osmnx network_type
    threshold_s: int           # routing cutoff, seconds
    weight: str                # networkx edge attribute used as Dijkstra weight
    weight_is_time: bool       # True if weight already in seconds


MODE_PROFILES: Final[dict[Mode, ModeProfile]] = {
    "walk": {
        "network_type": "walk",
        "threshold_s": 20 * 60,
        "weight": "length",
        "weight_is_time": False,
    },
    "drive": {
        "network_type": "drive",
        "threshold_s": 20 * 60,
        "weight": "travel_time",
        "weight_is_time": True,
    },
}

MODE: Final[Mode] = os.environ.get("VISAGE_MODE", "walk")  # type: ignore[assignment]
if MODE not in MODE_PROFILES:
    raise ValueError(
        f"Unknown MODE {MODE!r}. Expected one of {list(MODE_PROFILES)}."
    )

PROFILE: Final[ModeProfile] = MODE_PROFILES[MODE]


# =============================================================================
# WALKING SPEED (uniform, matches OSRM foot.lua conceptually)
# =============================================================================

WALK_SPEED_KPH: Final[float] = 4.8
WALK_SPEED_MPS: Final[float] = WALK_SPEED_KPH * 1000.0 / 3600.0


# =============================================================================
# STUDY AREA
# =============================================================================
# Oxford + Cherwell by default so cross-engine validation with
# get_network_england_osrm (which uses the same two LADs as its test region)
# works out of the box. Reduce to Oxford only for the historical case study.

LAD_SELECTIONS: Final[dict[str, list[str]]] = {
    "oxford_plus_cherwell": [
        "E07000178",  # Oxford
        "E07000177",  # Cherwell
    ],
}


# =============================================================================
# LEGACY MODE (historical Oxford reproduction)
# =============================================================================
# When True, destinations come from OX_ASSEMBLE_GREENSPACE (pre-union polygon
# points) and the output carries park_dataset / park_class columns instead of
# site_id + designation flags. Reproduces src/data/get_network/ outputs
# verbatim for backward comparison.

LEGACY_DESTINATIONS: Final[bool] = os.environ.get(
    "VISAGE_LEGACY_DESTINATIONS", "0"
) == "1"


# =============================================================================
# CHECKPOINTING + PARALLELISM
# =============================================================================

CHECKPOINT_EVERY: Final[int] = 100  # destinations per batch
N_JOBS: Final[int] = 4              # joblib worker count


# =============================================================================
# OUTPUT PATHS
# =============================================================================
# Mode is encoded in the path so walk and drive don't clash. Legacy runs
# write to the same MODE folder but with '_legacy' suffixed onto the leaf
# filenames so they never overwrite the primary outputs.

GET_NETWORK_OXFORD_OSMNX: Final[Path] = (
    PROCESSED / "get_network_oxford_osmnx" / MODE
)

# ---- Graph cache (projected graphml, per mode)
GRAPH_CACHE: Final[Path] = GET_NETWORK_OXFORD_OSMNX / "graph.graphml"

# ---- Cached inputs so re-runs skip re-loading
ORIGINS_CACHE: Final[Path] = GET_NETWORK_OXFORD_OSMNX / "origins.parquet"
DESTINATIONS_CACHE: Final[Path] = (
    GET_NETWORK_OXFORD_OSMNX / "destinations.parquet"
)

# ---- Per-destination batch parquets + progress CSV
BATCHES_DIR: Final[Path] = GET_NETWORK_OXFORD_OSMNX / "batches"
PROGRESS_FILE: Final[Path] = GET_NETWORK_OXFORD_OSMNX / "progress.csv"

# ---- Final outputs
_leaf_suffix = "_legacy" if LEGACY_DESTINATIONS else ""
DISTANCES_FINAL: Final[Path] = (
    GET_NETWORK_OXFORD_OSMNX / f"distances_final{_leaf_suffix}.parquet"
)
DISTANCES_PER_SITE: Final[Path] = (
    GET_NETWORK_OXFORD_OSMNX / f"distances_per_site{_leaf_suffix}.parquet"
)

# ---- Optional route geometry (shortest_path)
SHORTEST_PATH_FINAL: Final[Path] = (
    GET_NETWORK_OXFORD_OSMNX / "shortest_paths.parquet"
)


# =============================================================================
# CRS
# =============================================================================

BNG_EPSG: Final[int] = 27700
WGS84_EPSG: Final[int] = 4326
