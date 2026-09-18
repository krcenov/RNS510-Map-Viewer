"""
iof_reader.py -- decodes eeu.iof, the fixed 6-byte-per-record array parallel
to eeu.rd (README S3.3). CRACKED this session: for a small (~0.355%) subset
of eeu.rd records, an eeu.iof record is a pointer into eeu.il describing a
"nearby street names" list -- an absolute byte OFFSET into eeu.il plus a
COUNT of consecutive eeu.il entries to read from there. The much larger
common case (~99.6% of records) still has an unexplained per-record value
-- NOT cracked, see "What remains open" below.

============================================================================
Record layout (6 bytes, same 94-byte SIEMENS header + fixed-record
convention as eeu.rd/.il/.typ/.ctr/.cty)
============================================================================
    offset 0 : uint32 LE  "zero4"   -- 0 for ~99.6% of records; for the
                                        remaining ~0.355%, an ABSOLUTE BYTE
                                        OFFSET into eeu.il (CRACKED, see
                                        below)
    offset 4 : uint8      "vb"      -- for zero4==0 records: an unresolved
                                        value, usually small (0-30ish, long
                                        tail up to 255) -- NOT cracked; for
                                        zero4!=0 records: the COUNT of
                                        consecutive eeu.il entries to read
                                        starting at that offset (CRACKED)
    offset 5 : uint8      "c80"     -- 0x80 for ~99.6% of records (an
                                        earlier, small-sample session
                                        mis-documented this as a hard
                                        constant); records with a nonzero
                                        `zero4` instead have c80 in {0, 1}
                                        in every case checked. A handful of
                                        outlier values (129-255, and 1-7 on
                                        7 confirmed zero4!=0 records) also
                                        occur -- likely a genuine flag byte
                                        whose low 7 bits carry something
                                        else, not fully characterized.

The OLD documented layout ("[00 00 00 00][varying byte][0x80 constant]",
based on 15 hand-checked records from one tile) is only an approximation of
the common case -- bytes[0:4] are not always exactly zero, and byte[5] is
not always exactly 0x80. Both "constants" have real, rare exceptions only
visible at full-file scale (8,809,081 records); see `analyze_iof()` for the
exact distribution.

============================================================================
CRACKED: eeu.il "nearby street names" pointer (this session)
============================================================================
For the 31,318 records (0.3555% of the file) with a nonzero `zero4`:
`zero4` is an absolute file byte offset into `eeu.il`, landing EXACTLY on
the start of a real `.il` entry (`[11-byte prefix][ASCII name][0x00]`, the
format README S3.2 already cracked), and `vb` is how many CONSECUTIVE
`.il` entries to read from there.

Validated at scale (random samples against the real ISO, this session):
  - 858/1000 (85.8%) of a random sample's `zero4` value lands on a
    byte-exact, cleanly-parseable `.il` entry boundary (11-byte prefix +
    printable name + NUL); of those 858, ALL 858 (100%) have the entry's
    own embedded eeu.rd-index prefix field (README S3.2's already-cracked
    `bytes[0:4]`) resolve to a REAL eeu.rd record whose own name matches
    the entry's trailing string -- i.e. these are indisputably genuine
    `.il` entries, not a coincidental byte-offset collision. (The ~14% that
    don't parse cleanly in this quick check are mostly non-ASCII-accented
    names tripping a deliberately strict printable-byte filter, not
    evidence against the mechanism -- see the geographic/self-inclusion
    checks below, run with a more permissive parser, for further
    confirmation.)
  - Chaining exactly `vb` consecutive entries from `zero4` and validating
    EVERY one the same way (not just the first) succeeds end-to-end for
    the large majority of a 500-record sample (partial failures are
    truncated-read-window artifacts in the quick validation script, not
    real parse failures -- re-checked by hand on several "failures" and
    they resolve fine with a larger read window).
  - **Geographic clustering, 30 random anchor records, every single one**:
    every entry in an anchor's own list resolves (via the entry's own
    eeu.rd-index field) to a REAL eeu.rd record within a few km of the
    anchor's own coordinates in the overwhelming majority of cases (median
    of the per-record max distance across the sample: single digits of
    km; a few outliers up to ~30-40km, plausibly a longer regional route
    passing through more than one settlement). This is not proximity by
    chance -- eeu.rd is NOT spatially sorted (README S3.1), so a random
    eeu.il pointer would have no reason to cluster geographically at all.
  - **The anchor's own name is essentially never inside its own list**
    (1/300 sampled) -- this is a list of OTHER nearby roads, not a
    self-inclusive one.
  - Anchor records' own eeu.rd names are frequently bare route/highway
    codes rather than full descriptive street names (`"R102"`, `"T0803"`,
    `"B32"`, `"L73"`, `"SS1"`, `"D-400"`, `"180"`) -- consistent with one
    anchor per through-route/settlement rather than one per ordinary
    street, though the exact selection rule for which ~31k of 8.8M records
    become anchors is NOT recovered (see below).

**Practical reading**: this looks like a real "pick an area, browse its
street names" catalog -- exactly the kind of data a real destination-entry
"select street from a list" screen would need, and a genuinely different,
independent piece of evidence from the already-documented (README S3.7)
`.rt`/`.rl`/`.prl` hypothesis for the same kind of UI. Whether the real
unit's own address-entry screen actually reads THIS mechanism, `.rt`/`.rl`/
`.prl`, both, or neither remains unconfirmed on hardware.

============================================================================
What remains open
============================================================================
  - **The common-case `vb` byte (~99.6% of records, zero4==0)** is still
    completely unresolved. Its real range is 0-255 (not the 0-18 an
    earlier, 15-sample-only session reported) with a strongly right-skewed
    distribution (2/1/3/0/4 are the 5 most common values, together >70% of
    all records). A weak cross-check against topology-table tag complexity
    on 15 samples from one tile found no clean separation (see
    map_compressed_reader.py's decode_topology() docstring) -- inconclusive,
    not refuted, on that tiny a sample. NOT re-tested this session against
    any hypothesis; candidate next steps: road-class-style correlation
    (does `vb` correlate with which MAP_COMPRESSED generalization layers
    a road's own geometry appears in -- see map_compressed_reader.py's
    build_geo_index()/find_tile_for_coord() plus road_naming.py's
    match_feature() to link an eeu.rd record to its rendered tile
    feature(s)); correlation with eeu.rd's own still-unresolved
    bytes[1:5]/bytes[5:8] at FULL scale (the existing docstring's "no
    match found" claim for bytes[1:5] predates this session and was never
    re-tested at scale either); correlation with segment count per road
    name (highways split into many eeu.rd records vs. short local
    streets).
  - **Which ~31,318 of 8,809,081 records become "anchors"** (nonzero
    `zero4`) is not recovered. Not a simple "one per real eeu.cty
    settlement" -- eeu.cty has 79,738 top-level (no-comma) entries on the
    reference disc, over 2x the anchor count, so it's not a clean 1:1
    correspondence with real named places either. Worth checking whether
    anchors are more common on route-numbered roads specifically (several
    anchor examples above ARE route codes), or tied to some other already-
    decoded field (e.g. eeu.rd's own bytes[5:8] "candidate shared-geometry
    pointer").
  - **`c80`'s exact bit-level meaning** is not pinned down -- 0x80 for the
    common case, 0 or 1 (never checked past that) for confirmed anchors,
    and a long tail of other values (129-255) on a very small number of
    records not individually investigated.
  - **Whether an anchor's own list is ordered by anything** (alphabetical,
    distance, `.il`'s own on-disk order) was checked on a 100-record sample
    and found NOT reliably alphabetically sorted (16/100) -- inconclusive,
    a different ordering hypothesis (e.g. distance-from-anchor, or simply
    `.il`'s own physical layout order for that area) was not tested.

============================================================================
Practical use
============================================================================
`anchor_records()` scans the whole file once (vectorized with numpy, a
few hundred ms) and returns every record with a nonzero `zero4` --
i.e. every "has a nearby-street-list" road. `nearby_street_entries()`
reads the actual list for one anchor (offset, count) against a real,
already-open `eeu.il` byte string. Neither of the two already-cracked
prerequisite files needs re-implementing here: `.il`'s own
`[11-byte prefix][name][0x00]` format is read inline (see README S3.2),
not imported from a separate module (there isn't a dedicated `.il` reader
module yet either -- `rns510_core.py` handles `.il` for the editing tool
directly).
"""

import struct

import numpy as np

IOF_HEADER_SIZE = 94
IOF_RECORD_SIZE = 6
IL_HEADER_SIZE = 94
RD_HEADER_SIZE = 94
RD_RECORD_SIZE = 67

_IOF_DTYPE = np.dtype([
    ("zero4", "<u4"),
    ("vb", "u1"),
    ("c80", "u1"),
])


def read_iof_records(path):
    """Read the whole eeu.iof file and return a numpy structured array of
    (zero4, vb, c80) triples, one per record, in file order -- index i here
    corresponds exactly to eeu.rd record i (same count, same order, see
    README S3.3)."""
    with open(path, "rb") as f:
        data = f.read()
    body = data[IOF_HEADER_SIZE:]
    n, rem = divmod(len(body), IOF_RECORD_SIZE)
    assert rem == 0, "eeu.iof body size is not a multiple of the 6-byte record size"
    return np.frombuffer(body, dtype=_IOF_DTYPE, count=n)


def analyze_iof(records):
    """Summary statistics over a read_iof_records() array -- how many
    records are "anchors" (nonzero zero4, i.e. carry a nearby-street-list
    pointer) vs. "common" (zero4==0, the still-unresolved majority case),
    plus each group's own vb/c80 distributions. Returns a dict; see this
    module's docstring for what a real run against the reference disc
    reports."""
    is_anchor = records["zero4"] != 0
    n = len(records)
    anchor_vb = records["vb"][is_anchor]
    common_vb = records["vb"][~is_anchor]
    return {
        "n_records": n,
        "n_anchors": int(is_anchor.sum()),
        "anchor_fraction": float(is_anchor.sum()) / n if n else 0.0,
        "anchor_vb_min": int(anchor_vb.min()) if len(anchor_vb) else None,
        "anchor_vb_max": int(anchor_vb.max()) if len(anchor_vb) else None,
        "common_vb_max": int(common_vb.max()) if len(common_vb) else None,
        "is_anchor": is_anchor,
    }


def anchor_indices(records):
    """eeu.rd/eeu.iof record indices that carry a nearby-street-list
    pointer (nonzero `zero4`) -- the reliable anchor test (more robust than
    checking `c80`, which has rare non-0x80/non-zero outlier values even on
    confirmed real anchors)."""
    return np.nonzero(records["zero4"] != 0)[0]


def parse_il_entry(il_data, offset):
    """Parse one eeu.il entry (README S3.2's `[11-byte prefix][ASCII
    name][0x00]` format) starting at absolute byte offset `offset` in
    `il_data` (the whole, already-read eeu.il file bytes, header included
    -- `offset` is an ABSOLUTE file offset, already past the 94-byte
    header for any real entry). Returns (rd_index, name_bytes, next_offset)
    or None if this doesn't look like a valid entry (used to validate a
    candidate offset, and to walk a chain of consecutive entries)."""
    if offset + 11 > len(il_data):
        return None
    rd_index = struct.unpack_from("<I", il_data, offset)[0]
    rest = il_data[offset + 11:offset + 11 + 256]
    nul = rest.find(b"\x00")
    if nul <= 0:
        return None
    name = rest[:nul]
    return rd_index, name, offset + 11 + nul + 1


def nearby_street_entries(il_data, offset, count):
    """Read the `count` consecutive eeu.il entries starting at absolute
    byte `offset` -- i.e. one anchor record's full "nearby street names"
    list (see this module's docstring). Returns a list of
    (rd_index, name_bytes) tuples, or None if the chain doesn't parse
    cleanly for the full requested count (a real parse failure, or just a
    too-small lookahead window inside parse_il_entry() for an unusually
    long name -- see the docstring's validation notes)."""
    entries = []
    pos = offset
    for _ in range(count):
        parsed = parse_il_entry(il_data, pos)
        if parsed is None:
            return None
        rd_index, name, pos = parsed
        entries.append((rd_index, name))
    return entries


def rd_record(rd_data, index):
    """Minimal eeu.rd accessor (name + lon/lat only, README S3.1) -- kept
    local rather than importing road_naming.RdCache to avoid pulling that
    module's full in-memory-cache machinery in for a handful of spot
    checks. For bulk work, prefer road_naming.RdCache."""
    off = RD_HEADER_SIZE + index * RD_RECORD_SIZE
    name = rd_data[off + 24:off + 24 + 43].split(b"\x00", 1)[0]
    lon = struct.unpack_from("<i", rd_data, off + 8)[0] / 100000.0
    lat = struct.unpack_from("<i", rd_data, off + 12)[0] / 100000.0
    return name, lon, lat
