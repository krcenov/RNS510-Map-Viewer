"""
poi_db_reader.py -- documents `EDB/POI/POI.DB3` (disc root, NOT under
`db/`), CRACKED: a real, populated, standard SQLite database (open
directly with any SQLite client/library -- no proprietary container,
unlike everything under `db/`), AND (a LATER session) its own
`Coordinate` field -- a 64-bit Morton/Z-order code, decoded and
validated at real bulk scale (99.9% of 10,000 real POIs across 5 cities
land inside their own correct real-world bbox) -- see `decode_coordinate()`
and the dedicated section below. Its existence was already predicted by
this project's own firmware investigation (README S2.5: `vdo.nav.api.
edb.*` is a JDBC-like client to an embedded SQLite engine, and "POI
databases (`.db3` files under `EDB/POI/`, matches the map disc's own
`EDB\\POI` folder)" was already noted as the confirmed real use) -- this
is the first session with direct access to the actual disc content to
open it and confirm that prediction against real data.

Found via `config/create_cd` (research/create_cd_reader.py), the disc's
own build script -- its `cd EDB / mkdir POI / cd POI / cp ... POI.DB3`
lines are what led here.

============================================================================
Real content -- CONFIRMED, not hypothesized
============================================================================
20 real tables. The 2 largest:

    Poi_BaseAttributes           4,733,183 rows
      (Poi_ID, PoiPartition_ID, Coordinate, Name_String_ID, Name, PhoneNumber)
    Poi_AddressAttributes        4,614,762 rows
      (Poi_ID, HouseNumber_String_ID, Street_String_ID, Village_String_ID,
       City_String_ID, Region_String_ID, Country_String_ID,
       IsoCountry_String_ID, PhoneNumber_String_ID)
    String_BaseAttributes        5,091,214 rows  (String_ID, Value)
    String_TranslationString_Relation  496,452 rows
    Poi_Relation                   865,543 rows  (Poi_ID, RelationType, Related_Poi_ID)

-- a genuinely large, real Points-of-Interest database: 4.7 MILLION
real POIs, each with a name, coordinate, and (for most) a full address
(house number/street/city/region/country, each as a foreign key into
the shared `String_BaseAttributes` string pool, not inline text -- the
same dedup-by-string-id pattern used elsewhere on this disc, e.g.
`eeuz.prl`).

`DatabaseAttribute` (18 rows) is a real, human-readable metadata table:
`database.id = "EDB_20190607"`, `database.DateCreatedIso = "2019-06-07"`,
`database.CountPoi = "4614762"` (matches `Poi_AddressAttributes`'s own
row count exactly), `schema.poi = "2.07"`. One row's own `Value` field
(`PredefinedStatementBuild.ConfigSpec`) is a literal ClearCase
config-spec listing real internal source-control element paths --
confirms the real internal codebase name `arriba2`/`arriba2_VW`
(`/siemens/source/navicore/tools/predefstmt/...`) and a Java Swing
internal authoring tool (`vdo/nav/nursery/location/swinghmi/
MainUI.java`) -- `vdo` (Siemens VDO) is the same root Java package
namespace already found in the firmware's own `vdo.nav.api.edb.*`
strings (README S2.5), now independently confirmed from the OTHER side
(the tool that built this very database, not just the firmware that
reads it).

**`Category_BaseAttributes` (79 rows) confirms this POI database is
shared across the WHOLE VW Group brand family, not VW alone**: real
category names include `"main seat"`, `"main skoda"`, `"main vw"`,
`"main bentley"`, `"car and travel vw"`, `"car and travel seat"`, etc. --
brand-specific category sets for SEAT, Škoda, Volkswagen, and Bentley
all built from the same underlying POI data.

**Real, immediately-recognizable POI names, confirmed**: sampling
`Poi_BaseAttributes.Name` (populated for a minority of rows -- most POIs
carry their name only via the `Name_String_ID` -> `String_BaseAttributes`
join instead) finds real European fuel-station brands: `Q8`, `ENI`,
`TAMOIL`, `ESSO`, `IP` -- all genuine, well-known European petroleum
retailers, consistent with `PoiPartition_ID=1`/category `"gas station"`
(`Category_BaseAttributes` row 6).

============================================================================
`PredefinedStatement` -- CRACKED (identity + real embedded SQL text),
confirms this project's own firmware-based architecture finding
============================================================================
35 rows, `(Statement_ID, Name, Class, Version, Par1, Par2, Par3)`. Each
`Class='script'` row's own `Par3` blob is a small proprietary bytecode
prefix followed directly by REAL, READABLE SQL TEXT -- e.g.
`GetNumberOfCategories` embeds `select count(*) from
Category_BaseAttributes;`; `GetFullPoiData` embeds a real multi-table
join (`select b.Poi_ID, b.Coordinate, b.Name_String_ID, a.HouseNumber_
String_ID, ... from Poi_BaseAttributes b left join Poi_AddressAttributes
a on b.Poi_ID = a.Poi_ID left join Poi_AlertAttributes al on b.Poi_ID =
al.Poi_ID where b.Poi_ID = ?1;`); `GetPartitionsOfCategoriesByName1`
embeds a real subquery chain through `PoiPartition_Category_Relation`
-> `Category_BaseAttributes` -> `String_BaseAttributes`. One
`Class='sql'` row (`CurrentDateTime`) is plain SQL with no bytecode
prefix at all (`select strftime('%s', 'now');`). **This directly
confirms, from the database's own side, this project's earlier
firmware-only finding** (README S2.5): the real `vdo.nav.api.edb.*`
client only ever calls a FIXED CATALOG of precompiled, parameterized
statement templates (`?1` placeholders) -- never arbitrary SQL -- and
`PredefinedStatement` is that literal catalog.

`PoiPartition_BaseAttributes` (61 rows) real fields include a
`MapZoomLevel`-shaped column with plausible real map-scale values
(500000, 400000, 150000, 50000, ...) and a constant `AlertDistance=255`
sentinel on early rows -- consistent with partitions controlling at
which zoom level a POI category becomes visible, not independently
confirmed against the actual rendering code.

`Poi_Relation` (865,543 rows) `RelationType` column takes only 2
distinct values (`0`, `1`) -- a simple binary relation (plausibly
"same place, different category" vs. a franchise/chain link, given
`Related_Poi_ID` pairs of nearby `Poi_ID`s) -- not resolved further.

============================================================================
`Poi_BaseAttributes.Coordinate` -- CRACKED (a LATER session): a 64-bit
Morton (Z-order) interleaved code, NOT the `/100000`-scaled int32 lon/lat
pair used everywhere else on this disc
============================================================================
The earlier "NOT decoded" note's own leading candidate -- "a Hilbert/
Morton space-filling-curve index" -- turned out to be exactly right.
`Coordinate` (a signed 64-bit integer, e.g. `-4348166494090153079`) is a
classic Morton/Z-order code: reinterpret as UNSIGNED 64-bit, then
DEINTERLEAVE its bits into two 32-bit values (even bit positions ->
longitude, odd bit positions -> latitude), each linearly scaled from the
full unsigned 32-bit range to `[-180, 180)` degrees:

    u = Coordinate & 0xFFFFFFFFFFFFFFFF          # reinterpret signed -> unsigned
    x = deinterleave(u, start_bit=0)              # even bits -> raw longitude
    y = deinterleave(u, start_bit=1)              # odd bits  -> raw latitude
    lon = x / 2**32 * 360.0 - 180.0
    lat = y / 2**32 * 360.0 - 180.0                # SAME 360-based scale as lon,
                                                    # not the intuitive -90..90 --
                                                    # latitude simply never uses the
                                                    # top/bottom quarter of its own
                                                    # 32-bit range on a real disc

**Discovered and validated via real-world cross-reference, not guessing**:
joining `Poi_BaseAttributes` -> `Poi_AddressAttributes` -> `String_
BaseAttributes` on `City_String_ID` for a real, well-known city name
(e.g. `'SOFIA'`) showed every one of that city's own POI `Coordinate`
values sharing an unmistakably similar high-order-bit prefix when printed
as unsigned 64-bit -- exactly the spatial-locality signature a Morton
code produces (nearby real-world points share nearby codes) and a
completely different city's own POIs (e.g. `'BERLIN'`, `'MOSKVA'`) showing
a very different, but internally similarly-tight, prefix. This directly
motivated the deinterleave-and-linearly-scale test above.

**Validated at TWO levels of precision**:
- **Broad (18 real cities spanning the whole EEU dataset, Stockholm to
  Athens, Moscow to Zagreb)**: averaging 50 POIs' decoded positions per
  city and comparing against each city's real, independently-known
  center coordinate -- every one lands within a fraction of a degree
  (mostly < 0.1°, i.e. a few km; the 2 largest outliers, Moskva ~0.38°
  and Berlin ~0.20°, are consistent with real POI scatter across a huge
  metro area sampled from the database's own row order, not a formula
  error) of the real city, with no systematic city-independent bias.
- **Precise (2 real, individually-known landmarks)**: Fiumicino (Rome's
  airport town, real airport ~41.8003°N/12.2389°E) decodes to
  (41.770°N, 12.227°E) -- **~0.01-0.03° off, ~1-3km**; a POI literally
  named `"R7 DOLGOSROCHNAYA PARKOVKA DOMODEDOVO"` ("R7 long-term parking,
  Domodedovo") -- Moscow Domodedovo airport's real location is
  55.4088°N/37.9063°E -- decodes to (55.431°N, 37.875°E), **~0.02-0.03°
  off, ~2-3km**, exactly the precision expected for "a parking lot on
  airport grounds", not a formula error.

This is a real, validated crack, not a coincidence: 2 independent
precision anchors (different countries, different real landmarks found
by NAME not by pre-selecting for a good fit) both converge on the SAME
simple formula with the SAME small, geographically-sensible residual,
and the broad 18-city sweep shows zero gross/outlier failures across the
whole dataset's geographic span. **Confirmed at bulk scale, not just a
handful of samples**: 10,000 real POIs (2,000 each from 5 cities spread
across the dataset -- Sofia, Berlin, Praha, Budapest, Athina), decoded
and checked against each city's own real, generously-padded metro-area
bounding box -- **9,988/10,000 (99.9%) decode INSIDE the correct real
bbox**, with the tiny remainder (12/2,000 for Sofia only, the others
100.0%) plausibly genuine data-entry POIs near the bbox edge rather than
formula failures. `decode_coordinate()` below implements this. Not yet
bit-exact to the disc's own encoder precision -- the deinterleave loop
and scale constants are correct in shape, sign, and bulk statistical
placement, but an even tighter fit (matching this project's usual "exact
to the last unit" standard for the `/100000`-scaled fields elsewhere)
was not pursued further this session.

The `String_ID` -> name join, `Category`/`PoiPartition` hierarchy
(`Category_ParentCategory_Relation`, `PoiPartition_Category_Relation`),
and `Image`/`ImageBlob` icon tables were identified by table/column name
and row count only -- not explored in depth.

============================================================================
Practical use
============================================================================
This is a standard SQLite file -- use Python's built-in `sqlite3` module
(or any SQLite client) directly:

    import sqlite3
    conn = sqlite3.connect(r"CD_8555/EDB/POI/POI.DB3")
    cur = conn.cursor()
    cur.execute("SELECT Poi_ID, Coordinate, Name FROM Poi_BaseAttributes LIMIT 10")

No custom parsing code is needed or provided by this module for the
database itself -- it exists to document what's inside, not to wrap a
format that's already a standard one. `decode_coordinate()` below is the
one exception: the CRACKED `Coordinate` Morton-code decode (see above),
since that value needs real decoding logic, not just an SQL column read.
"""

_LON_ODD_BIT = 0  # even bits (0,2,4,...) -> longitude
_LAT_ODD_BIT = 1  # odd bits  (1,3,5,...) -> latitude


def _deinterleave(u, start_bit):
    """Extract every-other-bit of a 64-bit unsigned int `u`, starting at
    bit `start_bit` (0 or 1), into a 32-bit result -- the Morton/Z-order
    decode half of decode_coordinate(). Pure bit-twiddling, no I/O."""
    x = 0
    for i in range(32):
        x |= ((u >> (2 * i + start_bit)) & 1) << i
    return x


def decode_coordinate(coordinate):
    """Decode one `Poi_BaseAttributes.Coordinate` value (a signed 64-bit
    int as read from SQLite) into (lon, lat) degrees -- CRACKED, see this
    module's docstring for the full validation writeup (2 independent
    real-landmark precision checks + an 18-city broad sweep, both
    converging on this exact formula with no gross failures). Returns a
    (lon, lat) tuple in degrees. Precision is on the order of a few km
    (validated directly against 2 real airport-area landmarks), not this
    project's usual bit-exact standard -- treat as "correct area/city",
    not "exact address point", until a tighter fit is found."""
    u = coordinate & 0xFFFFFFFFFFFFFFFF
    x = _deinterleave(u, _LON_ODD_BIT)
    y = _deinterleave(u, _LAT_ODD_BIT)
    lon = x / 2**32 * 360.0 - 180.0
    lat = y / 2**32 * 360.0 - 180.0
    return lon, lat
