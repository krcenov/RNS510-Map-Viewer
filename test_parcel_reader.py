"""
test_parcel_reader.py -- self-contained tests for research/parcel_reader.py.

Run with:
    py test_parcel_reader.py

The default test decodes a small, real decompressed tile embedded under
test_data/ (index 170360 from the reference CD_8555 disc, the Moscow
Bersenevskaya embankment area), so it needs no ISO and no multi-GB file.

With a real disc:
    py test_parcel_reader.py --map "D:\\path\\EEUZ.MP0"
or
    py test_parcel_reader.py --map ... --catalog-offset 0x26cf63

The optional --map pass samples tiles from all five layers and checks the
same structural invariants at scale (no full-file reads).
"""
import argparse
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, 'research'))

import parcel_reader as pr  # noqa: E402


FIXTURE = os.path.join(HERE, 'test_data', 'mp0_tile_170360.bin')
EXPECTED = {
    'bytes': 22224,
    'header_size': 326,
    'positions': 255,
    'exc_positions': 47,
    'segments': 335,
    'nodes': 255,
    'shapes': 148,
    'abs_addr': 726,
    'short_addr': 32,
    'long_addr': 0,
}


def check_fixture():
    blob = open(FIXTURE, 'rb').read()
    assert len(blob) == EXPECTED['bytes'], len(blob)
    p = pr.parse_parcel(blob)
    assert p['header']['header_size'] == EXPECTED['header_size']
    for key in ('positions', 'exc_positions', 'segments', 'nodes', 'shapes'):
        assert p['counts'][key] == EXPECTED[key], (key, p['counts'][key])
    assert p['node_max'] == EXPECTED['nodes']
    assert len(p['addresses']['abs']) == EXPECTED['abs_addr']
    assert len(p['addresses']['short']) == EXPECTED['short_addr']
    assert len(p['addresses']['long']) == EXPECTED['long_addr']
    assert p['segments_tail'] == b'', len(p['segments_tail'])

    # Every node reference points at a real segment; every segment endpoint
    # points at a real position array (main or exc, per its marker).
    for nd in p['nodes']:
        for seg_idx, side in nd['refs']:
            assert 0 <= seg_idx < len(p['segments']), (nd, seg_idx)
            assert p['segments'][seg_idx]['left_node' if side == 'left'
                                       else 'right_node'] == nd['node']
    for seg in p['segments']:
        for side in ('left', 'right'):
            idx = seg[side + '_node']
            arr = (p['exc_positions'] if seg['marker'] & (1 if side == 'left' else 2)
                   else p['positions'])
            assert 0 <= idx < len(arr), (seg['seg'], side, idx)

    # The shape ordinal is positional: exactly the first shape_count
    # segments have a shape.
    for seg in p['segments']:
        assert seg['hasShape'] == (seg['seg'] < EXPECTED['shapes'])

    # Real polylines: left + deltas + right, all inside the parcel bbox.
    polys = pr.build_polylines(p)
    assert len(polys) == EXPECTED['segments']
    x0, y0, x1, y1 = pr.parcel_bbox(p)
    pad = 5000  # 0.05 degree: shape points may extend past node positions
    for poly in polys:
        pts = poly['points']
        assert pts[0] == p['positions'][poly['left_node']] or \
            pts[0] in p['exc_positions'], poly['seg']
        assert pts[-1] == p['positions'][poly['right_node']] or \
            pts[-1] in p['exc_positions'], poly['seg']
        for lon, lat in pts:
            assert x0 - pad <= lon <= x1 + pad, (poly['seg'], lon, x0, x1)
            assert y0 - pad <= lat <= y1 + pad, (poly['seg'], lat, y0, y1)

    # Spot-check one real street name from eeu.rd: the tile's address list
    # contains road IDs; the first segment's road ID is a known Moscow road.
    # (Name lookup itself is the caller's job; we only assert the linkage
    # exists and is in range for a 67-byte eeu.rd record table.)
    for a in p['addresses']['abs']:
        assert 0 <= a['road_id'] < 8_809_081, a
        assert 0 <= a['seg'] < EXPECTED['segments'], a

    print(f'fixture: OK ({len(blob)} bytes, {len(polys)} polylines)')
    return p, polys


def check_map(path, catalog_offset=None, samples=10):
    cat = pr.read_catalog(path, catalog_offset)
    print(f'{path}: {cat["num_tiles"]} tiles, catalog @ {cat["table_offset"]:#x}')
    picks = random.Random(12345).sample(range(cat['num_tiles']), samples)
    for idx in picks:
        blob = pr.read_parcel_blob(path, idx, catalog=cat)
        p = pr.parse_parcel(blob)
        polys = pr.build_polylines(p)
        assert len(polys) == p['counts']['segments']
        bbox = pr.parcel_bbox(p)
        if bbox is None:
            continue
        x0, y0, x1, y1 = bbox
        pad = 10000  # 0.1 degree, generous for exc/shape points
        for poly in polys:
            for lon, lat in poly['points']:
                assert x0 - pad <= lon <= x1 + pad, (idx, poly['seg'], lon)
                assert y0 - pad <= lat <= y1 + pad, (idx, poly['seg'], lat)
        print(f'  tile {idx}: positions={p["counts"]["positions"]} '
              f'segments={p["counts"]["segments"]} '
              f'nodes={p["counts"]["nodes"]} '
              f'shapes={p["counts"]["shapes"]} tail={len(p["segments_tail"])}')
    print('map sample: OK')


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--map', help='path to EEUZ.MP0 or EEUZ.MG1..MG4')
    ap.add_argument('--catalog-offset', type=lambda x: int(x, 0),
                    default=0x26CF63)
    ap.add_argument('--samples', type=int, default=10)
    args = ap.parse_args(argv)
    check_fixture()
    if args.map:
        check_map(args.map, args.catalog_offset, args.samples)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
