"""
tpd_reader.py -- documents `tpd/` (disc root, not under `db/`), by far
the largest never-examined area on the disc: 1,443 files. CRACKED at
the "what is this system and how does it work" level -- every distinct
FILE ROLE identified and confirmed with real content, including a LATER
session opening `TPD3.DIC` (previously assumed a binary dictionary,
actually a tiny plain-text 3rd product manifest). The per-country `.IDX`
search tables' self-describing headers were already decoded; a LATER
session additionally cracked the per-block `(offset, lambda_hash)` index
table sitting between the header and the data (previously assumed to
just be part of "the compressed body") -- the compressed block BODIES
themselves remain unidentified (tested and refuted as standard zlib/
deflate/gzip/bz2, despite the file's own `compr-type=Z` label).

Found via `config/create_cd` (research/create_cd_reader.py).

============================================================================
What TPD is -- CRACKED, confirmed directly from its own self-
documenting config file
============================================================================
`nscWeu_eue_20190607/INFO25.PSC` is plain, real, human-readable text:

    # Product Specific Contents file
    # (c) Continental Automotive GmbH, 2019
    TPD-PRODID      2019060000
    TPD-PRO         MAP_TPD_NT
    TPD-CNTRY       AL,AT,BA,BG,BY,CH,CZ,DE,DK,EE,FI,GR,HR,HU,IT,KO,LI,
                     LT,LV,MD,CS,MK,NO,PL,RO,RU,SE,SI,SK,SM,TR,UA,VA
    TPD-LAN         1 2 3 4 5 6 15 20
    TPD-LSC         1  /DUT/DUT.LSC   2  /ENG/ENG.LSC   3  /FRE/FRE.LSC
                    4  /GER/GER.LSC   5  /ITA/ITA.LSC   6  /SPA/SPA.LSC
                    15 /POR/POR.LSC   20 /CZE/CZE.LSC
    TPD-ATTRIB-TYPES  BRANDNAME=S?CITY=S?COUNTRY=S?ENTP=P?FAX=S?
                       HOUSENUMBER=S?IMPORTANCE=S?LPG=S?NAME=S?PHONE=S?
                       POSTAL_CODE=S?POSWGS=P?STREET=S?VILLAGE=S
    LPOIPRO         Y

"TPD" = a real POI/destination-search product config ("Traffic Product
Data" or similar -- the exact expansion isn't stated, but its role is
unambiguous from context). `TPD-PRODID 2019060000` matches
`LPOI.TXT`'s own content exactly, and matches `cdrom.toc`'s own `TPD:
2019060000` line exactly (research/create_cd_reader.py) -- the same
build stamp confirmed 3 independent ways. `TPD-CNTRY` lists the SAME 33
countries already found via `eeu.cal`/`eeu.ctr` (README S3.13/S3.11-
adjacent). `LPOIPRO Y` ("Leveled POI Product") ties this system to the
same "Leveled POI" concept `EDB/POI/POI.DB3`'s own metadata names
(research/poi_db_reader.py) -- plausibly the SAME underlying POI data,
surfaced through two different subsystems (a lightweight embedded-HTML
search UI here, a full SQLite database there), not confirmed directly.

============================================================================
The HTML "browser" destination-search UI -- CRACKED, confirmed by real
content
============================================================================
Each of the 8 language folders (`CZE`/`DUT`/`ENG`/`FRE`/`GER`/`ITA`/
`POR`/`SPA`) holds an IDENTICAL 122-file set (verified: sorted,
language-code-normalized filenames hash identically across all 8
folders) of real HTML files. Every one starts with a machine-readable
comment identifying its own role:

    <!--TPD TYPE="2" LAN=ENG FORMID=11000-->   (a "SF_" search-FORM file)
    <!--TPD TYPE=3   LAN=ENG-->                 (an "ST_" search-RESULTS template)
    <!--TPD TYPE="4" LAN=ENG-->                 (CATTEMPLATE.HTM, the category picker)

`SF_<FORMID>.HTM` (a search-criteria form, e.g. `SF_11000.HTM`,
FORMID matches the filename number exactly) is real, functional HTML
submitting to `http://tpdhost/cgi/search` -- **the head unit runs (or
emulates) a local embedded web server** (`tpdhost`) with a CGI-style
handler, and destination search is implemented as rendered HTML forms,
not a native compiled UI screen. Confirmed real example (`SF_11000.HTM`,
"Airports"): a radius selector (5-500 units) and a "part of name" text
filter, referencing `/TABLES/0/0001.IDX` + `/TABLES/0/0002.URL` as its
own search index, and a companion results template `/ENG/ST_11000.HTM`.
Template placeholders (`##u`=unit, `##p`=position, `##c`, `##h`=heading)
and a real conditional/substitution template language (`<%if_defined
CITYNAME>...<%CITYNAME>...<%endif>`, `<%unit>`) are both used
throughout.

`ST_<FORMID>.HTM` (the matching results page, 60 files, one per SF_
form minus a few shared ones) links back to its own `SF_` form (`<A
HREF="http://tpdhost/cgi/form?templ=/ENG/SF_11000.HTM&...">`), shows
paged results (`<%if_previous>`/`<%if_result>`/`<%INDEX_FIRST>`-
`<%INDEX_LAST>`), and references real icon images (`/IMAGES/
vw_search.gif`, `/IMAGES/vw_prev.gif`).

`CATTEMPLATE.HTM` (1 per language) is the category-picker screen: a
`<select name="CAT">` populated at runtime ("Options will be inserted
by the software") submitting to `http://tpdhost/cgi/StartTPD`.

`<LAN>.LSC`/`<LAN>_EXT.LSC` ("Language Specific Contents", 1 pair per
language) are plain, self-documenting text -- real examples from
`ENG.LSC`: `TPD-CT /ENG/CATTEMPLATE.HTM` (the category template path),
`TPD-PETROL-STATIONS 7311` (a specific real category ID for petrol/gas
stations -- note `SF_7311.HTM` exists in every language folder,
confirming this exact category<->form linkage), and a real
**category-group hierarchy**: `TPD-GRP <group-id> <child category/
group ids>` -- e.g. `TPD-GRP 0 20 22 23 24` (top-level group 0 contains
groups/categories 20/22/23/24), `TPD-GRP 20 10004 10006 10008 10009
10012` (group 20 contains 5 real leaf categories) -- this is the real
tree structure feeding `CATTEMPLATE.HTM`'s own dropdown. Plausibly
related to (not confirmed identical to) `EDB/POI/POI.DB3`'s own
`Category_BaseAttributes`/`Category_ParentCategory_Relation` tables (79
categories, 326 parent-child relations, research/poi_db_reader.py) --
not cross-checked this session.

============================================================================
Icons and images -- CRACKED (standard formats, real content)
============================================================================
`ICONS/` (187 files) and `ICONS810/` (194 files, plausibly an
alternate-resolution/screen-width variant, "810" unconfirmed) are
standard PNG images (confirmed via `file`: e.g. `ACCOMMODATIONS.png`,
34x39, 8-bit RGBA) with real, self-explanatory POI-category names
(`AIRPORT`, `ALL_RESTAURANTS`, `AMERICAN`, `AMUSEMENT_PARKS`, `APPAREL`,
`ASIAN`, `ATM_EUR`, `ATM_US`, ...) -- real category icons, matching the
`TPD-GRP` hierarchy's own leaf categories. `IMAGES/` (22 files) holds UI
chrome (`vw_search.gif`, `vw_prev.gif`, ... -- GIF format) referenced
directly from the `ST_*.HTM` templates above.

============================================================================
`TABLES/` -- search index tables: CRACKED (self-describing header),
compressed body NOT decoded
============================================================================
`TABLES/GENERIC.IDX`/`GENERIC.URL` plus `TABLES/0/<NNNN>.IDX` (60 real
numbered index files, referenced directly by the `SF_*.HTM` forms
above). Each `.IDX` file's own header is plain, self-documenting ASCII:

    block-offset=428?compr-max-size=1860?compr-type=Z?order-type=lambda?
    table-type=G?uncompr-max-size=3012
    ID:A:6|POS:P:8|NAME:V:84|LKI:B:1|PHONE:V:19|IMPORTANCE:B:...

-- a real, named, TYPED schema for a zlib-compressed (`compr-type=Z`)
block-based table (`block-offset`/`compr-max-size`/`uncompr-max-size`,
the same block-packing convention as this disc's own FLAT_COMPRESSED
files, research/flat_compressed_reader.py -- a different container,
same design idiom), with fields `ID` (type `A`, 6 bytes), `POS` (type
`P`, 8 bytes -- plausibly a packed position, not confirmed: a direct
"2x int32 lon/lat" split tested against `EDB/POI/POI.DB3`'s own still-
uncracked 64-bit `Coordinate` field produced no plausible degree values
in either byte order, so this specific hypothesis doesn't resolve that
field either), `NAME` (type `V`=variable, up to 84 bytes), `LKI` (type
`B`=byte/boolean, 1 byte), `PHONE` (type `V`, up to 19 bytes),
`IMPORTANCE` (type `B`). This is structurally the SAME kind of POI
record schema as `EDB/POI/POI.DB3`'s own `Poi_BaseAttributes`/
`Poi_AddressAttributes` tables (ID + position + name + phone,
research/poi_db_reader.py) -- plausibly a lighter-weight, embedded-
search-optimized parallel representation of similar underlying data.

**A LATER SESSION: the region right after the 2-line header, previously
assumed to just be "the compressed body", is actually a real per-block
`(offset, lambda_hash)` index table -- CRACKED (structurally). The
actual compressed block BODIES remain an unidentified format -- TESTED
and REFUTED as standard zlib/deflate/gzip/bz2, despite the `compr-type=Z`
label.**

Right after the 2 header lines (ending `\r\n`), both a small per-form
table (`TABLES/0/0001.IDX`, 37,504 bytes, 30 entries) and the much
larger merged `TABLES/GENERIC.IDX` (136,913,204 bytes, 92,006 entries)
show the SAME repeating 9-byte record shape: `[4-byte big-endian
uint32][4-byte big-endian uint32]['|' (0x7C) delimiter]`, running for
exactly as many records as the table needs, then a `___\r\n` terminator
(3 underscores) before whatever follows.

**Both fields are monotonically non-decreasing across every record,
confirmed on real data**: field A (`0001.IDX`: 0, 896, 2584, 3580,
5204, ..., 35984 -- 30 values, strictly increasing) is consistent with
a cumulative byte offset of some kind (its final value, 35,984, is close
to this small file's own remaining body size past the header/table,
37,504-434=37,070, not close to the much larger fully-uncompressed size
30 blocks at `uncompr-max-size` would imply -- suggesting these are
COMPRESSED byte offsets, not uncompressed ones). Field B (`0001.IDX`:
59946290, 84824411, 102162240, ..., 1547972188 -- also strictly
increasing, spanning a large fraction of the full uint32 range) is
consistent with the header's own `order-type=lambda`: a per-block
lambda/hash boundary value, sorted ascending, letting a real client
BINARY-SEARCH this table for a query's own hash to find which single
block might contain it, without decompressing every block in order --
exactly the kind of structure a real "browse an area's street/POI
names" search index needs. `GENERIC.IDX`'s own much larger version of
this same table (92,006 records) shows the identical shape and the same
monotonic-in-both-fields property, and field A's own final value
(~136M) is in the right ballpark for that file's own much larger total
size (136.9MB) -- the same pattern at a different scale, not a
coincidence specific to the small file.

**Tested and REFUTED: the block bodies are NOT standard zlib (RFC1950),
NOT raw DEFLATE (RFC1951), NOT gzip, NOT bz2.** On the small, fully
scanned `0001.IDX` file: every byte position past the offset table
(every possible starting byte, not just the position the table's own
field-A offsets point to) was tested for a valid zlib header-and-stream,
a valid raw-deflate stream (no header), a gzip magic (`1F 8B`), and a
bz2 magic (`BZh`) -- zero real hits in any of these (one coincidental
2-byte gzip-magic-shaped match exists in the file by chance, but does
not lead to a real gzip stream). The declared `compr-type=Z` therefore
names a real but still UNIDENTIFIED proprietary compression or encoding
scheme, not any of the standard library formats already used elsewhere
on this disc (FLAT_COMPRESSED/MAP_COMPRESSED both use plain zlib) --
left open for a future session (candidates not yet tried: LZO, a custom
Siemens/Continental scheme, or a non-byte-aligned/bit-packed encoding
that wouldn't present a recognizable byte-aligned magic at all).

============================================================================
Root-level `tpd/` files -- `TPD3.DIC` opened and CRACKED (a LATER
session; despite the name, NOT a word/phrase dictionary), `LPOI.TXT`'s
version stamp already confirmed
============================================================================
`TPD3.DIC` (disc-root `tpd/TPD3.DIC`, not under a language/product
folder) is tiny -- 60 bytes -- and turns out to be plain text, not a
binary dictionary as its name/extension first suggested:

    TPD-DBID	2019060000
    TPD-UPI	eue_0	25	/nscWeu_eue_20190607 D

A 3rd, disc-root-level product manifest, one directory level ABOVE
`INFO25.PSC`/`LPOI.TXT` (which live inside `nscWeu_eue_20190607/`
itself) -- this is the file that tells the search UI WHICH product
subfolder(s) exist at all. `TPD-DBID 2019060000` is the SAME build
stamp already confirmed 3 ways (`INFO25.PSC`'s `TPD-PRODID`, `LPOI.TXT`,
`cdrom.toc`'s own `TPD:` line) -- now a 4th independent confirmation.
`TPD-UPI` ("Update Package Info", by the obvious reading of the name,
not independently confirmed) names the one real product instance on
this disc: `eue_0` (a product code -- "eue" matches this dataset's own
`nscWeu_EUE` naming, `_0` not otherwise explained), the real relative
path `/nscWeu_eue_20190607` (byte-exact match to the real directory on
disc), and a trailing `D` flag (plausibly "Directory"/"Data", not
confirmed). The middle field, `25`, was tested against every other
count already known for this disc and does NOT match: not
`TPD-CNTRY`'s 33 countries, not `TPD-LAN`'s 8 languages, not any
language code in `TPD-LAN`/`TPD-LSC` (`1 2 3 4 5 6 15 20`) -- real,
unexplained. Since a disc could in principle ship more than one `TPD-UPI`
line (one per product update package), `TPD3.DIC`'s own real ROLE is a
short manifest of which packages exist -- this disc only has the one.

`LPOI.TXT` (a version-stamp file under `nscWeu_eue_20190607/`, content
confirmed to be exactly `2019060000`, matching `INFO25.PSC`'s own
`TPD-PRODID` -- nothing more decoded).

============================================================================
Practical use
============================================================================
Most file formats documented here are either plain text (`.PSC`/`.LSC`/
`.HTM`/`.TXT`, read directly) or a standard image format (`.png`/`.gif`,
use any image library) -- no parsing function needed. `read_idx_header()`
below parses an `.IDX` file's 2-line text header plus its per-block
`(offset, lambda_hash)` index table (CRACKED, see above) -- the
compressed block BODIES themselves are NOT decoded (unidentified
compression scheme, see above), so this only gets you the table of
`(block_offset, lambda_hash)` pairs, not the actual POI records inside
each block.
"""

import struct


def read_idx_header(path):
    """Parse one `.IDX` file's 2-line text header (the `block-offset=...`
    config line and the `ID:A:6|POS:P:8|...` field-schema line) plus its
    per-block `(offset, lambda_hash)` index table -- see this module's
    docstring, "the region right after the 2-line header... is actually a
    real per-block (offset, lambda_hash) index table". Returns a dict:
    {"config": {...}, "schema": [(field_name, type_code, size_str), ...],
    "blocks": [(offset, lambda_hash), ...], "table_end": int}. Does NOT
    decode the compressed block bodies themselves (unidentified format,
    tested and refuted as zlib/deflate/gzip/bz2 -- see docstring)."""
    with open(path, "rb") as f:
        data = f.read()
    line1_end = data.find(b"\r\n")
    line2_end = data.find(b"\r\n", line1_end + 2)
    config = {}
    for kv in data[:line1_end].split(b"?"):
        k, _, v = kv.partition(b"=")
        config[k.decode("ascii")] = v.decode("ascii")
    schema = []
    for field in data[line1_end + 2:line2_end].split(b"|"):
        parts = field.split(b":")
        schema.append(tuple(p.decode("ascii", errors="replace") for p in parts))
    pos = line2_end + 2
    blocks = []
    while pos + 9 <= len(data):
        a, b = struct.unpack_from(">II", data, pos)
        if data[pos + 8] != 0x7C:
            break
        blocks.append((a, b))
        pos += 9
    return {"config": config, "schema": schema, "blocks": blocks, "table_end": pos}
