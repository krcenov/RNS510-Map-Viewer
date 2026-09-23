# RNS510 Firmware & Map Reverse-Engineering / Editing Project

Personal reverse-engineering project on a VW RNS-510 navigation head unit, covering both
the application firmware and the navigation map database, working toward a tool that can
open a map ISO, edit its content (roads, POIs), and produce a new ISO the unit will load.

**Status at a glance:** editing/adding roads by name + coordinates is fully working and
tested (GUI tool below). Making a *newly added* road visible on the rendered map display
is not yet solved on real hardware, but the two format pieces that stood in the way are
now both decoded — the rendering tile's geometry format is fully readable/writable
per-feature (§3.6: anchor+delta block format, multi-feature delimiting both cracked and
validated), and the per-vertex topology/adjacency table that follows the geometry in
each tile now has its node-id<->coordinate mapping cracked too (§3.6/§8 item 5:
`resolve_topology_adjacency()`, validated edge-by-edge against two independent real,
human-verified ground-truth tiles) — so a valid topology entry for a newly inserted
road's own vertices can now be synthesized in principle. What (if anything) real
hardware actually needs from that table to render/route a new road correctly remains
untested on real hardware — see "Open problems" at the end. Separately, the
long-unexamined `eeuz.fea` file is now understood at the "what is it" level (§3.10):
a multi-language place-name gazetteer (cities, seas, islands, road-shield labels) —
not road geometry at all, which is why no previously-cracked file ever showed a lake
or a sea label. Its directory record format is now cracked (a big-endian
offset/length index, not coordinate data — see §3.10), but three independent
coordinate-attachment hypotheses (embedded per-record value, `.cty`/`.cl` join,
per-section/per-sub-tile granularity) have all been tested and refuted, so
per-record geolocation remains unavailable except via embedded name lookup.

---

## 1. The two source materials

- **Firmware / software ISO**: `RNS510_5238_MOD_C3_C4.iso` (717MB) — an unofficial "SWL"
  (Software Loading) disc for the Continental/VDO "CP2" RNS510 platform, hardware variants
  C3/C4A/C5C/C6/C10/C12, VW software index 5238. This is the application/OS software, not
  map data.
- **Map ISO**: `CD_8555.ISO` (~6.48GB) — a genuine official VW navigation map disc,
  "EU East V17", Navteq database EEU (East Europe) 2019Q1, VW part number `1T0051859AR`.
  This is what the editing tool works on.

Maps and application software are separate products on this platform; the firmware ISO
never contains map data, and vice versa.

---

## 2. Firmware findings

### 2.1 Architecture
The unit's application processor runs **VxWorks 5.5** hosting an embedded Java VM
(**Insignia Jeode EVM**). The touchscreen UI is a Java application (packages
`vdo.rns.*`, `vdo.most.*`, `vdo.nav.*`, `vdo.bsl.*` — Siemens VDO/Continental in-house
codebase). The actual navigation/routing engine is **native PowerPC code**, internally
named **"navicore"** (codename "e60"), running on a **Freescale/Motorola MPC5200/5200B**
SoC, built with a Wind River GCC 2.96 cross-toolchain.

All three layers — native navicore code, the Java class store, and the VxWorks
kernel/BSP — are packed into one file: `APPS\SILVER_1\RNSMIDEC\PROG\FHDD6.FLI` (85.6MB):
roughly 0–24MB native PowerPC, 24–76MB Java classes, 76–85.6MB VxWorks kernel/BSP.

### 2.2 Satellite chips identified (not the main application processor)
Two other automotive MCU datasheets were checked against the unit's known hardware
descriptions and don't run the UI/nav engine (way too little RAM), but likely handle
sub-systems:
- **ST10F276E** (STMicroelectronics, 16-bit, 64MHz, 68KB RAM, dual CAN) — matches the
  size of `VUCI\B101\...\GATEWAY.FLI`/`GWBOOTL.FLI`; almost certainly the **MOST-bus/CAN
  gateway** controller.
- **TMS470MF04207** (TI ARM Cortex-M3 automotive safety MCU, 24KB RAM, dual CAN) —
  likely tied to the `SYS_CODE_SYSTEM_SAFE`/immobilizer-style security-code subsystem
  seen in the menu tree. Unconfirmed.

### 2.3 Full menu tree (recovered from compiled class names)
Every screen/overlay the UI can show is a `vdo/rns/ui/Menu_<NAME>Rules` or
`MenuNet_<NAME>Rules` class. Full inventory (86 unique screens) is in the chat history;
categories: Startup/System, Navigation/Map, Radio/Tuner, Media/Audio, Video, Phone,
Traffic/TMC, Setup, and Test/Service (`TESTMODE`, `TESTMODE_SYSTEM`,
`TESTMODE_DAB_MONITOR_MAIN`, `SERVICE` — likely technician diagnostic screens, not yet
investigated further). **Notably absent**: no Climate Control or Parking Sensor screen
exists anywhere in the menu tree — those subsystems only have backend status-integration
classes (audio ducking, icons), never a navigable screen, in this firmware build.

**Destination-entry UI classes found (corroborating, not proving, the `.rt`/`.rl`/`.prl`
hypothesis below)**: `research/class_name_inventory.txt` contains a
`vdo/rns/app/nav/std/ctrls/addressentry/` package with `AECitySuggestionList`,
`AEStreetSuggestionList`, `SuggestionCityItem`, `SuggestionStreetItem`, `AESpellerType`
(a letter-by-letter spelling/input control), and `AESpeechInputStringCA` — i.e. a real,
distinct "type letters, get narrowing city/street suggestions" screen exists in the
firmware, matching the on-unit UI described in §3.7's hypothesis. The actual native
search implementation behind these classes is reached only through
`vdo/rns/app/nav/std/ctrls/edalwrapper/EdalWrapper*` (a generic native-navicore search
bridge also used for POI/gas-station/search-along-route lookups — not destination-entry
specific), and — like all real method bodies in this firmware, §2.4 — is compiled in the
still-uncracked "romized" bytecode format, so which on-disc file(s) actually back
`AECitySuggestionList`/`AEStreetSuggestionList` cannot be confirmed by decompilation.
This is corroborating evidence that the real UI has exactly the kind of search screen
`.rt`/`.rl`/`.prl` would plausibly serve, not proof that they do.

### 2.4 UI customization — blocked
Most Java class bodies in the store use a proprietary "romized"/pre-linked constant-pool
format from the embedded JVM's ROM-build toolchain (not standard `javac` bytecode).
Only trivial classes (interfaces with no real method bodies) survive in standard,
decompilable form. This blocks decompiling/patching the interesting UI logic
(`ClimateControlAdapter`, `SystemBundle`, etc.) with normal tools. A later attempt to
find the underlying native code's parsing logic via Ghidra/PowerPC disassembly also hit
a wall: the ~0–24MB native region isn't a single flat statically-linked image (mixes
ROM-resident code with runtime-relocated heap/RTTI structures), so a load-base address
couldn't be recovered. **Net effect: UI-level modding (new buttons/screens) is not
currently achievable** — pivoted this project to map editing instead, which turned out
to be much more tractable.

### 2.5 Extensions Database (EDB) — a real, limited customization API
`vdo.nav.api.edb.*` is a JDBC-like client to an embedded SQLite engine in the native
navicore process (confirmed via literal SQL strings like
`INSERT OR IGNORE INTO Tiles VALUES (?1,?2,?3,?4,?5)`). Clients can only call a fixed
catalog of precompiled statement templates, not arbitrary SQL. Confirmed real use: POI
databases (`.db3` files under `EDB/POI/`, matches the map disc's own `EDB\POI` folder),
satellite-radio song tagging, weather/traffic tile caching. Schema is point data only
(name/lat/lon) — **no road geometry or routing fields**, so this cannot be used to add
roads, only custom POIs ("Personal POI" is an explicit, supported list type).

### 2.6 `5238_ALL` — the real factory Software-Loading (SWL) CD, found and extracted this session
A later session, at the user's direct prompt (`C:\Users\krcenov\Desktop\
rns510\5238_ALL`), found and extracted a SEPARATE disc from the map disc
`CD_8555`: a real Continental/VW factory "Software Loading" CD (VwSwIndex
5238, matching this section's own already-known firmware generation) —
`VERSION.TXT` confirms `CdTreeBuilder version 3.06`, `#VwSwPartNumber:`
lists **18** real VW part numbers (re-verified directly against the raw
file, corrected from an earlier miscount of 15 — the field wraps across
2 lines, easy to undercount): `1T0035680L`, `3T0035680G`, `7F0035680B`,
`7E0035680B`, `1T0035680P`, `1T0035680Q`, `3T0035680K`, `3T0035680L`,
`1T0035686`, `1T0035686C`, `1T0035686D`, `7F0035686`, `7E0035686`,
`3T0035686`, `3T0035686C`, `3T0035686D`, `7N5035686`, `2H0035680` — one
per real vehicle-specific installation kit. `#Steckbrief: C_EU_13.236_t3
C3/C4A/C5C/C6/C10/C12` names 6 codes — **corrected**: these are NOT
vehicle platform codes as previously stated here; `INFO/CDSTRUCT.CFG`'s
own `#ifdef HARDWARE_C3`/`HARDWARE_C4A`/etc. blocks confirm they're
internal Continental HARDWARE-REVISION codes for the head unit's own
PCB (mapped to sequential numeric IDs under the same `SILVER_1` product
line), not vehicle codes. Discloses this exact image is `"an unofficial
SWL CD by josi"` (a community repack, not verified byte-identical to the
original factory CD, though CRC.16 files throughout the tree would make
tampering detectable). **`ECUORDER.TXT`
+ `INFO/CDSTRUCT.CFG`** (25,955-line `#ifdef`-guarded flashing script,
with a real, dated 2006-2008+ internal Continental/VW engineering
changelog as its own leading comment block — named engineers, real
`TlaWtz#`-numbered bug IDs, real project-line codenames) confirm the
real ECU flashing order: `APPS`/`HOST`/`HDD`/`RADIO`/`MPEG`/`SPEECH`/
`DAB`/`VUCI`, one top-level folder per target (`VUCI` = the already-
identified MOST-bus/CAN gateway, §2.2). `HWIDMAP.TXT`/`PRJCTMAP.TXT`
(plain text) are real hardware-ID→revision (`SILVER_1`/`SILVER_6`) and
per-vehicle-config-ID→project-variant lookup tables.

**`DLSCRIPT.TXT` — CRACKED, genuinely new**: each project variant's own
`CONFIG/DLSCRIPT.TXT` is a real, plain-text, line-oriented flash-
programming script (`INSTALL_FRAGMENT`/`LOAD_FIB`/`LOAD_LIBRARY`/
`RUN_SHELL_SCRIPT`/`COMPARE_REG_ID ... GOTO <label>`/`UPDATE_SYS_CONFIG`/
`FINISHED_ECU`) — every declared byte-size argument matches its real
on-disc file's exact size. This directly shows how `APPS\SILVER_1\
RNSMIDEC\PROG\FHDD6.FLI` (§2.1's already-examined 85.6MB application
image) actually reaches the unit: `INSTALL_FRAGMENT` first applies
`A_HDD.FRG` (85,254,064 bytes, real magic `"ZZZZ"`), then `LOAD_FIB`
writes `FHDD6.FLI` itself. `COMPARE_REG_ID 0x091C 0x09 <lang> ...` is a
real per-language branch chain confirming register `0x091C` is the
on-unit language-selection value the factory tool reads before
installing the matching `SPEECH/FRG/LANG_*.FRG`+`RECOG_*.FRG` pair.

**`.FRG`'s own `"ZZZZ"` container — CRACKED, a later session**: the
fixed 64-byte header, validated EXACTLY across 5 independent files
spanning 2 ECU targets and a 94x size range (`A_HDD.FRG` for `APPS`;
`H_PQEE.FRG`/`H_SB_HDD.FRG`/`H_AK.FRG`/`H_SE_DAB.FRG` for `HOST`). As 16
big-endian uint32 words: `word0`=`"ZZZZ"` magic; `word1`=constant
`0x7d020100`; `word2`=constant `36` (this header's own byte length);
`word4`/`word7`=constant `1`; **`word5`/`word8` (a redundant duplicate
pair) = `(real file size) − 36`, exact with zero exceptions across all
5 files**; `word6`=a per-ECU-TARGET constant (99 for every `HOST` file
tested regardless of size, 160 for `APPS`'s `A_HDD.FRG`); `word9`=a
`0x69696969` ("iiii") marker; `word10`-`word15`=6 more fixed constants.
**`word3` (offset 12) — CRACKED, a later session, completing this
header 100%**: a standard CRC-CCITT (XModem variant, polynomial
`0x1021`, initial value `0`) checksum of the payload starting at byte
36, validated exactly on all 5 files (first spotted because every
observed value fit in 16 bits despite the 32-bit field — not chance
across 5 independent files, and a direct pointer at a 16-bit CRC). Right
after this header, each `.FRG` embeds its own small real plain-text
sub-script — genuinely new commands beyond `DLSCRIPT.TXT`'s own
vocabulary: `INSTALL_IMAGE`/`INSTALL_ALL_LOG_DB`/`SET_LOG_DB_STATUS`/
`STORE_FRAGMENT`/`FINISHED_FRAGMENT` — followed by a real, dated
VxWorks 5.5.1 build banner (`"Copyright 1984-2001 Wind River Systems,
Inc."`, `"Sep 25 2012, 11:33:51"`) confirming the separate `HOST`
processor runs the SAME RTOS version as `APPS` (§2.1), plus standard
zlib inflate error strings confirming zlib is linked there too.

**A first pass over the other, previously untouched ECU images found
one genuinely new architectural discovery**: `DAB\1\RNSMIDEC\PROG\
DAB.FLI`'s own real, clean startup banner (`"DSPLink Version:
dsplink_sla_1_62_02"`, `"PSP DRx40x: Version 1.1.4.3"`, `"EDMA3 driver
used: Version 1.05"`, `"Starting J2VIS. Build Date: %s, Time: %s"`,
dated `"Mar  2 2012, 13:55:04"`) confirms the DAB digital-radio tuner
runs on a **Texas Instruments DSP** — `DSPLink`/`EDMA3`/`PSP` are real
TI DSP/BIOS ecosystem terms — a 3rd distinct processor architecture in
this whole system, alongside PowerPC/VxWorks (`APPS`/`HOST`) and the
already-known ST10F276E/TMS470 satellite MCUs (§2.2), not previously
documented anywhere in this project. `VUCI`'s `GATEWAY.FLI` shows real
`"NO_BOOT"`/`"ipcRP_uart"` strings (an inter-processor-communication-
over-UART mechanism); `RADIO.FLI` references a 3rd-party `osAbsLayer.c`
framework distinct from the `navicore` codebase; `MPEGAPPS.FLI` showed
no clear identifying strings in this first pass. None of these 4 show
any `.cpp`/`.h` debug-string paths at all, unlike `FHDD6.FLI`/
`CTEST.OUT` — consistent with different (non-Siemens/Continental)
codebases or debug-stripped builds. Not investigated further; real,
open, low-priority leads for a future session.

**`HDD/` has no `.FLI`/`.FRG` payloads of its own — just 2 variant
`DLSCRIPT.TXT`s.** `NO_HDD`'s is a trivial no-op; `HDD_20GB`'s is real
and substantive: a `MULTI_VERIFY_HDD` integrity-check step, then 22
`FILE_UPDATE <dest> <size> <src>` commands (a 3rd genuinely new
`DLSCRIPT.TXT` command) copying every `SPEECH/*.ZIP` voice pack onto
the unit's own internal hard disk — confirming a real on-unit
filesystem mount point (`/hdb2/speech/...`) and the real locale-code-
to-disc-filename mapping for all 14 `UVO_*.ZIP` packs (e.g.
`FILE_UPDATE /hdb2/speech/parts/uvo_csCZ_01.zip 16746861 /cddos/
SPEECH/UVO_CZ.ZIP`).

**`FHDD6.FLI` re-examined — one refutation, no new crack**: a raw ELF-
magic scan over the whole 85.6MB file finds 4 hits inside the
already-identified 76-85.6MB VxWorks-kernel region (§2.1) — all 4 are
FALSE POSITIVES (each one's own `e_shoff`, followed as if real, points
at incoherent garbage, unlike a genuinely valid ELF). Documented so a
future session doesn't repeat the same naive scan expecting a hit; does
not affect or extend §2.4's own separate, already-documented
disassembly wall on the 0-24MB native region.

**`WA/CTEST.OUT` — CRACKED, genuinely new**: a small (89,576-byte),
COMPLETE, standalone 32-bit BE PowerPC `ET_REL` ELF object — same
container family as `dbal/*.OUT` (§3's `dbal/` bullet) but, unlike
those, small enough that its own section-header table parses cleanly,
exposing a full `.symtab`/`.strtab` (102 real symbols) AND real DWARF
debug sections (`.debug_info`/`.debug_line`/`.debug_abbrev`, not
parsed). Real source files: `CodingTest.c`/`RegTest.c`/
`ConfigFblockTest.c`/`ctdt.c` — a factory ECU CODING/diagnostics test
utility (`TestCoding`/`SetCodingHex`/`ResetEcu`/`configLogin`), NOT part
of the navigation core. Real imported API surface reveals a genuine,
named application lifecycle framework on this platform —
`bootMgrNotifyStartupAchieved`/`RunupAchieved`/`RundownAchieved`/
`ShutdownAchieved`, `bootMgrAddShutdownConsumer`,
`svcb_addServiceListener` — plus direct MOST-bus calls
(`cc_tla_most_addSink`/`cc_tla_most_send`/
`cc_tla_most_getLocalDeviceId`), confirming §2.2's inferred MOST-bus
gateway chip from the actual call-site side. **Successfully
disassembled** with `capstone` (newly installed this session, not
previously used in this project) — a real function (`TestCoding`)
decodes to a textbook GCC-PowerPC-ELF prologue and a `.rela.text`-
relocated external call sequence, confirming both the disassembler and
this project's understanding of the platform's PowerPC ABI are correct
— a real, reusable capability for any future session that wants to read
compiled logic on this platform directly, not just embedded strings.
**`FHDD6.FLI`'s own 0-24MB native region — mined for debug strings (not
disassembled), an enormous, load-bearing payoff**: 1,476 distinct real
`.cpp`/`.h` source basenames found in a single representative 5.3MB
slice alone (far beyond `dbal/`'s own ~330-path inventory). **The
complete, real, end-to-end `dbal/` dynamic-loading mechanism is
directly confirmed from the firmware's own runtime log strings**
(`"dbaLib: best matching dbal.out version on DVD: V%03d_%03d"`,
`"now unload DBAL version: V%03d_%03d"`, etc.) — the firmware detects
which DBAL version the inserted disc requires, searches `dbal/` for a
matching (or best-compatible) `V0NN_0MM/DBAL.OUT`, and dynamically
loads/unloads it as discs are swapped — explaining exactly why 5
separate builds ship side by side (§2.6's `dbal/` cross-reference,
§3's own `dbal/` bullet). **A catalog of 77 real, versioned `db_*_V0NN`
accessor function names** was extracted, independently confirming field
names this project had only inferred from `eeu.mod`'s own authoring-tool
schema: `db_seg_marker_left_V004`/`db_seg_marker_right_V004` (an exact
name match to `eeu.mod`'s own fields), `db_seg_rank_V004`/`_speed_V004`/
`_tunnel_V004`/`_node_V004`/`_unique_vid_V005` (the still-open
MAP_COMPRESSED `seg_list` wall, §3.16), `db_tmc_all_headers_V003`/
`_deprecated_V005` (independently re-confirming the `db_tmc_deprecated`
correction above, this time from the accessor names themselves, not
just file coexistence), `db_get_parcel_dir_V005`/`db_load_pcl_dir_V005`
(the `eeuz.fea` parcel directory), `db_check_junction_view_V006` (the
V009_038-added junction-view schema), and `db_us_state_from_segment_
V008` (independent evidence of a real NA-specific map-data code path,
alongside the already-found `CPhonemeNA*Handler` split). **A direct
attempt to locate the CODE behind these names was made and hit a real
wall**: no `\x7fELF` magic anywhere in the 0-24MB region (ruling out any
surviving ELF/DWARF structure to parse), and a `lis`/`addi` string-
cross-reference load-base recovery (39,715 candidate absolute-address
pairs, tested against 7 known accessor-name strings) found no
consistent load base — each string's own top candidates are unrelated
to every other string's. Most likely explanation: these are DWARF-
`.debug_str`-like debug-only strings, structurally never referenced by
executing code, so no code-side cross-referencing technique can locate
them — a genuine, structural dead end for this line of attack, not an
unexplored gap. **Confirmed a 2nd, independent way, a still-later
session**: built and validated a real DWARF2 parser
(`research/dwarf2_reader.py`) against `WA/CTEST.OUT`'s own
`.debug_info` (a complete, correct 35-function map, exactly cross-
checked against that file's `.symtab`, plus the real compiler identity
`GNU C gcc-2.96 (2.96+ MW/LM) 19990621 AltiVec VxWorks 5.5` and a real
internal build path `F:\Entwicklung\e60-tools\CodingTest\cp2\PPC603gnu`
— "e60" directly extends §2.1's own already-known navicore codename to
this factory-test module too). Every one of that file's compilation
units carries this exact producer string — searching for it (and
related build-path fragments) across the whole 24MB `FHDD6.FLI` region
found **zero hits**, despite 1,476+ distinct source-file basenames
implying hundreds of compilation units that would each carry one if
real `.debug_info` survived. Direct, structural confirmation — not just
an absence-of-correlation inference — that no real DWARF info exists
there, only a bare stripped string pool.

**Confirmed a 3rd, independent way, a still-later session**: built and
ran a pattern-based PowerPC function-prologue finder (the fixed 8-byte
signature `stwu r1,-N(r1)` immediately followed by the byte-invariant
`mflr r0`, confirmed against `WA/CTEST.OUT`'s own real disassembled
function) — finds 7,757 real, low-false-positive candidate function
starts across the 24MB region. This does NOT fix the correlation
problem, but characterizes it precisely: match density drops from
900-1,235/MB (offsets 1-9MB) to essentially zero from 9MB onward — the
real code region is ~1.2MB-9MB, and the debug-string region (rich from
~8.9MB onward) starts right where code ends. Checked distance from 5
known accessor-name strings to their nearest real prologue: 194KB to
2.3MB — code and debug strings are genuinely separate, non-adjacent
regions by construction, not just unlucky. The prologue-finder works
exactly as designed; without a surviving symbol table there's still no
way to know WHICH of the 7,757 real functions is any specific named
accessor. Full details: `research/swl_5238_reader.py`.

**A still-later session built a real PowerPC emulator (Unicorn) as a
candidate classifier**, feeding a fake record pointer to thousands of
the 7,757 prologue matches and logging which small offsets each one
reads. Validated (matches `CTEST.OUT`'s known `TestCoding` exactly) and
confirmed the technique finds real, correctly-decoded logic — but "reads
a couple of small bytes near offset 0-4 of arg1" turned out to be too
common a shape across this codebase to be selective on its own: 2
strong-looking candidates were disassembled and confirmed unrelated (a
time conversion, a mode dispatcher). One candidate (VA `0x001f95d0`) is
a stronger match — it reads `mg4`'s `id`/`byte1`/`length` fields and
walks a multi-table lookup/linked-list chain, consistent with a
name/junction resolver rather than a plain accessor, refining (not
proving) what `byte1` feeds into. **All 8 candidates this classifier
ever surfaced were eventually disassembled**: 3 more confirmed
unrelated (a 2nd mode dispatcher; a floating-point node/coordinate
bounding-box test; a record-reset function whose offset-6/7 usage as 2
separate bytes conflicts with the confirmed `length` field, so it's
likely a different record type), 2 inconclusive. `0x1f95d0` remains the
only real lead, and its own caller could not be found 3 independent
static ways, nor could its lookup tables be read back from the file
(they resolve to RAM addresses outside the file's own size) — a genuine,
multi-angle dead end for this candidate, honestly documented rather than
left implied-promising. Full details:
`research/swl_5238_reader.py` and `research/map_compressed_reader.py`'s
`decode_topology()` docstring.

**Re-run against `mp0`'s own predicted field offsets, a still-later
session, over the FULL 7,757-candidate pool** (earlier passes only
covered the shortest 3,000-5,000): zero candidates matched `mp0`'s exact
zone-2/zone-3a byte positions combined with their tag/type bytes — a
real negative result. The overall read-offset distribution across all
1,393 loosely-matching candidates is dominated by 4-byte-ALIGNED offsets,
consistent with most short functions here operating on regular,
word-aligned runtime structs, not packed on-disk bytes directly. Two
disassembled candidates are genuinely informative anyway, though neither
is confirmed `mp0`-specific: one reconstructs an unaligned 32-bit value
from 4 individual byte reads for a table lookup, and one does real
bit-level unpacking (`rlwinm` mask/rotate) of packed bits into a
normalized runtime table — the architectural shape this project has
suspected (a decode/unpack layer between compressed tile bytes and any
named accessor) but never directly observed before. Full details:
`research/swl_5238_reader.py`.

**A complete, real, NAMED pipeline for the long-standing GLOBAL
routing-graph "topology node-id↔coordinate mapping" problem** (§3.2's
`vnodeID` lead, distinct from the ALREADY-CRACKED per-tile local vertex
adjacency, §3.6/§8 item 5) was found the same way: `db_vid_get_
map_id_V000`/`db_vid_get_pcl_id_V000` ("vid" = virtual id, i.e.
`vnodeID`) resolve a virtual node id to its owning map/parcel;
`db_find_node`/`db_node(i_toNode, &vNode)` then loads the real `VNode`
struct (confirmed field `vsegIDs[]`); `readNodeMP0__9RoutePathUiR5VNode`
reads a `VNode` directly from an `.mp0` MAP_COMPRESSED tile as part of
building a `RoutePath`; a large real maneuver-generator subsystem
(`mv_*`, source path `navicore/common/mnvr/mv_vnode.cpp`) consumes these
VNodes for real turn-by-turn guidance. Names only, byte-level encoding
still unrecovered — but this gives a concrete validation path (cross-
check a guessed `vnodeID` bit-split against `eeuz.fea`'s own
`ParcelHeader` directory or MAP_COMPRESSED's own tile directory) that
didn't exist before. Also found: `db_fea_map_V000`/`db_fea_get_
layer_range_V005`/`db_fea_read_parcels_V005`/etc, confirming `eeuz.fea`'s
own `ParcelHeader`/layer/scale/subindex structure (§3.10) the same way.
Full details: `research/swl_5238_reader.py`.

**BREAKTHROUGH, a still-later session: the load base WAS recovered,
overturning §2.4's "no recoverable load base" conclusion for
`FHDD6.FLI`'s 0-24MB native region's code-dense 1.2MB-9MB sub-range.**
The earlier `lis`/`addi` string-cross-reference attempt failed for a
real, now-understood reason: its 7 anchor strings are genuinely
never referenced by executing code (a DWARF-`.debug_str`-like pool).
A different technique sidesteps that: disassembled the region
instruction-by-instruction (capstone, every 4-byte-aligned offset
independently, no linear-stream drift), collected 34,652 `lis`+`addi`
absolute-address pairs, and ran a brute-force sliding-window scan over
the sorted targets — **95.1% (32,966/34,652) cluster inside one 24MB
window, 170x the uniform-random chance rate.** Exact base recovered and
verified 3 independent ways, byte-exact, zero discrepancy: `VA =
file_offset + 0xf688dcf4`. A pair's computed target lands EXACTLY on a
real runtime log string (`"bootMgrLax : Now I'm going to create the
image -"`) found independently by plain search; another lands EXACTLY
on a real, fixed-width UI button-label table (`PLAY`/`SEARCHBACK`/
`SEARCHFOR`/`STOP`/...), hit identically by 4 separate call sites; a
broader spot-check turned up more coherent real content (C++ mangled
class names, XML-like config fragments) without cherry-picking. This
reopens real disassembly of this sub-range with capstone — previously
blocked entirely. Does NOT yet locate any specific named accessor
(those names live in the confirmed-unreferenced debug-string pool);
whether the same base holds outside the verified 1.2MB-9MB range is
untested, and the whole-file sliding-window pass found a close but
NOT identical peak (`0xf687a020`), consistent with the region mixing
more than one addressing base. Full details, all verification
commands, and the concrete newly-unblocked next step (disassembling
the 7,757 known prologue candidates for real, now that a base exists):
`research/swl_5238_reader.py`.

**That next step was executed immediately after, same session: 330 of
7,757 prologue candidates (4.3%) reference at least one real,
CODE-LIVE string** — a fundamentally different, more useful catalog
than the earlier pure-string-scan inventory, since every entry is
something a real function's own disassembled code actually computes
the address of (guaranteed referenced, unlike the confirmed-dead
`db_*_V0NN`/VNode-pipeline debug-string pool). Real hits directly
relevant to this project's own routing/topology questions: `_vt$8MapRoute`/
`_vt$13VpRouteGetter` (real vtables — confirmed instantiated,
polymorphic classes), `getThinnedRoute_internal__9RoutePath` and
`newRoutePath__C17MapFlyRouteAccess` (real `RoutePath` methods, one
fully disassembled and confirmed as a genuine virtual-call-driven
function), `findSegIndex`, `_14CfcTypeSegment$TYPE_DESCRIPTOR`,
`_13CFlowSegStore`, `eeNodePool` (likely `TreeNodePool`), `avGraphMatch`
(likely `navGraphMatch`), `heR16ParcelPercentageP15MapRendererBase`
(`ParcelPercentage`) and `MDCacheParcelSpan` (real parcel-cache classes),
and `sendSoftWaypointManeuver__C19GuidanceManagerImpl` (naming, not just
string-hinting, the maneuver-generator subsystem). One false lead
recorded so it isn't rechecked: a real, code-referenced `"No Link
available!!!"` string turned out to be an HTML-hyperlink error message
(sits beside literal `<A HREF=...>` markup), not a routing-graph "link"
despite the tempting word match. None of the 330 have been traced to a
complete understanding yet — a concrete, well-scoped next step for a
future session. Full catalog and every verification command:
`research/swl_5238_reader.py`.

**Tracing `findSegIndex` further, immediately after, found something
bigger: a real, large-scale (~25,769+ entries) per-function symbol/EH-
descriptor table** — a repeating record format (a 4-byte marker, a
NUL-terminated mangled name, header fields, a monotonically-increasing
ordinal counter confirmed across 3 consecutive real records, then 5
trailing pointer fields). Real names recovered this way, independent of
and beyond the 330-candidate catalog above: `getPOIAlongGuidedRoute__
8MapRoute`, `PSD_Ges_Ueberholverbot__C12PSD_Database` (a real German
no-overtaking traffic-rule database), `__dl__13MDPOIDatabasePv`,
`processGetScaleUnitReq__C23CfcMapConfiguration`,
`vp_set_off_road_or_off_map__FP10master_rec`. **Confirmed real, not
speculative** — `findSegIndex`'s own record has one field exactly
equal to its independently-verified, already-disassembled function
start address. **Not yet confirmed at scale**: that same "field 5 =
code address" rule didn't validate on a 2nd test record (inconclusive,
not refuted — likely because that record's function is a simple leaf
function that validly omits the exact prologue byte pattern this
project checks against). Building a reliable bulk name-to-address
extractor from this table — which would give real symbolic names for a
large fraction of this codebase, unmatched by anything found so far —
is now this project's single most promising concrete next step. Full
details: `research/swl_5238_reader.py`.

---

## 3. Map database findings

The map disc's `files.cfg` (plain text, disc root) documents **39** logical file types
(`numFileIds = 39` — road, city, county, intersection list/offset, POI index, map
layers, etc., each with its own one-line comment — not all 39 are actually populated
on this specific disc, see §3.17) and 4 compression types: `0`=NOT_COMPRESSED,
`1`=FLAT_COMPRESSED, `2`=MAP_COMPRESSED, `3`=FEATURE_COMPRESSED. Filenames follow
`eeu.<ext>` when uncompressed and **`eeuz.<ext>`** (note the `z`) when compressed. All
are for the East Europe (`eeu`) dataset on this specific disc.

### 3.1 `eeu.rd` — road/routing graph (590MB, NOT_COMPRESSED) — CRACKED
- 94-byte header: ASCII `SIEMENS`, `(C) SIEMENS AG`, version strings. **3 more
  fields in this same header CRACKED this session (found while investigating
  `eeu.aff`, §3.12, but verified across every NOT_COMPRESSED file on the
  disc)**: `bytes[84:86]` (uint16 LE) is a small per-logical-file-type code,
  unique per file (`eeu.rd`=4, `eeu.cty`=3, `eeu.typ`=1, ...); `bytes[86:88]`
  (uint16 LE) is that file's own **record count, truncated to 16 bits** —
  confirmed exact for every fixed-record file checked, including ones whose
  real count exceeds 65,536 (e.g. `eeu.rd` itself: 8,809,081 mod 65536 =
  27,257, matching the header exactly; `eeu.cty`: 939,351 mod 65536 = 21,847,
  also exact) — genuinely useful for a not-yet-examined file: dividing
  `(filesize - 94)` by this field (adding multiples of 65,536 if the result
  isn't a clean integer) is a fast way to guess a real fixed record size
  without fully reverse-engineering the body first; `bytes[90:94]` (uint32
  LE) is the file's own total size in bytes — exact for 18/22 NOT_COMPRESSED
  files checked, with 2 confirmed exceptions storing the BODY size instead
  (`eeu.iof`, `eeu.mod` — both off from the real total by exactly 94, the
  header's own size) and one unexplained mismatch (`eeu.cal`).
- Then fixed **67-byte records**, no gaps: `(filesize - 94) / 67` records exactly
  (8,809,081 on the reference disc).
- Each record = **24-byte binary header + 43-byte null-padded ASCII name**.
- Verified fields in the 24-byte header:
  - `bytes[8:12]`: longitude, little-endian int32, degrees = value / 100000
  - `bytes[12:16]`: latitude, little-endian int32, degrees = value / 100000
- Verified against two independent real locations: records near the start decode to
  Linosa, Sicily; records ~300MB in decode to Timișoara, Romania. Both match real street
  names at those coordinates.
- Unresolved fields (preserved as-is when editing, zero-filled as best-effort when
  appending new records): `byte[0]` (high entropy), `bytes[1:5]` (candidate road-class/
  one-way flags — cross-checked against `eeu.typ`, no match found;
  **CORRECTED, later session, §3.3**: a full-file-scale scan finds
  **6,174 distinct values**, not "~5 distinct patterns" as this section
  previously reported from a much smaller sample — no single value
  covers more than 0.41% of records. Tested against `eeu.si` (§3.20):
  decoding `bytes[1]` with `eeu.si`'s own exact `rank`/`class`/`divided`
  bit layout produces values filling the full 0-7/0-15 range rather than
  `eeu.si`'s own bounded 0-4/0-12 ranges, so `eeu.rd` does not directly
  embed `eeu.si`-style flags that way; also tested for correlation
  against `eeu.iof`'s own common-case `count` field and found none
  (`r ≈ -0.02`, essentially zero) — see §3.3 for the full methodology),
  `bytes[5:8]` (3-byte LE, often shared across same-name records — candidate
  shared-geometry pointer), `bytes[16:20]`/`bytes[20:24]` (two more LE uint32 fields,
  small values, candidate cross-references — not matched to another file yet).

### 3.2 `eeu.il` — name/intersection index (39MB, NOT_COMPRESSED) — CRACKED
- Same 94-byte header. Variable-length entries: `[11-byte prefix][ASCII name][0x00]`.
- `bytes[0:4]` of the prefix (little-endian uint32) is a **verified exact record index
  into `eeu.rd`**, referring to *that same entry's* name (confirmed by decoding 20 real
  entries and cross-checking against `.rd` — corrects an earlier off-by-one guess).
- Remaining 7 prefix bytes unresolved (best-effort: copied from a nearby similar entry
  when appending).

### 3.3 `eeu.iof` — parallel array to `.rd` (52.8MB, NOT_COMPRESSED) — PARTIALLY CRACKED; a real "nearby street names" pointer mechanism found and validated for a ~0.36% subset, and which records become anchors substantially narrowed
- Same 94-byte header, then fixed **6-byte records**, exactly the same count as
  `eeu.rd` (`(filesize - 94) / 6` matches). One entry per road record, same order.
- Layout: `[uint32 LE "zero4"][uint8 "vb"][uint8 "c80"]`. The earlier
  `[00 00 00 00][varying byte][0x80 constant]` sketch (from only 15 hand-checked
  records) is an approximation of the COMMON case only — at full-file scale
  (8,809,081 records) neither `zero4` nor `c80` is a true constant: `zero4` is
  nonzero for 31,318 records (0.3555%), and `c80` is something other than `0x80`
  for a comparable-sized minority.
- **CRACKED this session, for the 31,318 records with nonzero `zero4`**: `zero4`
  is an **absolute byte offset into `eeu.il`**, and `vb` is a **count of
  consecutive `.il` entries** to read starting there — together, one road
  record's own list of OTHER nearby street names. Validated at scale against the
  real ISO: 858/1000 randomly sampled `zero4` values land byte-exact on a real,
  parseable `.il` entry (`[11-byte prefix][name][0x00]`, §3.2's already-cracked
  format), and of those, 100% resolve (via the entry's own embedded `eeu.rd`
  index) to a real road whose name matches the entry's own string. Chaining
  exactly `vb` such entries from `zero4` and validating every one the same way
  succeeds end-to-end on the large majority of a 500-record sample. **Geographic
  clustering, 30 random anchors, every one**: every entry in an anchor's own
  list resolves to a real `eeu.rd` record within a few km of the anchor's own
  coordinates (`eeu.rd` is NOT spatially sorted, so this clustering cannot be
  chance). The anchor's own name is essentially never inside its own list
  (1/300 sampled) — a list of OTHER nearby roads, not self-inclusive. Anchor
  names are frequently bare route/highway codes (`R102`, `T0803`, `B32`, `L73`,
  `SS1`, `D-400`) rather than full street names. **Practical reading**: looks
  like a real "pick an area, browse its street names" catalog — independent
  evidence for the same kind of destination-entry UI need §3.7's `.rt`/`.rl`/
  `.prl` hypothesis addresses, from a completely different file. Which (if
  either) the real unit's own address-entry screen actually uses is
  unconfirmed on hardware.
- **`eeu.mod`'s real field names** (§3.16, checked in a later session): this
  table is `intersectionOffsetFile`, with 4 real leaf fields —
  `offset`, `countAndType` (a wrapper), `type`, `count`. Confirms/renames
  what was already found: `offset`=`zero4`, `count`=`vb`. `c80` is really
  `type`, and its value shape now makes clean sense as a discriminator:
  `type=0x80` (bit 7 set) is the "no real anchor" default; confirmed
  anchors show `type` in `{0, 1}` (bit 7 clear) — plausibly bit 7 = "is
  this a real offset/count pair", with 0/1 a genuine 2-valued sub-type
  for real anchors. Not independently confirmed beyond this value-shape
  observation.
- **A later session's cross-reference attempts for the common-case
  `count`/`vb`**: one real, moderate correlation found — `count` for
  `zero4==0` records correlates positively (Pearson `r ≈ 0.21`, over the
  739,211 `eeu.rd` records referenced at least once) with how many
  `eeu.il` entries reference that same `eeu.rd` record elsewhere in the
  file (built by parsing all 1,448,723 real `eeu.il` entries); records
  `eeu.il` references at all have roughly DOUBLE the mean/median `count`
  of records it never references (mean 7.23 vs. 3.82, median 5 vs. 2) —
  a real, statistically significant signal, not an exact per-record
  formula. **Two hypotheses tested and refuted**: `eeu.rd`'s own
  `bytes[1:5]` does not correlate with `count` (`r ≈ -0.02`; this also
  corrected that field's own "~5 distinct patterns" claim to 6,174
  distinct values at full scale — see §3.1); a coordinate-grid local-
  road-density proxy (a literal intersection-count hypothesis, given the
  file's own real name) shows only a weak correlation (`r ≈ 0.04-0.15`).
- **A later session: which records become anchors, substantially
  narrowed (route-numbered roads strongly, not exclusively, enriched)**.
  Anchor names were tested against a simple "route-code-like" pattern
  (short, mostly-numeric, optional 1-4 letter prefix — `B215`/`SP246`/
  `L1`/`SS18`/`331`-shaped). At FULL FILE SCALE: 6.00% of all 8,809,081
  `eeu.rd` records match (528,463), vs. **44.80%** of the 31,318 anchor
  records (14,031) — anchors are **7.5x more likely** to have a
  route-code-like name, a real, large, full-scale-confirmed enrichment,
  visually obvious on inspection (`B215`, `SP246`, `L551`, `L1`, `T1810`,
  `SS18`, `N23`, `B96`, `L675`, interleaved with genuine settlement/
  street names). **Not a clean 1:1 rule though**: of the 528,463
  route-like-named records in the whole file, only 2.66% become anchors
  — combined with the already-confirmed geographic clustering and
  "anchor's own name almost never in its own list" findings, the most
  consistent picture is anchors being a curated, DEDUPLICATED subset —
  roughly one anchor per distinct real-world route/road identity, not
  one per `eeu.rd` segment (a single route like `B215` has many separate
  segment records along its length). Which specific segment of a
  multi-segment route gets picked, and what determines the remaining
  ~55% of settlement-name anchors, is still open.
- **A later session's 3rd `count` cross-reference, tested and REFUTED**:
  `eeuz.rl`'s own per-`eeu.rd`-index reference count (§3.7's cracked
  `.rl` `bytes[0:4]` "candidate index into `eeu.rd`" field, built the
  same way as the `.il`-reference-count correlation, over all
  46,432,934 `.rl` records) shows a slightly NEGATIVE correlation with
  the common-case `count` (`r ≈ -0.08`) — weaker than even the weak
  `.il` signal (`r ≈ 0.21`) and the wrong sign to be the same underlying
  quantity, despite `.rl` covering a much larger fraction of `eeu.rd`
  (95.0%, 8,372,058/8,809,081 records) than `.il` (8.4%, 739,211
  records).
- **Still open**: (1) the common-case `count`'s exact meaning beyond the
  `eeu.il`-reference-count correlation above (now 3 hypotheses tested:
  `eeu.il` reference count — weak positive; local road density — weak;
  `eeuz.rl` reference count — weak negative, refuted); its real range is
  0-255, heavily skewed toward small values (2/1/3/0/4 are the 5 most
  common, >70% of records combined). (2) the exact anchor-selection rule
  beyond the route-number enrichment above. (3) `type`'s exact bit-level
  meaning beyond the 0x80-vs-{0,1} discriminator (rare 129-255 outliers
  on the common-case side, and 2-7 on a few confirmed anchors, aren't
  individually explained). (4) whether an anchor's own list is ordered
  by anything checked (alphabetical: no, only 16/100 sampled; distance/
  on-disk-order: not tested).
  Full methodology, every validation number, and concrete next-step
  suggestions: `research/iof_reader.py`'s module docstring.

### 3.4 `eeu.typ` — street-type word dictionary (105KB, NOT_COMPRESSED) — CRACKED
- 94-byte header + exactly 2,574 fixed **41-byte records**:
  `[40-byte null-padded name][1-byte type code (0-3)]`.
- Contains localized street-type words used to compose full names (e.g. `AUTOSTRADA`,
  `BULEVARDI`, `RRUGA`, `SHESHI`), not a numeric road-class table — does not explain
  `.rd`'s unresolved `bytes[1:5]`.

### 3.5 FLAT_COMPRESSED (`eeuz.rt`, `.rl`, `.prl`, `.prd`, `.cl`, `.ct`, `.pct`, `.pca`) — CRACKED
Format (verified byte-for-byte, reusable reader: `research/flat_compressed_reader.py`):
```
offset 0  : 3 bytes ASCII "zip"
offset 3  : 1 byte version (always 1 observed)
offset 4  : uint32 LE block_size            (3072 in every file checked)
offset 8  : uint32 LE total_uncompressed_size
offset 12 : uint32 LE val3                  (meaning unconfirmed/reserved)
offset 16 : offset table, uint32 LE x (ceil(total_size/block_size)+1),
            offs[i]..offs[i+1] delimits block i's compressed bytes
```
Each block is an independent standard zlib stream decompressing to exactly `block_size`
bytes (remainder for the last block). Concatenating all blocks reproduces the exact
original logical file. Verified on `eeuz.pca` (decompresses to a clean phoneme/name
catalog: "EUROPE", "AUSTRIA", ...) and confirmed at scale on `eeuz.rt`.

`eeu.rt` (road tree), once decompressed, has a body size that divides evenly by 67 —
the same record size as `.rd` — suggesting it may reuse/derive from `.rd`'s road
records (e.g. a sorted or spatial-index view). (Superseded — see §3.7: this specific
hypothesis was tested and refuted; §3.7 also documents the CRACKED character-trie
structure `.rt` actually uses.)

**`eeuz.prd` — CRACKED: a phonetic pronunciation catalog for road
names**, presumably feeding the same text-to-speech engine `eeuz.pca`'s phoneme
catalog serves (voice guidance). This file's content had never been examined
before the session that cracked its record framing — only its FLAT_COMPRESSED
container was known. Decompresses to 572MB
(599,975,088 bytes). Record format, **validated at FULL scale (every byte of the
decompressed file)**: 94-byte header, then self-delimiting variable-length records
back-to-back — `[uint8 name_len][name][uint8 phon_len][phon][uint32 LE roadID][uint32 LE
minNumber][uint32 LE maxNumber]`. Parsing the ENTIRE decompressed body this way consumes every
byte with **zero leftover/misaligned bytes at EOF**, producing exactly 11,960,527
well-formed records — about as strong a structural confirmation as a variable-length
record format can get without an explicit spec.
- **`name`**: the full human-readable name, type word FIRST, natural spoken order
  (e.g. `"VIA LIDO AZZURRO"`) — unlike `.prl`'s `;`-demoted sort-key form (§3.7).
- **`phon`**: a phonetic transcription (custom/X-SAMPA-like), `|`-separated
  syllables, `"` = primary stress, `%` = secondary stress. Confirmed genuinely
  linguistically correct across unrelated language families: Italian `"GUITGIA"` →
  `kon|"tra|da "gwit|dZa` (`dZ` = correct voiced postalveolar affricate for
  Italian soft "gi"); Norwegian `"E75"` → `"e: s2|ti|"fem` (literally "E syttifem"
  = "E seventy-five", spoken out — genuine number-to-speech, not digit-by-digit
  playback); Norwegian `"341"` → `"tre: ""h}n|dr@ %O f2|ti|"e:n` ("tre hundre og
  førtién" = "three hundred and forty-one").
- **`roadID` — CRACKED**: a direct `eeu.rd` record index. Validated on a 5,000-record
  random sample spanning the whole file: 100% are valid indices, and 100% of those
  have `eeu.rd`'s own (type-word-free) name as an exact substring/suffix of this
  record's own `name` field. Coverage: 5,981,409/8,809,081 (67.9%) of `eeu.rd`
  records have at least one `.prd` entry; most get 1-3 (2 is the single most common
  count: 2,721,836 roads).
- **`minNumber`/`maxNumber` — CRACKED (later session): a real house-number
  address range**. `eeu.mod`'s own schema (§3.16) names this table `phRoad`
  with exactly these 2 field names after `roadID` — immediately explaining
  why the two hypotheses originally tried (nearby-road index; same-name
  count) both failed: neither field was ever a pointer or a count.
  **Validated EXHAUSTIVELY, not sampled**: `minNumber <= maxNumber` holds
  on every single one of the 11,960,527 records in the file, zero
  exceptions. 3,171,255 records (26.5%, matching the earlier-observed
  "`f2==0` for 26.5%" finding exactly) have `minNumber==maxNumber==0` — no
  house-number data for that road (plausible for piazzas, footpaths, and
  other non-addressed ways). Real, plausible examples: `"VIA LIDO
  AZZURRO"` → `47-49` (a short street); `"VIA DEPOSITI"` → `1-95` (a
  longer one). Also explains why the pair is IDENTICAL across every one
  of a road's own multiple `.prd` entries (§3.5's original observation) —
  a house-number range is a property of the road segment itself, not of
  any one phonetic-name variant. **A genuine cross-file curiosity, not a
  contradiction**: `eeuz.rl` (§3.7) independently declares its own
  `minNumber`/`maxNumber` pair, but that copy is ALWAYS ZERO on this disc
  — two different tables sharing the schema's naming convention,
  populated inconsistently at build time. A real, useful side finding
  from the original session: where a road has multiple entries, a
  common (not universal) pattern is one bare-name entry plus one
  `"<name>, <containing place>"` entry (`eeu.cty`'s own naming convention, §3.8) —
  e.g. plain `"VIA CRISTOFORO COLOMBO"` alongside `"VIA CRISTOFORO COLOMBO, LAMPEDUSA
  E LINOSA"` — plausibly for disambiguating a common street name by speaking the city
  too. Full methodology and every validation number: `research/prd_reader.py`'s
  module docstring.

**`eeuz.pct` — CRACKED this session: a phonetic pronunciation catalog for CITY
names**, the same family as `.prd` above (record shape: name + phonetic
transcription, same phonetic alphabet) but for major place names instead of
roads, and covering many languages per place rather than one entry per road
segment. Decompresses to 27,386,579 bytes. **Validated at full file scale**:
parsing the entire decompressed body as `[uint8 name_len][name][uint8
phon_len][phon][6-byte group]` consumes every byte with zero leftover,
producing exactly 649,956 records.
- **The 6-byte trailing "group" field reliably clusters every language's name
  for the SAME real place — validated directly, not just plausible-looking**:
  group `744f180bf414` (26 members) is `VENEDIG`/`VELENCE`/`VENETSIA`/
  `VENICE`/`VENISE`/`BENÁTKY`/`VENETIA`/`VENEZA`/... — every member a genuine
  real name/exonym for Venice, Italy; group `e4ac7f072c00` (26 members) is
  Vatican City in 26 languages (`VATIKÁNVÁROS`, `CIUDAD DEL VATICANO`, `CITTÀ
  DEL VATICANO`, `VATICAN CITY`, ...); Munich and Frankfurt am Main groups (22
  members each) show the identical pattern. 314,645 distinct group values
  across 649,956 records; median group size 2. The single largest "group"
  (`000000000000`, 73,396 members) is a **sentinel for "no cross-language
  grouping"** (consistent with this project's established `0`
  = unset/padding-sentinel convention elsewhere, e.g. the false-edge topology
  bug, §3.6/§10 "v16 → v17") — its members are small, single-language-looking
  local place names, not a real 73,396-way collision.
- **The group VALUE's own derivation — CRACKED in a later session (§3.16)**:
  it's `[uint32 LE offset][uint16 LE count]` — `eeu.mod`'s own real field
  names for this exact table are `.../phonemeRoadOffset/phonemeRoadCount`,
  a pointer into `eeuz.prd` naming that city's own road/route phonetic
  entries (multi-language name variants of one city correctly share the
  same value because they all point at the same city's same roads — not a
  "language-variant grouping key" as first guessed). Three earlier
  hypotheses (sequential/byte-offset index into `eeu.cty`; byte offset
  into `eeuz.fea`) were tested and refuted before the real answer turned
  up via `eeu.mod`'s schema; validated directly against real `eeuz.prd`
  content (Venice lands next to real ferry routes `VENEZIA-CORFÙ`/
  `VENEZIA-PATRASSO`, Vatican City among real Italian streets, Munich and
  Frankfurt among their own real streets). Full methodology:
  `research/pct_reader.py`'s and `research/mod_reader.py`'s module
  docstrings.

### 3.6 MAP_COMPRESSED (`eeuz.mp0`, `.mg1`-`.mg4`) — MOSTLY CRACKED; `eeuz.fea` DIFFERENT, UNCRACKED
These are the actual map-rendering tile layers (`mp0` = most detailed/primary,
`mg1`→`mg4` = progressively generalized for lower zoom levels). **CONFIRMED, a
later session, directly from the real RNS510 unit's own on-screen behavior**
(the user has the actual hardware running this exact disc): each layer is a
real ROAD-CLASS tier, not just a generic "less detail" simplification —
`mg4`=highways, `mg3`=main roads, `mg2`=boulevards, `mg1`=main streets,
`mp0`=everything else (local/residential streets and smaller roads). Directly
validated: a real A1/Trakia motorway segment near Sofia is present in `mg4`
but a real local one-way street (Vladimir Bashev, Sofia) is NOT present
anywhere near its own real coordinates in `mg4` (nearest anchor match was
~6-7km away) — only found in `mp0`, exactly matching this hierarchy.
Sizes on the reference disc: mp0 ≈ 2.14GB, mg1 ≈ 240MB, mg2 ≈ 113MB, mg3 ≈ 46MB,
mg4 ≈ 16.5MB. `eeuz.fea` (≈553MB) is nominally the same family but is actually
**compressionType 3 (FEATURE_COMPRESSED)**, not type 2 — it uses a genuinely different,
still-uncracked directory encoding (see below).

- Header: 80 bytes, different template from the plain-SIEMENS one:
  `(*$SIEMENS&^)` + `Copyright 1998` + version strings, no padding after — directory
  data starts immediately at byte 80.
- **Directory region** (byte 80 up to the first tile), has two sub-parts:
  1. **Geo-index prefix** (byte 80 → `table_start`; ~87.7KB for mg4's 6,110 tiles,
     ~14.4 bytes/tile) — **not cracked**. Variable-length records starting with an
     ascending uint32 counter, plus more fields; naive parsing becomes unreliable past
     the first ~10 records (small integers collide). Some embedded 4-byte values,
     divided by 100000, land in plausible Eastern-Europe lat/lon ranges (matching
     `.rd`'s coordinate convention) — a plausible-but-unproven lead that this is a
     geographic index mapping a coordinate/grid cell to a row in the flat table below.
     **This is what you'd need to look up "which tile covers lat/lon X,Y" from
     scratch, or to register a brand-new tile where none exists yet.**
  2. **Flat offset/length table** (`table_start` → first tile) — **CRACKED and
     validated at scale**: a fixed 8-byte record per tile, in physical tile order:
     `uint32 LE offset` (absolute file offset of the tile) + `uint16 LE decompressed
     length` + `uint16 LE compressed length` (== byte gap to the next tile). Validated
     by exact match against real decompressed data: 6,110/6,110 tiles on mg4,
     16,503/16,503 on mg3, 34,209/34,209 on mg2, 80/80 sampled on mp0. Caveat: lengths
     are uint16, capping any single tile at 65,535 bytes (comfortably true on every
     file checked so far). **This is enough to resize/relocate/edit a tile that
     already exists and is already known by ID** — rewrite its entry, shift every
     later tile's offset by the size delta.
  3. `eeuz.fea` does not use this table format at all — its first real tile was found
     fine (offset 11,727,784), but the literal offset value doesn't appear anywhere in
     its ~11.8MB pre-tile region. Different encoding (relative offsets, different
     unit, or keyed by feature/road ID instead of sequential tile order). Unresolved.
- **Tile data** (after the directory): hundreds of thousands of **independent, standard
  RFC1950 zlib streams**, packed back-to-back with **zero padding** between them
  (verified: each tile's consumed byte length exactly equals the offset gap to the
  next one). Reusable reader: `research/map_compressed_reader.py` — `find_tiles()`
  (brute-force, scans for zlib headers + verifies full decompression — slow but
  thorough), `find_first_tile()` (cheap, locates just the first tile, rejects
  false-positive zlib-header matches via a compression-ratio plausibility check),
  `read_directory()` (fast: ties `find_first_tile` + flat-table parsing together,
  returns `{geo_index_start, geo_index_end, table_start, table_end, num_tiles,
  entries: [(offset, declen, complen), ...]}` — 0.06s on mg4, 0.885s on the 2.1GB mp0;
  raises cleanly on `fea`), `decompress_tile()`, `pack_table_entry()` (inverse, for
  writing an edited entry back).
- **Decompressed tile content** (worked example: `eeuz.mg4` tile at file offset
  139500, 2276 decompressed bytes; anchor/vertex findings below apply identically to
  mg2/mg3/mg4):
  - `0x0000`: magic `0x0146` (constant across every tile sampled)
  - `0x0002`-`0x0017`: small header fields — uint16 values never exceed ~2000 in any
    sample, ruling this out as a direct geo-anchor (would need values in the
    ~1M-7M range for degrees×100000); more likely local tile-relative extents/counts.
    Not decoded.
  - `0x0018` onward: spatial sub-index made of **individual uint16 LE words** (not
    uint32 pairs as first guessed) — each word is either `declen` (the tile's own
    decompressed length, used as an "empty cell" sentinel) or `0` (a second pad
    marker). Ends at a variable but heavily-clustered position: **byte 326 for ~83%
    of tiles** (mg2/mg3/mg4), byte 24 for sparse/degenerate tiles, occasionally 328.
    `mp0`'s sub-index is deeper/differently shaped — the fixed-326 shortcut doesn't
    transfer to it directly.
  - **At `data_start` (end of sub-index): a 2-byte tag/count field (undecoded), then
    the tile's absolute geographic anchor** — `data_start+2`: int32 LE **longitude**
    (degrees = value/100000), `data_start+6`: int32 LE **latitude** (same scale) —
    then `data_start+10`: start of the int16 LE (dx,dy) delta-coordinate run, same
    /100000 scale, decoded relative to the anchor. (Corrects the earlier guess that
    the first delta pair itself was an anchor/preamble — the real anchor sits right
    before the delta run, not inside it.)
  - **Validated, not just hypothesized**: decoding the full delta chain for `mg4`
    tile_id 2231 (anchor 21.20056°E, 45.58739°N) produces a first vertex
    (21.20062, 45.58711) that is an **exact match to 5 decimal places** with a real
    `eeu.rd` road record named "DC158" near Timișoara, Romania — this single result
    confirms the anchor offset, its scale, and the delta-run decoding all at once.
    Independently cross-checked geographically too: an `(ITA)`-labeled `mp0` tile
    decodes to (8.53°E, 39.3°N), Sardinia — correct.
  - **Intra-tile feature/polyline delimiting — CRACKED and validated at scale**:
    the "2-byte tag/count field" documented above (at `data_start`, right before
    the anchor) is not a tag — it is a **point count for that feature's delta run
    specifically**. The coordinate region is a sequence of self-delimiting
    **feature blocks** packed back-to-back with no padding, starting at
    `data_start`:
    ```
    +0  uint16 LE  point_count (N) -- deltas in THIS block only
    +2  int32  LE  anchor longitude (degrees = value/100000)
    +6  int32  LE  anchor latitude  (degrees = value/100000)
    +10 N * (int16 LE dx, int16 LE dy)  -- cumulative from the anchor
    ```
    block size = `10 + 4*N` bytes, and the next feature's block starts exactly
    there. Blocks are read until a candidate's anchor fails the geographic
    plausibility check — that byte offset is where the coordinate region ends
    and the tagged per-vertex record table below begins. Reusable reader:
    `decode_features(raw, declen)` in `research/map_compressed_reader.py`.
    **Validated**: scanning the 80 largest tiles in `eeuz.mg4` and exact-integer
    matching every decoded vertex of every decoded feature against `eeu.rd`'s
    own int32 coordinate fields (same rigor as the original single-feature
    "DC158" match — bit-exact, no float rounding), 20/80 tiles produced **2 or
    more features that EACH independently landed an exact hit on a DIFFERENT
    real named road** — i.e. genuinely separate polylines, not one long chain
    that happens to pass near several roads. Cleanest example: the tile at file
    offset 11,298,518 (declen 10,386) decodes to exactly 2 features — a
    392-point chain exact-matching 10 distinct named roads near Iași, Romania
    (DC138, DN28, PETRU PONI, ION NECULCE, GARABET IBRAILEANU, ION CREANGA,
    STADION, PETRU GROZA, MATEI CORVIN, NEAGOE BASARAB, VLAD TEPES, MIHAI
    VITEAZU) and an independent 154-point chain exact-matching 2 different named
    streets (ROZELOR, NARCISELOR), anchors ~370m apart in the same tile. Also
    confirmed working on `mp0` (e.g. a tile near Geneva/Franco-Swiss border
    exact-matches 24 named streets — CHANCY, BELLEGARDE, AVUSY among them — and
    one near Prague exact-matches 7, including the real district "MALÁ STRANA").
    **Known caveat**: the greedy plausibility-based stop can occasionally accept
    a few small (0-6 point) trailing "phantom" blocks with no corresponding
    `eeu.rd` record at all before it finally hits real tagged-record bytes and
    stops (seen in `mg4` tile_id 4284: parses as 12 blocks, but only the two
    large ones — 306 and 109 points — exact-match named roads; the 10 tiny ones
    in between match nothing). These may be genuine unlabeled stub segments or
    a few bytes of the still-uncracked topology table that happen to look like
    a tiny valid block by chance — undetermined. This does not affect the large,
    validated features, but means "number of blocks" isn't a fully trustworthy
    feature count in isolation.
  - **⚠→✅ Threshold bug in `decode_features()`/`_find_data_start()` — FIXED
    and re-validated at scale.** The plausibility check used to reject false
    anchors (`_looks_like_real_chain()`) originally used a flat magnitude
    cutoff (`thresh=3000`, added to fix `mp0`'s dense sub-index false-positive
    problem, see below), which was too tight — it rejected some LEGITIMATE
    large shape-point gaps (real chains routinely have individual gaps over
    3,000 units, sometimes over 30,000 on `mp0`) and fell through to a wrong
    bruteforce split as a result. Concretely, this mis-split this section's own
    canonical 2-feature example (`eeuz.mg4` offset 11,298,518), reporting a
    bogus 24-point false feature at byte 824 instead of the correct 392+154
    split. **Fix**: replaced the magnitude cutoff with a distinct-value/
    repetition discriminator — real (dx,dy) deltas are almost always distinct
    from each other even when individually large, whereas a dense sub-index's
    cell values, misread as a delta run, are dominated by one repeated/
    ramped-then-flat value (e.g. `11478` repeating 7-8 times in a 24-value
    sample). The new rule requires ≥55% of a 12-pair (24-value) sample to be
    distinct, with **zero false rejections measured on 1,159 confirmed-real
    mp0 chains** (vs. 71.8% false-reject rate for the old magnitude
    threshold), while still correctly rejecting every hand-inspected
    sub-index echo. **Re-validated after landing the fix**: the Iasi tile now
    correctly decodes as 392+154 points; a full re-scan of the 80
    largest-declen `mg4` tiles found **28/80** with 2+ independently-matched
    named roads (up from the previously-reported 20/80 — the increase is
    tiles that were being silently mis-split by the old bug and are now
    recovered); full-file `build_geo_index()` coverage is unchanged on both
    `mg4` (6,106/6,110, byte-identical) and `mp0` (194,650/194,705), but on a
    1,500-tile `mp0` sample the new discriminator's named-road hit rate
    (a correctness lower bound) is 67.1%, vs. only 44.1% for the old
    magnitude-threshold "fix" and 55.3% for no verification at all — i.e. the
    new discriminator beats both the buggy fix and the original
    pre-`mp0`-fix behavior it was built to replace. Full writeup and numbers:
    `_looks_like_real_chain()`'s docstring in `map_compressed_reader.py`.
  - **⚠ Second, DIFFERENT bug found — "oscillating overrun" — root-caused;
    detector REDESIGNED this session (multi-cluster scan + split
    reassembly), still OPT-IN only (not safe to enable by default).**
    Found while building the map viewer (§10) and rendering a real area
    near Sofia, Bulgaria (`mg3`, lon=23.33750/lat=42.69055): two decoded
    features contained huge (24–33km) single-step jumps, oscillating
    between two near-fixed latitude bands while longitude crept slowly
    forward — a shape no real road produces. Root cause (concrete byte
    evidence in `_find_oscillation_clusters()`'s docstring): unlike the
    already-validated "one feature legitimately chains several distinct
    named roads" pattern above, cross-referencing all 8 biggest jump
    endpoints against the full 8,809,081-record `eeu.rd` found **zero
    matches** — this is not real geometry. Both bad blocks' anchors pass
    `_find_data_start()`'s verification (which only samples the first ~12
    pairs), but partway through the SAME declared block the bytes stop
    being real deltas and become some other still-unidentified
    fixed-stride structure. `decode_features()`'s per-block loop never
    re-validates a block's content once its `point_count` field is read,
    so it happily decodes the rest of the declared count as bogus
    vertices.
    **Original mitigation's negative result (previous session)**: a
    density-based statistical discriminator
    (`_find_oscillation_cutoff()`, single-cutoff, truncate-everything-
    after) that reliably flagged both confirmed-bad Sofia tiles was wired
    into `decode_features()` unconditionally, but re-running the
    established "80 largest `mg4` tiles" named-road validation with it
    enabled dropped the tile hit-count from 28/80 to **17/80** — several
    real, long, legitimately-chained tiles (e.g. `mg4` tile_id 2619)
    produce the identical statistical signature and were being wrongly
    truncated, losing all their real geometry AFTER the cutoff too.
    **This session: reproduced 4 additional confirmed-bad cases directly
    against the real ISO** (`mg3`, near Turin, Italy, lon=7.71507/
    lat=45.09368) that exposed two concrete gaps in the old single-cutoff
    design: (1) it only ever found the FIRST oscillation cluster in a
    block, missing a SECOND, later one (tile_id 1330, offset 4,174,363 —
    old code found no cluster at all, kept all 193 points) or hiding an
    EARLIER one inside its own "kept, clean" prefix (tile_id 61, offset
    534,136 — old cutoff kept 90 of 184 points, but real damage starts at
    ~point 85, inside that "kept" range); (2) pure truncation discarded
    real geometry AFTER a cluster even when unaffected, which is the exact
    mechanism behind the 28/80→17/80 regression. **Fix**:
    `_find_oscillation_clusters()` now scans the WHOLE delta sequence for
    every cluster (not just the first) and locally extends each
    confirmed cluster's boundary to absorb short "ramp-up" runs (fixes
    tile 61); `decode_features()` now SPLITS a block into separate
    surviving sub-features around each detected cluster — dropping only
    that cluster's own point range and keeping the "before"/"between"/
    "after" runs as independent features — instead of truncating
    everything from the first cluster onward. **Re-validated at the same
    80-largest-`mg4`-tiles scale**: the new split-based
    `trim_oscillation=True` scores **42/80** — not just a recovery from
    17/80, but an outright improvement over the untrimmed 28/80 baseline
    (some of the gain is a byproduct of splitting increasing the feature
    count per tile, not purely a correctness improvement — see the
    function's docstring for the full caveat). Only **one** tile
    regresses (tile_id 187: a real 2-named-road match gets dropped because
    both matching vertices happen to sit inside a flagged cluster).
    **One of the 4 new confirmed-bad cases remains an open gap**: tile_id
    1330 (offset 4,174,363) is NOT fixed — its corruption presents as two
    SPARSE, isolated round-trip events 44 delta-indices apart rather than
    a dense cluster, and those two events are numerically indistinguishable
    (same magnitude range, same ~99% cancellation ratio) from three
    perfectly legitimate, widely-spaced real jumps in the canonical Iasi
    reference tile — widening the clustering window to catch tile 1330
    was tried and directly confirmed to also wrongly flag the Iasi tile,
    so it was rejected and the safe parameters were kept. **Conclusion,
    reaffirmed with MORE evidence this session, not less**: tile-local
    delta statistics alone cannot safely classify a SPECIFIC oscillation
    cluster as corruption vs. a legitimate long chain doubling back —
    confirmed independently via mg4 tile_id 2619 (its flagged cluster
    turns out, on close inspection, to be two genuinely smooth,
    independently-progressing named-road-bearing sub-tracks interleaved
    point-by-point — real geometry, not corruption) and now also via mg3
    tile_id 1330 vs. the Iasi tile (isolated-jump statistics are
    identical between a confirmed-bad and a confirmed-good case). Several
    additional geometric discriminators (two-track nearest-tail
    splitting + per-track coherence, sticky-revisit diameter checks,
    direction-reversal-fraction checks) were tried this session
    specifically to solve this and all either still misclassified the
    real tile 2619 case as corrupt or, once loosened enough to accept it,
    also accepted confirmed-bad tiles. The only fully reliable test found
    (this session and the last) remains the `eeu.rd` cross-reference,
    which is out of scope for a single-tile, dependency-free decoder
    function. **Decision on defaulting**: `trim_oscillation` STAYS opt-in
    (default `False`) — despite the strong 42/80 number, real content
    loss is still directly demonstrated (tile 187) and the underlying
    per-cluster classification problem is proven, not just suspected, to
    be unsolved by tile-local statistics; ~~the new implementation is
    unambiguously the right choice wherever `trim_oscillation` is already
    used (the map viewer; see §10)~~, but is not safe to force on
    correctness-sensitive callers (editing/round-tripping/topology work).
    Full writeup: `decode_features()` and `_find_oscillation_clusters()`'s
    docstrings in `map_compressed_reader.py`.
    **UPDATE (§10 "v15 -> v16"): the struck-through claim above was
    directly tested against the real ISO and found WRONG for real
    dense-urban rendering.** A user's own first-hand observation
    ("unchecking hide decode garbage is producing more real accurate
    roads") led to a direct, per-named-road (not just per-tile-name-match)
    comparison at a real Sofia, Bulgaria `mg1` sample: the filter deleted 6
    entire real named roads and truncated 13 more — including Sofia's own
    ring road, "OKOLOVRASTEN PAT" (-84.6% of its matched points) — while
    removing only 5.74% of raw points. The 42/80 metric cannot see this
    failure mode (it only checks whether 2+ named roads match ANYWHERE in
    an `mg4` tile, not whether a SPECIFIC road survives, and was never run
    against `mg1`, the finer layer where the loss concentrates). The map
    viewer's own `App.hide_garbage_var` checkbox first defaulted to
    `False` (unchecked, §10 "v15 -> v16") then was REMOVED entirely in a
    later session (§10 "v26 -> v27", user request: it was always kept
    off anyway) — `MapData.trim_oscillation` remains, but only as a
    programmatic-only API now, unreachable from the running app. The
    library function's own default here is unaffected (already `False`).
  - **Topology/adjacency table — structure now understood, one major gap
    remains.** Past the coordinate run, each FEATURE (not each tile) gets its
    own table of exactly `point_count + 1` fixed 10-byte records (record 0 is a
    distinct non-node "header" record). Records 1..N: `[2-byte tag][up to 4 ×
    uint16 LE fields]`, where the tag's LOW byte determines how many of the 4
    fields are populated (2 fields for low-byte `0x22`/`0x02`, 3 for
    `0x23`/`0x32`/`0x43`/`0x63`, 4 for `0xc4`) — the tag's high byte is **not**
    reliably `0x04` as first thought (`0x0c` also seen), so a parser filtering
    on "second byte == 0x04" silently misses real records. Interpreting each
    record's populated fields as a short edge-chain (A-B, B-C, C-D) and
    building the resulting graph gives a **structurally realistic road-network
    topology**: e.g. the 83-point tile yields 105 distinct node-ids with degree
    histogram {1: 15 nodes, 2: 77-79 nodes, 3: 11-13 nodes} — mostly ordinary
    2-neighbor through-points, a plausible number of chain endpoints, and a
    plausible number of real junctions. **This directly confirms the original
    vertex-degree hypothesis**: junction points get bigger/more-populated
    records than plain through-points. **Not yet solved**: the node-id
    numbering in these records is NOT `decode_features()`'s own per-feature
    point-sequence order (tested directly: only 2/83 exact positional matches),
    and ids referenced go as high as the tile's COMBINED point total across
    ALL features (suggesting tile-global, not per-feature-local, ids) — but the
    actual assignment rule (spatial sort order? DB insertion order? something
    else?) hasn't been recovered. Without it, a specific graph record can't yet
    be tied back to a specific real (lon,lat) vertex, which blocks both (a)
    constructing a valid new topology entry for an inserted road's own
    vertices, and (b) the planned cross-checks against `eeu.iof`'s
    still-unexplained per-road byte and against Romanian DN/DC road-class
    numbering. Table placement within the tile also isn't byte-exact-formulaic
    yet (one example tile had a 104-byte unidentified gap before its table;
    another had zero gap but measured from the end of ALL features' geometry,
    not that feature's own block-end) — current reader locates it by searching
    for a run of plausible records rather than a fixed offset. Reusable reader:
    `decode_topology(raw, declen, features)` in `map_compressed_reader.py`
    (only validated for a tile's first feature so far; correctly reports
    `"found": False` rather than fabricating an answer when it can't locate a
    later feature's table — this happened for the 2-feature tile's second
    feature in testing).
    **UPDATE (later session): the graph-walk approach to recovering the
    node-id mapping was tried and DEFINITIVELY REFUTED, not just
    unmatched.** The natural hypothesis — a single feature's own polyline is
    a simple path, so its topology sub-graph should be graph-isomorphic to
    that path under an unknown node-id relabeling, recoverable by walking
    from a degree-1 endpoint — fails as a matter of graph structure on the
    83-point reference tile: its topology graph has TWO connected
    components (97 + 8 nodes, so it isn't even one connected path), the
    97-node component contains a CYCLE (97 nodes/97 edges) and 13
    degree-1/13 degree-3 nodes (not the 2/0 a simple path would have), and
    the LONGEST simple path between any pair of its 13 degree-1 nodes is
    only 53 nodes — no walk through this graph, under any labeling, can
    produce an 83-node path. Conclusion: at least for this tile, a
    feature's topology table encodes something structurally richer than
    "this feature's own point-to-point adjacency" — plausibly the real
    local road-network/routing mesh (cross-streets, small disconnected stub
    roads) rather than a per-feature-only structure. A byte-level side
    discovery from the same investigation: the previously fully-undecoded
    per-tile header bytes 0x02–0x17 are now partially decoded (feature 0's
    own point count and block_end, the count/end-offset of the small array
    that explains most of the "104-byte unidentified gap" above, and a
    field matching the topology graph's total node count to within 0-1) —
    see `decode_tile_header()`/`decode_topology_gap()` in
    `map_compressed_reader.py` — but this narrows, rather than closes, the
    node-id↔coordinate gap. A weak (11-sample), inconclusive positive signal
    was found between real named-road-transition points and 3-field
    (vs. 2-field) topology tags (55% vs 31% base rate); a parallel
    cross-check against `eeu.iof`'s varying byte (confirmed to actually sit
    at byte offset 4 of its 6-byte record, not offset 2) found no clean
    separation on the same small sample. Full writeup, numbers, and what
    was ruled out: `decode_topology()`'s docstring.
    **UPDATE (later session): first-ever REAL, human-verified ground-truth
    connectivity test — node-id mapping STILL NOT recovered, but the
    negative result is now much more precisely characterized, plus one
    real bug fixed.** A user who knows the streets around Sofia, Bulgaria
    used the map viewer's click-to-identify feature to confirm the real
    connectivity order of 19 consecutive points of a real `mp0` feature
    (tile_id 91124, file offset 1,003,495,557, feature 0, 306 points,
    offset 326 in the decompressed tile): decode_features() point indices
    221→200→183→186→190→198→218→227→244→253→259→270→274→282→277→271→264→
    251→240, all 19 exact-matched to 5 decimal places on direct re-decode
    (confirming decode_features() itself, independent of the topology
    question). **The user's own closure hypothesis — that point 240
    connects back to point index 0, since a DIFFERENT layer's (`mg1`)
    representation of the same real vertex as point 240 has identical
    coordinates — was directly tested and REFUTED**: point index 0 of
    this feature decodes to (23.39068, 42.68857), a real but unrelated
    location ~1.3km away, NOT the (23.40221, 42.68822) the closure would
    require. (decode_features()'s point 0 is just the arbitrary first
    vertex of the delta-encoding, not a semantically special "loop start"
    — this was worth checking directly rather than assuming, per the
    task that prompted this session, and it would have been a wrong
    foundation for everything downstream had it gone unchecked.) The 18
    real sequential edges among the remaining 19 points (plus the
    geometrically-plausible-but-coordinate-unconfirmed closing edge
    240–221) were then tested against this feature's real
    `decode_topology()` table (307 records, matching point_count+1
    exactly) under every hypothesis this session could construct:
      - **Direct point-index membership** (does record `i`'s fields
        contain point-index `j` for real edge i–j, or vice versa): **0/18
        hits** (21 including the refuted closure edges — still 0/21).
      - **Edge exists anywhere in the reconstructed graph**, regardless of
        which record position it comes from: only **1/18** (270–274),
        statistically indistinguishable from chance (363 of the graph's
        458 edges have both endpoints under 306, so a specific unrelated
        pair matching by luck has an expected rate of ~0.14 hits over 18
        trials — 1 hit is not a signal).
      - **Every rotational shift** of "which record belongs to which
        point" (all 307 possible shifts, both directions): best case only
        **2/18** — no shift comes close to a real signal, ruling out any
        simple constant record↔point offset.
      - **Pearson correlation** between point index (equivalently, that
        point's own byte offset in the tile) and its record's field
        values: a weak but real **+0.26** (mean field value) — consistent
        with, and about the same size as, the previously-documented 42/83
        "at least one expected neighbor" weak signal on the 83-point
        tile, but far too weak to reconstruct an exact mapping.
      - **Range/coverage check (new)**: this feature's own 306 points use
        node-ids that are **missing only ONE value (57) out of the full
        0–305 range** — i.e. the node-id set restricted to small values
        really is (almost exactly) this feature's own point-index set,
        just under an unrecovered non-trivial permutation (ruled out:
        simple rotation, per the shift-search above). At the same time,
        the graph also references **61 additional out-of-range ids**
        (up to 65,478, dominated by a contiguous run starting right at
        306 — i.e. immediately past this feature's own last point index).
        A from-scratch exhaustive scan of the ENTIRE tile (all 16,715
        bytes, not just the coordinate region) for any other plausible,
        `_looks_like_real_chain()`-verified feature anchor found **zero**
        — this tile genuinely contains only the one 306-point feature, so
        those extra referenced node-ids are NOT a second undiscovered
        feature in this same tile. They must be either a genuinely
        larger/global (cross-tile, or database-wide routing-node) id
        space, or non-feature real points (stub connectors / junctions
        with neighboring roads) that never get their own self-delimiting
        coordinate block at all — both consistent with, and sharpening,
        the existing "structurally richer than one feature's own
        adjacency" conclusion above, not resolving it.
      - **One genuine bug found and fixed, orthogonal to the mapping
        question**: tag low-bytes `0x01` (31/306 records on this feature)
        and `0x11` (33/306) were absent from the field-count table and
        fell through to the "strip trailing zeros, keep ≥2" fallback —
        but checking every one of those 64 records directly shows their
        2nd/3rd/4th raw uint16 fields are **exactly 0 in 100% of cases**
        (31/31 and 33/33), i.e. these tags mean exactly **ONE** real
        field, not two, and the fallback was manufacturing a fictitious
        edge to node-id 0 on over a fifth of this feature's records.
        Fixed (`_FIELDCOUNT_BY_LOW_BYTE` now maps `0x01`/`0x11` → 1
        field); on this tile, node 0's graph degree drops from an
        obviously-artifactual 74 to a still-elevated-but-far-more-
        plausible 10, and the feature's degree histogram changes from
        `{1:28, 2:195, 3:134, 4:6, 74:1}` to `{1:60, 2:183, 3:110, 4:6,
        10:1}` (total distinct nodes 364→360). Re-running the direct
        point-index membership test with the corrected extraction still
        scores **0/18** — this fix improves graph-construction accuracy
        but does not, by itself, crack the mapping. **Side note**:
        `decode_tile_header()`'s `w11_node_count_approx` matched this
        feature's PRE-fix node count exactly (364 vs 364) — a data point
        for that field's validation — but is now 4 nodes higher than the
        POST-fix, more-correct count (364 vs 360); which convention the
        original firmware's own header field actually used is unresolved
        by this single example.
    **Conclusion (unchanged bottom line, now much better evidenced)**: a
    feature's topology-table node-id assignment is still not recovered.
    This session adds real, human-verified negative evidence (not just
    one more untested tile) that rules out the simplest remaining
    candidates — direct point-index reference, any constant rotation,
    and the previously-live "maybe I just haven't found the right small
    shift" possibility — while also showing the node-id space, for this
    real 306-point feature, is NOT some completely disjoint numbering
    (305/306 of its own point-indices genuinely appear as node-ids
    somewhere in its own table), which argues for a real but
    non-trivial permutation or a richer shared graph rather than an
    unrelated ID scheme. A future session's best next lead: the
    "database insertion order" hypothesis was never actually tested
    (only spatial-sort-order and graph-walk were) — cross-referencing a
    tile's node-id-tagged trailing block or its raw byte layout against
    `eeu.rd`'s own record ordering (which is NOT spatially sorted,
    per §3.9) for the SAME real road might reveal whether node-ids
    track `.rd`'s insertion/record order rather than anything spatial or
    positional in the tile itself — untried this session, worth trying
    with this exact tile (91124/mp0, offset 1,003,495,557) as the
    reference example, since its connectivity order is now real,
    human-verified ground truth rather than an assumption.
    **UPDATE (later session): CRACKED — node-id<->coordinate mapping
    recovered, real edge-by-edge validation on TWO independent
    human-verified ground-truth tiles.** A second real, human-verified
    ground-truth example was obtained via the map viewer's click-to-
    identify feature: `mg2` tile_id 20597, file offset 69,486,644, feature
    0 (203 points), with the user confirming the real connectivity order
    of 17 of its points (16 sequential real edges): point-index order
    202→190→189→185→186→188→191→192→193→195→197→199→201→200→198→196→194.
    Raw-decode reproduction: `decode_features()` exact-matches all 17
    listed points to 5 decimal places (feature 0 at byte offset 326 as
    expected, 203 points total — the "17 points" are a subset of this
    larger feature, all but one of index range 185-202). Re-testing the
    SAME hypothesis suite the `mp0`/tile-91124 session used, on this NEW
    tile: direct point-index membership 0/16, edge-exists-anywhere-in-graph
    3/16, best of all 204 rotational shifts 3/16, Pearson correlation
    (point index vs. mean field value) −0.26 — all consistent with the
    prior session's chance-level conclusions, reproducing the same
    negative result on an independent tile.

    The `eeu.rd`-insertion-order lead recommended above was then tried
    directly and came back negative (no direct, rescaled, or
    rank-preserving relationship was found between this tile's topology
    node-ids and the `.rd` record indices of its matched real points —
    magnitudes alone rule out a direct match, `.rd` indices run into the
    millions while node-ids top out in the low hundreds) — but inspecting
    the data while testing it surfaced the actual mechanism instead.
    **A topology record does NOT reference an adjacent point's own index
    at all.** Two really-adjacent points' records instead SHARE one common
    FIELD VALUE — a per-edge "link id" — with no other point's record on
    that feature containing it. Example from this tile: point 188's record
    fields are `{46, 164, 179}`, point 191's are `{162, 163, 164}` — 191 is
    never named anywhere in 188's record (which is why every direct-
    reference test above, and in every prior session, scored at or near
    chance), but both records contain 164, and no other point's record
    does. This is a classic edge-id ("winged-edge"-style) topology
    encoding: a vertex's record lists the ids of the edges/links touching
    it, and two vertices are adjacent exactly when they share one.
    Checking every one of the 16 real edges on this tile this way: **16/16
    have a non-empty field-value intersection between their two records**
    (`record[point_index + 1]` — i.e. skip one leading header record, same
    convention already documented for the single-feature `mg4` reference
    tile) — versus a measured chance baseline on this same tile of 1.07%
    for uniformly random point pairs and 5.06% for pairs close in point-
    index (16/16 at either rate is astronomically unlikely by chance,
    p ~ 1e-21 at the looser 5% baseline). Building the FULL shared-value
    graph over all 203 points (not just the 16 known edges) gives a
    genuinely road-like structure: degree histogram `{1: 9, 2: 168, 3: 23,
    4: 3}` (9 plausible endpoints, 168 ordinary through-points, 26
    junctions), 201/203 points in one connected component with a
    cyclomatic number of 12 (a real local mesh with real loops/cross-
    streets, not a bare simple path — consistent with, and now
    mechanistically explaining, the earlier graph-walk refutation).

    **The remaining wrinkle: which record belongs to which point index is
    offset by a small, PER-FEATURE constant ("shift"), not always the same
    one.** Re-testing this exact method on the earlier `mp0` ground-truth
    tile (91124) at the same `shift=1` convention scored only 1/18 — but a
    shift-sweep found `shift=2` (i.e. `record[point_index + 2]`) scores
    **16/18** on that tile instead. This isn't a free parameter fitted to
    the ground truth: it can be found with NO ground truth at all, using
    only the feature's own already-decoded coordinates. For each candidate
    shift, build the shared-value graph it implies, then score the shift
    by the MEDIAN real-world distance between its implied edges' two
    endpoints — genuine road topology only ever connects geometrically
    close points, so the correct shift produces a dramatic, unambiguous
    minimum while every wrong shift's edges connect essentially random,
    far-apart points. Measured over the FULL shift range on both tiles:
    mg2 tile 20597's global minimum is at shift=1 (median edge distance
    49.7m, next-best shift 127.2m — a 2.6x gap); mp0 tile 91124's global
    minimum is at shift=2 (median 40.9m, next-best 395.5m — a 10x gap).
    Both exactly match the ground-truth-derived answer. The 2 misses on
    the mp0 tile (edges 253-259 and 259-270) both touch one specific point
    (259), whose record never shares a value with either neighbor — but
    259's immediate predecessor in point-index order, 258, DOES share a
    value with the far endpoint 270 (link id 352), suggesting the real
    topological edge runs through 258, not 259 (very plausibly two
    near-duplicate vertices at the same real junction, indistinguishable
    to a human clicking a small map marker), rather than a failure of the
    shared-value rule itself.

    Checked directly, not assumed: the shift is NOT a fixed per-LAYER
    constant. A third, independent single-feature `mp0` tile (tile_id
    79147, 91 points, no ground truth — checked only for structural
    plausibility) auto-detects shift=1 (median 355m vs. 853m next-best),
    not shift=2 — so "mp0 always needs shift=2" is false; it's a genuine
    per-feature property. The original 83-point single-feature `mg4`
    reference tile this docstring has used throughout (offset 5,138,331)
    also auto-detects shift=1 (median 77m vs. 146m next-best) with a
    clean, plausible degree histogram `{1: 4, 2: 76, 3: 2, 4: 1}` — a much
    more sensible 4-endpoint/3-junction reading for an 83-point road chain
    than the OLD, now-understood-to-be-wrong "chain within one record"
    interpretation's inflated 105-node/13-endpoint/13-junction count for
    the same tile.

    **Caveat, measured not hypothesized**: on small features (a 31-point
    and a 13-point single-feature `mp0` tile, both with no independent
    ground truth) the auto-detected "best" shift's median edge distance
    was implausibly large (13.9km and 23.0km respectively, versus every
    validated-correct case's under-400m median) — too few implied edges
    for the geometric signal to be reliable, and/or `_find_topology_table_
    start()`'s pre-existing small-integer-collision weakness (documented
    elsewhere in this docstring) more easily mis-locates the table
    entirely on a short feature. This is a real, gated limitation, not
    swept under the rug — see `resolve_topology_adjacency()`'s
    `"confidence"` field.

    Reusable implementation: `resolve_topology_adjacency(raw, declen,
    features, topo)` in `map_compressed_reader.py` — takes this function's
    own output and returns, per feature, the resolved `shift`, the
    winning median edge distance, a `"confidence"` flag (`"high"` if the
    median is under a generous 2km sanity threshold, `"low"` otherwise —
    ALWAYS check this before trusting the result for anything
    correctness-sensitive), and a real point-index adjacency dict directly
    usable against `decode_features()`'s own point indices. This is the
    concrete piece that had been blocking synthesis of a valid topology
    entry for a newly inserted road's own vertices (README §8 item 5).
    **Still open, deliberately not oversold as solved**: the numeric
    link-id VALUES themselves have no independently-confirmed meaning
    beyond "shared by exactly the two (or few) adjacent points" (e.g.
    whether they double as a real, separately-stored edge/segment id used
    elsewhere in the database), and why the per-feature "shift" varies at
    all is not explained, only cheaply discoverable per feature. Full
    numbers, mechanism, and all caveats: `resolve_topology_adjacency()`'s
    docstring in `map_compressed_reader.py`.
    **UPDATE (README §10 "v16 -> v17"): a real false-positive bug in this
    mechanism found via the map viewer's own edge click-to-identify
    feature, root-caused and FIXED with a new per-edge distance filter.**
    A user right-clicked 5 real rendered connected-roads lines in the
    Sofia, Bulgaria area and reported their two endpoints as real,
    confirmed-unrelated points 692m–2,917m apart (e.g. the real named
    street "OBORISHTE" wrongly "connected" to an unrelated unnamed point
    ~1.7km away) — all 5 reproduced exactly against the real ISO directly
    via `resolve_topology_adjacency()` (not a UI-only bug). Root cause: two
    points sharing a link-id value is necessary but **not sufficient** for
    real adjacency — in 4/5 cases the shared value was the literal `0`
    (almost certainly a padding/unset-field sentinel, the same role `0`
    plays elsewhere in this tile format, e.g. the spatial sub-index's
    "empty cell" markers earlier in this section), and the 5th shared a
    small non-zero value (11) whose full "clique" of sharing points mixed
    one genuine 38m edge with several 869m–1,345m bogus ones.
    Measured directly: even the two existing human-verified ground-truth
    tiles already had unnoticed implausible edges hiding inside their
    otherwise-"high"-confidence resolved sets before this fix (`mg2` 20597:
    up to 599.9m among 213 total edges, all 16 human-verified ones under
    104.2m; `mp0` 91124: up to 2,039.6m among 331 total edges, all
    16-18 human-verified ones under 45.3m) — the existing per-FEATURE
    `confidence` gate is a MEDIAN-based statistic, robust by design against
    exactly this kind of minority outlier, which is precisely why it never
    caught these. **Fix**: `resolve_topology_adjacency()` gained a new,
    independent per-EDGE distance sanity filter (`max_edge_m`, default
    200m — chosen with a >6.6x empirical margin over the highest distance
    among every human-verified real edge across both ground-truth tiles,
    104.2m, and comfortably below the closest reported bad edge, 692.4m),
    applied to the final edge list AFTER shift selection so it does not
    disturb the existing `shift`/`median_edge_m`/`confidence` computation
    or any previously-reported numbers. Re-validated: both ground-truth
    tiles still resolve every one of their human-verified edges unchanged
    (`mg2` 20597 still exactly 16/16, `mp0` 91124 still exactly 16/18)
    while dropping a real number of other implausible edges (`mg2` 20597:
    213→204 edges, 9 dropped; `mp0` 91124: 331→310, 21 dropped), and all 5
    user-reported false edges are now confirmed excluded — see
    `test_map_viewer.py`'s "8f" section for the full reproduction/
    validation against the real ISO. A new `"edges_dropped_implausible"`
    field reports the per-feature drop count. **Limitation, stated
    honestly**: 200m is an empirically-justified, not formally-derived,
    cutoff — a genuinely long rural real edge could in principle exceed it
    (not observed in this project's validated samples, all under 110m),
    and a short-but-still-wrong edge (e.g. two near-duplicate vertices at
    the same real junction, like the already-documented `mp0` 91124
    point-258-vs-259 case above) would not be caught by a pure distance
    filter — this closes the "obviously wrong, far away" failure mode the
    user's reports demonstrated, not every conceivable false-edge
    mechanism. Full write-up: `resolve_topology_adjacency()`'s own
    docstring, "PER-EDGE FALSE-POSITIVE FILTER" section.
  - trailing block: more small tagged records; the "one record per feature"
    (road-class/attribute) hypothesis was tested and **rejected** — the block
    runs to 878+ bytes after a single-feature tile and 3,900+ bytes after a
    2-feature tile's first feature, far too long for one record per feature.
    Actual grammar still uncracked — also unclear whether every feature gets
    its own trailing block or only some do.
  - **Label strings** (from a richer mp0 sample): live in a distinct tail section,
    pattern `[1-byte ascending local id][2-byte tag: 0x10c0/0x20c0/0x30c0/0x40c0]
    [optional inline null-terminated ASCII string]`, e.g. real label `"1200M(ITA)"`
    found this way. Strings are NOT deduplicated. The ascending id byte plausibly
    links back to a specific vertex, unproven.

- **Practical geo-index workaround — SOLVED for mg2/mg3/mg4 AND mp0** (distinct
  from, and doesn't require cracking, Continental's own undecoded geo-index prefix
  region described above): since every tile carries its own absolute anchor
  coordinate, `research/map_compressed_reader.py` now has `build_geo_index(path)`
  (decompresses every tile, extracts its anchor, returns
  `{tile_id: (lon, lat, method)}`) and `find_tile_for_coord(geo_index, lon, lat)`
  (nearest-anchor lookup). Coverage, **full-file runs** (not samples):
  6,106/6,110 tiles (99.93%) on `mg4` (~0.6s — `build_geo_index` was rewritten this
  session to read each tile's exact `complen` bytes once instead of a wasteful
  fixed 2MB re-open-per-tile, which is also what made a full `mp0` run practical);
  **194,650/194,705 tiles (99.97%) on the full 2.14GB `mp0`, ~55s** (previously only
  spot-checked — see below for why the old approach didn't transfer, and the fix).
  Also added: `find_tile_anchor()` (per-tile extraction primitive), `decode_features()`
  (see above, multi-feature-aware), and `decode_vertex_chain()` (legacy
  single-continuous-chain decoder, the function that produced the original DC158
  match — kept for backward compatibility, superseded by `decode_features()`).
  **Known caveat**: `find_tile_for_coord` is nearest-anchor, not
  true bounding-box containment (no tile extent was recovered), so a coordinate near
  a tile boundary might not resolve to the tile that actually renders it at a given
  zoom level. **Also noted**: `decompress_tile()`'s `consumed` byte count is
  unreliable for ~13% of tiles with default settings (a zlib buffering quirk, not
  data corruption — `declen`/content match is unaffected); don't rely on `consumed`
  for tile-boundary validation. **Also found (while building the map viewer, §10)**:
  on a real `mg3` tile near Iași, `find_tile_anchor()`'s `"bruteforce"` fallback
  method (used when the fast structural rule doesn't apply) produced an outright
  corrupt anchor/feature thousands of km from the tile's real location — not just
  imprecise, wildly wrong. The viewer works around this defensively (drops any
  decoded feature straying >3° from its own tile's anchor), but the underlying
  `"bruteforce"` path in `find_tile_anchor()` itself could still use tighter
  verification in a future session.
- **`mp0`'s sub-index is genuinely denser than mg2/mg3/mg4's, not just "deeper"**
  (this session pinned down what that meant): mg2/mg3/mg4 tiles are mostly
  SPARSE (few real roads per tile), so their spatial sub-index is mostly
  "empty-cell" sentinels (repeats of `declen` or `0`), and the original
  structural rule ("first word that isn't a sentinel") reliably lands on real
  data. `mp0` tiles are much richer (hundreds of points per tile is common), so
  their sub-index grid is mostly FULL of real, varied offset/count values —
  there's no sparse run of sentinels to scan past, and (worse) some of those
  real grid-cell values, read as an adjacent int32 pair, coincidentally satisfy
  the plausible-lon/lat range check too. Both the old structural rule AND the
  old plain brute-force fallback would confidently return a **wrong** anchor
  deep inside the sub-index on these tiles (measured: on a random 500-tile
  `mp0` sample, the old bruteforce-only logic disagreed with the fixed logic on
  246/499 tiles it claimed to "resolve" — silently wrong roughly half the
  time). **Original fix**: `_looks_like_real_chain()` — after finding a
  plausible (lon,lat) candidate, additionally require the next ~12 (dx,dy)
  shorts immediately following it to look like real small polyline deltas,
  which cheaply distinguishes a real anchor from a sub-index echo. Folded into
  `find_tile_anchor()` and a new `_find_data_start()` (used by
  `decode_features()`); re-verified this does NOT regress mg2/mg3/mg4
  (byte-identical 6,106/6,110 on the full mg4 before and after). This was the
  key structural difference to resolve for `mp0`, not a different byte layout
  — the anchor/delta-block format itself (see above) is identical across all
  five MAP_COMPRESSED files. **Revised fix (later session)**: that original
  version checked "bounded magnitude, not a repeated/near-constant run" —
  the magnitude half of that check turned out to be wrong (see the ⚠→✅
  threshold-bug note above): real deltas, including on `mp0`, are frequently
  large, so magnitude alone falsely rejected real chains too. Kept only the
  repetition/distinct-value half of the check (real deltas are almost always
  distinct even when large; sub-index echoes are dominated by one repeated
  value) and dropped the magnitude test entirely. Re-verified this still does
  NOT reintroduce the dense-mp0 false-positive problem measured above: on a
  fresh 1,500-tile `mp0` sample, the new discriminator's named-road hit rate
  is 67.1%, versus 55.3% for the original unguarded (pre-fix) scan — i.e.
  still solidly better than doing no verification, while also no longer
  rejecting legitimate large-gap chains (see the ⚠→✅ note above for the
  full before/after numbers, including why the old magnitude-based fix's own
  hit rate, 44.1%, was actually *worse* than doing no check at all).

### 3.7 `eeuz.rl` + `eeuz.prl` — name-search catalog — CRACKED and validated at scale;
`eeuz.rt` — character-trie node format CRACKED and cross-validated, a few fields/edge
cases still open
Reusable reader: `research/road_index_reader.py` (full details, caveats and validation
numbers in its module docstring — summary below).

- **`eeuz.prl`** ("road names" per files.cfg): decompresses to the standard 94-byte
  header + a **flat, NOT deduplicated** concatenation of null-terminated name strings,
  no length prefix. Reference disc: 879,892,357 body bytes, 46,433,034 strings — ~5.3x
  `.rd`'s own 8,809,081 records, because a single real road can get more than one catalog
  entry. Confirmed example (Linosa, Sicily): `.rd` stores the bare name `"GUITGIA"` (no
  street-type word at all — a new finding: `.rd`'s 43-byte name field never includes the
  localized type word, e.g. VIA/CONTRADA/STRADA; those live only in `eeu.typ`, §3.4).
  `.prl` carries this road under **two** catalog entries: verbatim `"CONTRADA GUITGIA"`
  and re-sorted `"GUITGIA;CONTRADA"` (core word first, type word demoted after `;`, so it
  sorts/searches by the meaningful word). The exact demotion rule isn't always
  first-word-only (`"LATTEA;VIA DELLA VIA"` reassembles to `.rd`'s real name `"VIA
  LATTEA"`, i.e. the whole phrase `"VIA DELLA"` is demoted, not just `"VIA"`) —
  not fully reverse-engineered, only observed on examples.
- **`eeuz.rl`** ("road list, pointers to names ... in *.prl"): fixed **12-byte records**,
  no gaps, starting right after the shared 94-byte header. Body length is exactly
  12 x 46,432,934 — essentially one `.rl` record per `.prl` string (off by ~100 at the
  very end of the file, unexplained). Record layout (all LE):
  - `bytes[0:4]`: candidate index into `eeu.rd`. Strong circumstantial evidence, not
    fully proven: bounded to exactly `.rd`'s record-count range in a 22,000-record random
    sample (max observed 8,808,636 vs `.rd`'s 8,809,081 records), and direct name
    cross-checking (undoing the `;` rewrite) succeeds exactly-or-via-suffix-match on
    133/300 (44%) of a random sample, with most of the remainder plausibly explained by
    accented-character transliteration differences rather than a wrong index (not
    independently confirmed character-by-character).
  - `bytes[4:7]`: **CONFIRMED always `0x00`** across the full ~46.4M-record file (checked
    every record, 0.000% nonzero on each byte lane) — reserved/padding.
  - `bytes[7:11]`: **byte offset into decompressed `.prl`, exact-match validated at full
    scale**: record i's value equals the start offset of the i-th `.prl` string, checked
    exactly at i = 0, 1, 2, 1000, 100000, 1M, 5M, 10M, 20M, 40M, and the last two records
    of the full 46,432,934-record file — 12/12 exact matches.
  - `byte[11]`: binary flag (71.02% are 1, 28.98% are 0 over the full file), meaning
    unresolved — tested and REJECTED as "entry has a `;` rewrite" (looked clean on a
    16-record first-block sample, failed at ~52% — noise level — on a 22,000-record
    random sample).
- **`eeuz.rt` — CRACKED this session: a character-trie with subtree-size "skip" pointers.**
  The previously-noted 67-byte divisibility coincidence remains refuted (decoding by
  `.rd`'s layout produces garbage — do not re-attempt). Byte-level statistics were
  re-derived and match prior sessions exactly (76.7%+5.1%+2.0%+... of bytes are values
  0-4; 4.2% of bytes are uppercase A-Z with a letter-frequency-like profile), but this
  session went further and recovered the actual node grammar. **Node format, fixed
  19 bytes**: `offset 0`: uint32 LE `subtree_size` — this node's ENTIRE subtree size
  (itself + all descendants) in whole 19-byte units; a leaf has `subtree_size==1`,
  and `subtree_size==0` marks a non-character terminator. `offset 4`: uint32 LE
  `char_code` — this node's edge-label character (printable ASCII: not just A-Z but
  also space/`;`/`,`/`.`/digits, matching `.prl`'s own character set). `offset 8`:
  uint32 LE `reserved` (unresolved). `offset 12`: 3 bytes, appears always 0. `offset
  15`: uint32 LE `field4` (unresolved; a candidate `.rd`/`.rl`/`.prl` leaf-pointer, not
  confirmed — see `road_index_reader.py`'s docstring for the numbers). **Traversal**:
  a node's children are stored depth-first starting at `node_start+19`; to advance to
  the NEXT SIBLING, skip forward by the previous child's own `subtree_size*19` bytes.
  **Validated three ways**: (1) direct hand-verified example — node 'D' at body offset
  65 (`subtree_size=3`) jumps `65+19*3=122`, landing exactly on node 'M'; nodes 'F'
  (84) and 'G' (103) are confirmed to be D's two children (D=1+F+G=3, matching
  `subtree_size` exactly), and both correctly chain to M as D's next sibling once
  their own subtrees are skipped. (2) a pointer hit-rate test: interpreting
  `subtree_size` as "jump `19*value` bytes forward, land on another node" scores
  **72.8%** on a 20,000-node random sample (excluding trivial zero-jumps), against a
  measured base rate of 4.23% — the other two same-shaped fields (`reserved`,
  `field4`) score only 15.4%/17.7% under the identical test, confirming the effect is
  specific to `subtree_size`. (3) **real, cross-referenced vocabulary**: walking
  children and concatenating edge characters spells genuine multi-language
  street-name fragments, including an exact literal match — `"SOKAK"` (Turkish
  "street") appears in a decoded leaf string (`"T;AZI SOKAK;ARS"`) using the SAME
  `;`-demotion convention already validated for `.prl` above, and `"SOKAK"` is
  independently confirmed present in `eeu.typ` at records 57/2376/2377/2529 (§3.4).
  Further sampled leaf strings separately contain `"PROEZD"`/`"ULITSA"` (Russian),
  `"VULYTSIA"` (Ukrainian), `"CADDESI"` (Turkish), and `"VICINALE DEI"` (Italian) — all
  also confirmed present in `eeu.typ` — plus plausible real full names matching
  European conventions (`"...TORIO VENETO;VIAO..."` → "VIA VITTORIO VENETO";
  `"MR KING;VIA MARTIN..."` → "VIA MARTIN LUTHER KING"). Quantified: of ~2,300 clean
  sampled leaf strings, 7.2% contain a real `eeu.typ` word (len≥3) as a substring
  (1.1% for a stricter len≥5 word match) — a lower bound, since most real street
  names are proper nouns with no generic type word to match, and sampled leaf
  strings are frequently missing their true prefix (see gaps below). **Not yet
  closed**: the true global root isn't located (the file's first ~46 bytes don't
  cleanly decode as this same node shape, so there's no `rt_root()` yet — you need a
  starting node offset from elsewhere, e.g. by scanning for plausible `char_code`
  values, as this session did); a node's `subtree_size` does not always account for
  100% of its own subtree byte-for-byte (e.g. node 'A' at offset 46 claims
  `subtree_size=42` but only 12 records' worth of valid children are found before
  hitting invalid data at offset 274 — most likely a second, wider node variant for
  non-ASCII/accented edge characters that this dataset clearly needs, not yet
  decoded); `reserved` and `field4` remain unconfirmed. Reusable functions:
  `rt_node()`, `rt_char()`, `rt_children()`, `rt_walk_strings()` in
  `research/road_index_reader.py` (full validation numbers and exact caveats in its
  docstring).
- **Practical relevance (unverified on hardware, best-informed read)**: `.rl`/`.prl` look
  like a large, multi-keyed name-search catalog clearly distinct from `.il` (5.3x more
  entries than `.rd` has records, vs `.il`'s much smaller single-entry-per-name-ish size),
  and `.rt` is now confirmed to be a real character-trie over that same kind of
  demoted/sort-key name string. Plausible (still not confirmed on real hardware)
  hypothesis: `.rt`/`.rl`/`.prl` back the unit's primary "City -> Street" destination-entry
  search screen, separately from whatever `.il` serves. If true, a newly added road absent
  from this catalog could be unfindable via the unit's normal address-entry UI even though
  it IS found by the GUI tool's own `.il`-based search — sharpens (doesn't newly create)
  the caveat already in README §6/§7.

### 3.8 `eeu.cty` — city/town/locality catalog (74.2MB, NOT_COMPRESSED) — CRACKED and
validated against real-world cities (Tirana, Timișoara, Iași, Sofia)
Reusable reader: `research/city_reader.py` (full details, all caveats and the `.cl`
validation numbers in its module docstring — summary below).

- Same 94-byte SIEMENS header convention as `.rd`/`.typ`, then fixed **79-byte
  records**, no gaps: `(74208823 - 94) / 79 = 939,351` records exactly on the
  reference disc.
- Record layout (all LE): `bytes[0:4]` self-referential sequential index (record i's
  index field always equals i — a sanity check, not needed for lookups);
  `bytes[4:6]` candidate finer admin-region reference (unresolved, see below);
  `bytes[6:22]` **a bounding box**, not a single point — `bytes[6:10]`/`[10:14]` are
  the MIN longitude/latitude (SW corner), `bytes[14:18]`/`[18:22]` the MAX
  longitude/latitude (NE corner), all int32 LE, degrees = value/100000; `bytes[22:57]`
  (35 bytes) the name, **UTF-8** (not Latin-1 like `.rd`/`.il` — confirmed: Albania's
  capital only decodes correctly as UTF-8, to "TIRANË"), NUL-padded, format
  `"<place>, <parent place>"` or bare `"<place>"` for a top-level entry;
  `bytes[57:59]` a coarser country/region tag (constant across every record
  of one country's contiguous block, e.g. 188 for Italy, 120 for Greece, 375 for
  Albania — does NOT match `eeu.ctr`'s own row index for those countries, so it's
  some other, unidentified numbering) — **CRACKED, README §10 "v13 -> v14"**: a
  full-file scan finds exactly 35 distinct values, one per real `eeu.ctr` country
  (`research/city_reader.py`'s `build_country_tag_map()`, empirically matching each
  tag group's real-world centroid against `eeu.ctr`'s own 35 countries rather than
  assuming any numbering relationship — see that function's docstring for the full
  methodology, the Kosovo/Serbia and Russia-Latin/Russia-Cyrillic disambiguation, and
  17/17 known-real-city validation numbers); `bytes[59:63]` unresolved int32;
  `bytes[63:71]` a **second, more precise representative point** (longitude then
  latitude, same /100000 scale) distinct from the bounding box — consistently closer
  to a real "city center" than the bbox midpoint in every city checked;
  `bytes[71:75]` unresolved int32 (frequently an explicit -1/0xffffffff sentinel);
  `bytes[75:79]` unresolved uint32.
- **Bounding-box interpretation validated, not just hypothesized**: a top-level entry
  with no name comma ("LAMPEDUSA E LINOSA", the whole comune) has a box wide enough to
  span both its islands (~40km apart), while a small locality inside it ("GUITGIA,
  LAMPEDUSA E LINOSA") has a ~1km box fully nested inside the comune's — exactly the
  hierarchy a real bounding box should show. Box area correlates with administrative
  level in every example checked, making it a usable **zoom-dependent importance
  proxy** (large areas surface at low zoom, small localities only once zoomed in) —
  this satisfies the same practical need a population/importance field would, without
  one being cleanly identified.
- **Validated against real-world coordinates** (this project's standard: exact
  matches, not just plausible ranges): record 220303, name "TIRANË", bbox
  (19.69818,41.24799)-(19.95216,41.39665), representative point
  (19.82517,41.32232) — real Tirana is (19.8189°E,41.3275°N), inside the bbox and
  ~700m from the representative point; surrounded by real "NJËSIA BASHKIAKE N,
  TIRANË" (Tirana municipal-unit) sub-records confirming the cluster. Record 226966,
  name "TIMISOARA", bbox (21.04681,45.607)-(21.39985,45.89984), representative point
  (21.22333,45.75342) — matches real Timișoara (21.23°E,45.75°N) almost exactly, with
  ~90 real Romanian-postal-code sub-records ("300522, TIMISOARA", etc.) clustered
  around it. Real Romanian-postal-code sub-records for Iași ("700719, IASI", etc.,
  clustered at 27.55-27.57°E/47.12-47.14°N — matches real Iași) and Bulgarian-postal-
  code sub-records for Sofia ("1696, SOFIA", "BANKYA, SOFIA", etc., clustered at
  23.1-23.3°E/42.6-42.75°N — matches real Sofia) were also found.
- **Practical use**: `.cty` alone is sufficient for both name search and zoom-
  dependent display, without needing `.cl`/`.ct` below — `search_cty()` does a plain
  substring scan over the whole 74MB file in memory, ~0.3s on the reference disc, no
  separate index file needed (unlike `.rd`, which needs `.il`).
- **`eeuz.cl`** ("city list", FLAT_COMPRESSED) — record layout CRACKED: fixed
  **54-byte records** (4,084,104 on the reference disc, no gaps): `bytes[0:4]`
  candidate index into `eeu.cty`, `bytes[4:54]` (50 bytes) a UTF-8 search-key name,
  ASCII-transliterated and/or `;`-sort-key-rewritten (same demotion convention as
  `.prl`, README §3.7) relative to the target `.cty` record's own name. Validated at
  the same confidence level this project already accepted for `.rl`'s `.rd`-index
  field: 314/500 (62.8%) of a random sample match the pointed-to `.cty` name exactly
  or by substring; the rest were hand-checked and fall cleanly into transliteration,
  `;`-rewrite, or same-admin-cluster-sibling cases (no case found where the pointer
  was outright wrong). Not required for basic search/display (see above) — a future
  session could use it for closer parity with the unit's own destination-search UI,
  which may or may not actually read `.cl`/`.ct` rather than `.cty` directly
  (unconfirmed, same caveat as `.rl`/`.prl`'s in §3.7).
- **`eeuz.ct`** ("city tree") — same cracked node format as `.rt` (§3.7), confirmed by
  a quick cross-check, not deeply pursued (per the task guidance to treat `.cl`/`.ct` as
  secondary to `.cty`, which already covers the practical search/display need).
  Decompresses to 16,454,990 body bytes with the identical "19-byte node,
  `subtree_size`-skip pointer" structure documented for `.rt`: the same pointer
  hit-rate test (interpreting the first uint32 field as "jump `19*value` bytes
  forward, land on another node") scores **80.7%** on a 14,283-node sample of
  `.ct`, against a measured base rate of 4.31% — matching `.rt`'s 72.8%-vs-4.2%
  result closely enough to be clearly the same mechanism, not a coincidence.
  Walking sampled subtrees with `road_index_reader.py`'s `rt_walk_strings()`
  (format-agnostic — works on `.ct` unchanged) spells real Russian/former-USSR
  administrative vocabulary: `"RAYON"`/`"RAION"` (district), `"KOZHUUN"` (a Tuva
  Republic-specific district term), and `"SAVYET"` (Soviet/council, as in a rural
  "selskiy sovyet") all appear in decoded leaf strings — plausible given this
  East-Europe dataset's real coverage, and consistent with `.ct` being a
  locality-name trie parallel to `.rt`'s road-name trie. Not independently
  cross-referenced against `eeu.cty`'s own names this session (unlike `.rt`'s
  `eeu.typ` cross-reference) — treat as strong structural confirmation, not a
  full crack of `.ct`'s own semantics.

### 3.9 Road-naming join — attaching real `.rd` names to decoded tile geometry
Reusable module: `research/road_naming.py` (full rationale, caveats and validation
notes in its module docstring — summary below). This is the piece that turns an
unlabeled rendered polyline (from `decode_features()`, §3.6) into labeled segments
("these vertices are DC158, these are STADION, ...").

- **Why it works**: `decode_features()` accumulates each vertex in INTEGER delta
  space and only divides by 100000 once at the end, so `round(lon*100000)` reliably
  recovers the exact original int32 for a genuine on-road vertex — the same bit-exact
  match already used to validate `decode_features()` itself (§3.6). `build_rd_index()`
  reads the whole 590MB `eeu.rd` into memory once, uses numpy to vectorize the
  coordinate decode + bounding-box filter across all 8.8M records (sub-second), then
  builds an exact-match dict `{(lon_i,lat_i): name}` plus a degree-binned grid for a
  nearest-within-tolerance fallback (default 75m) over just the records inside the
  requested box. Measured: ~0.3-0.7s per call on the reference disc for a
  single-tile-sized bounding box, dominated by the initial file read.
- **`match_feature()`** matches every vertex of one decoded feature (exact lookup
  first, then nearest-within-tolerance) and collapses the per-vertex results into
  contiguous `(start_idx, end_idx, name_or_None)` ranges — reflecting, rather than
  hiding, this project's already-documented finding that one feature can legitimately
  chain through several different named roads.
- **Validated on two independent real areas**, reproducing (and going beyond) the
  already-documented tile-decoding validations using only generic coordinate-join
  logic, no per-example special-casing:
  - The canonical Iași `eeuz.mg4` tile (file offset 11,298,518, the same 392+154-point
    2-feature tile documented in §3.6): the 392-point feature resolves to DC138,
    PETRU PONI, ION NECULCE, GARABET IBRAILEANU, ION CREANGA, STEFAN CEL MARE, 1 MAI,
    NARCISELOR, DN28, DC117, STADION, PETRU GROZA, MATEI CORVIN, PETRU RARES, NEAGOE
    BASARAB, VLAD TEPES, MIHAI VITEAZU, DJ281 across distinct vertex ranges (e.g.
    "vertices 357-359: STADION", "vertices 367-369: VLAD TEPES"); the 154-point
    feature resolves to 22 DECEMBRIE, ION CREANGA, NEAGOE BASARAB, STEJAR, ALEXANDRU
    IOAN CUZA, DJ281, MOVILEI, GARABET IBRAILEANU, DN28, ROZELOR, ETERNITATE, STEFAN
    CEL MARE, FULGER, NARCISELOR, DC117, DC116 — matching and exceeding the
    previously-documented 10-name/2-name split (more names surface here because this
    module checks EVERY vertex, not just a hand-picked sample).
  - A Timișoara-area `eeuz.mg4` tile (found via `find_tile_for_coord()` on the DC158
    anchor 21.20056°E/45.58739°N, tile_id 2231): its single 182-point feature
    resolves to "vertices 0-3: DC158" (reproducing the original single-vertex DC158
    validation from §3.6 exactly), then "vertices 84-86: DN59", "vertices 164-164:
    DJ592B" further along the same chain — confirming the join also finds ADDITIONAL
    real names beyond the one previously spot-checked.
- **Known limitations for a viewer session to be aware of**: (1) `eeu.rd` is not
  spatially sorted, so `build_rd_index()` is a per-call bounding-box scan of the whole
  590MB file — fine to call once per visible map area, NOT fine to call every
  pan/zoom frame; a future session could cache a persistent grid index to disk to
  avoid re-scanning. (2) the nearest-tolerance fallback uses a flat degree-distance
  grid with a latitude-only meters-to-degrees conversion, applied isotropically to
  both lon and lat — conservative (may occasionally miss a real match near the
  dataset's poleward edge), never falsely permissive. (3) most `.rd` records do not
  correspond to any tile vertex at all (many real, correctly-decoded vertices get
  `None`/unmatched — `.rd` looks like a name+anchor catalog, not a full shape-point
  store), so a fully-continuous "every vertex has a name" labeling should not be
  expected; a viewer should treat unmatched runs as "unlabeled connecting geometry",
  not as an error. (4) ambiguity between two close-together differently-named roads
  within tolerance is not resolved (first-found wins, undefined order) — not observed
  as a practical problem in this session's validation but not proven absent either.

### 3.10 `eeuz.fea` (FEATURE_COMPRESSED) — CRACKED: a multi-language place-name
gazetteer (cities, water bodies, islands, road-shield labels); directory
RECORD FORMAT now cracked (offset/length index, see below); coordinate
attachment tested at three granularities and REFUTED at all three
Reusable module: `research/feature_reader.py` (full details, caveats, and the
exact validation numbers in its module docstring — summary below). This
session's target was the one map-database file no prior session had properly
examined; it answers the long-standing "why has no cracked road tile ever
shown a lake, river, park, or coastline" question directly.

**What it contains (confirmed, not hypothesized)**: `eeuz.fea` is NOT a
water/land-use polygon file as originally hypothesized going in — it is a
general **multi-language named-place gazetteer**, covering at least:
cities/towns/villages at every scale (from national capitals down to tiny
Russian hamlets), named water bodies (Mediterranean, Black, Baltic, North,
Caspian Seas; Gulf of Bothnia), islands (the whole Greek archipelago:
Crete, Rhodes, Kos, Santorini, Milos, ...), and — not part of the original
hypothesis at all — **road/route shield labels** (European route numbers
E50/E58/E115/..., national route codes R22/A375/M4/..., Asian Highway
numbers AH30/AH61/..., relevant to this "EEU" dataset's extent into the
Caucasus/Russia). This is a real, previously-missing piece of the map: none
of the already-cracked road-geometry files (`eeu.rd`, `.mp0`/`.mg1`-`.mg4`)
carry any of this content, so it fully explains the original observation
that the rendered 2D map view (blue lakes/rivers, sea labels, route
shields) has no counterpart in anything decoded so far.

- **Container format (confirmed, same primitive as MAP_COMPRESSED)**:
  same 80-byte `(*$SIEMENS&^)`/`Copyright 1998` header template as
  `.mp0`/`.mg1`-`.mg4` (§3.6), then an ~11.7MB directory region (byte 80 to
  file offset 11,727,784 on the reference disc), then standard RFC1950 zlib
  streams packed back-to-back to EOF. Chaining verified byte-exact (not
  just via the window-based `consumed` heuristic, which §3.6 already
  documented as ~13% unreliable on MAP_COMPRESSED — this session
  additionally spot-checked with a byte-by-byte feed to confirm eeuz.fea
  doesn't share that quirk) across 4,036 consecutive entries before hitting
  the first of many small non-zlib "gaps" between entries (measured: one
  114-byte gap after the first 4,036-entry run; gap frequency and size vary
  a lot across the file, from 0 gaps/3,000 entries in some windows to
  282 gaps/3,000 in others — see feature_reader.py's docstring). The gap
  bytes are NOT understood (superficially resemble the same record
  "envelope" shape decompressed entries have, but this was not confirmed to
  be real data rather than coincidence) — `find_next_entry()`/
  `enumerate_entries()` treat them as an opaque region to skip past via
  local brute-force re-scan, which works reliably in practice.
- **Entry content**: unrelated to MAP_COMPRESSED's tile schema (no 0x0146
  magic, no anchor+delta feature blocks — `decode_features()`/
  `find_tile_anchor()` from `map_compressed_reader.py` were tried directly
  and found nothing). Entries are much smaller than MAP_COMPRESSED tiles
  (42-63,348 bytes decompressed observed, mean ~380 bytes in an early
  sample) and pack multiple small sub-records per compressed entry. Most
  sub-records are compact, mostly-identical "stub" records (many
  byte-for-byte identical across dozens of consecutive file entries,
  suggesting placeholder/empty-cell filler analogous to MAP_COMPRESSED's
  sentinel sub-index cells) with a 1-byte type/tag field (values 1-8,
  0x09, 0x12, 0x17, ... seen) and int16 fields that are frequently the
  literal sentinel `0x8000` — but a minority carry a much richer
  **multi-language name table**: `[1-byte language id][1-byte UTF-8 byte
  length][UTF-8 name bytes]`, repeated once per language (e.g. 20-26
  languages for a major place).
- **Concrete validation, same rigor as this project's other geographic
  checks**: an entry at file offset 11,781,130 (declen 1,056, the very
  first name-bearing entry after the confirmed first tile) decodes a
  26-language name table that is unambiguously **"Mediterranean Sea"** in
  every language on the disc's market (Bulgarian "SREDIZEMNO MORE", Czech
  "STŘEDOZEMNÍ MOŘE", English "MEDITERRANEAN SEA", Hungarian
  "FÖLDKÖZI-TENGER", Icelandic "MIDJARÐARHAF", Romanian "MAREA
  MEDITERANA", Russian "SREDIZEMNOE MORE", Turkish "AKDENIZ", ...). A wide
  scan spanning the WHOLE payload (11 sample windows at file fractions
  0%, 5%, 15%, 25%, 35%, 45%, 55%, 65%, 75%, 85%, 95%, 99.5% — 33,628
  entries sampled, 922 carrying a decodable 3+-language name) turned up
  hundreds more, including a direct cross-reference to a place this
  project has independently validated multiple times before: an entry at
  file offset 363,675,854 decodes **IASI, JASY, IASIO, JÁSZVÁSÁR, JASSY,
  YASSY, YAS** — every one a genuine historical/foreign-language exonym
  for **Iași, Romania** (JÁSZVÁSÁR is literally Hungarian for "market of
  Iași"; JASSY/YASSY are the standard English/German historical
  spellings) — the same real city already validated via `.rd`/tile
  decoding (§3.6) and `eeu.cty` (§3.8, postal-code cluster at
  27.55-27.57°E/47.12-47.14°N, matching real-world Iași at
  27.59°E/47.16°N). The wide scan's geographic spread on its own is a form
  of validation too: real, correctly-clustered place names appear all the
  way from Sicily/the Mediterranean to Scandinavia (OSLO, HELSINKI, TURKU/
  ÅBO, TRONDHEIM near the very end of the file) to deep into Russia
  (CHITA, BIROBIDZHAN, near the Mongolian/Manchurian border) — consistent
  with the "EEU" Navteq dataset's real, very wide coverage area.
- **NOT cracked: per-record coordinates.** Exhaustively scanning every
  2-byte-aligned offset inside both the "stub" records and the
  Mediterranean Sea/Iași records' non-string bytes for an int32 LE pair
  landing in the plausible EEU lon/lat range (3-46°E, 30-72°N, same
  convention as everywhere else in this project) after `/100000` found
  ZERO hits in the Iași record even under a much TIGHTER real-world-Iași
  window (27.3-27.9°E, 46.9-47.4°N), and zero hits across 500 sampled stub
  records. Broad-range hits DO occur elsewhere inside large entries, but
  scattered across totally unrelated countries within the SAME compressed
  entry (the Iași entry's other bytes coincidentally look like
  Algeria/Sicily/Georgia/Sweden/Finland coordinates) — strong evidence a
  large entry packs many UNRELATED small records together, not that any of
  those numbers are Iași's own position. Coordinates likely use a
  different scale/base (relative to an anchor stored in the still-uncracked
  directory region, or in a per-batch value not located this session), or
  named records may reference their real-world position by an external id
  into an already-cracked file (e.g. `eeu.cty`, which already has a real
  lon/lat for Iași) rather than storing it directly. **This means an
  arbitrary `.fea` entry can currently only be geolocated via its embedded
  name** (cross-referenced against real-world geography or `eeu.cty`) —
  there is no MAP_COMPRESSED-style `build_geo_index()` equivalent yet.
  **UPDATE (later session): the "external id into `eeu.cty`" sub-hypothesis
  above was tested directly and REFUTED, at this project's usual standard
  of evidence.** Ground truth: Iași's own top-level `eeu.cty` record is
  index **349791** (`eeu.cty` records' self-index always equals their file
  position, per §3.8, so this is exact). The full decompressed Iași `.fea`
  entry (offset 363,675,854) was scanned at every byte position for this
  exact value at 1/2/3/4-byte width × signed/unsigned × little/big-endian
  (14 encodings) — zero hits — plus its absolute and body-relative
  `eeu.cty` byte-offset, that offset divided by 2/4/8/16/79, `±1`, `×2`,
  `÷2`, and a two-uint16-word split — all zero. The same full sweep was
  repeated on **5 more independent, unambiguous real cities** (each the
  sole exact top-level `eeu.cty` name match): TURKU=403630,
  BRATISLAVA=182482, TRONDHEIM=389671, OSLO=384186, NISYROS=238217 —
  **0/6 hits in every encoding**, including the 586-byte NISYROS entry
  (only 3 packed names, negligible room for a false negative from noise).
  A parallel test of the alternative hypothesis — that the reference is to
  `eeuz.cl`'s own record position rather than the `.cty` index `.cl`
  stores (§3.8) — also came back empty (0/6 real hits; one apparent hit,
  TURKU/cl-position 122, is indistinguishable from chance given how small
  that value is relative to a 16KB entry, and did not recur for any other
  city). The directory region (see below) was checked too: neither a
  city's `.fea` entry offset nor its `.cty` index appears as a literal
  uint32 (LE or BE, byte-unaligned) anywhere in the ~11.7MB directory, for
  any of the 6 cities. **Conclusion: a `.fea` name record does not embed
  its place's `eeu.cty` self-index, byte-offset, or `.cl` position as a
  literal, scannable integer field** — this specific, previously-leading
  lead is closed, not just "still open." Full methodology, numbers, and
  remaining candidate leads (a hashed name key; an indirection through the
  still-uncracked directory; or `.fea` simply never storing a position at
  all, with real placement coming from elsewhere, e.g. the map-rendering
  label-placement mechanism noted in §3.6's "Label strings" finding):
  `research/feature_reader.py`'s module docstring, "CHECKED, REFUTED this
  session" section.
- **Directory region (byte 80 → file offset 11,727,784, ~11.7MB): a new,
  more specific structural lead, still not semantically cracked.** This
  session found the ENTIRE region divides EXACTLY into 977,308 fixed
  12-byte records plus an 8-byte trailer (11,727,704 = 977,308×12 + 8,
  confirmed by exact division, not just a heuristic — a stride-12
  byte-equality check also independently supports uniform 12-byte records
  end to end: 78-97% same-byte-at-offset-`i`-and-`i+12` in every 1MB
  window across the whole region). This is materially more specific than
  the prior session's "variable ~14-16 byte/tile records, ascending
  counter, unreliable past the first ~10" description — it's uniform
  12-byte records throughout, not just a short prefix. The last ~42-50
  records before the first real tile are byte-identical padding (one
  fixed 12-byte sentinel value), matching this file's own "stub record"
  padding convention seen elsewhere. **Field-level meaning NOT cracked**:
  the natural 3×uint32-LE grouping does not produce a clean offset/count
  table (values are large and look essentially random for most records,
  not small file-relative offsets); a promising hand-inspected
  sub-pattern near the tail (one field incrementing by ~38-39/record,
  suggestively close to real small entries' `complen`) did NOT hold up
  when checked programmatically across all 977,308 records with that same
  grouping — the true field boundaries within the 12 bytes are probably
  not a plain 4/4/4 split, or need extra context this session didn't find.
  Left as a concrete, actionable lead (977,308 records is also worth
  checking directly against a spatial-grid-cell-count hypothesis) rather
  than a decode.
- **Correction/discovery found while attempting a full-file enumeration
  run (important — changes the picture above): the 12-byte directory-table
  format is NOT unique to the byte-80 region — it recurs INSIDE the
  payload area too.** A full-file `enumerate_entries()` run (no time limit
  imposed, ran ~9 minutes) unexpectedly stopped at file offset 306,299,567
  (55.4% through the file, 507,680 entries enumerated, 15,569 small gaps
  successfully recovered along the way) because the small default
  gap-recovery window found nothing there. Direct investigation found the
  next real zlib entry only at file offset 311,300,723 — a gap of EXACTLY
  5,001,156 bytes (**416,763 × 12 + 0**, confirmed by exact division), and
  this gap region has the identical structural signature as the main
  directory (~87.5% stride-12 byte-equality; a long run of one repeated
  12-byte sentinel value; a tail of near-constant/slowly-incrementing
  fields immediately before real payload resumes — the same shape as the
  end of the byte-80 directory, just mirrored). The first entry after it
  has declen=72, identical to the very first entry of the whole file.
  **Conclusion**: `eeuz.fea` is not `[header][one 11.7MB directory][one
  long payload run]` — it embeds at least one more (plausibly several
  more, unexplored) directory-table-shaped region DIRECTLY IN THE PAYLOAD,
  most likely marking section/region boundaries (content immediately after
  this specific one, per the wide scan above, is the Greek islands
  cluster — plausibly a per-country/per-region partition boundary,
  unconfirmed). This is a materially better, more accurate structural
  understanding than "one directory at the front" — but it also means the
  original small-gap-window `enumerate_entries()` SILENTLY under-reports
  on a full-file run rather than erroring, which is now fixed:
  `find_next_entry_escalating()` retries with progressively larger windows
  (up to 25MB) and is the new default. A full-file run with the corrected
  default was not re-completed within this session's time budget (the
  first, uncorrected attempt alone took ~9 minutes to reach 55%), so the
  exact total entry/section count for the whole file is still unknown —
  left for a future session, now with the right tool to get there.
- **Practical fallback that WAS validated (per this session's explicit
  brief that this is an acceptable, valuable deliverable on its own)**:
  `enumerate_entries()` — brute-force but efficient, back-to-back
  zlib-stream walking with automatic gap recovery (now escalating-window
  by default, see above) — successfully enumerated real entries across ALL
  11 wide-scan sample windows spanning the full payload (0% to 99.5%,
  33,628 entries total) and, in the single longest contiguous run
  attempted, 507,680 consecutive real entries with 15,569 gaps correctly
  recovered before hitting the one large embedded directory region above.
  `scan_names()` extracts the multi-language name table from any given
  entry. Together these are, right now, the only working way to enumerate
  and approximately geolocate `.fea` content (via names), without a
  byte-level directory crack.
- **Honest scope assessment**: the core "what is this file" question is
  answered with concrete, cross-referenced evidence (a real, multi-market
  gazetteer of places/water/routes) — a genuinely new and useful answer to
  "what have we been missing" that's broader than the original water/parks
  hypothesis. The file's macro-structure is also now better understood
  than before (repeating directory-table-shaped section boundaries, not
  one directory at the front — see above). What remains open: the exact
  per-record coordinate encoding, the directory-table's field-level
  semantics, how many such embedded directory/section boundaries exist in
  total, and what the small (non-directory-shaped) non-zlib gaps actually
  are. **UPDATE (later session)**: the id-based cross-reference lead
  ((2) below, as it stood) was tried directly and REFUTED — see the
  dedicated "UPDATE" note on the per-record-coordinates bullet above for
  the full validation (6 independent real cities, 0/6 hits for a literal
  `eeu.cty` index/offset or `eeuz.cl` position, in every width/sign/
  endianness combination tried). A natural next session's starting point
  now: (1) re-run a full-file `enumerate_entries()` with the now-fixed
  escalating-window default to get the true total entry/section count,
  and (2) since a literal index/offset join is now ruled out, try a
  NON-literal link instead — e.g. hash/checksum the name string and look
  for that, or chase the still-uncracked directory region's own
  field-level semantics on the theory that IT (not the name record itself)
  holds the position/join key, indexed by the name record's position in
  file/decompression order.
- **UPDATE (later session): native-code symbol search corroborates the
  file's role and names its real loader class, but does not crack the
  coordinate link or the language-id numbering.** A targeted string/symbol
  search of `FHDD6.FLI`'s native PowerPC region (no disassembly — this
  remains a known dead end) found a much wider and denser cluster of
  demangled-looking C++ symbols than previously catalogued: roughly file
  offset 3.17M-3.2M and, more densely, **9.26M-14.02M** (extends past the
  previously-documented ~8.99M-11.35M range). This region reads like an
  embedded linker/RTTI symbol table (GCC2.x mangling, e.g.
  `16FeaCoordReceiver` = length-prefixed RTTI type-info name), not
  semantically-adjacent related code, so byte-proximity between symbols is
  not meaningful — only the symbol names themselves are.
  - **`MapLoaderJobFeatureFile`** (offset e.g. 0x00c8fbd0/13,171,664,
    `Load__23MapLoaderJobFeatureFile`) is almost certainly the real native
    loader class for FEATURE_COMPRESSED (compressionType 3, i.e. `.fea`)
    content: methods `startFeaParcel`/`endFeaParcel`/`failureFeaParcel`/
    `allowLoadParcelRawData`/`getExtractedMemory` (all taking a
    `FeaRequest&`), `receiveSegment(vseg&, ...)`, `receiveFeature(...,
    FeaCoordReceiver&)`, `addFeature(..., MapFeature*)`, `addKey(...,
    MapParcelKey&, MapRect&, MapPoint&)`, and nested classes
    `FeatureSorter` / `FeatureSorter::FeatureDescriptor`. Three sibling
    loader jobs share the identical `Fea*`-typed method signatures
    (`MapLoaderJobMP0Roads`, `MapLoaderJobTrafficView`, and
    `MapLoaderJobFeatureFlotPlot` — the last gated behind a
    `gl_bRunOnlyInSimulationOfLoadFlotPlotFile` flag, i.e. a
    simulation/test-only variant, not the real on-disc format) — so `Fea`
    here is confirmed to be this codebase's generic abbreviation for
    "Feature" (matches `MapFeature`, `MapSubFeature`,
    `MapFeaturePointList`, `createSubFeature`), not a `.fea`-specific
    coincidence, but `MapLoaderJobFeatureFile` is the one tied to a
    generic "feature file" rather than roads/traffic/simulation.
  - **Concrete new lead for the directory/coordinate question**:
    `addKey__23MapLoaderJobFeatureFileRC12MapParcelKeyRC7MapRectRC8MapPoint`
    (offset 12,888,100) shows the loader registers each parcel/entry's key
    together with a **`MapRect` (bounding box) and a `MapPoint`** — i.e.
    the real native code does associate a bounding rect + point with each
    `.fea` entry somewhere, which is consistent with (but does not decode)
    the still-uncracked 12-byte directory-region records or an
    equivalent `MapParcelKey` structure. Not pursued further this
    session (would require correlating this signature against the
    12-byte record layout, which is a data-structure-guessing exercise
    without the actual code) — a good next-session starting point.
  - **Class names corroborating `.fea`'s two content categories**:
    `MapRoadLabelFeature` (route/road-shield labels — `CB_AddLabel`,
    `SetRoadLabel`, `SetLabelParameters`) and
    `MapFeaturePolygonNamedLabel` (named area/polygon features — `AddCityLabel`,
    `AddAreaLabel`, `CB_AddNamedPolygon`, feeding `MapLabelCity`/
    `MapLabelArea`) are two distinct native classes that map cleanly onto
    `.fea`'s two confirmed content types (road-shield labels vs.
    named places/water bodies) — real corroborating evidence, not proof of
    which bytes mean what.
  - **Searched, not found**: no `Gazett*`, `Toponym`, `PlaceName`, or
    "place name"/"multilang" substrings anywhere in the native region or
    the 6,469-entry Java class inventory — this codebase simply doesn't
    use gazetteer terminology, it uses `Feature`/`Place`/`Label`. Also
    searched and found nothing useful: `CfcTypePlaceType`/
    `CfcTypePlaceCategoryType` (Java: `vdo.nav.api.shared.types.addr.Place*`)
    are real enums (`PLACE_CITY`, `PLACE_STREET`, `PLACE_CATALOG`, etc.,
    found as literal strings ~offset 25,511,437) but are the
    destination-entry/address-search subsystem's place-type vocabulary,
    not a `.fea` gazetteer-category tag — no `SEA`/`ISLAND`/`ROUTE_SHIELD`
    enum values were found anywhere.
  - **Language-id byte: no numeric mapping found.** A `LanguageTable`
    class exists (parsed via `XMLHandler`, i.e. `LanguageTable` is built
    at runtime from an external XML config not present as strings in this
    binary), alongside a `GlobalLanguageRuleTable` and `CfcLocale::Language`/
    `CfcLocale::Country` enums — but no literal small-integer-to-language
    mapping (e.g. "13=Hungarian") was found as a string anywhere searched.
    A separate, unrelated `LM::getTranslationType()` (LocationManagerImpl,
    for the destination-entry speller) maps a 2-letter ISO-style language
    *code string* to a transliteration type, which is a different,
    string-keyed mechanism, not the `.fea` per-name single-byte id.
    `SignpostInfo` (highway exit-sign text) independently uses the same
    general shape as `.fea`'s name records — a byte index selecting one
    of several per-language "text entries", each with its own coding/
    trans-type — useful as confirmation this multi-language-entry-by-byte-
    index pattern is a real, reused convention in this codebase, but it's
    a different class/file and doesn't reveal `.fea`'s specific id-to-
    language numbering.
  - **Bottom line**: this search materially deepens *what the surrounding
    native code looks like* (real loader class and method names now
    exist to anchor future work) but does not crack the byte-level
    directory format, the per-record coordinate encoding, or the
    language-id-to-language mapping — those remain exactly as
    UNCRACKED as stated above. No further disassembly was attempted, per
    this session's brief.
- **UPDATE (later session): the `addKey(MapParcelKey&, MapRect&, MapPoint&)`
  lead was tested directly — coordinate attachment at the per-section OR
  per-sub-tile-record granularity is REFUTED, but the investigation
  cracked the directory's actual byte-level format instead (a real,
  validated, independent result).** Task: test whether `.fea` attaches
  position at a coarser granularity than "one coordinate per name record"
  (already refuted, see above) — either one `MapRect` per directory-table
  "section", or one small coordinate per 12-byte directory record acting
  as a per-sub-tile anchor (the MAP_COMPRESSED pattern).
  - **Section/parcel-level `MapRect` or `MapPoint` at a directory table's
    own boundary — REFUTED.** Both known directory tables' exact byte
    boundaries (main table: byte 80 → file offset 11,727,784; embedded
    table: 306,299,567 → 311,300,723) were dumped and scanned at every byte
    alignment, LE and BE, `/100000` scale, for a 16-byte `MapRect` or 8-byte
    `MapPoint` decoding to real geography (Mediterranean/S.Europe for the
    first table's boundary, Greece 19-28°E/34-42°N for the second's, per
    the wide-scan content clustering already documented). Result: the true
    boundary bytes are occupied by the already-documented repeating 12-byte
    PADDING SENTINEL (`12 41 c2 af 00×8` / `12 8e 12 73 00×8` / `00×8 1f 92
    63 55`), which does not decode to plausible coordinates in any tested
    encoding — every apparent numeric "hit" is a trivial artifact of that
    sentinel value recurring every 12 bytes, not a genuine one-off header.
  - **Per-12-byte-record sub-tile anchor, expecting smooth spatial
    progression like MAP_COMPRESSED's tile anchors — REFUTED, and the real
    mechanism found instead.** Real MAP_COMPRESSED tile anchors have lag-1
    autocorrelation ≈0.98-0.99 (computed fresh this session on `mg4` for a
    direct baseline); real (non-padding) `.fea` directory records score only
    0.05-0.37 under every field-width/endianness tried — no smooth
    progression exists. Deeper inspection explains why: 42.7% of consecutive
    records in the main directory table are byte-identical to their
    predecessor (collision/padding runs), only 57% of all 977,308 records
    are even distinct, and run-length statistics follow a decay curve
    typical of a **hash table with open-addressing collisions**, not a
    spatial array — directly explaining the prior session's "small integers
    collide" note and its failed 4/4/4-byte little-endian grouping attempt.
  - **The real crack (validated at scale): 12-byte directory records are
    big-endian `(offset, declen, complen)` index triples — a file-position
    index, NOT geographic data.** The earlier sessions' mistake was
    assuming little-endian and a single fixed field order. Correctly read
    as three big-endian uint32 fields, a dense real run of 1,191 consecutive
    records (main table, records 764811-766002, file offset 9,177,812)
    shows `[declen][complen][offset]`, with `offset` pointing at a real
    zlib stream whose exact decompressed length/consumed bytes match
    `declen`/`complen` — verified by full decompression, not a
    "looks-like-a-header" heuristic: **1,008/1,191 (84.7%)** exact matches
    on this run, **1,478/5,000 (29.6%)** on a random whole-table sample, and
    **2.7%-73.5% per 20,000-record block** across a systematic sweep of all
    977,308 records (rising toward the end of the table) — a real,
    substantial, independently-reproducible fraction of the table, not
    noise. **A second field-order variant, `[offset][declen][complen]`
    (offset FIRST), was confirmed against real named-place ground truth**:
    searching both directory tables for the LITERAL, exact `(offset,
    declen, complen)` values of this project's own independently-verified
    real `.fea` entries (exact declen/complen obtained by direct
    decompression) found all three 32-bit fields adjacent and correctly
    ordered for **4 of 7** test cases — Mediterranean Sea (in the main
    table) and Iasi/Bratislava/Nisyros (in the embedded table) — at both
    12-byte-grid-aligned AND non-aligned byte positions (Mediterranean
    Sea's own record sits 8 bytes off the naive zero-phase grid, consistent
    with a genuine hash table rather than one uniform flat array). Getting
    three independent 32-bit values to land adjacently, correctly grouped,
    is not a coincidence at this project's evidentiary standard.
  - **Load-bearing negative finding (RESOLVED by a later session — see
    below)**: Turku, Trondheim, and Oslo (`.fea` entries all around file
    offset ~550MB) had **no record in either of the 2 known directory
    tables**, in any encoding, phase, or field order — confirmed absent,
    not just unfound. Since the embedded table was shown to index an
    entry (Iasi, 363MB) far past its own physical location (306-311MB),
    a directory table is not restricted to indexing the payload immediately
    following it — this is a keyed/hash index over (at least a large part
    of) the file, not a per-physical-section table. The natural explanation
    for the 3 missing cities was at least a THIRD, unlocated directory-table-
    shaped region further into the file — found and confirmed below.
  - **Why this is a refutation, not just another "not found"**: (1) the
    boundary scan found no MapRect/MapPoint-shaped data at all, only
    sentinel repeats; (2) the "12-byte record = coordinate" reading is now
    known to be wrong in a mechanistically understood way — these are
    big-endian file-offset/length index fields, and every earlier
    little-endian coordinate reading of the same bytes necessarily produces
    "essentially random"-looking 32-bit values, exactly as previously
    reported; (3) the byte ranges a directory table would notionally bound
    are enormous (hundreds of MB — most of the dataset), far too coarse to
    serve as a per-region `MapRect` even in principle; (4) `MapLoaderJob
    FeatureFile::addKey`'s `MapRect`/`MapPoint` arguments, under this new
    understanding, more plausibly correspond to `eeu.cty`'s ALREADY-KNOWN
    bounding boxes/representative points (§3.8), looked up by name/id AFTER
    resolving a `.fea` record via this hash index — i.e. the coordinate
    plausibly never lives in `.fea` at all. **Recommendation: three
    independent coordinate-attachment hypotheses (per-record embedded
    value, per-record `.cty`/`.cl` join, per-section/per-sub-tile
    granularity) have now all been tested and refuted at this project's
    usual evidentiary standard. Geolocating an arbitrary `.fea` entry via
    its own bytes is a reasonable case to set aside for now** — `scan_names()`
    + real-world/`eeu.cty` name cross-reference remains the only working
    method, which is already sufficient for the practical use cases this
    project has needed (name search, content inventory). The directory's
    now-cracked offset-index format is still useful in its own right (fast
    entry lookup without brute-force `enumerate_entries()` scanning) and is
    a legitimate, separate win from this session, even though it doesn't
    solve geolocation. Reusable code: `decode_directory_table()`,
    `verify_index_triple()`, `find_index_record_for_offset()`,
    `KNOWN_DIRECTORY_TABLES` in `research/feature_reader.py`.

**A LATER SESSION: the missing 3rd directory table (T3) found, plus a
4th (T4) — resolves the Turku/Trondheim/Oslo negative finding
completely.** The concrete next step above (an escalating-window scan
watching for another multi-MB non-zlib gap) was carried out, using a
faster method: a whole-file stride-12 self-similarity scan
(`arr[:-12] == arr[12:]`, blocked and averaged with numpy — a few
seconds over the whole 553MB file, vs. a slow sequential entry-by-entry
walk). This immediately located all previously-known directory-shaped
regions in one pass PLUS 2 new ones:
  ```
  T1 (known):  byte 80          - 11,800,000    density ~0.865
  T2 (known):  306,200,000      - 311,200,000   density ~0.838
  T4 (NEW):    529,687,345      - 529,889,749    density ~0.75 (16,867 records)
  T3 (NEW):    546,882,678      - 547,158,126    density ~0.63-0.79 (22,954 records)
  ```
  Both new tables share T1/T2's exact structure (real zlib-entry chain
  walking confirms a genuine non-payload gap at each, with a real zlib
  header starting immediately after) and a small twist: each begins with
  an undecoded 6-byte prefix before its 12-byte-aligned records start
  (`gap_len - 6` divides evenly by 12 in both cases — 275,454-6=275,448=
  12×22,954 for T3; 202,410-6=202,404=12×16,867 for T4). Both verify at
  HIGH rates with the existing `decode_directory_table()`/
  `verify_index_triple()` machinery, no new code needed: **T3: 17,107/
  22,954 (74.5%)**, **T4: 9,968/16,867 (59.1%)** — both well above T1's
  own average (2.7%-73.5% per block), consistent with real tables, not
  noise.
  **Direct resolution of the exact open negative finding**: the payload
  immediately following T3 contains Turku (offset 550,612,987), Trondheim
  (550,725,854), and Oslo (550,550,064) — the SAME 3 cities confirmed
  absent from T1/T2. `find_index_record_for_offset()` against T3 alone
  finds all 3 immediately, and the found `(declen, complen)` fields match
  a REAL decompression at each city's own offset EXACTLY, 3/3, both
  fields: Turku (16,028/10,596), Trondheim (34,972/24,283), Oslo
  (40,665/28,358) — no tolerance needed. This was never a hole in the
  offset/declen/complen index-triple model, just an unlocated 3rd table.
  Combined, `eeuz.fea` now has 4 confirmed directory tables (T1: 977,308
  records, T2: 416,763, T3: 22,954, T4: 16,867), strongly suggesting the
  file embeds a SERIES of these regions scattered throughout the payload,
  not just 1 or 2. A 5th, weaker candidate at the very end of the file
  (~551.16M-EOF, where real zlib chaining genuinely stops for good) was
  also found by the same density scan but does NOT verify cleanly at any
  byte phase tried (best: 3.4%) — left as an honest, low-confidence lead,
  not a validated 5th table. Full writeup: `research/feature_reader.py`'s
  "A LATER SESSION: the missing 3rd directory table (T3) FOUND" section.

**A LATER SESSION's new lead: `eeu.mod`'s own schema for this table** —
never checked against `eeuz.fea` specifically before. `eeu.mod`'s
`feature` block (§3.16) is the single largest in the whole schema (~77
real fields), describing a `MapHeader{db_cover bbox, parcel_width/
height/cnt_x/cnt_y/norm_x/norm_y grid, feaType, scaleCnt, scales[]}` →
`ParcelHeader{offset, byteCnt, byteCntZip}` → `FeatureDataHeader{
category, type, flags, feaPointCnt, ...}` structure, with type-specific
geometry variants (`line`/`poly`/`point`/`road`) each carrying
`delta_long`/`delta_lat` fields. **`ParcelHeader{offset, byteCnt,
byteCntZip}` is a striking independent confirmation-and-naming of the
already-cracked 12-byte directory triple above** (3 uint32 = 12 bytes
exactly: `offset`=the already-found `offset`, `byteCnt`=`declen`,
`byteCntZip`=`complen`) — found two different ways in the same session.
**Tested and refuted**: the schema's `parcel_cnt_x`×`parcel_cnt_y`
grid-dimension product, on the natural guess it should equal the
directory's own 977,308-record count — `977,308 = 929 × 1,052` — neither
value appears anywhere as a uint32 (either endianness) in the first
12MB of the file. **The single most actionable new lead, not yet
tested**: the schema explicitly names `delta_long`/`delta_lat` as
per-geometry-point fields — i.e. coordinates in this format are
RELATIVE deltas, not absolute values, directly explaining why the
exhaustive absolute-coordinate search above found nothing; a future
session should search for a small delta pair near an anchor (a parcel's
own coordinate, or `eeu.cty`'s already-known real position for that
place) rather than a standalone absolute value. **This is a genuine,
unresolved TENSION, not a resolved contradiction**: the schema's own
parcel-grid/delta-coordinate design sits uneasily next to the
independently well-evidenced "hash table, no locatable coordinate"
conclusion above. Possible reconciliations, none tested: this disc's
build may use only a subset of the schema's full generality (matching
the pattern already seen elsewhere, e.g. `eeuz.pca`'s always-zero
`clusterOffset`/`clusterCount`, §3.23) — note that T3/T4 (found and
confirmed above, including the Turku/Trondheim/Oslo table) are now
located and were checked; they show the same offset/declen/complen
index-triple shape as T1/T2, not a grid/delta-coordinate one, so this
reconciliation option remains open rather than resolved; or the entries
tested so far (Mediterranean
Sea, Iasi, ...) may be a `type`/`category` that doesn't carry the
`point`/`road` geometry sub-structure at all. Full details and the
complete field list: `research/feature_reader.py`'s module docstring
("A LATER SESSION's new lead" section) and `research/mod_reader.py`'s
`extract_blocks()` with token `['fea']`.

### 3.11 `eeu.abc` — alphabet / supported-language table (897 bytes, NOT_COMPRESSED) — CRACKED
The smallest file examined this session, and its name describes its content
exactly. **Validated at full scale — zero leftover bytes across the entire
803-byte body.** Layout: 94-byte header, then `[uint16 LE text_len][text_len
bytes of UTF-8][fixed 7-byte language-table records to EOF]`.
- **Character repertoire**: `text_len` (199) bytes of UTF-8 decode cleanly to
  125 codepoints — space, basic punctuation, digits, plain uppercase Latin
  A-Z, every accented/extended Latin uppercase letter used by a European
  language on this disc, the full uppercase Cyrillic alphabet, and a
  trailing NUL terminator. This is exactly the uppercase glyph set every
  place/road name on this disc already uses (§3.1/§3.8/etc. — names are
  consistently uppercase) — plausibly backing the firmware's on-screen
  spelling keyboard (`AESpellerType`, §2.3) and/or TTS input validation.
- **Language table — CRACKED**: the remaining 602 bytes parse as exactly
  **86 fixed 7-byte records**, `[3-byte ISO-639-2-style language code][flag
  byte A][uint8 index][flag byte B][the same index repeated]`. The `index`
  field is a plain ascending 1..86 counter (record N's own position — not a
  cross-reference to anything). 52 distinct language codes, mostly real
  ISO 639-2/B abbreviations (`bul`, `cze`, `dan`, `dut`, `eng`, `fin`, `fre`,
  `ger`, `gre`, `hun`, `ice`, `ita`, `pol`, `por`, `rum`, `rus`, `spa`,
  `swe`, `tur`, `ukr`, `wel`, `arm`, `aze`, `baq`, `bel`, `mne`, plus `und` =
  ISO 639-2's real "Undetermined" code) — a handful of non-standard-looking
  codes also appear (`aaa`, `bet`, `grt`, `mat`, `rst`, `sct`, `ukt`),
  unidentified against any standard list.
- **`(flag_a, flag_b)` — CONFIRMED, a much later session, via real embedded
  data.** Exactly 3 distinct pairs occur in the whole file — `(2, 2)` (42
  records, the most common), `(4, 8)` (23), `(1, 5)` (21) — no other
  combination appears. Found while investigating `mp0`'s own embedded
  district-name string table (§3.16): some entries near the Bulgaria/
  Turkey and Bulgaria/Greece border tiles pair a plain name with a
  syllable-broken PHONETIC transcription using the next language index up,
  e.g. `80^UZUNHACI$81^u|zun|ha|"dZ1` and — cleanest of all — `24^BULGARIA$
  25^bVl|"ge@|rI|@` (a real, correct IPA-ish rendering of the actual
  ENGLISH pronunciation of "Bulgaria") and `24^TURKEY$25^"t3|ki`.
  Cross-referencing the index pairs used against this table directly:
  `tur`=`(80,81)`=`(1,5)`+`(4,8)`; `eng`=`(24,25)`=`(2,2)`+`(4,8)`;
  `gre`=`(38,39)`=`(1,5)`+`(4,8)` — **`(4, 8)` is now CONFIRMED as the
  per-language PHONETIC/PRONUNCIATION-TRANSCRIPTION slot**, not a guess.
  `(1, 5)` and `(2, 2)` both serve as "plain display name" slots (confirmed
  via real entries using each); which of the two a given language gets
  isn't yet explained. Full methodology: `research/abc_reader.py`'s module
  docstring and `research/map_compressed_reader.py`'s `decode_topology()`
  docstring (the district-name-table discovery this rode in on).

### 3.12 `eeu.aff` — affix table (138 bytes, NOT_COMPRESSED) — CRACKED (structure); EMPTY on this disc
94-byte header (see §3.1's now-cracked trailing fields: type code 2, record
count 1, total size 138 — all consistent), then a **44-byte body that is
entirely zero bytes** — i.e. exactly **1 record of 44 bytes**, per the
header's own now-decoded record-count field, and that one record carries no
real data on this disc. Genuinely fully characterized structurally (there is
nothing left to decode — the record-count field, the body length, and the
all-zero content all agree with each other), just not semantically
informative here. The name plausibly stands for "affix" (cf. Hunspell's own
`.aff` file convention for spell-checking/word-stripping rules), which would
fit naturally alongside this disc's other language/TTS-support files
(§3.5 `eeuz.pca`, §3.11 `eeu.abc`) — a single empty record is consistent
with "this East-Europe dataset's languages don't need any affix-stripping
rule for search/TTS normalization," though that reading isn't independently
confirmed (no other disc region was available to compare against a
non-empty `.aff`). Reader: `research/aff_reader.py` (thin, given the empty
body — mainly documents the now-shared header-field decode).

### 3.13 `eeu.cal` — country/continent name catalog (23.3KB, NOT_COMPRESSED) — CRACKED
94-byte header (record count 484 read straight off its own now-cracked
`bytes[86:88]` field, §3.12), then exactly **484 fixed 48-byte records**,
**validated exhaustively — every one of the 35 distinct groups inspected in
full, not sampled**: `[uint16 LE country_id][uint8 is_continent][uint8
lang_index][40-byte NUL-padded name][4 bytes constant 0xFFFFFFFF]`.
- **`country_id` — CRACKED: alphabetical rank by ISO 3166-1 alpha-3 code.**
  `0` is reserved for 2 "Europe" pseudo-entries (`EUROPE`/`ЕВРОПА`), not
  tied to any real `eeu.ctr` row. `1`-`34` are the disc's 34 unique alpha-3
  codes (`eeu.ctr` has 35 rows but lists Russia twice, once transliterated
  and once in Cyrillic, both `RUS`) in exactly alphabetical order: `1`=ALB
  (Albania) ... `8`=DEU (Germany) ... `21`=MKD (North Macedonia) ...
  `34`=VAT (Vatican City). This is a **third, independent** country
  numbering on this disc — distinct from both `eeu.ctr`'s own arbitrary row
  order (§3.11-adjacent) and `eeu.cty`'s empirically-resolved `country_tag`
  (§3.8) — found by directly sorting `eeu.ctr`'s already-cracked alpha-3
  field and comparing against the observed groups, no new empirical
  matching needed. Every name in every one of the 35 groups was checked and
  is a genuine real-world name for that exact country/continent in some
  real language — e.g. group 8 (Germany) has 13 entries spanning
  Portuguese/Spanish/French/Turkish/German/Dutch/Italian/Russian/English/
  Slovak/Czech/Polish/Scandinavian; group 21 (North Macedonia) alone has 40
  entries, reflecting that country's real historical naming dispute (many
  literally spell out "former Yugoslav Republic of Macedonia" in different
  languages).
- **`lang_index` — CRACKED: matches `eeu.abc`'s own per-language `index`
  field exactly** (§3.11) — confirmed directly, e.g. `lang_index=24` ('eng')
  on the English entries, `66` ('rus') on the Cyrillic entry, `30` ('fre')
  on the French entries, `80` ('tur') on `ARNAVUTLUK` (Albania in
  Turkish) — every cross-check correct, no exceptions.
- **`is_continent`**: `1` only for the 2 Europe pseudo-entries, `0` for
  every real country.
- Trailing 4 bytes: constant `0xFFFFFFFF` on all 484 records — an unused
  reserved sentinel, not real content.

Full methodology: `research/cal_reader.py`'s module docstring.

### 3.14 `eeu.cat` — country/continent bounding-box table (759 bytes, NOT_COMPRESSED) — CRACKED
94-byte header (record count 35 read straight off its own header field,
§3.12), then exactly **35 fixed 19-byte records**: `[uint24 LE country_id][int32
LE lon_min][int32 LE lat_min][int32 LE lon_max][int32 LE lat_max]`, same
`/100000` degree convention used everywhere else on this disc. `country_id`
is the **same numbering §3.13 cracked for `eeu.cal`** (0=Europe, 1-34=the
34 real countries in alphabetical ISO alpha-3 order).
- **Validated directly against real-world geography** — most of the 35
  boxes match closely enough to be unambiguous: Germany (id 8) is (5.87,
  47.28)-(15.04, 55.05), essentially exact; Austria (2) is (9.53,
  46.39)-(17.16, 49.02), correct down to its real western/eastern borders;
  Switzerland and Italy are similarly exact. Three real microstates get
  correspondingly tiny boxes — San Marino (27): (12.40, 43.89)-(12.52,
  43.99); Liechtenstein (17): (9.48, 47.05)-(9.62, 47.26); Vatican City
  (34), the smallest of the three as expected: (12.45, 41.73)-(12.66,
  41.91). Norway (23) correctly reaches its real eastern border with
  Russia via Finnmark: (4.51, 57.75)-(31.13, 71.18). Russia (26) and
  "Europe" (0) both reach a max longitude of 179.38°E — consistent with
  this dataset's already-documented coverage of Russia's far east (§3.10's
  `eeuz.fea` findings: Chita, Birobidzhan) and with "Europe"'s own box
  being a genuine bounding union over every member country's box, not a
  separately-surveyed continent shape.
- **One honest anomaly, not resolved this session**: Denmark (id 9) shows
  `lon_min` = 1.69°E — identical, bit-for-bit, to "Europe"'s own overall
  `lon_min`. Real mainland Denmark's westernmost point is much further
  east (~8°E). Every other country's own values look geographically
  plausible in isolation, so this is flagged as a real, narrow open
  question, not swept into "probably fine."

Full methodology: `research/cat_reader.py`'s module docstring.

### 3.15 `eeu.cny` — county catalog (400KB, NOT_COMPRESSED) — CRACKED, field names corrected via §3.16's schema discovery
94-byte header (record count 2,326 read straight off its own header
field), then exactly **2,326 fixed 176-byte records**, **validated at full
scale (every record parses cleanly, zero exceptions)**:
`[uint16 LE county_id][uint16 LE state_id][26 zero bytes][36-byte
NUL-padded name][uint8 timeinfo_id][109 zero bytes]`. A real sub-national
administrative catalog — one level below `eeu.stt`'s "state" table
(regions/cantons — cracked in a later session, §3.21), one
level above `eeu.cty`'s cities/localities.

**Field names corrected**: this section originally called the first two
fields `index`/`region_id`; §3.16's discovery of `eeu.mod` (the disc's own
schema dictionary) named them precisely — `countyID`/`stateID` — and
confirmed this file is genuinely the schema's own "county" table (not, as
first guessed, a "region" table itself).
- **`name` — CRACKED**: real administrative divisions, confirmed directly.
  The first 5 records alone are `CHANIA`/`RETHYMNO`/`IRAKLEIO`/`LASITHI`
  — the 4 real prefectures of Crete, Greece, in their real west-to-east
  geographic order — followed by `IMPERIA`, a real Italian Liguria
  province. Further records include all 8 real provinces of Piedmont,
  Italy (`TORINO`/`CUNEO`/`ASTI`/`ALESSANDRIA`/`BIELLA`/`VERCELLI`/
  `NOVARA`/`VERBANO-CUSIO-OSSOLA`) and real districts of the Swiss cantons
  Valais, Vaud, and Fribourg.
- **`state_id` — CRACKED (identity, and — later session, §3.21 —
  independently confirmed directly against `eeu.stt`'s own content, not
  just real-world geography)**: groups counties into their real
  sub-national region/canton/province — not a country reference (`eeu.cal`/
  `eeu.cat`'s own `country_id` tops out at 34; this reaches 690) but a real
  foreign key into `eeu.stt`'s own "state" records (§3.16, opened §3.21).
  Validated directly against real geography: every county with
  `state_id=4` is a real Valais district; `state_id=6` is Vaud;
  `state_id=8` is Fribourg; `state_id=3` groups Piedmont's 8 provinces;
  `state_id=39` groups Liguria's. **§3.21 closes the loop**: `eeu.cny`'s
  691 distinct `state_id` values are the exact same *set* as `eeu.stt`'s
  own 691 `state_id` values, and 3 spot-checks (`CHANIA`→state 0=`KRITI`/
  Greece; `IMPERIA`→state 39=`LIGURIA`/Italy; `SION`→state 4=`WALLIS`/
  Switzerland) all resolve exactly right against `eeu.stt`'s own real
  content. Not allocated in file order (first-seen sequence is
  `0, 39, 3, 1, 4, 2, 5, 6, ...`, not `0, 1, 2, 3, ...`) and records
  sharing one `state_id` aren't necessarily contiguous.
- **`timeinfo_id` (byte 66) — CRACKED (identity), CONFIRMED directly
  against `eeu.ti`'s own content in a later session (§3.22)**: range
  1–13, heavily skewed (`1` alone covers 72% of records, `3` is next at
  17%); constant within 98.6% of `state_id` groups (681/691). §3.16's
  schema names the field immediately after `name` in the real "county"
  table `timeinfoID` — a foreign key into `eeu.ti`'s own time-dependent-
  restriction records (timezone, start/duration fields — seasonal or
  time-of-day access rules), which fits this byte's shape well (most
  counties share a common "default" profile) and directly explains why
  this section's own two originally-tested hypotheses (country
  reference; count of child `eeu.cty` localities) both failed — it isn't
  counting or naming the county itself, it's pointing at a shared,
  county-independent rule catalog. **§3.22 closes the loop**: `eeu.ti`'s
  own 2 richest, most-detailed timeinfo profiles (`timeinfo_id` 1 and 3)
  are EXACTLY this field's own 2 most common values (72% and 17% of all
  counties) — an exact, non-coincidental correspondence.
- The 26 always-zero bytes between `state_id` and `name`, and the 109
  always-zero bytes after `timeinfo_id`, match the schema's own remaining
  "county" fields (`zoneID`, `start_cityID`, `end_cityID`, `cover`, a
  `min_long`/`min_lat`/`max_long`/`max_lat` bounding box, `alpha_cities`,
  `cityID`) — all apparently unpopulated for every county on this disc,
  not incorrectly identified; exact per-field byte boundaries within these
  regions weren't independently determined (every candidate field being
  zero makes the split unverifiable from this file's own content alone).

Full methodology: `research/cny_reader.py`'s module docstring.

### 3.16 `eeu.mod` — database schema dictionary (40KB, NOT_COMPRESSED) — CRACKED: the single most valuable file examined this project
94-byte header (`bytes[86:88]` record count correctly reads `0` — this is
NOT a fixed-record file, same situation as `eeu.il`), then a dense run of
NUL-terminated ASCII strings (table names, field names, and short
file-extension markers) interleaved with short binary runs whose exact
per-field type/width encoding was **not** fully reverse-engineered (see
below) — but the string content alone, extracted with a plain
printable-ASCII-run-terminated-by-NUL scan, is already the biggest single
win of this whole project: **this file is the disc's own full database
schema / data dictionary**, built by the original authoring tool — whose
real name this file itself reveals: `Arriba`, version `5.3` (the literal
first two strings in the file), almost certainly the actual internal name
of Navteq/Siemens/Continental's own map-database compiler.

Scanning the whole body this way finds exactly 1,605 strings, organized as
one block per real table: `[table name][fieldHeader][stamp/copyright/
db_release/db_version/comp_version/dbID/fileID/rec_cnt/byte_cnt][own data
fields...][short file-extension marker]`. All **36 expected file-extension
tokens** appear, in the same order this project already independently
confirmed those files' identities in — strong corroboration the extraction
is correct, not coincidental: `abc`, `ctr`, `stt`, `cny`, `cty`, `rd`,
`typ`, `aff`, `mp0`/`mg1`-`mg4`/`mpa`/`mpb` (one shared block — `mpa`/
`mpb` aren't present as real files on this disc), `si`, `fea`, `cal`,
`ct`, `cl`, `rt`, `rl`, `prl`, `pot`, `pol`, `pmm`, `pmc`, `pmp`, `ti`,
`iof`, `il`, `tmc`, `cat`, `pca`, `pct`, `prd`. `eeu.pcl` has no
corresponding block at all (not just an empty one, like `.pmp`/`.pol`/
`.pot` get) — **its real purpose was tracked down in a later session, not
through this file but through the disc's own `files.cfg`, see §3.17.**

**Confirmed corrections and extensions to already-cracked files, found by
directly cross-referencing this schema**:
- **`eeuz.pct`'s "group" field mystery (§3.5) is fully solved**: the real
  fields are `.../phonemeRoadOffset/phonemeRoadCount` — a pointer into
  `eeuz.prd`, not a "language-variant grouping key." Validated directly
  against real `eeuz.prd` content for 4 example cities (Venice lands next
  to real Adriatic ferry routes `VENEZIA-CORFÙ`/`VENEZIA-PATRASSO`;
  Vatican City among real Italian streets; Munich at a real square;
  Frankfurt among real streets) — see `research/pct_reader.py`'s updated
  docstring.
- **`eeu.ctr`'s 2 "trailing zero bytes" (§3.11-adjacent)** are named
  `speedUnit`/`drivingSide` (both zero-valued for every country on this
  disc).
- **`eeuz.rl`'s previously-unresolved trailing flag byte and always-zero
  `bytes[4:7]` (§3.7)** are named `hasHouseNumbers` and a packed
  `minNumber`/`maxNumber` range — consistent with the flag's own
  already-measured 71%/29% split and the range's always-zero content.
- **`eeu.il`'s 7 still-unresolved prefix bytes (§3.2)** include a named
  `vnodeID` field — a real, disc-confirmed "virtual node id" reference,
  and a promising, **not yet pursued** lead for the long-standing
  topology node-id↔coordinate mapping problem
  (`resolve_topology_adjacency()`, §3.6/§8 item 5), since the MAP_COMPRESSED
  tile schema (below) independently references `left_node`/`right_node`
  fields on its own segment records.
- **`eeu.cal`'s always-`0xFFFFFFFF` trailer (§3.13)** is named
  `cityTreeOffset`/`postalcodeTreeOffset` (2× uint16, both the `0xFFFF`
  "unset" sentinel for every country/continent entry).
- **`eeu.cny`** — see §3.15's corrected write-up above.
- **The "Ordinary Map File" block is the MAP_COMPRESSED tile schema**
  (`eeuz.mp0`/`.mg1`-`.mg4`, §3.6) and is the largest single block (615
  field names) — parcels, k-d tree nodes, segments (`seg`, `seginfoID`,
  `restr_left`/`restr_right`, `left_node`/`right_node`, `length`), shapes,
  turn restrictions, ADAS/truck speed limits, lane connectivity, and much
  more. **`left_node`/`right_node` on a segment record is a strong, not
  yet pursued lead for finally closing the topology node-id↔coordinate
  mapping gap** — this session did not attempt cross-referencing it
  against the tile format's own still-partially-cracked tagged record
  table, given the scope of that undertaking on its own.
- **`eeu.si` is named `seginfo`**, with real fields `rank`, `class`,
  `divided`, `drivables`, `toll_vignette`, `toll_road`, `restclass`,
  `urban`, `route_num_type`, `paved`, ... — a genuine road-classification
  table. **Opened in a later session (§3.20)**: `rank`/`class`/`divided`,
  `route_num_type`/`paved`, `driveable_lower`/`drivable_upper`,
  `tollbooth_direction`, and `restclass` were all cracked, but the
  hoped-for link to `eeu.rd`'s own `bytes[1:5]` turned out not to hold up
  — `eeu.rd`'s `bytes[1:5]` doesn't decode to `eeu.si`-style values using
  `eeu.si`'s own bit layout, and shows no correlation with `eeu.iof`'s
  own `count` field either (§3.3). See §3.20/§3.3 for the corrected
  leads (the real `seginfoID` FK likely lives on the MAP_COMPRESSED tile
  format's own segment records instead). **A later session attempted
  exactly this** (goal: real per-segment road styling — divided/paved/
  tollbooth — in the map viewer). **Real progress, not a crack**: found
  a genuine, previously undocumented 3rd tile region right after
  `decode_topology()`'s own topology table ends (real, visibly grouped
  byte structure on a real 83-point test tile, confirmed non-empty and
  similarly-shaped on 8 more real tiles; its own byte length correlates
  with point count at ~8.95 bytes/point). This is almost certainly (part
  of) the `seg_list`/`attr_list` region `eeu.mod`'s schema describes —
  but the exact per-record boundary and field layout weren't pinned down
  precisely enough to test a specific byte position against `eeu.si`'s
  own real value ranges as ground truth, and a quick every-byte-position
  scan across several tiles was too noisy for a clean answer. **A
  record-boundary search was then attempted directly and found
  inconclusive** — a documented methodological trap: an unconstrained
  backtracking search for a `tag → record-length` rule that consumes a
  tile's tail with zero leftover "succeeds" trivially (many byte
  partitions sum to the right total), and even a more constrained search
  (uniform 8-byte records) that also "succeeds" numerically produces
  obvious garbage values after the first few records when actually
  decoded — exact total-byte-consumption is necessary but nowhere near
  sufficient here, unlike `eeuz.fea`'s directory crack or `eeu.tmc`'s
  `chain_count` formula, which both had an independent exact cross-check
  available. Left honestly as an open, real lead — see
  `map_compressed_reader.py`'s `decode_topology()` docstring for the
  full writeup and the suggested next step. **Confirmed real and
  actively used, a later session, from the firmware side** (§2.6): real,
  versioned accessor function names — `db_seg_rank_V004`/`_speed_V004`/
  `_tunnel_V004`/`_node_V004`/`_unique_vid_V005`/`_plural_junction_V005`/
  `_is_part_of_freeway_intersection_V005`, and an exact name match,
  `db_seg_marker_left_V004`/`db_seg_marker_right_V004` — names only, no
  byte offsets. **A fresh record-boundary attempt, directly informed by
  this field list (`seginfoID_ext_count` as a principled explanation for
  the variable record length), a still-later session**: suggestive but
  NOT a crack. A plain unaligned-2-byte-window frequency scan of the
  83-point reference tile's own tail found one value (`13708`) dominating
  74/83 records — bounded within `eeu.si`'s own real range, and looking
  that record up gives plausible (not contradictory) real field values —
  but the SAME test on 2 more independent reference tiles did NOT
  replicate cleanly (no single dominant value on either, and one shows
  the same byte pattern as a likely artifact on the first tile). Honest
  conclusion: a real, new lead, not a confirmed crack — see
  `decode_topology()`'s own docstring for the full account, including why
  the mixed result doesn't rule out the underlying hypothesis (the
  shortcut used unaligned scanning, not a real record parse). **That
  exact next step (a proper `seginfoID_ext_count`-driven parser) was
  then attempted directly, same session — and a single-count-field
  model is now EXHAUSTIVELY REFUTED, computationally.** A joint search
  over every plausible `(base length, count-byte offset, extension
  size, id offset)` combination, requiring exact whole-tail consumption
  under `record_length = base + count_value × extension_size`: **zero
  configurations succeed, at any count cap up to 15**. Root cause,
  confirmed directly: the single most plausible count-byte position
  (whose overall value distribution genuinely looks like a real small
  count field, 0/1/2/3 decreasing) reads the identical value on 3
  consecutive real records whose true lengths are 8, 8, and 11 bytes —
  no single formula tied to any fixed byte position can explain that.
  This is considerably more solid than the earlier hand-checked
  refutation. Real conclusion: the tail's true record format needs
  MULTIPLE independently-variable fields (plausible candidates:
  `seg_marker_left`/`seg_marker_right`/`restr_left`/`restr_right` each
  independently present or absent, not one shared toggle) — a genuinely
  bigger parsing problem, closer in scope to what it took to crack
  `eeu.tmc`'s own variable-field-count `chain_count` structure, than a
  quick continuation can responsibly solve. A real wall for the
  "single formula" approach specifically, with a concrete next-model
  suggestion, not a dead end for the investigation as a whole.
  **The user then provided real, human-verified ground truth from their
  own RNS510 unit running this exact disc** (3 precisely-located real
  road segments via the map viewer's edge-pick tool: 2 independent
  points on the A1/Trakia motorway near Sofia, confirmed divided, plus a
  contrast point on Vladimir Bashev street, Sofia, a confirmed one-way
  local street — exact tile/offset/feature/point coordinates preserved
  in `decode_topology()`'s own docstring). **3 independent shortcut
  methods were tested against this real ground truth and ALL REFUTED**:
  the `seginfoID`-lookup approach came back directionally plausible but
  weak for `divided`, and BACKWARDS (lower than baseline on a real
  Bulgarian motorway, which legally requires a toll vignette) for
  `toll_vignette` — a clean, real refutation, not just noise. A 3rd,
  purely positional/distributional scan found one candidate that failed
  a basic internal-consistency check (its own statistics swung wildly
  between the first and second half of a single real road's own tail
  region) — very plausibly a multiple-comparisons artifact from
  screening ~150 candidate positions, correctly caught rather than
  reported as a discovery. **A real, well-earned wall for any shortcut
  approach**, now backed by real ground truth rather than just internal
  statistics — see `decode_topology()`'s docstring for the full account,
  the exact preserved ground-truth coordinates, and a concrete reframing
  for a future session (the firmware's own `db_seg_speed_V004`/
  `db_seg_rank_V004` accessor names suggest per-segment classification
  may be encoded DIRECTLY in each `seg` record, with `seginfoID` being a
  comparatively rare optional cross-reference, not the primary
  mechanism). **A real, working per-ID-length parser was then built by
  hand (`research/map_compressed_reader.py`'s `parse_seg_tail_records()`/
  `seg_tail_region()`) — genuine progress, validated on `mg4`-format
  tiles**: the same 2-byte leading id at a record's start always implies
  the same record length (learned on the fly), and every valid record
  ends in exactly `00 00` — a real, semantically meaningful terminator
  that keeps this from the earlier over-permissive trap. Converges fast
  and deterministically (~2,000 steps, unseeded) to a stable solution
  whose length distribution (71% plain 8-byte records, rest larger
  "special" records) matches the already-established "junctions get
  bigger records" pattern from the local topology crack. **6 more real,
  human-verified ground-truth points from the user's own RNS510 unit**
  (full coordinates preserved in `decode_topology()`'s docstring) let
  this parser's own 8-vs-9-byte length-distribution signal be tested
  directly against KNOWN divided/non-divided status — **and it's now
  CLEANLY REFUTED as a "divided" indicator**: `A6` (confirmed non-
  divided, still under construction) and `Hemus/A2` (confirmed divided)
  show nearly IDENTICAL signatures (~40%/~46-49%), while `A1` (also
  confirmed divided) shows a completely different one (71%/14%) from
  both. Two roads with opposite divided status look alike; two roads
  with the same status look different — ruling this specific signal out
  as a divided-status indicator, though the underlying parser structure
  is still real. Plausible untested alternatives: construction/data-
  vintage status, geometric complexity, or an unrelated `eeu.si` field
  entirely. The `mp0`-format Vladimir Bashev ground truth remains
  unusable for this specific parser (confirmed genuinely different byte
  structure — a wide-range attempt exhausted 15M search steps with no
  solution) — was a separate reverse-engineering target, **now solved for
  a real chunk of the tail** (see below).

  **`mp0`'s own tail format — first real crack, a later session.** The
  Vladimir Bashev tail (14,393 bytes) splits into distinct zones, not
  one uniform structure. A dominant recurring 2-byte tag (`f1 44`, ~1 in
  every 15 bytes) marks a middle zone (bytes 3,788-12,312, 8,524 bytes)
  with a real, validated record format: 7 bytes normally (`[tag][0x44]
  [0x00][idx: u16][subidx][value]`), 11 bytes for a "special" case with
  4 extra bytes inserted (directly analogous to `mg4`'s own bigger
  junction records). Proved via an exhaustive backward DP (every
  position must reach the zone's exact end through a chain of 7s and
  11s, no partial credit) — **949 records, exact, zero-leftover coverage
  of the whole zone** (477×7-byte + 472×11-byte). `idx` climbs steadily
  through exactly 3 resets — matching this tile's 3 real, named streets
  (Vladimir Bashev/Svetlostruy/San Martin) one-for-one, strong
  independent confirmation `idx` is a real per-street segment counter,
  with street boundaries encoded purely by the counter resetting. The
  paired `subidx`/`value` pattern looks like a forward/backward
  attribute pair, but the real-world meaning of `value` isn't identified
  yet. **Cross-checked against Vladimir Bashev's own confirmed one-way
  status — CLEANLY REFUTED**: idx values missing a `subidx=1` record
  scatter randomly through the whole range in both groups (37%/48% rate)
  instead of clustering into a contiguous run, which is what a real
  one-way stretch should look like — `subidx` more likely marks a sparse
  per-segment attribute than direction of travel.

  **Zone 3 (tail bytes 12,312-14,393) hand-inspected next — a real,
  plausible SPEED-LIMIT crack.** Zone 3 itself splits into 3 further
  sub-zones. Sub-zone 3a (822 bytes) has its own validated record format
  (same exhaustive-DP technique, 131 records, zero leftover bytes): a
  `type` byte deterministically selects a 6- or 7-byte record width, and
  the byte right before the terminator is one of exactly 4 values —
  `30`, `40`, `50`, `80` — all real, standard km/h speed limits, a
  plausible on-disk match for the firmware's known `db_seg_speed_V004`
  accessor (not yet ground-truth-confirmed). Sub-zone 3b (196 bytes) is
  a clean monotonic list of multiples of 4, not yet identified — a
  later session tested and REFUTED the "scaled point/vertex index"
  hypothesis: dividing by 4 gives valid point indices on the original
  tile (with a weak, inconclusive bias toward junction points), but on
  a 2nd tile the resulting indices exceed that tile's own real point
  count entirely — a clean refutation, not just inconclusive. Sub-zone
  3c (1,056 bytes) starts as small signed deltas then shifts character
  partway through — a later session found the "large, repeating values"
  were a MISALIGNMENT ARTIFACT, not real data: the true record width
  changes to 3 bytes (`[value: s16][0x04 terminator]`) partway through,
  and reading it with the wrong 2-byte stride produces exactly this
  kind of confusing drift (`1279` = `0x04ff`, literally a terminator
  byte glued to the next record's own first byte). DP-validated: 34
  real 3-byte (plus a few 6/7-byte "special") records, zero leftover
  bytes. A 3rd, distinct sub-region (2 monotonically-increasing `u16`
  sequences read as pairs) sits between the deltas and this record run.
  None of the 3 regions are semantically named yet, but the "seemingly
  random large values" mystery is now explained. Full writeup:
  `decode_topology()`'s docstring, "FIRST REAL CRACK of a chunk of
  `mp0`'s own tail structure" and the zone-3 UPDATE immediately after it.

  **Zone 1 (tail bytes 0-3,788) — a real numeric-record crack PLUS a
  genuine, independently-verified Bulgarian place-name string table.**
  446 records exactly match this project's own already-confirmed `mg4`
  8-byte `seg_list` layout (`[id(2)][byte2(1)][byte3(1)][value(4, ends
  in 00 00)]`) via exhaustive DP — 98.5% exact coverage (3,731 of 3,788
  bytes), widths 6-14, 8-byte dominant (56.7%). The remaining 57 bytes
  are NOT records at all — they're a small, human-readable name table
  that continues seamlessly across the artificial zone1/zone2 boundary:
  3 real strings in the form `<binary header><lang-index digits>^<NAME>
  \0` — `13^ZHK IZTOK` (a real Sofia residential-complex name, "East"),
  `13^HLADILNIKA` (a real Sofia neighborhood), `13^TSENTAR/13^CENTRUM`
  (2 transliterations of "Center"). **The `13` prefix is independently,
  exactly confirmed**: `eeu.abc`'s own already-cracked language table
  has index 13 == `bul` (Bulgarian), checked directly against the real
  file (`('bul', 1, 13, 5)`) — the prefix is the language index written
  as literal ASCII digits, not a raw byte. Almost certainly district/
  neighborhood labels (not the street's own name), consistent with a
  "which area is this tile in" lookup.

  **Header partially cracked, a later session — one field real and
  validated.** Found the same name-table convention in 2 more tiles (25
  real entries total across 3 tiles), including a 2nd independently
  confirmed language index: `24^` = `eng` (English, `eeu.abc` index 24),
  correctly appearing on English-only entries (`24^SOFIA AIRPORT
  CENTER`) and paired with Bulgarian on bilingual ones (`13^TERMINAL 2/
  24^TERMINAL 2`) — real-world-plausible for an international airport.
  The header is a fixed 17 bytes: `[X: u16 LE][Y: u16 LE][0x01][0x00]
  [ZZ: 1 byte][WW: 1 byte][9 zero bytes]`. `[0x01][0x00]` is a constant
  marker on every entry.

  **Re-validated at scale, a later session — a real off-by-one bug
  caught and fixed, then `X` fully cracked.** Testing at scale (2,055
  entries, 400 Bulgaria-region tiles) first looked like a near-total
  failure of the `WW` formula — but the bug was in this project's own
  earlier claim, not the data: **`WW` actually equals `len(text)`
  exactly (no `-1`)**, re-confirmed against the original 3-tile sample.
  With the fix: 91.2% of entries match exactly; excluding a different,
  coincidentally-regex-matching record type (phonetic/pronunciation
  transcriptions) raises this to 95.8%. **`X` is now FULLY explained**:
  it's simply the entry's own total byte length (header + text + NUL)
  rounded up to the next odd integer — zero exceptions across 1,834
  validated entries.

  **The remaining 4.2% was a SECOND bug (fixed to 100%), and `Y`/`ZZ`
  turned out to encode a real HIGHWAY-SIGN structure.** The regex's own
  `{3,40}` length cap was truncating longer multi-destination strings
  (e.g. the real 47-character `13^MEZDRA/13^KREMIKOVTSI/13^KALOTINA/
  13^BELGRAD`), matching a spurious later point inside the string and
  reading garbage as its header — widened to `{3,200}`, now **100.0%
  exact match on both `WW` and `X`**. With clean data: **`Y` links
  PAIRS of entries into a route↔destination relationship, and `ZZ`'s
  family (16/17 vs 4/5) encodes which role a string plays** — 172 of
  203 same-tile `Y`-sharing pairs (84.7%) show one entry in each
  family, and the actual text confirms it directly: family-4 entries
  are real road/route designators (`13^A3/13^E79`, `65^DN6`, bare
  numbers like `13^9/13^E87`), family-16 entries are real destination
  place names (`SOFIA`, `PLOVDIV`, `BUCURESTI`). Entries whose `Y` is
  unique in their tile (no pairing partner) are overwhelmingly
  family-16 (98.4%) — the "standalone place name" default. Not
  perfectly clean (31 of 203 pairs share the same family); `Y`'s own
  numeric value beyond "is it shared" is still unidentified.

  **The entries this table's own regex deliberately excludes (`|`/`$`/
  apostrophe — "phonetic transcriptions") turned out to be a real,
  independent crack that closes an OLD open question in §3.11's own
  `eeu.abc` writeup.** See that section above for the full `(flag_a,
  flag_b)` = `(4,8)`-is-the-phonetic-slot confirmation, found via these
  exact entries (e.g. `24^BULGARIA$25^bVl|"ge@|rI|@`).

  **`Y`-vs-`idx` tested, genuinely inconclusive**: checked whether `Y`
  directly references zone 2's own per-street `idx` counter — 100% of
  `Y` values in every tile tested ARE valid `idx` values, but zone 2's
  own `idx` range turned out to be 100% dense (zero gaps) on every tile
  checked, making simple membership uninformative either way. Would
  need a tile with real `idx` gaps to test meaningfully — none found
  yet.

  **Zone 2's record format GENERALIZED to multiple tiles, a still-later
  session — one real correction found.** `decode_mp0_zone2()` re-derives
  the format without hardcoding Vladimir Bashev's own `0x44` middle
  byte, auto-detecting each tile's own dominant tag instead. Tested on 5
  more Sofia-area `mp0` tiles: 4 succeeded structurally (real 516-819-
  record dense runs, matching shape); a naive "first tag occurrence"
  boundary-finder failed on 2 of them (landed on a sparse, unrelated
  early occurrence) — fixed by requiring several consecutive anchors to
  already show the 7-or-11-byte stride before accepting a start
  position. **Correction**: the original write-up implied `0x44` was a
  fixed attribute-type tag; testing elsewhere shows each tile has its
  OWN dominant middle byte and its OWN per-slot tag values (the original
  `tag=0xf4/subidx=1` binary flag doesn't recur as `0xf4` anywhere else
  — other tiles show `0xf2`/`0xe8`/`0xf5`/`0xeb` instead, each still
  forming its own clean small-value slot) — confirming `id` is a genuine
  per-street identifier, not a record-type marker. `zone2_categorical_
  slots()` computes the "most categorical slot" fresh per tile.

  **A real bug found and fixed in that same boundary-finding, then zone
  3a (the speed-limit candidate) generalized on top of it.** Chaining
  `decode_mp0_zone3a()` right after `decode_mp0_zone2()`'s own `"end"`
  surfaced a genuine over-permissive-trap bug: on the ORIGINAL Vladimir
  Bashev tile, `"end"` landed 4 bytes past the true boundary — the last
  real record's own trailing bytes coincidentally also satisfied the
  11-byte check, producing an implausible `subidx=133` (real `subidx`
  is always 0-5). Fixed with a `subidx <= 10` plausibility guard;
  re-verified this changes nothing about the already-validated
  949-record result, only removes the spurious over-reach. With that
  fix, zone 3a reproduces the original speed distribution EXACTLY
  (`{0x00:61, 0x1e:7, 0x28:14, 0x32:24, 0x50:26}`) and generalizes to 4
  of 5 more tiles. **A genuinely exciting extra confirmation**: the
  Sofia-airport tile shows speed values `{0,20,40,50,60,70,80}` km/h —
  wider but still perfectly clean multiples of 10, exactly what you'd
  expect from an airport's mixed taxiway/access-road/parking zones vs.
  a uniform residential street.

  **Zone 2's own `(tag, subidx)` slots characterized by value
  distribution — one clean binary flag found.** `tag=0xf4, subidx=1`
  (70 records) has only 2 distinct values ever (`0xcc`: 43, `0xe1`: 27,
  a 61%/39% split) — the cleanest categorical slot in the whole zone, a
  real candidate for a boolean road property (one-way is an obvious
  guess). 2 more slots look like small enums with a dominant value; 2
  more (`f1/0`, `f1/1`) are clearly numeric, not flags. **2 independent
  attempts to localize which `idx` values belong to Vladimir Bashev
  specifically both failed**, honestly documented rather than reused:
  point-index-with-topology-shift landed on uninformative "no data"
  records, and an edge-ordinal check turned out to rely on an artifact
  of Python's own sort order, not a real structural correspondence — so
  `f4/1`'s guess remains untestable for now. Real fix needed: recover
  the topology table's own raw on-disk record order and test whether
  `idx` tracks that, not point index.

  **A DIFFERENT signal from the same parser, tried right after — real,
  clean, and the most promising lead in this file region so far**:
  whether an 8-byte record's `byte2` or `byte3` is EXACTLY ZERO. Across
  the 2 precisely-matched tiles with known status: `A1` and `Hemus`
  (both CONFIRMED divided) show `byte2/3==0` on 0 of 273 combined
  8-byte records (0.0%, exactly); `A6` (CONFIRMED non-divided) shows it
  on 11 of 89 (12.4%). A 3rd, less-certain sample (`A2-west`, confirmed
  non-divided but with only an imprecise ~13km tile match) shows 96 of
  137 (70.1%) — a much higher rate, but the SAME qualitative direction
  (nonzero, unlike both precisely-matched divided tiles' clean 0.0%). A
  real, qualitative presence/absence pattern, not just a magnitude
  shift — genuinely promising, but NOT yet a crack: only 2 tiles have
  both a precise match and confirmed status, and the non-divided rate
  varies a lot between samples (12.4% vs. 70.1%). One more precisely-
  matched divided-road ground-truth point would tell us whether 0.0%
  really holds as a hard rule. Full writeup: `decode_topology()`'s own
  docstring, "A REAL, CLEAN, QUALITATIVE signal" section. **Refined,
  still the same session**: a systematic per-byte sweep found bytes 1,
  2, and 3 (not just 2/3) each independently show this exact 0.0%
  pattern; byte4's own small "leak" on `A1` turned out to be numeric
  coincidence (its trailing `value` happening to be an exact multiple
  of 256), not real signal — refined to bytes 1-3 specifically. A
  specific semantic explanation (turn restrictions correlating with
  real intersections) was tested against this project's OWN already-
  cracked local topology/junction data and CLEANLY REFUTED — junction-
  dense tiles showed LESS signal, not more.

  **A genuine POSITIVE crack, not a refutation**: the trailing "value"
  field (bytes 4-7) is very likely `eeu.mod`'s own named `length`
  field — a real distance, in DECIMETERS. Confirmed by comparing its
  distribution against REAL point-to-point distances computed from
  this project's own already-cracked coordinate geometry (no new
  ground truth needed): the MAXIMUM value matches tightly on both
  tiles (`A1_2389`: 5709.0m vs. the real max 5754.2m, within 1%; `A6`:
  6476.9m vs. 6821.3m, within 5%) — not the kind of agreement two
  unrelated quantities produce by chance. The first field this project
  can actually NAME in the `seg_list` record, even though bytes 1-3's
  own divided-correlated meaning remains unnamed. The viewer's
  "Show predicted divided" overlay (`rns510_map_viewer.py`) was updated
  to the refined bytes 1-3 signal.

  **Firmware-side emulation probe, a later session** (§2.6 has the full
  technique writeup): a Unicorn PowerPC emulator used as a candidate
  classifier over real firmware code found one function (VA `0x1f95d0`)
  that genuinely reads `id`/`byte1`/`length` from a `seg_list`-shaped
  pointer and feeds them through a 3-table lookup/linked-list-walk chain
  before writing a resolved field into an output parameter — a real,
  substantive trace, but its shape (junction-chain walk, reference-byte
  match, output write) looks more like a name/label or junction resolver
  than a direct "divided flag" read, and its own callers couldn't be
  statically confirmed (indirect call convention), so this refines the
  open question rather than closing it. `byte1`'s exact identity is
  still unnamed.

**What's not cracked**: the exact binary encoding surrounding each field
name (hand inspection suggests a `[type/flag][size][size][...]`-style
per-field descriptor — e.g. `stamp`/`copyright`/`db_release`/`db_version`/
`comp_version` all share an identical trailing byte pattern, consistent
with 5 identically-shaped fixed 16-byte string fields — but a complete,
general parser for arbitrary fields wasn't built this session).

Full methodology, the complete table→file mapping, and every
cross-reference: `research/mod_reader.py`'s module docstring.

### 3.17 `eeu.pcl` — phoneme cluster list (94 bytes, NOT_COMPRESSED) — IDENTIFIED: genuinely empty on this disc, real name confirmed via the disc's own `files.cfg`
94-byte header only — **zero body bytes**, confirmed directly: file size
is exactly 94, and `bytes[90:94]` (`total_size`, §3.1) reads 94 too, an
exact match (this is *not* one of the 2 files where that field stores the
would-be body size instead of the header-inclusive total, e.g. `eeu.iof`/
`eeu.mod`). `bytes[86:88]` (`record_count_lo16`) reads `0`, consistent.
`bytes[84:86]` (`file_type`) reads `48` — a code private to this per-file
header field, confirmed **not** the same numbering as `files.cfg`'s own
`fileId` below (e.g. `eeu.rd`'s header `file_type` is `4`, but `files.cfg`
assigns it `fileId 0`).

§3.16's `eeu.mod` schema dictionary has no table block for `eeu.pcl` at
all (re-confirmed: the only `pcl` occurrences anywhere in `eeu.mod`'s
1,605-string dump are as a *prefix* inside compound field names —
`pcl_cnt`, `maxPclId`, `pcl_dir`, `pcl_hndl_list`, `pcl_hndl`, `pcl_offs`,
`max_pcl_id`, `pcl_handle` — all belonging to the unrelated "Ordinary Map
File" MAP_COMPRESSED tile schema, where "parcel" is an internal spatial-
subdivision/index concept for locating shapes inside a tile; no standalone
`\x00pcl\x00`-delimited token exists anywhere in the file). That dead end
is what this session's `eeu.mod` write-up meant by "its real purpose is
still unexplained."

The real answer was hiding in plain sight in a file this project had
already partially used (for its top-level 4-compression-type legend, §3
intro) but never fully read line-by-line: the disc's own **`files.cfg`**
(plain text, disc root, not part of the `db/` compressed-data model) is a
literal file-id → extension → compression-type → one-line-comment table
for **all 39** logical file types the database *format* supports
(`numFileIds = 39`) — not just the ~30-odd this specific EU-East disc
actually populates. Its entry for id 27:

```
27 = pcl, 0, cached		# phoneme cluster list
```

`compressionType 0` = NOT_COMPRESSED, matching the real file exactly (no
`eeuz.pcl` exists). The comment places it squarely in the same
phonetic/TTS-support family as [`eeu.abc`](#311-euabc--alphabet--supported-language-table-897-bytes-not_compressed--cracked)
(character repertoire), `eeuz.pca` (phoneme catalog — id 26, right before
`pcl` in the table), `eeuz.pct` (phoneme *city* list — id 28, right
after), and `eeuz.prd` (phoneme *road* list — id 29): a "phoneme cluster"
is a standard TTS/phonetics term for a grouped sequence of phonemes (e.g.
a syllable onset/coda consonant cluster), so this file's role was almost
certainly a lookup table of valid/known phoneme clusters for the TTS
engine's own pronunciation or syllabification rules — conceptually
adjacent to, but distinct from, `eeuz.pca`'s catalog of individual
phonemes.

**Cross-checking `files.cfg` further also surfaced 3 file-id entries this
project had never encountered on disc at all**: `7 = ptp` ("point types"),
`15 = pdx` ("poi index file"), `16 = pti` ("point types international") —
none of `eeu.ptp`/`eeu.pdx`/`eeu.pti`/`eeuz.ptp`/`eeuz.pdx`/`eeuz.pti`
exist anywhere under `db/` on this disc, not even as empty 94-byte
placeholders like `eeu.pcl`/`.pmp`/`.pol`/`.pot` — a real disc/build-time
distinction between "declared by the format, file not even created this
release" (`ptp`/`pdx`/`pti`) and "declared, file created but left empty"
(`pcl`/`pmp`/`pol`/`pot`). Not pursued further this session; noted for
completeness since it came directly from the same `files.cfg` read.

**Bottom line**: `eeu.pcl`'s identity is now fully established straight
from the disc's own authoring metadata (not inference) — a real, named,
NOT_COMPRESSED "phoneme cluster list" table that the map-authoring tool
simply never populated for this specific EU East V17 release. There is no
byte-level format left to reverse-engineer (zero body bytes exist to
examine); this is as cracked as an empty file can get.

### 3.18 `eeu.pmc` — postal-code "merge city" table (16.3MB, NOT_COMPRESSED) — CRACKED: fixed 4-byte records, all-identity content confirms this disc's whole postal-code subsystem is unpopulated
94-byte header (`bytes[90:94]` `total_size` matches the real file size
exactly, `16,336,510`). Body is `16,336,416` bytes of fixed **4-byte**
(uint32 LE) records — real record count **4,084,104**, an EXACT match
(`4,084,104 × 4 = 16,336,416`, zero leftover bytes) once the header's own
`record_count_lo16` field is un-truncated correctly: `20,872 + 65,536×62
= 4,084,104`. The earlier unexamined-files pass (§3 "Worth investigating
first") only tried small wraparound multiples (`k=0..4`) and flagged this
file "not clean" — the real multiple just needed a much larger `k`, not a
different convention.

**The content is a perfect identity function, checked exhaustively across
all 4,084,104 records, zero exceptions**: record `i`'s value is exactly
`i` — `0, 1, 2, 3, ..., 4084103`. A real "merge" table, even a mostly-
trivial one, would be expected to have at least some entries pointing
elsewhere; a perfect identity sequence across 4 million+ records this
large is the strongest possible signal of an auto-generated placeholder
array, not populated data.

`eeu.mod`'s own schema (§3.16) names this table `postalcodeListMergeCity`
(13 fields); `files.cfg` (§3.17) calls it the "postalcode merge city
file". **`eeu.pmm`** (schema name `postalcodeListSeparate`, `files.cfg`
"postalcode merge separator file") — same size, same `record_count_lo16`
— was checked directly against `eeu.pmc` and is **byte-identical in body
content**, the same 4,084,104-entry identity array; only the 94-byte
header's `file_type` byte (`63` vs. `64`) differs between the two files.
Combined with the already-confirmed-empty `eeu.pmp`
(`postalcodeListMergePostalcode`), `eeu.pol` (`postalcodeList`), and
`eeu.pot` (`postalcodeTree`) — all bare 94-byte headers with zero body —
**the entire postal-code subsystem (`.pol`/`.pot`/`.pmm`/`.pmc`/`.pmp`) is
unpopulated on this specific EU East V17 disc.** Plausibly this
East-Europe dataset's country set didn't have licensed/available postal
code data at build time, or the feature wasn't enabled for this
particular release — not independently confirmed (no other region/market
disc was available this session to compare against a populated
postal-code subsystem).

**RESOLVED (§3.19): why a 4-byte record when `eeu.mod`'s schema counts 13
(`postalcodeListMergeCity`)/15 (`postalcodeListSeparate`) strings per
block?** Those counts include 11 shared boilerplate strings every
`eeu.mod` table block carries (table name, `...Header` struct name, and
the 9 `stamp`/`copyright`/.../`byte_cnt` header-struct fields, §3.16)
plus 1 more struct-name wrapper — not 13/15 independent data fields. The
REAL per-record payload is `mergedListIndex` (1 field) for `eeu.pmc` and
`type`+`listIndex` (2 fields, packed under one wrapper struct name
`type_and_listIndex` — strongly suggesting a single bit-packed physical
word) for `eeu.pmm`. Both resolve cleanly to the single 4-byte field
found by direct inspection. See §3.19 for the investigation that found
this (`eeu.pmp`'s own schema independently confirms the pattern — same
lone-`mergedListIndex` shape as `eeu.pmc`).

### 3.19 `eeu.pmp`, `eeu.pol`, `eeu.pot` — postal-code merge/list/tree files (94 bytes each, NOT_COMPRESSED) — IDENTIFIED: genuinely empty on this disc, `eeu.mod`'s schema reconstructs the intended design
All 3 share the exact same 94-byte empty template as `eeu.pcl` (§3.17,
identical header bytes except the `file_type` byte): file size is exactly
94, `total_size` (`bytes[90:94]`) also reads 94 — an exact match, not one
of the 2 known "stores body size instead" exceptions — and
`record_count_lo16` (`bytes[86:88]`) reads `0`. `file_type`
(`bytes[84:86]`): `eeu.pmp`=65, `eeu.pol`=61, `eeu.pot`=62. `files.cfg`'s
own comments: `34 = pol, 0, cached # postalcode list file`,
`35 = pot, 0, cached # postalcode tree file`, `38 = pmp, 0, cached
# postalcode merge postalcode file`.

Pulling each file's real (non-boilerplate) field list straight from
`eeu.mod`'s schema (`research/mod_reader.py`'s `extract_blocks()`) gives
a coherent picture of a 3-stage postal-code lookup pipeline, none of it
populated on this disc:
- **`eeu.pot` (`postalcodeTree`)** — real fields: `key`,
  `nextSelectableCharTreeIndex`, `nextSelectableCharTreeCount`,
  `startDataListIndex`, `dataListCount`. **Byte-for-byte the same
  field-name template already found for `roadTree` (`eeuz.rt`) and
  `cityTree` (`eeuz.ct`)** (§3.7/§3.8) — i.e. `eeu.pot` was designed as a
  character-trie search index over postal-code strings, using the exact
  same data structure already used for road-name and city-name
  autocomplete/search (container differs though: `eeuz.rt`/`.ct` are
  FLAT_COMPRESSED, `eeu.pot` is plain NOT_COMPRESSED per `files.cfg`'s
  own compressionType column). The exact byte-level trie-node encoding
  itself is still not fully cracked even for the *populated*
  `eeuz.rt`/`.ct` (`research/city_reader.py`'s own docstring calls it
  "the same still-uncracked variable-node structure"), so `eeu.pot` being
  empty loses nothing that was otherwise crackable this session either
  way.
- **`eeu.pol` (`postalcodeList`)** — real fields: `postalcode`,
  `Latitude`, `Longitude`, `ListIdMain`. A real postal-code-to-coordinate
  lookup record: the postal code string itself, a representative point
  (the disc's usual `/100000` int32 convention elsewhere), and a
  `ListIdMain` foreign key — plausibly into the same kind of city/merge-
  list indices the `.pmc`/`.pmm`/`.pmp` trio manage, though this specific
  link was **not independently confirmed** (no populated `eeu.pol` was
  available this session to check against).
- **`eeu.pmp` (`postalcodeListMergePostalcode`)** — real field: a single
  `mergedListIndex`. Structurally the third sibling of the already-
  cracked `eeu.pmc`/`eeu.pmm` pair (§3.18) — same "merge" naming
  convention, same lone-index shape, and the cross-reference that
  resolved §3.18's own open question above.

Together the 3 "merge" files (`.pmc` city-side, `.pmm` type/list
separator, `.pmp` postalcode-side) read as a set of redirect/
consolidation tables for cases where postal codes and cities don't map
1:1 (one postal code spanning multiple cities, or one city needing
multiple postal-code entries) — a real, sensible design, just never
populated on this East-Europe V17 release. Combined with §3.18's finding
that `eeu.pmc`/`.pmm` carry a provable placeholder identity array rather
than real content, the coherent conclusion for the whole file family is:
**the entire postal-code subsystem (`.pol`/`.pot`/`.pmm`/`.pmc`/`.pmp`)
was designed and schema'd but never populated on this specific disc.**

### 3.20 `eeu.si` — segment classification table (195KB, NOT_COMPRESSED) — CRACKED: fixed 8-byte records, all 20 real leaf fields positioned in exact schema order
94-byte header (record count 24,353 read straight from the header),
then exactly **24,353 fixed 8-byte records** — validated at full scale:
`24,353 × 8 = 194,824` bytes, an exact match to the real body size, zero
leftover. Real content lives in the first **5 bytes**; `bytes[5:8]` are
**always zero** on every one of the 24,353 records checked (not sampled)
— unused/reserved padding.

Only **20,381 of 24,353 records have a distinct 5-byte payload** — 3,972
records duplicate another record's exact value. Not a clean dedup table
(that would require zero duplicates); more likely allocated per some
other axis (e.g. per-region/country) where the same attribute
combination legitimately recurs.

`eeu.mod`'s own schema (§3.16) names this table `seginfo`, with 20 real
leaf fields once the 11 shared header-struct boilerplate strings are
excluded (§3.16): `rank`, `class`, `divided`, [`drivables`:
`driveable_lower`, `drivable_upper`], `toll_vignette`, `toll_road`,
`tollbooth_direction`, `hwy_complex_bit`, `restclass`, `landmark`,
`dbldig`, `detailedcity`, `urban`, `bifurcation_left`,
`bifurcation_right`, `rnc`, `truck_digitized`, `route_num_type`,
`paved`. `drivables` is (by analogy with `eeu.pmm`'s own
`type_and_listIndex` wrapper, §3.19) almost certainly a struct/group
name wrapping its two children, not itself a field — the inconsistent
spelling ("driveable" vs "drivable") is a real quirk of the original
compiler's packing, not a project typo, consistent with a single logical
value split low/high across non-adjacent bits.

**Byte 0 (bits 0-7) CRACKED = `rank`/`class`/`divided`, in exact schema
order**:
```
bits[0:3]  rank      -- values 0-4 ONLY (5,6,7 never observed)
bits[3:7]  class     -- values 0-12 (13,14,15 never observed)
bit[7]     divided   -- boolean, 16.30% of records (3,970/24,353)
```
**Byte 4's low nibble (bits 32-35) CRACKED = `route_num_type`/`paved`,
the exact LAST 2 real fields in schema order, in the LAST real byte**:
```
bits[32:35]  route_num_type  -- values 0-6 ONLY (7 never observed)
bit[35]      paved           -- boolean, 94.56% of records (23,029/24,353)
```
Both crackings are validated by: exact bit-width match (sub-fields sum
to a whole byte with no slack), exact schema-order match, small/clean
bounded value ranges (not filling the sub-field's full range, consistent
with real bounded enums rather than noise), and real-world plausibility
(`divided`'s ~16% and `paved`'s ~95% are both realistic rates for a
European road network). Not independently confirmed against ground truth
— see the "eeu.rd cross-reference" note below.

**Bytes 1-3 (24 bits), all 15 remaining named fields, in exact schema
order throughout**:

- **CRACKED: `driveable_lower`/`drivable_upper` = byte 1, bits[0:2]**.
  Joint distribution across all 24,353 records: `(1,1)`=9,258, `(0,1)`=
  7,548, `(1,0)`=7,547, `(0,0)`=**0** — never both clear. Exactly
  matches real-world expectation for "drivable in the lower-numbered
  direction" / "drivable in the upper-numbered direction": a real road
  segment must be traversable in at least one direction, while
  bidirectional and the two single-direction cases are all real,
  distinct possibilities (and the near-identical one-direction counts
  fit "lower"/"upper" being an arbitrary node-order label, not a
  compass direction).
- **CRACKED (identity): `tollbooth_direction` = byte 1, bits[4:6]**.
  Joint distribution: `(0,0)`=23,729 (97.4%), `(1,0)`=314, `(0,1)`=310,
  `(1,1)`=**0** — mutually exclusive, both rare (~1.3% each). Matches a
  real "which direction requires toll payment" state (not a toll booth;
  tolled one way; tolled the other way — never both).
- **CRACKED (position, plausible identity): `restclass` = byte 2,
  bits[3:7]** (the 4 bits directly after byte 2's confirmed-always-zero
  bits[0:3]). All 16 of 16 possible 4-bit values are used across the
  file — a fully-saturated range, the cleanest possible signal for a
  tightly-packed enum with no wasted bit (stronger than the 5-bit
  interpretation tried first, only 30/32 values used).
- **CRACKED (position, later pass): the remaining 11 single-bit flags,
  assigned by exact schema order** — the same technique already
  validated for byte 0 and byte 4: eeu.mod lists exactly 11 more
  single-bit leaf fields after `restclass`, and exactly 11 real bits
  remain unassigned, in the same relative order:
  ```
  byte 1  bit[2]   toll_vignette      -- 11.62% (2,831/24,353)
  byte 1  bit[3]   toll_road          -- 14.72% (3,584/24,353)
  byte 1  bit[6]   hwy_complex_bit    --  2.66%   (647/24,353)
  byte 2  bit[7]   landmark           -- 10.84% (2,639/24,353)
  byte 3  bit[0]   dbldig             -- 24.19% (5,891/24,353)
  byte 3  bit[1]   detailedcity       -- 26.69% (6,499/24,353)
  byte 3  bit[2]   urban              -- 56.84% (13,842/24,353)
  byte 3  bit[3]   bifurcation_left   -- 46.69% (11,371/24,353)
  byte 3  bit[4]   bifurcation_right  --  3.75%   (914/24,353)
  byte 3  bit[5]   rnc                --  3.95%   (961/24,353)
  byte 3  bit[6]   truck_digitized    --  4.98% (1,212/24,353)
  ```
  `toll_vignette`/`toll_road` are schema-adjacent and land in the only 2
  bits available in byte 1's gap between `drivable_upper` and
  `tollbooth_direction`; `hwy_complex_bit` is the schema's next field
  after `tollbooth_direction` and lands on byte 1's only remaining real
  bit; `landmark` is the schema's next field after `restclass` and lands
  on byte 2's only remaining real bit; the final 7 fields (`dbldig`
  through `truck_digitized`) match byte 3's 7 real bits (bit[7]
  confirmed always zero) 1:1 in schema order with zero slack. Two
  independent signals beyond position: `rnc`/`truck_digitized` are
  **never both set** (joint `(0,0)`=22,180, `(0,1)`=1,212, `(1,0)`=961,
  `(1,1)`=**0**, the same clean exclusivity signature used for
  `tollbooth_direction`/`driveable_lower`\|`upper`), and
  `toll_vignette`/`toll_road` are almost always mutually exclusive
  (`(1,1)` only 37/24,353, 0.15%). The other 9 fields' individual
  semantics rest on position + schema-order + plausible value-rate only
  — the same standard already accepted for `rank`/`class`/`divided`.
  **Tested and refuted**: `dbldig` ("double digitized", the real Navteq
  term for a divided highway modeled as 2 separate carriageway
  geometries) was hypothesized to tightly track `divided` (byte 0 bit
  7) — joint distribution `(divided,dbldig)`: `(0,0)`=15,301, `(1,0)`=
  3,161, `(0,1)`=5,082, `(1,1)`=809 shows no such coupling; `dbldig` is
  a real, distinct field.

Full per-field byte tabulation and the `SegInfo` namedtuple:
`research/si_reader.py`.

**Corrects a previous session's lead**: §3.16 flagged `eeu.si` as "a
strong, not-yet-pursued lead" for `eeu.rd`'s own unresolved `bytes[1:5]`
(§3.1, "candidate road-class flags"). Originally checked against a since-
corrected "~5 distinct patterns" claim for `eeu.rd`'s own field (§3.1
now corrects this to 6,174 distinct values at full scale) — but even
with the correct cardinality, decoding `eeu.rd`'s `bytes[1]` using
`eeu.si`'s own exact `rank`/`class`/`divided` bit layout produces values
filling the FULL 0-7/0-15 range rather than `eeu.si`'s own bounded
0-4/0-12 ranges (and a 46.5% `divided`-equivalent rate vs. `eeu.si`'s
16.3%), and `eeu.rd`'s `bytes[1:5]` shows no correlation with
`eeu.iof`'s own `count` field either (§3.3, `r ≈ -0.02`).
**This specific cross-reference does not hold up.** More
likely: the real `seginfoID` foreign key lives on the MAP_COMPRESSED
tile format's own segment records (`eeu.mod`'s "Ordinary Map File" block
independently names a `seginfoID` field there, alongside `seg`/
`restr_left`/`restr_right`/`left_node`/`right_node`/`length`, §3.16),
not on `eeu.rd` at all — `eeu.rd` and the tile format are two separate
representations of the road network. Not pursued further this session
(would require reopening the tile format's own segment record parser).

### 3.21 `eeu.stt` — state/region catalog (79KB, NOT_COMPRESSED) — CRACKED and validated at full scale against real geography AND real cross-file content
94-byte header (record count 691 read straight from the header), then
exactly **691 fixed 114-byte records**. Every byte range was checked
across the whole file (not sampled) for "always zero" vs. real content,
giving an exact, unambiguous field layout:
```
uint16 LE  state_id    -- ascending 0-690, primary key
bytes[22]              -- always zero (691/691) -- eeu.mod's zoneID/
                          start_countyID/end_countyID/cover/bbox fields,
                          unpopulated -- the SAME pattern already found
                          in eeu.cny's own analogous region (§3.15)
bytes[36]  name        -- NUL-padded, in the parent country's own
                          language (matching eeu.ctr's own convention)
uint8      country_id  -- CRACKED, see below
bytes[53]              -- always zero (691/691) -- eeu.mod's
                          alpha_counties/countyID fields, unpopulated
```
This is the real "state" table `eeu.cny`'s own `state_id` field points
into (§3.15, §3.16) — closing a loop this project opened when `eeu.cny`
was first cracked.

**`name` — CRACKED**: real sub-national divisions, named in the parent
country's own language: `KRITI` (Crete, Greece), `GENÈVE`/`WALLIS`/
`TICINO` (3 real Swiss cantons, German/French as `eeu.ctr` itself uses
for that country), `VALLE D'AOSTA`/`PIEMONTE`/`LIGURIA` (3 real Italian
regions).

**`country_id` — CRACKED, validated exactly against all 691 records (zero
anomalies)**: a real foreign key into `eeu.ctr`'s own ROW ORDER (0-34) —
**not** `eeu.cal`'s alphabetical-by-ISO-rank numbering (§3.13). Brute-force
checked against `eeu.cal`'s scheme first and found no matching byte
offset at all; checked instead against `eeu.ctr`'s own literal row
position and found an exact match (row 0 = `SCHWEIZ`, row 2 = `ITALIA`,
row 13 = `ELLADA` — exactly the 3 initial test values). Extended to the
full file: every one of 691 records' `country_id` decodes to a real
`eeu.ctr` country, summing to exactly 691 with zero unmapped values.
Sanity-check counts per country are plausible (Vatican City=1, San
Marino=1, Liechtenstein=2 — microstates; Turkey=81 — many provinces),
with one unexplained outlier (Latvia=119, surprisingly high relative to
similarly-sized countries — not independently resolved). **This is now
the THIRD distinct country-numbering scheme confirmed on this disc**
(alongside `eeu.cal`'s alphabetical `country_id`, §3.13, and `eeu.cty`'s
own coarser per-country tag, §3.8) — every table that references a
country on this disc uses its own locally-consistent scheme, not one
shared space.

**Cross-validated against `eeu.cny`'s own `state_id` field — full set
equality, not just spot checks**: `eeu.cny`'s 691 distinct `state_id`
values are the exact same *set* as this file's own 691 `state_id` values
(both `{0, ..., 690}`, verified by direct set comparison). 3 individual
spot-checks, each independently correct: `CHANIA` (a real Cretan county)
has `state_id=0` → state 0 = `KRITI` (Crete), `country_id=13`=`ELLADA`
(Greece); `IMPERIA` (a real Ligurian province) has `state_id=39` → state
39 = `LIGURIA`, `country_id=2`=`ITALIA`; `SION` (a real Valais district)
has `state_id=4` → state 4 = `WALLIS`, `country_id=0`=`SCHWEIZ`
(Switzerland). All exactly right — `eeu.cny`'s `state_id` really is a
genuine foreign key into this real, independently-verifiable table, not
a guess.

### 3.22 `eeu.ti` — time-info / DST rule table (485 bytes, NOT_COMPRESSED) — CRACKED: a real DST/UTC-offset table, confirmed by exhaustive real-world geography (Russia's own 11 time zones)
94-byte header (record count 17 read straight from the header), then
exactly **17 fixed 23-byte records** — small enough to fully hand-inspect
in one pass.

```
uint16 LE  timeinfo_id  -- 1-13, CONFIRMED to match eeu.cny's own
                            timeinfo_id range exactly; NOT a per-record
                            primary key — multiple physical records can
                            share one value
uint16 LE  timezone     -- CRACKED (exact formula, see below):
                            utc_offset_hours = value/100 - 12
uint8      seqnr         -- a clean 0, 1, 2 sub-entry counter within one
                             timeinfo_id group
bytes[18]  ...           -- 14 more named fields (typeofentry,
                            startyear, monthorweek, flcount, startday,
                            starthour, startminute, durationnegative,
                            durationyears, durationmonths,
                            durationweeks, durationdays, durationhours,
                            durationminutes), byte POSITIONS assigned
                            (1 byte/field, 14 bytes used + 4 reserved),
                            exact real-world semantics of several
                            fields not independently confirmed — see
                            `research/ti_reader.py`
```

**`timezone` — CRACKED, CONFIRMED against real-world geography** (not an
opaque catalog index as first suspected): `utc_offset_hours =
timezone_field/100 - 12`. Validated **exhaustively** against Russia's
own real federal-district geography, which this disc's data happens to
span all 11 of Russia's real UTC offsets — `timeinfo_id=2` (Severo-
Zapadniy/NW district, Kaliningrad's zone) → `timezone=1400` → UTC+2,
real; `4` (Moscow Time, shared with Belarus/Turkey) → 1500 → UTC+3,
real; `5`→1600→UTC+4; `6`→1700→UTC+5 (Ural, Yekaterinburg); `7`→1800→
UTC+6; `8`→1900→UTC+7 (Novosibirsk/Krasnoyarsk); `9`→2000→UTC+8
(Irkutsk); `10`→2100→UTC+9 (Yakutsk); `11`→2200→UTC+10 (Vladivostok);
`12`→2300→UTC+11 (Magadan/Sakhalin); `13`→2400→UTC+12 (Kamchatka) — all
11 real Russian time zones, west to east, exactly right, zero
exceptions. Also confirmed for the 2 DST-observing zones: `timeinfo_id=
1` → 1300 → UTC+1, the real standard-time offset of Central European
Time; `timeinfo_id=3` → 1400 → UTC+2, real Eastern European Time.

**The id/country correspondence — CRACKED, via `eeu.cny` → `eeu.stt` →
`eeu.ctr`**: joining every county on the disc through its real state and
country reveals the WHOLE file's purpose at once. `timeinfo_id=1` (72%
of counties, the "rich" 3-entry group) is every real Central European
Time country on the disc (Germany, Italy, Poland, Switzerland, Austria,
Czechia, Slovakia, Hungary, the Balkans, Scandinavia, Vatican City, San
Marino, Liechtenstein). `timeinfo_id=3` (17%, also "rich") is every real
Eastern European Time country (Bulgaria, Estonia, Greece, Latvia,
Lithuania, Moldova, Romania, Finland, Ukraine). Every other id — each a
"simple", single-record group — is Russia (across its own 11 real time
zones) plus Belarus and Turkey (sharing `timeinfo_id=4`, Moscow Time).
**This is not a coincidence**: Russia permanently abolished DST in 2014,
Belarus does not observe DST, and Turkey abolished DST in 2016 (this
disc's own version strings date it to 2019) — exactly the 3
non-DST-observing country groups on the disc, and exactly the ids with
no detailed sub-schedule. The 2 DST-observing zones (CET, EET) are
exactly the 2 ids with a real 2-rule sub-schedule (`seqnr=0`/`seqnr=1`,
a real "spring forward"/"fall back" pair) plus a `seqnr=2` terminator;
every non-DST id has just 1 simple "no schedule" record.

**Grouping — CRACKED**: 17 physical records cover only 13 distinct
`timeinfo_id` values (`3 + 3 + 11×1 = 17`, exact). `timezone` is
constant within each group.

**Cross-validated EXACTLY against `eeu.cny`'s own `timeinfo_id`
distribution** (§3.15): `timeinfo_id=1` covers 1,674/2,326 counties
(72%), `timeinfo_id=3` covers 398/2,326 (17%) — together 89% of every
county on the disc, exactly matching which 2 ids carry real DST
sub-schedules here.

**Record shapes — byte positions assigned, not every field's exact
semantics confirmed**: the 14 named fields map 1:1 onto `bytes[5:19]`
in `eeu.mod`'s own field order, with `bytes[19:23]` always zero. "Real
entry" (4 records — both `seqnr=0`/`seqnr=1` records in each DST zone):
`typeofentry=121`; `startyear=77` (constant — plausibly a reference/
epoch year rather than a real calendar year, since an annually-recurring
rule doesn't need one); `monthorweek=108` (constant across BOTH DST
zones — consistent with CET and EET sharing the same real transition
CALENDAR DATE, last Sunday of March/October, differing only in local
clock hour); `starthour=3` (`seqnr=0`, "spring forward") or `10`
(`seqnr=1`, "fall back") — **not independently confirmed** to mean
literal local clock hour (the real EU-wide rule transitions at 01:00
UTC, and CET/EET should differ from each other by 1 local hour, but
both show `starthour=3` here — possibly UTC-referenced, or this byte's
position assignment is off by one field); `durationmonths` increases
monotonically across sub-entries (2, 3, 3, 4); `durationminutes=8`
constant. The "duration" fields' literal shape (~1 year, ~8 minutes)
doesn't obviously match a real 1-hour DST clock shift, so these may
encode a rule *validity window* rather than the shift amount — not
resolved. "Simple default" (11 singleton records): byte-for-byte
identical across all 11 (`typeofentry=121`, `startyear=77`,
`monthorweek=100` — different from the DST zones' 108, consistent with
"no real transition month" — everything else 0). "Terminator" (2
`seqnr=2` records): `typeofentry=42`, everything else 0.

Full methodology and the complete per-field byte tabulation:
`research/ti_reader.py`.

### 3.23 `eeuz.pca` — country/continent phoneme catalog (7.5KB decompressed, FLAT_COMPRESSED) — CRACKED (record framing, full file scale); 2 of 4 trailer fields decoded
Standard FLAT_COMPRESSED container (§3 intro). Same self-delimiting
record family as `eeuz.pct`/`eeuz.prd` (§3.5, §3.6):
```
uint8    name_len
bytes    name           -- name_len bytes, e.g. "EUROPE", "AUSTRIA"
uint8    phon_len
bytes    phon           -- phon_len bytes, same phonetic alphabet as eeuz.prd
bytes[16] trailer        -- see below
```
**Validated at FULL scale**: parsing the entire 7,451-byte body this way
consumes every byte with zero leftover at EOF, producing exactly **188**
well-formed records — previously only "decompresses to a clean phoneme/
name catalog" was known; content was never actually parsed.

`eeu.mod` (§3.16) names this table `phCatalog`, with 4 real per-record
fields after `graphem`(=name)/`phonem`(=phon): `clusterOffset`,
`clusterCount`, `cityOffset`, `cityCount` — read as 4 consecutive
uint32 LE values (16 bytes, matching the trailer width exactly).

**`clusterOffset`/`clusterCount` (first 8 bytes) — CRACKED (identity):
always zero on every one of the 188 records**, checked exhaustively.
Fully consistent with — and cross-validates — `eeu.pcl` ("phoneme
cluster list", §3.17) being confirmed genuinely empty on this disc:
there is no real phoneme-cluster data for this catalog to point into.

**`cityOffset`/`cityCount` (last 8 bytes) — position cracked, meaning
NOT cracked (target file not identified)**: a real, non-trivial value
pair, constant across every name-variant of one country (all 11
`AUSTRIA`/`AUTRICHE`/`OOSTENRIJK`/`RAKOUSKO`/... variants share
`cityOffset=14379305`/`cityCount=10712`), monotonically increasing in
file order as new countries appear — 20 distinct (offset, count) groups
across the 188 records, one per real country/continent entry. **Tested
against `eeu.cty`** (the obvious candidate given the field name):
neither a raw byte offset (lands on unrelated Hungarian content for
Austria) nor the reversed field assignment (lands on unrelated Greek
content) produces Austrian place names at the expected position — and
the "contiguous per-country block" model this would require doesn't fit
`eeu.cty`'s own real layout either: a full-file scan of `eeu.cty`'s own
`bytes[57:59]` country tag (§3.8) finds **441,325** tag-change
transitions across 939,351 records — the tag interleaves at fine
granularity (consistent with a spatial/tile ordering), not one
contiguous block per country as previously summarized. A direct byte-
offset test into `eeuz.pct` (city phonetics) — the next most plausible
candidate, by analogy with that file's own `phonemeRoadOffset` pointer
into `eeuz.prd` — also failed (lands on unrelated Turkish content).
`eeuz.cl`/`eeuz.ct` and `eeuz.fea` were not tested. Left open for a
future session.

### 3.24 `config/create_cd` and 5 disc-root subsystems outside `db/` — ALL 1,535 files on the disc now examined and documented; every distinct file FORMAT identified, most CRACKED, a handful of proprietary binaries identified-but-not-decoded
`config/create_cd` (5,105 bytes, plain text) is the disc's own
build/mastering script — the literal, authoritative record of how
`CD_8555.ISO` was assembled, not inferred or reverse-engineered.
Shell-like syntax (`mkdir`/`cd`/`cp`/`cp -r`), dated 22.07.2019 (matching
every file's real mtime on this disc), and self-referential — its own
last lines copy itself into `config/create_cd`. Full details:
`research/create_cd_reader.py`.

**Confirms the origin of the `EEU50530910.84` version string** every
NOT_COMPRESSED file's own 94-byte header carries (§3, §3.1): most `cp`
lines source from `v:\db\PRODUCTION\NT\VW\EU2019Q1\eu910\eeu\eeu\
505.30.910.1.84\...`, a real internal Navteq/Siemens production
file-server path. The correspondence is strong but not a trivial
dot-stripping match — see `create_cd_reader.py` for the exact digit-by-
digit comparison.

**Confirms `ZIP_3kb` is the source tree's own real folder name** for
every `eeuz.*` file's compressed variant — `block_size=3072` (§3.5) was
a deliberately named packaging choice at the source, not just an
empirically observed constant.

**2 root-level manifest files, CRACKED (plain text), tying every
subsystem's own version stamp together**: `cdrom.toc` (543 bytes) is a
real, human-readable manifest — `Version: 505.30.910.1.84` (an EXACT
match to `create_cd`'s own source path, closing that loop completely),
`TPD: 2019060000` (matches `tpd/nscWeu_eue_20190607/LPOI.TXT` and
`INFO25.PSC`'s own `TPD-PRODID` exactly), `SVD: EDB_20190607` (matches
`EDB/POI/POI.DB3`'s own `database.id` exactly), `TMC: 20190610`
(matches `telemat/`'s own source path date exactly), `DBAL: V006.047
V007.038 V008.704 V009.038 V010.015` (matches `dbal/`'s own 5 folder
names exactly), `Customer Info: VW`, `Customer: 1627386654`. `DBINFO.TXT`
is a real per-brand manifest: VW part number `1T0051859AR`, system name
`"EU East V17"`, and placeholder (`"tbd"`) Seat/Skoda/Bentley part
numbers — confirms this disc build serves the whole VW Group brand
family, matching `POI.DB3`'s own category split below.

**5 disc-root subsystems, ALL now examined** (alongside the already-
extensively-investigated `db/`):

- **`EDB/POI/POI.DB3`** — CRACKED: a real, standard SQLite database
  (open directly, no proprietary container). Confirms this project's
  own firmware investigation (§2.5), which had already predicted a
  `.db3` POI file at exactly this path from `vdo.nav.api.edb.*` strings
  but never had disc access to open one. **4,733,183 real POIs**, most
  with a full address (house number/street/city/region/country, each
  dedup'd through a shared 5,091,214-row string pool — the same pattern
  `eeuz.prl` uses). Real, immediately-recognizable content: fuel-brand
  POIs `Q8`/`ENI`/`TAMOIL`/`ESSO`/`IP` (all genuine European petroleum
  retailers) under a real `"gas station"` category. **Confirms this POI
  database is shared across the whole VW Group brand family**: real
  category names include `"main seat"`/`"main skoda"`/`"main vw"`/
  `"main bentley"`. One metadata row's own ClearCase config-spec text
  names the real internal codebase `arriba2`/`arriba2_VW` directly —
  independently corroborating `eeu.mod`'s own `Arriba`/`5.3` self-
  identification (§3.16) from the OTHER side (the tool that built this
  database, not just the firmware that reads it) — and a Java Swing
  authoring tool under the same `vdo/nav/...` package namespace already
  found in the firmware. **`PredefinedStatement` (35 rows) embeds real,
  readable SQL text behind a small bytecode prefix** (e.g.
  `GetFullPoiData`: `select b.Poi_ID, b.Coordinate, ... from
  Poi_BaseAttributes b left join Poi_AddressAttributes a on b.Poi_ID =
  a.Poi_ID ... where b.Poi_ID = ?1;`) — directly confirms, from the
  database's own side, this project's firmware-only finding (§2.5) that
  the real client only ever calls a fixed catalog of precompiled,
  parameterized statements, never arbitrary SQL. **`Coordinate` — CRACKED
  (a LATER session)**: a 64-bit integer, not this disc's usual
  `/100000`-scaled int32 lon/lat pair (splitting it into two int32
  halves, tested earlier, produces no plausible degree values) — but the
  originally-flagged leading candidate, "a Hilbert/Morton space-filling-
  curve index", turned out to be exactly right: reinterpret as unsigned
  64-bit, DEINTERLEAVE into two 32-bit values (even bits → longitude,
  odd bits → latitude), each scaled linearly from the full unsigned
  32-bit range to `[-180, 180)` degrees (latitude uses the SAME
  360-based scale as longitude, not the intuitive ±90 — it just never
  uses the top/bottom quarter of its own 32-bit range on a real disc).
  Found by joining `Poi_BaseAttributes` → `Poi_AddressAttributes` →
  `String_BaseAttributes` on a real city name (e.g. `'SOFIA'`) and
  noticing every one of that city's own `Coordinate` values shares an
  unmistakable high-bit prefix when printed unsigned — exactly a Morton
  code's spatial-locality signature. **Validated at 2 precision levels**:
  a broad 18-city sweep (Stockholm to Athens, Moscow to Zagreb) lands
  every city within a fraction of a degree of its real center; 2
  individually-known real landmarks found by NAME (Fiumicino/Rome's
  airport town, and a POI literally named `"R7 DOLGOSROCHNAYA PARKOVKA
  DOMODEDOVO"` — Domodedovo/Moscow airport's own long-term parking) both
  decode within **~0.01-0.03° (1-3km)** of their real published
  coordinates. **Confirmed at bulk scale**: 10,000 real POIs (2,000 each
  from 5 spread-out cities) decoded and checked against each city's own
  real, padded metro bbox — **9,988/10,000 (99.9%) land inside the
  correct real bbox**. `decode_coordinate()` in `research/poi_db_reader.py`
  implements this; not yet bit-exact to this disc's usual precision
  standard, but correct in shape, sign, and bulk placement. Full
  validation writeup: `research/poi_db_reader.py`.
- **`telemat/tmc2/`** — CRACKED (the config file, and the `.et` files'
  real content); the `.lt`/`.et` binary PACKING NOT fully decoded. Real,
  standard ALERT-C (ISO 14819) TMC traffic location tables for 14
  European countries, plus 19 per-language event-text tables.
  `TMCCONFIG.ini` is plain, self-documenting text — `PROD =
  "RNS_EU_38"`, and one line per country giving its real ALERT-C
  Country Code + Location Table Number, ISO 3166-1 alpha-2 code, and a
  real bounding box in plain decimal degrees (Germany:
  `5.877°E–15.0087°E, 47.387°N–55.017°N` — immediately verifiable as
  correct). **`lan/*.et` files confirmed to hold real TMC/ALERT-C
  phrase-fragment text**: `lan/english.et`'s body contains real English
  fragments ("Approach with care", "Queuing traffic for 1/2/3/4/6/10
  km", "Road closed", "Slippery roads", "Traffic flowing freely", real
  month/day names) — the standard phrase library RDS-TMC receivers use
  to reconstruct messages; a small header embeds the real source
  filename (`english.csv`) directly, confirming these are compiled from
  plain CSV. The exact string length/packing scheme was not decoded
  (extracted fragments are often missing their own leading 1-3
  characters, consistent with an un-decoded length-prefix byte). **A
  later session made a real attempt and hit a genuine wall**: the file
  splits cleanly into a 39-byte header, a 5,764-byte binary region, and
  a 7,397-byte NUL-free text blob (first real string: `"proach with
  care"`, i.e. `"Approach with care"` missing its own `"Ap"`). 2 clean
  hypotheses for the 5,764-byte region were tested and REFUTED with
  concrete evidence: a plain (offset,length) uint16 index table (only
  36% of values land inside the blob's own valid byte range, no visible
  sequential pattern) and a plain float32 array (motivated by a real,
  highly skewed byte distribution — `0x40` in 22% of header bytes,
  `0x00` in 21% — but only 36% of the reinterpreted floats land in a
  plausible range). The "missing leading characters" effect is real and
  precisely reproducible at the byte level (confirmed via hex dump, not
  a scan artifact): the same leading letter `A` is encoded 2 different
  ways in 2 adjacent entries (`August`'s own `A` is literal; `April`'s
  is replaced by a single non-ASCII byte) — real evidence of some kind
  of per-entry prefix/dictionary substitution whose exact scheme (a
  static shared prefix table? bit-level Huffman coding of just the
  first few characters?) wasn't identified. **A later session, from the
  FIRMWARE side**: the same firmware image (§2.6) embeds a real,
  complete `LanguageTable`/`TokenTable`/`NodeTokenEntity` subsystem
  (`SortTokenTable`, `FindLongestInTokenTable`, `AddTokenEntity`, a real
  `decode()` deserializer) — architecturally exactly the kind of
  longest-match dictionary tokenizer that would produce this "missing
  leading characters" pattern. Important caveat: its real source path is
  `naviservice/voicegeneral/SentenceAssembler.cpp` — the TURN-BY-TURN
  VOICE-GUIDANCE sentence assembler, a different (though `LanguageTable`
  does have its own `AddTmc`/`GetTmc`/`SetTmc` methods, so TMC content
  does flow through it when spoken aloud) resource from `.et`'s own raw
  phrase table. Upgrades this wall from "unknown scheme" to "very likely
  a dictionary/token-table scheme, real precedent exists in this exact
  code area" without closing it. Full details:
  `research/telemat_reader.py`. `.lt`
  files (real per-country binary ALERT-C location tables) were
  identified by convention and structurally examined (no clean small
  fixed-record width found, consistent with the real format's own
  variable-length record shapes) but not byte-level cracked. **This
  ground truth directly enabled cracking `eeu.tmc` itself in a later
  pass — see §3.25.** Full details: `research/telemat_reader.py`.
- **`speech/`** — CRACKED (identity + real embedded metadata); the
  actual voice-synthesis binary formats (proprietary, third-party) NOT
  decoded. `SpeechRes.xml` is a real, readable XML resource manifest
  covering 8 per-locale voice packs (`parts/uvo_*.zip`) and confirms
  real SPEECH RECOGNITION support (per-user `SpeakerProfiles/*.cfg`/
  `*.voc` file masks), not just TTS output. **The ZIPs confirm the real
  TTS engine vendor is SVOX** (a real commercial speech-synthesis
  company later acquired by Nuance/Cerence) — `svox.bin`'s own header is
  plain ASCII: `OS VxWorks PLANG 1 ... FILETYPE BIN MAJVERS 3` —
  **the first confirmation in this project of the actual embedded
  real-time OS** (VxWorks), previously only known as an unidentified
  PowerPC native-code region (§2.4). `SVOXKEYS.txt` is a real, dated
  license-key string: `P 10 6 2005 AS 3.0 Siemens_VDO CP2 9
  DABFSNIPC...` — confirms Siemens VDO licensed SVOX's engine on 10
  June 2005, tying this subsystem to the same corporate lineage already
  established from the firmware's `vdo.nav.*` namespace (§2.5) and
  `eeu.mod`/`POI.DB3`'s own `Arriba`/`arriba2` codebase identity.
  `vsi.img`'s own header is also plain text: real per-locale voice IDs
  (`enGBFemale`) and named sound events (`beep`, `navi_specific`,
  `tone_error`, `tone_sds_error`) alongside an `mp4`-tagged audio
  reference. The actual voice-model/phoneme-inventory binary payloads
  (`kj0ca0b16_0.pil`, `svox.bin`, `vsi.img`) are real, proprietary SVOX
  formats — not reverse-engineered. Full details:
  `research/speech_reader.py`.
- **`dbal/`** — CRACKED (container format + an enormous real internal
  source-file/class-name inventory extracted from embedded debug
  strings); not disassembled. All 5 `DBAL.OUT` files are confirmed
  32-bit big-endian PowerPC ELF **relocatable object files** (`ET_REL`,
  `EM_PPC`) — ties directly to the firmware's own already-known PowerPC
  native-code region (§2.4). A plain printable-ASCII-run scan (no ELF
  tooling needed) finds ~330 distinct real internal source paths under
  `J:\siemens\source\libraries\dbal\...`/`J:\siemens\source\navicore\
  ...`, matching this project's own already-cracked `db/` files by name
  almost one-to-one: `db_road.cpp`/`db_city.cpp`/`db_county.cpp`/
  `db_state.cpp`/`db_country.cpp` (→ `eeu.rd`/`.cty`/`.cny`/`.stt`/
  `.ctr`), `db_catalog.cpp`/`db_catalog_list.cpp` (→ `eeu.cat`/`.cal`),
  `db_timeinfo.cpp` (→ `eeu.ti`), `db_postalcode.cpp` (→ `eeu.pol`/
  `.pot`/`.pmm`/`.pmc`/`.pmp`), `db_phoneme_*.cpp` (→ `eeuz.pca`/`.pct`/
  `eeu.pcl`/`eeuz.prd`), `db_intersection*.cpp` (→ `eeu.il`/`.iof`),
  `db_tmc.cpp` + `db_tmc_deprecated.cpp` (→ `eeu.tmc`), `db_page.cpp`/
  `db_page_pcl_dir.cpp`/`db_kd.cpp` (→ the MAP_COMPRESSED/`eeuz.fea`
  "parcel"/kd-tree concepts §3.10's later-session lead already named),
  and `ZlibDecompressor.cpp` (→ this project's own empirically-cracked
  FLAT_COMPRESSED/MAP_COMPRESSED decompression logic). **A runtime log
  string independently confirms an already-established empirical
  finding from the source's own words**: `"db_page::update_pnext:
  element is already in the hash"` confirms `eeuz.fea`'s directory
  really is a hash table (§3.10), not spatial/sequential. **A real,
  dated ClearCase build history** names dozens of individual bug-fix
  branches, several directly relevant to open problems here (
  `alle_DbNavRbg3057_vw_split_mp0`, `alle_dbal_DbNavRbg3119_
  house_number_opt`, `alle_DbNavRbg2825_intersection_roundabout`,
  `alle_tmc_exit_fix`, and `lupa_dbal_DbNavRbg3501_RNS510_
  wrong_phoneme_Dummy_V10` — literally naming "RNS510"). **A later
  session, prompted by a direct re-check of this folder, diffed all 5
  versions' own embedded string sets against each other** (string counts
  grow monotonically 4208→4405→4600→4780→4802, real successive builds):
  a "first appears in version X" scan finds `db_postalcode.*` was ADDED
  in V007_038 (absent from V006_047's own baseline); V008_704 adds 36
  files in one jump, including a whole aspect/event/listener-proxy
  observer-pattern framework for display-language/voice-language/unit-
  of-measurement change notifications (`displaylanguagechangedaspect.h`
  etc.) plus a `mapjobqueue.h`/`maploader.h` job-queue abstraction, and
  the `CPhonemeEUHandler`/`CPhonemeNA*Handler` class family (see below);
  V009_038 adds 25 files, a real "navmedia" disc/media-management
  subsystem (coverage/vendor/version/part-number/"request copy
  database"/"select media"/"eject media", directly relevant to this
  disc's own `DBINFO.TXT`/`cdrom.toc` part-number metadata) plus
  `guidancejunctionviewinfo.h`, independently confirming `eeu.mod`'s own
  `intersection_view`/`junction_view` schema fields (§3.16) were a V009-
  era addition; V010_015 adds exactly 1 file,
  `routepath_coordhashtable.h`, a coordinate-keyed hash table over
  route-path segments (found alongside 2 real error strings,
  `"itemsEqual(), headPosition/tailPosition, getNodePosition failed!"` —
  not yet linked to any specific on-disc table). **A full V010_015-vs-
  V006_047 file diff found 65 additions and 11 REMOVALS — all 11 belong
  to one real "generic corridor" subsystem** (`corridorbackend.h`,
  `corridorcatalogstorage.h`, `corridorhelpers.h`, `corridormp0storage.h`,
  etc, source path `K:\siemens\...\genericcorridor\...`), present in
  BOTH V006_047 and V007_038 and gone from V008_704 onward — removed at
  exactly the same release boundary the aspect/event framework was
  added at. Real runtime strings (`"Unsupported request in corridor mode
  (dir=%d, catID=%d, count=%d)!"`, `"MP0Storage:constructor:
  oslib_MutexCreate failed"`) confirm it was a real working feature, not
  dead code; `corridormp0storage.h` directly referencing `eeuz.mp0`
  suggests it was a route-corridor predictive tile-prefetch cache, later
  removed/replaced. **The V008_704 phoneme classes are a real, dated
  EU/North-America architectural split**, confirmed via mangled C++
  symbols naming an actual `dbal::phonemes::` namespace
  (`Q34dbal8phonemes17CPhonemeEUHandler`) — `CPhonemeEUHandler` (this
  disc's own family) reads `eeuz.pca`/`.pct`/`.prd`/`eeu.pcl` directly,
  while `CPhonemeNAFileReaderHandler`/`CPhonemeNAFlashHandler`/
  `CPhonemeNAFlashFile` use a completely different "flash file"
  (`loadPhonemeFileFlashMemory`) code path — strong evidence the
  phoneme *data format itself*, not just the handler class, differs
  between EU discs like this one and the (never-seen here) North
  American disc family. Full details: `research/dbal_reader.py`.
- **`tpd/`** (1,443 files, by far the largest disc-root area) —
  CRACKED at the system level (every distinct file role identified and
  confirmed with real content); the per-country compressed search-table
  BODIES not decoded. `nscWeu_eue_20190607/INFO25.PSC` is a real,
  self-documenting config file (`TPD-PRODID 2019060000`, `TPD-CNTRY`
  listing the same 33 countries already found via `eeu.cal`/`eeu.ctr`,
  `LPOIPRO Y`). **Confirmed to be a real embedded HTML "browser"
  destination-search UI**: each of 8 per-language folders holds an
  IDENTICAL 122-file set (verified by hash) of real HTML forms
  submitting to `http://tpdhost/cgi/search`/`StartTPD` — the head unit
  runs (or emulates) a local embedded web server with a CGI-style
  handler. `SF_<FORMID>.HTM` (search-criteria forms, e.g. `SF_11000
  .HTM` = "Airports", radius + name filters) and `ST_<FORMID>.HTM`
  (results pages, with `<%if_result>`/`<%INDEX_FIRST>`-style template
  substitution) reference real per-form search index tables under
  `TABLES/0/<NNNN>.IDX` + `.URL`, whose own header is plain,
  self-documenting text (`compr-type=Z`, a real named+typed schema
  `ID:A:6|POS:P:8|NAME:V:84|LKI:B:1|PHONE:V:19|IMPORTANCE:B` — the same
  ID+position+name+phone shape as `POI.DB3`'s own `Poi_BaseAttributes`).
  **A later session cracked the structure right after that header,
  previously assumed to just be part of "the compressed body"**: a real
  per-block `(offset, lambda_hash)` index table — repeating 9-byte
  records (`[4-byte BE uint32][4-byte BE uint32]['|' delimiter]`), BOTH
  fields strictly monotonically increasing across every record, on both
  a small per-form `.IDX` (30 records) and the much larger merged
  `TABLES/GENERIC.IDX` (136.9MB, 92,006 records, same shape at a larger
  scale) — exactly the structure `order-type=lambda` implies: a sorted
  hash-boundary table enabling binary search for which single compressed
  block a query's own lambda hash falls into, without decompressing
  every block. **Tested and REFUTED**: the compressed block BODIES
  themselves are not standard zlib (RFC1950), raw DEFLATE (RFC1951),
  gzip, or bz2 — exhaustively scanned at every byte position in a small,
  fully-scanned `.IDX` file, zero real hits in any of these formats
  despite the file's own `compr-type=Z` label — a real but still
  unidentified proprietary encoding. **A later session, prompted by a
  direct re-check of this whole folder's contents, found a 2nd real
  embedded CGI host and the actual "navigate here" action**:
  `ST_DETAIL.HTM` (1 per language, real content identical except the
  `LAN` tag/translated text) is the single POI-detail screen shown after
  picking a result — and it's the only file anywhere in `tpd/`
  referencing `ctrlhost` (distinct from `tpdhost`, which only ever
  handles `cgi/search`/`cgi/form`/`cgi/StartTPD`, the DATA-fetching
  endpoints). `ctrlhost` handles 3 CONTROL/ACTION endpoints instead:
  `cgi/menu?option=tpd_prev_page` ("back"), `cgi/phone?NR=...`
  (click-to-call), and — the real payoff —
  `cgi/setdest?NAME=...&PHONE=...&LOC=...&ENTRY=...` (up to 9 real
  `ENTRY` parameters, plausibly one per usable building entrance) — the
  concrete "set this POI as my destination" action §2.5's firmware
  investigation had only inferred existed, now with its real endpoint
  and parameter shape. **Also corrected 2 stale file-count claims found
  while investigating this**: exactly 59 real numbered `SF_<FORMID>.HTM`
  search forms per language (not 60) with a byte-exact matching 59
  numbered `TABLES/0/<NNNN>.IDX` files (also not 60 — that count was
  actually this directory's `ST_*.HTM` total, 59 numbered +
  `ST_DETAIL.HTM`). `<LAN>.LSC` files are
  plain, self-documenting text naming a real category-group hierarchy
  (`TPD-GRP <group-id> <child ids>`) feeding the category picker;
  `ICONS`/`ICONS810` (381 real PNG files, self-explanatory POI-category
  names like `AIRPORT`/`ALL_RESTAURANTS`/`ATM_EUR`) and `IMAGES` (22
  GIF UI-chrome files) round out the system. **A later session opened
  the one previously-unopened file, `tpd/TPD3.DIC`** — despite the
  `.DIC` extension, NOT a binary word dictionary: 60 bytes of plain
  text, a 3rd disc-root-level product manifest one directory above
  `INFO25.PSC`/`LPOI.TXT` (`TPD-DBID 2019060000`, the same build stamp
  now confirmed a 4th independent way; `TPD-UPI eue_0 25
  /nscWeu_eue_20190607 D` names the one real product instance —
  `eue_0`, the real path, and a trailing `D` flag, plausibly
  "Directory"/"Data". The middle field `25` doesn't match `TPD-CNTRY`'s
  33 countries, `TPD-LAN`'s 8 languages, or any individual language
  code — real, unexplained). Full details: `research/tpd_reader.py`.

### 3.25 `eeu.tmc` — TMC traffic-data file (25.8MB, NOT_COMPRESSED) — CRACKED: the file's own top-level directory AND the complete per-location byte-offset index (100% of the file's own addressing structure) validated at full scale; only the deepest leaf chain records' own content remains undecoded
The last "genuinely unexplored" NOT_COMPRESSED file on the disc,
cracked using ground truth found via `config/create_cd` (§3.24):
`telemat/tmc2/TMCCONFIG.ini` confirmed this disc's real ALERT-C/TMC
conventions, and `dbal/`'s own embedded source-file list independently
confirms the real handler is named `db_tmc.cpp` (plus a
`db_tmc_deprecated.cpp` twin — **CORRECTED, a later session**: a 5-
version diff of every `dbal/V0*/DBAL.OUT` found both files coexist in
ALL 5 DBAL versions, refuting the earlier guess that the on-disc TMC
format changed between DBAL releases; `_deprecated` more likely means a
legacy/alternate encoding kept for backward compatibility, §3.24-
adjacent `dbal/` bullet).

`eeu.mod` names this table `"tmc file"` (74 raw strings, §3.16) — after
the usual boilerplate, a `tmc_file_header` (`no_of_location_tables`,
`max_segment_chain_len`, `max_location_size`, then an array of
`location_table_header`s: `name`/`start_location`/`no_of_locations`/
`offset_of_location_offset_table_p`/`offset_of_location_offset_table_n`)
followed by a much deeper nested payload (`location_offset_tables` →
`location_chains` → `segment_chains` → `exception`/`exploration_points`).

**CRACKED, validated at full scale: the file header + 44-table
directory**:
```
uint16 LE  no_of_location_tables  -- 44, exactly matching the number
                                      of directory records that follow
uint16 LE  ???                    -- 1716; position matches
                                      max_segment_chain_len, value not
                                      independently confirmed
uint16 LE  ???                    -- 240; position matches
                                      max_location_size, not confirmed
44 x 20-byte location_table_header records:
    bytes[4]   code         -- 3-char alphanumeric + NUL (e.g. "117",
                                "225", "A01", "F49") -- confirmed
                                exactly 3 characters + NUL on all
                                44/44 records
    uint32 LE  start_location?    -- position matches, not confirmed
    uint32 LE  no_of_locations?   -- position matches, not confirmed
    uint32 LE  offset_p           -- CRACKED (identity), see below
    uint32 LE  offset_n           -- CRACKED (identity), see below
```
**Validated**: the 44-record count exactly matches the header's own
`no_of_location_tables` field. `offset_p`/`offset_n` are monotonically
increasing across all 44 records (980, 105460, 209940, 452364, 838444,
..., up to 8,482,780) with `offset_n > offset_p` on every record, and
each record's own `offset_p` at or past the previous record's
`offset_n` — exactly the shape real, sequentially-allocated byte
offsets into a shared payload would have, matching `eeu.mod`'s own
field names by position exactly. Spot-checked: the bytes AT both
`offset_p[0]`=980 and `offset_n[0]`=105460 are themselves further
small, regular, non-random binary structure, not garbage/misalignment.
A real, unexplained sub-pattern: 4 consecutive tables (codes `714`-
`717`) share the exact same `start_location?` value (10001) — plausibly
sub-divisions of one larger region.

**The 44 codes are NOT the same identifier convention `telemat/tmc2/
TMCCONFIG.ini`'s own 14 Western-European countries use** (hex Country
Code + decimal LTN) — this disc's own 44 tables are a real, distinct
catalog, plausibly covering the "eeu" (East Europe) dataset's own wider
country/region footprint. Not matched against external ground truth.

**A LATER SESSION: the COMPLETE per-location byte-offset index CRACKED,
validated at 100% scale, zero exceptions across all 44 tables.** Each
table's own `offset_p` doesn't point at a single struct — it's the
start of a flat array, `eeu.mod`'s own `location_offset_table_p`. Its
element count is exactly `no_of_locations + 1` (the classic prefix-sum/
CSR shape), confirmed EXACTLY on all 44/44 tables with zero exceptions:
`(offset_n - offset_p) / (no_of_locations + 1) == 4` every time — i.e.
`location_offset_table_p` is `no_of_locations + 1` little-endian
**uint32 absolute file byte offsets**, monotonically non-decreasing on
every table (confirmed, zero exceptions): location *i*'s own data spans
`[table_p[i], table_p[i+1])`.

`location_offset_table_n` (the mirror "negative direction" array)
immediately follows `location_offset_table_p`, starting at `offset_n`
and using the IDENTICAL `(no_of_locations + 1) × 4`-byte size — confirmed
EXACTLY on all 43/43 consecutive table pairs:
`next_table.offset_p − this_table.offset_n == (no_of_locations + 1) × 4`.

**The whole file is now fully self-consistent end to end**: the LAST
table's (`F49`) own `location_offset_table_n` — unbounded by a "next"
directory record — computes to end at exactly byte **8,584,500**, and
separately the FIRST table's (`117`) own `location_offset_table_p[0]`
value is ALSO exactly **8,584,500** — 2 independent computations
agreeing to the byte. The LAST value of the LAST table's `location_
offset_table_n` equals **25,814,096** — the file's own exact total size
(EOF), also to the byte. Every offset for every one of the 44 tables
falls within the file's real bounds, and both arrays are monotonic on
every table — no exceptions found anywhere.

**Practical consequence**: byte 94 (end of the SIEMENS header) to EOF is
now fully mapped — the 6-byte header, the 880-byte 44-record directory,
44 back-to-back `[location_offset_table_p][location_offset_table_n]`
pairs (886 to 8,584,500), then one shared **"location_chains" bulk
region** (8,584,500 to EOF, 17,229,596 bytes, 66.75% of the file) all 44
tables' own arrays point into. Given any `(table_code, location_index)`,
that location's exact byte range in BOTH ALERT-C directions is now
directly computable, with zero guessing.

**CRACKED (further, same later session): `chain_count` = byte 0's low
nibble, and each `segment_chain` has a fixed 7-byte MINIMUM footprint —
confirmed by an EXACT integer formula.** Grouping every non-empty
location record by byte 0's low nibble and looking at each group's own
minimum record size: `min_size == 1 + low_nibble × 7` holds EXACTLY for
low_nibble 1 (n=724,059, min=8), 2 (n=493,817, min=15), 3 (n=691,
min=22), 4 (n=83, min=29), and 6 (n=8, min=43) — the one exception
tested, low_nibble=5 (n=29, min=37 vs. predicted 36), is plausibly just
a sampling gap in a 29-record group, not a contradiction. This confirms
byte 0's low nibble really is `chain_count` (matching `eeu.mod`'s field
name and position exactly), a fixed 1-byte record header, and a 7-byte
minimum per `segment_chain` (reached at 0 `exploration_points`) — mean
record size also grows roughly linearly with `chain_count` (10.4, 19.5,
28.8, 39.4, 50.8, 57.5 bytes for low_nibble 1-6).

**Byte-level characterization (statistical, not bit-pinned) of the
minimal 7-byte `segment_chain`**, from the FULL, true-scale
`chain_count=1`, exactly-8-byte-total subset (310,888 records, all 44
tables, both directions — an earlier pass of this same analysis this
session used an accidentally truncated ~26,220-record sample from only
the first few tables and wrongly reported byte 4 as "mostly constant"
and byte 6 as "always 0"; both corrected below at true full scale):
byte 0 has only 2 distinct values (1, 17 — low nibble=`chain_count`,
bit 4 a 2nd flag set on 72.1% of records); bytes 1-4 are all high-entropy
(candidate: `start`/`vseg_id`, byte 4's own bit 7 a real ~50/50 flag,
candidate `side`). **Tested and REFUTED (a later session), 2 more
hypotheses for bytes[1:4]**: as a plain within-table location index
(`r ≈ 0.012` against the real index, essentially zero correlation), and
as a cross-reference (big-endian, matching the directory's own
convention) to another location's own offset-table boundary elsewhere
in the file (only 2.86% of 74,848 real records land on one of the
1,218,695 real boundary offsets across all 44 tables — below the ~7%
rate pure chance alone would predict given that set's own density,
i.e. coincidental collisions, not a signal). bytes[1:4]'s real meaning
remains open. byte 5 is power-law distributed, 78.6% == 1 (robust
at full scale, matches real-world `no_of_segments` — most chains cover
exactly 1 segment); byte 6 is 99.955% == 0 but has a real, rare
(325/724,059) nonzero signal (values 1-4) that correlates STRONGLY and
MONOTONICALLY with extra record length (mean extra bytes 2.41/41.88/
75.00/75.00/225.00 for byte6=0/1/2/3/4) — consistent with a real
internal-chain- or exploration-point-related count that's simply almost
always 0, not refuted as originally thought.

None of this reaches the same standard as this disc's fully bit-pinned
fields elsewhere (e.g. `eeu.si`'s `rank`/`class`/`divided`) — it's a
real, statistically strong characterization of the outer shape, not an
individually-confirmed bit-level layout. Full methodology and reusable
functions (`read_location_offset_arrays()`, `location_byte_range()`,
`read_location_chain_bytes()`, `chain_count()`): `research/tmc_reader.py`.

### 3.26 `db/zone.cfg` (81 bytes, plain text) — IDENTIFIED: the very last file on the disc this project had never actually opened
The whole file is one line: `eeu = 10.1/DB 01234 18408555
44444444444444434441111444444444214114442222444444`. `eeu` matches the
disc's own dataset name; `18408555` ends in `8555` — this reference
disc's own volume number (`CD_8555`, matching `cdrom.toc`'s own
`Volume: CD_8555` line, §3.24) — consistent with a disc-specific (not
dataset-generic) config value. `10.1/DB` and `01234` weren't matched
against anything else found this session. The trailing 50-character
digit string is mostly `4` (37/50, 74%) with a handful of `1`/`2`/`3`
values — 50 doesn't match this project's own per-country (35) or
per-timeinfo (13) counts exactly, so it isn't a direct 1:1 list under
either existing counting, though the overall shape (one dominant value,
several rare minorities) is qualitatively similar to `eeu.ti`'s own
`timeinfo_id` distribution (§3.22). Not decoded further. Full details:
`research/zone_reader.py`.

**With this, every file on `CD_8555` — all 1,535 of them across `db/`
and the 5 disc-root subsystems — has been examined at least once.**

---

## 4. ISO container handling

`CD_8555.ISO` is a **UDF + ISO9660 "bridge" disc** (2048-byte sectors, standard for
DVD data discs of this era). Its UDF layer is **broken in the original retail image**
(not something introduced by editing) — the root directory's File Identifier
Descriptors fail ECMA-167 validation, though the surrounding UDF structures (anchor
volume descriptors, partition/logical volume descriptors, file set descriptor) all
parse correctly. Real hardware and Windows Explorer both read this disc via its
ISO9660 tree, not UDF — UDF is vestigial on this disc family.

**`research/` was copied out of the reverse-engineering scratchpad for permanence, but
the actual ISO read/write module used by the GUI tool lives next to it:**
`rns510_iso.py` (project root) — `open_tolerant(path)` opens the ISO with `pycdlib`,
tolerating the broken UDF tree (a monkeypatch treats the first unparsable File
Identifier Descriptor as end-of-directory padding instead of raising); `strip_udf(iso)`
removes UDF state before writing, producing a clean, standard ISO9660-only image.
Round-trip verified byte-for-byte (SHA256 match) on the 590MB `eeu.rd` file when
unmodified; full 6.48GB open+write takes ~11 seconds. **No checksum, hash, or signing
mechanism exists anywhere on the disc** — the official disc-mastering script
(`config/create_cd`) is just `mkdir`/`cp` commands. The only real risk from editing is
internal data-consistency (record counts, cross-reference indices), not any
copy-protection gate.

pycdlib gotcha: use `update_file_contents_fp(fp, length, iso_path=...)` (pycdlib 1.20+)
to replace a file's content with a different size — no need for a remove+re-add dance.

---

## 5. SD card deployment

The RNS510 doesn't read a map ISO directly from an SD card — a separate, existing,
**already-verified community tool** handles that: `maps-tool 2.0.2`
(`C:\Users\krcenov\Desktop\maps-tool 2.0.2\maps-tool-2.0.2.exe`, GPL/Apache-2.0 licensed
Java GUI app, not written by us). Decompiled and tested (headlessly, via its own
extracted classes) directly against `CD_8555.ISO`:

- **Works unpatched**, despite our disc (V17, 2019) being newer than anything in its
  documentation (which only lists up to V12/2014) — that's a stale help file, not an
  actual code restriction. The only real validation gate is a region-code check
  (`EEU`/`EU`/`AUNZ`/`NA`), which our disc passes.
- It builds a `MAPS`/`MAPSDVD` folder structure via a straight recursive byte-copy from
  the ISO (a few hardcoded filename-typo fixes for old disc versions, none of which
  trigger on ours), plus a **static, version-independent** `sd_to_hdd_fw.iso` bootstrap
  disc (bundled inside the tool itself, doesn't need to be built per map version).
- Real-world procedure (from the tool's own help.html): prepare an 8GB+ FAT32 SD card
  with `MAPS`/`MAPSDVD`/`test.mp3`, burn `sd_to_hdd_fw.iso` to a blank DVD+R (slow
  speed, Track-at-Once), then on the unit: insert SD card (confirm `test.mp3` plays),
  enter Software Upgrade Mode (SETUP + EJECT + MIC/INFO buttons), insert the firmware
  DVD, confirm the prompt, wait ~30 min while it copies SD → internal HDD.

**Our tool's job stops at producing an edited ISO.** Run `maps-tool` separately on that
output to prepare the actual SD card.

---

## 6. The map editor GUI tool

Location: `rns510_gui.py` (GUI), `rns510_core.py` (all format/business logic, no GUI
code), `rns510_iso.py` (ISO read/write helper), `test_core.py` (non-GUI functional
test), all in this folder.

**Run it:**
```
py rns510_gui.py
```
(On this machine, use the `py` launcher — plain `python`/`python3` aren't on PATH.)

**Features:**
- **Open Map ISO** — loads via `rns510_iso.py`, extracts just `db/eeu.rd`, `db/eeu.il`,
  `db/eeu.iof` to local temp files (never holds the full multi-GB ISO in memory).
- **Search roads by name** — scans `eeu.il`'s name index (fast, capped result display).
- **Edit an existing road** — change name and/or nudge coordinates; patches the record
  in place, preserving all unresolved bytes unchanged. Best-effort keeps `.il` in sync.
- **Add a new road** — form for name + lat/lon; appends a new `.rd` record (unknown
  bytes zero-filled), a best-effort `.il` entry, and a default `.iof` entry. **Marked
  EXPERIMENTAL in the UI with a warning and confirmation dialog** — it does not touch
  `.rt`/`.rl`, city/county tables, or the `.mg1`-`.mg4` rendering tiles, so a new road
  may be searchable in-tool but not necessarily visible or routable on real hardware
  (see Open Problems).
- **Save As new ISO** — never overwrites the original; writes edits back via
  `rns510_iso.py`, then automatically reopens the new file and verifies the edits read
  back byte-exact before reporting success.

**Tested against the real `CD_8555.ISO`** (not just written and assumed to work):
search returned real matches, an existing road was renamed and the change verified,
a new test road was appended and verified, and a full save-as + round-trip readback
passed, including a full 1,535-file diff confirming everything untouched matches the
original exactly.

---

## 7. What's solid vs. experimental (read this before editing your real map)

| Capability | Status |
|---|---|
| Open/parse the map ISO | Solid, verified |
| Search roads by name | Solid, verified |
| Rename an existing road / move its coordinates | Solid, verified — preserves all unknown fields |
| Add a brand-new road (data-only) | Works, but experimental — see below |
| New road appears in name search | Works |
| New road renders on the map display | **Not yet tested on real hardware** — tile geometry format (per-feature anchor+delta blocks) is readable/writable, and the per-vertex topology/adjacency table's node-id mapping is now also cracked (§3.6/§8 item 5, `resolve_topology_adjacency()`), so a topology entry consistent with a new road's own vertices can be synthesized in principle; whether real hardware actually needs one (and whether this understanding is complete enough to satisfy it) is unverified — nothing has been write-tested on-device |
| New road is routable | **Unverified** — `.rt`/`.rl`/city-county wiring not done; `.rl`/`.prl` are now decoded (§3.7) but not yet used by the GUI tool, and may back the unit's own address-search UI (unconfirmed) |
| Rebuild a valid ISO | Solid, verified byte-for-byte |
| Prepare SD card from the ISO | Solid — via the separate `maps-tool` |
| Real hardware acceptance | **Not yet tested** — recommended next real-world step is a *zero-edit* round-trip test (rebuild the ISO unmodified, deploy via `maps-tool`, confirm the unit loads it normally) before trusting any real edits |

---

## 8. Open problems / next steps

1. **Continental's own geo-index prefix region** in `.mp0`/`.mg1`-`.mg4`
   (byte 80 → `table_start`) — still not cracked, but **no longer a practical
   blocker**: every tile carries its own absolute anchor coordinate (see §3.6), so
   `build_geo_index()` + `find_tile_for_coord()` now give a working, validated
   coordinate→tile lookup for mg2/mg3/mg4/mp0 without needing this region at all. Only
   worth revisiting if the nearest-anchor approximation (see gap below) proves too
   imprecise in practice.
2. ~~`mp0` geo-index coverage~~ **SOLVED** — full-file run, 194,650/194,705 tiles
   (99.97%), ~55s; see §3.6 for the structural fix (`_looks_like_real_chain()`
   verification, needed because `mp0`'s sub-index is dense rather than sparse).
3. **True tile bounding boxes** — `find_tile_for_coord()` currently does
   nearest-anchor matching, not exact containment, since no tile extent/size was
   recovered (the still-undecoded `0x02-0x17` per-tile header is the likely home for
   this). A coordinate near a tile boundary might resolve to the wrong neighboring
   tile as a result.
4. **`eeuz.fea`'s directory and per-record coordinates** — see §3.10 for this
   session's full findings (reusable module `research/feature_reader.py`).
   Headline result: `.fea` is CRACKED at the "what is it" level — a
   multi-language named-place gazetteer (cities, seas, islands, road-shield
   labels), concretely cross-referenced (a 7-language name-table entry
   decodes to real historical exonyms of Iași, Romania, a place this
   project has independently validated multiple times before). Still open:
   the directory region (confirmed this session to be a uniform grid of
   977,308 fixed 12-byte records + an 8-byte trailer spanning the whole
   ~11.7MB region at byte 80 — more specific than previously known, but
   field-level meaning not cracked; ALSO found this session: the identical
   12-byte-record format recurs at least once more DIRECTLY IN THE
   PAYLOAD, at file offset 306,299,567-311,300,723, exactly 416,763 more
   records — i.e. the file has multiple embedded directory/section
   boundaries, not just one at the front, which is why the first full-file
   enumeration attempt silently stopped at 55% before this was found and
   fixed with an escalating-window retry) and per-record coordinate
   encoding (no absolute
   lon/lat field found inside a decompressed entry despite the same
   search technique working on MAP_COMPRESSED — coordinates are either
   relative to an anchor stored elsewhere, or named records reference
   position by an external id, e.g. into `eeu.cty`, instead of storing it
   directly). **UPDATE (later session): the "external id into `eeu.cty`"
   idea was tested directly and REFUTED** — 6 independent real cities
   (Iași=349791, Turku=403630, Bratislava=182482, Trondheim=389671,
   Oslo=384186, Nisyros=238217, all verified unique `eeu.cty` self-indices)
   each had their `.fea` name entry exhaustively scanned for that exact
   index (1/2/3/4-byte, signed/unsigned, LE/BE) plus its `.cty` byte-offset
   and several arithmetic transforms, and separately for `eeuz.cl`'s own
   record position — **0/6 hits in every case**, including a 586-byte,
   near-zero-noise entry (Nisyros) where a false negative from search-space
   noise is implausible. A `.fea` name record does not embed a literal,
   scannable `eeu.cty`/`eeuz.cl` join key — this lead is now closed, not
   open; see §3.10's dedicated write-up and `feature_reader.py`'s
   docstring for the full method and remaining candidate leads (a hashed
   name key, or the still-uncracked directory region itself holding the
   join). Practical fallback validated this session: brute-force
   `enumerate_entries()` (handles the format's intermittent non-zlib gaps
   between compressed entries) + `scan_names()` (extracts a record's
   multi-language name table) together give a working, validated way to
   enumerate and approximately geolocate `.fea` content by name, without a
   byte-level directory crack.
   **UPDATE (later session): directory record format CRACKED (an
   `(offset, declen, complen)` big-endian index triple — see §3.10's
   dedicated write-up); coordinate attachment tested at per-section and
   per-sub-tile-record granularity and REFUTED at both, joining the
   already-refuted per-record-embedded and `.cty`/`.cl`-join hypotheses.**
   Three independent, rigorously-tested coordinate-attachment hypotheses
   have now all failed at this project's usual evidentiary standard —
   recommend treating `.fea` per-record/per-section geolocation as not
   worth further pursuit for now; `scan_names()` + `eeu.cty` cross-reference
   remains the practical path, and is already sufficient for this project's
   actual needs (search, content inventory). The directory-format crack
   itself is a genuine, separate, reusable win (`decode_directory_table()`,
   `verify_index_triple()`, `find_index_record_for_offset()` in
   `research/feature_reader.py`) even though it doesn't solve geolocation.
5. ~~Intra-tile feature/topology delimiting~~ **Feature/polyline delimiting SOLVED**
   (see §3.6, `decode_features()`) — a tile's coordinate region is a sequence of
   self-delimiting `[point_count][anchor][deltas]` blocks, validated against 28+
   tiles with 2+ independently-matched named roads each (re-measured after the
   fix below; was 20+). ~~⚠ Caveat found: threshold bug~~ **FIXED**:
   `decode_features()` previously had a magnitude-threshold bug that could
   silently mis-split tiles with legitimately large shape-point gaps (confirmed
   on the section's own canonical 2-feature example) — replaced with a
   distinct-value/repetition discriminator and re-validated at full scale
   (mg4 + mp0 `build_geo_index()` coverage unchanged, mp0 named-road hit rate
   improved) — see §3.6 for the full writeup and numbers.
   **⚠ Second bug found: "oscillating overrun" — root-caused, detector
   REDESIGNED this session, still OPT-IN only, not a default-safe fix.**
   A block's declared `point_count` can run past where its real geometry
   actually ends and into some other still-unidentified fixed-stride
   binary structure, producing decoded "vertices" that ping-pong 24-33km
   between two near-fixed positions (found while rendering a real `mg3`
   tile near Sofia, Bulgaria — see §3.6 and §10). Confirmed NOT an
   instance of the legitimate-chaining pattern above (zero `eeu.rd`
   matches at any of 8 checked jump endpoints). The original single-
   cutoff discriminator (`_find_oscillation_cutoff()`, truncate-
   everything-after-the-first-cluster) dropped the established 80-tile
   hit-count from 28/80 to 17/80 when applied unconditionally, because
   it discarded real geometry AFTER a flagged cluster along with the
   cluster itself. **This session**, direct testing against 4 more
   confirmed-bad tiles near Turin, Italy found two concrete gaps in that
   design (only the first cluster was ever found; reassembly was pure
   truncation) and fixed both: `_find_oscillation_clusters()` now scans
   the WHOLE delta sequence for every cluster, and `decode_features()`
   SPLITS a block into surviving sub-features around each one instead of
   truncating. Re-validated at the same 80-tile scale: **42/80** (an
   outright improvement over the untrimmed 28/80 baseline, with only 1
   tile regressing) — see §3.6 for the full numbers. One of the 4 new
   confirmed-bad tiles (tile_id 1330) remains an open gap: its corruption
   is numerically indistinguishable, at the single-event level, from
   legitimate widely-spaced real jumps in the canonical Iasi reference
   tile, so it is deliberately left uncaught rather than risk the Iasi
   guarantee. Still ships as `decode_features(..., trim_oscillation=True)`,
   opt-in only, used by the map viewer for display purposes but explicitly
   NOT the default and NOT safe for editing/round-tripping use: the
   per-cluster real/fake classification problem is now proven (not just
   suspected) unsolvable from tile-local statistics alone (see §3.6 for
   the mg4 tile 2619 and mg3 tile 1330-vs-Iasi counter-examples). Finding
   a discriminator precise enough to enable by default (the most
   promising lead: using the topology table's own structure as a positive
   "this region has started" signal, rather than purely statistical
   delta-shape heuristics) is unsolved and left for a future session —
   see `_find_oscillation_clusters()`'s docstring for the full evidence,
   including the several additional discriminators tried and rejected
   this session.
   **Topology/adjacency table — structure understood, node-identity mapping
   still open**: each feature gets its own `point_count + 1`-record table with a
   real, degree-aware graph structure (junctions get bigger records than
   through-points — this is now graph-confirmed, not just hypothesized, see
   §3.6). What's missing: the node-id numbering used inside this table doesn't
   match `decode_features()`'s own point order and isn't yet tied back to
   specific real (lon,lat) vertices, so **a valid new topology entry for an
   inserted road's own vertices can't yet be synthesized** — this is the
   concrete remaining gap before a new road can be added with confidence nothing
   downstream (routing/connectivity) breaks. The separate trailing per-feature
   block (possibly attributes like road class/width) is also still unresolved,
   and it's unclear whether every feature even gets one.
   **The "graph-walk" lead (walk the topology graph from a degree-1 endpoint,
   match the resulting order to `decode_features()`'s point sequence) was
   tried and DEFINITIVELY REFUTED**, not just unmatched: the topology graph
   for the 83-point reference tile has two connected components (97+8
   nodes), the 97-node one contains a cycle and 13 endpoints/13 junctions
   (not the 2/0 a simple path would have), and its longest simple
   endpoint-to-endpoint path is only 53 nodes — structurally incapable of
   reproducing an 83-node path under ANY labeling. This means a feature's
   topology table encodes something richer than that one feature's own
   point-to-point adjacency (plausibly the real surrounding road mesh,
   including cross-streets/stub roads outside the feature's own decoded
   geometry) — **a future session should not re-attempt a plain graph-walk
   here**. The previously-suggested fallback lead (spatial sub-index
   construction order) was checked on the same tile and found inconclusive
   only because that particular tile's sub-index is entirely sparse/empty
   (no real cell values to correlate against) — untested on a denser tile
   (e.g. `mp0`). One genuine side-advance: the per-tile header bytes
   0x02-0x17, previously fully undecoded, are now partially explained
   (feature 0's point count/block_end, the small array that accounts for
   most of the "104-byte unidentified gap" before a table, and a
   near-exact total-node-count field) — see `decode_tile_header()` /
   `decode_topology_gap()` in `map_compressed_reader.py` — though this
   narrows rather than closes the node-id↔coordinate gap. Weak, inconclusive
   signal only on both of: (a) real named-road-transition points getting
   bigger topology tags more often (55% vs. 31% baseline, n=11) and (b)
   `eeu.iof`'s varying byte (confirmed to live at byte offset 4 of its
   6-byte record — `[00 00 00 00][varying byte][0x80]` — correcting the
   offset-2 sketch in §3.3) against that same tag-complexity proxy (no
   clean separation, n=15). Full numbers: `decode_topology()`'s docstring.
   **UPDATE (later session): first real, human-verified ground-truth connectivity
   test run against this table — mapping STILL not recovered, but now with much
   sharper negative evidence.** A user-confirmed real 19-point connectivity order
   for a real `mp0` feature (tile_id 91124, offset 1,003,495,557) exact-matched
   decode_features() to 5 decimal places (good), but the user's own hypothesis that
   it closes back through decode_features()'s point index 0 was directly tested and
   REFUTED (point 0 decodes to a real but unrelated location ~1.3km away). Against
   the resulting 18 confirmed real edges: direct point-index membership in the
   topology table's fields scored 0/18; the best of all 307 possible record↔point
   rotational shifts scored only 2/18 (no real signal); edges appearing anywhere in
   the reconstructed graph regardless of position scored 1/18 (chance-level). A
   genuine, unrelated bug WAS found and fixed in the process: tag low-bytes `0x01`/
   `0x11` (~21% of this feature's records) were missing from the field-count table
   and always have all-zero trailing fields (confirmed 64/64), so they mean exactly
   1 real field, not the fallback's forced-minimum-2 — fixed in
   `_FIELDCOUNT_BY_LOW_BYTE`, removing a source of fictitious "edges to node 0"
   (that node's measured degree on this tile dropped from an obviously-bogus 74 to
   10). Positive structural lead: this feature's own 306 points are missing only
   ONE value (id 57) from the topology graph's small-id range 0-305, i.e. the
   node-id set really does appear to be (almost) the same SET as this feature's own
   points, just under an unrecovered, non-simple-rotation permutation — narrowing,
   not closing, the gap.
   **UPDATE (later session): CRACKED.** A second real, human-verified ground-truth
   tile (`mg2` tile_id 20597, offset 69,486,644, feature 0, 203 points — 17 of them
   confirmed by the user in a specific real connectivity order, 16 sequential real
   edges) was obtained and used to test the recommended `eeu.rd`-insertion-order
   lead from the previous update. That specific lead came back negative (no direct/
   rescaled/rank-preserving relationship was found between topology node-ids and
   `eeu.rd`'s own record indices for the matched points) — but investigating it
   surfaced the real mechanism: **a topology record does not reference an adjacent
   point's own index at all. Two really-adjacent points' records instead SHARE one
   common FIELD VALUE** (a per-edge "link id"), and which table record belongs to
   which `decode_features()` point index is offset by a small, PER-FEATURE constant
   ("shift", typically the count of non-point "header" records at the front of the
   table) that is not a fixed layer-wide constant and must be discovered per
   feature. Concretely: on the mg2 tile, point 188's record fields are `{46, 164,
   179}` and point 191's are `{162, 163, 164}` — 191 is never named anywhere in
   188's record, but both share the value 164, and no other point's record on this
   feature contains 164. This is a classic edge-id ("winged-edge"-style) topology
   encoding, explaining why every direct-reference hypothesis tried in every prior
   session (membership, rotation search, "edge exists anywhere in the A-B/B-C/C-D
   chain graph") scored at or near chance — they were testing the wrong
   relationship. The per-feature "shift" is found with NO ground truth needed: try
   every candidate shift, build the shared-value graph it implies, and score it by
   the median real-world distance between its implied edges' endpoints (using the
   feature's own already-decoded coordinates) — the correct shift is a dramatic,
   unambiguous minimum (genuine road topology only connects geometrically close
   points), while every wrong shift's edges connect essentially random, far-apart
   points. Validated: mg2 tile 20597 auto-detects shift=1 (median 49.7m vs. 127.2m
   for the next-best shift) and recovers **16/16** real edges (vs. a measured
   1.07%/5.06% random/nearby-pair chance baseline on this same tile — 16/16 at that
   rate has a chance probability around 1e-21); re-running the exact same method on
   the earlier `mp0` tile 91124 auto-detects shift=2 (median 41m vs. 395m for the
   next-best) and recovers **16/18** real edges (89%, vs. ~0.8% chance baseline) —
   the 2 misses both touch one specific point (259) whose immediate predecessor
   (258) DOES share a value with the far endpoint (270), suggesting a near-duplicate
   junction vertex rather than a failure of the rule. A THIRD, independent
   `mp0` tile (tile_id 79147, no ground truth, checked only for structural
   plausibility) auto-detects shift=1, not 2 — confirming the shift is genuinely
   per-feature, not a fixed per-layer value. Reusable implementation:
   `resolve_topology_adjacency()` in `map_compressed_reader.py`, which returns a
   real point-to-point adjacency graph directly usable against `decode_features()`
   point indices — this is the concrete piece that had been blocking synthesis of a
   valid topology entry for a newly inserted road. **Caveat, measured not
   hypothesized**: on small features (31-point and 13-point single-feature `mp0`
   tiles tested) the auto-detected "best" shift's median edge distance was
   implausibly large (13.9km, 23.0km) — too few implied edges for the geometric
   signal to be reliable, and/or the pre-existing `_find_topology_table_start()`
   small-integer-collision weakness is more likely to mis-locate the table on a
   short feature. `resolve_topology_adjacency()` reports `"confidence": "low"` in
   this case (gated on a 2km median-distance sanity threshold, generous relative to
   every validated correct-shift median seen so far, all under 400m) — always check
   this before trusting a feature's adjacency for anything correctness-sensitive.
   Still open: the numeric link-id values' own independent meaning (e.g. whether
   they're a real, separately-stored edge/segment id used elsewhere in the
   database) and why the per-feature header-record "shift" varies are not
   explained, only discoverable cheaply per feature. Full numbers and mechanism:
   see the "UPDATE (later session): CRACKED" paragraph in §3.6's topology
   write-up, `decode_topology()`'s and `resolve_topology_adjacency()`'s
   docstrings in `map_compressed_reader.py`.

   **Link-id value characterization AT SCALE, a still-later session** (a
   direct follow-up to the "still open" question above): sampled 402
   clean single-feature high-confidence tiles (≥30 points, all 3 layers,
   Bulgaria-wide bbox) and classified every non-zero link-id value by how
   many points share it. **74.2% (91,767/123,618) are shared by EXACTLY
   2 points** — a clean pairwise edge, confirming the core mechanism's
   design at far larger scale than the original hand-verified ground
   truth. **25.4% (31,423) are "orphans"**: present in only 1 point's own
   record, no local partner in this feature — meaning still unresolved
   (unused padding field? a stub for a cross-feature/cross-tile link
   that doesn't resolve locally? a different field role entirely?).
   Only 0.3% form groups of 3+ (real junctions, matching the earlier
   degree-vs-tag-complexity finding). Also found a **second sentinel
   pattern**, distinct from the already-known `0` padding value: values
   near the uint16 ceiling (>65,000) show up in some tiles and badly
   skew naive "value range" stats (e.g. a 39-point feature with values
   spanning `[4, 65455]`) — but confirmed harmless: checked 597
   qualifying tiles and found **zero** cases of a near-65535 value
   forming a spurious 2-point group, so it never produces a false edge
   under the existing mechanism (it's always either an orphan or part of
   an already-filtered 7+-point group) — no code change needed, pure
   characterization. Clean tiles' value ranges are dense (`[1, K]`, no
   gaps) with `K` roughly 1.2-1.8x the feature's point count — consistent
   with a per-tile-authored LOCAL numbering scheme, not an obviously
   external stable key. Whether the values (or the 25.4% orphans
   specifically) correspond to anything in `eeu.rd`'s own record layout
   remains untested: `eeu.rd` has 16 bytes per 67-byte record (offsets
   0-7 and 16-23) not yet mapped to any known field (see §3.1's `eeu.rd`
   write-up) that could plausibly hold such an id.

   **Tested directly, immediately following, same session — REFUTED.**
   Built a full in-memory exact-coordinate index over all 8,809,081
   `eeu.rd` records (~50s) and compared each matched point's `eeu.rd`
   record bytes 16-20/20-24 (uint32 LE, confirmed to hold small
   plausible integers on inspection) against its link-id value set.
   Across 2,963 qualifying points: only **20 matches (0.67%)** —
   actually below the ~1.6% naive chance-collision rate for value sets
   this size. `eeu.rd` bytes 16-24 are NOT the link-id's external
   reference.

   Also tested `eeu.rd`'s other 2 documented "unresolved" candidate
   fields against the same sample: `bytes[5:8]` (previously noted above
   as "often shared across same-name records," a plausible
   shared-geometry pointer) holds values around 3.6-7.7 million on real
   records — far outside any plausible link-id magnitude, 0/2,963
   matches, ruled out on magnitude alone. `bytes[1:5]` (the road-class
   candidate already ruled out against `eeu.typ`/`eeu.si` above) also
   scored 0/2,963. **This is now a complete sweep of every field
   `eeu.rd` documents as unresolved or candidate** — none of them are
   the topology link-id's external reference. The link-id values' own
   independent meaning remains genuinely open.

   **Cross-FEATURE edges (same tile, different feature): the obvious
   mechanism tested and REFUTED, a still-later session.** A structural
   hint (node-ids in one feature's table have been observed going as
   high as the tile's *combined* point total across all its features)
   raised the hypothesis that the existing shared-link-id mechanism
   might just work across features too, unmodified — i.e. two nearby
   dead-end points in different features of the same tile might share a
   link-id value. Tested at scale (Bulgaria-wide bbox, `mg4`/`mg2`/`mp0`,
   646 qualifying multi-feature tiles): compared the shared-value hit
   rate for geographically NEAR (≤150m) dead-end pairs against a FAR
   (>150m) control. If real, NEAR should hit far more often — it
   doesn't: `mg4` 0.33% near vs 0.58% far; `mg2` 0.30% vs 0.33%; `mp0`
   0.54% vs 0.68% — far is equal to or HIGHER in every layer, and many
   "hits" pair points 26km-54km apart (impossible for a real edge).
   **Conclusion: pure small-integer coincidence, not a real mechanism.**
   Cross-feature adjacency remains unsolved; this specific approach is
   closed, not just untried. Full numbers: `resolve_topology_adjacency()`'s
   docstring in `research/map_compressed_reader.py`.

   **Real, user-reported CROSS-TILE example, a still-later session**: an
   even bigger version of the same gap — `resolve_topology_adjacency()`
   only ever resolves adjacency WITHIN one feature/tile; it has no
   mechanism at all for a road that continues into a DIFFERENT tile.
   User right-clicked 2 real points on `mg4` expected to connect: tile
   2384 point 132 (23.45508, 42.63235) and tile 2385 point 12
   (23.45595, 42.63224) — different tiles, ~72m apart, a real, plausible
   connection. Confirmed the structural signature matches a genuine
   tile-boundary split exactly: both resolve at "high" confidence within
   their own tile, but each is a degree-1 dead end locally (no further
   neighbor within its own tile's data). The actual cross-tile link is
   NOT encoded via the usual shared-link-id trick — the 2 points' own
   raw topology records share no common field value at all. This is the
   same GLOBAL routing-graph problem the firmware string-mining already
   named a real pipeline for (`db_vid_get_map_id_V000`/`db_vid_get_
   pcl_id_V000`, §2.6) but never cracked at the byte level — this real
   example is preserved as ground truth for that future attempt. Full
   coordinates: `decode_topology()`'s docstring in
   `research/map_compressed_reader.py`.

   **A predicted-but-unobserved limitation of `max_edge_m` CONFIRMED
   and FIXED, a still-later session.** User-reported: 2 `mg4` points
   (tile offset 6,546,198, feature 0, points 72 and 74) with "I think
   there should be more points" between them, then correctly "these 2
   must be connected" once cross-checked. Investigation found the real
   topology here is genuinely 2 INTERLEAVED PARALLEL CHAINS (a divided
   road's 2 carriageways, one correctly dead-ending) — the shared-
   link-id mechanism itself works right — but the real edge `(72, 74)`,
   1,518m apart, was being dropped by `resolve_topology_adjacency()`'s
   own `max_edge_m=200` default. That default was calibrated ENTIRELY
   from `mg2`/`mp0` ground truth (dense layers, every real edge under
   110m) and applied uniformly to every layer — never validated against
   `mg4`, the coarsest layer, where 200m-2,000m between shape points is
   normal. Auditing just this one feature found **28 real, legitimate
   edges (200m-1,810m) silently dropped**. Fixed at the caller level
   (not the function's own default, which stays correct for the layers
   it was validated against): the viewer's `MAX_EDGE_M_BY_LAYER` now
   passes 5,000m for `mg4`/`mg3`, unchanged 200m for `mg2`/`mg1`/`mp0`.
   Verified directly: real rasterized connected-roads line pixels
   increased in a live redraw test (667→1,183 and 1,055→1,460 at 2
   zoom levels) — more real edges drawn, confirmed not a regression.

   **Follow-up tested and rejected, same session**: whether the
   interleaved-parallel-chains structure behind the (72, 74) fix
   generalizes into a divided-road detector (scan for alternating
   gap=2 edges). Checked against the project's 4 existing
   human-confirmed ground-truth sites (A1 x2, Hemus, A6) at their
   *exact* reported points: only 1 of 3 divided sites (Hemus) shows
   the pattern right at its reported location; the other 2 look
   mostly sequential, and the non-divided control isn't clean either.
   Real but inconsistent — not usable, not pursued further.
6. ~~`.rt`/`.rl` semantics~~ **`.rl`/`.prl` SOLVED and validated at scale; `.rt`'s node
   format also now CRACKED and cross-validated, with a few fields/edge cases still
   open** — see §3.7. `.rl` (12-byte records: candidate `.rd` index + validated `.prl`
   byte-offset pointer + unresolved flag byte) and `.prl` (flat, non-deduplicated
   null-terminated name catalog, ~5.3 entries per `.rd` record) are cracked, with the
   `.prl`-pointer field exact-match validated across the full 46.4M-record file. `.rt`
   is a fixed-19-byte-node character trie: each node stores `[subtree_size][char_code]
   [reserved][field4]`, where `subtree_size` doubles as a "skip this many 19-byte units
   to reach my next sibling" pointer — validated via a direct hand-checked example
   (node D → children F,G → next sibling M, sizes matching exactly), a 72.8%-vs-4.2%-
   base-rate pointer hit-rate test at 20,000-node scale, and real cross-referenced
   vocabulary (walking the trie spells `"SOKAK"`, independently confirmed present in
   `eeu.typ`, plus `"PROEZD"`/`"ULITSA"`/`"VULYTSIA"`/`"CADDESI"` and plausible real
   full street names like "VIA VITTORIO VENETO"). Still open: the true root isn't
   located (no `rt_root()` yet), a node's `subtree_size` doesn't always account for
   100% of its own subtree (likely an undecoded wider node variant for non-ASCII edge
   characters), and the `reserved`/`field4` fields are unconfirmed. Practical
   implication worth prioritizing: if `.rt`/`.rl`/`.prl` turn out to back the unit's
   actual on-screen "City → Street" destination search (now better-evidenced given
   `.rt` demonstrably encodes the same demoted/sort-key name strings as `.prl`, still
   not confirmed on real hardware), a road added only to `.rd`/`.il` may be invisible
   to that search on real hardware even though the GUI tool's own search (which uses
   `.il`) finds it.
7. Several `.rd` header bytes remain unresolved (candidate road-class/one-way flag,
   candidate shared-geometry pointer, two more candidate cross-reference fields).
8. **Real hardware validation** — nothing in this project has been tested on an actual
   RNS510 unit yet. Recommended order: (a) zero-edit round-trip test first, (b) a
   trivial content edit (rename one existing street) second, (c) only then attempt a
   structurally novel addition.

---

## 9. Research artifacts

`research/` in this folder holds reusable, documented format-reader modules pulled out
of the session scratchpad for permanence:
- `flat_compressed_reader.py` — open/decompress any FLAT_COMPRESSED file.
- `map_compressed_reader.py` — parse MAP_COMPRESSED headers, locate and decompress
  individual tiles.
- `road_index_reader.py` — decode `.rl` (road list) 12-byte records and `.prl` (road
  names) name catalog, plus `.rt` (road tree)'s cracked 19-byte character-trie node
  format (`rt_node()`/`rt_char()`/`rt_children()`/`rt_walk_strings()`) and what
  remains open on it (see §3.7).
- `city_reader.py` — decode `.cty` (city/town/locality) 79-byte records and `.cl`
  (city list) 54-byte records (see §3.8), plus documents what was ruled out on `.ct`.
- `road_naming.py` — join decoded tile geometry (`decode_features()`) to real `.rd`
  road names by coordinate match, for labeling rendered polylines (see §3.9).
- `feature_reader.py` — FEATURE_COMPRESSED (`eeuz.fea`) reader: locate/decompress
  its zlib payload entries (tolerating the format's intermittent non-zlib gaps),
  extract multi-language place-name tables (`scan_names()`), and decode the
  directory's big-endian `(offset, declen, complen)` index-triple records
  (`decode_directory_table()`, `verify_index_triple()`,
  `find_index_record_for_offset()`) — see §3.10.
- `class_name_inventory.txt` — ~6,500 Java class names extracted from the firmware's
  UI application, for reference if UI-side work resumes later.

Deeper, less-reusable exploratory scripts (byte-level probing, hypothesis testing,
Ghidra project files, etc.) remain in the session's temp scratchpad directory and will
not persist — the modules above are the load-bearing outputs worth keeping.

---

## 10. Map viewer (visualization/validation tool)

`rns510_map_viewer.py` (project root, run with `py rns510_map_viewer.py`) — a
**read-only**, light-themed 2D map view of the actual decoded road network —
"Google Maps but simple", per the explicit ask that prompted this rewrite, not a
clone of the unit's own dark 3D night-mode UI. It shows labeled roads, labeled
cities/towns, a unified place/road search box, and reloads more of the map as you
pan/zoom, rather than a fixed, unlabeled, non-interactive snapshot of raw line
segments (see "v1 vs v2" below for exactly what changed).

**Quick demo**: `py rns510_map_viewer.py` → File → Open Map ISO... → type
`TIRANE` (or `TIRAN`) in the search box → double-click the `[City]` result. This
centers on a previously-validated real city (§3.8) and loads/labels the roads and
neighboring towns around it. Panning/zooming from there loads more tiles for the
new view in the background.

### v1 → v2: what changed

| | v1 (original) | v2 |
|---|---|---|
| Tiles | fixed K-nearest, loaded once per search | dynamic: `MapData.ensure_area_loaded()` loads/caches tiles for the current (padded) viewport, re-triggered on pan/zoom |
| Road names | none — raw unlabeled polylines | real `eeu.rd` names attached via `road_naming.name_features()`, drawn at the midpoint of sufficiently-long-on-screen named runs |
| Cities/towns | none | real `eeu.cty` names, zoom-dependent (bbox-area threshold), drawn as a dot + label |
| Search | roads only (`.il`) | unified: roads (`.il`) + cities (`.cty`) in one result list, tagged `[Road]`/`[City]` |
| Theme | dark, unit-style night mode | light "Google Maps but 2D": white/light-gray background, gray roads (thicker/darker for longer named runs), dark labels, bold larger city labels, a distinct red pin marker |
| Pan/zoom | canvas-only; tiles never reload, far panning shows blank canvas | debounced background reload of tiles/road-names/cities as the view moves |

### v2 → v3: automatic zoom-dependent layer selection (this session)

**The explicit user complaint that prompted this rewrite** (verbatim): *"instead
of having many layers and me having to choose seems stupid. im a user of this
viewer, and i dont need to choose a layer, can we just have all layers visible
at all time?"* — sharpened by a concrete, reproduced finding: `mg3` (v2's fixed
default layer) has **zero tiles** in a small real bbox around Sofia, Bulgaria
(`lon=23.40102/lat=42.65533`, ±0.01°), while `mg2` has a few and `mp0` is far
denser. Separately, `mg1` turned out to be **completely missing** from
`LAYER_ISO_PATHS` — a real gap, not a deliberate omission (the ISO does have
`db/eeuz.mg1`, ~240MB/64,000 tiles, sitting between `mg2` and `mp0` in size).

v3 removes the layer dropdown from the UI **entirely** and replaces the fixed
single-layer model with **automatic zoom-dependent layer selection** — the way
every real digital map (and the RNS510 unit itself) works: the user never sees
a "layer" concept at all, the app just shows the appropriate amount of road
detail for the current view, transparently, upgrading/downgrading as they zoom.

**Fast layers, built eagerly.** `mg4`/`mg3`/`mg2`/`mg1` (`FAST_LAYERS`, coarsest
to finest) are all cheap to geo-index — measured directly against the reference
disc this session (`build_geo_index()` wall-clock time): mg4 6,110 tiles/~0.3-0.6s,
mg3 16,503/~1s, mg2 34,209/~2s, mg1 63,996/~4s. `MapData.load()` (run once, on
"Open Map ISO") now extracts and geo-indexes all four eagerly — combined cost is
a few seconds, comparable to the `RdCache`/`CtyCache` build that already happens
at open time, so this barely adds to perceived startup time and means every zoom
level except the very closest ("street level") works the instant the ISO finishes
loading.

**The heavy layer, built in the background.** `mp0` (`HEAVY_LAYER`, 2.14GB,
194,705 tiles, by far the densest) is a different story — `build_geo_index()`
alone measured **34-55s** on the reference disc this session, far too slow to
block "Open Map ISO" on. `App.on_open_iso()` now kicks off
`MapData.load_heavy_layer()` in its **own** `BackgroundTask`, started right
after the fast layers finish, so it runs in parallel with the user's first
search/pan/zoom rather than gating it. A subtle, non-blocking status-bar line
(`App.mp0_status_var`, separate from the main status bar so ordinary messages
never overwrite it) shows "Loading detailed street-level roads in the
background..." while this runs, then "Detailed street-level roads ready."
briefly before clearing.

**Choosing a layer for the current view.** `choose_layer_for_scale(scale,
mp0_ready)` (`scale` = pixels/degree, the same value `App.scale` already
tracked for zoom) maps the current view scale to a single layer:

| scale (px/deg) | layer | roughly |
|---|---|---|
| < 800 | `mg4` | country/regional overview |
| < 2,500 | `mg3` | wide city / metro-area view |
| < 6,000 | `mg2` | city view |
| < 15,000 | `mg1` | close-in / neighborhood view |
| ≥ 15,000 | `mp0` (or `mg1` if not ready yet) | street level |

These thresholds were picked from two things measured directly against the real
ISO this session, not tuned by feel: (1) a real per-area density comparison at
the same Sofia-area bbox that motivated this feature (0.1°-wide box) found road
POINT counts increasing substantially and monotonically at every layer step —
mg4 **141**, mg3 **397**, mg2 **952**, mg1 **2,218**, mp0 **11,821** points — so
each threshold step is a genuine, substantial upgrade in what's actually drawn,
not a cosmetic one; and (2) a typical "jump to a searched place" action's
resulting scale lands in the ~800-2,500 px/deg range on a normal window size,
which is why that range keeps using `mg3` — v2's fixed default was in fact
already tuned for exactly this one scale, it was just never extended to cover
any other. The task's own framing agrees exact cutoffs don't need to be
perfectly tuned; retune `SCALE_LAYER_THRESHOLDS` in a future session if better
numbers are found.

`MapData.ensure_area_loaded()` now takes the current `scale` as a required
argument, calls `choose_layer()` internally, and decodes tiles from whichever
layer that returns — the caller (the GUI) never picks a layer itself.
`App._maybe_reload_viewport()` (the existing pan/zoom debounce) reloads not
only when the viewport escapes the last-loaded bbox but also when the
scale-appropriate layer has *changed* — covering both "the user zoomed across a
threshold" and "`mp0` just finished building in the background and this
close-in view should silently upgrade to it now" (the latter is triggered
directly from `load_heavy_layer()`'s completion callback, with no user action
needed). A "jump to X" action estimates its likely resulting scale from the
requested span before any tiles are decoded (`App._estimate_scale_for_span()`)
to pick a reasonable starting layer, then re-checks against the real,
post-auto-fit scale once decoding finishes and silently corrects the layer if
the estimate was off.

**Per-layer tile caching.** `MapData.tile_caches` is now `{layer: {tile_id:
decoded_features}}` — one cache per layer, not one shared dict — because
`tile_id` numbering is independent per layer (mg3's tile 100 and mp0's tile 100
are unrelated tiles; sharing one dict would either collide or force
re-decoding on every layer switch). Once a tile is decoded in a given layer it
is never re-decoded or evicted, so zooming back out to a previously-seen area
at a previously-used zoom level is instant. `covered_bbox`/`covered_layer`
together track what the currently-pooled tiles guarantee coverage for.

**Honest remaining limitation.** If the user zooms to street level *before*
`mp0`'s background geo-index finishes, they see `mg1`'s detail — not an error,
not a freeze, just the next-best already-ready layer — until `mp0` becomes
ready, at which point the view upgrades automatically. In a real area that has
almost nothing in `mg1` but does have content in `mp0` (measured directly: the
same tight ~0.02°-wide Sofia-area box used above has **zero** tiles in
mg1-through-mg4 but 1 tile/2 features/426 points in `mp0`), this means the map
can look genuinely near-empty for the few-seconds-to-under-a-minute it takes
`mp0` to finish, even though nothing has gone wrong. This is a real UX
rough edge, not swept under the rug — there was no way to make `mp0`'s own
34-55s geo-index build itself faster this session (see §3.6), so the fallback
window is inherent to the approach, only its blast radius (falling back to the
next-best layer instead of showing nothing at all, and upgrading the instant
`mp0` is ready rather than requiring a manual refresh) was minimized.

### v3 → v4: roads rendered as unconnected dots, not lines (this session)

**User feedback that prompted this** (verbatim): *"i think we have something
wrong, because roads are not roads in the viewer they are lines that go
crazy.... instead of having connected lines from the dots points, can we just
see all the dot points and not connect them? i think thats better."*

This is a real, structural sidestep of a still-open problem (§3.6/§8): a
decoded feature's point sequence can legitimately jump between unrelated real
road segments with no marker of where one ends and the next begins (the
segmentation/topology table is still uncracked), which previously rendered as
long, geometrically-nonsensical straight "teleport" lines connecting two
correct-but-unrelated points. **Drawing each decoded vertex as an independent
point instead of connecting consecutive points with a line makes this class of
visual artifact structurally impossible** — nothing is ever connected, so
there's no wrong line to draw. Dense real road geometry still reads as a
recognizable street shape from point density alone, without needing to know
(or guess) where a chain should have been cut.

`_redraw()`'s road-drawing loop now does `canvas.create_oval` (tiny radius,
1.0-1.6px depending on the existing named/vertex-count importance proxy) per
point instead of one `canvas.create_line(*coords)` per named/unnamed run. The
line-count-based test assertion (`test_map_viewer.py`) was updated to check
for a large oval count instead, since roads no longer produce any `"line"`
canvas items at all — this is an intentional behavior change, not a
regression, and full re-verification (`py test_map_viewer.py`) confirms
everything else (search, dynamic loading, real name/city labels near Tirana)
still passes unchanged.

**Real performance regression found and fixed as a direct consequence**: more
canvas items (one oval per vertex, vs. one line per named run) makes a full
`_redraw()` meaningfully slower — measured **0.5s for ~21,000 points** on a
dense `mp0`-level view near Tirana. Panning (`_on_drag_move`) previously called
a full `_redraw()` on *every single mouse-move event* during a drag, which at
that cost would have made dragging unusably choppy (roughly 2 redraws/sec vs.
a smooth continuous drag). Fixed by no longer recomputing the geo→screen
projection during an active drag at all: `_on_drag_move` now just calls
`self.canvas.move("all", dx, dy)` (a cheap coordinate-only shift of already-
drawn items, by the mouse's incremental per-tick delta) for immediate visual
feedback, and a new `_on_drag_end` (bound to `<ButtonRelease-1>`) does exactly
one real, accurate `_redraw()` once the drag actually stops — reconciling any
`canvas.move` floating-point drift and drawing anything newly revealed at the
canvas edges. Zoom (`_on_zoom`, a lower-frequency, discrete-tick interaction)
was left calling `_redraw()` directly, unchanged.

### v4 → v5: show every layer's points at once, not just one (this session)

**User feedback that prompted this** (verbatim, said right after seeing the
v3→v4 dot-rendering change and liking it): *"it looks so much more like a map
now but i think we should keep all the points from all layers shown all the
time."* Their reasoning, confirmed correct rather than re-derived: since dots
never create a "wrong connecting line" between unrelated points (that's the
whole point of v3→v4), overlaying points from ALL layers simultaneously can't
create the visual mess that overlaying multiple generalization levels'
*lines* would have — it just adds more real points onto the same real
streets that a coarser layer already drew a simplified version of.

**What changed.** The v3 automatic zoom-dependent single-layer choice
(`choose_layer_for_scale()`/`SCALE_LAYER_THRESHOLDS`/`MapData.choose_layer()`
— "v2 → v3" above) is removed outright, not just bypassed: those names no
longer exist in `rns510_map_viewer.py`. In their place, `MapData.
available_layers()` returns the layers currently safe to query — always
`mg4`/`mg3`/`mg2`/`mg1` (`FAST_LAYERS`, unchanged: still eagerly extracted +
geo-indexed on "Open Map ISO"), plus `mp0` (`HEAVY_LAYER`) once its background
geo-index build finishes (`load_heavy_layer()`/`mp0_ready`, also unchanged —
still a separate `BackgroundTask` kicked off right after "Open Map ISO", still
non-blocking). `MapData.ensure_area_loaded()` no longer takes a `scale`
argument at all: it loops over `available_layers()`, decodes each layer's own
not-yet-cached tiles covering the (padded) viewport into that layer's own
`tile_caches[layer]` entry (tile_id numbering is not shared across layers, so
this was already a per-layer dict — see "v2 → v3" — it just gets populated
for every layer now instead of one), and flat-concatenates every layer's
decoded features into one pooled list before road-naming and returning.
Returns `{"bbox", "layers", "tile_ids", "new_tiles", "features"}` where
`layers` is the list actually queried and `tile_ids` is `{layer: [tile_id,
...]}` — both plural now, replacing the old singular `"layer"`/`"tile_ids"`
(a flat list) shape. `App._maybe_reload_viewport()` now triggers a reload
when the viewport escapes the covered bbox OR `available_layers()` itself has
changed (i.e. `mp0` just became ready) — the same hook that used to detect "a
zoom threshold was crossed" now detects "a new layer became available",
which is what makes `mp0` still fold in automatically the moment its
background build finishes, exactly as before except **additively** (the 4
fast layers' already-decoded, already-cached tiles are untouched; only `mp0`'s
own tiles get newly decoded and unioned in) instead of a full layer swap.

**Sanity-checked, not just designed, against a combinatorial bug.** The task
that prompted this explicitly flagged that a flat per-layer decode + pool is
correct, but a naive implementation could accidentally multiply points
instead of summing them. Verified directly against the real ISO at the same
real Sofia, Bulgaria area used throughout this project's testing
(`lon=23.40102/lat=42.65533`, ±0.05°): per-layer point counts from ONE
`ensure_area_loaded()` call were `mg4=501, mg3=1303, mg2=3512, mg1=7342`,
summing to exactly `12,658` — which is exactly the pooled `union_points` the
call actually returned, confirmed by a direct equality assertion in
`test_map_viewer.py` (`union_points == sum(per_layer_points.values())`), not
just eyeballed. No combinatorial blow-up.

**Real before/after point counts, same real Sofia-area bbox**
(`test_map_viewer.py`, against `CD_8555.ISO`):
- 4 fast layers only (before `mp0`'s background geo-index finishes):
  **12,658 points** (190 tiles across the Timișoara-area load, 906 tiles for
  a separate simulated pan to the Prague area — both fully additive across
  `mg4`/`mg3`/`mg2`/`mg1` in one call each, per the numbers above for Sofia).
- All 5 layers, immediately after `load_heavy_layer()` finishes (41.7s this
  run, vs. 10.2s for the entire fast-layer "Open Map ISO" path — consistent
  with the "v2 → v3" measurements, mp0's build is still the genuinely slow
  part): `mp0` alone contributed **35,644 points** at the same bbox, for a
  pooled total of **48,302 points** — and `12,658 + 35,644 = 48,302` exactly,
  confirmed by a direct equality assertion (`all_points == union_points +
  mp0_points`), i.e. the fold-in really is additive, not a recomputation that
  happens to land on a bigger number.

**Real `_redraw()` timing, same real Sofia-area bbox, driven directly (not
estimated)**:
- 4 fast layers only: **12,658 points → 9,849 ovals → 0.175s**.
- All 5 layers incl. `mp0`: **48,302 points → 35,347 ovals → 0.595s**.

Both comfortably under the "starts to feel sluggish" ballpark (~1s) this
session's task used as a guideline, so **no downsampling/point-cap mitigation
was added** — the task was explicit that this should only be built if real
measurement showed it was actually needed, and it didn't. (Separately, the
existing GUI smoke test's Tirana-area redraw — now merging all 5 layers
instead of one — produced 59,663 ovals from a 0.15°-radius box, a useful
data point that a *wider* viewport at full 5-layer density can run noticeably
higher than the Sofia numbers above; still not measured to be a problem, but
worth knowing if a future session revisits this.) If a future session finds a
real interactive case that does feel slow (e.g. a much wider viewport, or a
lower-spec machine), the task's own suggested cheap mitigation — a
per-viewport point cap with random/stride-based downsampling in the render
path only, not the decode path — is still the right first thing to try
before anything more invasive.

**The v3→v4 dot-rendering choice is what makes this safe**, not incidental:
because roads render as unconnected per-vertex dots, not lines, pooling
5 generalization levels' worth of points can only ever make the same real
streets look denser/more filled-in — there is structurally no way for it to
draw a new wrong CONNECTION between two points the way overlaying multiple
levels of *lines* would have. This is also why no per-layer visual
distinction (e.g. dimming coarser-layer dots) was added: the whole premise of
this change is that all layers' points belong on the same map at the same
time, at equal visual weight, since they all describe the same real roads at
different levels of the same real dataset.

**Test changes.** `test_map_viewer.py`'s assertions that checked a specific
single `result["layer"]` (e.g. `== "mg3"` at a given scale) were replaced,
not deleted — they now check `result["layers"] == FAST_LAYERS` (or
`FAST_LAYERS + ["mp0"]` once ready), that `tile_ids`/per-layer point sums
behave as described above, and that the pooled total is an exact flat sum
(the anti-combinatorial check). The `choose_layer_for_scale()` threshold
probe test was removed since the function no longer exists; replaced with a
direct `available_layers()` check before/after `load_heavy_layer()`. A new
real `App._redraw()` timing measurement (both layer-availability states, same
real bbox) was added, matching the numbers reported above. Full suite
re-verified passing end to end against the real ISO (`py test_map_viewer.py`)
and the separate editing tool's own suite (`py test_core.py`) was re-run
unchanged to confirm it's unaffected.

**Limitations found, stated honestly.**
- No new dedup was added on top of the flat per-layer pool, by design (the
  user's own stated preference) — the same real road's coarser and finer
  representations both draw their own dots, so a well-mapped street can look
  visually "thicker"/denser purely from layer overlap, not from any new road
  data. This was the explicit ask, not an oversight.
- The mp0-background-build honest edge case from "v2 → v3" is narrowed, not
  eliminated: before `mp0` finishes, an area that's genuinely sparse in every
  fast layer (the same real ~0.02°-wide Sofia-area example used in "v2 → v3"
  — 0 tiles in `mg1`-`mg4`) still looks blank until `mp0`'s points fold in;
  the difference is that a MIXED area (real content in some fast layers,
  more in `mp0`) now shows a still-correct, just-less-detailed set of real
  points immediately rather than substituting a coarser layer's worth of
  detail for the "right" one.
- No layer-availability change is possible OTHER than mp0 turning on (the
  fast layers are always all present together, from the first successful
  "Open Map ISO"), so `available_layers()` only ever has two possible values
  per `MapData` instance in practice — simple by construction, not a
  simplification that was tested away.
- The Tirana-area 59,663-oval data point above (a wider box than the Sofia
  measurement) was not independently re-timed with a stopwatch assertion the
  way the Sofia bbox was — it's reported as a useful upper-range data point
  from the existing GUI smoke test, not a second fully-instrumented
  before/after comparison.

### v5 → v6: cumulative scale-stacked layers — zoom out shows one layer, zoom in stacks more on top (this session)

**The explicit user request that prompted this** (verbatim): *"i need you to
make it work in the following way: zoomed out 1 layer and the more you zoom
in the more layers stack one ontop of the other."*

**What changed and why.** v5's "pool every available layer, all the time,
regardless of zoom" model is replaced — not just tuned — by a scale-aware
model again, but a fundamentally different one from v3's: v3 picked exactly
ONE layer per scale and swapped it out entirely as the user zoomed (a real,
user-reported problem in its own right — see "v2 → v3"'s Sofia/mg3 example).
v6 instead grows a **cumulative** set: at maximum zoom-out only `mg4` is
pooled, and each zoom-in step **adds** the next-finer `FAST_LAYERS` entry on
top of the ones already there, ending with `mp0` once the view is zoomed in
enough AND `mp0`'s background geo-index has finished — never swapping a
coarser layer back out while zoomed in. Zooming back out reverses this:
finer layers stop being pooled/rendered again, so a wide view isn't stuck
paying v5's full 5-layer redraw cost when it doesn't need that much detail.
This keeps v4's "dots, not lines" property doing the same safety work it did
for v4→v5 — see below — while capping the worst-case per-redraw point count
to whatever the CURRENT zoom actually needs, not the full pooled-everything
cost regardless of zoom.

**New function**: `layers_for_scale(scale, available)` (`rns510_map_viewer.py`)
returns `FAST_LAYERS[:n]` for a scale-dependent `n`, plus `mp0` appended only
once `scale >= MP0_MIN_SCALE` **and** `mp0` is present in `available` (i.e.
`MapData.available_layers()`'s own gating on `mp0_ready` — this never blocks
on or requests an unindexed layer). `MapData.ensure_area_loaded()` takes
`scale` as a required parameter again (removed in v4→v5, reinstated here) and
pools tiles/features only from `layers_for_scale(scale, self.available_layers())`,
not from every available layer unconditionally.

**Chosen thresholds — reused, not re-derived, and here's why that's sound.**
`SCALE_LAYER_THRESHOLDS` reuses the exact scale boundary VALUES this project
already measured and validated for v3's single-winner
`choose_layer_for_scale()` ("v2 → v3" above), which came from a real
per-area density comparison at the same Sofia, Bulgaria bbox used throughout
this project's testing (0.1°-wide box):

| scale (px/deg) | cumulative layers | roughly | points at this bbox (own layer / cumulative) |
|---|---|---|---|
| < 800 | `mg4` | regional overview | 141 / 141 |
| < 2,500 | `mg4`,`mg3` | metro-area view | 397 / — |
| < 6,000 | `mg4`,`mg3`,`mg2` | city view | 952 / — |
| < 15,000 | `mg4`,`mg3`,`mg2`,`mg1` | neighborhood view | 2,218 / — |
| ≥ 15,000 (+ `mp0` ready) | `mg4`,`mg3`,`mg2`,`mg1`,`mp0` | street level | 11,821 / — |

Each step is a genuine, substantial (>2x, up to >5x for `mp0`) upgrade in
real drawn detail, not a cosmetic one — the same justification v3 used still
holds. Only the SELECTION RULE at each boundary changed (add the next layer,
never swap one out), so reusing the boundaries was a deliberate choice, not
laziness: the values were already right for "when does this dataset actually
get meaningfully denser," which is exactly the question a threshold table
should answer whether the rule at each boundary is "swap" or "add."
`MP0_MIN_SCALE` is the same 15,000 boundary — mp0 is added on top of, not
instead of, the four fast layers once street level is reached.

**Real before/after measurements, same real Sofia-area bbox
(`lon=23.40102/lat=42.65533`, `±0.05°`), fixed area, scale swept**
(`test_map_viewer.py`, against `CD_8555.ISO`, before `mp0` is ready):

| scale | cumulative layers | pooled points |
|---|---|---|
| 500 | `['mg4']` | **501** |
| 1,500 | `['mg4','mg3']` | **1,804** |
| 4,000 | `['mg4','mg3','mg2']` | **5,316** |
| 10,000 | `['mg4','mg3','mg2','mg1']` | **12,658** |

Confirmed monotonic AND additive at every step (`layers[i][:len(layers[i-1])]
== layers[i-1]` for every consecutive pair, checked directly, not just
eyeballed) — this is the concrete evidence that zooming in stacks layers on
top of each other rather than swapping. Zooming back OUT to scale 500 at the
exact same bbox reproduced the exact same layer set (`['mg4']`) and the exact
same point count (**501**, not partial) — confirming finer layers really do
stop being pooled once zoomed back out, not just "stop growing further."
With `mp0` ready and scale raised to 20,000, the same bbox additionally
pooled `mp0`'s own **35,644** points for a **48,302**-point cumulative total —
matching the v4→v5 "all 5 layers" figure exactly, since at high-enough scale
with `mp0` ready the v6 cumulative set equals v5's "everything" set; the
difference is v6 no longer pays that cost at LOW scale, which v5 always did.

**Zoomed-out cost, concretely reduced**: the v4→v5 writeup measured a full
5-layer `_redraw()` at 48,302 points / 0.595s for the Sofia bbox regardless
of zoom. Under v6, that same bbox at the lowest scale (500) now redraws only
**501** points — the 0.595s worst case is only paid once the user has
actually zoomed in far enough to want it, not on every redraw of a
zoomed-out view.

**Reload trigger, extended (Task 3).** `App._maybe_reload_viewport()`
previously reloaded on two conditions: the viewport escaping the covered
bbox, or `available_layers()` changing (i.e. `mp0` finishing in the
background). Both are now folded into ONE check alongside a new third
condition: `layers_for_scale(self.scale, data.available_layers())` no longer
equalling `data.covered_layers`. This single comparison catches "the
viewport escaped," "`mp0` just became available," AND "the user zoomed
across a `SCALE_LAYER_THRESHOLDS` boundary" — the last one being the new
case needed to make "zoom in → more layers actually appear on screen" work
in the running app, not just inside `MapData`. Verified END TO END against
the real ISO (`test_map_viewer.py`'s GUI section), not just at the
`MapData` level: with the canvas/center/pan held fixed and only
`App.scale` changed from 500 → 10,000 (a real zoom-in), the new viewport was
first confirmed to already be fully contained in the previously-loaded
(padded) bbox — i.e. trigger (a), bbox escape, could NOT be what fires next
— and `_maybe_reload_viewport(force=False)` still started a real background
`BackgroundTask` load (`App._area_loading` flips `True` synchronously),
which on completion changed `app.data.covered_layers` from `['mg4']` to
`['mg4','mg3','mg2','mg1']` with every newly-added layer (`mg3`/`mg2`/`mg1`)
confirmed to contribute real, non-zero points (415/1,003/2,418/5,911 for
mg4/mg3/mg2/mg1 respectively, at that particular zoomed-in viewport size).
Zooming back out to scale 500 (same center/pan/canvas) triggered a second
real reload, dropping back to `covered_layers == ['mg4']` and reproducing
the exact original 18,680-point count for that bbox — confirming the drop
on zoom-out also works end to end, not just inside `MapData`.

**Task 4 — verified this is stacking, not v3's regression, and the caching
question.** Explicitly checked and confirmed: (1) zooming in KEEPS the
coarser layer's points visible additively (the monotonic/additive table
above, plus the GUI-level per-layer non-zero-contribution check); (2)
zooming back out drops the finer layers again rather than staying saddled
with v5's full pooled cost (measured above, both at the `MapData` level and
end to end through the running `App`). On the caching question specifically:
`MapData.tile_caches` is **not** evicted when a layer falls out of the
current cumulative set — a fine layer's already-decoded tiles simply stay in
their own `tile_caches[layer]` entry, just excluded from `active_tile_ids`
(and therefore from what gets pooled/rendered) until the user zooms back in.
This was a deliberate choice, not an oversight: keeping decoded-but-unused
tiles in memory costs nothing extra at redraw time (they're plain Python
dicts sitting unreferenced by the current draw call, not iterated), and
means zooming back into the SAME area at a PREVIOUSLY-visited scale is a
pure cache hit — confirmed directly (`ensure_area_loaded()`'s `new_tiles`
count was exactly **0** when re-zooming into a previously-visited scale/bbox
combination in `test_map_viewer.py`). Actually evicting would only save
memory (never measured to be a problem on this project's reference
hardware/dataset) at the cost of a real, avoidable re-decode the next time
the user zooms back in to a spot they already visited — a bad trade for a
read-only visualization tool with no memory pressure evidence.

**Limitations found, stated honestly.**
- The chosen thresholds are the same ones "v2 → v3" already flagged as "not
  perfectly tuned by design, retune if better numbers are found" — that
  caveat still applies unchanged; only the SELECTION RULE built on top of
  them changed this session, not the boundary values themselves.
- Total pooled-point counts are **not** directly comparable across different
  *scales* when the viewport's on-screen size is held fixed (as in the real
  `App`, unlike the fixed-bbox `MapData`-level sweep test): zooming in
  shrinks the visible-area bbox by roughly `(scale ratio)²` (a 20x scale
  jump, 500→10,000, shrinks the visible area by roughly 400x), which
  comfortably outweighs the 2-5x per-layer density gain from stacking more
  layers. This is correct, expected real-map behavior (a zoomed-in view
  legitimately shows fewer absolute points over its much smaller area, even
  though each point is "more detailed" per unit area) — but it means "does
  the total point count go up when I zoom in" is NOT itself a valid
  end-to-end test at the `App` level; `test_map_viewer.py`'s GUI-level check
  instead verifies additivity via the layer-SET growing monotonically and
  every newly-added layer having non-zero real contribution, and verifies
  the fixed-bbox growth claim separately at the `MapData` level where area
  is held constant on purpose.
- `mp0`'s background-build honest edge case (documented in "v2 → v3"/"v4 →
  v5") is unchanged in kind, but its window is now also gated by scale: a
  user who zooms to street level before `mp0`'s background geo-index
  finishes sees whatever the cumulative fast-layer set for that scale
  already provides (typically all four `FAST_LAYERS`, since street level is
  `>= MP0_MIN_SCALE`) — not `mp0`'s own extra detail — until it becomes
  ready, at which point the same reload-trigger mechanism above folds it in
  automatically.
- No attempt was made to dim/de-emphasize coarser layers' dots once finer
  ones are stacked on top at high zoom (the same "equal visual weight"
  choice v4→v5 made, for the same reason: all layers describe the same real
  roads at different generalization levels of the same real dataset, so
  there is no principled way to prefer one dot over another at a shared
  location).

### v6 → v7: click-to-identify points, for user-supplied connectivity ground-truth (this session)

**The explicit user request that prompted this** (verbatim): *"make the
points clickable, and when i click them you can give me some info to give
you i will tell you which 10 points need to be connected to help you figure
out the others how to be connected by lines."*

**Why this matters (not solving the topology table itself).** §3.6's
per-vertex topology/adjacency table is still uncracked after two separate
deep automated attempts (a fixed-stride record parse, then a graph-theoretic
walk hypothesis that was DEFINITIVELY REFUTED on structural grounds — see
§3.6's "graph-walk approach... refuted" note). Roads render as unconnected
dots (v3→v4) specifically because this project cannot yet reconstruct
correct point-to-point connectivity from the tile bytes alone. This
session's plan, and the ONLY thing it builds: let the user — who knows real
streets (e.g. around Sofia) — click points in the viewer, read back enough
identifying info to locate each one byte-for-byte, and report in a later
chat message which specific points are actually connected in real life.
A future session can then go back to those exact points' raw tile bytes and
look for a pattern in the topology table that explains that real
connectivity, turning this into a constrained, evidence-driven
reverse-engineering problem instead of blind guessing. **This session does
NOT attempt to solve the topology table** — only the point-identification UI.

**Binding chosen: right-click (`<Button-3>`), not a hold-still left-click.**
Left-click (`<ButtonPress-1>`/`<B1-Motion>`/`<ButtonRelease-1>`) is already
the pan-drag gesture (v3→v4's perf-fix era), and `<Button-3>` was completely
unused by the canvas beforehand, so binding it to `App._on_point_pick()` is a
zero-conflict addition — no distance/movement heuristic is needed to
disambiguate a click from a drag, which a hold-still-left-click design would
have required (and could still occasionally misfire as a tiny pan on a real
mouse/trackpad). **Verified, not just argued, that panning is unaffected**:
`test_map_viewer.py` explicitly drags a known distance after exercising a
real pick (press at (300,200), move to (340,175), release) and asserts
`pan_x`/`pan_y` update by exactly the mouse delta (+40, -25) — passed against
the real ISO (`"panning explicitly re-verified working ... PASSED"`).

**What a pick captures.** `MapData.decode_tile()` now tags every feature dict
it returns with `"layer"`, `"tile_id"`, `"tile_offset"`/`"tile_declen"` (the
tile's own file offset/decompressed length, already on hand from the
directory entry this method already reads) and `"feature_index"` (this
feature's position within THIS tile's own kept/decoded feature list, i.e.
after the existing drift filter — not a position in any later pooled list).
These are plain dict keys, so they ride along unchanged through
`road_naming.name_features()`'s `dict(feat)` copy and the flat cross-layer
pooling in `ensure_area_loaded()` — a point picked from the final rendered,
multi-layer-pooled `App.features` list can still be traced back to its exact
source tile. `find_nearest_point(features, click_lon, click_lat, center_lat,
scale, max_px=POINT_PICK_RADIUS_PX=10.0)` (a plain, dependency-free scan over
the already-in-memory point lists — deliberately not a spatial index, since a
pick happens once per click, not once per redraw) measures distance in the
SAME pixel-space metric `project_point()` already uses (longitude scaled by
`cos(center_lat)` before multiplying by `scale`), so a flat pixel-radius
cutoff is meaningful regardless of latitude/zoom; it returns `None` (not an
error) when nothing is within range. `canvas_to_lonlat()` is the exact
algebraic inverse of `project_point()` + `App._to_canvas()`'s
centering/pan offset, verified by round-tripping three different
`(lon, lat)` values through `project_point()` then back through
`canvas_to_lonlat()` to within `1e-9` degrees.

A successful pick's full identifying-info dict:
```
{"layer", "tile_id", "tile_offset", "tile_declen", "feature_index",
 "feature_byte_offset",  # decode_features()'s own "offset" field: this
                         # feature's block start, in bytes, within the
                         # DECOMPRESSED tile -- a genuine bonus byte-level
                         # locator, not just tile/feature-index bookkeeping
 "point_index", "lon", "lat", "name", "number"}
```
Real example from this session's own test run against the actual ISO
(a real point near the Albania/Macedonia border area, from the Tirana-area
test view):
```python
{'layer': 'mg4', 'tile_id': 2075, 'tile_offset': 5666672, 'tile_declen': 3433,
 'feature_index': 1, 'feature_byte_offset': 776, 'point_index': 0,
 'lon': 20.43368, 'lat': 41.10615, 'name': None, 'number': 1}
```
(`name` is `None` here because this particular point's vertex range had no
`eeu.rd` match within tolerance — road_naming's own documented, expected
"unlabeled connecting geometry" case, §3.9 — not a bug in the pick.)

**UI**: each pick is numbered (incrementing per session), drawn on the
canvas as a magenta ring + number label (positioned from the pick's own
stored `(lon, lat)`, drawn LAST in `_redraw()` on top of everything
including the center marker, so marks stay correctly placed across every
future pan/zoom regardless of which tiles happen to be pooled at redraw
time — independent of `self.features`), and appended as a plain-text row to
a new `tk.Text` panel (`App.points_text`, scrollable, left in normal/
editable Tk state deliberately so ordinary mouse-drag selection and Ctrl+C
copy work exactly like any other text widget — Tk's DISABLED state blocks
selection in some Tk versions, and this panel is a scratch reporting surface
the user copies FROM, not a source of truth read back by the app). A
"Clear points" button (`App.on_clear_points()`) resets the running list/
counter and the panel back to just its header; picks are also cleared
automatically on a fresh "Open Map ISO" (a previous ISO's layer/tile_id
numbering is meaningless for a different disc). A miss (click further than
`POINT_PICK_RADIUS_PX` from every rendered point) is a plain status-bar
message, not an error or a crash.

**Real test evidence (not just design description), against the actual ISO
(`CD_8555.ISO`), `test_map_viewer.py`**:
- Pure-function checks (no ISO needed): `canvas_to_lonlat()` exact-inverse
  round-trip for three different points; `find_nearest_point()` against a
  small synthetic feature list correctly resolves an exact-coordinate click
  to the right layer/tile_id/feature_index/point_index/name, correctly
  reports `name=None` for a point in an explicitly-unnamed vertex range
  (not conflating "no match" with a crash/omission), correctly returns
  `None` for a click far from every point, and correctly still resolves a
  click a few pixels off-target (within `POINT_PICK_RADIUS_PX`) to the same
  point — all passed.
- Real end-to-end pick against the live Tirana-area view (all 5 layers
  pooled, `mp0` already loaded by this point in the test): a coordinate
  PROVABLY UNIQUE across the whole pooled `app.features` set was selected
  first (real finding while writing this test, see below), its exact
  on-screen pixel position computed via `App._to_canvas()`, a real
  `<Button-3>` event simulated at that pixel, and `App._on_point_pick()`'s
  resulting pick checked field-by-field against that feature's own real
  tags — exact match on layer/tile_id/tile_offset/tile_declen/
  feature_index/point_index, `(lon,lat)` within `1e-6`, and `name` matching
  `road_naming`'s own `named_ranges` result. The picked-points text panel
  was independently confirmed to contain a readable row with the real
  layer/tile_id/name. A miss-click far from any rendered point was
  confirmed to add nothing. `on_clear_points()` was confirmed to empty both
  the in-memory list and the panel. Passed against the real ISO:
  `"real click-to-identify: known point correctly identified end to end,
  panel row confirmed -- PASSED"`.
- **A real subtlety found while writing this test, not swept under the
  rug**: an earlier version of this test picked a fixed point (a feature's
  own first vertex) as the pick target and asserted the resulting pick's
  `layer` matched that specific feature — this FAILED on the first real run
  (`AssertionError`, picked `layer='mp0'` when the target was `layer='mg4'`)
  because that particular coordinate happened to be an exact anchor point
  shared by BOTH a coarse (`mg4`) and a fine (`mp0`) layer's own decoded
  geometry — a real, legitimate consequence of v4→v5's multi-layer point
  pooling (the same real road sampled at multiple generalization levels can
  legitimately share exact vertices), not a bug in `find_nearest_point()`
  (which correctly found A point within radius — just not necessarily the
  specific layer's copy of it, since coincident-coordinate ties are
  order-dependent by design, `<=` in the comparison). **Fixed by making the
  test itself pick a coordinate provably unique across the whole pooled
  feature set** (counting exact-coordinate occurrences across every pooled
  point first) before using it as a target — a real finding worth knowing
  for a future session doing precise connectivity reporting: if the user
  clicks a point that happens to sit exactly on a shared coarse/fine-layer
  anchor, the reported `layer`/`tile_id` is whichever layer's copy
  happened to be checked first/closest, not necessarily "the layer the user
  meant" (there usually isn't a meaningful difference for the user's own
  reporting purposes, since both copies represent the same real point).
- Full existing suite re-verified passing end to end (`py test_map_viewer.py`,
  exit code 0): all prior sections (§10 "v2→v3" through "v5→v6", search,
  dynamic loading, real names/cities, GUI construction/no-layer-dropdown,
  multi-layer pooling, cumulative scale-stacking, zoom-triggered reload,
  redraw timing) still pass unchanged, confirming this is a pure addition.
  `test_core.py` (the separate editing tool's own suite) re-run unmodified,
  exit code 0, `ALL TESTS PASSED` — fully unaffected, as expected (this
  session never touched `rns510_core.py`/`rns510_gui.py`).

**Limitations, stated honestly.**
- No spatial index for the nearest-point scan — a plain per-click scan over
  every currently-pooled point (up to ~48K+ points at a dense, fully-
  zoomed-in, all-5-layers Sofia-style view per "v5→v6"'s own measurements).
  Not measured to be slow enough to matter for a once-per-click interaction
  (unlike `_redraw()`, which runs far more often and was the actual subject
  of v3→v4's perf fix) — deliberately not over-engineered per the task's own
  "this happens once per click, not per redraw" framing.
- As documented above, a click that lands exactly on a coordinate shared by
  two layers' own decoded copies of the same real point resolves to
  whichever copy is closer/first-scanned, not a specific "preferred" layer
  — harmless for the user's own reporting purpose (both describe the same
  real point) but worth knowing if a future session wants to reconcile a
  reported pick against a SPECIFIC layer's own topology table bytes.
  Practically: report BOTH the picked point's number/coordinate from the
  panel and, if in doubt, note which zoom level you were at when you
  clicked it.
- Picks are pure client-side/in-memory state (not persisted to disk) — the
  user needs to read/copy the panel text into a chat message before closing
  the app or clicking "Clear points" if they want to keep it.

### v7 → v8: connecting line between picks + undo-last-point (this session)

**User request** (verbatim, made while mid-way through reporting a real
ground-truth connectivity path): *"can you make it so line is drawn between
the points i select and an ability to delete the last point only."*

Two small additions to the click-to-identify feature (`_redraw()` and the
picked-points panel logic in `rns510_map_viewer.py`):
- A dashed line is now drawn connecting `self.picked_points` **in pick
  order** (the order the user clicked them, i.e. by pick number) whenever
  2+ points are picked — immediate visual feedback so the user can see and
  confirm the path they're specifying before reporting it back in chat,
  rather than only seeing isolated numbered rings. Drawn from each pick's
  own stored (lon, lat) like the rings already were, so it stays correctly
  positioned across pan/zoom/reload.
- A new "Undo last point" button (`App.on_undo_last_point()`) removes only
  the MOST RECENT pick — not the whole set like "Clear points" already did
  — for correcting a single mis-click without starting over. It also
  rewinds the running pick-number counter, so the next new pick reuses the
  undone point's number rather than leaving a gap (undo #7, then the next
  click becomes #7 again, not #8). The panel is fully rebuilt from
  `self.picked_points` on undo (`_rebuild_points_panel()`) rather than
  surgically deleting one `Text` widget line, since the pick list is always
  small and a full rebuild can't get the line-indexing wrong.

Tested end to end against the real ISO (`test_map_viewer.py`): picking a
2nd real point confirms a `"line"`-type canvas item now exists (none did
with only 1 pick); `on_undo_last_point()` is confirmed to remove exactly
the 2nd pick and leave the 1st untouched (not just "a" pick), confirmed to
make the connecting line disappear again (back under 2 points), confirmed
to shrink the text panel, and confirmed to rewind the counter (re-picking
the same point afterward reuses its original number). Full suite —
`test_map_viewer.py` and `test_core.py` — re-run and passes unchanged.

### v8 → v9: per-layer visibility checkboxes, as a restriction on top of the automatic zoom stacking (this session)

**The explicit user request that prompted this** (verbatim, made mid-way
through reporting real click-identified ground-truth connectivity data for
the still-unsolved topology-table problem — §3.6/§8 — but this change
itself is unrelated to that data): *"add an option for me to see only
selected layers, with checkboxes so i can do it more precisely."* Their
concrete workflow problem: since coarser/finer `MAP_COMPRESSED` layers
represent the same real roads, their points often render at (or very near)
the same real-world location, which makes it hard to right-click precisely
on a point from ONE SPECIFIC layer for the click-to-identify ground-truth
workflow ("v6 → v7"/"v7 → v8") — a right-click can land on whichever
layer's dot happens to be nearest, not necessarily the one the user meant.

**What changed, and the one design choice that matters.** Five
`tk.Checkbutton`s (`mg4`/`mg3`/`mg2`/`mg1`/`mp0`), labeled "Show layers:",
added to the search panel just below the coordinate-entry row — all
CHECKED by default (`App.layer_visible`, a `{layer: tk.BooleanVar(True)}`
dict). Critically, checking a box does **NOT** force a layer to always
render regardless of zoom — that would silently reintroduce the exact cost
v6 was built to avoid (paying `mp0`'s full point count while zoomed out).
Instead, `MapData.ensure_area_loaded()` gained an `allowed_layers` param:
when given, the final pooled/rendered set is
`layers_for_scale(scale, available) ∩ allowed_layers` — a pure
**restriction**, never an override. Unchecking a box always excludes that
layer, at every zoom; leaving every box checked (the default) makes
`allowed_layers` equal to the full `ALL_LAYERS` set, which is a no-op
intersection — so a fresh app instance, or anyone who never touches the
checkboxes, gets byte-for-byte the same v6 behavior as before.
`allowed_layers=None` (the default parameter value, used by every
pre-existing non-GUI call site and test) means "no restriction at all,"
so nothing outside `App` had to change. Toggling any checkbox calls
`App._on_layer_visibility_changed()`, which reuses the exact same
`_maybe_reload_viewport(force=True)` path the `mp0`-ready fold-in and
jump/search already use, so the visible layers update immediately, without
needing a pan/zoom first.

**Why intersection-not-override, concretely.** An override design ("checked
= always show, regardless of zoom") was considered and rejected: it would
mean checking `mp0` while zoomed all the way out silently pays `mp0`'s
worst-case decode/geo-index/redraw cost (the exact 34-55s geo-index build
and the 35,644-point/0.85s Sofia-area redraw both already measured in
"v5 → v6"/"v4 → v5") even though the user is nowhere near street level —
reintroducing v5's "always pool everything" regression by the back door,
just gated by a checkbox instead of unconditionally. The chosen design
keeps `layers_for_scale()` as the sole source of "what zoom wants," and the
checkboxes as a strictly-narrower user override on top of it — "hide a
layer I don't want to click on right now," never "show a layer this zoom
level wouldn't otherwise want."

**Real-ISO test results** (`test_map_viewer.py`, against `CD_8555.ISO`,
same Sofia bbox `lon=23.40102/lat=42.65533, ±0.05°` used throughout "v5 → v6"):
- **Default (all-checked) behavior confirmed byte-for-byte unchanged from
  v6**: `allowed_layers=None` and, explicitly, `allowed_layers=set(ALL_LAYERS)`
  (the literal "every checkbox checked" GUI state) both reproduce the exact
  pre-existing reference numbers — 500→`['mg4']`/**501** pts,
  1,500→+`mg3`/**1,804** pts, 4,000→+`mg2`/**5,316** pts,
  10,000→+`mg1`/**12,658** pts.
- **Unchecking `mg1` at scale=10,000** (where it would normally be
  included): pooled set restricts to `['mg4','mg3','mg2']`, **5,316**
  points — exactly the same count already measured at scale=4,000 for this
  identical bbox (since `layers_for_scale(4000)` is that same 3-layer set)
  — a real, exact **12,658 → 5,316** drop (mg1's own precise contribution),
  not just "fewer points."
- **Unchecking `mp0`** after it's ready AND the scale is street-level
  (20,000, `≥ MP0_MIN_SCALE`): excluded entirely (**12,658** points, i.e.
  identical to the pre-mp0-ready 4-fast-layer total) even though it is both
  available and scale-eligible. **Re-checking it** restores its exact
  **35,644**-point contribution (48,302-point pooled total) via a pure
  cache hit — `new_tiles == 0` — since those tiles were already decoded
  earlier in the same session/test.
- **Empty `allowed_layers`** (hypothetically every box unchecked) pools
  nothing and does not crash.
- **End-to-end through the running `App`, not just `MapData`**: flipping a
  real `tk.BooleanVar` and calling the checkbox's own bound command
  (`App._on_layer_visibility_changed`) was confirmed to start a real
  `BackgroundTask` (`App._area_loading` flips `True` synchronously) at a
  live Sofia-area view — unchecking `mg1` dropped `app.data.covered_layers`
  from `['mg4','mg3','mg2','mg1']` to `['mg4','mg3','mg2']` and
  `app.features`'s real point count from **9,335 → 3,705**; re-checking it
  restored both to their exact original values.
- Full suite re-run and confirmed passing, including everything predating
  this change (pan/zoom, click-to-identify + undo + connecting line,
  search, the zoom-triggered cumulative-layer reload, no-`Combobox`
  widget-tree check) — this was a pure addition, nothing existing was
  restructured. `test_core.py` (the separate editing tool) re-run
  unmodified and still passes, including its full write/round-trip
  verification against a real output ISO — expected, since it shares no
  code path with the viewer.

**Limitations, stated honestly.**
- The checkboxes are a client-side restriction on an already-computed
  cumulative set, not a way to add detail earlier than a zoom level would
  otherwise provide — checking `mp0` while zoomed out still shows nothing
  from it, by design (see above). Some users' first instinct may be to
  expect "check the box = show me that layer now," so the checkboxes are
  paired with the SAME zoom-cumulative behavior as before, not a truly
  independent per-layer toggle.
- No visual indicator distinguishes "a layer is empty because nothing
  decoded there" from "a layer is empty because it's unchecked" or "because
  the zoom level doesn't want it yet" — the status bar's tile/layer-count
  message after a reload is the only feedback, same as before this session.

### v9 → v10: "Draw connected roads" — real topology-derived lines, not dots (this session)

**User request** (verbatim, immediately after the topology-table breakthrough
landed — §3.6/§8): *"add a checkbox to draw real connected roads and make it
checked by default."*

A new checkbox, "Draw connected roads" (`App.connected_roads_var`, next to
the "Show layers" row), **checked by default**. This is fundamentally
different from the old, removed line-rendering (README "v3 → v4") that
connected consecutive decoded points and produced wrong "teleport" lines —
this uses `map_compressed_reader.resolve_topology_adjacency()`'s real,
derived connectivity (§3.6/§8), which is not the same thing as point
sequence order. For every feature with a high-confidence adjacency
resolution, real edges are drawn as `canvas.create_line()` segments between
their true endpoints; any feature without high confidence falls back to
the existing per-vertex dot rendering for just that feature — never a
guessed line. Unchecking the box reproduces the exact pre-existing
dot-only rendering, a fully reversible toggle. Each tile's
`resolve_topology_adjacency()` result is cached per-layer alongside its
already-cached decoded features (`MapData`'s per-tile adjacency cache), so
it's computed once per tile, not on every redraw.

**Ground-truth canvas verification** (not just data-level, per this
project's standard — actual `canvas.create_line()` items checked for
correct endpoints): the `mg2` tile 20597 street (17 points) renders
**16/16** human-verified real edges as correct canvas lines (213 total
resolved edges drawn); the `mp0` tile 91124 loop renders **17/18** (331
total resolved edges drawn) — one better than the 16/18 recovered at the
raw-data level in the topology-cracking session, i.e. rendering didn't lose
anything and may have picked up one more via a slightly different edge
traversal. Toggling the checkbox off on the same loaded tile reproduces the
exact prior dot-only output (205 dots, 0 lines) — confirmed reversible, not
just assumed.

**Performance — measured honestly, a real cost exists at maximum density.**
`resolve_topology_adjacency()` does real extra work per tile (a
`decode_topology()` parse plus an auto-shift-detection sweep) — measured
directly: computing it for every tile in a 59-tile Sofia-area query took
1.11s vs. 0.10s without (an 11x per-load cost, though this is a one-time
per-tile cost thanks to caching, not paid again on re-pan/re-zoom of the
same tiles). The `_redraw()` cost itself (drawing time, separate from
computing adjacency) was also measured at two zoom levels for the same
Sofia area:
- Fast layers only (scale=1,500, 1,804 points, 11/12 features high-confidence):
  connected-roads ON 0.074s vs OFF 0.065s — negligible difference.
- All 5 layers incl. `mp0` (scale=20,000, 48,302 points, 161/257 features
  high-confidence): connected-roads ON **2.56s** vs OFF **0.80s** — a real,
  noticeable ~1.75s slowdown at the densest possible view (mostly the sheer
  number of line-drawing canvas calls at that point count, not the cached
  adjacency lookup itself). **No mitigation was added this session** — the
  checkbox ships as-is with this honestly-disclosed cost at maximum zoom-in
  density; a future session could investigate capping/batching line draws
  or skipping connected-roads rendering above some point-count threshold if
  this proves bothersome in practice.

**How low-confidence features look in practice**: mixed in the same view —
at the all-5-layers Sofia measurement, 161 of 257 pooled features (63%)
resolved with high confidence and rendered as real connected lines; the
remaining 96 (37%) rendered as dots, same as before this session, right
alongside the connected ones. This is expected and by design, not a bug —
per §3.6/§8, small/simple features and features whose auto-detected
alignment shift doesn't produce a plausible real-world edge distance are
deliberately excluded from line-rendering rather than risk a wrong guess.

Full existing test suite (`test_map_viewer.py`) re-run and passes
unchanged alongside the new checks above — search, pan (unaffected, as
expected, since panning only ever calls `canvas.move` and doesn't care what
was drawn), zoom, cumulative layer stacking, layer-visibility checkboxes,
click-to-identify + connecting-line-between-picks + undo all still work.
`test_core.py` (the separate editing tool) re-run unmodified and passes,
confirming it shares no code path with any of this.

### v10 → v11: "Hide decode garbage" — a toggle for the oscillation filter (this session)

**Context that prompted this**: asked directly whether the viewer shows
every real point or silently drops some, a direct measurement (not a
guess) found real, non-trivial data loss: the oscillation-garbage filter
(`decode_features(trim_oscillation=True)`, §3.6) removed **5.74% of raw
points** in a real Sofia-area sample (2,353 → 2,218 points across 9 mg1
tiles). Most of that is genuine corruption being correctly caught, but the
filter has a confirmed non-zero false-positive rate (§3.6's 80-tile mg4
validation already documents one real named road getting dropped by it),
so some fraction of that 5.74% is real data being discarded along with the
actual garbage — with no way, until now, to see what was being hidden.

**User request** (verbatim): *"lets fix 2, add a checkbox that enables and
disables the filter."*

A new checkbox, **"Hide decode garbage"** (`App.hide_garbage_var`, next to
"Draw connected roads"), **checked by default** (unchanged behavior for
anyone who doesn't touch it). Unchecking it sets
`MapData.trim_oscillation = False` and re-decodes every currently-relevant
tile with `decode_features(trim_oscillation=False)` instead — showing the
RAW, unfiltered points, including whatever the filter would have removed.
This is a genuine re-decode, not a display-only toggle: `decode_features()`
produces different output entirely depending on this flag, so
`MapData.set_trim_oscillation()` resets `tile_caches`/`topo_caches` to
empty per-layer dicts on a real change (a tile decoded under the old
setting is stale and must not be served from cache) — verified directly:
toggling off at a real Sofia view changed the pooled point count from
9,335 to 9,687 (a real, measured +352 points revealed), and toggling back
on restored exactly 9,335. Wired through the same
`App._maybe_reload_viewport(force=True)` path every other checkbox in this
UI already uses.

**Practical use**: this is a diagnostic/inspection tool, not a
recommendation to leave it off — with the filter off, real oscillation
corruption (the "crazy lines" class of bug, though now rendered as
scattered raw dots rather than connected lines) will also reappear
alongside whatever real data was wrongly caught. Comparing the same area
with the checkbox on vs. off is the way to visually judge, tile by tile,
whether the filter's trade-off is acceptable for that specific area.

Full test suite (`test_map_viewer.py`) extended with a real GUI end-to-end
check (toggle off → real background reload → real re-decode → different,
measured point count; toggle back on → exact original count restored) and
re-run in full — all pre-existing checks (search, pan, zoom, cumulative
layer stacking, layer-visibility checkboxes, connected-roads mode,
click-to-identify + undo) still pass unchanged. `test_core.py` (the
separate editing tool) re-run unmodified and passes.

### v11 → v12: Address entry — a real letter-by-letter destination-entry keyboard, live per-letter narrowing from the cracked `.rt`/`.ct`/`.ctr` data (this session)

**Reference photos this session started from** (ground truth for the UI,
reproduced verbatim from the task brief, not pixel-perfect — see below for
exactly where this diverges and why):

- **Photo 1 ("Address entry")**: a screen titled "Address entry" (back-arrow
  top-right) with 4 rows, each a lighter/bordered label box on the left and
  a dark value box on the right: "Country" → "BALGARIA", "City/P.cd." →
  "SOFIA", "Street" → "ZHK LYULIN,LYULIN", "Number" → "785" (this row also
  has an "Intersect." button beside it). Below the 4 rows, a final row of 4
  buttons: "Save", "POI", "Map", "Start".
- **Photo 2 (letter keyboard)**, shown for Country/City/Street: a text field
  at top showing what's typed so far, a small live match-count badge, and a
  back/undo arrow; below that, an alphabetical (not true QWERTY) letter
  grid — "A B C D E F G" / "H I J K L M N" / "Ö P Q R S T U" / "V W X Y Z -
  ÃÄÆ" — plus a numeric/symbol toggle ("$..% 0..9"), a keyboard-layout
  icon, an "ABC/АБВ" (Cyrillic) toggle, backspace, and "OK". **The core
  feature**: letters that can't lead to any valid remaining match are
  visually disabled/greyed out, live, as a real reflection of which
  characters exist as trie children of the current node.

**What's functional vs. decorative** (same established pattern this app
already uses for its RADIO/MEDIA/PHONE/TONE/TRAFFIC bezel buttons):
FUNCTIONAL — the "NAV" bezel button (previously purely decorative) now
opens `AddressEntryDialog`; Country/City/Street rows open `SpellerDialog`,
a real letter-keyboard with LIVE per-letter enable/disable computed from
real cracked data; the Number field (plain text entry); "Start" resolves
the typed address to a real coordinate and jumps the main map there (the
same `App._jump_to()` "search a place, double-click a result" already
uses). DECORATIVE — "Save"/"POI"/"Map" (inside this dialog — the bezel's
own MAP button already does something real), "Intersect.", the numeric/
symbol toggle, the keyboard-layout icon, and "ABC/АБВ" (per this session's
own task guidance not to implement real Cyrillic input) — each reports
what it is via a status label rather than doing nothing silently.

**Known prerequisite tackled first, per this session's task: locating
`.rt`/`.ct`'s true root.** The single-unified-root hypothesis
(`road_index_reader.py`'s own suggested approach — scan early offsets for
a node whose `subtree_size` covers a large fraction of the whole tree) was
tried exhaustively and **directly refuted, not just left unfound**:

- A vectorized scan of every printable-`char_code` position in the whole
  245,698,715-byte `.rt` body for a plausible "near-total-coverage"
  candidate found many that LOOKED enormous (claimed `subtree_size`
  covering 20–99% of the file) but every one was a false positive — a
  non-printable `char_code` (typically the impossible value 65536) landing
  in a low-entropy byte region, not a real node.
- A **fully recursive self-consistency check** (`subtree_size` must equal
  `1 + sum(child subtree sizes)`, recursively, matching the exact
  accounting the original hand-verified D/F/G/M example satisfies) was run
  against 2,089,302 structurally-plausible candidates across the entire
  file. Result: the **largest fully self-consistent subtree found anywhere
  is `subtree_size = 60`** — nowhere close to the ~12.93M total node count
  a real global root would need. This is exhaustive, not "didn't look hard
  enough," evidence that `.rt` (and, by the same cross-check, `.ct`) is
  best modeled as a **forest of many independent subtrees**, not one
  unified trie with a single root — consistent with, and now sharpening,
  the pre-existing "`subtree_size` doesn't always account for 100%"
  caveat.
- **Concrete, directly-demonstrated consequence**: `eeuz.cl` (the flat
  "city list" catalog `.ct` is presumed to be a trie over) was confirmed
  this session to contain an exact entry `"SOFIA"` (record 2,483,612 →
  `eeu.cty` index 230704, the real Bulgarian capital) — but an exhaustive
  search of every `.ct` node starting with 'S' (12,984 candidates,
  checked via both the tolerant children-walk and a raw positional check
  that ignores `subtree_size` bookkeeping entirely) found **zero** paths
  spelling "SOFIA". Real names are genuinely partitioned across shards
  this method cannot guarantee to enumerate exhaustively.
- **Practical resolution — `rt_root()`/`ct_root()`** (new, in
  `road_index_reader.py`/`city_reader.py`): the best validated entry-point
  shard per starting letter (A–Z), found by cross-referencing every leaf
  string reachable from a candidate (existing `rt_walk_strings()`) against
  real vocabulary — `eeu.typ` street-type words for `.rt` (this project's
  own established validation bar), real `eeu.cty` place-name tokens for
  `.ct`. **Concrete "how much better than the old hand-picked node" number,
  reproduced in `test_map_viewer.py` against the real ISO, not just
  asserted**: the old single starting point this project has used since
  `.rt` was first cracked (node 'D' at body offset 65) reaches exactly
  **2** leaf strings; the union of the 26 `rt_root()` entries reaches
  **5,072–5,135** leaf strings (capped at 20,000/letter — the real total
  is at least this many) — a **~2,500x** increase — with **21 distinct,
  independently real** cross-referenced words (SOKAK, CADDESI, ULITSA,
  VULYTSIA, STRADA PROVINCIALE, VIA DEL/DELLA/DELLE, STRASSE, GATVE,
  PROEZD/PRAYEZD, PROVULOK, …). `ct_root()`'s 26-letter union reaches
  5,166 leaf strings with 110 distinct real cross-referenced words
  (RAYON/RAION, SYEL'SAVYET, SOLNECHNOGORSKIY — a real Russian town,
  TUZLA — a real Bosnian city, NOVAYA). Every `rt_root()`/`ct_root()` entry
  is also directly offset-verified (`rt_char()` at the stored offset
  really does decode to that letter).

**The accented/non-ASCII node variant — characterized, not decoded.**
Investigating exactly where the already-known 'A' node (offset 46,
claimed `subtree_size=42`, previously only 12 of 42 validating) breaks
down found a concrete, reproducible byte pattern right at the failure
point: the byte at `node_start + 12` — the first byte of the "3 bytes,
always 0" field, confirmed zero on every other validated node — is **0xDA
(Latin-1 'Ú'), at TWO CONSECUTIVE 19-byte-aligned node positions**
(body offsets 274 and 293) exactly where the accounting fails. This is
concrete positive evidence (not a hand-wave) for the already-hypothesized
"second, wider node variant for accented/non-ASCII edge characters" this
East-Europe dataset clearly needs (Ö/Ã/Ä/Æ are literally in this feature's
own reference photo) — but whether the record stays 19 bytes with this
field repurposed, or is a genuinely different size, was **not** resolved
this session.

**Fail-safe UI design — the explicit, documented tradeoff this gap forces.**
Because real subtrees don't always account for their own children 100%
(above) and real names are genuinely partitioned across shards no single
scan enumerates completely (the SOFIA finding above), confidently
DISABLING every letter absent from a node's found children would
frequently grey out real, valid options. `road_index_reader.
rt_children_with_confidence()` reports whether its walk exactly tiled the
node's claimed `subtree_size` (`complete=True`) or had to stop early
(`complete=False`); `rt_enabled_next_chars()` and the map viewer's keyboard
propagate this: a letter is disabled ONLY when the walk for the current
prefix completed cleanly at EVERY step AND that letter's child genuinely
wasn't found — otherwise every other letter stays enabled. Concretely
tested (`test_map_viewer.py`): the empty-prefix ("nothing typed") state is
always reported `confident=False` (no single node covers every real
starting letter), so no character is ever disabled purely for being
absent from `rt_root()`'s 26 keys; a genuine **confident dead end** was
found via exhaustive DFS from the root shards (prefix `"NL"`, under the
'N' shard) where `confident=True` and every letter is correctly disabled —
notably, naively always taking a node's FIRST child rarely reaches a fully
confident leaf within a reasonable depth (a real, measured finding, not
assumed), so the test (and any future reasoning about this data) needs a
real search, not a single greedy walk, to find one.

**Country (`eeu.ctr`) — fully cracked, no fallback needed.** Quickly
tractable, as hoped: 94-byte SIEMENS header + fixed **43-byte records**,
35 on the reference disc (`byte[0]` sequential index, `bytes[1:36]` UTF-8
name, `bytes[36:39]`/`[39:41]` ISO 3166-1 alpha-3/alpha-2 codes,
2 trailing zero bytes) — see `research/ctr_reader.py`. Directly validated
against this feature's own reference photo: record 19 is **"BALGARIA"**,
codes `BGR`/`BG` — an exact match. Full 35-country East-Europe list
decoded cleanly, including one country listed twice (Russia, once
transliterated "ROSSIYA" and once in Cyrillic "РОССИЯ", both `RUS`/`RU`).

**City — a deliberate hybrid, not a straight `.ct` port.** Given the
"SOFIA is unreachable from `.ct`'s own 'S' shard" finding above, the City
field's live per-letter narrowing is backed by a NEW `city_reader.
PrefixNameIndex` — a sorted, de-duplicated in-memory index over the
already-fully-cracked, exhaustive `eeu.cty` (939,351 real records, no
coverage gaps), built once from the same `CtyCache` this viewer's city
search/labels already use (no extra file I/O). This is exact, not
best-effort: a letter absent from `PrefixNameIndex.enabled_next_chars()`
is a real, confident dead end. `ct_root()` is still fully implemented,
offset-verified, and separately tested on its own terms (per the task's
ask to crack `.ct` "the same way as Street") — it's just not what the
shipped UI's correctness depends on.

**Street — the real `.rt` trie, fail-safe by design.** `MapData.
street_enabled_next_chars()` wraps `road_index_reader.rt_enabled_next_chars()`
directly against the real, lazily-decompressed 245,698,715-byte `.rt` body.
Coverage is honestly partial (see above), so the keyboard leans on the
fail-safe design rather than claiming completeness — and importantly,
**"Start" never depends on the trie for correctness**: `MapData.
resolve_address()` resolves City via `CtyCache.search()` and Street via
`MapProject.search()` (the SAME `.il`/`eeu.rd` search the unified search
box's `[Road]` results already use), preferring a road result inside the
resolved city's own bounding box — reusing already-proven infrastructure
for the one step that must always work, exactly as the task asked.

**A real, previously-latent bug found and fixed by this feature's own
end-to-end test.** `App._jump_to()` — used by search results, coordinate
"Go", AND now this feature's "Start" — was computing `self.canvas.
winfo_width()/winfo_height()` (via `_estimate_scale_for_span()`) and
reading two `tk.BooleanVar`s (`_get_allowed_layers()`,
`connected_roads_var.get()`) **inside `do_load_area()`, i.e. on the
BackgroundTask's WORKER thread** — Tk widget/variable access from a
non-main thread is not safe in general. This had never been exercised by
a prior automated end-to-end test (every existing GUI test drove
`ensure_area_loaded()`/`_maybe_reload_viewport()` directly, with scale
already computed on the main thread) — it's this session's own NAV →
Start test, run under scripted `root.update()` polling rather than a live
`mainloop()`, that first exercised `_jump_to()`'s real threading path and
hit a reproducible hang. **Fixed** by computing `est_scale`,
`allowed_layers`, and `want_adjacency` on the main thread, before the
worker thread starts — `do_load_area()` now only touches `self.data`,
matching every other `BackgroundTask` call site in this file. Re-verified:
the full existing test suite (search, pan, zoom, layer stacking,
click-to-identify, connected roads, hide-garbage) still passes unchanged,
and this exact fix is what makes the new NAV/Start end-to-end test pass
reliably rather than hang.

**Real test evidence** (`test_map_viewer.py`, against `CD_8555.ISO`):
`rt_root()`/`ct_root()` validated as above (offset-verified, ~2,500x more
reachable leaves, 21/110 distinct real cross-referenced words); `eeu.ctr`
35/35 decoded, BALGARIA confirmed; City live narrowing walked through
`"S"`→`"SO"`→`"SOF"`→`"SOFI"` (44,058 → 2,929 → 115 → 38 real matches,
strictly non-increasing, confirming genuine narrowing) with `'A'`
confirmed to remain enabled at `"SOFI"` and at least one letter (e.g.
`'B'`/`'C'`/`'D'`) confirmed disabled; `resolve_address("BALGARIA",
"SOFIA", "", "")` → `(23.32431, 42.69718)`, matching Sofia's real,
already-validated coordinates (§3.8); Country narrowing `"B"`→`"BA"`→
`"BAL"` confirming `'G'` stays enabled to complete BALGARIA; Street's
fail-safe root state and a genuine confident dead end (`"NL"`); and a full
GUI run — `on_bezel_nav()` opens a real `AddressEntryDialog`; the City
`SpellerDialog`'s actual Tk button *widget states* (not just the
underlying data) are confirmed to flip disabled/enabled correctly at every
typed letter, its live match-count badge matches the real count, "OK"
writes "SOFIA" back into the Address entry row; "Start" performs a real
end-to-end `BackgroundTask` jump (`app.busy` toggled, polled to
completion) landing on real Sofia coordinates and closing the dialog; and
every decorative control (Save/POI/Map/Intersect./numeric-toggle/
Cyrillic-toggle/the always-enabled accented keys) confirmed non-crashing
and self-reporting. Full pre-existing suite re-run and passes unchanged
end to end; `test_core.py` (the separate editing tool) re-run unmodified
and passes.

**Limitations, stated honestly.**
- Street's live per-letter narrowing has genuinely partial coverage (the
  forest-not-tree finding above) — a real street name may fail to narrow
  correctly even though it exists somewhere in `.rt`, if it isn't reachable
  from the specific shard `rt_root()` found for its starting letter, or if
  its real trie entry is a `;`-demoted sort-key form (README §3.7) rather
  than the natural typed order. This is disclosed, not hidden, and is
  exactly why "Start" never depends on the trie for the actual resolution.
- Accented-letter input (Ö/Ã/Ä/Æ) and Cyrillic ("ABC/АБВ") are decorative,
  per this session's own task guidance — those keys are always enabled
  (the fail-safe default for anything this project's data can't currently
  validate) but don't affect what's typed.
- The reference photo's exact keyboard layout ("Ö P Q R S T U", no plain
  "O") was deliberately deviated from — a plain "O" was added (with "Ö"
  moved to the decorative accented cluster) because the feature's own
  validation target ("SOFIA") needs a working "O", and the task's own
  guidance prioritizes functional fidelity over pixel-perfect layout.
- `.rt`/`.ct` are decompressed/held fully in memory when the "NAV" screen
  is first opened (245MB/16MB respectively) — lazy (not part of "Open Map
  ISO"), matching this viewer's existing pattern for `mp0`, but a real,
  one-time few-second cost the first time NAV is used.
- Number/"Intersect." don't feed into `resolve_address()` — Start
  resolves City+Street only, matching what `MapProject.search()`/
  `CtyCache.search()` can actually answer; house-number-level resolution
  would need `eeu.rd`'s own still-unresolved header fields (§3.1) or a
  different data source not identified this session.

Non-GUI functional test additions: `test_map_viewer.py` — see this
session's own docstring bullet at the top of the file for the itemized
list; run with `py test_map_viewer.py`.

### v12 → v13: Address entry re-hosted as an embedded screen panel, not a separate OS window (this session)

**The user's explicit correction**, made after seeing a screenshot of
"v11 → v12"'s own implementation (verbatim): *"this shouldnt be a new
window, instead it should show on the nav screen."*

**What was wrong.** `AddressEntryDialog` and `SpellerDialog` (§10
"v11 → v12") were built as `tk.Toplevel` subclasses — real, separate
OS-level windows, floating independently of the simulated unit's own
bezel/screen chrome. This broke the illusion the bezel (§10 "v9 → v10"
and earlier — the whole point of building a fake RADIO/MEDIA/PHONE/TONE/
MAP/NAV/TRAFFIC/SETUP hardware bezel around a glossy-black inset "screen")
exists to create: a real head unit has exactly ONE screen, and every UI
state (map / address entry / letter keyboard) replaces the others WITHIN
it — never as a second window floating on top. It also didn't match any
of the 4 reference photos this feature was built from, each of which
shows one screen area transitioning between states, never two overlapping
windows.

**The fix.** Both classes now subclass `tk.Frame` instead of
`tk.Toplevel`, parented directly to `App.screen_frame` — the SAME
glossy-black inset `tk.Frame` that has, until now, only ever shown
`canvas_frame` (the map canvas) + `status_bar` packed inside it. Each
panel:
- Is built with ordinary `pack()`-based internal layout, exactly as
  before (no widget content changed) — only the base class and the
  parent widget changed.
- Shows itself at the END of its own `__init__` via
  `self.place(relx=0, rely=0, relwidth=1, relheight=1)` then `self.lift()`
  — `place()` and the pre-existing `pack()` geometry of `canvas_frame`/
  `status_bar` coexist fine in the same container (Tk raises no error
  mixing geometry managers across *siblings*, only within the same
  widget's own children), and `screen_frame`'s own size continues to be
  driven entirely by its packed children, unaffected by an overlay placed
  on top of them.
- Is dismissed by plain `.destroy()` (the back-arrow button, `SpellerDialog`'s
  OK/backspace-to-empty, or `AddressEntryDialog`'s "Start" on success) —
  since the map view underneath was only ever COVERED, never hidden or
  rebuilt, destroying the overlay reveals it again immediately, with its
  center/zoom/pan/loaded features completely untouched. No manual "restore
  the canvas" step exists anywhere in this fix, by design: there is
  nothing to restore.
- `SpellerDialog` is now a SIBLING of `AddressEntryDialog` in
  `screen_frame` (previously a child `Toplevel` of the `AddressEntryDialog`
  `Toplevel`), shown on top of it via the exact same place()+lift()
  mechanism — clicking Country/City/Street covers Address Entry with the
  keyboard screen; OK/back reveals Address Entry again underneath, since
  it was never destroyed, just covered.
- `AddressEntryDialog.destroy()` is overridden to also tear down
  `self.active_speller` first if one is somehow still open — a cheap
  safety net for a state that shouldn't be reachable in normal use (OK/
  backspace-to-empty already closes the speller before Address Entry's
  own buttons become clickable again), not a behavior change.

**The NAV bezel button** (`App.on_bezel_nav()`) needed NO changes at
all — it already just constructed `AddressEntryDialog(self)`, and a
`tk.Frame` subclass's constructor works identically from the caller's
point of view; the class itself now shows a panel instead of opening a
window. Likewise `_on_start()`'s existing `self.destroy()` call (closing
Address Entry on a successful "Start") needed no changes — it now removes
the overlay instead of closing a window, revealing the freshly-jumped map
underneath exactly as intended.

**Real test evidence** (`test_map_viewer.py`, against `CD_8555.ISO`),
not just code inspection — every check below counts real
`tk.Toplevel` instances across the ENTIRE widget tree (`root` down),
not just `AddressEntryDialog`'s own would-be parent:
- Baseline `tk.Toplevel` count across the whole widget tree was
  established before opening Address Entry, and re-checked identical
  (never incremented) after: opening Address Entry via the NAV bezel
  button, opening the City speller, confirming "SOFIA" via OK, running
  "Start" end to end, opening a second Address Entry + Street speller for
  the decorative-controls check, and after the entire flow finished — six
  separate checkpoints, all confirming zero new `tk.Toplevel` windows at
  any point.
- The panel returned by `on_bezel_nav()` was confirmed to be a real
  `tk.Frame` (explicitly NOT a `tk.Toplevel`), found among
  `App.screen_frame.winfo_children()` (i.e. actually embedded in the
  simulated screen, not floating elsewhere), and `winfo_ismapped()`-true
  (actually visible), both for `AddressEntryDialog` and for the City/
  Street `SpellerDialog` panels.
- **Map-state preservation, checked explicitly across the show/hide
  cycle**: `(center_lon, center_lat, scale, pan_x, pan_y, len(features))`
  was snapshotted before opening Address Entry, confirmed byte-for-byte
  identical immediately after showing the panel (proving the overlay
  doesn't disturb the map underneath), and confirmed byte-for-byte
  identical again after destroying it (proving dismissal doesn't need to
  — and doesn't — do anything extra to "restore" the map).
- **The full pre-existing NAV → City speller → Start → real-Sofia-jump
  flow from "v11 → v12" re-verified working unchanged through the new
  embedded presentation**: live per-letter enable/disable widget states
  through `"S"→"SO"→"SOF"→"SOFI"→"SOFIA"`, the live match-count badge,
  OK writing the value back into the Address Entry row, and `"Start"`
  performing a real end-to-end `BackgroundTask` jump landing on real
  Sofia coordinates (23.32431, 42.69718) — all identical to "v11 → v12"'s
  own results, since none of the underlying data/logic (`resolve_address()`,
  the tries, `PrefixNameIndex`) was touched, only how the UI is hosted.
  After `"Start"`, the map canvas was confirmed `winfo_ismapped()`-true
  again (the screen fully restored) with no leftover Address
  Entry/Speller panel anywhere in `screen_frame`.
- Full pre-existing suite (search, pan, zoom, cumulative layer stacking,
  layer-visibility checkboxes, connected-roads mode, hide-decode-garbage,
  click-to-identify + undo + connecting line) re-run and passes unchanged
  — a pure presentation-layer refactor, confirmed not to have disturbed
  anything else. `test_core.py` (the separate editing tool) re-run
  unmodified and passes, including its full write/round-trip verification
  against a real output ISO.

**Limitations, stated honestly.**
- Because each panel now fills the ENTIRE screen area
  (`relwidth=1, relheight=1`) rather than a small fixed-size window
  (`460x420` for the old `AddressEntryDialog` Toplevel), the on-screen
  proportions differ from "v11 → v12"'s dialog — a deliberate consequence
  of "replace the whole screen," not a bug, but it means the layout reads
  more spread-out/larger than the original reference-photo-sized popup
  did. No attempt was made to cap the panel to a smaller centered region
  within the screen, since a real head unit's address-entry screen also
  occupies its whole display, not a popup within it.
- The theoretical "Speller left open while somehow reaching an Address
  Entry button" state that `AddressEntryDialog.destroy()`'s override
  guards against isn't actually reachable through the UI as built (the
  speller panel covers Address Entry's own buttons entirely while open),
  so that guard is untested-because-unreachable defensive code, not a
  case with its own real-ISO test evidence.
- Nothing else about this feature's own real logic (root-finding, live
  enable/disable computation, `resolve_address()`, country/city/street
  data loading) was touched or re-derived this session, per the task's
  own explicit scope — see "v11 → v12" above for that write-up, unchanged.

### v13 → v14: Country → City → Street scoping, matching real nav UX (this session)

**The user's explicit correction** (verbatim): *"the ways that real nav
works is you select a country then you select a city only from that
country then you select an adress only from that city sooo, dont display
all cities and all streets."*

**What was wrong.** "v11 → v12"'s Address Entry City speller searched ALL
939,351 `eeu.cty` records regardless of the selected Country, and the
Street speller searched the whole `.rt` character-trie regardless of the
selected City. This doesn't match how a real nav unit's destination search
works (country narrows the city list, city narrows the street list) and
meant a same-named city/street in a completely unrelated country could
surface as a candidate.

**Country → City: `eeu.cty`'s "country_tag" field, CRACKED this session.**
§3.8 already documented `bytes[57:59]` as "a candidate coarser country/
region tag... does NOT match `eeu.ctr`'s own row index" — real and
structured, but not tied to anything. This session cracked it properly,
per the task's approach (a): a full-file scan of the reference disc's
939,351 records finds **exactly 35 distinct `country_tag` values** — the
same count as `eeu.ctr`'s own 35 rows, not a coincidence. Rather than
assume the tag equals `.ctr`'s row index (already refuted) or invent a
new numbering, `research/city_reader.py`'s new `build_country_tag_map()`
builds the mapping **empirically**: it computes each tag group's robust
(median) representative-point centroid plus a Cyrillic-script fraction
from a small name sample, then greedily matches each group to the real
`eeu.ctr` country whose approximate real-world centroid (ordinary public
geography, not anything from the disc) is closest — special-casing the
one case geography alone can't resolve (`eeu.ctr` lists Russia twice, once
transliterated and once in Cyrillic, both with the identical real-world
centroid) by matching each tag group's own script to whichever `eeu.ctr`
row's name uses that script.

**Validated, this project's standard**: the greedy nearest-centroid
assignment produces a clean **35/35 bijection** on the reference disc (no
tag left over, no country left over). Cross-referencing 17 known real
cities against their OWN `eeu.cty` record's `country_tag`, resolved through
this mapping: **17/17 correct**, spanning countries already validated
elsewhere in this project (Tiranë→Shqipëria, Timișoara/Iași/București→
România, Sofia→Balgaria, Chișinău→Moldova) plus a fresh batch specifically
chosen to stress-test geographically tight neighbors where a wrong
nearest-centroid assignment would be easy to get away with unnoticed —
Ljubljana→Slovenija, Zagreb→Hrvatska, Sarajevo→Bosna i Hercegovina,
Wien→Österreich, Praha→Česko, Bratislava→Slovensko, Budapest→Magyarország,
Podgorica→Crna Gora, Skopje→P.Jugoslovenska Republika Makedonija,
Beograd→Srbija, Warszawa→Polska — including correctly keeping Kosovo
(tag 201, a separate ~482-record group covering real Kosovo towns like
Gjakovë) distinct from Serbia (tag 402, ~5,830 records) even though
`eeu.ctr` itself gives Kosovo Serbia's own ISO alpha-2 code "RS" (§10
"v11 → v12"'s `ctr_reader.py`). `MapData.city_name_index_for_country()`
builds a `city_reader.PrefixNameIndex` scoped to one country's own tag
group (lazily, cached forever per tag): real measured example, Bulgaria's
scoped index is **6,009 names** vs. the global **616,483** (~100x smaller),
contains real "SOFIA", and does NOT contain "TIRAN" (Albania's own
590-name scoped index has the exact reverse: contains "TIRAN", not
"SOFIA").

**City → Street: the selected city's own padded `eeu.cty` bbox joined
against real `eeu.rd` coordinates.** There is no known direct "which city
does this street belong to" field anywhere in the street/road data (§3.7's
`.rt`/`.rl`/`.prl` catalog has no city cross-reference either). The
practical, buildable approach per the task: `MapData.street_names_for_city()`
takes the selected city's own real `eeu.cty` bounding box (§3.8, already
cracked), pads it by `CITY_STREET_PAD_DEG` (0.15°, ~15-17km at this
dataset's latitudes — `eeu.cty`'s own bbox is documented as tight/
administrative, not necessarily covering a city's whole built-up area, so
a fixed padding margin was chosen empirically rather than using the bare
box), and reuses the ALREADY-BUILT `road_naming.RdCache` (built once at
`load()` time for the map's own road-name labeling, §3.9) to collect every
distinct real `eeu.rd` name whose own coordinate falls inside that padded
box — a numpy bbox mask plus a small Python loop, no new file I/O.
`MapData.street_name_index_for_city()` wraps this in a `PrefixNameIndex`,
cached per resolved city. This is actually a genuine UPGRADE over the old
global `.rt`-trie narrowing, not just a restriction: it's an exact,
always-correct name list (like City's `PrefixNameIndex`), whereas `.rt` is
a documented-partial forest of shards (§3.7).

**Validated against real data**: for Sofia (`eeu.cty` record 230704),
`street_names_for_city()` returns **7,751** distinct real street names in
its padded bbox, including the real, well-known **"VITOSHA"** (Vitosha
Boulevard); Tirana's own scoped set (**590** names, `eeu.cty` record
220303) includes real Albanian street names not shared with Sofia's (e.g.
**"RAMAZAN SHIJAKU"**), and — checked in both directions — Sofia's
"VITOSHA" is correctly absent from Tirana's scoped set and Tirana's
"RAMAZAN SHIJAKU" is correctly absent from Sofia's.

**Wiring into the UI, and the required-order choice.** Real nav UX
requires picking in order (country before city before street), and the
three Address Entry fields are already presented top-to-bottom in exactly
that order, so matching the real unit's own required order was the
easy, natural choice here (over silently falling back to an unscoped
search): `AddressEntryDialog._open_speller()` now refuses to open the City
speller until a Country resolves to a real `eeu.ctr` entry, and refuses to
open the Street speller until the City field has ANY text — both refusals
show a plain status-bar message, not an error. Street is deliberately
LESS strict about VALIDITY than City: it only requires the City text to be
non-empty, not that it already resolves to a real place — `SpellerDialog.
_backing_index()` calls `MapData.street_name_index_for_city()`, and if
that returns `None` (city text doesn't resolve to a real `eeu.cty` record,
or resolves but has zero real `eeu.rd` coordinates in its padded bbox),
`_recompute()` falls through to the ORIGINAL global `.rt`-trie fail-safe
path (`street_enabled_next_chars()`) instead of hard-blocking the field —
graceful degradation for a case this project's own reverse-engineering
limits can't rule out, per the task's explicit "degrade gracefully" option.
`resolve_address()` (the final "Start" resolution) was also upgraded to
prefer a city match inside the given Country when one resolves
(`MapData.resolve_city_record(city_name, country_rec=...)`), so a city
name that exists in more than one country no longer risks resolving to the
wrong one.

**Real-ISO test evidence** (`test_map_viewer.py`, against `CD_8555.ISO`):
non-GUI sections "8h-viii"/"8h-ix" reproduce every number above directly
against the live ISO (the 35/35 bijection, a 16-known-city cross-check
(the automated test's own subset of the 17-city validation above),
the Bulgaria/Albania scoped-index sizes and cross-exclusion, the Sofia/
Tirana street-set sizes and cross-exclusion); the GUI section re-drives the
NAV → City speller → Street speller → Start flow with a real Country
("BALGARIA") selected first, confirming the on-screen match-count badge
and per-letter enabled/disabled key states now reflect the SCOPED
Bulgaria/Sofia data (not the old global counts), confirms the City speller
refuses to open with no Country selected and the Street speller refuses to
open with no City text (both via a real status-bar message, not a crash),
and confirms "Start" still lands on real Sofia coordinates end to end.
Full pre-existing suite (search, pan, zoom, layer checkboxes, connected-
roads, hide-garbage toggle, click-to-identify, the embedded panel
mechanics from "v12 → v13") re-run and passes unchanged. `test_core.py`
(the separate editing tool) re-run unmodified and passes.

**Limitations, stated honestly.**
- `build_country_tag_map()`'s 35 reference centroids (`REF_CENTROID` in
  `city_reader.py`) are rough (capital-city-ish) approximations, not
  verified bounding polygons — sufficient here because the reference
  disc's 35 real tag groups turned out to be geographically well-separated
  (confirmed by the clean 35/35 bijection and 17/17 city cross-check), not
  because the method is inherently immune to two very close countries. The
  greedy nearest-centroid assignment is also not a globally optimal
  bipartite match (no `scipy` in this environment) — it happened to be
  correct for all 35 groups on the reference disc, but a hypothetical
  future disc with less geographic separation could need a real optimal
  assignment (`scipy.optimize.linear_sum_assignment`) instead.
- `CITY_STREET_PAD_DEG` (0.15°) is an empirical choice, not derived from
  any field in the data — a real street that legitimately crosses a city's
  padded bbox boundary (e.g. a long arterial road connecting two nearby
  towns) could in principle be excluded from one city's scoped list and
  included in a neighbor's, or vice versa near the boundary; not observed
  as a concrete problem in this session's testing, but not proven absent
  either. A future session could make this configurable per-city (e.g.
  scaled by the city's own bbox size) if a real case is found needing it.
- Street's "city text non-empty but doesn't resolve" graceful-degradation
  path was exercised by code review and the `street_name_index_for_city()`
  return contract, not by a dedicated real-ISO test of an actually-
  unresolvable city name (every city name used in this session's testing
  does resolve) — the fallback function itself (`street_enabled_next_chars()`)
  is the SAME already-validated path "v11 → v12" tested directly, so the
  risk surface is narrow (just the `is None` branch selection), but stated
  here rather than silently assumed correct.
- `resolve_city_record()`'s country-preference logic only helps when a
  Country was actually selected/resolves; `resolve_address()` called with
  an empty/unresolvable country string (e.g. a very old caller, or Street-
  only "Start" flows) behaves exactly as before this session — unscoped
  city substring search, first-hit-wins — which is unchanged, pre-existing
  behavior, not a new gap.

### v14 → v15: Street's last documented fallback made exhaustive (this session)

**The user's request** (verbatim, quoting an older, now partly-stale
summary of this project's known gaps, then asking): *".rt/.ct are forests
of shards, not fully connected trees -- some real entries are unreachable
(worked around for City by using .cty directly; Street still has
documented partial coverage). can we do something about this?"*

**What the actual remaining gap was, precisely (not what the old summary
implied).** By "v13 -> v14" (previous section), Street search was already
mostly fixed: the NORMAL path (a City that actually resolves) uses
`MapData.street_name_index_for_city()`, an exact `city_reader.
PrefixNameIndex` built from real `eeu.rd` coordinates inside the selected
city's own bounding box -- no `.rt` involved, no coverage gap. The user's
quoted summary was describing the state BEFORE that fix, which by this
session was already stale. Investigation (reading `SpellerDialog.
_backing_index()`'s own docstring, which already documented this
precisely) found the ACTUAL remaining gap was narrower and more specific
than "Street still has documented partial coverage": it was exactly ONE
fallback path -- `street_name_index_for_city()` returning `None` (a City
that doesn't resolve to a real `eeu.cty` record, or resolves but has zero
nearby `.rd` coverage) -- which fell through to `MapData.
street_enabled_next_chars()`, the real but genuinely partial `.rt`
character-trie (§3.7: a forest of independent per-letter shards reaching
only ~5,100 of the real leaf strings total, versus the exhaustive,
validated 46,432,934-entry `.rl`/`.prl` catalog covering the same real
names). Everything else about Street search (the common, City-selected
case, and final "Start" resolution via `resolve_address()`) was already
exact and unaffected by `.rt`'s incompleteness.

**The fix: `MapData.street_name_index_global`, the same `PrefixNameIndex`
pattern already used for Country/City, applied globally.** Built from
EVERY distinct real name in `road_naming.RdCache` (the whole disc's
`eeu.rd`, not one city's bbox) via a new `RdCache.distinct_names()`
method, wrapped in a `city_reader.PrefixNameIndex` exactly like every
other exact index in this feature. `SpellerDialog._backing_index()`'s
"street" branch is now:
```python
return (data.street_name_index_for_city(self.city_name, country_rec=...)
        or data.street_name_index_global)
```
-- byte-for-byte the same `or`-fallback SHAPE already established for City
(`city_name_index_for_country(...) or city_name_index`), just with the
Street-specific pieces. The `.rt`-trie fallback is gone from the live UI's
own narrowing path entirely: `_backing_index()` now ALWAYS returns a real,
exhaustive index for all three fields.

**A real implementation bug caught by this session's own "measure, don't
assume" standard, not shipped silently.** `RdCache.distinct_names()`'s
first version deduplicated the raw 43-byte name field as fixed-width
binary via `numpy.unique()` -- fast, but WRONG: directly checking the
reference disc found two real records both named `"LINOSA"` with
byte-identical 6-byte strings + NUL terminator but DIFFERENT trailing
garbage in the remaining 36 bytes (leftover buffer content, not
consistently zero-filled), so the naive raw-byte dedup found 8,808,597
"distinct" rows out of 8,809,081 records -- essentially no dedup at all,
silently contradicting the expectation that many road segments share a
name. **Fixed**: every byte at or after each row's own first NUL byte is
explicitly zeroed (vectorized via `numpy.cumsum()` over the per-row
zero-byte mask) before packing rows for `numpy.unique()`, so two records
encoding the same real string always compare byte-identical regardless of
trailing garbage. After the fix: **2,674,757 distinct names** out of
8,809,081 records (a real ~3.3x dedup ratio, consistent with "many
segments share a name" -- the sanity check the bug's own symptom failed).

**Exhaustiveness PROVEN, not assumed** (`test_map_viewer.py`, against
`CD_8555.ISO`): the real, well-known Sofia street **"VITOSHA"** (Vitosha
Boulevard -- already used and validated elsewhere in this project's own
City->Street scoping tests, "v13 -> v14" above) is directly confirmed
UNREACHABLE via the OLD `.rt`-trie prefix walk
(`road_index_reader.rt_lookup_prefix(rt_body, "VITOSHA", rt_root())`
matches only 2 of 7 characters before failing, `node=None`) but IS found
in the NEW global index (`street_name_index_global.count_matches
("VITOSHA") >= 1`). This is not a cherry-picked worst case: a full scan of
all 2,674,757 distinct real names found this pattern (real name present in
the global index, NOT fully spellable via `.rt`) essentially immediately
-- e.g. `"A AERODROMIOU"`, `"A AFRODITIS"`, and 8 more real Greek street
names in the same scan's first handful of hits -- consistent with `.rt`'s
own already-documented ~5,100/2,674,757-leaf coverage (roughly 0.2% of the
real universe), not a fluke.

**Load-timing measurement and the eager-vs-lazy decision.** Measured
directly against the reference disc (already-loaded, in-memory `RdCache`,
no extra file I/O), two ways, both consistent: a standalone benchmark
script (`RdCache.distinct_names()` alone, the `numpy.unique()` pass over
all 8,809,081 records) measured **~6.6-8.5s** across repeated runs, plus a
further **~2.3-3.1s** to wrap the result in a `PrefixNameIndex` (sorting
~2.67M case-folded strings); `test_map_viewer.py`'s own real-ISO test
("8h-x") measured the SAME combined property access
(`street_name_index_global`'s first touch, `distinct_names()` +
`PrefixNameIndex` construction together) end to end at **10.58 seconds**
for the resulting 2,674,739-name index, confirming the same one-time
**roughly 9-11 second** cost via the actual shipped code path, not just a
standalone script. Decision:
**LAZY**, built on first actual property access
(`MapData.street_name_index_global`, a Python `@property`, NOT part of
`load_address_entry_data()`), not eager. Rationale: the required
Country->City->Street order this UI already enforces ("v13 -> v14") means
the common case -- a City was actually selected and resolves -- never
reaches this fallback at all, so paying a ~9-11s cost on every "NAV"
screen open would be pure waste for the overwhelmingly common case; paying
it once, only the first time a City genuinely fails to resolve (or the
first time some other future caller needs a global street list), is the
right tradeoff. `test_map_viewer.py` confirms both halves of this
directly: `data._street_name_index_global is None` before first access,
a real measured build time on first access, and a second access reusing
the identical cached object in under 0.01s.

**Real-ISO test evidence** (`test_map_viewer.py`, against `CD_8555.ISO`):
non-GUI section "8h-x" reproduces every number above directly (lazy-until-
accessed, the build timing, the VITOSHA unreachable-via-`.rt`-but-
reachable-via-global proof, and `_backing_index()`'s own `or` fallback
returning the exact same cached object `street_name_index_global` returns
for an unresolvable city, mirroring City's already-established fallback
contract); the GUI section drives the real widgets end to end -- typing a
nonsense city (`"ZZZQQXNOTAREALCITY999"`) into the City field, then opening
the Street speller and confirming (by object identity, not just matching
behavior) that `SpellerDialog._backing_index()` returns
`street_name_index_global`, that the on-screen match-count badge and
per-letter enabled/disabled key states reflect the real global counts, and
that "VITOSHA" -- unreachable via the old trie -- spells out correctly
letter by letter through the real Tk widgets. Full pre-existing suite
(search, pan, zoom, layer checkboxes, connected-roads, hide-garbage
toggle, click-to-identify, the full Country->City->Street cascading flow
with a VALID city from "v13 -> v14") re-run and passes unchanged --
confirming the common, City-resolves path never touches this new code at
all. `test_core.py` (the separate editing tool) re-run unmodified and
passes, including its full write/round-trip verification against a real
output ISO.

**`.rt`'s own trie code: status, not deletion.** Grepped directly, not
assumed: `road_index_reader.rt_enabled_next_chars()` has exactly one
caller in this codebase, `MapData.street_enabled_next_chars()`, which
itself has exactly one call site, the `else` branch of `SpellerDialog.
_recompute()` -- now unreachable from the live UI (`_backing_index()`
never returns `None` for "street" any more) except in the defensive edge
case `self.app.data.rd_cache` is somehow unbuilt. Neither function was
deleted: both remain real, cracked, cross-validated code (§3.7's node-
format validation, the 72.8%-vs-4.2% pointer hit-rate test, the real
`eeu.typ`/multi-language vocabulary cross-references), and both are still
directly, independently exercised by `test_map_viewer.py`'s own
pre-existing `.rt` fail-safe-design tests (the unconfident-empty-prefix
case and the genuine confident-dead-end case, "8h-vii", untouched this
session) -- kept available/testable on their own terms, the same
"validated bonus, not load-bearing" status `city_reader.ct_root()` already
had for City since "v11 -> v12".

**Limitations, stated honestly.**
- `RdCache.distinct_names()`'s dedup is exact-string-equality only (after
  the NUL-padding fix above) -- it does not further normalize case,
  diacritics, or the `;`-demotion sort-key convention `.rt`/`.prl` use
  (§3.7); `PrefixNameIndex` already upper-cases for its own internal
  comparison, but two differently-spelled real records for what a human
  would consider "the same" street (e.g. a transliteration difference)
  are still counted and indexed as distinct entries, exactly as
  `street_name_index_for_city()`'s own existing docstring already
  disclosed for the per-city path.
- The one-time ~9-11s lazy build cost is paid on the Tk main thread the
  first time `street_name_index_global` is accessed (inside `_recompute()`,
  itself called synchronously from `_on_key()`/`_backspace()`/`__init__`)
  -- i.e. the UI will visibly pause for several seconds the first time a
  user types into the Street field with an unresolved/unresolvable City.
  Not wrapped in a `BackgroundTask` this session (every other lazy index
  in this class -- `city_name_index_for_country()`,
  `street_name_index_for_city()` -- is cheap enough not to need one); a
  future session could move this specific first-build off the main thread
  if the pause proves annoying in practice.
- This closes the one documented fallback gap Street had, but does not
  change `resolve_address()` (the final "Start" resolution), which never
  depended on `.rt` for correctness in the first place (README §10
  "v11 -> v12") -- there was no resolution-correctness bug here, only a
  live-narrowing coverage gap in one fallback branch.

### v15 → v16: "missing roads" / "dots not connected" investigated end to end; "Hide decode garbage" DEFAULT FLIPPED to unchecked (this session)

**The user's own first-hand observation that prompted this** (verbatim):
*"right now we need to first start showing the roads correctly, some roads
are missing, i see the dots but they are not connected, also im seeing
that unchecking hide decode garbage is producing more real accurate roads
then when i enable it, meaning its not usefull and the garbage is not
actually garbage."* This directly challenged the existing 42/80-vs-28/80
mg4 tile-count benchmark (§3.6) that had been the basis for the oscillation
filter's "checked by default" choice in the viewer ("v10 -> v11") -- the
task this session started from was explicit that real, first-hand visual
observation should be trusted and investigated honestly, not defended
against. Every claim below was checked directly against the real ISO
(`CD_8555.ISO`), reusing `MapData` so the numbers reflect the exact code
path the shipped app runs, not a hypothetical.

**Method.** All measurements below use the same Sofia, Bulgaria bbox this
project has used throughout ("v4 -> v5" onward, `lon=23.40102/lat=42.65533`,
`±0.05°`), the area the user has actually been testing against, plus a
second real area (Timișoara, `±0.05°`) for cross-checking the two
non-oscillation "missing roads" hypotheses. `mp0` was fully loaded
(background geo-index build completed, 194,650/194,705 tiles) before any of
these numbers were taken, so none of them can be explained by "mp0 wasn't
ready yet."

**Hypothesis 1 -- unreachable geo-index tiles near Sofia: ruled out.**
Full-file geo-index coverage on this reference disc, re-measured this
session: `mg4` 6,106/6,110 (99.93%), `mg3` 16,495/16,503 (99.95%), `mg2`
34,200/34,209 (99.97%), `mg1` 63,970/63,996 (99.96%), `mp0` 194,650/194,705
(99.97%) -- consistent with §3.6's own previously-reported figures, not
drifted. To check whether any of the small number of genuinely-unresolved
tiles sit near Sofia specifically (the unresolved tiles have no known
coordinate by definition, so this can only be a proxy check): tile_ids are
assigned in physical/on-disk tile order, and a direct check this session
confirmed that order correlates strongly with geographic locality (74-98%
of consecutive resolved tile_id pairs, across all 5 layers, are within
0.5° of each other) -- so a real Sofia-area tile going missing should show
up as an unresolved tile_id numerically close to Sofia's own resolved
tile_ids. Result: **zero** of the 4/8/9/26/55 unresolved tile_ids (mg4
through mp0 respectively) fall within ±3 tile_id of any of the 3-88
Sofia-area resolved tile_ids found per layer. This isn't proof no Sofia
tile is ever unreachable, but it's real evidence against it being the
explanation for what the user is seeing -- the unresolved tiles appear to
be scattered elsewhere on the disc, not clustered near Sofia.

**Hypothesis 2 -- `MAX_FEATURE_DRIFT_DEG` dropping whole features: ruled
out.** Re-measured directly (previous sessions only had one sample showing
zero drops): at Sofia AND Timișoara, across all 5 layers (`mg4`/`mg3`/
`mg2`/`mg1`/`mp0`), decoding every tile in each bbox and counting features
that fail the drift-plausibility check (`_feature_keep_indices()`) found
**zero dropped features and zero dropped points** in every one of the 10
layer/area combinations tested (e.g. Sofia `mp0`: 33 tiles, 48 raw
features, 48 kept; Timișoara `mp0`: 34 tiles, 61 raw features, 61 kept).
This filter is not silently eating real roads in either real dense area
tested.

**Hypothesis 3 -- the oscillation-garbage filter: CONFIRMED, this is the
real, dominant cause, and the old benchmark could not see it.** This is
where the user's own observation is directly vindicated. A geometric,
per-named-road comparison (not just a raw point count) of `decode_features
(trim_oscillation=True)` vs `(trim_oscillation=False)` for the SAME real
Sofia tiles:

| layer | tiles | pts ON (filtered) | pts OFF (raw) | named roads ON | named roads OFF | roads ENTIRELY deleted by filter | roads truncated by filter |
|---|---|---|---|---|---|---|---|
| `mg1` | 9 | 2,218 | 2,353 | 164 | 170 | **6** | **13** |
| `mp0` | 33 | 11,821 | 11,821 | 691 | 691 | 0 | 0 |

At `mg1` -- a layer in active use at ordinary "neighborhood" zoom, not an
edge case -- the filter removes only 5.74% of raw points (matching §3.6's
earlier-reported figure exactly) but that 5.74% is disproportionately real
road geometry: **6 entire real named roads vanish completely**
(`BISTRISHKO SHOSE`, `BIZNES PARK SOFIA`, `MLADOST 4`, `TSAR ASENOV PAT`,
`TSARITSA`, and a numbered route `"6"`), and **13 more are measurably
truncated**, worst of all Sofia's own ring road:

```
OKOLOVRASTEN PAT      ON=  2  OFF= 13   (lost 11 pts, 84.6%)
ALEKSANDAR MALINOV    ON= 14  OFF= 24   (lost 10 pts, 41.7%)
TSAR ASENOV PAT       ON=  0  OFF=  5   (lost 5 pts, 100%)
BISTRISHKO SHOSE      ON=  0  OFF=  4   (lost 4 pts, 100%)
HAN ASPARUH           ON=  1  OFF=  5   (lost 4 pts, 80.0%)
```

`OKOLOVRASTEN PAT` ("Ring Road") is not an obscure stub -- it's Sofia's
own orbital motorway, exactly the kind of major real road a user would
notice missing/mangled while looking at the map. At `mp0` (the densest
layer, same bbox), the filter had **zero** measurable effect either way in
this specific area -- the filter's impact is real but tile/layer-dependent,
not uniform, which is itself part of why the old benchmark's single-layer
(`mg4`) aggregate count missed it.

**Why the existing 42/80-vs-28/80 `mg4` benchmark (§3.6) did not catch
this.** That metric asks one binary question per tile: "does this tile
still have 2+ features that EACH independently exact-match a different
named road, ANYWHERE in the tile?" It was never designed to (and cannot)
detect (a) a SPECIFIC named road disappearing as long as some OTHER 2 roads
still match somewhere in the same tile, (b) partial truncation of a road
that still has at least one matched vertex left, or (c) an effect that
concentrates on a DIFFERENT layer (`mg1`, finer/more commonly viewed at
normal zoom) than the one the benchmark was ever run against (`mg4`,
the coarsest, most zoomed-out layer). All three of those are exactly what
happened here. The benchmark's own 28/80-vs-42/80 result is not wrong on
its own terms -- it is a real measurement of a real, narrower question --
it is simply the wrong proxy for "does this make the rendered map more
complete for a real user looking at a real dense area," which is the
question that actually matters for the viewer's default.

**A secondary, inconclusive line of investigation (reported honestly, not
oversold).** Since `MapData.decode_tile()` passes the SAME (possibly
oscillation-split) `features` list into both `decode_features()` and
`decode_topology()`/`resolve_topology_adjacency()`, and
`decode_topology()`'s table-location search sizes itself using
`len(feature["points"]) + 1` (correct for an untouched block, but smaller
than the real on-disk record count for a SPLIT sub-feature -- see
`decode_topology()`'s own docstring), there was a plausible mechanism for
`trim_oscillation=True` to also depress connected-roads confidence via
topology-table misalignment. Tested directly at Sofia: split (oscillation-
affected) sub-features actually resolved SLIGHTLY HIGHER on both
`"found"` (70.6% vs 61.7%) and high-confidence (64.7% vs 61.7%) rates than
un-split features at the per-feature level, but tiles CONTAINING any split
averaged slightly LOWER on both (61.9%/58.3%) than tiles with no split at
all (69.8%/69.8%). The sample is small (17 split features / 7 tiles-with-
a-split vs 60 / 43) and the two directions disagree, so this is reported as
an open, unresolved question, not a confirmed contributing cause -- it did
NOT factor into the decision below, which rests entirely on the direct
per-named-road evidence above.

**"Dots not connected" -- reconfirmed as an honest, unchanged limitation,
not a regression.** Re-measured `resolve_topology_adjacency()`'s
high-confidence rate at the same Sofia bbox: **91.7%** (11/12 features) at
scale=1,500 (`mg4`+`mg3` only, 1,804 points) and **62.6%** (161/257
features) at scale=20,000 (all 5 layers, 48,302 points) -- matching "v9 ->
v10"'s own previously-measured 63% figure almost exactly, i.e. this has not
drifted from earlier sessions. At the densest, most-zoomed-in real view,
roughly **37% of features are still, correctly, rendered as dots** because
`resolve_topology_adjacency()`'s own confidence gate (§3.6) genuinely
cannot resolve them (small/simple features, or an auto-detected shift whose
median implied edge distance exceeds the 2km sanity threshold) -- this is
the deliberate, documented behavior of "never draw a guessed line," not a
bug found this session. Some fraction of what the user is seeing as "dots
that should be connected" is very likely this expected, disclosed
coverage gap, not new breakage.

**UPDATE (later pass, this session): the 37% figure above was investigated
further and is no longer accurate** -- most of it was a fixable weakness
in `_find_topology_table_start()`'s search, not a fundamental limit. Two
real bugs were found and fixed (full writeup, mechanism, and byte-level
evidence in `resolve_topology_adjacency()`'s and `decode_topology()`'s own
docstrings in `map_compressed_reader.py` -- not repeated in full here):
a magnitude `cap`/search-window that was far too tight for real
dense-urban field values (fixed with a cap ladder), and a subtler
false-positive this exposed where a large feature's loosened-cap search
could match a byte-misaligned echo of a smaller sibling feature's own
genuine table on a multi-feature tile (fixed by resolving each tile's
features tightest-cap-first with non-overlapping byte-range reservation,
instead of a blind per-feature sequential scan). Re-measured on the same
Sofia bbox at scale=20,000: high confidence is now **75.5%** (194/257
features, up from 62.6%/161/257), re-confirmed to NOT change either
ground-truth tile's result (`mg2` 20597, `mp0` 91124 both reproduce their
exact original table_start/shift/edge results). The remaining ~24% (63
features) does NOT correlate cleanly with feature size (63-90% high
across every point-count bucket from 2 to 400+ points) -- it correlates
more with LAYER (54/63 are `mp0`, the densest street-level layer with the
most multi-feature tiles) -- see `resolve_topology_adjacency()`'s
docstring for the full size-bucket breakdown. `test_map_viewer.py` was
re-run in full and passes, including both ground-truth checks.

**Decision and fix.** Given (1) the user's own direct, repeated visual
observation, (2) concrete confirmation via real, specific, named Sofia
roads (including a major arterial) being deleted/truncated by the filter
at a real, ordinarily-used zoom level, and (3) a clear structural
explanation for why the old benchmark could not have caught this --
`MapData.trim_oscillation` and `App.hide_garbage_var` both now **default
to `False`/unchecked**. A user who never touches the "Hide decode garbage"
checkbox now sees the raw, unfiltered geometry -- measurably MORE complete
for real named roads in real dense areas, per the evidence above. The
checkbox itself is unchanged mechanically (still a real re-decode via
`MapData.set_trim_oscillation()`, still fully reversible, still useful for
side-by-side inspection of what the filter would remove) -- only which
state it starts in changed. `research/map_compressed_reader.py`'s own
`decode_features(trim_oscillation=...)` library default was already
`False`; this change simply makes the viewer stop overriding it to `True`,
so the viewer and the library it's built on now agree. The known,
already-documented false positives (§3.6: `mg4` tile_id 187's real 2-road
match, `mg4`/`mg3` tile_id 2619's real interleaved two-track chain, `mg3`
tile_id 1330's un-caught corruption either way) are unchanged by this
decision -- they were never the deciding evidence; the fresh, direct Sofia
`mg1` measurement above is.

**Test changes** (`test_map_viewer.py`): the single shared `MapData`
instance most of this file's OTHER exact-point-count regression
assertions depend on (layer-stacking arithmetic, checkbox-restriction
logic, connected-roads edge counts, etc. -- all unrelated to the garbage
filter) is now explicitly pinned to `trim_oscillation = True` right after
construction, so none of those pre-existing numbers needed to be
re-derived. The REAL, un-pinned default is verified separately and
explicitly: a fresh `App` is asserted to start with `hide_garbage_var.get()
is False` immediately after construction (before its `data` is overwritten
by the pinned shared instance), and the existing "Hide decode garbage"
GUI toggle test now starts with an explicit sync step (checking the box to
match the pinned baseline) before exercising the same True->False->True
real-re-decode toggle path it always has. Full pre-existing suite (search,
pan, zoom, cumulative layer stacking, layer-visibility checkboxes,
connected-roads mode, click-to-identify + undo + connecting line, Address
Entry Country->City->Street flow) re-run and passes unchanged.
`test_core.py` (the separate editing tool) re-run unmodified and passes,
confirming it shares no code path with any of this.

**Honest remaining uncertainty.**
- `mp0` showed literally zero measurable effect (either direction) at this
  exact Sofia bbox, but the ORIGINAL oscillation bug that motivated this
  whole filter (§3.6) was found in an `mg3` tile at a real coordinate
  (`lon=23.33750/lat=42.69055`) only ~1.3km outside this bbox -- so the
  filter unquestionably still catches SOME real corruption near Sofia, just
  not inside the specific box measured here. This is a real tradeoff, not
  a case where the filter has no benefit anywhere: turning it off by
  default trades a small, real amount of caught corruption (rendered as a
  few scattered stray dots now that roads are dots-not-lines, "v3 -> v4" --
  no longer the long "crazy line" artifact this filter was originally built
  to fix) for a larger, now-measured amount of real road geometry recovered.
- The 42/80-vs-28/80 `mg4` benchmark itself was not re-run or invalidated
  this session -- it remains an accurate measurement of its own specific
  question at that specific layer. What changed is which question the
  viewer's default should actually be optimized for.
- The secondary split-vs-topology-confidence investigation above is
  genuinely inconclusive (mixed direction, small sample) and would need a
  larger, purpose-built sample (many more tiles with a confirmed split) to
  resolve either way -- left as an open lead for a future session, not
  acted on here.

### v16 → v17: red dots, clickable connected-roads edges, zoom-independent layer pooling, bitmap rasterization, and a real background-reload staleness bug found and fixed (this session)

**The user's request (verbatim):** *"now in the map viewer make the points
red dots not gray ones, also make the dots visible when roads are visible
also and make roads clickable and show the road segment's connecting
points 2 so i can debug this and tell you fixes also, always show the
selected layers independent of zoom."*

**Dots and edges.**
- Points now rasterize as solid red (`DOT_COLOR = "#d32f2f"`), always --
  previously they were only drawn when "Draw connected roads" was off
  (dots-vs-lines used to be an either/or rendering choice); now a dot is
  drawn at every real point regardless of that checkbox, with resolved
  edges drawn on top when it's checked.
- Edges are now clickable: right-clicking near the midpoint of a rendered
  connected-roads line (`_add_edge_pick()`) identifies **both** endpoints
  in one click (marked as an `edge<->#` pair in the picked-points panel,
  distinguishable from two independent single-point picks) -- this is the
  exact debugging tool that surfaced the real false-edge bug fixed in
  §3.6's "v16 -> v17" update above (the user right-clicked 5 real rendered
  lines and reported their endpoints as implausibly far apart; all 5
  reproduced directly against the ISO and are now fixed and covered by a
  regression test).

**Zoom-independent layer pooling.** Previously (`"v5 -> v6"`)
`layers_for_scale()` automatically restricted which layers got pooled
based on the current zoom, as a cost-saving gate -- checkboxes only ever
*narrowed* that automatic set further, they never had full control. Per
the user's explicit request ("always show the selected layers independent
of zoom"), `MapData.ensure_area_loaded()`'s `allowed_layers` is now the
**only** restriction: the pooled set is exactly `available_layers() ∩
allowed_layers`, at every scale, with `layers_for_scale()`/
`SCALE_LAYER_THRESHOLDS` left in place as pure, tested, but no-longer-
called functions. **Stated cost, not hidden:** this removes the gate that
existed specifically because `mp0` alone can be tens of thousands of
points over a real, wide, fully-zoomed-out viewport -- a user who wants
that cost back can simply uncheck the heavier layers manually. Measured
directly: a maximally-zoomed-out, all-layers-checked reload over a real
Sofia-area viewport pooled 480,059 points (268,285 from `mp0` alone,
across 1,062 tiles) in real end-to-end testing, taking several minutes on
real hardware -- a genuine, disclosed tradeoff, not an oversight.

**Bitmap rasterization rewrite.** The old renderer created one real
Tkinter canvas item (`create_oval`/`create_line`) per point/edge --
tens of thousands of individual widgets, which is where the actual
"Not Responding" freezing the user reported came from (not CPU or disk
speed). `App._redraw()` now rasterizes every point/edge into a single
`PIL.Image`/`ImageDraw` bitmap, shown via exactly one
`canvas.create_image()` call, regardless of point count. Measured
directly: Sofia-area, all 5 layers (48,302 points, 36,849 dot pixels),
0.086s per `_redraw()` -- one canvas item instead of tens of thousands.
Tests were reworked to match: assertions sample real pixel colors from
`App._current_image` at exact projected coordinates instead of counting
canvas items.

**A real background-reload staleness bug, found and fixed while building
this section's own test coverage.** `App._maybe_reload_viewport()` starts
each pan/zoom/checkbox-triggered reload on a background thread
(`BackgroundTask`) and, on completion, applied its result unconditionally
-- including writing `MapData.covered_bbox`/`covered_layers` (set as a
side effect deep inside `MapData.ensure_area_loaded()`, on the worker
thread) and `App.features`. With the old scale-based gate removed above,
overlapping reloads became easy to trigger in practice (e.g. a debounced
`_schedule_viewport_check()` reload left pending from an earlier pan,
still queued in Tk's `after()` mechanism, whose worker thread keeps
running and can finish **after** a newer, faster reload already
completed) -- and there was no mechanism anywhere to detect or discard a
stale, superseded completion. A late-finishing old reload would silently
overwrite the current view's state with its own unrelated area/feature
set, well after a newer request had already finished successfully.
Reproduced directly while writing this session's own end-to-end GUI test
(a real Sofia-area reload's own bookkeeping was observed reverting to an
unrelated, much-earlier Tirana-area test's result, several minutes after
the Sofia reload itself had already completed with the correct data).
**Fix:** `App` now tracks its own generation counter
(`self._load_token`, bumped every time a new reload actually starts) and
the "what area/layers does the CURRENT view have loaded" state
(`self._covered_bbox`/`self._covered_layers`) separately from
`MapData.covered_bbox`/`covered_layers` (left unchanged -- still simple,
unconditional bookkeeping on `MapData` itself, which existing direct/
non-GUI tests rely on). `_maybe_reload_viewport()`'s `done()` callback now
checks its own captured token against the current one first and discards
the entire result (no `features`/`_covered_bbox`/`_redraw()` update) if a
newer reload has since started, regardless of which `BackgroundTask`
happens to finish first. This is a real correctness fix, not just a test
artifact -- the same class of bug could analogously let a real user's
slow, superseded pan/zoom reload revert their current view after a faster
follow-up reload already updated it.

**Test suite:** `test_map_viewer.py`'s GUI end-to-end section was extended
with real, running-`App`-level coverage for all of the above (scale-
independent layer pooling actually reaching the running app, not just
`MapData`; the layer-visibility/hide-garbage checkboxes actually firing a
real background reload; ground-truth pixel-sampled rendering checks for
both dots and edges; edge click-to-identify against a known real edge).
Two real test-hygiene issues surfaced and were fixed along the way: (1)
the bbox-nesting "setup check" comparing a zoomed-out load against a
subsequent zoom-in now computes both sides via `compute_visible_bbox()`
against a canvas size captured once, synchronously, right before the
load -- real canvas geometry is not guaranteed stable across the several
real minutes a wide, all-layers reload takes (the window is pinned to a
fixed size, but sibling widgets like the status bar can still shift how
much of that fixed budget the canvas gets as its own text changes length)
so re-reading `winfo_width()/height()` live at both ends of a long wait
was flaky; (2) the "NAV -> Start" end-to-end jump test now temporarily
disables connected-roads mode around the jump (same pattern already used
elsewhere in this file) since the ~34x per-tile adjacency cost, paid over
a real not-yet-cached area, is unrelated to what that check verifies and
was blowing past its own timeout. Full suite re-run and passes end to end
against the real ISO.

### v17 → v18: discrete, real-hardware-style zoom steps (this session)

**The user's request (verbatim):** *"make the start zoom at 5km and the
zoom steps must be as follows: 500km, 400km, 300km, 200km, 150km, 100km,
75km, 50km, 40km, 30km, 20km, 15km, 10km, 7.5km, 5km, 4km, 3km, 2km, 1.5km,
1km, 750m, 500m, 400m, 300m, 200m, 150m, 100m, 75m, 50m, 25m."*

Previously the mouse-wheel zoom was continuous: each tick multiplied
`scale` by `1.15` (or divided), clamped only to a broad `[1, 5,000,000]`
range -- not the fixed, discrete zoom "rings" a real GPS nav unit (and the
real RNS510) actually has. Replaced with:
- `ZOOM_LEVELS_M`: the exact 30-level table above, widest (500km) to
  narrowest (25m).
- `scale_for_zoom_span_m(span_m, width_px, height_px)`: converts a named
  real-world span into a `scale` (pixels/degree) such that the SMALLER of
  the canvas's two pixel dimensions spans exactly that distance --
  `span_m / METERS_PER_DEGREE_LAT` (111,320m/° of latitude; longitude's own
  shrink-by-`cos(lat)` is already handled by `project_point()`'s existing
  factor, so the same `scale` value works for both axes).
- `nearest_zoom_level_index(scale, width_px, height_px)`: finds which
  table entry the CURRENT scale is closest to (compared on a log scale,
  since the levels are geometric/multiplicative, not linear) -- this is
  what lets `App._on_zoom()` step exactly one real level per wheel tick
  from *whatever* `self.scale` happens to be (a previous discrete step, the
  fixed jump default below, or a test setting `app.scale` directly),
  without needing to separately track "which level am I on" as extra
  mutable state. Zooming past either end of the table clamps there instead
  of overshooting.
- `DEFAULT_ZOOM_SPAN_M = 5,000.0`: a freshly-jumped-to location (search
  result double-click, Address Entry "Start") now opens at the 5km level,
  per the user's explicit request -- replacing the previous behavior of
  auto-fitting the scale to whatever bounding box that jump's own decoded
  features happened to have (`App._initial_scale()`, kept as a general
  framing utility -- several ground-truth test sections still use it to
  frame a specific area on screen, it's just no longer what a live jump's
  own display scale uses).

Covered by `test_map_viewer.py`: pure-function round-trip checks (every
level's own `scale_for_zoom_span_m()` output resolves back to that same
level via `nearest_zoom_level_index()`, and scale increases monotonically
as the named span narrows), a real `App._on_zoom()` GUI check confirming
one wheel tick moves exactly one table level (5km <-> 4km) and stays
cursor-centered (the existing "keep the point under the cursor fixed"
pan math, unchanged, re-verified against the new discrete `new_scale`),
and clamping at both the 25m and 500km ends. Full suite re-run and passes
end to end against the real ISO.

### How it works

`MapData` (GUI-free, exercised directly by `test_map_viewer.py`) extracts
`FAST_LAYERS` (`mg4`/`mg3`/`mg2`/`mg1`) plus `eeu.cty` from the ISO on `load()`,
builds each fast layer's own geo-index, and builds two whole-session in-memory
caches — `HEAVY_LAYER` (`mp0`) is deliberately left untouched until
`load_heavy_layer()` runs separately (see above):
- `road_naming.RdCache` — reads/vectorizes all of `eeu.rd` (8.8M records) ONCE;
  `RdCache.index_for_bbox()` then repeats only `build_rd_index()`'s cheap
  numpy-mask-and-decode step against those resident arrays for any viewport, with
  no further file I/O (closing the "don't call this per-frame" gap §3.9 flagged).
  Shared across all layers — `eeu.rd` is a separate source file, unaffected by
  which tile layer is currently selected.
- `city_reader.CtyCache` — reads/vectorizes all of `eeu.cty` (939,351 records)
  ONCE; `CtyCache.query()` answers "cities intersecting this viewport, above this
  bbox-area importance threshold" with a couple of numpy boolean masks.

`MapData.ensure_area_loaded(bbox, scale)` is the single entry point for both the
initial "jump to X" and every pan/zoom-triggered reload (`scale`, pixels/degree,
required as of "v5 → v6" — see above): it pads the requested bbox (`AREA_PAD_FRAC`,
gives pan headroom before the next reload), decodes any not-yet-cached tiles whose
geo-index anchor falls inside it, but only for the CUMULATIVE layer set
`layers_for_scale(scale, available_layers())` returns for the given scale,
further restricted by its optional `allowed_layers` param (the checked
layers from the "v8 → v9" checkboxes, or `None`/unrestricted for every
pre-existing caller) via simple set intersection — not
every available layer unconditionally (tiles, once decoded, are NEVER evicted —
`MapData.tile_caches` only grows, even for a layer that later falls out of the
current cumulative set — see "v5 → v6"'s caching-design writeup), rebuilds the
road-name index only if the current one doesn't already cover the new area
(`rd_index_for_bbox()` — replace-with-a-bigger-box, not true incremental merging;
simpler and, since `RdCache` has no file I/O, cheap enough not to need true
incrementality — see the method's own docstring for the full reasoning), and
returns freshly-named features. City queries are cheap enough to just run fresh
on every redraw instead of being cached at all.

On the GUI side, dragging/zooming redraws immediately from already-loaded data,
then debounces (`App._schedule_viewport_check`, Tk `after`, 350ms of no further
pan/zoom activity) before checking whether a reload is needed
(`App._maybe_reload_viewport()`): either the new viewport (`compute_visible_bbox`)
escaped the last-loaded (padded) area (`bbox_contains`), or the scale-dependent
cumulative layer set itself has changed (a zoom threshold was crossed, or `mp0`
just became available — see "v5 → v6") — either way, a background `BackgroundTask`
calls `ensure_area_loaded()` for the new view/scale without disabling the UI. Road-
run labels are placed at the midpoint of named vertex ranges above a minimum
on-screen pixel length, longest-on-screen-first, with a same-name proximity de-dup
so a long chain crossing the view twice doesn't repeat its label. City labels use a
zoom-dependent minimum bbox-area threshold (`city_min_area_for_scale()`) so only
large places show when zoomed out.

### Real-ISO test results (`test_map_viewer.py`, against `CD_8555.ISO`)

- Geo-index (mg3, at the scale used for the Timișoara/Prague checks below):
  16,495/16,503 tiles (99.95%) resolved. `RdCache`: all 8,809,081 `eeu.rd`
  records loaded/vectorized. `CtyCache`: all 939,351 `eeu.cty` records.
- Unified search: `"TIMISOARA"` → 2 road hits + a `TIMISOARA` city hit (of 522
  total city matches); `"TIRAN"` → 65 city hits including one within ~2km of
  Tirana's already-validated real-world coordinates (§3.8).
- `ensure_area_loaded()` near Timișoara (scale=1500, auto-picked `mg3`): 34
  tiles decoded, 86 features, **820 named vertex-ranges with real road names
  actually attached** — e.g. `MARSALA TITA`, `IVE LOLE RIBARA`, `M-7`, `M-7.1`,
  `JNA`, `DOSITEJA OBRADOVICA`, `SVETOSAVSKA` (genuine Serbian/Romanian
  border-area road and route names, not placeholders).
- Road-name index caching verified working as designed: re-querying an
  already-covered sub-area took 0.006s vs. 0.090s for the initial load, with
  `data._rd_index_bbox` unchanged (confirmed no rebuild) — this is the "build
  once per area, don't rebuild every frame" requirement working as intended.
- Simulated pan (Timișoara → Prague-area, a real, distant place, same `mg3`
  scale throughout): 99 new tiles decoded; Timișoara's previously-decoded
  tiles remained in `tile_caches["mg3"]` (confirmed by direct set-containment
  check) rather than being evicted or re-decoded — dynamic loading adds
  coverage without discarding what was already there.
- City labeling: querying Tirana's own real-world bounding box against `CtyCache`
  correctly surfaces `TIRANË` among a cluster of real `NJËSIA BASHKIAKE
  N, TIRANË` (municipal-unit) and postal-code sub-records — reproducing §3.8's
  own validation via the new viewport-query path, not just the original
  full-file scan.
- Actual canvas rendering (not just decoded data): driving `App._redraw()` with a
  real loaded Tirana-area view produced 175 road polylines and 24 text labels on
  the `tk.Canvas`, including a real `TIRANË`-named label and real neighboring
  towns (`DURRËS`, `OHRID`, `STRUGA`, `DEBAR`, `ELBASAN`-area localities, etc.).
  The same run also directly confirmed **no `ttk.Combobox` (layer dropdown)
  exists anywhere in the widget tree**.

### Real-ISO test results: automatic zoom-dependent layer selection (this session)

- **Startup stays fast**: `MapData.load()` (extracting + geo-indexing all four
  `FAST_LAYERS` plus loading `RdCache`/`CtyCache`) took **10.2s** end-to-end;
  `mp0` was confirmed completely untouched at that point
  (`"mp0" not in data.directories`, `mp0_ready is False`). `mg1` (previously
  entirely missing from `LAYER_ISO_PATHS`) geo-indexed cleanly: 63,970/63,996
  tiles (99.96%) resolved.
- **`choose_layer_for_scale()` behaves exactly as designed**: probed at scales
  500/1,500/4,000/10,000/50,000 px/deg, it returns
  `['mg4','mg3','mg2','mg1','mg1']` while `mp0` isn't ready yet (falling back
  to `mg1` at the closest zoom instead of erroring or picking an unbuilt
  layer) and `['mg4','mg3','mg2','mg1','mp0']` once it is.
- **Real before/after density at the same real bbox** (Sofia, Bulgaria area,
  `lon=23.40102/lat=42.65533`, the exact location that originally motivated
  this feature — via `ensure_area_loaded()`, includes its normal `AREA_PAD_FRAC`
  headroom padding): far zoom (scale=1200, auto-picked `mg3`) → 7 tiles / 8
  features / **1,303 points**; close zoom (scale=10,000, auto-picked `mg1`,
  same bbox) → 31 tiles / 46 features / **7,342 points** — a ~5.6x increase in
  actual decoded road detail from automatically picking a finer layer, not a
  hypothetical one. A smaller, unpadded apples-to-apples per-layer comparison
  at the same coordinates (0.1°-wide box, all 5 layers, no viewport padding)
  measured this same session: mg4 141 / mg3 397 / mg2 952 / mg1 2,218 / mp0
  **11,821** points — confirming the increase is monotonic across every layer
  step, not just between the two endpoints exercised by the automatic test.
- **Background `mp0` load + automatic upgrade, proven end to end**: before
  `load_heavy_layer()` ran, a street-level scale (20,000 px/deg) at the Sofia
  bbox correctly fell back to `mg1` (7,342 points, no error). `load_heavy_layer()`
  then took **37.3s** (extraction + geo-index for 194,705 tiles, 194,650
  resolved) — genuinely slower than the entire fast-layer startup (10.2s),
  confirming it really is the part worth keeping off the critical path. Once
  it finished, the identical street-level scale/bbox automatically resolved to
  `mp0` and produced 104 tiles / 168 features / **35,644 points** — more than
  4.8x `mg1`'s fallback figure, with **zero code changes or user action**
  needed to trigger the upgrade (`App._start_heavy_layer_load()`'s completion
  callback calls `_maybe_reload_viewport(force=True)` directly).
- Confirms `mp0` gets its own separate `tile_caches["mp0"]` entry, distinct
  from `tile_caches["mg1"]` (no shared/colliding `tile_id` numbering).

### v18 → v19: 2 real performance fixes (repeated re-naming, per-vertex Tk calls), plus a "nearby streets" click-to-identify feature (this session)

**The user's request (verbatim):** *"now with all this knowledge implement
it into the map viewer everything you can, and optimize the viewer please,
its really slow.... and laggy."* "This knowledge" refers to this session's
`eeu.si`/`eeu.iof`/`eeu.tmc`/`tpd/` cracks (§3.20/§3.3/§3.25/§3.24) — most
of it (TMC's internal chain format, the `.IDX` lambda-hash index, `TPD3.DIC`)
isn't map-viewer material at all, just internal file-format trivia, so
rather than guess which of the remaining pieces to wire in, the user was
asked directly and chose the `eeu.iof`/`eeu.il` "nearby street names"
lookup (§3.3) as the one concrete feature to build.

**Performance fix 1: redundant road-name re-matching on every reload.**
`MapData.ensure_area_loaded()` used to call `road_naming.name_features()`
(a real per-vertex spatial-index lookup, `match_feature()`) over the
**entire pooled feature list** on every single call — including tiles a
previous, overlapping call had already decoded AND already matched
identically (a tile's own geometry never changes, and the `rd_index`
covering it only ever grows, never shrinks or changes what it returns
for an already-covered area, so a tile's own match result is stable
forever once computed). At a wide, long-panned-around viewport with
hundreds of thousands of already-cached points, this meant every
incremental pan/zoom repaid the FULL re-naming cost again, on top of
whatever was genuinely new — the real remaining "still laggy after every
pan" cost once the "v17 → v18" bitmap-rasterization fix already made
RENDERING itself fast (0.086s for 48,302 points, §10 "v16 → v17"). Fixed
with a new `MapData.name_caches` dict, the exact same per-`(layer,
tile_id)` caching pattern `topo_caches` already uses for connected-roads
adjacency (§10 "v9 → v10"): a tile is only ever matched once (keyed by
`(tile_id, tol_m)` in case a future caller ever varies the tolerance),
reused on every later reload that revisits it; reset alongside
`tile_caches` on `set_trim_oscillation()`, since that toggle changes the
underlying geometry a cached match would otherwise misdescribe.
**Measured directly on a real Sofia-area viewport** (0.08° half-width,
all 5 layers, 365 pooled features): an identical-repeat reload dropped
from 0.353s to 0.001s (**293x faster**), and a simulated ~30%-panned,
mostly-overlapping reload cost only 0.016s for the 7 genuinely new tiles
— scaling with what's actually new, not the whole visible set. Verified
byte-for-byte identical `named_ranges` results against a fresh, uncached
`rdn.name_features()` ground truth (0 mismatches across all pooled
features, both on an identical repeat and against independent
recomputation).

**Performance fix 2: `App._to_canvas()` re-querying Tk on every vertex.**
`_to_canvas()` called `self.canvas.winfo_width()`/`winfo_height()` — a
real Tcl round-trip through the interpreter, not a cheap Python attribute
read — on **every single point/vertex it projects**, i.e. potentially
hundreds of thousands of times per `_redraw()` at a dense pooled
viewport, even though `_redraw()` itself already computes the canvas
size exactly once at its own top. Fixed by caching that size on
`self._canvas_w`/`self._canvas_h` (set at the top of every `_redraw()`,
kept fresh by the canvas's own `<Configure>` binding which already calls
`_redraw()` on any resize) and having `_to_canvas()` read those instead,
falling back to a live query only if called before the first redraw has
ever run. Verified the cached path produces byte-identical output to an
independent `project_point()` computation, both immediately after
`_redraw()` and across 20 repeated calls.

Both fixes verified with real, running-`App`-level smoke tests against
the actual `CD_8555.ISO` (not just unit-level function calls) — loading
real data, driving the real `MapData`/`App` methods, and cross-checking
results against independent ground truth.

**New feature: "nearby streets" via `eeu.iof`/`eeu.il` (§3.3).** A normal
left-click-then-right-click point pick (the existing click-to-identify
flow, §10 "v6 → v7") now ALSO looks up the nearest real `eeu.iof`
"anchor" record to the picked point (`MapData.nearby_streets_for_point()`)
and, if one exists within ~3.3km, appends its own real "nearby street
names" list (decoded via `research/iof_reader.py`'s already-cracked
`offset`/`count` → `eeu.il` chain, this session's §3.3 crack) to both the
status bar and the picked-points panel — e.g. clicking near a real German
route `L162` surfaces 88 real nearby street names (`ACKERSTRASSE`,
`AHREMER LICHWEG`, `ALTER BURGWEG`, ...). Anchors are sparse (~0.36% of
`eeu.rd`'s 8.8M records), so this deliberately searches for the NEAREST
one rather than requiring an exact hit on the anchor itself — "what
streets are named near here" is the useful question for a map viewer,
not "is this exact point an anchor". Implementation notes: the small
(~31,318-record) anchor index is built lazily on first use, straight from
`MapData`'s already-resident `RdCache` coordinate arrays (no extra
`eeu.rd` read); `eeu.il`'s 39MB body is read once and cached
(`self._il_data`) on first lookup. A silent no-op (no panel line, no
status addition) if no anchor is within range — this is a bonus
enrichment on an ordinary pick, never a blocking part of it (wrapped in a
`try`/`except` in `App._append_nearby_streets_row()` for exactly that
reason). **Verified directly against `research/iof_reader.py`'s own
functions as ground truth**: for 5 real anchors spread across the whole
file (queried at their own exact coordinates, so the nearest-anchor
search must land on themselves), `nearby_streets_for_point()`'s anchor
name, distance (< 1m), and full de-duplicated street-name list matched
the independently-computed ground truth exactly, 5/5 — and a point far
from any real anchor (0°, 0°) correctly returned `None` rather than a
false hit.

### v19 → v20: real POI display, unlocked by this session's own `POI.DB3.Coordinate` crack (this session)

**The user's request:** after cracking `POI.DB3`'s `Coordinate` field (a
64-bit Morton/Z-order code, §3.24) while investigating what to build next
in the viewer, the user was asked whether to build real POI display and
said yes.

**Data pipeline**: `MapData.load_poi_data()` extracts `EDB/POI/POI.DB3`
(~1.1GB, disc root, a new `POI_ISO_PATH = "/EDB/POI/POI.DB3"` — not under
`/DB/` like every other extracted file) in its own background
`BackgroundTask`, same deferred-loading pattern as `load_heavy_layer()`
("mp0") — kicked off right after "Open Map ISO" returns, so it never
blocks opening the disc. `research/poi_db_reader.py` gained a vectorized
bulk-decode path (`decode_coordinates_np()`, `load_poi_cache()`) — the
whole-file "read once, numpy-filter per viewport" pattern
`road_naming.RdCache` already uses for `eeu.rd`. **Measured on the
reference disc**: 8.6s total to extract POI.DB3 and decode all
4,733,183 real POI coordinates (verified byte-for-byte identical to the
scalar `decode_coordinate()` on a random sample, 0 mismatches).

**Real, disc-designed zoom gating, not a guessed cutoff.**
`PoiPartition_BaseAttributes.MapZoomLevel` (previously only noted as
"consistent with partitions controlling visibility, not confirmed") is
used directly as each POI category's own visible-span-in-meters cutoff
— `"airport"` (`zoom_level_m` 5,000,000) stays visible zoomed way out,
`"downtown area"` (50,000) only appears zoomed in close, `"gas
station"`/`"restaurants"`/etc. sit in between — exactly matching this
viewer's own existing `ZOOM_LEVELS_M` span-in-meters convention, so no
new unit conversion was needed (`span_m_for_scale()`, the exact inverse
of the already-existing `scale_for_zoom_span_m()`). `MapData.
pois_for_bbox(lon_min, lon_max, lat_min, lat_max, max_span_m)` combines
this with the ordinary bbox filter. **Verified directly**: a Sofia-area
query at a 50km span returns 6,162 real POIs with a sensible category
mix (826 restaurants, 811 ATMs, 807 pharmacies, 95 gas stations, 213
hotels, ...); the SAME query widened to the whole EEU bbox at a 500km
span correctly drops to ONLY long-range categories (`airport`, `cng
station`, `lpg station`, `monuments`) — `"gas station"` is confirmed
ABSENT at that span, exactly as its own 400,000m `zoom_level_m` demands.

**Rendering: rasterized into the SAME bitmap as road dots, not
individual canvas items.** A wide-but-still-in-range viewport (e.g. a
broad category's own 400,000m cutoff implies a viewport that could
plausibly cover hundreds of thousands of real POIs — confirmed directly:
185,520 POIs at the widest EEU-spanning 500km-span query above) drawn as
individual `canvas.create_oval()` items would risk reintroducing the
exact "Not Responding" freeze the "v17 → v18" rasterization rework
already fixed for road dots. POI markers (`POI_DOT_COLOR`, Material
"purple 700" — visually distinct from every other on-map color already
in use) are drawn into the same `PIL.Image`/`ImageDraw` bitmap
`_redraw()` already builds for roads; only POI NAME labels are real
canvas text items, capped at `MAX_POI_LABELS` (40, the same pattern
`MAX_CITY_LABELS` already uses) regardless of how many markers were
drawn. A new "Show POIs" checkbox (checked by default) is a pure
rendering-time filter — no background reload needed, unlike the layer/
connected-roads checkboxes, since it doesn't change what's loaded, only
what a redraw draws.

**Verified with a real, running-`App`-level test** (not just `MapData`-
level): after a real redraw of a Sofia-area view, 6,918 sample pixels of
the rendered bitmap match `POI_DOT_COLOR` exactly (within a small
anti-aliasing tolerance); unchecking "Show POIs" and redrawing again
finds exactly 0 such pixels — confirms both that POIs actually render
and that the checkbox actually controls it, at the pixel level, not just
"the code path didn't crash".

### v20 → v21: real POI category icons, not plain dots (this session)

**The user's request (verbatim):** *"lets do poi icons."*

**`POI.DB3`'s icon schema — CRACKED, a clean, fully self-documenting
chain, real standard PNG images throughout.**
`PoiPartition_BaseAttributes.Icon_ID` → `Image_BaseAttributes.Image_ID`
(validated directly: joining the two and comparing each partition's own
real CATEGORY name against its linked image's own real NAME shows an
exact or near-exact match for every partition checked — e.g. partition 3
`"gas station"` → an image itself named `"gas station"`; partition 14
`"atm"` → `"atm eur"`) → `Image_ImageBlob_Relation` (filtered to one
`ImageSet_ID` — `ImageSet_BaseAttributes` names 4 real sets,
`2D.34.39.PNG.Day`/`.Day.Shadow`, `3D.34.39.PNG.Day`/`.Day.Shadow`;
`ImageSet_ID=1` — the plain 2D set, no shadow — is the natural choice
for this viewer's top-down 2D view) → `ImageBlob_BaseAttributes.
ImageData`, which is a REAL, STANDARD PNG FILE (confirmed via its own
magic bytes, `89 50 4E 47 0D 0A 1A 0A` — no proprietary container at
all). Every icon in the `2D.34.39...` sets is exactly 34×39 pixels — the
SAME dimensions already found for `tpd/`'s own `ICONS/` PNG folder
(§3.24), consistent with a shared/sibling icon set across both POI
subsystems on this disc. `HotSpotX`/`HotSpotY` (17, 19 for these icons)
give each icon's own real anchor point. **Visually confirmed**: decoded
and saved several real icons directly — a genuine, recognizable gas
pump (partition 3), airplane (partition 24, `"airport"`), and pharmacy
cross (partition 11) — not garbage or placeholder art.
`poi_db_reader.load_poi_icons()` implements the whole chain, returning
raw PNG bytes per `PoiPartition_ID` (no PIL dependency in `research/` —
the viewer decodes).

**Viewer integration**: `App._get_poi_icon()` decodes each of the 61
real icons once (PNG → `PIL.Image`, RGBA) and caches it for the App's
whole lifetime. `_redraw()` pastes the real icon (alpha-composited,
anchored at its own real hotspot) into the SAME rasterized bitmap as
road dots, in place of the plain colored dot used in "v19 → v20" —
**measured at ~0.0056ms per paste**, so even the widest realistic view
(100k+ POIs) stays well under a second (confirmed: a whole-EEU 500km-span
redraw with POIs on takes 0.150s total). Falls back to the plain dot
only if a partition has no resolvable icon (not observed on the
reference disc).

**A real problem found and fixed while testing on the real ISO: icon
clutter.** A real, dense area (central Sofia at a ~6km span, where every
POI category active within that range legitimately has hundreds of real
entries) rendered as a solid, unreadable wall of overlapping icons on
the first pass — confirmed directly by rendering and visually inspecting
a real screenshot, not assumed. **Fixed** with a cheap grid-occupancy
declutter: each icon's own anchor point is bucketed into a
`POI_ICON_CELL_PX`-sized cell (52px, padded past the 34×39 icon size for
breathing room), and any POI whose cell is already taken is skipped —
caps rendered density to roughly one icon per cell regardless of how
many real POIs are actually in view. Re-rendered the same real Sofia
area after the fix: genuinely readable, recognizable icons (gas pumps,
restaurant fork/knife, coffee cups, pharmacy crosses, parking `P`, bank
`€`) spread across the view with visible road detail between them, confirmed
by direct visual inspection of the re-rendered output — not just "the
code ran".

**Disclosed limitation, not fixed this session**: which POI "wins" a
contested declutter cell is simply whichever one `pois_for_bbox()`
returns first (no priority weighting) — `PoiPartition_BaseAttributes.
MapPriority` is uniformly `255` for every real partition on the
reference disc, so it carries no usable signal for this. A future
session could weight by real-world rarity/importance instead of query
order if this matters more.

### v21 → v22: POI click-to-identify (this session)

**Natural completion of the POI feature arc**: with real icons now on
the map ("v20 → v21"), the obvious next gap was that clicking one did
nothing — road points/edges were already click-to-identify-able
("v6 → v7"/"v16 → v17"), but POIs weren't.

`find_nearest_poi()` (module-level, same pixel-distance-metric contract
as `find_nearest_point()`) is checked FIRST in `App._on_point_pick()`,
before road points/edges — a real icon is the visually obvious "target"
at its own screen position, and its own pick radius
(`POI_PICK_RADIUS_PX`, 18px) is deliberately wider than a road dot's
10px, matching a 34×39 icon's real on-screen size rather than a 1-2px
dot. **Correctness detail**: it searches `App._rendered_pois` — the
EXACT set the last `_redraw()` actually drew AFTER the "v20 → v21"
declutter pass — never the full, undecluttered `pois_for_bbox()` result,
so a click can only ever hit something the user could actually see. A
hit shows the POI's real name and category in the status bar (no
picked-points panel row — that panel's columns, `tile_id`/
`feature_index`/etc., are road-specific debugging fields a POI simply
doesn't have).

**Verified with real, running-`App`-level tests**: right-clicking
exactly at a real rendered POI's own screen position correctly reports
`"POI identified: GO -- gas station (23.276820, 42.683760)"` for a
named one and `"POI identified: (unnamed) (...)"` for an unnamed one
(real data — most POIs simply don't have a `Name`); a click in genuinely
empty space (no POI, no road point, no edge nearby) correctly falls
through to the existing "no rendered point or road segment" message,
confirming no false-positive POI hits.

### v22 → v23: POI search (this session)

**Completes the POI feature arc**: crack → display → icons →
click-to-identify → now search — the same unified search box (already
merging road + city results, §10 "v13 → v14"/earlier) now also searches
real POI names.

`poi_db_reader.search_pois(cache, query, limit)` is a plain, case-
insensitive linear substring scan over `load_poi_cache()`'s own
`name_upper` list (a new precomputed field, uppercased once at load
time so a repeated search never re-uppercases 4.7M strings). **Measured
on the reference disc**: ~0.20s per search (e.g. `"MCDONALD"` → 4,781
real matches) — acceptable for an explicit "press Enter" interaction
this app already runs inside a `BackgroundTask` (never blocks the UI
thread), not attempted as live per-keystroke filtering.
`MapData.search_combined()` now returns a 4-tuple (`hits, road_total,
city_total, poi_total`) — every existing call site (the App itself,
3 in `test_map_viewer.py`) updated to match. `SearchHit` gained a
`"poi"` kind (tagged `[POI]`, showing its real category alongside the
name) and a proper breadcrumb branch (previously any non-city hit fell
through to a hardcoded `"ROAD"` label, which would have mislabeled a
POI hit).

**Verified with a real, running-`App`-level end-to-end test**: typing
`"MCDONALD"` and running the real search returns 20 shown POI hits (of
4,781 total) alongside genuine road/city results; selecting a POI
result and jumping to it lands `center_lon`/`center_lat` exactly on
that POI's own real coordinates, and the breadcrumb correctly reads
`RESTAURANTS | POI | MCDONALD'S` — not the old hardcoded `"ROAD"` label
a POI hit would previously have gotten.

### v23 → v24: `mp0` district-name table + zone-2 candidate flag slots + zone-3a candidate speed limits surfaced in the point-pick panel (this session)

**Standing rule established this session**: every real discovery gets
implemented in this viewer, not just documented in the research files —
previously only the `mg4` "predicted divided" overlay had ever been
wired in (§3.6/§8), and only because it was explicitly requested.

Three new EXPERIMENTAL, `mp0`-only rows now append to the picked-points
panel on an ordinary point pick (or an edge pick), alongside the
existing "nearby streets" enrichment:
  - **Tile area label(s)**: `MapData.get_tile_district_names()` →
    `mcr.extract_district_names()` — the real, independently-verified
    Bulgarian/English district-name table (§3.16/§8). TILE-level, not
    attributed to the specific picked point.
  - **Zone-2 candidate flag slot(s)**: `MapData.get_tile_seg_zone2_
    summary()` → `mcr.decode_mp0_zone2()`/`zone2_categorical_slots()` —
    the generalized (not hardcoded to one tile's own tag byte) version
    of the zone-2 record crack (§3.16/§8). Structure validated
    (exhaustive DP, zero-leftover coverage on every tile tested); the
    real-world meaning of any given slot's value is explicitly NOT
    claimed. Generalizing this surfaced and fixed a real
    over-permissive-trap bug in its own boundary-finding (a `subidx <=
    10` plausibility guard, §3.16/§8) — re-verified to change nothing
    about the already-validated 949-record result on the original tile.
  - **Zone-3a candidate speed-limit-shaped value(s)**: `MapData.
    get_tile_seg_zone3a_summary()` → `mcr.decode_mp0_zone3a()`/
    `zone3a_speed_distribution()` — the generalized speed-limit
    candidate (§3.16/§8), built on the corrected zone-2 boundary above.
    Reproduces the original tile's exact speed distribution and
    generalizes to 4 of 5 more tiles tested, including a wider but still
    clean multiple-of-10-km/h range on a Sofia-airport tile. NOT
    ground-truth-confirmed on any tile.

All 3 follow the existing best-effort-enrichment pattern (`try`/`except`
→ empty string, never blocks or crashes an ordinary pick) and the
`_predecode_caches`-reuse-then-disk-fallback pattern already used by
`get_tile_adjacency()`/`get_tile_seg_prediction()`. `test_map_viewer.py`
re-run in full after every addition — all tests still pass, zero
regressions.

**Update, still this session**: fixing a regex-truncation bug in
`extract_district_names()` (widened `{3,40}` → `{3,200}`, §3.16/§8)
took `WW`/`X` from 95.8% to 100.0% exact match, and with clean data
revealed `Y`/`ZZ` encode a real highway-sign route↔destination
structure. The "tile area label(s)" panel row now uses `mcr.
group_district_name_signs()` to join paired entries into one readable
`"9/E87 -> BURGAS/SOFIA"`-style label instead of 2 separate-looking
strings — itself EXPERIMENTAL (84.7% validated, not perfectly clean).
`test_map_viewer.py` re-run again, all tests pass.

**Update, still this session — a REAL (not experimental) new panel
row.** The entries `extract_district_names()` deliberately excludes
(phonetic transcriptions, `|`/`$`/apostrophe) turned out to be real
embedded TTS pronunciation-guide data, cross-referenced and CONFIRMED
against `eeu.abc`'s own language table (§3.11's `(flag_a, flag_b)`
crack). `mcr.extract_pronunciations()` parses these into clean
name/pronunciation pairs; `MapData.get_tile_pronunciations()` and a new
"pronunciation guide(s)" panel row surface them on point pick —
exactly the kind of data a real GPS unit uses for voice announcements,
so it earns a spot even though (like the district-name table) it's
TILE-level, not attributed to the specific picked point. Unlike most of
this session's other `mp0` panel rows, this one is NOT labeled
EXPERIMENTAL — the underlying field meaning is genuinely confirmed, not
a candidate. `test_map_viewer.py` re-run once more, all tests pass.

### v24 → v25: a REAL, SEVERE bug found and fixed — every app close leaked its entire temp workdir (this session)

**User-reported, confirmed directly against a real system's own temp
folder.** `MapData.__init__()` creates a real `tempfile.mkdtemp()`
workdir per ISO opened (extracted copies of `eeu.cty`, all 5 `eeuz.mg*`/
`mp0` layer files, `POI.DB3`, a `search/` subfolder — often 500MB-3GB+
per open) and `MapData.close()` cleans it up correctly (`shutil.
rmtree`). But `close()` was ONLY ever called from `on_open_iso()`, when
replacing an already-loaded ISO with a different one in the same
session — never on normal app shutdown. No `WM_DELETE_WINDOW` handler
and no `atexit` registration existed anywhere in the file, so closing
the app via the window's X button (or Alt+F4) exited the Python process
without ever calling `close()`, silently leaking the ENTIRE workdir
every single session.

**Confirmed with real evidence, not just code reading**: the real
system this project runs on had **56 leaked `rns510_viewer_*`
directories totaling 146GB**, dating back to this project's own early
sessions (Sep 18) — one sample directory alone was ~490MB just for the
4 non-`mp0` layer files. Verified no viewer instance was currently
running (only the test suite itself, via `Get-CimInstance
Win32_Process`) before deleting all 56 with the user's explicit
confirmation.

**Fixed** with a real `self.root.protocol("WM_DELETE_WINDOW",
self.on_close)` handler — `App.on_close()` calls `self.data.close()`
(if an ISO is loaded) before destroying the window, exactly mirroring
the cleanup `on_open_iso()` already did correctly when switching ISOs.
`test_map_viewer.py` re-run in full after the fix — all tests pass.

### v25 → v26: "Show tile boundaries" checkbox (this session, user-requested)

Prompted directly by the real cross-tile adjacency gap found this
session (§8 item 5): a user-reported road connection crossed from `mg4`
tile 2384 into tile 2385 entirely — a class of gap `resolve_topology_
adjacency()` has no mechanism for at all. `MapData.active_tile_bboxes()`
computes each currently-pooled tile's own bounding box from its
already-decoded points (`tile_caches`, no extra disk I/O) — no real
per-tile grid bbox is stored on-disc for these layers (checked:
`decode_tile_header()`'s own 12-word header has no such field), so
this is a pragmatic, data-derived box, not a claim about the format's
own exact tile-grid geometry. **Sanity-checked directly against the
real cross-tile report**: tile 2384's computed bbox ends at lon
23.45547; tile 2385's begins at lon 23.4555 — a near-exact match, and
the reported point 132 (lon 23.45508) sits almost exactly on that
edge, confirming the boundary overlay will genuinely help spot more
candidates like it. New "Show tile boundaries" checkbox draws each box
as a thin outline rectangle, rasterized into the same single `PIL`
image as every other overlay (never individual canvas items — a wide,
zoomed-out viewport can pool 1,000+ tiles, and this project already
learned the hard way, "v17 → v18", that per-item Tk canvas overhead at
that scale is a real, measured freeze). Drawn first, under all
points/roads, so it never obscures real data. OFF by default.
`test_map_viewer.py` re-run in full, all tests pass.

### v26 → v27: "Hide decode garbage" checkbox REMOVED entirely (this session, user-requested)

User request (verbatim): *"remove the hide decode garbage mechanism, i
keep it always off because it doesnt help"* — consistent with the
checkbox's own history (§10 "v15 → v16": real-ISO testing had already
found the oscillation filter net NEGATIVE for real dense-urban
rendering, which is why it defaulted to unchecked). The checkbox, its
`BooleanVar`, and its `_on_hide_garbage_changed()` handler are gone
entirely — nothing in the running app can re-enable the filter anymore,
so real usage always gets the raw, unfiltered (measurably more
complete) geometry. `MapData.trim_oscillation`/`set_trim_oscillation()`
are KEPT as a programmatic-only API (`decode_features()`'s own
`trim_oscillation=True` detector still exists in `research/
map_compressed_reader.py` for research use, and `test_map_viewer.py`
still exercises the toggle directly against the real ISO — one shared
`MapData` instance is deliberately pinned to `trim_oscillation=True` so
dozens of unrelated, already-recorded exact point-count assertions
elsewhere in that file stay reproducible) — only the UI surface is
gone. The removed checkbox's own GUI test was rewritten to call
`MapData.set_trim_oscillation()` directly instead of through the now-
gone `App` handler, preserving the same real coverage (toggling
actually re-decodes and changes the real point count, caches correctly
invalidated) with no UI involved. `test_map_viewer.py` re-run in full,
all tests pass.

### v27 → v28: a real, confirmed bug fixed — `max_edge_m=200` was wrongly dropping real `mg4`/`mg3` edges (this session, user-reported)

Continuation of the user's "missing points" report (§8 item 5 has the
full investigation): a real `mg4` edge (points 72↔74, 1,518m, a genuine
divided-road carriageway transition) was being silently dropped by
`resolve_topology_adjacency()`'s own `max_edge_m=200` default, which
was calibrated only against `mg2`/`mp0` ground truth and never
validated against `mg4`/`mg3` (the coarsest layers, where long real
edges between shape points are normal). Auditing just one feature found
28 real edges dropped this way. **Fixed at the call-site level**: new
`MAX_EDGE_M_BY_LAYER` dict (`mg4`/`mg3`: 5,000m; `mg2`/`mg1`/`mp0`:
unchanged 200m), threaded into both of `MapData`'s own
`resolve_topology_adjacency()` call sites via the `layer` already in
scope there — the function's own default is untouched, so its existing
`mg2`/`mp0` ground-truth validation still applies unchanged. Verified
with a real, live redraw test: rasterized connected-roads line pixels
increased at 2 different Sofia-area zoom levels (667→1,183, 1,055→
1,460) — confirmed more real edges now drawn, re-run twice for
determinism, not a regression. `test_map_viewer.py` re-run in full
(twice, since one run hit an unrelated, non-reproducing timing flake in
the Address Entry panel-visibility check — confirmed NOT caused by
this change by a clean re-run), all tests pass.

### Two more real bugs found while building/testing v2 (beyond the v1 bugs below)

- **`_initial_scale()` outlier sensitivity.** A single decoded feature can
  legitimately be a long chain whose far end is a meaningful fraction of a degree
  (occasionally approaching the full `MAX_FEATURE_DRIFT_DEG=3.0` tolerance) away
  from the searched point. Letting one such outlier set the initial auto-fit zoom
  collapsed a real Tirana-area load to a near-country-wide scale, at which point
  far-away-but-genuinely-large cities (Bari, Ancona, Split — real Adriatic port
  cities, just hundreds of km away) out-ranked Tirana's own label. Fixed by
  clipping the auto-fit's bounding-box calculation to a generous multiple
  (2.5x) of the requested jump span; this only affects the one-time initial zoom
  choice, not what gets drawn once framed.
- **A minority of `eeu.cty` records have an implausibly huge bounding box.**
  Found while tuning zoom-dependent city importance: a small number of records —
  so far only observed among postal-code-tagged sub-entries, e.g. `"185 45,
  PEIRAIAS"` (real Piraeus is a compact Athens-area port city) — have a bbox
  spanning tens of degrees (in one observed case, ~34 deg²: most of the southern
  Aegean/Balkans for what should be one postal code's neighborhood), sitting
  right next to sibling entries for the SAME place with normal, tight boxes.
  This is not a decode-offset bug (surrounding fields on the same record decode
  sanely, e.g. `country_tag=120` correctly for Greece, and neighboring records at
  adjacent file offsets are fine) — it looks like a genuine data-quality quirk in
  a minority of source records, newly documented in `city_reader.py`'s
  `CtyCache.query()` docstring. Because "rank by bbox area" is this project's own
  established zoom-importance proxy (§3.8), an unfiltered ranking lets these
  degenerate records win every low-zoom label slot by sheer (spurious) size,
  crowding out the real large cities actually in view. Mitigated with an optional
  `max_area` cap on `CtyCache.query()` (the map viewer passes `CITY_MAX_AREA_DEG2
  = 2.0`, comfortably above any genuine city/admin area observed — Timișoara's
  is ~0.1) — the reader itself still returns the raw, unfiltered records (no
  silent data-hiding), a filtering consumer just has to opt in.
- Separately, `App._ensure_center_city_included()` guards a related, subtler
  case: even after the above fix, a WIDE viewport can still rank a real (not
  degenerate) but much bigger surrounding admin area's box above the actual
  place at the view's center — observed directly: a rural municipality
  ("ZALL BASTAR") northeast of Tirana has a bbox that also legitimately covers
  central Tirana's coordinates. The fix looks up whichever real `.cty` record
  most TIGHTLY contains the exact center point (smallest bbox among all
  containing records, using §3.8's own nested-bbox hierarchy) and makes sure
  that one specifically is represented, not just any containing record.

### Carried-over v1 bugs (still relevant, unchanged this session)

**Found and defensively handled**: on a real `mg3` tile near Iași,
`find_tile_anchor()`'s `"bruteforce"` fallback path produced an outright corrupt
anchor/feature thousands of km from the tile's true location. The viewer guards
against this (drops any feature straying >3° from its own tile's anchor,
`MAX_FEATURE_DRIFT_DEG`) but the underlying fallback path in
`map_compressed_reader.py` could use tighter verification in a future session
(see §3.6 caveat note).

**Found and fixed at the source**: rendering a real `mg3` area near Sofia,
Bulgaria produced long straight "spike" lines — two decoded features
oscillating 24-33km between two near-fixed latitude bands, well within the 3°
drift guard above. Root-caused to `decode_features()` running a block's declared
point_count past where its real geometry ends into misread non-coordinate bytes
(see §3.6's "oscillating overrun" writeup). The viewer calls
`decode_features(raw, declen, trim_oscillation=True)` in `MapData.decode_tile()`,
which removes both Sofia spikes cleanly.

**Follow-up this session, also confirmed and re-checked against the real ISO**:
a fresh manual investigation near Turin, Italy (`mg3`, lon=7.71507/
lat=45.09368) found the same oscillating-overrun signature still slipping
through the old single-cutoff mitigation in two ways — a second cluster
hiding inside what the old code reported as a "clean, kept" prefix
(tile_id 61), and a cluster the old code missed entirely because it only
ever looked for the FIRST one (tile_id 1330). `decode_features()`'s
detector and reassembly were redesigned (multi-cluster scan + split into
surviving sub-features instead of truncating — see §3.6 for the full
before/after numbers, including the new 42/80 validation result). Re-
running the same jump-detection style check used to originally find the
Sofia bug, over the same Turin-area viewport: single-step jumps >1km
across all pooled features dropped from 551 to 399 (max jump 10.4km→
8.1km, total "wasted" jump distance roughly halved, 1,759km→896km) —
a real, measured improvement, though not a total elimination: tile_id
1330's specific corruption remains uncaught (see §3.6) and is visible
among the remaining jumps in this same viewport.

### Known v2 limitations (explicit, not oversights)

- `tile_ids_in_bbox()`/`find_tile_for_coord()` are anchor-inside-box/nearest-
  anchor, not exact tile-boundary containment (no tile extent was ever
  recovered — §3.6/§8) — a coordinate near a tile edge might miss a
  technically-adjacent tile's content until the viewport nudges further.
- Road "importance" styling (thicker/darker for longer named runs) is a
  vertex/run-length proxy, not a real road-class field (still unresolved, §3.1).
- `decode_features()` still can't split one rendered chain back into
  per-named-road segments at the geometry level (the topology table that would
  allow this is still uncracked, §3.6/§8) — `name_features()` only ATTACHES
  names to vertex ranges of the geometry as already decoded, it doesn't re-cut
  the polyline. **As of v4 (see "v3 → v4" above), this no longer produces a
  visible wrong-line artifact** — roads render as unconnected per-vertex dots,
  so a chain crossing several real streets just shows as several separately-
  labeled dot clusters rather than one continuous line jumping between them.
  The underlying data gap (can't cleanly separate one named road's geometry
  from its neighbor's within a chain) is unchanged, only its visual symptom
  is gone.
- The `eeu.cty` huge-bbox data quirk above is capped for display, not explained
  — a future session could investigate which record types/fields predict it.
- **`mp0`'s background-build window (unchanged since "v2 → v3"; its EFFECT
  changed in "v4 → v5" from a full layer swap to an additive fold-in)**:
  `mp0` (the densest layer, `build_geo_index()` measured 34-55s on the
  reference disc, see §3.6) is still not opened eagerly — it loads in the
  background right after "Open Map ISO" and folds into the same pooled view
  automatically once ready (see "v4 → v5" above). The honest edge case:
  before that finishes, the view shows only whatever the 4 fast layers have
  — not an error, not a block — which can still look near-empty in an area
  that's sparse in every fast layer but has real content in `mp0` (measured:
  a tight Sofia-area box has 0 tiles in mg1-mg4 but 1 tile/2 features/426
  points in mp0) — see "v2 → v3"/"v4 → v5" above for the full writeup. This
  is a real, un-eliminated rough edge, not an oversight: there was no way
  found to make `mp0`'s own geo-index build meaningfully faster (§3.6's
  `build_geo_index()` already reads every tile's exact byte range once, no
  wasted I/O), so a background window of some length is inherent to the
  current approach.
- **[SUPERSEDED TWICE — "v4 → v5" then "v5 → v6"]** The v3 automatic
  single-layer model and its hand-picked `SCALE_LAYER_THRESHOLDS` were
  removed entirely in v4→v5, replaced by pooling every available layer at
  once regardless of zoom. **v5 → v6 (this session)** reinstated a
  `SCALE_LAYER_THRESHOLDS` table (reusing v3's own boundary values — see
  "v5 → v6" for why that's sound) and a scale-dependent layer SET again, but
  cumulative/additive rather than v3's single-winner swap — see "v5 → v6"
  above for the full current design; this bullet's original concern (were
  the thresholds well-tuned) is answered the same way each time: not
  perfectly tuned by design, retune if better numbers are found.

Non-GUI functional test: `test_map_viewer.py` (run with `py test_map_viewer.py`)
— covers viewport-bbox math, both new in-memory caches, unified search, dynamic
area loading (including cache-reuse and cache-growth-not-eviction checks on
panning), real names/cities actually appearing in decoded data, actual canvas
rendering (item counts + label text) driven with real ISO data, the
GUI-construction smoke test (now also asserting no layer dropdown/Combobox
exists anywhere in the widget tree), `mg1` wiring, and ("v4 → v5") multi-layer
pooling behavior end to end: `available_layers()` before and after
`load_heavy_layer()`, a real same-bbox multi-layer pooling check proving the
total is an exact flat sum of each layer's own decode output (not
combinatorial), the full background-`mp0`-load → additive-fold-in path with
real point-count evidence before and after, and real `App._redraw()`
wall-clock timing at both layer-availability states on the same dense real
bbox. As of **"v5 → v6" (this session)**: pure-function `layers_for_scale()`
cumulative-growth/mp0-gating checks; a real-ISO scale sweep at a fixed Sofia
bbox proving monotonic/additive point-count growth and confirming a zoom
back out to a low scale drops the finer layers' points again while their
tiles stay cached (`new_tiles == 0` on re-zooming back in); mp0 confirmed
excluded at a low scale even once it's ready; and a full end-to-end GUI
check that `App._maybe_reload_viewport()` really triggers a background
reload purely from a layer-set change (bbox provably still covered,
confirmed via `bbox_contains` before the reload fires) in both the zoom-in
and zoom-out directions. `test_core.py` (the separate editing tool's own
suite) was re-run unmodified and confirmed unaffected.
