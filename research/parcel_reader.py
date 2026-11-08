"""
parcel_reader.py -- decode the real internal structure of one MP0
(MAP_COMPRESSED) tile / parcel: positions, segments, nodes, shapes and
address lists.

Why this exists
---------------
`research/map_compressed_reader.py` reads the *container* (directory, kd
geo-index, zlib streams) and then treats the first coordinate region of a
decompressed tile as a sequence of "feature" polylines.  That is not what
the payload actually is.  The decompressed blob begins with a fixed
326-byte parcel header (`pcl_offs` in `eeu.mod`'s schema) whose entries
point at *sections*; the first section is the parcel's **positions array**
(the node coordinates), not a road polyline.  A road polyline is built per
segment as `left_position + shape_deltas + right_position`; the connectivity
comes from the `nodes` section.

This module is a standalone, dependency-free port of the parts of
`DBAL.OUT` that decode those sections.  It was developed in a separate
project that ported the relevant functions 1:1 and checked them against a
Unicorn emulator executing the real PowerPC code; the function addresses
below refer to `dbal/V010_015/DBAL.OUT` from the reference disc.

Verified DBAL.OUT functions (Hex-Rays/IDA addresses, image base 0x08000000)
-----------------------------------------------------------------------
  db_upack_positions         0x08060598
  db_upack_exc_positions     0x08060994
  db_upack_segs              0x08061cc4
  db_upack_segment_data      0x08061774
  db_upack_nodes             0x08061148
  db_upack_shape             0x08062608
  db_upack_shape_compressed_fast 0x08062804
  db_upack_parcel            0x0806652c
  db_seg_and_shape_main      0x08073... (see the project notes)

Parcel header
-------------
The first four bytes of a decompressed blob are the first `(offset,
count)` pair; that offset is 326 on every layer sampled (mp0, mg1..mg4),
which is where section 0 starts and therefore also the header size.  It
is NOT a magic number, although it looks like one (`0x0146`) because it
is constant.  The pairs are relative to the blob start:

    index 0  positions
    index 2  exc_positions
    index 4  nodes
    index 5  segments
    index 16 shapes

Index 1 is `alt`, 3 is `exc_alt`; the other indices are other DBAL sections
(turn restrictions, drivable times, signs, addresses, ADAS, lanes, ...).
Only the five sections above are decoded here.  Entries beyond index 16 are
NOT all simple `(offset,count)` pairs -- do not parse them as such.

Positions section
-----------------
A sequence of blocks; each block is

    uint16 n_deltas
    int32  anchor_lon
    int32  anchor_lat
    n_deltas * (int16 dlon, int16 dlat)   # cumulative from the anchor

and the sum `1 + n_deltas` over blocks equals the section's `count`.
Coordinates are 1/100000 degree.

Segments section
----------------
Variable-length records, decoded exactly as `db_upack_segment_data`:

    b0: bit0 has_left, bit1 has_right, bit2 has_restr,
        bits3-4 ext_count, bits5-7 low 3 bits of the seginfo index
    ext_count bytes: high bits of the index:
        idx = (b0 >> 5) | (byte[k] << (3 + 8*k))
    if bit2: restr_left (u8), restr_right (u8)
    if bit0: left_node  (u16 LE)
    if bit1: right_node (u16 LE)
    3 bytes: length (u24 LE)
    1 byte: tail, always 0x00 on the reference disc

`hasShape` is the segment's ORDINAL (`seg_index < shape_count`), not a
field.  The node lists then overwrite `left_node`/`right_node`; see below.

Nodes section
-------------
Each entry is one `uint8 info0`:

    count = info0 & 0x0F
    short (count <= 4): 10 bytes
        info0, nodeinfo1, count * u16 LE segment indices
        hands = info0 >> 4
        node id increments by 1
    long  (count > 4): 20 bytes (two 10-byte slots in the in-memory array)
        info0, lHands, nodeinfo2, nodeinfo3, 8 * u16 LE segment indices
        hands = lHands
        node id increments by 2

For each slot i: `seg_idx = u16 & 0x0FFF`; `hands` bit i selects
right (1) or left (0); the segment's left/right node becomes the node id.
This is the real topology/adjacency of the parcel.

Shapes section
--------------
`count + 1` uint16 LE bounds, relative to the section start; bounds[0] is
`2 * (count + 1)`.  Shape i is the `int16` pairs from `bounds[i] & ~1` to
`bounds[i+1] & ~1`, four bytes per point.  Deltas are cumulative from the
segment's left node and use the same 1/100000 degree unit.

Address lists (bonus)
---------------------
The same header's sections 7/8/9 are `abs_addr`, `short_addr`, `long_addr`
records carrying `(segment_index, name_info, road_id)`.  `road_id` indexes
`eeu.rd` (67-byte records at offset 94), which is where street names live.
"""
from __future__ import annotations

import argparse
import json
import os
import struct
import sys
import zlib
from typing import Iterable, Iterator, Sequence

# ---------------------------------------------------------------------------
# Parcel header
# ---------------------------------------------------------------------------
HEADER_ENTRIES = 17
TAB_POSITIONS = 0
TAB_EXC_POSITIONS = 2
TAB_NODES = 4
TAB_SEGMENTS = 5
TAB_SHAPES = 16
TAB_ABS_ADDR = 7
TAB_SHORT_ADDR = 8
TAB_LONG_ADDR = 9

# Reference disc directory table offsets (table of 8-byte entries
# (file_offset, decompressed_size, compressed_size)).  They can also be
# found automatically with find_catalog().
LAYER_CATALOGS = {
    0: ('DB/EEUZ.MP0', 0x26CF63),
    1: ('DB/EEUZ.MG1', 0x0CD9F3),
    2: ('DB/EEUZ.MG2', 0x06EDFA),
    3: ('DB/EEUZ.MG3', 0x036E0B),
    4: ('DB/EEUZ.MG4', 0x0156F6),
}

TABLE_ENTRY = struct.Struct('<IHH')  # offset, decompressed_len, compressed_len


def u32(x: int) -> int:
    return x & 0xFFFFFFFF


# ---------------------------------------------------------------------------
# Header / section table
# ---------------------------------------------------------------------------
def read_header(blob: bytes) -> dict:
    """Return the five section descriptors plus the raw first 17 pairs."""
    if len(blob) < 4 * HEADER_ENTRIES:
        raise ValueError(f'parcel too short: {len(blob)} bytes')
    table = [struct.unpack_from('<HH', blob, 4 * i)
             for i in range(HEADER_ENTRIES)]
    header_size = table[0][0]
    if header_size < 4 * HEADER_ENTRIES or header_size > len(blob):
        raise ValueError(f'implausible parcel header size {header_size}')
    return {
        'header_size': header_size,
        'table': table,
        'positions': table[TAB_POSITIONS],
        'exc_positions': table[TAB_EXC_POSITIONS],
        'nodes': table[TAB_NODES],
        'segments': table[TAB_SEGMENTS],
        'shapes': table[TAB_SHAPES],
    }


def _section_size(blob: bytes, table: Sequence[tuple], index: int) -> int:
    """Section end = nearest larger offset among the real sections 0..16."""
    off = table[index][0]
    later = [table[j][0] for j in range(HEADER_ENTRIES)
             if table[j][1] and table[j][0] > off]
    return (min(later) - off) if later else (len(blob) - off)


# ---------------------------------------------------------------------------
# Positions
# ---------------------------------------------------------------------------
def decode_positions(blob: bytes, offset: int, size: int,
                     count: int) -> list[tuple[int, int]]:
    """Decode positions/exc_positions into a list of `(lon, lat)`.

    Raises ValueError if the section does not produce exactly `count`
    points or if a block overruns the section.
    """
    end = offset + size
    pos = offset
    points: list[tuple[int, int]] = []
    while pos + 10 <= end and len(points) < count:
        n = struct.unpack_from('<H', blob, pos)[0]
        if pos + 10 + 4 * n > end:
            raise ValueError(f'position block at {pos} overruns section')
        lon, lat = struct.unpack_from('<ii', blob, pos + 2)
        pos += 10
        points.append((lon, lat))
        for _ in range(n):
            dlon, dlat = struct.unpack_from('<hh', blob, pos)
            pos += 4
            lon += dlon
            lat += dlat
            points.append((lon, lat))
    if len(points) != count:
        raise ValueError(f'positions: decoded {len(points)} of {count}')
    return points


# ---------------------------------------------------------------------------
# Segments
# ---------------------------------------------------------------------------
def decode_segments(blob: bytes, offset: int, size: int,
                    count: int, shape_count: int = 0
                    ) -> tuple[list[dict], bytes]:
    """Decode `count` variable-length segment records.

    Returns `(segments, trailing)`.  On the most-detailed layer (`mp0`) the
    section is consumed exactly.  On generalized layers (`mg1`..`mg4`) with
    no shapes, a separate signs block can follow the last segment; it is
    returned as `trailing` rather than treated as a malformed record.
    """
    end = offset + size
    pos = offset
    out = []
    for seg in range(count):
        if pos >= end:
            raise ValueError(f'segment {seg}: section ended early')
        b0 = blob[pos]
        pos += 1
        ext_count = (b0 >> 3) & 3
        idx = b0 >> 5
        for k in range(ext_count):
            idx |= blob[pos] << (3 + 8 * k)
            pos += 1
        restr_left = restr_right = 0
        left = right = 0
        if b0 & 4:
            if pos + 2 > end:
                raise ValueError(f'segment {seg}: truncated restr')
            restr_left, restr_right = blob[pos], blob[pos + 1]
            pos += 2
        if b0 & 1:
            left = struct.unpack_from('<H', blob, pos)[0]
            pos += 2
        if b0 & 2:
            right = struct.unpack_from('<H', blob, pos)[0]
            pos += 2
        if pos + 4 > end:
            raise ValueError(f'segment {seg}: truncated length/tail')
        length = blob[pos] | (blob[pos + 1] << 8) | (blob[pos + 2] << 16)
        pos += 3
        tail = blob[pos]
        pos += 1
        if tail != 0:
            raise ValueError(f'segment {seg}: non-zero tail {tail:#x}')
        out.append({
            'seg': seg,
            'seginfo_index': idx,
            'marker': b0 & 3,
            'has_left': bool(b0 & 1),
            'has_right': bool(b0 & 2),
            'has_restr': bool(b0 & 4),
            'restr_left': restr_left,
            'restr_right': restr_right,
            'left_node': left,
            'right_node': right,
            'length': length,
            'hasShape': seg < shape_count,
        })
    if pos > end:
        raise ValueError(f'segments: overran section by {pos - end} bytes')
    trailing = blob[pos:end]
    if trailing and shape_count:
        # On shapes-bearing layers the section is consumed exactly; a tail
        # here would mean the record layout changed, so fail loudly.
        raise ValueError(f'segments: {len(trailing)} unexpected trailing bytes')
    return out, trailing


# ---------------------------------------------------------------------------
# Nodes / topology
# ---------------------------------------------------------------------------
def assign_nodes(blob: bytes, offset: int, size: int,
                 segments: list[dict]) -> tuple[list[dict], int]:
    """Apply `db_upack_nodes`: node lists overwrite segment left/right."""
    end = offset + size
    pos = offset
    node_id = 0
    nodes = []
    while pos < end:
        info0 = blob[pos]
        count = info0 & 0x0F
        if count > 4:
            if pos + 20 > end:
                raise ValueError(f'node at {pos}: truncated long record')
            hands = blob[pos + 1]
            slots = [struct.unpack_from('<H', blob, pos + 4 + 2 * k)[0]
                     for k in range(8)]
            step, delta = 20, 2
        else:
            if pos + 10 > end:
                raise ValueError(f'node at {pos}: truncated short record')
            hands = info0 >> 4
            slots = [struct.unpack_from('<H', blob, pos + 2 + 2 * k)[0]
                     for k in range(count)]
            step, delta = 10, 1
        refs = []
        for i, slot in enumerate(slots[:count]):
            seg_idx = slot & 0x0FFF
            side = 'right' if (hands >> i) & 1 else 'left'
            refs.append((seg_idx, side))
            if seg_idx >= len(segments):
                raise ValueError(
                    f'node {node_id}: segment index {seg_idx} >= '
                    f'{len(segments)}')
            segments[seg_idx]['left_node' if side == 'left'
                             else 'right_node'] = node_id
        nodes.append({
            'node': node_id,
            'count': count,
            'hands': hands,
            'refs': refs,
            'long': count > 4,
        })
        node_id += delta
        pos += step
    if pos != end:
        raise ValueError(f'nodes: consumed {pos - offset} of {size} bytes')
    return nodes, node_id


# ---------------------------------------------------------------------------
# Shapes
# ---------------------------------------------------------------------------
def decode_shapes(blob: bytes, offset: int, count: int) -> list[list[tuple[int, int]]]:
    """Decode `count` shapes; each is a list of cumulative `(dlon, dlat)`."""
    if count == 0:
        return []
    bounds = [struct.unpack_from('<H', blob, offset + 2 * i)[0]
              for i in range(count + 1)]
    expected_first = 2 * (count + 1)
    if bounds[0] != expected_first:
        raise ValueError(f'shapes: first bound {bounds[0]} != {expected_first}')
    shapes = []
    for i in range(count):
        a = bounds[i] & 0xFFFE
        b = bounds[i + 1] & 0xFFFE
        if b < a or (b - a) % 4:
            raise ValueError(f'shape {i}: bad bounds {a}..{b}')
        pts = [struct.unpack_from('<hh', blob, offset + p)
               for p in range(a, b, 4)]
        shapes.append(pts)
    return shapes


# ---------------------------------------------------------------------------
# Address lists
# ---------------------------------------------------------------------------
def decode_abs_addr(blob: bytes, table: Sequence[tuple],
                    limit: int | None = None) -> list[dict]:
    """Section 7: 7-byte `(seg_idx u16, name_info u8, road_id u32)`."""
    off, count = table[TAB_ABS_ADDR]
    if not count:
        return []
    out = []
    for k in range(count if limit is None else min(count, limit)):
        p = off + 7 * k
        if p + 7 > len(blob):
            break
        seg, ni, rid = struct.unpack_from('<HBI', blob, p)
        out.append({'seg': seg, 'name_info': ni, 'road_id': rid})
    return out


def decode_short_addr(blob: bytes, table: Sequence[tuple],
                      limit: int | None = None) -> list[dict]:
    """Section 8: 11-byte short addresses with a house-number range."""
    off, count = table[TAB_SHORT_ADDR]
    if not count:
        return []
    out = []
    for k in range(count if limit is None else min(count, limit)):
        p = off + 11 * k
        if p + 11 > len(blob):
            break
        seg, ni, rid, flags, n, number = struct.unpack_from('<HBIBBH',
                                                            blob, p)
        out.append({
            'seg': seg, 'name_info': ni, 'road_id': rid, 'flags': flags,
            'number': number | ((flags & 0x30) << 12),
            'count': n | (((flags >> 6) & 1) << 8),
        })
    return out


def decode_long_addr(blob: bytes, table: Sequence[tuple],
                     limit: int | None = None) -> list[dict]:
    """Section 9: 13-byte long addresses with a 24-bit house number."""
    off, count = table[TAB_LONG_ADDR]
    if not count:
        return []
    out = []
    for k in range(count if limit is None else min(count, limit)):
        p = off + 13 * k
        if p + 13 > len(blob):
            break
        seg, ni, rid, flags, ext, c, d = struct.unpack_from(
            '<HBI B B H H', blob, p)
        out.append({
            'seg': seg, 'name_info': ni, 'road_id': rid, 'flags': flags,
            'ext': ext, 'c': c, 'd': d,
            'number': c | (ext << 16) | ((flags & 0x30) << 20),
        })
    return out


# ---------------------------------------------------------------------------
# Top-level
# ---------------------------------------------------------------------------
def parse_parcel(blob: bytes) -> dict:
    """Decode one decompressed MP0/MG1..MG4 parcel into all core sections."""
    hdr = read_header(blob)
    t = hdr['table']

    pos_off, pos_cnt = hdr['positions']
    pos = decode_positions(blob, pos_off,
                           _section_size(blob, t, TAB_POSITIONS), pos_cnt)
    exc_off, exc_cnt = hdr['exc_positions']
    exc = decode_positions(blob, exc_off,
                           _section_size(blob, t, TAB_EXC_POSITIONS), exc_cnt)

    seg_off, seg_cnt = hdr['segments']
    segs, segs_tail = decode_segments(blob, seg_off,
                                      _section_size(blob, t, TAB_SEGMENTS),
                                      seg_cnt, hdr['shapes'][1])
    nodes_off, node_cnt = hdr['nodes']
    nodes, node_max = assign_nodes(blob, nodes_off,
                                   _section_size(blob, t, TAB_NODES),
                                   segs)
    shapes = decode_shapes(blob, hdr['shapes'][0], hdr['shapes'][1])

    return {
        'header': hdr,
        'positions': pos,
        'exc_positions': exc,
        'segments': segs,
        'nodes': nodes,
        'node_max': node_max,
        'shapes': shapes,
        'segments_tail': segs_tail,
        'counts': {
            'positions': pos_cnt,
            'exc_positions': exc_cnt,
            'segments': seg_cnt,
            'nodes': node_cnt,
            'shapes': hdr['shapes'][1],
        },
        'addresses': {
            'abs': decode_abs_addr(blob, t),
            'short': decode_short_addr(blob, t),
            'long': decode_long_addr(blob, t),
        },
    }


def node_coord(seg: dict, side: str, positions: list[tuple[int, int]],
               exc_positions: list[tuple[int, int]]) -> tuple[int, int]:
    """Coordinate of a segment endpoint, honoring the left/right marker."""
    if side == 'left':
        idx, marker = seg['left_node'], seg['marker'] & 1
    else:
        idx, marker = seg['right_node'], seg['marker'] & 2
    arr = exc_positions if marker else positions
    return arr[idx]


def build_polylines(parsed: dict) -> list[dict]:
    """Build real road polylines: left + shape deltas + right."""
    out = []
    positions = parsed['positions']
    exc = parsed['exc_positions']
    for seg in parsed['segments']:
        left = node_coord(seg, 'left', positions, exc)
        right = node_coord(seg, 'right', positions, exc)
        pts = [left]
        if seg['hasShape']:
            lon, lat = left
            for dlon, dlat in parsed['shapes'][seg['seg']]:
                lon += dlon
                lat += dlat
                pts.append((lon, lat))
        pts.append(right)
        out.append({
            'seg': seg['seg'],
            'seginfo_index': seg['seginfo_index'],
            'left_node': seg['left_node'],
            'right_node': seg['right_node'],
            'length': seg['length'],
            'points': pts,
            'points_deg': [(lon / 1e5, lat / 1e5) for lon, lat in pts],
        })
    return out


def parcel_bbox(parsed: dict) -> tuple[int, int, int, int] | None:
    """Bounding box of positions (1/100000 degree), or None if empty."""
    pts = parsed['positions']
    if not pts:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


# ---------------------------------------------------------------------------
# Container access (standalone; no pycdlib, no import from the GUI)
# ---------------------------------------------------------------------------
def _is_zlib(b0: int, b1: int) -> bool:
    return (b0 & 0x0F) == 8 and ((b0 * 256 + b1) % 31) == 0


def find_first_tile(path: str, scan_bytes: int = 32 << 20,
                    start: int = 80, window: int = 2 << 20):
    """Find the first (offset, decompressed_len, compressed_len) tile entry."""
    with open(path, 'rb') as f:
        f.seek(start)
        data = f.read(scan_bytes)
    for i in range(len(data) - 1):
        if not _is_zlib(data[i], data[i + 1]):
            continue
        do = zlib.decompressobj()
        try:
            out = do.decompress(data[i:i + window])
        except zlib.error:
            continue
        if not do.eof or not out:
            continue
        consumed = window - len(do.unused_data)
        # reject implausible expansion (same heuristic as the container reader)
        if consumed <= len(out) * 1.3 + 32:
            return start + i, len(out), consumed
    return None


def find_catalog(path: str) -> int:
    """Locate the 8-byte-entry directory table before the first tile."""
    first = find_first_tile(path)
    if first is None:
        raise RuntimeError(f'could not locate first tile in {path}')
    off, declen, complen = first
    pat = TABLE_ENTRY.pack(off, declen, complen)
    with open(path, 'rb') as f:
        f.seek(80)
        region = f.read(off - 80)
    pos = region.find(pat)
    if pos < 0:
        raise RuntimeError(
            f'could not locate directory table in {path} '
            f'(first tile at {off}, declen={declen}, complen={complen})')
    return 80 + pos


def read_catalog(path: str, catalog_offset: int | None = None) -> dict:
    """Read the flat directory table; returns entries + table offset."""
    if catalog_offset is None:
        catalog_offset = find_catalog(path)
    with open(path, 'rb') as f:
        f.seek(catalog_offset)
        first = f.read(8)
        if len(first) != 8:
            raise RuntimeError('truncated catalog')
        first_off = TABLE_ENTRY.unpack(first)[0]
        if first_off <= catalog_offset:
            raise RuntimeError('bad first tile offset')
        count = (first_off - catalog_offset) // 8
        f.seek(catalog_offset)
        raw = f.read(count * 8)
    entries = [TABLE_ENTRY.unpack_from(raw, 8 * i) for i in range(count)]
    return {'table_offset': catalog_offset, 'entries': entries,
            'num_tiles': count, 'table_end': first_off}


def read_parcel_blob(path: str, index: int,
                     catalog_offset: int | None = None,
                     catalog: dict | None = None) -> bytes:
    """Decompress one tile by index (physical order, 0-based)."""
    if catalog is None:
        catalog = read_catalog(path, catalog_offset)
    off, declen, complen = catalog['entries'][index]
    with open(path, 'rb') as f:
        f.seek(off)
        raw = f.read(complen)
    blob = zlib.decompress(raw)
    if len(blob) != declen:
        raise RuntimeError(f'tile {index}: declen {declen} != {len(blob)}')
    return blob


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description='Decode the real sections of one MP0/MG tile/parcel.')
    ap.add_argument('--file', help='eeuz.mp0 / eeuz.mg1..mg4')
    ap.add_argument('--layer', type=int, choices=sorted(LAYER_CATALOGS),
                    help='use the reference disc path/offset for this layer')
    ap.add_argument('--index', type=int, default=0, help='tile index')
    ap.add_argument('--catalog-offset', type=lambda x: int(x, 0),
                    help='directory table offset (hex ok); default: auto')
    ap.add_argument('--fixture', help='read an already decompressed blob')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--polylines', action='store_true')
    ap.add_argument('--sections', action='store_true')
    args = ap.parse_args(argv)

    if args.fixture:
        blob = open(args.fixture, 'rb').read()
        path = args.fixture
    else:
        path = args.file
        if not path and args.layer is not None:
            path = LAYER_CATALOGS[args.layer][0]
        if not path:
            ap.error('need --file/--layer or --fixture')
        cat_off = args.catalog_offset
        if cat_off is None and args.layer is not None:
            cat_off = LAYER_CATALOGS[args.layer][1]
        blob = read_parcel_blob(path, args.index, cat_off)

    parsed = parse_parcel(blob)
    polys = build_polylines(parsed)
    info = {
        'path': path,
        'bytes': len(blob),
        'header_size': parsed['header']['header_size'],
        'counts': parsed['counts'],
        'bbox': parcel_bbox(parsed),
        'node_max': parsed['node_max'],
        'address_counts': {k: len(v)
                           for k, v in parsed['addresses'].items()},
        'polylines': len(polys),
    }
    if args.json:
        out = dict(info)
        if args.sections:
            out['sections'] = parsed['header']['table']
        if args.polylines:
            out['polylines'] = polys
        json.dump(out, sys.stdout, indent=2)
        sys.stdout.write('\n')
        return 0

    print(f'{path}: {len(blob)} bytes, header {parsed["header"]["header_size"]}')
    c = parsed['counts']
    print(f'  positions {c["positions"]}, exc {c["exc_positions"]}, '
          f'nodes {c["nodes"]} (max id {parsed["node_max"]}), '
          f'segments {c["segments"]}, shapes {c["shapes"]}')
    print(f'  bbox {parcel_bbox(parsed)} (1/100000 deg)')
    print(f'  addresses: abs {len(parsed["addresses"]["abs"])}, '
          f'short {len(parsed["addresses"]["short"])}, '
          f'long {len(parsed["addresses"]["long"])}')
    if args.sections:
        print('  section table (offset, count):')
        for i, (off, cnt) in enumerate(parsed['header']['table']):
            print(f'    {i:2d}: {off:8d} {cnt:8d}')
    if args.polylines:
        for p in polys:
            pts = p['points_deg']
            print(f'  seg {p["seg"]:5d} si={p["seginfo_index"]:7d} '
                  f'len={p["length"]:9d} pts={len(pts):4d} '
                  f'first={pts[0]} last={pts[-1]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(_main())
