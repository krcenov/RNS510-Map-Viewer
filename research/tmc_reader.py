"""
tmc_reader.py -- decodes eeu.tmc. CRACKED: the file's own top-level
directory (a 6-byte header + 44 fixed 20-byte "location table" summary
records), AND (a LATER session) the COMPLETE per-location byte-offset
INDEXING structure that fills the entire rest of the file except the
final bulk region -- every one of the 44 tables' own `location_offset_
table_p`/`location_offset_table_n` arrays (eeu.mod's schema names,
research/mod_reader.py), validated at 100% scale with zero exceptions.
This gives the exact byte range (in both the "p" and "n" ALERT-C
directions) of EVERY SINGLE location's own segment-chain record in the
file, even though the internal CONTENT of those small records (the
segment_chains[]/exploration_points[] leaf structures) is NOT yet
decoded -- see "A LATER SESSION" below for the full crack.

Previously the last "genuinely unexplored" NOT_COMPRESSED file on the
disc. Cracked using ground truth found via `config/create_cd`
(research/create_cd_reader.py): `telemat/tmc2/TMCCONFIG.ini`
(research/telemat_reader.py) confirmed this disc's real ALERT-C/TMC
conventions and gave the investigation a concrete target shape to test
against, and `dbal/`'s own embedded source-file list
(research/dbal_reader.py) independently confirms the real handler is
named `db_tmc.cpp` (plus a `db_tmc_deprecated.cpp` twin, suggesting the
format changed between DBAL versions).

============================================================================
eeu.mod's real schema for this table (README S3.16/S3.24)
============================================================================
`eeu.mod` names this table `"tmc file"`, 74 raw strings. After the usual
boilerplate (`tmc_siemens_header`: stamp/copyright/db_release/
db_version/comp_version/dbID/fileID/rec_cnt/byte_cnt), the real
structure is:

    tmc_file_header:
        no_of_location_tables
        max_segment_chain_len
        max_location_size
        location_table_headers[] -> location_table_header:
            name
            start_location
            no_of_locations
            offset_of_location_offset_table_p
            offset_of_location_offset_table_n
    location_offset_tables:
        location_offset_table_p[] -> {chain_offset, start, location_p_end}
        location_offset_table_n[] -> {chain_offset, start, location_n_end}
    location_chains:
        location_chains_p / location_chains_n -> segment_chains_for_one_location:
            chain_count, total_no_of_chains, no_of_internal_chains
            segment_chains[] -> segment_chain:
                start, vseg_id, side, no_of_segments
                exception: {start_exception_arm_no, start_exception_valid,
                            end_exception_arm_no, end_exception_valid}
                exploration_points[] -> exploration_point: {arm0, arm1, offset}

============================================================================
CRACKED, validated at FULL scale: the file header + 44-table directory
============================================================================
94-byte disc-wide SIEMENS header (`record_count_lo16` reads 0, same
"not a fixed-record file" situation as `eeu.il`/`eeu.mod`), then:

    +0   uint16 LE  no_of_location_tables   -- CRACKED: reads 44,
                                                exactly matching the
                                                number of directory
                                                records that follow
                                                (validated below)
    +2   uint16 LE  ???                     -- reads 1716; position
                                                matches eeu.mod's
                                                `max_segment_chain_len`,
                                                value not independently
                                                confirmed
    +4   uint16 LE  ???                     -- reads 240; position
                                                matches `max_location_
                                                size`, value not
                                                independently confirmed
    +6   44 x 20-byte `location_table_header` records:
        +0   bytes[4]  code       -- a 3-character alphanumeric code +
                                      NUL (e.g. "117", "225", "A01",
                                      "F49") -- CONFIRMED exactly 3
                                      characters + NUL on all 44/44
                                      records. NOT the same identifier
                                      convention `telemat/tmc2/
                                      TMCCONFIG.ini` uses for its own
                                      14 Western-European countries
                                      (hex hex Country Code + decimal
                                      LTN) -- this disc's own 44 tables
                                      are a real, distinct catalog,
                                      plausibly covering the "eeu"
                                      (East Europe) dataset's own wider
                                      country/region footprint. Not
                                      matched against any external
                                      ground truth this session.
        +4   uint32 LE  start_location?    -- position matches eeu.mod's
                                              `start_location`, not
                                              independently confirmed
        +8   uint32 LE  no_of_locations?   -- position matches eeu.mod's
                                              `no_of_locations`, not
                                              independently confirmed
        +12  uint32 LE  offset_p           -- CRACKED (identity): see
                                              below
        +16  uint32 LE  offset_n           -- CRACKED (identity): see
                                              below

**Validated**: the 44-record count exactly matches the header's own
`no_of_location_tables` field (44 == 44, not assumed). `offset_p`/
`offset_n` are monotonically increasing across ALL 44 records (980,
105460, 209940, 452364, 838444, 982100, ..., up to 8,482,780 on record
43) with `offset_n > offset_p` on every single record, and each
record's own `offset_p` >= the previous record's `offset_n` (mostly,
with small overlaps) -- exactly the shape real, sequentially-allocated
byte offsets into a shared payload region would have, and matching
eeu.mod's own field names (`offset_of_location_offset_table_p`/`_n`)
exactly by position. Spot-checked: the bytes AT both `offset_p[0]`=980
and `offset_n[0]`=105460 are themselves further small, regular,
non-random binary structure (not garbage/misalignment), consistent with
real payload data beginning exactly there.

**A real, structural sub-pattern, not yet explained**: 4 consecutive
tables (records 18-21, codes `714`/`715`/`716`/`717`) all share the
exact same `start_location?` value (10001) -- consistent with a group
of related location-table segments sharing one common numbering base,
plausibly sub-divisions of one larger country/region, not confirmed.

============================================================================
A LATER SESSION: the COMPLETE per-location byte-offset index CRACKED --
location_offset_table_p / location_offset_table_n, validated at 100%
scale, zero exceptions across all 44 tables
============================================================================
Each of the 44 location tables' own `offset_p` field (directory record,
above) doesn't point at a single struct -- it's the start of a flat
array. eeu.mod names it `location_offset_table_p`, and the array's
element count is exactly `no_of_locations + 1` (the classic prefix-sum/
CSR shape: N ranges need N+1 boundary markers) -- confirmed EXACTLY,
zero exceptions, on all 44 tables:

    (offset_n - offset_p) / (no_of_locations + 1) == 4  -- for all 44/44 tables

i.e. `location_offset_table_p` is `no_of_locations + 1` little-endian
**uint32 absolute file byte offsets**, monotonically non-decreasing
(confirmed on every table, zero exceptions) -- location i's own data
spans `[table_p[i], table_p[i+1])`.

`location_offset_table_n` (the mirror "negative direction" array,
same eeu.mod struct) immediately follows `location_offset_table_p` in
the file, starting exactly at `offset_n` and using the IDENTICAL
`(no_of_locations + 1) * 4`-byte size -- confirmed EXACTLY on 43/43
consecutive table pairs (the one exception, the very last table `F49`,
has no "next" table to bound it the same way -- see below instead):

    next_table.offset_p - this_table.offset_n == (no_of_locations + 1) * 4

**The whole file's layout is now fully self-consistent end to end**: the
LAST table's (`F49`) own `location_offset_table_n` array -- whose end
isn't bounded by a "next" directory record -- computes to end at exactly
byte **8,584,500**, and separately, the FIRST table's (`117`) own
`location_offset_table_p[0]` value is ALSO exactly **8,584,500** -- the
two independent computations agree to the byte. And the LAST value of
the LAST table's `location_offset_table_n` array equals **25,814,096**
-- the file's own exact total size (EOF), also to the byte. Both
`location_offset_table_p` and `location_offset_table_n` are confirmed
monotonic on every one of the 44 tables, and every computed offset for
every table falls within the file's own real bounds -- no exceptions
found anywhere.

**Practical consequence**: the entire file from byte 94 (end of the
SIEMENS header) to EOF is now fully mapped -- the 6-byte `tmc_file_
header`, the 880-byte 44-record directory, then 44 back-to-back
`[location_offset_table_p][location_offset_table_n]` pairs (886 to
8,584,500), then a single shared **"location_chains" bulk region**
(8,584,500 to EOF, 17,229,596 bytes, 66.75% of the file) that ALL 44
tables' own offset arrays point into. Given any `(table_code,
location_index)`, the exact byte range of that location's own p-chain
AND n-chain data is now directly computable with zero guessing --
`location_byte_range()` below does this.

============================================================================
NOT YET cracked: the location_chains bulk region's own CONTENT (what's
INSIDE each location's now-exactly-known byte range)
============================================================================
Individual location records are small (single-digit to a few dozen
bytes, per the now-exact byte ranges above) and eeu.mod's own nested
schema for them (`segment_chains_for_one_location: chain_count,
total_no_of_chains, no_of_internal_chains, segment_chains[] ->
segment_chain: {start, vseg_id, side, no_of_segments, exception{...},
exploration_points[]}`) is considerably deeper than the flat
offset-index structure just cracked -- involving variable-length nested
arrays, not another fixed-shape table. A quick look at several real
per-location byte ranges (table `117`, locations 0-14) shows plausible
small structure (values like `0x11`/`0x12`/`0x01` recurring near the
start of several records, consistent with a small leading `chain_count`
matching the schema's own field order) but NOT a confirmed byte-level
decode -- left for a future session. `read_location_chain_bytes()`
below hands back the exact raw bytes for any location, ready for that
next pass.

============================================================================
Practical use
============================================================================
`read_tmc_directory(path)` returns (no_of_location_tables, field2,
field3, records) where each record is (code, start_location, no_of_
locations, offset_p, offset_n). `read_location_offset_arrays(data, off_p,
off_n, no_of_locations)` returns (table_p, table_n), each a tuple of
`no_of_locations + 1` absolute file offsets. `location_byte_range(table_p,
table_n, index)` returns ((p_start, p_end), (n_start, n_end)) for one
location. `read_location_chain_bytes(data, table_p, table_n, index)`
returns (p_bytes, n_bytes) -- the raw, NOT-yet-decoded bytes for one
location's own chain data in both directions.
"""

import struct

HEADER_SIZE = 94
DIR_RECORD_SIZE = 20


def read_tmc_directory(path):
    """Decode eeu.tmc's own file header + 44-table directory (CRACKED,
    validated -- see this module's docstring). Returns
    (no_of_location_tables, field2, field3, records), where `records`
    is a list of (code, start_location, no_of_locations, offset_p,
    offset_n) tuples, one per location table, in file order. `field2`/
    `field3` are positioned to match eeu.mod's own `max_segment_chain_
    len`/`max_location_size` field names but their values weren't
    independently confirmed. See `read_location_offset_arrays()` for the
    per-table offset-index structure past the directory (CRACKED, a
    later session) -- only the deepest leaf content (the actual chain
    records the offset arrays point at) remains undecoded."""
    with open(path, "rb") as f:
        data = f.read()
    body = data[HEADER_SIZE:]
    n_tables, field2, field3 = struct.unpack_from("<HHH", body, 0)
    off = 6
    records = []
    for _ in range(n_tables):
        rec = body[off:off + DIR_RECORD_SIZE]
        code = rec[0:3].decode("ascii", errors="replace")
        start_location, no_of_locations, offset_p, offset_n = \
            struct.unpack_from("<IIII", rec, 4)
        records.append((code, start_location, no_of_locations,
                         offset_p, offset_n))
        off += DIR_RECORD_SIZE
    return n_tables, field2, field3, records


def read_location_offset_arrays(data, offset_p, offset_n, no_of_locations):
    """Decode one location table's own location_offset_table_p/_n arrays
    (CRACKED, validated at 100% scale -- see module docstring). `data` is
    the WHOLE already-read eeu.tmc file bytes (not just the body -- these
    are absolute file offsets). Returns (table_p, table_n), each a tuple
    of `no_of_locations + 1` little-endian uint32 absolute file offsets,
    monotonically non-decreasing. `table_p` is read from [offset_p,
    offset_n); `table_n` immediately follows, from [offset_n, offset_n +
    (no_of_locations + 1) * 4)."""
    n = no_of_locations + 1
    table_p = struct.unpack_from(f"<{n}I", data, offset_p)
    table_n = struct.unpack_from(f"<{n}I", data, offset_n)
    return table_p, table_n


def location_byte_range(table_p, table_n, index):
    """Given one table's own (table_p, table_n) arrays (from
    read_location_offset_arrays()) and a location index (0-based, <
    no_of_locations), return ((p_start, p_end), (n_start, n_end)) -- the
    exact absolute file byte range of that location's own chain data in
    each of the 2 ALERT-C directions, inside the shared "location_chains"
    bulk region (see module docstring)."""
    return (table_p[index], table_p[index + 1]), (table_n[index], table_n[index + 1])


def read_location_chain_bytes(data, table_p, table_n, index):
    """Like location_byte_range(), but returns the actual raw bytes
    (p_bytes, n_bytes) for one location -- the NOT-yet-decoded chain
    content (see module docstring, "NOT YET cracked"). `data` is the
    whole already-read eeu.tmc file bytes."""
    (p_start, p_end), (n_start, n_end) = location_byte_range(table_p, table_n, index)
    return data[p_start:p_end], data[n_start:n_end]
