# pag-greenspace-net-travel

[![Code DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22028407.svg)](https://doi.org/10.5281/zenodo.22028407)
[![Dataset DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22013904.svg)](https://doi.org/10.5281/zenodo.22013904)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)

Routing pipeline used to build **GreenRoute** — a national dataset of Lower Super Output Area (LSOA) walking and driving network travel times to nearest accessible greenspace across England.

The **dataset** is deposited on Zenodo: <https://doi.org/10.5281/zenodo.22013904>.
This **code repository** has its own DOI: <https://doi.org/10.5281/zenodo.22028407>.
The accompanying **data descriptor** has been submitted to *Scientific Data*.

## What this code does

Given the Office for National Statistics' 2021 population-weighted LSOA centroids as origins, and Natural England's Accessible Green Infrastructure (AGI) access nodes as destinations (with SSSI/SAC/SPA/Ramsar overlaps preserved via a designation-aware polygon union), the pipeline computes network travel times under a 20-minute threshold, in two modes:

- **Walking** — via the OSRM `foot.lua` profile.
- **Driving** — via the OSRM `car.lua` profile.

Both modes route against a single England-wide OpenStreetMap graph, which eliminates the boundary-edge artefacts seen in tiled routing implementations. Outputs are provided per-access-point (primary) and per-site (derived by keeping the closest access point per LSOA-site pair).

A parallel `osmnx` + `networkx` pipeline is included for cross-engine validation over an Oxford + Cherwell case-study region.

## Repository structure

```
main_config.py                          # central path config (env-var overrides)
src/
  get_geography/                        # LAD boundaries used as clip masks
  get_greenspace/                       # AGI + SSSI + SAC + SPA + Ramsar prep,
                                        #   union, access-point join
  get_network_england_osrm/             # primary OSRM pipeline (walk + drive)
  get_network_oxford_osmnx/             # osmnx + networkx cross-validation pipeline
scripts/                                # (empty; add local scratch here)
examples/                               # example loaders + queries against the deposit
tests/                                  # unit + smoke tests
environment.yml, pyproject.toml         # conda + pip package specs
CITATION.cff                            # machine-readable citation
LICENSE                                 # MIT
```

Each module carries its own `README.md` with input paths, run order, and output schema.

## Requirements

- **Python 3.12+**
- **Docker** (for the OSRM server; foot + car profiles preprocessed once)
- **16 GB RAM minimum** (OSRM foot server: ~3–5 GB; car: ~6–10 GB; run one at a time on 16 GB)

## Installation

Recommended: conda (avoids native-lib pain with GeoPandas / Fiona / pyproj on Windows):

```bash
conda env create -f environment.yml
conda activate pag-greenspace-net-travel
```

Or pip (may require system-level GDAL/GEOS):

```bash
pip install -e .
```

## Data (not committed)

The pipeline consumes ~8 input datasets from ONS and Natural England. They are **not** committed to this repo (too large; original sources are the canonical hosts). Download them and either:

- place them under `./data/` matching the default paths in `main_config.py`, **or**
- set `PAG_DATA_ROOT` (or per-file env vars) to point at your local layout.

See `main_config.py` for the full list of expected filenames and env-var overrides.

**Sources:**

| Input | Source |
|---|---|
| LSOA 2021 population-weighted centroids (EW V4) | <https://geoportal.statistics.gov.uk> |
| LSOA / LAD / county boundaries | <https://geoportal.statistics.gov.uk> |
| Accessible Green Infrastructure (AGI) polygons and access nodes | <https://naturalengland-defra.opendata.arcgis.com> |
| SSSI, SAC, SPA, Ramsar polygons | <https://naturalengland-defra.opendata.arcgis.com> |
| OpenStreetMap PBF (England extract) | <https://download.geofabrik.de/europe/united-kingdom/england.html> |

Output data are on Zenodo — see below.

## Running the pipeline

Full pipeline is **inputs → destinations → routing → deposit**. Set env vars for your input paths, then:

**1. Build the destinations layer** (union polygons + access-point join):

```bash
python -m src.get_greenspace.assemble_greenspace
python -m src.get_greenspace.greenspace_union
python -m src.get_greenspace.greenspace_access_union
```

**2. Preprocess OSRM graphs** — one-off per profile per OSM snapshot. See `src/get_network_england_osrm/README.md` for the exact `docker run osrm-extract / osrm-partition / osrm-customize` commands (Windows PowerShell format included).

**3. Start the OSRM server for the mode you're routing:**

```bash
# walk:
docker run --rm -d --name osrm-foot -p 5000:5000 -v ${PWD}:/data osrm/osrm-backend osrm-routed --algorithm mld --max-table-size 100 /data/england-260517-foot.osrm
# drive (stop the foot server first on 16 GB):
docker run --rm -d --name osrm-car  -p 5001:5000 -v ${PWD}:/data osrm/osrm-backend osrm-routed --algorithm mld --max-table-size 100 /data/england-260517-car.osrm
```

**4. Run the routing pipeline** (checkpointed, resumable, threaded):

```bash
VISAGE_MODE=walk  python -m src.get_network_england_osrm._run_get_network_england_osrm
VISAGE_MODE=drive python -m src.get_network_england_osrm._run_get_network_england_osrm
```

Full England walk finishes in ~30–90 minutes; drive is longer (a few hours on a laptop with 8 workers). The per-mode outputs land at `PROCESSED/get_network_england_osrm/<mode>/distances_final.parquet` and `distances_per_site.parquet`.

**5. Cross-engine validation** (Oxford + Cherwell case study):

```bash
VISAGE_MODE=walk  python -m src.get_network_oxford_osmnx._run_get_network_oxford_osmnx
VISAGE_MODE=drive python -m src.get_network_oxford_osmnx._run_get_network_oxford_osmnx
```

Deposits Spearman rank correlations of walk ρ=0.93 and drive ρ=0.96 against the OSRM outputs.

## Example: load the deposited data

Once you've downloaded the archive from Zenodo:

```python
import geopandas as gpd
import pandas as pd

# Walking travel time to nearest greenspace, per LSOA
walk = pd.read_parquet("deposit/distances/walk/distances_per_site.parquet")

# Join to LSOA centroids for mapping
origins = gpd.read_parquet("deposit/origins/lsoa_centroids.parquet")
walk_geo = origins.merge(walk, on="origin_id", how="inner")

# Walk-drive gap per (LSOA, site)
drive = pd.read_parquet("deposit/distances/drive/distances_per_site.parquet")
gap = walk.merge(
    drive[["origin_id", "site_id", "travel_time_s"]],
    on=["origin_id", "site_id"],
    suffixes=("_walk", "_drive"),
)
gap["walk_minus_drive_s"] = gap["travel_time_s_walk"] - gap["travel_time_s_drive"]
```

See `examples/` for a runnable script.

## Citation

**Dataset (please cite):**

> Collins, T. (2026). *GreenRoute: Pedestrian and Driving Network Travel Times to Greenspace for Lower Super Output Areas in England* [Data set]. Zenodo. <https://doi.org/10.5281/zenodo.22013904>

**Descriptor paper (once accepted):**

> Collins, T. et al. (2026). *Pedestrian and Driving Network Distances to Greenspace for Lower Super Output Areas in England*. Manuscript submitted to *Scientific Data*.

`CITATION.cff` provides the machine-readable citation — GitHub renders a "Cite this repository" button from it.

## License

- **Code:** MIT — see [LICENSE](LICENSE).
- **Data (on Zenodo):** Creative Commons Attribution 4.0 International (CC BY 4.0).

Underlying inputs carry their own upstream licences: OpenStreetMap © OSM contributors under ODbL; Natural England and ONS layers under the Open Government Licence v3.0.

## Acknowledgements

Produced as part of the **Planning Access to Greenspace (PAG)** project, commissioned by **Natural England**.
