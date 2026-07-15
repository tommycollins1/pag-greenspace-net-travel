"""
-------------------------------------------------------------------------------
Title: loaders
Description: Origin and destination loaders for the England-scale OSRM routing
    pipeline. Previously lived in get_network_england/tile_manifest.py
    alongside the osmnx tiled pipeline; extracted here when that module was
    retired in favour of get_network_england_osrm.

    load_origins()      -- LSOA 2021 pop-weighted centroids as routing origins
    load_destinations() -- greenspace access points with designation flags

    Both functions optionally clip to the Oxford + Cherwell test region when
    CLIP_TO_TEST_REGION is True in cfg.py. Set it to False for a full England
    run.
Created: 2026-05-26
Author: tommycollins1 (trc207)
Notes:
    input:  LSOA_POP_WEIGHTED_CENTROIDS_2021 (origins),
            ALL_GREENSPACE_ACCESS_UNION (destinations).
    output: GeoDataFrames (in-memory; callers write to disk as needed).
-------------------------------------------------------------------------------
"""
from typing import Optional

import geopandas as gpd

from main_config import LSOA_POP_WEIGHTED_CENTROIDS_2021
from src.data.get_geography.cfg import OX_LAD_2024_BUFF
from src.data.get_greenspace.cfg import ALL_GREENSPACE_ACCESS_UNION
from src.data.get_network_england_osrm.cfg import (
    BNG_EPSG,
    CLIP_TO_TEST_REGION,
    LAD_SELECTIONS_TEST,
)


def _load_clip_region() -> Optional[gpd.GeoDataFrame]:
    """Return the test-region polygon if CLIP_TO_TEST_REGION, else None."""
    if not CLIP_TO_TEST_REGION:
        return None

    lads = gpd.read_file(OX_LAD_2024_BUFF).to_crs(BNG_EPSG)
    selected_codes = [
        cd for cds in LAD_SELECTIONS_TEST.values() for cd in cds
    ]
    region = lads[lads["LAD24CD"].isin(selected_codes)].copy()
    if region.empty:
        raise RuntimeError(
            "Test region LADs not found in OX_LAD_2024_BUFF. "
            f"Looked for: {selected_codes}"
        )
    return region.dissolve()


def load_origins() -> gpd.GeoDataFrame:
    """LSOA 2021 population-weighted centroids as routing origins.

    Reads the canonical ONS population-weighted centroid dataset (already
    a point geometry per LSOA, properly weighted by where people actually
    live within the LSOA -- much more accurate than the geometric centroid
    of the LSOA polygon).

    Population itself is intentionally NOT carried here. The routing step
    only needs (origin_id, geometry); population is a downstream join
    against the full ENG_POPULATION_2020_2024 dataset when computing
    population-served / accessibility-by-deprivation metrics.
    """
    centroids = gpd.read_file(
        LSOA_POP_WEIGHTED_CENTROIDS_2021
    ).to_crs(BNG_EPSG)

    centroids = centroids[["LSOA21CD", "geometry"]].rename(
        columns={"LSOA21CD": "origin_id"}
    )

    clip = _load_clip_region()
    if clip is not None:
        centroids = gpd.clip(centroids, clip)

    return centroids.reset_index(drop=True)


def load_destinations() -> gpd.GeoDataFrame:
    """Greenspace access points with designation flags.

    Reads ALL_GREENSPACE_ACCESS_UNION -- one row per access point, joined to
    the decomposed union polygon it sits on so each access point carries
    has_agi/has_sssi/has_sac/is_protected/designation_count.

    The routing pipeline treats each access point as a distinct destination
    (dest_id = access_pt_id). Sites with multiple entries appear multiple
    times with a shared site_id; the optional collapse_to_site step
    aggregates to (origin_id, site_id) by min(travel_time_s) downstream.
    """
    access = gpd.read_parquet(ALL_GREENSPACE_ACCESS_UNION).to_crs(BNG_EPSG)

    # dest_id is the access-point id.
    access = access.rename(columns={"access_pt_id": "dest_id"})

    clip = _load_clip_region()
    if clip is not None:
        access = gpd.clip(access, clip)

    keep = [c for c in (
        "dest_id", "site_id",
        "has_agi", "has_sssi", "has_sac",
        "is_protected", "designation_count",
        "geometry",
    ) if c in access.columns]
    if "geometry" not in keep:
        keep.append("geometry")

    return access[keep].reset_index(drop=True)
