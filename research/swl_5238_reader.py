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
`#DATE:2012-10-19`, `#Project: VWRNS`, `#VwSwPartNumber:` lists **18**
real VW part numbers sharing this build -- RE-VERIFIED directly against
the real file (the field wraps across 2 lines in the raw text, easy to
undercount at a glance; corrected from an earlier "15" miscount):
`1T0035680L`, `3T0035680G`, `7F0035680B`, `7E0035680B`, `1T0035680P`,
`1T0035680Q`, `3T0035680K`, `3T0035680L`, `1T0035686`, `1T0035686C`,
`1T0035686D`, `7F0035686`, `7E0035686`, `3T0035686`, `3T0035686C`,
`3T0035686D`, `7N5035686`, `2H0035680`. `#VwSwIndex:5238` (x5, matching
the already-known firmware generation this project calls "5238").
`#Steckbrief: C_EU_13.236_t3 C3/C4A/C5C/C6/C10/C12` -- RE-VERIFIED,
CORRECTED: these are **NOT vehicle platform codes** (this docstring's
own earlier characterization was wrong); `INFO/CDSTRUCT.CFG` directly
confirms via `#ifdef HARDWARE_C3`/`HARDWARE_C4A`/`HARDWARE_C4B`/
`HARDWARE_C6`/`HARDWARE_C10`/`HARDWARE_C12`/`HARDWARE_C14` conditional
blocks (plus a plain `HARDWARE_C`) that these are internal Continental
HARDWARE-REVISION codes for the head unit's own PCB, all mapped to
sequential numeric hardware IDs (`000100020040`-`000100020047`) under
the SAME `SILVER_1` product line -- i.e. they identify which physical
head-unit board revision the firmware build targets, not which VW/Seat/
Skoda vehicle it's installed in (that's what the 18 `VwSwPartNumber`
values above are for, one per real vehicle-specific installation kit).
`#CommentStart: This is an unofficial SWL CD by josi. Use it at your own
risk. #CommentEnd:` -- this specific disc image is a community repack
(not the original factory CD verbatim), a real, disclosed provenance
detail worth keeping in mind for any byte-level claim below (the
repacker could in principle have altered file contents, though CRC.16
files throughout the tree -- see below -- would make that detectable).

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
real magic `b"ZZZZ"` -- see the dedicated section below, a LATER session
CRACKED its 64-byte fixed header), then
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

**A LATER session tried the load-base recovery (b) directly, and hit a
real, well-reasoned wall -- not just "not attempted".** Confirmed first:
no `b"\x7fELF"` magic anywhere in the 0-24MB region (0 hits) -- unlike
`WA/CTEST.OUT`, there is no ELF container surviving here at all, ruling
out approach (a) outright (there is no `.debug_info`/symtab structure to
parse -- the debug strings are the ONLY surviving trace). For (b): every
`lis Rt,HI16` PowerPC instruction immediately followed by an `addi
Rt,Rt,LO16` on the SAME register was found via a direct 32-bit
big-endian word scan (no capstone needed for this narrow pattern) across
the whole 24MB region -- 39,715 such pairs, each forming a candidate
32-bit absolute address `(HI16<<16)+sign_extend(LO16)`. The idea: if any
of these pairs load the real address of one of the known debug strings
above, then `candidate_address - string_file_offset` should equal one
CONSISTENT unknown load-base value across MANY independent strings --
directly recovering the load base this project has never had. **Tested
against 7 known string offsets (`db_seg_marker_left_V004`,
`db_tmc_all_headers_V003`, `db_get_dbal_version_V000`, etc): each
string's own top candidate "base" values are COMPLETELY DIFFERENT from
every other string's** (no shared value appears as a top candidate for
more than one string) -- i.e. none of these 39,715 `lis`/`addi` pairs
are genuinely loading any of these strings' addresses; the high
per-string counts (700-900 each) are just the most common unrelated
immediate-pair values occurring anywhere in 24MB of code, coincidence
only.

**Why, most likely**: byte-level inspection around several of these
strings (`db_page_releaseParcel_V003\x00\x00db_tmc_all_headers_
V003\x00db_tmc_seg_V003\x00\x00\xe8\x00\x19\x00\x00\x01 _city_
V004\x00\x00...`, `_vt$27RouteCalculatorMana<4 raw garbage bytes>
roxy\x00fp_db_seg_marker_left_V004\x00...`) shows this is MOSTLY a
plain, flat NUL-terminated string pool (consistent with a DWARF
`.debug_str`-style section, or a stripped `.strtab` with its `.symtab`
counterpart removed) -- occasionally interrupted by a few stray binary
bytes at what look like segment/seam boundaries, not a regular per-
string binary header. A `.debug_str` (or bare `.strtab`) is, by design,
referenced ONLY by other debug/symbol-table structures (an external
debugger, or a linker's own bookkeeping) -- NEVER by the executing
code's own instruction stream. If that is what survived here, there is
NO `lis`/`addi` reference to find, for ANY string, no matter how
thorough the scan -- not a limitation of this technique, but a
structural fact about what kind of data this is. This is consistent
with, and extends, README S2.4's own finding (no recoverable load base
for a proper disassembly) — it adds a second, independent reason (no
runtime code ever touches these specific bytes) alongside the original
one (the region mixes ROM-resident code with runtime-relocated
structures).

**Genuine wall for this session, not a workaround-able gap**: getting
real byte offsets for `db_seg_marker_left`/`db_seg_rank`/etc would need
either (1) the ACTUAL executing code that calls these accessors (not
their debug-only name strings) — a much harder, unscoped disassembly
search with no current entry point, or (2) external tooling/ground
truth this project doesn't have (a symbol map, a debugger attached to
real hardware, or the original build's own unstripped object files).
Recorded here in detail so a future session doesn't repeat the same
`lis`/`addi` correlation attempt expecting a different result.

**UPDATE, a still-later session: the pattern-based prologue-finder
identified above WAS built and run -- finds 7,757 REAL function starts,
but does NOT solve the correlation problem; a real, informative
structural finding, not a fix.** PowerPC's `mflr r0` instruction always
encodes to the exact same 4 bytes (`7c 08 02 a6`) regardless of which
function it's in, and every real GCC-2.96 function prologue in this
codebase starts with `stwu r1,-N(r1)` (`94 21` + a 2-byte frame size)
immediately followed by it (confirmed on `WA/CTEST.OUT`'s own real,
disassembled `TestCoding` function). Scanning the whole 24MB region for
the fixed 8-byte pattern `94 21 ?? ?? 7c 08 02 a6` finds 7,757 matches --
real, low-false-positive candidate function starts (2 wildcard bytes
out of 8 is a very tight signature).

**The real payoff of this scan is a clear map of the file's own
internal layout, not a name-to-address link**: match DENSITY drops from
900-1,235 per MB (1MB-9MB) to functionally ZERO from 9MB onward (only 2
stray matches in 11-12MB, none at all in 9-11MB) -- i.e. the real
`.text`-equivalent code region is roughly file offset 1.2MB-9MB, and
the debug-string region this session's earlier scans found (rich from
~8.9MB onward, e.g. `db_seg_marker_left_V004` at 11,296,384) starts
right where the code region ends. **This directly explains why no
proximity-based correlation is possible**: checked the nearest real
prologue to each of 5 known accessor-name string offsets -- distances
ranged 194,844 to 2,425,295 bytes (194KB to 2.3MB) -- code and debug
strings are genuinely separate, non-adjacent regions by construction
(consistent with a real, if stripped, `.text`/`.debug_str`-style
section split), not merely unlucky. **Honest conclusion**: the
prologue-finder works exactly as designed (finds real functions) but,
without a surviving symbol table or recoverable load-base address
(both independently confirmed absent above), there is no way to
determine WHICH of the 7,757 real candidate functions is
`db_seg_marker_left_V004` specifically. A further, much more labor-
intensive next step for a future session -- manually disassembling a
sample of the SHORTEST candidate functions (a real getter/accessor
like `db_seg_marker_left` should be very short: load one field, mask/
shift, return) looking for a pattern that plausibly matches -- was
identified but not attempted this session, given the scale (7,757
candidates) and the lack of any way to verify a match once found short
of testing its extracted bit-offset against real `mg4` tile bytes.

**UPDATE, a still-later session: this DWARF-debug-only-data hypothesis
was tested a 2nd, independent, more DIRECT way and CONFIRMED.** Built a
real DWARF2 parser (`research/dwarf2_reader.py`) and validated it
against `WA/CTEST.OUT`'s own `.debug_info` (a complete, correct 35-
function map, cross-checked exactly against that file's `.symtab`) --
confirming real DWARF `.debug_info` from THIS SAME GCC 2.96 toolchain
always carries a `DW_AT_producer` string (`"GNU C gcc-2.96 (2.96+
MW/LM) 19990621 AltiVec VxWorks 5.5"`) and a `DW_AT_comp_dir` build path
(`"F:\Entwicklung\e60-tools\CodingTest\cp2\PPC603gnu"`) on EVERY single
compilation unit. Searched the whole 24MB `FHDD6.FLI` region directly
for this exact producer string and build-path fragments (`"gcc-2.96"`,
`"GNU C"`, `"AltiVec VxWorks"`, `"PPC603gnu"`, `"e60-tools"`,
`"Entwicklung"`): **zero hits for every one**, despite 1,476+ distinct
source-file basenames implying hundreds of compilation units that WOULD
each carry one of these strings if real `.debug_info` survived. This is
direct, structural confirmation (not just an absence-of-correlation
inference from the `lis`/`addi` test) that no real DWARF `.debug_info`
exists anywhere in this region -- only a bare, stripped string pool
does. Closes the load-base question a 2nd, independent way; see
`research/dwarf2_reader.py`'s own docstring for the full writeup.

**UPDATE, a still-later session: built a real PowerPC instruction-level
emulator (Unicorn, `UC_ARCH_PPC`/`UC_MODE_BIG_ENDIAN`) as a targeted
"candidate classifier" over the 7,757 prologue-scan matches, to try to
pick out `seg_list`-accessor-shaped functions without a symbol table.**
Validated correctness against `CTEST.OUT`'s own known `TestCoding`
function (exact match to manual disassembly) before trusting any result.
Mapped the whole ~9MB code region once at a fixed base, pointed a fake
"record pointer" argument (`r3`) at a recognizably-patterned scratch
buffer, and used a `UC_HOOK_MEM_READ` hook to log which small offsets
each candidate function actually reads from it -- a real, working
technique (confirmed 3 separate times against correctly-decoded,
sensible real logic: a H:M:S-to-milliseconds time conversion, a magic-
constant mode dispatcher, and a genuine multi-table lookup/traversal
routine, full writeup in `research/map_compressed_reader.py`'s
`decode_topology()` docstring under "firmware emulation used to probe
byte1's real role"). **Honest limitation found**: the read-offset
heuristic alone is not selective enough on its own -- many unrelated
record shapes across this 9MB codebase produce the same "reads a couple
of small bytes near offset 0-4 of arg1" signature, so 2 of the
strongest-looking candidates were confirmed false positives once fully
disassembled. The technique correctly finds and lets us read REAL
function logic (this is the useful, durable result); it does not by
itself solve candidate SELECTION at scale without a much tighter filter
or a way to confirm real call sites (this codebase calls almost
everything indirectly via computed `lis`/`addi` + `mtlr`/`blrl`, which
also defeated static cross-reference search for at least one otherwise-
promising candidate's own callers -- see the map_compressed_reader.py
writeup for specifics).

**UPDATE, same investigation, candidate pool exhausted**: disassembled
all 8 candidates ever surfaced by this classifier's "reads a small byte
at offset 1/2/3" filter. 3 were confirmed false positives on full
disassembly (time conversion, mode dispatcher, and a floating-point
node/coordinate bounding-box test), 2 were inconclusive/trivial, 1
(offset 3,409,852) reads its own offsets 6-7 as 2 SEPARATE bytes --
conflicting with the independently-confirmed 4-byte `length` field at
those offsets, so it's most likely a different, similarly-shaped record
type -- and only 1 (`0x1f95d0`, offset 2,069,968) remains a strong,
unconfirmed match. That candidate's own caller could not be found by 3
independent static methods (direct `bl` scan, `lis`/`addi` absolute-
address scan, raw literal-pointer scan of the full 85MB image), and the
3 lookup tables it indexes resolve to RAM addresses (~`0xf6a5xxxx`) this
project has no file-offset mapping for. Full writeup:
`research/map_compressed_reader.py`'s `decode_topology()` docstring.
Honest conclusion: this candidate pool is exhausted for now; a future
session's best next step is either a tighter/different emulation filter
over a LARGER candidate set, or abandoning static/emulation analysis for
this specific question in favor of more ground-truth-driven byte
correlation on the map-data side.

**UPDATE, a still-later session: the same emulation-classifier technique
re-run against `mp0`'s own zone-2/zone-3a offsets (rather than `mg4`'s),
this time over ALL 7,757 prologue candidates (the earlier passes only
covered the shortest 3,000-5,000).** 1,393 candidates showed 1-4 reads
from the fake record buffer. Filtering for reads matching `mp0`'s
specific predicted field positions (zone-2's `value` byte at offset 6/10
co-occurring with the `tag` byte at offset 0; zone-3a's `speed` byte at
offset 4/5 co-occurring with the `type` byte at offset 2) found **zero**
candidates -- a real negative result, not an unexplored gap. The overall
read-offset distribution across all 1,393 candidates is dominated by
4-byte-ALIGNED offsets (0, 4, 8, 12, 16... -- the most common by a wide
margin), consistent with most short functions in this codebase operating
on regular, word-aligned in-memory C/C++ structs, not packed on-disk
byte layouts directly. Loosening the filter to single-byte reads at just
offset 4, 5, 6, or 10 (dropping the co-occurrence requirement) found 4
real candidates; 2 disassembled cleanly and are genuinely informative
even though neither is confirmed `mp0`-specific:
  - Offset 1,998,624: reconstructs an UNALIGNED 32-bit big-endian value
    from 4 individual byte reads at offsets 4-7 (`lbz`+`slwi` chain, the
    standard idiom for reading a multi-byte field that isn't 4-byte
    aligned), then searches a 20-byte-stride reference table for a
    matching value -- a generic "find the table entry whose stored value
    matches this input's unaligned 4-byte field" lookup utility.
  - Offset 2,337,788: genuine BIT-LEVEL unpacking -- reads byte 4 of its
    argument, extracts its top 2 bits (`srwi r0,r0,6`) as a category
    check, then uses `rlwinm` bit-rotate/mask operations to pull further
    sub-fields out of bytes 4 and 5 and writes them into a normalized,
    word-aligned 84-byte-stride runtime table (indexed by its own 2nd
    argument). This is exactly the architectural SHAPE this project has
    suspected but never directly observed: a real function that decodes
    packed on-disk attribute bits into individually-addressable runtime
    fields, consistent with why no direct 1:1 accessor for our exact
    raw byte offsets has ever been found -- there is likely a decode/
    unpack layer between the compressed tile bytes and whatever the
    named `db_seg_*` accessors actually read. NOT confirmed to be
    `mp0`-specific or to touch OUR exact `seg_list` zones (the offsets
    4-5 pattern is common enough to belong to any number of unrelated
    packed structures in this 9MB codebase), so treated as suggestive
    architectural evidence, not a crack of `mp0`'s own encoding.

============================================================================
The GLOBAL routing-graph node problem (`vnodeID`, README's own long-
standing "topology node-id<->coordinate mapping" open lead, wiki's
`eeu-il`/`eeu-mod` pages) -- a real, complete PIPELINE confirmed by
name, still not byte-offset cracked. Distinct from the ALREADY-CRACKED
per-tile LOCAL vertex-adjacency problem (README's own `resolve_
topology_adjacency()`, §3.6/§8 item 5) -- this is the cross-tile/
cross-parcel graph used for actual route calculation, not single-tile
rendering.
============================================================================
The same debug-string mining that found `db_seg_*`/`db_tmc_*` (above)
also found a dense, real `VNode`/route-calculation subsystem, giving a
complete, real, NAMED pipeline for exactly the problem `eeu.il`'s own
`vnodeID` field pointed at (README S3.2, wiki `eeu-il-Name-
Intersection-Index`, flagged as "a promising, not yet pursued lead"):

  1. `db_find_node_V000` / `fp_db_find_node` / `fp_db_find_node_
     from_draw_map` / `fp_db_find_node_from_complete_parcel` -- real
     node-lookup accessors, one variant specifically for resolving a
     node "from the drawn map" (i.e. from a currently-loaded/rendered
     tile) and another "from the complete parcel" (a full, not
     partially-loaded, tile) -- directly suggesting nodes are resolved
     differently depending on whether their home tile is already in
     memory.
  2. `db_vid_get_map_id_V000` / `fp_db_vid_get_map_id` and `db_vid_
     get_pcl_id_V000` / `fp_db_vid_get_pcl_id` -- "vid" = virtual id,
     i.e. exactly `eeu.il`'s own `vnodeID` naming. These 2 accessors
     are the REAL resolution step: given a virtual node id, get which
     MAP and which PARCEL (tile) contains it -- the crucial "which tile
     do I even need to open" step that has been entirely missing from
     this project's own understanding.
  3. `db_node(i_toNode, &vNode)` (real runtime error-log context:
     `"g: db_node(i_toNode, &vNode) != ARR_SUCCESS"`) -- once the right
     parcel is known, this loads the actual `VNode` structure. `VNode`
     has a confirmed real field `vsegIDs[]` (an array of segment IDs
     the node connects to, from `"db_seg(vNode.vsegIDs[i],&vSeg)"`) and
     is used with `db_find_hand(&vNode, &vSeg, &fromHand)` (a real
     "which hand/side" resolver, plausibly for divided-road/ramp
     disambiguation).
  4. `readNodeMP0__9RoutePathUiR5VNode` / `RoutePath_readNodeMP0__
     FP9RoutePathUiP5VNode` / `RoutePath_readNodeArmMP0__
     FP9RoutePathUiP5VNodePi` -- real functions reading a `VNode`
     DIRECTLY FROM AN `.mp0` (MAP_COMPRESSED) TILE, as part of building
     a `RoutePath`. This is the step that would actually surface a
     node's real coordinate, since MAP_COMPRESSED tiles are where this
     project's own already-cracked geometry/coordinate data lives
     (`research/map_compressed_reader.py`).
  5. A large real "maneuver generator" subsystem (`mv_*` functions,
     `Mv_Vnode`/`Mv_Info_Struct`/`Mv_Turn_Data`/`Mv_Obar_Data` classes,
     real source path `N:/siemens/source/navicore/common/mnvr/
     mv_vnode.cpp`) consumes these VNodes to build real turn-by-turn
     maneuvers (`mv_motorway_generate_keep`, `mv_roundabout_generate`,
     `mv_uturn_detect`, `mv_houseNumberSide`, etc) -- confirms VNode is
     genuinely THE cross-tile routing/guidance graph node, not a
     rendering-only construct.
  6. `resolveUnsetVNodeId__15LaneCalculationP4vsegi` -- a real function
     literally named for resolving an UNSET vnode id from a segment,
     in the lane-calculation module -- direct confirmation `vnodeID`
     really is sometimes absent/needs resolution, consistent with
     `eeu.il`'s own field not being populated for every entry.

**Net effect**: this is a complete, real, NAMED pipeline
(`vnodeID` -> `db_vid_get_map_id`/`db_vid_get_pcl_id` -> `db_node`/
`db_find_node` -> `VNode{vsegIDs[]}` -> `readNodeMP0` against the
correct `.mp0` parcel) -- but, same limitation as the `db_seg_*` catalog
above, only the NAMES are confirmed, not the byte-level encoding of
`vnodeID` itself or of `db_vid_get_map_id`/`get_pcl_id`'s own lookup
table. No attempt was made this session to locate or disassemble any of
this code (same structural wall as above -- no recoverable load base,
and these strings are likely debug-only data too). Concrete next step
for a future session: if `eeu.il`'s own already-cracked `vnodeID`
prefix bytes (wiki `eeu-il-Name-Intersection-Index`) can be fed through
a real `db_vid_get_map_id`/`get_pcl_id`-equivalent formula (even a
guessed one, e.g. a simple bit-split of the 32-bit vid into a map-id
field and a parcel-id field), the result could be cross-validated
against `eeuz.fea`'s own already-cracked `ParcelHeader{offset,
byteCnt,byteCntZip}` directory (wiki `eeu-mod-Database-Schema`) or
MAP_COMPRESSED's own tile directory -- a real, concrete validation path
that didn't exist before this session's firmware findings, even though
it wasn't executed here.

============================================================================
**UPDATE, a still-later session: the load base WAS recovered --
the earlier "no consistent load base" conclusion is OVERTURNED**
============================================================================
The earlier `lis`/`addi` correlation attempt (39,715 candidate pairs,
tested against 7 known `db_*` accessor STRING offsets) failed for a
real, now-confirmed reason: those specific strings are a DWARF-
`.debug_str`-style pool genuinely never touched by executing code, so
there was NOTHING for any `lis`/`addi` pair to legitimately match
against them -- that technique was sound, but its anchor points were
structurally unreachable. This session used a DIFFERENT technique that
doesn't need a known anchor at all: disassembled the 24MB native
region's code-dense sub-range (offsets 1.2MB-9MB, matching the
prologue-finder's own density map) instruction-by-instruction at every
4-byte-aligned offset (capstone, no linear-stream drift), collected
every `lis rX,HI16` immediately followed (within 10 instructions) by
`addi rX,rX,LO16` targeting the same register (34,652 such pairs from
116,383 `lis` instructions), and ran a BRUTE-FORCE sliding-window scan
over the sorted set of computed absolute targets: for a candidate
window width of 24,000,000 (the native region's own size), find the
window position containing the most targets. **Result: 32,966/34,652
pairs (95.1%) cluster inside ONE 24MB window** -- 170x the count a
uniform-random distribution across the full 32-bit address space would
predict (170.2x expected chance rate). This is not a subtle signal.

**Exact base recovered and independently verified 3 ways, byte-exact,
zero discrepancy each time**: `VA = file_offset_within_FHDD6.FLI +
0xf688dcf4` (mod 2^32). Verification: (1) a real runtime log string
`"bootMgrLax : Now I'm going to create the image -"` -- found via plain
search at file offset 0x2f5c (12,124); one of the 34,652 pairs computes
target `0xf6890c50` from a completely different file location, and
`0xf6890c50 - 0xf688dcf4 == 12124` EXACTLY. (2) A real, fixed-width
UI button-label table (`"PLAY      \x00\x00SEARCHBACK\x00\x00
SEARCHFOR \x00\x00STOP      \x00\x00PAUS..."`) sits exactly at the file
offset a different pair's target (`0xf6a51878`) implies, byte-for-byte,
with the same 4 repeated references from 4 different call sites landing
on the exact same table start. (3) Spot-checking the wider 24MB-window
sample independently found coherent, real content at implied offsets
without cherry-picking: C++ mangled class names (`...19SampleRate
ConverterRC...`), more XML-like `idref="G.NNNN"` state-machine
fragments (consistent with the already-known `.debug_str`-adjacent
config data), and further real UI/config strings. **This base is
DIFFERENT from anything the string-length-6 `lis`/`addi` correlation
attempt could ever have found**, because it was never anchored to the
unreachable debug-string pool -- it was recovered purely from code's
OWN real references to LIVE data (UI strings, log strings, RTTI names),
which the earlier technique never tried using as anchors.

**What this does and doesn't unblock**: this is a real, verified,
byte-exact file-offset-to-VA mapping for (at least) the 1.2MB-9MB
code-dense sub-range's own absolute references, reopening real
disassembly of this region with capstone (previously blocked entirely).
It does NOT yet locate any SPECIFIC named function (`db_vid_get_map_id_
V000`, `readNodeMP0`, etc) -- those names live in the confirmed-
unreferenced debug-string pool, so finding the CODE that implements them
still needs a different approach (e.g. the 7,757-candidate prologue
list, now finally disassemblable with a real base, cross-referenced
against what each candidate's own absolute references resolve to -- a
concrete, newly-unblocked next step that didn't exist before this
finding). Whether this SAME base (or a nearby, cleanly-derived one)
also holds for the 9MB-24MB tail or the 24MB-85.6MB Java/VxWorks-kernel
regions is untested; the whole-file 85.6MB sliding-window pass found a
similarly strong but NOT identical peak (`0xf687a020`, 96.3% at 48.3x
chance), consistent with the already-documented "mixes ROM-resident
code with runtime-relocated structures" caveat -- i.e. more than one
base may be in play across the full image, and this finding should not
be assumed to extend past the specific 1.2MB-9MB range it was derived
and verified against.

============================================================================
**UPDATE, immediately following, same session: the "newly-unblocked
next step" above WAS executed -- 330 real, CODE-REFERENCED C++ symbol
names found, a qualitatively new catalog beyond pure string-mining**
============================================================================
Regenerated the full 7,757-candidate prologue list (same `stwu r1,-N(r1)`
+ `mflr r0` signature) across the WHOLE 24MB native region this time
(not a sub-slice), disassembled the first ~200 bytes of each with the
recovered base, and resolved every `lis`/`addi` absolute-address pair
against the FULL 85.6MB file (not just the 24MB region -- string data
can live past it). **330 of 7,757 candidates (4.3%) reference at least
one address landing on readable text.** This is a fundamentally
DIFFERENT, and more useful, catalog than the earlier plain-string-scan
inventory (the 1,476 `.cpp`/`.h` basenames, the 77 `db_*_V0NN`
accessors): those were found by scanning for text patterns anywhere in
the file, with NO way to tell if real code ever touched them (and for
the specific `db_*`/VNode names, direct testing proved they don't).
This new catalog is the OPPOSITE: every entry is a string some real
function's OWN disassembled code actually computes the address of --
guaranteed live, not just present.

**Real, meaningful hits directly relevant to this project's routing/
topology questions** (C++ symbols are GCC-2.x-mangled -- a leading
digit is a length prefix, e.g. `9RoutePath` = the 9-character class
name `RoutePath`, already known from the VNode pipeline write-up
above):
  - `_vt$8MapRoute` and `_vt$13VpRouteGetter` -- real VIRTUAL TABLE
    symbols (the `_vt$<len><Class>` mangling is GCC 2.x's vtable-symbol
    convention) for `MapRoute` and `VpRouteGetter` classes -- their
    existence as vtables means these are real, instantiated,
    polymorphic classes, not just names in a debug pool.
  - `getThinnedRoute_internal__9RoutePathiiii` -- a real `RoutePath`
    method, referenced by a genuine, fully-disassembled function
    (file offset 0x79f364) with a normal prologue/epilogue and several
    virtual (`mtlr`+`blrl`) calls with return-code branching (-5, 1, 2
    checked) -- confirmed via direct disassembly, not just the string
    hit.
  - `newRoutePath__C17MapFlyRouteAccessPQ217M...` -- a `newRoutePath`
    factory-style method on `MapFlyRouteAccess`.
  - `copyRoutePaths: pRoutePathFirs[t]` -- a real runtime debug-log
    string about copying route paths.
  - `findSegIndex` -- referenced by a real, fully-disassembled function
    (file offset 0x815a80) doing exactly the same virtual-call/return-
    code-branching shape as the RoutePath function above.
  - `_14CfcTypeSegment$TYPE_DESCRIPTOR` -- a real RTTI type descriptor
    for a `CfcTypeSegment` class (the `Cfc*` prefix appears throughout
    this catalog -- a large, real application framework this project
    hadn't previously named at this granularity).
  - `_13CFlowSegStore`, `rackSegList` (likely `trackSegList`),
    `eeNodePool` (likely `TreeNodePool`) -- segment/node storage
    classes.
  - `avGraphMatch` (likely `navGraphMatch`) -- a real graph-matching
    function name, directly relevant to route calculation.
  - `heR16ParcelPercentageP15MapRendererBase` (`ParcelPercentage`) and
    `__tf26MDCacheParcelSpanC` (`MDCacheParcelSpan`) -- real parcel-
    cache classes, extending this project's own `eeuz.fea`
    `ParcelHeader` understanding from the code side.
  - `sendSoftWaypointManeuver__C19GuidanceManagerImpl` and
    `nceManeuverProximityFuture8Callback` -- real `GuidanceManagerImpl`
    methods, confirming and naming the maneuver-generator subsystem the
    earlier `mv_*` string catalog only named from debug strings.
  - **One false-lead worth recording so it isn't rechecked**: a real,
    code-referenced string `"No Link available!!!"` was found (2
    separate call sites) -- given this project's own extensive
    same-session "link-id" topology work, this looked like a possible
    confirmation that "link" is the real internal term for a graph
    edge. Checked the surrounding bytes directly: it sits right next to
    `<A HREF="/%s/%d">`/`</A>` HTML-anchor-tag text -- this is an HTML
    HYPERLINK error message (probably from an embedded help/browser
    view), unrelated to routing graph edges. Coincidental word overlap,
    not a real lead.

**Not yet done**: only ~200 bytes per candidate were disassembled (one
string-reference pass, not full function bodies), and only 2 of the 330
candidates were followed up with a complete disassembly (`findSegIndex`
and `getThinnedRoute_internal`'s callers, both real but not yet fully
understood). None of the 330 were cross-checked against the specific
VNode-pipeline names (`db_vid_get_map_id_V000` etc.) -- this
catalog was found independently of that search and doesn't itself
locate those specific functions. Tracing any of these `Route`/`Seg`/
`Node`/`Parcel` classes' real method implementations in full is a
concrete, well-scoped next step for a future session, now that both a
working load base AND a real catalog of live, code-referenced symbol
names exist -- neither was available before this session.

============================================================================
**UPDATE, immediately following, same session: tracing `findSegIndex`'s
caller found a MUCH bigger structure -- a real, large-scale per-function
symbol/EH-descriptor table, ~25,769+ entries, confirmed genuine on at
least 1 case, exact record layout NOT yet fully nailed down**
============================================================================
Disassembled the `findSegIndex`-referencing function (file offset
`0x815a80`) in full: a real, complete function with normal prologue/
epilogue, ending `blr`. It reads the SAME argument pointer twice and
compares it to itself (always true -- a defensive/paranoid-check idiom,
not a bug), constructs a 0x38-byte object via a virtual call, then calls
2-3 more virtual methods (`mtlr`+`blrl`) checking a small integer return
code against {1, 2, -5}, writing a result into `*arg2` on one success
path. This is a C++ container/iterator "find" pattern operating on
ALREADY-PARSED in-memory objects -- architecturally a level above the
raw on-disk `seg_list` bytes, so it does NOT explain the topology
link-id values' on-disk encoding (the original motivating question);
it's a genuine but orthogonal finding.

Searching for `findSegIndex`'s own caller (`bl`/`lis`+`addi` scan of the
full 24MB region, plus a whole-85.6MB-file literal-pointer scan) found
NO direct call, but DID find one raw literal occurrence of its exact VA
at file offset 12,887,552. The surrounding bytes turned out to be a
repeating record format, NOT a simple vtable: a `0x0010,05,<var>`
3-byte-fixed/1-byte-variable marker, a NUL-terminated mangled C++ name,
several header fields, a monotonically-INCREASING 4-byte ordinal
counter (confirmed: 0x6fe6 -> 0x6fe7 -> 0x6fe8 on 3 consecutive records
-- this table has entries in a real, deliberate sequence, not scattered
coincidence), then 5 more 4-byte fields before the next record's marker.
**Real, unambiguous symbol names found this way, independent of and far
beyond the earlier 330-candidate catalog**: `getPOIAlongGuidedRoute__
8MapRouteiii`, `PSD_Ges_Ueberholverbot__C12PSD_Database` (a real German
"no-overtaking" traffic-rule database -- "PSD" un-expanded), `__dl__
13MDPOIDatabasePv` (a real `operator delete` for `MDPOIDatabase`),
`processGetScaleUnitReq__C23CfcMapConfiguration`, `uncompress`,
`vp_set_off_road_or_off_map__FP10master_rec` (directly relevant --
"master_rec" and "off road/off map" strongly suggest a real GPS
map-matching status function). **Scale**: a plain 4-byte marker search
(`\x00\x10\x05\x00` only, the one confirmed variant) already finds
25,769 occurrences file-wide -- since the marker's last byte is
CONFIRMED variable (one real record used `0x0a` not `0x00`), the true
total is higher; this search under-counts.

**What's confirmed vs. still open**: the table's existence, its real
content, and its deliberate/sequential nature (the ordinal counter) are
all confirmed, not speculative. For exactly ONE record (`findSegIndex`)
the LAST of its 5 trailing pointer fields was independently verified to
equal that function's own real, already-disassembled start address.
Tested whether this "last field = code address" rule generalizes on a
2nd record (`getPOIAlongGuidedRoute`): NONE of its 5 fields matched the
strict `stwu`/`mflr` prologue signature -- inconclusive rather than a
refutation, since simple leaf functions can validly omit that exact
prologue shape (no stack frame needed), so this doesn't rule the rule
out, it just isn't confirmed a 2nd way yet. **The exact record
layout/field-role mapping is NOT yet reliably established for general
use** -- building a real bulk name-to-address extractor needs either
more independently-known addresses to cross-validate field position, or
a looser prologue detector (not just the exact `stwu`/`mflr` byte
pattern) to test candidate fields against. This is the single most
promising concrete next step this project now has: if this table can be
parsed reliably at scale, it would give real symbolic names for a large
fraction of this codebase's functions -- something no technique in this
project has achieved before, VNode/`db_vid_get_map_id_V000` included
(not yet checked against this specific table; a natural next test).

**UPDATE, immediately following, same session: that natural next test
WAS run, AT SCALE (26,323 records) -- the "position 4 = code address"
rule is confirmed as a real, dominant signal in aggregate, but NOT
reliable enough yet to trust for any single specific record, including
the highest-value one.** Rebuilt the full known-good prologue set
(7,757 `stwu`+`mflr` addresses, whole 24MB region) and, for every
parsed record, checked whether EACH of its 5 trailing fields lands on
a known-good prologue. Position 4 (the last field) wins decisively: 35
hits vs. 3-6 for positions 0-3, all far above the ~0.05-hit uniform-
chance baseline for this sample size -- a real, non-coincidental
structural signal, not a repeat of the earlier 1-case anecdote.
**However**: extracted `readNodeMP0__9RoutePathUiR5VNode`'s own record
this way (the single highest-value name this table could recover,
given this whole investigation's original goal) and its position-4
field does NOT resolve to valid code -- it lands on more pointer-
looking data (`0xf7de9cf0...`), and none of its OTHER 4 fields resolve
to valid code either (one even decodes as `std`, a 64-bit-only
instruction invalid on this platform's 32-bit PowerPC 603e --
definitely not real code). A 2nd occurrence of the substring
`readNodeMP0` exists elsewhere in the file (offset `0xbf58c2`) with NO
preceding marker at all -- a plain, unrelated string occurrence, not a
2nd table entry. **Honest conclusion**: this table's field-role mapping
is real and mostly correct in aggregate, but almost certainly has
MULTIPLE record "kinds" with different field layouts (plausibly keyed
by the marker's confirmed-variable 4th byte, or by argument-count/
name-length parity) that this session did not have time to
discriminate. Recovering `readNodeMP0`'s real address specifically
needs that discrimination done first -- claiming its address from the
naive single-layout extraction would be overclaiming past what the
evidence supports, so it is deliberately NOT reported as found here.
Concrete next step: classify this table's records by kind (start from
the ~35 confirmed-correct position-4 hits as a "known good, single
layout" training set, and diff their exact byte structure against
records like `readNodeMP0`'s that don't fit) -- genuinely promising,
but unfinished.

**UPDATE, immediately following, same session: the record-kind
hypothesis was tested directly -- REFUTED as the explanation; the REAL
reason `readNodeMP0` fails is a region limit, now precisely
characterized, not a record-layout mismatch.** Compared `readNodeMP0`'s
own record structure (marker 4th byte `0x00`, 13 bytes between name and
the 5 trailing fields) against the 54 confirmed-good records found
above: it matches the SAME "kind" as many of them exactly (e.g. `Dump__
15EHDatagramGraphi`, identical marker byte and identical 13-byte middle
section) -- so a record-layout mismatch is NOT the problem. Checked
instead where ALL 35 confirmed-good position-4 hits' implied addresses
actually land: **100% (35/35) are under 9MB; ZERO are at or beyond
9MB.** `readNodeMP0`'s own implied address (~11.4MB) falls squarely in
that untested territory. Tried the whole-file sliding-window's
alternate base (`0xf687a020`) on the same field -- lands on different
but still non-code content (readable text, `"...lTraffic..."`), not
valid code either. Searched a generous +/-200,000-byte window around
the naive target address for ANY real `stwu`+`mflr` prologue at all:
**zero found** -- not "off by a small calibration delta," a genuinely
empty stretch of a few hundred KB with no recognizable function starts.
This is fully consistent with, and now sharpens, the project's own
earlier prologue-density finding ("match density drops from
900-1,235/MB [1-9MB] to essentially zero from 9MB onward -- the real
code region is ~1.2MB-9MB"): the symbol table's records DO correctly
point at real code for functions living in the verified 1.2MB-9MB
range (confirmed 35 times over), but for functions whose code lives
beyond that range (like `readNodeMP0`), this project has no working
address-resolution technique at all -- not a wrong formula, a genuine
absence of recognizable code at that location under any base tried so
far. Closing this specific thread here: reaching `readNodeMP0`'s real
implementation needs either a fundamentally different base for the
9MB+ region (no candidate found despite trying the one alternate this
project has) or ground truth (a real symbol map, hardware access) this
project doesn't have.

Also found in the same scan: `db_fea_map_V000`, `db_fea_get_layer_
range_V005`, `db_fea_get_file_header_V005`, `db_fea_get_layer_
properties_V005`, `db_fea_read_parcels_V005`, `db_fea_init_V005`,
`db_fea_get_scale_from_subindex_V005` -- real, versioned accessors for
`eeuz.fea` confirming its `ParcelHeader`/layer/scale/subindex structure
(README S3.10, wiki `eeuz-fea-Place-Name-Gazetteer`) is real and
actively used, same pattern of confirmation as the `db_seg_*` catalog.

============================================================================
`.FRG`'s own `b"ZZZZ"` container -- CRACKED (a later session): the fixed
64-byte header, validated exact across 5 independent files spanning 2
different ECU targets and a 94x size range
============================================================================
Every `.FRG` file on this disc (`A_HDD.FRG` for `APPS`, and every
`HOST\SILVER_1\RNSMIDEC\PROG\H_*.FRG` variant checked) opens with the
SAME fixed 64-byte header template, only 2 fields of which vary by
file. As 16 big-endian uint32 words:

    word0  (off 0)   0x5a5a5a5a                 -- "ZZZZ" magic
    word1  (off 4)   0x7d020100                 -- constant, format/version tag
    word2  (off 8)   36                         -- constant: this header's own
                                                    "overhead" size in bytes
    word3  (off 12)  CRC-CCITT (XModem) of payload -- CRACKED, see below
    word4  (off 16)  1                          -- constant
    word5  (off 20)  = (real file size) - 36    -- EXACT, all 5 files tested
    word6  (off 24)  99 (HOST files) / 160 (APPS)-- per-ECU-TARGET constant,
                                                    not size-derived (same value,
                                                    99, across H_PQEE/H_AK/
                                                    H_SB_HDD/H_SE_DAB.FRG despite
                                                    very different file sizes)
    word7  (off 28)  1                          -- constant, = word4
    word8  (off 32)  = word5                     -- exact duplicate (redundancy/
                                                    checksum-style double-store)
    word9  (off 36)  0x69696969                 -- "iiii" marker/sentinel
    word10 (off 40)  33554432 (0x02000000 BE)   -- constant
    word11 (off 44)  1                          -- constant
    word12 (off 48)  0                          -- constant
    word13 (off 52)  32                         -- constant
    word14 (off 56)  2                          -- constant
    word15 (off 60)  16                         -- constant

`word5`/`word8` = `filesize - 36` validated EXACTLY on `A_HDD.FRG`
(85,254,064 bytes), `H_PQEE.FRG` (1,286,592), `H_SB_HDD.FRG`
(1,855,592), `H_AK.FRG` (1,286,592, note: same size as `H_PQEE.FRG` but
a genuinely different file/variant), and `H_SE_DAB.FRG` (994,140) --
zero exceptions, confirming `word2`'s own constant `36` really is this
header's own byte length and `word5` is a real, self-describing payload-
size field (the container knows its own total size, useful for the SWL
loader to validate a clean read/copy before installing).

**`word3` -- CRACKED, a later session (the header's last unresolved
field): a standard CRC-CCITT (XModem variant -- `binascii.crc_hqx`,
polynomial `0x1021`, initial value `0`) checksum of the payload starting
at byte 36** (i.e. everything after the header's own declared 36-byte
overhead, `word2`). Validated EXACTLY on all 5 files, no exceptions --
first noticed because every observed `word3` value happened to fit in
16 bits despite being stored in a 32-bit field (a real CRC32 wouldn't
do that by chance across 5 independent files), which pointed directly
at a 16-bit CRC. This completes the 64-byte `.FRG` header format 100%
-- every field is now understood: magic, format/version tag, header-
size constant, this CRC, a constant, the real payload size (stored
twice), a per-ECU-target constant, and a fixed tail of format
constants. Directly useful: any future session extracting/rebuilding a
`.FRG` file can now validate its own header is well-formed and its
payload hasn't been corrupted, the same way this project's own ISO
read/write tooling already validates other checksummed structures.

Immediately after this 64-byte header, the file's own readable
sub-script begins (see below) -- i.e. bytes 64+ are NOT yet more binary
header, they're the next real content.

============================================================================
`HDD/` -- 2 more real `DLSCRIPT.TXT` commands, and confirmed real
on-unit filesystem paths (a later session, direct follow-up)
============================================================================
`HDD/` has no `.FLI`/`.FRG` payloads of its own -- just 2 variant
`DLSCRIPT.TXT`s (`HDD_20GB`/`NO_HDD`, matching the 2 real hardware
configs `HWIDMAP.TXT`/`PRJCTMAP.TXT` already showed exist elsewhere).
`NO_HDD/RNSMIDEC/CONFIG/DLSCRIPT.TXT` is a trivial no-op (`BOOTMODE_SWL`
/ `SHOW_SCREEN` / `EXPECTED_TIME 240` / `FINISHED_ECU`, nothing
installed). `HDD_20GB`'s own script is real and substantive: a
`MULTI_VERIFY_HDD 3 3 50 2 25 3 25 0 0` integrity-check step (real
command, numeric parameters not decoded), then 22 `FILE_UPDATE <dest>
<byte-size> <src>` commands (a 3rd, genuinely new `DLSCRIPT.TXT`
command beyond `INSTALL_FRAGMENT`/`LOAD_FIB`/`LOAD_LIBRARY`) copying
every `SPEECH/*.ZIP`/`SpeechRes.xml`/`LanguagePackage_version.txt` file
onto the unit's own internal hard disk, e.g.:

    FILE_UPDATE /hdb2/speech/parts/uvo_csCZ_01.zip 16746861 /cddos/SPEECH/UVO_CZ.ZIP

Confirms a REAL on-unit filesystem mount point, `/hdb2/speech/...`
("hdb2", plausibly "hard disk B, partition 2"), and gives the real
locale-code-to-disc-filename mapping for every one of the 14 `UVO_*.ZIP`
voice packs (`csCZ`=Czech, `deDE`=German, `enGB`=British English,
`enGM`=a 2nd English variant, `esES`=Spanish, `frFR`=French,
`itIT`=Italian, `nlNL`=Dutch, `ptPT`=Portuguese, `svSV`=Swedish,
`trTR`=Turkish, `plPL`=Polish, `noNO`=Norwegian, `ruRU`=Russian,
`arAE`=Arabic) -- this disc's own real byte-size arguments match the
real on-disc `SPEECH/*.ZIP` file sizes exactly (same convention
already confirmed for `DLSCRIPT.TXT`'s other commands, above).

============================================================================
`.FRG`'s own embedded sub-script -- a genuinely new, small command
vocabulary, extending `DLSCRIPT.TXT`'s own (both found this session)
============================================================================
Right after the 64-byte header, `H_PQEE.FRG` (and presumably every
`.FRG`) embeds its own short, real, plain-text script:

    INSTALL_IMAGE 15
    INSTALL_IMAGE 23
    INSTALL_ALL_LOG_DB
    SET_LOG_DB_STATUS 2 2
    STORE_FRAGMENT
    FINISHED_FRAGMENT

4 of these 5 distinct commands (`INSTALL_IMAGE`, `INSTALL_ALL_LOG_DB`,
`SET_LOG_DB_STATUS`, `STORE_FRAGMENT`, `FINISHED_FRAGMENT`) do not
appear anywhere in `DLSCRIPT.TXT`'s own vocabulary (which uses
`INSTALL_FRAGMENT`/`LOAD_FIB`/`LOAD_LIBRARY`/etc, README S2.6) --
real, additional, per-fragment-internal directives the outer
`DLSCRIPT.TXT`'s `INSTALL_FRAGMENT` step hands off to once it opens
this specific `.FRG`. Immediately following this tiny script:
`"Copyright 1984-2001 Wind River Systems, Inc."`, `"VxWorks"`,
`"VxWorks5.5.1"`, and a real dated build stamp `"Sep 25 2012,
11:33:51"` -- confirms the separate `HOST` processor ALSO runs VxWorks
5.5.1 (same RTOS version already confirmed for `APPS`, README S2.1),
and gives a real, independent build timestamp ~1 month before this
disc's own `VERSION.TXT` date (2012-10-19). Standard zlib inflate
error strings follow (`"oversubscribed dynamic bit lengths tree"`,
etc) -- confirms zlib is linked into the `HOST` image too, consistent
with this whole project's own already-established zlib-based
FLAT_COMPRESSED/MAP_COMPRESSED decompression scheme.

============================================================================
Other ECU images -- a first pass, real new findings, not deeply pursued
============================================================================
`DAB\1\RNSMIDEC\PROG\DAB.FLI` (3.2MB) -- **a genuinely new discovery**:
the DAB digital-radio tuner runs on a **Texas Instruments DSP**, not the
same PowerPC/VxWorks platform as everything else on this disc. Real,
clean, readable startup banner:

    ************* Current Configuration: *********************
    DSPLink Version:          dsplink_sla_1_62_02
    PSP DRx40x:               Version 1.1.4.3
    EDMA3 driver used:        Version 1.05
    Number of ADE instances:  %d
    Number of AEE instance:   %d
    Radio configuration: DAB
    Starting J2VIS. Build Date: %s, Time: %s
    Platform Initialization complete

`DSPLink`/`EDMA3`/`PSP` (Platform Support Package) are real, standard TI
DSP/BIOS ecosystem terms -- `DSPLink` is TI's own cross-processor (ARM
host <-> DSP) communication framework, `EDMA3` its DMA controller
driver. A real, independent dated build stamp: `"Mar  2 2012,
13:55:04"`. "J2VIS" is plausibly this DAB decoder software's own
internal codename. This is a 3rd distinct processor architecture in the
whole system, alongside the already-known PowerPC/VxWorks (`APPS`/
`HOST`) and the already-identified ST10F276E/TMS470 satellite MCUs
(README S2.2) -- not previously documented anywhere in this project.

`VUCI\B101\RNSMIDEC\PROG\GATEWAY.FLI` (864KB, the already-identified
MOST-bus/CAN gateway, README S2.2's ST10F276E): real strings
`"NO_BOOT"`/`"NO_BOOTSW"` and a heavily-repeated `"ipcRP_uart"` token --
consistent with a real inter-processor-communication-over-UART
mechanism on this chip, not decoded further.

`RADIO\1\RNSMIDEC\PROG\RADIO.FLI` (896KB): mostly compiled/compressed
binary, one real embedded source path found: `"..\..\libraries\
frameworks\osAbsLayer\sources\osAbsLayer.c"` -- a 3rd-party "OS
Abstraction Layer" framework, distinct from the `navicore`/`dbal`
codebase this whole project otherwise studies. Not investigated
further.

`MPEG\1\RNSMIDEC\PROG\MPEGAPPS.FLI` (2MB): mostly compiled/compressed
binary, no real source paths or identifying banners found in a first
pass; one recognizable fragment, `"DEBUG: R"` / `" @ 0x%08"`, suggesting
real printf-style debug logging exists but wasn't captured intact by
the plain-string scan (likely broken up by intervening binary bytes).
Not investigated further -- a real, open, low-priority lead for a
future session (this ECU is peripheral to the map/navigation work this
project otherwise focuses on).

None of `RADIO`/`MPEG`/`DAB`/`VUCI`'s images showed any `.cpp`/`.h`
source-path strings at all (0 hits each, vs. hundreds/thousands in
`FHDD6.FLI`/`CTEST.OUT`) -- consistent with these being built without
debug info, or from a different (non-Siemens/Continental in-house)
codebase entirely for at least some of them (`osAbsLayer`, the TI DSP
stack).

============================================================================
NOT done this session
============================================================================
- `INFO/CDSTRUCT.CFG` (25,955 lines) was characterized (grammar, keyword
  set, the real dated comment header) but not fully parsed line-by-line.
- `WA/*.WSH` shell scripts, `SPEECH/FRG/*.FRG` (44 files) and
  `SPEECH/*.ZIP` (24 files, though `HDD/HDD_20GB`'s own `DLSCRIPT.TXT`
  now confirms their real on-unit destination paths and locale codes,
  above) were enumerated by name/size only, not opened. `HOST`/`RADIO`/
  `MPEG`/`DAB`/`VUCI` got only a first-pass string scan (above), not a
  deep investigation. `HDD` itself was fully checked (no `.FLI`/`.FRG`
  payloads exist there at all -- confirmed, not just unexamined -- see
  above).
- `CTEST.OUT`'s `.debug_info`/`.debug_abbrev`/`.debug_line` -- ALL
  CRACKED, a later session: see `research/dwarf2_reader.py`, a real,
  validated DWARF2 parser giving a complete function-name-to-byte-range
  map for all 35 real functions across its 4 compilation units,
  cross-validated exactly against `.symtab`, plus the real compiler
  identity (`GNU C gcc-2.96 (2.96+ MW/LM) 19990621 AltiVec VxWorks
  5.5`) and real internal build path (`F:\Entwicklung\e60-tools\
  CodingTest\cp2\PPC603gnu` -- directly extends README S2.1's already-
  known "navicore, codename e60" identity to this factory-test module
  too). `.debug_line`'s own real line-number-program state machine was
  added too, giving an exact address-to-(file,line) map, validated
  against `.debug_info`'s own function `low_pc` values (e.g. address
  5736 maps to both `RegServiceAvailableCB`'s own `low_pc` AND to
  `RegTest.c:16`, an independent cross-check). `.debug_pubnames`/
  `.debug_aranges` remain unparsed (lower priority, largely redundant
  with `.debug_info`/`.debug_line`).
- The 0-24MB native-PowerPC region's rich debug-STRING table was mined
  (source paths, the `dbaLib` dynamic-loader log strings, 77 versioned
  `db_*_V0NN` accessor names -- see above). Locating or disassembling
  the actual CODE behind any of those names WAS attempted (a `lis`/
  `addi` string-cross-reference load-base recovery, 39,715 candidate
  pairs tested against 7 known string offsets) and hit a real,
  documented wall: no consistent load base was found, most likely
  because these strings are DWARF-`.debug_str`-like debug-only data
  never referenced by executing code (see the detailed writeup above).
  This is a genuine dead end for THIS specific technique, not an
  unexplored gap — a different technique (real ground truth from
  external tooling or hardware) would be needed to go further.

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
