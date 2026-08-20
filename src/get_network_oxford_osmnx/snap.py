"""
-------------------------------------------------------------------------------
Title: snap
Description: Snap origin and destination points to nearest graph nodes,
    recording the snap distance for QA. Mirrors the OSRM module's
    diagnostic columns (origin_snap_m, dest_snap_m) so both engines'
    outputs can be compared like-for-like.

    Function signature is deliberately generic (gdf + id_col + G) so the
    same code handles origins and destinations. Snap distance is computed
    as the Euclidean distance in BNG metres between the point geometry
    and the snapped node's (x, y).
Created: 13/05/2026
Author: tommycollins1 (trc207)
Notes:
    input:  origins/destinations gdf in EPSG:27700, graph G already
            projected to EPSG:27700.
    output: DataFrame with [id_col, node, snap_m, geometry].
-------------------------------------------------------------------------------
"""
from __future__ import annotations

import geopandas as gpd
import networkx as nx
import numpy as np
import osmnx as ox
import pandas as pd


def snap_points(
    gdf: gpd.GeoDataFrame,
    G: nx.MultiDiGraph,
    id_col: str,
) -> pd.DataFrame:
    """Snap each geometry to its nearest graph node.

    Returns a DataFrame with columns [id_col, node, snap_m, geometry].
    snap_m is the Euclidean distance (BNG metres) from the input point to
    the snapped node -- kept as a per-row QA field.
    """
    if gdf.empty:
        return pd.DataFrame(
            columns=[id_col, "node", "snap_m", "geometry"]
        )

    xs = gdf.geometry.x.to_numpy()
    ys = gdf.geometry.y.to_numpy()
    nodes = ox.distance.nearest_nodes(G, X=xs, Y=ys)

    node_xs = np.array([G.nodes[n]["x"] for n in nodes])
    node_ys = np.array([G.nodes[n]["y"] for n in nodes])
    snap_m = np.hypot(xs - node_xs, ys - node_ys).astype("float32")

    return pd.DataFrame(
        {
            id_col: gdf[id_col].to_numpy(),
            "node": nodes,
            "snap_m": snap_m,
            "geometry": gdf.geometry.to_numpy(),
        }
    )
