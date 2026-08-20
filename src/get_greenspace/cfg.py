"""
-------------------------------------------------------------------------------
Title: ""
Description: ""
Created: 17/02/2026
Author: tommycollins1 (trc207)
Notes:
    input:
    output:
-------------------------------------------------------------------------------
"""
from pathlib import Path
from typing import Final

from main_config import PROCESSED

GET_GREENSPACE: Final[Path] = PROCESSED / "get_greenspace"

# =============================================================================
# ACCESS POINTS
# =============================================================================

ALL_ACCESS_POINTS: Final[Path] = GET_GREENSPACE / "all_access_points.gpkg"
OX_ACCESS_POINTS: Final[Path] = GET_GREENSPACE / "ox_access_points.gpkg"

# =============================================================================
# ACCESSIBLE GREENSPACE (AGI)
# =============================================================================

ALL_AGI: Final[Path] = GET_GREENSPACE / "all_accessible_gs.gpkg"
OX_AGI: Final[Path] = GET_GREENSPACE / "ox_accessible_gs.gpkg"

# =============================================================================
# PROTECTED SITES (RAW DOWNLOADS)
# =============================================================================

ALL_PROTECTED_SITES: Final[Path] = GET_GREENSPACE / "all_protected_sites.gpkg"
OX_PROTECTED_SITES: Final[Path] = GET_GREENSPACE / "ox_protected_sites.gpkg"
ENGLAND_BUFFER: Final[Path] = GET_GREENSPACE / "eng_land.gpkg"

# =============================================================================
# ASSEMBLE GREENSPACE
# =============================================================================

ALL_ASSEMBLE_GREENSPACE: Final[Path] = (GET_GREENSPACE /
                                        "all_assemble_greenspace.parquet")
OX_ASSEMBLE_GREENSPACE: Final[Path] = (GET_GREENSPACE /
                                       "ox_assemble_greenspace.parquet")

# =============================================================================
# GREENSPACE UNION
# =============================================================================

OX_GREENSPACE_UNION: Final[Path] = (
        GET_GREENSPACE / "ox_greenspace_union.gpkg"
)
OX_SURFACE_GREENSPACE_UNION: Final[Path] = (
        GET_GREENSPACE / "ox_surface_greenspace_union.gpkg"
)
ALL_GREENSPACE_UNION: Final[Path] = (
        GET_GREENSPACE / "all_greenspace_union.gpkg"
)
ENG_SURFACE_GREENSPACE_UNION: Final[Path] = (
        GET_GREENSPACE / "all_surface_greenspace_union.gpkg"
)

# =============================================================================
# GREENSPACE_ACCESS_UNION
# =============================================================================
# Access points joined to decomposed union polygons -- the destinations
# artefact consumed by src/data/get_network_england_osrm.
# England-scale version is the live pipeline output; Oxford version is for
# the Oxford case-study network.

ALL_GREENSPACE_ACCESS_UNION: Final[Path] = (
        GET_GREENSPACE / "all_greenspace_access_union.parquet"
)
OX_GREENSPACE_ACCESS_UNION: Final[Path] = (
        GET_GREENSPACE / "ox_greenspace_access_union.parquet"
)

# =============================================================================
# GREENSPACE_H3
# =============================================================================

# GREENSPACE_H3: Final[Path] = (GET_GREENSPACE /
#                                  f"greenspace_union.gpkg")
# OX_SURFACE_GREENSPACE_UNION: Final[Path] = (GET_GREENSPACE /
#                                          f"surface_greenspace_union.gpkg")
