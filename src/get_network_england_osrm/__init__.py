"""
-------------------------------------------------------------------------------
Title: get_network_england_osrm
Description: OSRM-backed routing pipeline for VISAGE greenspace
    accessibility. Companion to get_network_england/, which uses osmnx +
    networkx with a tiled architecture. This module replaces the tiling
    layer with a single locally-hosted OSRM server that holds an
    England-wide preprocessed graph in memory and answers /table queries
    over HTTP.

    The output schema is identical to get_network_england/, so downstream
    analysis code is unchanged regardless of which engine produced the
    distances. The two implementations can be cross-validated on the
    Oxford + Cherwell test region.

    Mode (walk / drive) is configured the same way. One running OSRM
    server per profile: foot for walk, car for drive. On a 16 GB RAM
    machine, run them sequentially (foot server -> walk pipeline -> stop
    foot -> car server -> drive pipeline), not concurrently.
Created: 13/05/2026
Author: tommycollins1 (trc207)
Notes:
    input:  origins (LSOA pop-weighted centroids), destinations (greenspace
            access points), running OSRM server at OSRM_URL.
    output: distances_final.parquet (per access point) and optionally
            distances_per_site.parquet (per decomposed union polygon).
-------------------------------------------------------------------------------
"""
