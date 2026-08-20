# get_network_oxford_osmnx

Oxford case-study routing pipeline using osmnx + networkx. Sibling module to `get_network_england_osrm/` — same inputs, same output schema, different engine — and the pair together forms the cross-engine technical validation for the data descriptor.

Also a reformalisation of the earlier `src/data/get_network/` scripts. The original module is left untouched; nothing here modifies it.

## Why this module exists

Two reasons:

**Cross-engine validation.** For the Scientific Data paper to make a defensible claim that OSRM's foot/car profiles produce sensible accessibility distances, we need a second independent implementation to compare against on the same inputs. osmnx + networkx built the graph and ran the Dijkstra loop in the historical Oxford work; using it against identical origins and destinations, on the same LAD selection, with the same threshold and the same walking speed, gives a per-(origin, dest) diff that measures pure engine-vs-engine agreement.

**Historical reproducibility.** The original `get_network/` output has been used in earlier PAG work. Setting `VISAGE_LEGACY_DESTINATIONS=1` switches destinations back to `OX_ASSEMBLE_GREENSPACE` (pre-union) and preserves `park_dataset` / `park_class` columns so the historical outputs can be regenerated verbatim.

## What it produces

Two parquet outputs per run, under `PROCESSED / "get_network_oxford_osmnx" / <mode> /`:

- `distances_final.parquet` — one row per (origin, access point) within the threshold. Same schema as `get_network_england_osrm/distances_final.parquet` so the two are directly diffable on `(origin_id, dest_id)`.
- `distances_per_site.parquet` — the same rows collapsed to (origin, site) by the minimum travel time.

Legacy runs write to `distances_final_legacy.parquet` / `distances_per_site_legacy.parquet` so they never overwrite the primary outputs.

Optionally: `shortest_paths.parquet` (route geometries as LineStrings, for map visualisations) via `shortest_path.py`.

## Mode

`VISAGE_MODE` env var picks walk or drive. Both use a 20-minute threshold.

| | walk | drive |
|---|---|---|
| `network_type` | `walk` | `drive` |
| Dijkstra weight | `length` (m) | `travel_time` (s) |
| Cutoff | `1200 s * 4.8 km/h / 3600 = 1600 m` | `1200 s` |
| Output `travel_time_s` | `length / walk_speed_mps` | Dijkstra weight direct |
| Output `dist_m` | Dijkstra weight direct (exact) | approximate (`travel_time_s * 13.4 m/s`) |

Walk speed is uniform at 4.8 km/h, matching what OSRM's `foot.lua` uses conceptually. Drive uses `osmnx.add_edge_speeds` + `osmnx.add_edge_travel_times`, which infer per-edge speeds from OSM `maxspeed` tags with per-highway-class fallbacks — the same approach OSRM's `car.lua` follows.

## Setup

Only Python packages. No Docker needed for this engine.

```
conda install -c conda-forge osmnx networkx geopandas joblib tqdm pyarrow
```

The graph is downloaded via osmnx's Overpass API the first time you run either mode, then cached to `graph.graphml` under the mode's output folder. Subsequent runs load from the cache and skip the network fetch.

## Running

Same debugger-driven pattern as the other modules. Skip the trip wire at the top of `_run_get_network_oxford_osmnx.py` and call `main()`:

```
# Walk
main()

# Drive
# VISAGE_MODE=drive at the shell, then:
main()

# Legacy Oxford reproduction (walk only, pre-union destinations)
# VISAGE_LEGACY_DESTINATIONS=1 at the shell, then:
main()
```

Each mode writes to its own sub-directory so runs don't collide.

The pipeline is resumable: destinations completed in a previous run are skipped via the per-mode `progress.csv`. Delete `progress.csv` and the `batches/` directory to force a full re-run.

## Cross-engine comparison

The two engines' primary outputs are directly join-able on `(origin_id, dest_id)`. Recommended pattern for the data paper:

```
walk_osmnx = pd.read_parquet(PROCESSED / "get_network_oxford_osmnx/walk/distances_final.parquet")
walk_osrm  = pd.read_parquet(PROCESSED / "get_network_england_osrm/walk/distances_final.parquet")

merged = walk_osmnx.merge(
    walk_osrm[["origin_id", "dest_id", "travel_time_s"]],
    on=["origin_id", "dest_id"],
    suffixes=("_osmnx", "_osrm"),
    how="inner",
)

merged["delta_s"] = merged["travel_time_s_osmnx"] - merged["travel_time_s_osrm"]
```

The Spearman rank correlation on `travel_time_s` should be near 1 for walk mode (both engines are effectively uniform-speed pedestrian routing on the same underlying OSM data), with small differences attributable to how OSRM's `foot.lua` handles specific edge tag combinations. Repeat for drive mode.

## Files

`cfg.py` — mode profiles, paths, LAD selection (Oxford + Cherwell), legacy toggle, walking speed.

`graph.py` — study area polygon from LAD selection, graph fetch via `ox.graph_from_polygon`, projection to BNG, `travel_time` annotation for drive, graphml cache.

`snap.py` — snap origins/destinations to nearest graph node, record snap distance for QA.

`routing.py` — `process_destination` runs single-source Dijkstra from one destination and returns reachable (origin, dest) rows in the shared schema. Also the batch parquet + progress CSV helpers.

`compute_distances.py` — end-to-end pipeline function. Handles input loading, snapping, joblib-parallel Dijkstra per batch with checkpointing, and the final concat into `distances_final.parquet`.

`collapse_to_site.py` — optional min-per-(origin, site) collapse.

`shortest_path.py` — optional route geometry writer (LineStrings).

`_run_get_network_oxford_osmnx.py` — orchestrator; trip wire lives here only.

## Design notes worth documenting for the paper

- **Per-destination Dijkstra, not per-origin.** In a small graph with many destinations and fewer origins (Oxford + Cherwell: ~600 LSOAs, ~thousands of access points), routing per destination and mapping back to origins is what osmnx historically did in `get_network/`. It's a reasonable choice at Oxford scale even if it's the wrong choice at England scale. Preserved for continuity.
- **Cutoff in native weight units.** For walk we translate the 20-minute threshold into a metre cutoff via `WALK_SPEED_MPS`; for drive we pass 1200 seconds directly. This keeps the Dijkstra call efficient in either mode.
- **Postcodes dropped.** The historical `get_network/` also routed to postcode centroids as a second origin type. That's unnecessary for the paper's LSOA-level accessibility analysis and would bloat the output; dropped in the reformalisation. If postcode-level routing is needed for a later analysis, it's a small addition against the same graph.
- **No boundary-edge artefact by construction.** This module fetches a single graph for the entire Oxford + Cherwell area and routes against it. The boundary-edge issue that motivated the England pipeline's tiling architecture doesn't arise at this scale.
