"""
-------------------------------------------------------------------------------
Title: main_config
Description: Central path configuration for the pipeline. Every module reads
    input filepaths and the output root (`PROCESSED`) from this file, so a
    fresh checkout only needs one thing configured -- the local root where
    the input datasets live.

    Two environment variables control everything:

      PAG_DATA_ROOT     -- root folder containing the downloaded input datasets
                           (LSOA centroids, AGI, SSSI, SAC, SPA, Ramsar, LAD
                           boundaries). Default: ./data at the repo root.
      PAG_PROCESSED     -- root folder where pipeline outputs are written.
                           Default: ./processed at the repo root.

    Individual paths (LSOA_POP_WEIGHTED_CENTROIDS_2021, AGI_GI, ...) can be
    overridden separately with matching env vars if inputs are stored on a
    different disk or under different filenames. See the block at the bottom
    for the full list of override names.

    Where to get the input files:
      https://geoportal.statistics.gov.uk          -- ONS boundaries + centroids
      https://naturalengland-defra.opendata.arcgis.com  -- AGI, SSSI, SAC, SPA, Ramsar
      https://download.geofabrik.de/europe/united-kingdom/england.html  -- OSM PBF

    See README.md for the exact filenames expected under PAG_DATA_ROOT.
Created: 2026-08-19
Author: tommycollins1 (trc207)
-------------------------------------------------------------------------------
"""
import os
from pathlib import Path


# =============================================================================
# ROOTS
# =============================================================================
# Everything else derives from these. Override with env vars for a custom
# layout; otherwise sensible defaults point to ./data and ./processed under
# the repo root.

REPO_ROOT: Path = Path(__file__).resolve().parent

DATA_ROOT: Path = Path(os.environ.get("PAG_DATA_ROOT", REPO_ROOT / "data"))
PROCESSED: Path = Path(os.environ.get("PAG_PROCESSED", REPO_ROOT / "processed"))
FIGURES: Path = Path(os.environ.get("PAG_FIGURES", REPO_ROOT / "figures"))


# =============================================================================
# ONS BOUNDARY + CENTROID INPUTS
# =============================================================================
# Download from https://geoportal.statistics.gov.uk. Filenames below are the
# ONS defaults; if you renamed on download, either rename to match or set the
# matching env var (see block at bottom).

LSOA_POP_WEIGHTED_CENTROIDS_2021: Path = Path(os.environ.get(
    "PAG_LSOA_POP_WEIGHTED_CENTROIDS_2021",
    DATA_ROOT / "ons" / "LSOA_Dec_2021_PWC_EW_V4.gpkg",
))

LSOA_POLYS_2024: Path = Path(os.environ.get(
    "PAG_LSOA_POLYS_2024",
    DATA_ROOT / "ons" / "LSOA_2024_BFC.gpkg",
))

LAD_BFC_2024: Path = Path(os.environ.get(
    "PAG_LAD_BFC_2024",
    DATA_ROOT / "ons" / "LAD_Dec_2024_BFC_UK.gpkg",
))

COUNTIES_2021: Path = Path(os.environ.get(
    "PAG_COUNTIES_2021",
    DATA_ROOT / "ons" / "Counties_and_Unitary_Authorities_Dec_2021.gpkg",
))

UK_COUNTRIES_BFE_2023: Path = Path(os.environ.get(
    "PAG_UK_COUNTRIES_BFE_2023",
    DATA_ROOT / "ons" / "Countries_Dec_2023_BFE.gpkg",
))

URBAN_RURAL_CLASS_2021: Path = Path(os.environ.get(
    "PAG_URBAN_RURAL_CLASS_2021",
    DATA_ROOT / "ons" / "RUC_2021_LSOA.csv",
))


# =============================================================================
# NATURAL ENGLAND -- ACCESSIBLE GREEN INFRASTRUCTURE + PROTECTED SITES
# =============================================================================
# All from https://naturalengland-defra.opendata.arcgis.com.

AGI_GI: Path = Path(os.environ.get(
    "PAG_AGI_GI",
    DATA_ROOT / "natural_england" / "Accessible_Green_Infrastructure.gpkg",
))

AGI_ACCESS_NODES_GI: Path = Path(os.environ.get(
    "PAG_AGI_ACCESS_NODES_GI",
    DATA_ROOT / "natural_england" / "AGI_Access_Nodes.gpkg",
))

ALL_AGI_GI: Path = Path(os.environ.get(
    "PAG_ALL_AGI_GI",
    DATA_ROOT / "natural_england" / "AGI_all.gpkg",
))

# Protected sites: SSSI, SAC, SPA, Ramsar. The pipeline reads them by dataset
# key from the dict below so adding a new designation is a one-line change.
PROTECTED_SITES_DICT: dict[str, Path] = {
    "sssi":   Path(os.environ.get(
        "PAG_SSSI_ENGLAND",
        DATA_ROOT / "natural_england" / "SSSI_England.gpkg",
    )),
    "sac":    Path(os.environ.get(
        "PAG_SAC_ENGLAND",
        DATA_ROOT / "natural_england" / "SAC_England.gpkg",
    )),
    "spa":    Path(os.environ.get(
        "PAG_SPA_ENGLAND",
        DATA_ROOT / "natural_england" / "SPA_England.gpkg",
    )),
    "ramsar": Path(os.environ.get(
        "PAG_RAMSAR_ENGLAND",
        DATA_ROOT / "natural_england" / "Ramsar_England.gpkg",
    )),
}


# =============================================================================
# LAD SELECTIONS
# =============================================================================
# The Oxford + Cherwell case-study region used for cross-engine validation
# (osmnx pipeline). Add new entries here to define alternative case-study
# regions; the pipeline reads whichever set is referenced from cfg.py.

LAD_SELECTIONS: dict[str, list[str]] = {
    "oxford_plus_cherwell": [
        "E07000178",  # Oxford
        "E07000177",  # Cherwell
    ],
}


# =============================================================================
# ENV VAR OVERRIDES REFERENCE
# =============================================================================
#   PAG_DATA_ROOT                        -- root of downloaded input datasets
#   PAG_PROCESSED                        -- pipeline output root
#   PAG_FIGURES                          -- figure output root
#   PAG_LSOA_POP_WEIGHTED_CENTROIDS_2021 -- ONS pop-weighted centroids EW V4
#   PAG_LSOA_POLYS_2024                  -- ONS LSOA polygons 2024 BFC
#   PAG_LAD_BFC_2024                     -- ONS LAD boundaries 2024 BFC
#   PAG_COUNTIES_2021                    -- ONS counties/unitaries 2021
#   PAG_UK_COUNTRIES_BFE_2023            -- ONS countries BFE 2023
#   PAG_URBAN_RURAL_CLASS_2021           -- ONS rural-urban classification LSOA
#   PAG_AGI_GI                           -- Natural England AGI polygons
#   PAG_AGI_ACCESS_NODES_GI              -- Natural England AGI access nodes
#   PAG_ALL_AGI_GI                       -- Natural England full-AGI extract
#   PAG_SSSI_ENGLAND                     -- Natural England SSSI
#   PAG_SAC_ENGLAND                      -- Natural England SAC
#   PAG_SPA_ENGLAND                      -- Natural England SPA
#   PAG_RAMSAR_ENGLAND                   -- Natural England Ramsar
# =============================================================================


# On import: ensure output directories exist (harmless if already present).
for _p in (PROCESSED, FIGURES):
    _p.mkdir(parents=True, exist_ok=True)
