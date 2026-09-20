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
