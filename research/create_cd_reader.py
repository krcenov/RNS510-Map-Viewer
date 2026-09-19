"""
create_cd_reader.py -- documents config/create_cd, CRACKED (it's plain
text, nothing to "decode" byte-wise): the disc's own build/mastering
script, the literal record of how `CD_8555.ISO` was assembled from
Navteq/Siemens/Continental's internal production file servers. This is
the single most authoritative source this project has found for what's
really on the disc and where it came from -- not inferred, not
reverse-engineered, just read directly.

============================================================================
What it is
============================================================================
A tiny (5,105 byte) plain-text script at `config/create_cd` (disc root,
not under `db/`), dated 22.07.2019, matching every file's own real
mtime on this disc. Shell-like syntax (`mkdir`/`cd`/`cp`/`cp -r`), one
command per line, semicolon comments. It is the LAST file copied onto
the disc (its own final lines copy itself into `config/create_cd` --
the build script documents its own inclusion).

Every `cp` line's SOURCE path is a real internal Navteq/Siemens
production file-server path, most under a mapped drive `v:\\db\\
PRODUCTION\\NT\\VW\\EU2019Q1\\eu910\\eeu\\eeu\\505.30.910.1.84\\...` --
this is the literal origin of the `EEU50530910.84` version string every
NOT_COMPRESSED file's own 94-byte SIEMENS header carries (README S3,
S3.1 and everywhere else, verified directly: `eeu.rd`'s own header bytes
spell out exactly `EEU50530910.84`). The correspondence is strong but
not a trivial dot-stripping match: the path's `505.30.910.1.84` has 5
dot-separated components; the header string is `EEU` + `50530910` + `.`
+ `84` -- the first 3 path components concatenated (`505`+`30`+`910`),
then the LAST component (`84`) after a literal dot, with the 4th
component (`1`) not represented at all. Plausibly the header format only
ever carries `<major><minor><patch>.<build>`, with a `<revision>`
component (the path's own `1`) that exists in the source tree's own
versioning but isn't surfaced on-disc -- not confirmed against another
disc/release to verify the pattern holds in general.

============================================================================
Confirms/extends things this project already suspected
============================================================================
- **`ZIP_3kb` is the source tree's own folder name** for every
  FLAT_COMPRESSED/MAP_COMPRESSED file's compressed variant (`eeuz.*`) --
  i.e. `block_size=3072` (README S3.5) was a deliberately NAMED packaging
  choice at the source, not just an empirically observed constant.
  `eeuz.fea` -- despite being FEATURE_COMPRESSED, a different container
  -- is ALSO sourced from a `ZIP_3kb` folder, consistent with the shared
  80-byte-header/zlib-block-packing primitive both formats reuse (README
  S3.10).
- `db/zone.cfg` and `files.cfg` are copied from a SEPARATE path
  (`d:\\GDVDImages\\CD_8555\\...`, the disc-mastering staging area) --
  not from the `eeu` map-data production tree at all. Consistent with
  them being disc/mastering-level metadata, not map content.
- `eeu.mod`'s own first-string identity as `Arriba`/`5.3` (README
  S3.16) is independently corroborated: `EDB/POI/POI.DB3`'s own
  `PredefinedStatementBuild.ConfigSpec` metadata (see poi_db_reader.py)
  names the real internal codebase `arriba2`/`arriba2_VW` directly
  (ClearCase VOB element paths under
  `/siemens/source/navicore/tools/predefstmt/...`) -- "Arriba" is
  Siemens/Continental's own real internal name for this whole
  navigation-core toolchain, not just the map-compiler component.

============================================================================
New: 5 disc-root subsystems this project had NEVER examined, now
identified by name and real source
============================================================================
The script also builds 5 top-level folders alongside the already-heavily
-investigated `db/`, all present on the reference disc:

  config/   -- this script + (implicitly) other disc-mastering metadata
  tpd/      -- `TPD3.DIC` + `nscWeu_eue_20190607/` (per-LANGUAGE subfolders
               CZE/DUT/ENG/FRE/GER/ITA/POR/SPA, plus ICONS/ICONS810/
               IMAGES/TABLES/INFO25.PSC/LPOI.TXT) -- sourced from
               `...\\505.30.910.84\\TPD\\` (note: NO ".1" in this specific
               source version, unlike the main `eeu` tree's
               `505.30.910.1.84` -- a real, minor version-numbering
               discrepancy between sub-components of the same release,
               not investigated further). Plausibly "Text and Picture
               Database" -- POI-category icons and per-language HTML
               help/legal template pages (`CATTEMPLATE.HTM`,
               `SF_*.HTM`) -- NOT opened/decoded this session.
  EDB/POI/  -- `POI.DB3`, a real SQLite database -- CRACKED, see
               poi_db_reader.py. Confirms and finally OPENS the file
               this project's own firmware investigation (README S2.5)
               already predicted must exist from `vdo.nav.api.edb.*`
               JDBC-like strings, but never had disc access to check
               directly until now.
  telemat/  -- `tmc2/` -- real, standard ALERT-C (ISO 14819) TMC traffic
               location tables. CRACKED (config file; `.lt`/`.et` binary
               tables NOT decoded), see below.
  speech/   -- `SpeechRes.xml` + `parts/*.zip` (8 per-locale ZIPs:
               csCZ/deDE/enGB/esES/frFR/itIT/nlNL/ptPT, filename prefix
               `uvo_`) -- sourced from a DIFFERENT internal server
               (`\\\\rbfs02p2\\did02377\\db1\\db\\a3\\speech\\vw\\
               20061102\\...`, dated 2006 -- much older than the map
               data itself, i.e. a long-lived, slowly-updated shared
               speech-resource component reused across many map
               releases). NOT opened this session -- a real lead for
               understanding the actual TTS ENGINE (as opposed to the
               phoneme/pronunciation DATA this project has already
               extensively cracked in eeu.abc/eeuz.pca/eeuz.prd/
               eeuz.pct/eeu.pcl).
  dbal/     -- `VERSIONS.CFG` + 5 version folders (V006_047/V007_038/
               V008_704/V009_038/V010_015), each a single `DBAL.OUT`
               file -- "Database Abstraction Layer", one compiled binary
               per supported head-unit software generation, all reading
               the SAME map database format. Sourced from
               `\\\\rbfs02p2\\did02377\\db1\\db\\tools\\dbal\\VW\\
               VW-V6.47_V7.38_V8_704_V9_38_V10_15_wrong_phoneme_Dummy\\
               ...` -- the literal source folder name suggests this is a
               specific internal build/test configuration ("wrong
               phoneme Dummy"), not necessarily the exact retail DBAL,
               though it shipped on this retail disc regardless. NOT
               opened this session (binary format, no obvious text
               structure from a quick look).

Also 2 disc-root manifest files, opened and CRACKED (plain text) in a
later pass of this same session -- tying every subsystem's own version
stamp together: `cdrom.toc` (543 bytes) is a real, human-readable
manifest -- `Version: 505.30.910.1.84` (an EXACT match to `create_cd`'s
own source path, closing that loop completely), `TPD: 2019060000`
(matches `tpd/nscWeu_eue_20190607/LPOI.TXT` and `INFO25.PSC`'s own
`TPD-PRODID` exactly), `SVD: EDB_20190607` (matches `EDB/POI/POI.DB3`'s
own `database.id` exactly), `TMC: 20190610` (matches `telemat/`'s own
source path date exactly), `DBAL: V006.047 V007.038 V008.704 V009.038
V010.015` (matches `dbal/`'s own 5 folder names exactly), `Customer
Info: VW`, `Customer: 1627386654`. `DBINFO.TXT` is a real per-brand
manifest: VW part number `1T0051859AR`, system name `"EU East V17"`,
and placeholder (`"tbd"`) Seat/Skoda/Bentley part numbers -- confirms
this disc build serves the whole VW Group brand family, matching
`POI.DB3`'s own category split (see the POI.DB3 section above).

============================================================================
telemat/tmc2 -- CRACKED (the human-readable config); a strong, validated
new lead for eeu.tmc, itself NOT opened this session
============================================================================
`telemat/tmc2/TMCCONFIG.ini` is plain, human-readable, self-documenting
text: `PROD = "RNS_EU_38"`, `SCOPE = "EU"`, and one `[LT]`/`[LTX]` line
per country:

    AUSTRIA = 0xa, 1, "AT", "aut_A_1_3_4", 9.53485, 46.41923, 17.11080,
              48.99898, 0, 272678, , "A"

-- real ALERT-C **Country Code** (hex) and **Location Table Number**
(the international TMC standard identifier pair every real TMC receiver
uses), the real ISO 3166-1 alpha-2 code, the `.lt` filename, and a REAL
bounding box in plain decimal degrees (no scaling needed) -- Germany's
own line (`5.877, 47.387, 15.0087, 55.017`) is Germany's real bounding
box, immediately verifiable, no further validation needed. 14 countries'
worth of real `.lt` binary location tables are present (Austria,
Belgium, Switzerland, Czechia, Germany x2 CCs, Denmark, Spain, Finland,
France, UK, Italy, Netherlands, Norway, Sweden), plus a `[LTX]` UTF-8
Czech variant, plus an `[ET]` section listing 19 real per-language
"event text" tables (`.et` files, ISO 639 language codes) with their own
exact byte sizes (matching the real files on disc exactly).

The `.lt`/`.et` files themselves are NOT plain text (binary, not opened
this session) -- but `eeu.tmc` itself (README S3, "still genuinely
unexplored" as of the prior session) was checked against this new
ground truth and shows a real, promising, NOT YET CRACKED structural
lead: scanning the first ~20KB of its body for short ASCII digit runs
terminated by NUL finds a real sequence of small, mostly-ascending
integers (117, 118, 225, 259, 305, 306, 336, 338, 339, 340, ... up to
951 in a 20KB sample) -- consistent with real ALERT-C **Location Code**
(LCD) point numbers, which are conventionally small integers assigned
per-country in real TMC tables. Not cross-checked against any specific
country's own `.lt` file content, and no surrounding field structure was
decoded -- left as a concrete, well-motivated starting point for a
future session (this module intentionally stops short of a full
`eeu.tmc` crack; that deserves its own dedicated investigation the way
every other `eeu.*` file in this project got).

============================================================================
Practical use
============================================================================
This module has no parsing functions -- `config/create_cd` is plain
text, read directly. See `poi_db_reader.py` for `EDB/POI/POI.DB3`.
"""
