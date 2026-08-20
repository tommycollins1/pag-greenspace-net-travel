"""
-------------------------------------------------------------------------------
Title: _run_get_network_oxford_osmnx
Description: Driver for the Oxford osmnx routing pipeline. Runs:
      1. compute_distances (load cached graph or fetch, load inputs, snap,
         Dijkstra per destination with checkpointing, concat batches).
      2. optional collapse_to_site.

    Re-runs are safe: the graph cache is reused, and per-destination
    checkpointing in progress.csv skips already-processed dests.
Created: 13/05/2026
Author: tommycollins1 (trc207)
Notes:
    input:  origins, destinations, graph -- all handled inside
            compute_distances().
    output: DISTANCES_FINAL and DISTANCES_PER_SITE parquets.
-------------------------------------------------------------------------------
"""
from src.get_network_oxford_osmnx.collapse_to_site import collapse_to_site
from src.get_network_oxford_osmnx.compute_distances import (
    compute_distances,
)


def main(do_collapse: bool = True):
    df = compute_distances()
    if do_collapse:
        collapse_to_site()
    return df


# ----------------------------------------------------------------------- Run -
if __name__ == '__main__':
    def debug_pause(msg): input(msg)  # inlined for public repo

    debug_pause("Paused. Press Enter to continue...")

    main(do_collapse=True)
