"""
-------------------------------------------------------------------------------
Title: ""
Description: ""
Created: 18/02/2026
Author: tommycollins1 (trc207)
Notes:
    input:
    output:
-------------------------------------------------------------------------------
"""
from pathlib import Path
from typing import Final

from main_config import PROCESSED

GET_GEOGRAPHY: Final[Path] = PROCESSED / "get_geography"

# =============================================================================
# BUFFER LAD
# =============================================================================

LAD_BFC_2024_BUFF: Final[Path] = GET_GEOGRAPHY / "buffer_lad.gpkg"
OX_LAD_2024_BUFF: Final[Path] = GET_GEOGRAPHY / "ox_buffer_lad.gpkg"

# =============================================================================
# URBAN RURAL
# =============================================================================

OX_URBAN_RURAL: Final[Path] = GET_GEOGRAPHY / "ox_urban_rural.gpkg"
ENG_URBAN_RURAL: Final[Path] = GET_GEOGRAPHY / "eng_urban_rural.gpkg"

# =============================================================================
# LAD TO LSOA
# =============================================================================

ALL_LAD_TO_LSOA: Final[Path] = GET_GEOGRAPHY / "all_lad_to_lsoa.gpkg"
OXF_LAD_TO_LSOA: Final[Path] = GET_GEOGRAPHY / "oxford_lad_to_lsoa.gpkg"

# =============================================================================
# LAD TO POSTCODE
# =============================================================================

ALL_LAD_TO_POSTCODE: Final[Path] = GET_GEOGRAPHY / "all_lad_to_postcode.gpkg"
OXF_LAD_TO_POSTCODE: Final[Path] = GET_GEOGRAPHY / "oxford_lad_to_postcode.gpkg"
