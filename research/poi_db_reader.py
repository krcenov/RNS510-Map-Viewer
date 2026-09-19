"""
poi_db_reader.py -- documents `EDB/POI/POI.DB3` (disc root, NOT under
`db/`), CRACKED: a real, populated, standard SQLite database (open
directly with any SQLite client/library -- no proprietary container,
unlike everything under `db/`). Its existence was already predicted by
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
NOT decoded this session
============================================================================
**`Poi_BaseAttributes.Coordinate` is a single 64-bit integer** (e.g.
`-4414907183593832374`), NOT the `/100000`-scaled int32 lon/lat pair
used everywhere else on this disc. Far too large in magnitude to be two
packed 32-bit halves under that same scale -- likely a proprietary
single-value spatial encoding (candidates: a Hilbert/Morton space-filling
-curve index for fast spatial range queries, a signed offset from some
global origin at a different precision, or a vendor-specific "EDB"
coordinate convention distinct from the rest of this disc's `eeu.*`
files). Not reverse-engineered this session -- a real, self-contained
next investigation (4.7M real POIs, each with a name/address to
cross-reference against, is an excellent validation set for whichever
encoding is eventually tried).

The `String_ID` -> name join, `Category`/`PoiPartition` hierarchy
(`Category_ParentCategory_Relation`, `PoiPartition_Category_Relation`),
`Image`/`ImageBlob` icon tables, and `PredefinedStatement` (35 rows, a
real scripted-query mechanism named in the `DatabaseAttribute` metadata)
were all identified by table/column name and row count only -- not
explored in depth.

============================================================================
Practical use
============================================================================
This is a standard SQLite file -- use Python's built-in `sqlite3` module
(or any SQLite client) directly:

    import sqlite3
    conn = sqlite3.connect(r"CD_8555/EDB/POI/POI.DB3")
    cur = conn.cursor()
    cur.execute("SELECT Poi_ID, Coordinate, Name FROM Poi_BaseAttributes LIMIT 10")

No custom parsing code is needed or provided by this module -- it exists
to document what's inside, not to wrap a format that's already a
standard one.
"""
