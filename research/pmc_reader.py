"""
pmc_reader.py -- decodes eeu.pmc, CRACKED this session: fixed 4-byte
(uint32 LE) records, and on this disc every single record's value is
exactly equal to its own 0-based index -- a pure identity array, not
real postal-code data. eeu.mod's own schema (research/mod_reader.py)
names this table `postalcodeListMergeCity` (13 fields); `files.cfg`
calls it the "postalcode merge city file". eeu.pmm (schema name
`postalcodeListSeparate`, files.cfg "postalcode merge separator file")
is BYTE-IDENTICAL in body content to eeu.pmc -- same 4,084,104-entry
identity array -- confirmed by direct comparison; only the 94-byte
header's `file_type` byte (63 vs. 64) differs between the two files.

============================================================================
Record format -- CRACKED, validated at FULL scale (every one of
4,084,104 records)
============================================================================
94-byte header, then fixed 4-byte records:

    +0   uint32 LE   value   -- on this disc: value == record's own
                                 0-based index, for every record, no
                                 exceptions (see below)

Real record count is 4,084,104 -- NOT derivable from the header's own
`record_count_lo16` field (aff_reader.decode_not_compressed_header())
using the small wraparound multiples (`record_count_lo16 + 65536*k` for
k=0..4) tried in the original unexamined-files pass (README S3 "Worth
investigating first" / wiki Unexamined-Files.md), which is why this file
was flagged "not clean at k=0..4" there. The real count needs **k=62**:
`20,872 + 65,536*62 = 4,084,104`, and `4,084,104 * 4 = 16,336,416` bytes
-- an EXACT match to this file's own real body size, and to eeu.mod's
own total_size field. Confirmed independently at both ends: parsing
16,336,416 bytes as 4-byte records consumes the entire body with zero
leftover, AND the last record's value (4,084,103, hex `3e5187`) is
byte-for-byte what the tail of the file actually contains.

============================================================================
The content -- CRACKED (identity function): confirms this whole
postal-code subsystem is unpopulated on this disc, not that this file's
format is somehow unusual
============================================================================
Every one of the 4,084,104 records, checked exhaustively (not sampled),
satisfies `value == index`: 0, 1, 2, 3, ..., 4084103, with ZERO
deviation anywhere in the file. A real "merge" table -- even a mostly-
trivial one -- would be expected to have at least SOME entries pointing
somewhere other than themselves; a perfect identity function across 4
million+ records is not something real merge data would ever produce by
chance, and is the strongest possible signal of an auto-generated
default/placeholder array, not real content.

This directly matches the already-established status of this table's 3
siblings in the "postal-code" file family: `eeu.pmp`
(`postalcodeListMergePostalcode`) and `eeu.pol` (`postalcodeList`) and
`eeu.pot` (`postalcodeTree`) are all confirmed genuinely EMPTY (94-byte
header, zero body) on this disc. `eeu.pmc`/`eeu.pmm` aren't literally
empty -- they still carry a full-size placeholder array -- but the
content itself carries zero real information, for the same underlying
reason: **the entire postal-code subsystem (`.pol`/`.pot`/`.pmm`/`.pmc`/
`.pmp`) is unpopulated on this specific EU East V17 disc.** Plausibly
this East-Europe dataset's country set didn't have licensed/available
postal-code data at build time, or the feature wasn't enabled for this
particular disc release -- not independently confirmed (no other
region/market disc was available this session to compare against a
populated postal-code subsystem).

============================================================================
Open question: why a 4-byte record when eeu.mod's schema declares 13
(`postalcodeListMergeCity`) / 15 (`postalcodeListSeparate`) fields?
============================================================================
Not resolved this session. eeu.mod's own docstring already notes the
exact binary type/width encoding around each field name was never fully
cracked -- plausible explanations, untested: (a) most of those 13/15
logical fields are zero-width/flag-only in the compiled physical format
and only manifest when real data populates them, so the "true" populated
record would be wider than 4 bytes and this disc's placeholder simply
uses the field list's FIRST (or only physically-fixed) field; (b) the
schema's field list describes a richer pre-compaction data model than
the final on-disc physical layout. Given the record boundary is exact at
4 bytes/record (zero leftover bytes, header count matches exactly), this
is not a byte-alignment guess -- just an open question about what the
*other* declared fields would look like if this disc's data were
populated.

============================================================================
Practical use
============================================================================
`read_pmc(path)` returns the raw list of uint32 values (rarely useful on
this disc, since it's provably the identity function) and
`is_identity_placeholder(path)` is the fast full-file check used to
confirm that. Use `research/pmc_reader.py`'s constants for a future
disc where this subsystem might actually be populated -- the record
layout (or at least its first field) is already known.
"""

import struct

from research.aff_reader import decode_not_compressed_header, HEADER_SIZE

RECORD_SIZE = 4


def read_pmc(path):
    """Decode the whole eeu.pmc file. Returns a list of uint32 values,
    one per record, in file order. On the reference disc this is
    provably the identity function (value == index for every record) --
    see this module's docstring."""
    with open(path, "rb") as f:
        data = f.read()
    body = data[HEADER_SIZE:]
    n = len(body) // RECORD_SIZE
    return list(struct.unpack_from("<%dI" % n, body, 0))


def is_identity_placeholder(path):
    """True if every record's value equals its own 0-based index --
    the reference disc's eeu.pmc AND eeu.pmm both return True here,
    confirming the whole postal-code subsystem is unpopulated on this
    disc rather than this file having some unusual real format."""
    values = read_pmc(path)
    return all(v == i for i, v in enumerate(values))
