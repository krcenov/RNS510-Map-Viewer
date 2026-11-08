# MP0 / MG1–MG4 Parcel Internals

**Status: ✅ core sections investigated and validated** · MAP_COMPRESSED

This page documents what is inside a *decompressed* `eeuz.mp0` /
`eeuz.mg1`–`mg4` tile — the parcel sections, not the container. It is a
correction and extension of
[Tile Geometry and Topology](Tile-Geometry-and-Topology): the first
coordinate region of a tile is **the parcel's positions array** (node
coordinates), not a road polyline, and the connectivity is in the `nodes`
section, not in a guessed 10-byte "topology table".

Reader: [`research/parcel_reader.py`](https://github.com/krcenov/RNS510-Map-Viewer/blob/main/research/parcel_reader.py)
(standalone, no dependencies). Tests: `test_parcel_reader.py`.

The byte layouts below are a port of real `DBAL.OUT` functions, not a
statistical guess. The functions were decompiled with IDA/Hex-Rays and then
ported 1:1 into Python; the ports were checked against a Unicorn emulator
executing the real PowerPC code on real parcels. Function addresses are
from `dbal/V010_015/DBAL.OUT` (image base `0x08000000`).

---

## 0. The one-paragraph correction

`MAP_COMPRESSED` has an 80-byte file header, a k-d geo-index, and an 8-byte
per-tile directory (already documented on
[MAP_COMPRESSED Container Format](MAP_COMPRESSED-Container-Format)). After
`zlib.decompress()`, a tile starts with a **326-byte parcel header**. Its
first four bytes are the first `(offset, count)` pair, and that offset is
`326` — where section 0 starts, which is therefore also the header size.
It is not a magic number; it was read as a magic `0x0146` earlier because
it is constant. The 17 four-byte pairs are *section offsets and counts*.
Section 0 is the positions array:
a delta-coded list of **all node coordinates in the parcel**, not a chain.
Road polylines are built per segment from `left position + shape deltas +
right position`; the segment↔node connectivity is the `nodes` section.
The earlier "feature blocks" are simply the positions array; the
"oscillating overrun" and the "10-byte topology table" are segment/node
data being read with the wrong model.

---

## 1. Parcel header (`pcl_offs`)

Offsets are relative to the start of the decompressed blob. Integers are
little-endian.

```
+0x00  uint16  entry[0].offset      = 326 (positions; also the header size)
+0x02  uint16  entry[0].count       = positions count
+0x04  uint16  entry[1].offset      = alt offset
+0x06  uint16  entry[1].count
...
+0x40  uint16  entry[16].offset     = shapes offset
+0x42  uint16  entry[16].count      = shapes count
```

The used entries:

| index | section | decoded here |
|---:|---|---|
| 0 | `positions` | ✅ |
| 1 | other (`db_upack_parcel` order; not mapped) | — |
| 2 | `exc_positions` | ✅ |
| 3 | other | — |
| 4 | `nodes` | ✅ |
| 5 | `segments` | ✅ |
| 6 | other | — |
| 7 | `abs_addr_list` | ✅ (bonus) |
| 8 | `short_addr_list` | ✅ (bonus) |
| 9 | `long_addr_list` | ✅ (bonus) |
| 10 | other | — |
| 16 | `shapes` | ✅ |

The five geometry/topology sections were identified by their exact
consumption and by matching `db_upack_*` behavior, not by name order. The
remaining indices (altitudes, turn restrictions, signs, lanes, ADAS, ...)
are present in `db_upack_parcel`'s own sequence; their exact index mapping
is not needed for this decoder and is not asserted here.

`entry[0].offset` is 326 on `mp0`, `mg1`, `mg2`, `mg3`, `mg4`. The first
data section starts at 326 in every sampled tile; that is why the old
reader's `data_start == 326` heuristic worked for most `mg2`–`mg4` tiles.

**Do not parse entries beyond index 16 as `(offset,count)` pairs.** They
are part of the same `pcl_offs` metadata block but include other kinds of
records; only the five sections above are needed for geometry/topology.

The section end is the nearest larger offset among entries `0..16` with a
non-zero count. (On generalized layers, a separate section can follow the last
segment; see §6. It is not decoded here and is not assumed to be signs.)

---

## 2. Positions (`entry[0]`)

A sequence of self-delimiting blocks:

```
uint16 n_deltas
int32  anchor_lon      # 1/100000 degree
int32  anchor_lat
n_deltas × (int16 dlon, int16 dlat)   # cumulative from the anchor
```

The sum of `1 + n_deltas` over all blocks equals `entry[0].count`. The
section is usually one block, but not always (e.g. tile 180809 has 45
blocks). Coordinates are `1/100000` degree, as everywhere else on the
disc.

**This is a point array, not a polyline.** Consecutive positions can be
tens/hundreds of metres apart and in arbitrary order (fixture 170360:
median 220 m, max 913 m between consecutive positions). Drawing them as
one chain produces the zig-zag that the old reader called a "feature" and
the "oscillating overrun".

`exc_positions` (`entry[2]`) has the same format. A segment endpoint uses
`exc_positions` when the corresponding marker bit is set, otherwise
`positions`.

---

## 3. Segments (`entry[5]`)

Variable-length records, decoded exactly as `db_upack_segment_data`
(`0x08061774`):

```
b0:  bit0 has_left
     bit1 has_right
     bit2 has_restr
     bits3-4 ext_count
     bits5-7 low 3 bits of seginfo index
ext_count bytes: high bits of seginfo index:
     idx = (b0 >> 5) | (byte[k] << (3 + 8*k))
if bit2: restr_left (u8), restr_right (u8)
if bit0: left_node  (u16 LE)
if bit1: right_node (u16 LE)
3 bytes: length (u24 LE)
1 byte:  tail, always 0x00 on the reference disc
```

Field order is `restr`, `left`, `right`, then `length`. `hasShape` is the
segment's **ordinal**: segment `i` has a shape iff `i < shape_count`. It is
not stored in the record.

The initial `left_node`/`right_node` values are overwritten by the node
lists (next section); the record's own values are just an initial hint.

---

## 4. Nodes / topology (`entry[4]`)

A sequence of entries; each starts with a `uint8 info0`:

```
count = info0 & 0x0F

count <= 4  ("short", 10 bytes):
    +0 u8   info0
    +1 u8   nodeinfo1
    +2 u16[count] segment slots (LE)
    hands = info0 >> 4
    next node id += 1

count > 4   ("long", 20 bytes = two 10-byte slots in memory):
    +0 u8   info0
    +1 u8   lHands
    +2 u8   nodeinfo2
    +3 u8   nodeinfo3
    +4 u16[8] segment slots (LE)
    hands = lHands
    next node id += 2
```

For slot `i`:

```
seg_idx = u16 & 0x0FFF
side    = right if (hands >> i) & 1 else left
segment[seg_idx].side_node = current_node_id
```

**This is the real adjacency/topology of the parcel.** A node lists the
segments that meet there and which side of each segment it is. There is no
separate 10-byte "topology table" to search for.

The long-node detail is where Ghidra's decompilation had a real bug (it
used `nodeinfo0` instead of `lHands`); IDA and the raw `r2` disassembly
agree, and the port follows them.

---

## 5. Shapes (`entry[16]`)

```
count + 1 × uint16 LE bounds, relative to the section start
bounds[0] = 2 * (count + 1)
shape i = int16 pairs from (bounds[i] & ~1) to (bounds[i+1] & ~1)
```

Each pair is a cumulative `(dlon, dlat)` from the segment's left node, in
`1/100000` degree. A shape contains only **intermediate** points; the
final right node is appended separately. Do not expect
`left + Σdeltas == right` — the shape is a simplification, not a closed
delta chain.

`shape_count` is `entry[16].count`; segment `i` uses `shapes[i]` when
`i < shape_count`. The field sometimes called "shape_idx" in the raw
record is not a shape index.

**Which shape decoder?** The reference disc's section 16 uses the
**uncompressed** layout above (`shape_size[]` bounds + i16 pairs), i.e. the
`db_upack_shape` path. `db_upack_shape_compressed_fast` is a real bit-packed
alternative in `DBAL.OUT`, but it is not what this section contains here:
the first shape of tile 0 starts with `bounds[0]=14` and five i16 pairs
`(4692,-182), (3061,-134), ...`, which is not a bit stream. Do not apply the
bit decoder to this section.

`entry[4].count` counts **10-byte slots**, not node records: a long node
occupies two slots. In every sampled tile the final node id (`node_max`)
equals the positions count (`entry[0].count`), which is a useful sanity
check.

---

## 6. Generalized layers (`mg1`–`mg4`)

The same header and sections apply. `mg1`–`mg4` usually have
`shape_count == 0`, and a separate section can follow the last segment in
the segment section. It is **not decoded here** and is not assumed to be
signs; it is returned as `segments_tail` instead of being treated as a
malformed segment. On `mp0` (with shapes) the segment section is consumed
exactly.

---

## 7. Address lists (bonus)

These carry `(segment_index, name_info, road_id)`; `road_id` indexes
`eeu.rd` (67-byte records at offset 94), which is where street names live.

| section | record | layout |
|---|---|---|
| 7 `abs_addr` | 7 B | `u16 seg`, `u8 name_info`, `u32 road_id` |
| 8 `short_addr` | 11 B | `u16 seg`, `u8 name_info`, `u32 road_id`, `u8 flags`, `u8 count`, `u16 number` |
| 9 `long_addr` | 13 B | `u16 seg`, `u8 name_info`, `u32 road_id`, `u8 flags`, `u8 ext`, `u16 c`, `u16 d` |

For `short_addr`, the real house number is
`number | ((flags & 0x30) << 12)`; for `long_addr`,
`c | (ext << 16) | ((flags & 0x30) << 20)`.

This is enough to name a decoded polyline without guessing from geometry.

**Verification level:** the 7-byte `abs_addr` records are validated
end-to-end (section size is `7 × count` in most tiles; road ids are in
range and the resulting polylines fit `eeu.rd` bboxes). The 11-byte
`short_addr` and 13-byte `long_addr` decoders read the first `count`
records, but their sections can contain additional bytes after those
records (e.g. tile 170360: section 8 is 2,524 bytes vs `32 × 11 = 352`).
Those trailing bytes are not decoded here; treat short/long as partial.

---

## 8. Building a road polyline

```
left  = positions[left_node]        (or exc_positions if marker_left)
right = positions[right_node]       (or exc_positions if marker_right)
pts   = [left]
if segment.hasShape:
    lon, lat = left
    for dlon, dlat in shapes[segment_index]:
        lon += dlon; lat += dlat
        pts.append((lon, lat))
pts.append(right)
```

Every point is in `1/100000` degree. The segment's `length` field is left
as-is (units not asserted here).

---

## 9. Validation

* **Fixture** `test_data/mp0_tile_170360.bin` (Moscow, Bersenevskaya
  embankment): 22,224 bytes, 255 positions, 47 exc positions, 335
  segments, 255 nodes, 148 shapes, 726 absolute addresses, 32 short
  addresses. All 335 polylines decode; every node reference resolves; all
  points stay within 0.05° of the positions bbox.
* **All five layers**: sampled tiles from `mp0`, `mg1`, `mg2`, `mg3`,
  `mg4` parse without errors; `mg1`–`mg4` tails (signs blocks) are
  reported separately.
* **Real road names**: on tile 170360, decoded polylines for segments with
  `road_id` land inside the corresponding `eeu.rd` bounding boxes, and
  `eeu.rd` names include `BERSENEVSKIY` / `BERSENEVSKAYA`. On tile 1
  (France) the names are `VERS-VAUX` / `FARGOUT`.
* **Against the real firmware** (source project, not reproducible from
  this repository alone): the same Python logic reproduces the unit's own
  segment set for a map window (35,540/35,540 segments, 443 parcels, frame
  comparison 1:1) when driven by the same DBAL rules. That is the same code
  path the firmware uses to build `vseg`; here it is cited as provenance,
  not as a check you can run without that harness.
* **Against the decompiler**: `db_upack_nodes`' long-node path was
  cross-checked between IDA, Ghidra and raw PowerPC disassembly; the one
  Ghidra discrepancy (`lHands` vs `nodeinfo0`) is documented and the port
  follows the disassembly.
* **Independent audit, 1,000 random tiles per layer (5,000 total)**:
  - 0 parse failures; `entry[0].offset == 326` in all 5,000;
  - positions/exc/segment/shape counts exact; `node_max == positions count`
    in all 5,000;
  - 0 bad node references, 0 invalid segment endpoints, 0 bad shape bounds,
    0 out-of-range address records;
  - `mp0`: address lists present in 1,000/1,000 tiles (`abs`), 812
    (`short`), 6 (`long`); `mg1`–`mg4` had none in this sample;
  - `mg1`–`mg4`: 154–235 of 1,000 tiles have a separate trailing section,
    not decoded here.
* **Road-name/bbox audit, 500 `mp0` tiles**: 147,231 segment→road-id
  links; 144,354 (98.0%) polylines fit the `eeu.rd` bbox exactly, 147,231
  (100%) within 0.05°; 58,063 have a plain-text name (the rest are
  bracketed internal ids, e.g. `[7823063]`).
* **Old-reader comparison, 100 random `mp0` tiles**: its
  `decode_features()` returns 0 features in 2 tiles, 1 in 55, 2 in 43;
  the sum of its points equals the real positions count in only 48/100;
  the real segment count is larger than the positions count in 99/100.
  On the fixture it returns 1 feature of 255 points vs 335 real segments.
* **Emulator runs in the source project** (not part of this repository):
  `verify_seg.py --check --n 50` — 178 checks, 0 diffs
  (`db_seg_V004/V000`, `db_seg_mp0_V004/V000`); `verify_node.py --check`
  — 300 checks, 0 diffs (`db_convert_ninfo` / `db_copy_node`).

---

## 10. What to change in the existing reader

A concrete measurement on the fixture (tile 170360): the old
`decode_features()` returns **1 feature with 255 points**; the real parcel
has **335 segments, 255 nodes and 148 shapes**. `decode_topology()` returns
a single **256-record** table (the positions count again), not 335
segments. The difference is the payload model, not a tuning issue.


* `_find_data_start()` / `decode_features()`: stop treating the first
  coordinate region as a polyline. Read the 326-byte header and decode
  positions as a **point array**.
* `decode_topology()` / `_find_topology_table_start()`: replace the
  search for a 10-byte "topology table" with the `nodes` section. The
  connectivity is explicit, including the left/right side per segment.
* `seg_tail_region()` / `parse_seg_tail_records()` / `decode_mp0_zone2()`:
  these are (different) attempts to parse the segment/tail bytes without
  the segment record layout. The variable-length record decoder above
  replaces them for `mp0`; `mg1`–`mg4` tails are a separate signs block.
* `decode_tile_header()`: word 0 is `header_size` (326), not a magic.
  Words 1..32 are `(offset,count)` section descriptors.
* Road naming: use `abs_addr`/`short_addr`/`long_addr` + `eeu.rd`, not
  nearest-coordinate matching.

The map viewer can keep its container/kd-index code; only the payload
decoder changes.

---

## 11. Open questions

* The exact meaning of every `pcl_offs` entry beyond index 16 (some are
  not simple pairs).
* Units of the segment `length` field (the geometry is in 1/100000
  degree; `length` is an integer, likely centimetres/decimetres, not
  asserted).
* `nodeinfo1/2/3`, the low bits of shape bounds, and the exact semantics
  of `name_info`.
* Why some `mg1`–`mg4` tiles have a signs tail and others do not.

---

## 12. Reproduce

```bash
# fixture only
py test_parcel_reader.py

# a real disc: sample all five layers
py test_parcel_reader.py --map "D:\\path\\EEUZ.MP0" --catalog-offset 0x26cf63
py test_parcel_reader.py --map "D:\\path\\EEUZ.MG4" --catalog-offset 0x156f6

# one tile, sections and polylines
py research/parcel_reader.py --file "D:\\path\\EEUZ.MP0" --index 170360 \
    --catalog-offset 0x26cf63 --sections --polylines
```

The reference disc's catalog offsets (verified against both this reader
and the existing container reader):

| layer | file | catalog offset |
|---:|---|---:|
| 0 | `eeuz.mp0` | `0x26cf63` |
| 1 | `eeuz.mg1` | `0x0cd9f3` |
| 2 | `eeuz.mg2` | `0x06edfa` |
| 3 | `eeuz.mg3` | `0x036e0b` |
| 4 | `eeuz.mg4` | `0x0156f6` |
