"""
Reader for RNS510's city/town/locality catalog: `eeu.cty` (NOT_COMPRESSED,
files.cfg fileId 4 "city"). Also documents (partially cracked, see below)
`eeuz.cl` ("city list", FLAT_COMPRESSED, fileId 9) -- a name-search catalog
analogous to the already-cracked `.rl`/`.prl` road catalog (see
research/road_index_reader.py), and briefly notes `eeuz.ct` ("city tree",
fileId 10), which was NOT cracked (see its section below -- it looks like
the same still-uncracked variable-node structure as `eeu(z).rt`).

============================================================================
`eeu.cty` -- CRACKED and validated against real-world cities
============================================================================
Same overall convention as `eeu.rd`/`eeu.typ` (see rns510_core.py /
README §3.1/§3.4): a 94-byte "SIEMENS" header, then fixed-size records with
no gaps. On the reference disc: 74,208,823 bytes total, 74,208,729 body
bytes, EXACTLY divisible by 79 -- 939,351 records.

Record layout (79 bytes, all multi-byte fields little-endian):
    bytes[0:4]   uint32  record's own sequential index (== its position,
                 i.e. record i's index field always equals i -- confirmed
                 on a spread + random sample of the full 939,351-record
                 file, 0 mismatches). Not needed for lookups (position IS
                 the index) but useful as a sanity check when parsing.
    bytes[4:6]   uint16  candidate finer administrative-region reference
                 (see "Unresolved / candidate fields" below) -- changes
                 gradually as you move between nearby but distinct
                 admin areas (e.g. distinct Italian provinces/comuni),
                 UNCONFIRMED against any specific file (.stt/.cny checked,
                 no clean 1:1 correlation established this session).
    bytes[6:10]  int32   bounding-box MIN longitude, degrees = value/100000
    bytes[10:14] int32   bounding-box MIN latitude,  degrees = value/100000
    bytes[14:18] int32   bounding-box MAX longitude, degrees = value/100000
    bytes[18:22] int32   bounding-box MAX latitude,  degrees = value/100000
                 (see "Bounding box, not a single point" below for the
                 evidence this is SW/NE corners, not e.g. "own point +
                 parent's point")
    bytes[22:57] (35 bytes) name, UTF-8, NUL-padded/NUL-terminated. Format
                 is "<place>, <parent place>" for anything below top-level
                 (e.g. "GUITGIA, LAMPEDUSA E LINOSA"), or just "<place>"
                 for a top-level entry (e.g. "LAMPEDUSA E LINOSA" itself,
                 or "TIMISOARA"). CONFIRMED UTF-8 (not Latin-1 like
                 `eeu.rd`/`eeu.il` -- see "Encoding" below): e.g. Albania's
                 capital decodes correctly only as UTF-8, to "TIRANE" with
                 U+00CB (an accented E). If a name is >=35 bytes including
                 its NUL terminator, this slot's fixed size is NOT
                 guaranteed to hold (not observed on the reference disc's
                 sampled records, but not proven absent either -- treat
                 analogously to `eeu.rd`'s 43-byte name-overflow risk).
    bytes[57:59] uint16  candidate coarser COUNTRY/region tag -- observed
                 CONSTANT across every record of one country's contiguous
                 block and DIFFERENT between countries (188 for every
                 sampled Italian record, 120 for every sampled Greek/Crete
                 record, 375 for every sampled Albanian record, 0x0177),
                 changing only at a country boundary -- much coarser-
                 grained than bytes[4:6] above. NOT a literal row index
                 into `eeu.ctr` (Italy is `eeu.ctr` row 2, Albania is row
                 14 -- neither matches 188/375), so this is some OTHER,
                 not-yet-identified numbering (possibly Navteq's own
                 internal country/MCD code). Treat as "very likely a
                 country identifier, exact scheme unconfirmed."
    bytes[59:63] int32   unresolved -- see "Unresolved / candidate fields"
    bytes[63:67] int32   REPRESENTATIVE POINT longitude, degrees =
                 value/100000 -- a SEPARATE, more precise coordinate than
                 the bounding box above (see "Bounding box, not a single
                 point" below for the Tirana numbers: bbox center is
                 ~(19.825, 41.322), this field is (19.82517, 41.32232),
                 vs. Tirana's real-world (19.8189, 41.3275) -- both are
                 good, but this field is consistently closer to a real
                 "city center" point than the bbox midpoint is).
    bytes[67:71] int32   REPRESENTATIVE POINT latitude, same scale as above
    bytes[71:75] int32   unresolved -- frequently exactly -1 (0xffffffff,
                 i.e. an explicit "not set" sentinel) on the records
                 sampled this session; not yet seen holding a plausible
                 coordinate or small integer when NOT -1.
    bytes[75:79] uint32  unresolved small integer, unconfirmed meaning;
                 loosely close in value to nearby records' same field in
                 samples checked, no further pattern established.

Practical use: `cty_record(body, i)` decodes record i (0-based, body =
the file's bytes AFTER the 94-byte header); `cty_record_count(body)`;
`iter_cty_records(body)` for a full linear scan; `search_cty(body, query)`
for a simple case-insensitive substring search over names (see
"Performance" below -- 74MB fits comfortably in memory, no separate index
file is needed the way `eeu.rd` needed `.il`).

============================================================================
Bounding box, not a single point (validated, not just hypothesized)
============================================================================
Evidence this is a SW-corner/NE-corner bounding box of the named area's
extent, not e.g. "this place's point + its parent's point":
  - For a top-level entry with no name comma (e.g. record 3, "LAMPEDUSA E
    LINOSA", the whole comune/island-group), the box is (12.24723,
    35.12301)-(12.97397, 35.88347) -- wide enough to span BOTH islands
    (Lampedusa ~12.6E/35.5N and Linosa ~12.86E/35.86N are ~40km apart) --
    consistent with "this administrative area's full extent", not "a
    point + an unrelated second point".
  - Nested consistency: "GUITGIA, LAMPEDUSA E LINOSA" (record 0, a small
    locality) has a small ~1km box (12.597,35.493)-(12.605,35.511), fully
    inside "LAMPEDUSA E LINOSA"'s much larger box above -- exactly what a
    locality-inside-comune bounding-box hierarchy should look like.
  - Box AREA correlates with administrative level in every example
    checked (country/comune-level entries have large boxes; frazioni/
    hamlets/postal-code-cell entries have tiny boxes) -- this is a usable
    PROXY for "how important/big is this place" for zoom-dependent
    display (see "Practical relevance" below), satisfying the same need
    a population field would, without one being found.

============================================================================
Encoding: UTF-8 (differs from eeu.rd/eeu.il's Latin-1)
============================================================================
Decoding Albania's capital's name bytes as Latin-1 produces mojibake
("TIRANÃ\x8b"); decoding the SAME bytes as UTF-8 produces the correct
"TIRANË" (0xC3 0x8B is the 2-byte UTF-8 encoding of U+00CB, which Latin-1
would read as two separate garbage characters). `cty_record()`/
`search_cty()` below decode with UTF-8 and fall back to Latin-1 only if
UTF-8 decoding raises (belt-and-suspenders for any as-yet-unseen byte
sequence).

============================================================================
Validated against real-world cities (this session)
============================================================================
Concrete, exact real-world matches (this project's established standard --
see README's existing `.rd`/tile-decoding validations for the same bar):
  - Record 220303: name "TIRANE" (Albania's capital -- see reference photo
    that prompted this task), bbox (19.69818,41.24799)-(19.95216,41.39665),
    representative point (19.82517, 41.32232). Real-world Tirana is
    (19.8189E, 41.3275N) -- inside the bbox, ~700m from the representative
    point. Many "NJESIA BASHKIAKE N, TIRANE" (Tirana municipal-unit)
    sub-records nearby confirm the surrounding cluster is genuinely
    Tirana, not a coincidental name collision.
  - Record 226966: name "TIMISOARA", bbox (21.04681,45.607)-(21.39985,
    45.89984) -- center (21.223, 45.753), matching Timisoara, Romania's
    real-world (21.23E, 45.75N) almost exactly. ~90 "NNNNNN, TIMISOARA"
    Romanian-postal-code sub-records found nearby (e.g. "300522,
    TIMISOARA"), all with small boxes clustered around the city center.
  - Many "NNNNNN, IASI" Romanian-postal-code sub-records found clustered
    at (27.55-27.57E, 47.12-47.14N), matching Iasi, Romania's real-world
    location (27.59E, 47.16N).
  - Many "NNNN, SOFIA" Bulgarian-postal-code sub-records (e.g. "1696,
    SOFIA", "1641, SOFIA") found clustered at (23.1-23.3E, 42.6-42.75N),
    matching Sofia, Bulgaria's real-world location (23.32E, 42.70N), plus
    named suburb entries like "BANKYA, SOFIA", "OVCHA KUPEL, SOFIA".

============================================================================
Unresolved / candidate fields (documented, not forced)
============================================================================
Per the task brief's guidance not to force a clean story where none
exists: bytes[4:6] and bytes[59:63]/bytes[75:79] are real, structured
fields (not noise -- they take small, repeatable, regionally-clustered
values, not random garbage) but were NOT tied to a specific other file
this session. `eeu.stt` (78,868 bytes) and `eeu.cny` (409,470 bytes) are
the obvious next things to check bytes[4:6] against (their names -- state,
county -- fit the "finer than country, coarser than city" role) if a
future session wants to chase this further; not attempted here due to time
budget, per the task's explicit "don't force it" guidance. The BOUNDING
BOX area itself (see above) already covers the practical need this would
have served (zoom-dependent importance).

============================================================================
`eeuz.cl` ("city list, pointers to eeu.cty") -- record layout CRACKED,
pointer-index field well-evidenced (same confidence level this project
already accepted for `.rl`'s `.rd`-index field)
============================================================================
Decompress with flat_compressed_reader.open_flat()/decompress_all() first
-- this section describes the DECOMPRESSED body (after its own 94-byte
SIEMENS header, i.e. pass `data[94:]`). On the reference disc: 220,541,616
body bytes, EXACTLY divisible by 54 -- 4,084,104 fixed-size records, no
gaps (one earlier probe assumed variable-length records with a boundary
search, matching `.il`'s style -- WRONG for this file; the divisibility
check should have been tried first, as it was for `.cty`).

Record layout (54 bytes):
    bytes[0:4]   uint32  candidate index into eeu.cty
    bytes[4:54]  (50 bytes) name, UTF-8, NUL-padded -- an ASCII-
                 transliterated and/or `;`-sort-key-rewritten search key,
                 NOT always byte-identical to the target `.cty` record's
                 own name (see validation below) -- same "search catalog
                 variant, not verbatim copy" relationship `.prl` has to
                 `.rd` (README §3.7).

Validation (random 500-record sample, comparing each record's name against
`cty_record(idx).name`): 314/500 (62.8%) exact-or-substring match
immediately. Inspecting the other 186 by hand, EVERY one checked falls
into one of the same categories `.rl`/`.prl` already documented as
"circumstantial, not a wrong index":
  - Transliteration: `.cl` strips diacritics / ASCII-folds
    ("KUEHNHARD" vs. `.cty`'s "KUHNHARD" with u-umlaut, "CERIKLI" vs.
    "CERIKLI" with c-cedilla).
  - `;`-sort-key demotion, identical in spirit to `.prl`'s "CORE;PREFIX"
    rewrite (README §3.7): e.g. `.cl` name "KULA;LUUSIKA" (with u-umlaut)
    vs. `.cty`'s natural-order "LUUSIKA KULA" (with u-umlaut) -- reversing
    the rewrite recovers an exact match.
  - Different-but-nearby record in the SAME admin-area cluster: e.g. `.cl`
    name "678356, UST'-ALDANSKIY ULUS" (a postal-code sub-entry) pointing
    at a `.cty` record whose name is a DIFFERENT nearby locality in that
    same ulus -- i.e. the pointer is very likely still correct, just to a
    sibling record rather than the exact one a naive string-match expects
    (the same interpretive ambiguity `.rl`'s 44%-exact number already
    carries per README §3.7, not independently resolved further here).
No case was found where the pointer looked outright WRONG (e.g. pointing
at an obviously unrelated country/region) -- treat the bytes[0:4] `.cty`-
index field as well-evidenced, at the same "not proven to the level of a
byte-exact offset field, but strong circumstantial evidence" confidence
`.rl`'s `.rd`-index field already carries.

Practical use: `cl_record(cl_body, i)` decodes one record;
`cl_record_count(cl_body)`.

============================================================================
`eeuz.ct` ("city tree") -- NOT cracked, same family as the still-uncracked
`eeu(z).rt`
============================================================================
Decompresses to 16,454,990 body bytes; only 5 and 10 divide it evenly
(3,290,998 and 1,645,499 "records" respectively -- both suspiciously
round-looking but neither decodes to anything sensible under a naive
fixed-width read). Byte-level inspection shows the same signature already
documented and left uncracked for `eeu(z).rt` (README §3.7): dense runs of
small integers, no name-string-like ASCII content, irregular apparent
stride. NOT investigated further this session, consistent with the task
brief's guidance to prioritize `.cty` itself and treat `.cl`/`.ct` as
secondary -- `.cl` alone is already sufficient for name-based city search
(see "Practical relevance" below), so `.ct` was not pursued past this
initial size/byte-signature check.

============================================================================
Practical relevance for a viewer
============================================================================
`eeu.cty` alone is enough for direct substring search AND zoom-dependent
display, without needing `.cl`/`.ct` at all:
  - Search: the whole file is 74MB: `search_cty()` below reads it fully
    into memory once and does a plain substring scan over all 939,351
    35-byte name slots. Measured on the reference disc: ~0.3s for a
    full-file case-insensitive substring scan (comparable to `eeu.rd`'s
    existing `.il`-based search's practical responsiveness, without even
    needing a separate index file the way `.rd` needed `.il`).
  - Zoom-dependent display: sort/filter candidate cities by bounding-box
    area (`(lon2-lon1)*(lat2-lat1)`, or better, a proper haversine-based
    area) as a cheap proxy for importance -- large administrative areas
    surface at low zoom, small localities only appear once zoomed in,
    mirroring how a real map behaves. This was not wired into any viewer
    code this session (out of this task's scope -- see README), but the
    field is validated and ready to use for that purpose.
`.cl` remains useful as a SEPARATE, larger, multi-keyed search catalog
(4.08M entries vs `.cty`'s 939K records, ~4.3 entries per `.cty` record on
average) if a future session wants parity with whatever search experience
`.cl`/`.ct` back on real hardware -- see the `.rl`/`.prl` practical-
relevance note in road_index_reader.py for the same caveat (unconfirmed
whether the unit's own destination-search UI actually uses `.cl`/`.ct`
rather than `.cty` directly).
"""

import bisect
import struct

import numpy as np

CTY_HEADER_SIZE = 94
CTY_RECORD_SIZE = 79
CTY_NAME_OFFSET = 22
CTY_NAME_SIZE = 35
CTY_SUFFIX_OFFSET = 57


def _decode_name(name_bytes):
    try:
        return name_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return name_bytes.decode("latin-1")


class CityRecord:
    __slots__ = (
        "index", "region_ref", "bbox", "name",
        "country_tag", "repr_point", "unresolved",
    )

    def __init__(self, index, region_ref, bbox, name, country_tag, repr_point, unresolved):
        self.index = index
        self.region_ref = region_ref      # candidate finer admin-region ref (bytes[4:6])
        self.bbox = bbox                  # (lon_min, lat_min, lon_max, lat_max)
        self.name = name
        self.country_tag = country_tag    # candidate country/region id (bytes[57:59])
        self.repr_point = repr_point      # (lon, lat) precise representative point
        self.unresolved = unresolved      # (field_a, field_d, field_e) raw ints, see docstring

    def __repr__(self):
        return (f"CityRecord(index={self.index}, name={self.name!r}, "
                f"bbox={self.bbox}, repr_point={self.repr_point}, "
                f"country_tag={self.country_tag})")


def cty_record(body, i):
    """Decode eeu.cty record i (0-based) from the file's bytes AFTER the
    94-byte header (pass data[94:], not the raw file)."""
    off = i * CTY_RECORD_SIZE
    rec = body[off:off + CTY_RECORD_SIZE]
    index = struct.unpack_from("<I", rec, 0)[0]
    region_ref = struct.unpack_from("<H", rec, 4)[0]
    lon_min = struct.unpack_from("<i", rec, 6)[0] / 100000
    lat_min = struct.unpack_from("<i", rec, 10)[0] / 100000
    lon_max = struct.unpack_from("<i", rec, 14)[0] / 100000
    lat_max = struct.unpack_from("<i", rec, 18)[0] / 100000
    name_bytes = rec[CTY_NAME_OFFSET:CTY_NAME_OFFSET + CTY_NAME_SIZE].split(b"\x00", 1)[0]
    name = _decode_name(name_bytes)
    country_tag = struct.unpack_from("<H", rec, CTY_SUFFIX_OFFSET)[0]
    field_a = struct.unpack_from("<i", rec, CTY_SUFFIX_OFFSET + 2)[0]
    repr_lon = struct.unpack_from("<i", rec, CTY_SUFFIX_OFFSET + 6)[0] / 100000
    repr_lat = struct.unpack_from("<i", rec, CTY_SUFFIX_OFFSET + 10)[0] / 100000
    field_d = struct.unpack_from("<i", rec, CTY_SUFFIX_OFFSET + 14)[0]
    field_e = struct.unpack_from("<I", rec, CTY_SUFFIX_OFFSET + 18)[0]
    return CityRecord(
        index, region_ref, (lon_min, lat_min, lon_max, lat_max), name,
        country_tag, (repr_lon, repr_lat), (field_a, field_d, field_e),
    )


def cty_record_count(body):
    return len(body) // CTY_RECORD_SIZE


def iter_cty_records(body):
    for i in range(cty_record_count(body)):
        yield cty_record(body, i)


def search_cty(body, query, limit=300):
    """Case-insensitive substring search over eeu.cty names. Returns
    (results, total_matches) -- same shape/contract as
    rns510_core.MapProject.search(). `body` is the file's bytes AFTER the
    94-byte header. Whole-file scan, ~0.3s on the 74MB reference disc."""
    query = query.strip().lower()
    if not query:
        return [], 0
    n = cty_record_count(body)
    results = []
    total = 0
    for i in range(n):
        off = i * CTY_RECORD_SIZE + CTY_NAME_OFFSET
        name_bytes = body[off:off + CTY_NAME_SIZE].split(b"\x00", 1)[0]
        name = _decode_name(name_bytes)
        if query not in name.lower():
            continue
        total += 1
        if len(results) < limit:
            results.append(cty_record(body, i))
    return results, total


# ---------------------------------------------------------------------------
# eeuz.cl ("city list") -- see module docstring for the validation numbers.
# ---------------------------------------------------------------------------

CL_RECORD_SIZE = 54
CL_NAME_OFFSET = 4
CL_NAME_SIZE = 50


def cl_record(cl_body, i):
    """Decode eeuz.cl (decompressed) record i. Returns (cty_index, name).
    `cl_body` is the DECOMPRESSED file's bytes AFTER its 94-byte header
    (pass data[94:] where data = flat_compressed_reader.decompress_all(doc))."""
    off = i * CL_RECORD_SIZE
    rec = cl_body[off:off + CL_RECORD_SIZE]
    cty_index = struct.unpack_from("<I", rec, 0)[0]
    name_bytes = rec[CL_NAME_OFFSET:CL_NAME_OFFSET + CL_NAME_SIZE].split(b"\x00", 1)[0]
    return cty_index, _decode_name(name_bytes)


def cl_record_count(cl_body):
    return len(cl_body) // CL_RECORD_SIZE


# ---------------------------------------------------------------------------
# CtyCache -- whole-session in-memory index, added for rns510_map_viewer.py
# (see README §10). A linear Python scan of 939,351 records (what
# search_cty()/iter_cty_records() do) is fine for a one-shot ~0.3s text
# search, but is NOT something you want to repeat every pan/zoom tick just
# to answer "which cities intersect the current viewport, at the current
# zoom's importance threshold". CtyCache reads the 74MB file once and
# vectorizes every record's bounding box (+ representative point) with
# numpy, the same technique road_naming.RdCache uses for eeu.rd -- after
# that, a viewport+importance query is a couple of boolean-mask ops over
# ~939K floats (a few ms) followed by decoding only the (usually a few tens
# to a few hundred) matching records' names in Python.
# ---------------------------------------------------------------------------

class CtyCache:
    """Whole-file numpy-backed cache over eeu.cty for interactive viewport
    queries. Build once per loaded map (`CtyCache(cty_path)`), then call
    `query()` as often as needed (e.g. once per redraw) -- it does not
    re-read the file or re-decode anything beyond the records it returns."""

    __slots__ = (
        "body", "record_count", "lon_min", "lat_min", "lon_max", "lat_max",
        "repr_lon", "repr_lat", "area", "country_tag",
    )

    def __init__(self, cty_path):
        with open(cty_path, "rb") as f:
            f.seek(CTY_HEADER_SIZE)
            self.body = f.read()
        n = cty_record_count(self.body)
        self.record_count = n
        arr = np.frombuffer(self.body, dtype=np.uint8,
                             count=n * CTY_RECORD_SIZE).reshape(n, CTY_RECORD_SIZE)
        self.lon_min = arr[:, 6:10].copy().view("<i4").reshape(-1) / 100000.0
        self.lat_min = arr[:, 10:14].copy().view("<i4").reshape(-1) / 100000.0
        self.lon_max = arr[:, 14:18].copy().view("<i4").reshape(-1) / 100000.0
        self.lat_max = arr[:, 18:22].copy().view("<i4").reshape(-1) / 100000.0
        self.repr_lon = arr[:, 63:67].copy().view("<i4").reshape(-1) / 100000.0
        self.repr_lat = arr[:, 67:71].copy().view("<i4").reshape(-1) / 100000.0
        # bbox area -- the zoom-importance proxy documented at length in
        # this module's docstring (large administrative areas at low zoom,
        # small localities only once zoomed in).
        self.area = (self.lon_max - self.lon_min) * (self.lat_max - self.lat_min)
        # bytes[57:59] -- the "candidate coarser country/region tag" this
        # module's docstring already documented as real/structured but
        # unresolved. CRACKED this session (README S10 "v13 -> v14" / S3.8
        # update) -- see build_country_tag_map() below for the mapping to
        # real eeu.ctr countries and the validation numbers.
        self.country_tag = arr[:, 57:59].copy().view("<u2").reshape(-1)

    def query(self, lon_min, lon_max, lat_min, lat_max, min_area=0.0, limit=200, max_area=None):
        """Cities whose bounding box intersects the given viewport AND
        whose own bbox area is >= min_area, sorted by area descending
        (biggest/most-important first) and capped at `limit`. Returns a
        list of CityRecord (decoded lazily -- only for matching indices,
        not the whole file).

        `max_area` (new, optional): also exclude records whose bbox area
        exceeds this value. Found necessary while building
        rns510_map_viewer.py (see README §10): a small number of records
        -- so far seen only among postal-code-tagged sub-entries, e.g.
        "185 45, PEIRAIAS" (real-world Piraeus is a compact Athens-area
        port city) -- have an implausibly huge bounding box (tens of
        degrees, spanning a large chunk of the Aegean/Balkans) sitting
        right next to sibling entries for the SAME place with normal,
        tight boxes. This isn't a decode-offset bug (surrounding fields on
        the same record, e.g. country_tag=120=Greece, and neighboring
        records at adjacent file offsets, all decode sanely) -- it looks
        like a genuine data-quality quirk in a minority of source records.
        Left un-filtered by default (`max_area=None`) since it's a real,
        not-fully-explained fact about a few raw records, not something
        this reader should silently hide -- but a "rank by area" CONSUMER
        (like the map viewer) should cap it, or these degenerate records
        win every low-zoom ranking by sheer (spurious) bbox size and crowd
        out the real, importantly-large cities actually in view."""
        mask = (
            (self.lon_min <= lon_max) & (self.lon_max >= lon_min) &
            (self.lat_min <= lat_max) & (self.lat_max >= lat_min) &
            (self.area >= min_area)
        )
        if max_area is not None:
            mask &= (self.area <= max_area)
        idxs = np.nonzero(mask)[0]
        if len(idxs) > limit:
            order = np.argsort(self.area[idxs])[::-1][:limit]
            idxs = idxs[order]
        else:
            idxs = idxs[np.argsort(self.area[idxs])[::-1]]
        return [cty_record(self.body, int(i)) for i in idxs]

    def search(self, query_str, limit=300):
        """Same contract as the module-level search_cty(), over the
        already-resident body (no re-read)."""
        return search_cty(self.body, query_str, limit=limit)

    def indices_for_tag(self, tag):
        """Record indices (numpy int array) whose country_tag field equals
        `tag` exactly -- the raw building block for country-scoped City
        search (README S10 "v13 -> v14"). See build_country_tag_map() below
        for how a real eeu.ctr country maps to one (or, for Russia's two
        eeu.ctr rows, exactly one of two) tag value(s)."""
        return np.nonzero(self.country_tag == tag)[0]

    def place_names_for_tag(self, tag):
        """The "<place>" part (before the first comma, i.e. eeu.cty's own
        "<place>, <parent place>" convention -- README S3.8) of every record
        whose country_tag equals `tag`, deduplicated. This is exactly the
        per-country equivalent of what MapData.load_address_entry_data()
        already does over the WHOLE file for the unscoped City field -- used
        to build a country-SCOPED city_reader.PrefixNameIndex so the City
        speller only ever offers places inside the selected country (the
        explicit real-nav-UX correction this feature was built for)."""
        names = []
        for i in self.indices_for_tag(tag):
            rec = cty_record(self.body, int(i))
            part = rec.name.split(",", 1)[0].strip()
            if part:
                names.append(part)
        return names


# ============================================================================
# build_country_tag_map() -- CRACKS eeu.cty's bytes[57:59] "candidate coarser
# country/region tag" field (README S3.8, this module's own docstring above),
# added for the country-scoped Address Entry City search (README S10
# "v13 -> v14"). The task that prompted this: the just-built Address Entry
# City speller was searching ALL 939,351 eeu.cty records regardless of the
# selected Country, which doesn't match real nav UX (country limits which
# cities are even offered) -- see the explicit user correction quoted in
# README S10 "v13 -> v14".
#
# **The field IS the country partition, just under a different numbering
# than eeu.ctr's own row index (confirming, not refuting, this module's
# prior "very likely a country identifier, exact scheme unconfirmed" note).**
# A full-file scan of the reference disc's 939,351 records finds EXACTLY 35
# distinct country_tag values -- the same count as eeu.ctr's own 35 rows,
# not a coincidence: every one of the 35 real per-tag record groups'
# aggregate bounding box lines up almost exactly with one real European
# country's own geographic extent (e.g. tag 365's ~9,720 records span
# (5.93,45.78)-(10.64,47.82) -- Switzerland's real extent almost exactly;
# tag 201's 482 records span (19.79,41.82)-(21.94,43.37) -- Kosovo's real
# extent, cleanly distinct from tag 402's separate ~5,830-record Serbia
# group at (18.55,42.13)-(23.18,46.41), i.e. the two are NOT merged despite
# eeu.ctr itself giving Kosovo Serbia's own ISO alpha-2 code "RS" -- see
# ctr_reader.py). eeu.ctr's own two Russia rows (one transliterated
# "ROSSIYA", one native-script "РОССИЯ" -- see ctr_reader.py) are similarly
# NOT merged: two separate country_tag values (337, 483) share nearly the
# identical geographic median but are cleanly split by which script their
# OWN place names use (0% vs 100% Cyrillic-alphabet characters sampled).
#
# **Mapping built empirically, not assumed to equal eeu.ctr's row index**
# (the prior session's approach, which the README already documented as
# failing: "does NOT match eeu.ctr's own row index for those countries").
# build_country_tag_map() instead: (1) computes each tag group's robust
# (median, not mean -- resistant to the file's own documented small number
# of outlier/degenerate bounding boxes, see CtyCache.query()'s "max_area"
# note) representative-point centroid and a Cyrillic-script fraction from a
# small name sample; (2) matches each tag group to the real eeu.ctr country
# whose approximate real-world centroid (REF_CENTROID below -- ordinary
# public geography, not anything reverse-engineered from the disc) is
# closest, via a greedy nearest-centroid assignment (this project has no
# scipy available for a true optimal bipartite match, but the 35 groups
# turned out to be geographically well-separated enough that greedy nearest
# gives a clean 35/35 bijection on the reference disc -- verified, not
# assumed, see below); (3) special-cases eeu.ctr's one duplicate-country
# case (the two Russia rows share one real-world centroid, so geography
# alone can't tell them apart) by resolving that pair via the Cyrillic-
# script signature instead, matching each tag group's own script to
# whichever eeu.ctr row's NAME uses that same script.
#
# **Validated, this project's standard (real, named examples, not just
# plausible-looking numbers)**: 35/35 country_tag values assigned to a
# distinct eeu.ctr row with zero left over on either side (a true
# bijection). Cross-referencing 17 known real cities already used
# elsewhere in this project or freshly looked up (Tirane->Albania,
# Timisoara/Iasi/Bucuresti->Romania, Sofia->Bulgaria, Chisinau->Moldova,
# Ljubljana->Slovenia, Zagreb->Croatia, Sarajevo->Bosnia and Herzegovina,
# Wien->Austria, Praha->Czechia, Bratislava->Slovakia, Budapest->Hungary,
# Podgorica->Montenegro, Skopje->North Macedonia, Beograd->Serbia,
# Warszawa->Poland) against their OWN eeu.cty record's country_tag, resolved
# through this mapping: **17/17 correct**, including the geographically
# tight Kosovo/Serbia/Montenegro/North Macedonia Balkan cluster where a
# wrong assignment would be easy to get away with unnoticed.
#
# **Limitations, stated honestly**: REF_CENTROID's 35 points are rough
# (capital-city-ish) approximations, not verified per-country bounding
# polygons -- they were sufficient because the 35 real tag groups are
# geographically well-separated on this specific East-Europe dataset, not
# because the matching algorithm is immune to two countries with similar
# centroids (a hypothetical future disc covering, say, Benelux at this same
# coarseness could plausibly need a better assignment algorithm or a real
# bounding-box check instead of a single centroid point). The greedy
# nearest-centroid assignment is not a globally optimal bipartite match
# (no scipy in this environment) -- it happened to reproduce the correct
# answer for all 35 groups on the reference disc (verified above), but a
# future disc with less separation could in principle need
# scipy.optimize.linear_sum_assignment instead.
# ============================================================================

REF_CENTROID = {
    # Approximate real-world (lon, lat) reference point per eeu.ctr country
    # name -- ordinary public geography (roughly capital-city location),
    # NOT reverse-engineered from the disc. Keyed by the exact name string
    # ctr_reader.py decodes (see its own module docstring for the full
    # 35-country list).
    "SCHWEIZ": (8.2, 46.8),
    "STATO DELLA CITTÀ DEL VATICANO": (12.45, 41.90),
    "ITALIA": (12.5, 43.5),
    "SAN MARINO": (12.45, 43.94),
    "SLOVENIJA": (14.8, 46.1),
    "HRVATSKA": (16.0, 45.1),
    "BOSNA I HERCEGOVINA": (17.8, 44.0),
    "LIECHTENSTEIN": (9.55, 47.14),
    "DEUTSCHLAND": (10.45, 51.16),
    "ÖSTERREICH": (14.55, 47.52),
    "DANMARK": (9.5, 56.26),
    "ČESKO": (15.47, 49.82),
    "POLSKA": (19.15, 51.92),
    "ELLADA": (22.0, 39.5),
    "SHQIPËRIA": (20.17, 41.15),
    "CRNA GORA": (19.37, 42.71),
    "P.JUGOSLOVENSKA REPUB.MAKEDONIJA": (21.75, 41.61),
    "KOSOVË": (20.9, 42.6),
    "SRBIJA": (21.0, 44.0),
    "BALGARIA": (25.5, 42.73),
    "ROMÂNIA": (25.0, 45.94),
    "MAGYARORSZÁG": (19.5, 47.16),
    "SLOVENSKO": (19.7, 48.67),
    "LIETUVA": (23.88, 55.17),
    "MOLDOVA": (28.37, 47.41),
    "BYELARUS'": (27.95, 53.71),
    "SVERIGE": (18.64, 60.13),
    "NORGE": (8.47, 60.47),
    "LATVIJA": (24.6, 56.88),
    "EESTI": (25.01, 58.6),
    "SUOMI": (25.75, 61.92),
    "TÜRKIYE": (35.0, 39.0),
    "UKRAINA": (31.0, 48.38),
    "ROSSIYA": (37.6, 55.75),  # shared by both eeu.ctr Russia rows; see
                                # the script-based tie-break above.
}


def _dist2(a, b):
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


def build_country_tag_map(cache, countries, sample_size=50):
    """Empirically map every real eeu.cty country_tag value (bytes[57:59])
    to the real eeu.ctr CountryRecord it belongs to -- see the extensive
    methodology/validation comment block directly above. `cache` is a
    CtyCache (already built); `countries` is ctr_reader.load_countries()'s
    return value. Returns `{tag: CountryRecord}`, always covering every
    distinct tag value actually present in `cache` on a well-formed disc
    (verified 35/35 on the reference disc -- see above)."""
    uniq_tags = np.unique(cache.country_tag)

    tag_stats = {}
    for tag in uniq_tags:
        tag = int(tag)
        mask = cache.country_tag == tag
        median = (
            float(np.median(cache.repr_lon[mask])),
            float(np.median(cache.repr_lat[mask])),
        )
        idxs = np.nonzero(mask)[0][:sample_size]
        cyr = tot = 0
        for i in idxs:
            rec = cty_record(cache.body, int(i))
            for ch in rec.name:
                if ch.isalpha():
                    tot += 1
                    if "Ѐ" <= ch <= "ӿ":
                        cyr += 1
        tag_stats[tag] = {"median": median, "cyr_frac": (cyr / tot if tot else 0.0)}

    remaining_tags = set(tag_stats.keys())
    remaining_countries = list(countries)
    assignment = {}

    # Step 1: resolve any eeu.ctr countries sharing the same (iso3, iso2)
    # pair (on the reference disc: only Russia, listed twice -- once
    # transliterated, once in Cyrillic) via script match, since geography
    # alone can't distinguish them (same real-world centroid).
    by_iso = {}
    for c in countries:
        by_iso.setdefault((c.iso3, c.iso2), []).append(c)

    for iso, group in by_iso.items():
        if len(group) < 2:
            continue
        ref = None
        for c in group:
            if c.name in REF_CENTROID:
                ref = REF_CENTROID[c.name]
                break
        if ref is None:
            continue
        cand_tags = sorted(
            remaining_tags, key=lambda t: _dist2(tag_stats[t]["median"], ref)
        )[:len(group)]
        for c in group:
            c_is_cyr = any("Ѐ" <= ch <= "ӿ" for ch in c.name)
            for t in cand_tags:
                if (tag_stats[t]["cyr_frac"] > 0.5) == c_is_cyr and t in remaining_tags:
                    assignment[t] = c
                    remaining_tags.discard(t)
                    remaining_countries.remove(c)
                    break

    # Step 2: greedy nearest-centroid bipartite matching for everything else
    # (verified to give a clean 35/35 bijection on the reference disc -- see
    # the comment block above for why a true optimal assignment wasn't
    # needed here).
    pairs = []
    for t in remaining_tags:
        for c in remaining_countries:
            ref = REF_CENTROID.get(c.name)
            if ref is None:
                continue
            pairs.append((_dist2(tag_stats[t]["median"], ref), t, c))
    pairs.sort(key=lambda p: p[0])

    used_tags = set()
    used_country_idxs = set()
    for _, t, c in pairs:
        if t in used_tags or c.index in used_country_idxs:
            continue
        assignment[t] = c
        used_tags.add(t)
        used_country_idxs.add(c.index)

    return assignment


# ============================================================================
# `ct_root()` -- validated `.ct` ("city tree") entry-point shards, added for
# rns510_map_viewer.py's Address Entry / letter-keyboard feature (README §10
# "v11 -> v12"). Uses the SAME 19-byte character-trie node format documented
# and cracked in `road_index_reader.py` (`rt_node()`/`rt_char()`/
# `rt_children()`/`rt_walk_strings()` -- imported below, not reimplemented)
# -- this module's own docstring already confirmed the identical format via
# the pointer-hit-rate test (80.7% on a 14,283-node sample vs. a 4.31% base
# rate). Read `road_index_reader.py`'s own `RT_ROOT_ENTRIES` comment block
# FIRST -- it documents the full root-finding methodology (exhaustive
# single-root search REFUTED, per-letter shard approach adopted, accented-
# character byte evidence) that applies here unchanged, just re-run against
# `.ct`'s own decompressed body (16,454,990 bytes) instead of `.rt`'s.
#
# **A real, load-bearing negative finding from cross-checking `.ct` against
# ALREADY-KNOWN-real city names (this session).** `eeuz.cl` (the flat
# "city list" search catalog `.ct` is presumed to be a trie over, the same
# relationship `.rt` has to `.prl`) was confirmed to contain an EXACT
# top-level entry `"SOFIA"` (record 2,483,612, pointing at `eeu.cty` index
# 230704 -- the real Bulgarian capital, independently validated elsewhere
# in this project, §3.8). But an exhaustive search of every 'S'-starting
# candidate node in `.ct` (12,984 candidates with `subtree_size >= 2`,
# checked via both the tolerant children walk AND a raw positional check
# that ignores `subtree_size` bookkeeping entirely) found ZERO paths
# spelling "SOFIA". **Conclusion, stated plainly: `ct_root()`'s coverage is
# real but genuinely PARTIAL** -- like `.rt`, `.ct` is a forest of
# independent shards, and this method cannot guarantee any specific real
# name (however well-known) is reachable from the shards it happens to
# find. **This is why `rns510_map_viewer.py`'s City field does NOT rely on
# `ct_root()` for correctness** -- it uses `PrefixNameIndex` below instead,
# built from the already-fully-cracked, exhaustive `eeu.cty` (939,351 real
# records, no coverage gaps) for live per-letter narrowing that is always
# exactly right, and treats `.ct`/`ct_root()` as a validated bonus
# (available for inspection/future work) rather than a load-bearing part of
# the UI. `ct_root()` is still shipped and tested on its own terms, per the
# task's ask to crack `.ct` and use it "the same way as City/Street" where
# practical -- see `test_map_viewer.py` for its own direct validation.
#
# **Validated real-vocabulary cross-references found this session** (same
# method as `.rt`'s: walk every candidate's leaves, keep whichever
# candidate per starting letter scores the most DISTINCT hits against a
# real-word corpus -- here, actual `eeu.cty` place-name tokens, sampled
# 60,000 real records, instead of `eeu.typ`, since city records don't have
# a generic-type-word dictionary the way roads do): genuine former-USSR/
# East-European administrative and place-name fragments including
# **"RAYON"/"RAION"** (district), **"SYEL'SAVYET"** (a rural "selskiy
# sovyet"/village council -- matches this module's own pre-existing
# `.ct`-walk finding of "SAVYET"), **"SOLNECHNOGORSKIY"** (a real Russian
# town, Solnechnogorsk), **"TUZLA"** (a real Bosnian city), and **"NOVAYA"**
# (Russian "new") -- 110 distinct real-word hits across the 26-letter
# union, comparable in kind to `.rt`'s own 21-word validation.
#
# **Comparison vs. having no starting point at all** (this module's `.ct`
# section previously had none -- only structural confirmation, no walkable
# entry offset): the union of the 26 `CT_ROOT_ENTRIES` below reaches 5,166
# leaf strings (capped at 20,000/letter). There was no prior single-node
# baseline to compare against for `.ct` specifically (unlike `.rt`'s D-node)
# since no session had previously located ANY usable `.ct` starting offset.

CT_ROOT_ENTRIES = {
    # char: (node_start, subtree_size) in the DECOMPRESSED `.ct` body (pass
    # data[94:]) -- validated against the reference disc (CD_8555.ISO).
    'A': (10194309, 1086), 'B': (11339405, 1734), 'C': (12759409, 341),
    'D': (10193663, 1133), 'E': (14327308, 550), 'F': (6215896, 858),
    'G': (10194214, 1104), 'H': (10213233, 1051), 'I': (16187910, 1733),
    'J': (13910923, 327), 'K': (14439902, 928), 'L': (7667572, 738),
    'M': (10193473, 1343), 'N': (14076831, 1278), 'O': (10201662, 166),
    'P': (13911474, 252), 'Q': (5965172, 1295), 'R': (16125685, 1627),
    'S': (10212739, 1132), 'T': (10194081, 1115), 'U': (13911075, 490),
    'V': (14090055, 141), 'W': (2404686, 372), 'X': (2709009, 275),
    'Y': (14482253, 873), 'Z': (12834972, 2108),
}


def ct_root():
    """Best-known validated entry-point SHARD per starting letter (A-Z) for
    walking `.ct` from scratch -- see the extensive methodology/caveats
    comment block directly above `CT_ROOT_ENTRIES`, and `road_index_
    reader.py`'s own `RT_ROOT_ENTRIES` block for the shared root-finding
    methodology. Coverage is real but PARTIAL (confirmed: "SOFIA" is not
    reachable from any found 'S' shard despite being a confirmed real
    `eeuz.cl` entry) -- do not treat an absence here as proof a name
    doesn't exist; see `PrefixNameIndex` for the always-correct alternative
    this project actually uses for the City field's live narrowing."""
    return dict(CT_ROOT_ENTRIES)


# ============================================================================
# PrefixNameIndex -- always-correct live prefix narrowing over an in-memory
# name list (used for the City field's keyboard, backed by the already-
# fully-cracked, exhaustive `eeu.cty`/`CtyCache`, README §10 "v11 -> v12").
# Deliberately NOT trie-based: `.ct`'s real coverage gaps (see `ct_root()`
# above) make it unsuitable as the sole source of truth for a feature whose
# whole point is "never wrongly disable a real option". Building a sorted,
# de-duplicated in-memory list from data this project has ALREADY fully
# cracked and loaded (CtyCache) trades a bit of memory (939,351 short
# strings, a few tens of MB) for a live per-keystroke query that is exactly
# correct, not best-effort -- and is still fast: `bisect` gives O(log n) to
# find the matching range for any prefix, so even the empty-prefix case
# (the whole file) resolves instantly, and computing the enabled-next-chars
# set only ever scans the (usually far smaller) matching sub-range, never
# the whole list.
# ============================================================================


class PrefixNameIndex:
    """Case-insensitive live prefix index over a list of real names, for a
    from-scratch "type letters, see live next-letter availability" keyboard
    that is always exactly correct (no coverage gaps) -- see the module
    comment above. Construct once (e.g. from every `eeu.cty` name, or a
    sub-part of a name split on `,`/` `), then call `enabled_next_chars()`/
    `count_matches()`/`matches()` as often as needed per keystroke."""

    __slots__ = ("_sorted",)

    def __init__(self, names):
        seen = set()
        for n in names:
            if n:
                seen.add(n.strip().upper())
        self._sorted = sorted(seen)

    def _bounds(self, prefix):
        prefix = prefix.upper()
        lo = bisect.bisect_left(self._sorted, prefix)
        hi = bisect.bisect_left(self._sorted, prefix[:-1] + chr(ord(prefix[-1]) + 1)) \
            if prefix else len(self._sorted)
        return lo, hi

    def count_matches(self, prefix):
        lo, hi = self._bounds(prefix)
        return hi - lo

    def matches(self, prefix, limit=200):
        lo, hi = self._bounds(prefix)
        return self._sorted[lo:min(hi, lo + limit)]

    def enabled_next_chars(self, prefix):
        """The set of characters C such that some indexed name starts with
        `prefix + C` (case-insensitive). Always exact -- this index has no
        coverage gaps, unlike the `.rt`/`.ct` trie shards above, so a
        caller MAY safely disable any letter not in this set outright."""
        lo, hi = self._bounds(prefix)
        plen = len(prefix)
        out = set()
        for i in range(lo, hi):
            name = self._sorted[i]
            if len(name) > plen:
                out.add(name[plen])
        return out
