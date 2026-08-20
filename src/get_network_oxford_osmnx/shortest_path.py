"""
-------------------------------------------------------------------------------
Title: shortest_path
Description: Optional companion to compute_distances that also emits the
    actual route geometries (LineStrings) rather than just travel times.
    Useful for map visualisations of catchment flows in the paper.

    Not part of the main pipeline output -- run separately when needed.
    Reads the cached graph and snapped origin/destination nodes, computes
    shortest paths with nx.single_source_dijkstra (which returns paths as
    well as lengths), and writes a GeoParquet of one LineString per
    reachable (origin, dest) pair.
Created: 13/05/2026
Author: tommycollins1 (trc207)
Notes:
    input:  cached graph, cached snapped nodes.
    output: SHORTEST_PATH_FINAL parquet with geometry.
-------------------------------------------------------------------------------
"""
from __future__ import annotations

import geopandas as gpd
import networkx as nx
import osmnx as ox
from joblib import Parallel, delayed
from shapely.geometry.linestring import LineString
from tqdm import tqdm

from src.get_network_oxford_osmnx.cfg import (
    DESTINATIONS_CACHE,
    GRAPH_CACHE,
    N_JOBS,
    ORIGINS_CACHE,
    PROFILE,
    SHORTEST_PATH_FINAL,
)
from src.get_network_oxford_osmnx.routing import cutoff_for_dijkstra
from src.get_network_oxford_osmnx.snap import snap_points


def _routes_from_origin(
    o_node: int,
    dest_nodes: set[int],
    G: nx.MultiDiGraph,
) -> list[dict]:
    """One single-source Dijkstra from an origin, return LineString per dest."""
    _, paths = nx.single_source_dijkstra(
        G,
        o_node,
        weight=PROFILE["weight"],
        cutoff=cutoff_for_dijkstra(),
    )
    routes = []
    for d_node in dest_nodes:
        if d_node not in paths:
            continue
        path = paths[d_node]
        if len(path) < 2:
            continue
        coords = [(G.nodes[n]["x"], G.nodes[n]["y"]) for n in path]
        routes.append(
            {
                "origin_node": o_node,
                "dest_node": d_node,
                "geometry": LineString(coords),
            }
        )
    return routes


def main(n_jobs: int = N_JOBS) -> gpd.GeoDataFrame:
    """Compute route geometries for every reachable (origin, dest) pair."""
    G = ox.load_graphml(GRAPH_CACHE)
    origins = gpd.read_parquet(ORIGINS_CACHE)
    destinations = gpd.read_parquet(DESTINATIONS_CACHE)

    origin_nodes = snap_points(origins, G, "origin_id")
    dest_nodes = snap_points(destinations, G, "dest_id")

    o_ids = origin_nodes["node"].unique()
    d_set = set(dest_nodes["node"].unique())

    all_results = Parallel(n_jobs=n_jobs, backend="loky")(
        delayed(_routes_from_origin)(o_node, d_set, G)
        for o_node in tqdm(o_ids, desc="origins")
    )

    flat = [row for sublist in all_results for row in sublist]
    gdf = gpd.GeoDataFrame(
        flat, geometry="geometry", crs=G.graph.get("crs", "EPSG:27700")
    )

    SHORTEST_PATH_FINAL.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_parquet(SHORTEST_PATH_FINAL)
    print(f"Wrote {len(gdf):,} routes -> {SHORTEST_PATH_FINAL}")
    return gdf
