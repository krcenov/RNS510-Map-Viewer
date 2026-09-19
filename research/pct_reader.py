"""
pct_reader.py -- decodes eeuz.pct, CRACKED this session (and the one
remaining open field fully closed out in a LATER session via eeu.mod,
research/mod_reader.py -- the disc's own schema dictionary): a phonetic
pronunciation catalog for CITY names (major places only, multi-language),
the same family as eeuz.prd (research/prd_reader.py, road names) and
presumably feeding the same TTS engine eeuz.pca's phoneme catalog serves.
Not previously examined at all -- only its FLAT_COMPRESSED container was
known (README S3.5).

============================================================================
Container
============================================================================
Standard FLAT_COMPRESSED (research/flat_compressed_reader.py) -- on the
reference disc: 15,653,000 bytes compressed, 27,386,579 bytes decompressed,
block_size 3072.

============================================================================
Record format -- CRACKED, validated at FULL scale (every byte of the
decompressed file)
============================================================================
Same 94-byte SIEMENS header, then self-delimiting variable-length records,
back-to-back, no padding -- structurally close to eeuz.prd's format but
with a smaller, differently-shaped trailer:

    +0            uint8   name_len
    +1            bytes   name (ASCII/UTF-8, name_len bytes -- e.g.
                          "VENICE", "MUNCHEN", "ATHINA")
    +1+name_len   uint8   phon_len
    ...           bytes   phon (phon_len bytes -- same phonetic alphabet
                          as eeuz.prd: `|` syllable breaks, `"` primary
                          stress, `%` secondary stress)
    ...           6 bytes "group" -- CRACKED behavior, NOT cracked meaning
                          (see below)

**Validated at FULL scale**: parsing the entire 27,386,485-byte
decompressed body this way consumes every byte with ZERO leftover at EOF,
producing exactly 649,956 well-formed records.

============================================================================
The phonetic transcription
============================================================================
Same alphabet as eeuz.prd (see that module's docstring) -- syllable-broken,
stress-marked. Real examples from this file: Hungarian `ATENY` (Athens) ->
`"?a|te:|ni`; English `ATHENS` -> `"{|T@nz` (`{` = the TRAP vowel, `T` =
voiceless "th", both correct X-SAMPA for English "Athens"); Turkish
`ISTANBUL` -> `is|tan|"bu5` (soft final consonant symbol consistent with
Turkish's rounded/darkened final "l" in some transcription schemes).

============================================================================
The 6-byte "group" field -- FULLY CRACKED (a later session closed the
remaining gap via eeu.mod, the disc's own schema dictionary)
============================================================================
**This field reliably groups every language's name variant for the SAME
real place** -- and IS a `[uint32 LE offset][uint16 LE count]` pointer
into `eeuz.prd` (research/prd_reader.py), naming that city's own list of
ROAD/ROUTE phonetic entries -- confirmed by `eeu.mod`'s own real field
names for this exact table (`phCity`): `.../phonemeRoadOffset/
phonemeRoadCount`. Multi-language name variants of the same real city
correctly share the identical group value because they all refer to the
SAME underlying place's SAME roads -- what looked at first like a
"language-variant grouping key" is really "this city's own roads",
incidentally shared across every spelling of that city's name.

**Validated directly against real content in `eeuz.prd`, not just
schema-name-matching**: interpreting the group bytes this way and looking
at `eeuz.prd` right around the resulting offset finds real, clearly
place-appropriate road/route entries for every example checked --
Venice's group (`744f180bf414`) lands right next to real Adriatic
ferry-route entries `VENEZIA-CORFÙ` and `VENEZIA-PATRASSO`; Vatican
City's group lands among real Italian streets (`VIA ARIANO IRPINO`, `VIA
SORRENTO` -- Vatican City sits inside Rome, so nearby Italian street
names is exactly right); Munich's lands at a real Munich square
(`LEONRODPLATZ`); Frankfurt's lands among real Frankfurt streets
(`MANNHEIMER STRASSE`, `DÜSSELDORFER STRASSE`). The exact byte-level
anchor convention (whether `offset` is a raw absolute file position or
needs a small fixed adjustment) was not pinned down to the last byte --
the landing point is sometimes a handful of bytes before the nearest
clean `eeuz.prd` record boundary rather than exactly on one -- but the
overall mechanism (offset+count pointer to a city's own road phonetics)
is no longer in doubt.

Across the full file: 649,956 records, 314,645 distinct 6-byte values,
median group size 2, mean 2.07. The single largest "group"
(`000000000000`, 73,396 members) is the sentinel for "no roads/offset
recorded" (consistent with this project's established `0` = unset/
padding-sentinel convention seen elsewhere, e.g. the false-edge topology
bug, README S3.6/S10 "v16 -> v17") -- its members are small, single-
language-looking local place names (observed: minor Cretan localities/
hamlets) with presumably no road data linked, not a real 73,396-way
collision.

Full methodology for the schema discovery itself: research/mod_reader.py.

============================================================================
Practical use
============================================================================
`iter_pct_records()` mirrors prd_reader.iter_prd_records()'s streaming
interface -- pass it flat_compressed_reader.decompress_all()'s return
value directly (this file is small enough, ~27MB decompressed, that
decompressing the whole thing is cheap, well under a second).
"""

import struct


def iter_pct_records(body, header_size=94):
    """Yield (name, phon, group) tuples from an already-decompressed
    eeuz.pct buffer (the FULL logical file, header included). `group` is
    the raw 6-byte trailer -- see this module's docstring for what's
    established about it (reliably groups a real place's multi-language
    name variants) and what isn't (the value's own derivation)."""
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
        group = data[pos:pos + 6]
        pos += 6
        yield name, phon, group


def group_int(group_bytes):
    """The 6-byte group trailer as a single little-endian integer, for
    convenience when testing a new hypothesis against it."""
    return int.from_bytes(group_bytes, "little")


def parse_group(group_bytes):
    """The 6-byte group trailer as (offset, count) -- eeu.mod's own real
    field names, `phonemeRoadOffset`/`phonemeRoadCount`: a pointer into
    eeuz.prd (prd_reader.py) naming this city's own road/route phonetic
    entries. `offset` may need a small manual adjustment to land exactly
    on a prd record boundary -- see this module's docstring."""
    return struct.unpack_from("<IH", group_bytes, 0)
