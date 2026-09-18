"""
prd_reader.py -- decodes eeuz.prd, CRACKED this session: a phonetic
pronunciation catalog for road names, presumably feeding the same
text-to-speech engine eeuz.pca's phoneme catalog serves (voice guidance,
e.g. "turn right onto Via ..."). Not previously examined at all -- this is
the first session to look at this file's content (only its FLAT_COMPRESSED
container was known, README S3.5).

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
Fields 2 and 3 -- NOT CRACKED (two hypotheses tested and REFUTED this
session -- read before re-attempting either)
============================================================================
**REFUTED: "index of a nearby/related road."** An early small sample (the
first ~40 records, all from one tight Linosa, Sicily cluster) looked like
`f2`/`f3` were `eeu.rd` indices of geographically nearby roads (every
pair under 1km apart). This did NOT hold up at full-file, randomly-sampled
scale: median distance between a record's own road and its `f2`/`f3`
"targets" (interpreted the same way) is ~1,700km, essentially the span of
the whole dataset -- i.e. uncorrelated with real distance. The early
sample was misleading because in that specific tight cluster, EVERY small
index (both origin and "target") happens to be geographically close
regardless of any real relationship between them -- a sampling artifact,
caught by re-testing at proper scale (this project's established
discipline: don't trust a hypothesis validated on fewer than a few
thousand real, randomly-drawn samples).

**REFUTED: "total count of eeu.rd records sharing this exact name."**
`f3` is usually a small number (rarely above a few dozen). Real `eeu.rd`
name-frequency counts for the same sample roads are much larger (e.g.
"MASSIMO D'AZEGLIO" occurs 556 times across the whole disc, this record's
own `f3` was 3) -- doesn't match at the whole-disc scope. Scoping the
count to "just this local area/city" was not tested (no ready per-area
grouping to test against was available this session) and remains a live,
untested variant of this idea.

**Observed, not yet explained**: `f2` is 0 for 26.5% of records and,
when nonzero, is very heavily concentrated at small values (median 1,
with `f2==1` alone covering roughly half of ALL 11.96M records) --
looks rank/count-like, not like an arbitrary pointer. `f3` is 0 for the
same 26.5% of records (i.e. `f2`/`f3` are zero together) but has a wider,
less concentrated nonzero distribution (median 20). Both are IDENTICAL
across every one of a road's own multiple `.prd` entries (e.g. all 2-3
entries for one `eeu.rd` index always share the exact same `(f2, f3)`
pair) -- so whatever they mean, it's a property of the ROAD (or its local
context), not a per-duplicate-entry variant counter (a "1st/2nd/3rd
phonetic variant" rank hypothesis was checked directly against this and
also does NOT hold -- the observed duplicate groups all show identical,
not incrementing, `(f2, f3)`). A genuinely untested next idea: `f2`/`f3`
as a (rank, total) pair over `eeu.rd` records sharing the same name
WITHIN A SMALL LOCAL AREA specifically (not the whole disc) -- would need
a per-area grouping (e.g. via `eeu.cty` bounding boxes, README S3.8) to
test properly.

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
    """Yield (name, phon, f1, f2, f3) tuples from an already-decompressed
    eeuz.prd buffer (the FULL logical file, header included -- pass
    flat_compressed_reader.decompress_all()'s own return value directly).
    Streams without building a full list, so this is safe to call on the
    whole 572MB decompressed file."""
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
        f1, f2, f3 = struct.unpack_from("<III", data, pos)
        pos += 12
        yield name, phon, f1, f2, f3


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
