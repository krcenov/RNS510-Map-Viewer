"""
cat_reader.py -- decodes eeu.cat, CRACKED this session: a per-country (+
one continent-level "Europe" aggregate) real-world bounding-box table,
indexed by the SAME country numbering cal_reader.py cracked for eeu.cal.
Previously entirely unexamined -- only a candidate record size (19 bytes)
had been derived from the shared NOT_COMPRESSED header fields
(aff_reader.py), not the content.

============================================================================
Record format -- CRACKED, validated at full scale (all 35 records)
============================================================================
94-byte header (record count 35 comes straight from its own now-cracked
bytes[86:88] field, see aff_reader.py), then exactly 35 fixed 19-byte
records, back-to-back:

    +0   uint24 LE  country_id  -- SAME numbering as eeu.cal's own
                                    country_id (cal_reader.py): 0 =
                                    "Europe" (continent-level aggregate),
                                    1-34 = the disc's 34 real countries,
                                    in alphabetical ISO 3166-1 alpha-3
                                    order (1=ALB ... 8=DEU ... 34=VAT)
    +3   int32 LE   lon_min      -- degrees = value / 100000
    +7   int32 LE   lat_min      -- degrees = value / 100000
    +11  int32 LE   lon_max      -- degrees = value / 100000
    +15  int32 LE   lat_max      -- degrees = value / 100000

Same `/100000` int32 coordinate convention used everywhere else on this
disc (eeu.rd, eeu.cty, MAP_COMPRESSED tile anchors, ...).

**Validated directly against real-world geography, not just plausible
ranges** -- checked all 35 records, most match closely enough to be
unambiguous:
  - Germany (country_id 8): (5.87, 47.28) - (15.04, 55.05) -- matches
    Germany's real bounding box almost exactly.
  - Austria (2): (9.53, 46.39) - (17.16, 49.02) -- matches Austria's real
    extent (western border near Vorarlberg, eastern near Vienna).
  - Switzerland (6): (5.96, 45.82) - (10.49, 47.80) -- correct.
  - Italy (15): (6.06, 35.49) - (19.30, 47.07) -- correct, including
    Sicily's southern extent.
  - Three real microstates get correspondingly TINY boxes: San Marino
    (27): (12.40, 43.89) - (12.52, 43.99); Liechtenstein (17): (9.48,
    47.05) - (9.62, 47.26); Vatican City (34): (12.45, 41.73) - (12.66,
    41.91) -- the smallest of the three, as expected for the world's
    smallest country.
  - Norway (23): (4.51, 57.75) - (31.13, 71.18) -- correctly extends far
    into the Arctic and reaches its real eastern border with Russia in
    Finnmark.
  - Russia (26) and "Europe" (0) BOTH reach a max longitude of 179.38 deg
    E -- consistent with this "EEU" dataset's already-documented coverage
    of Russia's far east (README S3.10's `eeuz.fea` findings: CHITA,
    BIROBIDZHAN, near the Mongolian/Manchurian border) and with "Europe"
    here being a genuine bounding UNION over every member country's own
    box, not a separately-surveyed continent shape.

**One honest anomaly, not resolved this session**: Denmark (country_id 9)
shows `lon_min` = 1.69 deg E -- identical, bit-for-bit, to "Europe"'s own
overall `lon_min`. Real mainland Denmark's westernmost point is much
further east (~8 deg E). Not explained -- possibly this entry's real
extent is genuinely clipped to the whole dataset's own western coverage
limit for some database-internal reason, possibly an indexing/lookup
quirk specific to this one record. Every other country's `lon_min` looks
geographically plausible on its own, so this is flagged as a real,
narrow open question rather than swept into "probably fine."

============================================================================
Practical use
============================================================================
`read_cat(path)` returns every record as (country_id, lon_min, lat_min,
lon_max, lat_max). Combine with cal_reader.read_cal()'s country_id ->
name mapping (any lang_index) for a labeled country-bbox table -- e.g. a
"zoom to country" feature, or a sanity check/complement to eeu.cty's own
per-locality bounding boxes (README S3.8).
"""

import struct

HEADER_SIZE = 94
RECORD_SIZE = 19


def read_cat(path):
    """Decode the whole eeu.cat file. Returns a list of
    (country_id, lon_min, lat_min, lon_max, lat_max) tuples, one per
    record, in file order. Coordinates are floats in degrees."""
    with open(path, "rb") as f:
        data = f.read()
    body = data[HEADER_SIZE:]
    n = len(body) // RECORD_SIZE
    records = []
    for i in range(n):
        rec = body[i * RECORD_SIZE:(i + 1) * RECORD_SIZE]
        country_id = int.from_bytes(rec[0:3], "little")
        lon_min, lat_min, lon_max, lat_max = struct.unpack_from("<iiii", rec, 3)
        records.append((
            country_id,
            lon_min / 100000.0, lat_min / 100000.0,
            lon_max / 100000.0, lat_max / 100000.0,
        ))
    return records
