"""
stt_reader.py -- decodes eeu.stt, CRACKED this session: the real
"state" table -- sub-national regions/cantons/provinces, one level
above `eeu.cny`'s counties (`eeu.cny`'s own `state_id` field, cracked
via eeu.mod, README S3.15, is a foreign key straight into this file).
Previously unexamined -- only a candidate record size (114 bytes) had
been derived from the shared NOT_COMPRESSED header fields
(aff_reader.py), not the content.

============================================================================
Record format -- CRACKED, validated at FULL scale (every one of 691
records)
============================================================================
94-byte header (record count 691 comes straight from its own now-cracked
bytes[86:88] field), then exactly 691 fixed 114-byte records. Every byte
range was checked across the WHOLE file (not sampled) for "always zero"
vs. real content, giving an exact, unambiguous field layout with zero
guesswork about boundaries:

    +0    uint16 LE  state_id    -- plain ascending 0..690, record N's
                                     own position (confirmed exact, no
                                     gaps) -- eeu.mod's real field name:
                                     `stateID`. Matches eeu.cny's own
                                     `state_id` field EXACTLY: same 691
                                     distinct values, same 0..690 range,
                                     verified as literally the same SET
                                     (research/cny_reader.py cross-check,
                                     see below) -- this really is the
                                     real "state" table eeu.cny points
                                     into.
    +2    bytes[22]  --  always zero on every record checked (691/691)
                          -- per eeu.mod's own "state" schema, this
                          region should hold `zoneID`, `start_countyID`,
                          `end_countyID`, `cover`, and a `min_long`/
                          `min_lat`/`max_long`/`max_lat` bounding box (8
                          real sub-fields) -- all apparently unpopulated
                          on this disc, the SAME situation already found
                          for eeu.cny's own analogous always-zero region
                          (README S3.15) -- a consistent, disc-wide
                          pattern, not a one-off.
    +24   bytes[36]  name        -- NUL-padded, the state/region/
                                     canton's real name, in the SAME
                                     language the disc's own eeu.ctr uses
                                     for that country (German for
                                     Switzerland, Italian for Italy,
                                     Greek-transliterated for Greece,
                                     etc.)
    +60   uint8      country_id  -- CRACKED, validated EXACTLY against
                                     ALL 691 records (100% match, zero
                                     anomalies): a real foreign key into
                                     eeu.ctr's own ROW ORDER (0-34), NOT
                                     eeu.cal's alphabetical-by-ISO-rank
                                     numbering (a THIRD, independent
                                     country-numbering scheme already
                                     found on this disc, alongside
                                     eeu.cal's and eeu.cty's own tag --
                                     see below). eeu.mod's real field
                                     name: `countryID`.
    +61   bytes[53]  --  always zero on every record checked (691/691)
                          -- per the schema, this region should hold
                          `alpha_counties` and `countyID`, both
                          apparently unpopulated here too.

============================================================================
`name` -- CRACKED: real sub-national administrative divisions, named in
the parent country's own language
============================================================================
Confirmed directly: `KRITI` (Crete, Greece), `GENÈVE`/`WALLIS`/`TICINO`
(3 real Swiss cantons, named in German/French as eeu.ctr itself does for
that country), `VALLE D'AOSTA`/`PIEMONTE`/`LIGURIA` (3 real Italian
regions). Every name checked is a real, correctly-spelled administrative
division of its own `country_id`.

============================================================================
`country_id` -- CRACKED: a real foreign key into eeu.ctr's OWN ROW
ORDER, not eeu.cal's numbering -- a 3rd distinct country-numbering
scheme found on this disc
============================================================================
Brute-force checked against eeu.cal's alphabetical-by-ISO-alpha-3-rank
`country_id` (cal_reader.py) FIRST and found NO byte offset in the
record matching it at all -- the value at byte 60 for Switzerland/Italy/
Greece test records (0, 2, 13) doesn't match eeu.cal's own numbering for
those countries (6, 15, 12). Checked instead against `eeu.ctr`'s own row
index (the literal position of each country's record in eeu.ctr's own
file, README S3.11-adjacent) and found an EXACT match: row 0 =
`SCHWEIZ` (Switzerland), row 2 = `ITALIA` (Italy), row 13 = `ELLADA`
(Greece) -- exactly the 3 test values. Extended to the full file: every
one of the 691 records' `country_id` byte (range checked: 0-34, all 35
`eeu.ctr` rows represented) decodes to a real `eeu.ctr` country name,
summing to exactly 691 with zero unmapped/invalid values. Sanity-check
counts per country are plausible (Vatican City=1, San Marino=1,
Liechtenstein=2 -- microstates; Turkey=81, Latvia=119 -- larger
subdivision counts for bigger states, though Latvia's is surprisingly
high relative to similarly-sized countries and not independently
explained).

This is now the THIRD distinct country-numbering scheme confirmed on
this disc (alongside eeu.cal's alphabetical-by-ISO-rank `country_id`,
README S3.13, and eeu.cty's own coarser per-country tag, README S3.8) --
this project has found no single unified country-ID space; every table
that references a country uses its own locally-consistent scheme.

============================================================================
Cross-validated against eeu.cny's own `state_id` field -- full set
equality, not just a few spot checks
============================================================================
`eeu.cny`'s own 691 distinct `state_id` values (research/cny_reader.py)
are the EXACT SAME SET as this file's own 691 `state_id` values (both
`{0, 1, ..., 690}`, verified by direct set comparison, not just matching
counts). 3 individual cross-checks, each independently correct:
`CHANIA` (a real Cretan county, eeu.cny) has `state_id=0` -> this file's
state 0 is `KRITI` (Crete), `country_id=13`=`ELLADA` (Greece) -- exactly
right. `IMPERIA` (a real Ligurian province) has `state_id=39` -> state 39
is `LIGURIA`, `country_id=2`=`ITALIA` -- exactly right. `SION` (a real
Valais district) has `state_id=4` -> state 4 is `WALLIS` (German name
for Valais), `country_id=0`=`SCHWEIZ` (Switzerland) -- exactly right.
This closes the loop this project opened when `eeu.cny` was first
cracked: `state_id` really is a genuine foreign key into a real,
independently-verifiable "state" table, not a guess.

============================================================================
Practical use
============================================================================
`read_stt(path)` returns every record as (state_id, name, country_id).
Combine with `eeu.ctr` (35 real countries, row-order `country_id`) and
`eeu.cny`/`eeu.cty` (research/cny_reader.py, README S3.8) for a full
4-level administrative hierarchy (country -> state -> county -> city).
"""

import struct

HEADER_SIZE = 94
RECORD_SIZE = 114


def read_stt(path):
    """Decode the whole eeu.stt file. Returns a list of
    (state_id, name, country_id) tuples, one per record, in file order.
    `name` is bytes (mostly ASCII, some non-ASCII European characters --
    decode with errors='replace' or per-locale as needed). `country_id`
    is a real foreign key into eeu.ctr's own row order (0-34), NOT
    eeu.cal's alphabetical numbering -- see this module's docstring."""
    with open(path, "rb") as f:
        data = f.read()
    body = data[HEADER_SIZE:]
    n = len(body) // RECORD_SIZE
    records = []
    for i in range(n):
        rec = body[i * RECORD_SIZE:(i + 1) * RECORD_SIZE]
        state_id = struct.unpack_from("<H", rec, 0)[0]
        name = rec[24:60].split(b"\x00", 1)[0]
        country_id = rec[60]
        records.append((state_id, name, country_id))
    return records
