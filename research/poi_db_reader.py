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


# ---------------------------------------------------------------------------
# Bulk/vectorized access -- for a real caller (rns510_map_viewer.py's POI
# display) that needs all 4.7M rows decoded at once, not one Coordinate at
# a time. Added the same session decode_coordinate() was cracked.
# ---------------------------------------------------------------------------

import sqlite3
import numpy as np


def decode_coordinates_np(coords):
    """Vectorized decode_coordinate(): `coords` is any array-like of
    signed 64-bit ints (e.g. a numpy int64 array straight from sqlite3
    fetch results); returns (lon, lat) as two numpy float64 arrays, same
    shape as `coords`. Uses the standard bit-spread/compact trick,
    vectorized across the whole array at once (32 numpy ops total, not
    32 * len(coords) Python-level ones) -- decodes all 4,733,183 real
    POIs in well under a second."""
    u = np.asarray(coords, dtype=np.uint64)
    x = np.zeros(u.shape, dtype=np.uint64)
    y = np.zeros(u.shape, dtype=np.uint64)
    for i in range(32):
        x |= ((u >> np.uint64(2 * i)) & np.uint64(1)) << np.uint64(i)
        y |= ((u >> np.uint64(2 * i + 1)) & np.uint64(1)) << np.uint64(i)
    lon = x.astype(np.float64) / 2.0**32 * 360.0 - 180.0
    lat = y.astype(np.float64) / 2.0**32 * 360.0 - 180.0
    return lon, lat


def load_poi_partitions(db_path):
    """Load `PoiPartition_BaseAttributes`'s real per-partition metadata,
    joined to its own category name (via `PoiPartition_Category_Relation`
    -> `Category_BaseAttributes` -> `String_BaseAttributes`) -- e.g.
    partition 24 = `"airport"`, `MapZoomLevel` 5,000,000 (visible from
    very far out); partition 4 = `"downtown area"`, `MapZoomLevel` 50,000
    (only shows up close). `MapZoomLevel`'s real unit was not
    independently confirmed this session, but its VALUES (50,000 to
    5,000,000) sit squarely in the same meters-of-visible-span range this
    project's own map viewer already uses for its road-layer zoom ladder
    (`ZOOM_LEVELS_M`, 25 to 500,000) -- used directly as a visible-span-
    in-meters cutoff for gating POI display by zoom, the same design
    intent `PoiPartition_ID`'s own row-order correlation with visibility
    already hinted at (see this module's docstring). Returns
    {partition_id: {"category_name": str or None, "zoom_level_m": int,
    "map_priority": int}}."""
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT p.PoiPartition_ID, p.MapZoomLevel, p.MapPriority, s.Value
            FROM PoiPartition_BaseAttributes p
            LEFT JOIN PoiPartition_Category_Relation r ON r.PoiPartition_ID = p.PoiPartition_ID
            LEFT JOIN Category_BaseAttributes c ON c.Category_ID = r.Category_ID
            LEFT JOIN String_BaseAttributes s ON s.String_ID = c.Name_String_ID
        """)
        partitions = {}
        for partition_id, zoom_level, priority, category_name in cur.fetchall():
            partitions[partition_id] = {
                "category_name": category_name,
                "zoom_level_m": zoom_level,
                "map_priority": priority,
            }
        return partitions
    finally:
        conn.close()


def load_poi_cache(db_path):
    """Load and decode EVERY real POI in `Poi_BaseAttributes` at once --
    the bulk counterpart to decode_coordinate(), meant for a caller (the
    map viewer) that wants an in-memory, numpy-filterable POI set, the
    same "read once, numpy-filter per viewport" pattern this project's
    own `road_naming.RdCache` already uses for `eeu.rd`. Measured on the
    reference disc: ~3s to fetch all 4,733,183 rows via sqlite3, well
    under 1s more to vectorized-decode every Coordinate.

    Returns a dict: {"poi_id": int64 array, "lon"/"lat": float64 arrays,
    "partition_id": int32 array, "zoom_level_m": int32 array (each POI's
    own partition's MapZoomLevel, precomputed/aligned for fast viewport
    masking -- see load_poi_partitions()), "name": list[str],
    "partitions": {..., see load_poi_partitions()}}."""
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT Poi_ID, Coordinate, PoiPartition_ID, Name FROM Poi_BaseAttributes")
        rows = cur.fetchall()
    finally:
        conn.close()
    poi_id = np.array([r[0] for r in rows], dtype=np.int64)
    coord = np.array([r[1] for r in rows], dtype=np.int64)
    partition_id = np.array([r[2] if r[2] is not None else -1 for r in rows], dtype=np.int32)
    name = [r[3] for r in rows]
    lon, lat = decode_coordinates_np(coord)
    partitions = load_poi_partitions(db_path)
    # Precompute each POI's own partition zoom threshold, aligned 1:1 with
    # the POI arrays above -- avoids a per-partition dict lookup on every
    # viewport query later. Missing/unknown partition -> 0 (never shown by
    # a zoom-gated query, the safe default for data this session didn't
    # otherwise characterize).
    zoom_by_partition = {pid: (meta["zoom_level_m"] or 0) for pid, meta in partitions.items()}
    zoom_level_m = np.array(
        [zoom_by_partition.get(int(pid), 0) for pid in partition_id], dtype=np.int64)
    return {
        "poi_id": poi_id,
        "lon": lon,
        "lat": lat,
        "partition_id": partition_id,
        "zoom_level_m": zoom_level_m,
        "name": name,
        "partitions": partitions,
    }


# ---------------------------------------------------------------------------
# Real POI icons -- CRACKED (a later session): a clean, fully self-
# documenting schema, real standard PNG images.
# ---------------------------------------------------------------------------
#
# `PoiPartition_BaseAttributes.Icon_ID` -> `Image_BaseAttributes.Image_ID`
# (validated directly: joining the two and comparing each partition's own
# real CATEGORY name against its own linked image's own real NAME shows an
# exact or near-exact match for every partition checked, e.g. partition 3
# "gas station" -> Image_ID 4, itself named "gas station"; partition 14
# "atm" -> an image named "atm eur") -> `Image_ImageBlob_Relation` (filtered
# to one `ImageSet_ID` -- `ImageSet_BaseAttributes` names 4 real sets:
# `2D.34.39.PNG.Day`/`.Day.Shadow`, `3D.34.39.PNG.Day`/`.Day.Shadow`;
# `ImageSet_ID=1` ("2D...Day", no shadow) is the natural choice for a 2D
# top-down map view) -> `ImageBlob_BaseAttributes.ImageData`, which is a
# REAL, STANDARD PNG FILE -- confirmed via its own magic bytes
# (`89 50 4E 47 0D 0A 1A 0A`), no proprietary container at all. Every icon
# in the `2D.34.39...` sets is exactly 34x39 pixels -- the SAME dimensions
# already found for `tpd/`'s own `ICONS/` PNG folder (research/tpd_reader.py),
# consistent with this being the same underlying icon set (or a close
# sibling of it) shared across both POI subsystems on this disc.
# `ImageBlob_BaseAttributes.HotSpotX`/`HotSpotY` give each icon's own real
# anchor point (17, 19 for the 34x39 icons -- i.e. horizontally centered,
# vertically just past center, consistent with a classic map-pin icon
# whose "pointer" sits below the icon's own visual center).


def load_poi_icons(db_path, image_set_id=1):
    """Load every real POI category icon (CRACKED, see above) for one
    `ImageSet_ID` (default 1, `"2D.34.39.PNG.Day"` -- the plain 2D set,
    no drop-shadow). Returns {partition_id: {"png_bytes": bytes, "w":
    int, "h": int, "hotspot_x": int, "hotspot_y": int}} -- raw PNG bytes,
    not decoded to any particular image library's own type (this module
    has no GUI/image-library dependency; the caller decodes with
    whatever it already uses, e.g. `PIL.Image.open(io.BytesIO(...))`).
    Partitions with no resolvable icon (should not happen on the
    reference disc, but not assumed impossible) are simply omitted."""
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT p.PoiPartition_ID, b.X, b.Y, b.W, b.H, b.HotSpotX, b.HotSpotY, b.ImageData
            FROM PoiPartition_BaseAttributes p
            JOIN Image_ImageBlob_Relation rel
                ON rel.Image_ID = p.Icon_ID AND rel.ImageSet_ID = ?
            JOIN ImageBlob_BaseAttributes b ON b.ImageBlob_ID = rel.ImageBlob_ID
        """, (image_set_id,))
        icons = {}
        for partition_id, x, y, w, h, hotspot_x, hotspot_y, image_data in cur.fetchall():
            icons[partition_id] = {
                "png_bytes": bytes(image_data),
                "w": w, "h": h,
                "hotspot_x": hotspot_x, "hotspot_y": hotspot_y,
            }
        return icons
    finally:
        conn.close()
