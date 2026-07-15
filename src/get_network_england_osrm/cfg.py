"""
-------------------------------------------------------------------------------
Title: get_network_england_osrm cfg
Description: Configuration for the OSRM-backed routing pipeline. Mirrors
    the cfg.py pattern used elsewhere in src/data/.

    MODE selects walk or drive. The relevant OSRM server must be running
    locally on the matching port for the active mode. On 16 GB RAM, run
    one server at a time -- see README.md for the Docker incantations.
Created: 13/05/2026
Author: tommycollins1 (trc207)
Notes:
    input:  PROCESSED root from main_config.
    output: paths for OSRM distances outputs (per access point + per site).
-------------------------------------------------------------------------------
"""
import os
from pathlib import Path
from typing import Final, Literal, TypedDict

from main_config import PROCESSED


# =============================================================================
# MODE PROFILE
# =============================================================================
# Mode-specific routing parameters. Threshold is the travel-time cutoff in
# seconds (applied per OD pair after OSRM returns durations).
# candidate_radius_m is a generous Euclidean upper bound used to pre-filter
# destinations before sending /table queries to OSRM. It must be larger
# than threshold_s * peak_speed so we don't miss any reachable pair.

Mode = Literal["walk", "drive"]


class ModeProfile(TypedDict):
    osrm_profile: str         # OSRM Lua profile (foot / car)
    threshold_s: int          # routing cutoff (s)
    candidate_radius_m: int   # Euclidean radius for spatial pre-filter (m)
    osrm_port: int            # local OSRM server port for this mode


MODE_PROFILES: Final[dict[Mode, ModeProfile]] = {
    "walk": {
        "osrm_profile": "foot",
        "threshold_s": 20 * 60,         # 20 min
        "candidate_radius_m": 3_000,    # 3 km Euclidean catches a 20-min walk
        "osrm_port": 5000,
    },
    "drive": {
        "osrm_profile": "car",
        "threshold_s": 20 * 60,         # 20 min
        "candidate_radius_m": 30_000,   # 30 km Euclidean catches a 20-min drive
        "osrm_port": 5001,
    },
}

MODE: Final[Mode] = os.environ.get("VISAGE_MODE", "drive")  # type: ignore[assignment]
if MODE not in MODE_PROFILES:
    raise ValueError(
        f"Unknown MODE {MODE!r}. Expected one of {list(MODE_PROFILES)}."
    )

PROFILE: Final[ModeProfile] = MODE_PROFILES[MODE]


# =============================================================================
# OSRM SERVER
# =============================================================================
# Resolved at import: OSRM_URL points at the port that matches the active
# MODE. Override the host (e.g. for a remote server) with VISAGE_OSRM_HOST.

OSRM_HOST: Final[str] = os.environ.get("VISAGE_OSRM_HOST", "localhost")
OSRM_URL: Final[str] = f"http://{OSRM_HOST}:{PROFILE['osrm_port']}"

# Max coordinates per /table call. Must be strictly less than the server's
# --max-table-size (default 100, limit is exclusive). We send 1 source +
# up to (BATCH_SIZE - 1) destinations = BATCH_SIZE total coordinates.
TABLE_BATCH_SIZE: Final[int] = 99

# Annotations requested from OSRM /table.
# "duration"          -- works on all OSRM versions (dist_m will be None)
# "duration,distance" -- requires OSRM >= 5.22 (adds dist_m to output)
# Switch to "duration,distance" after upgrading the Docker image.
TABLE_ANNOTATIONS: Final[str] = "duration"


# =============================================================================
# PBF (for reference; preprocessing is a one-off Docker step, not Python)
# =============================================================================
# Path to the locally downloaded PBF used for OSRM preprocessing. Not read
# by the Python pipeline -- recorded here so the run is self-documenting
# and the README can point at the same file.

PBF_PATH: Final[Path] = Path(
    os.environ.get(
        "VISAGE_PBF_PATH",
        str(PROCESSED.parent / "data" / "geographic_areas" /
            "england-260517.osm.pbf"),
    )
)


# =============================================================================
# TEST REGION
# =============================================================================
# Same Oxford + Cherwell test region as get_network_england/. Setting
# CLIP_TO_TEST_REGION=True restricts origins and destinations to this
# region; the OSRM server still serves the whole-England graph, that's
# fine, the pipeline just queries less of it.

LAD_SELECTIONS_TEST: Final[dict[str, list[str]]] = {
    "oxford_plus_cherwell": [
        "E07000178",  # Oxford
        # "E07000177",  # Cherwell
    ],
}

CLIP_TO_TEST_REGION: Final[bool] = False


# =============================================================================
# OUTPUT PATHS
# =============================================================================
# Mode is encoded in the path so walk and drive runs don't collide. The
# parent directory differs from get_network_england/ so the two engines'
# outputs sit side-by-side and can be diffed.

GET_NETWORK_ENGLAND_OSRM: Final[Path] = (
    PROCESSED / "get_network_england_osrm" / MODE
)

DISTANCES_FINAL: Final[Path] = (
    GET_NETWORK_ENGLAND_OSRM / "distances_final.parquet"
)
DISTANCES_PER_SITE: Final[Path] = (
    GET_NETWORK_ENGLAND_OSRM / "distances_per_site.parquet"
)

# Diagnostic outputs.
ORIGINS_CACHE: Final[Path] = GET_NETWORK_ENGLAND_OSRM / "origins.parquet"
DESTINATIONS_CACHE: Final[Path] = (
    GET_NETWORK_ENGLAND_OSRM / "destinations.parquet"
)


# =============================================================================
# CRS
# =============================================================================

BNG_EPSG: Final[int] = 27700
WGS84_EPSG: Final[int] = 4326
