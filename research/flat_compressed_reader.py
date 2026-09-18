"""
Reader for RNS510 FLAT_COMPRESSED (files.cfg compressionType=1) files:
eeuz.rt, eeuz.rl, eeuz.prl, eeuz.prd, eeuz.cl, eeuz.ct, eeuz.pct, eeuz.pca.

Format (fully verified against eeuz.pca and eeuz.rt -- decompressing all
blocks and concatenating reproduces a file starting with the standard
94-byte "SIEMENS" header, byte-identical in the pca case to the whole
uncompressed logical file):

  offset 0   : 3 bytes ASCII magic "zip"
  offset 3   : 1 byte version (=1 observed everywhere)
  offset 4   : uint32 LE block_size  -- uncompressed block size, 3072 in
               every file examined (pca/rt/rl/prl/cl)
  offset 8   : uint32 LE total_uncompressed_size -- size of the logical
               (original NOT_COMPRESSED-equivalent) file
  offset 12  : uint32 LE val3 -- meaning not fully confirmed; for the
               3-block eeuz.pca it exactly equals the first block's
               COMPRESSED size (1233), but this does not hold for larger
               files (rt: val3=1352, but offs[1]-offs[0]=911) so it is
               probably NOT simply "size of block 0" in general -- treat
               as unknown/reserved, not required for decoding.
  offset 16  : offset table, (n_blocks + 1) x uint32 LE, where
               n_blocks = ceil(total_uncompressed_size / block_size).
               offs[i] = file offset where compressed block i begins;
               offs[n_blocks] == total FILE size (of the .z file itself).
               Each block is an independent raw zlib (RFC1950, has the
               0x78 header) stream; decompressing block i yields exactly
               block_size bytes, except the last block which yields
               total_uncompressed_size % block_size (or block_size if
               it divides evenly).

Usage:
    import flat_compressed_reader as fcr
    doc = fcr.open_flat(r"D:\\DB\\eeuz.rt")
    data = fcr.decompress_all(doc)          # full logical file, bytes
    block = fcr.decompress_block(doc, 5)    # just block 5
"""

import struct
import zlib
from dataclasses import dataclass


@dataclass
class FlatDoc:
    data: bytes          # raw bytes of the .z file (mmap-friendly if needed)
    version: int
    block_size: int
    total_size: int
    val3: int
    offsets: tuple        # n_blocks+1 uint32 file offsets


def open_flat(path):
    with open(path, "rb") as f:
        data = f.read()
    assert data[:3] == b"zip", f"unexpected magic {data[:3]!r}"
    version = data[3]
    block_size, total_size, val3 = struct.unpack_from("<3I", data, 4)
    n_blocks = -(-total_size // block_size)  # ceil
    offsets = struct.unpack_from(f"<{n_blocks+1}I", data, 16)
    assert offsets[-1] == len(data), (
        f"offset table end {offsets[-1]} != file size {len(data)} "
        "(block_size guess or header parsing is wrong for this file)"
    )
    return FlatDoc(data, version, block_size, total_size, val3, offsets)


def decompress_block(doc: FlatDoc, i: int) -> bytes:
    chunk = doc.data[doc.offsets[i]:doc.offsets[i + 1]]
    return zlib.decompress(chunk)


def decompress_range(doc: FlatDoc, start_block: int, end_block: int) -> bytes:
    return b"".join(decompress_block(doc, i) for i in range(start_block, end_block))


def decompress_all(doc: FlatDoc) -> bytes:
    n_blocks = len(doc.offsets) - 1
    out = decompress_range(doc, 0, n_blocks)
    return out[:doc.total_size]


def byte_offset_to_block(doc: FlatDoc, logical_offset: int):
    """Given a byte offset into the logical uncompressed file, return
    (block_index, offset_within_decompressed_block)."""
    return divmod(logical_offset, doc.block_size)
