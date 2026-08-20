# get_network_england_osrm

OSRM-backed routing pipeline. Companion to `get_network_england/` (which uses osmnx + networkx with a tiled architecture). This module is the recommended engine for any England-scale work — walking *and* driving — and is what the data paper should describe.

## What it produces

`distances_final.parquet` and `distances_per_site.parquet` under `PROCESSED / get_network_england_osrm / <mode> /`. Same schema as the tiled module, plus two extra columns: `origin_snap_m` and `dest_snap_m`, the distances OSRM had to snap the origin and destination to the nearest routable node. Useful for QA — large snap distances flag points that aren't on the road/path network and whose travel times may be inflated.

## What it changes versus get_network_england/

The tiling architecture disappears entirely. There's one OSRM server holding an England-wide preprocessed graph in memory, and the pipeline loops over origins, queries `/table` for each one's spatial-candidate destinations, filters to threshold, and writes. No tile manifest, no per-tile graph cache, no merge step. The pipeline is ~300 lines versus ~600.

OSRM is essentially always-on infrastructure — once preprocessed and started, queries are sub-millisecond. The cost moves from "long routing run" to "one-off Docker preprocessing" (~30–60 min per profile).

## Cross-validation with get_network_england/

Both engines write to `PROCESSED/<engine>/<mode>/distances_final.parquet`. A validation run over the Oxford + Cherwell test region (walk mode) produced the following results:

- Overall Spearman ρ = 0.92 on travel time
- Per-LSOA site-ranking agreement: median ρ = 0.97, with 75% of LSOAs above ρ = 0.9
- 71% of shared pairs within 60 s, 84% within 120 s
- OSRM found 937 additional origin–site pairs not present in the tiled output, likely due to the absence of tile boundary artefacts

OSRM returns systematically shorter travel times (mean −60 s, median −34 s) because `foot.lua` assigns road-type-specific speeds rather than a uniform 4.8 km/h. Both engines rank sites consistently — the difference is in absolute times, not ordering. OSRM is the preferred engine for production runs.

## One-off setup

These steps are done once per machine. Re-run the preprocessing only when you want to refresh the OSM snapshot (quarterly is reasonable).

### 1. Docker Desktop + WSL2

Install Docker Desktop from https://docker.com. On Windows, Docker Desktop uses WSL2 as its backend — enable WSL2 if prompted during installation.

**WSL2 memory limit (required for England-scale preprocessing)**

By default WSL2 on a 16 GB machine allocates only ~8 GB to Docker. England-scale OSRM extract peaks at ~11 GB RAM. You must raise the limit before preprocessing or extract will crash partway through.

Create (or edit) `C:\Users\<you>\.wslconfig`:

```ini
[wsl2]
memory=12GB
swap=8GB
processors=4
```

Then restart WSL2 from PowerShell:

```powershell
wsl --shutdown
```

Restart Docker Desktop afterwards.

**Confirm Docker is working**

Make sure Docker Desktop is open and showing "Engine running" (green dot, bottom-left). Then in PowerShell:

```powershell
docker run --rm hello-world
```

### 2. Install routingpy

Use pip — the conda-forge build conflicts with shapely ≥ 2 (required by pyrosm):

```powershell
pip install routingpy
```

If on a university VPN, disconnect first — VPNs commonly block or throttle PyPI connections.

### 3. Preprocess the PBF, twice (foot + car)

The PBF is at `data/geographic_areas/england-260517.osm.pbf` (set `VISAGE_PBF_PATH` if you move it).

**Before running:** pause OneDrive sync (right-click tray icon → Pause syncing → 24 hours). OneDrive interferes with large concurrent file writes and can cause extract to fail silently.

Open PowerShell and `cd` to the directory containing the PBF:

```powershell
cd "C:\path\to\data\geographic_areas"
```

Run the three steps for each profile in order, waiting for each to finish before the next. Note: PowerShell does not support backslash line continuation — each command must be on one line.

**Foot profile:**

```powershell
docker run --rm -t -v ${PWD}:/data osrm/osrm-backend osrm-extract -p /opt/foot.lua /data/england-260517.osm.pbf
```
*(20–40 min, peaks at ~11 GB RAM)*

```powershell
docker run --rm -t -v ${PWD}:/data osrm/osrm-backend osrm-partition /data/england-260517.osrm
```

```powershell
docker run --rm -t -v ${PWD}:/data osrm/osrm-backend osrm-customize /data/england-260517.osrm
```

Rename the foot outputs so the car preprocessing does not overwrite them:

```powershell
mv england-260517.osrm england-260517-foot.osrm
Get-ChildItem -Filter "england-260517.osrm.*" | Rename-Item -NewName { $_.Name -replace "england-260517\.osrm\.", "england-260517-foot.osrm." }
```

Confirm with `ls *.osrm*` before continuing.

**Car profile:**

```powershell
docker run --rm -t -v ${PWD}:/data osrm/osrm-backend osrm-extract -p /opt/car.lua /data/england-260517.osm.pbf
```
*(20–40 min, peaks at ~7 GB RAM)*

```powershell
docker run --rm -t -v ${PWD}:/data osrm/osrm-backend osrm-partition /data/england-260517.osrm
```

```powershell
docker run --rm -t -v ${PWD}:/data osrm/osrm-backend osrm-customize /data/england-260517.osrm
```

Rename the car outputs:

```powershell
mv england-260517.osrm england-260517-car.osrm
Get-ChildItem -Filter "england-260517.osrm.*" | Rename-Item -NewName { $_.Name -replace "england-260517\.osrm\.", "england-260517-car.osrm." }
```

**Disk:** foot + car outputs together are ~15–20 GB. Consider storing on an external drive. The files load into RAM at server startup so drive read speed matters only at launch, not during routing.

**Time:** 20–40 min per profile on a typical laptop.

### 4. Run the OSRM server

**16 GB RAM: run one server at a time, not both.** Stop the foot server before starting the car server. The pipeline state is in the parquet outputs, so this is a clean swap.

Start the foot server (for walk):

```powershell
docker run --rm -d --name osrm-foot -p 5000:5000 -v ${PWD}:/data osrm/osrm-backend osrm-routed --algorithm mld --max-table-size 100 /data/england-260517-foot.osrm
```

Confirm it is running:

```powershell
docker ps
```

Wait ~60–90 seconds for the graph to load into RAM, then verify:

```powershell
curl http://localhost:5000/route/v1/foot/-1.5,50.9;-1.4,51.0
```

You should receive a JSON response. An empty reply means the server is still loading — wait and retry.

When walk is done, stop and start the car server:

```powershell
docker stop osrm-foot
docker run --rm -d --name osrm-car -p 5001:5000 -v ${PWD}:/data osrm/osrm-backend osrm-routed --algorithm mld --max-table-size 100 /data/england-260517-car.osrm
```

Note port 5001 → container port 5000. The `cfg.py` `MODE_PROFILES` already expects walk on 5000 and drive on 5001.

**After a reboot:** Docker containers do not persist across restarts. `cd` to wherever the `.osrm` files live (including on an external drive) and re-run the `docker run` server command above before running the Python pipeline.

MLD ("Multi-Level Dijkstra") is the recommended algorithm. CH ("Contraction Hierarchies") uses less RAM but does not support the `/table` endpoint well with per-query customisation. MLD on England-foot fits in ~3–5 GB; England-car ~6–10 GB.

`--max-table-size 100` matches `TABLE_BATCH_SIZE` in `cfg.py`. If you raise the server-side limit (more RAM cost) you can raise the batch size to send fewer larger calls per origin.

## Running the pipeline

Set `VISAGE_MODE=walk` (or `drive`) as an environment variable (in PyCharm: Run → Edit Configurations → Environment variables). Confirm the right OSRM server is running, then:

```python
from src.data.get_network_england_osrm._run_get_network_england_osrm import main
main(do_collapse=True)
```

The orchestrator calls `compute_distances()` (queries OSRM, writes the per-access-point parquet) and then `collapse_to_site()` (writes the per-site parquet).

**Test region:** `CLIP_TO_TEST_REGION = True` in `cfg.py` restricts the run to Oxford + Cherwell. Set to `False` for a full England run. Full England walk takes 30 min to a few hours depending on hardware.

## Output schema

Per-access-point (`distances_final.parquet`):

| column | dtype | meaning |
|---|---|---|
| `origin_id` | str | LSOA21CD |
| `dest_id` | str | access point id (`ap_NNNNNNN`) |
| `site_id` | int | decomposed union polygon id |
| `travel_time_s` | float32 | OSRM travel time, seconds |
| `dist_m` | float32 | OSRM route distance, metres |
| `mode` | str | `walk` or `drive` |
| `has_agi`, `has_sssi`, `has_sac`, `is_protected` | bool | inherited from union polygon |
| `designation_count` | int32 | from union polygon |
| `origin_snap_m` | float32 | how far OSRM snapped the LSOA centroid to its network |
| `dest_snap_m` | float32 | how far OSRM snapped the access point to its network |

Per-site (`distances_per_site.parquet`): same columns; `dest_id` records which specific access point won the min-time tie for each (origin, site) pair.

## Why MLD over CH

CH bakes assumptions about edge weights into the preprocessed graph and does not support sources/destinations filtering on `/table` well. MLD lets you compute customisable weights at query time, which is what the `/table` endpoint relies on. RAM cost is a bit higher (~3–5 GB foot, ~6–10 GB car for England) but on 16 GB with a single server at a time it is fine.

## Limitations

The 100-coordinate `/table` limit means an origin with 500 candidate destinations needs 5 OSRM calls. Each call is fast (sub-second), but at England-walk scale (~33k LSOAs × ~10–30 candidates each) you will do ~100k–300k `/table` calls per mode. Expect 30 min to a few hours of wall-clock per mode. Still vastly faster than the tiled approach.

OSRM's `foot.lua` is uniform walking — no slope correction, no surface penalties. If that matters for your analysis, swap to a customised Lua profile and re-preprocess.

No isochrone semantics: pairs above `threshold_s` are filtered post-hoc rather than excluded at query time. OSRM's `/table` does not take a cutoff parameter natively. Network cost is essentially the same since OSRM computes the full one-to-many matrix per call regardless.