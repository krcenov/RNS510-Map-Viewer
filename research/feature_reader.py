"""
Reader/scanner for RNS510 FEATURE_COMPRESSED (compressionType=3: eeuz.fea).

This is a SEPARATE, genuinely different format from MAP_COMPRESSED
(compressionType=2: eeuz.mp0/.mg1-.mg4, see map_compressed_reader.py) despite
files.cfg nominally grouping them as "feature files". See README.md section
"eeuz.fea (FEATURE_COMPRESSED)" for the full writeup; this module docstring
covers only what's needed to use the code.

============================================================================
CONFIRMED this session
============================================================================
- Same 80-byte file header template as MAP_COMPRESSED
  ("(*$SIEMENS&^)\x00\x00\x00" + "Copyright 1998..." etc, see
  map_compressed_reader.read_header() -- byte-identical layout, reused here).
- Payload entries (from file offset 11,727,784 on the reference disc's
  eeuz.fea, to EOF) are standard RFC1950 zlib streams packed back-to-back,
  same primitive as MAP_COMPRESSED tiles -- CONFIRMED by chaining 4,036
  consecutive entries byte-exactly (each entry's exact consumed-byte count,
  verified via byte-by-byte decompression, not the window-based heuristic
  which can occasionally over/under-report -- see decompress_entry_exact())
  lands EXACTLY on the next entry's zlib header, repeatedly.
- UNLIKE MAP_COMPRESSED, this chaining is NOT unconditional: real gaps of
  non-zlib bytes occur between runs of entries (measured: one 114-byte gap
  after 4,036 perfectly-chained entries in the first ~880KB of payload
  sampled this session). The gap bytes are NOT padding/zero-fill -- they
  decode (unparsed) to something that superficially resembles the same
  "envelope" byte shape as a decompressed entry's own content (see below),
  but this was NOT confirmed to be a real uncompressed record type opposed
  to coincidental structure -- treat `find_next_entry()`'s gap-skipping as
  a practical workaround, not a cracked "gap record" format.
- Decompressed entry content is UNRELATED to MAP_COMPRESSED's tile format
  (no 0x0146 magic, no sub-index, no anchor+delta-run feature blocks at a
  fixed data_start -- decode_features()/find_tile_anchor() from
  map_compressed_reader.py were tried directly against .fea entries and
  found NOTHING, confirming this is a genuinely different internal schema,
  not just a different container around the same one).
- Decompressed entries are small (42-26,348 bytes observed in the first
  4,036-entry sample; mean declen 380 bytes, mean complen 218 bytes) --
  MUCH smaller than MAP_COMPRESSED tiles (hundreds of bytes to ~35KB, but
  typically representing many packed road features per tile). This is
  consistent with .fea's compression unit being closer to one
  feature/record, not one spatial tile of many records.
- **Record envelope** (recurring shape, NOT a fully cracked byte format):
  each decompressed entry starts with a 4-byte field (LE uint32, but only
  ever a single-digit-to-two-digit value in the observed sample -- e.g.
  0x00000002, 0x00000004 -- i.e. the real information is a small integer
  in the LAST byte when read as bytes) that behaves like a **record/type
  count or tag**, followed by one or more fixed-shape sub-records. A very
  common sub-record shape (observed byte-for-byte identical across
  thousands of samples for the "simple" case) is a small (~34-42 byte)
  block containing: a handful of small varying bytes, a single **tag byte**
  whose value (1,2,3,4,5,6,7,8,0x09,0x12,0x17,... seen) plausibly encodes a
  feature TYPE, then two pairs of int16 LE fields that are frequently the
  literal sentinel `0x8000` (-32768, i.e. an "unset" placeholder, the same
  sentinel convention MAP_COMPRESSED's sub-index uses for empty cells),
  then 1-2 more int16 LE pairs holding small real-looking values whose
  meaning (coordinates? indices? something else?) is NOT decoded -- see
  "OPEN PROBLEMS" below, this is the biggest remaining gap.
  Many of these small sub-records are BYTE-IDENTICAL across dozens of
  consecutive file entries (e.g. offsets 11727871..11728363 on the
  reference disc all decompress to the exact same 80-byte content) --
  this strongly suggests a large fraction of the early payload is
  placeholder/empty-cell filler entries (analogous to MAP_COMPRESSED's
  sub-index sentinel cells), not real per-location data, though this was
  NOT proven at file-scale, only observed in samples.
- **CRACKED, high-value: named-feature records with embedded multi-language
  name tables.** A minority of entries carry a MUCH larger sub-record
  containing a `[1-byte language/id code][1-byte UTF-8 byte length][UTF-8
  name bytes]` sequence, repeated once per language, e.g. (real example,
  reference disc, entry at file offset 11,781,130, declen 1056, complen
  409): id=0x0d,len=15,"SREDIZEMNO MORE" (Bulgarian/Macedonian), id=0x12,
  len=19, UTF-8 "STŘEDOZEMNÍ MOŘE" (Czech), id=0x18, len=17, "MEDITERRANEAN
  SEA" (English), and 20+ more covering effectively every language on the
  reference disc's "EU East" market (Danish, Dutch, Estonian, French,
  German, Hungarian, Icelandic, Lithuanian x2, Norwegian, Polish,
  Portuguese/Spanish/Italian "MAR MEDITERRANEO", Romanian "MAREA
  MEDITERANA", Russian "SREDIZEMNOE MORE", Slovak/Croatian/Serbian variants,
  Swedish "MEDELHAVET", Turkish "AKDENIZ", Ukrainian) -- all correctly
  meaning "Mediterranean Sea" in their respective language. This is
  DEFINITIVE, concrete proof that eeuz.fea stores NAMED geographic features
  distinct from eeu.rd's road/street names, directly confirming this
  session's target hypothesis (non-road cartographic features: water
  bodies at minimum). See `scan_names()` / `parse_name_records()` below.
  Structure of the name-bearing sub-record: same ~22-byte preamble shape as
  the simple sub-record (first 5 bytes "02 7d 01 0f 0a" constant in samples
  seen so far, though NOT confirmed universal -- see caveat below), then a
  1-byte language/name COUNT (0x1a=26 in the Mediterranean Sea example,
  plausible for a ~26-language European nav database), then repeated
  [id][len][utf8] entries until the count is exhausted, then a short
  trailer of int16-sized values (unparsed) before the next sub-record or
  entry begins.
  **CAVEAT**: the "02 7d 01 0f 0a" 5-byte prefix, while constant across
  every "simple" sub-record example decompressed so far AND the
  Mediterranean Sea record's own preamble, was found NOT to match the
  non-zlib "gap" bytes' superficially-similar envelope (see above) -- so
  either the prefix is not truly universal, or the gap bytes are not a
  real record of this same type. Left unresolved.

============================================================================
CONFIRMED this session, part 2: this is a general PLACE-NAME GAZETTEER,
not just water bodies
============================================================================
A wide, spread-out scan (11 sample windows of 3,000 entries each, at file
fractions 0%, 5%, 15%, ..., 99.5% of the ~541MB payload -- i.e. genuinely
spanning the whole file, not just the start) found **hundreds of
multi-language name-table hits per window** in populated regions. The named
entries are NOT limited to water/parks -- they cover, at minimum:
  - **Cities/towns/villages** at every scale, from major capitals (BERLIN,
    WIEN/VIENA/VÍDEŇ, BUDAPEST/BUDAPESHTA/BUDAPEŠŤ, BRATISLAVA/POZSONY,
    MÜNCHEN/MUNICH/MUNIC) down to tiny Russian/Ukrainian villages (a few
    hundred people).
  - **Named water bodies**: seas (Mediterranean, Black/CHERNO MORE/
    KARADENIZ, Baltic, North/NORDSEE/SEVERNO MORE, Caspian/KHAZAR DANIZI,
    Gulf of Bothnia/PERÄMERI), confirming the session's original hypothesis.
  - **Islands**: Crete/KRITI, Rhodes/RODOS, Kos, Santorini/THIRA, Karpathos,
    Kythira, Milos, Ios, Sifnos, Amorgos (the whole Greek archipelago is
    present).
  - **Road/route shield labels**: European route numbers (E58, E50, E115,
    E101, E391, E105, E40, E391 -- with Cyrillic transliterations like
    "Е58"), national route codes (R22, R456, R487, R228, R226, R239, A375,
    AH30/AH61/AH63/AH64/AH70/AH4/AH6 -- Asian Highway numbers, relevant to
    the dataset's eastward extent into the Caucasus/Russia), and
    Ukraine-style route codes (T0804, N09, N21, N23, M4, M5). These are
    almost certainly the road-shield icons drawn on motorways/trunk roads,
    a label type that has NO equivalent in the already-cracked `.rd`/
    MAP_COMPRESSED road-geometry files.
  - **CONCRETE, individually cross-referenced validation** (same rigor as
    this project's other geographic validations): an entry at file offset
    363,675,854 (declen 15,687) decodes a 7-language name table --
    IASI, JASY, IASIO, JÁSZVÁSÁR, JASSY, YASSY, YAS -- every one of these
    is a genuine, real historical/foreign-language exonym for **Iași,
    Romania** (JÁSZVÁSÁR is literally Hungarian for "market of Iași";
    JASSY/YASSY are the standard English/German historical spellings).
    Iași is one of this project's own previously-validated reference
    cities (README §3.6's "Iasi 392-point chain" and `eeu.cty`'s
    postal-code cluster at 27.55-27.57E/47.12-47.14N, matching real-world
    Iași at 27.59E/47.16N) -- i.e. this is not a coincidental name match,
    it is the SAME real city this project has independently validated
    multiple times before, now found by name inside `eeuz.fea`.
  - Sample validated via `research/city_reader.py`'s `eeu.cty` catalog
    cross-reference; see README's new section for the full writeup.

Practical consequence: `scan_names()` + a real-world/`eeu.cty` name lookup
is, this session, the ONLY reliable way to geolocate an arbitrary `.fea`
entry (see OPEN PROBLEMS #1 below for why coordinate-field decoding did not
succeed) -- but it works well precisely because so much of the file's
content IS named places.

============================================================================
Directory region (byte 80 -> file offset 11,727,784, ~11.7MB): a genuine
NEW structural lead, still NOT semantically cracked
============================================================================
This session found that the ENTIRE ~11.7MB region divides EXACTLY into
977,308 fixed 12-byte records plus an 8-byte trailer (11,727,704 =
977,308*12 + 8) -- confirmed by direct division, not just a byte-equality
heuristic (though a stride-12 byte-equality check also independently
supports it: 78-97% same-byte-at-offset-i-and-i+12 in every 1MB window
across the whole region, far above chance). This is a materially different,
more specific characterization than prior sessions' "variable ~14-16
byte/tile records, an ascending uint32 counter, naive parsing unreliable
past the first ~10 records" description -- the WHOLE region is uniform
12-byte records, not just a small prefix.
The LAST ~42-50 records (right before the first real tile) are
BYTE-IDENTICAL placeholder/padding records (repeating one fixed 12-byte
value) -- consistent with a table sized larger than needed and padded with
a sentinel at the end, the same convention MAP_COMPRESSED's sub-index and
this file's own "point stub" records both already use elsewhere.
**NOT cracked**: interpreting each 12-byte record as 3 uint32 LE fields (the
most natural guess) does NOT produce a clean offset/count/length table --
sampled fields take huge, essentially-random-looking 32-bit values in most
records (not small file-relative offsets), and a promising-looking
hand-inspected sub-pattern near the tail (one field slowly incrementing by
~38-39 per record, suggestively close to real small entries' `complen`)
did NOT hold up as a global pattern when checked programmatically across
all 977,308 records with that same 4/4/4-byte grouping -- so either the
true field boundaries within the 12 bytes are different (not a clean
4-byte-aligned triple), or the encoding needs additional context (e.g. a
per-region base value) this session did not find. Left as a confirmed,
specific, actionable lead for a future session (977,308 is also a
plausible "one record per spatial grid cell" count, worth checking against
a spatial-grid hypothesis directly, e.g. does 977,308 factor into a
sensible lon x lat cell grid over the EEU coverage area?), not a decode.

**IMPORTANT correction/discovery (found later this session): this 12-byte
directory-table format is NOT unique to the byte-80 region -- it recurs
elsewhere in the file, embedded directly in the payload area.** A full-file
enumeration run stopped unexpectedly at file offset 306,299,567 (55.4%
through the file, 507,680 entries in) because `find_next_entry()`'s default
small search window couldn't find a next entry there. Direct investigation
found the next real zlib entry only at file offset 311,300,723 -- a gap of
EXACTLY 5,001,156 bytes (416,763 * 12 + 0, confirmed by exact division),
and this gap region has the SAME structural signature as the byte-80
directory (stride-12 byte-equality ~87.5%, a long run of one repeated
12-byte sentinel value at its START this time rather than its end, and a
tail of records right before the resumed payload showing the same "two
near-constant fields + one slowly-incrementing field" shape found at the
end of the main directory). The first entry after this second table has
declen=72 -- identical to the very first entry of the whole file --
consistent with each such table/section boundary being followed by a
similarly-shaped small canonical record. Conclusion: `eeuz.fea` is not
simply [header][one 11.7MB directory][one long payload run] -- it embeds at
least one more (and plausibly several more, unexplored) directory-table-
shaped region DIRECTLY IN THE PAYLOAD, likely marking section/region
boundaries (the content immediately after this specific one, per the wide
scan elsewhere in this docstring, is the Greek islands cluster -- plausibly
a per-country or per-region partition boundary, unconfirmed). Practical
consequence: `find_next_entry_escalating()` / `enumerate_entries(...,
gap_search_window=None)` (the default) now retry with much larger search
windows (up to 25MB) specifically to survive this -- a full-file
enumeration with the OLD small-fixed-window behavior will silently stop
partway through and under-report, as this session's own first attempt did.

============================================================================
CHECKED, REFUTED this session: name records do NOT embed a literal
`eeu.cty` record-index (or byte-offset, or `eeuz.cl` record-position) field
============================================================================
The leading lead left by the previous session (see OPEN PROBLEMS #1(c)
below, as it stood before this check) was that a name-bearing entry might
skip storing its own coordinate and instead reference it indirectly via a
small-integer id into `eeu.cty` -- the same "join instead of embedded
coordinate" pattern already proven for `.il`->`.rd` and `.cl`->`.cty`
(README S3.2/S3.8). This was tested directly and thoroughly, not just
attempted once:

**Ground truth** (via `research/city_reader.py`): Iasi's own top-level
`eeu.cty` record is index **349791** (`cty_record(body, 349791).name ==
"IASI"`, bbox (27.37182,47.0239)-(27.80278,47.29492), repr_point
(27.5873, 47.15941) -- matches real-world Iasi almost exactly, and per
`.cty`'s own documented format a record's self-index always equals its
file position, so 349791 is exact, not inferred). Five more independent,
unambiguous, unique top-level `.cty` records were used as additional
ground truth: TURKU=403630, BRATISLAVA=182482, TRONDHEIM=389671,
OSLO=384186, NISYROS=238217 (each verified to be the SOLE exact top-level
name match in the 939,351-record file).

**Method**: for each of these 6 cities' `.fea` name entries (offsets
363,675,854 / 550,612,987 / 371,700,185 / 550,725,854 / 550,550,064 /
312,374,782), the full decompressed entry was scanned at EVERY byte
position for the ground-truth `.cty` index as: 1/2/3/4-byte width, signed
and unsigned, little- and big-endian (14 encoding combinations total per
target). Also tried: the index's absolute file byte-offset into `eeu.cty`
(`94 + index*79`), the body-relative byte-offset (`index*79`), the byte-
offset divided by 2/4/8/16/79, `index +/-1`, `index*2`, `index//2`, and the
index split as two adjacent uint16 words. Also tried the alternative
hypothesis that the reference is to `eeuz.cl`'s OWN record position (not
the `.cty` index `.cl` itself stores) -- every `.cl` record (of the
4,084,104 total) whose embedded `.cty`-index field equalled the target was
collected (12-24 alias positions per city, since `.cl` carries multiple
transliteration/sort-key variants per place, README S3.8) and each of
those positions was searched for too.

**Result: 0/6 cities, in every encoding tried.** Including the
586-byte NISYROS entry (only 3 packed names, negligible search-space
noise) -- a value as specific as 238217 or its derivatives simply is not
present in that entry in any tested form. The one apparent `.cl`-position
"hit" (TURKU, cl_position=122 found as a raw uint16) is not treated as a
real signal: 122 is small enough to appear by chance in a 16KB entry
packed with small integer sub-record fields, and it is the ONLY such hit
across 6 cities x up to 24 alias positions each -- exactly the kind of
false positive this project's standard rejects (compare the "IAS"
substring false-positive sweep below).

A **separate, complementary check** on the single Iasi entry: every
2/4-byte field in the raw entry was decoded AS a `.cty` record index (when
in the valid 0-939350 range) and the resulting name checked for the
substring "IAS" -- 663 positions matched, but manual inspection shows
every one is an unrelated place whose name merely CONTAINS "ias" as a
substring (CIVIASCO, ROCCASPINALVETI, OGLIASTRO CILENTO, ...), never Iasi
itself or a plausible sibling Romanian record -- consistent with pure
coincidence over a 939K-name space, not a real cross-reference.

Finally, the directory region (see below) was searched too: neither the
`.fea` entry's own absolute file offset, nor its city's `.cty` index,
appears as a literal uint32 (LE or BE, byte-unaligned scan) anywhere in
the full ~11.7MB/977,308-record directory region, for any of the 6 test
cities (0/12 hits: 6 cities x {offset, index}).

**Conclusion**: the specific hypothesis "a `.fea` name record contains its
place's `eeu.cty` self-index (or a simple transform of it) as a literal,
scannable integer field" is REFUTED at this project's standard of
evidence (6/6 independent real-world cities, 0 hits, including a
near-zero-noise small entry) -- not just "not found yet". If a link to
`.cty` (or another already-cracked file) exists at all, it is not a raw
index/offset sitting in plaintext in the record bytes -- candidates a
future session could try instead: a hash/checksum of the name string
rather than a numeric join key; an indirection through the still-uncracked
12-byte directory record's OTHER fields (i.e. the directory entry
encodes the link, and this session only checked whether the DIRECTORY
itself echoes an already-known value, not whether some transform of an
uncracked directory field points to `.cty`); or the architecturally
simplest explanation -- that `.fea` is purely a name/label lookup table
with no stored position at all, and real position comes from whatever
OTHER system (map-rendering label placement, e.g. the still-not-fully-
understood "ascending local id" byte noted in README S3.6's "Label
strings" finding) decides where to draw the label, i.e. `.fea` may simply
never need to answer "where is this" on its own. Reusable test script (not
folded into a library function, since nothing was cracked):
`research/`-adjacent one-off scripts used this session are not checked in,
but the method above is fully specified here for reproducibility.

============================================================================
LATER SESSION: directory RECORD FORMAT CRACKED -- an (offset, declen,
complen) index triple, NOT a coordinate/MapRect. Coordinate-attachment
hypotheses at section/parcel and sub-tile granularity TESTED AND REFUTED.
============================================================================
Task for this session: given native-firmware evidence that the real loading
code calls `addKey(MapParcelKey&, MapRect&, MapPoint&)`, test whether
coordinates attach at a coarser-than-per-record granularity -- one bounding
box per directory "section", or one small coordinate per 12-byte directory
record treated as a per-sub-tile anchor (analogous to MAP_COMPRESSED's flat
table). Both were tested directly against real ground truth. Neither holds
-- but the investigation cracked the actual byte-level meaning of the
12-byte directory record instead, which explains why every earlier and
current coordinate attempt came up empty.

**Hypothesis 1/2 (MapRect or MapPoint at a directory table's own header or
trailer boundary) -- REFUTED.** Both known directory tables' exact boundary
regions (T1: byte 80 to file offset 11,727,784, its last 8-byte trailer and
surrounding records; T2: file offset 306,299,567 to 311,300,723, both ends)
were dumped and scanned byte-by-byte (every alignment, LE and BE, /100000
scale) for a 16-byte MapRect or 8-byte MapPoint decoding to real geography
(Mediterranean/Southern-Europe range for T1, since real content resumes
there per the wide scan; Greece 19-28E/34-42N for T2, per the "Greek
islands cluster" observation). Result: T1's trailer is all zeros; both
tables' true boundary bytes are occupied by the same repeating 12-byte
PADDING SENTINEL already documented in the module docstring (T1:
`12 41 c2 af 00*8` at its tail; T2: `12 8e 12 73 00*8` at its head, `00*8
1f 92 63 55` near its tail) -- these sentinels do NOT decode to plausible
coordinates in any tested encoding, and every apparent "hit" the sweep
found is a trivial artifact of the sentinel value repeating every 12 bytes
(the same numeric coincidence recurs at every multiple of 12, which is what
you'd expect from a repeated non-coordinate constant, not a one-off header
field). No distinct, plausible MapRect/MapPoint block exists at either
table's boundary.

**Hypothesis 3 (each 12-byte directory record is a per-sub-tile coordinate
anchor, values should progress smoothly like MAP_COMPRESSED tile anchors)
-- REFUTED, and the real structure found instead.** A naive lag-1
autocorrelation check on a sample of "real" (non-padding) records gave weak,
inconsistent values (0.05-0.37 depending on field/encoding) -- nothing close
to MAP_COMPRESSED's genuine tile-anchor autocorrelation (0.98/0.99 lon/lat,
computed this session on real `mg4` anchors for direct comparison). A deeper
look explains why: **42.7% of consecutive directory records in `T1` are
byte-identical to their predecessor** (collision/padding runs), only
560,276/977,308 (57%) distinct values exist at all, and run-length
statistics follow a decay curve (mostly 2-12-record runs of "changing"
values) typical of a **hash table with open-addressing collisions**, not an
ordered spatial array. This directly explains the prior session's "small
integers collide" observation and the failed 4/4/4-byte-uint32-LE grouping
attempt.

**The real crack: 12-byte records are (offset, declen, complen) index
triples, big-endian uint32, NOT geographic data at all.** The key mistake
in every prior attempt (this session's own early ones included) was
assuming little-endian and/or a single fixed field order. Reading a
concrete, densely-packed real run of 1,191 consecutive directory records
(`T1`, records 764811-766002, file offset 9,177,812) as three big-endian
uint32 fields shows: field0/field1 constant per sub-run (e.g. 42, 38),
field2 increasing by exactly field1's value each record -- and field2,
taken as an ABSOLUTE FILE OFFSET, points at a real zlib stream every time,
whose decompressed length exactly equals field0 and whose exact consumed
byte count exactly equals field1. **Verified at scale, not just on this one
run**: full byte-exact decompression-and-length-match (not just "looks like
a zlib header") on the 1,191-record run scores 1,008/1,191 (84.7%); a
random 5,000-record sample across the whole T1 table (excluding all-zero
padding records) scores 1,478/5,000 (29.6%); a systematic 20,000-record-block
sweep of the ENTIRE 977,308-record table scores between 2.7% and 73.5% per
block, generally rising toward the end of the table -- i.e. this is a real,
substantial, verifiable fraction of the table's content, not noise. (Field
order in this run: `[declen][complen][offset]`, offset THIRD.)

**A second field-order variant exists, confirmed against real named-place
ground truth.** Searching both directory tables for the LITERAL (offset,
declen, complen) values of this project's own independently-verified real
`.fea` entries (exact declen/complen obtained by direct decompression, not
assumed) found an EXACT, contiguous, correctly-ordered 12-byte match --
all three 32-bit fields adjacent, big-endian -- for **4 of 7** test cases:
Mediterranean Sea (offset 11,781,130/declen 1,056/complen 409) in `T1` at
body offset 329,924, and Iasi (363,675,854/15,687/11,740), Bratislava
(371,700,185/34,174/24,840), and Nisyros (312,374,782/586/350) all in `T2`,
at body offsets 1,259,760 / 1,337,676 / 343,296 respectively. This ordering
is `[offset][declen][complen]`, offset FIRST -- the mirror image of the
dense-run ordering above (a rotation, not a different byte width or scale).
Getting all three independent 32-bit values to align adjacently and in the
right order is not something that happens by chance (a single coincidental
32-bit collision across an 11.7MB region has estimated probability ~0.27%;
three independent fields landing adjacently, correctly grouped, is
vanishingly unlikely) -- this is a real, validated crack, not a
pattern-matching artifact. **Notably, the Iasi/Bratislava hits are NOT
12-byte-grid-aligned relative to their table's start in the naive
zero-phase sense assumed elsewhere** (Mediterranean Sea's hit sits 8 bytes
off the naive grid), which is consistent with this being a genuine hash
table with internal structure (collision chains, variable local grouping)
rather than one uniform flat array -- the ~87.5% stride-12 self-similarity
statistic documented earlier in this file is a real, dominant regularity,
just not a perfectly rigid, phase-locked one throughout.

**Practical, load-bearing negative finding: 3 of the 7 test cities (Turku,
Trondheim, Oslo -- all with `.fea` entries around file offset ~550MB) have
NO record in EITHER known directory table, in any encoding, any phase, any
field order** (confirmed both via the literal-offset raw-byte-string search
and the full same-record-triple search). Since `T2` was shown to index at
least one entry (Iasi, at 363MB) far past its OWN physical location (it
sits at 306-311MB), a directory table is not restricted to indexing only
the payload immediately following it -- **this is a hash/keyed index across
(at least a large part of) the file, not a per-physical-section table** --
so the natural explanation for Turku/Trondheim/Oslo's absence is that at
least a THIRD directory-table-shaped region exists further into the file
(not located this session; a good next step would be an escalating-window
`find_next_entry_escalating()`-style scan starting past file offset
311,300,723, watching specifically for another multi-MB non-zlib gap with
the same stride-12 signature).

**Why this refutes, rather than just fails to confirm, the
per-section/per-parcel MapRect hypothesis this session set out to test**:
(1) the boundary scan (hypotheses 1/2) found no MapRect/MapPoint-shaped data
at all, only sentinel repeats; (2) the "12-byte record = coordinate" reading
(hypothesis 3) is now known to be WRONG in a mechanistically understood
way -- these bytes are a big-endian file-offset/length index, and reading
them as little-endian coordinates (what every earlier session, including
this one initially, tried) necessarily produces "essentially random"-looking
32-bit values, exactly as previously reported; (3) the sections a directory
table would notionally bound are enormous (T1's own indexed range, if it
even makes sense to speak of one, spans from just after byte 11.7M to well
past 300MB -- hundreds of MB, i.e. most of the dataset), far too coarse to
serve as a per-region MapRect even in principle; and (4) `MapLoaderJob
FeatureFile::addKey`'s `MapRect`/`MapPoint` arguments, per this new
understanding, more plausibly correspond to the ALREADY-KNOWN `eeu.cty`
bounding boxes/representative points (§3.8) that the loader would look up
by name/id AFTER resolving a `.fea` record via this hash index -- i.e. the
coordinate plausibly never lives in `.fea` at all, consistent with (and now
mechanistically motivated by) the file's role as a pure name/label
gazetteer with an internal name-or-id-keyed lookup structure, not a
spatial database of its own.

Reusable implementation (validated at the scale described above):
`decode_directory_table()`, `verify_index_triple()`, `_index_triple_
candidates()` below. `KNOWN_DIRECTORY_TABLES` records the two located
tables' exact byte ranges for reuse.

============================================================================
OPEN PROBLEMS (honest, not swept under the rug)
============================================================================
1. **No confirmed absolute coordinate field found inside a decompressed
   entry.** Exhaustively scanning every 2-byte-aligned offset inside both
   the "simple" sub-record and the Mediterranean Sea/Iasi records'
   non-string bytes for an adjacent int32 LE pair that lands in the
   plausible EEU lon/lat range (3-46E, 30-72N), or even the much TIGHTER
   real-world Iași window (27.3-27.9E, 46.9-47.4N), after /100000 -- the
   exact technique `map_compressed_reader.py` uses successfully on
   MAP_COMPRESSED tiles -- found ZERO tight-window hits on the Iasi entry
   and ZERO hits at all across 500 sampled "simple" records. Broad-range
   (EEU-wide) hits DO occur inside large entries, but scattered across
   totally unrelated countries within the SAME compressed entry (e.g. the
   Iasi entry's other bytes coincidentally decode to plausible-looking
   Algeria/Sicily/Georgia/Sweden/Finland coordinates) -- strong evidence
   that a large entry packs MANY unrelated small sub-records together (only
   one of which is the named Iasi record), not that any of those numbers
   are Iasi's own coordinate. This means either (a) coordinates use a
   different scale/encoding/base in this format, (b) coordinates are
   RELATIVE to an anchor stored elsewhere (the directory region above, or a
   per-batch value this session did not locate), or (c) name-bearing
   records don't carry their own coordinate at all and instead reference
   geometry/position by an external id (plausible given the "feature file"
   name -- e.g. a cross-reference into `eeu.cty`, which already has real
   lon/lat for every named place). **UPDATE: the (c) sub-hypothesis's most
   natural form -- a literal `.cty` record-index or byte-offset sitting
   somewhere in the record bytes -- was tested directly this session (see
   the dedicated section above) and REFUTED across 6 independent real
   cities, 0 hits in any of 1/2/3/4-byte x signed/unsigned x LE/BE
   encodings, plus several offset transforms and the `.cl`-position
   alternative.** Not resolved: (a) and (b) remain untested/open, as does
   any NON-literal (b) variant of (c) (e.g. a hashed name, or an
   indirection through the still-uncracked directory region rather than a
   direct index).
2. **Directory region field-level meaning: CRACKED (later session, see
   dedicated section above)** -- 12-byte records are big-endian (offset,
   declen, complen) index triples (two field-order variants observed,
   `[declen,complen,offset]` and `[offset,declen,complen]`), validated by
   exact decompression match at scale (84.7% on one dense real run, 29.6%
   on a random whole-table sample, exact ground-truth triple matches for
   Mediterranean Sea/Iasi/Bratislava/Nisyros) -- this is a keyed lookup
   structure (hash-table-like: high collision/duplicate-record rate, a
   directory can index entries far outside its own physical byte range),
   NOT a spatial/geographic index or a per-section MapRect. `enumerate_
   entries()` below remains the practical BRUTE-FORCE workaround for a
   full sequential walk (still needed since the directory decode above is
   not 100% recall and a 3rd+ directory table, needed to cover ~550MB-ish
   content like Turku/Trondheim/Oslo, has not been located yet) --
   validated across 11 sample windows spanning the full payload (0% to
   99.5%) plus gap-recovery tested at each.
3. **Geolocation of an arbitrary entry is only possible via an embedded
   name string** (cross-referenced against real-world geography or
   `eeu.cty`), NOT via a decoded coordinate field -- unlike MAP_COMPRESSED's
   `build_geo_index()`, there is no known way to recover a (lon,lat) anchor
   directly from an arbitrary .fea entry's bytes yet. Entries with no
   embedded name (the majority -- named entries are common but still a
   minority of all entries) cannot currently be geolocated at all.
4. The intermittent non-zlib "gaps" between chained entries (see above) are
   not understood -- `find_next_entry()` below treats them as an opaque
   region to skip over via local brute-force search, which works in
   practice (see `enumerate_entries()`'s validation) but is not a decode of
   what they actually are.

============================================================================
A LATER SESSION's new lead: eeu.mod's own schema for this table -- a
real, previously-unchecked source, but in tension with the hash-table
conclusion above, not yet reconciled
============================================================================
`eeu.mod` (the disc's own schema dictionary, research/mod_reader.py --
README S3.16) was never checked against `eeuz.fea` specifically before
this pass. Its `feature` block is the single largest and most detailed
in the whole schema (90 raw strings, ~77 real fields once boilerplate is
excluded), and describes a MUCH richer nested structure than anything
tested above:

    FeatureFileHeader -> fileCnt, Zip_Statistic{dummy1ForZip,
    dummy2ForZip}, MapHeaderDirectory -> MapHeader{
        db_cover{min_long, min_lat, max_long, max_lat},      -- a real bbox
        parcel_width, parcel_height, parcel_cnt_x, parcel_cnt_y,
        parcel_norm_x, parcel_norm_y,                         -- a tile/parcel GRID
        feaType, scaleCnt, scales[]{scale, offset},           -- multiple zoom scales
    } -> SubFiles -> ParcelHeaderX, ParcelHeaderY,
    ParcelHeader{offset, byteCnt, byteCntZip}                 -- 12 bytes/record!
    -> ParcelFeatureData -> feaCnt -> FeatureDataList ->
    FeatureDataHeader{category, type, flags, scaleFlag, feaPointCnt,
        trans_1, trans_2, lenAtt, lenName_1, lenName_2, attribute,
        [geometry variant: line | poly | point | road], ...}

**`ParcelHeader{offset, byteCnt, byteCntZip}` is a striking, independent
confirmation-and-naming of the already-cracked 12-byte directory index
triple above** (3 uint32 fields = 12 bytes, exactly): `offset`=the
already-found `offset`, `byteCnt`=`declen`, `byteCntZip`=`complen` --
the schema gives real names to a structure a prior pass in this same
session found empirically (big-endian, hash-table-like). This is a
genuine cross-validation, found independently two different ways.

**Tested and REFUTED this session**: the schema's own `parcel_cnt_x`/
`parcel_cnt_y` grid-dimension fields, on the natural guess that their
product should equal the directory's own exact 977,308-record count
(one `ParcelHeader` per parcel) -- `977,308 = 929 x 1,052` (and no other
close/round factor pair) -- neither `929` nor `1052`, nor any of
977,308's other factor pairs, appears anywhere as a little-endian OR
big-endian uint32 in the first 12MB of the file (which fully covers the
already-located directory region). Either the grid model doesn't apply
this simply to the already-found directory, `parcel_cnt_x`/`_y` aren't
adjacent to the directory's own physical start, or the schema's parcel
concept doesn't correspond 1:1 with the already-found hash-table index
at all.

**The single most actionable new lead, not yet tested**: the schema
names `delta_long`/`delta_lat` as real per-geometry-point fields (once
for `point` records, once for `pointList` entries under `road`) --
i.e. coordinates in this format are explicitly DELTAS relative to some
anchor, not absolute values. This gives open problem #1 above (zero
absolute-coordinate hits found anywhere) a concrete, specific
explanation and a concrete next test: search for a SMALL int16/int32
delta pair near a real named entry's own bytes that, when ADDED to a
plausible anchor (the entry's own `MapHeader.db_cover` corner, a
per-parcel anchor, or `eeu.cty`'s own already-known real coordinate for
that same place), lands close to the place's real-world position --
rather than continuing to search for a standalone absolute value.

**This is a genuine, unresolved TENSION, not a resolved contradiction**:
the already-established empirical finding (the located directory tables
behave as a hash/keyed index -- high collision rate, entries indexed far
outside a table's own physical range, no coordinate-like regularity) sits
uneasily next to the schema's own explicit parcel-GRID and delta-
COORDINATE design. Both are independently well-supported by their own
evidence. Possible reconciliations, none tested: (a) this disc's build
uses only a subset of the schema's full generality, and the "real"
grid/coordinate machinery the schema describes is simply unpopulated or
superseded by the simpler hash-index this session already found
(matching the pattern already seen elsewhere on this disc, e.g.
`eeuz.pca`'s always-zero `clusterOffset`/`clusterCount`, §3.23); (b) the
schema's grid/coordinate fields belong to a DIFFERENT, not-yet-located
region of the file (recall open problem #2's own note that a 3rd+
directory-table-shaped region, covering Turku/Trondheim/Oslo, was never
located); or (c) the named entries tested so far (Mediterranean Sea,
Iasi, ...) are a `type`/`category` of record that doesn't carry the
`point`/`road` geometry sub-structure the schema's `delta_long`/
`delta_lat` fields belong to, and a genuinely geometry-bearing entry
(rather than a name-only "label" entry) would look different. Left for a
future session -- see `research/mod_reader.py`'s `extract_blocks()` with
token `['fea']` for the complete, ordered field list to work from
directly.

============================================================================
Usage
============================================================================
    import feature_reader as fr

    # cheap: verify the confirmed first entry + chaining still holds
    fr.FIRST_ENTRY_OFFSET   # 11_727_784 (reference disc eeuz.fea)

    # decompress one entry, byte-exact consumed count (slow-ish -- feeds
    # byte-by-byte until eof; fine for spot checks, NOT for a full-file
    # scan -- enumerate_entries() below uses a faster window-based method
    # with the same plausibility guard map_compressed_reader.py uses)
    raw, consumed = fr.decompress_entry_exact(path, offset)

    # fast, practical full(or partial)-file enumeration with automatic
    # gap-skipping (BRUTE-FORCE fallback for the uncracked directory --
    # see enumerate_entries()'s docstring for validated coverage numbers)
    entries, gaps = fr.enumerate_entries(path, start=fr.FIRST_ENTRY_OFFSET,
                                          end=None, max_entries=None)

    # scan a batch of (offset, declen, complen) entries (as returned by
    # enumerate_entries) for the multi-language name-table pattern
    hits = fr.scan_names(path, entries)   # [{"offset":..., "names": [(id,name),...]}, ...]
"""

import struct
import zlib


HEADER_MAGIC = b"(*$SIEMENS&^)\x00\x00\x00"

# Confirmed on the reference disc's eeuz.fea (~553MB, EEU v17 dataset).
FIRST_ENTRY_OFFSET = 11_727_784
FIRST_ENTRY_DECLEN = 72
FIRST_ENTRY_COMPLEN = 40


def read_header(path):
    with open(path, "rb") as f:
        data = f.read(96)
    assert data[:16] == HEADER_MAGIC, f"unexpected magic {data[:16]!r}"
    return {
        "magic": data[0:16],
        "copyright": data[16:32],
        "format_version": data[32:48],
        "data_version": data[48:64],
        "sub_version": data[64:80],
    }


def _is_zlib_header(b0, b1):
    return (b0 & 0x0F) == 8 and ((b0 * 256 + b1) % 31) == 0


def _plausible(declen, consumed):
    """Same compression-ratio sanity guard map_compressed_reader.py's
    find_first_tile() uses -- rejects byte sequences that superficially
    decompress-to-eof but would imply an absurd compression ratio."""
    return consumed <= declen * 1.3 + 32


def decompress_entry_window(f, offset, window=2_000_000):
    """Fast entry decompression using a single bounded read + decompressobj
    (same technique as map_compressed_reader.decompress_tile()). Returns
    (raw, consumed) or None if offset isn't a real, plausible zlib entry.
    `f` must already be open in binary mode; this seeks it."""
    f.seek(offset)
    chunk = f.read(window)
    if len(chunk) < 2 or not _is_zlib_header(chunk[0], chunk[1]):
        return None
    do = zlib.decompressobj()
    try:
        out = do.decompress(chunk)
    except zlib.error:
        return None
    if not do.eof:
        return None
    consumed = window - len(do.unused_data)
    if not _plausible(len(out), consumed):
        return None
    return out, consumed


def decompress_entry_exact(path, offset, max_bytes=5000):
    """Byte-exact consumed-length decompression by feeding growing prefixes
    until zlib reports eof -- slower than decompress_entry_window() but
    immune to any window-based buffering quirk (map_compressed_reader.py
    documents a ~13% unreliable-`consumed` rate for MAP_COMPRESSED tiles
    with the window method; this session did NOT find that quirk on .fea
    but this function exists for spot-check validation). Returns
    (raw, consumed_exact)."""
    with open(path, "rb") as f:
        f.seek(offset)
        chunk = f.read(max_bytes)
    for i in range(1, len(chunk) + 1):
        do = zlib.decompressobj()
        try:
            out = do.decompress(chunk[:i])
        except zlib.error:
            continue
        if do.eof:
            return out, i - len(do.unused_data)
    raise RuntimeError(f"entry at {offset} did not terminate within {max_bytes} bytes")


def find_next_entry(f, start, search_window=8192):
    """Starting at absolute file offset `start` (which may or may not itself
    be a valid zlib entry), find the next real, plausible zlib entry at or
    after `start`, scanning up to `search_window` bytes. Returns
    (offset, declen, complen) or None. This is the practical workaround for
    the non-zlib "gaps" documented in the module docstring -- NOT a decode
    of what the gap bytes are, just a way to keep enumerating past one.

    IMPORTANT (found this session): most gaps are small (tens to a few
    hundred bytes -- see module docstring), but at least one gap on the
    reference disc is HUGE: file offset 306,299,567 to 311,300,723 (exactly
    5,001,156 bytes = 416,763 * 12 + 0) is itself ANOTHER instance of the
    same 12-byte-record directory-table structure documented for the
    byte-80 directory region (see DIRECTORY REGION section above) -- i.e.
    eeuz.fea embeds MULTIPLE directory-table-shaped regions throughout the
    payload, not just one at the very front. A small `search_window` (the
    8192 default, fine for the common small gaps) will return None here and
    silently look like "no more entries" rather than "there's a 5MB
    non-payload region ahead" -- `enumerate_entries()` below escalates
    through progressively larger windows specifically to survive this."""
    f.seek(start)
    data = f.read(search_window + 2_000_000)  # extra room for decompression window
    limit = min(search_window, len(data) - 1)
    for i in range(limit):
        if not _is_zlib_header(data[i], data[i + 1]):
            continue
        do = zlib.decompressobj()
        try:
            out = do.decompress(data[i:i + 2_000_000])
        except zlib.error:
            continue
        if not do.eof:
            continue
        consumed = 2_000_000 - len(do.unused_data)
        if _plausible(len(out), consumed):
            return start + i, len(out), consumed
    return None


# Escalating window sizes find_next_entry_escalating() tries in order. The
# largest (25MB) comfortably covers the biggest confirmed embedded
# directory-table region found this session (~5MB) with margin to spare.
_ESCALATING_WINDOWS = (8192, 65536, 1_000_000, 6_000_000, 25_000_000)


def find_next_entry_escalating(f, start, windows=_ESCALATING_WINDOWS):
    """Like find_next_entry(), but retries with progressively larger
    `search_window` values (see `_ESCALATING_WINDOWS`) instead of giving up
    after one small scan -- needed because at least one confirmed gap on
    the reference disc is ~5MB (another embedded directory-table region,
    see find_next_entry()'s docstring), far larger than the small gaps
    (tens to hundreds of bytes) that are common elsewhere. Cheap in the
    common case (the small window succeeds immediately for ordinary gaps);
    only pays the larger scan cost on genuinely large non-payload regions."""
    for w in windows:
        result = find_next_entry(f, start, w)
        if result is not None:
            return result
    return None


def enumerate_entries(path, start=FIRST_ENTRY_OFFSET, end=None, max_entries=None,
                       gap_search_window=None, progress_every=None):
    """BRUTE-FORCE (but efficient) enumeration of every real zlib entry from
    `start` to `end` (default: EOF), tolerating the non-zlib gaps documented
    above by falling back to find_next_entry() whenever the expected
    back-to-back offset isn't itself a valid entry. This is the practical
    fallback deliverable for "enumerate entries" since the directory region
    itself remains uncracked (see module docstring, OPEN PROBLEMS #2).

    Returns (entries, gaps):
      entries: [(offset, declen, complen), ...] in file order
      gaps:    [(prev_entry_end_offset, next_entry_offset, gap_len), ...]

    VALIDATED this session: run on the first ~880KB of real payload on the
    reference disc's eeuz.fea, this recovered 4,036 entries chained
    back-to-back (zero gap) plus correctly jumped a genuine 114-byte gap to
    resume at entry 4,037 -- i.e. it does not stop or silently skip data at
    a gap, unlike a naive back-to-back-only chain walker.
    Performance note: gap recovery does a bounded local re-scan (cheap) only
    when needed; the common case (back-to-back, no gap) is a single seek+
    read+decompress per entry, same cost as map_compressed_reader.py's
    tile-walking functions.

    IMPORTANT correction (found later the same session, via a full-file
    run): gaps are NOT always small. File offset 306,299,567-311,300,723
    (exactly 5,001,156 = 416,763*12 bytes) is itself ANOTHER embedded
    12-byte-record directory-table region (see the module's DIRECTORY
    REGION section) sitting in the middle of the payload -- with the small
    default `gap_search_window` (8192), `find_next_entry()` returns None
    there and this function stops SILENTLY, as if it had reached the true
    end of readable data, when 245MB of real payload (~45% of the file)
    still remained past that point. A full run with the small default
    window reached only 507,680 entries (offset 306,299,567, 55.4% of the
    file) before stopping this way. `gap_search_window=None` (the default)
    now uses `find_next_entry_escalating()` instead of a single fixed
    window, which DOES survive this specific gap (confirmed: the next real
    entry after it is at file offset 311,300,723, declen 72 -- the same
    declen as the very first entry in the whole file, consistent with each
    such section starting with a similar small canonical record). Pass an
    explicit integer for `gap_search_window` to force the old
    single-fixed-window behavior (faster, but will silently stop early if
    it meets another large embedded directory region -- NOT recommended
    for a full-file run; only one ~5MB instance is confirmed so far but
    there is no reason to assume it's the only one in the file).
    """
    import os
    if end is None:
        end = os.path.getsize(path)

    entries = []
    gaps = []
    offset = start
    f = open(path, "rb")
    try:
        while offset < end:
            if max_entries is not None and len(entries) >= max_entries:
                break
            result = decompress_entry_window(f, offset)
            if result is None:
                if gap_search_window is None:
                    nxt = find_next_entry_escalating(f, offset)
                else:
                    nxt = find_next_entry(f, offset, gap_search_window)
                if nxt is None:
                    break
                next_offset, declen, complen = nxt
                gaps.append((offset, next_offset, next_offset - offset))
                offset = next_offset
                entries.append((offset, declen, complen))
                offset += complen
                continue
            out, consumed = result
            entries.append((offset, len(out), consumed))
            offset += consumed
            if progress_every and len(entries) % progress_every == 0:
                print(f"  ...{len(entries)} entries, at file offset {offset}")
    finally:
        f.close()
    return entries, gaps


# ---------------------------------------------------------------------------
# Name-table records: [1-byte id][1-byte utf8 len][utf8 bytes], repeated.
# ---------------------------------------------------------------------------

def _try_parse_name_list(raw, start_pos, max_names=80):
    """Attempt to parse a run of [id][len][utf8] entries starting at
    start_pos. Returns (names, end_pos) where names is a list of
    (id, str); stops at the first entry that fails to decode as plausible
    text, or after max_names. Returns ([], start_pos) if nothing parses."""
    names = []
    pos = start_pos
    n = len(raw)
    while pos + 2 <= n and len(names) < max_names:
        lid = raw[pos]
        slen = raw[pos + 1]
        if slen == 0 or pos + 2 + slen > n:
            break
        chunk = raw[pos + 2:pos + 2 + slen]
        try:
            s = chunk.decode("utf-8")
        except UnicodeDecodeError:
            break
        if not s.isprintable():
            break
        names.append((lid, s))
        pos += 2 + slen
    return names, pos


def scan_entry_for_names(raw, min_names=3):
    """Scan one decompressed .fea entry's raw bytes for an embedded
    multi-language name table (see module docstring). Tries every byte
    offset (cheap -- entries are small) and keeps the longest run of
    successfully-parsed names found anywhere in the entry. Returns a list
    of (lang_id, name) tuples (possibly empty) for the best run found with
    at least `min_names` entries."""
    best = []
    n = len(raw)
    for pos in range(n - 2):
        if raw[pos + 1] == 0 or pos + 2 + raw[pos + 1] > n:
            continue
        names, _end = _try_parse_name_list(raw, pos, max_names=80)
        if len(names) > len(best):
            best = names
    return best if len(best) >= min_names else []


def scan_names(path, entries, min_names=3):
    """Given a list of (offset, declen, complen) entries (e.g. from
    enumerate_entries()), decompress each and look for an embedded
    multi-language name table. Returns
        [{"offset": int, "declen": int, "names": [(id, str), ...]}, ...]
    for every entry where one was found (min_names+ languages)."""
    hits = []
    with open(path, "rb") as f:
        for offset, declen, complen in entries:
            f.seek(offset)
            try:
                raw = zlib.decompress(f.read(complen))
            except zlib.error:
                continue
            names = scan_entry_for_names(raw, min_names=min_names)
            if names:
                hits.append({"offset": offset, "declen": declen, "names": names})
    return hits


# ---------------------------------------------------------------------------
# Directory-table index records: (offset, declen, complen) big-endian
# triples -- see module docstring "LATER SESSION: directory RECORD FORMAT
# CRACKED" section for the full validation writeup (this is NOT a
# coordinate/MapRect mechanism -- that hypothesis was tested and refuted;
# this is a keyed offset/length index, most likely hash-table-like).
# ---------------------------------------------------------------------------

# The two directory-table byte ranges located and validated so far (on the
# reference disc's eeuz.fea). At least one more exists further into the
# file (needed to explain why Turku/Trondheim/Oslo's real .fea entries,
# all around file offset ~550MB, are NOT indexed by either table below --
# confirmed absent, not just unfound, via full raw-byte-string search) but
# has not been located -- a future session could find it with an
# escalating-window scan (see find_next_entry_escalating()) starting past
# T2's end, watching for another multi-MB non-zlib gap with the same
# stride-12 self-similarity signature.
KNOWN_DIRECTORY_TABLES = [
    (80, 11_727_784),                # "T1", the main byte-80 directory
    (306_299_567, 311_300_723),      # "T2", embedded mid-payload
]

_MAX_PLAUSIBLE_COMPLEN = 200_000  # generous upper bound; real entries observed up to ~63KB declen


def _index_triple_candidates(rec, filesize):
    """Given a 12-byte candidate directory record, return a list of
    (offset, declen, complen, order_name) candidates under the two field
    orderings observed this session (both big-endian uint32, see module
    docstring): '[offset,declen,complen]' (Mediterranean Sea/Iasi/
    Bratislava/Nisyros's own real index records) and
    '[declen,complen,offset]' (the validated-at-scale dense run at T1
    records 764811-766002). This is a cheap structural pre-filter only
    (offset in file bounds, complen/declen in a sane range) -- it does NOT
    verify against real decompressed content, see verify_index_triple()
    for that. Returns [] if neither ordering looks structurally plausible."""
    if len(rec) != 12:
        return []
    a, b, c = struct.unpack('>3I', rec)
    out = []
    if 0 < a < filesize and 0 < c <= _MAX_PLAUSIBLE_COMPLEN and 0 <= b <= _MAX_PLAUSIBLE_COMPLEN:
        out.append((a, b, c, "offset_declen_complen"))
    if 0 < c < filesize and 0 <= a <= _MAX_PLAUSIBLE_COMPLEN and 0 < b <= _MAX_PLAUSIBLE_COMPLEN:
        out.append((c, a, b, "declen_complen_offset"))
    return out


def verify_index_triple(f, rec, filesize):
    """Like _index_triple_candidates(), but also verifies each structural
    candidate by actually decompressing at the claimed offset and checking
    an EXACT declen/complen match (not just "looks like a zlib header") --
    the same rigor used for this module's scale validation (84.7% on the
    dense reference run, 29.6% on a random whole-T1 sample, see module
    docstring). `f` must already be open in binary mode. Returns
    (offset, declen, complen, order_name) for the first ordering that
    verifies, or None."""
    for offset, declen, complen, order in _index_triple_candidates(rec, filesize):
        f.seek(offset)
        chunk = f.read(complen + 16)
        if len(chunk) < 2 or not _is_zlib_header(chunk[0], chunk[1]):
            continue
        do = zlib.decompressobj()
        try:
            out = do.decompress(chunk)
        except zlib.error:
            continue
        consumed = complen + 16 - len(do.unused_data)
        if do.eof and len(out) == declen and consumed == complen:
            return offset, declen, complen, order
    return None


def decode_directory_table(path, table_start, table_end, filesize=None):
    """Decode a directory-table byte range (see KNOWN_DIRECTORY_TABLES) into
    verified (offset, declen, complen) index records, reading 12-byte
    records aligned to `table_start` (the naive zero-phase grid) and trying
    both known field orderings at each position (see verify_index_triple()).

    NOT exhaustive/100% recall -- see module docstring for measured coverage
    (2.7%-84.7% depending on which part of the table, generally higher
    toward the end of T1) and for the specific, confirmed counter-example
    (Mediterranean Sea's own real index record sits 8 bytes off this
    zero-phase grid) showing a minority of genuine records use a different
    byte PHASE not searched here -- treat a record this function does NOT
    verify as "not decoded", not "not present". This is a research/spot-
    check tool, not a certified complete index.

    Returns a list of dicts: {"table_pos": int (byte offset within the
    table), "offset": int, "declen": int, "complen": int, "order": str}."""
    if filesize is None:
        import os
        filesize = os.path.getsize(path)
    with open(path, "rb") as f:
        f.seek(table_start)
        body = f.read(table_end - table_start)
        results = []
        for pos in range(0, len(body) - 11, 12):
            rec = body[pos:pos + 12]
            verified = verify_index_triple(f, rec, filesize)
            if verified is not None:
                offset, declen, complen, order = verified
                results.append({
                    "table_pos": pos, "offset": offset,
                    "declen": declen, "complen": complen, "order": order,
                })
    return results


def find_index_record_for_offset(path, target_offset, tables=None):
    """Search known directory table(s) (default: KNOWN_DIRECTORY_TABLES) for
    a literal, byte-adjacent (offset, declen, complen) triple matching
    `target_offset` exactly, in EITHER field ordering, at ANY byte
    alignment (not just the 12-byte zero-phase grid -- this is the method
    that found Mediterranean Sea/Iasi/Bratislava/Nisyros's real index
    records, two of which are NOT phase-aligned to their table's start).
    `declen`/`complen` are not known in advance here, so this only confirms
    the OFFSET field's position and reads whatever the other two fields at
    the matching position happen to be -- caller should cross-check those
    against a real decompression (see verify_index_triple) if it matters.

    Returns a list of {"table_range": (start,end), "table_pos": int,
    "offset": int, "field_a": int, "field_b": int} dicts (one per raw
    byte-string hit whose neighboring 8 bytes are available), or [] if
    `target_offset` doesn't appear in either table at all -- which IS a
    real, meaningful negative result on this reference disc for entries
    around file offset ~550MB (Turku/Trondheim/Oslo), consistent with at
    least one more, unlocated directory table existing further into the
    file (see module docstring)."""
    if tables is None:
        tables = KNOWN_DIRECTORY_TABLES
    needle = struct.pack('>I', target_offset)
    hits = []
    with open(path, "rb") as f:
        for start, end in tables:
            f.seek(start)
            body = f.read(end - start)
            idx = body.find(needle)
            while idx != -1:
                # try both "offset first" and "offset last" neighbor reads
                if idx + 12 <= len(body):
                    a, b = struct.unpack('>2I', body[idx + 4:idx + 12])
                    hits.append({"table_range": (start, end), "table_pos": idx,
                                 "offset": target_offset, "field_a": a, "field_b": b,
                                 "order_guess": "offset_first"})
                if idx - 8 >= 0:
                    a, b = struct.unpack('>2I', body[idx - 8:idx])
                    hits.append({"table_range": (start, end), "table_pos": idx - 8,
                                 "offset": target_offset, "field_a": a, "field_b": b,
                                 "order_guess": "offset_last"})
                idx = body.find(needle, idx + 1)
    return hits
