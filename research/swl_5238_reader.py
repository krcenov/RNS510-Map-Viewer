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
`INFO/` folder, the rest of it -- CRACKED (a still-later session,
user-asked "check these files what are they? anything interesting
inside?"): `USER.CFG`, `INOUT.TXT`, `CDSTRUCTTMP.CFG` -- real,
substantial NEW material, not just `CDSTRUCT.CFG` padding.
`HISTORY.TXT` -- genuinely empty, 0 bytes, nothing to find
============================================================================
`USER.CFG` (184 lines) is the REAL factory build-configuration input for
THIS SPECIFIC DISC -- not a generic template, an actually-filled-in one
-- and settles several things this module previously only inferred:

  - **Real named engineers, for the first time**: its own header says
    "This is the User configuration file which controles the
    CdStruct.cfg file... If changes are needed please contact
    **David Yates** or **Torsten Hildebrand**." This disc's own
    `<AUTHOR>` tag: `RoNe`.
  - **Real facility**: `<VERSION_FILE_HEAD>` reads "Software Loading CD
    for CP2 based units / (c) CONTINENTAL Wetzlar" -- Continental's
    Wetzlar, Germany site (the former Siemens VDO Automotive location --
    ties directly to the `(c) 2005 Siemens VDO Automotive AG` string
    already found inside the `HOST` BSP image, above) is now directly
    confirmed as the real build facility, not inferred.
  - **`<LOGISTIC_DATA>`**: `#Integrationphase: Delivery cw45/12
    C10/C12/C6-samples` -- this exact disc was a calendar-week-45-2012
    delivery of HARDWARE SAMPLE units for the C6/C10/C12 revisions
    specifically (ties directly to `BLSCRIPT.CFG`'s own 4 hardware-match
    sections, above -- this is the disc that has C6/C10/C12 = 1 and
    C3/C4A/C4B/C14 = 0 in the block below).
  - **A large `<PREDEFINITIONS>` block is the actual filled-in
    `#ifdef` flag set** driving `CDSTRUCT.CFG`'s own conditional-build
    logic (already characterized above as a real but unparsed grammar --
    this is what a REAL instance of those flags looks like). Confirms
    `EUROPA=1` / `NORTHAMERICA=0` / `JAPAN=0` / `CHINA=0` (this disc is
    Europe-only) and enumerates a real, complete per-vehicle-platform
    flag list: `PQ`, `SK` (Skoda), `SE` (Seat), `SB` (Skoda **Superb** --
    matches `PRJCTMAP.TXT`'s own `SB`=Skoda-Superb inference, now
    confirmed independently), `PH` (Phaeton), `T5`, `BY`, `BM`, `PHGO`,
    `AK`, plus NAR-only codes `TH`, `GN`, `CH184` (ties to `H_PQ_184.frg`/
    `H_TO_184.frg` seen in `INOUT.TXT`, below), and China-only `NMS`
    (VW's real "New Midsize Sedan"/US-market Passat platform), `ECAR`.
    Also real, previously-unknown per-feature flags: `HDD` section's
    `40GB_HDD=1` (this variant's real HDD CAPACITY) and `TRAVELLINK=0`
    (the real "TravelLink" traffic/content service, present as a build
    option, disabled on this disc); confirms `IBOC=0` and `MPEG=0` for
    this specific disc (both exist as build options -- see `INOUT.TXT`
    below -- just switched off here); a `VUCI` section (`VUCBL`,
    `VUC_HEAL`) naming a subsystem this project has not examined at all.

`INOUT.TXT` (236 lines) is the build tool's own master file manifest --
maps every internal build-tree source path to the short on-disc filename
this whole project already works with elsewhere. Confirms real internal
platform naming (`BL_VW.FLI` <- `SSW\\SF_INTEGRA\\cp2\\bin\\flash\\ppc\\
fli\\bootloader.fli` -- `SF_INTEGRA` is the real internal platform
codename, ties directly to `BLSCRIPT.CFG`/the `SSW_VW-RNS` BSP above) and
surfaces several genuinely new, never-before-mentioned components:

  - Per-vehicle-platform CAN gateway routing tables (`PQTABLE.FLI`/
    `TOTABLE.FLI`/`SKTABLE.FLI`/`PHTABLE.FLI`/`T5PQTBL.FLI`/
    `T5TOTBL.FLI`, each really named `GWTABLE.FLI` in its own
    platform-specific source folder) -- the gateway routing table
    differs by VEHICLE PLATFORM, not just hardware revision.
  - Regional radio tuner firmware: `RADIO.FLI`<-`VWRnsEur.fli`,
    `NARRADIO.FLI`<-`VWRnsNar.fli`, `JAPRADIO.FLI`<-`VWRnsJap.fli`.
  - **`IBOC.FLI`** <- `IBOC\\iboc.fli` -- a completely new subsystem:
    In-Band On-Channel, the North American HD Radio standard. Real
    build flag (`IBOC=0`/`FORCE_IBOC_UPDATE`) also confirmed in
    `USER.CFG` above.
  - **A parallel DVD-based nav-firmware line**: `FDVD.FLI`,
    `FSE_DVD.FLI` (Seat DVD variant), sitting alongside the
    already-exhaustively-studied HDD line (`FHDD6.FLI`/`FSE_HDD.FLI`/
    `FSE_HDD6.FLI`) -- plus an OLDER HDD-firmware generation,
    `FHDD4.FLI`. This whole project has only ever looked at the `FHDD6`
    line; `FDVD`/`FHDD4` are unexamined siblings.
  - **`CCC_NAVP.FRG`/`CCC_NAVP_BY.FRG`** <- `JNAV\\CCC_navp.frg`/
    `JNAVBY\\CCC_navp.frg` -- a separate Java-navigation-specific
    fragment (`JNAV`), distinct from `FHDD6.FLI`, not examined.
  - **`SIRIUS.DB3`** <- `SIRIUS\\NA_SIRIUS.DB3`, plus `MDSIRIUS`/
    `DELSIR` management scripts (`WA\\MD_SIR.WSH`/`WA\\DEL_SIR.WSH`) --
    a **SiriusXM satellite radio** database, North-America-specific, a
    subsystem never mentioned anywhere else in this project.
  - `RVCLOW.WSH` -- a rear-view-camera-related script; ties directly to
    the `cpdrVideoInSetSource ... RVC` video-input source found in the
    `HOST` BSP disassembly, above (independent corroboration from a
    completely different file).
  - Real per-script purposes for several already-known `WA/*.WSH` names:
    `RECOG`/`RECOG_N` <- `RECOG_ON.WSH`/`RECOG_OF.WSH` (toggle speech
    recognition on/off), `FHDD`/`PARTHDD`/`FORMHDB1` (format/partition
    the HDD), `DEL_ERRL` (delete the error log -- matches
    `CDSTRUCTTMP.CFG`'s own `"080204-MaRu: Added DEL_ERRL for
    Factory-CD"` changelog entry, below), `CTEST` <- `WA\\CTEST.OUT`
    (confirms the already-fully-disassembled ELF diagnostic object's
    real internal short-name, tying 2 independently-analyzed files
    together).

`CDSTRUCTTMP.CFG` (4,853 lines) is an EARLIER DRAFT of the final,
25,955-line `CDSTRUCT.CFG` already characterized above -- and its
leading changelog comment block is longer and more detailed than what
survives in the final file: a real, dated (2006-2008), named-engineer
engineering log (`AKls`/`m.`/`y.`/`MaRu`/`AKr`) that gives ACTUAL CONTEXT
for bug IDs this project previously only knew as bare numbers:

  - `TlaWtz#46435` -- `"070705-MaRu: Due to the Showstopper TlaWtz#46435
    an additional Restart_System is entered in front of RADIO"` -- a
    real, understood workaround, not just an ID.
  - `TlaWtz#47169` -- `"070725-MaRu: Take out COD_BAP workaround because
    of PR TlaWtz#47169"` -- this PR caused a workaround to be REMOVED.
  - `"080213-MaRu: adapted for EUR SB (Skoda Superb) with GW Tbl from
    SK and coding of SK"` -- direct, independent confirmation `SB` =
    Skoda Superb (matches `PRJCTMAP.TXT`'s/`USER.CFG`'s own inference).
  - `"080708-MaRu: Adaptation for VUC-SEAT_HDD"` and `"...Adaptation for
    JNAV loading (JNAVMNT.WSH)"` -- ties the `VUCI` and `JNAV`
    subsystems (both otherwise-unexamined, above) to real, dated
    feature work.
  - `"081024-AKr: New type BM"` -- confirms `BM` (a `PREDEFINITIONS`
    flag in `USER.CFG`, above) is a real, distinct project/vehicle type,
    introduced at a specific date, not a typo or leftover.
  - A real `//ECUORDER` parameter comment, self-documented by its own
    author: `0 1` = user input required (OK/CANCEL), `1 1` = no user
    input -- a real, load-bearing flashing-flow control parameter,
    directly explaining behavior already observed in `DLSCRIPT.TXT`/
    `BLSCRIPT.CFG` above (screens that wait for a button vs. ones that
    don't).

`HISTORY.TXT`: confirmed genuinely empty, 0 bytes. Nothing to find --
recorded here only so a future session doesn't re-open it expecting
content.

============================================================================
`BLSCRIPT.CFG` -- CRACKED (a still-later session, user-asked "what is
this"): the BOOTLOADER's own config, ONE STAGE EARLIER than
`DLSCRIPT.TXT` below -- genuinely new, disc-root-level, not per-variant
============================================================================
Sits at the disc ROOT (`RNS510_5238_MOD_C3_C4\\BLSCRIPT.CFG`), not inside
any `APPS/SILVER_1/<variant>/CONFIG/` folder like `DLSCRIPT.TXT` -- there
is exactly ONE of these per disc, shared across every project variant.
Its own header comment says exactly what it is and settles its place in
the boot chain without any guessing needed: "The BlScript will be parsed
by the bootloader only. This is the file only where the bootloader is
dependent to. It describes the process how to load the right SWL
application and what to show during SWL application loading on the
screen." I.e. this runs BEFORE any `DLSCRIPT.TXT`-driven install step
below -- the bootloader reads this file directly, off raw hardware
detection, before the SWL (Software Loading) application itself even
exists on the unit.

Real, fully self-documented grammar (a `[FORMAT]` section spells out its
own field meanings): a `[HW_INFO]` block declares 3 named hardware
registers read via `<AREA ID>.<GIID>` pairs (`HW_MODULE_ID = 01.08`,
`HW_VERSION = 01.01`, `CUSTOMER_PRODUCT_ID = 01.07`), then a series of
`[<CUSTOMER_PRODUCT_ID>.<HW_MODULE_ID>.<HW_VERSION BEGIN>.<HW_VERSION
END>]` section headers (wildcard hex ranges, e.g.
`[0x000201XX.0x00010002.0x00000000.0xFFFFFFFF]`,
`[0x0002XXXX.0xXXXXXXXX.0x00000000.0xFFFFFFFF]`,
`[0x0005XXXX...]`, `[0x0006XXXX...]` -- 4 total on this disc, one per
matched hardware family) select which section's script body the
bootloader runs for a given detected unit. Each body is a tiny drawing +
load script: `BAR`/`TEXT`/`PROGRESS_BAR` directives paint a progress
screen (the `TEXT` directives pull live version text straight out of
`VERSION.TXT`'s own `#CD:`/`#DATE:` fields via a
`<path;"search string">` lookup syntax -- the SAME `VERSION.TXT` this
module's own "Disc identity" section already parses), then
`LOAD_FLASH_IMAGE //cddos/SWL/SILVER_1/RNSMIDEC/SWL/SWL.FLI` flashes a
DIFFERENT image than `FHDD6.FLI` -- `SWL.FLI`, the standalone bootstrap
"Software Loading" application -- followed by `SET_BOOT_MODE 0x12` (sent
twice) and `REBOOT`. All 4 hardware-matched sections on this disc run the
IDENTICAL body; they differ only in which hardware IDs select them, not
in behavior.

**This completes the full boot-chain picture, now traced end to end**:
bootloader reads `BLSCRIPT.CFG` (this file) off raw hardware-register
detection -> flashes and reboots into `SWL.FLI` (small loader app,
already separately ruled out elsewhere in this module as unrelated
map/navicore code, just a bootstrap) -> THAT app is what parses
`DLSCRIPT.TXT` (below) -> which installs `A_HDD.FRG` and finally
`FHDD6.FLI` itself (the real navigation firmware this whole project
reverse-engineers). Nothing left uncracked here -- short, fully
self-documented, plain text.

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
shell scripts. NOT opened in THIS pass (out of scope; the `DLSCRIPT.TXT`
grammar itself was the target) -- see the dedicated section below, a
LATER session opened and CRACKED every one of them.

============================================================================
`WA/*.WSH` -- CRACKED (a still-later session, user-asked "check the
files here"): real VxWorks target-shell scripts, not a custom language --
reveal the real on-unit `/tffs0/lib/` filesystem tree AND the real
vehicle-coding bit definitions
============================================================================
This disc's `WA/` folder holds only 12 of the ~60+ files the master
`INFO/INOUT.TXT` manifest (above) lists across all builds: `CTEST.OUT`
(already fully disassembled, above), `CYCFLAG0.TXT`/`CYCFLAG1.TXT`,
`DEL_FOLD.WSH`/`DEL_LANG.WSH`/`DEL_OUT.WSH`, `FIXCOD.WSH`, and 5
REGION-CODING scripts (`EURPQTO.WSH`/`EURPQTOD.WSH`/`EURSEDAB.WSH`/
`ESKHDDL.WSH`/`ESKHDDDL.WSH`) dated **March 2013** on disk -- 5 months
AFTER every other file on this disc (Oct 2012) -- a later addition/patch
to this specific repack, not part of the original Oct-2012 burn.

**`.WSH` is literally VxWorks target-shell (WindShell) input, not a
custom scripting format**: every cleanup script uses the real WindShell
`sp xdelete, "<path>"` (spawn a task running `xdelete`) / `rmdir`
syntax -- `sp` is the exact command this project's own HOST-BSP
decompilation (above) already found in the shell's own built-in help
text (`"sp adr,args... Spawn a task"`). `CYCFLAG0.TXT`/`CYCFLAG1.TXT`
are each one line, `dlpSetCyclicFlag 0`/`dlpSetCyclicFlag 1` -- a real,
directly-invoked diagnostic-loading-protocol function call.

**`DEL_LANG.WSH`** deletes `/tffs0/data/speech/{uvo,synth,recog}` --
matches, exactly, `INFO/INOUT.TXT`'s own `UVO_*.ZIP` / `LANG_*.FRG`
(synth/TTS) / `REC_*.FRG` (recog) naming, above -- direct confirmation
of the real on-unit path each of those 3 fragment families installs to.

**`DEL_FOLD.WSH`** deletes `/tffs0/FLASH`, with a real German comment,
`"30.04.2008 MaRu # Flash-Ordner wird gelöscht"` ("flash folder is
being deleted") -- matches `INFO/CDSTRUCTTMP.CFG`'s own changelog entry
for this exact file, word for word: `"080430-MaRu: The flash folder is
deleted in ECU SWL and after every external ECU (Radio;MPEG;GW) (search:
DEL_FOLD.WSH)"` (above) -- 2 independently-read files agreeing exactly.

**`DEL_OUT.WSH`** (dated `06.07.2010`, author `RoNe` -- the SAME initials
as this disc's own `USER.CFG` `<AUTHOR>` tag, above -- a real engineer
active across at least 2010-2012) is the single richest file here: a
real change-request ID, `"Delete out files acc. to CR 54634"` (a
DIFFERENT internal tracker numbering style from the `TlaWtz#` bug IDs
already known -- a 2nd real internal tracking system), followed by ~20
real compiled-module paths under `/tffs0/lib/`, directly revealing the
live filesystem layout of the `APPS` processor for the first time (this
project previously only had file-internal debug strings, never a real
deployed directory tree):

  - `/tffs0/lib/mm/*.out` (multimedia): `mostgen.out`, `madMM.out`,
    `WMADEC.out` (WMA decoder), `MpegAtaSwitcher.out` (ties the ATA/IDE
    HDD driver found in the `HOST` BSP, above, directly to MPEG
    playback), `mm_drives.out`, `dab.out`, `util.out`,
    `servicebroker.out` (matches the `vdo::svc::dispatcher::Dispatcher`
    command/event-dispatch pattern this project's own firmware
    disassembly already found at the 25MB/30MB regions, above -- same
    architecture, now named on the real filesystem), `micromedia.out`,
    `mpeg4_celp_lib.out`/`mpeg4_celp_micromedia.out` (MPEG-4 CELP audio
    codec), `micromedia_wma.out`, `recorder.out`, `msdcontrol.out`.
  - `/tffs0/lib/pos/pos.out` -- the real positioning/GPS library.
  - **`/tffs0/lib/arriba/navcore.out`** -- this is the first DIRECT
    confirmation this whole project has had that `"Arriba"` (previously
    only ever a bare string COUNT, 28x, README S2.1) is a real product/
    codebase name and not just an incidental string -- its actual
    compiled navigation-core module is `navcore.out`, living in a
    directory named after it.
  - `/tffs0/lib/kernel/libDelayImage.out`, `fileMgr.out`; a lone
    `/tffs0/data/SysCfgConfig` (system config data, not a `.out` module).

**`FIXCOD.WSH`** independently confirms and extends the same picture:
`sp xdelete, "/tffs0/lib/Arriba/dbal.out"` -- `dbal.out` (this whole
project's single most-studied subsystem) sits in the SAME `Arriba/`
directory as `navcore.out` above (capitalization of `arriba` varies
`DEL_OUT.WSH` vs `FIXCOD.WSH` -- real-world inconsistency, not 2
different paths) -- direct, concrete proof `dbal` and `navcore` are
sibling compiled modules of the same product line, not merely
thematically related. Also references `/tffs0/data/fwdir/bundles/4` (a
real firmware/data "bundle" directory, workaround for "wrong Bundle
installations") and calls `IL_Flush` twice -- ties to the `InfoLog 1/2`
named flash regions already found decompiling the `HOST` BSP, above (an
"InfoLog Flush" function, real and invoked from userland scripts, not
just a flash-region label).

**The 5 region-coding scripts are real, human-readable VEHICLE CODING
DEFINITIONS** -- each calls `SetCoding(0x400, <value>, <bit>, 1)`, a
bit-indexed vehicle-options register at address `0x400`, with its own
plain-English comment per call. Comparing all 5 files resolves the real
bit map directly, no guessing:

    manufacturer field   0x02 = VW            0x05 = Skoda
    bit 2                HDD active           (0/1)
    bit 5                Tuner "RUDI" active   (a real internal tuner
                                                 codename, not previously
                                                 seen anywhere else)
    bit 6                DAB active            0 in EURPQTO/EURPQTOD,
                                                1 in EURSEDAB/ESKHDDL/
                                                ESKHDDDL
    bit 7                SDARS active          0 for EUR everywhere --
                                                SDARS is Sirius XM's own
                                                formal name, ties
                                                directly to `SIRIUS.DB3`
                                                (`INOUT.TXT`, above,
                                                NAR-market-only)
    bit 8                MPEG active           (0/1)
    bits 9-15             unused on this build (all 0 across every file)

Plus real register-level commands, identical across all 5 files:
`SetRegData(0xa91,0,0,2,0x8a)` ("Delete Presets"), `SetRegDataHex(0x21,
"01",0x0,0x1,0x1)` ("Testmode: Active" -- register 0x21 is a real
factory-testmode toggle), `SetRegDataHex(0x0B3A,"012C",0x0,0x2,0x89)`
("Speed limit DVD/TV: 300km/h" -- `0x012C` = 300 decimal -- a real,
concrete confirmation of the well-known automotive "no video while
driving" lockout feature, configured here to a factory/test threshold
rather than a normal low roadworthy one). `ESKHDDDL.WSH` (Skoda) adds
one more, not present in the VW-branded scripts: `SetRegDataHex(0x0a0a,
"01",0x0,0x1,0x1)`, commented `"Big VW Splashscreen in NAND: Not
Active"` -- register `0x0a0a` is a real per-brand splash-screen
selector, ties directly to the `SplashScr` named flash region already
found in the `HOST` BSP disassembly, above.

============================================================================
`WA/CTEST.OUT` -- the real vehicle-coding/register-data functions the
`.WSH` scripts above call, DISASSEMBLED end to end (a still-later
session, user-asked to chase this specific lead, then "what can we
tackle next" -> finish the remaining functions) -- a complete,
validated picture of 2 distinct real UDS-style diagnostic write paths
============================================================================
`CTEST.OUT`'s own symbol table (already known to this module -- see the
dedicated section below for its container/ELF details) names the exact
functions `SetCoding`/`SetRegData`/`SetRegDataHex`/`SetRegDataStr`/
`ReadRegData`/`DeleteRegData`/`SaveRegData` with real `.text` offsets.
All 7 disassembled with capstone, relocations resolved via `.rela.text`
(`R_PPC_ADDR16_HI`/`_LO` pairs target the instruction's own 2-byte
IMMEDIATE FIELD, i.e. `r_offset & ~3` gives the owning instruction --
easy to get wrong; a first attempt keyed lookups on the raw `r_offset`
and silently found nothing).

**`SetCoding(reg, value, offset, width)` -- real UDS-style "long
coding" (Kodierung) byte-array read/patch/write**, fully traced
instruction by instruction:

1. The logical register id (`0x400` in every `.WSH` call seen) is
   transformed into the real ECU diagnostic identifier by adding
   `0x3000` -- `clrlwi r9,r0,0x10; addi r0,r9,0x3000` -- giving
   `0x400 -> 0x3400`. Only taken when a flag bit in the input register
   id itself (PPC-bit 15) is clear, the normal case for every real call
   site found.
2. `ReadEcuData(status_byte, 1, 0x3400, &local_buffer, 0xff, 0)` reads
   the current coding byte array (a real external call, resolved via
   relocation, not guessed).
3. `width` computes a byte-shift amount (`(4-width)*8`) and `value` is
   shifted into the correct byte position of a 4-byte word, then
   `memcpy(&buffer[offset], &shifted_value, width)` patches EXACTLY
   `width` bytes at byte-offset `offset` -- confirming the `.WSH`
   scripts' 3rd/4th arguments are a byte OFFSET and BYTE WIDTH into a
   coding array, not a bit index (an earlier, less precise
   characterization from reading the `.WSH` comments alone).
4. `WriteEcuData(status_byte, 1, 0x3400, &buffer, length, 0)` writes
   the patched array back, using the length `ReadEcuData` itself
   returned.

**`SetRegData`/`SetRegDataHex`/`SetRegDataStr` -- a separate,
security-gated register channel via a real 4-slot function-pointer
table, `pReg`**: a global object (`pReg`), lazily registered once via
`svcb_addServiceListener(sServiceReg)` on first use. Requires a cached
2-byte global, `accKey` (see the dedicated correction below), fetched
once through `pReg[0x10]` before any write. `pReg` itself turns out to
be a real service vtable, mapped exactly by tracing all 6 RegData
functions against each other:

| `pReg` offset | Role | Confirmed by |
|---|---|---|
| `0x00` | read | `ReadRegData`, `SetRegData`, `SetRegDataHex`, `SetRegDataStr` (all read-modify-write) |
| `0x04` | write | `SetRegData`, `SetRegDataHex`, `SetRegDataStr` |
| `0x14` | delete | `DeleteRegData` |
| `0x1c` | save | `SaveRegData` |

`SetRegData`/`SetRegDataHex` share `SetCoding`'s exact read -> shift-
value-into-byte-position -> `memcpy` -> write-back shape, just through
`pReg[0x00]`/`pReg[0x04]` instead of `ReadEcuData`/`WriteEcuData`
directly, and return a real status byte. `SetRegDataHex` is the
identical routine, just parsing the value from a hex string (`"01"`)
first instead of taking a raw int -- confirmed structurally identical
to `SetRegData` past that point, matching its real call sites
(`SetRegDataHex(0x21,"01",...)` etc., above).

**`SetRegDataStr(reg, str_ptr, ?, width)` -- a 2nd, distinct write
style, genuinely new**: instead of a fixed-width integer shifted into a
byte position, this calls `strlen(str_ptr)`, bounds-checks the result
against `0xfe`, then `memcpy`s the STRING content directly into the
read buffer at the right offset -- a variable-length string write, not
`SetCoding`'s single/multi-byte integer write. Same
read-via-`pReg[0x00]` / write-via-`pReg[0x04]` outer shape otherwise.

**`ReadRegData(reg, ?)`**: the pure read half -- same `pReg`/`accKey`
boilerplate, calls `pReg[0x00]` with `(reg, &buffer, 0xff, accKey,
param2)`, returns the byte count `pReg[0x00]` itself reports, no patch/
write-back. Confirms field `0x00` = read independently of the
`SetRegData` family.

**`DeleteRegData(reg, ?)` and `SaveRegData(a, b)` -- a real access-
control ASYMMETRY, confirmed structurally**: unlike `Read`/`Set*`
(which silently call `pReg[0x10]` to acquire `accKey` on first use if
it's still 0), `DeleteRegData` and `SaveRegData` do NOT auto-acquire
it -- if `accKey` is still 0 when either is called, they immediately
`printf` an error string and return early, requiring the caller to have
already authenticated via a prior `Read`/`Set*` call. `DeleteRegData`
calls `pReg[0x14](reg, param2, accKey)` -> a status byte.
`SaveRegData` calls `pReg[0x1c]` with a real 9-argument signature
(`param1, 2, 0, 0, 0, 0, 0, accKey, param2` -- the literal `2` as arg2
is plausibly a "record type"/"save mode" constant; `param2` is spilled
to the caller's own stack frame, beyond the 8 GPR argument registers)
-- a genuinely more complex call than any other function in this
family, and one no `.WSH` script on this disc actually invokes.

**A real correction, made directly to the user rather than left
standing**: `accKey`'s NAME suggested "UDS SecurityAccess key" (service
`0x27`), and that label was used when first describing this to the
user -- WRONG, caught by 2 pieces of direct evidence. First, `accKey`
is a plain 2-byte `.data` global (`size=2` in `CTEST.OUT`'s own symbol
table) -- too small for a real crypto seed-key, and unable to hold
every possible 5-digit decimal VCDS-style code the user described from
real experience with this exact vehicle/tool (values 65536-99999
wouldn't fit in a `uint16`). Second, and decisively, `FHDD6.FLI`
itself contains 2 real debug format strings using the exact same name
in a completely unrelated, non-automotive context: `"registry srv %s
avail., accessKey: 0x%x"` and `"SVDOID %x sizeof(sint32_t) %x result %x
suppData.accesskey %x MASK_EVT %x"` -- both about a SERVICE REGISTERING
ITSELF with this codebase's own internal message-broker/service-
registry framework (the same `Cfc*`/`svcb_*` framework
[Firmware Reversing](Firmware-Reversing) already names), printed as a
raw hex HANDLE, not a diagnostic PIN. A 2nd candidate string,
`checkSecurityAccess`, was ALSO checked directly against its surrounding
bytes and is unrelated: it sits inside `java/util/Vector`'s own
standard method list (`insertElementAt`/`removeElement`/
`ensureCapacityHelper`/`VectorEnumerator`) -- Java's own standard
`SecurityManager.checkSecurityAccess()` platform API, nothing
automotive about it, a coincidental name match only. **Net conclusion**:
the real VCDS-style vehicle security-access/Login PIN validation logic
was NOT found anywhere in `FHDD6.FLI` -- searched directly and came up
empty on both plausible leads -- and is not believed to live there; it
more plausibly lives lower in the diagnostic stack (a native PowerPC
region not reachable with current tooling, or even the CAN gateway
chip) or is delegated to an external tester entirely. `accKey` is
CTEST.OUT's own internal service-registry handle, unrelated to the
vehicle's actual SecurityAccess code.

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
function names** was extracted (regex `db_[A-Za-z_]+_V\\d{3}` over the
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

============================================================================
UPDATE, a still-later session: `parse_symbol_table()` written and run
at scale -- CORRECTS this whole section's `findSegIndex` identity, and
finds an important, broader methodological lesson
============================================================================
Turned the manual extraction above into a real, reusable function
(`parse_symbol_table()`, this module, plus `find_prologues()` factored
out of the earlier ad-hoc prologue scans). Restricted to the verified
1.2MB-9MB range (per the confirmed limit above): **8,041 entries**
resolve to a plausible in-range address; requiring the STRICT
`stwu`/`mflr` prologue match narrows that to **35 high-confidence
entries** (leaf functions without that exact frame shape are real but
excluded by the strict filter, expected and documented in the
function's own docstring).

**Direct, important correction**: cross-checked the 35 strict entries
against the earlier "330 candidates reference a readable string"
catalog (this section's own "UPDATE... 330 real, CODE-REFERENCED C++
symbol names" above) -- 4 addresses appear in both. For EVERY one of
those 4, **the symbol table's own confirmed name has NOTHING to do
with the string the function's own code happened to reference**:

| address | symbol table's REAL name (authoritative) | string it merely referenced (misleading on its own) |
|---|---|---|
| `0x815a80` | `getId__C26CfcMsgStreamedServicePoint` | `"findSegIndex"` |
| `0x5c00f4` | `isController__22CfcCtrlControllerProxy` | an unrelated fragment (`"...Positioning...Future"`-shaped) |
| `0x6c31e8` | `__vn__21CfcTypeStageDistancesUi` (operator `new[]`) | a generic `%08x`-format debug-log string |
| `0x82c4a8` | `SetScrollType__13MapController...` | `"...CfcTypeNavMediaRequestCopyDatabase"` |

**This directly corrects the earlier identification of `0x815a80` as
"the `findSegIndex`-referencing function"** (the section above, "tracing
`findSegIndex` further..."). Its real, confirmed identity is
`CfcMsgStreamedServicePoint::getId`. "`findSegIndex`" was never this
function's name -- it's a string the function's own implementation
happens to compute the address of, almost certainly an internal debug/
trace tag for one step of its own multi-table lookup algorithm (which
now reads naturally as "resolve a streamed service-point's real id by
walking cached lookup tables" -- consistent with everything already
disassembled about this function, just under the right name). The
disassembly itself was accurate; only the assumed IDENTITY was wrong,
and it was always flagged as an assumption, not asserted as confirmed
-- but it should still be corrected now that real evidence exists.

**The broader, more important lesson, confirmed 4-for-4 with zero
exceptions**: a function's own string references (the 330-candidate
catalog's whole basis) tell you almost NOTHING reliable about that
function's identity or purpose -- real code routinely references
unrelated debug tags, generic log-format strings, and other functions'
names in ways that have no bearing on its own role. **Every name in the
330-candidate catalog elsewhere in this file should be read as "this
function touches this string somewhere," never as "this function does
what this string suggests"** -- that catalog's entries are real and
useful as raw material, but none of their earlier framing implied
identity beyond what evidence supported; this makes that caveat
explicit and evidenced rather than just implied. The symbol table's own
name field, by contrast, IS the function's real, compiler-assigned
identity (via RTTI/EH descriptor generation) -- authoritative where it
resolves.

============================================================================
UPDATE, immediately following, same session: the LOOSE catalog (no
strict-prologue requirement, 8,041 entries) surfaced a large, genuinely
new, directly relevant routing/VID catalog -- and one strong new lead,
`getNodeVidArmMP0`, disassembled and confirmed real
============================================================================
The loose catalog (`parse_symbol_table(fli, require_prologue=False)`,
83.1% of whose entries at least decode as SOME valid instruction) turned
up dozens of real `RoutePath`/`vseg`/maneuver-generator names living
INSIDE the verified 1.2MB-9MB range -- unlike `readNodeMP0` itself,
these are structurally reachable. Most directly relevant:
`getNodeVidArmMP0__9RoutePathUiRUlRi` (file offset `0x80c87c` from the
naive field-4 lookup) -- its name explicitly combines "Vid" (virtual
id, this project's own `vnodeID` terminology) with "Arm" (a junction's
connected road segment) and "MP0" (this project's own already-cracked
tile format), making it the single most directly-named VID-resolution
lead found so far. Also found in the same pass: `ResolveUnsetNodeID__
12AdasDBAccessP4vsegi`, `getIndexOfVid__9RoutePath...`,
`calculateManeuvers__24ManeuverGeneratorManagerP19CfcJourneyInterface...`,
`addSegmentData__16DYNA_SegmentListP8_tmc_segUsiP4vsegRUi`,
`filterToggleSeg__FP4vseg`, `getSegProperty__9RoutePathUiR12
_SegProperty`, and many more real `RoutePath`/segment/maneuver methods
-- a genuinely large, newly-opened catalog for a future session to work
through, all in principle reachable (unlike the 9MB+ names).

`getNodeVidArmMP0` disassembled and confirmed real: the naive field-4
address (`0x80c87c`) landed 168 bytes INTO the function, not at its
start (a real, if imprecise, limitation of the naive lookup -- the true
start, `0x80c7d4`, was found by scanning backward for the nearest real
`stwu`+`mflr` prologue). The full function is genuine, complete,
well-formed code (clean prologue, matching clean epilogue, no invalid
bytes in between): its 3rd argument is tested for zero, then a 31-entry
POWER-OF-2 lookup table is built on the stack (`1, 2, 4, 8, ...` via a
`slwi`-by-1 loop, 0x1f/31 iterations) and a bit-by-bit walk of that
argument follows (`andi. r0,r31,1` tests the low bit, `srawi. r31,r31,1`
shifts to the next one), with a virtual method call made for each SET
bit found. This is consistent with **iterating a caller-supplied
BITMASK of requested arms and resolving each one's VID individually**
-- exactly the shape "get the VID of node arms N, given a bitmask of
which arms to resolve" would take.

**UPDATE, immediately following, same session: its own virtual-call
targets were checked -- CORRECTING an error in this section's own
first-pass claim that they were reachable.** The 2 computed call
targets (`0xbce5d8`/`0xbce5a8`) are actually ~12.4MB in -- this
section originally, wrongly, called them "within the verified <9MB
range"; they are not (12,379,608 and 12,379,560 respectively, both
past the confirmed 9MB boundary). Consistent with that: neither
resolves to a valid prologue, a backward search of 3,000 bytes found
no real function start near either, and `0xbce5d8` itself lands on
readable text (`"...iptor__C..."`, a mangled-name fragment) rather
than code. This is the SAME already-understood 9MB+ limitation
`readNodeMP0` hits, not a new anomaly -- `getNodeVidArmMP0`'s own
virtual-call targets are genuinely unreachable with the current
technique too. Corrected here, in the README, and on the wiki's
`Firmware-Reversing` page (all 3 repeated the same magnitude error).

**A 4th function fully traced, immediately following, same session:
`AdasDBAccess::ResolveUnsetNodeID`** (file offset `0x828940`, found via
the loose catalog same as `getNodeVidArmMP0`, true start located the
same backward-scan way). The largest, most complex function traced this
session -- real, reaches a genuine `blr`. Checks offset+4 of its own
argument against zero (a "resolved" flag, matching its own name); if
unset, makes a virtual call (`0x828978`, passing `this+0x28`) then
performs substantial real pointer/tree manipulation: an `li r3,0x18` /
`li r5,0x19` pair immediately before a virtual call (`0x828aa0`) reads
as a real `sizeof`+alignment pair feeding an allocator, followed by
linked pointer-field stores, a chain-walk loop (`lwz r11,0(r11)` until
NUL), and a branchless XOR-based conditional-swap idiom
(`0x828c64`-`0x828c7c`) -- the shape a self-balancing tree's insert/
rotate step takes. Consistent with "if this node's id hasn't been
resolved yet, compute it and insert the result into a cache/index
structure." **One boundary honestly flagged as uncertain**: the
already-set path pops its stack frame (`addi r1,r1,0x30` at `0x82899c`)
and falls DIRECTLY into what looks like a separate function's own
prologue (`stmw r28,0x20(r1)` at `0x8289a8`) with no call instruction
in between -- consistent with a real GCC tail-call optimization, not a
mistake, but it means this function's own exact boundary there isn't
fully pinned down. None of its own virtual-call targets have been
checked yet. Full exact disassembly: the wiki's `Firmware-Reversing`
page.

Also found in the same scan: `db_fea_map_V000`, `db_fea_get_layer_
range_V005`, `db_fea_get_file_header_V005`, `db_fea_get_layer_
properties_V005`, `db_fea_read_parcels_V005`, `db_fea_init_V005`,
`db_fea_get_scale_from_subindex_V005` -- real, versioned accessors for
`eeuz.fea` confirming its `ParcelHeader`/layer/scale/subindex structure
(README S3.10, wiki `eeuz-fea-Place-Name-Gazetteer`) is real and
actively used, same pattern of confirmation as the `db_seg_*` catalog.

============================================================================
UPDATE, a still-later session: the MAP_COMPRESSED spatial index's real
ARCHITECTURE identified -- a genuine R-TREE (`MDCacheTIRTree`) -- but
its exact byte-level node/MBR layout remains unreachable, same 9MB+
wall, now confirmed to extend to the whole rendering subsystem too
============================================================================
Direct follow-up to README §8 item 1/3 (the still-uncracked pre-table
"geo-index prefix" region in `.mp0`/`.mg1`-`.mg4`, and the still-
approximate `find_tile_for_coord()`/`tile_ids_in_bbox()`) -- user asked
to find out exactly how the real firmware reads this region and make
the viewer work the same way. The `db_get_parcel_dir_V005`/`db_load_
pcl_dir_V005`/`db_page_pcl_V000`/`db_map_dir_V000` catalog (this
session's own "MAP_COMPRESSED parcel directory" bullet, several
sections up) was checked against `parse_symbol_table()` first and
refuted as a path forward: none of them have ANY resolvable code
address in the symbol table, at any range (unlike `readNodeMP0`, which
at least has a table entry, just in the already-confirmed-unreachable
9MB+ zone) -- worse off than the routing-graph problem, not better.

**The real breakthrough came from the LOOSE catalog's much larger
`CfcMapViewProxy`/`MapViewImpl`/`MapController`/`MapCache`/`MDCache*`
cluster** (586 matches for a `Map*`-family keyword sweep, 120 of them
in the verified-reachable <9MB range -- by far the largest coherent,
reachable, directly-relevant cluster this project has found). Real,
unambiguous R-tree terminology confirmed present as actual mangled
C++ symbols, not inference: `findNode__14MDCacheTIRTreeRC7MapRectPP18`
(a class LITERALLY named "TIRTree", taking a `MapRect` query and
returning node pointers -- exactly `find_tile_for_coord()`'s own real
counterpart), `enlargeMBR__C33MDCacheQSortForRTreeCreationTIJamR7MapRecti`
/ `enlargeMBR__C27MDCacheQSortForRtreeTIIconsR7MapRecti` (MBR = minimum
bounding rectangle, the textbook R-tree term), `splitNodeElements__
32MDCacheQSortForRTreeCreationBase...` (R-tree node splitting, the core
bulk-load step), `intersectsRecursive__C12MDCacheTIJamRC7MapRectPC16
MDCacheTIJamNodeRiT3` (recursive rectangle-intersection tree walk,
against a real `MDCacheTIJamNode` type), and `calcFromBoundingRect__
24MDCacheTIConvertLoc2GlobR7MapRect`. `QSortForRTreeCreation`'s own name
("quicksort for R-tree creation") reads as this codebase's real STR
(sort-tile-recursive) bulk-loading implementation -- a well-known real
R-tree construction algorithm, not a guess. **This is a genuinely new,
correct architectural finding**: the still-uncracked pre-table region
in `.mp0`/`.mg1`-`.mg4` is almost certainly a serialized R-tree (or
R-tree-adjacent structure), explaining properties already observed
empirically and previously unexplained -- variable-length per-tile
records (R-tree nodes hold a variable child count), and the ascending-
counter walk's own collision/breakdown after ~10-32 entries (multiple
interleaved counters at different tree levels/node-splits, not one flat
per-tile sequence, is exactly what a real multi-level tree would
produce).

**Disassembly of every REACHABLE candidate near this cluster was
attempted directly (capstone installed this session) -- real progress,
but the exact `MapRect`/R-tree-node byte layout was NOT reached**:
- `enlargeMBR` (TIJam variant, file offset 8,705,104): genuine, valid,
  well-formed code (confirmed real start via the established backward-
  prologue-scan technique) -- but a large function (640-byte stack
  frame) whose visible body batch-processes ~19 fields at a regular
  8-byte stride via `lhz`/`add`/`sth`, not a simple 2-rectangle MBR
  union -- its exact semantics need more register-level tracing than
  this session had time for.
- `enlargeMBR` (TIIcons variant): the naive backward-prologue-scan
  landed on a **false-positive prologue match in non-code data**
  (confirmed: the very next word decodes as an invalid PowerPC opcode,
  `0x00670019`) -- a concrete, caught instance of this project's own
  already-acknowledged `find_prologues()` false-positive risk, not a
  new technique failure.
- The `CfcTypeMapWindow` `getLeft`/`getTop`/`getRight`/`setTop`/
  `setRight`/`setBottom` accessor cluster all resolved to the SAME
  single address, which turned out to be a cross-task RPC proxy/stub
  dispatch routine (real code, matches this subsystem's own `CfcMap
  ViewProxy`/`CfcMapViewStub`/`processXxxReq` naming, i.e. this whole
  `Cfc*` layer marshals requests to a different task rather than
  touching fields directly) -- a genuine, new architectural fact (this
  codebase's UI-facing map API is IPC-proxied, not a direct in-process
  accessor layer), but not the byte layout being sought.
- `getVisibleArea__C6MapAPIP16CfcTypeMapWindow` (file offset 8,676,584,
  a `MapAPI` method writing a `CfcTypeMapWindow*` OUTPUT parameter --
  the single most directly promising target tried): genuine, short, real
  code, but its body makes exactly 2 indirect calls (computed via `lis`/
  `addi`/`mtlr`/`blrl`, the shape of a matched lock()/unlock() pair
  around a critical section, given the identical `r4=2` argument both
  times) and returns -- **both computed call targets land at ~12.84MB**,
  resolved and directly checked: zero decodable instructions there
  either. The actual field-copying logic this function exists to run is
  bracketed by, but not itself contained in, code below 9MB.

**Net, honestly stated**: this session materially deepened the
project's own understanding of the 9MB+ wall -- it was previously
characterized only against the VNode/routing-graph subsystem
(`readNodeMP0` etc, earlier in this section); it now is CONFIRMED, via
4 independently-traced call sites across a completely different
subsystem (map rendering/spatial-cache), to be the SAME wall, not a
narrower one specific to routing. Every reachable (<9MB) function found
near this cluster is a thin wrapper (RPC proxy, lock/unlock pair, sort
helper) that itself calls into the unreachable zone to do its real
work, rather than touching struct fields directly. Reaching the actual
`MapRect`/R-tree-node byte layout this way would mean solving the same
underlying problem already on record as attempted-and-failed (a valid
load base for the 9MB+ region) -- not a matter of trying more
individual functions. **Concrete, valuable output despite this**: the
R-TREE ARCHITECTURE ITSELF is now real, confirmed, citable fact (not
inference) for any future session -- a fundamentally better starting
model than "unknown ascending-counter structure" for a fresh attempt at
the raw region bytes, and a short list of real class/method names
(`MDCacheTIRTree::findNode`, `MDCacheQSortForRTreeCreation*::
enlargeMBR`/`splitNodeElements`) to specifically target if a working
9MB+ disassembly technique is ever found.

**UPDATE, immediately following, same session: the "fresh attempt at the
raw region bytes" this section just predicted was made -- PARTIALLY
successful, without needing the blocked 9MB+ disassembly at all.** See
`research/map_compressed_reader.py`'s `scan_native_geo_hints()` (and
README §8 item 1's matching update) for the full mechanism and
validation numbers. Short version: the R-tree architecture confirmed
above directly motivated re-testing the region's already-documented
small-integer pairs as `(tile_id, tile_id+1)` REFERENCES (using the
SAME flat-directory-table numbering, not a separately-sorted rank) --
confirmed true for a large fraction of them, and built into a working,
no-decompression-needed partial native geo-index reader, cross-
validated at ~42% exact-match coverage on two independent files (`mg4`,
`mg3`). A separate, more exciting-looking hypothesis tried in the same
pass -- that a record's trailing field was a recursive pointer to
ANOTHER instance of the same structure -- was tested at real scale
(2,275 records) and cleanly refuted (0.6% hit rate); noted here so nobody
re-chases it. This is genuine, partial, validated progress on the
region's byte-level format from a completely different angle than
disassembly -- informed by, but not dependent on, the architectural
finding above.

**UPDATE, a still-later session: a full "try every remaining firmware
asset on disk" sweep -- COMPREHENSIVE, and the 9MB+ wall CONFIRMED
STRUCTURAL, not an artifact of one specific file** (user-asked
"disassemble the whole firmware, check all files and folders"). Motivated
by a road-classification investigation (README §2.6's own real-hardware-
ground-truth-backed thread) that independently hit the exact same wall
for `db_seg_rank_V004`/`db_seg_speed_V004` etc -- confirmed zero
resolvable code address, same as `db_vid_get_map_id_V000` earlier.
Checked every other firmware-adjacent asset actually present on disk:
  - **2 more real, genuinely different `FHDD6.FLI` builds found and
    tested** (`RNS510_5274_MOD_C6_C12.iso`, dated Nov 2013;
    `RNS510_6276_MOD_C14.iso`, dated Mar 2014 -- distinct SHA256 hashes
    and file sizes from the original `5238` build analyzed everywhere
    else in this module, confirmed genuinely different compiled
    outputs, not copies). **The already-recovered `FHDD6_LOAD_BASE`
    transfers almost perfectly to both**: 26,212/26,215 symbol-table
    entries resolve (vs. the original's 26,215) -- these builds share
    the SAME underlying memory layout. `db_seg_rank`/`db_seg_speed`/
    `db_vid_get_map_id`/`db_get_parcel_dir` are unresolvable in ALL 3
    builds; `readNodeMP0`/`findNode__14MDCacheTIRTree` land in the
    unreachable >9MB zone in ALL 3 (shifted by only ~100-150KB build to
    build -- still deep in unreachable territory every time). A
    different firmware build is NOT a viable workaround.
  - **All 13 other embedded-processor firmware files** on all 3 discs
    (`DAB.FLI`, both `RADIO.FLI` variants, `GATEWAY.FLI`/`GWBOOTL.FLI`/
    `T5GATEW.FLI` and 4 more 8KB config tables, `MPEGAPPS.FLI`/
    `MPEGSWL.FLI`, `SWL.FLI`, `SWLBOOT.FLI`) checked for the same
    `\x00\x10\x05` symbol-table marker and any `db_seg_*`/`MDCacheTIRTree`/
    `navicore` string presence: NONE found (a handful of unrelated
    marker-byte coincidences in `DAB.FLI`/`RADIO.FLI`, nothing
    resembling a real symbol table). Confirmed genuinely separate
    subsystems (DAB tuner, AM/FM radio, CAN gateway, MPEG decoder) with
    no map/routing code linked in, exactly as this module's own §2.1
    architecture summary already stated -- not re-derived from nothing,
    but now directly, exhaustively confirmed rather than assumed.
  - **`rns_code_finders/RNS510_code_finder_ver20.exe`/`ver22.exe`**
    (found alongside the firmware ISOs, plausible-sounding name):
    confirmed by string extraction to be unrelated .NET/Mono serial-port
    tools (`serialPort1`, `RNS510_decode`, baud-rate settings) for
    computing a UNIT'S OWN anti-theft PIN/unlock code over a physical
    RS232 connection to real hardware -- nothing to do with firmware
    binary analysis. Ruled out directly, not assumed.
  - **`maps-tool 2.0.2/maps-tool-2.0.2.exe`** (SD-card deployment tool):
    16,688 extracted strings, zero matches for any `db_seg_*`/road/
    `MDCache`/`navicore`/firmware-offset-shaped keyword. Confirmed
    purely an ISO/file-deployment tool, no firmware-internals content.
  **Net conclusion**: every firmware-adjacent binary actually present on
  disk has now been checked, across 3 real firmware builds spanning
  2012-2014 and every embedded subsystem on each. The wall blocking
  byte-level road-classification/routing/R-tree/parcel-directory
  disassembly is consistent everywhere it was tested -- a real,
  structural property of how this codebase's deeper map/routing/
  spatial-index logic was linked or stripped, not something a
  different file, build, or third-party tool on hand can route around.
  Closing this specific "try more files" avenue as exhausted, not
  abandoned early.

**UPDATE, a still-later session: 3 MORE native-PowerPC code regions found
INSIDE the file's own "24-76MB Java classes" territory** (user-asked
"disassemble the whole firmware... check all files and folders", then
specifically "lets investigate" a "second/multiple load base" hypothesis
raised while explaining why the >9MB zone above is unreachable). A full
`find_prologues()` sweep across the ENTIRE 85.7MB `FHDD6.FLI` (not just
the known 0-9MB window) found 14,845 total prologue hits and 3 dense
clusters beyond the known native blob: **~25MB** (374 prologues, file
offset ~24.5-26.5MB), **~30MB** (362 prologues, ~29.5-31.5MB), and
**76-82MB** (6,130 prologues -- this one already known to be the VxWorks
kernel/BSP tail per README S2, not new). Recovering a candidate load base
per region with the same `lis`/`addi` address-clustering technique used
for `FHDD6_LOAD_BASE` gave 88.8% (25MB), 88.2% (30MB), and 99.8%
(76-82MB, strongly confirming that region is real and matches known
VxWorks/Jeode strings) clustering -- all well above chance.

None of the specific already-known-unreachable target addresses
(`readNodeMP0`, `findNode__14MDCacheTIRTree`, `db_seg_rank_V004`, etc.)
resolve into any of these 3 regions under their new candidate bases, and
none of the 26,215 parsed `\x00\x10\x05` symbol-table entries' own
addresses land there either -- this new code is a SEPARATE set of
compilation units from the known native map/navicore blob, not a hidden
continuation of it. Confirmed by disassembling AT the raw unreachable
target addresses directly: several decode to literal ASCII mangled-name
text or non-code pointer data, not instructions -- fresh, independently-
derived confirmation (not just a repeat) of this module's existing
"field 4 breaks beyond 9MB" finding.

Whether 25MB/30MB were REAL code (vs. `find_prologues()` false-positives
inside the Java-class byte territory) was genuinely ambiguous at first:
plain-string scans of each region found only Java class-path/method-
signature strings for 25MB and 30MB (DVD/AV-app and ski-resort/weather-
app content respectively) with zero VxWorks-identifying strings, yet the
FIRST candidate function tried in the 25MB region reached a clean,
textbook-perfect `blr` exit (31 straight instructions, epilogue register-
save offsets exactly matching its own prologue's frame size) -- a result
that's very hard to get from random misaligned data by chance, but also
hard to reconcile with an all-Java-strings region. A broader stress test
(sampling ~40-60 prologues per region, checking what fraction reach a
clean `blr` within a 4000-byte window) turned out to be UNDISCRIMINATING
on its own: even the KNOWN-real 0-9MB region only hits a clean exit in
10.0% of samples in that window, and the confirmed-real 76-82MB VxWorks
region in 8.3% -- both in the SAME ballpark as the 25MB (1.7%) and 30MB
(5.0%) candidates (most real functions here are simply bigger than a
4000-byte window, or `find_prologues()`'s byte-pattern heuristic hits
plenty of coincidental matches even inside genuinely real code -- this
metric doesn't separate real from fake here and should not be trusted
alone for this question in the future).

**The decisive test was mangled C++ symbol-name strings physically
adjacent to the code**, using the exact same "name string precedes its
function's prologue by ~100-300 bytes" layout already established for
the known 0-9MB native blob's own symbol table. Searching each region for
the project's established cfront-style mangling pattern
(`Name__NClassArgs`) found 28 unique names in 25MB and **310 unique names
in 30MB** -- not generic filler, coherent real C++ identifiers. 25MB's
names are all `Q33vdo3svc*`/`Q33vdo4util*` (a `vdo::svc`/`vdo::util`
namespace -- Service/Dispatcher/String plumbing), consistent with the
DVD/AV-app strings found there: a genuinely separate multimedia-subsystem
module, not misread Java bytecode. **30MB's names are navigation/geometry
math**: `GEO_PntPnt_UCangle__FPC9geo_coordT0` (angle between two geo-
coordinates), `GEO_RpntPnt_NCpnt__FPC9geo_coordT0P10cart_coord`
(geo_coord -> cart_coord conversion), `GON_YXL_Atan__Fll`, plus PTT/
telephony-looking names (`H_dialed_numbers`, `H_ptt_*`). Nailed down
exactly: the string `GEO_PntPnt_UCangle__FPC9geo_coordT0` sits at file
offset 30320528, just 148 bytes before the prologue at file offset
30320676 -- a 1:1 match on the SAME name-then-prologue convention as the
known map-native symbol table. **Conclusion: genuinely real, newly-
identified native code, not a false positive** -- but a FOLLOW-UP pass
(same session, user-asked "lets dig in") corrected the INITIAL
characterization of exactly what's here, and that correction is worth
keeping:

  - Full disassembly of the 30320676 prologue shows a huge register-save
    frame (r17-r31, 15 registers) and a repeated
    `lwz r0,OFF(r9); mtlr r0; blrl` idiom several times over (load a
    vtable slot through an object pointer, call through it) -- the
    classic C++ virtual-dispatch-through-a-service-object shape, NOT a
    simple leaf math routine. This is a dispatch/registration routine,
    not `GEO_PntPnt_UCangle` computing anything itself.
  - Its `lis`/`addi` address constants were tested against the
    statistically-recovered candidate base (0xf8ce3df4) and resolve to
    file offset ~59MB -- outside every known region (25MB, 30MB,
    76-82MB) and not matching plausible data. That candidate base is
    NOT reliable for individual address resolution inside this specific
    function; treat it as a rough regional signal only (it was recovered
    from aggregate clustering across ~360 prologues' pairs, not
    validated per-function the way `FHDD6_LOAD_BASE` was).
  - Searching for `GEO_`/`GON_`/`geo_` mangled names ACROSS THE WHOLE
    85.7MB FILE (not just this region) found exactly these same 3 hits
    and no others -- a single isolated cluster, not a spread-out library.
    Combined with this project's OWN already-documented finding (this
    module's earlier "a real, large-scale... symbol/EH-descriptor
    table" section) that the `\x00\x10\x05`-marker tables are
    exception-handling/RTTI type-descriptor tables, not plain per-
    function symbol tables, the more accurate read is: these 3 names are
    TYPE-DESCRIPTOR entries the compiler emitted because something,
    somewhere in the linked binary, references/catches/registers by
    these types -- not 3 function bodies sitting at this exact spot.
  - The immediate neighborhood's OTHER mangled names are from a totally
    unrelated domain -- `H_dialed_numbers`, `H_ptt_*` (telephony/PTT) --
    reinforcing that this is a multi-subsystem COMMAND/EVENT DISPATCH
    REGISTRATION table (binding string command names to native function
    pointers, the same role as the 25MB region's own
    `dispatch__Q43vdo3svc10dispatcher10DispatcherlliPCvi`), not a
    dedicated geo-math library. Geo-coordinate math is real and compiled
    in (the type names prove it exists), but this specific byte range is
    where it gets NAMED/REGISTERED for remote/scripted invocation, not
    necessarily where its own leaf implementation lives.

Practical takeaway for future sessions: don't re-chase "disassemble
30320676 itself" expecting to find the angle-math implementation there --
that address is a dispatcher/registration routine. If the actual
`GEO_PntPnt_UCangle`/`GEO_RpntPnt_NCpnt`/`GON_YXL_Atan` leaf bodies are
wanted, they're elsewhere and unidentified (their names appear nowhere
else in the file, so no more string-proximity leads remain for them).
This was NOT tested against README S2.6's specific open road-
classification/routing questions; the already-unreachable
`db_seg_rank`/`readNodeMP0`/R-tree targets specifically do NOT live here
(confirmed above), so this whole avenue is a real, validated architecture
finding (a vdo::svc command-dispatcher spanning 25-30MB across multiple
subsystems) but not a solution to those existing open items.

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
`HOST\SILVER_1\RNSMIDEC\PROG\H_*.FRG` -- DECOMPRESSED (a still-later
session, user-asked "try decompressing"): the zlib inflate errors above
were a real clue, not just linked-in dead code -- the `.FRG`'s own bulk
payload past the tiny embedded script/VxWorks-banner region genuinely IS
a zlib stream, and it inflates to the real VxWorks BOOTROM/BSP source
image, `SSW_VW-RNS`
============================================================================
A real zlib (RFC 1950, standard `78 xx` header) stream starts at a FIXED
file offset, **16051**, in every `H_*.FRG` file checked (`H_PQEE.FRG`,
`H_SB_HDD.FRG`, `H_SE_DAB.FRG`, `H_AK.FRG`) -- `zlib.decompress()` on it
succeeds immediately, no scanning/guessing needed once the offset is
known. Consumes exactly 497,964 compressed bytes -> **1,573,904 bytes**
decompressed, in EVERY file tested (byte-identical: same SHA256 across
all 4 -- this is ONE shared image, not a per-variant build). The
decompressed bytes open with `\x94\x21...\x7c\x08\x02\xa6` -- this
project's own `_PROLOGUE_TAIL` function-prologue signature -- and
`find_prologues()` finds **3,079 real prologues** in it: genuine,
substantial, executable PowerPC code, not junk.

**This is the real VxWorks bootrom/BSP (Board Support Package) source
for the RNS-510 hardware**, self-named directly in its own strings:
`SSW_VW-RNS` (Siemens-VDO-convention "System SoftWare" + "VW-RNS"
project code) and `(c) 2005 Siemens VDO Automotive AG` -- this is the
first DIRECT internal evidence this project has found tracing any of
this codebase's origin specifically to Siemens VDO Automotive (VW's
original Tier-1 for this unit, acquired by Continental in 2007 -- this
project elsewhere only ever says "Continental"). Real, dated internal
revision-control stamps span 2004-2011 (`$Revision: 1.2/1.4/11313/9902d
$Date: 2004/04/08 .. 2011-10-05 ...$`), well before this disc's own
Sep 25 2012 HOST build stamp -- a genuinely long-lived, actively
maintained codebase, not a one-off.

**Real embedded C source file names** (a live BSP driver/bootstrap file
list, not guessed): `usrStartup.c`, `usrConfig.c`, `usrCache.c`,
`usrBreakpoint.c`, `usbPciStub.c`, `sysTffs.c` (True FFS flash
filesystem), `sysSerial.c`, `sysPciManualConfig.c`, `sysLib.c`,
`sysGpTimer.c`, `sysGpioDemux.c`, `sysAta.c` (ATA/IDE disk driver --
almost certainly what the HDD-equipped variants, e.g. `H_SB_HDD.FRG`,
actually need this for), `ssw_memorymap.c`, `pca9554LedI2CSlave.c` (a
real I2C LED-driver chip), `nvRamToImageIO.c`, `nvRamToFlash.c`,
`minicoreStubs.c`, `flashMem.c`, `bootInit.c`, `bootConfig.c`.

**Functionally, this BSP/bootrom owns**: MMU setup and machine-check/
exception handling (`usrRoot: MMU configuration failed`, real PowerPC
exception-vector dump strings); a full **PCI bus scanner/enumerator**
(real Freescale `M5200 PCI Configuration` strings, vendor/device ID and
BAR-register dumps, `Mediator`/`CoralP` graphics-controller config-space
access -- CoralP is a real automotive display/graphics controller chip);
**video-input source switching** (`cpdrVideoInSetSource JN/DVD/TV/RVC`
-- confirms rear-view-camera, DVD, and TV-tuner video-in muxing lives at
this layer, driven through real Analog Devices video-decoder chips,
`ad9883`/`adv7400`, over I2C); **flash/NAND image management with real
A/B-style versioning** (`BuildFlashTable`, `RF_ProcessImage` --
"Curently Stored Image Id %d is newer/older than recent one so deleting
..." -- a real rollback-safe image-update mechanism) against a REAL
Samsung NAND part number, `K9F12088U0`; and a **detailed physical
memory map** covering SDRAM/NOR/NAND/PCI0-2/FPGA/PCMCIA regions and
named image slots (`ImageIO static/dyn`, `InfoLog 1/2` -- this is what
`INSTALL_ALL_LOG_DB`/`SET_LOG_DB_STATUS` above actually initializes --
`NAND bad sec. FIB/SWL`, `SplashScr`, `BootLoader 1/2`, `BootStrap 1/2`,
`Test SW`, `HW Info`, `Bestcomm` [Freescale's real MPC5200 DMA/queue
engine, confirms the already-known MPC5200B chip ID], `OSNVR`, `ROM FS`,
`host img`). A live interactive VxWorks debug shell is present too
(`sp adr,args... Spawn a task`, `version Print VxWorks version info, and
boot line` -- real WindShell command help text).

**This settles the `HOST` vs `APPS` question directly, not by
inference**: `HOST` is the base hardware platform layer -- boot,
low-level drivers, PCI/flash/video-mux/graphics-chip bring-up, the
persistent fault-log store -- that boots and runs regardless of which
navigation app variant is installed. It is NOT part of the `navicore`/
`dbal`/map codebase this project otherwise studies; zero `db_*`/
`navicore`/`MDCache`-family strings appear anywhere in it. `APPS`
(`FHDD6.FLI`) is the actual navigation/media application logic layered
on top.

**Per-variant differences, resolved**: the 3 tested files' outer
`.FRG` sizes differ (994,140 / 1,286,592 / 1,855,592 bytes) purely
because of what comes AFTER the shared 497,964-byte compressed BSP
stream, not because the BSP itself differs. That remainder (772,577 /
1,341,577 / 480,125 bytes respectively) is a separate, non-zlib,
tightly-repetitive-pattern binary region containing exactly ONE real
readable string each -- a genuine VW part number matching this
project's own already-known `#VwSwPartNumber` format
(`1T0035680Q`/`3T0035680G`/`7N5035686`) plus the literal product-family
label `"RNS-MID"` -- consistent with the BSP's own `SplashScr`/`host
img` named flash regions above: almost certainly a per-variant boot
splash-screen bitmap + part-number label, not further decoded (its
exact pixel/palette format wasn't reverse-engineered this session).

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

============================================================================
3 NEW discs -- the user reorganized all extracted firmware/maps under a
new `BASE/` folder and added 3 real, previously-unseen SWL discs to it:
`RNS510_4366`, `US_RNS-510_SW1140`, `VIM_Berto89`. The first 2 are this
project's FIRST-EVER North America (`C_NAR`) firmware, opening up
several subsystems only ever known by reference until now.
============================================================================
All 3 confirmed real via the same `Version.txt`/`BlScript.cfg` format
already cracked above -- no new container format, same disc family.

**`US_RNS-510_SW1140`**: `#Steckbrief: C_NAR_9.442_t950 C3/C4C/C6`,
`VwSwIndex 1140/1142`, dated 2011-04-12, author `RoNe` (the same
engineer already known from the EU disc's own `USER.CFG`). Real VW part
numbers `3C0035684C/7L6035684D/3C0035684D/7L6035684E` -- a completely
different prefix series from the EU discs' `1T00.../3T00...` (`3C` =
Passat B6/CC NAR, `7L6` = Touareg NAR, by real VW part-number
convention).

**`RNS510_4366`**: `#Steckbrief: C_NAR_18.366_t1 C10/C12`, `VwSwIndex
4366`, dated 2012-11-15, author `MaGo` -- a NEW engineer initial, not
among the ones already known from `CDSTRUCTTMP.CFG`'s changelog
(`AKls`/`m.`/`y.`/`MaRu`/`AKr`/`RoNe`). A later-generation NAR build
than `SW1140` (Steckbrief `18.366` vs `9.442`), same Continental Wetzlar
facility.

**`VIM_Berto89`**: a real but much OLDER and much SMALLER disc --
`#Steckbrief: C_EU_9.242_t560`, `VwSwIndex 1300/1302/1304`, dated
2010-04-27, the SAME `"This is an unofficial SWL CD by josi"` community-
repack disclaimer already known from the main `5238_ALL` disc, now
confirmed to be a real, recurring repacker across multiple disc
generations, not a one-off. Only 159KB total, missing every top-level
ECU folder (`APPS`/`HOST`/`HDD`/etc) -- just `BlScript.cfg`/`CRC.16`/
`Dir.inf`/`EcuOrder.txt`/`Version.txt` + a `WA/` folder holding
`CTEST.OUT` (dated 2006-03-28 -- an OLDER build than every other
`CTEST.OUT` copy examined so far, a real lead for a future diff) and
**`VIM.WSH`** (what "VIM" in the folder name actually refers to): a
minimal, GENERIC coding script -- only the universal register-level
calls (`SetRegDataHex(0x21,"01",...)` testmode,
`SetRegDataHex(0x0B3A,"012C",...)` speed-limit), zero `SetCoding` calls
-- confirming these 2 register-level settings really are
vehicle/manufacturer-independent baseline setup, cleanly separate from
the per-variant `SetCoding` calls every other region script carries.

**Both NAR discs ship `WA/NARRADIO.FLI`/`NARADIO6.FLI` directly**
(previously only known by path reference in the EU disc's own
`INFO/INOUT.TXT` manifest) plus real NAR region-coding scripts
(`NARPQTO.WSH`, `NARBY.WSH` on `RNS510_4366`) -- and `RNS510_4366`
additionally ships **`SIRIUS.DB3`** (its own dedicated section below),
a real `CH_ARTS.WSH`/`DEL_CA.WSH`/`DEL_CHAR.WSH` trio (resolving the
previously-unidentified "CH_ARTS" name from `INOUT.TXT` -- "Channel
ARTS", i.e. Sirius channel-art management, confirmed by the sibling
`CHARTS/` folder below) and `DEL_SIR.WSH`/`MD_SIR.WSH` (also previously
only known by name).

**The NAR coding scripts REFINE, not just extend, the coding byte
map**: `SetCoding(0x400, 2, 7, 1)` -- commented `"SDARS/Sirius: Active
for NAR"` -- uses value **`2`**, not the plain boolean `1` every other
flag in this byte array uses. Byte-offset 7 is a small ENUM, not a
single bit -- plausibly XM=1/Sirius=2 (the 2 satellite-radio providers
that merged in 2008; RNS510 NAR units shipped with either depending on
model year/trim), not independently confirmed further. Also: both
`NARPQTO.WSH`/`NARBY.WSH` set `"Testmode: NOT active"` (`SetRegDataHex
(0x21,"00",...)`, value `"00"`) -- the FIRST time this project has seen
that register explicitly OFF; every EU region script found earlier
left it `"01"`/active. Real, concrete evidence these NAR scripts are
production-configuration coding, not factory-sample coding like the EU
ones -- and independent confirmation register `0x21` really is a
genuine binary active/inactive toggle (both states now directly
observed).

============================================================================
`RNS510_4366\SIRIUS\SIRIUS.DB3` -- OPENED: a real, substantial Sirius
TravelLink content database, same schema family as the map disc's own
`POI.DB3` -- its coordinate decoder transfers UNMODIFIED
============================================================================
A real, standard SQLite database (opens directly, no proprietary
container -- exactly like `POI.DB3`). 62 tables. The 2 largest --
**`Poi_BaseAttributes`/`Poi_AddressAttributes`/`Poi_SiriusAttributes`,
all 158,088 rows each** -- share `POi_BaseAttributes`'s exact column
shape from the map disc's own `POI.DB3`
(`Poi_ID`/`PoiPartition_ID`/`Coordinate`/`Name`), plus a
Sirius-specific sibling table
(`SiriusPoiId`/`Poi_ID`/`Version`/`CategoryId`/`Constraint_A`/
`Constraint_B`). Real, immediately recognizable content: `"BLOXHAMS
SHELL"`, `"CHEVRON"`, `"UNION 76"`, `"FORTUNA CHEVRON"` -- real US gas-
station brand POIs.

**`decode_coordinate()` (`research/poi_db_reader.py`, already cracked
against the map disc's `POI.DB3`) applies to this file completely
UNCHANGED** -- no adaptation needed, tested directly against 15 real
rows: every one decodes to `lon~-124, lat~40-41`, exactly Humboldt
County/Eureka, Northern California (the real US-101 corridor) --
immediately plausible for real "Union 76"/"Chevron"/"Fortuna Chevron"
station names, not a coincidental range match.

**This is the real, concrete home of `USER.CFG`'s own `TRAVELLINK`
build flag** (found weeks earlier, disabled on the EU disc): real
Sirius TravelLink content-service tables exist in the schema --
`FuelPrice`/`FuelBrand`/`FuelRegions`/`FuelType` (fuel prices),
`WeatherMessages`/`StormAttributes`/`StormWatchBoxes`/`SkiMessages`
(weather/ski conditions), `Movies` (showtimes), `Sports`/`Teams`/
`TeamStatus`/`HeadToHeadSportTable`/`RankedSportEvent` (live sports
scores), `Headlines` (news) -- all real, named, typed tables, though
EMPTY on this specific disc (0 rows each; only the POI/fuel-station
layer is populated here, consistent with this being a factory SWL
sample rather than a live subscriber unit's own downloaded content).
`DatabaseAttribute` confirms real per-subsystem schema version stamps
(`schema/core=001.0001`, `schema/poi=003.0000`, `schema/sirius=
005.0000`). Not yet explored: `.DDB` channel-art images
(`CHARTS/CHANNELARTSCACHE/128X88/*.DDB`, hundreds of files) and whether
`IBOC.FLI` exists on either NAR disc -- both pending, this session.

============================================================================
`RNS510_4366\CHARTS\CHANNELARTSCACHE\128X88\*.DDB` -- CRACKED completely
(same session, immediate follow-up): a self-documenting header, a real
2-plane color+mask bitmap format, real Sirius channel-art logos
rendered and visually confirmed
============================================================================
156 files, one per Sirius channel, in this specific `128X88/` folder
(the folder name IS the pixel dimensions, confirmed exactly below --
plausibly sibling folders at other resolutions exist elsewhere,
not checked). The header is almost entirely self-documenting plain
ASCII, no guessing needed for most of it:

```
DDBDDB          -- 6-byte magic
\x01            -- version = 1
B               -- 1 byte, role not decoded
__RGB555\x00    -- 8-byte pixel-format tag, NUL-terminated ("__" padding)
\x80\x00        -- uint16 LE width  = 128
\x58\x00        -- uint16 LE height = 88 (0x58 -- byte 19 alone happens
                   to print as the letter 'X', pure coincidence)
\x41            -- 1 byte, role not decoded
<zlib stream>   -- starts immediately after, real `78 da` header
```

Confirmed on `1.DDB`: width/height fields read back exactly `128`/`88`,
matching the folder name exactly -- not a coincidence, a real
cross-check. The zlib stream's own decompressed size is **always
exactly `width*height*3`** (33,792 bytes for 128x88) -- NOT
`width*height*2` as a naive reading of the `RGB555` tag would predict
(2 bytes/pixel). Tested and refuted a first hypothesis (plain
interleaved 3-byte-per-pixel RGB truecolor, ignoring the format tag
entirely) by rendering it directly: pure scrambled noise, not a real
image.

**The real layout is 2 SEPARATE planes, concatenated, not
interleaved**: a `width*height*2`-byte RGB555 color plane (real 16-bit
little-endian RGB555 pixels, confirmed -- see below) immediately
followed by a `width*height*1`-byte plain 8-bit alpha/mask plane.
`22,528 + 11,264 = 33,792`, exact. Rendering the mask plane alone as a
grayscale image on `1.DDB` shows a clean, coherent silhouette shape
(not noise) -- confirms the plane-split hypothesis before even getting
the color channel order right.

**Channel order is BGR555, not RGB555 despite the header's own literal
tag** -- confirmed by rendering both orderings directly: `RGB555`
(interpreting the 16-bit value as `RRRRR GGGGG BBBBB` from the top bit
down) produces wrong, inverted-looking colors; `BGR555` (`BBBBB GGGGG
RRRRR`) produces correct, natural colors. **Visually confirmed on 3
real files, real Sirius channel names, fully legible with correct
transparency**: `1.DDB` = "40s on 4" (a real 1940s-music Sirius
channel) with an airplane-silhouette mask; `50.DDB` = "WATERCOLORS"
(clean cyan/magenta text on transparent background); `100.DDB` =
"SIRIUS XM Patriot" with an eagle icon. This is the actual Sirius
channel-logo artwork this project can now decode from any `.DDB` file
on this disc.

**The filename IS the real key, confirmed exactly against
`SIRIUS.DB3`'s own `Sources` table**: `<N>.DDB` <-> `Sources.SourceId =
N`. `1.DDB` = "40s on 4" matches `Sources` row `(1, '40s on 4')`
exactly; `50.DDB`'s "WATERCOLORS" matches row `(50, 'Watrclrs')`
(abbreviated in the DB, same channel); `100.DDB`'s "SIRIUS XM Patriot"
matches row `(100, 'Patriot')` -- 3 for 3, no ambiguity. `Sources` has
157 rows to this folder's 156 files (off by one -- plausibly
`SourceId=0`, `"Preview"`, has no dedicated channel-art file; not
chased further). This `CHARTS/CHANNELARTSCACHE/` folder is a live,
per-channel logo CACHE keyed directly by `SourceId` -- separate from
`SIRIUS.DB3`'s own baked-in `Image_BaseAttributes`/
`ImageBlob_BaseAttributes` tables (which, by the map disc's own already-
cracked `POI.DB3` icon-chain precedent, most likely hold generic
category icons, not per-channel logos -- not independently verified
this session).

============================================================================
`IBOC.FLI` -- CHECKED directly on both real North America discs, a
clean, structural NEGATIVE result across ALL 5 real discs this project
now has (3 EU + 2 NAR)
============================================================================
Neither `RNS510_4366` nor `US_RNS-510_SW1140` (the first 2 real NAR
discs this project has ever had -- the single most plausible place
In-Band On-Channel/HD Radio firmware would actually ship) contains an
`IBOC.FLI` file or an `IBOC` folder anywhere -- checked with a
recursive filename search, not just the top level. Both discs' own
`USER.CFG`/`user.cfg` confirm exactly why: `IBOC = 0` /
`FORCE_IBOC_UPDATE = 0`, the SAME disabled state already found on the
EU disc. Both discs' real `ECUORDER.TXT`/`EcuOrder.txt` flash sequences
(`SWL -> HOST -> APPS -> HDD -> RADIO -> [MPEG, NAR-disc-only] -> VUCI`)
confirm this isn't an oversight -- `IBOC` genuinely never appears as a
flashed target, while `RADIO`/`VUCI`/etc do. `IBOC` IS a real, known
build option in the shared build-configuration system on every disc
checked (`CDSTRUCT.CFG`/`USER.CFG` all reference it) -- it's just never
been ENABLED on any of the 5 real discs this project has. A genuinely
different disc (one built with `IBOC=1`) would be needed to actually
open this file -- not something reachable by checking more of the
discs already on hand.

============================================================================
The 2 real North America `FHDD6.FLI` builds -- a 4th independent
cross-build confirmation the 9MB+ disassembly wall is structural, not
an artifact of the EU market specifically ("lets continue", same
session)
============================================================================
Each NAR disc's `PROG/` folder is per-project-variant (`APPS/SILVER_1/
NARBY/PROG/`, `.../NARPQTO/PROG/`), unlike the EU discs' single shared
location -- but both variants on a given disc are byte-identical
(same SHA256), so effectively 2 more real, distinct `FHDD6.FLI` builds:
**`RNS510_4366`, 87,890,828 bytes** (~2.2MB LARGER than the EU disc)
and **`US_RNS-510_SW1140`, 75,554,712 bytes** (~10MB smaller -- an
older, 2011 build). Real `"Sirius"`/`"SDARS"`/`"IBOC"` debug strings
appear in ALL 3 builds checked, including the EU one (329/785/188
hits) -- this is shared, market-independent APPLICATION code gated at
runtime by the `SetCoding` byte-7 enum (above), not a separate
per-market codebase; NAR4366 simply has more (472/2178/237),
consistent with it being the newer, larger build.

**A promising-looking lead, tested and REFUTED**: `NAR4366`'s own
`"Sirius"`/`"SDARS"` strings cluster heavily at file offset 10-15MB
(162/243 hits) -- inside the exact zone (~10-17MB) this project's own
[Firmware Reversing wiki page](https://github.com/krcenov/RNS510-Map-Viewer/wiki/Firmware-Reversing)
already confirmed dead for the EU build, raising a real hope that a
different market's build might have LIVE code there. Checked directly
with `find_prologues()`: prologue density is **1000+/MB from 2-9MB,
then ZERO from 10MB on** -- the identical shape already documented for
EU, not a NAR-specific exception. The 10-15MB strings are Java-class
content (or similar non-code data), not native code.

**The SAME `FHDD6_LOAD_BASE` (`0xf688dcf4`) resolves a real, sensible
symbol table on this completely different-sized build** --
`parse_symbol_table()` finds 26,215 total entries (10,268 under 9MB) on
`NAR4366` -- real, independent confirmation (a 4th distinct build
family now, not just 2 EU siblings) that this base is a genuine, stable
toolchain property, not a coincidence specific to one build. And
`readNodeMP0`/`findNode__14MDCacheTIRTree` (the project's own
highest-value unreachable targets) resolve to 10.9MB/16.4MB in THIS
build too -- squarely inside the confirmed-dead zone, same as every EU
build already checked. **Net conclusion**: the 9MB+ wall is now
confirmed across EU and NAR market families both -- not an EU-specific
stripping choice, genuinely structural to how this codebase is linked
everywhere it's been checked. Closing "try a different market's
firmware" as a real, tested avenue for this specific problem, not an
unexplored one.

**A quick follow-up check, same session**: `WA/CTEST.OUT` is
byte-IDENTICAL (same SHA256) across all 6 copies now available --
`5238_MOD_C3_C4`, `5274_MOD_C6_C12`, `6276_MOD_C14`, `RNS510_4366`,
`US_RNS-510_SW1140`, and `VIM_Berto89` -- including the 2006-dated
`VIM_Berto89` copy. No diffing opportunity; this tool hasn't changed at
the byte level across years of firmware releases and both market
families. The differing filesystem mtimes seen earlier are stale/
inherited from repackaging, not evidence of real content changes.

```python
import zlib, struct

def decode_ddb(path):
    with open(path, "rb") as f:
        data = f.read()
    zlib_start = data.find(b"x\\xda")
    header = data[:zlib_start]
    w = header[17] | (header[18] << 8)
    h = header[19] | (header[20] << 8)
    payload = zlib.decompress(data[zlib_start:])
    color_plane = payload[:w * h * 2]
    mask_plane = payload[w * h * 2:]
    rgb = bytearray()
    for i in range(0, len(color_plane), 2):
        v = color_plane[i] | (color_plane[i + 1] << 8)
        b5, g5, r5 = (v >> 10) & 0x1f, (v >> 5) & 0x1f, v & 0x1f
        rgb += bytes([(r5 * 255) // 31, (g5 * 255) // 31, (b5 * 255) // 31])
    return w, h, bytes(rgb), mask_plane   # RGB888 pixels + 8-bit alpha, both row-major
```
"""

# `FHDD6.FLI`'s recovered load base for its 0-24MB native-PowerPC region's
# code-dense 1.2MB-9MB sub-range: VA = file_offset + FHDD6_LOAD_BASE.
# Verified byte-exact 3 independent ways (see this module's own docstring,
# "the load base WAS recovered" section). Do NOT assume this holds beyond
# ~9MB -- see parse_symbol_table()'s own docstring for the confirmed limit.
FHDD6_LOAD_BASE = 0xf688dcf4

# Real function-prologue signature for this codebase's compiler (GCC 2.96,
# PowerPC 603gnu): `stwu r1,-N(r1)` (bytes 0x94 0x21, N in bytes 2-3)
# immediately followed by `mflr r0` (fixed bytes 0x7c 0x08 0x02 0xa6).
# Finds 7,757 real, low-false-positive candidates across the whole 24MB
# native region (README S2.6). Does NOT catch every real function --
# simple leaf functions can validly skip this exact frame-setup shape.
_PROLOGUE_TAIL = b"\x7c\x08\x02\xa6"


def find_prologues(data, offset_base=0):
    """Scan `data` for the `stwu r1,-N(r1)` + `mflr r0` byte signature at
    every 4-byte-aligned offset. Returns a set of absolute offsets
    (`offset_base` + position within `data`). See `_PROLOGUE_TAIL`'s own
    comment for what this does and doesn't catch."""
    hits = set()
    for off in range(0, len(data) - 8, 4):
        if data[off] == 0x94 and data[off + 1] == 0x21 and data[off + 4:off + 8] == _PROLOGUE_TAIL:
            hits.add(offset_base + off)
    return hits


def parse_symbol_table(fli_bytes, base=FHDD6_LOAD_BASE, max_code_offset=9_000_000,
                        require_prologue=False, prologue_set=None):
    """Parse `FHDD6.FLI`'s real, large-scale (~26,000+ entry) per-function
    symbol/EH-descriptor table -- discovered this session by tracing a
    literal-pointer reference to a known function (`findSegIndex`) found
    via `find_prologues()`. NOT documented anywhere else; this is the
    first parser for it. See this module's own docstring, "a real,
    large-scale... symbol/EH-descriptor table" section, for the full
    discovery writeup and validation numbers.

    Record format (empirically derived, not from any spec): a 3-byte-
    fixed/1-byte-variable marker (`\\x00\\x10\\x05<var>`), a NUL-terminated
    mangled C++ name, variable-length header fields (compiler-generated,
    role not fully decoded), a monotonically-increasing 4-byte ordinal
    counter (confirmed sequential across real records), then 5 trailing
    4-byte fields ending right before the next record's marker. Field
    INDEX 4 (the last of the 5) is the function's own real code address
    for records whose code lives in the verified 1.2MB-9MB range --
    confirmed via a 7,757-known-prologue cross-check: position 4 wins
    decisively (35 hits vs. 3-6 for positions 0-3, ~700x the ~0.05-hit
    chance baseline for that sample size).

    **CONFIRMED LIMIT, load-bearing, do not ignore**: this resolution
    ONLY works for code living in the load-base-verified 1.2MB-9MB range.
    ALL 35 confirmed-good hits land under 9MB; ZERO land at or beyond.
    `readNodeMP0`'s own record (the VNode-pipeline's single highest-value
    target) implies an address ~11.4MB in -- a +/-200,000-byte search
    around that target found ZERO real prologues at all, confirming this
    isn't a calibration issue but a genuine absence of resolvable code
    there under any base tried so far. Passing `max_code_offset` narrower
    than the default is more conservative; widening it past ~9MB will
    silently include unreliable entries -- this function does NOT
    validate that for you beyond the simple range check.

    Args:
        fli_bytes: the whole `FHDD6.FLI` file's bytes (not just a slice --
            record fields can reference content anywhere in the file, and
            name text is read directly from `fli_bytes` too).
        base: load base for VA-to-file-offset conversion.
        max_code_offset: only return entries whose field-4 implied file
            offset falls below this -- see the CONFIRMED LIMIT above for
            why the default is 9,000,000, not the full 24,000,000.
        require_prologue: if True, only return entries whose field-4
            offset ALSO matches `find_prologues()`'s strict signature
            (highest confidence, but excludes real leaf functions that
            don't use that exact shape -- this is why it defaults False).
        prologue_set: required if `require_prologue=True` -- pass
            `find_prologues(fli_bytes[:24_000_000])`'s own return value.

    Returns:
        {name: file_offset} for every record whose field-4 implied
        address falls in `[0, max_code_offset)` (and, if
        `require_prologue`, also matches a known-good prologue).
        Later records with a duplicate name overwrite earlier ones (this
        table has genuine duplicate/overloaded-method entries -- callers
        wanting every occurrence should not use this function as-is).
    """
    if require_prologue and prologue_set is None:
        raise ValueError("require_prologue=True needs prologue_set")

    prefix = b"\x00\x10\x05"
    markers = []
    idx = 0
    while True:
        idx = fli_bytes.find(prefix, idx)
        if idx == -1:
            break
        markers.append(idx)
        idx += 1

    results = {}
    for i in range(len(markers) - 1):
        m = markers[i]
        next_m = markers[i + 1]
        span = next_m - m
        if span < 20 or span > 4000:
            continue  # implausible record size -- marker collision or unrelated data
        name_end = fli_bytes.find(b"\x00", m + 4, m + 4 + 200)
        if name_end == -1:
            continue
        fields_start = next_m - 20
        if fields_start < name_end:
            continue
        code_va = int.from_bytes(fli_bytes[fields_start + 16:fields_start + 20], "big")
        fo = code_va - base
        if not (0 <= fo < max_code_offset):
            continue
        if require_prologue and fo not in prologue_set:
            continue
        name = fli_bytes[m + 4:name_end].decode("latin-1")
        results[name] = fo
    return results
