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

**CONFIRMED from the FIRMWARE side, a later session** (the user
provided a separate factory firmware disc, `research/
swl_5238_reader.py`): the exact dynamic-loading mechanism this implies
is real and directly readable in the firmware's own `dbaLib` runtime
log strings (`"dbaLib: best matching dbal.out version on DVD:
V%03d_%03d"`, `"now unload DBAL version: V%03d_%03d"`, etc, embedded in
`FHDD6.FLI`) -- the firmware determines which DBAL version the inserted
disc requires, searches `dbal/` for a matching (or best-compatible)
`V0NN_0MM/DBAL.OUT`, and dynamically loads/unloads it as discs are
swapped. This is WHY 5 separate builds ship side by side: real forward/
backward compatibility infrastructure, not redundancy. See that module
for the full picture, including a 77-function catalog of real, versioned
`db_*_V0NN` accessor names (e.g. `db_seg_rank_V004`, `db_tmc_all_
headers_V003`/`_deprecated_V005`) found in the same firmware image.

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
                                     -- eeu.tmc (still unopened). CORRECTED in a later
                                        session's 5-version diff (see below): both files
                                        coexist in ALL 5 DBAL versions, V006_047 through
                                        V010_015 -- this refutes the earlier guess that
                                        "_deprecated" meant the on-disc format changed
                                        between DBAL releases. More likely `db_tmc_
                                        deprecated.cpp` is a legacy/alternate TMC encoding
                                        kept for backward compatibility with older discs,
                                        not a version-gated format change.
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
5-version diff -- CRACKED (a later session): a real, dated architectural
history across DBAL V006_047 -> V007_038 -> V008_704 -> V009_038 ->
V010_015, directly answering "did we check dbal/" with yes -- and finding
a lot that the single-version (V010_015-only) pass above missed.
============================================================================
Per-version printable-string counts (plain `[ -~]{6,}` scan, whole file):
V006_047=4208, V007_038=4405, V008_704=4600, V009_038=4780, V010_015=4802
-- monotonically growing, confirming these are 5 real successive builds,
not 5 unrelated/shuffled ones. Per-version distinct `.cpp`/`.h` basename
counts: 109, 112, 124, 128, 128 (same monotonic growth).

A "first_seen" diff (which version each real source-file basename first
appears in) over the full V006_047 union V010_015 set:

  V006_047 (160 files, baseline) -- not individually diffed, see above.

  V007_038 (+4): corridorroadstorage.h, db_condition.cpp,
    db_postalcode.cpp, db_postalcode.h
    -- `db_postalcode.*` is ADDED here, not present in V006_047 at all --
       postal codes (eeu.pol/.pot/.pmm/.pmc/.pmp, README S3.19) were a
       DBAL V007 feature, absent from the V006 build.

  V008_704 (+36) -- the single biggest jump, and a real architectural
    inflection point:
    - CPhonemeEUHandler.cpp/.h, CPhonemeNAFileReaderHandler.cpp/.h,
      CPhonemeNAFlashFile.cpp/.h, CPhonemeNAFlashHandler.cpp,
      CPhonemeRetrievalInfo.cpp/.h, CPlaceRecordFile.cpp -- see the
      phoneme-handler section below.
    - CCatalogListAllData.cpp/.h, db_catalog_list.h, db_page_int.h
    - A whole "aspect"/"event"/"listener" observer-pattern framework
      appears in one shot: aspect.h, aspectregistry.h,
      aspmodelobjectchangedaspect.h, configurationservicemodelimpl.h,
      displaylanguage.h/displaylanguagechangedaspect.h/...changedevent.h/
      ...changedlistenerproxy.h, unitofmeasurementchanged{aspect,event,
      listenerproxy}.h, voicelanguagechanged{aspect,event,listenerproxy}.h,
      entity.h, modelobject.h, modeltask.h, taskstate.h, mapinclude.h,
      mapjobqueue.h, maploader.h, speedtable.h -- this is a real UI/model
      settings-change notification framework (display language, voice
      language, unit of measurement each get their own aspect+event+
      listener-proxy triple) bolted onto the DBAL/navicore codebase at
      V008_704, alongside a generic `modeltask`/`taskstate` job-queue
      abstraction (`mapjobqueue.h`/`maploader.h`) -- likely the plumbing
      that lets the head unit's settings menu (language, units) propagate
      into the DBAL layer without a restart.

  V009_038 (+25) -- a second clean architectural addition, this time a
    real "navmedia" (navigation media/disc) management subsystem:
    navmediacoverage.h, navmediadbinfo.h, navmediadbversion.h,
    navmediaimpl.h, navmediainfo.h, navmediapartnumber.h,
    navmediarequestcopydatabase.h, navmediaselectmedia.h,
    navmediaupdateprogress.h, navmediavendor.h, plus matching
    mediainfochanged{aspect,event,listenerproxy}.h,
    requestcopydatabase{aspect,event,listenerproxy}.h,
    requestmediaeject{aspect,event,listenerproxy}.h,
    selectmedia{aspect,event,listenerproxy}.h -- real source path
    `J:\siemens\source\generated\cpp\headers\api\media\types\media\
    navmedia*.h`, plus `navmediaimpl.h` under
    `...\navicore\modules\naviservice\media\` (symbol
    `getInstance__12NavMediaImpl`). This is disc/media-management code:
    coverage area, vendor, version, part number, "request copy database",
    "select media", "eject media" -- directly relevant to this project's
    own already-cracked `DBINFO.TXT`/`cdrom.toc` disc-identity metadata
    (VW part number `1T0051859AR` etc, README's disc-root section) --
    DBAL V009 is where the firmware gained the ability to manage/compare
    MULTIPLE map discs (part numbers, versions, vendors), not just read
    one. Also added here: db_intersection_view.cpp,
    guidancejunctionviewinfo.h -- the latter independently matches
    `eeu.mod`'s own "Ordinary Map File" schema, which already names an
    `intersection_view`/`junction_view` field group (wiki
    `eeu-mod-Database-Schema.md`) -- confirms that part of the schema was
    a V009-era addition too, not present from the start.

  V010_015 (+1, the newest build on this disc): only
    `routepath_coordhashtable.h` is new. Real source path
    `J:\siemens\source\navicore\common\dataobjects\
    routepath_coordhashtable.h`. Context strings around every occurrence
    (4 total in V010_015) place it directly alongside
    `...\api\shared\types\db\segment.h` and `...\db\navigationimage.h`,
    with 2 adjacent runtime error strings: `"itemsEqual(), headPosition,
    getNodePosition failed!"` / `"itemsEqual(), tailPosition,
    getNodePosition failed!"` -- a real coordinate-keyed hash table over
    route-path segments, checking whether the head/tail node of each
    path item still resolves to a valid position. A plausible, NOT yet
    cross-checked parallel to this project's own `eeuz.fea` directory
    hash-table finding and the `db_page::update_pnext` hash log string
    below -- worth revisiting if the route-path/navigationimage tables
    are ever tackled directly (currently out of scope: no on-disc file
    has been identified as "the route-path table" specifically, since
    routing is computed at runtime from `eeu.rd`, not stored precomputed).

**The "generic corridor" subsystem -- REMOVED between V007_038 and
V008_704, exactly at the same release boundary as the aspect/event
framework's addition.** A full file-set diff (V010_015 minus V006_047)
found 65 files added and 11 REMOVED; all 11 removed files belong to one
real subsystem, under real source path
`K:\siemens\source\navicore\modules\genericcorridor\
{corridorhelpers,corridormain,corridorstorages}\...` (note the `K:`
drive, vs. `J:` for every other path in this file -- a different build
machine/drive mapping for this one subtree, consistent with it being
older/separately-maintained code):

    corridorbackend.h, corridorcatalogstorage.h, corridorcitylistrecord.h,
    corridorcityrecord.h, corridorconfig.h, corridorfrontend.h,
    corridorhelpers.h, corridorlitree.h, corridormp0storage.h,
    corridorobjectpool.h, corrstatus.h

Precise version presence, checked per-file (not just the aggregate
diff): all 11 are present in BOTH V006_047 and V007_038, and ABSENT from
V008_704 onward -- the removal happened at exactly the V007->V008
boundary, the same release that added the whole aspect/event framework
above. A 12th related file, `corridorroadstorage.h`, was actually ADDED
in V007_038 (one version before the whole subsystem was deleted) --
real, brief further investment in "corridor mode" immediately before it
was cut.

Two real runtime strings confirm this was a genuine, working feature,
not dead code: `"Unsupported request in corridor mode (dir=%d, catID=%d,
count=%d)!"` (a real request-dispatch fallback message) and
`"MP0Storage:constructor:oslib_MutexCreate failed"` (from
`corridormp0storage.h`'s own constructor, an `oslib`-backed mutex-
protected object pool, per the adjacent `"%s- Max. object capacity: %d,
free pool objects: %d, heap objects: %d"` / `"%s- Current memory usage:
%d bytes."` diagnostic strings). `corridormp0storage.h` directly
references `eeuz.mp0` (this project's own heavily-studied MAP_COMPRESSED
layer, README S3.6) -- strongly suggesting "corridor mode" was a
route-corridor predictive prefetch/caching mechanism with its own
dedicated `mp0`-tile storage backend (likely: pre-load map tiles along
the upcoming route corridor before the vehicle reaches them), later
removed/replaced by whatever mechanism V008_704's `mapjobqueue.h`/
`maploader.h` job-queue abstraction implements instead. Purely
speculative beyond that -- no corridor-mode-specific file was ever found
elsewhere on this disc (this was PowerPC firmware-only functionality,
like the tpd `ctrlhost` CGI actions and the eeu.mod schema itself).

**The V008_704 phoneme-handler class names (CPhonemeEUHandler etc, see
above) are a real, dated architectural split between EU and North
American phoneme handling**, confirmed via real mangled C++ symbols
(CFront/old-GCC qualified-name mangling) naming an actual
`dbal::phonemes::` namespace:

    Q34dbal8phonemes17CPhonemeEUHandler = dbal::phonemes::CPhonemeEUHandler

Real classes: `CPhonemeEUHandler`, `CPhonemeNAFileReaderHandler`,
`CPhonemeNAFlashHandler`, `CPhonemeNAFlashFile`,
`CPhonemeNAGraphemeReferenceBuffer`, `PhonemeRetrievalInfo`,
`PhonemeKey`, `CPlaceRecordFile`. Real member functions:
`getPhonemeList`, `getPhonemeRecord`, `getPhonemeCount`,
`isPhonemeAvailable`, `getApproximatePhonemeCount`, `db_phoneme_unpack`,
`fillIntersectionsFromPhonemeFile`, `getObjectOffsetByID`,
`loadPhonemeFileFlashMemory`/`unloadPhonemeFileFlashMemory`,
`getNextRecord`, `getLine`, `isEOF`, `validate`, `deliverGraphemes`,
`addNameReference`, `cmpNameReference`. Real diagnostic strings for the
NA flash-file path: `"CPhonemeNAFlashHandler: loadPhonemeFileFlashMemory"`,
`"...could not open file %s"`, `"...file %s does not exist"`,
`"...file %s exists and is load = %d"`, `"CPhonemeNAFlashFile:
getNextRecord: record = %s"`, `"CPhonemeNAFlashHandler::
getPhonemeCount: Phoneme is not available for listType = %d and
ulOffset = %ld"`. This confirms the EU disc family this whole project
studies (`eeu.*`/`eeuz.*`, this exact `CD_8555` disc) uses
`CPhonemeEUHandler` reading `eeuz.pca`/`.pct`/`.prd`/`eeu.pcl` directly
(README S3.23/S3.5/S3.17), while North American discs (a DIFFERENT,
never-seen disc family -- presumably `ena.*`/`enaz.*` by this project's
own established naming convention) use a completely different
`CPhonemeNA*` code path built around a "flash file" abstraction
(`loadPhonemeFileFlashMemory`) instead of a `.pca`/`.pct`/`.prd`-style
disc-file read -- i.e. the phoneme *data format itself* likely differs
between EU and NA discs, not just the handler class name. Real source
paths: `J:\siemens\source\libraries\dbal\include\CPhonemeEUHandler.h`,
`J:\siemens\source\libraries\dbal\db\CPhonemeEUHandler.cpp`,
`J:\siemens\source\libraries\dbal\include\
CPhonemeNAFileReaderHandler.h`, etc.

============================================================================
NOT done this session
============================================================================
No disassembly, decompilation, or symbol-table (ELF section header)
parsing was attempted -- all findings above came from a plain printable-
ASCII-run scan of the raw file bytes. No attempt was made to correlate
the ClearCase branch-name history (above) against the specific version
each branch first landed in, though the raw data to do so is on-disc
(all 5 `DBAL.OUT` files, unchanged). `routepath_coordhashtable.h` was
found but not further pursued -- no on-disc file has been positively
identified as "the route-path table" it manages.

============================================================================
Practical use
============================================================================
This module has no parsing functions. To reproduce the string
extraction: `re.findall(rb"[ -~]{6,}", open(path, "rb").read())` on any
`DBAL.OUT`, no ELF library needed.
"""
