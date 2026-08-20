"""
Smoke test: every module imports without side effects. Catches the class of
bug where a stale `from src.data.X` import (or a missing dependency) breaks
the repo on a fresh checkout.

Run:
    pytest tests/
"""
import importlib

MODULES = [
    # cfgs (import-time path resolution)
    "src.get_geography.cfg",
    "src.get_greenspace.cfg",
    "src.get_network_england_osrm.cfg",
    "src.get_network_oxford_osmnx.cfg",

    # OSRM pipeline
    "src.get_network_england_osrm.loaders",
    "src.get_network_england_osrm.osrm_client",
    "src.get_network_england_osrm.compute_distances",
    "src.get_network_england_osrm.collapse_to_site",

    # osmnx pipeline
    "src.get_network_oxford_osmnx.snap",
    "src.get_network_oxford_osmnx.graph",
    "src.get_network_oxford_osmnx.routing",
    "src.get_network_oxford_osmnx.compute_distances",
    "src.get_network_oxford_osmnx.collapse_to_site",
    "src.get_network_oxford_osmnx.shortest_path",

    # greenspace assembly
    "src.get_greenspace.greenspace_union",
    "src.get_greenspace.greenspace_access_union",
]


def test_all_modules_importable():
    """Every listed module should import cleanly."""
    for name in MODULES:
        importlib.import_module(name)
