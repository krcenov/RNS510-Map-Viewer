"""
si_reader.py -- decodes eeu.si, CRACKED this session (record framing and
2 of 5 real data bytes; 3 bytes remain unassigned to specific named
fields). eeu.mod's own schema (research/mod_reader.py) names this table
`seginfo` -- a real road-segment classification/attribute table, 20
named leaf fields (rank, class, divided, toll_vignette, toll_road,
restclass, urban, route_num_type, paved, and more).

============================================================================
Record format -- CRACKED, validated at FULL scale (24,353 records)
============================================================================
94-byte header (record count 24,353 read straight from its own header
field, aff_reader.decode_not_compressed_header()), then exactly 24,353
fixed **8-byte** records -- validated at full scale: `24,353 * 8 =
194,824` bytes, an EXACT match to the real body size, zero leftover.

    +0    5 bytes    real per-record data, see below
    +5    3 bytes    always zero on every record checked (24,353/24,353)
                      -- unused/reserved padding, not incorrectly
                      identified (confirmed via full-file byte histogram,
                      not sampled)

All real content lives in the first 40 bits (5 bytes). Only 20,381 of the
24,353 records have a DISTINCT 5-byte payload -- 3,972 records duplicate
another record's exact value. Not treated as a dedup/unique-combination
table (that would require zero duplicates); more likely these are
allocated per some other axis (e.g. per-region/country) where the same
attribute combination legitimately recurs.

============================================================================
eeu.mod's real field list for this table
============================================================================
`seginfo` (research/mod_reader.py's `extract_blocks()`, 36 raw strings,
of which 11 are shared header-struct boilerplate present in every
eeu.mod table -- README S3.16 -- leaving these REAL leaf fields, in
file order): `rank`, `class`, `divided`, [`drivables`: `driveable_lower`,
`drivable_upper`], `toll_vignette`, `toll_road`, `tollbooth_direction`,
`hwy_complex_bit`, `restclass`, `landmark`, `dbldig`, `detailedcity`,
`urban`, `bifurcation_left`, `bifurcation_right`, `rnc`,
`truck_digitized`, [then a 2nd struct, `seginfo1`:] `route_num_type`,
`paved`. `drivables` is (by analogy with eeu.pmm's own
`type_and_listIndex` wrapper, research/postal_reader.py) almost
certainly a struct/group name wrapping its two children
(`driveable_lower`/`drivable_upper`), not itself a 21st real field --
consistent with `driveable_lower` and `drivable_upper`'s inconsistent
spelling ("driveable" vs "drivable") suggesting a single logical value
whose storage got split (low part / high part) across non-adjacent bits
when packed, a real quirk of the original compiler, not a project typo.
That leaves 20 real leaf fields total for 40 bits of real storage --
2 bits/field on average, consistent with mostly-boolean-or-small-enum
attributes.

============================================================================
CRACKED: byte 0 (bits 0-7) = rank / class / divided, in exact schema
order
============================================================================
Byte 0 splits cleanly into 3 sub-fields whose combined bit width is
exactly 8 (a whole byte), in the EXACT order eeu.mod's schema lists them
(the first 3 real leaf fields):

    bits[0:3]  rank      -- values 0-4 ONLY (5,6,7 never observed) --
                             a real, bounded 5-value enum
    bits[3:7]  class     -- values 0-12 (13,14,15 never observed) --
                             a real, bounded 13-value enum
    bit[7]     divided   -- boolean, set on 16.30% of records (3,970 /
                             24,353) -- plausible for "divided highway"
                             on a real, mostly-undivided-road network

Validated by: (a) the 3 sub-fields' combined width is exactly 1 byte with
no slack bits, (b) their order matches eeu.mod's own field order exactly,
(c) each sub-field's value RANGE is small and clean (not filling its
full bit-width, consistent with a real bounded enum rather than
arbitrary noise), (d) `divided`'s ~16% true rate and `rank`'s 5-value
spread are both realistic for a real European road network. Not
independently confirmed against ground truth (no populated cross-
reference was available -- see "eeu.rd cross-reference" below for why
the obvious cross-check doesn't work).

============================================================================
CRACKED: byte 4's low nibble (bits 32-35) = route_num_type / paved, in
exact schema order
============================================================================
Byte 4 is the last non-zero byte (values 0-14 only, confirmed the same
14 as bit 35's own 94.56%-set rate -- bit 35 is byte 4's top bit).
Splits cleanly into the LAST 2 real leaf fields in eeu.mod's own
schema order:

    bits[32:35]  route_num_type  -- values 0-6 ONLY (7 never observed)
                                     -- a real, bounded 7-value enum
    bit[35]      paved           -- boolean, set on 94.56% of records
                                     (23,029 / 24,353) -- plausible: most
                                     roads on a real European disc are
                                     paved

Same validation logic as byte 0: exact bit-width match (3+1=4 bits =
byte 4's entire real range), exact schema-order match (last 2 real
fields, last real byte), bounded/clean value ranges, and `paved`'s ~95%
true rate matches real-world expectation.

============================================================================
NOT CRACKED: bytes 1-3 (24 bits) -- 15 more named fields, no bit
assignment determined
============================================================================
`driveable_lower`, `drivable_upper`, `toll_vignette`, `toll_road`,
`tollbooth_direction`, `hwy_complex_bit`, `restclass`, `landmark`,
`dbldig`, `detailedcity`, `urban`, `bifurcation_left`,
`bifurcation_right`, `rnc`, `truck_digitized` -- 15 real fields, 24 real
bits, averaging 1.6 bits/field, consistent with mostly single-bit flags
plus a few 2-3-bit codes, but no specific bit range was assigned to any
specific name this session. One clean STRUCTURAL fact, not yet tied to a
name: byte 2's low 3 bits (bits 16-18) are always zero on every record
(every observed byte-2 value is a multiple of 8), leaving a clean 5-bit
sub-field (bits 19-23, values 0-30, 30 of 32 possible values used) --
high cardinality, more consistent with a multi-value code (`rnc`? a
restriction-class enum?) than a boolean flag, but not assigned to a
specific name. Bytes 1 and 3 show no comparably clean internal boundary.

============================================================================
eeu.rd cross-reference -- CORRECTS a previous session's lead: does NOT
hold up as a direct index
============================================================================
README S3.16 (`eeu.mod` write-up) flagged `eeu.si` as "a strong,
not-yet-pursued lead" for `eeu.rd`'s own unresolved `bytes[1:5]`
("candidate road-class flags", README S3.1). Checked directly this
session: `eeu.rd`'s `bytes[1:5]` was previously found to have only ~5
distinct patterns across the WHOLE file (README S3.1) -- far too few
to serve as a direct foreign-key index into `eeu.si`'s 20,381 distinct
records (a real FK into a table that size would need on the order of
15 bits of entropy, not ~5 discrete states). This specific cross-
reference does not hold up structurally. More likely: the real
`seginfoID` foreign key lives on the MAP_COMPRESSED tile format's own
segment records (`eeu.mod`'s "Ordinary Map File" block independently
names a `seginfoID` field there, alongside `seg`/`restr_left`/
`restr_right`/`left_node`/`right_node`/`length` -- README S3.16), not on
`eeu.rd` at all -- `eeu.rd` and the tile format are two separate
representations of the road network. Not pursued further this session
(would require reopening the tile format's own segment record parser).

============================================================================
Practical use
============================================================================
`read_si(path)` returns every record as (rank, class, divided,
route_num_type, paved, unassigned_bits). `unassigned_bits` is the raw
24-bit value of bytes[1:3] for a future session to decompose further.
"""

import struct

from research.aff_reader import decode_not_compressed_header, HEADER_SIZE

RECORD_SIZE = 8


def read_si(path):
    """Decode the whole eeu.si file. Returns a list of (rank, class,
    divided, route_num_type, paved, unassigned_bits) tuples, one per
    record, in file order. `unassigned_bits` is the raw uint32 formed
    from bytes[1:4] (24 bits) -- 15 more real fields live here (see this
    module's docstring) but no per-field bit assignment was cracked this
    session."""
    with open(path, "rb") as f:
        data = f.read()
    body = data[HEADER_SIZE:]
    n = len(body) // RECORD_SIZE
    records = []
    for i in range(n):
        rec = body[i * RECORD_SIZE:(i + 1) * RECORD_SIZE]
        b0 = rec[0]
        rank = b0 & 0b111
        klass = (b0 >> 3) & 0b1111
        divided = bool((b0 >> 7) & 1)
        b4 = rec[4]
        route_num_type = b4 & 0b111
        paved = bool((b4 >> 3) & 1)
        unassigned_bits = int.from_bytes(rec[1:4], "little")
        records.append((rank, klass, divided, route_num_type, paved,
                         unassigned_bits))
    return records
