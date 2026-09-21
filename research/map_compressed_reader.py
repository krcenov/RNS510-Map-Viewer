"""
Reader/scanner for RNS510 MAP_COMPRESSED (compressionType=2: eeuz.mp0,
eeuz.mg1..mg4) and FEATURE_COMPRESSED (compressionType=3: eeuz.fea) files.

**The 5 layers are real ROAD-CLASS tiers, not just generic zoom-level
simplification -- CONFIRMED, a later session, directly from the real
RNS510 unit's own on-screen behavior** (the user has the actual hardware
running this exact disc, CD_8555): `mg4`=highways, `mg3`=main roads,
`mg2`=boulevards, `mg1`=main streets, `mp0`=everything else (local/
residential streets and smaller roads). Directly validated: a real
A1/Trakia motorway segment near Sofia is present in `mg4`, but a real
local one-way street (Vladimir Bashev, Sofia) is NOT present anywhere
near its own real coordinates in `mg4` (nearest-anchor match landed
~6-7km away) -- only found in `mp0`, exactly matching this hierarchy.

CONFIRMED:
  - File-level header uses a distinct-but-recognizable 84-byte template
    (same slot layout/lengths as the plain 94-byte "SIEMENS" header used
    by NOT_COMPRESSED files, but with different text):
        bytes[0:16]  = "(*$SIEMENS&^)\0\0\0"   (vs "SIEMENS\0..." plain)
        bytes[16:32] = "Copyright 1998\0\0"     (vs "(C) SIEMENS AG\0\0")
        bytes[32:48] = "2.0.0\0..."             (same as plain files)
        bytes[48:64] = data version string, e.g. "EEU50530910.84\0\0"
        bytes[64:80] = sub-version, e.g. "5.0.5\0..."
    Identical across mp0/mg1/mg2/mg3/mg4/fea (only the per-disc version
    strings would differ disc to disc).
  - Immediately after byte 80 (no padding -- unlike NOT_COMPRESSED files,
    which zero-pad out to 94 bytes) comes a directory/index region of
    non-trivial size (verified: ~130KB for the 16.5MB mg4, ~1.35MB for
    the 240MB mg1, ~4.1MB for the 2.1GB mp0, ~11.8MB for the 553MB fea --
    scales with tile count, not proportionally with file size). The LAST
    part of this region (immediately before the first tile) is a CONFIRMED,
    fixed-stride flat table of (file offset, decompressed length,
    compressed length) triples, one per tile -- see `read_directory()`
    below, and the second docstring block further down for full details.
    The part of this region BEFORE that flat table is still not decoded in
    detail (see `header_walk()` and the second docstring block).
  - After the directory region, the rest of the file is many
    independently zlib-compressed (RFC1950, standard 0x78.. header)
    "tiles" packed back-to-back with NO padding between them (verified:
    a tile's consumed-byte count exactly equals the gap to the next
    tile's start offset, in both mg4 and mp0). Tile sizes are highly
    variable (hundreds of bytes to ~35KB decompressed seen in samples).
  - Decompressed tile content starts with a small fixed-shape header
    whose very first uint16 is a constant magic 0x0146 (seen identically
    across every decompressed tile sampled from mg4 and mp0), followed
    by more header fields, then what looks like a spatial sub-index
    (many repeated uint32 "sentinel" entries whose value equals the
    tile's own total decompressed length -- i.e. sparse/empty sub-cells
    point at end-of-tile), then apparent geometry data resembling
    int16 LE (dx, dy) delta-coordinate pairs (candidate polyline shape
    points relative to a local origin), and embedded null-terminated
    ASCII strings for labels (e.g. distance/scale markers seen in mp0:
    "300M(ITA)", "2300M(ITA)", "21KM(ITA)" -- country-tagged labels).
    None of this internal tile schema is fully decoded; this is as far
    as this session got.

USE THIS FOR: finding and decompressing any given tile (find_tiles /
decompress_tile), cheaply parsing the confirmed flat offset/length
directory table (read_directory) without brute-force scanning the whole
file, AND (new this session) looking up "which tile covers lat/lon X,Y"
via a DERIVED geo-index built from real anchor coordinates found INSIDE
decompressed tile content -- see build_geo_index() / find_tile_for_coord()
/ find_tile_anchor() further down, and the big comment block above them
for the full writeup. This sidesteps Continental's own still-undecoded
pre-table "geo-index prefix" region entirely (that region -- see below --
remains uncracked, but is no longer required for this purpose). It also
lets you relocate/resize an EXISTING tile (rewrite its flat-table entry
and shift every later entry's offset by the size delta), enough to edit
content inside a tile that already covers your target area.

Usage:
    import map_compressed_reader as mcr
    tiles = mcr.find_tiles(path, max_bytes=30_000_000)   # brute-force, slow, exact: [(offset,decompressed_len), ...]
    raw, consumed = mcr.decompress_tile(path, offset)

    directory = mcr.read_directory(path)   # fast, no brute force -- works on multi-GB files
    directory["entries"]        # [(offset, decompressed_len, compressed_len), ...] in file order
    directory["table_start"]    # absolute file offset of the flat table
    directory["geo_index_end"]  # == table_start; region before it is still undecoded

    geo_index = mcr.build_geo_index(path)             # {tile_id: (lon, lat, method)}, ~O(filesize)
    tile_id = mcr.find_tile_for_coord(geo_index, lon, lat)  # nearest-anchor tile lookup
    lon, lat, method = mcr.find_tile_anchor(raw, declen)    # per-tile anchor, given raw bytes
    points = mcr.decode_vertex_chain(raw, declen)           # [(lon,lat), ...] absolute vertex chain (single-feature only, see caveat)
    features = mcr.decode_features(raw, declen)             # [{"count","offset","block_end","points":[(lon,lat),...]}, ...] -- multi-feature-aware, CRACKED this session
    topology = mcr.decode_topology(raw, declen, features)   # per-feature topology/adjacency table -- record layout cracked; see resolve_topology_adjacency() for the node-id<->coordinate mapping (its docstring has the REFUTED hypotheses, incl. the graph-walk approach)
    adjacency = mcr.resolve_topology_adjacency(raw, declen, features, topology)  # NEW: CRACKED -- per-feature real point-to-point adjacency (which decode_features() point indices are actually connected), see its docstring for the mechanism and validation numbers
    header = mcr.decode_tile_header(raw)                    # NEW: partial decode of the per-tile 0x02-0x17 header words (feature 0 point count/block_end, topology-table sizing hints, node-count) -- see its docstring for exactly which fields are validated
    gap = mcr.decode_topology_gap(raw, header)               # NEW: decode the small array that explains most of the previously-"unidentified" gap before a feature's topology table -- meaning of its values still unresolved, see docstring

CONFIRMED (this session, see README section 8 / research log): the region
immediately BEFORE the first tile is a flat, fixed-stride 8-byte-per-tile
table -- NOT the ascending-index region described above (that region, from
byte 80 up to this table's start, is a SEPARATE, still-undecoded structure;
see below). Record layout, one entry per tile, in the SAME order tiles
physically appear in the file (entry i <-> the i-th tile found by
find_tiles()):
    offset 0: uint32 LE  absolute byte offset of the tile in the file
    offset 4: uint16 LE  decompressed tile length
    offset 6: uint16 LE  compressed tile length (== gap to next tile's start)
Table start = (first tile's file offset) - (num_tiles * 8); table end ==
first tile's file offset EXACTLY (zero padding, consistent with the rest of
this format). Validated by decompressing at the computed offset and checking
declen/complen match, at 100% hit rate on held-out entries across FOUR
MAP_COMPRESSED files of very different sizes:
    eeuz.mg4 (16.5MB,  6,110 tiles): 6110/6110 exact
    eeuz.mg3 (46MB,   16,503 tiles): 16503/16503 exact
    eeuz.mg2 (113MB,  34,209 tiles): 34209/34209 exact
    eeuz.mp0 (2.14GB,194,705 tiles): 80/80 randomly-sampled entries exact
      (full table too large to brute-force-verify every entry; find_tiles()
      over the whole 2.1GB file is impractical -- use find_first_tile() +
      find_table_start() instead, see below, which only need to scan a few
      MB and complete in well under a second)
NOTE: the uint16 length fields cap a single tile at 65,535 bytes compressed
or decompressed. All four files above stay well under that (max compressed
length observed: 9,327 bytes on mg2). If a future edit ever needs to write a
tile larger than that, this record format cannot represent it as-is.
NOT YET CONFIRMED on eeuz.fea (FEATURE_COMPRESSED, compression type 3, not
MAP_COMPRESSED type 2 like the others) -- its first tile was located fine
(offset 11727784, declen 72, complen 40, verified by direct decompression +
confirming the next tile's zlib header immediately follows at
offset+complen), but the exact 4-byte absolute offset value does not appear
ANYWHERE in its pre-tile region, unlike the other four files. fea's
directory almost certainly uses a different encoding (relative offsets? a
different scale/unit? a different key entirely, since FEATURE_COMPRESSED
may be indexed by feature/road ID rather than spatial tile) -- unresolved,
left for a future session.

UPDATE (later session): eeuz.fea was investigated in depth -- see
research/feature_reader.py and README.md section 3.10. Headline finding:
it is a multi-language named-place gazetteer (cities, seas, islands,
road-shield labels), NOT a MAP_COMPRESSED-style tile file, despite sharing
the same 80-byte header template and the same "back-to-back zlib streams"
payload primitive documented above. Its internal tile/entry schema is
unrelated to decode_features()'s anchor+delta format (tried directly,
found nothing), its directory region's field-level semantics are still
uncracked (though its record framing is now known -- a uniform grid of
977,308 fixed 12-byte records + an 8-byte trailer), and no per-record
coordinate field was found. feature_reader.py's enumerate_entries() +
scan_names() give a validated, if brute-force, way to enumerate and
name-based-geolocate its content instead.

The region BEFORE this flat table (byte 80 up to table_start) is a SEPARATE,
still-undecoded structure of variable-length records, ~14-16 bytes/tile on
average, whose first field is an ascending uint32 counter (1, 2, 3, ...,
num_tiles) -- see `header_walk()` below. It very likely maps a geographic
coordinate or grid cell to an INDEX into the flat table above (values seen
during manual decoding are large integers plausible as
degrees*100000-scaled lat/lon, e.g. ~43.19, ~46.20, ~59.06 -- all inside
plausible Eastern-Europe bounds -- but this was NOT proven; those exact
values do not appear in the confirmed flat table and a byte-exact record
framing was not established because small ascending integers collide too
easily with unrelated small values elsewhere in the same records to trust
a naive "search for the next index" walk beyond the first ~10 records).
This geo-index region is NOT required to relocate/resize an EXISTING tile
(you only need to rewrite that one flat-table entry's offset/length, and
shift every later entry's offset field by the size delta) -- it IS required
to look up "which tile covers lat/lon X,Y" from scratch, or to add a
brand-new tile at a location with no existing tile.
"""

import math
import struct
import zlib


HEADER_MAGIC = b"(*$SIEMENS&^)\x00\x00\x00"


def read_header(path):
    with open(path, "rb") as f:
        data = f.read(96)
    assert data[:16] == HEADER_MAGIC, f"unexpected magic {data[:16]!r}"
    return {
        "magic": data[0:16],
        "copyright": data[16:32],
        "format_version": data[32:48],
        "data_version": data[48:64],
        "sub_version": data[64:80],
    }


def _is_zlib_header(b0, b1):
    return (b0 & 0x0F) == 8 and ((b0 * 256 + b1) % 31) == 0


def find_tiles(path, max_bytes=30_000_000, min_decompressed=1):
    """Scan the first max_bytes of `path` for byte offsets that are the
    start of a real, fully-valid zlib stream (checked by actually
    decompressing to EOF). Returns [(offset, decompressed_len), ...] in
    file order. Only reads/holds max_bytes in memory."""
    with open(path, "rb") as f:
        data = f.read(max_bytes)

    candidates = [
        i for i in range(len(data) - 1)
        if _is_zlib_header(data[i], data[i + 1])
    ]

    found = []
    for off in candidates:
        try:
            do = zlib.decompressobj()
            out = do.decompress(data[off:off + 2_000_000])
        except zlib.error:
            continue
        if do.eof and len(out) >= min_decompressed:
            found.append((off, len(out)))
    return found


def decompress_tile(path, offset, read_window=2_000_000):
    with open(path, "rb") as f:
        f.seek(offset)
        chunk = f.read(read_window)
    do = zlib.decompressobj()
    out = do.decompress(chunk)
    assert do.eof, "tile did not terminate within read_window; increase it"
    consumed = read_window - len(do.unused_data)
    return out, consumed


TABLE_ENTRY_STRUCT = struct.Struct("<IHH")  # offset, declen, complen -- 8 bytes


def find_first_tile(path, scan_bytes=16_000_000, start=80, window=300_000):
    """Cheaply locate just the FIRST real tile in a MAP_COMPRESSED file,
    without brute-force-scanning the whole file like find_tiles() does.
    Scans only the first `scan_bytes` after `start` for zlib-header
    candidates, and for each one attempts a bounded decompression. Rejects
    candidates whose compressed/decompressed ratio is implausible (a known
    false-positive failure mode: some byte sequences look like a valid,
    fully-terminating zlib stream but "consume" far more input than their
    tiny output could ever legitimately compress from). Returns
    (offset, decompressed_len, compressed_len) or None.

    For eeuz.fea (11.8MB directory) you need scan_bytes >= ~12_000_000; the
    default covers every eeuz.mg1-mg4/mp0 file on the reference disc."""
    with open(path, "rb") as f:
        f.seek(start)
        data = f.read(scan_bytes)
    for i in range(len(data) - 1):
        if not _is_zlib_header(data[i], data[i + 1]):
            continue
        do = zlib.decompressobj()
        try:
            out = do.decompress(data[i:i + window])
        except zlib.error:
            continue
        if not do.eof or not out:
            continue
        consumed = window - len(do.unused_data)
        if consumed <= len(out) * 1.3 + 32:  # reject implausible expansion
            return start + i, len(out), consumed
    return None


def find_table_start(path, first_tile_offset, first_declen, first_complen,
                      region_start=80):
    """Locate the flat per-tile directory table by searching for the exact
    8-byte signature (offset, declen, complen) of the FIRST tile (from
    find_first_tile()) within the region before it. Returns the absolute
    file offset of the table's first record, or None if not found (seen on
    eeuz.fea -- see module docstring; not confirmed to use this format)."""
    with open(path, "rb") as f:
        f.seek(region_start)
        region = f.read(first_tile_offset - region_start)
    pat = TABLE_ENTRY_STRUCT.pack(first_tile_offset, first_declen, first_complen)
    pos = region.find(pat)
    if pos == -1:
        return None
    return region_start + pos


def read_directory(path):
    """Locate and parse the flat per-tile offset/length table (CONFIRMED
    format -- see module docstring) WITHOUT brute-force scanning the whole
    file. Works on multi-GB files (eeuz.mp0) in well under a second, unlike
    find_tiles(). Returns:
        {
          "geo_index_start": 80,
          "geo_index_end": <table_start>,   # unparsed, see docstring
          "table_start": <int>,
          "table_end": <int>,               # == first tile's file offset
          "num_tiles": <int>,
          "entries": [(offset, decompressed_len, compressed_len), ...],
        }
    entries[i] describes the i-th tile in physical file order (same order
    find_tiles() would return, and the same order this table stores them).
    Raises RuntimeError if the file's directory doesn't match the confirmed
    record format (known to happen on eeuz.fea)."""
    first = find_first_tile(path)
    if first is None:
        raise RuntimeError(f"could not locate first tile in {path}")
    first_offset, first_declen, first_complen = first

    table_start = find_table_start(path, first_offset, first_declen, first_complen)
    if table_start is None:
        raise RuntimeError(
            f"could not locate directory table in {path} "
            f"(first tile at {first_offset}, declen={first_declen}, "
            f"complen={first_complen}) -- this file may not use the "
            f"confirmed mg1-mg4/mp0 record format (e.g. eeuz.fea doesn't)"
        )

    num_tiles = (first_offset - table_start) // 8
    with open(path, "rb") as f:
        f.seek(table_start)
        raw = f.read(num_tiles * 8)

    entries = [TABLE_ENTRY_STRUCT.unpack_from(raw, i * 8) for i in range(num_tiles)]

    return {
        "geo_index_start": 80,
        "geo_index_end": table_start,
        "table_start": table_start,
        "table_end": first_offset,
        "num_tiles": num_tiles,
        "entries": entries,
    }


def pack_table_entry(offset, decompressed_len, compressed_len):
    """Encode one 8-byte directory record for writing back into the flat
    table (see read_directory()). Raises ValueError if a length exceeds the
    format's uint16 cap (65,535 bytes) -- see module docstring caveat."""
    return TABLE_ENTRY_STRUCT.pack(offset, decompressed_len, compressed_len)


def header_walk(data, start=0x82, max_records=50):
    """Exploratory helper: walk the mg4/mp0-style directory region
    assuming records begin with an ascending uint32 index (1, 2, 3, ...).
    Returns a list of (index, record_start_offset, record_bytes) using
    the NEXT record's start as this record's end. Best-effort / manual
    verification tool, not a trusted parser -- the tail-field semantics
    within each record are NOT understood (see module docstring)."""
    import struct
    records = []
    pos = start
    idx = 1
    starts = []
    # First pass: locate the start offset of each ascending index by
    # searching for its 4-byte LE pattern near the expected region.
    search_from = start
    for idx in range(1, max_records + 1):
        pat = struct.pack("<I", idx)
        found = data.find(pat, search_from, search_from + 64)
        if found == -1:
            break
        starts.append(found)
        search_from = found + 4
    for i in range(len(starts) - 1):
        records.append((i + 1, starts[i], data[starts[i]:starts[i + 1]]))
    return records


# ---------------------------------------------------------------------------
# DERIVED geo-index: an absolute-anchor coordinate found INSIDE decompressed
# tile content itself (NOT Continental's pre-table "geo-index prefix" region,
# which remains uncracked -- see module docstring above). CONFIRMED this
# session by decompressing all 6,110 tiles of eeuz.mg4 in full, plus large
# samples of eeuz.mg3/mg2/mp0:
#
#   Inside a decompressed tile, after the magic (0x0000) and the 22-byte
#   undecoded header (0x0002-0x0017), there is a spatial sub-index region
#   made of individual uint16 LE words, each one of:
#     - the tile's own decompressed length (`declen`)  -- "empty cell" sentinel
#     - 0                                               -- a second marker/pad
#   "data_start" = byte offset of the FIRST uint16 word that is neither of
#   those two values. Empirically this is byte 326 for ~83% of eeuz.mg4/mg3/
#   mg2 tiles (a fixed-size sub-index grid), byte 24 for tiles with almost no
#   sub-index content (very sparse tiles -- degenerate case, see below), and
#   occasionally 328.
#
#   At `data_start`: a 2-byte tag/count field (meaning not decoded), then:
#     data_start+2 : int32 LE   anchor LONGITUDE, degrees = value/100000
#     data_start+6 : int32 LE   anchor LATITUDE,  degrees = value/100000
#     data_start+10: start of the int16 LE (dx,dy) delta-coordinate run
#                    (see decode_vertex_chain() below) -- SAME /100000 scale
#                    as the anchor, i.e. each delta unit is 0.00001 degree
#                    (~1.1m at mid-latitudes). Confirmed by cumulative-
#                    summing a real chain from anchor (21.20056, 45.58739)
#                    and finding the very first resulting vertex,
#                    (21.20062, 45.58711), is an EXACT match (5 decimal
#                    places) to a real eeu.rd road record named "DC158"
#                    near Timisoara, Romania.
#
#   Validated at scale: on eeuz.mg4 (6,110/6,110 tiles decompressed), the
#   structural rule above (data_start via sentinel-scan, anchor at
#   data_start+2/+6) yields a value that is *geographically plausible*
#   (lon 3-46E, lat 30-72N -- generous bounds for the "EEU" Navteq dataset,
#   which spans from Italy/France in the west to the Caucasus/Urals in the
#   east) for 4,435/6,110 tiles (72.6%) directly, and for 87.8% of the
#   majority data_start==326 subgroup specifically. A small fraction of
#   tiles (~1,026/6,110, those with data_start==24 -- very sparse tiles
#   where the "first non-sentinel" heuristic degenerates and returns two
#   more sentinel halves instead of real data) fail the structural rule
#   outright. Country-tagged label strings (e.g. "(ITA)") are ABSENT from
#   mg2/mg3/mg4 (they only appear in the much richer mp0 layer), so
#   geographic cross-validation on mg4/mg3/mg2 relied on (a) internal
#   consistency of the decoded lon/lat range sweeping smoothly and
#   plausibly across the whole Eastern-Europe+neighbors extent as tile_id
#   increases, and (b) the exact eeu.rd "DC158" match above. On mp0,
#   country labels ARE present and were used directly: e.g. tile at file
#   offset 6,126,355 is labelled "(ITA)" and a real (non-sentinel, twice-
#   repeated) coordinate pair inside it decodes to (8.53E, 39.3N) --
#   Sardinia, Italy -- correct. (mp0's sub-index is deeper/differently
#   shaped, so the fixed data_start==326 structural shortcut does not
#   transfer to mp0 as cleanly; the brute-force fallback below does still
#   work on mp0.)
#
#   PRACTICAL fallback (used automatically when the structural rule fails
#   or yields an implausible value): brute-force scan the whole tile at
#   every 2-byte-aligned position for an adjacent int32-LE pair that (a)
#   both fall within the plausible lon/lat bounds and (b) are not equal to
#   each other (rules out sentinel/filler false-positives, which always
#   have lon==lat since they're just a repeated single value read as two
#   fields). Taking the FIRST such match found (byte order) recovered a
#   plausible anchor for 6,106/6,110 mg4 tiles (99.93%) -- either agreeing
#   with the structural answer (97% of the time it was cross-checked) or,
#   in the ~3% disagreement cases, landing a few bytes off but still in the
#   same real-world region (both were plausible Turkish coordinates in the
#   sample checked), i.e. never wildly wrong.
#
# NOT YET DONE: converting this per-tile ANCHOR POINT into a true bounding
# box (we don't yet know the tile's width/height in degrees, so
# find_tile_for_coord() below is nearest-anchor, not exact containment).
# The undecoded 22-byte header (0x0002-0x0017) is the most likely place a
# width/height or point-count would live, but was NOT cracked this session
# -- its values (order of magnitude 1-2000) are far too small to be
# degree*100000 coordinates directly, so they are NOT themselves anchor
# candidates (ruled out).
# ---------------------------------------------------------------------------

_ANCHOR_LON_RANGE = (3.0, 46.0)
_ANCHOR_LAT_RANGE = (30.0, 72.0)


def _find_subindex_data_start(raw, declen):
    """Byte offset of the first uint16 LE word (scanning from byte 24) that
    is neither the tile's own `declen` (empty-cell sentinel) nor 0 (pad
    marker). Returns None if the whole tile past byte 24 is sentinel/zero
    (shouldn't normally happen) or the tile is too short to have a header."""
    n16 = declen // 2
    if n16 <= 12:
        return None
    u16 = struct.unpack_from(f"<{n16}H", raw, 0)
    for i in range(12, n16):
        if u16[i] != 0 and u16[i] != declen:
            return i * 2
    return None


def _plausible_lonlat(lon, lat):
    lon_lo, lon_hi = _ANCHOR_LON_RANGE
    lat_lo, lat_hi = _ANCHOR_LAT_RANGE
    return lon_lo <= lon <= lon_hi and lat_lo <= lat <= lat_hi


def _looks_like_real_chain(raw, lon_pos, declen, k=12, min_distinct_frac=0.55):
    """FIXED this session (see the "FIX, this session" comment block below
    _find_subindex_data_start() for the full writeup of what was wrong and
    why): `lon_pos` is the byte offset of the candidate anchor's int32
    LONGITUDE field (so the delta run being checked starts at lon_pos+8).

    Discriminator: require the next `k` (dx,dy) shorts to be MOSTLY
    DISTINCT values (>= `min_distinct_frac` of the `2*k` samples must be
    unique). A DENSE spatial sub-index's raw cell values, when accidentally
    read as a delta run, are dominated by ONE repeated large value (a
    filled/ramped grid row bottoming out at an unfilled-cell sentinel and
    then staying there) -- e.g. a real sample: `(11075, 41, 11362, 75,
    11437, 41, 11478, 0, 11478, 0, 11478, 0, ...)`, only 8 distinct values
    across 24 samples. Real (dx,dy) polyline deltas essentially never
    repeat like that -- even tiles with legitimately large individual
    gaps (see below) still have close to all-distinct sampled values.

    This REPLACES an earlier flat-magnitude version of this check
    (`thresh=3000`, rejecting any candidate with a delta >= 3000 units in
    the sampled window) that was too aggressive: real large-but-legitimate
    shape-point gaps are common on both mg4 (e.g. a validated 392-point
    Iasi-area chain has individual gaps up to 6,054 units, ~60m) and mp0
    (empirically, real matched chains had a mean peak delta of ~4,441
    units and up to 31,884 units in a sample of ~1,159 confirmed-real mp0
    candidates -- see below), so magnitude alone cannot separate real data
    from sub-index noise. Distinctness can: measured on that same
    confirmed-real/confirmed-fake mp0 sample (1,159 candidates that
    independently exact-matched a named `eeu.rd` road at k=12, vs 2,935
    that didn't), `distinct <= 13` (out of 24 samples, i.e. this function's
    default `min_distinct_frac=0.55` requiring >=14/24) had a **0.00%
    false-reject rate on confirmed-real chains** (0/1,159) while rejecting
    ~23% of the confirmed-fake pool outright (the rest of that pool is
    largely unnamed/unmatched real segments, not further distinguishable
    by content alone -- the old flat threshold, by contrast, falsely
    rejected 832/1,159 = 71.8% of confirmed-real chains when tested the
    same way, which is the mechanism behind the Iasi mis-split bug).
    All 5 hand-inspected pure sub-index echoes in that sample had only
    8 distinct values and were correctly rejected."""
    start = lon_pos + 8
    if start + k * 4 > declen:
        k = (declen - start) // 4
        if k < 4:
            return False
    vals = struct.unpack_from(f"<{k*2}h", raw, start)
    n = len(vals)
    min_required = max(4, math.ceil(min_distinct_frac * n))
    return len(set(vals)) >= min_required


def _find_data_start(raw, declen, k=12, min_distinct_frac=0.55):
    """Generalized data_start finder -- returns the byte offset of the
    2-byte point-count field that precedes the anchor (i.e. the value
    documented in find_tile_anchor()/decode_features() as `data_start`),
    verified with _looks_like_real_chain() so it works on BOTH the sparse
    mg2/mg3/mg4-style sub-index (where the plain sentinel scan already
    finds the right spot almost every time) and the dense mp0-style
    sub-index (where the sentinel scan AND a naive plausible-range brute
    force both false-positive on real grid pointer values -- see
    find_tile_anchor() docstring). Returns None if nothing verifiable is
    found. Tries, in order: (1) the fast structural sentinel-scan result,
    if it passes verification; (2) a brute-force scan for the first
    plausible+verified candidate; (3) as a last resort, the first
    plausible-but-UNVERIFIED candidate (for very short tiles with too few
    trailing deltas to run the smoothness check at all)."""
    data_start = _find_subindex_data_start(raw, declen)
    if data_start is not None:
        p = data_start + 2
        if p + 8 <= declen:
            a = struct.unpack_from("<i", raw, p)[0]
            b = struct.unpack_from("<i", raw, p + 4)[0]
            lon, lat = a / 100000, b / 100000
            if _plausible_lonlat(lon, lat) and abs(lon - lat) > 0.02:
                if _looks_like_real_chain(raw, p, declen, k, min_distinct_frac):
                    return data_start

    for pos in range(24, declen - 8, 2):
        a = struct.unpack_from("<i", raw, pos)[0]
        b = struct.unpack_from("<i", raw, pos + 4)[0]
        lon, lat = a / 100000, b / 100000
        if not (_plausible_lonlat(lon, lat) and abs(lon - lat) > 0.02):
            continue
        if _looks_like_real_chain(raw, pos, declen, k, min_distinct_frac):
            return pos - 2

    for pos in range(24, declen - 8, 2):
        a = struct.unpack_from("<i", raw, pos)[0]
        b = struct.unpack_from("<i", raw, pos + 4)[0]
        lon, lat = a / 100000, b / 100000
        if _plausible_lonlat(lon, lat) and abs(lon - lat) > 0.02:
            return pos - 2

    return None


def find_tile_anchor(raw, declen=None):
    """Recover a single (lon, lat) anchor coordinate (degrees) from ONE
    already-decompressed tile's bytes, using the derived geo-index scheme
    documented above. Returns (lon, lat, method) where method is
    "structural" (the fast, byte-exact rule, delta-smoothness VERIFIED --
    see below), "bruteforce" (fallback scan, smoothness-verified),
    "bruteforce_unverified" (last-resort scan with no smoothness check,
    for tiles too short to run it), or None if nothing was found at all.

    UPDATED (original fix): mp0's spatial sub-index is much DENSER than
    mg2/mg3/mg4's (most grid cells hold a real offset/count value instead
    of an empty-cell sentinel), so both the original structural
    sentinel-scan AND the original plain brute-force range check would
    frequently latch onto a sub-index cell pair that merely LOOKS like a
    plausible (lon,lat) pair by chance (measured: on a random 500-tile mp0
    sample, the old bruteforce-only logic disagreed with the
    then-new verified logic on 246/499 tiles it "resolved" -- i.e. it was
    silently wrong roughly half the time on this file, despite reporting
    success). The fix added `_looks_like_real_chain()`: after finding a
    plausible (lon,lat) candidate, also require the next dozen (dx,dy)
    shorts to look like real polyline deltas, not more sub-index cell
    values.

    UPDATED AGAIN (this session): the original `_looks_like_real_chain()`
    used a flat magnitude cutoff (reject if any of the next 12 deltas had
    |value| >= 3000) as its "looks like real deltas" test. That cutoff
    itself turned out to be wrong in the OTHER direction -- large
    legitimate shape-point gaps are common on real chains (see that
    function's docstring for the numbers), so it was silently mis-locating
    the anchor on plenty of real tiles too, on both mg4 (the canonical
    Iasi 2-feature validation tile, offset 11,298,518, was one such case)
    and mp0. Replaced the magnitude check with a distinct-value/repetition
    check (same function, new default `min_distinct_frac=0.55`) -- see
    `_looks_like_real_chain()`'s docstring for the full rationale and the
    empirical numbers that justified it over magnitude-based alternatives.
    Re-verified end to end after the change:
      - mg4 full-file `build_geo_index()`: still 6,106/6,110 (99.93%,
        byte-identical tile-for-tile with before) -- confirms no
        regression on the sparse-sub-index files.
      - mg4 canonical Iasi tile now correctly decodes as 392+154 points
        (previously mis-split into a bogus 24-point feature).
      - mg4 80-largest-tiles named-road re-scan: 28/80 tiles now show 2+
        features EACH independently exact-matching a different named
        `eeu.rd` road (up from the pre-fix 20/80 -- the increase is
        tiles that were being mis-split by the old magnitude bug and are
        now recovered, not a methodology change).
      - mp0 full-file `build_geo_index()`: still 194,650/194,705 (99.97%)
        -- same raw coverage, but the method mix improved substantially:
        tiles falling through to the unverified last-resort path dropped
        from 2,823 to 45 (i.e. thousands more tiles now get a
        content-verified anchor instead of an unverified guess).
      - mp0 1,500-tile random-sample re-run of the ORIGINAL false-positive
        methodology (comparing against a fully-unverified naive scan):
        the new discriminator disagrees with the naive/no-check scan on
        only 242/1,500 (16.1%) of tiles, vs the OLD magnitude-based fix's
        753/1,500 (50.2%) -- consistent with (reproduces) the original
        246/499 (~49%) measurement. Named-road exact-match hit rate
        (a lower bound on correctness, since many real roads are
        unnamed) across that same sample: NEW 67.1%, OLD (magnitude
        threshold) 44.1%, NAIVE (no verification at all) 55.3% -- i.e.
        the new discriminator is strictly better than both the buggy
        "fixed" version AND the original unguarded scan, confirming it
        fixes the Iasi-style false-negative without reintroducing the
        original mp0 sub-index false-positive problem.

    `declen` defaults to len(raw) (pass it explicitly if `raw` has trailing
    padding beyond the true decompressed tile length)."""
    if declen is None:
        declen = len(raw)

    data_start = _find_subindex_data_start(raw, declen)
    if data_start is not None:
        p = data_start + 2
        if p + 8 <= declen:
            a = struct.unpack_from("<i", raw, p)[0]
            b = struct.unpack_from("<i", raw, p + 4)[0]
            lon, lat = a / 100000, b / 100000
            if _plausible_lonlat(lon, lat) and abs(lon - lat) > 0.02:
                if _looks_like_real_chain(raw, p, declen):
                    return lon, lat, "structural"

    for pos in range(24, declen - 8, 2):
        a = struct.unpack_from("<i", raw, pos)[0]
        b = struct.unpack_from("<i", raw, pos + 4)[0]
        lon, lat = a / 100000, b / 100000
        if not (_plausible_lonlat(lon, lat) and abs(lon - lat) > 0.02):
            continue
        if _looks_like_real_chain(raw, pos, declen):
            return lon, lat, "bruteforce"

    for pos in range(24, declen - 8, 2):
        a = struct.unpack_from("<i", raw, pos)[0]
        b = struct.unpack_from("<i", raw, pos + 4)[0]
        lon, lat = a / 100000, b / 100000
        if _plausible_lonlat(lon, lat) and abs(lon - lat) > 0.02:
            return lon, lat, "bruteforce_unverified"

    return None


def build_geo_index(path):
    """Decompress EVERY tile in a MAP_COMPRESSED file (mp0/mg1-mg4) and
    extract each one's derived anchor coordinate (see scheme documented
    above `find_tile_anchor()`). Returns
        {tile_id: (lon, lat, method)}
    tile_id is the tile's position in `read_directory(path)["entries"]`
    (physical file order), matching every other function in this module.
    Tiles where no plausible anchor could be recovered are OMITTED from the
    dict (check `len(index)` vs `read_directory(path)["num_tiles"]` for
    coverage).

    Coverage, full-file runs (not samples), after the ORIGINAL
    find_tile_anchor() fix (dense-mp0-sub-index false positives):
        eeuz.mg4 (6,110 tiles):    6,106/6,110  (99.93%),  ~7s
        eeuz.mp0 (194,705 tiles): 194,650/194,705 (99.97%), ~55s
    RE-VERIFIED after the LATER fix (magnitude threshold -> distinct-value
    discriminator, see find_tile_anchor()/`_looks_like_real_chain()`):
    coverage is numerically UNCHANGED on both files --
        eeuz.mg4: 6,106/6,110 (99.93%), ~0.4s, byte-identical tile-for-tile
        eeuz.mp0: 194,650/194,705 (99.97%), ~35s
    -- but the underlying method mix improved substantially on mp0: tiles
    resolved only via the unverified last-resort path dropped from 2,823
    to 45 (i.e. thousands of tiles that previously got an unverified guess
    now get a content-verified anchor instead; see find_tile_anchor() for
    the full before/after comparison). Coverage staying flat while method
    quality improves is expected: the ~0.03%/~0.07% of tiles that fail
    entirely are short/degenerate tiles with too little trailing data to
    evaluate any discriminator, unrelated to which discriminator is used.
    mp0 is NOW practical to run in full (previously documented as
    "impractical" -- that was mostly an I/O inefficiency in this function,
    not a fundamental cost: it used to call decompress_tile(), which reads
    a fixed 2MB window per tile regardless of the tile's real size and
    reopens the file every call. This version opens the file once and
    reads exactly `complen` bytes per tile using the directory's own
    compressed-length field, which is enough for zlib to decompress fully
    since tiles are packed back-to-back with no padding)."""
    directory = read_directory(path)
    index = {}
    with open(path, "rb") as f:
        for tile_id, (offset, declen, complen) in enumerate(directory["entries"]):
            f.seek(offset)
            try:
                raw = zlib.decompress(f.read(complen))
            except zlib.error:
                continue
            if len(raw) != declen:
                continue
            result = find_tile_anchor(raw, declen)
            if result is None:
                continue
            lon, lat, method = result
            index[tile_id] = (lon, lat, method)
    return index


def find_tile_for_coord(geo_index, lon, lat):
    """Given a geo_index from build_geo_index(), return the tile_id whose
    anchor coordinate is closest (plain Euclidean distance in degree space
    -- fine for the small regions a single tile covers) to (lon, lat).

    NOTE: this is NEAREST-ANCHOR, not exact bounding-box containment -- we
    have not cracked each tile's width/height, only a single anchor point
    per tile (see module notes above). For picking "a reasonable existing
    tile near this new road" this is good enough in practice; it is not a
    guarantee the returned tile's rendered extent actually covers the exact
    target coordinate at every zoom level. O(n) linear scan -- fine for
    mg2/mg3/mg4 (tens of thousands of entries); build a KD-tree instead if
    you need this on mp0's ~194,705 tiles repeatedly.

    Returns None if geo_index is empty."""
    best_id = None
    best_dist2 = None
    for tile_id, (t_lon, t_lat, _method) in geo_index.items():
        d2 = (t_lon - lon) ** 2 + (t_lat - lat) ** 2
        if best_dist2 is None or d2 < best_dist2:
            best_dist2 = d2
            best_id = tile_id
    return best_id


def _oscillation_events(pairs, min_jump=3000, cancel_ratio=0.03):
    """Core "round-trip" signal shared by both cluster-detection passes
    below: delta index i is flagged if it's a large jump (>= min_jump)
    whose very next delta almost exactly cancels it (net magnitude <=
    cancel_ratio * the jump's own magnitude). This is the ORIGINAL,
    unchanged, already-validated signal from the single-cutoff version of
    this function (see `_find_oscillation_clusters()`'s docstring for the
    concrete tile 9246/9248 numbers this was tuned against) -- kept exactly
    as-is because it is what the Iasi false-positive guard (see below) was
    already proven not to trip on."""
    n = len(pairs) // 2
    events = []
    for i in range(n - 1):
        dx0, dy0 = pairs[2*i], pairs[2*i+1]
        m0 = math.hypot(dx0, dy0)
        if m0 < min_jump:
            continue
        dx1, dy1 = pairs[2*i+2], pairs[2*i+3]
        msum = math.hypot(dx0 + dx1, dy0 + dy1)
        if msum <= cancel_ratio * m0:
            events.append(i)
    return events


def _cluster_events(events, cluster_window=20, min_cluster_events=2):
    """Group event indices into clusters of >= min_cluster_events events
    each within any `cluster_window`-wide span. Returns a list of
    [first_event, last_event] delta-index ranges, in increasing order."""
    if not events:
        return []
    clusters = []
    cur = [events[0]]
    for e in events[1:]:
        if e - cur[-1] <= cluster_window:
            cur.append(e)
        else:
            if len(cur) >= min_cluster_events:
                clusters.append([cur[0], cur[-1]])
            cur = [e]
    if len(cur) >= min_cluster_events:
        clusters.append([cur[0], cur[-1]])
    return clusters


def _extend_cluster_bounds(pairs, a, b, lookback=12, min_jump=2500,
                            cancel_ratio=0.15, max_width=4):
    """Try to grow an already-confirmed cluster [a, b] backward/forward by
    up to `lookback` delta-indices past each boundary, using a LOOSER
    round-trip test (net displacement over up to `max_width` consecutive
    deltas, not just an immediate pair) -- this absorbs a "ramp-up"/
    "ramp-down" pattern of short (1-3 point) same-band runs that often
    precedes a cluster degenerating into strict single-point ping-pong
    (see `_find_oscillation_clusters()`'s docstring, tile 61 example).

    Deliberately only ever EXTENDS an already-confirmed cluster -- it never
    creates one from nothing, so it cannot introduce a false cluster in an
    otherwise-clean stretch (this is what keeps it safe on the Iasi
    reference tile, whose one real large-cancelling jump has no nearby
    confirmed cluster to extend from in the first place)."""
    n = len(pairs) // 2

    def is_roundtrip(i):
        dx0, dy0 = pairs[2*i], pairs[2*i+1]
        m0 = math.hypot(dx0, dy0)
        if m0 < min_jump:
            return False
        for w in range(2, max_width + 1):
            if i + w > n:
                break
            sx = sum(pairs[2*k] for k in range(i, i + w))
            sy = sum(pairs[2*k + 1] for k in range(i, i + w))
            if math.hypot(sx, sy) <= cancel_ratio * m0:
                return True
        return False

    new_a = a
    i = a - 1
    misses = 0
    while i >= 0 and misses < lookback:
        if is_roundtrip(i):
            new_a = i
            misses = 0
        else:
            misses += 1
        i -= 1

    new_b = b
    i = b + 1
    misses = 0
    while i < n and misses < lookback:
        if is_roundtrip(i):
            new_b = i
            misses = 0
        else:
            misses += 1
        i += 1

    return new_a, new_b


def _find_oscillation_clusters(pairs, min_jump=3000, cancel_ratio=0.03,
                                cluster_window=20, min_cluster_events=2):
    """Detect the "oscillating-overrun" signature documented in
    `decode_features()`'s docstring (bug found while rendering a real mg3
    area near Sofia, Bulgaria) and return EVERY corrupted delta-index span
    found anywhere in the block, as a list of (first_bad_delta,
    last_bad_delta) tuples in increasing order, or `[]` if the block looks
    clean throughout. NOT applied by default -- see
    `decode_features(..., trim_oscillation=)` for why this stays opt-in.

    ROOT CAUSE / THE SIGNATURE (unchanged from the original single-cutoff
    version of this function): past the point where real polyline data
    runs out mid-block, the misread bytes produce a run of near-perfectly-
    CANCELLING consecutive delta pairs -- delta i is a huge vector, delta
    i+1 is almost exactly its negation, so points ping-pong between two
    near-fixed positions instead of progressing. On the two originally-
    confirmed-bad tiles (mg3 tile_id 9246, 9248 on the reference disc):
    tile 9246's very first delta is (dx=5, dy=10773) -- a ~12km jump --
    immediately followed by (dx=46, dy=-10814), cancelling to a net
    residual of only 65 units (0.6% of the jump's own magnitude); this
    repeats every few deltas throughout the block. tile 9248 is clean for
    its first 65 deltas and then shows the exact same pattern from index 66
    onward. `_oscillation_events()` implements this exact check, unchanged
    since the original version; `_cluster_events()` groups nearby events
    (>= `min_cluster_events` within any `cluster_window`), also unchanged.

    ⚠→✅ TWO REAL GAPS IN THE ORIGINAL SINGLE-CUTOFF VERSION, FOUND AND
    FIXED THIS SESSION (confirmed by direct testing against real tiles near
    Turin, Italy, mg3 lon=7.71507/lat=45.09368 -- NOT hypothetical):

    Gap 1 -- only the FIRST cluster was ever found, and everything from
    its start onward was unconditionally dropped (truncation), even though
    (a) a SECOND, later cluster can exist further into the SAME block after
    a stretch of real geometry resumes, and (b) an EARLIER cluster can
    exist that the truncation then hid inside the "kept" prefix reported to
    the caller. (b) is directly confirmed and fixed on the reference disc
    (mg3 tile_id 61, below); (a) was also confirmed on mg3 tile_id 1330
    (offset 4,174,363, near Turin: the old single-cutoff scan found NO
    cluster at all there, `truncated` absent, all 193 points kept, because
    a real corrupted region -- delta-index span ~72-89, points oscillating
    between lat ~45.246-45.275 and isolated ~45.21-45.22 spikes, 3-9km
    jumps, while longitude crawls by <400m across the whole span -- sits
    surrounded on both sides by clean, plausible-looking geometry) but
    turned out NOT fixable by this session's cluster-density signal either
    -- see `decode_features()`'s docstring, "tile 1330: NOT FIXED", for
    why: its corruption presents as two SPARSE, isolated round-trip events
    44 delta-indices apart rather than a dense cluster, and those two
    events are numerically indistinguishable from perfectly legitimate,
    widely-spaced real jumps elsewhere in this dataset (the Iasi reference
    tile has three of its own, at similar magnitude and cancellation
    ratio) -- so nothing in this function safely catches tile 1330 without
    also wrongly flagging Iasi. Left as a confirmed, documented remaining
    gap rather than "fixed."
      - mg3 tile_id 61 (offset 534,136, near Turin): the old cutoff landed
        at delta index 89 (kept 90 of 184 points, `truncated: True`) --
        but a SECOND real oscillation is visible from delta index ~84
        onward, alternating point85<->point87<->point89 between lat
        ~44.957 and ~45.037 (an ~8.9km jump, repeated 3x in 6 points)
        while longitude barely moves. The old single-event trigger
        (`_oscillation_events()` above) only fires at delta 88 (the first
        delta whose IMMEDIATE next delta cancels it >=97%); deltas 84 and
        86 are also large jumps but their immediate next delta is a TINY
        same-band step (not a cancellation) rather than the reversal --
        the real cancellation happens two deltas later, meaning this
        cluster actually starts with short (1-2 point) same-band runs
        before it degrades into strict single-point ping-pong. The old
        code kept its "clean" prefix through point 89, i.e. INCLUDING this
        already-corrupted region, because its trigger point (delta 88) is
        past where the visible damage actually starts.

    Gap 2 -- reassembly was pure truncation ("drop everything from the
    cutoff onward"), so a block with real geometry both BEFORE and AFTER a
    corrupted cluster lost the "after" portion entirely, even when it
    independently matched real named roads. This is what caused the
    documented 28/80 -> 17/80 mg4 regression when the old fix was tried as
    a default (see below) -- e.g. mg4 tile_id 2619's 355-point block has
    its (real, per the investigation below) named-road hits BEFORE and
    AFTER a mid-block dense-cancellation cluster; truncating at the
    cluster's start threw away the entire 277-point "after" portion (10
    independently-matched named roads: DN1B, DJ203C, DN2, MIHAI BRAVU,
    ...) along with it.

    FIX: `_find_oscillation_clusters()` (this function) now (1) scans the
    WHOLE delta sequence for every cluster via `_oscillation_events()` +
    `_cluster_events()` (unchanged core signal, so it doesn't stop after
    the first hit), then (2) locally EXTENDS each confirmed cluster's
    boundary backward/forward with `_extend_cluster_bounds()` (a looser,
    wider-round-trip check that only ever grows an EXISTING cluster, never
    creates a new one from nothing -- see that function's docstring for why
    this keeps it safe on clean data) to absorb short same-band ramp-up/
    ramp-down runs like tile 61's, then (3) merges any clusters that now
    overlap after extension. `decode_features()` then reassembles by
    SPLITTING the block into separate surviving sub-features around each
    cluster (dropping only that cluster's own point range) instead of
    truncating everything from the first cluster onward -- see
    `decode_features()`'s docstring for the reassembly details and the
    concrete before/after point counts on all 4 confirmed-bad tiles.

    ⚠ STILL UNRESOLVED, same as before -- classifying a SPECIFIC cluster
    as "real long chain that happens to double back" vs "misread bytes" is
    NOT solved by this fix and this session confirmed (again, by direct
    testing, not just re-reading the old caveat) that it may not be
    solvable from tile-local delta statistics at all: mg4 tile_id 2619's
    dense-cancellation cluster (deltas ~42-77, 3 back-to-back near-total-
    cancellation pairs, magnitude/density indistinguishable from the
    confirmed-bad tiles) turns out, on close inspection, to be two
    genuinely smooth, independently-progressing sub-tracks interleaved
    point-by-point (one at lat ~44.80-44.83 monotonically decreasing, one
    at lat ~44.95 with real named-road hits DC67/DJ102C/DN1B threaded
    through it) -- a real, if visually alarming, GIS pattern (plausibly two
    adjacent named roads sharing a topological edge in the source graph),
    NOT corruption. Several geometric discriminators were tried this
    session to separate this from genuine corruption (two-track parity/
    nearest-tail splitting + per-track coherence, sticky-revisit diameter
    checks, direction-reversal-fraction checks with and without a noise
    floor) and every one either still misclassified this cluster as
    corrupt, or -- once loosened enough to accept it -- ALSO accepted
    confirmed-bad tiles (e.g. mg3 tile 1328, whose corrupted range shows
    the same kind of "smooth-looking sub-track" artifact by construction
    once you allow a greedy 2-way split, since any greedy nearest-neighbor
    partition of a finite point set tends to look locally smooth whether
    the underlying data is real or not). No further attempt at a
    per-cluster real/fake classifier is shipped this session; see
    `decode_features()`'s docstring and README §3.6/§8 for the practical
    consequence (this keeps `trim_oscillation` opt-in, not default) and
    the actual measured numbers -- the split-instead-of-truncate fix from
    Gap 2 above, on its own and WITHOUT solving this classification
    problem, already recovers most of the previously-lost named-road hits
    in the false-positive tiles, because the "after" (and "before")
    portions of an incorrectly-flagged cluster now survive as their own
    sub-features even when the cluster itself still gets dropped.

    Returns a list of (first_bad_delta_index, last_bad_delta_index) tuples,
    already extended and merged, in increasing order; `[]` if the block has
    no detected oscillation anywhere."""
    events = _oscillation_events(pairs, min_jump=min_jump, cancel_ratio=cancel_ratio)
    clusters = _cluster_events(events, cluster_window=cluster_window,
                                min_cluster_events=min_cluster_events)
    if not clusters:
        return []
    extended = [_extend_cluster_bounds(pairs, a, b) for a, b in clusters]
    extended.sort()
    merged = []
    for a, b in extended:
        if merged and a <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    return merged


def decode_features(raw, declen=None, max_features=20000, max_points_per_feature=5000,
                     trim_oscillation=False):
    """CRACKED (this session): split a tile's coordinate region into its
    individual polyline FEATURES instead of treating it as one continuous
    chain (see decode_vertex_chain()'s long-standing limitation).

    Format, confirmed by exact-coordinate cross-validation against eeu.rd
    (see below): starting at the tile's `data_start` (see
    _find_subindex_data_start()), the coordinate region is a sequence of
    self-delimiting FEATURE BLOCKS packed back-to-back with NO padding:

        offset +0: uint16 LE point_count (N) -- the number of (dx,dy)
                   deltas in THIS block only (not a tile-wide total; this
                   is the same field previously mis-documented as an
                   "undecoded 2-byte tag" before the anchor -- it is
                   actually this block's own delta-pair count)
        offset +2: int32 LE anchor longitude, degrees = value/100000
        offset +6: int32 LE anchor latitude,  degrees = value/100000
        offset +10: N * (int16 LE dx, int16 LE dy), cumulative from the
                   anchor, same /100000 scale (as decode_vertex_chain())
        -> block size = 10 + 4*N bytes; the NEXT feature block (if any)
           starts immediately at this exact byte offset.

    Blocks are read greedily until the next candidate block's anchor
    fails a geographic plausibility check (see _plausible_lonlat()) or the
    read would run past `declen` -- that byte offset is where the
    coordinate region ends and the still-undecoded ~10-byte tagged
    per-vertex record table (topology/attributes, tag bytes like
    `22 04`/`43 04`/`63 04`, see README open problem) begins. This is a
    HEURISTIC stopping rule, not a hard tile-wide feature count read from
    the file -- see caveat below.

    VALIDATED at scale: scanning the 80 largest-declen tiles in eeu(z).mg4
    and exact-integer-matching every decoded vertex of every decoded
    feature against eeu.rd's own (lon,lat) int32 fields (bit-exact, no
    float rounding -- same standard as the original single-feature "DC158"
    validation), 28/80 tiles produced 2+ features that EACH independently
    landed an exact hit on a DIFFERENT real named road -- i.e. two or more
    genuinely separate polylines correctly recovered from one tile's
    packed coordinate region, not one long chain that happens to pass near
    several roads. (This figure was re-measured after fixing the
    `_find_data_start()` magnitude-threshold bug described below -- it was
    originally reported as 20/80; the 8-tile increase is tiles that were
    being silently mis-split by that bug and are now decoded correctly,
    not a change in methodology.) Cleanest example: eeuz.mg4 tile at file
    offset 11,298,518 (declen 10,386) decodes to exactly 2 features -- a
    392-point chain that exact-matches 10 distinct named roads near Iasi,
    Romania along its length (DC138, DN28 x3, PETRU PONI, ION NECULCE,
    GARABET IBRAILEANU, ION CREANGA, STADION, PETRU GROZA, MATEI CORVIN,
    NEAGOE BASARAB, VLAD TEPES, MIHAI VITEAZU) and an independent 154-point
    chain that exact-matches 2 different named streets (ROZELOR,
    NARCISELOR) -- both starting from anchors ~370m apart in the same
    tile. This is also this module's regression test for the
    magnitude-threshold bug fix (see below): this exact tile used to
    mis-split into a bogus 24-point feature at byte 824 and now correctly
    splits at byte 326 into 392+154 points. Also seen at tile-scale in
    eeu(z).mg4 tiles 1245, 4740, 5152, 1763, 1758, 2394, 5154, 1811, 3309,
    1267, 4071, 2629, 3294, 1268, 3771, 225, 187, 4058, 3536 (per-tile
    counts vary from 2 to 120 blocks).

    FIXED (was: "KNOWN BUG"): earlier versions of `_find_data_start()`'s
    verification step (`_looks_like_real_chain()`) used a flat delta
    magnitude threshold that rejected legitimate large shape-point gaps,
    causing this function to mis-split some tiles (the Iasi tile above was
    the canonical example). Replaced with a distinct-value/repetition
    discriminator -- see `_looks_like_real_chain()`'s docstring for the
    mechanism and the empirical numbers (0% false-reject rate on ~1,159
    confirmed-real mp0 candidates, vs 71.8% for the old magnitude
    threshold, while still correctly rejecting sub-index echoes). Full
    mg4 (6,106/6,110) and mp0 (194,650/194,705) `build_geo_index()`
    coverage is unchanged after the fix; see `find_tile_anchor()`'s
    docstring for the complete before/after numbers.

    CAVEAT (still open, unrelated to the fix above): the greedy
    plausibility-based stop can occasionally accept a few small (0-6
    point) TRAILING blocks with no corresponding eeu.rd record at all
    before it finally hits real tagged-record bytes and stops -- seen e.g.
    in mg4 tile_id 4284, which parses as 12 "blocks" but only blocks #0
    (306 pts) and #11 (109 pts) exact-match named roads; blocks #1-10
    (0-6 points each) match nothing in eeu.rd, even loosely. These may be
    genuine tiny unlabeled stub/connector road segments (plausible --
    Navteq data has many), or they may be a few bytes of the topology
    table that happen to still look like a valid tiny block by chance.
    Either way this does NOT affect the validated LARGE/real features
    (their block boundaries are exact), but it means "number of blocks
    returned" is not a fully reliable feature count in isolation -- treat
    trailing tiny/unmatched blocks with suspicion, especially for
    round-tripping (deleting/reordering features), less so for pure
    appending (see README open problem #5 for the still-uncracked
    topology-table semantics, which is the remaining piece needed to
    KNOW this for certain rather than infer it statistically).

    ⚠→~ Oscillating-overrun bug -- FOUND, root-caused, IMPROVED this
    session (multi-cluster scan + split reassembly), STILL opt-in only.
    Found while building the map viewer (`rns510_map_viewer.py`) and
    rendering a real area near Sofia, Bulgaria (mg3, lon=23.33750/
    lat=42.69055): two of the pooled features near that point (declared
    counts 241 and 239, i.e. mg3 tile_ids 9248 and 9246 on the reference
    disc) contained huge (24-33km) single-step jumps, oscillating back and
    forth between two near-fixed latitude bands while longitude crept
    slowly forward -- a shape no real road produces. ROOT CAUSE, with
    concrete byte evidence (full writeup: `_find_oscillation_clusters()`'s
    docstring): this is NOT the already-documented "a feature legitimately
    chains several distinct named roads together" behaviour in the
    ordinary sense (that specific hypothesis was tested and REJECTED for
    these two tiles -- exact-coordinate cross-referencing ALL 8 jump
    endpoints against the full 8,809,081-record `eeu.rd` found zero
    matches, whereas the genuine Iasi chaining example elsewhere in this
    docstring matches 10-12 real named roads). Both bad blocks' anchors and
    first ~12 sampled deltas legitimately pass `_find_data_start()`'s
    `_looks_like_real_chain()` distinctness check (that check only samples
    a small window right at the candidate anchor), but LATER in the SAME
    declared block -- at delta index 66 for tile 9248 (real geometry for
    indices 0-~65), immediately at delta index 0 for tile 9246 (no real
    geometry precedes it at all) -- the bytes being read as (dx,dy) stop
    being real polyline data and start being some other, still-
    unidentified fixed-stride binary structure. `decode_features()`'s main
    loop never re-validates a block's content once its `point_count` field
    has been read -- it walks exactly `count` more (dx,dy) pairs no matter
    what they look like, so once real geometry runs out mid-block, nothing
    catches the transition and the whole rest of the declared count gets
    decoded as bogus vertices.

    ⚠→✅ TWO CONCRETE GAPS IN THE ORIGINAL (single-cutoff, truncate-only)
    MITIGATION, found this session by direct testing against real tiles
    near Turin, Italy (mg3, lon=7.71507/lat=45.09368) -- summarized here,
    full detail in `_find_oscillation_clusters()`'s docstring:
      1. Only the FIRST cluster in a block was ever found (the scan
         stopped there), so a SECOND, later cluster elsewhere in the same
         block (mg3 tile 1330, offset 4,174,363 -- `truncated` wasn't even
         set, all 193 points kept, corruption at delta-index ~72-89 missed
         entirely) or an EARLIER cluster hidden inside what got reported as
         the "clean, kept" prefix (mg3 tile 61, offset 534,136 -- old
         cutoff kept 90 of 184 points, but a real oscillation is visible
         from ~point 85 onward, INSIDE that "kept" prefix) went undetected.
      2. Reassembly was pure truncation (drop everything from the cutoff
         onward), so real geometry AFTER a corrupted cluster was discarded
         even when it independently matched real named roads -- the
         mechanism behind the previously-measured 28/80 -> 17/80 mg4
         regression (see below).

    FIX: `_find_oscillation_clusters()` scans the WHOLE delta sequence for
    every cluster (not just the first) and locally extends each one's
    boundary to absorb short ramp-up/ramp-down runs (fixes tile 61);
    `decode_features()` (this function) now SPLITS a block into separate
    surviving sub-features around each detected cluster -- dropping only
    that cluster's own point range and keeping the "before"/"between"/
    "after" runs as independent output features -- instead of truncating
    everything from the first cluster onward (fixes tiles 61 and 9248's
    lost tails, and substantially mitigates the 28/80 -> 17/80 regression:
    see numbers below).

    MEASURED RESULTS on the 4 confirmed-bad Turin-area tiles (mg3, offsets
    as above) plus the 2 original Sofia tiles, with `trim_oscillation=True`:
      - tile 61:    184 pts, 1 block -> 3 sub-features (85, 24, 28 pts);
                    the 84-89 oscillation that used to hide inside the old
                    90-point "kept" prefix is now excised (prefix ends at
                    point 84) -- FIXED.
      - tile 1328:  106 pts, 1 block -> 2 sub-features (2, 6 pts); this
                    block is corrupt almost throughout (multi-band, not a
                    clean 2-track oscillation), so most of it is dropped,
                    same as the old cutoff's own 11-point "kept" prefix
                    already implied but now the tiny 100-105 tail also
                    survives instead of being silently discarded -- FIXED
                    (already caught by the old code too, now with a better
                    tail).
      - tile 51:    2 blocks (57, 16 pts), NEITHER touched -- no clusters
                    found by the new scan either, matching the "should stay
                    clean" expectation confirmed via direct re-inspection.
      - tile 9246:  240 pts, 1 block -> 1 surviving sub-feature (177 pts,
                    dropping the corrupt prefix) -- FIXED (already caught
                    by the old code too).
      - tile 9248:  242 pts, 1 block -> 2 sub-features (66, 3 pts) --
                    matches the original "clean for ~65, corrupt after"
                    finding, now with the small tail recovered too instead
                    of dropped -- FIXED.
      - tile 1330:  193 pts, 1 block -> **NOT FIXED, confirmed remaining
                    gap**: `_find_oscillation_clusters()` finds only 2
                    isolated strict events here (delta index 38, magnitude
                    3379, 98.9% cancellation; delta index 82, magnitude
                    5024, 98.5% cancellation), 44 delta-indices apart --
                    too far apart to form a cluster under the validated
                    `cluster_window=20` (this tile's corruption is a
                    SPARSE run of isolated round-trip spikes, unlike tile
                    61/9246/9248's DENSE clusters). Widening
                    `cluster_window` to catch it (tried: 50) DOES catch it,
                    but ALSO merges the Iasi reference tile's THREE
                    separate, individually-legitimate large-cancelling
                    jumps (delta indices 30/52/93, magnitudes 3288-3747,
                    98.7-99.3% cancellation -- numerically indistinguishable
                    from tile 1330's) into one bogus cluster spanning most
                    of its validated 392-point chain. Since the Iasi
                    no-flag guarantee is a hard requirement, the safe
                    `cluster_window=20` was kept and tile 1330 is
                    knowingly left uncorrected -- a second, independent
                    confirmation (beyond tile 2619's, see below) that
                    single-event delta magnitude/cancellation-ratio alone
                    cannot separate real widely-spaced chaining jumps from
                    corruption; only clustering DENSITY does, and tile
                    1330's corruption doesn't happen to present densely.

    ⚠ STILL UNRESOLVED (unchanged conclusion, now backed by MORE evidence,
    not less): classifying a SPECIFIC cluster as "real long chain that
    happens to double back" vs "misread bytes" remains unsolved from
    tile-local statistics alone -- see `_find_oscillation_clusters()`'s
    docstring for the concrete mg4 tile 2619 counter-example (a real,
    smooth, two-track interleaved chain with real named-road hits threaded
    through the exact same statistical signature) and the several
    discriminators tried and rejected this session. Because of this,
    `trim_oscillation` remains OPT-IN, not default (see Args below) --
    but the split-instead-of-truncate reassembly fix, EVEN WITHOUT solving
    that classification problem, substantially recovers the previously
    lost false-positive named-road hits: re-running the mg4 tile_id
    2619/4125/2629/4645 false-positive investigation from the original fix
    with the NEW split logic, every one of them still has its
    (mis-)flagged cluster dropped, but the "before"/"after" survivors keep
    matching real named roads (e.g. tile 2619's 272-point "after" survivor
    alone still matches 10 distinct real roads: DN1B, DJ203C, DN2, MIHAI
    BRAVU, ...). Full 80-tile re-scan number: see below.

    RE-VALIDATED at the same 80-largest-mg4-tiles scale as the original
    28/80 (no trim, reproduced exactly with this session's own re-run of
    the methodology, using STRICT exact-integer eeu.rd matching only, no
    nearest-tolerance fallback) / 17/80 (old truncate-only trim) numbers:
    the NEW split-based `trim_oscillation=True` scores **42/80** -- not
    just a recovery from 17/80, but an outright improvement over the
    untrimmed 28/80 baseline. Only ONE tile regresses (mg4 tile_id 187:
    its 84-point block legitimately matched 2 real roads, CODA DEL SAVUTO
    and ALTILIA-GRIMALDI, but the matching vertices sat inside a cluster
    that the new scan (correctly or not -- undetermined) flags and drops,
    so no surviving fragment of that block keeps either name -- a second,
    independently-observed instance of real content loss, on top of the
    already-documented tile 2619-style ambiguity). 15 tiles are newly
    gained (e.g. tile_id 4125, one of the ORIGINAL false-positive tiles
    from the old fix, is now counted as a hit rather than a loss, since
    its split-out survivors keep matching M1/M10/M12/TORGOVAYA/etc.).
    CAVEAT on the 42/80 figure: some of the gain is a byproduct of
    splitting increasing the number of features per tile (a single long
    chain crossing several real named roads becomes several shorter
    surviving fragments, each more easily satisfying "matches its own
    distinct named road" than the one long original chain needed to) --
    this metric was always a proxy, not a perfect ground truth, and that
    proxy is now easier to satisfy structurally as well as by genuine
    correctness. Weighed against that caveat, this session's decision
    (see README §3.6/§8) is: keep `trim_oscillation` OPT-IN, not default,
    because (a) real content loss is still directly demonstrated (tile
    187), (b) the per-cluster true/false-positive classification problem
    remains genuinely unsolved (not just "rare" -- tile 2619 and tile 1330
    are both concrete, reproducible counter-examples to any simple fix),
    and (c) the new implementation is unambiguously the right choice
    WHENEVER trim_oscillation is already being used (it strictly
    dominates the old truncate-only version on every measured axis).

    ⚠ UPDATE (README §10 "v15 -> v16"): `rns510_map_viewer.py` no longer
    defaults to `trim_oscillation=True` either. A direct, real-ISO,
    per-named-road investigation (going beyond this docstring's own
    tile-name-match-count proxy) found the filter net NEGATIVE for real
    dense-urban rendering at the zoom levels the viewer is actually used
    at: a real Sofia, Bulgaria `mg1` sample (9 tiles) had 6 entire real
    named roads deleted and 13 more truncated -- including Sofia's own
    ring road, "OKOLOVRASTEN PAT", losing 84.6% of its matched points --
    for only a 5.74% raw-point reduction, directly confirming a real
    user's own first-hand observation that the "garbage" being hidden was
    often real road geometry. The 42/80 mg4 tile-count metric this
    docstring uses cannot see that failure mode: it only asks whether 2+
    named roads match ANYWHERE in a tile, not whether any SPECIFIC real
    road's geometry survives intact, and mg1 (a finer, more commonly-
    viewed-at layer than the mg4 sample this metric was built on) is
    exactly where the loss concentrates. The viewer's "Hide decode
    garbage" checkbox (`App.hide_garbage_var`/`MapData.trim_oscillation`)
    still exists and still works exactly as before for inspection/
    comparison -- it is simply UNCHECKED by default now, matching this
    library function's own default below, instead of being turned on by
    the caller.

    Args (new):
        trim_oscillation: if True, run `_find_oscillation_clusters()` on
            every block and split it into separate surviving sub-features
            around each detected cluster (dropping only that cluster's own
            point range), instead of decoding the full declared
            point_count unconditionally. Default False (preserves the
            validated 28/80 mg4 baseline exactly, byte-for-byte, and now
            also matches `rns510_map_viewer.py`'s own default as of
            README §10 "v15 -> v16" -- see UPDATE above). Turning it on
            can still be useful for side-by-side INSPECTION of what the
            filter would remove (the viewer's checkbox does this on
            request), but do NOT turn it on by default for anything
            correctness-sensitive (editing, round-tripping, topology-table
            work) OR for general display/visualization without re-reading
            both `_find_oscillation_clusters()`'s docstring and the
            "v15 -> v16" UPDATE above for the full false-positive
            evidence first.

    Returns a list of dicts, one per decoded (sub-)feature, in file order
    (a single declared block can now produce MULTIPLE dicts if
    trim_oscillation=True and it contained 1+ oscillation clusters):
        {"offset": <int, byte offset of this block's count field --
                    SHARED by every sub-feature split out of the same
                    block>,
         "count": <int, number of deltas actually in THIS sub-feature's
                   "points" list -- for an untouched block this is the
                   block's own declared N; for a split-out sub-feature
                   this is just that fragment's own length - 1>,
         "block_end": <int, byte offset where the next block starts --
                       shared by every sub-feature split out of this one>,
         "points": [(lon, lat), ...],
         "point_range": <(start, end) tuple, the ORIGINAL block-local point
                         indices this sub-feature covers -- only present
                         when trim_oscillation=True AND the block had 1+
                         clusters (whether or not this exact fragment is
                         the first)>,
         "truncated": <bool True -- only present under the same condition
                       as "point_range" above, on EVERY sub-feature split
                       out of an affected block (not just non-first ones),
                       meaning "this is a fragment of a block that had
                       oscillation removed from it"; absent (not set) for
                       an untouched block>}
    """
    if declen is None:
        declen = len(raw)
    data_start = _find_data_start(raw, declen)
    if data_start is None:
        return []

    features = []
    pos = data_start
    while pos + 10 <= declen and len(features) < max_features:
        count = struct.unpack_from("<H", raw, pos)[0]
        lon0_i = struct.unpack_from("<i", raw, pos + 2)[0]
        lat0_i = struct.unpack_from("<i", raw, pos + 6)[0]
        lon0, lat0 = lon0_i / 100000, lat0_i / 100000
        block_end = pos + 10 + count * 4
        if not _plausible_lonlat(lon0, lat0):
            break
        if count > max_points_per_feature or block_end > declen:
            break
        pairs = struct.unpack_from(f"<{count*2}h", raw, pos + 10)

        pts = [(lon0_i, lat0_i)]
        clon, clat = lon0_i, lat0_i
        for i in range(count):
            dx, dy = pairs[2*i], pairs[2*i+1]
            clon += dx
            clat += dy
            pts.append((clon, clat))

        clusters = _find_oscillation_clusters(pairs) if trim_oscillation else []
        if not clusters:
            if len(pts) >= 2:
                features.append({
                    "offset": pos,
                    "count": count,
                    "block_end": block_end,
                    "points": [(lon / 100000, lat / 100000) for lon, lat in pts],
                })
        else:
            # Split the block into surviving sub-features around each
            # cluster: drop point-range [a+1, b+1] (the flagged delta
            # span's own excursion points) per cluster, keep the
            # before/between/after runs as separate output features --
            # see _find_oscillation_clusters()'s docstring for why this
            # replaces truncate-from-the-first-cluster-onward.
            sub_ranges = []
            prev = 0
            last_idx = len(pts) - 1
            for a, b in clusters:
                bad_start = a + 1
                bad_end = min(b + 1, last_idx)
                if bad_start > prev:
                    sub_ranges.append((prev, min(a, last_idx)))
                prev = bad_end + 1
            if prev <= last_idx:
                sub_ranges.append((prev, last_idx))

            for s, e in sub_ranges:
                if e - s + 1 < 2:
                    continue
                sub_pts = pts[s:e + 1]
                features.append({
                    "offset": pos,
                    "count": e - s,
                    "block_end": block_end,
                    "points": [(lon / 100000, lat / 100000) for lon, lat in sub_pts],
                    "point_range": (s, e),
                    "truncated": True,
                })
        pos = block_end
    return features


def decode_vertex_chain(raw, declen=None, max_points=200):
    """Decode the (dx,dy) delta-coordinate run immediately following a
    tile's anchor (see find_tile_anchor()) into a list of ABSOLUTE (lon,
    lat) vertex coordinates. Requires the "structural" data_start rule to
    have located the anchor (i.e. only works when find_tile_anchor() would
    return method=="structural"); returns None if that rule doesn't apply
    to this tile.

    CONFIRMED this session: the delta run uses the SAME /100000 degrees
    scale as the anchor itself (int16 LE dx, then int16 LE dy, cumulative).
    Validated by decoding eeuz.mg4 tile_id 2231 (file offset 6,121,146,
    anchor 21.20056E/45.58739N near Timisoara, Romania) and finding its
    first resulting vertex, (21.20062, 45.58711), is an EXACT match (to 5
    decimal places) for a real eeu.rd road record named "DC158" at
    (21.20062, 45.58711) -- strong confirmation of both the anchor offset
    and the delta scale/encoding.

    SUPERSEDED by decode_features() (see below), which now correctly
    splits a multi-feature tile's coordinate region into separate
    polylines using the point-count field this function ignores (it just
    reads (declen-start)//4 pairs, i.e. everything left in the tile, which
    is only correct for a tile whose first feature IS the whole rest of
    the tile). Kept for backward compatibility; prefer decode_features()
    for anything multi-feature-aware, e.g. decode_features(raw, declen)[0]
    for "just the first feature"."""
    if declen is None:
        declen = len(raw)
    data_start = _find_subindex_data_start(raw, declen)
    if data_start is None:
        return None
    p = data_start + 2
    if p + 8 > declen:
        return None
    lon0 = struct.unpack_from("<i", raw, p)[0] / 100000
    lat0 = struct.unpack_from("<i", raw, p + 4)[0] / 100000
    if not _plausible_lonlat(lon0, lat0):
        return None

    start = p + 8
    n_pairs = min(max_points, (declen - start) // 4)
    if n_pairs <= 0:
        return [(lon0, lat0)]
    pairs = struct.unpack_from(f"<{n_pairs * 2}h", raw, start)

    points = [(lon0, lat0)]
    clon, clat = lon0, lat0
    for i in range(n_pairs):
        dx, dy = pairs[2 * i], pairs[2 * i + 1]
        clon += dx / 100000
        clat += dy / 100000
        points.append((clon, clat))
    return points


# ---------------------------------------------------------------------------
# FIXED (this session; was a "KNOWN BUG" note found while investigating
# decode_topology() below): _looks_like_real_chain()'s old default
# `thresh=3000` flat magnitude cutoff was too strict for some REAL chains
# and caused _find_data_start()/decode_features() to silently return a
# WRONG feature split on at least one tile that is this module's own
# canonical validated example: eeuz.mg4 tile at file offset 11,298,518
# (declen 10,386 -- the "392+154 points, 10 named Iasi roads" tile
# documented above). That tile's real first delta run legitimately
# contains jumps up to 6,054 units (~60m, a normal shape-point gap on a
# road with sparse vertices; 24 of its 391 deltas exceed 3,000), which
# exceeded thresh=3000 and failed verification -- so _find_data_start()
# rejected the CORRECT structural candidate at data_start=326 and fell
# through to a WRONG bruteforce match at byte 824 (a false anchor with
# only 24 spurious "points"). Confirmed at the time by comparing against
# the OLD pre-_looks_like_real_chain logic (_find_subindex_data_start()
# alone), which still got this tile right.
#
# FIX: replaced the flat magnitude threshold with a distinct-value/
# repetition discriminator in _looks_like_real_chain() (same function,
# new default `min_distinct_frac=0.55` -- see its docstring for the full
# mechanism and empirical numbers). Rationale in short: real (dx,dy)
# deltas can legitimately be large (both the Iasi tile above and, at
# scale, confirmed-real mp0 chains routinely exceed 3,000, some over
# 30,000), so magnitude cannot separate real chains from sub-index noise
# -- but a dense sub-index's cell values, when misread as a delta run,
# are dominated by ONE repeated/ramped-then-flat value in a way real
# geometry never is. This was verified, not assumed, against both known
# failure modes before landing: re-ran the full eeuz.mg4 (6,110 tiles,
# unchanged 6,106/6,110 coverage, byte-identical) AND a large eeuz.mp0
# sample (the fix does not reintroduce the original mp0 sub-index
# false-positive problem -- named-road hit-rate on a 1,500-tile sample
# went UP, from 44.1% under the old magnitude threshold to 67.1% under
# the new discriminator, both improving on the 55.3% hit-rate of doing no
# verification at all). Full numbers: find_tile_anchor()'s docstring.
# decode_features() now correctly splits the Iasi tile as 392+154 points,
# and _find_subindex_data_start()-only workarounds (as previously used
# for topology-table analysis on known multi-feature tiles) are no longer
# necessary -- decode_features()/_find_data_start() can be trusted directly.
# ---------------------------------------------------------------------------


def decode_tile_header(raw):
    """NEW (this session) -- partial decode of the previously-"undecoded
    0x02-0x17 per-tile header" (12 little-endian uint16 words, byte offsets
    2-23; byte 0-1 is the already-known 0x0146 magic). Validated by exact
    cross-reference against decode_features()/decode_topology() output on
    BOTH reference tiles (single-feature eeuz.mg4 offset 5,138,331 and the
    2-feature "Iasi" tile at offset 11,298,518) -- these are small integers
    (order 10^2-10^4) that were previously ruled out as anchor candidates
    (correctly -- they are NOT geo-coordinates) but never otherwise
    explained. Confirmed field meanings (word index -> byte offset):

        word[1]  (byte 2 ): feature 0's point count (== len(features[0]["points"]))
        word[2]  (byte 4 ): feature 0's block_end (== features[0]["block_end"])
        word[3]  (byte 6 ): COUNT of a small 3-byte-per-entry array that sits
                             between feature 0's block_end and its topology
                             table (see decode_topology_gap() below) --
                             0 on the 2-feature tile (matching the observed
                             ZERO-gap table placement documented in
                             decode_topology()), 4 on the single-feature
                             tile (matching its previously "unidentified
                             104-byte gap", of which this array's 12 bytes
                             are now explained -- see decode_topology_gap()).
        word[4]  (byte 8 ): END byte offset of that same array (word[2] +
                             3*word[3] exactly, on both tiles) -- equals
                             word[2] again when word[3]==0.
        word[5]  (byte 10): on the 2-feature tile, exactly the SECOND
                             feature's point count (154) -- plausibly "next
                             feature's point count, 0/absent if none", but
                             the single-feature tile's value here (24) does
                             NOT fit that pattern (24 has no confirmed
                             meaning for a tile with no second feature) --
                             UNRESOLVED, only 1/2 tiles support this reading.
        word[9]  (byte 18): repeats word[1] (feature 0's point count again)
                             on both tiles -- confirmed but redundant.
        word[10] (byte 20): CLOSE but not exact -- on the single-feature
                             tile this equals feature 0's topology
                             table_end exactly (768+84*10=1608); on the
                             2-feature tile it equals the byte offset of a
                             single anomalous, large-valued trailing record
                             immediately after feature 0's 392 plausible
                             body records (offset 6442, tag "2e17", fields
                             (512,0,255)) -- i.e. NOT simply "table_end" in
                             both cases (table_end there is 6452, 10 bytes
                             later). UNRESOLVED which reading is "the" rule;
                             may indicate feature 0's real per-point body is
                             392 records starting AT table_start (2522) with
                             NO separate leading header slot on this tile,
                             vs. the single-feature tile which DOES have a
                             distinct leading header record (offset 768,
                             large/weird values) before its 83 real body
                             records start at 778 -- i.e. whether a
                             feature's table has a separate "header record"
                             in front of its per-point records may itself be
                             tile/feature-dependent, not universal (see
                             decode_topology()'s docstring for the
                             corroborating record-content evidence: tile B
                             feature 0's own record[0] has SMALL plausible
                             values (146,147), unlike tile A's record[0]).
        word[11] (byte 22): the topology table's total DISTINCT node-id
                             count for that feature (from graph_degree, see
                             decode_topology()) -- matched EXACTLY on the
                             single-feature tile (105 vs computed 105) and
                             within 1 on the 2-feature tile (547 vs computed
                             546) -- the off-by-one on the second tile is
                             unexplained (possibly an edge-extraction
                             boundary artifact in decode_topology()'s own
                             degree-counting, not necessarily a header
                             decode error).
        word[0]  (byte 0 ): == data_start (already known, see
                             _find_subindex_data_start()).
        word[6],[7],[8] (bytes 12,14,16): word[6]/[8] both repeat the same
                             value (778 on tile A, 2522 on tile B) -- see
                             word[10] discussion above, this looks like it's
                             the SAME "boundary offset" concept duplicated;
                             word[7] is 0 on both tiles (unexplained,
                             possibly padding).

    Practical effect: the "104-byte unidentified gap" noted in
    decode_topology()'s docstring for the single-feature reference tile is
    NO LONGER fully unidentified -- its first 12 bytes are a real, header-
    described 4-entry array (see decode_topology_gap()); the remaining 92
    bytes (676-768) are still unexplained (tried treating them as 23 more
    (dx,dy) int16 pairs continuing the coordinate delta run -- produces
    implausible jumps up to +/-17,728 units, i.e. NOT geometry; rejected).

    Returns a dict of the 12 raw word values (byte offsets 0,2,4,...,22 ->
    keys w0..w11) plus the confirmed-name aliases where a meaning is
    established. Callers needing byte-exact values for other tiles should
    treat every field beyond w0/w1/w2/w3/w4/w9 as UNVERIFIED beyond these
    two reference tiles."""
    words = struct.unpack_from("<12H", raw, 0)
    return {
        "w0_data_start": words[0],
        "w1_feature0_point_count": words[1],
        "w2_feature0_block_end": words[2],
        "w3_gap_array_count": words[3],
        "w4_gap_array_end": words[4],
        "w5_unresolved": words[5],
        "w6_boundary_offset_a": words[6],
        "w7_unresolved_zero": words[7],
        "w8_boundary_offset_b": words[8],
        "w9_feature0_point_count_repeat": words[9],
        "w10_boundary_offset_or_table_end": words[10],
        "w11_node_count_approx": words[11],
        "raw_words": words,
    }


def decode_topology_gap(raw, header=None):
    """NEW (this session) -- decode the small 3-byte-per-entry array that
    sits between feature 0's coordinate block_end and its topology table
    (see decode_tile_header()'s word[3]/word[4] for how its count/end
    offset are read directly from the tile header, and decode_topology()'s
    docstring for the "104-byte unidentified gap" this partially explains).

    Format: `count` entries (count = header's w3_gap_array_count) of
    `[uint16 LE value][uint8 flag]`, starting immediately at feature 0's
    block_end. Validated on the single-feature reference tile (eeuz.mg4
    offset 5,138,331): count=4, entries [(14,1),(41,1),(44,1),(77,1)],
    ending exactly at byte 676 == header's w4_gap_array_end. On the
    2-feature Iasi tile, count=0 (array is empty, consistent with that
    tile's previously-documented ZERO-gap table placement).

    MEANING OF THE VALUES: UNRESOLVED. Tested and REJECTED this session:
    (a) they are NOT point-indices where feature 0's decoded chain crosses
    a DIFFERENT named eeu.rd road (checked all 4 values -- 14, 41, 44, 77 --
    against feature 0's own decoded (lon,lat) at those point indices;
    only index 77 landed an exact eeu.rd coordinate hit, and that road
    (Swedish "E4") is plausibly just feature 0's OWN name, not a crossing
    road, so this is not confirmed as a junction marker); (b) they do not
    obviously correspond to the topology graph's own degree-3+ (junction)
    node-ids for this tile (which are {0,1,13,15,17,25,30,45,68,87,92,97,
    103} -- no direct/off-by-one match to {14,41,44,77}). The constant
    trailing flag byte (always 1 in the one example decoded) suggests a
    real, deliberate per-entry structure rather than noise, but what it
    flags is not known.

    Returns [(value, flag), ...], length `count`; [] if count is 0 or
    `header` isn't supplied and decode_tile_header(raw) reports count 0."""
    if header is None:
        header = decode_tile_header(raw)
    start = header["w2_feature0_block_end"]
    count = header["w3_gap_array_count"]
    out = []
    for i in range(count):
        pos = start + i * 3
        val = struct.unpack_from("<H", raw, pos)[0]
        flag = raw[pos + 2]
        out.append((val, flag))
    return out


# Extra, progressively looser magnitude caps tried by decode_topology()'s
# cap ladder (see that function's docstring) after the tight/default
# `n_records*6 + 200` formula finds nothing at all for a given feature.
_TOPOLOGY_CAP_LADDER_EXTRA = (5000, 10000, 20000, 40000, 50000)


def _find_topology_table_start(raw, declen, n_records, region_end, max_gap=2000, cap=None,
                                reserved=()):
    """Locate the byte offset where a feature's (point_count+1)-record
    topology table begins, searching forward from `region_end` (see
    decode_topology() for what `region_end` should be -- it is NOT simply
    "this feature's own block_end"; see that function's docstring for why).
    Tries every byte offset in [region_end, region_end+max_gap) and accepts
    the first one where the NEXT n_records fixed-10-byte records all have
    small/plausible field values (`<= cap`, default `n_records*6 + 200`) --
    EXCEPT record 0, which is deliberately exempted from this check: on
    every tile examined this session, record 0 of a feature's table is a
    distinct "header" record with large, non-node-id-like values (seen:
    64568/2484/2217/60623 on an 83-point tile, and up to 65,478 on the mp0
    91124 ground-truth tile -- see decode_topology()). Returns None if
    nothing is found in the search window.

    `reserved`: optional iterable of `(start, end)` byte ranges to treat as
    unavailable -- any candidate whose own `[start, start+n_records*10)`
    range would overlap one is skipped. This is decode_topology()'s
    mechanism (see that function's docstring) for stopping one feature's
    search from stealing/aliasing a DIFFERENT feature's already-claimed
    table region in the same tile -- a real false-positive found and fixed
    this session (see decode_topology()). Empty by default (no exclusion).

    This function itself only ever tries ONE fixed `cap` (or the one
    default formula) -- it does not loop over a ladder of caps or decide
    which feature to search first; see decode_topology() for the ladder +
    greedy non-overlapping-reservation scheme built on top of this
    primitive, and for the full history of why a single loose cap was
    tried and rejected."""
    if cap is None:
        cap = n_records * 6 + 200
    for start in range(region_end, region_end + max_gap):
        end = start + n_records * 10
        if reserved and any(start < r_end and r_start < end for r_start, r_end in reserved):
            continue
        ok = True
        for k in range(1, n_records):  # skip record 0 (the header)
            pos = start + k * 10
            if pos + 10 > declen:
                ok = False
                break
            a, b, c, d = struct.unpack_from("<HHHH", raw, pos + 2)
            if not all(v <= cap for v in (a, b, c, d)):
                ok = False
                break
        if ok:
            return start
    return None


def decode_topology(raw, declen=None, features=None):
    """PARTIALLY CRACKED (this session) -- decode the tagged record table
    that follows a tile's coordinate region (see decode_features()). This
    is the "~10-byte tagged record table" documented in the README/module
    docstring as the last major unsolved piece; this function captures what
    was nailed down this session, with explicit caveats for what wasn't.

    SOLVED, validated on 2 tiles:
      - The table for a tile's FIRST feature does NOT necessarily start
        immediately at that feature's own `block_end` -- an earlier version
        of this function assumed that and was WRONG (caught during this
        session's own testing, see git-free history: it produced garbage
        degree histograms on both test tiles). The two tiles examined this
        session actually disagree on the byte-for-byte placement rule:
          - Single-feature tile (eeuz.mg4 offset 5,138,331, declen 2,486,
            83 points): the feature's own block_end (664) is NOT the table
            start -- there is a 104-byte gap of still-unidentified data
            (raw[664:768], does NOT look like a valid coordinate/feature
            block, does NOT look like small plausible node-ids either) and
            the real table starts at byte 768.
          - 2-feature tile (eeuz.mg4 offset 11,298,518, declen 10,386,
            features of 392 and 154 points): feature 0's table starts with
            ZERO gap, but at the OVERALL coordinate-region end (byte 2522,
            i.e. after BOTH features' geometry blocks) -- NOT after
            feature 0's own block_end (1900, which is where feature 1's
            raw geometry starts instead).
        Net effect: this session could not pin down a byte-exact formula
        for "where does the first topology table start" (0 bytes vs 104
        bytes of unexplained gap in the two samples) -- `decode_topology()`
        works around this by using `_find_topology_table_start()` (see
        above) to SEARCH for it (by requiring the next `point_count+1`
        records to hold small/plausible values), anchored after the LAST
        feature's `block_end` (i.e. the overall coordinate-region end,
        matching the 2-feature tile's observed zero-gap behavior, with
        enough search slack to also catch the single-feature tile's
        104-byte gap).
      - Once located, each table is a run of fixed 10-byte records:
            +0: 2-byte tag (byte layout varies; the tag's role is which of
                the 4 trailing uint16 fields are "real" node-id references
                vs unused/zero -- see caveat below)
            +2,+4,+6,+8: four uint16 LE fields (A, B, C, D) -- not all
                necessarily populated per record
        and the run is EXACTLY `point_count + 1` records long, where
        `point_count` is that feature's own decoded point count (anchor +
        deltas, i.e. `len(feature["points"])` from decode_features()).
        VALIDATED: a single-feature 83-point tile (eeuz.mg4 offset
        5,138,331, declen 2,486) has exactly 84 such records immediately
        after its coordinate block ends at byte 664 (matching the earlier
        README finding); the FIRST feature of the 2-feature "Iasi" tile
        (eeuz.mg4 offset 11,298,518, declen 10,386, 392-point feature) has
        exactly 393 such records immediately after ITS block ends at byte
        1900 -- both independently confirmed by finding the exact byte
        where record fields stop being small/plausible node-ids and jump to
        clearly-garbage large values (a robust, reproducible boundary, not
        a guess).
      - Interpreting the 4 fields per record as a short CHAIN of edges
        (A-B, and if more fields are populated, B-C, C-D) and building the
        resulting graph over all referenced node-ids produces a REALISTIC
        topology: for the 83-point tile, 105 distinct node-ids (0-104,
        every value in range present, no gaps) with degree distribution
        {degree 1: 15 nodes, degree 2: 79 nodes, degree 3: 11 nodes} -- i.e.
        mostly ordinary 2-neighbor "pass-through" shape points, a plausible
        number of chain endpoints (degree 1), and a plausible number of
        real BRANCH/JUNCTION points (degree 3) that always fall on records
        using a tag with MORE populated fields. This is genuine, structural
        evidence for the hypothesis that record complexity scales with a
        vertex's real topological degree (junctions get bigger records) --
        the qualitative shape of the graph is validated even though the
        exact node-id<->coordinate mapping (next paragraph) is not.

    NOT SOLVED (this is why this function does NOT return decoded
    coordinates or a road-ready graph):
      - The node-ids referenced in a record (0-104 for the 83-point tile;
        up to 546 referenced WITHIN the first feature's own 393-record
        table on the 2-feature tile, where 546 == 392+154, the tile's
        COMBINED point total across BOTH features) do NOT match
        decode_features()'s own per-feature point ordering (tested
        directly: treating node-id i as "the i-th decoded point," only
        42/83 nodes had a chain-neighbor relationship with node i-1 or
        i+1, and only 2/83 were an exact neighbor-set match -- i.e. not a
        simple positional/sequential mapping). The node-ids are most
        likely a GLOBAL, tile-wide numbering shared across every feature in
        the tile (consistent with a genuine cross-feature routing/topology
        graph, given the 546 figure above lines up exactly with the
        2-feature tile's combined point count) -- but the exact assignment
        rule (spatial sort order? original database insertion order?
        something else?) was not recovered this session.
      - **Graph-walk hypothesis tested THIS session and DEFINITIVELY
        REFUTED, not just "unmatched"**: the natural next hypothesis (a
        single feature's own polyline is a simple path, so its topology
        graph restricted to that feature ought to be graph-ISOMORPHIC to
        the path 0-1-2-...-N, just under an unknown node-id labeling, and
        so a walk from a degree-1 endpoint should reproduce
        decode_features()'s point order) is FALSE as a matter of graph
        structure, not merely "the labels don't line up": on the
        single-feature 83-point tile, the topology graph (edges = chain
        A-B/B-C/C-D within each record, as used above) has TWO connected
        components (97 and 8 nodes -- the 83-point feature's own topology
        can't even be a single connected path if part of its own node-id
        space is disconnected from the rest), and the 97-node component
        contains a CYCLE (97 nodes, 97 edges, cyclomatic number 1) and 13
        degree-1 endpoints + 13 degree-3 junctions -- not the 2 endpoints /
        0 junctions a simple 83-point path would have. Concretely: the
        LONGEST simple path between any pair of that component's 13
        degree-1 nodes is only 53 nodes (a BFS check over all 78 pairs),
        far short of the 83 needed -- i.e. NO walk through this graph, from
        any endpoint, can reproduce an 83-node path, regardless of node-id
        labeling. (The small 8-node component, in isolation, IS a clean
        simple path with exactly 2 endpoints -- interesting, but it can't
        be "the" 83-point feature's path either, since it only has 8
        nodes.) Also tested and rejected: interpreting record i's fields as
        a direct neighbor-list for point (i-1) or point i (rather than an
        A-B chain among the fields themselves) -- this reproduces the SAME
        underlying edge set (so the same negative structural result) and
        scores even worse positionally (1/83 "at least one expected
        neighbor" hits, vs 42/83 under the chain interpretation).
        CONCLUSION: for at least this tile, the per-feature topology table
        is NOT simply "this feature's own point-to-point adjacency
        relabeled" -- it encodes something structurally richer (plausibly
        the real local road-network/routing mesh, including cross-streets
        and small nearby stub roads that are not part of this feature's own
        decoded geometry at all), so recovering decode_features()'s point
        order from a walk of this graph is not possible even in principle,
        let alone practice. A future session should not re-attempt the
        plain graph-walk approach without a new idea for why the mismatch
        above wouldn't apply.
      - **New but still-inconclusive lead: the tile's own per-tile header
        (bytes 0x02-0x17) is now substantially decoded** (see
        `decode_tile_header()`), including an exact field for "this
        feature's own topology-graph node count" (105 vs computed 105 on
        the single-feature tile; 547 vs computed 546, off by one, on the
        2-feature tile) and a field pinpointing the small array that
        explains most of the previously-"unidentified 104-byte gap" before
        the topology table (see `decode_topology_gap()`) -- but neither of
        these decodes the node-id<->coordinate mapping itself; they narrow
        the remaining unknown surface without closing it.
      - **Weak/inconclusive signal on tag complexity vs. real intersections
        (not node-ids)**: cross-referencing feature 0 of the 2-feature Iasi
        tile's OWN decoded points against `eeu.rd` by exact coordinate
        (independent of any node-id, since record POSITION i+1 is known to
        correspond to point i by construction -- only the ID VALUES inside
        are unresolved) found 15/392 points landing on a named `eeu.rd`
        road, with 11 "road name changes" along the chain (plausible real
        intersections). At those 11 transition points, the record's tag
        implied a 3-field ("bigger") record 55% of the time (6/11) vs a
        31% base rate (121/392) across all of feature 0's records -- a
        mild positive signal consistent with, but far from strong
        confirmation of, "junctions get bigger records." A parallel
        cross-reference of `eeu.iof`'s unexplained per-road varying byte
        (confirmed here to live at byte OFFSET 4 of its 6-byte record, NOT
        offset 2 as the structure sketch in the README/module docstring
        elsewhere implies -- `[00 00 00 00][varying byte][0x80]`, verified
        against 15 real records) against this same tag-complexity proxy
        found NO clean separation (mean varying-byte 3.75 at plain 2-field
        points vs 4.71 at 3-field points, but overlapping ranges 0-10 on
        both sides) -- inconclusive on only 15 samples from one tile, not
        strong enough to call either confirmed or refuted.
      - The record's own TAG->field-count mapping is not exhaustively
        solved: this function uses "keep field A and B always; keep C if
        it's part of a >=3-field tag family seen this session
        (0x23/0x32/0x43/0x63 as the tag's low byte); keep D only for the
        0xc4 low-byte family; keep ONLY A for the 0x01/0x11 low-byte
        family (see FIXED note below)" -- a best-effort table built from
        the tags seen on the small tile fully hand-annotated the session
        this was first written, PLUS (later session) the real 306-point
        `mp0` ground-truth tile documented below (tags with LOW byte in
        {0x01,0x11} => 1 field; {0x22,0x02} => 2 fields;
        {0x23,0x32,0x43,0x63} => 3 fields; {0xc4} => 4 fields; anything
        else falls back to a "strip trailing zero fields, keep >=2"
        heuristic). The tag's HIGH byte was assumed to always be 0x04 in
        the original README note but is NOT reliable -- 0x0c was also seen
        heading a normal-looking, plausible-valued record on the 2-feature
        tile (tag "63 0c"/"c4 0c") -- so this function does NOT filter on
        the high byte at all, only walks a fixed 10-byte stride for
        exactly `point_count + 1` records and lets the low-byte table pick
        the field count.
        **FIXED (later session)**: low-bytes `0x01` and `0x11` were
        previously ABSENT from this table and fell through to the
        strip-trailing-zero/keep->=2 fallback, which forcibly manufactured
        a fictitious second field (always literal 0) for every such
        record. Checked directly against a real 306-point `mp0` feature
        (tile_id 91124, file offset 1,003,495,557 -- see the ground-truth
        paragraph below): EVERY one of that feature's `0x01`-tagged
        records (31/31) and `0x11`-tagged records (33/33) has its 2nd/3rd/
        4th raw uint16 fields exactly 0 -- i.e. these tags reliably mean
        exactly ONE real field, not two. Added to the table. Concrete
        effect on this tile: node-id 0's graph degree drops from an
        obviously-artifactual 74 (nearly 20x any other node) to a
        still-elevated-but-far-more-plausible 10, and the feature's
        overall degree histogram shifts from `{1:28, 2:195, 3:134, 4:6,
        74:1}` to `{1:60, 2:183, 3:110, 4:6, 10:1}` (364->360 distinct
        nodes). This is a real correctness fix for graph construction,
        but -- checked directly -- does NOT by itself crack the node-id
        mapping (see the ground-truth ledger below: the fix doesn't
        change the 0/18 real-edge score).
      - What comes AFTER each feature's (point_count+1)-record table (the
        README's "trailing block, plausibly per-feature attributes") is
        NOT decoded by this function and is returned raw/unsliced. This
        session explicitly tested and REJECTED the hypothesis that this
        trailing section is a simple 1-record-per-feature attribute table
        (road class/width/etc): on the single-feature tile it is 878 bytes
        long with an internally repeating sub-pattern (a "8c 35" 2-byte
        marker recurs 7+ times), and on the 2-feature tile it is at least
        ~3,900 bytes long after just the FIRST feature -- far more content
        than "one record per feature" would produce, and clearly not a
        fixed 10-byte record stream either (values look like reasonable
        node-ids for only ~0 records before turning to large/incoherent
        numbers). A byte-level brute-force search (`_find_topology_table_
        start()`, given a max_gap of 4,000 bytes) for a SECOND feature's
        (point_count+1)-record topology table anywhere in the 2-feature
        tile's remaining bytes (after feature 0's own table+trailing
        section) did NOT find one -- so it's unresolved whether every
        feature gets a full topology table (and this session's search
        strategy/threshold was wrong) or only certain features do. This
        function therefore only reliably locates feature 0's table; see
        Returns below for how later features are reported.
      - **UPDATE (later session): first REAL, human-verified ground-truth
        connectivity test run against this table -- mapping STILL NOT
        recovered, but the negative result is now precisely measured
        rather than inferred from graph structure alone.** A user who
        knows the real streets around Sofia, Bulgaria used the map
        viewer's click-to-identify feature to confirm the real
        connectivity order of 19 consecutive points of a real `mp0`
        feature: tile_id 91124, file offset 1,003,495,557, feature 0 (306
        points, data_start offset 326). Order (as decode_features() point
        indices): 221-200-183-186-190-198-218-227-244-253-259-270-274-
        282-277-271-264-251-240. All 19 re-decoded to 5 decimal places
        exactly matching the user's real-world-verified coordinates (good
        -- confirms decode_features() independent of the topology
        question). The user also hypothesized this closes back through
        point index 0 (since a DIFFERENT layer's, `mg1`, representation
        of the same real vertex as point 240 has identical coordinates)
        -- **this was tested directly and REFUTED**: point index 0 of
        this feature decodes to (23.39068, 42.68857), a real but
        unrelated location ~1.3km away, not the (23.40221, 42.68822) the
        closure hypothesis needs. (decode_features()'s point 0 is just
        the arbitrary first vertex of the delta encoding, confirmed here
        to carry no special "loop start" meaning -- worth checking
        directly rather than assuming, since it would have been a wrong
        foundation for everything downstream.)

        Against the resulting 18 confirmed real sequential edges (plus
        the geometrically-plausible-but-NOT-coordinate-confirmed closing
        edge 240-221), every hypothesis available this session was tested
        on the REAL `decode_topology()` output (307 records, matching
        point_count+1 exactly):
          - Direct point-index membership (record i's fields contain
            point-index j, or vice versa, for real edge i-j): **0/18**
            (0/21 including the two refuted closure-based edges).
          - Real edge exists ANYWHERE in the reconstructed graph,
            regardless of record position: **1/18** (270-274) --
            statistically indistinguishable from chance (363 of the
            graph's 458 edges have both endpoints under 306, giving an
            expected ~0.14 chance hits over 18 trials at that density).
          - EVERY possible rotational shift of "which record belongs to
            which point" (all 307 shifts, both directions, brute-forced):
            best case only **2/18** -- no shift comes close to a signal,
            ruling out any simple constant record<->point offset,
            forward or backward.
          - Pearson correlation between point index (equivalently, that
            point's own byte offset in the tile) and its record's mean
            field value: a weak but nonzero **+0.26** -- same order of
            magnitude as the previously-documented 42/83 "at least one
            expected neighbor" weak signal on the 83-point tile, but far
            too weak to reconstruct an exact mapping from.
          - Range/coverage check (new, informative even though it doesn't
            crack the mapping): this feature's own 306 points are missing
            only ONE value (node-id 57) from the topology graph's
            0-305 small-id range -- i.e. the small-id node set really is
            (almost exactly) this feature's own point-index SET, just
            under an unrecovered, non-rotational permutation. At the same
            time the graph also references 61 additional out-of-range
            ids (up to 65,478, with a contiguous run starting right at
            306, immediately past this feature's own last index). An
            exhaustive whole-tile scan (all 16,715 bytes, using the same
            `_looks_like_real_chain()`-verified anchor check
            decode_features() itself uses) for ANY other plausible
            feature block anywhere in this tile found **zero** -- this
            tile genuinely contains only the one 306-point feature, so
            the extra referenced ids are NOT a second undiscovered
            feature in the SAME tile. They must be either a genuinely
            larger/global (cross-tile or database-wide routing-node) id
            space, or real points that never get their own
            self-delimiting coordinate block at all (stub connectors,
            shared junction nodes with neighboring roads) -- both
            consistent with, and sharpening rather than resolving, the
            "structurally richer than one feature's own adjacency"
            conclusion above.
          - The tag-table bug documented above (0x01/0x11 missing ->
            fictitious edges to node 0) was found DURING this
            investigation and fixed; re-running the direct
            point-index-membership test with the corrected extraction
            still scores 0/18 -- confirming the fix is a real but
            orthogonal correctness improvement, not the missing piece of
            the mapping.
        **UPDATE (later session): CRACKED.** The "database insertion
        order" hypothesis suggested above was tried and found NOT to be
        the mechanism (no usable direct/rescaled/rank-preserving
        relationship was found between this tile's node-ids and `eeu.rd`
        record indices for the same real points) -- but investigating it
        surfaced the real answer instead: two really-adjacent points'
        records don't reference each other's point index at all, they
        SHARE one common field VALUE (a per-edge "link id"), and which
        record belongs to which point index is offset by a small,
        per-feature "shift" that can be found by brute force using only
        the feature's own decoded coordinates (the correct shift is the
        one whose implied edges connect geometrically close points). See
        `resolve_topology_adjacency()` below for the full mechanism,
        validation against BOTH this tile (16/18 real edges recovered) and
        a second, independent real ground-truth tile (`mg2` tile_id 20597,
        16/16), and the caveats (small features can give an unreliable/
        implausible result). This closes the node-id<->coordinate gap that
        this function's docstring spent several sessions unable to close.

    PRACTICAL BOTTOM LINE (see README for the fuller discussion): as of
    THIS docstring, the node-id<->coordinate mapping described as unsolved
    above is now CRACKED -- see `resolve_topology_adjacency()` below, which
    takes this function's own output and returns a real point-to-point
    adjacency graph, validated against two independent real ground-truth
    tiles. What is still genuinely open: the numeric link-id VALUES
    themselves have no independently-confirmed meaning beyond "shared by
    exactly the two (or few) adjacent points" (e.g. whether they are a
    real, separately-stored edge/segment id used elsewhere in the
    database), and why the leading-header-record "shift" varies per
    feature is not explained, only discoverable per-feature cheaply. Real
    hardware testing (insert a road with a topology table synthesized via
    this new understanding, vs. none at all, and see whether it renders/
    routes differently) remains the fastest way to learn whether real
    hardware actually depends on this table for a newly-added feature.

    Args:
        raw, declen: as for decode_features().
        features: optional, the return value of decode_features(raw,
            declen) -- computed internally if not passed. (Historical
            note: an earlier session's decode_features() had a magnitude-
            threshold bug that mis-split some multi-feature tiles,
            including the 2-feature "Iasi" reference tile used throughout
            this module's docstrings -- see the FIXED block comment just
            above this function. That bug is now fixed and re-verified at
            scale; decode_features() can be trusted directly and no
            workaround/legacy walk is needed any more.)

    Returns a list of dicts, one per feature IN THE ORDER GIVEN:
        {"found": <bool, whether a table could be located for this feature>,
         "table_start": <int or None>,
         "table_end": <int or None, table_start + (point_count+1)*10>,
         "records": [{"offset", "tag" (hex str), "fields" (tuple of
                       however many are considered "real" per the
                       best-effort tag table below)}, ...],  # [] if not found
         "graph_degree": {node_id: degree, ...}}  # from the chain-edge
                       interpretation described above; use for the
                       "does this vertex look like a junction" question,
                       NOT as a verified ground truth. {} if not found.

    **REVISED this session: table location is now a GREEDY, TIGHTEST-CAP-
    FIRST, NON-OVERLAPPING-RESERVATION search across ALL of a tile's
    features at once, not a simple per-feature sequential scan.** This
    followed directly from fixing a real, at-scale problem: a Sofia-area
    characterization (257 real features, 5 layers) found 96/257 (37%)
    failing to reach `resolve_topology_adjacency()`'s "high" confidence,
    and 94 of those 96 were `"found": False` outright -- traced to
    `_find_topology_table_start()`'s magnitude `cap` being far too tight
    for real dense-urban field values (measured up to ~49,664 on a
    300+-point `mp0` feature, vs. the old cap's ~2,000-ish ceiling for a
    feature that size -- see `_find_topology_table_start()`'s history for
    the full numbers). Raising the cap (as a simple ladder: try the tight
    `n_records*6+200` formula first, only escalate to 5,000/10,000/20,000/
    40,000/50,000 if that finds nothing) recovers those 94 in isolation --
    but doing so with the OLD per-feature-sequential search order
    introduced a NEW, worse failure directly measured on a real tile
    (`mp0` 88098, a 2-feature tile: a 368-point feature and a 57-point
    feature): searched first (as the tile's "feature 0"), the 368-point
    feature's tight cap found nothing, so it escalated -- and at the
    loosened cap it matched a **6-byte-misaligned echo of the 57-point
    feature's own genuine, tightly-locatable table** (confirmed by
    directly inspecting the raw bytes: the "false" table's field values at
    each record are the SAME underlying bytes as the real 57-point table's
    fields, just read 6 bytes out of phase). That false match's own
    (point_count+1)*10-byte span then became this tile's advancing
    `search_from` for the NEXT feature, pushing the 57-point feature's
    search past its own real table entirely -- so it went from correctly
    `"found": True` (confidence "high", median 774m, BEFORE this session's
    changes) to wrongly `"found": False` (regression) while the 368-point
    feature became a spurious `"found": True, confidence: "high"` (a
    plausible-looking but fabricated ~63m median from mis-strided real
    bytes, not genuine topology) -- silently trading one correct result for
    one wrong one while the tile's total "high-confidence" count looked
    unchanged. Root cause: the OLD design lets whichever feature is
    searched FIRST claim territory using a loose cap, even when a
    DIFFERENT feature in the same tile could be found unambiguously
    (tight cap, first try) at an overlapping/adjacent position -- there
    was no mechanism to prefer the more-confident match.

    **Fix**: search every feature in the tile from the SAME shared anchor
    (`search_from`, defined below) rather than sequentially advancing past
    each feature's own (possibly-spurious) result, resolve features in
    order of INCREASING minimal-cap-needed (i.e. whichever feature is
    locatable most tightly/confidently goes first, regardless of its
    position in `features`), and RESERVE each resolved feature's own byte
    range -- excluded from every other, still-pending feature's search --
    before moving to the next. Re-run on the `mp0` 88098 case above: the
    57-point feature (tight cap succeeds immediately) is now resolved
    FIRST and its range reserved, which correctly blocks the 368-point
    feature's loose-cap search from ever landing on the same bytes again;
    the 368-point feature is left `"found": False` (an honest "don't know"
    -- no other valid, non-overlapping position was found for it either)
    rather than a fabricated `"found": True`. Re-validated: both required
    ground-truth tiles (`mg2` 20597, `mp0` 91124 -- single-feature tiles,
    so this scheme is a no-op for them) reproduce their exact original
    results; see `resolve_topology_adjacency()`'s docstring for the full
    before/after high-confidence numbers on the Sofia sample after this
    fix (including this specific tile's corrected outcome).

    ============================================================================
    A LATER SESSION: a genuine, PREVIOUSLY UNDOCUMENTED 3rd tile region exists
    right after this function's own topology table ends -- real structure
    found, NOT parsed into named fields, task was locating `eeu.si`'s own
    `seginfoID` (eeu.mod's "Ordinary Map File" schema, README §3.16, names
    `seg`/`seginfoID`/`restr_left`/`restr_right`/`left_node`/`right_node`/
    `length` fields on a per-segment record this session set out to find)
    ============================================================================
    This session's goal was to link a rendered tile segment to its real
    `eeu.si` classification (rank/class/divided/paved/tollbooth, README
    §3.20) so the map viewer could style roads by real attributes, not
    just draw plain dots. `eeu.mod`'s own schema for this table is the
    largest in the whole disc (615 field names) with a MUCH deeper nested
    structure than either the coordinate region or this function's own
    10-byte topology table (a `seg` record alone has ~13 real leaf
    fields: `seg_marker`/`seg_marker_left`/`seg_marker_right`/
    `seg_turn_restr`/`seginfoID_ext_count`/`seginfoID`/`seginfoIDext1`/
    `seginfoIDext2`/`restr_left`/`restr_right`/`left_node`/`right_node`/
    `length`, itself nested under `parcel_data` -> `node_list`/`seg_list`/
    `attr_list`/`abs_addr_list`/etc., each with their own counts, under a
    kd-tree parcel-navigation structure this session did not attempt to
    fully walk).

    **A real finding, on the way to that goal**: on a real single-feature
    83-point tile (`eeuz.mg4` offset 5,138,331), the bytes immediately
    after this function's own topology table (which ends at
    `table_start + (point_count+1)*10`) are NOT simply the end of the
    compressed entry -- there are 878 more real bytes, containing
    visible, repeating, GROUPED structure (spot-checked by eye: runs like
    `8c 35 01 02 dc 00 00 00` / `8c 35 01 06 62 02 00 00` recur, with the
    leading 2 bytes and a small "count-like" 3rd byte varying by group,
    consistent with a real, `attr_list`/`abs_addr_list`-shaped tagged
    record region, not padding). **Confirmed on 8 more real single-feature
    tiles**: every one has a real, non-empty tail of the same general
    shape, and the tail's own BYTE LENGTH correlates strongly with the
    feature's own point count -- a linear fit across the 8 tiles gives
    ~8.95 bytes/point (intercept ~35), consistent with roughly one small
    variable-length record per point/segment, not a fixed global size.
    Checking whether a small integer anywhere in this tail resembles a
    real `eeu.si` `seginfoID` (bounded 0-24,352, `eeu.si`'s own real
    24,353-record range) was NOT completed this session -- the region's
    own record boundaries/field layout were not pinned down precisely
    enough to test a specific byte position with confidence, and a naive
    every-byte-position overlapping scan across several tiles (looking
    for one dominant recurring value) was too noisy to draw a real
    conclusion (dominated by small-integer/padding collisions, not a
    clean answer). **Honest status: this is a real, new, previously
    undocumented lead (the tile format has a 3rd real content region
    here, not just [coordinates][topology table]) -- not yet a crack of
    `seginfoID` or road styling.** A future session's most promising next
    step: find the exact per-record boundary within this tail (the same
    "search forward for a plausible small-value run" technique
    `_find_topology_table_start()` already uses for the topology table
    might work here too, once a candidate record shape is guessed from a
    few more hand-inspected examples), then test candidate small-integer
    fields against `eeu.si`'s own real, already-cracked value ranges
    (rank 0-4, class 0-12, paved's ~94.6% true rate, etc.) as ground
    truth, the same cross-validation technique that cracked `eeu.si`
    itself (README §3.20).

    **UPDATE, same later session, record-boundary search attempted and
    inconclusive -- a real methodological trap documented here so a
    future session doesn't repeat it.** Hand-inspecting the first ~7
    records of the 83-point tile's own tail (above) initially looked like
    a clean `[uint16 LE id][byte][byte][uint32 LE value]` 8-byte shape
    for several consecutive records -- but the very next record
    (`b5 bd 01 01 05 03 00 da 01 00 00`) shares the SAME 3rd byte (`01`)
    two 8-byte records used as their own "tag" while itself needing 11
    bytes to hold a plausible trailing value, directly refuting "3rd byte
    alone determines record length" as a rule. **A backtracking
    constraint search** (find a `tag -> length` mapping, tag = the 3rd
    byte of each record, that consumes the WHOLE 878-byte tail with zero
    leftover) was tried next -- and is a real, documented CAUTIONARY
    result: an unconstrained search (candidate lengths 3-42) trivially
    "succeeds" by mostly picking the smallest possible length at every
    step (a degenerate, meaningless decomposition -- total-byte-
    consumption alone is FAR too weak a validation criterion, since many
    different partitions of 878 bytes exist). A more constrained search
    (candidate lengths restricted to {8,9,10,11}, longest-first) found a
    DIFFERENT "successful" decomposition -- uniform 8-byte records
    almost everywhere -- but printing out the resulting fields shows
    values that are plausible for the first 2-3 records and then become
    obvious garbage (huge, effectively-random uint32 values with no
    plausible interpretation) from record 4 onward, i.e. this
    "successful" consumption is ALSO a false positive, not the real
    structure -- it just happens to sum to the right total length.
    **Conclusion: exact total-byte-consumption is a NECESSARY but nowhere
    near SUFFICIENT test for a candidate record-boundary rule in this
    region** (unlike, e.g., `eeuz.fea`'s directory-table crack or
    `eeu.tmc`'s `chain_count` formula, both of which had an independent,
    exact cross-check available) -- a future attempt needs a genuinely
    independent validation signal (real ground truth to match against,
    not just "the bytes add up") before trusting any candidate record
    shape here.

    **UPDATE, a later session, from the FIRMWARE side (`research/
    swl_5238_reader.py`)**: the user provided a separate factory firmware
    disc; its `FHDD6.FLI` application image embeds a real, versioned
    `db_seg_*` accessor-function-name catalog directly confirming this
    exact field group is real and actively read at runtime: `db_seg_
    rank_V004`, `db_seg_speed_V004`, `db_seg_tunnel_V004`, `db_seg_
    node_V004`, `db_seg_unique_vid_V005`, `db_seg_plural_junction_V005`,
    `db_seg_is_part_of_freeway_intersection_V005`, and -- an EXACT name
    match -- `db_seg_marker_left_V004`/`db_seg_marker_right_V004` for
    `eeu.mod`'s own `seg_marker_left`/`seg_marker_right` fields. This is
    strong independent confirmation the field names are real (not an
    authoring-tool-only convention), and narrows any future disassembly
    attempt to specific, named functions instead of a blind search of
    the whole tile-tail region -- but the functions' own CODE was not
    located or disassembled this session (no recoverable load-base
    address for that region, same wall as README S2.4), so this remains
    a confirmed lead, not a byte-offset crack.

    **UPDATE, same later session: a direct attempt to recover the load
    base was made and REFUTED.** String cross-referencing via `lis`/
    `addi` immediate-pair scanning (39,715 candidate absolute-address
    pairs found across the whole 24MB region, tested against 7 known
    accessor-name string offsets including `db_seg_marker_left_V004`
    itself) found NO consistent load base -- each string's own top
    candidate values are completely unrelated to every other string's.
    Most likely explanation (see `research/swl_5238_reader.py` for the
    full writeup): these strings are DWARF-`.debug_str`-like debug-only
    data, structurally never referenced by executing code, so no amount
    of code-side cross-referencing can locate them -- a real, structural
    dead end for this specific technique, not an unexplored gap.

    **UPDATE, a still-later session: a fresh record-boundary attempt,
    directly informed by the firmware's own field names -- suggestive
    on one tile, but did NOT replicate cleanly across 3, so NOT a crack.**
    `eeu.mod`'s schema names a `seginfoID_ext_count` field on the `seg`
    record (0-2 extension IDs) -- a plausible, principled explanation for
    the earlier "8 vs 11-byte record" contradiction that broke the naive
    single-tag-length hypothesis (varying record length because of a
    real variable extension count, not an inconsistent tag rule). Before
    testing THAT directly, a cheaper, complementary idea was tried first:
    if the tail's leading 2 bytes of each record are a real `seginfoID`
    (bounded 0-24,352, `eeu.si`'s own real range), then on a tile
    dominated by ONE real road, that same ID should recur across MOST
    records, and different tiles/roads should show DIFFERENT dominant
    values.

    On the 83-point reference tile (`eeuz.mg4` offset 5,138,331): a
    plain unaligned 2-byte sliding-window frequency count over the whole
    878-byte tail finds `13708` (`0x358c`) as overwhelmingly dominant --
    74 occurrences, vs. the next non-zero/non-artifact value far behind
    -- and `13708 < 24,352` fits `eeu.si`'s bound. Looking up `eeu.si`
    record #13708 directly (`research/si_reader.py`) gives real,
    self-consistent field values (`rank=1, class=3, urban=True,
    paved=True, ...`) -- plausible, not contradictory, for this tile's
    real coordinates (~61.05N 16.96E, coastal Sweden near Sundsvall) but
    NOT independently confirmed (no external ground truth for what this
    specific road's real classification should be).

    **Tested on 2 more independent reference tiles and did NOT
    replicate as cleanly**: the 2-feature "Iasi" tile's own 392-point
    feature (`eeuz.mg4` offset 11,298,518) shows NO single dominant
    value at all -- several candidates (`19456`, `60416`, `29772`,
    `59392`) each appear only 40-53 times out of 392 points (~10-13%
    each), a plausible-but-unproven read being that a dense real urban
    intersection area (Iasi is a real city) naturally has many
    real, genuinely different street IDs rather than one dominant road
    -- but this is NOT independently confirmed either, so it cannot be
    used to rescue the hypothesis. More concerning: the 3rd reference
    tile (`mg2` tile_id 20597, offset 69,486,644, 203 points) ALSO shows
    no strong single dominant value (max 62/203, ~30%), AND its own
    top candidates include `35840` (`0x8c00`) -- the SAME "ghost" value
    that appeared as a sliding-window artifact on the FIRST tile (from
    the same `0x8c` byte at a different alignment) -- raising real doubt
    that `0x8c` is specifically "this road's own ID" rather than just a
    common byte value/tag that recurs across many unrelated tiles for
    an entirely different reason (e.g. a common flag byte, not an ID).

    **Honest conclusion: suggestive on 1 of 3 tiles, does not replicate
    cleanly, NOT a crack.** This is a real, new lead (the dominance
    pattern on tile 1 is genuine and striking, and `seginfoID_ext_count`
    remains an unexplored, principled candidate explanation for the
    variable record length) but the cross-tile evidence is mixed enough
    that treating `13708` as a confirmed `seginfoID` would be
    overclaiming. A future session's most promising next step: actually
    pursue the `seginfoID_ext_count`-driven variable-record-length
    hypothesis directly (rather than the unaligned frequency-count
    shortcut tried here), since a correctly-bounded record parse would
    let the SAME leading-2-bytes-per-record test be re-run on cleanly
    aligned data instead of an overlapping sliding window -- the tile-2
    and tile-3 noise could plausibly be a real alignment/parsing
    artifact of the shortcut, not evidence against the underlying field
    itself.

    **UPDATE, that exact next step attempted, same still-later session:
    a single-count-field variable-length model is EXHAUSTIVELY REFUTED,
    computationally, not just by hand.** Built a joint search requiring
    a candidate `(base_record_length, ext_count_byte_offset,
    ext_field_size, id_field_offset)` to simultaneously (a) consume the
    WHOLE 878-byte tail with zero leftover via `record_length =
    base_record_length + ext_count_value * ext_field_size`, where
    `ext_count_value` is read from a fixed record-relative byte offset
    every record, AND (b) never see an `ext_count_value` above a
    generous cap. Swept `base_record_length` 5-13, every possible
    `ext_count_byte_offset`/`ext_field_size`/`id_field_offset` within
    that range, and caps up to 15 (`eeu.mod`'s own `seginfoID_ext_count`
    field would realistically only need 0-2): **zero configurations
    achieve exact consumption, at ANY cap**. Root cause, confirmed by
    direct inspection: the byte at the single most plausible candidate
    position (relative offset 2, whose whole-tail value distribution
    genuinely looks like a real small count field -- 0/1/2/3 in
    decreasing frequency, `eeu.si`-scale evidence, not a coincidence)
    reads the SAME value (`1`) on 3 consecutive real records whose true
    lengths are 8, 8, and 11 bytes -- direct, irreconcilable proof that
    no single formula tied to that byte (or, the exhaustive sweep shows,
    to ANY other fixed-offset byte) can be the sole length driver.
    **Conclusion, now considerably more solid than the earlier hand-
    checked version**: the tail's true record format needs genuinely
    MULTIPLE, independently-variable fields (plausible candidates from
    `eeu.mod`'s own 13-field `seg` list: `seg_marker_left`/
    `seg_marker_right`/`restr_left`/`restr_right` could each
    independently be present or absent, not just one shared
    `seginfoID_ext_count` toggle) -- a genuinely bigger parsing problem
    than a quick continuation can responsibly solve. This is a real
    wall for the "single formula" approach specifically, not a dead end
    for the whole investigation: a future session with more time should
    move to a per-record, per-field presence/absence model (closer to
    `eeu.tmc`'s own successfully-cracked variable-field-count
    `chain_count` structure) rather than a single count byte.

    ============================================================================
    REAL HUMAN GROUND TRUTH obtained, a still-later session -- 3 precisely-
    located, real-world-confirmed road segments (the user has the actual
    RNS510 unit running this exact disc, CD_8555, and used the map viewer's
    own edge-pick tool to identify exact tile/feature/point locations for
    roads they could personally confirm). This is the same category of
    evidence that eventually cracked the LOCAL topology graph (the human-
    verified 19-point/17-point connectivity orders) -- preserved here in
    full so a future session does not need to re-acquire it.
    ============================================================================
      1. **A1 motorway (Trakia), segment 1** -- CONFIRMED divided motorway.
         `eeuz.mg4`, tile_id 2391, file offset 6,562,278, feature 0 (of 5
         real features in this tile -- the motorway is NOT necessarily the
         only feature), edge points #158<->#160<->#161<->#162<->#165<->#166
         <->#171 (real coords 23.69253,42.55447 through 23.69857,42.5527).
      2. **A1 motorway (Trakia), segment 2** -- CONFIRMED divided motorway,
         a 2nd, independent real point on the same road. `eeuz.mg4`,
         tile_id 2389, file offset 6,557,013, feature 0 (this tile's ONLY
         feature, 196 points), point #71 (real coords 23.99894,42.34009).
      3. **Vladimir Bashev street, Sofia** -- CONFIRMED one-way LOCAL
         street (contrast case: NOT divided). `eeuz.mp0`, tile_id 88178,
         file offset 972,000,264, feature 0 (this tile's ONLY feature, 391
         points), edge points #198<->#269 (real coords 23.3561,42.67998
         and 23.35786,42.6796).

    **3 independent shortcut methods were tried against this real ground
    truth, ALL REFUTED -- a real, thorough negative result, not just
    inconclusive:**

    (a) The earlier "unaligned 2-byte sliding-window, filter by `eeu.si`'s
    0-24,352 bound" approach (this docstring's own earlier UPDATE) was
    re-run against `divided` on all 3 segments: weighted `divided` rate
    among candidate IDs was 15.4%/19.5% for the 2 CONFIRMED-divided A1
    segments and 10.7% for the CONFIRMED-non-divided one-way street --
    directionally plausible (lower for the local street) but nowhere near
    a clean, confident signal, and NOT what a real, working ID lookup
    should look like. **A key realization, testing this**: `eeu.si` has
    24,353 of 65,536 possible 16-bit values -- ANY random 16-bit number
    has a ~37% chance of passing the "plausible index" filter purely by
    chance, meaning this filter is far weaker than it first appeared, and
    the whole approach may have been analyzing mostly noise all along.

    (b) The SAME test re-run for `toll_vignette` (motivated by real-world
    knowledge: Bulgarian motorways legally require a toll vignette, a
    strong, distinctive, binary real-world fact for the 2 A1 segments)
    came back BACKWARDS -- both A1 segments showed a LOWER weighted
    `toll_vignette` rate (7.0%/7.9%) than the disc-wide baseline (11.6%),
    the opposite of the expected direction. This is a real, clean
    refutation, not just noise: a working ID-lookup mechanism should never
    show a real motorway's own toll-vignette rate BELOW baseline.

    (c) A positional/distributional scan (not ID-based at all): for every
    candidate `(period 4-16, phase)`, compared the byte-value distribution
    at that position across the whole tail between the 2 real motorway
    tiles and the real one-way-street tile, looking for a position where
    both motorway tiles agree with each other but differ from the street.
    One candidate survived the initial filter (period=14, phase=11: both
    A1 tiles ~65-75% "small" (<=4) values vs. 44% for the street) -- but
    FAILED a basic internal-consistency check (splitting each tile's own
    tail in half and re-checking): tile 2391's own first half was 90%
    small values, its second half only 60% -- a huge swing WITHIN one
    real road's own single tail region, which a genuine structural field
    would not show. Given ~150 `(period, phase)` combinations were
    screened, this is very plausibly a multiple-comparisons artifact, not
    a real field -- correctly caught by the follow-up check rather than
    reported as a discovery.

    **Honest overall conclusion**: 3 independent shortcut families, tested
    against 3 independent pieces of real, human-verified ground truth
    (not just internal statistics), all fail. This is now a well-earned,
    thoroughly-tested wall for ANY approach that doesn't first solve the
    real per-record field-boundary problem -- see the exhaustive
    single-count-field refutation above for why that's a genuinely bigger
    undertaking than a shortcut. A concrete reframing worth trying next,
    suggested by the firmware's own `db_seg_speed_V004`/`db_seg_rank_V004`
    accessor names (README S2.6, `research/swl_5238_reader.py`): the
    per-segment classification (rank, speed, tunnel, etc) may be encoded
    DIRECTLY in each `seg` record's own fields, not solely via an indirect
    `seginfoID` lookup into `eeu.si` -- `seginfoID_ext_count`/`seginfoID`/
    `seginfoIDext1`/`seginfoIDext2` may be a comparatively RARE, optional
    cross-reference (an "extension"), not the primary classification
    mechanism for the common case. A future session should build the real
    per-record parser directly against these 3 known real segments (not
    blind statistics across a whole tail), since a correct parser must,
    at minimum, decode something distinctly different between the 2
    CONFIRMED-divided motorway segments and the 1 CONFIRMED-non-divided
    street segment -- a genuine, human-verified acceptance test that no
    prior candidate in this project has ever had for this specific file
    region.

    ============================================================================
    A REAL PER-ID-LENGTH PARSER, a still-later session: genuine structural
    progress on `mg4`-format tiles, PLUS 6 more real, human-verified ground-
    truth points from the user's own RNS510 unit -- but the "divided road"
    hypothesis this parser initially suggested is now CLEANLY REFUTED with
    2 more confirmed non-divided highways. Real structure was found; it
    just isn't "divided" that it encodes.
    ============================================================================
    **The parser, built from scratch by hand (not blind search)**: careful
    byte-level inspection of the CONFIRMED-divided `A1_2389` tile's own tail
    found that the SAME 2-byte leading value at a record's start ALWAYS
    implies the SAME record length across every occurrence (e.g. id 42509
    is always 10 bytes, id 15660 is always 8 bytes, id 5204 is always 9
    bytes -- verified by hand across a dozen+ records before automating).
    Crucially, EVERY verified record also ends in exactly 2 zero bytes
    (`00 00`) -- a real, semantically meaningful terminator, not just a
    consumption artifact. Automating this as a constraint-propagation
    backtracking parser (`id -> length` map, built on the fly, requiring
    every candidate length to end in `00 00`) converges FAST and
    deterministically on `A1_2389` (2,068 steps, unseeded) to a stable
    229-record/196-point solution (~1.17 records/point) whose length
    distribution (71% plain 8-byte records, the rest 9-14-byte "special"
    records) matches the ALREADY-established "junctions get bigger records
    than through-points" pattern from the LOCAL topology crack -- real,
    independent corroboration, not just self-consistency.

    **6 more real, human-verified ground-truth points, all from the user's
    own RNS510 unit** (preserved here in full, extending the 3 already
    logged above):
      4. **Hemus/A2 motorway, Sofia** -- `eeuz.mg4`, tile_id 2388, file
         offset 6,553,798, feature 0 (196... actually 226 points), edge
         points #177<->#179 (23.46552,42.70888 / 23.46688,42.70935).
         Initially thought to be a contrast (non-divided) case; the user
         later CONFIRMED this specific point IS on a newer DIVIDED
         motorway section.
      5. **A6, near Sofia** -- `eeuz.mg4`, tile_id 2380, file offset
         6,533,304, point 65 of feature 0 (192 points), EXACT coordinate
         match (23.14611,42.66354 vs. the user's own 23.14609,42.66354).
         CONFIRMED by the user: single carriageway, still under
         construction toward eventual motorway status -- i.e. real,
         current NON-divided status.
      6. **A2, western Bulgaria** -- named coordinate 22.23181,42.17325 in
         `eeu.rd`; the nearest-anchor `mg4` tile match was ~13km off (not
         trustworthy, not used further). CONFIRMED by the user: "single
         dual lane road, 1 lane in one direction and another single lane
         in the other direction" -- i.e. also real NON-divided status,
         just not tied to a precisely-verified tile/byte position here.
      7-9. Also checked and RULED OUT as unusable: a 2nd `eeuz.mg4`
         coordinate on the real A2 corridor near Varna (27.86042,43.22266)
         turned out not to be on the A2 at all (confirmed via the disc's
         own `nearby_streets_for_point` output, matching a real Varna
         street context instead); a coordinate near the real A3/Maritsa
         motorway (22.76347,41.95991) turned out to be an unrelated
         village street/dirt road, not the motorway. Both correctly
         identified as bad data points by the user's own real-world
         knowledge before being used for anything -- exactly the kind of
         check that keeps ground truth trustworthy.

    **The "divided" hypothesis this parser's own length-distribution
    signal initially suggested is now CLEANLY REFUTED.** Testing the
    length-distribution split (percentage of plain 8-byte vs. 9-byte
    records) across all 3 tiles with KNOWN, PRECISE ground truth:

        A1_2389   (CONFIRMED divided)    8-byte=71%  9-byte=14%
        Hemus/A2  (CONFIRMED divided)    8-byte=40%  9-byte=46%
        A6        (CONFIRMED NON-divided) 8-byte=41%  9-byte=49%

    `A6` (non-divided) and `Hemus` (divided) show NEARLY IDENTICAL
    length-distribution signatures (~40%/~46-49%), while `A1` (also
    divided) shows a COMPLETELY DIFFERENT one (71%/14%) from BOTH of
    them. This directly rules out "divided status" as what the 8-vs-9-
    byte record-length split encodes -- two roads with OPPOSITE divided
    status look alike, while two roads with the SAME divided status look
    different. A real, honest refutation using precise ground truth, not
    a discouraging outcome to hide: the underlying PARSER (per-ID-
    consistent length, `00 00`-terminated records) is still real,
    working structure -- it just isn't `divided` specifically that this
    particular signal (8-vs-9-byte ratio) tracks. Plausible alternatives,
    not yet tested: construction/data-vintage status (A6 is explicitly
    "still under construction" -- a real, unusual state that could
    affect how its segments are encoded), real geometric complexity
    (curve/junction density), or a real attribute unrelated to road
    classification entirely (e.g. `eeu.si`'s own `restclass`/
    `route_num_type`/`urban` fields, not `divided`).

    **Also confirmed the SAME session, directly from the user's own
    on-screen observation of the real unit**: the 5 tile layers are real
    ROAD-CLASS tiers, not generic zoom simplification --
    `mg4`=highways, `mg3`=main roads, `mg2`=boulevards, `mg1`=main
    streets, `mp0`=everything else (see this module's own top docstring
    and README S3.6 for the full writeup) -- meaning the `mp0`-format
    Vladimir Bashev ground truth (points 1-3 above) is in a DIFFERENT,
    not-yet-analyzed record format from this `mg4` parser, and could not
    be used for a direct same-format comparison this session (a real,
    separate reverse-engineering target for a future session, not
    started successfully here -- a wide-candidate-range attempt
    exhausted 15,000,000 search steps with no solution).

    ============================================================================
    A REAL, CLEAN, QUALITATIVE (not just statistical) signal found the SAME
    session, right after the "divided" length-ratio refutation above --
    `byte2==0 or byte3==0` on an 8-byte record. Promising, not yet a full
    crack, but the strongest lead in this whole file region so far.
    ============================================================================
    Every 8-byte `seg_list` record decodes as `[id(2)][byte2(1)][byte3(1)]
    [value(4)]`. Checking whether `byte2` or `byte3` is EXACTLY ZERO on any
    8-byte record, across the SAME 3 precisely-matched ground-truth tiles
    used for the (now-refuted) length-ratio test:

        A1_2389   (CONFIRMED divided)      163 8-byte records, 0 with byte2/3==0  ( 0.0%)
        Hemus/A2  (CONFIRMED divided)      110 8-byte records, 0 with byte2/3==0  ( 0.0%)
        A6        (CONFIRMED non-divided)   89 8-byte records, 11 with byte2/3==0 (12.4%)

    A 3rd, less certain sample (the `A2-west` coordinate, 22.23181,42.17325,
    CONFIRMED non-divided by the user -- "single dual lane road, 1 lane
    each direction" -- but its `mg4` tile match is a ~13km nearest-anchor
    approximation, NOT a precise coordinate match like the other 3, so
    treat this one as directionally-suggestive only, not fully trustworthy)
    shows 96 of 137 8-byte records with `byte2/3==0` (70.1%) -- much
    higher than A6's rate, but the SAME qualitative direction (nonzero,
    unlike the 2 precisely-matched divided tiles' clean 0.0%).

    **This is a real, qualitative (presence/absence, not just a magnitude
    shift) pattern across 2 solid + 1 suggestive sample**: `byte2==0 or
    byte3==0` NEVER happens on either precisely-confirmed divided road
    (0/273 combined 8-byte records), but DOES happen on both non-divided
    roads (11/89 and 96/137). Genuinely promising -- exactly the kind of
    clean effect the earlier length-ratio test never produced -- but NOT
    yet a crack: only 2 tiles have BOTH a precise coordinate match AND
    confirmed divided status, and the magnitude varies a lot between the
    2 non-divided samples (12.4% vs. 70.1%), so this needs at least 1-2
    more precisely-matched samples (ideally another confirmed-divided
    tile, to test whether 0.0% really holds as a hard rule rather than
    "usually low") before it can be called cracked. A concrete next step
    for a future session: get 1 more precise divided-road ground-truth
    point and check whether `byte2/3==0` really stays at exactly 0%, or
    whether A1/Hemus's own 0% was itself a (much less likely, but not
    impossible) coincidence.

    ============================================================================
    UPDATE, immediately following, same session: a systematic per-byte-
    position sweep (all 8 byte offsets, not just byte2/byte3 chosen ad hoc)
    STRENGTHENS this signal -- 4 independent byte positions agree, not 2.
    ============================================================================
    Checked `==0` at EVERY byte offset 0-7 of an 8-byte record, across the
    same 3 tiles (`A1_2389`=163, `Hemus`=110 divided records;
    `A6`=89 non-divided records):

        byte0: A1=2.5%   Hemus=2.7%   A6=10.1%   (nonzero on all 3 -- noisy)
        byte1: A1=0.0%   Hemus=0.0%   A6=2.2%    (clean)
        byte2: A1=0.0%   Hemus=0.0%   A6=4.5%    (clean -- already known)
        byte3: A1=0.0%   Hemus=0.0%   A6=7.9%    (clean -- already known)
        byte4: A1=1.2%   Hemus=0.0%   A6=7.9%    (nearly clean)
        byte5: A1=28.2%  Hemus=40.9%  A6=51.7%   (no clean split at all)
        byte6: A1=100%   Hemus=100%   A6=100%    (ALWAYS zero -- but this is
                                                    TAUTOLOGICAL, not a finding:
                                                    the parser's own `00 00`
                                                    terminator constraint
                                                    REQUIRES bytes[6:8]==0 for
                                                    a record to be accepted at
                                                    all -- byte6/7 prove
                                                    nothing about content)
        byte7: same tautology as byte6.

    **Bytes 1, 2, 3, and 4 are NOT constrained by the parser's own rules**
    (only bytes 6-7 are required to be zero to accept a record) -- so their
    agreement is real, independent evidence, not another instance of the
    same tautology. Checking ANY of byte1/2/3/4 `==0` together: `A1`=1.2%
    (2/163, both attributable to byte4 alone -- byte1/2/3 individually stay
    at a clean 0/163), `Hemus`=0.0% (0/110, perfectly clean), `A6`=19.1%
    (17/89). Still a real, strong separation -- but honestly NOT a
    mathematically perfect hard rule once byte4 is folded in (A1's 1.2% is
    a real, small leak, not zero). The cleanest single positions remain
    byte2/byte3 (each individually exactly 0/163 and 0/110 on both divided
    tiles). Byte5 shows no divided/non-divided split at all (28-52% across
    all 3, monotonically increasing but present everywhere) -- whatever it
    encodes, it isn't this. Still NOT a byte-by-byte semantic crack (no
    field NAME is attached to any of these positions -- this is purely "X
    correlates with divided status", not "byte N is the `divided` bit"),
    but meaningfully stronger evidence than the original byte2/3-only
    finding: 4 independent positions, not 2, converge on the same
    qualitative pattern.

    ============================================================================
    A specific semantic hypothesis was then tested using data this project
    ALREADY had (no new ground truth needed) -- CLEANLY REFUTED.
    ============================================================================
    `eeu.mod`'s own schema names real per-record flag fields
    (`seg_turn_restr`, `restr_left`, `restr_right`) that would plausibly be
    zero at a plain through-point and nonzero only at a real intersection
    -- and divided motorways have far fewer at-grade intersections along
    their mainline than ordinary roads, which could explain the observed
    correlation INDIRECTLY (via junction density) rather than "divided"
    being encoded directly. This is testable against data already in hand:
    `resolve_topology_adjacency()`'s own already-cracked local topology
    graph gives a real per-tile junction fraction (nodes with degree > 2)
    with NO new ground truth needed.

        A1_2389  (divided):      166 topology nodes, 0 junctions (0.0%)   | seg anyzero=1.2%
        Hemus    (divided):      209 topology nodes, 5 junctions (2.4%)   | seg anyzero=0.0%
        A6       (non-divided):  186 topology nodes, 1 junction  (0.5%)   | seg anyzero=19.1%

    If the signal tracked junction/intersection density, MORE junctions
    should mean a HIGHER `seg anyzero` rate. It's the OPPOSITE: `Hemus` has
    the MOST junctions (2.4%) of the 3 tiles but the LOWEST `seg anyzero`
    rate (0.0%, even lower than `A1`'s 0% junctions/1.2% rate); `A6` has
    FEWER junctions than `Hemus` (0.5% vs. 2.4%) but a FAR higher rate
    (19.1%). A real, clean refutation, efficiently obtained by reusing
    already-cracked data rather than assuming the explanation or asking
    for more ground truth. Whatever bytes 1-4 encode, it is NOT simply
    "is this point a real intersection" -- the underlying STATISTICAL
    correlation with divided status (from real human ground truth) still
    stands; only this one candidate SEMANTIC explanation for it is ruled
    out.

    ============================================================================
    UPDATE: byte4's own small "leak" on A1 (2/163) is explained away as
    numeric coincidence, not signal -- REFINES the finding to bytes 1-3
    specifically, not 1-4.
    ============================================================================
    Checked A1_2389's own 2 exception records directly: both are ordinary
    recurring road ids already seen elsewhere in this tile (15660, 15948,
    each appearing multiple times with DIFFERENT byte4 values in their
    other occurrences) -- and both have a trailing "value" field of
    exactly 256 (`0x0100`). Since `value` is parsed as a 4-byte
    little-endian integer with byte4 as its LOWEST-order byte, `value ==
    256` makes byte4 zero purely because 256 is an exact multiple of 256
    -- a real but numerically INCIDENTAL zero, not a separate meaningful
    flag. Under a rough uniform/Poisson estimate (~1/256 chance per
    record for the low byte to land on exactly zero), 2 such coincidences
    across 163 records is unsurprising (order ~0.4 expected). By
    contrast, `A6`'s own 17/89 (19.1%) zero-rate is far too high to be
    this same coincidence (expected ~0.35 by chance) -- `A6`'s zero
    records really are systematically different, not luck.

    **Refined conclusion: the real, clean signal is bytes 1, 2, and 3
    specifically** (each individually EXACTLY 0/163 and 0/110 on both
    divided tiles, `A6` nonzero on all three) -- `byte4` should be
    treated as part of the continuous trailing numeric `value` field, not
    a 3rd independent flag byte, and its own apparent near-agreement with
    the pattern was mostly coincidental magnitude, not real structure.

    ============================================================================
    A GENUINE, POSITIVE crack (not a refutation): the trailing "value"
    field (bytes 4-7) is very likely `eeu.mod`'s own named `length` field
    -- a real distance, in DECIMETERS -- confirmed by comparing its
    distribution against REAL point-to-point distances computed directly
    from this project's own already-cracked coordinate geometry (no new
    ground truth needed).
    ============================================================================
    For each of `A1_2389` and `A6`, computed the real haversine distance
    (meters) between every pair of consecutive decoded points, and
    compared the sorted distribution against the tail's own 8-byte
    records' trailing `value` field (as a plain little-endian uint32),
    divided by 10 (the standard decimeter-to-meter conversion):

        A1_2389: real dist (m)   min=9.5    p25=15.1   median=62.9  p75=148.6  max=5754.2
                 value/10 (m)    min=7.0    p25=24.4   median=47.0  p75=177.1  max=5709.0
        A6:      real dist (m)   min=7.7    p25=30.7   median=57.1  p75=117.9  max=6821.3
                 value/10 (m)    min=2.5    p25=16.7   median=25.0  p75=85.1   max=6476.9

    The MAXIMUM values are a striking, tight match on BOTH independent
    tiles -- `A1_2389`: 5709.0m vs. the real max 5754.2m (within 1%);
    `A6`: 6476.9m vs. the real max 6821.3m (within 5%) -- not the kind of
    agreement that happens by chance for two unrelated quantities pulled
    from a whole tile's own real geometry. The medians/percentiles are
    the same rough order of magnitude too (tens to low hundreds of
    meters), consistent with real road-segment span lengths. This is
    real, independent, positive confirmation -- via a completely
    different method than any per-record correspondence -- that `value`
    (bytes 4-7 of an 8-byte record) is a real distance/length value, most
    plausibly `eeu.mod`'s own named `length` leaf field on the `seg`
    record, stored in decimeters. Not exact-record-to-exact-point
    validated (the per-record<->per-point correspondence problem that's
    dogged this whole investigation is still open), but a real,
    independently-confirmed field identification nonetheless -- the
    FIRST semantic field name this project can attach to a specific byte
    range in this record, even though bytes 1-3's own meaning (the
    divided-status-correlated signal above) remains unnamed.

    ============================================================================
    A further attempt to NAME bytes 1-3: "local topology node id"
    (`left_node`/`right_node`, real `eeu.mod` field names) -- CLEANLY
    REFUTED, and a real structural difference found in `byte1`'s own
    VALUE (not just its zero-rate) between the 2 test tiles.
    ============================================================================
    `eeu.mod` also names `left_node`/`right_node` on the `seg` record --
    if `byte1` (a single byte, range 0-255) were a direct index into this
    project's own already-cracked LOCAL topology graph, its value could
    never exceed that tile's own real node count. On `A6`, `byte1` reaches
    253 -- but `A6`'s own real topology graph has only 186 nodes (max
    real node id 191). 253 > 191: `byte1` cannot be a direct local
    topology node index. A real, sharp, cheap refutation (one inequality
    check, no new ground truth needed).

    A real, separate observation surfaced while testing this: `byte1`'s
    own VALUE DISTRIBUTION has a genuinely different CHARACTER between
    the 2 tiles, independent of the divided-status zero-rate question --
    on `A1_2389` it is overwhelmingly dominated by just 2 close values
    (61 and 62, together 159/163 = 97.5% of records), while on `A6` it is
    spread across 14 distinct values up to 253 with no dominant value.
    Not yet explained -- a plausible, untested guess is some kind of
    per-road-run "chain"/grouping identifier that stays nearly constant
    across many consecutive records of the SAME real road (matching `A1`'s
    own simple, mostly-single-road tile) but varies more on a tile with
    more real sub-segments or cross-streets (`A6`) -- but this is
    speculation, not tested against anything independent yet.

    ============================================================================
    `mp0`'s OWN seg_list tail format -- a real, honest attempt, MULTIPLE
    hypotheses tried, ALL FAILED. A genuine wall for this session, not a
    quick-fix gap.
    ============================================================================
    `mp0` (the densest layer, real ground truth: the Vladimir Bashev/
    Svetlostruy/San Martin one-way-street tile, tile_id 88178, offset
    972,000,264) has a real ~13.8 bytes/point tail density (vs. `mg4`'s
    ~8.95) and a visibly different raw byte character. `parse_seg_tail_records()`
    (the `mg4`-validated model: 2-byte id, per-id-consistent length,
    every record ends in exactly `00 00`) was tried directly against the
    real 14,393-byte tail and TIMED OUT (15,000,000 steps) on the whole
    tail. Narrowing to short PREFIXES isolated the real problem: a
    50-byte prefix parses cleanly and fast (6 records, only 7 backtrack
    steps -- an almost-unambiguous fit), but even a 100-byte prefix
    fails to find ANY valid decomposition within budget. Inspecting the
    50-byte "solution" directly shows it's GARBAGE, not real structure --
    several of its own "records" start with a leading `0x00` byte,
    producing implausible 2-byte ids like `0x4e00`/`0x4800`/`0x6800`
    that don't look like anything seen in the real, validated `mg4`
    records (which never showed this leading-zero-byte pattern in a
    real id). This is the exact over-permissive trap this project has
    hit before (see the much earlier "single-count-field" refutation
    above): the `00 00`-terminator constraint that worked well for `mg4`
    is NOT tight enough to prevent false-positive parses on `mp0`'s
    different byte structure.

    **3 terminator-width variants tried, all fail differently** (2-byte
    `00 00`, 3-byte `00 00 00`, 4-byte `00 00 00 00`, each with a widened
    candidate-length range 4-24, tested on several prefix lengths): the
    2-byte terminator finds garbage (above); the 3-byte terminator
    exhausts its ENTIRE search space in a tiny, constant 24 steps
    regardless of prefix length (genuinely no valid decomposition
    exists under that rule, not a timeout); the 4-byte terminator fails
    IMMEDIATELY at step 1 (no candidate length even starting at position
    0 satisfies it). None of these represent `mp0`'s real record
    boundary rule.

    **Honest conclusion**: `mp0`'s `seg_list` tail needs a genuinely
    different structural model than `mg4`'s, not a parameter tweak on
    the same one -- consistent with `mp0` being a separately-populated,
    more detailed layer (per `eeu.mod`'s own schema, likely with MORE
    real per-segment attributes active at this zoom level than `mg4`
    ever populates, e.g. lane/ADAS/traffic-sign fields the schema names
    but this project has never seen populated data for). This is a real
    wall for this session -- multiple concrete hypotheses tried and
    cleanly refuted, not an unexplored gap. A future session's most
    promising next step: hand-inspect a much longer real stretch of this
    SAME tail (the 50-byte "clean" prefix as a starting anchor) byte by
    byte, the same painstaking way `mg4`'s own model was originally
    built, rather than another blind parameterized search.

    ==== UPDATE, a later session: FIRST REAL CRACK of a chunk of `mp0`'s
    own tail structure -- the "hand-inspect a longer stretch" step above
    was finally taken, and it worked ====
    Re-derived the Vladimir Bashev tail fresh from disk (`eeuz.mp0`,
    tile_id 88178, file offset 972,000,264) via `seg_tail_region()`
    (14,393 bytes). Raw byte-value histogram immediately showed 2 bytes
    (`0x44` and `0xf1`) each occurring roughly 1 in every 15 bytes --
    far too frequent to be organic per-record data, and a strong hint of
    a recurring structural tag. Searching for the literal 2-byte
    sequence `f1 44` found 829 hits, but ALL of them cluster in the tail
    HALF of the region (first hit at byte 3788 of 14,393; zero hits
    before that) -- the tail is NOT homogeneous, it splits into
    distinct zones, each apparently with its own encoding.

    **Zone 2 (tail bytes 3788-12,312, 8,524 bytes) is now a REAL,
    VALIDATED crack.** Every record in this zone starts with `[tag_byte:
    1 byte][0x44][0x00]` (confirmed constant across the whole zone), and
    comes in exactly 2 widths:
      - **7 bytes** (the common case): `[tag][0x44][0x00][idx: u16 LE]
        [subidx: 1 byte][value: 1 byte]`.
      - **11 bytes** (a "special"/extended case, directly analogous to
        `mg4`'s own bigger junction records): the SAME 7-byte layout
        with 4 extra bytes inserted right after the `0x00` and before
        `idx` -- `[tag][0x44][0x00][extra: 4 bytes][idx: u16 LE][subidx:
        1 byte][value: 1 byte]`.
    Proved this is the REAL rule, not another over-permissive false fit,
    with an exhaustive backward dynamic-program (every position either
    reaches the zone's own end exactly via a chain of 7s and 11s, or the
    whole thing fails -- no partial credit, no leftover bytes possible):
    **949 records, EXACT, ZERO-byte-leftover coverage of the entire
    8,524-byte zone** (477 width-7 + 472 width-11). A naive greedy
    parser (always try width 7 first) fails at exactly one point through
    pure bad luck -- a real 11-byte record's own 4 "extra" bytes happen
    to end in a value that locally LOOKS like the start of a fresh valid
    7-byte record -- but the exhaustive DP does not suffer from this
    since it requires GLOBAL, not just local, consistency to the zone's
    own true end.

    `idx` climbs steadily upward within each of 3 clean, distinct runs
    (0-498, then a hard reset down to 3-497, then a 2nd reset to 267+)
    -- **exactly 3 groups, matching this tile's own 3 real, named
    streets (Vladimir Bashev / Svetlostruy / San Martin) one-for-one.**
    This is strong, independent structural confirmation that `idx` is a
    genuine PER-STREET running segment/sub-record counter, not a
    tile-wide index -- and that street boundaries in this format are
    encoded purely by the counter resetting, with no explicit
    "street count" or "street length" header found (or needed) to
    detect them. `subidx` is small (0, 1, occasionally 2) and pairs of
    consecutive records sharing the same `idx` but `subidx=0`/`subidx=1`
    consistently show correlated `value` bytes (e.g. one whole street
    run alternates `value=0x83`/`subidx=0` with `value=0xcc-or-0xe1`/
    `subidx=1` for dozens of consecutive `idx` values in a row) --
    exactly the shape of a per-direction attribute pair (forward/
    backward), though which real-world attribute `value` encodes is
    NOT yet identified.

    **UPDATE, same session: the "missing subidx=1 marks the one-way
    direction" hypothesis was tested directly and CLEANLY REFUTED.** For
    each of the 2 fully-analyzable groups (group 2 is cut off almost
    immediately by this zone's own boundary, only 1 record visible),
    checked whether `idx` values missing a `subidx=1` record (i.e. only
    `subidx=0` present) cluster into a contiguous run -- the shape a
    real one-way STRETCH of a street would produce -- or scatter
    randomly. **Group 0**: 475 records, 284 distinct idx, 106 "only
    subidx=0" idx values (37%) vs. 174 "has both" (61%). **Group 1**:
    473 records, 239 distinct idx, 115 "only subidx=0" (48%) vs. 103
    "has both" (43%). In BOTH groups, the "only subidx=0" idx values are
    scattered essentially at random throughout the whole idx range (e.g.
    group 0: 34, 51, 52, 77, 83, 87, 88, 97, 98, 100, 102, 106... --
    interleaved with "has both" idx values the entire way, no contiguous
    block). A real directional (one-way) property should show up as a
    contiguous run where the reverse direction is systematically absent,
    not scattered presence/absence -- this is a clean, real refutation,
    not just inconclusive noise. **Revised interpretation**: `subidx`
    presence more likely reflects a sparse PER-SEGMENT ATTRIBUTE FLAG
    (present on some individual segments, absent on others, independent
    of neighboring segments) than forward/backward direction -- e.g. a
    signage or local-restriction marker. Whether Vladimir Bashev's own
    one-way status is encoded here at all (vs. elsewhere, e.g. `eeu.mod`'s
    own `restr_left`/`restr_right` fields already tested and refuted
    against `mg4`, or a completely different part of `mp0`'s own record)
    remains open.

    ==== UPDATE, same session: zone 3 (tail bytes 12,312-14,393, 2,074
    bytes) hand-inspected properly -- a REAL, PLAUSIBLE SPEED-LIMIT
    crack found, plus 2 more sub-structures characterized ====
    Zone 3 is itself NOT one uniform structure either -- it splits into
    (at least) 3 further sub-zones:

    **Sub-zone 3a (zone-3 bytes 0-822, 822 bytes): a real, exhaustively-
    validated record format, and a strong speed-limit candidate.** Naive
    "split on the next `0x04` byte" parsing looked plausible at first but
    is WRONG -- it breaks the instant `idx`'s own low byte happens to
    equal `0x04` (e.g. `idx=0x0104`), producing a spurious 1-byte
    "record". Fixed with the same exhaustive backward-DP technique used
    for zone 2 (candidate widths 5-8, validity = last byte of the
    candidate slice is `0x04`, requiring a fully consistent chain to the
    zone's own true end): **131 records, exact, zero-leftover coverage**,
    idx strictly non-decreasing throughout (12 to 490 -- the SAME
    numeric range as zone 2's own per-street `idx` counters, strongly
    suggesting this is a 2nd, sparser attribute list over the SAME
    per-street segment numbering). Record shape: `[idx: u16 LE][type: 1
    byte][...][speed-like byte][0x04 terminator]`, total width 6 or 7
    bytes. The `type` byte (9 distinct values seen: `0x02`,
    `0x12`, `0x40`, `0x49`, `0x50`, `0x80`, `0x85`, `0x90`, `0xc0`)
    DETERMINISTICALLY selects the width (each type maps to exactly ONE
    width, verified directly, no exceptions) -- `{0x49,0x85,0xc0}` are
    always 7 bytes, the rest always 6. **The byte immediately before the
    terminator, across almost every type, lands on one of exactly 4
    values: `0x1e`(30), `0x28`(40), `0x32`(50), `0x50`(80)** -- all real,
    standard urban/rural speed limits in km/h, and nothing else (types
    `0x02`/`0x12` show `0x00` instead, plausibly "no speed limit
    recorded" for that segment). This is a strong, plausible candidate
    for the on-disk location of the firmware's own known
    `db_seg_speed_V004` accessor (README S2.6/`research/swl_5238_reader.py`)
    -- not yet cross-checked against real ground truth (no confirmed
    real-world speed limit for any of this project's ground-truth
    points yet), so treated as a strong lead, not a closed crack.

    **Sub-zone 3b (zone-3 bytes 822-1018, 196 bytes): a clean, monotonic
    list, meaning not yet identified.** 98 `u16 LE` values, ALL exact
    multiples of 4, strictly non-decreasing, spanning 196 to 844 (49 to
    211 in units of 4). Real and clean, but no working hypothesis yet
    for what it indexes (candidates: byte offsets into a 4-byte-stride
    table, or a scaled point/vertex reference).

    **Sub-zone 3c (zone-3 bytes 1018-2074, 1,056 bytes): partially
    characterized, itself probably not uniform.** 528 `u16 LE` values,
    signed-looking (roughly half negative). The first ~349 values are
    small (single/double-digit magnitude, consistent with coordinate or
    positional DELTAS), then the character changes -- occasional much
    larger values appear (-1532, 1279, -11516, ...) with some of them
    REPEATING exactly, which argues against pure organic delta noise and
    suggests a further, not-yet-isolated sub-boundary partway through.
    Not solved.

    **Overall**: zone 1 (tail bytes 0-3,788) remains completely
    uncharacterized. This session's real, validated positive results are
    zone 2 (949 records, full 8,524-byte coverage) and zone-3's sub-zone
    3a (131 records, full 822-byte coverage, with a genuine plausible
    semantic identification -- speed limit) -- the first time this
    project has both structurally AND semantically cracked any part of
    `mp0`'s own tail. Sub-zones 3b/3c and zone 1 are honest open work for
    a future session.

    ==== UPDATE, same session: zone 2's own `(tag, subidx)` slots
    characterized by value distribution -- ONE clean binary flag found
    ====
    Grouped all 949 zone-2 records by their `(tag byte0, subidx)` pair
    and looked at each slot's `value` byte distribution (the same "few
    distinct values = categorical, many = numeric" heuristic that led to
    the sub-zone-3a speed-limit find). Results:
      - **`tag=0xf4, subidx=1` (70 records): a clean, genuine BINARY
        flag** -- only 2 distinct values ever seen, `0xcc` (43 records,
        61%) and `0xe1` (27 records, 39%). The single cleanest
        categorical slot in the whole zone; `0xf4` never co-occurs with
        any other `subidx`. A real candidate for a boolean road property
        (one-way/two-way is an obvious guess, since this exact tile has
        a real, confirmed one-way street) -- NOT yet testable against
        ground truth, for the same reason the missing-subidx=1
        hypothesis above couldn't be localized: no confirmed `idx`<->
        point/segment mapping exists yet (2 independent attempts this
        session -- point-index-with-topology-shift, and an
        artificially-sorted edge-ordinal position -- both failed to
        produce usable evidence; see below).
      - `tag=0xf3, subidx=2` (28 records) and `tag=0xf1, subidx=3` (16
        records): small categorical-LOOKING enums with one dominant
        value (82% and 87.5% respectively) plus rare others -- plausibly
        real categories, but not as clean as `0xf4/1`.
      - `tag=0xf1, subidx=0` (539 records, 52 distinct values, range
        110-247) and `subidx=1` (248 records, 18 distinct, range 0-246):
        clearly NUMERIC/continuous, not flags -- too many distinct
        values across too narrow a record count to be a small enum.
        Real candidates: a name/label reference id, or a continuous
        measurement (width, elevation, etc.); not investigated further.

    ==== UPDATE, same session: 2 independent attempts to map `idx` to a
    real point/edge, to localize Vladimir Bashev's own segments -- BOTH
    FAILED, honestly documented so a future session doesn't repeat them
    ====
    Used `resolve_topology_adjacency()` (already validated elsewhere in
    this file) on this exact tile/feature: confirms the real ground-
    truth edge (point 198 <-> point 269, Vladimir Bashev) IS present at
    "high" confidence (437 total real edges, shift=1). Attempt 1: assume
    `idx` approximately equals point index (reusing this feature's own
    validated topology shift=1) -- checked `idx` values near 195-198 and
    269-277 in sub-zone 3a; ALL show `speed=0x00` (no data), which is
    UNINFORMATIVE (0 is the single most common speed value overall, 61 of
    131 records), not a confirming or refuting result. Attempt 2:
    compute edge (198,269)'s ordinal position in `resolve_topology_
    adjacency()`'s returned edge list -- landed on position 230, and
    sub-zone-3a's `idx=230` DOES have real speed data (`0x28`=40 km/h,
    close to but not exactly the user's confirmed real 50 km/h) -- but
    this is NOT real evidence: the returned edge list is sorted by plain
    Python tuple comparison on `(point_a, point_b)`, an ARTIFACT of how
    this project's own code presents results, with no reason to relate
    to how the original encoder ordered anything on disk. Correctly
    caught and disclaimed before being reported as a finding, not after.
    **Honest conclusion**: localizing which `idx`/`seg_list` records
    belong to which real, named street remains unsolved. The real fix
    would be recovering the topology table's own RAW on-disk record
    order for this feature (not point index, not an artificial sort) and
    testing whether `idx` tracks that instead -- a genuinely uncertain,
    non-trivial next step, not attempted further this session.

    ==== UPDATE: firmware emulation used to probe byte1's real role ====
    Built a Unicorn-based (UC_ARCH_PPC/UC_MODE_BIG_ENDIAN) "emulation
    classifier" over `FHDD6.FLI`'s real code region (see
    `research/swl_5238_reader.py` for the full prologue-scan/emulator
    methodology). Fed a fake `seg_list`-record pointer (matching this
    project's confirmed 8-byte layout: `id`@0-1, `byte1`@2, `byte2`@3,
    `byte3`@4... -- see caveat below) as arg1 to thousands of real
    candidate functions and logged which small-offset bytes each one
    actually reads. Two close-looking candidates turned out to be
    unrelated (a genuine H:M:S-to-milliseconds time conversion; a
    magic-constant mode dispatcher) -- a real, useful negative result:
    "reads a couple of small bytes near offset 0-4 of arg1" is a common
    shape across this 9MB codebase and is NOT selective for `seg_list`
    accessors on its own.

    One candidate (firmware offset 2,069,968 / VA 0x001f95d0) is a much
    stronger match: it reads the id (offset 0, halfword), `byte1`
    (offset 2, byte) and the confirmed `length` field (offset 4, word)
    from its arg1, then:
      1. resolves `id` through a small lookup/insert table (0x54-byte
         records),
      2. resolves `length` (+0) through a second cache table (0x60-byte
         records, linear-scan-then-fallback),
      3. uses the resolved index to walk a THIRD table of 0x78-byte
         records via a `-1`-terminated linked chain (`next` pointer at
         record offset 0x74), testing two different bits (`&1`, `&2`)
         of per-record flag fields at each step,
      4. on a match, writes a halfword field (record offset 4) into the
         function's OWN 2nd argument (its output parameter) and calls a
         formatting/lookup routine tagged with a fixed constant
         (0x6a140202).
    This is consistent with a **name/label or junction-connectivity
    resolver** that walks nearby segments sharing a junction and picks
    one matching a reference byte (record offset 6) -- i.e. `byte1`
    functions here as part of a LOOKUP KEY feeding a multi-table
    resolution chain, not as a standalone boolean read directly off the
    struct. This refines (does not overturn) the "divided-road signal"
    correlation already established: it's still true that bytes1-3's
    zero-rate correlates cleanly with divided/non-divided status on our
    2 precisely-matched ground-truth tiles, but this trace suggests that
    correlation may be a downstream EFFECT of whatever `byte1` actually
    indexes into (its true identity is still unnamed), not a direct
    "divided flag" bit read in isolation.

    Important caveat: `0x1f95d0`'s own callers could not be located by
    static `bl`/`lis`+`addi` cross-reference search inside the scanned
    9MB region -- this codebase calls almost everything indirectly
    (computed absolute address via `lis`/`addi` into `mtlr`+`blrl`), and
    no matching load sequence for this address was found in-region, so
    it is likely reached through a runtime function-pointer table this
    project cannot yet locate. That means the assumption that arg1 here
    IS a `seg_list` record pointer (rather than some structurally
    similar but unrelated record) is plausible but NOT proven by a
    confirmed real call site -- flagged here explicitly rather than
    overstated. `0x1f70d0`/`0x1f7738` (2 of its 3 callees) turned out to
    be two different mid-function entry points of the SAME large,
    generic shared table utility (starting at `0x1f70c0`), not
    `seg_list`-specific code, so they were not traced further.

    Tried to locate `0x1f95d0`'s own caller 3 independent ways, all
    negative: (1) direct `bl` cross-reference scan of the 9MB code
    region -- only finds its own 3 internal calls; (2) `lis`/`addi`
    absolute-address-load scan (same region) -- zero matches; (3) raw
    4-byte big-endian literal-pointer search across the ENTIRE 85MB
    firmware image -- zero matches. A genuine, 3-way-confirmed dead end
    for this specific candidate, not a lack of effort. Also tried to
    read the real byte contents of the 3 lookup tables this function
    itself indexes into (computed their absolute addresses from the
    `lis`/`addi` pairs: ~`0xf6a51878`-`0xf6a5f3b8`) -- these fall far
    outside the 85MB file's own size, confirming they're RAM/data
    addresses in a completely different address range than the code
    region (where file-offset-as-VA has worked reliably so far); this
    project has no known file-offset-to-RAM-address mapping for static
    data, so these tables' real contents remain unreadable from the
    file. A 4th genuine wall for this specific lead.

    Disassembled the other 5 remaining emulation-classifier candidates
    from the same "1-byte read at offset 1/2/3" filter (see
    `research/swl_5238_reader.py` for the technique) to completion:
    - Offset 2,383,136: confirmed false positive, a magic-constant mode
      dispatcher (already documented in swl_5238_reader.py).
    - Offset 3,254,056: a tiny, inconclusive stack-buffer-init function;
      no clear connection either way.
    - Offset 3,496,552: only partially traced; inconclusive.
    - Offset 3,409,852: reads bytes at arg1 offsets 0, 2, 3, 6, AND 7
      individually (as single bytes, via separate `lbz`s) to reset a
      112-byte (`0x70`) table record indexed by the offset-2 byte.
      Reading offsets 6 and 7 as 2 SEPARATE bytes conflicts with this
      project's already-confirmed, independently-cross-validated
      `length` field occupying offsets 4-7 as ONE 4-byte value -- so
      this function is most likely walking a DIFFERENT record type that
      merely shares the same front-of-struct shape (id@0, category@2,
      sub-category@3), not `seg_list` itself. A useful negative result,
      not a threat to the `length`-field crack.
    - Offset 3,482,796: uses FLOATING-POINT instructions (`lfd`, `frsp`,
      `fadds`, `lfs`) and reads a 16-bit value at offset 6 (`lha`) fed
      into a branchless `abs(a-b)`-style delta computation against a
      44-byte-stride (`0x2c`) table, compared as a bounding-box-style
      test (2 signed comparisons ANDed via condition-register tricks --
      the same idiom this project's own coordinate-decoding work uses
      elsewhere). This looks like NODE/COORDINATE geometry logic, not a
      road-attribute accessor -- almost certainly another false
      positive for this specific search, sharing only the same
      "reads 2 small bytes near the front" shape that the classifier's
      filter keys on.

    **Overall conclusion for this candidate set**: of 8 total candidates
    checked across 2 sessions, only `0x1f95d0` (offset 2,069,968) is a
    strong, real match consuming `id`/`byte1`/`length` together in a way
    consistent with `seg_list`, and even it could not be confirmed via a
    real call site. The emulation-classifier technique is validated and
    works, but this specific candidate pool is now exhausted without a
    single-purpose, provably-`seg_list` accessor function identified.
    """
    if declen is None:
        declen = len(raw)
    if features is None:
        features = decode_features(raw, declen)

    _FIELDCOUNT_BY_LOW_BYTE = {
        0x01: 1, 0x11: 1,
        0x22: 2, 0x02: 2,
        0x23: 3, 0x32: 3, 0x43: 3, 0x63: 3,
        0xc4: 4,
    }

    # Anchor the search after the LAST feature's block_end (the overall
    # coordinate-region end) -- matches the 2-feature tile's observed
    # zero-gap behavior; _find_topology_table_start()'s search window
    # covers the single-feature tile's 104-byte gap case too. See the
    # docstring above for why this (rather than each feature's own
    # block_end) is the anchor used.
    search_from = max(feat["block_end"] for feat in features) if features else 0

    n = len(features)
    n_records_list = [len(feat["points"]) + 1 for feat in features]

    # Greedy, tightest-cap-first, non-overlapping reservation (see the
    # docstring above for why this replaced a simple per-feature
    # sequential scan). Every PENDING feature is tried, from the same
    # shared `search_from`, against its own cap ladder (tight formula
    # first, then the shared looser rungs); whichever pending feature
    # succeeds at the lowest rung "wins" this round, its table is
    # reserved, and the next round repeats over the remaining pending
    # features (now excluding the reserved byte range). Stops when no
    # remaining pending feature can be found at any rung.
    resolved_start = [None] * n
    reserved = []
    pending = list(range(n))
    while pending:
        best_i = None
        best_rank = None
        best_start = None
        for i in pending:
            nr = n_records_list[i]
            tight = nr * 6 + 200
            cap_ladder = sorted(set(
                c for c in (tight,) + _TOPOLOGY_CAP_LADDER_EXTRA if c >= tight))
            for rank, cap_try in enumerate(cap_ladder):
                s = _find_topology_table_start(
                    raw, declen, nr, search_from, cap=cap_try, reserved=reserved)
                if s is not None:
                    if best_rank is None or rank < best_rank:
                        best_rank, best_i, best_start = rank, i, s
                    break  # this feature's own tightest available match -- don't loosen further
        if best_i is None:
            break  # no remaining pending feature can be located anywhere
        resolved_start[best_i] = best_start
        reserved.append((best_start, best_start + n_records_list[best_i] * 10))
        pending.remove(best_i)

    results = []
    for i, feat in enumerate(features):
        n_records = n_records_list[i]
        table_start = resolved_start[i]
        found = table_start is not None
        records = []
        edges = []
        table_end = None
        if found:
            table_end = table_start + n_records * 10
            for k in range(n_records):
                pos = table_start + k * 10
                tag_bytes = raw[pos:pos + 2]
                a, b, c, d = struct.unpack_from("<HHHH", raw, pos + 2)
                low = tag_bytes[0]
                nfields = _FIELDCOUNT_BY_LOW_BYTE.get(low)
                allf = [a, b, c, d]
                if nfields is None:
                    # best-effort fallback: strip trailing zero fields,
                    # keep at least 2 -- see caveat in the docstring above
                    nfields = 4
                    while nfields > 2 and allf[nfields - 1] == 0:
                        nfields -= 1
                fields = tuple(allf[:nfields])
                records.append({
                    "offset": pos,
                    "tag": tag_bytes.hex(),
                    "fields": fields,
                })
                if k == 0:
                    continue  # record 0 is the header, not a real edge list -- exclude from the graph
                for j in range(len(fields) - 1):
                    edges.append((fields[j], fields[j + 1]))
        degree = {}
        for u, v in edges:
            degree[u] = degree.get(u, 0) + 1
            degree[v] = degree.get(v, 0) + 1
        results.append({
            "found": found,
            "table_start": table_start,
            "table_end": table_end,
            "records": records,
            "graph_degree": degree,
        })
    return results


# ---------------------------------------------------------------------------
# `seg_list` TAIL REGION -- real, working per-ID-length record parser for
# MG4-FORMAT tiles (real structure, validated on 2 tiles with precise real
# ground truth; the "divided road" hypothesis it initially suggested was
# tested against 2 MORE ground-truth tiles and REFUTED -- see
# decode_topology()'s own docstring, "A REAL PER-ID-LENGTH PARSER" section,
# for the full writeup and all 6 ground-truth points). NOT yet extended to
# `mp0`-format tiles (confirmed a genuinely different byte structure --
# a wide-candidate-range attempt exhausted 15,000,000 search steps with no
# solution).
# ---------------------------------------------------------------------------
_SEG_TAIL_CANDIDATE_LENGTHS = (8, 9, 10, 4, 11, 12, 13, 14, 6, 7, 5)


def seg_tail_region(raw, declen, feature, features, table_start=None):
    """Return the raw bytes of one feature's own `seg_list` tail (the region
    immediately after its local topology table, up to the next feature's own
    topology table or the tile's end) -- the region `decode_topology()`
    itself stops at. For a SINGLE-feature tile this is exact (bounded by
    `declen`); for a MULTI-feature tile the true per-feature boundary is
    NOT reliably locatable yet (an attempt via `_find_topology_table_start`
    on the next feature produced an implausible, too-short result on a real
    multi-feature tile -- see the docstring above) -- only use this on
    single-feature tiles until that's fixed."""
    n = len(feature["points"])
    if table_start is None:
        last_block_end = max(f["block_end"] for f in features)
        table_start = _find_topology_table_start(raw, declen, n + 1, last_block_end)
    tail_start = table_start + (n + 1) * 10
    return raw[tail_start:declen]


def parse_seg_tail_records(tail, max_steps=8_000_000, candidate_lengths=_SEG_TAIL_CANDIDATE_LENGTHS):
    """Parse a `seg_list` tail (see `seg_tail_region()`) into records using
    the real, validated model: each record starts with a 2-byte LE id;
    the SAME id always implies the SAME record length (learned on the fly,
    not assumed); every valid record ends in exactly `\\x00\\x00`. This is a
    constraint-propagation backtracking search, NOT a blind formula search
    -- the `00 00`-terminator requirement is what keeps it from the
    over-permissive trap documented in `decode_topology()`'s own docstring
    (a blind "any length that consumes the tail" search there was refuted).

    Returns `(ok, records, id_length_map, steps)` where `records` is a list
    of `(offset, id, length)` tuples in tail-relative order (empty if
    `ok` is False). Validated (real ground truth, see `decode_topology()`'s
    docstring): converges in ~2,000-4,500 steps on real MG4-format tiles
    with 190-230 points; has NOT been validated on tiles much larger than
    that (larger real tiles may need a bigger `max_steps` budget, or may
    need per-feature boundary fixes for multi-feature tiles -- see
    `seg_tail_region()`'s own caveat)."""
    n = len(tail)
    id_len = {}
    steps = [0]
    records = []

    def valid_end(pos, length):
        return pos + length <= n and tail[pos + length - 2:pos + length] == b"\x00\x00"

    def rec(pos):
        steps[0] += 1
        if steps[0] > max_steps:
            raise TimeoutError
        if pos == n:
            return True
        if pos + 2 > n:
            return False
        idv = struct.unpack_from("<H", tail, pos)[0]
        if idv in id_len:
            length = id_len[idv]
            if not valid_end(pos, length):
                return False
            records.append((pos, idv, length))
            ok = rec(pos + length)
            if not ok:
                records.pop()
            return ok
        for length in candidate_lengths:
            if not valid_end(pos, length):
                continue
            id_len[idv] = length
            records.append((pos, idv, length))
            if rec(pos + length):
                return True
            records.pop()
            del id_len[idv]
        return False

    try:
        ok = rec(0)
    except TimeoutError:
        return False, [], {}, steps[0]
    return ok, records, id_len, steps[0]


# ---------------------------------------------------------------------------
# NODE-ID <-> COORDINATE MAPPING -- CRACKED (later session, real ground truth
# from `mg2` tile_id 20597 + re-tested against the earlier `mp0` tile_id 91124
# ground truth). See resolve_topology_adjacency() below for the full writeup;
# this comment block just orients a reader jumping straight to this section.
#
# THE MECHANISM: a topology-table record does NOT reference an adjacent
# point's node-id directly (that hypothesis -- tested exhaustively in prior
# sessions, see decode_topology()'s docstring -- was always going to score
# ~0/N, and did). Instead, two points that are really adjacent in the road
# network have records whose FIELD VALUES SHARE exactly one common value --
# a per-edge "link id" -- rather than one record naming the other point's
# own id. Concretely, on the mg2 ground-truth tile, consecutive real edges'
# records look like (point 188's fields){46,164,179} / (point 191's fields)
# {162,163,164} -- point 191 is never mentioned by number anywhere in point
# 188's record, but the value 164 is present in BOTH, and 164 appears in
# NO other point's record on this feature. This is a classic "edge-id"
# (winged-edge-style) topology encoding, not a direct adjacency-list one --
# which is exactly why every previous session's "does record i reference
# point j" family of tests (direct membership, rotation search, "edge
# exists anywhere in the reconstructed A-B/B-C/C-D chain graph") scored at
# or near chance: those tests were looking for the wrong relationship.
#
# THE COMPLICATION: which table record belongs to which decode_features()
# point index is offset by a small, PER-TILE constant ("shift") that isn't
# always the same. `record[point_index + 1]` (i.e. shift=1, skipping one
# leading header record) is correct on the mg2 tile and on the original
# 83-point mg4 reference tile, but the mp0 ground-truth tile (tile_id
# 91124) needs shift=2. This matches the module's older, previously
# inconclusive note (decode_tile_header()'s word[10] discussion) that
# whether a feature's table carries a distinct leading "header" record
# in front of its real per-point records is tile/feature-dependent, not a
# universal constant -- confirmed here with a second, independent data
# point (a THIRD single-feature mp0 tile, tile_id 79147, also needed
# shift=1, not always-2 -- so this is genuinely per-tile, not a
# per-LAYER constant, and must be resolved per feature, not hardcoded).
#
# THE FIX: brute-force every candidate shift, build the shared-value graph
# it implies, and use the feature's OWN decoded (lon,lat) coordinates to
# score each candidate by the real-world distance its implied edges
# connect -- genuine road topology only ever connects geometrically CLOSE
# points, so the correct shift stands out as a dramatic minimum in median
# edge distance, while every wrong shift produces edges between
# essentially random, far-apart points (median distances 5-10x higher).
# This needs no ground truth at all (only the feature's own already-decoded
# points), which is what makes it a general, reusable primitive rather
# than a one-off fit to the two known ground-truth tiles.
# ---------------------------------------------------------------------------


def _shared_value_edges(records, n_points, n_records, shift, min_group=2, max_group=6):
    """Build the undirected point-index edge set implied by treating
    `records[(i + shift) % n_records]["fields"]` as point i's set of
    "link ids", and connecting any two (or few) points whose link-id sets
    share a common value. `max_group` bounds how many points a single
    shared value is allowed to connect (a real per-edge link id is shared
    by exactly 2 points; values shared by a handful more are treated as
    small real junctions -- see resolve_topology_adjacency()'s docstring;
    values shared by MORE than `max_group` points are almost certainly a
    generic/common field value, e.g. a padding 0, not a genuine link id,
    and are dropped so they don't create a clique of bogus edges).
    Returns a set of (min(i,j), max(i,j)) tuples."""
    value_to_points = {}
    for i in range(n_points):
        idx = (i + shift) % n_records
        for v in records[idx]["fields"]:
            value_to_points.setdefault(v, []).append(i)
    edges = set()
    for pts in value_to_points.values():
        if min_group <= len(pts) <= max_group:
            for x in range(len(pts)):
                for y in range(x + 1, len(pts)):
                    a, b = pts[x], pts[y]
                    edges.add((a, b) if a < b else (b, a))
    return edges


def _haversine_ish_m(p1, p2):
    """Cheap equirectangular-projection distance in meters between two
    (lon, lat) points -- fine at the sub-tile scale resolve_topology_
    adjacency() uses this for (single tiles never span enough latitude for
    the flat-projection error to matter)."""
    lon1, lat1 = p1
    lon2, lat2 = p2
    m_per_deg_lat = 111_320.0
    m_per_deg_lon = 111_320.0 * math.cos(math.radians((lat1 + lat2) / 2))
    dx = (lon1 - lon2) * m_per_deg_lon
    dy = (lat1 - lat2) * m_per_deg_lat
    return math.hypot(dx, dy)


def resolve_topology_adjacency(raw, declen=None, features=None, topo=None,
                                max_shift_scan=None, implausible_median_m=2000,
                                max_edge_m=200.0):
    """CRACKED (this session) -- resolves the node-id<->coordinate mapping
    that decode_topology() explicitly could NOT (see that function's long
    "NOT SOLVED" section). Returns, per feature, a real point-index adjacency
    graph -- "point i is really connected to points [...]" -- usable
    directly against decode_features()' own point indices, closing the gap
    that blocked synthesizing a valid topology entry for a newly inserted
    road (README §8 item 5).

    MECHANISM (see the big comment block above this function for the full
    writeup): a topology record does not reference its neighbor's point
    index directly. Instead, two really-adjacent points' records share one
    common FIELD VALUE (a per-edge "link id"); which table record belongs to
    which point index is offset by a small per-tile/per-feature constant
    ("shift", typically the number of non-point "header" records at the
    front of the table) that must be discovered per feature, not assumed
    constant. This function does both steps: for a range of candidate
    shifts, it builds the shared-value graph via `_shared_value_edges()`,
    then scores each candidate using the feature's OWN already-decoded
    (lon,lat) points -- the correct shift is the one whose implied edges
    connect geometrically CLOSE points (real road topology never has a
    "real" edge between points hundreds of meters apart at these zoom
    levels), scored as the MEDIAN great-circle-ish distance of all implied
    edges. No ground truth or cross-file lookup is required; only the
    feature's own decode_features() output.

    VALIDATED against BOTH of this project's real, human-verified
    ground-truth connectivity examples:
      - `mg2` tile_id 20597 (this session's new ground truth, README §3.6/
        §8, 203-point feature, 17 confirmed real points / 16 confirmed real
        sequential edges): auto-detected shift=1 (global minimum over the
        FULL 0..203 shift range, median edge distance 49.7m vs the next-best
        shift's 127.2m -- a clean, unambiguous 2.6x gap), and at that shift
        ALL 16/16 real edges are present in the shared-value graph (vs a
        1.07% random-pair / 5.06% nearby-pair chance baseline measured on
        this same tile -- 16/16 at that base rate has a chance probability
        around 1e-21).
      - `mp0` tile_id 91124 (the earlier session's ground truth, 306-point
        feature, 18 confirmed real edges, offset 1,003,495,557): auto-
        detected shift=2 (global minimum over the full 0..306 range, median
        41m vs the next-best shift's 395m -- a 10x gap), and at that shift
        16/18 real edges are present (89%, vs a chance baseline computed on
        this tile of 0.8-0.83%). The 2 misses both touch the SAME point
        (259): its record's fields never share a value with either
        neighbor's (253 or 270) record, while the immediately-preceding
        point 258's record DOES share a value with 270 (via link id 352) --
        i.e. the real topological edge into that stretch most likely
        actually runs through point 258, not 259; 258 and 259 are very
        probably two near-duplicate vertices at the same real junction (the
        kind of thing a human clicking a small map marker would not
        reliably distinguish), not a failure of the shared-value rule
        itself. Not fully confirmed (no coordinate cross-check was
        conclusive at this junction), but the clean 16/18 with both misses
        localized to one specific point is a categorically different,
        far-stronger result than every previous session's hypothesis (best
        prior result on this exact tile: 2/18, chance-level).
      - IMPORTANT, checked directly: shift is NOT a fixed per-LAYER
        constant (e.g. "mp0 always needs shift=2") -- a THIRD, independent
        single-feature `mp0` tile (tile_id 79147, 91 points, no ground
        truth, only structural plausibility) auto-detects shift=1 (median
        355m vs next-best 853m, a 2.4x gap), and the original 83-point
        `mg4` reference tile (offset 5,138,331, the tile decode_topology()'s
        docstring has always used as its worked example) auto-detects
        shift=1 too (median 77m vs next-best 146m) with a clean, plausible
        road-like degree histogram ({1: 4, 2: 76, 3: 2, 4: 1} -- 4
        endpoints, 76 ordinary through-points, 3 small junctions for an
        83-point chain -- much more plausible than the OLD, wrong
        chain-within-one-record interpretation's inflated {1:15, 2:79,
        3:11} / 105-node count for the same tile). This is genuinely a
        PER-FEATURE property that must be resolved by this function's own
        search, not hardcoded from the layer name.

    CAVEAT, found directly, not hypothetical: on SMALL features (tested:
    31-point and 13-point single-feature mp0 tiles) the auto-detected
    "best" shift's median edge distance was implausibly large (13.9km and
    23.0km respectively -- far beyond any real road-vertex spacing), with
    only a weak gap to the next-best candidate. This is a real, measured
    failure mode, not a hedge: too few points means too few implied edges
    for the geometric-distance signal to be reliable, and/or
    `_find_topology_table_start()`'s own small-integer-collision weakness
    (documented in that function's docstring) is more likely to mis-locate
    the table entirely on a short feature. `implausible_median_m` (default
    2000, i.e. 2km -- generously above any real observed correct-shift
    median in this session's samples, all under 400m) gates this: a result
    whose best median exceeds it is reported with `"confidence": "low"`
    rather than silently returned as if it were as trustworthy as the
    validated cases. ALWAYS check `"confidence"` before trusting a
    feature's adjacency for anything correctness-sensitive (e.g. writing a
    new topology table).

    AT-SCALE CHARACTERIZATION + FIX (this session, later pass): the two
    ground-truth tiles above are real but only 2 samples. A broader check --
    every feature (257 total, 5 layers: mg4/mg3/mg2/mg1/mp0) in a real
    ~11km x 11km box around Sofia, Bulgaria, `want_adjacency=True` -- found
    only 161/257 (62.6%) reaching `"confidence": "high"` BEFORE this
    session's changes (1 "low", 95 "none"). Root-causing the 95 "none"s
    (see `_find_topology_table_start()`'s and `decode_topology()`'s
    docstrings for the full mechanism writeups) found TWO real, distinct,
    independently-fixed bugs:
      1. `_find_topology_table_start()`'s magnitude `cap` and `max_gap`
         were fit to two small reference tiles (83 and 392+154 points) and
         were far too tight at real dense-urban scale (real field values up
         to ~49,664 measured vs. an old cap of ~2,000-ish for a
         similar-sized feature) -- causing 94/95 of the "none"s outright
         (`"found": False`). Fixed with a cap LADDER (tight formula first,
         escalating only if nothing is found at all) plus a wider search
         window.
      2. Raising the cap on its own exposed a SEPARATE, more serious
         problem on multi-feature tiles: a large feature searched with a
         loosened cap could match a byte-misaligned ECHO of a smaller
         sibling feature's own genuine table (directly confirmed on a real
         tile, `mp0` 88098, by inspecting the raw bytes) -- silently
         trading a correct result for a fabricated one while returning
         `"confidence": "high"` either way, undetectable from this
         function's output alone. Fixed in `decode_topology()` by resolving
         a tile's features in order of increasing minimal-cap-needed
         (tightest/most-confident first) with each resolved feature's byte
         range RESERVED against every other feature's search, rather than
         a blind per-feature sequential scan -- see that function's
         docstring for the full writeup, including a second, independently
         -confirmed instance of the same pre-existing bug found on tile
         `mp0` 91122 (a 4-feature tile) that predates ANY of this session's
         changes.

      Net result after BOTH fixes: 194/257 (75.5%) high confidence, 1 low,
      62 none -- a real +33-feature gain (+12.9 points), re-validated to
      change NEITHER ground-truth tile's result at all (`mg2` 20597 and
      `mp0` 91124 both reproduce their exact table_start/shift/edge results
      above, unchanged). Diffing the full before/after feature-by-feature:
      160 features were already high and stayed high, 34 went from
      not-high to high, and exactly 1 went from high to not-high -- and
      that one (`mp0` 91122, feature 3, 274 points) was independently
      confirmed to be bug #2 above (its old "high" result's byte range
      provably overlaps the newly-recovered, tightly-locatable tables of
      3 OTHER features in the same tile), i.e. a correction, not a loss.

      Size-vs-confidence, re-measured on the FINAL (post-fix) numbers, by
      point-count bucket (n=feature count in that bucket, high%=fraction
      reaching "high"): [0,10): 10, 90%; [10,20): 7, 86%; [20,30): 7, 71%;
      [30,50): 40, 80%; [50,80): 30, 63%; [80,120): 11, 82%; [120,200): 20,
      85%; [200,400): 114, 73%; [400,+): 18, 78%. There is NO clean
      "small features fail, large ones succeed" correlation -- confidence
      failure is fairly evenly spread (63-90%) across every size bucket;
      the remaining 63 non-high features (61 "found": False, 1 zero-edge,
      1 implausible-median) span point counts from 2 to 441, and are 54/63
      `mp0`, 5 `mg1`, 4 `mg2` -- concentrated by LAYER (dense street-level
      `mp0` tiles, which have the most multi-feature tiles and the longest
      per-feature record runs) more than by feature size.

    CONCRETE "found: False" EXAMPLE, user-reported, investigated directly
    (this session): a user right-clicked/reported 5 real points they
    expected connected -- `mp0` tile_id 88189 (offset 972,122,528), points
    at (23.35035,42.68571)/"SITNYAKOVO", (23.34998,42.68592) and
    (23.34966,42.68611)/"BOYCHO VOYVODA" x2, (23.34434,42.68906)/"MIZIA",
    (23.34238,42.68971) -- decode_features() point_index 189/175/172/54/25,
    ALL in this tile's feature 0 (278 points). Real-world distances between
    each reported-adjacent pair (33.7m-545.3m, computed directly from their
    own decoded coordinates) are entirely plausible real road spacing, so
    this is not a case of the user mis-reading unrelated points -- and
    directly confirms this specific feature is a genuine instance of the
    "found: False" bucket characterized above, not a new bug: `decode_
    topology()` cannot locate feature 0's own table anywhere in this tile.
    Manually re-probed well past what `decode_topology()`'s own cap ladder
    and default 2000-byte search window try (every cap up to 65535, and the
    ENTIRE rest of the tile as the search window, both with and without
    excluding feature 1's already-claimed byte range) turned up nothing
    genuine: the only "hit" at a loose cap lands exactly on feature 1's own
    already-resolved, validated table bytes (1670-2230) -- i.e. an ALIASED
    false match of the same kind bug #2 above already found and fixed, here
    correctly REJECTED by the existing reservation mechanism (working as
    designed, not a regression) -- and the only "hit" once that range is
    excluded is at `cap=65535`, which accepts literally any byte value and
    so is not a real signal, just the first unreserved position tried. This
    tile's feature 0 has no locatable topology table under the currently-
    cracked understanding of the format; closing it would need the same
    kind of new structural insight as the still-open "NOT SOLVED" node-id
    section above, not a quick parameter tweak.
    A SECOND, DISTINCT, ARCHITECTURAL limitation the same report surfaced:
    the user's 6th point (23.34024,42.69020), point_index 41, is in this
    SAME tile's feature 1 (55 points, itself resolved at "high" confidence)
    -- i.e. the user expects an edge crossing a FEATURE boundary. This
    function resolves adjacency entirely WITHIN each feature independently
    (see the per-feature loop above) and has never attempted a cross-
    feature edge -- consistent with the "NOT SOLVED" section's own note
    that node-ids are plausibly a GLOBAL, tile-wide numbering shared across
    every feature in a tile (the 546 == 392+154 observation), which would
    make real cross-feature edges structurally expected, not accidental.
    Even a tile where every one of its features individually resolves at
    "high" confidence would still miss this class of edge today -- a real,
    separate gap from the per-feature "found: False" issue above, and not
    yet attempted in any session.

    PER-EDGE FALSE-POSITIVE FILTER (this session, README §10 "v16 -> v17" --
    found via the map viewer's new edge click-to-identify feature, which
    lets a user right-click a specific rendered connected-roads LINE and
    get back exactly which two points it connects, precisely so real
    connections could be debugged/reported this way). A user right-clicked
    5 real rendered edges in the Sofia, Bulgaria area and reported their
    endpoints as REAL, CONFIRMED-UNRELATED points -- e.g. "OBORISHTE" (a
    real named street) connected by a resolved edge to an unnamed point
    ~1.7km away; four more examples ranging 692m-2,917m apart, all inside
    features whose OVERALL confidence was "high". Investigated directly
    against the real ISO (all 5 reproduced exactly via this function, not a
    UI-only bug -- see `test_map_viewer.py` section "8f" for the full
    reproduction): in 4/5 cases the two "connected" points shared the
    literal link-id value **0** (their records' fields intersected only at
    0); the 5th shared a small non-zero value (11) whose full "clique"
    (`_shared_value_edges()`'s `value_to_points[v]`) mixed one genuinely
    short real edge (38m) with several implausibly long ones (869m-1,345m)
    to other members sharing that same value. This is a real, root-caused
    gap in the mechanism this docstring describes above: two points sharing
    a link-id value is necessary but NOT SUFFICIENT for real adjacency --
    `0` in particular is almost certainly a padding/unset-field sentinel
    (the same role plain `0` plays elsewhere in this exact tile format, see
    §3.6's spatial-sub-index write-up), not a genuine edge id, so any two
    points that both happen to have an unrelated/unused field slot land in
    the same `value_to_points[0]` bucket and get wrongly wired together by
    `_shared_value_edges()`'s clique-forming logic.

    Why the existing per-FEATURE median-based `confidence` gate did NOT
    catch this: `confidence` is computed from the MEDIAN distance across
    ALL of a feature's resolved edges for the winning shift -- a robust
    statistic BY DESIGN, specifically so a handful of outliers can't drag
    down an otherwise-good feature's confidence. That robustness is exactly
    why a small number of bad edges can hide inside an aggregate "high"
    confidence undetected: measured directly on the two existing human-
    verified ground-truth tiles, the FULL (pre-fix) resolved edge sets
    contained edges up to 599.9m (`mg2` 20597, 213 edges total, its 16
    human-verified edges all under 104.2m) and up to 2,039.6m (`mp0` 91124,
    331 edges total, its 16-18 human-verified edges all under 45.3m) --
    i.e. even the two BEST-VALIDATED tiles in this project already had
    some real, unnoticed implausible edges mixed in; the user's 5 reports
    just happened to land on unlabeled/rarely-inspected tiles where nobody
    had looked closely before.

    FIX: a NEW, independent per-EDGE distance sanity check
    (`max_edge_m`, default 200.0), applied to the FINAL edge list AFTER
    shift selection -- deliberately NOT folded into the median/confidence
    calculation above, so shift-selection robustness and the existing
    `confidence`/`median_edge_m` semantics (and every number already
    reported/tested for them) are completely unchanged; this only prunes
    which edges make it into the RETURNED `"edges"`/`"adjacency"`. 200m was
    chosen with a large empirical margin: the single highest distance among
    EVERY human-verified real edge across BOTH ground-truth tiles combined
    is 104.2m (`mg2` 20597); the closest of the 5 reported bad edges is
    692.4m -- a >6.6x gap with no edges observed anywhere near the middle of
    it, the same "pick a threshold with a large empirical safety margin"
    principle this function's own `implausible_median_m=2000` already uses.
    Re-validated: BOTH ground-truth tiles still resolve every one of their
    human-verified edges after the fix (`mg2` 20597 still exactly 16/16,
    `mp0` 91124 still exactly 16/18) while each drops a real number of
    other, implausible edges from their full resolved sets (`mg2` 20597:
    213 -> 204, 9 dropped; `mp0` 91124: 331 -> 310, 21 dropped) -- and all
    5 of the user-reported false edges are now confirmed excluded.
    **Limitation, stated honestly**: 200m is an empirically-justified
    but not formally-derived cutoff -- a real edge on an unusually long,
    sparse rural road segment could in principle exceed it and be wrongly
    dropped (not observed in this project's own validated samples so far,
    all well under 110m), and conversely a short-but-still-wrong edge
    (e.g. two closely-spaced but topologically-unrelated points, such as
    the `mp0` 91124 point-258-vs-259 near-duplicate-junction case already
    documented above) would NOT be caught by a pure distance filter --
    this closes the "obviously wrong, far away" failure mode the user's
    reports demonstrated, not every conceivable false-edge mechanism.
    `"edges_dropped_implausible"` (new field, see Returns below) reports
    exactly how many edges this filter removed for a given feature, so a
    caller/future session can audit or retune the threshold.

    PRACTICAL CONSEQUENCE: this closes the concrete gap blocking README §8
    item 5 -- given a feature's decoded points and topology table, this
    function now tells you which OTHER real points a given point is
    actually adjacent to (not just "this vertex looks like a junction").
    It does NOT (yet) explain what the shared numeric link-id VALUES
    themselves independently mean beyond "not-0 and shared by <= max_group
    points is a plausible-but-not-guaranteed real edge, subject to the
    per-edge distance filter above" (e.g. whether a genuine non-zero,
    non-sentinel value is a real, separately-stored edge/segment id used
    elsewhere in the database remains open). It also does not explain why
    the leading-header-record count ("shift") varies per feature, only how
    to discover it per feature cheaply. All three are reasonable follow-ups
    for a future session but are NOT required to use this function's output.

    Args:
        raw, declen: as for decode_features()/decode_topology().
        features: optional, decode_features(raw, declen) if not given.
        topo: optional, decode_topology(raw, declen, features) if not given.
        max_shift_scan: if given, only scan shifts in
            range(-max_shift_scan, max_shift_scan) instead of the full
            range(n_records) -- use this on very large features (thousands
            of points) where the O(n_records * n_points) full scan would be
            slow; every case actually validated this session needed a shift
            in {1, 2}, but this is only 2 data points, so the default is
            still a full, unbounded scan.
        implausible_median_m: see CAVEAT above (feature-level, median-based
            gate -- see "PER-EDGE FALSE-POSITIVE FILTER" above for how this
            differs from `max_edge_m`).
        max_edge_m: see "PER-EDGE FALSE-POSITIVE FILTER" above -- any
            individual edge (from the winning shift) whose two endpoints
            are more than this many real-world meters apart is dropped
            from the returned `"edges"`/`"adjacency"`, regardless of the
            feature's own aggregate `median_edge_m`/`confidence`. Does NOT
            affect shift selection or the `confidence`/`median_edge_m`
            fields, which are still computed from the full, unfiltered
            edge set for the winning shift.

    Returns a list of dicts, one per feature, in the same order as
    `features`:
        {"found": <bool, False if decode_topology() couldn't locate this
                  feature's table at all -- see decode_topology()>,
         "shift": <int or None>,
         "median_edge_m": <float or None, the winning shift's median
                  real-world edge distance, computed from the FULL
                  unfiltered edge set for that shift -- see CAVEAT>,
         "confidence": <"high" if found and median_edge_m <=
                  implausible_median_m, "low" if found but the median
                  exceeds it, "none" if not found at all -- computed from
                  the unfiltered edge set, same as median_edge_m>,
         "edges": [(point_i, point_j), ...] (i < j, deduplicated, AFTER
                  the per-edge max_edge_m distance filter above),
         "adjacency": {point_index: sorted[neighbor_point_index, ...]}
                  (built from the same filtered "edges"),
         "edges_dropped_implausible": <int, how many edges the max_edge_m
                  filter removed for this feature -- 0 if none/not found>}
    """
    if declen is None:
        declen = len(raw)
    if features is None:
        features = decode_features(raw, declen)
    if topo is None:
        topo = decode_topology(raw, declen, features)

    results = []
    for feat, t in zip(features, topo):
        if not t["found"]:
            results.append({
                "found": False, "shift": None, "median_edge_m": None,
                "confidence": "none", "edges": [], "adjacency": {},
            })
            continue

        points = feat["points"]
        n_points = len(points)
        records = t["records"]
        n_records = len(records)

        if max_shift_scan is None:
            shift_candidates = range(n_records)
        else:
            shift_candidates = (s % n_records for s in
                                 range(-max_shift_scan, max_shift_scan))

        best_shift = None
        best_median = None
        best_edges = None
        for shift in shift_candidates:
            edges = _shared_value_edges(records, n_points, n_records, shift)
            if not edges:
                continue
            dists = sorted(_haversine_ish_m(points[a], points[b]) for a, b in edges)
            median = dists[len(dists) // 2]
            if best_median is None or median < best_median:
                best_median = median
                best_shift = shift
                best_edges = edges

        if best_shift is None:
            results.append({
                "found": True, "shift": None, "median_edge_m": None,
                "confidence": "none", "edges": [], "adjacency": {},
                "edges_dropped_implausible": 0,
            })
            continue

        # Per-EDGE distance sanity filter (found this session via real
        # user-provided ground truth -- see this function's own docstring,
        # "PER-EDGE FALSE-POSITIVE FILTER" section below, for the full
        # investigation). `best_shift`/`best_median`/`confidence` above are
        # deliberately computed from the FULL, unfiltered edge set for that
        # shift (median is already a robust statistic against a minority of
        # bad edges, and changing shift-selection/confidence semantics is
        # out of scope for this fix) -- this filter only prunes which edges
        # make it into the RETURNED "edges"/"adjacency", dropping any
        # individual edge whose two endpoints are further apart than
        # `max_edge_m` regardless of the feature's own aggregate median.
        filtered_edges = []
        dropped = 0
        for a, b in best_edges:
            if _haversine_ish_m(points[a], points[b]) <= max_edge_m:
                filtered_edges.append((a, b))
            else:
                dropped += 1

        adjacency = {}
        for a, b in filtered_edges:
            adjacency.setdefault(a, set()).add(b)
            adjacency.setdefault(b, set()).add(a)
        adjacency = {k: sorted(v) for k, v in adjacency.items()}

        confidence = "high" if best_median <= implausible_median_m else "low"
        results.append({
            "found": True,
            "shift": best_shift,
            "median_edge_m": best_median,
            "confidence": confidence,
            "edges": sorted(filtered_edges),
            "adjacency": adjacency,
            "edges_dropped_implausible": dropped,
        })
    return results
