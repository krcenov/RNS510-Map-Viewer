"""
cny_reader.py -- decodes eeu.cny, CRACKED this session (structure and
content identity fully understood; two numeric fields' exact semantics
only partially resolved): a "county" catalog -- real sub-national
administrative divisions (Italian provinces, Swiss canton districts,
Greek prefectures, ...) one level below eeu.cal's countries and one
level above eeu.cty's cities/localities. Previously entirely unexamined
-- only a candidate record size (176 bytes) had been derived from the
shared NOT_COMPRESSED header fields (aff_reader.py), not the content.

============================================================================
Record format -- CRACKED, validated at full scale (every one of 2,326
records parses cleanly, zero exceptions)
============================================================================
94-byte header (record count 2,326 comes straight from its own now-
cracked bytes[86:88] field), then exactly 2,326 fixed 176-byte records:

    +0    uint16 LE  index     -- plain ascending 0..2325, record N's own
                                   position (confirmed exact, no gaps)
    +2    uint16 LE  region_id -- CRACKED (identity, not full semantics):
                                   groups counties into real sub-national
                                   regions/cantons/provinces -- see below
    +4    bytes[26]  --  always zero on every record checked (2326/2326)
    +30   bytes[36]  name      -- NUL-padded, the county/district's real
                                   name
    +66   uint8      level     -- NOT fully cracked, see below
    +67   bytes[109] --  always zero on every record checked (2326/2326)

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
`region_id` -- CRACKED (identity): groups counties into their real
sub-national region/canton/province
============================================================================
Not a country reference (eeu.cal/eeu.cat's own country_id tops out at 34;
`region_id` reaches 690) -- a genuinely finer-grained identifier, one
level between country and county. Validated directly: every county with
`region_id=4` is a real district of the Swiss canton VALAIS; every one
with `region_id=6` is a real district of VAUD; `region_id=8` is FRIBOURG;
`region_id=3` groups the 8 real provinces of Piedmont, Italy; `region_id
=39` groups real provinces of Liguria, Italy (Imperia, Savona). 691
distinct `region_id` values across the whole file -- plausible for ~34
countries' real regional/cantonal subdivisions (e.g. Italy alone has 20
real regions further split into ~107 provinces; Switzerland has 26
cantons with further district-level splits).

`region_id` is NOT allocated in the file's own record order (the first
few distinct values encountered, by increasing `index`, are 0, 39, 3, 1,
4, 2, 5, 6, ... -- not 0, 1, 2, 3, ...), so it's an opaque id assigned
elsewhere in the source database, not a per-file sequential allocation
counter. Records with the same `region_id` are NOT necessarily
contiguous in the file either (e.g. `region_id=39`'s two Liguria members,
Imperia and Savona, are 11 records apart, with unrelated Swiss/other-
Italian counties between them) -- the file's own overall record order
looks driven by real geographic/administrative source-data clustering
that only loosely groups by region, not a strict per-region block layout.

============================================================================
`level` (byte 66) -- NOT fully cracked
============================================================================
Range 1-13 across the file, heavily skewed: `1` alone covers 1,674/2,326
(72%) of all records; `3` is next-most-common (398, 17%); the rest (4, 6,
8, 5, 11, 12, 9, 10, 13, 2, 7) are rare (2-180 records each).

**Confirmed characterized, not yet semantically explained**: `level` is
constant within 681/691 (98.6%) of `region_id` groups -- e.g. every real
Valais district (`region_id=4`) shares the same `level`, strongly tying
it to the SAME region/hierarchy concept `region_id` encodes, not an
independent per-county property. The 10 exceptions (multiple `level`
values within one `region_id` group) are concentrated at the highest
`region_id` values (679-690, near the end of the id range) and were not
investigated further this session.

**Hypotheses tested and refuted**: a direct country reference (does not
match eeu.cal/eeu.cat's 0-34 country_id range meaningfully, and the same
`level` value recurs across clearly different real countries -- e.g. both
Italian and Swiss counties commonly show `level=1`); a count of that
county's own child localities in eeu.cty (cross-referenced real `", county
name"`-suffixed eeu.cty record counts for Chania/Rethymno/Irakleio/
Imperia/Torino against their own `level` values -- 15/6/35/8/31 real
sub-locality counts vs. `level` values of 3/3/3/1/1 respectively -- no
relationship found). A plausible remaining idea, not tested: some kind of
real administrative-hierarchy DEPTH indicator, given real European
countries genuinely differ in how many admin levels exist between
"country" and "county" (e.g. Greece's nomoi vs. a Swiss canton's own
districts) -- `level=3` uniformly on the 4 (real, single-level) Greek
prefectures sampled is at least consistent with this, not proof of it.

============================================================================
Practical use
============================================================================
`read_cny(path)` returns every record as (index, region_id, name, level).
Combine with eeu.cal/eeu.cat (cal_reader.py/cat_reader.py) for a 3-level
administrative hierarchy (country -> region -> county), and with eeu.cty
(README S3.8) for the 4th level down (city/locality) -- though the exact
cross-file KEY linking a `eeu.cny` region_id back to a specific eeu.cal/
eeu.cat country_id was not recovered this session.
"""

import struct

HEADER_SIZE = 94
RECORD_SIZE = 176


def read_cny(path):
    """Decode the whole eeu.cny file. Returns a list of
    (index, region_id, name, level) tuples, one per record, in file
    order. `name` is bytes (mostly ASCII, some non-ASCII European
    characters -- decode with errors='replace' or per-locale as needed)."""
    with open(path, "rb") as f:
        data = f.read()
    body = data[HEADER_SIZE:]
    n = len(body) // RECORD_SIZE
    records = []
    for i in range(n):
        rec = body[i * RECORD_SIZE:(i + 1) * RECORD_SIZE]
        index, region_id = struct.unpack_from("<HH", rec, 0)
        name = rec[30:66].split(b"\x00", 1)[0]
        level = rec[66]
        records.append((index, region_id, name, level))
    return records
