"""
-------------------------------------------------------------------------------
Title: _run_get_network_england_osrm
Description: Driver for the OSRM-backed routing pipeline. Steps:

      1. Confirm OSRM server reachable at OSRM_URL for the active mode.
      2. Run compute_distances (loads origins/destinations, queries OSRM,
         filters to threshold, writes DISTANCES_FINAL).
      3. Optionally run collapse_to_site to produce the per-site view.

    Re-runs are safe: the existing parquet is overwritten on success, and
    OSRM holds the graph in memory so there's no fetch step to checkpoint.
    If OSRM is down mid-run, it'll fail fast on the next /table call.
Created: 13/05/2026
Author: tommycollins1 (trc207)
Notes:
    input:  origins + destinations + running OSRM server.
    output: DISTANCES_FINAL parquet (+ optional DISTANCES_PER_SITE parquet).
-------------------------------------------------------------------------------
"""
from src.data.get_network_england_osrm.collapse_to_site import collapse_to_site
from src.data.get_network_england_osrm.compute_distances import (
    compute_distances,
)


def main(do_collapse: bool = True):
    df = compute_distances()
    if do_collapse:
        collapse_to_site()
    return df
sgb

# ----------------------------------------------------------------------- Run -
if __name__ == '__main__':
    from project_help.project_level_help import debug_pause

    debug_pause("Paused. Press Enter to continue...")

    main(do_collapse=True)
