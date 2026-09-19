"""
mod_reader.py -- decodes eeu.mod, CRACKED this session: this is the
single most valuable file examined in the whole project. It is the
disc's own FULL DATABASE SCHEMA / DATA DICTIONARY -- a serialized
description, authored by the original build tool ("Arriba", version
"5.3" -- the literal first two strings in the file, almost certainly the
real internal name of Navteq/Siemens/Continental's own database-
compilation toolkit), of every table and every field in every other file
on this disc, in order, terminated by that file's own short extension
("abc", "ctr", "cty", "rd", ... one marker per real on-disc file).
Previously entirely unexamined -- only a candidate record size had been
derived from the shared header fields, and that candidate (this file is
NOT fixed-record, see below) was correctly flagged as not applicable.

============================================================================
Container
============================================================================
Standard 94-byte SIEMENS NOT_COMPRESSED header (own bytes[86:88]
"record_count_lo16" field is 0 here -- correctly signaling this is NOT a
fixed-record file, same as eeu.il). Body: 40,929 bytes on the reference
disc, a dense run of NUL-terminated ASCII strings (table names, field
names, and short file-extension markers) interleaved with short runs of
binary bytes whose EXACT per-field type/width encoding was NOT fully
reverse-engineered this session (see "What's not cracked" below) -- but
the STRING CONTENT ALONE, extracted with a simple "printable-ASCII-run-
terminated-by-NUL" scan, is already a complete, clean, unambiguous win:
scanning the whole body this way finds exactly 1,605 strings, and every
one of the 36 expected short file-extension tokens (`abc`, `ctr`, `stt`,
`cny`, `cty`, `rd`, `typ`, `aff`, `mp0`/`mg1`-`mg4`/`mpa`/`mpb` (one
shared block), `si`, `fea`, `cal`, `ct`, `cl`, `rt`, `rl`, `prl`, `pot`,
`pol`, `pmm`, `pmc`, `pmp`, `ti`, `iof`, `il`, `tmc`, `cat`, `pca`, `pct`,
`prd`) appears, in the SAME order this project independently discovered/
confirmed those files' own real-world identities in -- itself strong
corroboration this extraction is correct, not coincidental.

============================================================================
The table -> file mapping (every block, in file order)
============================================================================
Each block's first string is that table's own internal name; its last
short token (3-4 lowercase letters, occasionally with digits) is the real
on-disc file extension its data is stored under. `extract_blocks()`
returns exactly this structure.

  Arriba/... (used-character-set + language table)      -> eeu.abc
  country/...                                            -> eeu.ctr
  state/...                                               -> eeu.stt
  county/...                                              -> eeu.cny
  city/...                                                -> eeu.cty
  road/...                                                -> eeu.rd
  rtype/...                                               -> eeu.typ
  affix/...                                               -> eeu.aff
  "Ordinary Map File"/... (huge: parcels/segments/nodes/  -> eeuz.mp0,
    shapes/turn restrictions/lanes/ADAS+truck speed          .mg1-.mg4,
    limits/intersection+junction views/traffic signs/...)    (+mpa/mpb,
                                                                not present
                                                                as real
                                                                files here)
  seginfo/...                                             -> eeu.si
  feature/...                                             -> eeuz.fea
  catalogList/...                                         -> eeu.cal
  cityTree/...                                            -> eeuz.ct
  cityList/...                                            -> eeuz.cl
  roadTree/...                                            -> eeuz.rt
  roadList/...                                            -> eeuz.rl
  roadListNames/...                                       -> eeuz.prl
  postalcodeTree/...                                      -> eeu.pot
  postalcodeList/...                                      -> eeu.pol
  postalcodeListSeparate/...                              -> eeu.pmm
  postalcodeListMergeCity/...                             -> eeu.pmc
  postalcodeListMergePostalcode/...                       -> eeu.pmp
  timeinfo/...                                            -> eeu.ti
  intersectionOffsetFile/...                              -> eeu.iof
  intersectionListFile/...                                -> eeu.il
  "tmc file"/...                                          -> eeu.tmc
  catalog/...                                             -> eeu.cat
  phCatalog/...                                           -> eeuz.pca
  phCity/...                                               -> eeuz.pct
  phRoad/...                                               -> eeuz.prd

`eeu.pcl` has no corresponding block -- its real purpose is still
unknown (it's one of the four always-empty 94-byte stub files on this
disc, along with `.pmp`/`.pol`/`.pot`, which DO appear here with real
field lists despite being empty on this specific disc -- `.pcl` being
absent from the schema entirely, not just empty, is a genuinely different
situation, not yet explained).

============================================================================
Confirmed corrections and extensions to already-cracked files, this
session
============================================================================
Cross-referencing this schema against work already done elsewhere in
`research/` immediately resolved several previously-open questions:

  - **`eeuz.pct` (pct_reader.py) -- the "group" field mystery is SOLVED.**
    `phCity`'s own real fields end `.../phonemeRoadOffset/phonemeRoadCount`
    -- i.e. the 6-byte trailer this project's own last session left
    uncracked is `[uint32 LE offset][uint16 LE count]` into `eeuz.prd`,
    NOT a language-variant "group id" as first guessed (both readings
    happened to look identical because multi-language name variants of
    the SAME real city correctly share the SAME "this city's own roads"
    pointer). **Validated directly, not just plausible-sounding**: Venice's
    group (`744f180bf414`) points into `eeuz.prd` right next to real
    Adriatic ferry-route entries `VENEZIA-CORFÙ` and `VENEZIA-PATRASSO`;
    Vatican City's group lands among real Italian streets (`VIA ARIANO
    IRPINO`, `VIA SORRENTO`); Munich's lands at a real Munich square
    (`LEONRODPLATZ`); Frankfurt's lands among real Frankfurt streets
    (`MANNHEIMER STRASSE`, `DÜSSELDORFER STRASSE`). The exact byte-level
    anchor (whether `offset` is a raw absolute file position or needs a
    small fixed adjustment) wasn't pinned down to the last byte -- the
    landing point is sometimes a handful of bytes before a clean record
    boundary rather than exactly on one -- but the overall mechanism is
    no longer in doubt.
  - **`eeu.ctr` (README S3.11-adjacent)'s 2 "trailing zero bytes"** are
    named: `speedUnit` and `drivingSide` (both zero-valued for every
    country on this disc -- plausibly unused/not-yet-populated fields
    for this product, not evidence against the identification).
  - **`eeuz.rl` (README S3.7)'s previously-unresolved trailing flag byte
    and always-zero `bytes[4:7]`** are named `hasHouseNumbers` and a
    packed `minNumber`/`maxNumber` house-number range -- consistent with
    the flag's own already-measured 71%/29% split and the range bytes'
    always-zero content (no house-number data populated on this disc).
  - **`eeu.il` (README S3.2)'s 7 still-unresolved prefix bytes** include a
    named `vnodeID` field -- a real, disc-confirmed "virtual node id"
    reference. This is a genuinely promising, NOT YET PURSUED lead for
    the long-standing topology node-id<->coordinate mapping problem
    (`map_compressed_reader.py`'s `resolve_topology_adjacency()`) --
    `vnodeID` might be the same node-numbering space the tile topology
    table's own node-ids live in, since the "Ordinary Map File" block's
    own segment records (see below) also reference `left_node`/
    `right_node` fields directly. Not tested this session.
  - **`eeu.cal` (cal_reader.py)'s always-`0xFFFFFFFF` trailer** is named
    `cityTreeOffset`/`postalcodeTreeOffset` (2x uint16, both the `0xFFFF`
    "unset" sentinel for every country/continent entry -- consistent with
    country-level catalog entries never needing their own city-tree/
    postalcode-tree sub-index).
  - **`eeu.cny` (cny_reader.py) is actually the "county" table, and
    `eeu.cal`/`region_id` are wrong names for 2 of its own fields** --
    see cny_reader.py's own updated docstring for the full correction:
    the file's `index`/`f2` fields are really `countyID`/`stateID`, and
    `eeu.stt` (still unexamined) is the real "state" table `stateID`
    refers to, not `eeu.cny` itself.
  - **The "Ordinary Map File" block is the MAP_COMPRESSED tile schema**
    (`eeuz.mp0`/`.mg1`-`.mg4`, `map_compressed_reader.py`) and is easily
    the largest single block (615 field names) -- covering parcels,
    k-d tree nodes, segments (`seg`, `seginfoID`, `restr_left`/
    `restr_right`, `left_node`/`right_node`, `length`), shapes, turn
    restrictions, ADAS/truck speed limits, lane connectivity, and more.
    **`left_node`/`right_node` on a segment record is a strong,
    NOT YET PURSUED lead for finally closing the topology node-id<->
    coordinate mapping gap** (`resolve_topology_adjacency()`'s own
    docstring) -- this session did not attempt cross-referencing it
    against the tile format's own still-partially-cracked "tagged record
    table", given the scope of that undertaking on its own.
  - **`eeu.si` is named `seginfo`** with real fields `rank`, `class`,
    `divided`, `drivables`, `toll_vignette`, `toll_road`, `restclass`,
    `urban`, `route_num_type`, `paved`, ... -- a genuine ROAD
    CLASSIFICATION table. This is a strong, NOT YET PURSUED lead for
    `eeu.rd`'s own long-unresolved `bytes[1:5]` "candidate road-class
    flags" (README S3.1) -- `eeu.si` was not opened or decoded this
    session; only its schema-declared identity is established here.

============================================================================
What's NOT cracked
============================================================================
The exact BINARY encoding surrounding each field name (the bytes between
consecutive NUL-terminated strings) was not fully reverse-engineered --
hand inspection strongly suggests a `[type/flag][size][size][...]`-style
per-field descriptor (many fields sharing an identical trailing pattern,
e.g. `stamp`/`copyright`/`db_release`/`db_version`/`comp_version` all
show the same `ffff 10000000 10000000 1000 1000 0100` tail, consistent
with 5 identically-shaped fixed 16-byte string fields), but a complete,
general parser for arbitrary fields (arrays vs. scalars, exact byte
widths, the meaning of the `0xffff` vs `0x0000` "type" marker) was not
built this session. `extract_blocks()` below only needs the string
content, not this deeper encoding, to deliver the (already very high)
value documented above -- a natural next step for a future session.

============================================================================
Practical use
============================================================================
`extract_blocks(path)` returns the list of (file_extension_tokens,
field_names) tuples described above, in file order -- the whole schema,
ready to cross-reference against any other file's own reverse-engineering
effort.
"""

import re

HEADER_SIZE = 94

# Every real on-disc file extension token this schema is known to define
# a block for, used to split the flat string stream into per-table blocks.
KNOWN_EXTENSIONS = frozenset({
    "abc", "ctr", "stt", "cny", "cty", "rd", "typ", "aff",
    "mp0", "mg1", "mg2", "mg3", "mg4", "mpa", "mpb",
    "si", "fea", "cal", "ct", "cl", "rt", "rl", "prl",
    "pot", "pol", "pmm", "pmc", "pmp", "ti", "iof", "il",
    "tmc", "cat", "pca", "pct", "prd",
})

# The "Ordinary Map File" block documents 7 related extensions together
# (mp0/mg1-mg4 are real files on this disc; mpa/mpb are not, but are
# still part of the same schema block).
_MAP_TOKEN_GROUP = {"mp0", "mg1", "mg2", "mg3", "mg4", "mpa", "mpb"}


def extract_strings(path):
    """Every NUL-terminated printable-ASCII run (length >= 2) in the
    file's body, in file order -- table names, field names, and the
    short file-extension markers, all mixed together (this function does
    not separate them; see extract_blocks() for that)."""
    with open(path, "rb") as f:
        data = f.read()
    body = data[HEADER_SIZE:]
    return [m.group()[:-1].decode("ascii")
            for m in re.finditer(rb"[ -~]{2,}\x00", body)]


def extract_blocks(path):
    """Split the file's full string stream into (extension_tokens,
    field_names) blocks -- one per real table, in file order.
    `extension_tokens` is normally a single-element list (e.g. `["ctr"]`);
    for the MAP_COMPRESSED tile schema it's the 7-element group
    `["mp0","mg1","mg2","mg3","mg4","mpa","mpb"]`. `field_names` is every
    string from just after the previous block's own extension marker up
    to (not including) this block's own marker -- the first entry is
    always that table's own internal name (e.g. `"country"` for the
    `ctr` block)."""
    strings = extract_strings(path)
    blocks = []
    prev_end = 0
    i = 0
    while i < len(strings):
        tok = strings[i]
        if tok not in KNOWN_EXTENSIONS:
            i += 1
            continue
        if tok in _MAP_TOKEN_GROUP:
            group = []
            while i < len(strings) and strings[i] in _MAP_TOKEN_GROUP:
                group.append(strings[i])
                i += 1
            blocks.append((group, strings[prev_end:i - len(group)]))
            prev_end = i
            continue
        blocks.append(([tok], strings[prev_end:i]))
        prev_end = i + 1
        i += 1
    return blocks
