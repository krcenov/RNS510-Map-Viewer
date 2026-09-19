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
