"""
-------------------------------------------------------------------------------
Title: get_network_oxford_osmnx
Description: Oxford case-study routing pipeline using osmnx + networkx.
    Companion to get_network_england_osrm/, which uses OSRM at England scale.
    Both engines share the same input artefacts and produce the same output
    schema, so their per-(origin, dest) travel times are directly comparable
    and the pair serves as the cross-engine technical validation for the
    data descriptor.

    Reformalisation of the earlier src/data/get_network/ scripts:
      - Single distance-only script chain -> mode-parameterised (walk, drive)
        pipeline mirroring the OSRM module's shape.
      - Loose scripts with `if __name__ == '__main__':` bodies -> importable
        functions per file, trip wire lives on _run_ only.
      - Ambiguous cfg naming (directory used as filename) -> clean split into
        *_DIR (directories) and *_FINAL (concat parquets).
      - Old destinations (OX_ASSEMBLE_GREENSPACE, no designation flags) ->
        OX_GREENSPACE_ACCESS_UNION as default (designation-aware, matches
        OSRM). Legacy toggle available for reproducing the historical
        Oxford outputs verbatim.

    Nothing in src/data/get_network/ is modified; the two coexist.
Created: 13/05/2026
Author: tommycollins1 (trc207)
Notes:
    input:  LSOA pop-weighted centroids, OX_GREENSPACE_ACCESS_UNION,
            Oxford + Cherwell LAD clip, mode profile (walk / drive).
    output: distances_final.parquet (per access point) and, optionally,
            distances_per_site.parquet (per site) per mode.
-------------------------------------------------------------------------------
"""
