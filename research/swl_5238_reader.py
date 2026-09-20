"""
swl_5238_reader.py -- documents `5238_ALL` (a SEPARATE disc from the map
disc `CD_8555`, extracted this session at the user's direct prompt): a
real Continental/VW factory "Software Loading" (SWL) CD for CP2-based
RNS510 units, VwSwIndex 5238 -- the SAME firmware build whose flashed
end product, `FHDD6.FLI`, README S2 already examined at the
0-24MB(native PowerPC)/24-76MB(Java classes)/76-85.6MB(VxWorks
kernel/BSP) region level. This disc is the ORIGIN of that exact file
(`APPS\\SILVER_1\\RNSMIDEC\\PROG\\FHDD6.FLI`, byte-identical path),
plus everything AROUND it: the real flash-programming procedure, sibling
ECU firmware images, and (genuinely new) a small, complete, disassembly-
ready PowerPC ELF object with full symbol/debug info.

============================================================================
Disc identity -- CRACKED (plain text)
============================================================================
`VERSION.TXT`: `CdTreeBuilder version 3.06`, `#CD:P 0 0 5 . 6 7 0 . 3 0 6`,
`#DATE:2012-10-19`, `#Project: VWRNS`, `#VwSwPartNumber:` lists 15 real VW
part numbers sharing this build (`1T0035680L`, `3T0035680G`,
`7F0035680B`, ... `2H0035680`), `#VwSwIndex:5238` (x5, matching the
already-known firmware generation this project calls "5238"),
`#Steckbrief: C_EU_13.236_t3 C3/C4A/C5C/C6/C10/C12` (a real internal
"characteristics sheet" ID naming 6 real VW platform codes this build
supports). `#CommentStart: This is an unofficial SWL CD by josi. Use it
at your own risk. #CommentEnd:` -- this specific disc image is a
community repack (not the original factory CD verbatim), a real,
disclosed provenance detail worth keeping in mind for any byte-level
claim below (the repacker could in principle have altered file
contents, though CRC.16 files throughout the tree -- see below --
would make that detectable).

============================================================================
Disc structure -- CRACKED: a real ECU-by-ECU ordered flashing tree
============================================================================
`ECUORDER.TXT` (plain text) lists the real flashing order:
`APPS`/`HOST`/`HDD`/`RADIO`/`MPEG`/`SPEECH`/`DAB`/`VUCI` -- matching the
top-level folder names exactly. Each top-level folder is one real ECU
target:
  - `APPS` -- the main head-unit application processor (navicore/Java/
    VxWorks -- README S2's own subject)
  - `HOST` -- a separate "host" controller processor
  - `HDD`/`RADIO`/`MPEG`/`DAB`/`VUCI` -- peripheral ECUs (hard disk
    controller, radio tuner, MPEG/video decoder, DAB tuner, and the
    MOST-bus/CAN gateway -- `VUCI\\B101\\...\\GATEWAY.FLI`/
    `GWBOOTL.FLI`/`T5GATEW.FLI`, matching the already-identified
    ST10F276E gateway chip, README S2.2)
  - `SPEECH` -- TTS/speech-recognition data (`FRG/LANG_*.FRG`/
    `RECOG_*.FRG` per-language fragments, `SDS_*.ZIP`/`UVO_*.ZIP` per-
    locale voice packs -- same naming convention as the map disc's own
    `speech/` folder, README's speech_reader.py)
  - `WA` -- shared shell scripts (`.WSH`) and one small diagnostic
    utility (`CTEST.OUT`, cracked below), used across multiple ECU
    targets, not itself a flashable ECU image
  - `INFO`/`config` -- build metadata (`CDSTRUCT.CFG`, below)

Every leaf project folder (e.g. `APPS/SILVER_1/EURPQEE/`) holds only a
`CONFIG/DLSCRIPT.TXT` + `CRC.16` -- the real flashable payloads
(`.FRG`/`.FLI` files) live in a SHARED location
(`APPS/SILVER_1/RNSMIDEC/PROG/`) and are referenced BY PATH from each
variant's own `DLSCRIPT.TXT`, not duplicated per variant. `HWIDMAP.TXT`
(plain text, `<12-digit hex ID> <hardware name>`) maps a real detected
hardware ID to one of 2 real head-unit hardware revisions on this disc,
`SILVER_1`/`SILVER_6`. `PRJCTMAP.TXT` (plain text, `<8-digit ID>
<variant folder name>`) maps a real per-vehicle configuration ID (the
same kind of ID a VW dealer tool reads off the vehicle) to one of the
~15 real project-variant folders (`EURPQEE`/`EURPQWE`/`EURSKEE`/
`EURSKWE`/`EURSBHDD`/`EURTN`/`EUT5PQ`/`EUT5TO`/`EURAK`/`EURSEDAB`/...) --
`EE`/`WE` = East/West Europe (matching this whole project's own `eeu`/
`eeuz` naming convention for the East-Europe map disc), `SK` = Skoda,
`SB` = Skoda Superb, `T5`/`TO`/`PQ`/`AK`/`DAB` = real VW platform/
hardware-option codes.

`INFO/CDSTRUCT.CFG` (25,955 lines) is the real top-level build/flash
ORCHESTRATION script -- a `#ifdef`/`#else`/`#endif`-preprocessed
sequence choosing which ECU targets to flash (`SWL`/`HOST`/`APPS`/`HDD`/
`RADIO`/`IBOC`/`MPEG`/`NAVP`/...) per build configuration, each guarded
block invoking that ECU's own real flashing keyword (`SWL`, `HOST`,
`APPS`, ...) plus real housekeeping steps (`RUN_SHELL_SCRIPT ...
DEL_FOLD.WSH`, `RESTART_SYSTEM`). Its own leading ~50-line comment block
is a real, dated (2006-2008+) internal Continental/VW engineering
changelog -- named engineers (`AKls`, `MaRu`, `AKr`, `y.`, `m.`), real
internal bug-tracker IDs (`TlaWtz#46435`, `TlaWtz#47169`), and real
project-line codenames (`EU-PQ`, `NAR`, `JAP`, `CHN`, `SB`=Skoda Superb,
`PH`=Phaeton) -- the same kind of real, dated build-history evidence
this project already found in `dbal/`'s ClearCase branch names (README
S3's `dbal/` bullet) and `POI.DB3`'s own build metadata, now from a 3rd,
independent subsystem. Not further parsed line-by-line this session
(25,955 lines is a lot; the `#ifdef` grammar and per-ECU keyword set are
identified, not a complete parser).

Every folder carries a `CRC.16` file (a real, presumably per-directory
checksum used by the SWL loader to verify a clean burn/copy) -- not
decoded, but its universal presence (119 occurrences disc-wide) is
itself confirmation this is a real integrity-checked deployment format,
not an ad-hoc file dump.

============================================================================
`DLSCRIPT.TXT` -- CRACKED: a real, self-documenting flash-programming
script language (genuinely new; not covered by README S2)
============================================================================
Each project variant's own `CONFIG/DLSCRIPT.TXT` (plain text) is a real,
line-oriented bytecode-free script the SWL loader interprets step by
step. Confirmed real commands, from a representative file
(`APPS/SILVER_1/EURPQEE/CONFIG/DLSCRIPT.TXT`):

    BOOTMODE_SWL
    SHOW_SCREEN <flag> <id> <screen-name>
    EXPECTED_TIME <seconds>
    RUN_SHELL_SCRIPT <flag> <byte-size> <path.WSH>
    INSTALL_FRAGMENT <flag> <byte-size> <path.FRG>
    LOAD_FIB <flag> <byte-size> <path.FLI>
    LOAD_LIBRARY <flag> <byte-size> <path.OUT>
    UPDATE_SYS_CONFIG
    COMPARE_REG_ID <reg> <mask> <value> <goto-label-if-match> <default>
    GOTO <label>
    <label>                    -- a bare identifier line is a jump target
    FINISHED_ECU

Every `<byte-size>` argument to `INSTALL_FRAGMENT`/`LOAD_FIB`/
`LOAD_LIBRARY` matches the real on-disc file's own exact byte size
(cross-checked directly: `LOAD_FIB 20 85658916 .../FHDD6.FLI` against
the real file's `85,658,916`-byte size on disc, exact). This single
`DLSCRIPT.TXT` shows exactly how `FHDD6.FLI` gets onto the unit:
`INSTALL_FRAGMENT` first applies `A_HDD.FRG` (85,254,064 bytes, its own
real magic `b"ZZZZ"` -- a distinct, NOT yet decoded container format,
plausibly a delta/patch or a pre-verification wrapper around the same
payload, given its size is within 0.5% of `FHDD6.FLI`'s own), then
`LOAD_FIB` writes `FHDD6.FLI` itself. `COMPARE_REG_ID 0x091C 0x09 <lang>
<label> de` is a real per-language branch chain (11 languages this
project's own `speech/`/`SpeechRes.xml` work already enumerated,
README's speech section) selecting which `SPEECH/FRG/LANG_*.FRG` +
`RECOG_*.FRG` pair to install based on a real hardware/config register
value -- confirms `0x091C` is (part of) the real on-unit language-
selection register the factory flashing tool reads.

`WA/*.WSH` files (9 total, e.g. `DEL_FOLD.WSH`/`DEL_LANG.WSH`/
`FIXCOD.WSH`/`EURPQTO.WSH`) are referenced by `RUN_SHELL_SCRIPT` -- real
shell scripts, not opened this session (out of scope; the `DLSCRIPT.TXT`
grammar itself was the target).

============================================================================
`FHDD6.FLI` -- the disc's own copy of README S2's already-examined
85.6MB application image; ONE NEW, MINOR addendum, mostly a REFUTATION
============================================================================
Byte-identical path (`APPS\\SILVER_1\\RNSMIDEC\\PROG\\FHDD6.FLI`) and
size (85,658,916 bytes) to the file README S2.1 already attributes
"0-24MB native PowerPC / 24-76MB Java classes / 76-85.6MB VxWorks
kernel/BSP". Directly re-confirmed this session via a plain string
count: 535x `"navicore"`, 278x `"dbal"`, 57x `"VxWorks"`, 28x `"Arriba"`
found in the file -- consistent with, not beyond, the already-documented
picture. Real magic bytes: `b"\\xaaU\\xaaU"` (`0xAA55AA55`), not
previously noted.

**A new angle was tried and REFUTED, not a new crack**: a raw `b"\\x7fELF"`
magic-byte scan over the whole 85.6MB file finds 4 hits (~82.9MB-84.2MB,
inside the already-identified 76-85.6MB VxWorks-kernel region). All 4
are FALSE POSITIVES: each one's own `e_shoff` field, read as if it were
a real standalone ELF header at that position, points at data that
fails to re-parse as a coherent section-header table (garbage
`sh_type`/`sh_offset`/`sh_size` values, inconsistent with any real
section layout) -- unlike `WA/CTEST.OUT` below, whose single real ELF
header parses perfectly end-to-end. This does not contradict or extend
README S2.4's own separately-documented wall (a Ghidra/disassembly
attempt on the 0-24MB native region failed because that region "isn't a
single flat statically-linked image ... so a load-base address couldn't
be recovered") -- it is a different, narrower negative result in a
different region of the same file, recorded here so a future session
doesn't re-try naive ELF-magic scanning on this file expecting a clean
hit.

============================================================================
`WA/CTEST.OUT` -- CRACKED: a real, complete, standalone PowerPC ELF
object with FULL symbol table AND DWARF debug info -- genuinely new,
and successfully disassembled
============================================================================
89,576 bytes. Same container profile this project already knows from
`dbal/*.OUT` (32-bit big-endian PowerPC, `ET_REL` relocatable object,
`EM_PPC`) -- but unlike those, this one is SMALL and SELF-CONTAINED
enough that its `e_shoff`/section-header table parses perfectly, giving
direct access to real content no `dbal/*.OUT` file exposed this
directly:

  - **`.symtab`/`.strtab`**: 102 real symbols with real names, sizes,
    and `.text` offsets (no guessing needed).
  - **`.debug_info`/`.debug_line`/`.debug_abbrev`/`.debug_pubnames`/
    `.debug_aranges`**: real DWARF debug info (not just the plain-string
    dumps `dbal/*.OUT` offered) -- not parsed this session, but present
    and available for a future session wanting real source-line-level
    detail.
  - **Real source files** (from the symbol table's own compilation-unit
    markers): `CodingTest.c`, `RegTest.c`, `ConfigFblockTest.c`,
    `ctdt.c` -- this is a factory ECU CODING/diagnostics test utility,
    NOT part of the navigation core (no `db_*`/`navicore`/`dbal`-family
    symbol appears anywhere in it).
  - **Real function names**: `TestCoding`, `SetCoding`, `SetCodingHex`,
    `TestDetail`/`SetDetail`, `ReadRegData`/`SetRegData`/
    `DeleteRegData`/`SaveRegData`, `configSetRegHex`/`configLogin`/
    `configRegister`/`configTestReadReg`, `ResetEcu`,
    `ConfigTestShadowInit`/`configTestShadowSink`, `TestRegSync`/
    `TestRegistrySync`/`RegTestDoSync`.
  - **Real external API surface** (imported, undefined symbols -- i.e.
    what this factory-test module calls INTO): `CodingApi_GetCodingData`/
    `GetCodingDetail`/`SetCodingData`/`SetCodingDetail`/
    `RegisterNotification`/`RegisterNotificationDetail`,
    `ErrorLog_SetError`, `bootMgrNotifyStartupAchieved`/
    `RunupAchieved`/`RundownAchieved`/`ShutdownAchieved`,
    `bootMgrAddShutdownConsumer`, `svcb_addServiceListener` -- a real,
    named application lifecycle/service-registration framework running
    under VxWorks on this platform, genuinely new to this project.
    `cc_tla_most_addSink`/`cc_tla_most_send`/
    `cc_tla_most_getLocalDeviceId` -- real, direct MOST-bus (Media
    Oriented Systems Transport, the actual automotive multimedia bus VW
    uses) API calls, confirming this diagnostic module talks MOST
    directly, consistent with README S2.2's already-inferred
    MOST-bus/CAN gateway chip.

**Disassembled successfully** with `capstone` (installed this session;
was not previously available/used in this project) -- `TestCoding`
(`.text` offset 1864, 472 bytes) decodes to a real, valid,
textbook GCC-PowerPC-ELF function prologue (`stwu r1,-0x130(r1)` /
`mflr r0` / save callee-saved `r29`-`r31` / `mr r31,r1`) followed by
real argument handling and a relocation-patched external call sequence
(`lis r9,0` / `addi r29,r9,0` / `mtlr r29` / `blrl` -- the two zero
immediates are `.rela.text`-relocated placeholders, consistent with the
file's own `.rela.text` section, 0x1938 bytes of relocation records).
Confirms the disassembler and this project's understanding of the
platform's PowerPC ABI are both correct -- a real, usable capability for
any future session wanting to read compiled logic on this platform
directly, not just its embedded strings.

============================================================================
`FHDD6.FLI`'s own 0-24MB native-PowerPC region -- CRACKED at the debug-
string level: a MASSIVE, genuinely load-bearing inventory directly
confirming (and extending) this project's own schema/format guesses
from the ACTUAL RUNNING CODE's own names, not just an authoring tool's
schema dictionary
============================================================================
A LATER session within this same investigation: rather than trying to
disassemble the 0-24MB native region (README S2.4's own documented wall
-- no recoverable load-base address for a proper relocation-aware
disassembly), a plain printable-string scan of that SAME region (no ELF/
load-base knowledge needed for this) finds an enormous, dense debug-
string table -- 129,870 printable-ASCII runs of length >=5 in just the
first 24MB, including **1,476 distinct real `.cpp`/`.h` source
basenames in a single representative 5.3MB slice alone** (far exceeding
`dbal/`'s own ~330-path inventory from its much smaller 1.19-1.33MB
relocatable objects). This is effectively the debug-string table for
the WHOLE compiled navicore application, not just the swappable DBAL
plugin.

**The complete, real, end-to-end `dbal/` DYNAMIC-LOADING mechanism --
CONFIRMED from the firmware's own runtime log strings**, closing the
loop between this project's map-disc-side `dbal/` findings
(`research/dbal_reader.py`) and how the firmware actually uses them:

    dbaLib: DBAL version is dynamic linked
    dbaLib: determine loaded dbal version
    dbaLib: loaded dbal version: V_%03d_%03d
    dbaLib: no file %s on DVD ==> use version %03d.%03d from
    dbaLib: best matching dbal.out version on DVD: V%03d_%03d
    compatible dbal.out version on DVD: V%03d_%03d
    FATAL!!! No matching dbal.out version on DVD!!! Invalid
    dbaLib: try to load %s
    loadModule for dbal.out
    dbal_link_symbols failed!
    dbaLib: actual: V%03d_%03d - requested: ...
    now unload DBAL version: V%03d_%03d
    dbaLib: unload current dbal.out
    dbaLib: ERROR!! Loaded %s version does not match DVD; %s
    The current implementation cannot exchange a loaded DBAL_NAME !!!

The `V%03d_%03d` format string is an EXACT match for the map disc's own
`dbal/V006_047`/`V007_038`/.../`V010_015` folder-naming convention
(3-digit major, underscore, 3-digit minor) -- confirming, from the
firmware side, that: the firmware reads whichever map disc is inserted,
determines its own required DBAL version, searches the disc's `dbal/`
folder for a matching (or "best compatible") `V0NN_0MM/DBAL.OUT`,
dynamically `loadModule`s it (real PowerPC dynamic linking --
`dbal_link_symbols`), and can later `unload` and swap to a DIFFERENT
version if a different disc is inserted. This directly explains WHY the
map disc ships 5 separate DBAL builds side by side (README's own
`dbal/` bullet) — it's not redundancy, it's real forward/backward
compatibility infrastructure, matching multiple possible disc
generations against one firmware build. Real function names:
`dbal_load__Fv`, `dbal_unload__Fv`, `dbal_get_compatible_version__FPiT0`,
`dbal_get_minor_version_1__Fv`, `initializeDBAL__9MapLoader`,
`cleanupDBAL__9MapLoader`.

**A catalog of 77 distinct, real, VERSIONED `db_*_V0NN` accessor
function names** was extracted (regex `db_[A-Za-z_]+_V\d{3}` over the
same region) — direct, compiled-code confirmation of exactly the kind
of per-field accessor this project has inferred only from `eeu.mod`'s
own authoring-tool schema dictionary (README S3.16) until now. Most
directly relevant to this project's own open walls:

  - **MAP_COMPRESSED segment record** (the still-open `seg_list`/
    `seginfoID` wall, README S3.16's own `eeu.mod` bullet): `db_seg_
    rank_V004`, `db_seg_speed_V004`, `db_seg_tunnel_V004`, `db_seg_
    node_V004`, `db_seg_unique_vid_V005`, `db_seg_plural_junction_V005`,
    `db_seg_is_part_of_freeway_intersection_V005`, `db_seg_marker_
    left_V004`/`db_seg_marker_right_V004` (the latter pair an EXACT
    name match for `eeu.mod`'s own already-found `seg_marker_left`/
    `seg_marker_right` fields) — real, compiled, versioned accessors
    for exactly the segment fields this project has been trying to
    locate a byte offset for. Does NOT by itself give the byte offset
    (no disassembly of the function bodies was attempted — see below)
    but is strong, independent confirmation the field names are real
    and actively used at runtime, and gives exact function names a
    future disassembly-based attempt could search for specifically
    (much narrower than blindly hunting the whole 24MB region).
  - **`eeuz.fea`/MAP_COMPRESSED parcel directory**: `db_get_parcel_
    dir_V005`, `db_load_pcl_dir_V005`, `db_remove_pcl_list_V005`,
    `db_page_pcl_V000`, `db_page_releaseParcel_V003`, `db_map_dir_V000`,
    `db_rd_fea_pdir_uncached_V000`, `db_get_fea_file_header_V000`,
    `db_fea_map_V000`, `db_fea_get_layer_range_V005`.
  - **`eeu.tmc`**: `db_tmc_all_headers_V003` and `db_tmc_all_headers_
    deprecated_V005`, `db_tmc_seg_V003` — direct, compiled-code
    confirmation these are REAL, versioned per-disc-format readers
    (found immediately adjacent to each other in the string table, and
    to `db_page_releaseParcel_V003`/`db_road_NameListDataByIndex_V004`
    — consistent with alphabetically/table-grouped debug info, not
    randomly scattered). **This independently confirms, from a
    completely different angle, this project's own earlier correction**
    (README S3.25 / `dbal_reader.py`'s own db_tmc_deprecated note): the
    "V003" vs "deprecated_V005" split is a real ON-DISC-FORMAT-VERSION
    distinction the firmware's `dbaLib` code handles by calling a
    DIFFERENT accessor depending on which version the inserted disc
    actually has — not evidence the format changed between DBAL BUILD
    versions.
  - **Junction views** (added at DBAL V009_038 per this project's own
    5-version diff, `dbal_reader.py`): `db_check_junction_view_V006`,
    `db_get_junction_view_V006`.
  - **North America**: `db_us_state_from_segment_V008` — confirms a
    real, distinct NA-specific map-data code path exists in this exact
    codebase, independent evidence alongside the already-found
    `CPhonemeNA*Handler` phoneme split (`dbal_reader.py`).
  - Two literal PLACEHOLDER-named entries, `db_xxxx_V003`/`db_xxxx_
    adaptor_V000..V002` and `db_zzzz_V002` — real evidence these `db_*`
    accessors are machine-generated from a common template (a code
    generator or macro producing one `db_<table>_V<N>` function per
    real table), consistent with `eeu.mod`'s own "authoring tool
    dictionary" nature (README S3.16) — the runtime accessor layer and
    the authoring-tool schema dictionary are almost certainly generated
    from the SAME underlying table definitions.

**Not attempted**: disassembling any of these named functions'
actual code bodies. Their STRING locations are known (offsets within
`FHDD6.FLI`), but their CODE addresses are not directly recoverable
without either (a) parsing this region's own `.debug_info`/symbol table
properly (README S2.4's documented wall — no recoverable load base for
the whole 24MB region) or (b) a pattern-based heuristic function-finder
(searching for real PowerPC prologue bytes, as confirmed working on
`WA/CTEST.OUT` above, then trying to correlate candidates to these
known names by cross-referencing string-table/`.rodata` proximity) —
neither was built this session. This is the concrete, well-scoped next
step for a future session wanting exact byte offsets rather than just
confirmed field names.

============================================================================
NOT done this session
============================================================================
- `INFO/CDSTRUCT.CFG` (25,955 lines) was characterized (grammar, keyword
  set, the real dated comment header) but not fully parsed line-by-line.
- `A_HDD.FRG`'s own `b"ZZZZ"` container format was identified as real
  and distinct from `FHDD6.FLI`'s own `0xAA55AA55` format, but not
  decoded.
- `WA/*.WSH` shell scripts, `SPEECH/FRG/*.FRG` (44 files) and
  `SPEECH/*.ZIP` (24 files), and every non-`APPS` ECU target's own
  `.FLI`/`.FRG` payloads (`HOST`, `RADIO`, `MPEG`, `DAB`, `VUCI`, `HDD`)
  were enumerated by name/size only, not opened.
- `CTEST.OUT`'s real DWARF `.debug_info`/`.debug_line` sections were
  confirmed present but not parsed (no DWARF parser was written this
  session -- would give real source-line-level detail if a future
  session wants it).
- The 0-24MB native-PowerPC region's rich debug-STRING table was mined
  (source paths, the `dbaLib` dynamic-loader log strings, 77 versioned
  `db_*_V0NN` accessor names -- see above), but no attempt was made to
  locate or disassemble the actual CODE behind any of those names --
  README S2.4 already documents why that's hard in general (no
  recoverable load-base address for the whole region) and this
  session's own ELF-magic-scan attempt (in the DIFFERENT 76-85.6MB
  VxWorks region, not the native-code region) was a real, refuted
  negative result, not a new angle on the S2.4 wall itself. A pattern-
  based heuristic function-finder (real PowerPC prologue bytes,
  confirmed to work on `WA/CTEST.OUT`) was identified as the concrete
  next step but not built.

============================================================================
Practical use
============================================================================
This module has no parsing functions yet. `DLSCRIPT.TXT`/`CDSTRUCT.CFG`/
`*.TXT`/`*.CFG` are plain text, read directly. `WA/CTEST.OUT`'s ELF
structure can be parsed with plain `struct.unpack('>HHIIIIIHHHHHH', ...)`
on its 52-byte ELF header (same recipe as `dbal_reader.py`'s own
container-format notes) followed by a standard 40-byte
`Elf32_Shdr`/16-byte `Elf32_Sym` walk -- both straightforward since,
unlike `dbal/*.OUT`, this file's `e_shoff` is directly trustworthy.
Disassembly: `capstone.Cs(capstone.CS_ARCH_PPC, capstone.CS_MODE_BIG_ENDIAN | capstone.CS_MODE_32)`.
"""
