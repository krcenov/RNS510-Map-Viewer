"""
road_naming.py -- joins decoded MAP_COMPRESSED tile geometry
(map_compressed_reader.decode_features()) to real road names from eeu.rd, by
coordinate match. This is the piece that turns an unlabeled rendered
polyline into "these vertices are DC158, these are STADION, ..." for a
viewer to display.

============================================================================
Why this works at all
============================================================================
Prior sessions established (README §3.6) that tile vertices are frequently
BIT-EXACT matches to eeu.rd's own int32 coordinate fields -- both files
store the same underlying road-network points, just in different
containers (a compact polyline chain for rendering vs. a named point
catalog for search/routing). decode_features() computes each vertex by
integer delta-accumulation from an integer anchor, THEN divides by 100000
once at the very end to produce a float -- so round(lon*100000) reliably
recovers the exact original int32 for a genuine on-road vertex (no
compounding float error from repeated divide/multiply). This module
exploits that: build an index of every eeu.rd (lon_i, lat_i) int32 pair in
a bounding area, then for each tile vertex do an O(1) exact-dict lookup on
round(lon*100000), round(lat*100000).

============================================================================
Two-tier matching strategy
============================================================================
1. EXACT (gold standard, matches this project's established validation
   bar): dict lookup on the bit-exact (lon_i, lat_i) int32 pair. This is
   what the README's "10 distinct named roads in one 392-point chain"
   validation used.
2. NEAREST-WITHIN-TOLERANCE (fallback, ~50-100m default): eeu.rd does not
   contain every shape point of every road (it looks like a name+anchor
   catalog, not a full shape-point store -- most roads have far fewer
   `.rd` records than tile polyline vertices), so many real, correctly
   decoded vertices will have NO exact match at all. A small-radius nearest
   lookup via a degree-binned grid catches vertices that are genuinely on
   a named road but not one of `.rd`'s own sampled points.

A single decoded feature can legitimately pass through several different
named roads in sequence (already documented and validated in README §3.6 --
the Iasi 392-point chain example). This module reflects that directly: it
returns a list of contiguous VERTEX RANGES, each with whatever name (or
None) was found for that stretch, rather than forcing one name per feature.

============================================================================
Known limitations (read before using in a viewer)
============================================================================
- eeu.rd is NOT globally spatially sorted (per README §3), so there is no
  way to query "$records near (lon,lat)" faster than a scan without a
  persistent index. `build_rd_index()` does a single bounding-box-filtered
  scan (see its docstring for measured timing) -- fine for "build once for
  the currently-visible map area", NOT fine to call per-frame during pan/
  zoom. A future session could cache a global grid index to disk (e.g. one
  pass building {grid_cell: [(lon,lat,name),...]} and pickling it) to avoid
  re-scanning the 590MB file every time the viewer moves -- not built here,
  see README's road-naming section for the concrete suggestion.

  **UPDATE (map-viewer session): `RdCache` below closes most of this gap
  without needing a disk-backed index.** `build_rd_index()`'s own ~0.3-0.7s
  cost is DOMINATED by re-reading the whole 590MB file from disk on every
  call, not by the numpy filtering step itself (that part is sub-second
  across all 8.8M records). `RdCache.__init__()` reads the file and
  vectorizes its (lon, lat) int32 arrays into memory exactly ONCE per
  viewer session; `RdCache.index_for_bbox()` then repeats only the cheap
  numpy-mask + per-hit-decode part of `build_rd_index()` against the
  already-resident arrays, with no further file I/O. This is what
  `rns510_map_viewer.py` calls on every pan/zoom settle (see its
  `MapData.rd_index_for_bbox()`, which additionally only rebuilds when the
  viewport has moved outside the last-built box, rather than on every
  call) -- see README §10 for measured before/after timing.
- The nearest-tolerance fallback uses a flat degree-distance grid, NOT a
  true haversine distance. At the reference disc's latitudes (~35-72N) 1
  degree of longitude is meters-per-degree = 111,320*cos(lat), i.e.
  meaningfully SHORTER than a degree of latitude -- `match_feature()`
  converts a caller-given meters tolerance into a LATITUDE-based degree
  tolerance and applies it isotropically (same tolerance in both lon and
  lat degrees), which means the EFFECTIVE ground tolerance in the
  longitude direction is tighter than requested at high latitude (a
  conservative bug, not a permissive one -- it will occasionally miss a
  real nearby match near the poleward edge of the dataset rather than
  produce a false one).
- Ambiguity is NOT resolved: if two different named roads both have an
  eeu.rd point within tolerance of a vertex, whichever is found first in
  that grid cell's list wins (undefined tie-break order). Rare in practice
  (roads that close together are usually the same named road, e.g. a
  divided highway's two carriageways) but not proven absent.
- A short run of unmatched vertices between two identically-named runs is
  NOT merged back into the surrounding name -- it is reported as its own
  `None` range. This is deliberate (don't silently paper over gaps), but a
  viewer that wants fewer, cleaner label breaks may want to post-process
  short (e.g. <=2 point) `None` gaps by merging them into a neighboring
  same-name run.
- This module has no dependency on, and does not attempt to use, the
  still-uncracked per-tile topology/adjacency table (README §3.6/§8) --
  matching is pure coordinate geometry, independent of that open problem.

============================================================================
Validated on real areas (this session)
============================================================================
See the module-level test invocation logic in the project's session
scratchpad (not committed here) and the README's new road-naming section
for concrete before/after examples: the canonical Iasi eeuz.mg4 tile at
file offset 11,298,518 (392+154 point, 2-feature tile) reproduces the
already-documented 10-name and 2-name splits using ONLY this module's
generic exact-match logic (no per-example special-casing), and a Timisoara-
area tile reproduces the original single-vertex "DC158" match plus
resolves names for the rest of that chain.
"""

import math
import struct

import numpy as np

RD_HEADER_SIZE = 94
RD_RECORD_SIZE = 67
RD_LON_OFFSET = 8
RD_LAT_OFFSET = 12
RD_NAME_OFFSET = 24
RD_NAME_SIZE = 43

METERS_PER_DEG_LAT = 111_320.0


class RdSpatialIndex:
    """In-memory spatial index over a bounded lon/lat window of eeu.rd,
    built by build_rd_index()/build_rd_index_for_features(). Not meant to
    be constructed directly."""

    __slots__ = ("exact", "grid", "cell_deg", "bbox", "record_count")

    def __init__(self, exact, grid, cell_deg, bbox, record_count):
        self.exact = exact          # {(lon_i, lat_i): name}
        self.grid = grid            # {(gx, gy): [(lon, lat, name), ...]}
        self.cell_deg = cell_deg
        self.bbox = bbox            # (lon_min, lon_max, lat_min, lat_max)
        self.record_count = record_count  # number of eeu.rd records indexed

    def lookup_exact(self, lon, lat):
        return self.exact.get((round(lon * 100000), round(lat * 100000)))

    def lookup_nearest(self, lon, lat, tol_deg):
        gx, gy = int(lon // self.cell_deg), int(lat // self.cell_deg)
        best_name = None
        best_d2 = tol_deg * tol_deg
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for plon, plat, name in self.grid.get((gx + dx, gy + dy), ()):
                    d2 = (plon - lon) ** 2 + (plat - lat) ** 2
                    if d2 <= best_d2:
                        best_d2 = d2
                        best_name = name
        return best_name


def build_rd_index(rd_path, lon_min, lon_max, lat_min, lat_max, cell_deg=0.001):
    """Single-pass scan of eeu.rd, filtered to a bounding box, building an
    RdSpatialIndex for name lookups within that area.

    Implementation: reads the WHOLE eeu.rd file into memory once (590MB on
    the reference disc -- fine for a one-shot "build an index for the
    currently visible area" call, NOT meant to be cached/repeated for the
    full file's lifetime; see module docstring for the "don't call this
    per-frame" caveat) and uses numpy to vectorize the coordinate-decode +
    bbox-filter step over all ~8.8M records, then only Python-loops over the
    (typically a few hundred to a few tens of thousands) records that
    actually fall in the box to decode names and populate the index.
    Measured on the reference disc (590MB, 8,809,081 records): ~0.3-0.7s
    total per call for a single-tile-sized bounding box, dominated by the
    initial file read (numpy filtering and the per-hit Python loop are
    each a small fraction of that).

    `cell_deg` sets the nearest-match grid's cell size in degrees (default
    0.001 deg, ~111m in latitude, ~60-90m in longitude at this dataset's
    latitude range -- see module docstring's tolerance-conversion caveat).
    """
    with open(rd_path, "rb") as f:
        f.seek(RD_HEADER_SIZE)
        body = f.read()
    n = len(body) // RD_RECORD_SIZE
    arr = np.frombuffer(body, dtype=np.uint8, count=n * RD_RECORD_SIZE).reshape(n, RD_RECORD_SIZE)
    lon_i = arr[:, RD_LON_OFFSET:RD_LON_OFFSET + 4].copy().view("<i4").reshape(-1)
    lat_i = arr[:, RD_LAT_OFFSET:RD_LAT_OFFSET + 4].copy().view("<i4").reshape(-1)
    lon = lon_i / 100000.0
    lat = lat_i / 100000.0

    mask = (lon >= lon_min) & (lon <= lon_max) & (lat >= lat_min) & (lat <= lat_max)
    idxs = np.nonzero(mask)[0]

    exact = {}
    grid = {}
    for i in idxs:
        i = int(i)
        off = i * RD_RECORD_SIZE
        name_bytes = body[off + RD_NAME_OFFSET:off + RD_NAME_OFFSET + RD_NAME_SIZE].split(b"\x00", 1)[0]
        if not name_bytes:
            continue
        name = name_bytes.decode("latin-1")
        li, la = int(lon_i[i]), int(lat_i[i])
        plon, plat = lon[i], lat[i]
        exact[(li, la)] = name
        gx, gy = int(plon // cell_deg), int(plat // cell_deg)
        grid.setdefault((gx, gy), []).append((plon, plat, name))

    return RdSpatialIndex(exact, grid, cell_deg, (lon_min, lon_max, lat_min, lat_max), len(idxs))


def build_rd_index_for_features(rd_path, features, pad_deg=0.02, cell_deg=0.001):
    """Convenience wrapper: compute a bounding box (with `pad_deg` degrees of
    padding on each side, default ~2km) around every point in every feature
    (as returned by map_compressed_reader.decode_features()), then call
    build_rd_index() for that box. Raises ValueError if `features` has no
    points at all."""
    lons = []
    lats = []
    for feat in features:
        for lon, lat in feat["points"]:
            lons.append(lon)
            lats.append(lat)
    if not lons:
        raise ValueError("no points found in the given features")
    return build_rd_index(
        rd_path,
        min(lons) - pad_deg, max(lons) + pad_deg,
        min(lats) - pad_deg, max(lats) + pad_deg,
        cell_deg=cell_deg,
    )


class RdCache:
    """Whole-session cache over eeu.rd for interactive callers (built for
    rns510_map_viewer.py's dynamic pan/zoom reloading -- see the "UPDATE"
    note in this module's docstring).

    Reads the file ONCE (`__init__`), vectorizing its (lon, lat) int32
    fields with numpy exactly like `build_rd_index()` does internally, then
    `index_for_bbox()` repeats only build_rd_index()'s cheap
    numpy-mask-and-decode step against those already-resident arrays for
    any given bounding box, with NO further file I/O. Measured on the
    reference disc (8,809,081 records): building the cache once costs
    about the same ~0.3-0.7s `build_rd_index()' always cost (that time was
    always dominated by the file read, not the numpy math); each subsequent
    `index_for_bbox()` call for a viewport-sized box then costs a few
    milliseconds (a boolean mask over 8.8M floats) plus a small Python loop
    over just the matching records -- fast enough to re-run on every
    pan/zoom settle rather than only once per session."""

    __slots__ = ("body", "lon_i", "lat_i", "lon", "lat", "record_count")

    def __init__(self, rd_path):
        with open(rd_path, "rb") as f:
            f.seek(RD_HEADER_SIZE)
            self.body = f.read()
        n = len(self.body) // RD_RECORD_SIZE
        arr = np.frombuffer(self.body, dtype=np.uint8, count=n * RD_RECORD_SIZE).reshape(n, RD_RECORD_SIZE)
        self.lon_i = arr[:, RD_LON_OFFSET:RD_LON_OFFSET + 4].copy().view("<i4").reshape(-1)
        self.lat_i = arr[:, RD_LAT_OFFSET:RD_LAT_OFFSET + 4].copy().view("<i4").reshape(-1)
        self.lon = self.lon_i / 100000.0
        self.lat = self.lat_i / 100000.0
        self.record_count = n

    def index_for_bbox(self, lon_min, lon_max, lat_min, lat_max, cell_deg=0.001):
        """Same contract/return type as build_rd_index(), but filters the
        already-resident in-memory arrays instead of re-reading the file."""
        mask = (self.lon >= lon_min) & (self.lon <= lon_max) & (self.lat >= lat_min) & (self.lat <= lat_max)
        idxs = np.nonzero(mask)[0]

        exact = {}
        grid = {}
        for i in idxs:
            i = int(i)
            off = i * RD_RECORD_SIZE
            name_bytes = self.body[off + RD_NAME_OFFSET:off + RD_NAME_OFFSET + RD_NAME_SIZE].split(b"\x00", 1)[0]
            if not name_bytes:
                continue
            name = name_bytes.decode("latin-1")
            li, la = int(self.lon_i[i]), int(self.lat_i[i])
            plon, plat = self.lon[i], self.lat[i]
            exact[(li, la)] = name
            gx, gy = int(plon // cell_deg), int(plat // cell_deg)
            grid.setdefault((gx, gy), []).append((plon, plat, name))

        return RdSpatialIndex(exact, grid, cell_deg, (lon_min, lon_max, lat_min, lat_max), len(idxs))

    def distinct_names(self):
        """Every distinct real street name found ANYWHERE in eeu.rd, GLOBAL
        (not bbox-scoped) -- added for rns510_map_viewer.py's exhaustive
        `MapData.street_name_index_global` (README §10 "v14 -> v15"), which
        replaces the incomplete `.rt`-trie fallback the Street speller used
        when no city has resolved yet (README §3.7 documents `.rt` as a
        forest of independent shards reaching only ~5,100 of the real
        leaf strings, a tiny fraction of the ~46.4M-entry `.prl`/`.rl`
        catalog covering the same real names -- see that section for the
        full gap analysis this method closes for the Street field's one
        remaining unscoped fallback path).

        eeu.rd has 8,809,081 records but many real streets get more than
        one record (one per road segment/shape point sharing that name),
        so this deduplicates to distinct name strings before returning --
        NOT the raw per-record count. Implementation: reshapes the
        already-resident raw byte body into (record_count, 43) name-column
        rows and dedupes them as RAW FIXED-WIDTH BINARY via
        `numpy.unique()` over a void-typed view (a single vectorized sort,
        not 8.8M individual Python string hashes) -- only the resulting
        distinct rows (a small fraction of the record count in practice)
        are then decoded to text and NUL-stripped. Returns a plain list of
        names (str); empty names are dropped. `city_reader.PrefixNameIndex`
        (the caller) does its own case-insensitive de-duplication into a
        sorted set on top of this, so a caller does not need to dedupe by
        anything beyond exact byte equality here.

        **A real, measured gotcha this method must (and does) account for:
        the 43-byte name field's bytes AFTER the NUL terminator are NOT
        reliably zero.** Directly checked against the reference disc: two
        real records both named "LINOSA" have byte-for-byte IDENTICAL
        6-byte strings + terminator, but different trailing garbage in the
        remaining 36 bytes (leftover/uninitialized buffer content from
        whatever the original authoring tool last wrote there, not
        consistently zero-filled padding) -- e.g. one ends in
        `...\x00S\x16\x00\x00{\x02\x00\x00`, the other in
        `...\x00\x27\x00\x00\x00`. A naive raw-43-byte dedup (this method's
        first implementation, caught by this project's own "measure, don't
        assume" standard rather than shipped silently) is fooled by this:
        it found 8,808,597 "distinct" rows out of 8,809,081 records on the
        reference disc -- essentially no dedup at all, contradicting the
        expectation that many segments share a street name, because two
        records with the IDENTICAL real name but different trailing
        garbage bytes were counted as different. **Fix**: before packing
        rows for `numpy.unique()`, every byte at or after each row's own
        first NUL byte is explicitly zeroed (vectorized via
        `numpy.cumsum()` over the per-row zero-byte mask, not a Python
        loop) so two records encoding the same real string always compare
        byte-identical regardless of what garbage followed their own
        terminator; a row with no NUL byte anywhere in its 43 bytes (the
        documented name-overflow-risk case, not observed on the reference
        disc but not proven impossible) is left untouched rather than
        assumed to have a safe truncation point.

        Measured cost and the eager-vs-lazy load-timing decision this
        informed: see `MapData.street_name_index_global`'s own docstring
        in rns510_map_viewer.py."""
        n = self.record_count
        arr = np.frombuffer(self.body, dtype=np.uint8, count=n * RD_RECORD_SIZE).reshape(n, RD_RECORD_SIZE)
        name_cols = np.array(arr[:, RD_NAME_OFFSET:RD_NAME_OFFSET + RD_NAME_SIZE])  # copy, mutated below
        is_zero = (name_cols == 0)
        # cumsum > 0 marks every column at or after each row's OWN first
        # zero byte (inclusive) -- rows with no zero byte at all get an
        # all-zero cumsum (nothing cleared), the safe no-op for that case.
        after_first_nul = np.cumsum(is_zero, axis=1) > 0
        name_cols[after_first_nul] = 0
        packed = np.ascontiguousarray(name_cols).view(np.dtype((np.void, RD_NAME_SIZE))).reshape(-1)
        uniq_rows = np.unique(packed)
        names = []
        for row in uniq_rows:
            raw = row.tobytes().split(b"\x00", 1)[0]
            if raw:
                names.append(raw.decode("latin-1"))
        return names


def _tol_deg_for_meters(tol_m):
    return tol_m / METERS_PER_DEG_LAT


def match_feature(points, index, tol_m=75):
    """Match every vertex of a single decoded feature's `points` (a list of
    (lon, lat) tuples, e.g. one element of decode_features()'s return value)
    against `index`, then collapse the per-vertex results into contiguous
    runs.

    Returns a list of (start_idx, end_idx, name) tuples (both indices
    inclusive, 0-based into `points`), covering every index in `points`
    exactly once, in order. `name` is None for a run where no exact or
    near-tolerance match was found at any of its vertices.

    Matching per vertex: try index.lookup_exact() first (bit-exact int32
    match -- this project's established gold standard); if that misses,
    try index.lookup_nearest() within `tol_m` meters (converted to degrees
    via the latitude-based approximation documented in the module
    docstring)."""
    if not points:
        return []
    tol_deg = _tol_deg_for_meters(tol_m)
    names = []
    for lon, lat in points:
        name = index.lookup_exact(lon, lat)
        if name is None:
            name = index.lookup_nearest(lon, lat, tol_deg)
        names.append(name)

    runs = []
    start = 0
    cur = names[0]
    for i in range(1, len(names)):
        if names[i] != cur:
            runs.append((start, i - 1, cur))
            start = i
            cur = names[i]
    runs.append((start, len(names) - 1, cur))
    return runs


def name_features(features, index, tol_m=75):
    """Run match_feature() over every feature in `features` (as returned by
    map_compressed_reader.decode_features()). Returns a NEW list of dicts,
    each the original feature dict plus a "named_ranges" key holding
    match_feature()'s output. Does not mutate the input."""
    out = []
    for feat in features:
        named_ranges = match_feature(feat["points"], index, tol_m=tol_m)
        new_feat = dict(feat)
        new_feat["named_ranges"] = named_ranges
        out.append(new_feat)
    return out


def summarize_named_ranges(named_ranges, min_len=1):
    """Human-readable one-line-per-run summary, e.g. 'vertices 0-50: DC158'
    or 'vertices 51-90: (unmatched)'. Skips runs shorter than `min_len`
    vertices if requested (default 1, i.e. keeps everything)."""
    lines = []
    for start, end, name in named_ranges:
        if (end - start + 1) < min_len:
            continue
        label = name if name is not None else "(unmatched)"
        lines.append(f"vertices {start}-{end}: {label}")
    return lines
