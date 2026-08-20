"""
-------------------------------------------------------------------------------
Title: osrm_client
Description: Thin wrapper around routingpy's OSRM client for the VISAGE
    routing pipeline. The reason this exists rather than calling
    routingpy directly:

      - OSRM's /table endpoint has a max coordinate count per call
        (default 100). For our pipeline an origin can have hundreds of
        candidate destinations within the spatial radius, so we batch.
      - We need a uniform return type (durations, distances, snap
        distances) per (origin, destination) pair regardless of how many
        batches were used.
      - We want a single retry / timeout policy across all calls.

    The wrapper assumes 1 source per call (the current origin) and
    BATCH_SIZE - 1 destinations per call. If you ever switch to many-source
    many-destination patterns, generalise from here.

    routingpy install:  conda install -c conda-forge routingpy
                        (or: pip install routingpy)
Created: 13/05/2026
Author: tommycollins1 (trc207)
Notes:
    input:  OSRM_URL must point at a running OSRM server matching the
            active MODE's profile.
    output: pandas DataFrames returned in-memory; no parquet writes here.
-------------------------------------------------------------------------------
"""
from __future__ import annotations

import time
from typing import Sequence

import pandas as pd
import requests

from src.get_network_england_osrm.cfg import (
    OSRM_URL,
    PROFILE,
    TABLE_ANNOTATIONS,
    TABLE_BATCH_SIZE,
)


# Connection / retry policy. OSRM is fast and local, but routingpy can
# occasionally raise transient connection errors when the server is busy.
HTTP_TIMEOUT_S = 30
MAX_RETRIES = 3
RETRY_SLEEP_S = 1.0


# ----------------------------------------------------------- HEALTHCHECK -

def ping() -> bool:
    """Return True iff the OSRM server at OSRM_URL is reachable.

    Sends a trivial /route query at coordinates 0,0;0,0 -- OSRM responds
    even though the result is meaningless; we only care that it responds.
    """
    try:
        r = requests.get(
            f"{OSRM_URL}/route/v1/{PROFILE['osrm_profile']}/0,0;0,0",
            timeout=5,
        )
        return r.status_code in (200, 400)  # 400 = no route, server is up
    except requests.RequestException:
        return False


# ------------------------------------------------------------- TABLE CALL -

def _one_batch_table(
    origin_lonlat: tuple[float, float],
    dest_lonlats: Sequence[tuple[float, float]],
) -> dict:
    """Single /table call: 1 source, up to TABLE_BATCH_SIZE-1 destinations.

    Returns the raw JSON dict. Caller flattens into rows.
    """
    if len(dest_lonlats) + 1 > TABLE_BATCH_SIZE:
        raise ValueError(
            f"Too many destinations for one batch: {len(dest_lonlats)}; "
            f"max is {TABLE_BATCH_SIZE - 1}."
        )

    # Use explicit decimal notation: OSRM rejects scientific notation (e.g.
    # 7.26e-05) for coordinates near zero, returning a 400 Bad Request.
    coords = ";".join(
        f"{lon:.8f},{lat:.8f}" for lon, lat in [origin_lonlat, *dest_lonlats]
    )
    params = {
        "sources": "0",
        "destinations": ";".join(str(i) for i in range(1, len(dest_lonlats) + 1)),
        "annotations": TABLE_ANNOTATIONS,
    }
    url = f"{OSRM_URL}/table/v1/{PROFILE['osrm_profile']}/{coords}"

    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(url, params=params, timeout=HTTP_TIMEOUT_S)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as exc:
            last_exc = exc
            time.sleep(RETRY_SLEEP_S * (attempt + 1))

    raise RuntimeError(
        f"OSRM /table call failed after {MAX_RETRIES} attempts: {last_exc}"
    )


def one_to_many(
    origin_lonlat: tuple[float, float],
    dest_lonlats: Sequence[tuple[float, float]],
    dest_ids: Sequence[str],
) -> pd.DataFrame:
    """One source vs many destinations.

    Batches across TABLE_BATCH_SIZE-1 destinations per /table call. Returns
    a long DataFrame:
        dest_id, travel_time_s, dist_m, origin_snap_m, dest_snap_m
    Rows where OSRM couldn't find a route (null duration) are dropped.
    """
    if not dest_lonlats:
        return pd.DataFrame(
            columns=[
                "dest_id", "travel_time_s", "dist_m",
                "origin_snap_m", "dest_snap_m",
            ]
        )
    if len(dest_lonlats) != len(dest_ids):
        raise ValueError(
            "dest_lonlats and dest_ids must be the same length."
        )

    rows = []
    step = TABLE_BATCH_SIZE - 1
    for i in range(0, len(dest_lonlats), step):
        batch_coords = dest_lonlats[i:i + step]
        batch_ids = dest_ids[i:i + step]
        payload = _one_batch_table(origin_lonlat, batch_coords)

        # OSRM returns durations as [[d1, d2, ...]] for one source. Same
        # shape for distances. Waypoints carry snap distances; index 0 is
        # the origin, 1..N are destinations.
        durations = payload.get("durations", [[]])[0]
        distances = payload.get("distances", [[]])[0]
        waypoints = payload.get("waypoints", [])
        origin_snap = waypoints[0]["distance"] if waypoints else None

        for j, dest_id in enumerate(batch_ids):
            tt = durations[j] if j < len(durations) else None
            dm = distances[j] if j < len(distances) else None
            if tt is None:
                continue
            dest_snap = (
                waypoints[j + 1]["distance"]
                if (j + 1) < len(waypoints)
                else None
            )
            rows.append(
                (dest_id, float(tt), float(dm) if dm is not None else None,
                 origin_snap, dest_snap)
            )

    return pd.DataFrame(
        rows,
        columns=[
            "dest_id", "travel_time_s", "dist_m",
            "origin_snap_m", "dest_snap_m",
        ],
    )
