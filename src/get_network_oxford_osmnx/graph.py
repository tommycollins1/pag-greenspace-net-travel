"""
-------------------------------------------------------------------------------
Title: graph
Description: OSM graph fetch + project + cache. Cache-first: if the
    projected graphml already exists at GRAPH_CACHE, load it and skip
    the network fetch. Otherwise download via osmnx.graph_from_polygon
    using the mode's network_type, project to British National Grid,
    annotate travel_time for drive, and persist.

    The Oxford study area is small enough that a single England-wide
    graph server (as OSRM uses) is overkill; osmnx.graph_from_polygon
    against Overpass or a local extract returns in minutes.
Created: 13/05/2026
Author: tommycollins1 (trc207)
Notes:
    input:  Oxford + Cherwell LAD boundary (from get_geography), mode
            profile.
    output: projected networkx MultiDiGraph, optionally cached to disk.
-------------------------------------------------------------------------------
"""
from __future__ import annotations

import geopandas as gpd
import networkx as nx
import osmnx as ox
from shapely.geometry import Polygon

from src.get_geography.cfg import LAD_BFC_2024_BUFF
from src.get_network_oxford_osmnx.cfg import (
    BNG_EPSG,
    GET_NETWORK_OXFORD_OSMNX,
    GRAPH_CACHE,
    LAD_SELECTIONS,
    MODE,
    PROFILE,
    WGS84_EPSG,
)


def study_area_polygon() -> Polygon:
    """Dissolve the LADs in LAD_SELECTIONS into a single study-area polygon.

    Returned in EPSG:4326 (WGS84) because osmnx.graph_from_polygon expects
    lat/lon.
    """
    lads = gpd.read_file(LAD_BFC_2024_BUFF).to_crs(BNG_EPSG)
    codes = [cd for cds in LAD_SELECTIONS.values() for cd in cds]
    sel = lads[lads["LAD24CD"].isin(codes)].copy()
    if sel.empty:
        raise RuntimeError(
            f"None of {codes} found in LAD_BFC_2024_BUFF. "
            "Update LAD_SELECTIONS in cfg.py."
        )
    dissolved = sel.dissolve().to_crs(WGS84_EPSG)
    return dissolved.geometry.iloc[0]


def _annotate_travel_time(G: nx.MultiDiGraph) -> nx.MultiDiGraph:
    """Attach a 'travel_time' attribute per edge (seconds).

    walk: not needed; the pipeline uses edge 'length' as weight and
          converts to travel_time downstream via WALK_SPEED_MPS.
    drive: use osmnx.add_edge_speeds to infer per-edge speed from OSM
           maxspeed tags with fallbacks per highway class, then
           add_edge_travel_times to compute travel_time from length.
    """
    if PROFILE["network_type"] == "walk":
        return G
    G = ox.add_edge_speeds(G)
    G = ox.add_edge_travel_times(G)
    return G


def fetch_graph() -> nx.MultiDiGraph:
    """Download the OSM graph for the study area and project to BNG."""
    boundary_ll = study_area_polygon()
    G = ox.graph_from_polygon(
        boundary_ll,
        network_type=PROFILE["network_type"],
        simplify=False,
        retain_all=False,
    )
    G = ox.project_graph(G, to_crs=f"EPSG:{BNG_EPSG}")
    G = _annotate_travel_time(G)
    return G


def load_or_fetch_graph() -> nx.MultiDiGraph:
    """Cache-first: load the projected graphml if it exists, else fetch."""
    if GRAPH_CACHE.exists():
        return ox.load_graphml(GRAPH_CACHE)
    GET_NETWORK_OXFORD_OSMNX.mkdir(parents=True, exist_ok=True)
    G = fetch_graph()
    ox.save_graphml(G, GRAPH_CACHE)
    print(f"[graph] MODE={MODE}; fetched + cached graph -> {GRAPH_CACHE}")
    return G
