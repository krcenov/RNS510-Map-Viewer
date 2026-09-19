"""
tpd_reader.py -- documents `tpd/` (disc root, not under `db/`), by far
the largest never-examined area on the disc: 1,443 files. CRACKED at
the "what is this system and how does it work" level -- every distinct
FILE ROLE identified and confirmed with real content; the per-country
`.IDX`/`.URL` search-table BODIES (compressed, self-describing headers
decoded) were not decompressed/decoded further.

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
The compressed table BODY (past the header) was not decompressed or
decoded this session.

============================================================================
Root-level `tpd/` files -- NOT decoded
============================================================================
`TPD3.DIC` (a dictionary file, presumably word/phrase lookup for the
search UI -- not opened) and `LPOI.TXT` (a version-stamp file, content
confirmed to be exactly `2019060000`, matching `INFO25.PSC`'s own
`TPD-PRODID` -- nothing more decoded).

============================================================================
Practical use
============================================================================
This module has no parsing functions -- every file format documented
here is either plain text (`.PSC`/`.LSC`/`.HTM`/`.TXT`, read directly)
or a standard image format (`.png`/`.gif`, use any image library). The
`.IDX` compressed table bodies were not decoded; no reader is provided
for them.
"""
