"""
ti_reader.py -- decodes eeu.ti, CRACKED this session: the real
"timeinfo" table `eeu.cny`'s own `timeinfo_id` field points into
(`eeu.cny`'s "identity, plausible, not independently confirmed"
identification, README S3.15, is now CONFIRMED directly), and a real
Daylight Saving Time (DST) rule / UTC-offset table -- confirmed, not
just plausible, via an exhaustive real-world geography cross-check
(see "timezone" below). Previously unexamined -- only a candidate
record size (23 bytes) had been derived from the shared NOT_COMPRESSED
header fields, not the content. Small enough (17 records) to fully
hand-inspect in one pass.

============================================================================
Record format -- CRACKED (framing + 3 fields fully, 1 field positioned),
validated at FULL scale (all 17 records)
============================================================================
94-byte header (record count 17 comes straight from its own now-cracked
bytes[86:88] field), then exactly 17 fixed 23-byte records:

    +0    uint16 LE  timeinfo_id  -- CRACKED, CONFIRMED against eeu.cny:
                                      range 1-13, exactly matching
                                      eeu.cny's own timeinfo_id range
                                      (README S3.15/cny_reader.py). NOT a
                                      per-record primary key of this file
                                      -- multiple physical records can
                                      share one value (see "grouping"
                                      below). eeu.mod's real field name:
                                      `timeinfoID`.
    +2    uint16 LE  timezone     -- CRACKED (exact formula), CONFIRMED
                                      against real-world geography (see
                                      below): `utc_offset_hours =
                                      value/100 - 12`.
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
                                      durationminutes) live here. Byte
                                      POSITIONS assigned (1 byte/field,
                                      matching eeu.mod's own field order
                                      exactly, 14 bytes used + 4 reserved/
                                      always-zero trailing bytes) but
                                      several fields' exact real-world
                                      semantics were NOT independently
                                      confirmed -- see "record shapes"
                                      below.

============================================================================
`timezone` -- CRACKED, CONFIRMED against real-world geography (a UTC
offset, not an opaque catalog index as first guessed)
============================================================================
`utc_offset_hours = timezone_field/100 - 12` -- validated EXHAUSTIVELY
against real Russian federal-district geography, which this disc's own
data happens to span all 11 of Russia's real UTC offsets:

    timeinfo_id  timezone  implied UTC   real eeu.stt states (Russia)
    2            1400      UTC+2         Severo-Zapadniy (NW) -- Kaliningrad's own zone, real
    4            1500      UTC+3         Tsentralniy/Privolzhskiy/... -- Moscow Time, real
    5            1600      UTC+4         Privolzhskiy/Yuzhniy -- real
    6            1700      UTC+5         Privolzhskiy/Uralskiy -- real (Yekaterinburg)
    7            1800      UTC+6         Sibirskiy -- real
    8            1900      UTC+7         Sibirskiy -- real (Novosibirsk/Krasnoyarsk)
    9            2000      UTC+8         Sibirskiy -- real (Irkutsk)
    10           2100      UTC+9         Sibirskiy/Dalnevostochniy -- real (Yakutsk)
    11           2200      UTC+10        Dalnevostochniy -- real (Vladivostok)
    12           2300      UTC+11        Dalnevostochniy -- real (Magadan/Sakhalin)
    13           2400      UTC+12        Dalnevostochniy -- real (Kamchatka)

Every single one of Russia's 11 real time zones, west to east, is
represented exactly once, at exactly the right UTC offset by this
formula, with zero exceptions or reordering. This is not a coincidence:
`timeinfo_id=4` is also shared with Belarus and Turkey (both real UTC+3,
Moscow-aligned), and `timeinfo_id`s 2/5/6/7/8/9/10/11/12/13 are
exclusively Russia -- see "the id/country correspondence" below for the
full real-country cross-reference this rests on.

Also confirmed for the disc's 2 DST-observing zones: `timeinfo_id=1`
(the Central European Time zone, see below) has `timezone=1300` ->
UTC+1, the real standard-time offset of CET (Germany, Italy, Poland,
Switzerland, ...). `timeinfo_id=3` (Eastern European Time) has
`timezone=1400` -> UTC+2, EET's real standard-time offset (Greece,
Romania, Finland, ...). Both exactly correct.

============================================================================
The id/country correspondence -- CRACKED (real-world cross-reference,
research/cny_reader.py + research/stt_reader.py + eeu.ctr)
============================================================================
Joining eeu.cny -> eeu.stt -> eeu.ctr for every county on the disc:

  timeinfo_id=1  (72% of all counties, 3-entry "rich" group): every
      real Central European Time country on the disc -- Germany, Italy,
      Poland, Switzerland, Austria, Czechia, Slovakia, Hungary,
      Bosnia, Montenegro, Croatia, Kosovo, North Macedonia, Serbia,
      Albania, Denmark, Norway, Sweden, Vatican City, San Marino,
      Liechtenstein.

  timeinfo_id=3  (17% of all counties, 3-entry "rich" group): every
      real Eastern European Time country on the disc -- Bulgaria,
      Estonia, Greece, Latvia, Lithuania, Moldova, Romania, Finland,
      Ukraine.

  timeinfo_id=2,5,6,7,8,9,10,11,12,13  (Russia only, 1-entry "simple"
      groups each): Russia's own 11 real federal districts/time zones
      -- see the `timezone` table above.

  timeinfo_id=4  (1-entry "simple" group): Russia (Moscow Time zone) +
      Belarus + Turkey.

**This is a fully real-world-grounded, non-coincidental explanation for
the whole file's structure**: the 2 timeinfo_id values with detailed
2-real-rule DST sub-schedules are EXACTLY the disc's 2 real DST-
observing zones (CET, EET); every timeinfo_id with just a single
"no schedule" default record is EXACTLY a country/region that does NOT
observe DST in real life -- Russia abolished DST permanently in 2014,
Belarus does not observe DST, and Turkey abolished DST in 2016 (this
disc's own version strings date it to 2019, consistent with all three
already being DST-free by build time).

============================================================================
Grouping -- CRACKED: timeinfo_id is a real one-to-many key, not a
per-record primary key
============================================================================
17 physical records cover only 13 distinct timeinfo_id values:
timeinfo_id=1 has 3 sub-records (seqnr 0, 1, 2); timeinfo_id=3 has 3
sub-records (seqnr 0, 1, 2); every other value (2, 4, 5, 6, 7, 8, 9, 10,
11, 12, 13) has exactly 1 sub-record each (3 + 3 + 11*1 = 17, exact).
`timezone` (bytes[2:4]) is CONSTANT within each group.

============================================================================
Cross-validated EXACTLY against eeu.cny's own timeinfo_id distribution
============================================================================
The 2 timeinfo_id values with rich 3-sub-record groups here (1 and 3)
are EXACTLY the 2 most common values in eeu.cny's own timeinfo_id field
(cny_reader.py): id=1 covers 1,674/2,326 counties (72%), id=3 covers
398/2,326 (17%) -- together 89% of every county on the disc.

============================================================================
Record shapes -- byte POSITIONS assigned (1 field = 1 byte, matching
eeu.mod's own field order and the tail's exact 14-real-bytes-of-18
width), exact real-world SEMANTICS not independently confirmed for
every field
============================================================================
Every record's bytes[5:23] falls into one of 3 clean shapes, given
14 named fields mapped 1:1 onto bytes[5:19] (typeofentry through
durationminutes, in eeu.mod's own order) with bytes[19:23] always zero
(reserved/padding):

  "Real entry" shape (4 records: both seqnr=0/seqnr=1 records in each
  rich group): typeofentry=121 (0x79, constant); startyear=77
  (constant, plausibly a reference/epoch year rather than a real
  calendar year, since a recurring annual rule doesn't need one);
  monthorweek=108 (0x6c, constant across BOTH rich groups -- consistent
  with CET and EET sharing the same real-world transition CALENDAR DATE,
  last Sunday of March/October, differing only in local clock hour);
  flcount=0; startday=0; starthour=3 (seqnr=0, "spring forward") or 10
  (seqnr=1, "fall back") -- NOT independently confirmed to mean literal
  local clock hour (the real EU-wide DST rule transitions at 01:00 UTC,
  and CET/EET should differ from each other by 1 local hour, but both
  show starthour=3 here -- possibly this field is UTC-referenced, or the
  1-byte-per-field position assignment is off by one field for this
  specific byte); startminute=1; durationnegative=0; durationyears=1
  (seqnr=0) growing to match durationmonths; durationmonths=2 (id=1,
  seqnr=0), 3 (id=1 seqnr=1 / id=3 seqnr=0), 4 (id=3, seqnr=1) --
  monotonic across sub-entries; durationweeks=0; durationdays=0
  (seqnr=0) or 1 (seqnr=1); durationhours=0; durationminutes=8
  (constant). The "duration" fields' literal numeric shape (~1 year,
  ~8 minutes) does not obviously match a real 1-hour DST clock shift,
  so these may encode a rule VALIDITY window (how long this specific
  rule version applies) rather than the shift amount itself -- not
  resolved.

  "Simple default" shape (11 singleton records, one per non-DST
  region): every byte identical across all 11 --
  `79 4d 64 00 00 03 00 00 00 00 00 00 00 00 00 00 00 00` -- i.e.
  typeofentry=121, startyear=77, monthorweek=100 (0x64, DIFFERENT from
  the DST zones' 108 -- consistent with "no real transition month"),
  starthour=3, everything else 0 (no real DST duration data, as
  expected for a region without DST).

  "Terminator" shape (the 2 seqnr=2 records, one per rich group):
  typeofentry=42 (0x2a), every other byte zero -- consistent with a
  list-terminator or explicit "2 real entries" count marker, not
  independently confirmed.

============================================================================
Practical use
============================================================================
`read_ti(path)` returns every record as (timeinfo_id, timezone, seqnr,
tail_bytes). `utc_offset(timezone_field)` applies the cracked formula.
`tail_bytes` is the raw 18-byte region covering `typeofentry` through
the reserved trailing bytes, for a future session to pin down the exact
day/hour semantics.
"""

import struct

HEADER_SIZE = 94
RECORD_SIZE = 23


def read_ti(path):
    """Decode the whole eeu.ti file. Returns a list of
    (timeinfo_id, timezone, seqnr, tail_bytes) tuples, one per record, in
    file order. `timezone` is the raw uint16 at bytes[2:4] -- apply
    utc_offset() to get the real UTC offset in hours. `tail_bytes` is
    bytes[5:23] (18 bytes covering 14 more named fields -- see this
    module's docstring for the byte-position mapping)."""
    with open(path, "rb") as f:
        data = f.read()
    body = data[HEADER_SIZE:]
    n = len(body) // RECORD_SIZE
    records = []
    for i in range(n):
        rec = body[i * RECORD_SIZE:(i + 1) * RECORD_SIZE]
        timeinfo_id, timezone = struct.unpack_from("<HH", rec, 0)
        seqnr = rec[4]
        tail_bytes = rec[5:23]
        records.append((timeinfo_id, timezone, seqnr, tail_bytes))
    return records


def utc_offset(timezone_field):
    """The cracked timezone formula: UTC offset in hours, validated
    exhaustively against Russia's own real 11 time zones and CET/EET's
    real standard-time offsets (see this module's docstring)."""
    return timezone_field / 100 - 12
