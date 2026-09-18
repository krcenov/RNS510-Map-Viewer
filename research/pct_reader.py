"""
pct_reader.py -- decodes eeuz.pct, CRACKED this session: a phonetic
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
The 6-byte "group" field -- grouping behavior CRACKED and validated;
numeric meaning NOT cracked (several hypotheses tested and refuted)
============================================================================
**CRACKED: this field reliably groups every language's name variant for
the SAME real place.** Across the full file: 649,956 records, 314,645
distinct 6-byte values. Real, checked examples (every member of the group,
not a cherry-picked pair):
  - Group `744f180bf414` (26 members): `VENEDIG`, `VELENCE`, `VENETSIA`,
    `VENICE`, `VENISE`, `BENATKY`, `VENETIA`, `VENEZA`, ... -- every one a
    genuine real name/exonym for Venice, Italy, in a different language.
  - Group `e4ac7f072c00` (26 members): `VATIKANVAROS`, `CIUDAD DEL
    VATICANO`, `CITTA DEL VATICANO`, `CIDADE DO VATICANO`,
    `VATIKANSTATEN`, `VATICAN CITY`, `KRATOS TOU VATIKANOU`, `CITE DU
    VATICAN`, ... -- Vatican City in 26 languages.
  - Group `9b7c220eb618` (22 members) and `bb934d036b0e` (22 members) --
    Munich and Frankfurt am Main, same pattern.
Group sizes: median 2, mean 2.07, max 73,396 -- but that max is a single
outlier: the all-zero group `000000000000` (73,396 members) is clearly a
SENTINEL for "no cross-language grouping" (consistent with this project's
established `0` = unset/padding-sentinel convention seen elsewhere, e.g.
the false-edge topology bug, README S3.6/S10 "v16 -> v17") -- its members
are small, single-language-looking local place names (observed: minor
Cretan localities/hamlets) with no obvious international exonym, not real
"same group" collisions. Excluding that sentinel, the real groups' mean
size is closer to 1.8 -- a handful of major internationally-known cities
get a dozen-plus variants, most named places get 1-2.

**NOT cracked: what the nonzero 6-byte value itself actually IS.** Three
hypotheses tested this session, all refuted by direct lookup:
  - Sequential index into `eeu.cty` (README S3.8, 939,351 records): the
    interpreted-as-uint32 values (tens to hundreds of millions) are far
    outside `eeu.cty`'s own record-count range.
  - Absolute byte offset into `eeu.cty` (74,208,823 bytes): landing at
    that offset does not produce a valid-looking 79-byte record for any
    of the 5 example groups checked.
  - Absolute byte offset into `eeuz.fea` (README S3.10, 553,149,233
    bytes -- itself a multi-language gazetteer with the exact same "many
    names, one real place" shape, the most structurally plausible
    candidate): none of the tested offsets land on a recognizable zlib
    stream header.
  Not yet tried: a hash function (FNV or similar) over some canonical
  internal identifier this session had no independent way to derive: the
  fact that WIDELY different spellings (`VENICE` vs `VENEDIG` vs
  `BENATKY`) share the identical group value rules out a hash of the
  displayed text itself, so if this is a hash, it's over some other,
  not-yet-identified per-place database key.

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
