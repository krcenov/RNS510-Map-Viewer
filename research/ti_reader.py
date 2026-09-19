"""
ti_reader.py -- decodes eeu.ti, CRACKED (partially) this session: the
real "timeinfo" table `eeu.cny`'s own `timeinfo_id` field points into
(`eeu.cny`'s "identity, plausible, not independently confirmed"
identification, README S3.15, is now CONFIRMED directly). Plausibly a
Daylight Saving Time (DST) transition-rule table, based on the schema's
own field names and this file's own structural pattern (see below) --
not verified byte-by-byte against outside ground truth. Previously
unexamined -- only a candidate record size (23 bytes) had been derived
from the shared NOT_COMPRESSED header fields, not the content. Small
enough (17 records) to fully hand-inspect in one pass.

============================================================================
Record format -- CRACKED (framing + 2 fields), validated at FULL scale
(all 17 records)
============================================================================
94-byte header (record count 17 comes straight from its own now-cracked
bytes[86:88] field), then exactly 17 fixed 23-byte records:

    +0    uint16 LE  timeinfo_id  -- CRACKED, CONFIRMED against eeu.cny:
                                      range 1-13, exactly matching
                                      eeu.cny's own timeinfo_id range
                                      (README S3.15/cny_reader.py) -- see
                                      below for the exact-count
                                      cross-validation. NOT a per-record
                                      primary key of this file -- multiple
                                      physical records can share one
                                      value (see "grouping" below).
                                      eeu.mod's real field name:
                                      `timeinfoID`.
    +2    uint16 LE  ???           -- eeu.mod's real field name:
                                      `timezone`, position CRACKED (2
                                      bytes, right after timeinfo_id, no
                                      slack), MEANING NOT cracked: values
                                      (1300, 1400, 1400, 1500, 1600, ...,
                                      2400) step by ~100 per group rather
                                      than resembling a real UTC-offset
                                      timezone value -- more likely an
                                      internal catalog index/offset than
                                      a literal timezone, not resolved
                                      this session.
    +4    uint8      seqnr         -- CRACKED (identity): a clean 0, 1, 2
                                      sub-entry counter WITHIN one
                                      timeinfo_id group (see "grouping"
                                      below) -- matches eeu.mod's own
                                      field order exactly (right after
                                      `timezone`).
    +5    bytes[18]  ???           -- 14 more named fields (typeofentry,
                                      startyear, monthorweek, flcount,
                                      startday, starthour, startminute,
                                      durationnegative, durationyears,
                                      durationmonths, durationweeks,
                                      durationdays, durationhours,
                                      durationminutes) live here (18 real
                                      bytes for 14 fields, mostly 1-byte).
                                      NOT decomposed into individual named
                                      fields this session -- see "record
                                      shapes" below for what IS
                                      established about this region.

============================================================================
Grouping -- CRACKED: timeinfo_id is a real one-to-many key, not a
per-record primary key
============================================================================
17 physical records cover only 13 distinct timeinfo_id values:
timeinfo_id=1 has 3 sub-records (seqnr 0, 1, 2); timeinfo_id=3 has 3
sub-records (seqnr 0, 1, 2); every other value (2, 4, 5, 6, 7, 8, 9, 10,
11, 12, 13) has exactly 1 sub-record each (3 + 3 + 11*1 = 17, exact).
`timezone` (bytes[2:4]) is CONSTANT within each group (both id=1's and
id=3's 3 sub-records share one value each) -- consistent with it being a
real per-group attribute, not a per-sub-entry one.

============================================================================
Cross-validated EXACTLY against eeu.cny's own timeinfo_id distribution
============================================================================
The 2 timeinfo_id values with rich 3-sub-record groups here (1 and 3)
are EXACTLY the 2 most common values in eeu.cny's own timeinfo_id field
(cny_reader.py): id=1 covers 1,674/2,326 counties (72%), id=3 covers
398/2,326 (17%) -- together 89% of every county on the disc. Every OTHER
id here (2, 4-13, each with just 1 simple sub-record) matches eeu.cny's
own much rarer counts for those same ids (2-180 counties each). This is
an exact, non-coincidental correspondence: the two heavily-used
"default" time-info profiles are exactly the two with real, detailed
sub-schedule data; the rare, edge-case profiles are simple one-record
defaults. This closes the loop `eeu.cny`'s own write-up left open --
`timeinfo_id` really is a genuine foreign key into this real,
independently-verifiable table, not a guess.

============================================================================
Record shapes -- CRACKED (structural pattern), NOT decomposed into named
fields
============================================================================
Every record's bytes[5:23] falls into one of 2 clean shapes:

  "Real entry" shape (14/17 records: both seqnr=0 records, both seqnr=1
  records, and all 11 singleton records): byte[5] = 0x79 (121) constant.
  The singleton records additionally share an IDENTICAL 18-byte tail
  (`79 4d 64 00 00 03 00 00 00 00 00 00 00 00 00 00 00 00`) on every one
  of the 11 -- i.e. every rare/simple timeinfo_id profile carries the
  EXACT SAME "no extra schedule" default payload, differing from each
  other only in `timeinfo_id` and `timezone`.

  "Terminator" shape (the 2 seqnr=2 records, one per rich group):
  byte[5] = 0x2a (42), every other byte in bytes[5:23] is zero. Distinct
  from the "real entry" shape's own byte[5] value -- consistent with a
  list-terminator or explicit "2 real entries" count marker, not
  independently confirmed.

**Plausible (untested) interpretation, based on the schema's own field
names**: `eeu.ti` is a real Daylight Saving Time (DST) transition-rule
table. The field list (`startyear`/`monthorweek`/`startday`/`starthour`/
`startminute` = when a transition happens; `durationnegative`/
`durationyears`/.../`durationminutes` = how far the clock shifts, and in
which direction) matches the classic shape of a DST rule (e.g. POSIX TZ
rules or Windows `TIME_ZONE_INFORMATION`, which also encode transition
dates as day-of-week + week-of-month). A real DST profile needs exactly
2 rules -- "spring forward" and "fall back" -- which is EXACTLY the
seqnr=0/seqnr=1 pair found in both rich groups here, with seqnr=2 as a
count/terminator record. Not verified byte-by-byte; the "real entry" tail
bytes (typeofentry through durationminutes) were not decomposed into
individual fields this session.

============================================================================
Practical use
============================================================================
`read_ti(path)` returns every record as (timeinfo_id, unknown_field,
seqnr, tail_bytes). `tail_bytes` is the raw 18-byte region covering
`typeofentry` through `durationminutes` for a future session to decode
further.
"""

import struct

HEADER_SIZE = 94
RECORD_SIZE = 23


def read_ti(path):
    """Decode the whole eeu.ti file. Returns a list of
    (timeinfo_id, unknown_field, seqnr, tail_bytes) tuples, one per
    record, in file order. `unknown_field` is the raw uint16 at
    bytes[2:4] (eeu.mod's real name: `timezone`, meaning not cracked).
    `tail_bytes` is bytes[5:23] (18 bytes covering 14 more named fields,
    not decomposed -- see this module's docstring)."""
    with open(path, "rb") as f:
        data = f.read()
    body = data[HEADER_SIZE:]
    n = len(body) // RECORD_SIZE
    records = []
    for i in range(n):
        rec = body[i * RECORD_SIZE:(i + 1) * RECORD_SIZE]
        timeinfo_id, unknown_field = struct.unpack_from("<HH", rec, 0)
        seqnr = rec[4]
        tail_bytes = rec[5:23]
        records.append((timeinfo_id, unknown_field, seqnr, tail_bytes))
    return records
