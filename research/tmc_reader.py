"""
tmc_reader.py -- decodes eeu.tmc, CRACKED (partially): the file's own
top-level directory (a 6-byte header + 44 fixed 20-byte "location
table" summary records) is fully decoded and validated; the much larger
bulk payload (the real per-location offset tables, segment chains, and
exploration points the directory points into -- eeu.mod's own much
deeper nested schema for this table, research/mod_reader.py) is NOT
decoded.

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
NOT cracked: the bulk payload (~17.3MB, 67% of the file, past the last
table's own offset_n)
============================================================================
The last table's own `offset_n` (8,482,780) is well within the real
25,814,002-byte body, but leaves 17,331,222 bytes (67% of the file)
unaccounted for by the directory alone -- consistent with this being
where the real `location_chains`/`segment_chains`/`exploration_points`
data lives (eeu.mod's own much deeper nested schema, above), not yet
decoded. A quick look at the bytes located via `offset_p[0]`/
`offset_n[0]` shows a repeating structure with a roughly-constant
2-byte value (`0x0082`/`0x8a00`-ish) paired with a slowly, near-linearly
incrementing 2-byte value (steps of ~15) -- not decoded into named
fields.

============================================================================
Practical use
============================================================================
`read_tmc_directory(path)` returns (no_of_location_tables, field2,
field3, records) where each record is (code, start_location, no_of_
locations, offset_p, offset_n). Nothing beyond the directory is parsed.
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
    independently confirmed. Nothing past the directory (the real
    per-location payload data) is decoded."""
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
