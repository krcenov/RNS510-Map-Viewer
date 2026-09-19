"""
prd_reader.py -- decodes eeuz.prd, CRACKED: a phonetic pronunciation
catalog for road names, presumably feeding the same text-to-speech
engine eeuz.pca's phoneme catalog serves (voice guidance, e.g. "turn
right onto Via ..."). Not previously examined at all before the session
that cracked the record framing and `roadID` field (only its
FLAT_COMPRESSED container was known, README S3.5); the 2 remaining
fields (`minNumber`/`maxNumber`, a real house-number address range) were
cracked in a later session via `eeu.mod`'s own schema, validated
exhaustively (zero exceptions across all 11,960,527 records).

============================================================================
Container
============================================================================
Standard FLAT_COMPRESSED (research/flat_compressed_reader.py) -- on the
reference disc: 279,342,884 bytes compressed, 599,975,088 bytes (572MB)
decompressed, block_size 3072 (same as every other FLAT_COMPRESSED file).
Decompresses in ~2.5s with flat_compressed_reader.decompress_all().

============================================================================
Record format -- CRACKED, validated at FULL scale (every byte of the
decompressed file, not a sample)
============================================================================
Same 94-byte SIEMENS header as every other file on this disc, then a
sequence of self-delimiting variable-length records, back-to-back, no
padding:

    +0            uint8   name_len
    +1            bytes   name (ASCII, name_len bytes -- the FULL human-
                          readable name, type word FIRST, natural spoken
                          order, e.g. "VIA LIDO AZZURRO" -- NOT the
                          type-word-demoted `;`-rewritten sort-key form
                          eeuz.prl (README S3.7) uses)
    +1+name_len   uint8   phon_len
    ...           bytes   phon (ASCII, phon_len bytes -- a phonetic
                          transcription, see below)
    ...           uint32 LE  f1  -- the eeu.rd record index this entry
                                    describes (CRACKED, see below)
    ...           uint32 LE  f2  -- NOT cracked (see below)
    ...           uint32 LE  f3  -- NOT cracked (see below)

**Validated at full scale, not a sample**: parsing the ENTIRE 599,975,088-
-byte decompressed body this way, record after record, consumes EVERY
byte with ZERO leftover/misaligned bytes at EOF and produces exactly
11,960,527 well-formed records. A wrong record-format guess would almost
certainly drift and either crash or leave a nonzero remainder well before
reaching 572MB of real data -- this is about as strong a structural
confirmation as a fixed-plus-variable-length record format can get without
an explicit spec.

============================================================================
The phonetic transcription
============================================================================
A custom (or lightly adapted X-SAMPA-like) phonetic alphabet, syllable
breaks marked with `|`, primary stress marked with a leading `"` on the
stressed syllable, secondary stress with `%`. Confirmed genuinely
linguistically correct on real examples across UNRELATED language
families (strong evidence this is real phonetic data, not noise that
happens to look structured):
  - Italian "GUITGIA" -> `kon|"tra|da "gwit|dZa` (for "CONTRADA GUITGIA")
    -- `dZ` = voiced postalveolar affricate, the correct sound for
    Italian soft "gi".
  - Italian "VIA MASSIMO D'AZEGLIO" -> `"vi|a "mas|si|mo dad|"dzEL|Lo` --
    `dz` for the "z" in "Azeglio", `E` for the open-e in "-zeglio", a
    doubled `L` for the palatal "gli" /ʎ/ sound -- all correct for real
    Italian pronunciation.
  - Norwegian "E75" -> `"e: s2|ti|"fem` -- literally "E syttifem" (E
    seventy-five) spoken out, `2` standing in for the Norwegian ø/ö
    vowel in "sytti".
  - Norwegian "341" -> `"tre: ""h}n|dr@ %O f2|ti|"e:n` -- "tre hundre og
    førtién" (three hundred and forty-one), spoken out digit-group by
    digit-group, `}` for another rounded-vowel sound and `2` again for ø.

Route/highway numbers are spoken out as real number words in the local
language, not read digit-by-digit -- genuine number-to-speech generation,
not a lookup table of pre-recorded digit clips.

============================================================================
Field 1 -- CRACKED: the eeu.rd record index
============================================================================
`f1` is a direct `eeu.rd` (README S3.1) record index. Validated on a
5,000-record random sample spanning the WHOLE file (not just the initial
cluster): 5000/5000 (100%) are valid indices, and 5000/5000 (100%) of
those have `eeu.rd`'s own (type-word-free) name as an exact
substring/suffix of this record's own `name` field -- e.g. `eeu.rd`
record 6's name is "LIDO AZZURRO"; this file's own record for `f1=6` is
"VIA LIDO AZZURRO" (the type word `VIA` prepended, natural spoken order,
unlike `.prl`'s `;`-demoted sort-key form).

Coverage: 5,981,409 of `eeu.rd`'s 8,809,081 records (67.9%) have at least
one `.prd` entry. Multiplicity (most roads get more than one phonetic
entry -- e.g. once for the bare name, once with the containing place name
appended for disambiguation, see below): 2 entries is the single most
common case (2,721,836 roads), then 1 (1,779,289), then 3 (1,207,162),
tailing off sharply from there (max observed: 9 entries for 2 roads).

============================================================================
Fields 2 and 3 -- CRACKED (later session): a house-number address range
============================================================================
`eeu.mod`'s own schema (research/mod_reader.py) names this table
`phRoad`, with real fields `graphemLength`/`graphem`(=name)/
`phonemLength`/`phonem`(=phon)/`roadID`(=f1, already confirmed)/
`minNumber`(=f2)/`maxNumber`(=f3) -- directly naming `f2`/`f3` as a
house-number address range, immediately explaining why the two earlier
hypotheses (nearby-road index; same-name count) both failed: they
were never pointers or counts at all.

**Validated EXHAUSTIVELY, not sampled**: `f2 <= f3` holds on EVERY SINGLE
one of the 11,960,527 records in the file, zero exceptions -- about as
strong a confirmation as a real min/max range invariant can get.
3,171,255 records (26.5%, matching the earlier-observed "`f2==0` for
26.5% of records" finding exactly) have `f2==f3==0` -- no house-number
data for that road (plausible: piazzas, footpaths, and other
non-addressed ways realistically have none). Real, plausible-looking
examples: "VIA LIDO AZZURRO" -> `47-49` (a short street, small range);
"VIA DEPOSITI" -> `1-95` (a longer street, wider range);
"PIAZZA MEDUSA"/"PIAZZA CASTELLO"-style square/plaza entries mostly
`0-0` (matches the earlier observation of the pattern skewing toward
0/1-ish `f2` values -- squares with no linear address range are common
in this sample). Also explains the earlier observation that `(f2, f3)`
is IDENTICAL across every one of a road's own multiple `.prd` entries
(e.g. bare name + "name, containing place" variants) -- a house-number
range is a property of the ROAD segment itself, not of any one
phonetic-name variant.

**A genuine cross-file curiosity, not a contradiction**: `eeuz.rl`
(README S3.7) independently declares its OWN `minNumber`/`maxNumber`
pair (packed, gated by a `hasHouseNumbers` flag) but that copy is
ALWAYS ZERO on this disc -- while `eeuz.prd`'s own copy here IS
populated with real data. Two different tables, sharing the schema's
naming convention, populated independently and inconsistently at build
time -- not investigated further (would require checking a different
region/market disc to see whether `eeuz.rl`'s own range is ever
populated there).

============================================================================
The duplicate-entry pattern (a real, useful side finding)
============================================================================
Where a road has 2+ `.prd` entries, a common pattern (not universal) is:
one or more entries for the bare name, plus one entry for
`"<name>, <containing place>"` (the same `"<place>, <parent place>"`
convention `eeu.cty`, README S3.8, uses) -- e.g. `eeu.rd` record 8
("CRISTOFORO COLOMBO") has entries for plain "VIA CRISTOFORO COLOMBO"
and for "VIA CRISTOFORO COLOMBO, LAMPEDUSA E LINOSA". Plausible real use:
disambiguating a common street name by speaking the city too ("Via
Cristoforo Colombo, Lampedusa e Linosa") -- not confirmed on hardware.

============================================================================
Practical use
============================================================================
`iter_prd_records()` streams every record from an already-decompressed
buffer (pass `flat_compressed_reader.decompress_all(open_flat(path))`).
For quick spot checks on a manageable prefix, `decompress_range()` on the
first few blocks is much cheaper than decompressing the whole 572MB.
"""

import struct


def iter_prd_records(body, header_size=94):
    """Yield (name, phon, road_id, min_number, max_number) tuples from an
    already-decompressed eeuz.prd buffer (the FULL logical file, header
    included -- pass flat_compressed_reader.decompress_all()'s own return
    value directly). `road_id` is an eeu.rd record index; `min_number`/
    `max_number` is a real house-number address range for that road
    (min_number <= max_number holds on every record in the file, or both
    are 0 if the road has no house-number data -- see this module's
    docstring). Streams without building a full list, so this is safe to
    call on the whole 572MB decompressed file."""
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
        road_id, min_number, max_number = struct.unpack_from("<III", data, pos)
        pos += 12
        yield name, phon, road_id, min_number, max_number


def rd_name_and_lonlat(rd_data, index, header_size=94, record_size=67):
    """Minimal eeu.rd accessor (name + lon/lat), same convention as
    iof_reader.rd_record() -- kept local to avoid a cross-module
    dependency for a handful of spot checks. For bulk cross-referencing,
    prefer road_naming.RdCache."""
    off = header_size + index * record_size
    name = rd_data[off + 24:off + 24 + 43].split(b"\x00", 1)[0]
    lon = struct.unpack_from("<i", rd_data, off + 8)[0] / 100000.0
    lat = struct.unpack_from("<i", rd_data, off + 12)[0] / 100000.0
    return name, lon, lat
