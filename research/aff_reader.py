"""
aff_reader.py -- decodes eeu.aff, CRACKED this session (structurally
complete; the disc's own copy simply carries no real data). Also the
origin of a broader, previously-undocumented finding: 3 more fields
inside the shared 94-byte "SIEMENS" NOT_COMPRESSED header, confirmed
across every such file on the disc, not just this one -- see
`decode_not_compressed_header()` below.

============================================================================
eeu.aff itself
============================================================================
138 bytes total. 94-byte header (see below), then a 44-byte body that is
**entirely zero bytes** -- i.e. exactly 1 record of 44 bytes (per the
header's own record-count field, decoded below), carrying no real content
on this disc. Fully characterized structurally: the header's record-count
field (1), the body length (44), and the all-zero content all agree with
each other -- there's nothing left to decode, just nothing informative to
find here either.

The name plausibly stands for "affix" (cf. Hunspell's own `.aff` file
convention for spell-checking/word-stripping rules), fitting naturally
alongside this disc's other language/TTS-support files
(prd_reader.py/pct_reader.py's phonetic catalogs, abc_reader.py's
alphabet/language table). A single empty record is consistent with "this
East-Europe dataset's languages don't need any affix-stripping rule for
search/TTS normalization" -- plausible, not independently confirmed (no
other disc region was available this session to compare against a
non-empty `.aff`).

============================================================================
CRACKED (found here, verified across every NOT_COMPRESSED file on the
disc): 3 more fields in the shared 94-byte SIEMENS header
============================================================================
Every NOT_COMPRESSED file on this disc (eeu.rd/.il/.iof/.typ/.ctr/.cty/
.abc/.aff/... -- the ones with a plain `SIEMENS`/`(C) SIEMENS AG` header,
as opposed to the different 80-byte template MAP_COMPRESSED/
FEATURE_COMPRESSED files use) shares this SAME 94-byte header. Only the
first ~50-ish bytes (the literal ASCII strings) were previously decoded;
this session found 3 more meaningful fields in the header's own tail,
checked against all 22 NOT_COMPRESSED files present on the reference disc:

    bytes[84:86]  uint16 LE  file_type   -- a small per-logical-file-type
                                            code, unique per file (e.g.
                                            eeu.rd=4, eeu.cty=3, eeu.typ=1)
    bytes[86:88]  uint16 LE  record_count_lo16
                                         -- CRACKED: that file's own
                                            record count, TRUNCATED to 16
                                            bits for files whose real
                                            count exceeds 65,536
    bytes[90:94]  uint32 LE  total_size  -- the file's own total size in
                                            bytes (header + body) for most
                                            files; 2 confirmed exceptions
                                            store the BODY size instead

**`record_count_lo16` validated exactly** against every already-known
real record count on this disc: `eeu.typ` (2,574, README S3.4) matches
exactly; `eeu.ctr` (35, README S3.11-adjacent) matches exactly; and for
the two files whose real count exceeds a uint16, the field matches the
count taken mod 65,536 exactly -- `eeu.rd`: 8,809,081 mod 65,536 = 27,257,
matching the header exactly; `eeu.cty`: 939,351 mod 65,536 = 21,847, also
exact. This is genuinely useful for a not-yet-examined file: dividing
`(filesize - 94)` by this field (trying `field + 65536*k` for small `k` if
the plain field doesn't divide evenly) is a fast way to GUESS a real fixed
record size before reverse-engineering the body at all -- used this
session to derive strong candidate record sizes for 6 of the disc's
remaining unexamined files (see below).

**`total_size` validated exactly on 18/22 NOT_COMPRESSED files.** 2
confirmed exceptions store the file's BODY size instead (off from the real
total by exactly 94, the header's own size): `eeu.iof` (52,854,486 vs. real
52,854,580) and `eeu.mod` (40,929 vs. real 41,023). One file's value
doesn't match either convention and is unexplained: `eeu.cal` (header says
24,778; real size is 23,326).

**Derived record-size candidates for 6 still-unexamined files** (using
`record_count_lo16` against each file's own real body size, this session --
not independently verified against real content, but exact-integer-
dividing at k=0 for all 6 is a strong structural signal, not a guess):

    eeu.cal   484   records x  48 bytes  (body 23,232 bytes)
    eeu.cat    35   records x  19 bytes  (body   665 bytes)
    eeu.cny 2,326   records x 176 bytes  (body 409,376 bytes)
    eeu.si  24,353  records x   8 bytes  (body 194,824 bytes)
    eeu.stt   691   records x 114 bytes  (body 78,774 bytes)
    eeu.ti     17   records x  23 bytes  (body 391 bytes)

`eeu.pmc`/`eeu.pmm` (record_count_lo16 = 20,872 each) do NOT divide their
own body sizes evenly at k=0..4 -- either their real record size isn't
fixed, the true count needs a larger wraparound multiple, or they don't
use this convention at all.
CORRECTION (later session, via research/pmc_reader.py): the real
wraparound multiple was k=62 (20,872 + 65,536*62 = 4,084,104), giving an
exact 4-byte fixed record -- this convention held after all, the k=0..4
search range tried here just wasn't wide enough. Both files' bodies
turned out to be a pure identity array (value == index for every
record), confirming this disc's postal-code subsystem is unpopulated
rather than this file having some unusual non-fixed format.
`eeu.mod`/`eeu.tmc` both show
`record_count_lo16 == 0` -- consistent with either a genuinely
variable-length body (like `eeu.il`, README S3.2, which also doesn't fit
a clean fixed-record model) or a real count that's an exact multiple of
65,536 (implausible for files this size).
"""

import struct

HEADER_SIZE = 94


def decode_not_compressed_header(path_or_bytes):
    """Decode the shared 94-byte SIEMENS header's now-cracked trailing
    fields. Accepts either a file path or the raw header bytes (>= 94
    bytes). Returns a dict: {file_type, record_count_lo16, total_size,
    real_size (if a path was given -- None otherwise)}. See this module's
    docstring for which fields are exact and which files are known
    exceptions."""
    if isinstance(path_or_bytes, (bytes, bytearray)):
        header = path_or_bytes[:HEADER_SIZE]
        real_size = None
    else:
        with open(path_or_bytes, "rb") as f:
            header = f.read(HEADER_SIZE)
        import os
        real_size = os.path.getsize(path_or_bytes)
    return {
        "file_type": struct.unpack_from("<H", header, 84)[0],
        "record_count_lo16": struct.unpack_from("<H", header, 86)[0],
        "total_size": struct.unpack_from("<I", header, 90)[0],
        "real_size": real_size,
    }


def read_aff(path):
    """Decode eeu.aff: returns (header_fields, body_bytes). On the
    reference disc, body_bytes is 44 bytes, all zero."""
    with open(path, "rb") as f:
        data = f.read()
    return decode_not_compressed_header(data), data[HEADER_SIZE:]
