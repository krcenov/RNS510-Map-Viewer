"""
pca_reader.py -- decodes eeuz.pca, CRACKED (record framing, full file
scale) this session: a phoneme catalog for COUNTRY/CONTINENT names,
the same self-delimiting record family as eeuz.pct (city phonetics,
research/pct_reader.py) and eeuz.prd (road phonetics,
research/prd_reader.py). Previously only "decompresses to a clean
phoneme/name catalog" was known -- content was never actually parsed.

============================================================================
Container
============================================================================
Standard FLAT_COMPRESSED (research/flat_compressed_reader.py) -- small:
7,545 bytes decompressed (3 blocks of up to 3,072 bytes each).

============================================================================
Record format -- CRACKED, validated at FULL scale (every byte of the
decompressed file)
============================================================================
Same 94-byte SIEMENS header, then self-delimiting variable-length
records, back-to-back, no padding:

    +0            uint8   name_len
    +1            bytes   name (ASCII/UTF-8, name_len bytes -- e.g.
                          "EUROPE", "AUSTRIA", "SCHWEIZ")
    +1+name_len   uint8   phon_len
    ...           bytes   phon (phon_len bytes -- same phonetic alphabet
                          as eeuz.prd/eeuz.pct: `|` syllable breaks, `"`
                          primary stress)
    ...           16 bytes  trailer -- CRACKED (2 of 4 sub-fields), see
                          below

**Validated at FULL scale**: parsing the entire 7,451-byte body this way
(94-byte header subtracted from 7,545) consumes every byte with ZERO
leftover at EOF, producing exactly 188 well-formed records.

============================================================================
The 16-byte trailer -- eeu.mod's real field names, 2 of 4 sub-fields
CRACKED
============================================================================
eeu.mod (research/mod_reader.py) names this table `phCatalog`, with 4
real per-record fields after `graphem`(=name)/`phonem`(=phon):
`clusterOffset`, `clusterCount`, `cityOffset`, `cityCount` -- read here
as 4 consecutive uint32 LE values (16 bytes total, matching the trailer
width exactly).

**`clusterOffset`/`clusterCount` (first 8 bytes) -- CRACKED (identity):
ALWAYS ZERO on every one of the 188 records, checked exhaustively.**
This is fully consistent with -- and cross-validates -- `eeu.pcl`
("phoneme cluster list", research/pcl_reader.py) being confirmed
genuinely EMPTY on this disc: there is no real phoneme-cluster data
anywhere for this catalog to point into, so every record's
`clusterOffset`/`clusterCount` correctly reads as the unset/empty
sentinel.

**`cityOffset`/`cityCount` (last 8 bytes) -- position CRACKED, MEANING
NOT CRACKED (target file not identified)**: a real, non-trivial
per-record value pair, CONSTANT across every name-variant of the same
country (all 11 AUSTRIA/AUTRICHE/OOSTENRIJK/RAKOUSKO/... variants share
`cityOffset=14379305`/`cityCount=10712`), and monotonically increasing
in file order as new countries appear (`EUROPE`: 0/295201; `AUSTRIA`:
14379305/10712; `SCHWEIZ`: 15096780/6821; `CECHIA`: 15351594/14353;
`ALEMANHA`: 16004066/73209; `ITALIA`: 20445379/38006; ...) -- 20 distinct
(offset, count) groups total across the 188 records, one per real
country/continent entry.

**Tested against `eeu.cty`** (the obvious candidate, given the field
name): neither a raw byte offset into `eeu.cty`'s own file (lands on
unrelated Hungarian content for Austria's `cityOffset`) nor the reversed
field assignment (lands on unrelated Greek content) produces Austrian
place names at the expected position. Further ruled out the "contiguous
per-country block" model this would require: a full-file scan of
`eeu.cty`'s own `bytes[57:59]` country tag (README S3.8) finds **441,325**
tag-change transitions across the file's 939,351 records -- the tag is
NOT one single contiguous block per country as previously summarized,
but interleaves at fine granularity (consistent with a spatial/tile
ordering, not a strict per-country sort) -- so a simple "offset = start
of this country's one block" model doesn't fit `eeu.cty`'s own real
layout regardless of the specific offset value tried.

**Not tested**: `eeuz.cl`/`eeuz.ct` (the FLAT_COMPRESSED city-search
sibling files) and `eeuz.fea` (the gazetteer -- FEATURE_COMPRESSED, own
directory encoding not fully cracked, so a raw "byte offset" may not
even be a meaningful concept there without further work). Given the
field's real name (`cityOffset`/`cityCount`), the most likely remaining
candidate is a pointer into `eeuz.pct` (city phonetics) analogous to
that file's own `phonemeRoadOffset` pointer into `eeuz.prd` -- i.e. this
country catalog pointing forward to "this country's own city name
phonetic entries" -- but a direct byte-offset test into `eeuz.pct`'s
decompressed body also failed (lands on unrelated Turkish content for
Austria). Left open for a future session.

============================================================================
Practical use
============================================================================
`iter_pca_records()` mirrors `pct_reader.iter_pct_records()`'s streaming
interface. `parse_trailer()` unpacks the 16-byte trailer into its 4
named uint32 sub-fields.
"""

import struct


def iter_pca_records(body, header_size=94):
    """Yield (name, phon, trailer) tuples from an already-decompressed
    eeuz.pca buffer (the FULL logical file, header included). `trailer`
    is the raw 16-byte region -- see this module's docstring for what's
    cracked (clusterOffset/clusterCount, always zero) and what isn't
    (cityOffset/cityCount's target file)."""
    data = body[header_size:]
    pos = 0
    n = len(data)
    while pos < n:
        name_len = data[pos]
        name = data[pos + 1:pos + 1 + name_len]
        pos = pos + 1 + name_len
        phon_len = data[pos]
        phon = data[pos + 1:pos + 1 + phon_len]
        pos = pos + 1 + phon_len
        trailer = data[pos:pos + 16]
        pos += 16
        yield name, phon, trailer


def parse_trailer(trailer_bytes):
    """The 16-byte trailer as (clusterOffset, clusterCount, cityOffset,
    cityCount) -- eeu.mod's own real field names. clusterOffset/
    clusterCount are always 0 on this disc (eeu.pcl is empty);
    cityOffset/cityCount's target file is not identified (see this
    module's docstring)."""
    return struct.unpack_from("<IIII", trailer_bytes, 0)
