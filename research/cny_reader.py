"""
cny_reader.py -- decodes eeu.cny, CRACKED this session, with field names
CORRECTED and EXTENDED in a later session once eeu.mod (the disc's own
schema dictionary, research/mod_reader.py) was found and decoded: this is
the "county" table -- real sub-national administrative divisions (Italian
provinces, Swiss canton districts, Greek prefectures, ...) one level below
`eeu.stt`'s "state" table (regions/cantons -- CRACKED in a later session,
research/stt_reader.py) and one level above `eeu.cty`'s cities/
localities. Previously entirely unexamined
-- only a candidate record size (176 bytes) had been derived from the
shared NOT_COMPRESSED header fields (aff_reader.py), not the content.

============================================================================
CORRECTION (later session, via eeu.mod): this file's own two field names
used in the original write-up ("index", "region_id") were guesses. The
real schema (eeu.mod's own "county" block) names them `countyID` and
`stateID` -- confirmed to be the SAME fields, just correctly named now.
The original write-up also guessed this file might BE the "region/state"
table; eeu.mod's schema shows that's actually `eeu.stt`, which
`eeu.cny`'s own `stateID` field refers to -- CONFIRMED directly in a
later session (research/stt_reader.py): `eeu.cny`'s 691 distinct
`state_id` values are the exact same SET as `eeu.stt`'s own 691
`state_id` values, and CHANIA/IMPERIA/SION (this file) all resolve to
the exactly-correct real state (KRITI/LIGURIA/WALLIS) in `eeu.stt`'s own
content.
============================================================================

============================================================================
Record format -- CRACKED, validated at full scale (every one of 2,326
records parses cleanly, zero exceptions)
============================================================================
94-byte header (record count 2,326 comes straight from its own now-
cracked bytes[86:88] field), then exactly 2,326 fixed 176-byte records:

    +0    uint16 LE  county_id   -- plain ascending 0..2325, record N's
                                     own position (confirmed exact, no
                                     gaps) -- eeu.mod's real field name:
                                     `countyID`
    +2    uint16 LE  state_id    -- CRACKED (identity): groups counties
                                     into real sub-national regions/
                                     cantons/provinces, see below --
                                     eeu.mod's real field name: `stateID`,
                                     referencing eeu.stt's own "state"
                                     records -- CONFIRMED (later session,
                                     research/stt_reader.py): a real,
                                     exact foreign key, not just a
                                     plausible guess
    +4    bytes[26]  --  always zero on every record checked (2326/2326)
                          -- per eeu.mod's own "county" schema, this
                          region should hold `zoneID`, `start_cityID`,
                          `end_cityID`, `cover`, and a `min_long`/
                          `min_lat`/`max_long`/`max_lat` bounding box (the
                          usual /100000 int32 convention -- 16 of these
                          26 bytes) -- all apparently unpopulated
                          (zero-valued) for every county on this disc,
                          not incorrectly identified; exact per-field
                          byte boundaries within these 26 bytes were NOT
                          independently determined this session (every
                          candidate field being zero makes the split
                          unverifiable from this file's own content
                          alone)
    +30   bytes[36]  name        -- NUL-padded, the county/district's
                                     real name
    +66   uint8      timeinfo_id -- CRACKED (identity, plausible, not
                                     independently confirmed): the next
                                     field in eeu.mod's own "county"
                                     schema after `name` is `timeinfoID`
                                     -- referencing eeu.ti's own
                                     time-dependent-restriction records
                                     (not yet independently opened/
                                     decoded). See below for why this
                                     fits better than the original
                                     write-up's untested "admin depth"
                                     guess.
    +67   bytes[109] --  always zero on every record checked (2326/2326)
                          -- per the schema, this region should hold
                          `alpha_cities` and `cityID`, both apparently
                          unpopulated here too.

============================================================================
`name` -- CRACKED: real sub-national administrative divisions
============================================================================
Confirmed directly, not just plausible-looking: the first 5 records alone
are `CHANIA`, `RETHYMNO`, `IRAKLEIO`, `LASITHI` -- the 4 real prefectures
of Crete, Greece, in their real west-to-east geographic order -- followed
immediately by `IMPERIA`, a real Italian province in Liguria. Scanning
further finds dozens more real, correctly-spelled administrative names:
`TORINO`/`CUNEO`/`ASTI`/`ALESSANDRIA`/`BIELLA`/`VERCELLI`/`NOVARA`/
`VERBANO-CUSIO-OSSOLA` (all 8 real provinces of Piedmont, Italy);
`MONTHEY`/`SAINT-MAURICE`/`MARTIGNY`/`ENTREMONT`/`CONTHEY`/`SION`/
`HERENS`/`SIERRE`/`LEUK`/`VISP`/`BRIG` (real districts of Valais,
Switzerland); `NYON`/`MORGES`/`LAUSANNE`/`AIGLE`/... (real districts of
Vaud, Switzerland); `LA SARINE`/`LA GRUYERE`/`LA GLANE`/`SENSE`/... (real
districts of Fribourg, Switzerland).

============================================================================
`state_id` -- CRACKED (identity): groups counties into their real
sub-national region/canton/province (eeu.stt's own "state" records)
============================================================================
Not a country reference (eeu.cal/eeu.cat's own country_id tops out at 34;
`state_id` reaches 690) -- a genuinely finer-grained identifier, one
level between country and county, confirmed by eeu.mod's own schema to
be a real foreign key into eeu.stt's own "state" table, and CONFIRMED
DIRECTLY in a later session (research/stt_reader.py) by opening
eeu.stt's own content: eeu.cny's 691 distinct state_id values are the
exact same SET as eeu.stt's own 691 state_id values.
Validated directly against real geography regardless: every county with
`state_id=4` is a real district of the Swiss canton VALAIS; every one
with `state_id=6` is a real district of VAUD; `state_id=8` is FRIBOURG;
`state_id=3` groups the 8 real provinces of Piedmont, Italy; `state_id
=39` groups real provinces of Liguria, Italy (Imperia, Savona). 691
distinct `state_id` values across the whole file -- plausible for ~34
countries' real regional/cantonal subdivisions (e.g. Italy alone has 20
real regions further split into ~107 provinces; Switzerland has 26
cantons with further district-level splits).

`state_id` is NOT allocated in the file's own record order (the first
few distinct values encountered, by increasing `county_id`, are 0, 39, 3,
1, 4, 2, 5, 6, ... -- not 0, 1, 2, 3, ...), consistent with it being a
real foreign key assigned by eeu.stt's own record order (CONFIRMED,
research/stt_reader.py). Records with the same `state_id` are NOT
necessarily contiguous in this file either (e.g. `state_id=39`'s two
Liguria members, Imperia and Savona, are 11 records apart, with unrelated
Swiss/other-Italian counties between them).

============================================================================
`timeinfo_id` (byte 66) -- CRACKED (identity), CONFIRMED in a later
session directly against eeu.ti's own content (research/ti_reader.py)
============================================================================
Range 1-13 across the file, heavily skewed: `1` alone covers 1,674/2,326
(72%) of all records; `3` is next-most-common (398, 17%); the rest (4, 6,
8, 5, 11, 12, 9, 10, 13, 2, 7) are rare (2-180 records each).

CONFIRMATION (later session): eeu.ti's own 17 physical records cover
exactly these same 13 distinct id values, and the 2 ids with RICH,
detailed sub-schedule data in eeu.ti (id=1 and id=3, each with 3
sub-records) are EXACTLY this file's own 2 most common ids (72% and 17%
of all counties respectively) -- an exact, non-coincidental
correspondence between "how often a profile is used" and "how much real
schedule data that profile carries." See research/ti_reader.py for the
full cross-check.

eeu.mod's own "county" schema lists `timeinfoID` as the field immediately
following `name` -- matching this byte's own position exactly. This is a
foreign key into eeu.ti's own "timeinfo" table (timezone, start year/
month/day/hour, duration, ... -- a genuine time-dependent-restriction
definition, e.g. seasonal or time-of-day access rules), which fits this
byte's own measured shape well: a small, heavily-skewed set of ids where
most counties reference a common "default" profile (`timeinfo_id=1`,
72% of records) and a minority reference a more specific one -- and
directly explains why the ORIGINAL write-up's two tested hypotheses
(direct country reference; count of child eeu.cty localities) both
failed: `timeinfo_id` isn't counting or naming anything about the county
itself, it's referencing a SHARED, county-independent time-rule catalog.
`timeinfo_id` is constant within 681/691 (98.6%) of `state_id` groups --
consistent with a real region typically sharing one time-zone/rule
profile, with a handful of real exceptions (10 groups, concentrated at
the highest `state_id` values, 679-690) plausibly reflecting a region
that genuinely spans more than one such profile.

**Confirmed** (research/ti_reader.py, later session): the exact
correspondence between eeu.cny's own id-frequency distribution and
eeu.ti's own per-id record richness closes this gap -- `timeinfo_id`
really is a genuine foreign key into eeu.ti's real "timeinfo" table, now
fully identified as a DST-rule/UTC-offset table: `timeinfo_id=1` is the
disc's Central European Time DST zone, `timeinfo_id=3` is Eastern
European Time, and every other id is one of Russia's 11 real time zones
(plus Belarus/Turkey, none of which observe DST) -- see ti_reader.py's
own docstring for the full real-world cross-reference.

============================================================================
Practical use
============================================================================
`read_cny(path)` returns every record as (county_id, state_id, name,
timeinfo_id). Combine with eeu.cal/eeu.cat (cal_reader.py/cat_reader.py)
and eeu.stt (research/stt_reader.py) for a 4-level administrative
hierarchy (country -> state -> county -> city), and with eeu.cty
(README S3.8) for the city level itself.
"""

import struct

HEADER_SIZE = 94
RECORD_SIZE = 176


def read_cny(path):
    """Decode the whole eeu.cny file. Returns a list of
    (county_id, state_id, name, timeinfo_id) tuples, one per record, in
    file order. `name` is bytes (mostly ASCII, some non-ASCII European
    characters -- decode with errors='replace' or per-locale as needed).
    Field names match eeu.mod's own real schema (mod_reader.py) --
    `state_id` is validated against real geography AND directly against
    eeu.stt's own content (stt_reader.py), `timeinfo_id` is confirmed
    directly against eeu.ti's own content (ti_reader.py) via an exact
    id-frequency correspondence (see this module's
    docstring)."""
    with open(path, "rb") as f:
        data = f.read()
    body = data[HEADER_SIZE:]
    n = len(body) // RECORD_SIZE
    records = []
    for i in range(n):
        rec = body[i * RECORD_SIZE:(i + 1) * RECORD_SIZE]
        county_id, state_id = struct.unpack_from("<HH", rec, 0)
        name = rec[30:66].split(b"\x00", 1)[0]
        timeinfo_id = rec[66]
        records.append((county_id, state_id, name, timeinfo_id))
    return records
