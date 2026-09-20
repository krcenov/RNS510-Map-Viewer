"""
telemat_reader.py -- documents `telemat/tmc2/` (disc root, not under
`db/`): real, standard TMC (Traffic Message Channel, ISO 14819/ALERT-C)
traffic-data resources. `TMCCONFIG.ini` is CRACKED (plain, self-
documenting text). The `.lt`/`.et`/`.cat` binary tables are IDENTIFIED
(real content confirmed) but NOT byte-level cracked.

Found via `config/create_cd` (research/create_cd_reader.py).

============================================================================
`TMCCONFIG.ini` -- CRACKED (plain text)
============================================================================
`[PROD]` section: `PROD = "RNS_EU_38"`, `SCOPE = "EU"`. `[LT]`/`[LTX]`
sections: one line per country --

    AUSTRIA = 0xa, 1, "AT", "aut_A_1_3_4", 9.53485, 46.41923, 17.11080,
              48.99898, 0, 272678, , "A"

fields: real ALERT-C **Country Code** (hex) + **Location Table Number**
(the international TMC identifier pair every real TMC receiver uses),
ISO 3166-1 alpha-2 code, `.lt` filename (encodes country/CC/LTN/version
-- `aut_A_1_3_4.lt` = Austria, CC=0xA, LTN=1, version 3.4), a real
bounding box in plain decimal degrees (Germany's own line:
`5.877, 47.387, 15.0087, 55.017` -- immediately verifiable as Germany's
real bounding box, no scaling needed), and the file's own exact byte
size (matches the real file on disc exactly). 14 countries present:
Austria, Belgium, Switzerland, Czechia, Germany (2 Country Codes, 0x1
and 0xD -- two real regional broadcast variants), Denmark, Spain,
Finland, France, UK, Italy, Netherlands, Norway, Sweden. `[LTX]` adds
one UTF-8 Czech variant. `[ET]` lists 19 real per-language "event text"
tables (ISO 639 codes) with their own exact byte sizes.

============================================================================
`.lt` files (`loc/*.lt`, 14 files) -- IDENTIFIED, NOT byte-level cracked
============================================================================
Real ALERT-C binary location tables (per-country hierarchical point/
segment/road/area location codes with linear-referencing offsets, per
the international TMC standard) -- confirmed by `TMCCONFIG.ini`'s own
description and the standard `<country>_<CC>_<LTN>_<version>.lt` naming
convention, not by decoding the binary layout itself. Whole-file size
does not divide evenly by any small candidate record width (checked
4-40 bytes) -- consistent with the real ALERT-C format's own variable-
length record shapes (point/segment/area/road records differ in size),
not a simple fixed-record table like most `db/` files on this disc. Not
compressed (no zlib/gzip magic found) and not human-readable text.

============================================================================
`.et` files (`lan/*.et`, 19 files) -- content CONFIRMED, packing NOT
cracked
============================================================================
Real, standard TMC/ALERT-C phrase-fragment libraries -- confirmed
directly: `lan/english.et`'s own body contains real, recognizable
English phrase fragments ("Approach with care", "Beware of stationary
traffic", "Blocked entry", "Carriageway reduction", "Contraflow in
operation", "Danger of stationary traffic", "Delays expected", "Hard
shoulder closed", "Lanes closed", "Passable with care", "Queuing traffic
for 1/2/3/4/6/10 km", "Road closed", "Single alternate traffic",
"Slippery roads", "Slow traffic for N km", "Stationary traffic for N
km", "Traffic flowing freely"), plus real month names (April, August,
February, June, ...) and day names (Friday, Monday, Saturday, ...) --
exactly the phrase-template library a real RDS-TMC receiver uses to
reconstruct human-readable traffic messages from a small set of coded
event/distance/date fragments. A small header embeds the source
filename directly (`english.csv` -- confirming this is a COMPILED
version of a real, plain CSV source file) plus a language code (`en`).

Many extracted fragments are missing their own leading 1-3 characters
(e.g. `pril` instead of `April`, `eware` instead of `Beware`, `hursday`
instead of `Thursday`) -- consistent with a length-prefixed or bit-
packed string table where a short binary control/length byte
immediately precedes each string and was not distinguished from
printable text by a naive scan; the exact packing scheme (and any
string-sharing/overlap compression) was NOT decoded this session.

----------------------------------------------------------------------------
A LATER SESSION: a real, careful attempt at the packing scheme --
2 clean hypotheses tested and REFUTED with concrete evidence; the exact
scheme NOT identified. A genuine wall for this session.
----------------------------------------------------------------------------
`english.et` (13,200 bytes) splits cleanly into 3 regions by direct
inspection: a 39-byte file header (embeds `english.csv` + a language
code `en`, confirmed prior session), a **5,764-byte binary region**
(bytes 39-5802), then the **7,397-byte text blob** (bytes 5803-end,
where the first real readable text, `"proach with care"` -- i.e.
`"Approach with care"` missing its own leading `"Ap"` -- begins). The
blob itself contains ZERO `0x00` (NUL) bytes anywhere -- rules out a
plain NUL-terminated string list outright.

**Hypothesis 1, plain (offset, length) index table in the 5,764-byte
region -- REFUTED.** Reinterpreted as an array of 2,882 little-endian
uint16s and checked how many fall inside the blob's own valid byte
range (0-7397): only 1,044 of 2,882 (36%) do, with no visible
increasing/sequential pattern in the ones that do -- inconsistent with
a real offset table, where the great majority of entries would have to
land inside the blob's range by construction.

**Hypothesis 2, plain IEEE-754 float32 array (motivated by the header's
own highly skewed byte distribution -- `0x40` appears in 22% of all
header bytes, `0x00` in 21%, `0x01` in 7%, `0xC1` in 6.8%, `0xC0` in
4.3%, all classic "common float32 exponent byte" values, vs. a near-
flat distribution a real offset table or bit-flag table would show) --
REFUTED. Reinterpreted as 1,441 little-endian float32s: only 36% land in
a plausible small-magnitude range (`0.01 < |x| < 10000`); the rest
decode to nonsensical huge (`1e35`) or vanishingly small (`1e-38`)
exponents. The skewed byte distribution is real and reproducible, but
does not resolve into a clean float table this way (a different
endianness, a different float width, or a genuinely different meaning
for those bytes was not tried further).

**The in-blob "missing leading characters" phenomenon is real, exact,
and reproducible** (confirmed via precise byte-offset hex dumps, not
scan artifacts): `"...care"` is followed by exactly one byte `0x14`,
then literally `p`,`r`,`i`,`l` (4 bytes, no `A` anywhere) -- yet 6 bytes
later, `August` appears as `0x06` followed by the COMPLETE 6-byte word
`August` (including its own `A`). The same leading letter (`A`) is
encoded two completely different ways in two adjacent entries just a
few bytes apart -- real evidence of *some* kind of per-entry prefix/
dictionary substitution (the file's very first real string, `Approach`,
already has its own leading `"Ap"` (2 chars) replaced the same way, so
it cannot be a simple back-reference to an *earlier* occurrence in the
SAME blob -- there is no earlier occurrence for the first entry). Concrete,
unresolved candidates for a future session: (a) a small STATIC
prefix/dictionary table shared across ALL 19 `.et` files (would need
cross-referencing multiple languages' files at the same relative
control-byte values to test), (b) genuine bit-level Huffman coding of
just the first 1-3 characters with the remainder left as literal bytes
(would explain why the boundary sometimes falls byte-aligned, as with
`August`, and sometimes doesn't). Neither was tested -- both require
either the real format spec or substantially more dedicated statistical/
cross-file analysis than a single continuation session affords. Marked
here as a genuine, not-yet-workaroundable wall, not abandoned
prematurely -- 2 concrete simple hypotheses were tried and cleanly
refuted with real byte-level evidence rather than just re-asserting the
prior session's "not decoded" note.

**A LATER session, from the FIRMWARE side** (a separate factory
firmware disc the user provided, `research/swl_5238_reader.py`): while
investigating the `eeu.tmc` leaf-content wall, the firmware's own
embedded debug strings revealed a real, complete `LanguageTable`/
`TokenTable`/`NodeTokenEntity` subsystem -- real methods
`SortTokenTable`, `FindLongestInTokenTable__13LanguageTableUiUi`,
`FindTextInTokenTable__13LanguageTablePC9CfcStringRUiP9CfcString`,
`AddTokenEntity__13LanguageTableRC9CfcStringT1Ui`, and a real
`decode__13LanguageTableR19CfcIoCodecInterfaceR13CfcUtilBuffer`
deserializer -- i.e. a genuine LONGEST-MATCH DICTIONARY TOKENIZER,
architecturally exactly the kind of mechanism that would produce this
project's own "missing leading characters" observation (a common
prefix/word gets replaced by a short token id during encoding; decoding
looks the id back up in the same shared table). **Important caveat, to
avoid overclaiming**: the real source path for this exact class is
`N:/siemens/source/navicore/modules/naviservice/voicegeneral/
SentenceAssembler.cpp` -- this is the TURN-BY-TURN VOICE-GUIDANCE
sentence assembler (building spoken instructions from `NodeVoiceToken`
sequences), a DIFFERENT, though clearly related, resource from
`telemat/tmc2/lan/*.et`'s own raw phrase-fragment library. `LanguageTable`
does have its own `AddTmc`/`GetTmc`/`SetTmc`/`GetTmcToken` methods,
confirming TMC-derived content DOES flow through this same token-table
pipeline when being spoken aloud -- but that's downstream of the raw
`.et` bytes (presumably read by the separate `CFlowTmc`/`TMC_List`
code the same firmware scan found), not proof this exact class parses
`.et` files directly. **Net effect**: a plausible, structurally
consistent MECHANISM (dictionary/token-table substitution) for the same
codebase and era, not a confirmed identification of `.et`'s own file
format -- upgrades this wall from "no idea what kind of scheme this is"
to "very likely a dictionary/token-table scheme, real precedent exists
in this exact code area," without closing it.

============================================================================
`eventinfo_2011_11_30_eu_nar_chnexc.cat` (866 bytes) -- NOT examined
in depth
============================================================================
Binary, small. Filename embeds a real date (2011-11-30) and plausible
region/purpose tags ("eu_nar" -- Europe/North America?; "chnexc" --
"channel exception"?). Not decoded.

============================================================================
Relationship to `eeu.tmc` -- a strong lead, not yet closed
============================================================================
`eeu.tmc` (README S3, still not opened as of the prior sessions) is
almost certainly a COMPILED, on-board-optimized derivative of exactly
this same underlying TMC/ALERT-C data (`eeu.mod`'s own schema names its
real table `"tmc file"`, 74 fields, README S3.16/S3.22). A quick scan of
`eeu.tmc`'s own first ~20KB for short ASCII-digit runs finds a real
sequence of small, mostly-ascending integers (117, 118, 225, 259, 305,
306, 336, 338, 339, 340, ..., up to 951 in that sample) -- consistent
with real ALERT-C Location Code (LCD) point numbers. Not cross-checked
against any specific country's own `.lt` content, and no surrounding
field structure decoded -- left as a concrete starting point for a
future, dedicated `eeu.tmc` session.

============================================================================
Practical use
============================================================================
This module has no parsing functions -- `TMCCONFIG.ini` is plain text,
read directly; the `.lt`/`.et`/`.cat` binary formats were not decoded
this session.
"""
