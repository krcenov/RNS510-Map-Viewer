import struct
import sys
sys.path.insert(0, r"C:\Users\krcenov\Desktop\rns510\research")
import map_compressed_reader as mcr


def parse_features(raw, declen, verbose=False):
    """Walk repeated [uint16 count][int32 lon][int32 lat][count*(int16 dx,int16 dy)]
    blocks starting at the tile's data_start, for as many blocks as remain
    plausible. Returns (features, end_offset) where features is a list of
    dicts {offset, count, anchor, points}."""
    data_start = mcr._find_subindex_data_start(raw, declen)
    if data_start is None:
        return [], None

    features = []
    pos = data_start
    while pos + 10 <= declen:
        count = struct.unpack_from("<H", raw, pos)[0]
        lon0 = struct.unpack_from("<i", raw, pos + 2)[0] / 100000
        lat0 = struct.unpack_from("<i", raw, pos + 6)[0] / 100000
        block_end = pos + 10 + count * 4
        if not mcr._plausible_lonlat(lon0, lat0):
            break
        if count > 5000 or block_end > declen:
            break
        pairs = struct.unpack_from(f"<{count*2}h", raw, pos + 10)
        pts = [(lon0, lat0)]
        clon, clat = lon0, lat0
        ok = True
        for i in range(count):
            dx, dy = pairs[2*i], pairs[2*i+1]
            clon += dx/100000
            clat += dy/100000
            pts.append((clon, clat))
        features.append({
            "offset": pos, "count": count, "anchor": (lon0, lat0), "points": pts,
            "block_end": block_end,
        })
        if verbose:
            print(f"  feature@{pos}: count={count} anchor=({lon0:.5f},{lat0:.5f}) "
                  f"end={block_end} last_pt={pts[-1]}")
        pos = block_end
    return features, pos
