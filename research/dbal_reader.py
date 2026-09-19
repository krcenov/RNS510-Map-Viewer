"""
dbal_reader.py -- documents `dbal/` (disc root, not under `db/`): 5
versioned `DBAL.OUT` files, the actual compiled "Database Abstraction
Layer" that reads every `eeu.*`/`eeuz.*` file this whole project has
spent months reverse-engineering. CRACKED at the "what is it, and what
is its real internal source structure" level -- container format (ELF)
fully identified, and an enormous amount of real internal source-file/
class-name/build-history metadata extracted directly from the binary's
own embedded debug strings. NOT disassembled or further reverse-
engineered (no Ghidra/decompilation attempted).

Found via `config/create_cd` (research/create_cd_reader.py). `dbal/
VERSIONS.CFG` lists the 5 version folders present (`V006_047`,
`V007_038`, `V008_704`, `V009_038`, `V010_015`), each holding exactly
one `DBAL.OUT` (1.19-1.33MB) -- one build per supported head-unit
software generation, all reading the SAME on-disc map format.

============================================================================
Container -- CRACKED: 32-bit big-endian PowerPC ELF relocatable objects
============================================================================
All 5 files share the same real ELF header profile (checked via the
standard `\\x7fELF` magic + `e_ident`/`e_type`/`e_machine` fields, no
external tool needed): `EI_CLASS=1` (32-bit), `EI_DATA=2` (big-endian),
`e_type=1` (`ET_REL` -- a relocatable OBJECT file, meant to be linked
into the main firmware image at build/load time, not run standalone),
`e_machine=20` (`EM_PPC`, PowerPC). This directly ties `dbal/` to this
project's own earlier firmware investigation, which already found a
PowerPC native-code region in the main application firmware (README
S2.4) -- DBAL is a real, compiled component of that same PowerPC
codebase, not a separate architecture.

============================================================================
Embedded debug strings -- a genuinely enormous, real source-file /
class-name inventory for the exact format this project reverse-
engineered blind
============================================================================
Every `DBAL.OUT` embeds hundreds of literal internal source file paths
(compiler debug info, not stripped) under a real internal source tree
root `J:\\siemens\\source\\libraries\\dbal\\...` (and
`J:\\siemens\\source\\navicore\\...`). ~330 distinct `.h`/`.cpp` paths
found in `V010_015` alone via a simple printable-ASCII-run scan (no
ELF section parsing needed). A representative, highly informative
sample, matched directly against this project's own already-cracked
(or still-open) `db/` files by name:

    db_road.cpp / db_road_list.cpp / db_road_cache.cpp / db_road_sel_char.cpp
                                     -- eeu.rd / eeuz.rl / eeuz.rt (README S3.1, S3.7)
    db_city.cpp / db_city_sel_char.cpp
                                     -- eeu.cty / eeuz.ct (README S3.8)
    db_county.cpp / db_state.cpp / db_country.cpp
                                     -- eeu.cny / eeu.stt / eeu.ctr (README S3.15/S3.21/S3.11-adjacent)
    db_catalog.cpp / db_catalog_list.cpp
                                     -- eeu.cat / eeu.cal (README S3.14/S3.13)
    db_timeinfo.cpp                 -- eeu.ti (README S3.22)
    db_zone.cpp                     -- zone.cfg
    db_affix.cpp                    -- eeu.aff (README S3.12)
    db_rtype.cpp                    -- eeu.typ (README S3.4)
    db_postalcode.cpp               -- eeu.pol/.pot/.pmm/.pmc/.pmp (README S3.19)
    db_tmc.cpp / db_tmc_deprecated.cpp
                                     -- eeu.tmc (still unopened -- the "_deprecated" twin
                                        suggests the on-disc TMC format changed between
                                        DBAL versions, a real lead for a future session)
    db_intersection.cpp / db_intersection_view.cpp / db_intersectionfirst.cpp
                                     -- eeu.il / eeu.iof (README S3.2/S3.3)
    db_phoneme_catalog.cpp / db_phoneme_city.cpp / db_phoneme_cluster.cpp /
    db_phoneme_road.cpp / db_phoneme_hierarchy.cpp / db_phoneme_intersection.cpp
                                     -- eeuz.pca / eeuz.pct / eeu.pcl / eeuz.prd
                                        (README S3.23/S3.5 (pct)/S3.17/S3.5 (prd)) --
                                        `db_phoneme_intersection.cpp` has no obvious
                                        already-cracked counterpart; a new, real lead
                                        for a phoneme/intersection linkage not yet
                                        investigated.
    db_shape.cpp / db_turn.cpp / db_lane.cpp / db_signpost.cpp / db_slope.cpp /
    db_speed.cpp / db_adas.cpp      -- the MAP_COMPRESSED tile format's own many
                                        sub-feature types (README S3.6), independently
                                        confirming eeu.mod's own "Ordinary Map File"
                                        field list (turn restrictions, lanes, ADAS/truck
                                        speed limits, traffic signs, README S3.16).
    db_page.cpp / db_page_pcl_dir.cpp / db_pclcv.cpp / db_kd.cpp / db_kd_cache.cpp
                                     -- "page"/"pcl_dir" directly names the MAP_COMPRESSED/
                                        eeuz.fea "parcel" concept eeu.mod's own schema
                                        revealed this session (research/feature_reader.py's
                                        "A LATER SESSION's new lead" section); "kd"
                                        independently confirms the "kd_node"/"kd_info"
                                        fields already found in that same schema.
    db_place_hierarchy.cpp / db_place_tree.cpp / db_place_list.cpp / db_place_object.cpp
                                     -- the general place/POI hierarchy (relevant to
                                        EDB/POI/POI.DB3, research/poi_db_reader.py, and
                                        eeuz.fea's own gazetteer role, README S3.10).
    du_find_address_range.cpp / du_find_closest_address.cpp / du_streetname.cpp /
    du_get_road_data.cpp            -- directly relevant to eeuz.prd's newly-cracked
                                        minNumber/maxNumber house-number range (README
                                        S3.5's "prd" entry).
    ZlibDecompressor.cpp / DecompressorFactoryImpl.cpp / zlibdecompressor.h
                                     -- the exact FLAT_COMPRESSED/MAP_COMPRESSED zlib
                                        decompression logic this project already cracked
                                        empirically (research/flat_compressed_reader.py,
                                        map_compressed_reader.py).

**Runtime log-message strings independently CONFIRM an already-
established empirical finding**: `"db_page::update_pnext: element is
already in the hash"` -- directly confirms `eeuz.fea`'s own directory
region really is implemented as a HASH TABLE (not a spatial/sequential
index), exactly matching this project's own hard-won empirical
conclusion (research/feature_reader.py, README S3.10) -- from the
ACTUAL SOURCE CODE'S OWN WORDS, not just external inference.
`"DBMEMMAN: free_pcl(): ... no element found"` uses `pcl` to mean
"parcel" here too, consistent with (not contradicting) `eeu.mod`'s own
schema finding that `pcl_*` fields belong to the tile "parcel" concept,
not `eeu.pcl` ("phoneme cluster list", a same-3-letter but unrelated
name, research/pcl_reader.py).

**A real, dated ClearCase version-control element history** (the same
convention already found in `EDB/POI/POI.DB3`'s own build metadata,
research/poi_db_reader.py) names dozens of individual bug-fix branches
merged into this exact DBAL build, several directly relevant to open
problems elsewhere in this project:

    alle_DbNavRbg3057_vw_split_mp0       -- a fix about SPLITTING eeuz.mp0
    alle_dbal_DbNavRbg3119_house_number_opt
                                          -- a house-number-range optimization,
                                             plausibly related to eeuz.prd's own
                                             minNumber/maxNumber (README S3.5)
    alle_DbNavRbg2825_intersection_roundabout /
    alle_DbNavRbg3065_vw_roundabout_fix  -- roundabout-specific intersection fixes
    alle_tmc_exit_fix                    -- a TMC-specific fix
    alle_suppress_arabic_dynamic         -- Arabic-language handling
    lupa_dbal_DbNavRbg3501_RNS510_wrong_phoneme_Dummy_V10
                                          -- literally names "RNS510" and matches the
                                             "wrong_phoneme_Dummy" branch name already
                                             seen in config/create_cd's own dbal source
                                             path (research/create_cd_reader.py)

============================================================================
NOT done this session
============================================================================
No disassembly, decompilation, or symbol-table (ELF section header)
parsing was attempted -- all findings above came from a plain printable-
ASCII-run scan of the raw file bytes. The 5 versions' own string sets
were not diffed against each other to see exactly which files/fixes
differ between DBAL releases (only `V010_015`, the newest, was scanned
in this pass).

============================================================================
Practical use
============================================================================
This module has no parsing functions. To reproduce the string
extraction: `re.findall(rb"[ -~]{6,}", open(path, "rb").read())` on any
`DBAL.OUT`, no ELF library needed.
"""
