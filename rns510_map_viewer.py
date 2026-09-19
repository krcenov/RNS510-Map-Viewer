"""
rns510_map_viewer.py -- read-only tkinter GUI that renders the decoded road
network AND real road/city names from a VW RNS510 nav map ISO, styled like a
light 2D "Google Maps but simple" view rather than the unit's own dark
night-mode UI, to visually validate the reverse-engineered MAP_COMPRESSED
tile/geometry format (research/map_compressed_reader.py), the road-naming
join (research/road_naming.py) and the city catalog (research/city_reader.py)
all at once, as an actually-usable map rather than raw unlabeled lines.

This is a SEPARATE tool from rns510_gui.py / rns510_core.py (the map
EDITING tool) -- it never writes anything back to the ISO. It reuses:
  - rns510_iso.open_tolerant() to read the ISO (same as the editor).
  - rns510_core.MapProject's eeu.il/eeu.rd name search, for "search by
    place/road name" (imported, not duplicated) -- one half of the unified
    search box (see below).
  - rns510_gui.BackgroundTask, so long operations (extracting a tile layer,
    building its geo-index, decoding nearby tiles, rebuilding the road-name
    index for a new area) run off the Tk main thread, same pattern as the
    editor GUI.
  - research/map_compressed_reader.py's read_directory() / build_geo_index()
    / decode_features() to locate and decode MAP_COMPRESSED tiles
    (eeuz.mg2/mg3/mg4/mp0).
  - research/road_naming.py's RdCache/name_features()/summarize_named_ranges()
    to attach real eeu.rd road names to decoded tile geometry.
  - research/city_reader.py's CtyCache/search_cty() for city/town labels and
    the other half of the unified search box.

Core logic (MapData class, viewport/bbox math, label-placement decisions) is
plain Python with no GUI dependency, so it can be exercised directly by a
non-GUI test script (test_map_viewer.py) against the real ISO.

Depends on numpy (already required) and, as of README §10 "v17 -> v18",
Pillow (PIL) -- the road-point dots and connected-roads lines are rasterized
into one Pillow image per redraw and shown as a single canvas.create_image()
item, instead of tens of thousands of individual canvas.create_oval()/
create_line() items (see App._redraw()'s own docstring/comments for the full
rationale and before/after numbers). `py -m pip install Pillow` if missing.

Run with:
    py rns510_map_viewer.py

Quick demo: File > Open Map ISO..., then type "TIRANE" (or "TIRANA") in the
search box and double-click the "[City]" result -- this centers on a
previously-validated real city (README §3.8) and loads enough tiles around
it to show labeled roads converging on a labeled city center. Panning/
zooming from there triggers loading more tiles for the new view in the
background.

============================================================================
What changed vs. the v1 raw-lines viewer (see README §10 for full details)
============================================================================
1. Dynamic pan/zoom tile loading: MapData.ensure_area_loaded() replaces the
   old fixed "K nearest tiles, loaded once" model. Tiles are decoded once
   and cached forever, per layer, in MapData.tile_caches; MapData.covered_bbox
   / covered_layers track the (padded) area and the set of layers currently
   guaranteed loaded, and the GUI only triggers a new background load when
   the visible viewport would extend outside it OR the set of available
   layers has changed (debounced via Tk's `after`, see
   App._schedule_viewport_check).
2. Road name labels: every decoded feature is run through
   road_naming.name_features() against a road_naming.RdCache built once per
   ISO load and re-queried (not re-read from disk) per visible area (see
   MapData.rd_index_for_bbox()) -- this is the caching layer road_naming.py's
   own docstring flagged as missing for interactive use.
3. City/town labels: city_reader.CtyCache loads the whole 939,351-record
   eeu.cty into memory once as numpy arrays; each redraw queries it for
   cities intersecting the visible viewport above a zoom-dependent
   bounding-box-area threshold (see city_min_area_for_scale()).
4. Unified search: MapData.search_combined() merges rns510_core.MapProject's
   road search with city_reader's city search into one result list, tagged
   "[Road]"/"[City]"; picking a city result centers and zooms to roughly
   fit its bounding box, picking a road result behaves like the old jump.
5. Light "Google Maps but 2D" theme: white/light-gray background, gray
   road lines (thicker/darker for longer matched-name runs, a crude
   importance proxy -- see the module docstring caveat that no reliable
   road-class field exists), dark labels, city names bolder/larger than
   road names, a distinct red pin-style marker for the current center.
6. [v3, SUPERSEDED -- see 7] For one session this app auto-picked a SINGLE
   tile layer (mg4/mg3/mg2/mg1/mp0) from the current view scale via
   choose_layer_for_scale()/SCALE_LAYER_THRESHOLDS. Removed in v5 (see 7
   below) at explicit user request in favor of showing every layer's points
   at once -- those names are gone from this module now; see README §10
   "v4 -> v5" for the full rationale.
7. [v5, SUPERSEDED -- see 8] For one session the render/load path pooled
   EVERY currently-available layer (MapData.available_layers()) regardless
   of the current view scale, all the time. Replaced in v6 (see 8 below) at
   explicit user request in favor of scale-stacking -- see README §10
   "v4 -> v5" for the full rationale that motivated pooling multiple
   generalization levels' points together safely (still true and still the
   reason v6's stacking is safe too), and "v5 -> v6" for why unconditional
   pooling was then narrowed to be scale-aware again.
8. Cumulative scale-stacked layers (this session, v6): the render/load path
   again depends on the current view scale, but additively, not via a
   single-winner swap: `layers_for_scale(scale, available_layers())` returns
   `FAST_LAYERS[:n]` for a scale-dependent `n` that only grows as the user
   zooms in (starting at exactly `["mg4"]` fully zoomed out), plus `mp0`
   once BOTH the scale is high enough AND its background geo-index has
   finished (App._start_heavy_layer_load, unchanged). `ensure_area_loaded()`
   takes the current `scale` again (removed in v4/v5, reinstated) and pools
   tiles/features only from that cumulative set, not every available layer
   unconditionally. This keeps the "pooling multiple generalization levels
   is visually safe" property from v4/v5 (roads are still unconnected
   per-vertex dots, see "v3 -> v4" below) while capping the worst-case
   per-redraw point/oval count at whatever the CURRENT zoom actually needs,
   rather than paying the full 5-layer cost even when fully zoomed out. See
   README §10 "v5 -> v6" for the chosen thresholds' justification and real
   point-count/timing measurements at increasing scale.
9. Click-to-identify points (this session, v7): every rendered point can now
   be right-clicked (App._on_point_pick, bound to <Button-3> -- left-click
   is untouched, still pure pan, see _on_drag_start/_on_drag_move/
   _on_drag_end) to find the nearest currently-rendered point within
   POINT_PICK_RADIUS_PX screen pixels (find_nearest_point(), a GUI-free
   function) and record its full identifying info: layer, tile_id, the
   tile's own file offset/decompressed length, the feature's index within
   that TILE's own decoded feature list, the feature's byte offset within
   the decompressed tile, the point's index within that feature's own
   "points" list, decoded (lon, lat), and any road_naming-matched name.
   MapData.decode_tile() now tags every decoded feature dict with
   "layer"/"tile_id"/"tile_offset"/"tile_declen"/"feature_index" so this
   survives flat pooling across layers/tiles and name_features()'s
   dict-copy (road_naming.name_features() copies the input dict with
   `dict(feat)`, so any extra keys already on a feature ride along
   unchanged). Each pick is numbered, drawn on the canvas as a small ring +
   number (App._redraw()'s new picked-points pass, positioned in (lon,lat)
   so marks stay correctly placed across pan/zoom), and appended as a
   plain-text row to a new selectable/copyable `tk.Text` panel
   (App.points_text) below the map, so the user can read/copy the exact
   identifying info to report which real points are actually connected
   (the still-open topology-table problem, README §3.6) in a later
   session. A "Clear points" button resets the running list. This is a
   pure ADDITION -- see README §10 "v6 -> v7" for the full design
   rationale, the exact binding choice, and real-ISO test evidence that a
   known point is picked correctly.
10. Connected-roads rendering, checked by default (this session, v9 -> v10):
    a "Draw connected roads" checkbox (App.connected_roads_var, default
    CHECKED) makes _redraw() draw real canvas.create_line() edges -- from
    map_compressed_reader.resolve_topology_adjacency()'s just-landed,
    ground-truth-validated node-id<->coordinate mapping (README §3.6) --
    for any feature whose resolved confidence is "high", replacing the
    v3->v4 per-vertex dots for that specific feature only; every other
    feature (confidence not high, or not yet resolved) still renders as
    dots, unchanged. Unchecking the box reproduces the exact pre-existing
    dot-only behavior. Adjacency is resolved once per tile and cached in
    MapData.topo_caches (mirroring tile_caches' own cache-forever policy),
    computed inline during decode_tile() for a newly-decoded tile
    (MapData.decode_tile(..., want_adjacency=True), no extra decode pass)
    or lazily via MapData.get_tile_adjacency() for a tile decoded before
    connected-roads mode needed it. See README §10 "v9 -> v10" for the
    full design, real ground-truth canvas-rendering evidence, and
    measured performance numbers.
11. Address entry / letter-keyboard (this session, v11 -> v12): the "NAV"
    bezel button now opens AddressEntryDialog (Country/City/Street/Number,
    reference photo #1), each of Country/City/Street opening SpellerDialog
    (reference photo #2) -- a letter-by-letter keyboard whose keys are
    LIVE enabled/disabled per keystroke from real cracked data: Country/
    City via city_reader.PrefixNameIndex (exact, over eeu.ctr/eeu.cty),
    Street via the real `.rt` character-trie (road_index_reader.rt_root()/
    rt_enabled_next_chars(), fail-safe: an uncertain/incomplete walk never
    disables a letter). "Start" resolves the typed address via
    MapData.resolve_address() (reusing MapProject.search()/CtyCache.search()
    -- NOT the tries, whose real coverage is only partial) and jumps the
    map via the existing App._jump_to(). See README §10 "v11 -> v12" for
    the full root-finding methodology/validation, the accented-character
    and forest-not-single-tree findings, and a real thread-safety bug this
    feature's own end-to-end test found and fixed in `_jump_to()` itself.
12. Address entry hosted as an embedded screen PANEL, not a separate OS
    window (this session, v12 -> v13): AddressEntryDialog/SpellerDialog
    (item 11 above) are now `tk.Frame` panels parented directly to
    `App.screen_frame` -- the SAME glossy-black inset that otherwise only
    ever shows `canvas_frame`/`status_bar` -- shown via
    `.place(relx=0, rely=0, relwidth=1, relheight=1)` + `.lift()` and
    dismissed via plain `.destroy()`, instead of `tk.Toplevel` subclasses
    that opened as separate, independently-floating OS windows. Prompted
    by the user's explicit correction after seeing a screenshot: "this
    shouldnt be a new window, instead it should show on the nav screen" --
    a real head unit has exactly one screen, and UI states replace each
    other WITHIN it. Pure presentation-layer change: none of item 11's
    underlying logic (root-finding, live per-letter narrowing,
    resolve_address()) was touched. See README §10 "v12 -> v13" for real
    test evidence (zero new tk.Toplevel instances anywhere in the widget
    tree at any point in the flow, map center/zoom/pan/feature-count
    proven unchanged across showing/dismissing these panels, and the full
    NAV -> City speller -> Start -> real-Sofia-jump flow re-verified
    working unchanged through the new embedded presentation).
13. Country -> City -> Street SCOPING, matching real nav UX (this session,
    v13 -> v14): items 11/12's City and Street spellers used to search ALL
    939,351 `eeu.cty` records / the WHOLE global `.rt` trie regardless of
    what Country/City was already selected. Prompted by the user's explicit
    correction: "the ways that real nav works is you select a country then
    you select a city only from that country then you select an adress
    only from that city sooo, dont display all cities and all streets."
    Country -> City is scoped via a newly-cracked `eeu.cty` field
    (`city_reader.build_country_tag_map()` -- bytes[57:59], previously
    documented as "candidate coarser country/region tag, unresolved" in
    README §3.8, now confirmed to partition the whole file into exactly the
    35 real `eeu.ctr` countries, validated against 17 known real cities
    across the Balkans/Central Europe). City -> Street is scoped via the
    selected city's own `eeu.cty` bounding box (padded, `CITY_STREET_PAD_DEG`)
    intersected against real `eeu.rd` coordinates (`MapData.
    street_names_for_city()`, reusing the already-built `RdCache`) -- an
    exact, always-correct name list, actually BETTER than the old global
    `.rt`-trie narrowing (which only has partial forest coverage). Required
    order, matching the real unit: City can't be opened before a valid
    Country is selected, Street can't be opened before City has text (see
    `AddressEntryDialog._open_speller()`); Street gracefully falls back to
    the old global `.rt`-trie narrowing if the typed city doesn't resolve to
    a real place. See README §10 "v13 -> v14" for the full crack
    methodology, validation numbers, and real-ISO test evidence.
14. Street's remaining fallback made EXHAUSTIVE, closing the last
    documented coverage gap (this session, v14 -> v15): item 13's
    "gracefully falls back to the old global `.rt`-trie narrowing" case
    (a City that doesn't resolve, or resolves with zero nearby `.rd`
    coverage) used to hand off to road_index_reader.rt_enabled_next_chars()
    -- real, but a documented, ~5,100-leaf-string partial forest (README
    S3.7), a tiny fraction of the real street-name universe. MapData.
    street_name_index_global (a lazily-built city_reader.PrefixNameIndex
    over EVERY distinct name in road_naming.RdCache -- i.e. every real
    eeu.rd street name on the whole disc, not just one city's bbox) now
    backs that one remaining fallback instead, so SpellerDialog.
    _backing_index()'s "street" branch (street_name_index_for_city(...)
    or street_name_index_global) NEVER falls through to the `.rt` trie any
    more -- mirroring the exact city_name_index_for_country(...) or
    city_name_index pattern item 13 already established for City.
    road_index_reader.rt_enabled_next_chars()/MapData.
    street_enabled_next_chars() are kept (still directly unit-tested, per
    README S3.7) as a validated, standalone piece of reverse-engineering,
    but are no longer reachable from the live UI's own narrowing path. See
    README S10 "v14 -> v15" for the exhaustiveness proof (a real street
    name confirmed unreachable via the old trie, reachable via the new
    global index), the measured one-time build cost, and the eager-vs-lazy
    load-timing decision.
15. "Hide decode garbage" DEFAULT FLIPPED to unchecked -- the oscillation
    filter is net negative for real dense-urban rendering (this session,
    v15 -> v16). Prompted by the user's own first-hand observation
    (verbatim): "unchecking hide decode garbage is producing more real
    accurate roads then when i enable it, meaning its not usefull and the
    garbage is not actually garbage." A direct, real-ISO, per-named-road
    investigation (not just the old tile-name-match-count benchmark)
    confirmed it: a real Sofia, Bulgaria `mg1` sample (9 tiles) lost 6
    entire real named roads and had 13 more truncated -- including Sofia's
    own ring road, "OKOLOVRASTEN PAT", losing 84.6% of its matched points --
    while the filter removed only 5.74% of raw points. `MapData.
    trim_oscillation` and `App.hide_garbage_var` both now default to
    `False` (filter OFF); checking the box still re-enables the filter
    exactly as before, for inspection/comparison. See README §10
    "v15 -> v16" for the full investigation, including why the old 42/80
    mg4 benchmark could not see this failure mode, real MAX_FEATURE_DRIFT_DEG
    and geo-index-coverage checks that ruled out two OTHER "missing roads"
    hypotheses at Sofia, and current connected-roads confidence numbers.
16. Four user-requested debugging-workflow changes (this session, v16 -> v17):
    (a) road-point dots are now a single, unambiguous red (DOT_COLOR,
    "#d32f2f") instead of the old gray/gold ROAD_COLOR_* shades -- user's
    verbatim request: "make the points red dots not gray ones". (b) dots
    are now drawn for EVERY point even when connected-roads mode (v9 -> v10)
    also draws real lines for a high-confidence feature -- previously a
    high-confidence feature's dots were suppressed once its lines were
    drawn; now both render together, so the raw point data stays visible
    alongside the derived connectivity ("make the dots visible when roads
    are visible also"). (c) connected-roads LINES are now clickable too:
    find_nearest_line_segment()/_iter_high_confidence_edges() (new,
    GUI-free pure functions) do a point-to-segment nearest-edge lookup, and
    App._on_point_pick()'s right-click handler falls back to it whenever a
    click misses every point -- a hit adds BOTH the edge's real endpoints
    as a linked pick pair (App._add_edge_pick(), tagged with each other's
    pick number as "edge_partner" so the picked-points panel/status clearly
    show they came from one specific clicked edge, not two independent
    point-clicks) -- for reporting exactly which two points a specific
    drawn connection joins, to help debug the still-unsolved topology
    resolution (§3.6). (d) layer visibility is now controlled ONLY by the
    "Show layers" checkboxes -- MapData.ensure_area_loaded()/
    App._maybe_reload_viewport() no longer also intersect with
    layers_for_scale()'s scale-dependent cumulative set (the "v5 -> v6"
    model): the pooled set is now exactly available_layers() intersected
    with allowed_layers, independent of the current view scale.
    layers_for_scale()/SCALE_LAYER_THRESHOLDS are UNCHANGED and still real,
    tested, pure functions -- just no longer called to gate rendering.
    mp0 specifically is still only ever pooled once its own background
    geo-index build has actually finished (available_layers() including
    it, unchanged since "v2 -> v3") -- this removes the SCALE gate on top
    of that, not the availability one, so "Open Map ISO" still doesn't
    block on mp0. Known, disclosed tradeoff: this reintroduces the exact
    cost "v5 -> v6" was originally built to avoid -- a heavily zoomed-out
    view with every box checked (including mp0, once ready) now pays mp0's
    full point/redraw cost even far from street level; the user explicitly
    asked for this, for debugging, understanding they can manually uncheck
    heavier layers if a view feels sluggish. See README §10 "v16 -> v17"
    for real test evidence and measured performance impact.

Known v2 limitations (explicit, not oversights) -- see README §10:
  - find_tile_for_coord()/tile_ids_in_bbox() are nearest-anchor/anchor-
    inside-box, not exact tile-boundary containment (no tile extent was
    ever recovered -- see map_compressed_reader.py).
  - Road "importance" styling is a vertex/run-length proxy, not a real
    road-class field (still unresolved, see README §3.1/§8).
  - decode_features() still can't split one rendered chain back into
    per-named-road segments at the geometry level (the topology table that
    would allow this is still uncracked, README §3.6/§8) -- name_features()
    only ATTACHES names to vertex ranges of the geometry as already
    decoded, it doesn't re-cut the polyline.
  - mp0's background-build window (unchanged since v3, its EFFECT changed in
    v5 from "full layer swap" to "additive", and in v6 it's additionally
    gated on the scale being high enough to want mp0 at all -- see
    layers_for_scale()): if the user zooms to street level before mp0's
    background geo-index finishes, they see whatever fast layers
    layers_for_scale() already includes at that scale -- not an error, not
    a block -- and mp0's own points are folded into the SAME view
    automatically once ready (see App._start_heavy_layer_load). In a real
    area that is sparse in every fast layer but only has content in mp0
    (measured directly: a tight ~0.02 degree box around a real Sofia,
    Bulgaria location has 0 tiles in mg1-mg4 but 1 tile/2 features/426
    points in mp0), this can still mean a genuinely blank-looking map for
    the few seconds/tens-of-seconds before mp0 is ready -- see README §10
    for the full writeup.
"""

import math
import os
import shutil
import sys
import tempfile
import time
import tkinter as tk
import zlib
from tkinter import ttk, filedialog, messagebox

import numpy as np
from PIL import Image, ImageDraw, ImageTk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "research"))

import rns510_iso as riso
import rns510_core as core
import map_compressed_reader as mcr
import road_naming as rdn
import city_reader as cty
import road_index_reader as rir
import ctr_reader as ctrr
import flat_compressed_reader as fcr
from rns510_gui import BackgroundTask

APP_TITLE = "RNS510 Map Viewer (read-only)"

LAYER_ISO_PATHS = {
    "mg1": "/DB/EEUZ.MG1",
    "mg2": "/DB/EEUZ.MG2",
    "mg3": "/DB/EEUZ.MG3",
    "mg4": "/DB/EEUZ.MG4",
    "mp0": "/DB/EEUZ.MP0",
}
CTY_ISO_PATH = "/DB/EEU.CTY"

# Address-entry keyboard feature (README §10 "v11 -> v12"): eeuz.rt (street
# name character-trie, research/road_index_reader.py) and eeu.ctr (country
# list, research/ctr_reader.py). eeuz.ct (city tree) is NOT extracted here
# -- the City field's live keyboard narrowing uses city_reader.PrefixNameIndex
# over the already-loaded eeu.cty instead (see MapData.load_address_entry_data()
# docstring for why: ct_root()'s coverage was directly tested and found
# genuinely partial, e.g. "SOFIA" is not reachable from any found shard
# despite being a confirmed real eeuz.cl entry).
RT_ISO_PATH = "/DB/EEUZ.RT"
CTR_ISO_PATH = "/DB/EEU.CTR"

# ---------------------------------------------------------------------------
# Cumulative scale-stacked layer set (README §10, "v5 -> v6") -- replaces the
# old user-facing layer dropdown (gone since v3) AND both the v3 single-
# winner auto-selection (choose_layer_for_scale()/SCALE_LAYER_THRESHOLDS) AND
# the v5 "always pool every available layer regardless of zoom" model. The
# user still never sees a "layer" concept at all, but which layers get
# pooled together now DOES depend on the current view scale again: at
# maximum zoom-out only the coarsest layer (mg4) is included, and finer
# FAST_LAYERS are progressively ADDED (never swapped out) as the user zooms
# in, with mp0 added last once both the scale is high enough and its
# background geo-index has finished -- see layers_for_scale() below and
# MapData.ensure_area_loaded()/App._maybe_reload_viewport().
# ---------------------------------------------------------------------------

# "Fast" layers: cheap enough to extract + geo-index synchronously while the
# user waits for "Open Map ISO" to finish. Measured directly against the
# reference disc this session (build_geo_index() wall-clock time):
#   mg4:  6,110 tiles  -- ~0.3-0.6s
#   mg3: 16,503 tiles  -- ~1s
#   mg2: 34,209 tiles  -- ~2s
#   mg1: 63,996 tiles  -- ~4s
# ~7-8s combined -- comparable to the rd_cache/cty_cache build that already
# happens at open time, so building all four eagerly barely adds to
# perceived startup time. All four are ALWAYS included in the render pool
# (MapData.available_layers()) the instant the ISO finishes loading.
FAST_LAYERS = ["mg4", "mg3", "mg2", "mg1"]  # coarsest -> finest

# The densest/most detailed layer (2.14GB, 194,705 tiles). Its
# build_geo_index() alone measured 34-55s on the reference disc this
# session -- far too slow to block "Open Map ISO" on. App.on_open_iso()
# kicks off MapData.load_heavy_layer() in its OWN background BackgroundTask
# right after the fast layers are ready, so it finishes in parallel with
# the user's first search/pan/zoom. MapData.available_layers() folds "mp0"
# into the render pool the moment MapData.mp0_ready flips True -- until
# then, the pool is just the four fast layers (not an error, not a block --
# see App._start_heavy_layer_load).
HEAVY_LAYER = "mp0"

ALL_LAYERS = FAST_LAYERS + [HEAVY_LAYER]

# Cumulative scale thresholds -- (scale_upper_bound_exclusive, n_fast_layers).
# `scale` is pixels/degree, the same value App.scale already tracks for zoom.
# Reuses the exact boundary VALUES this project already measured and
# validated for v3's single-winner choose_layer_for_scale()/
# SCALE_LAYER_THRESHOLDS (README §10 "v2 -> v3", removed in v4/v5, now
# reinstated for v5 -> v6): those boundaries came from a real per-area
# density comparison at the Sofia, Bulgaria bbox that motivated this whole
# feature (0.1 degree-wide box, README §10) --
#   mg4    141 points
#   mg3    397 points  (2.8x mg4)
#   mg2    952 points  (2.4x mg3)
#   mg1  2,218 points  (2.3x mg2)
#   mp0 11,821 points  (5.3x mg1)
# i.e. each threshold step is a genuine, substantial (>2x, up to >5x for
# mp0) upgrade in real drawn detail, not a cosmetic one, so the same
# boundaries remain a sound place to ADD a layer even though what happens
# at each boundary is now cumulative (add the next layer) rather than a
# single-winner swap. Only the SELECTION RULE changed -- see
# layers_for_scale() below.
SCALE_LAYER_THRESHOLDS = [
    (800.0, 1),      # regional overview: mg4 only
    (2500.0, 2),     # metro-area view: + mg3
    (6000.0, 3),     # city view: + mg2
    (15000.0, 4),    # neighborhood view: + mg1 (all FAST_LAYERS)
]
# scale >= this ("street level"): also stack in mp0, once its background
# geo-index has finished -- see layers_for_scale().
MP0_MIN_SCALE = SCALE_LAYER_THRESHOLDS[-1][0]


def layers_for_scale(scale, available):
    """The CUMULATIVE list of tile layers to pool for the given view scale
    (pixels/degree) -- README §10 "v5 -> v6". Unlike v3's single-winner
    choose_layer_for_scale() (two sessions superseded now), this never
    swaps a coarser layer OUT: it returns FAST_LAYERS[:n] for a
    scale-dependent n that only grows as `scale` increases (see
    SCALE_LAYER_THRESHOLDS above), so at maximum zoom-out this returns
    exactly `["mg4"]` and every zoom-in step ADDS one more, finer FAST_LAYERS
    entry on top of the ones already included. HEAVY_LAYER ("mp0") is
    appended last, and only once BOTH the scale has reached street level
    (`scale >= MP0_MIN_SCALE`) AND it's actually present in `available`
    (i.e. its background geo-index has finished -- see
    MapData.load_heavy_layer()/mp0_ready) -- this never blocks on mp0 or
    requests a layer that hasn't been geo-indexed yet. `available` is
    expected to be MapData.available_layers()'s own return value."""
    n = len(FAST_LAYERS)
    for max_scale, count in SCALE_LAYER_THRESHOLDS:
        if scale < max_scale:
            n = count
            break
    layers = FAST_LAYERS[:n]
    if scale >= MP0_MIN_SCALE and HEAVY_LAYER in available:
        layers = layers + [HEAVY_LAYER]
    return layers


# Initial half-span (degrees) loaded around a freshly-searched/entered
# point, before any pan/zoom-triggered reload happens.
DEFAULT_JUMP_SPAN_DEG = 0.3

# Real-hardware-style discrete zoom levels (README §10 "v17 -> v18", user's
# explicit request): the mouse-wheel zoom steps through this fixed table of
# real-world distances -- matching how the actual RNS510's zoom
# knob/buttons work -- instead of the previous continuous
# `scale *= 1.15`-per-tick zoom. Ordered widest (most zoomed OUT) to
# narrowest (most zoomed IN); `scale_for_zoom_span_m()` converts a span here
# into a `scale` (pixels/degree) value, and `nearest_zoom_level_index()`
# finds the table entry closest to the CURRENT `scale`, so stepping always
# advances exactly one real level regardless of how `self.scale` was last
# set (a discrete step, a jump's fixed default below, or -- in tests -- an
# arbitrary direct assignment).
ZOOM_LEVELS_M = (
    500_000.0, 400_000.0, 300_000.0, 200_000.0, 150_000.0,
    100_000.0, 75_000.0, 50_000.0, 40_000.0, 30_000.0,
    20_000.0, 15_000.0, 10_000.0, 7_500.0, 5_000.0,
    4_000.0, 3_000.0, 2_000.0, 1_500.0, 1_000.0,
    750.0, 500.0, 400.0, 300.0, 200.0,
    150.0, 100.0, 75.0, 50.0, 25.0,
)

# The zoom level a freshly-jumped-to location (search result, address entry
# "Start", etc.) opens at -- user's explicit request ("make the start zoom
# at 5km"), replacing the previous behavior of auto-fitting the scale to
# whatever bounding box the jump's own decoded features happened to have
# (App._initial_scale(), kept below as a general-purpose framing utility --
# still used elsewhere, e.g. by tests that frame a specific ground-truth
# area -- just no longer what a live jump uses for its OWN display scale).
DEFAULT_ZOOM_SPAN_M = 5_000.0

# Standard great-circle-adjacent approximation, meters per degree of
# LATITUDE (longitude's own meters/degree shrinks by cos(lat), already
# handled by project_point()'s own cos(center_lat) factor -- see its
# docstring -- so this single constant, applied to the SAME `scale` value
# project_point() uses for both axes, is enough for both).
METERS_PER_DEGREE_LAT = 111_320.0


def scale_for_zoom_span_m(span_m, width_px, height_px):
    """`scale` (pixels/degree, as project_point()/App.scale use it) such
    that the SMALLER of the canvas's two pixel dimensions spans exactly
    `span_m` real-world meters -- the conversion behind ZOOM_LEVELS_M's
    discrete steps and DEFAULT_ZOOM_SPAN_M. Using the smaller dimension
    keeps the whole named span visible on screen regardless of the
    canvas's own aspect ratio."""
    span_deg = max(span_m, 1e-6) / METERS_PER_DEGREE_LAT
    return max(min(width_px, height_px), 1) / span_deg


def nearest_zoom_level_index(scale, width_px, height_px, levels=ZOOM_LEVELS_M):
    """Index into `levels` (ZOOM_LEVELS_M by default) whose own
    scale_for_zoom_span_m() is closest to the given `scale` -- lets
    App._on_zoom() step exactly one discrete real-world level per wheel
    tick from WHATEVER `self.scale` currently is (a previous discrete step,
    the DEFAULT_ZOOM_SPAN_M a jump opened at, or an arbitrary value a test
    set directly), without needing to separately track "which level am I
    on" as extra mutable state."""
    scale = max(scale, 1e-9)
    best_i, best_diff = 0, None
    for i, span_m in enumerate(levels):
        level_scale = scale_for_zoom_span_m(span_m, width_px, height_px)
        diff = abs(math.log(level_scale) - math.log(scale))
        if best_diff is None or diff < best_diff:
            best_i, best_diff = i, diff
    return best_i

# How far beyond the requested bbox MapData.ensure_area_loaded() loads, as a
# fraction of the requested bbox's own size -- gives the user some pan
# headroom before another background load is triggered. See
# App._maybe_reload_viewport()/MapData.ensure_area_loaded()'s docstrings for
# the full caching-granularity rationale requested by this session's task.
AREA_PAD_FRAC = 0.6

# Margin (degrees) added when rebuilding the road-name index for a new area
# -- kept separate from AREA_PAD_FRAC because the name index is cheap to
# rebuild (see road_naming.RdCache) and a small fixed margin is simpler to
# reason about than a fraction of a possibly-tiny bbox.
RD_INDEX_MARGIN_DEG = 0.05

# City -> Street scoping padding (README §10 "v13 -> v14"): how far beyond a
# selected city's own eeu.cty bounding box (README §3.8) MapData.
# street_names_for_city() looks for real eeu.rd street records when building
# the Address Entry Street field's scoped candidate list. eeu.cty's own
# bounding box is documented (§3.8) as tight/administrative -- it wraps the
# named place's own extent, not necessarily its whole built-up area or the
# streets a resident would consider "in town" -- so a small padding margin is
# added rather than using the bare bbox. 0.15 degrees (~15-17km at this
# dataset's latitudes) was chosen empirically against the real ISO: small
# enough to keep a dense city's own streets from being swamped by a
# neighboring town's, generous enough that a real street just outside the
# tight administrative box (e.g. a residential street in a city's outskirts)
# is still included. Not a hard science -- retune if a future session finds
# a concrete case that needs it.
CITY_STREET_PAD_DEG = 0.15

# Sanity filter, found necessary during this tool's own real-ISO testing
# (see test_map_viewer.py / README §10): map_compressed_reader.py's own
# docs note the "bruteforce"/"bruteforce_unverified" find_tile_anchor()
# methods are less reliable than "structural". MAX_FEATURE_DRIFT_DEG
# discards any decoded feature whose points stray further than this from
# its OWN tile's anchor coordinate before rendering.
MAX_FEATURE_DRIFT_DEG = 3.0

# Click-to-identify a point (README §10 "v6 -> v7"): a right-click within
# this many SCREEN PIXELS of a currently-rendered point picks it -- see
# find_nearest_point() below. 10px is comfortably bigger than the ~1-1.6px
# road dot radius _redraw() draws (so an imprecise click still lands it)
# while still being tight enough not to grab an unrelated nearby point in a
# dense mp0-level view.
POINT_PICK_RADIUS_PX = 10.0

# Click-to-identify a rendered connected-road EDGE (README §10 "v16 -> v17"):
# a right-click that misses every point (see POINT_PICK_RADIUS_PX above)
# falls back to checking whether it landed within this many SCREEN PIXELS of
# a rendered connected-roads canvas.create_line() segment (point-to-segment
# distance, not just distance to either endpoint) -- see
# find_nearest_line_segment() below. Same value as POINT_PICK_RADIUS_PX: a
# line is visually thin (1.0-1.6px), so the same generous pick radius used
# for a dot works just as well for a line, and having one number instead of
# two is simpler for anyone tuning it later.
LINE_PICK_RADIUS_PX = POINT_PICK_RADIUS_PX

# Header row for the picked-points text panel -- re-inserted by
# App.on_clear_points() after clearing, so the panel always shows the
# column layout even with zero picks. Plain "|"-separated key=value-ish
# columns, not a real table widget, so it's trivially copy/pasteable as
# plain text into a chat message.
POINTS_PANEL_HEADER = (
    "#  | layer | tile_id | tile_offset | feature_idx | feature_byte_off | point_idx | lon        | lat       | name\n"
    + "-" * 110 + "\n"
)

# ---------------------------------------------------------------------------
# Visual theme -- restyled (this session) to evoke the REAL RNS510 unit's
# daytime 2D map screen (warm cream background, gold major roads) rather
# than a generic "Google Maps" light theme, per reference photos taken of a
# real unit (see the task brief this session started from). Still a plain
# top-down 2D rendering -- no attempt to fake the unit's dark night mode or
# its 3D perspective mode, both out of scope.
# ---------------------------------------------------------------------------
BG_COLOR = "#f1e9d2"             # warm cream/tan -- real unit's daytime 2D map bg
ROAD_COLOR_MAJOR = "#cf9a1a"     # warm yellow/gold -- used for connected-roads LINES of longer/named runs
ROAD_COLOR_MINOR = "#b7b0a0"     # thin gray-white -- kept for any remaining line-color use (see below)
ROAD_COLOR_UNNAMED = "#d6cfba"   # unmatched/unlabeled connecting-roads LINES, barely visible
# Road-point DOT color (README §10 "v16 -> v17"): every decoded vertex is
# drawn as a small canvas.create_oval -- previously filled with one of the
# ROAD_COLOR_* shades above (grayish/gold, per the light "Google Maps"
# theme), which the user found hard to see against the cream background.
# User's explicit request (verbatim): "make the points red dots not gray
# ones". A single, unambiguous red (Material Design "red 700") is used for
# EVERY point dot regardless of layer/importance -- this only changes DOT
# fill color; connected-roads LINES (see "v9 -> v10") still use
# ROAD_COLOR_MAJOR/ROAD_COLOR_UNNAMED by named/unnamed status, unaffected.
DOT_COLOR = "#d32f2f"
ROAD_LABEL_COLOR = "#3a2f18"
CITY_DOT_COLOR = "#20304a"       # dark navy square markers (photo #4 style, adapted to light bg)
CITY_LABEL_COLOR = "#141c28"
MARKER_FILL = "#e8821b"          # orange current-position marker (photos #3/#4)
MARKER_OUTLINE = "#8a4c0a"
PICK_MARK_COLOR = "#c2185b"      # magenta ring/number for click-to-identify picks (v6 -> v7) -- distinct
PICK_MARK_HALO = "#ffffff"       # from every other on-map color (gold roads, navy cities, orange marker)

# --- Hardware bezel / physical-unit chrome (photo #1) ----------------------
BEZEL_COLOR = "#26282c"          # dark gunmetal/black plastic
BEZEL_BUTTON_BG = "#3a3d42"
BEZEL_BUTTON_FG = "#e8e8e8"
BEZEL_BUTTON_ACTIVE_BG = "#4c5058"
SCREEN_BORDER_COLOR = "#050505"  # glossy black inset frame around the screen
KNOB_FACE_COLOR = "#3a3d42"
KNOB_RIM_COLOR = "#0e0f11"
KNOB_HIGHLIGHT_COLOR = "#5a5e66"

# --- On-screen software chrome (photos #2/#3/#4) ----------------------------
STATUS_BAR_BG = "#12151b"        # dark segmented bottom bar
STATUS_BAR_FG = "#d8dde3"
STATUS_BADGE_BG = "#33445a"      # "2D" mode badge
STATUS_DIVIDER_COLOR = "#2a2f38"
SEARCH_PANEL_BG = "#1c3145"      # dark blue-gray gradient-ish destination-entry bg
SEARCH_PANEL_FG = "#dbe4ec"
SEARCH_PANEL_FG_DIM = "#8fa2b5"
TEAL_ACCENT = "#2f7f8f"          # teal/blue "Options"/"Curr. pos." style buttons
TEAL_ACCENT_ACTIVE = "#3d9cae"
TEAL_ACCENT_FG = "#f2fbfd"

MIN_LABEL_PIXEL_LEN = 26     # don't label a named run shorter than this on screen
LABEL_DEDUP_PX = 65          # don't draw a second same-name label within this many px
MAX_CITY_LABELS = 40
BIG_CITY_AREA_DEG2 = 0.02    # bbox area above which a city gets the bolder/larger label

# Sanity upper bound on a city's bbox area for DISPLAY ranking purposes --
# see city_reader.CtyCache.query()'s `max_area` docstring: a handful of real
# eeu.cty records (so far only seen among postal-code sub-entries) have an
# implausibly huge bounding box (tens of degrees) that would otherwise win
# every "rank by area" low-zoom label slot ahead of the real large cities
# actually in view. No genuine city/admin area in this dataset was observed
# anywhere near this large (Timisoara, one of the biggest seen, is ~0.1).
CITY_MAX_AREA_DEG2 = 2.0

# Zoom-dependent city importance threshold: (scale_upper_bound, min_bbox_area_deg2).
# scale is pixels/degree -- larger scale means more zoomed in, so the
# threshold shrinks as you zoom in, surfacing progressively smaller places,
# mirroring how a real map's label density works. Calibrated against this
# project's own already-validated eeu.cty bbox areas (README §3.8): Tirana's
# real bbox area is ~0.038 deg^2, Timisoara's ~0.10, a small named locality's
# ("GUITGIA, LAMPEDUSA E LINOSA") is ~0.00014 -- an EARLIER version of this
# table used a first threshold of 0.5 deg^2, which is bigger than any real
# city in this dataset and silently hid every city label (found via this
# session's own real-ISO test, see test_map_viewer.py / README §10); these
# numbers keep capital-city-sized entries visible even fairly zoomed out.
_CITY_ZOOM_THRESHOLDS = [
    (1500.0, 0.02),
    (4000.0, 0.005),
    (10000.0, 0.0008),
    (30000.0, 0.0001),
    (80000.0, 0.00002),
    (float("inf"), 0.000003),
]


def city_min_area_for_scale(scale):
    """Minimum eeu.cty bounding-box area (deg^2) a city must have to be
    labeled at the given canvas scale (pixels/degree). See
    _CITY_ZOOM_THRESHOLDS above."""
    for max_scale, min_area in _CITY_ZOOM_THRESHOLDS:
        if scale < max_scale:
            return min_area
    return _CITY_ZOOM_THRESHOLDS[-1][1]


# ---------------------------------------------------------------------------
# Core, GUI-free logic -- exercised directly by test_map_viewer.py
# ---------------------------------------------------------------------------

def project_point(lon, lat, center_lon, center_lat, scale):
    """Simple local equirectangular projection: (lon,lat) degrees -> canvas
    pixel offset from the center point, given `scale` pixels/degree.
    x grows east, y grows... DOWN on screen for increasing y pixel value, so
    latitude (which increases northward) is negated to point up-screen."""
    x = (lon - center_lon) * math.cos(math.radians(center_lat)) * scale
    y = -(lat - center_lat) * scale
    return x, y


def compute_visible_bbox(center_lon, center_lat, scale, pan_x, pan_y, width, height):
    """Inverse of project_point()+the canvas-centering offset used by
    App._to_canvas(): given the current view state and canvas size, return
    the (lon_min, lon_max, lat_min, lat_max) currently visible on screen.
    This is what drives dynamic tile/name/city loading on pan/zoom."""
    cos_lat = math.cos(math.radians(center_lat))
    if abs(cos_lat) < 1e-9:
        cos_lat = 1e-9 if cos_lat >= 0 else -1e-9
    lon_left = center_lon + (-width / 2 - pan_x) / (cos_lat * scale)
    lon_right = center_lon + (width / 2 - pan_x) / (cos_lat * scale)
    lat_top = center_lat + (height / 2 + pan_y) / scale
    lat_bottom = center_lat - (height / 2 - pan_y) / scale
    lon_min, lon_max = (lon_left, lon_right) if lon_left <= lon_right else (lon_right, lon_left)
    lat_min, lat_max = (lat_bottom, lat_top) if lat_bottom <= lat_top else (lat_top, lat_bottom)
    return (lon_min, lon_max, lat_min, lat_max)


def canvas_to_lonlat(cx, cy, center_lon, center_lat, scale, pan_x, pan_y, width, height):
    """Inverse of App._to_canvas() (which is project_point() plus the
    canvas-centering/pan offset): canvas pixel (cx, cy) -> (lon, lat).
    Used by the click-to-identify feature (README §10 "v6 -> v7") to turn a
    right-click's screen position into a real-world coordinate before
    looking for the nearest rendered point. Pure function, no GUI/Tk
    dependency, so it's directly testable against a known (lon, lat) run
    through project_point() first."""
    x = cx - width / 2 - pan_x
    y = cy - height / 2 - pan_y
    cos_lat = math.cos(math.radians(center_lat))
    if abs(cos_lat) < 1e-9:
        cos_lat = 1e-9 if cos_lat >= 0 else -1e-9
    lon = center_lon + x / (cos_lat * scale)
    lat = center_lat - y / scale
    return lon, lat


def _name_at_point(named_ranges, point_index):
    """Look up the road name (or None) covering `point_index` in a
    feature's own `named_ranges` list (`[(start, end, name), ...]`, as
    road_naming.name_features() attaches it). Shared between
    find_nearest_point() and App._redraw()'s connected-roads line-color
    logic (README §10 "v9 -> v10") so both use exactly the same "which
    named run is this point part of" rule instead of two independently-
    maintained copies of the same loop."""
    for start, end, name in named_ranges or ():
        if start <= point_index <= end:
            return name
    return None


def find_nearest_point(features, click_lon, click_lat, center_lat, scale, max_px=POINT_PICK_RADIUS_PX):
    """Click-to-identify core lookup (README §10 "v6 -> v7"): scan every
    point of every feature in `features` (the same flat, already-decoded/
    already-named list App.features holds -- one element per
    map_compressed_reader.decode_features() feature dict, each tagged by
    MapData.decode_tile() with "layer"/"tile_id"/"tile_offset"/
    "tile_declen"/"feature_index" and, after road_naming.name_features(),
    "named_ranges") and return identifying info for whichever point is
    closest to (click_lon, click_lat), IF it's within `max_px` screen
    pixels at the given view `scale` -- otherwise None (deliberately not an
    error: clicking empty map space is an expected, ordinary case).

    Distance is measured in the SAME pixel-space metric project_point()
    uses (longitude distance scaled by cos(center_lat) before multiplying
    by `scale`, exactly like project_point()'s own x term), not raw
    degrees -- this is what makes a flat pixel-radius cutoff meaningful
    regardless of latitude or zoom level, and it's a one-line reuse of the
    existing projection math rather than a new distance model. This is a
    plain, dependency-free scan over the in-memory point lists (no spatial
    index) -- deliberately not over-engineered per the task's own guidance,
    since a pick happens once per click, not once per redraw.

    Returns a dict (WITHOUT a "number" key -- the caller, App._on_point_pick,
    assigns that on a successful pick) with every field a future session
    would need to locate this exact point's raw bytes again:
        {"layer", "tile_id", "tile_offset", "tile_declen", "feature_index",
         "feature_byte_offset", "point_index", "lon", "lat", "name"}
    or None if nothing is within `max_px` pixels."""
    cos_lat = math.cos(math.radians(center_lat))
    if abs(cos_lat) < 1e-9:
        cos_lat = 1e-9 if cos_lat >= 0 else -1e-9
    best = None
    best_d2 = max_px * max_px
    for feat_idx, feat in enumerate(features):
        pts = feat.get("points") or ()
        for pt_idx, (lon, lat) in enumerate(pts):
            dx = (lon - click_lon) * cos_lat * scale
            dy = (lat - click_lat) * scale
            d2 = dx * dx + dy * dy
            if d2 <= best_d2:
                best_d2 = d2
                best = (feat_idx, pt_idx)
    if best is None:
        return None
    feat_idx, pt_idx = best
    feat = features[feat_idx]
    lon, lat = feat["points"][pt_idx]
    name = _name_at_point(feat.get("named_ranges"), pt_idx)
    return {
        "layer": feat.get("layer"),
        "tile_id": feat.get("tile_id"),
        "tile_offset": feat.get("tile_offset"),
        "tile_declen": feat.get("tile_declen"),
        "feature_index": feat.get("feature_index"),
        "feature_byte_offset": feat.get("offset"),
        "point_index": pt_idx,
        "lon": lon,
        "lat": lat,
        "name": name,
    }


def _iter_high_confidence_edges(features, topo_caches):
    """Yield (feat, a_idx, b_idx) for every edge App._redraw() would
    actually draw as a real connected-roads canvas.create_line() (README §10
    "v9 -> v10"/"v16 -> v17"): for each `feat` tagged with layer/tile_id/
    feature_index whose cached resolve_topology_adjacency() result (looked
    up the exact same way _redraw()'s own connected-roads block does, via
    `topo_caches[layer][tile_id][feature_index]`) has `found=True` and
    `confidence == "high"`, yield every one of its `edges` entries whose
    endpoint indices are in range. This is the shared "what edges are
    actually visible on screen right now" iterator used both by _redraw()
    (implicitly, via the same lookup inlined there) and by
    find_nearest_line_segment() below, so an edge pick can never identify an
    edge that isn't actually drawn."""
    for feat in features:
        layer = feat.get("layer")
        tile_id = feat.get("tile_id")
        f_idx = feat.get("feature_index")
        if layer is None or tile_id is None or f_idx is None:
            continue
        tlist = topo_caches.get(layer, {}).get(tile_id)
        if tlist is None or not (0 <= f_idx < len(tlist)):
            continue
        cand = tlist[f_idx]
        if not (cand.get("found") and cand.get("confidence") == "high"):
            continue
        pts = feat.get("points") or ()
        for a, b in cand.get("edges", ()):
            if a >= len(pts) or b >= len(pts):
                continue
            yield feat, a, b


def _point_segment_dist2(px, py, ax, ay, bx, by):
    """Squared distance from point (px,py) to the line SEGMENT (not
    infinite line) from (ax,ay) to (bx,by), in whatever 2D unit the
    caller's coordinates are already in (this module always calls it in the
    same "pixel-space" metric project_point()/find_nearest_point() use, not
    raw canvas pixels -- see find_nearest_line_segment())."""
    dx, dy = bx - ax, by - ay
    seg_len2 = dx * dx + dy * dy
    if seg_len2 <= 1e-12:
        ex, ey = px - ax, py - ay
        return ex * ex + ey * ey
    t = ((px - ax) * dx + (py - ay) * dy) / seg_len2
    t = max(0.0, min(1.0, t))
    cx, cy = ax + t * dx, ay + t * dy
    ex, ey = px - cx, py - cy
    return ex * ex + ey * ey


def _point_info(feat, pt_idx):
    """Build the SAME identifying-info dict shape find_nearest_point()
    returns (layer/tile_id/tile_offset/tile_declen/feature_index/
    feature_byte_offset/point_index/lon/lat/name), for one specific known
    point of `feat` -- shared by find_nearest_line_segment() below so an
    edge pick's two endpoints carry exactly the same identifying
    information a direct point pick would."""
    lon, lat = feat["points"][pt_idx]
    return {
        "layer": feat.get("layer"),
        "tile_id": feat.get("tile_id"),
        "tile_offset": feat.get("tile_offset"),
        "tile_declen": feat.get("tile_declen"),
        "feature_index": feat.get("feature_index"),
        "feature_byte_offset": feat.get("offset"),
        "point_index": pt_idx,
        "lon": lon,
        "lat": lat,
        "name": _name_at_point(feat.get("named_ranges"), pt_idx),
    }


def find_nearest_line_segment(features, topo_caches, click_lon, click_lat, center_lat, scale,
                               max_px=LINE_PICK_RADIUS_PX):
    """Click-to-identify-an-EDGE core lookup (README §10 "v16 -> v17"): the
    line-segment counterpart to find_nearest_point() above, for debugging
    the still-unsolved topology/connectivity resolution (§3.6) -- lets the
    user right-click a specific DRAWN connected-roads line and get back
    exactly which two real points it connects, to report back whether that
    connection is correct.

    Scans every edge _iter_high_confidence_edges() yields (i.e. exactly the
    edges App._redraw() actually draws as real canvas.create_line() segments
    when "Draw connected roads" is on -- never a guessed/low-confidence
    edge, since those never reach this iterator either) and returns the
    IDENTIFYING-INFO PAIR (find_nearest_point()'s own dict shape, for each
    endpoint) of whichever edge's SEGMENT (point-to-segment distance, not
    just distance to an endpoint -- clicking the middle of a long edge must
    still hit it) is closest to (click_lon, click_lat), if within `max_px`
    screen pixels at the given view `scale` -- otherwise None.

    Distance is measured in the exact same pixel-space metric
    find_nearest_point() uses (longitude scaled by cos(center_lat) before
    multiplying by `scale`), for the same reason: a flat pixel-radius cutoff
    stays meaningful regardless of latitude/zoom. Plain, dependency-free
    scan (no spatial index) -- same "once per click, not once per redraw"
    reasoning find_nearest_point() already documents.

    Returns `(info_a, info_b)` or `None`."""
    cos_lat = math.cos(math.radians(center_lat))
    if abs(cos_lat) < 1e-9:
        cos_lat = 1e-9 if cos_lat >= 0 else -1e-9

    def proj(lon, lat):
        return (lon - click_lon) * cos_lat * scale, (lat - click_lat) * scale

    best = None
    best_d2 = max_px * max_px
    for feat, a_idx, b_idx in _iter_high_confidence_edges(features, topo_caches):
        lon_a, lat_a = feat["points"][a_idx]
        lon_b, lat_b = feat["points"][b_idx]
        ax, ay = proj(lon_a, lat_a)
        bx, by = proj(lon_b, lat_b)
        d2 = _point_segment_dist2(0.0, 0.0, ax, ay, bx, by)
        if d2 <= best_d2:
            best_d2 = d2
            best = (feat, a_idx, b_idx)
    if best is None:
        return None
    feat, a_idx, b_idx = best
    return _point_info(feat, a_idx), _point_info(feat, b_idx)


def bbox_contains(outer, inner, tol=1e-9):
    """True if `outer` (lon_min,lon_max,lat_min,lat_max) fully contains
    `inner`, within a small tolerance. Used to decide whether the tiles/
    road-name index already loaded for `outer` still cover a new viewport
    `inner` without needing a reload."""
    olon_min, olon_max, olat_min, olat_max = outer
    ilon_min, ilon_max, ilat_min, ilat_max = inner
    return (
        olon_min - tol <= ilon_min and ilon_max <= olon_max + tol and
        olat_min - tol <= ilat_min and ilat_max <= olat_max + tol
    )


def pad_bbox(lon_min, lon_max, lat_min, lat_max, pad_frac):
    """Expand a bbox by `pad_frac` of its own width/height on every side
    (used to give pan/zoom headroom before the next reload is needed)."""
    dlon = max(lon_max - lon_min, 1e-5)
    dlat = max(lat_max - lat_min, 1e-5)
    pad_lon = dlon * pad_frac
    pad_lat = dlat * pad_frac
    return (lon_min - pad_lon, lon_max + pad_lon, lat_min - pad_lat, lat_max + pad_lat)


def nice_scale_step(value_m):
    """Round `value_m` (meters) down to a 'nice' 1/2/5 x 10^n step, the same
    convention real map scale bars use (photos #3/#4's "1.5 km"/"500 km"
    bottom-right indicator). Used by App._update_scale_bar() -- kept as a
    plain function (no GUI dependency) so it's directly testable."""
    if value_m <= 0:
        return 1.0
    exp = math.floor(math.log10(value_m))
    base = value_m / (10 ** exp)
    if base < 1.5:
        nice = 1.0
    elif base < 3.5:
        nice = 2.0
    elif base < 7.5:
        nice = 5.0
    else:
        nice = 10.0
    return nice * (10 ** exp)


class SearchHit:
    """One row of a unified road+city search result."""

    __slots__ = ("kind", "name", "lon", "lat", "extra")

    def __init__(self, kind, name, lon, lat, extra=None):
        self.kind = kind  # "road" or "city"
        self.name = name
        self.lon = lon
        self.lat = lat
        self.extra = extra  # core.RoadRecord or city_reader.CityRecord

    def label(self):
        tag = "[City]" if self.kind == "city" else "[Road]"
        return "%s  %s  (%.5f, %.5f)" % (tag, self.name, self.lon, self.lat)

    def jump_span_deg(self, default_span):
        """Suggested half-span (degrees) to load/zoom to when jumping to
        this hit -- for a city, scaled to roughly fit its own bounding box;
        for a road, the caller's layer-default span."""
        if self.kind == "city" and self.extra is not None:
            lon_min, lat_min, lon_max, lat_max = self.extra.bbox
            span = max(lon_max - lon_min, lat_max - lat_min) * 0.75
            return max(0.01, min(span, 2.0))
        return default_span


def _feature_keep_indices(features, anchor):
    """Given a decode_features() list and an optional tile anchor (as
    stored in MapData.geo_indexes[layer][tile_id] -- a
    map_compressed_reader.build_geo_index() entry, `(lon, lat, method)`),
    return the indices (in order) of features that pass
    MapData.decode_tile()'s own drift-plausibility filter
    (MAX_FEATURE_DRIFT_DEG) -- factored out (README §10 "v9 -> v10") so
    MapData.get_tile_adjacency() can reproduce EXACTLY the same "kept"
    feature ordering that decode_tile()'s own "feature_index" tags use,
    without duplicating the filter condition in two places that could
    silently drift apart. `anchor=None` (no geo-index entry for this
    tile) keeps every feature, matching decode_tile()'s own fallback.

    BUG FIX (README §10 "v9 -> v10"): this used to unpack `anchor` as a
    bare `(a_lon, a_lat)` 2-tuple, but build_geo_index() actually returns
    3-tuples `(lon, lat, method)` -- every real call site passes a real
    geo-index entry, so this raised `ValueError: too many values to
    unpack` on EVERY tile that had a geo-index anchor (i.e. essentially
    every tile), which decode_tile()'s caller (MapData.ensure_area_loaded())
    silently swallowed as `cache[tid] = []`, making tile decoding produce
    ZERO features project-wide -- caught by test_map_viewer.py's
    pre-existing (unrelated) "expected some decoded road features near a
    real city" assertion failing outright, not a connected-roads-specific
    symptom."""
    if anchor is None:
        return list(range(len(features)))
    a_lon, a_lat = anchor[0], anchor[1]
    return [
        i for i, feat in enumerate(features)
        if all(
            abs(lon - a_lon) <= MAX_FEATURE_DRIFT_DEG and abs(lat - a_lat) <= MAX_FEATURE_DRIFT_DEG
            for lon, lat in feat["points"]
        )
    ]


# No-adjacency placeholder (README §10 "v9 -> v10"): used wherever a tile's
# topology couldn't be resolved (locate failure, decode exception, etc.) so
# every entry in a topo_caches[layer][tile_id] list always has the same
# shape as a real resolve_topology_adjacency() result -- callers only ever
# need to check "confidence", never a separate "did this even run" flag.
_NO_ADJACENCY = {
    "found": False, "shift": None, "median_edge_m": None,
    "confidence": "none", "edges": [], "adjacency": {},
    "edges_dropped_implausible": 0,
}


class MapData:
    """GUI-free core: extracts the MAP_COMPRESSED tile layers + eeu.rd/eeu.il
    (via rns510_core.MapProject) + eeu.cty from the source ISO into local
    temp files, builds each fast layer's geo-index (README §10) plus
    in-memory road-name and city caches, and answers "what should be
    visible for this viewport" queries -- pooling points from every
    AVAILABLE layer (see available_layers() below) that isn't excluded by
    the caller's `allowed_layers` (the "Show layers" checkboxes, README §10
    "v8 -> v9"). **As of "v16 -> v17"** this is CHECKBOX-ONLY control: the
    current view scale no longer restricts which layers are considered at
    all (the "v5 -> v6" cumulative, scale-stacked `layers_for_scale()`
    model this docstring used to describe is superseded for this purpose --
    see ensure_area_loaded()'s own docstring for the full history and the
    known performance tradeoff). Tile decoding is lazy and cached forever,
    per layer. Read-only -- never writes to the ISO.

    ------------------------------------------------------------------
    Caching design (this is the "Task 3" caching/optimization the whole
    dynamic-loading feature depends on -- documented here per the task
    brief's request to write down whatever granularity was chosen):
    ------------------------------------------------------------------
    - `tile_caches` {layer: {tile_id: decode_features() result}} -- ONE
      cache per layer, keyed separately, because tile_id numbering is
      independent per layer (mg3's tile_id 100 and mp0's tile_id 100 are
      unrelated tiles) -- pooling multiple layers together at once must not
      let one layer's tile_ids collide with another's. Once a tile is
      decoded it is NEVER re-decoded or evicted for the lifetime of this
      MapData.
    - `covered_bbox` + `covered_layers` -- the single padded bbox (see
      AREA_PAD_FRAC) and the layer list (`available_layers() ∩
      allowed_layers` at the time of the call -- README §10 "v16 -> v17":
      no longer also intersected with a scale-dependent
      `layers_for_scale()` set) that the tiles currently in
      `active_tile_ids` are guaranteed to cover. ensure_area_loaded()
      REPLACES both (does not union/accumulate) every time it runs: simpler
      to reason about than incremental geometric union logic, and correct
      because the new padded bbox always contains the visible viewport that
      triggered the call. A reload is triggered when the viewport escapes
      the covered bbox OR when `available_layers() ∩ allowed_layers` no
      longer equals `covered_layers` -- which covers BOTH "mp0 just
      finished building in the background" AND "the user (un)checked a
      layer checkbox" in one check -- see App._maybe_reload_viewport(). A
      layer that falls OUTSIDE the current set (e.g. the user unchecked it)
      stays in its own `tile_caches` entry (so re-checking it is instant,
      no re-decode) but is dropped from `active_tile_ids` (so it's not
      pooled into what gets drawn while unchecked) -- deliberately NOT
      evicted from `tile_caches` itself: keeping already-decoded tiles in
      memory costs nothing extra to redraw (they're simply skipped, being
      absent from `active_tile_ids`) and saves a full re-decode if the user
      re-checks the box later.
    - `rd_cache` (road_naming.RdCache) -- the whole 590MB eeu.rd file is
      read and vectorized ONCE at load() time (this is the expensive part;
      unavoidable, matches build_rd_index()'s own documented cost). Per-area
      road-name indexes (`_rd_index`) are then rebuilt from that in-memory
      cache, NOT from disk, whenever the requested bbox would extend past
      the last-built index's own (margin-padded) bbox -- see
      rd_index_for_bbox(). This satisfies the task's "build the index once
      per loaded area, don't rebuild every frame" requirement while keeping
      the code simple (rebuild-a-bigger-box beats true incremental-merge
      logic here because RdCache.index_for_bbox() is already fast with no
      file I/O involved). Shared across all layers -- eeu.rd is a separate
      source file, unaffected by which tile layers are currently pooled.
    - `cty_cache` (city_reader.CtyCache) -- similarly built ONCE from the
      whole 74MB/939,351-record eeu.cty at load() time; NOT re-queried
      lazily/cached per-area because its query() is already cheap enough
      (a couple of numpy boolean masks over <1M floats) to just call fresh
      on every redraw -- see App._redraw().
    """

    def __init__(self, iso_path, workdir=None):
        self.iso_path = iso_path
        self._owns_workdir = workdir is None
        self.workdir = workdir or tempfile.mkdtemp(prefix="rns510_viewer_")
        os.makedirs(self.workdir, exist_ok=True)
        self.cty_path = os.path.join(self.workdir, "eeu.cty")

        self.layer_paths = {}       # {layer: local extracted eeuz.<layer> path}
        self.directories = {}       # {layer: mcr.read_directory() result}
        self.geo_indexes = {}       # {layer: {tile_id: (lon, lat, method)}}
        self._geo_arrays = {}       # {layer: (tile_ids_np, lons_np, lats_np)}

        self.mp0_ready = False      # True once HEAVY_LAYER's geo-index is built
        self.mp0_building = False   # True while load_heavy_layer() is running

        self.search_project = None  # core.MapProject, for road name search
        self.rd_cache = None        # road_naming.RdCache
        self.cty_cache = None       # city_reader.CtyCache

        # Oscillation-garbage filter toggle (README S10 "v10 -> v11",
        # DEFAULT FLIPPED in "v15 -> v16" -- see that section for the full
        # investigation). Direct, real-ISO, real-named-road-level testing
        # this session (not just the old tile-name-match-count benchmark)
        # found the filter is NET NEGATIVE for real, dense urban areas at
        # the zoom levels users actually look at: at a real Sofia, Bulgaria
        # `mg1` sample (9 tiles), the filter removed only 5.74% of raw
        # points but ENTIRELY deleted 6 real named roads (e.g. "TSARITSA",
        # "BISTRISHKO SHOSE") and truncated 13 more -- including Sofia's own
        # ring road, "OKOLOVRASTEN PAT", losing 84.6% of its matched points.
        # This directly confirmed the user's own first-hand observation
        # ("unchecking hide decode garbage is producing more real accurate
        # roads"). Defaults to False (filter OFF / raw, unfiltered geometry)
        # so a user who never touches the checkbox sees this measurably more
        # complete rendering. set_trim_oscillation() below is the only place
        # this should be changed at runtime, since it must also invalidate
        # the decode caches (a tile decoded under the old setting is stale).
        self.trim_oscillation = False
        self.tile_caches = {layer: {} for layer in ALL_LAYERS}  # per-layer decode cache
        # Per-layer resolve_topology_adjacency() cache (README §10 "v9 -> v10"):
        # {layer: {tile_id: [per-feature adjacency-result dict, ...]}}, index-
        # aligned with that tile's own KEPT feature list (i.e. decode_tile()'s
        # "feature_index" tag) via _feature_keep_indices() -- NOT with
        # decode_features()'s raw pre-drift-filter output. Populated lazily
        # (only when connected-roads mode actually needs a tile -- see
        # decode_tile()'s `want_adjacency` / get_tile_adjacency()) and never
        # evicted once computed, same lifetime policy as tile_caches itself.
        self.topo_caches = {layer: {} for layer in ALL_LAYERS}
        # Per-layer "pre-filter decode" cache (README §10 "v17 -> v18",
        # adjacency-backfill performance fix): {layer: {tile_id: (raw,
        # declen, features, keep_idx)}} -- the intermediate state
        # decode_tile() ALWAYS computes anyway (raw decompressed bytes +
        # decode_features() output + this tile's _feature_keep_indices()
        # result) is kept here too, regardless of `want_adjacency`, purely
        # so get_tile_adjacency()'s fallback path (see its own docstring)
        # never has to re-open the layer file / re-seek / re-decompress /
        # re-run decode_features() from scratch for a tile that's already
        # been read once -- that redundant re-read was the real, measured
        # cost that made turning on "Draw connected roads" over an already
        # panned-around area take minutes (see get_tile_adjacency()'s
        # docstring for the full writeup). Never evicted, same lifetime
        # policy as tile_caches/topo_caches -- this roughly doubles this
        # class's per-tile memory footprint (raw decompressed bytes are now
        # kept alongside the already-kept decoded feature dicts), a
        # deliberate, disclosed memory-for-speed tradeoff.
        self._predecode_caches = {layer: {} for layer in ALL_LAYERS}
        # Per-layer road-name-match cache (README §10 "v18 -> v19" perf
        # fix): {layer: {(tile_id, tol_m): [named_ranges per kept feature,
        # ...]}}, index-aligned with decode_tile()'s own "feature_index"
        # tag, same lifetime/invalidation policy as topo_caches (never
        # evicted; reset alongside tile_caches on set_trim_oscillation()
        # since a trim_oscillation toggle changes the underlying feature
        # geometry a cached tile_id's named_ranges would otherwise still
        # refer to). See ensure_area_loaded()'s own docstring for why this
        # exists: avoids re-running match_feature() (a real per-vertex
        # spatial lookup) over the WHOLE pooled feature set on every single
        # pan/zoom reload, only tiles genuinely new to `self` pay that cost.
        self.name_caches = {layer: {} for layer in ALL_LAYERS}
        self.covered_bbox = None    # (lon_min, lon_max, lat_min, lat_max)
        self.covered_layers = None  # list of layers covered_bbox's tiles were pooled from
        self.active_tile_ids = {}   # {layer: [tile_id, ...]} currently pooled for drawing

        self._rd_index = None       # road_naming.RdSpatialIndex, current area
        self._rd_index_bbox = None  # bbox that index was built for (padded)

        # Address-entry keyboard feature (README §10 "v11 -> v12") -- loaded
        # lazily (see load_address_entry_data()) on first use of the "NAV"
        # bezel button, not at "Open Map ISO" time, since decompressing the
        # full 245MB eeuz.rt body is real extra work not everyone needs.
        self.address_data_ready = False
        self.rt_body = None              # decompressed eeuz.rt body (data[94:])
        self.countries = []              # list[ctr_reader.CountryRecord]
        self.country_name_index = None   # city_reader.PrefixNameIndex over country names
        self.city_name_index = None      # city_reader.PrefixNameIndex over eeu.cty place names

        # Country -> City -> Street scoping (README §10 "v13 -> v14"): the
        # explicit user correction that real nav UX cascades ("select a
        # country then you select a city only from that country then you
        # select an address only from that city") -- see
        # city_reader.build_country_tag_map()'s own docstring for the full
        # eeu.cty bytes[57:59] "country_tag" crack this relies on.
        self.country_tag_map = None       # {country_tag: ctr_reader.CountryRecord}
        self.tag_by_country_index = {}    # {CountryRecord.index: country_tag} (reverse)
        self._city_index_by_tag = {}      # {country_tag: PrefixNameIndex}, built lazily
        self._street_index_by_city = {}   # {CityRecord.index: PrefixNameIndex}, lazily

        # Global, exhaustive street-name index (README §10 "v14 -> v15") --
        # replaces the `.rt`-trie fallback street_name_index_for_city() used
        # to hand off to when a City doesn't resolve. Built lazily (see the
        # street_name_index_global property below) on first actual access,
        # NOT as part of load_address_entry_data(): the common case (a real
        # city already selected) never needs it at all, so paying its
        # one-time cost (~8.8M eeu.rd records deduplicated, see
        # road_naming.RdCache.distinct_names()) up front on every "NAV"
        # screen open would be pure waste for that common case.
        self._street_name_index_global = None

    # ------------------------------------------------------------- loading

    def available_layers(self):
        """The list of tile layers currently ELIGIBLE to be queried/
        rendered -- always FAST_LAYERS (mg4/mg3/mg2/mg1, eagerly geo-indexed
        on "Open Map ISO"), plus HEAVY_LAYER ("mp0") once its background
        geo-index build has finished (see load_heavy_layer()/mp0_ready).
        **As of "v16 -> v17"**, this (intersected with `allowed_layers`,
        the checked boxes) is now DIRECTLY the set ensure_area_loaded()
        pools -- there is no more scale-dependent `layers_for_scale()`
        subset picked out of it first (that was the "v5 -> v6" model; see
        ensure_area_loaded()'s own docstring for the full history). Used by
        both ensure_area_loaded() and App._maybe_reload_viewport() (the
        latter to detect mp0 becoming newly eligible, still unchanged)."""
        layers = list(FAST_LAYERS)
        if self.mp0_ready:
            layers.append(HEAVY_LAYER)
        return layers

    def _build_layer_geo_index(self, layer):
        gi = mcr.build_geo_index(self.layer_paths[layer])
        self.geo_indexes[layer] = gi
        ids = list(gi.keys())
        self._geo_arrays[layer] = (
            np.array(ids, dtype=np.int64),
            np.array([gi[t][0] for t in ids], dtype=np.float64),
            np.array([gi[t][1] for t in ids], dtype=np.float64),
        )

    def load(self, progress=None):
        """Extract every FAST_LAYERS tile layer + eeu.cty from the ISO,
        build each fast layer's geo-index, and load the road-name
        (eeu.rd/eeu.il, via rns510_core.MapProject) and city (eeu.cty)
        in-memory caches. Deliberately does NOT touch HEAVY_LAYER ("mp0")
        -- see load_heavy_layer(), meant to be run afterwards in its own
        background task so "Open Map ISO" itself stays fast."""
        if progress:
            progress("Opening ISO...")
        iso = riso.open_tolerant(self.iso_path)
        try:
            for layer in FAST_LAYERS:
                iso_layer_path = LAYER_ISO_PATHS[layer]
                if progress:
                    progress("Extracting %s..." % iso_layer_path)
                path = os.path.join(self.workdir, "eeuz.%s" % layer)
                with open(path, "wb") as f:
                    iso.get_file_from_iso_fp(f, iso_path=iso_layer_path)
                self.layer_paths[layer] = path

            if progress:
                progress("Extracting %s..." % CTY_ISO_PATH)
            with open(self.cty_path, "wb") as f:
                iso.get_file_from_iso_fp(f, iso_path=CTY_ISO_PATH)
        finally:
            iso.close()

        for layer in FAST_LAYERS:
            if progress:
                progress("Locating tiles in %s..." % layer)
            self.directories[layer] = mcr.read_directory(self.layer_paths[layer])
            if progress:
                progress("Building geo-index for %d %s tiles..." % (
                    self.directories[layer]["num_tiles"], layer))
            self._build_layer_geo_index(layer)
            if progress:
                progress("%s geo-index ready: %d/%d tiles resolved." % (
                    layer, len(self.geo_indexes[layer]), self.directories[layer]["num_tiles"]))

        if progress:
            progress("Loading road name-search index (eeu.rd / eeu.il)...")
        self.search_project = core.MapProject(
            self.iso_path, workdir=os.path.join(self.workdir, "search"))
        self.search_project.load(progress=progress)

        if progress:
            progress("Building in-memory road-coordinate cache (eeu.rd)...")
        self.rd_cache = rdn.RdCache(self.search_project.rd_path)

        if progress:
            progress("Building in-memory city cache (eeu.cty)...")
        self.cty_cache = cty.CtyCache(self.cty_path)
        if progress:
            progress("City cache ready: %d records." % self.cty_cache.record_count)

    def load_heavy_layer(self, progress=None):
        """Extract + geo-index HEAVY_LAYER ("mp0") -- the slow part
        (README §3.6/§10: build_geo_index() alone measured 34-55s on the
        reference disc's 2.14GB/194,705-tile mp0). Meant to be run in its
        OWN BackgroundTask, kicked off right after load() returns (see
        App.on_open_iso/_start_heavy_layer_load), so it finishes in
        parallel with the user's first search/pan/zoom instead of blocking
        "Open Map ISO". Sets mp0_ready=True on success; until then,
        available_layers() simply omits "mp0" from the pool -- once it
        flips True, mp0's tiles are folded ADDITIVELY into the same view
        on the next reload (see App._maybe_reload_viewport)."""
        self.mp0_building = True
        try:
            layer = HEAVY_LAYER
            iso = riso.open_tolerant(self.iso_path)
            try:
                iso_layer_path = LAYER_ISO_PATHS[layer]
                if progress:
                    progress("Extracting %s (street-level detail)..." % iso_layer_path)
                path = os.path.join(self.workdir, "eeuz.%s" % layer)
                with open(path, "wb") as f:
                    iso.get_file_from_iso_fp(f, iso_path=iso_layer_path)
                self.layer_paths[layer] = path
            finally:
                iso.close()

            if progress:
                progress("Locating tiles in %s..." % layer)
            self.directories[layer] = mcr.read_directory(self.layer_paths[layer])
            if progress:
                progress(
                    "Building geo-index for %d street-level tiles "
                    "(this can take up to a minute)..." % self.directories[layer]["num_tiles"])
            self._build_layer_geo_index(layer)
            if progress:
                progress("Street-level geo-index ready: %d/%d tiles resolved." % (
                    len(self.geo_indexes[layer]), self.directories[layer]["num_tiles"]))
            self.mp0_ready = True
            return True
        finally:
            self.mp0_building = False

    # --------------------------------------------------------------- search

    def search_combined(self, query, limit=40):
        """Unified road+city search. Returns (hits: list[SearchHit],
        road_total: int, city_total: int)."""
        hits = []
        road_total = city_total = 0
        if self.search_project is not None:
            road_results, road_total = self.search_project.search(query, limit=limit)
            for r in road_results:
                hits.append(SearchHit("road", r.name, r.lon, r.lat, r))
        if self.cty_cache is not None:
            city_results, city_total = self.cty_cache.search(query, limit=limit)
            for c in city_results:
                hits.append(SearchHit("city", c.name, c.repr_point[0], c.repr_point[1], c))
        return hits, road_total, city_total

    # ------------------------------------------------------------- tiles

    def tile_ids_in_bbox(self, layer, lon_min, lon_max, lat_min, lat_max):
        """tile_ids in the given layer whose geo-index anchor falls inside
        the given bbox (vectorized over that layer's whole geo-index with
        numpy). Returns [] for a layer with no geo-index yet (e.g. mp0
        before load_heavy_layer() finishes -- callers should not normally
        hit this since available_layers() only includes "mp0" once
        mp0_ready is True, but it's handled defensively rather than
        raising)."""
        arrays = self._geo_arrays.get(layer)
        if not arrays:
            return []
        tile_ids, lons, lats = arrays
        if len(tile_ids) == 0:
            return []
        mask = (
            (lons >= lon_min) & (lons <= lon_max) &
            (lats >= lat_min) & (lats <= lat_max)
        )
        return [int(t) for t in tile_ids[mask]]

    def decode_tile(self, layer, tile_id, want_adjacency=False):
        """Decompress and decode_features() one tile by its geo-index/
        directory tile_id within the given layer, applying two independent
        defensive filters (see README §3.6/§10 for the full writeup of the
        two real bugs these catch): `trim_oscillation=True` (the
        "oscillating overrun" bug -- as of this session, decode_features()
        detects and excises EVERY oscillation cluster anywhere in a block
        and splits the block into separate surviving sub-features around
        each one, rather than truncating everything after the first
        cluster found; a single `tile_id` can therefore yield more feature
        dicts than it used to) and MAX_FEATURE_DRIFT_DEG (the
        "bruteforce"-anchor corruption bug). Returns a list of feature
        dicts (map_compressed_reader.decode_features), each additionally
        tagged (README §10 "v6 -> v7", for the click-to-identify feature)
        with "layer", "tile_id", "tile_offset"/"tile_declen" (this tile's
        own file offset/decompressed length, from the directory entry this
        method already has on hand) and "feature_index" (this feature's
        position within THIS tile's own returned/kept feature list -- not
        a position in any later pooled/flattened list). These extra keys
        are plain dict entries that ride along unchanged through
        road_naming.name_features()'s `dict(feat)` copy and the flat
        cross-layer pooling in ensure_area_loaded(), so a point picked from
        the final rendered/pooled `App.features` list can still be traced
        back to the exact tile/feature it came from.

        `want_adjacency` (README §10 "v9 -> v10", connected-roads mode):
        when True, ALSO runs decode_topology()+resolve_topology_adjacency()
        against this SAME already-decoded `features` list (no re-read/
        re-decode -- this is the efficient path, used whenever a tile is
        being decoded for the FIRST time while connected-roads mode is on)
        and caches the per-KEPT-feature result list in
        `self.topo_caches[layer][tile_id]`, index-aligned with the returned
        list's own "feature_index" tags via `_feature_keep_indices()`. A
        tile that was already decoded (and cached) before connected-roads
        mode needed it does NOT get adjacency computed here -- see
        `get_tile_adjacency()` for that lazy fallback path."""
        offset, declen, complen = self.directories[layer]["entries"][tile_id]
        with open(self.layer_paths[layer], "rb") as f:
            f.seek(offset)
            raw = zlib.decompress(f.read(complen))
        features = mcr.decode_features(raw, declen, trim_oscillation=self.trim_oscillation)

        geo_index = self.geo_indexes.get(layer)
        anchor = geo_index.get(tile_id) if geo_index else None
        keep_idx = _feature_keep_indices(features, anchor)
        candidates = [features[i] for i in keep_idx]

        kept = []
        for feat in candidates:
            feat["layer"] = layer
            feat["tile_id"] = tile_id
            feat["tile_offset"] = offset
            feat["tile_declen"] = declen
            feat["feature_index"] = len(kept)
            kept.append(feat)

        # Cache the pre-filter decode state (raw bytes + decode_features()
        # output + keep_idx) regardless of `want_adjacency` -- see
        # `_predecode_caches`'s own comment in __init__ -- so a LATER
        # get_tile_adjacency() fallback call for this exact tile_id never
        # needs to redo the disk read/decompress/decode_features() work
        # this method already did.
        self._predecode_caches[layer][tile_id] = (raw, declen, features, keep_idx)

        if want_adjacency:
            try:
                topo = mcr.decode_topology(raw, declen, features)
                adj_full = mcr.resolve_topology_adjacency(raw, declen, features, topo)
                self.topo_caches[layer][tile_id] = [adj_full[i] for i in keep_idx]
            except Exception:
                self.topo_caches[layer][tile_id] = [dict(_NO_ADJACENCY) for _ in kept]
        return kept

    def get_tile_adjacency(self, layer, tile_id):
        """Lazily compute + cache resolve_topology_adjacency() for one
        tile's KEPT features (README §10 "v9 -> v10"), index-aligned with
        decode_tile()'s own "feature_index" tags via
        `_feature_keep_indices()` -- so App._redraw()'s connected-roads
        mode can look up `self.topo_caches[layer][tile_id][feature_index]`
        directly, with no recomputation on every redraw once a tile has
        been visited once (this method is itself a pure cache-or-compute,
        never re-runs for a `tile_id` already in `self.topo_caches[layer]`).

        This is the FALLBACK path for a tile that was already decoded (and
        is therefore already sitting in `tile_caches`) BEFORE
        connected-roads mode needed it -- e.g. the checkbox was off when
        that tile was first loaded, or a coarser/earlier call decoded it.

        **README §10 "v17 -> v18" performance fix**: this used to
        unconditionally re-open the layer file, re-seek, re-decompress and
        re-run decode_features() from scratch for every single call,
        EVEN THOUGH decode_tile() already did all of that once for this
        exact tile_id -- it just never kept that intermediate state around
        for later reuse. That redundant full re-decode, multiplied across
        potentially hundreds of already-visible tiles the moment "Draw
        connected roads" got checked on over an already-panned-around area
        (made much more likely once "v16 -> v17" removed the scale gate
        that used to keep the touched-tile set tiny), was directly
        responsible for a real, user-reported multi-minute stall. Fixed by
        `_predecode_caches` (see its own comment in `__init__`):
        decode_tile() now ALWAYS stashes its raw bytes + decode_features()
        output + keep_idx there, regardless of `want_adjacency`, so this
        method's fallback -- when the cache has an entry -- skips the
        disk read/decompress/decode_features() entirely and does ONLY the
        work that's genuinely new for this tile: `decode_topology()` +
        `resolve_topology_adjacency()`. A tile this method is asked about
        that was somehow never routed through decode_tile() at all (should
        not normally happen -- see the `except Exception` fallback below)
        still re-reads from disk as a defensive last resort. Either way,
        the result is cached forever after in `topo_caches`, exactly like
        before, and this is only ever called from inside
        `ensure_area_loaded()`, i.e. inside a background `BackgroundTask`
        thread, never on the Tk main thread during a redraw -- see
        `ensure_area_loaded()`'s `want_adjacency` handling."""
        cache = self.topo_caches[layer]
        if tile_id in cache:
            return cache[tile_id]
        try:
            pre = self._predecode_caches[layer].get(tile_id)
            if pre is not None:
                raw, declen, features, keep_idx = pre
            else:
                offset, declen, complen = self.directories[layer]["entries"][tile_id]
                with open(self.layer_paths[layer], "rb") as f:
                    f.seek(offset)
                    raw = zlib.decompress(f.read(complen))
                features = mcr.decode_features(raw, declen, trim_oscillation=self.trim_oscillation)
                geo_index = self.geo_indexes.get(layer)
                anchor = geo_index.get(tile_id) if geo_index else None
                keep_idx = _feature_keep_indices(features, anchor)
                self._predecode_caches[layer][tile_id] = (raw, declen, features, keep_idx)
            topo = mcr.decode_topology(raw, declen, features)
            adj_full = mcr.resolve_topology_adjacency(raw, declen, features, topo)
            result = [adj_full[i] for i in keep_idx]
        except Exception:
            n_kept = len(self.tile_caches[layer].get(tile_id, ()))
            result = [dict(_NO_ADJACENCY) for _ in range(n_kept)]
        cache[tile_id] = result
        return result

    def set_trim_oscillation(self, value):
        """Toggle the oscillation-garbage filter (README S10 "v10 -> v11").
        A no-op if `value` already matches the current setting. Otherwise:
        every already-decoded tile in `tile_caches`/`topo_caches` was
        decoded under the OLD setting and is now stale (decode_features()'s
        output for a given tile genuinely differs between trim_oscillation
        True/False -- that's the whole point of this toggle), so both
        caches are reset to empty per-layer dicts. This is a one-time
        re-decode cost on toggle, same tradeoff already accepted elsewhere
        in this class for other cache-invalidating state changes -- the
        checkbox is expected to be flipped rarely (debugging/inspection),
        not on every redraw."""
        value = bool(value)
        if value == self.trim_oscillation:
            return
        self.trim_oscillation = value
        self.tile_caches = {layer: {} for layer in ALL_LAYERS}
        self.topo_caches = {layer: {} for layer in ALL_LAYERS}
        self._predecode_caches = {layer: {} for layer in ALL_LAYERS}
        self.name_caches = {layer: {} for layer in ALL_LAYERS}

    # --------------------------------------------------------- road names

    def rd_index_for_bbox(self, lon_min, lon_max, lat_min, lat_max, margin_deg=RD_INDEX_MARGIN_DEG):
        """Return a road_naming.RdSpatialIndex covering at least the given
        bbox, rebuilding from the in-memory RdCache only if the currently
        cached index (if any) doesn't already cover it -- see this class's
        docstring for the caching-granularity rationale."""
        if self._rd_index is not None and self._rd_index_bbox is not None:
            if bbox_contains(self._rd_index_bbox, (lon_min, lon_max, lat_min, lat_max)):
                return self._rd_index
        ebox = (lon_min - margin_deg, lon_max + margin_deg, lat_min - margin_deg, lat_max + margin_deg)
        self._rd_index = self.rd_cache.index_for_bbox(*ebox)
        self._rd_index_bbox = ebox
        return self._rd_index

    # ----------------------------------------------------- area / viewport

    def ensure_area_loaded(self, lon_min, lon_max, lat_min, lat_max, scale,
                            pad_frac=AREA_PAD_FRAC, name_tol_m=75, progress=None,
                            allowed_layers=None, want_adjacency=False):
        """The single entry point for both the initial "jump to X" load and
        every pan/zoom-triggered reload: decode any tiles covering a padded
        version of the given bbox that aren't already cached (in that
        layer's own tile_caches entry), pool all pooled layers' decoded
        features together, rebuild/reuse the road-name index for that area,
        and name every pooled feature.

        `allowed_layers` (README §10 "v8 -> v9", CHECKBOX-ONLY CONTROL as of
        "v16 -> v17"): optional iterable/set of layer names. **The layer set
        actually pooled is now exactly `available_layers()` INTERSECTED with
        `allowed_layers`** -- i.e. every layer that is both actually
        available (fast layers always; `mp0` once its background geo-index
        has finished, see `available_layers()`) and not excluded by a
        checkbox, with NO further restriction based on the current view
        `scale`. `None` (the default) means "no restriction at all" --
        every layer `available_layers()` returns gets pooled, at every
        scale. Order is `ALL_LAYERS`'s own coarsest-to-finest ordering (not
        `allowed_layers`' own iteration order), since several call sites
        (and tests) compare the returned `layers` list directly against
        `ALL_LAYERS`.

        **CHANGED (README §10 "v16 -> v17"), user's explicit request**: this
        used to restrict `layers_for_scale(scale, available_layers())` (the
        scale-dependent cumulative set from "v5 -> v6") down further by
        `allowed_layers` -- i.e. the checkboxes only ever NARROWED an
        automatic, zoom-based selection, they never had full control. The
        user explicitly asked for checkbox-ONLY control, for debugging
        purposes, understanding this removes the automatic "don't pool mp0
        while zoomed way out" cost-saving gate `layers_for_scale()` existed
        for in the first place (see "v5 -> v6"'s own writeup for why that
        gate was added: `mp0` alone can be tens of thousands of points at a
        dense real bbox) -- a user who wants that cost back can simply
        uncheck the heavier layers manually. `layers_for_scale()` and
        `SCALE_LAYER_THRESHOLDS` are UNCHANGED and still real, tested, pure
        functions (see their own docstrings) -- they're just no longer
        CALLED here to gate what's pooled. `scale` is still accepted (kept
        for call-site/API compatibility -- every existing caller passes it
        positionally) but is no longer used to choose which layers are
        considered; it's effectively unused by this method now.

        `mp0` specifically: still only ever appears in the pooled set once
        `available_layers()` actually includes it (i.e. its background
        geo-index build has finished, `load_heavy_layer()`/`mp0_ready`,
        unchanged since "v2 -> v3") -- this method never requests/decodes a
        layer that hasn't been geo-indexed yet, `allowed_layers` or not.

        Returns a dict: {"bbox", "layers", "tile_ids", "new_tiles",
        "features"}, where `layers` is the (checkbox-restricted, scale-
        independent) set actually used, `tile_ids` is {layer: [tile_id,
        ...]} (per-layer, since tile_id numbering isn't shared across
        layers) and `new_tiles` is the total count of tiles freshly decoded
        across all pooled layers this call. Tiles from a layer that falls
        OUTSIDE this call's final layer set (i.e. a layer the user has
        unchecked, or one not yet available) are simply not decoded/pooled
        here -- any of that layer's tiles decoded by an EARLIER call stay in
        that layer's own tile_caches entry rather than being evicted (see
        this class's docstring), so re-checking a box never re-decodes them.

        `want_adjacency` (README §10 "v9 -> v10", connected-roads mode):
        when True, every tile pooled by this call also gets its
        resolve_topology_adjacency() result computed and cached in
        `topo_caches` -- for a NEWLY-decoded tile this happens inline
        inside `decode_tile(..., want_adjacency=True)` (no extra
        decode/read pass); for a tile that was already decoded by an
        earlier call (so `decode_tile()` is skipped here) but doesn't have
        a cached adjacency result yet, `get_tile_adjacency()` is called
        separately to fill the gap. `False` (the default -- every
        pre-existing caller/test that doesn't pass this) skips all of this
        extra work entirely, so it costs nothing when connected-roads mode
        is off. Either way this method always runs inside a background
        `BackgroundTask` (see App._jump_to()/_maybe_reload_viewport()), so
        the extra per-tile cost never blocks the Tk main thread.

        **README §10 "v18 -> v19" performance fix**: road-name matching
        (`road_naming.match_feature()`, a real per-vertex spatial-index
        lookup) used to re-run over the FULL pooled feature list on every
        single call -- including tiles a PREVIOUS call had already decoded
        AND already named identically, since neither the tile's own
        geometry nor the (monotonically growing) `rd_index` covering it
        ever changes once computed. At a wide, long-panned-around viewport
        with hundreds of thousands of already-cached points, this meant
        every incremental pan/zoom paid full re-naming cost again, on top
        of whatever was genuinely new -- a real, measured source of the
        "still laggy after every pan" complaint once the "v17 -> v18"
        rasterization fix already made RENDERING itself fast. Fixed the
        same way `topo_caches` already handles adjacency: `name_caches`
        (see `__init__`) caches each tile's own `match_feature()` results
        by `(tile_id, tol_m)`, index-aligned with `feature_index`, computed
        once and reused forever after (reset only by
        `set_trim_oscillation()`, alongside `tile_caches`, since that
        toggle changes the underlying geometry). A tile revisited by a
        later overlapping call now costs one dict lookup instead of a full
        re-match."""
        # README §10 "v16 -> v17": no more layers_for_scale(scale, ...) gate
        # here -- the pooled set is purely `available_layers()` (what's
        # actually geo-indexed/ready) restricted by `allowed_layers` (the
        # checked boxes), independent of `scale`. `ALL_LAYERS`'s own
        # coarsest-to-finest order is used so the returned `layers` list
        # stays in a stable, predictable order for callers/tests.
        available = set(self.available_layers())
        if allowed_layers is None:
            layers = [l for l in ALL_LAYERS if l in available]
        else:
            allowed_layers = set(allowed_layers)
            layers = [l for l in ALL_LAYERS if l in available and l in allowed_layers]
        ebox = pad_bbox(lon_min, lon_max, lat_min, lat_max, pad_frac)

        if progress:
            progress("Finding tiles covering the visible area...")

        per_layer_tile_ids = {}
        any_tiles_with_features = False
        new_count = 0
        for layer in layers:
            tile_ids = self.tile_ids_in_bbox(layer, *ebox)
            per_layer_tile_ids[layer] = tile_ids
            cache = self.tile_caches[layer]

            for tid in tile_ids:
                if tid not in cache:
                    try:
                        cache[tid] = self.decode_tile(layer, tid, want_adjacency=want_adjacency)
                    except Exception:
                        cache[tid] = []
                    new_count += 1
                elif want_adjacency and tid not in self.topo_caches[layer]:
                    # Already decoded (e.g. by an earlier call before
                    # connected-roads mode was on) but never got adjacency
                    # computed -- fill the gap via the lazy fallback path.
                    try:
                        self.get_tile_adjacency(layer, tid)
                    except Exception:
                        pass
                if cache.get(tid):
                    any_tiles_with_features = True

        self.covered_bbox = ebox
        self.covered_layers = layers
        self.active_tile_ids = per_layer_tile_ids

        # Name matching (README §10 "v18 -> v19" perf fix): CACHED per
        # (layer, tile_id, tol_m) in `self.name_caches`, the same pattern
        # already used for `topo_caches`/`_predecode_caches` -- previously
        # this ran rdn.name_features() over the FULL pooled feature list on
        # EVERY call (every pan/zoom/checkbox reload), including features
        # from tiles that had already been named identically by an earlier,
        # overlapping call. A wide viewport accumulates hundreds of
        # thousands of already-cached, already-named points; re-running
        # match_feature() (a real per-vertex spatial-index lookup) over all
        # of them on every single incremental reload was pure, avoidable,
        # repeated work -- the actual "still laggy after every pan" cost
        # once the v17->v18 rasterization fix made RENDERING itself fast.
        # Now only a NEWLY-decoded tile (or a tile whose want_adjacency
        # fallback just ran, which doesn't affect naming) ever pays
        # match_feature() again; a tile revisited by a later overlapping
        # reload reuses its cached named_ranges list, aligned by
        # feature_index exactly like topo_caches.
        named = []
        if any_tiles_with_features:
            if progress:
                progress("Matching decoded features against real road names...")
            rd_index = self.rd_index_for_bbox(*ebox)
            for layer in layers:
                cache = self.tile_caches[layer]
                ncache = self.name_caches[layer]
                for tid in per_layer_tile_ids[layer]:
                    feats = cache.get(tid)
                    if not feats:
                        continue
                    key = (tid, name_tol_m)
                    ranges_list = ncache.get(key)
                    if ranges_list is None:
                        ranges_list = [rdn.match_feature(feat["points"], rd_index, tol_m=name_tol_m)
                                        for feat in feats]
                        ncache[key] = ranges_list
                    for feat, named_ranges in zip(feats, ranges_list):
                        new_feat = dict(feat)
                        new_feat["named_ranges"] = named_ranges
                        named.append(new_feat)

        return {
            "bbox": ebox,
            "layers": layers,
            "tile_ids": per_layer_tile_ids,
            "new_tiles": new_count,
            "features": named,
        }

    # ------------------------------------------------------ address entry

    def load_address_entry_data(self, progress=None):
        """Load everything the "NAV" bezel button's Address Entry / letter-
        keyboard feature needs (README §10 "v11 -> v12"), run lazily (in its
        own BackgroundTask, see App.on_bezel_nav()) the first time that
        screen is opened rather than at "Open Map ISO" time:
          - `eeu.ctr` (country list, research/ctr_reader.py -- CRACKED this
            session, small/fast: 35 records) -> self.countries +
            self.country_name_index (a city_reader.PrefixNameIndex, exact
            live per-letter narrowing over a closed 35-country list).
          - `eeuz.rt` (street-name character-trie, research/
            road_index_reader.py) -> extracted + FLAT_COMPRESSED-
            decompressed (research/flat_compressed_reader.py) into
            self.rt_body. This is the slow part -- the reference disc's
            eeuz.rt is ~62MB compressed / 245,698,715 bytes decompressed,
            comparable in cost to extracting one of the FAST_LAYERS map
            tiles -- which is why this whole method is lazy/background
            rather than part of load().
          - self.city_name_index: a city_reader.PrefixNameIndex built from
            the ALREADY-loaded self.cty_cache's own real names (no extra
            file I/O) -- used for the City field's live keyboard narrowing
            INSTEAD OF the `.ct` trie (`city_reader.ct_root()`). This is a
            deliberate choice, not an oversight: `ct_root()`'s own
            docstring documents a direct, real negative finding this
            session -- "SOFIA" is a confirmed real `eeuz.cl` entry but is
            NOT reachable from any found `.ct` shard -- so `.ct`'s coverage,
            while real (`ct_root()` is fully cracked and separately unit-
            tested), cannot be trusted as the sole source of truth for a
            feature whose whole point is "never wrongly disable a real
            option". `eeu.cty` has no such gap (939,351 real records, the
            same data this viewer's own city search/labels already use).
        Deliberately does NOT build `self.street_name_index_global` (README
        §10 "v14 -> v15") -- that exhaustive global street-name index is
        built lazily on first actual access instead (see its own docstring),
        since the common case (a City has already been selected and
        resolves) never needs it, and its one-time cost is dominated by a
        `numpy.unique()` pass over all 8.8M `eeu.rd` records, not something
        worth paying on every "NAV" screen open.
        Idempotent: a second call is a silent no-op once
        `self.address_data_ready` is True."""
        if self.address_data_ready:
            return
        if progress:
            progress("Loading country list (eeu.ctr)...")
        ctr_path = os.path.join(self.workdir, "eeu.ctr")
        iso = riso.open_tolerant(self.iso_path)
        try:
            with open(ctr_path, "wb") as f:
                iso.get_file_from_iso_fp(f, iso_path=CTR_ISO_PATH)
            if progress:
                progress("Extracting street name-search tree (eeuz.rt)...")
            rt_path = os.path.join(self.workdir, "eeuz.rt")
            with open(rt_path, "wb") as f:
                iso.get_file_from_iso_fp(f, iso_path=RT_ISO_PATH)
        finally:
            iso.close()

        self.countries = ctrr.load_countries(ctr_path)
        self.country_name_index = cty.PrefixNameIndex(c.name for c in self.countries)

        if progress:
            progress("Decompressing street name-search tree (this can take a few seconds)...")
        doc = fcr.open_flat(rt_path)
        rt_data = fcr.decompress_all(doc)
        self.rt_body = rt_data[94:]

        if progress:
            progress("Indexing city names for live search...")
        if self.cty_cache is not None:
            names = []
            for i in range(self.cty_cache.record_count):
                rec = cty.cty_record(self.cty_cache.body, i)
                # Index just the specific place (the part before the first
                # comma) -- eeu.cty's own "<place>, <parent place>" format
                # (README §3.8) -- so typing "SOFIA" matches the place, not
                # a random "..., SOFIA" suburb entry's own literal string.
                part = rec.name.split(",", 1)[0].strip()
                if part:
                    names.append(part)
            self.city_name_index = cty.PrefixNameIndex(names)

            if progress:
                progress("Building country->city scoping map (eeu.cty country_tag)...")
            # Country -> City scoping (README §10 "v13 -> v14"): partitions
            # eeu.cty's 939,351 records by their real country_tag field
            # (city_reader.build_country_tag_map() -- CRACKED this session,
            # README §3.8 update) so the City speller can be scoped to only
            # the currently-selected Country's own records, instead of the
            # whole file. This is a cheap pass over the already-resident
            # CtyCache arrays (no extra file I/O) plus a small per-tag name
            # sample for the Cyrillic/Latin script tie-break the Russia
            # duplicate-country case needs -- see that function's own
            # extensive docstring for the full methodology and validation
            # numbers (35/35 tags assigned, 17/17 known real cities resolve
            # to their correct real country).
            self.country_tag_map = cty.build_country_tag_map(self.cty_cache, self.countries)
            self.tag_by_country_index = {
                c.index: tag for tag, c in self.country_tag_map.items()
            }
        self.address_data_ready = True
        if progress:
            progress("Address entry ready: %d countries, %d city names indexed, %d country groups." % (
                len(self.countries), len(self.city_name_index._sorted) if self.city_name_index else 0,
                len(self.country_tag_map) if self.country_tag_map else 0))

    # --------------------------------------------------- Country/City/Street
    # scoping (README §10 "v13 -> v14")

    def resolve_country(self, country_name):
        """Exact (case-insensitive) match of `country_name` against the
        closed 35-entry eeu.ctr list -- returns a ctr_reader.CountryRecord or
        None. Country is backed by an exhaustive PrefixNameIndex (no
        coverage gaps), so a value that came from actually completing/
        confirming the Country speller will always resolve here; this is
        also called defensively on whatever raw text the Address Entry
        panel currently holds, which could in principle be a partial/typo'd
        string a caller never confirmed."""
        if not country_name:
            return None
        key = country_name.strip().upper()
        for c in self.countries:
            if c.name.strip().upper() == key:
                return c
        return None

    def resolve_city_record(self, city_name, country_rec=None):
        """Resolve typed City text to one real city_reader.CityRecord,
        SAME substring-search approach resolve_address() already uses
        (self.cty_cache.search(), preferring an exact place-name match over
        a mere substring hit) -- but, when `country_rec` is given, ALSO
        prefers a hit whose own country_tag matches that country (see
        city_reader.build_country_tag_map()), so a city name that happens to
        exist in more than one country resolves to the one actually inside
        the selected country rather than whichever the substring scan finds
        first. Falls back to the best unscoped hit if nothing in that
        country matches (a real name mismatch/typo should degrade, not
        silently return nothing). Returns None if nothing matches at all."""
        if not city_name or self.cty_cache is None:
            return None
        hits, _ = self.cty_cache.search(city_name, limit=200)
        if not hits:
            return None
        name_key = city_name.strip().upper()
        exact = [h for h in hits if h.name.split(",", 1)[0].strip().upper() == name_key]
        candidates = exact if exact else hits
        if country_rec is not None and self.tag_by_country_index:
            tag = self.tag_by_country_index.get(country_rec.index)
            if tag is not None:
                scoped = [h for h in candidates if h.country_tag == tag]
                if scoped:
                    candidates = scoped
        return candidates[0]

    def city_name_index_for_country(self, country_name):
        """The City field's live-narrowing PrefixNameIndex, SCOPED to only
        the records belonging to the given Country (README §10 "v13 -> v14"
        -- the explicit user correction that real nav UX never offers a
        city from the wrong country). Returns None if `country_name` doesn't
        resolve to a real eeu.ctr country (caller should treat this the same
        as "data not ready" -- i.e. don't silently fall back to the
        unscoped, whole-file self.city_name_index, since that's exactly the
        behavior this feature exists to avoid). Built lazily per country tag
        and cached forever (self._city_index_by_tag) -- a country-sized scan
        (34 records for Liechtenstein, up to ~222K for the reference disc's
        largest single-tag group) is cheap enough to build once on first
        selection and reuse for the rest of the session."""
        country_rec = self.resolve_country(country_name)
        if country_rec is None or self.country_tag_map is None or self.cty_cache is None:
            return None
        tag = self.tag_by_country_index.get(country_rec.index)
        if tag is None:
            return None
        idx = self._city_index_by_tag.get(tag)
        if idx is None:
            names = self.cty_cache.place_names_for_tag(tag)
            idx = cty.PrefixNameIndex(names)
            self._city_index_by_tag[tag] = idx
        return idx

    def street_names_for_city(self, city_rec, pad_deg=CITY_STREET_PAD_DEG):
        """Real eeu.rd street names whose own coordinate falls inside
        `city_rec`'s eeu.cty bounding box, padded by `pad_deg` degrees on
        each side (README §10 "v13 -> v14" -- CITY_STREET_PAD_DEG's own
        comment has the padding rationale). Reuses self.rd_cache
        (road_naming.RdCache, already built at load() time for the map's own
        road-name labeling -- no extra file I/O), so this is just a numpy
        bbox mask + a Python loop over the (usually a few hundred to a few
        thousand) records actually inside the padded box. Returns a plain
        list of distinct names (not deduplicated by any name-normalization
        beyond exact string equality)."""
        if self.rd_cache is None:
            return []
        lon_min, lat_min, lon_max, lat_max = city_rec.bbox
        idx = self.rd_cache.index_for_bbox(
            lon_min - pad_deg, lon_max + pad_deg, lat_min - pad_deg, lat_max + pad_deg)
        return sorted(set(idx.exact.values()))

    def street_name_index_for_city(self, city_name, country_rec=None):
        """The Street field's live-narrowing PrefixNameIndex, SCOPED to only
        street names found within the selected City's own (padded) bounding
        box (README §10 "v13 -> v14"). Returns None if `city_name` doesn't
        resolve to a real eeu.cty record, OR if it resolves but no real
        eeu.rd street coordinate falls inside its padded bbox -- in either
        case the caller (SpellerDialog._backing_index()) falls back to
        `street_name_index_global` below (README §10 "v14 -> v15") rather
        than hard-failing, since a resolvable city with zero nearby `.rd`
        coverage is a real (if hopefully rare) possibility this project's
        own §3.9 caveats already flag, not necessarily a bug.
        Built lazily per resolved city and cached forever
        (self._street_index_by_city)."""
        city_rec = self.resolve_city_record(city_name, country_rec=country_rec)
        if city_rec is None:
            return None
        idx = self._street_index_by_city.get(city_rec.index)
        if idx is None:
            names = self.street_names_for_city(city_rec)
            if not names:
                return None
            idx = cty.PrefixNameIndex(names)
            self._street_index_by_city[city_rec.index] = idx
        return idx

    @property
    def street_name_index_global(self):
        """The Street field's GLOBAL, exhaustive live-narrowing
        PrefixNameIndex -- README §10 "v14 -> v15", the fix for this
        project's last documented Street-search coverage gap.

        Before this: when `street_name_index_for_city()` above returns
        `None` (no City selected yet, a City that doesn't resolve to a
        real `eeu.cty` record, or one that resolves but has zero nearby
        `eeu.rd` coverage), `SpellerDialog._backing_index()` fell through
        to `street_enabled_next_chars()`'s real `.rt` character-trie walk
        -- a genuinely CRACKED structure (§3.7), but one with documented,
        provable partial coverage: `.rt` is a forest of independent
        per-letter shards reaching only ~5,100 real leaf strings total
        (README §10 "v11 -> v12"'s own `rt_root()` validation numbers),
        a tiny fraction of the real street-name universe (`.rl`/`.prl`,
        the exhaustive validated name catalog covering the same real
        names, has 46,432,934 entries). A real street whose `.rt` entry
        happens to live in a shard `rt_root()` never found, or whose only
        trie entry is a `;`-demoted sort-key form, could fail to narrow
        correctly even though `resolve_address()` (which never used the
        trie) would still resolve it fine on "Start".

        This property closes that gap the same way City's own unscoped
        fallback (`city_name_index`) already works: an exhaustive
        `city_reader.PrefixNameIndex` (the identical, already-proven
        live-narrowing structure used for Country/City/City-scoped-Street),
        built here from EVERY distinct real name in `road_naming.RdCache`
        (`RdCache.distinct_names()` -- the whole disc's `eeu.rd`, not one
        city's bbox) instead of a trie walk. `PrefixNameIndex` does its own
        case-insensitive dedup, so `distinct_names()`'s already-deduplicated
        list is not required to be perfectly clean going in.

        Built LAZILY, on first actual access, not eagerly at
        `load_address_entry_data()` time: the common case (a City has
        already been selected and resolves, which is the whole point of
        the required Country->City->Street order this UI enforces) never
        reaches this fallback at all, so paying its one-time build cost
        (see the measured number in this project's README §10 "v14 -> v15"
        entry -- dominated by `RdCache.distinct_names()`'s single
        `numpy.unique()` pass over all 8,809,081 `eeu.rd` records) on
        every "NAV" screen open would be pure waste for that common case.
        Cached forever on `self._street_name_index_global` once built, same
        "build once, reuse for the rest of the session" policy every other
        lazy index in this class already follows. Returns `None` (instead
        of building anything) only in the defensive case `self.rd_cache` is
        somehow not yet built (i.e. `load()` itself hasn't run) -- not
        expected to occur in normal use, since Address Entry is only
        reachable after a map ISO is already open."""
        if self._street_name_index_global is None and self.rd_cache is not None:
            self._street_name_index_global = cty.PrefixNameIndex(self.rd_cache.distinct_names())
        return self._street_name_index_global

    def street_enabled_next_chars(self, prefix):
        """Live "which next letters are possibly valid" query over the real
        `.rt` character-trie (README §10 "v11 -> v12"), backed by
        `road_index_reader.rt_enabled_next_chars()` (see that function's own
        docstring for the full fail-safe design: an uncertain/incomplete
        accounting NEVER results in a letter being disabled, only a
        confidently-complete walk that genuinely found no such child does).
        Returns `(enabled: set[str], confident: bool)`. Requires
        `load_address_entry_data()` to have been called first.

        **No longer reachable from SpellerDialog's own live narrowing
        (README §10 "v14 -> v15") -- kept as a validated, standalone
        piece of reverse-engineering, not dead code.** From "v13 -> v14"
        through "v14 -> v15" this was `_backing_index()`'s last-resort
        fallback for the Street field (used whenever
        `street_name_index_for_city()` returned `None`); "v14 -> v15"
        replaced that fallback with the exhaustive `street_name_index_global`
        (a `PrefixNameIndex` over every real `eeu.rd` name, not a trie
        walk), so `_backing_index()` now always returns a real index for
        "street" and this method's own `else` branch in `SpellerDialog.
        _recompute()` is never actually taken by the live UI any more.
        This function (and `road_index_reader.rt_enabled_next_chars()`
        underneath it) is intentionally NOT deleted: it remains real,
        cracked, cross-validated (`.rt`'s node-format validation, README
        §3.7) code, still directly exercised by `test_map_viewer.py`'s own
        `.rt` fail-safe-design tests (the unconfident-empty-prefix case and
        the genuine confident-dead-end case) independent of whether the
        live UI happens to route through it -- keeping it importable/
        testable on its own terms, exactly as `city_reader.ct_root()` was
        already kept for City after `PrefixNameIndex` superseded it as
        City's own load-bearing path (README §10 "v11 -> v12")."""
        if self.rt_body is None:
            return set(), False
        return rir.rt_enabled_next_chars(self.rt_body, prefix)

    def resolve_address(self, country_name, city_name, street_name, number, limit=200):
        """Resolve a typed Country/City/Street/Number address to a real
        (lon, lat) using the SAME already-proven search infrastructure this
        viewer's own search box and "jump to X" already use (README §10
        "v11 -> v12"'s "Start" button, per the task's explicit "reuse
        whatever coordinate-resolution logic already exists" guidance) --
        NOT the `.rt`/`.ct` tries, which are used only for the keyboard's
        live per-letter narrowing above, not for final resolution (their
        real, documented partial coverage makes them unsuitable for a
        "must actually find it" step; `.il`/`eeu.rd` search and
        `eeu.cty`/CtyCache have no such gap for names they do contain).

        Looks up the city via `self.resolve_city_record()` (eeu.cty, exact
        substring match against the SAME real, already-validated dataset
        used for city labels -- now ALSO preferring a hit inside the given
        Country when one resolves, README §10 "v13 -> v14", so a city name
        that exists in more than one country doesn't silently resolve to the
        wrong one), then the street via `self.search_project.search()`
        (eeu.il/eeu.rd, the same search the unified search box's "[Road]"
        results use) -- preferring whichever road result falls inside (a
        generous margin around) the resolved city's own real bounding box,
        if a city was found, so a common street name doesn't resolve to a
        same-named street in a different country. Falls back to the city's
        own representative point if no street result is found (or no street
        was typed), and returns None if NEITHER city nor street resolves to
        anything -- the caller (App._on_address_start()) shows this as an
        ordinary status message, not a crash.

        Returns `{"lon", "lat", "label", "matched_city", "matched_street"}`
        or `None`."""
        country_rec = self.resolve_country(country_name) if country_name else None
        city_rec = self.resolve_city_record(city_name, country_rec=country_rec) if city_name else None

        road_rec = None
        if street_name and self.search_project is not None:
            hits, _ = self.search_project.search(street_name, limit=limit)
            if hits:
                if city_rec is not None:
                    lon_min, lat_min, lon_max, lat_max = city_rec.bbox
                    pad = 0.3
                    near = [
                        h for h in hits
                        if lon_min - pad <= h.lon <= lon_max + pad and lat_min - pad <= h.lat <= lat_max + pad
                    ]
                    road_rec = near[0] if near else hits[0]
                else:
                    road_rec = hits[0]

        if road_rec is not None:
            lon, lat = road_rec.lon, road_rec.lat
            label = road_rec.name if city_rec is None else "%s, %s" % (road_rec.name, city_rec.name)
        elif city_rec is not None:
            lon, lat = city_rec.repr_point
            label = city_rec.name
        else:
            return None
        return {
            "lon": lon, "lat": lat, "label": label,
            "matched_city": city_rec.name if city_rec is not None else None,
            "matched_street": road_rec.name if road_rec is not None else None,
        }

    def close(self):
        if self.search_project is not None:
            self.search_project.close()
        if self._owns_workdir:
            shutil.rmtree(self.workdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

class App:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1150x760")

        self.data = None          # MapData once an ISO is loaded
        self.search_results = []  # last search hits: list[SearchHit]
        self.features = []        # currently rendered, NAMED features
        self.center_lon = None
        self.center_lat = None
        self.scale = 4000.0       # pixels per degree, adjusted on load
        self.pan_x = 0.0
        self.pan_y = 0.0
        # Cached canvas size (README §10 "v18 -> v19" perf fix): _to_canvas()
        # used to call self.canvas.winfo_width()/winfo_height() -- a real
        # Tcl round-trip, not a cheap Python attribute read -- on EVERY
        # single point/vertex it projects, i.e. hundreds of thousands of
        # times per _redraw() at a dense pooled viewport. _redraw() itself
        # already computes the canvas size exactly once at its own top for
        # its own use; it now also stores it here so _to_canvas() (and any
        # other per-point-frequency caller) reads a plain attribute instead.
        # Kept fresh by _redraw() itself and by the canvas <Configure>
        # binding (already wired to call _redraw() on every resize) -- None
        # here just means "no redraw has happened yet", handled by
        # _to_canvas()'s own live-query fallback.
        self._canvas_w = None
        self._canvas_h = None
        self._drag_start = None
        self.busy = False
        self._area_loading = False
        self._viewport_check_id = None
        # Generation token guarding against a stale reload's late completion
        # clobbering newer state (see _maybe_reload_viewport()'s docstring):
        # e.g. a debounced _schedule_viewport_check() reload left pending
        # from an earlier pan/zoom can still be sitting in Tk's event queue
        # when a LATER, unrelated jump/reload starts and finishes first --
        # without this guard, the stale one's own done() would fire anyway
        # once its queued completion is drained, overwriting the already-
        # current view's `_covered_bbox`/`features` with its own, unrelated
        # (and by then meaningless) result.
        self._load_token = 0
        self._covered_bbox = None    # App-level "what the CURRENT view has loaded" (see above -- NOT
        self._covered_layers = None  # the same thing as MapData.covered_bbox/covered_layers, see below)

        # README §10 "v17 -> v18": the single rasterized PIL/Tk image
        # _redraw() builds every call -- kept alive here since Tkinter does
        # not itself hold a strong reference to a PhotoImage (a classic
        # gotcha; without this it would be garbage-collected and vanish).
        self._current_photo = None
        self._current_image = None  # raw PIL Image behind it -- see _redraw()

        # Click-to-identify picks (README §10 "v6 -> v7"): a running,
        # numbered list of points the user has right-clicked, each an
        # identifying-info dict from find_nearest_point() plus a "number".
        # Independent of self.features/self.data -- once picked, a point's
        # recorded (lon, lat) is used to redraw its mark on every future
        # _redraw() regardless of what tiles are currently pooled/loaded.
        self.picked_points = []
        self._point_pick_counter = 0

        # Per-layer visibility checkboxes (README §10 "v8 -> v9"): all
        # CHECKED by default so a fresh app instance behaves EXACTLY like
        # the v6 automatic cumulative-by-zoom behavior for anyone who never
        # touches them. Unchecking a box RESTRICTS the automatically-chosen
        # layer set (layers_for_scale()) -- it never forces a layer on
        # regardless of zoom. See _get_allowed_layers()/_on_layer_visibility_changed().
        self.layer_visible = {layer: tk.BooleanVar(value=True) for layer in ALL_LAYERS}

        # "Draw connected roads" checkbox (README §10 "v9 -> v10"), CHECKED
        # by default per the explicit user request: "add a checkbox to draw
        # real connected roads and make it checked by default." When on,
        # _redraw() draws real canvas.create_line() edges (from
        # MapData.resolve_topology_adjacency()'s output, README §3.6) for
        # any feature/tile whose resolved confidence is "high", falling
        # back to the existing per-vertex dot rendering (v3 -> v4) for
        # every other feature -- never a guessed/low-confidence line. When
        # off, rendering is byte-for-byte the pre-existing dot-only
        # behavior. See _on_connected_roads_changed()/_redraw().
        self.connected_roads_var = tk.BooleanVar(value=True)

        self._build_menu()
        self._build_widgets()
        self._set_status("No ISO loaded. Use File > Open Map ISO...")
        self._set_controls_enabled(False)

    # ------------------------------------------------------------- layout

    def _build_menu(self):
        menubar = tk.Menu(self.root)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Open Map ISO...", command=self.on_open_iso)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=filemenu)
        self.root.config(menu=menubar)

    def _build_widgets(self):
        # No layer picker -- per the explicit ask that started this whole
        # feature ("instead of having many layers and me having to choose
        # seems stupid"), and now taken even further per this session's ask
        # ("keep all the points from all layers shown all the time", README
        # §10 "v4 -> v5"): mg4/mg3/mg2/mg1/mp0 are all pooled together all
        # the time, there is no single "current" layer at all any more. The
        # only trace of this left in the UI is the subtle, non-blocking
        # mp0-loading note in the status area below (self.mp0_status_var)
        # -- never a user-facing CHOICE.
        #
        # Visual restyle (this session): every control below is the SAME
        # widget kind/behavior the app already had (Entry/Button/Listbox/
        # Canvas/Progressbar) -- this only changes colors/fonts/layout to
        # evoke the real RNS510 unit's hardware bezel + on-screen UI (see
        # the reference-photo description this session's task started
        # from). Plain tk widgets (not ttk) are used wherever an explicit
        # background/foreground color needs to actually take effect.

        # ---- dark blue-gray "destination entry" style top panel (photo #2) ----
        search_panel = tk.Frame(self.root, bg=SEARCH_PANEL_BG)
        search_panel.pack(fill="x", side="top")

        self.iso_label = tk.Label(search_panel, text="(no ISO loaded)", anchor="w",
                                   bg=SEARCH_PANEL_BG, fg=SEARCH_PANEL_FG_DIM, font=("Segoe UI", 8))
        self.iso_label.pack(fill="x", padx=10, pady=(6, 0))

        # Breadcrumb-style address display, in the spirit of photo #2's
        # "BALGARIA / SOFIA / ZHK LYULIN..." country->city->street build-up
        # -- populated from whatever was last searched/selected/jumped to
        # (see _update_breadcrumb_from_hit()/_update_breadcrumb_coords()),
        # not a real drill-down destination-entry UI.
        crumb = tk.Frame(search_panel, bg=SEARCH_PANEL_BG)
        crumb.pack(fill="x", padx=10, pady=(2, 8))
        self.crumb_var1 = tk.StringVar(value="NO MAP LOADED")
        self.crumb_var2 = tk.StringVar(value="")
        self.crumb_var3 = tk.StringVar(value="")
        tk.Label(crumb, textvariable=self.crumb_var1, bg=SEARCH_PANEL_BG, fg=SEARCH_PANEL_FG_DIM,
                 font=("Segoe UI", 9), anchor="w").pack(fill="x")
        tk.Label(crumb, textvariable=self.crumb_var2, bg=SEARCH_PANEL_BG, fg=SEARCH_PANEL_FG_DIM,
                 font=("Segoe UI", 9), anchor="w").pack(fill="x")
        tk.Label(crumb, textvariable=self.crumb_var3, bg=SEARCH_PANEL_BG, fg=SEARCH_PANEL_FG,
                 font=("Segoe UI", 13, "bold"), anchor="w").pack(fill="x")

        controls = tk.Frame(search_panel, bg=SEARCH_PANEL_BG)
        controls.pack(fill="x", padx=10, pady=(0, 10))

        # --- unified name search (teal pill button, like photo #2's "Options" row) ---
        search_frame = tk.Frame(controls, bg=SEARCH_PANEL_BG)
        search_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))

        search_row = tk.Frame(search_frame, bg=SEARCH_PANEL_BG)
        search_row.pack(fill="x")
        self.search_var = tk.StringVar()
        search_entry = tk.Entry(search_row, textvariable=self.search_var,
                                 bg="#0f2130", fg=SEARCH_PANEL_FG, insertbackground=SEARCH_PANEL_FG,
                                 relief="flat", highlightthickness=1,
                                 highlightbackground="#3a5a72", highlightcolor=TEAL_ACCENT_ACTIVE)
        search_entry.pack(side="left", fill="x", expand=True, ipady=4)
        search_entry.bind("<Return>", lambda e: self.on_search())
        search_btn = self._make_pill_button(search_row, "Search", self.on_search)
        search_btn.pack(side="left", padx=(6, 0))

        self.results_list = tk.Listbox(search_frame, height=6, bg="#132635", fg=SEARCH_PANEL_FG,
                                        selectbackground=TEAL_ACCENT, selectforeground=TEAL_ACCENT_FG,
                                        relief="flat", highlightthickness=1, highlightbackground="#3a5a72",
                                        font=("Segoe UI", 9))
        self.results_list.pack(fill="both", expand=True, pady=(6, 0))
        self.results_list.bind("<Double-Button-1>", lambda e: self.on_go_to_result())
        self.results_list.bind("<<ListboxSelect>>", lambda e: self._on_result_selected())

        # --- direct coordinate entry ("Curr. pos." row style) ---
        coord_frame = tk.Frame(controls, bg=SEARCH_PANEL_BG)
        coord_frame.pack(side="left", fill="y")

        tk.Label(coord_frame, text="Lon:", bg=SEARCH_PANEL_BG, fg=SEARCH_PANEL_FG_DIM,
                 font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w")
        self.lon_var = tk.StringVar()
        tk.Entry(coord_frame, textvariable=self.lon_var, width=12, bg="#0f2130", fg=SEARCH_PANEL_FG,
                 insertbackground=SEARCH_PANEL_FG, relief="flat", highlightthickness=1,
                 highlightbackground="#3a5a72").grid(row=0, column=1, pady=1)
        tk.Label(coord_frame, text="Lat:", bg=SEARCH_PANEL_BG, fg=SEARCH_PANEL_FG_DIM,
                 font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w")
        self.lat_var = tk.StringVar()
        tk.Entry(coord_frame, textvariable=self.lat_var, width=12, bg="#0f2130", fg=SEARCH_PANEL_FG,
                 insertbackground=SEARCH_PANEL_FG, relief="flat", highlightthickness=1,
                 highlightbackground="#3a5a72").grid(row=1, column=1, pady=1)
        go_btn = self._make_pill_button(coord_frame, "Go", self.on_go_to_coords)
        go_btn.grid(row=0, column=2, rowspan=2, padx=(10, 0))

        # ---- per-layer visibility checkboxes (README §10 "v8 -> v9") ----
        # User request (verbatim): "add an option for me to see only
        # selected layers, with checkboxes so i can do it more precisely" --
        # their workflow need is isolating a SPECIFIC layer's points so a
        # right-click for the ground-truth connectivity workflow (v6 -> v7 /
        # v7 -> v8) lands on the intended layer's dot, not a coarser/finer
        # layer's dot rendered at the same real-world spot. All 5 boxes
        # default CHECKED (self.layer_visible, set up in __init__) so a
        # fresh app instance is unchanged from v6 for anyone who never
        # touches them -- unchecking a box RESTRICTS layers_for_scale()'s
        # automatic cumulative set (see MapData.ensure_area_loaded()'s
        # `allowed_layers` param), it never forces a layer to show
        # regardless of zoom. Toggling ANY box triggers an immediate reload
        # via the same _maybe_reload_viewport(force=True) path the mp0-ready
        # fold-in and jump/search already use, so the visible layers update
        # right away without needing a pan/zoom first.
        layers_row = tk.Frame(search_panel, bg=SEARCH_PANEL_BG)
        layers_row.pack(fill="x", padx=10, pady=(0, 8))
        tk.Label(layers_row, text="Show layers:", bg=SEARCH_PANEL_BG, fg=SEARCH_PANEL_FG_DIM,
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 8))
        self._layer_checkbuttons = {}
        for layer in ALL_LAYERS:
            cb = tk.Checkbutton(
                layers_row, text=layer, variable=self.layer_visible[layer],
                onvalue=True, offvalue=False, command=self._on_layer_visibility_changed,
                bg=SEARCH_PANEL_BG, fg=SEARCH_PANEL_FG, activebackground=SEARCH_PANEL_BG,
                activeforeground=SEARCH_PANEL_FG, selectcolor="#0f2130",
                font=("Segoe UI", 9), highlightthickness=0)
            cb.pack(side="left", padx=(0, 10))
            self._layer_checkbuttons[layer] = cb

        # ---- "Draw connected roads" checkbox (README §10 "v9 -> v10") ----
        # User request (verbatim): "add a checkbox to draw real connected
        # roads and make it checked by default." Placed on the same row as
        # the "Show layers:" checkboxes (a small vertical divider separates
        # them) since both rows control what the map rendering looks like,
        # and this keeps the control panel compact rather than adding a
        # whole new row for one checkbox. CHECKED by default
        # (self.connected_roads_var, set up in __init__). Toggling it
        # reuses the same _maybe_reload_viewport(force=True) path the
        # layer-visibility checkboxes already use (see
        # _on_connected_roads_changed()) so any currently-pooled tile that
        # doesn't yet have a cached resolve_topology_adjacency() result
        # gets it computed (in the background) before the next redraw.
        self._status_divider(layers_row)
        self.connected_roads_cb = tk.Checkbutton(
            layers_row, text="Draw connected roads", variable=self.connected_roads_var,
            onvalue=True, offvalue=False, command=self._on_connected_roads_changed,
            bg=SEARCH_PANEL_BG, fg=SEARCH_PANEL_FG, activebackground=SEARCH_PANEL_BG,
            activeforeground=SEARCH_PANEL_FG, selectcolor="#0f2130",
            font=("Segoe UI", 9), highlightthickness=0)
        self.connected_roads_cb.pack(side="left", padx=(10, 0))

        # ---- "Hide decode garbage" checkbox (README S10 "v10 -> v11") ----
        # User request (verbatim, after asking whether every real point was
        # being shown): "lets fix 2, add a checkbox that enables and
        # disables the filter" -- "2" being the oscillation-garbage filter
        # (decode_features(trim_oscillation=...), README S3.6/S10), which a
        # direct measurement showed removes ~5.7% of raw points in a real
        # sample area -- mostly genuine corruption, but with a confirmed
        # non-zero false-positive rate (at least one real named road is
        # known to get dropped by it, S3.6's 80-tile validation).
        #
        # DEFAULT FLIPPED TO UNCHECKED in "v15 -> v16" (README S10): this
        # session's direct, real-ISO, per-named-road investigation (started
        # from the user's own first-hand observation, verbatim: "unchecking
        # hide decode garbage is producing more real accurate roads then
        # when i enable it, meaning its not usefull and the garbage is not
        # actually garbage") found the filter is net NEGATIVE for real
        # dense-urban rendering at the zoom levels this app is actually used
        # at: a real Sofia `mg1` sample lost 6 whole real named roads and
        # badly truncated 13 more (including the Sofia ring road,
        # "OKOLOVRASTEN PAT", -84.6% of its matched points) while removing
        # only 5.74% of raw points -- the old 42/80-vs-28/80 mg4 tile-count
        # benchmark this checkbox's original "checked by default" choice was
        # based on cannot see this failure mode at all (it only checks
        # whether 2+ named roads match ANYWHERE in a tile, not whether any
        # SPECIFIC real road survives intact). Unchecked by default now, so
        # a user who never touches this checkbox sees the raw, unfiltered
        # (measurably more complete) geometry -- checking it re-enables the
        # filter for inspection/comparison, unchanged mechanically from
        # "v10 -> v11".
        self.hide_garbage_var = tk.BooleanVar(value=False)
        self._status_divider(layers_row)
        self.hide_garbage_cb = tk.Checkbutton(
            layers_row, text="Hide decode garbage", variable=self.hide_garbage_var,
            onvalue=True, offvalue=False, command=self._on_hide_garbage_changed,
            bg=SEARCH_PANEL_BG, fg=SEARCH_PANEL_FG, activebackground=SEARCH_PANEL_BG,
            activeforeground=SEARCH_PANEL_FG, selectcolor="#0f2130",
            font=("Segoe UI", 9), highlightthickness=0)
        self.hide_garbage_cb.pack(side="left", padx=(10, 0))

        # ---- hardware bezel + screen (photo #1) ----
        bezel = tk.Frame(self.root, bg=BEZEL_COLOR)
        bezel.pack(fill="both", expand=True)
        bezel.grid_columnconfigure(1, weight=1)
        bezel.grid_rowconfigure(0, weight=1)

        left_col = tk.Frame(bezel, bg=BEZEL_COLOR)
        left_col.grid(row=0, column=0, rowspan=2, sticky="ns", padx=(10, 6), pady=10)
        for label in ("RADIO", "MEDIA", "PHONE", "TONE"):
            self._make_bezel_button(left_col, label).pack(pady=4)

        right_col = tk.Frame(bezel, bg=BEZEL_COLOR)
        right_col.grid(row=0, column=2, rowspan=2, sticky="ns", padx=(6, 10), pady=10)
        for label, action in (
            ("MAP", self.on_bezel_map),
            ("NAV", self.on_bezel_nav),
            ("TRAFFIC", self.on_bezel_traffic),
            ("SETUP", self.on_bezel_setup),
        ):
            self._make_bezel_button(right_col, label, command=action).pack(pady=4)

        # Glossy black inset frame around the actual screen. Stashed as
        # self.screen_frame (README §10 "v12 -> v13") so AddressEntryDialog/
        # SpellerDialog can be built as tk.Frame children of THIS SAME
        # widget and shown/hidden by place()/lift()/destroy() -- a real
        # head unit has exactly one screen, and different UI states replace
        # each other WITHIN it, never as a second floating OS window.
        screen_frame = tk.Frame(bezel, bg=SCREEN_BORDER_COLOR, bd=0)
        screen_frame.grid(row=0, column=1, sticky="nsew", pady=(10, 0))
        self.screen_frame = screen_frame

        canvas_frame = tk.Frame(screen_frame, bg=SCREEN_BORDER_COLOR)
        canvas_frame.pack(fill="both", expand=True, padx=4, pady=(4, 0))
        self.canvas = tk.Canvas(canvas_frame, background=BG_COLOR, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda e: self._redraw())
        self.canvas.bind("<ButtonPress-1>", self._on_drag_start)
        self.canvas.bind("<B1-Motion>", self._on_drag_move)
        self.canvas.bind("<ButtonRelease-1>", self._on_drag_end)
        self.canvas.bind("<MouseWheel>", self._on_zoom)       # Windows/macOS
        self.canvas.bind("<Button-4>", lambda e: self._on_zoom(e, delta=120))   # Linux scroll up
        self.canvas.bind("<Button-5>", lambda e: self._on_zoom(e, delta=-120))  # Linux scroll down
        # Click-to-identify a point (README §10 "v6 -> v7"): RIGHT-click,
        # not left-click -- left-click (<ButtonPress-1>/<B1-Motion>/
        # <ButtonRelease-1> above) is already the pan-drag gesture, and
        # <Button-3> is otherwise completely unused by this canvas, so this
        # is a zero-conflict binding that leaves panning byte-for-byte
        # unchanged (verified explicitly in test_map_viewer.py: a simulated
        # drag still updates pan_x/pan_y exactly as before). A "hold still
        # enough while left-clicking" distance-based alternative was
        # considered but rejected -- it would need an arbitrary movement
        # threshold and could still occasionally misfire as a tiny pan on a
        # real trackpad/mouse, where a dedicated button has none of that
        # ambiguity.
        self.canvas.bind("<Button-3>", self._on_point_pick)

        # --- on-screen dark segmented status bar (photos #3/#4 style:
        # "3D | Navigation | 9:17 am | Extras | 1.5 km"). This tool is
        # inherently 2D-only, so the mode badge honestly reads "2D" rather
        # than claiming a 3D perspective capability the tool doesn't have.
        # Lives INSIDE the screen inset (it's on-screen software UI, not
        # part of the physical bezel).
        status_bar = tk.Frame(screen_frame, bg=STATUS_BAR_BG)
        status_bar.pack(fill="x", side="bottom", padx=4, pady=4)

        tk.Label(status_bar, text="2D", bg=STATUS_BADGE_BG, fg="white", font=("Segoe UI", 9, "bold"),
                 padx=10, pady=3).pack(side="left", padx=(4, 0), pady=3)
        self._status_divider(status_bar)

        self.status_var = tk.StringVar()
        tk.Label(status_bar, textvariable=self.status_var, bg=STATUS_BAR_BG, fg=STATUS_BAR_FG,
                 anchor="w", font=("Segoe UI", 9)).pack(side="left", fill="both", expand=True, padx=8)
        self._status_divider(status_bar)

        self.clock_var = tk.StringVar()
        tk.Label(status_bar, textvariable=self.clock_var, bg=STATUS_BAR_BG, fg=STATUS_BAR_FG,
                 font=("Segoe UI", 9)).pack(side="left", padx=8)
        self._status_divider(status_bar)

        # Subtle, non-blocking indicator for the one-time background mp0
        # ("street-level detail") geo-index build -- see
        # App._start_heavy_layer_load(). Empty/invisible-in-effect (blank
        # text) the rest of the time; deliberately a separate label from
        # self.status_var so it never gets overwritten by ordinary
        # search/pan/zoom status messages, and never disables anything.
        self.mp0_status_var = tk.StringVar()
        tk.Label(status_bar, textvariable=self.mp0_status_var, bg=STATUS_BAR_BG, fg="#8b93a0",
                 font=("Segoe UI", 8)).pack(side="left", padx=8)
        self._status_divider(status_bar)

        # Distance/scale indicator (photo #3/#4's rightmost segment) --
        # this tool derives it from the current view scale, see
        # _update_scale_bar()/nice_scale_step().
        scale_box = tk.Frame(status_bar, bg=STATUS_BAR_BG)
        scale_box.pack(side="right", padx=(8, 10))
        self.scale_text_var = tk.StringVar(value="--")
        tk.Label(scale_box, textvariable=self.scale_text_var, bg=STATUS_BAR_BG, fg="white",
                 font=("Segoe UI", 9, "bold")).pack()
        self.scale_bar_canvas = tk.Canvas(scale_box, width=80, height=7, bg=STATUS_BAR_BG, highlightthickness=0)
        self.scale_bar_canvas.pack()

        # ---- two round "rotary knob" hardware controls (photo #1) ----
        knob_row = tk.Frame(bezel, bg=BEZEL_COLOR)
        knob_row.grid(row=1, column=1, sticky="ew", pady=(0, 8))
        self._make_knob(knob_row).pack(side="left", padx=(20, 0))
        tk.Label(knob_row, text="RNS 510", bg=BEZEL_COLOR, fg="#5a5d63",
                 font=("Segoe UI", 8, "bold")).pack(side="left", expand=True)
        self._make_knob(knob_row).pack(side="right", padx=(0, 20))

        self.progress = ttk.Progressbar(self.root, mode="indeterminate")
        self.progress.pack(fill="x", side="bottom")

        # ---- click-to-identify picked-points panel (README §10 "v6 -> v7") ----
        # Right-click a rendered point on the map (see the <Button-3> binding
        # above) to add a numbered row here with everything a future session
        # needs to locate that exact point's raw bytes again -- see
        # find_nearest_point()/App._on_point_pick(). Packed with
        # side="bottom" AFTER the progress bar above, so it lands just above
        # it, not below it.
        points_panel = tk.Frame(self.root, bg=SEARCH_PANEL_BG)
        points_panel.pack(fill="x", side="bottom")

        points_header = tk.Frame(points_panel, bg=SEARCH_PANEL_BG)
        points_header.pack(fill="x", padx=10, pady=(4, 0))
        tk.Label(
            points_header,
            text="Picked points -- right-click a point on the map to identify it. "
                 "Select/copy rows below to report which points connect in real life:",
            bg=SEARCH_PANEL_BG, fg=SEARCH_PANEL_FG_DIM, font=("Segoe UI", 8),
        ).pack(side="left")
        clear_points_btn = self._make_pill_button(points_header, "Clear points", self.on_clear_points)
        clear_points_btn.pack(side="right")
        undo_point_btn = self._make_pill_button(points_header, "Undo last point", self.on_undo_last_point)
        undo_point_btn.pack(side="right", padx=(0, 6))

        points_text_frame = tk.Frame(points_panel, bg=SEARCH_PANEL_BG)
        points_text_frame.pack(fill="x", padx=10, pady=(2, 6))
        # Plain tk.Text, left in normal (editable) state deliberately: Tk's
        # DISABLED state also blocks mouse-drag text selection in some Tk
        # versions, and the task only needs ordinary select/copy (Ctrl+C),
        # not read-only enforcement -- this is a scratch reporting panel the
        # user copies FROM, not a source of truth the app reads back.
        self.points_text = tk.Text(
            points_text_frame, height=6, bg="#0f2130", fg=SEARCH_PANEL_FG,
            insertbackground=SEARCH_PANEL_FG, relief="flat", highlightthickness=1,
            highlightbackground="#3a5a72", font=("Consolas", 9), wrap="none")
        points_scroll = tk.Scrollbar(points_text_frame, command=self.points_text.yview)
        self.points_text.configure(yscrollcommand=points_scroll.set)
        self.points_text.pack(side="left", fill="both", expand=True)
        points_scroll.pack(side="left", fill="y")
        self.points_text.insert("end", POINTS_PANEL_HEADER)

        self._controls = [search_entry, search_btn, self.results_list, go_btn, clear_points_btn]
        self._controls.extend(self._layer_checkbuttons.values())
        self._controls.append(self.connected_roads_cb)
        self._controls.append(self.hide_garbage_cb)
        self._tick_clock()

    # -------------------------------------------------------- chrome helpers

    def _status_divider(self, parent):
        tk.Frame(parent, bg=STATUS_DIVIDER_COLOR, width=1).pack(side="left", fill="y", pady=6)

    def _make_pill_button(self, parent, text, command):
        """Teal/blue-accented button standing in for photo #2's rounded
        pill-shaped "Options"/"Go" style buttons. Plain tk.Button (not
        ttk) so the explicit colors below actually render on Windows;
        genuinely rounded corners aren't worth a custom canvas widget for
        this restyle, per the task's own "without excessive engineering
        effort" guidance."""
        return tk.Button(parent, text=text, command=command, bg=TEAL_ACCENT, fg=TEAL_ACCENT_FG,
                          activebackground=TEAL_ACCENT_ACTIVE, activeforeground=TEAL_ACCENT_FG,
                          relief="flat", bd=0, padx=14, pady=5, font=("Segoe UI", 9, "bold"),
                          highlightthickness=0, cursor="hand2")

    def _make_bezel_button(self, parent, label, command=None):
        """One physical-looking hardware button (RADIO/MEDIA/.../SETUP,
        photo #1). Buttons with no obvious sensible mapping just report
        what they are via the status bar rather than doing nothing
        silently or popping up an intrusive dialog."""
        if command is None:
            def command():
                self._set_status("%s: decorative hardware button (not wired to a function in this "
                                  "read-only map-data viewer)." % label)
        return tk.Button(parent, text=label, command=command, width=9,
                          bg=BEZEL_BUTTON_BG, fg=BEZEL_BUTTON_FG, activebackground=BEZEL_BUTTON_ACTIVE_BG,
                          activeforeground=BEZEL_BUTTON_FG, relief="raised", bd=1,
                          font=("Segoe UI", 8, "bold"), highlightthickness=0, cursor="hand2")

    def _make_knob(self, parent, size=46):
        """Decorative round volume/rotary-knob shape (photo #1's two
        below-screen knobs) -- a styled Canvas, no working rotary
        behavior, per the task's explicit "don't over-engineer fake
        functionality" guidance."""
        c = tk.Canvas(parent, width=size, height=size, bg=BEZEL_COLOR, highlightthickness=0)
        pad = 3
        c.create_oval(pad, pad, size - pad, size - pad, fill=KNOB_FACE_COLOR, outline=KNOB_RIM_COLOR, width=3)
        c.create_oval(size * 0.30, size * 0.20, size * 0.52, size * 0.34, fill=KNOB_HIGHLIGHT_COLOR, outline="")
        c.create_line(size / 2, size / 2, size / 2, pad + 5, fill=KNOB_HIGHLIGHT_COLOR, width=2)
        c.bind("<Button-1>", lambda e: self._set_status(
            "(decorative rotary knob -- not wired to a function in this read-only map-data viewer)"))
        return c

    def _tick_clock(self):
        self.clock_var.set(time.strftime("%I:%M %p").lstrip("0"))
        self.root.after(30000, self._tick_clock)

    def _update_scale_bar(self):
        """Populate the on-screen distance/scale indicator (photo #3/#4's
        rightmost status-bar segment, e.g. "1.5 km" with a tick-mark bar
        beneath it) from the current view scale (pixels/degree)."""
        c = getattr(self, "scale_bar_canvas", None)
        if c is None:
            return
        c.delete("all")
        if self.center_lat is None or self.scale <= 0:
            self.scale_text_var.set("--")
            return
        cos_lat = math.cos(math.radians(self.center_lat)) or 1e-9
        meters_per_px = (111320.0 * abs(cos_lat)) / self.scale
        target_px = 70.0
        nice_m = nice_scale_step(meters_per_px * target_px)
        bar_px = max(4.0, min(78.0, nice_m / meters_per_px))
        if nice_m >= 1000:
            km = nice_m / 1000.0
            text = ("%.0f km" if km >= 10 else "%.1f km") % km
        else:
            text = "%d m" % int(nice_m)
        self.scale_text_var.set(text)
        y = 4
        c.create_line(4, y, 4 + bar_px, y, fill="white", width=2)
        c.create_line(4, y - 2, 4, y + 2, fill="white", width=1)
        c.create_line(4 + bar_px, y - 2, 4 + bar_px, y + 2, fill="white", width=1)

    def _update_breadcrumb_from_hit(self, hit):
        """Best-effort breadcrumb-style display (photo #2's country/city/
        street build-up) from a single flat SearchHit -- this tool has no
        real country->city->street drill-down data, so this is a loose
        evocation, not a faithful reproduction."""
        if hit.kind == "city" and "," in hit.name:
            place, parent = hit.name.split(",", 1)
            self.crumb_var1.set(parent.strip().upper())
            self.crumb_var2.set("CITY")
            self.crumb_var3.set(place.strip().upper())
        elif hit.kind == "city":
            self.crumb_var1.set("")
            self.crumb_var2.set("CITY")
            self.crumb_var3.set(hit.name.upper())
        else:
            self.crumb_var1.set(getattr(self, "_last_query", "").upper())
            self.crumb_var2.set("ROAD")
            self.crumb_var3.set(hit.name.upper())

    def _update_breadcrumb_coords(self, lon, lat):
        self.crumb_var1.set("DIRECT COORDINATES")
        self.crumb_var2.set("")
        self.crumb_var3.set("%.5f, %.5f" % (lon, lat))

    def _on_result_selected(self):
        sel = self.results_list.curselection()
        if not sel:
            return
        self._update_breadcrumb_from_hit(self.search_results[sel[0]])

    # -------------------------------------------------------- bezel actions

    def on_bezel_map(self):
        """"MAP" hardware button -- the one bezel button with an obvious
        sensible mapping for a map-only viewer: re-center/re-home the
        current view (reset any pan offset), like a real unit's MAP
        button returns to the map screen."""
        if self.data is None or self.center_lon is None:
            self._set_status("MAP: nothing loaded yet -- search a place or enter lat/lon first.")
            return
        self.pan_x = self.pan_y = 0.0
        self._redraw()
        self._set_status("MAP: view re-centered.")

    def on_bezel_nav(self):
        """"NAV" hardware button (README §10 "v11 -> v12"): opens the
        "Address entry" screen (AddressEntryDialog), matching the real
        unit's own destination-entry workflow (reference photo #1) --
        Country/City/Street/Number rows, each opening a letter-by-letter
        keyboard (SpellerDialog, reference photo #2) with LIVE per-letter
        enable/disable computed from the real cracked `.rt`/`eeu.cty`/
        `eeu.ctr` data as the user types (see MapData.street_enabled_next_
        chars()/PrefixNameIndex/road_index_reader.rt_enabled_next_chars()
        for exactly how). Only the previously-decorative bezel buttons
        RADIO/MEDIA/PHONE/TONE/TRAFFIC remain purely decorative -- this is
        the first bezel button (besides MAP) with real, functional behavior."""
        if self.data is None:
            self._set_status("NAV: open a map ISO first (File > Open Map ISO...).")
            return
        if self._area_loading or self.busy:
            return
        if self.data.address_data_ready:
            AddressEntryDialog(self)
            return
        self._begin_busy("NAV: loading address-entry data (country list + street name index)...")

        def do_load(progress):
            self.data.load_address_entry_data(progress=progress)

        def done(result, error):
            self._end_busy()
            if error:
                messagebox.showerror("NAV", "Could not load address-entry data: %s" % error)
                self._set_status("NAV: failed to load address-entry data (%s)." % error)
                return
            self._set_status("NAV: address-entry data ready.")
            AddressEntryDialog(self)

        BackgroundTask(self.root, do_load, self._set_status, done).start()

    def on_bezel_traffic(self):
        self._set_status("TRAFFIC: no live traffic data available in this offline map-data viewer.")

    def on_bezel_setup(self):
        messagebox.showinfo(
            "RNS510 Map Viewer -- About",
            "%s\n\n"
            "Read-only viewer for reverse-engineered VW RNS510 navigation map data.\n\n"
            "RADIO / MEDIA / PHONE / TONE / TRAFFIC are decorative, styled after "
            "the real unit's hardware bezel.\n"
            "MAP re-centers the current view.\n"
            "NAV opens the Address entry screen (Country/City/Street/Number, with a "
            "live letter-by-letter keyboard) and can jump the map to a resolved address.\n"
            "SETUP shows this dialog." % APP_TITLE)

    # -------------------------------------------------------------- state

    def _set_status(self, text):
        self.status_var.set(text)

    def _set_controls_enabled(self, enabled):
        state = "normal" if enabled else "disabled"
        for w in getattr(self, "_controls", []):
            try:
                w.configure(state=state)
            except tk.TclError:
                pass

    def _begin_busy(self, msg):
        self.busy = True
        self._set_controls_enabled(False)
        self._set_status(msg)
        self.progress.start(12)

    def _end_busy(self):
        self.busy = False
        self.progress.stop()
        self._set_controls_enabled(self.data is not None)

    # ------------------------------------------------------------- actions

    def on_open_iso(self):
        if self.busy:
            return
        path = filedialog.askopenfilename(
            title="Open Map ISO",
            filetypes=[("ISO images", "*.iso *.ISO"), ("All files", "*.*")],
        )
        if not path:
            return

        if self.data is not None:
            self.data.close()
        self.data = MapData(path)
        # A previous ISO's picked points reference layer/tile_id numbering
        # from a completely different disc -- clear them on a fresh Open,
        # same reasoning as why tile_caches/covered_bbox aren't carried
        # over either.
        self.on_clear_points()
        self._begin_busy("Loading %s ..." % path)

        def do_load(progress):
            self.data.load(progress=progress)
            return path

        def done(result, error):
            self._end_busy()
            if error:
                messagebox.showerror("Open failed", str(error))
                self._set_status("Failed to open ISO: %s" % error)
                self.data = None
                return
            n_tiles = sum(self.data.directories[l]["num_tiles"] for l in FAST_LAYERS)
            n_resolved = sum(len(self.data.geo_indexes[l]) for l in FAST_LAYERS)
            self.iso_label.config(text="Loaded: %s  [%d/%d overview-to-neighborhood tiles ready, %d cities]" % (
                result, n_resolved, n_tiles, self.data.cty_cache.record_count))
            self._set_status("Ready. Search a place/road (or enter lat/lon), then Go.")
            self._set_controls_enabled(True)
            self._start_heavy_layer_load()

        BackgroundTask(self.root, do_load, self._set_status, done).start()

    def _start_heavy_layer_load(self):
        """Kick off HEAVY_LAYER ("mp0", street-level detail) extraction +
        geo-index build in its OWN background BackgroundTask, separate from
        the busy/controls-disabling one "Open Map ISO" itself used -- the
        user can search/pan/zoom (using mg4-mg1) the whole time this runs.
        Shows a subtle status-bar note while it's in progress and clears it
        a few seconds after it finishes; on success, immediately re-checks
        the current viewport so an already-close-zoomed view upgrades to
        mp0 automatically the moment it's ready, with no user action
        needed (README §10)."""
        self.mp0_status_var.set("Loading detailed street-level roads in the background...")

        def do_load(progress):
            return self.data.load_heavy_layer(progress=progress)

        def done(result, error):
            if error:
                self.mp0_status_var.set(
                    "Street-level detail unavailable (%s) -- using neighborhood-level "
                    "detail instead." % error)
                return
            self.mp0_status_var.set("Detailed street-level roads ready.")
            self.root.after(4000, lambda: self.mp0_status_var.set(""))
            # Upgrade the current view right away if it's now eligible for
            # mp0 (e.g. the user is already zoomed in close and was seeing
            # the mg1 fallback) -- otherwise the ordinary pan/zoom debounce
            # would only pick this up on the NEXT pan/zoom.
            self._maybe_reload_viewport(force=True)

        BackgroundTask(self.root, do_load, lambda msg: self.mp0_status_var.set(msg), done).start()

    def on_search(self):
        if self.busy or self.data is None:
            return
        query = self.search_var.get().strip()
        if not query:
            return
        self._last_query = query
        self._begin_busy("Searching for %r ..." % query)

        def do_search(progress):
            return self.data.search_combined(query, limit=40)

        def done(result, error):
            self._end_busy()
            if error:
                messagebox.showerror("Search failed", str(error))
                return
            hits, road_total, city_total = result
            self.search_results = hits
            self.results_list.delete(0, "end")
            for h in hits:
                self.results_list.insert("end", h.label())
            self._set_status(
                "Search: %d result(s) shown (%d road match(es) of %d total, %d city match(es) of %d total). "
                "Double-click a result to jump there." % (
                    len(hits), sum(1 for h in hits if h.kind == "road"), road_total,
                    sum(1 for h in hits if h.kind == "city"), city_total))

        BackgroundTask(self.root, do_search, self._set_status, done).start()

    def on_go_to_result(self):
        sel = self.results_list.curselection()
        if not sel:
            return
        hit = self.search_results[sel[0]]
        self._update_breadcrumb_from_hit(hit)
        self._jump_to(hit.lon, hit.lat, span_deg=hit.jump_span_deg(DEFAULT_JUMP_SPAN_DEG))

    def on_go_to_coords(self):
        try:
            lon = float(self.lon_var.get())
            lat = float(self.lat_var.get())
        except ValueError:
            messagebox.showerror("Invalid input", "Longitude/Latitude must be numbers.")
            return
        self._update_breadcrumb_coords(lon, lat)
        self._jump_to(lon, lat)

    def _jump_to(self, lon, lat, span_deg=None):
        if self.busy or self.data is None:
            return
        if span_deg is None:
            span_deg = DEFAULT_JUMP_SPAN_DEG
        lon_min, lon_max = lon - span_deg, lon + span_deg
        lat_min, lat_max = lat - span_deg, lat + span_deg
        self._begin_busy("Loading map area near (%.5f, %.5f) ..." % (lon, lat))

        # The real post-auto-fit scale (App._initial_scale()) isn't known
        # until AFTER the load returns (it's fit to the loaded features' own
        # bounding box) -- estimate a reasonable starting scale from the
        # requested span so ensure_area_loaded() picks a sensible cumulative
        # layer set for the first paint, same chicken-and-egg workaround v3
        # used (README §10 "v2 -> v3"'s App._estimate_scale_for_span()).
        # **Bug found and fixed (README §10 "v11 -> v12")**: this used to be
        # computed INSIDE do_load_area() below, i.e. on the BackgroundTask's
        # worker thread -- but _estimate_scale_for_span() calls
        # self.canvas.winfo_width()/winfo_height(), and Tk widget calls from
        # a non-main thread are not safe in general. This was never
        # exercised by a prior automated end-to-end test (every existing
        # GUI test drove ensure_area_loaded()/`_maybe_reload_viewport()`
        # directly, with the scale already computed on the main thread, not
        # through `_jump_to()`'s own BackgroundTask) -- it's the "NAV" ->
        # "Start" address-entry feature's own end-to-end test that first
        # exercised this exact path and reproducibly hung waiting for the
        # worker thread's cross-thread winfo call. Fixed by computing
        # `est_scale` HERE, on the main thread, before the worker thread
        # ever starts -- `do_load_area()` now only touches `self.data`
        # (already safe: every other BackgroundTask callsite in this file
        # does the same). Any mismatch between this estimate and the real
        # fitted scale is corrected for free by the
        # _maybe_reload_viewport(force=True) call in done() below, which
        # re-evaluates layers_for_scale() against the real self.scale once
        # it's set -- unchanged from before this fix.
        est_scale = self._estimate_scale_for_span(span_deg)

        # Same cross-thread-Tk-call class of bug as `est_scale` above:
        # `_get_allowed_layers()` reads each layer checkbox's `tk.BooleanVar`
        # and `connected_roads_var.get()` reads another -- both are Tk
        # `Variable.get()` calls, which are just as unsafe to make from the
        # worker thread as a `winfo_*()` call. Evaluated here, on the main
        # thread, for the same reason.
        allowed_layers = self._get_allowed_layers()
        want_adjacency = self.connected_roads_var.get()

        def do_load_area(progress):
            return self.data.ensure_area_loaded(
                lon_min, lon_max, lat_min, lat_max, est_scale, progress=progress,
                allowed_layers=allowed_layers, want_adjacency=want_adjacency)

        def done(result, error):
            self._end_busy()
            if error:
                messagebox.showerror("Load area failed", str(error))
                return
            self.center_lon, self.center_lat = lon, lat
            self.pan_x = self.pan_y = 0.0
            self.features = result["features"]
            # README §10 "v17 -> v18", user's explicit request: a jump opens
            # at the fixed DEFAULT_ZOOM_SPAN_M (5km) level, not auto-fit to
            # whatever bbox this jump's own decoded features happened to
            # have (the old App._initial_scale() behavior -- still used
            # elsewhere for test/ground-truth framing, just not here).
            self.scale = scale_for_zoom_span_m(
                DEFAULT_ZOOM_SPAN_M, self.canvas.winfo_width(), self.canvas.winfo_height())
            self._redraw()
            n_points = sum(len(f["points"]) for f in self.features)
            n_named = sum(1 for f in self.features for (_, _, name) in f.get("named_ranges", ()) if name)
            n_tiles = sum(len(ids) for ids in result["tile_ids"].values())
            self._set_status(
                "Loaded %d tile(s) across %d layer(s) near (%.5f, %.5f): %d road features "
                "(%d named segment runs), %d total vertices. Drag to pan, scroll to zoom." % (
                    n_tiles, len(result["layers"]), lon, lat, len(self.features), n_named, n_points))
            # mp0 may finish building in the background after this initial
            # load returns -- re-check right away so the view folds in mp0's
            # points immediately, not just on the next pan/zoom.
            self._maybe_reload_viewport(force=True)

        BackgroundTask(self.root, do_load_area, self._set_status, done).start()

    def _estimate_scale_for_span(self, span_deg):
        """Rough pixels/degree estimate for a "jump to X" span, used only to
        pick a reasonable starting cumulative layer set (layers_for_scale())
        for the FIRST ensure_area_loaded() call of a jump -- before any
        tiles are decoded, the real auto-fit scale (_initial_scale(), fit to
        the loaded features' own bounding box) isn't known yet. Mirrors
        _initial_scale()'s own "fill ~45% of the smaller canvas dimension"
        formula, just against the requested span instead of a real decoded
        bounding box. Any mismatch against the real post-load scale is
        corrected by the _maybe_reload_viewport(force=True) call right after
        (see _jump_to's done())."""
        w = max(self.canvas.winfo_width(), 200)
        h = max(self.canvas.winfo_height(), 200)
        return 0.45 * min(w, h) / max(span_deg, 1e-6)

    def _initial_scale(self, features, span_deg):
        """Pick pixels/degree so the loaded area roughly fills the canvas
        on first draw -- based on the actual loaded features' bounding box
        when available, falling back to the requested jump span otherwise
        (e.g. a city jump into an area with very sparse/no decoded roads).

        Ignores points further than `outlier_limit` from the center when
        computing that bounding box. Found necessary during this session's
        own real-ISO testing: a single decoded feature can legitimately be
        a long chain whose far end is several tenths of a degree (or, in
        rare cases, close to the full MAX_FEATURE_DRIFT_DEG=3.0 tolerance)
        away from the searched point -- letting one such outlier set the
        fit collapses the initial zoom out to a near-continental scale
        (observed directly: a real Tirana-area load's initial scale, before
        this fix, was blown out by one such chain, making Kavala/Ancona/
        Bari/Split -- all genuinely large cities, just hundreds of km away
        -- outrank Tirana's own label at the resulting zoomed-out
        min-city-area threshold). Clipping to a generous multiple of the
        requested jump span keeps the initial framing sane while still
        rendering the full outlier chain (this only affects the ONE-TIME
        initial zoom pick, not what gets drawn)."""
        w = max(self.canvas.winfo_width(), 200)
        h = max(self.canvas.winfo_height(), 200)
        cos_lat = math.cos(math.radians(self.center_lat)) or 1e-9
        outlier_limit = span_deg * 2.5
        max_wx = max_wy = 1e-6
        for feat in features:
            for lon, lat in feat["points"]:
                wx = abs((lon - self.center_lon) * cos_lat)
                wy = abs(lat - self.center_lat)
                if wx > outlier_limit or wy > outlier_limit:
                    continue
                if wx > max_wx:
                    max_wx = wx
                if wy > max_wy:
                    max_wy = wy
        if max_wx <= 1e-6 and max_wy <= 1e-6:
            max_wx = max_wy = span_deg * cos_lat
        return 0.45 * min(w, h) / max(max_wx, max_wy)

    # ------------------------------------------------------------- canvas

    def _to_canvas(self, lon, lat):
        # Perf (README §10 "v18 -> v19"): use the canvas size _redraw()
        # already cached on self (see __init__'s own comment) instead of
        # querying Tk live -- this function runs per-vertex, potentially
        # hundreds of thousands of times per redraw. Falls back to a live
        # query only if called before the first redraw has ever run.
        w = self._canvas_w
        h = self._canvas_h
        if w is None or h is None:
            w = self.canvas.winfo_width()
            h = self.canvas.winfo_height()
        x, y = project_point(lon, lat, self.center_lon, self.center_lat, self.scale)
        return w / 2 + x + self.pan_x, h / 2 + y + self.pan_y

    def _visible_bbox(self):
        if self.center_lon is None:
            return None
        w = max(self.canvas.winfo_width(), 50)
        h = max(self.canvas.winfo_height(), 50)
        return compute_visible_bbox(self.center_lon, self.center_lat, self.scale, self.pan_x, self.pan_y, w, h)

    def _ensure_center_city_included(self, cities):
        """Guard against a known limitation of using raw bbox area as a
        zoom-importance proxy (see city_reader.py's docstring): a WIDE
        viewport spanning several countries/regions can contain other
        administrative entries with a bigger bounding box than the one
        place actually at the center of the current view (found directly
        during this session's own real-ISO testing -- a Tirana-centered
        view at a fairly zoomed-out scale showed Ohrid/Struga/Durres
        labels, all real and legitimately nearby, but not Tirana itself,
        because several of those happened to have larger eeu.cty bounding
        boxes). Rather than build a full importance-scoring model, this
        does the minimal fix: if none of the area-ranked `cities` actually
        contains the current center point, look up whatever eeu.cty record
        DOES contain it (any area, tight query box) and swap it in for the
        smallest-area entry already selected."""
        if self.center_lon is None or self.data is None or self.data.cty_cache is None:
            return cities
        # Look up whatever eeu.cty record MOST TIGHTLY contains the exact
        # center point (smallest bbox area among all containing records --
        # per README §3.8's nested-bbox hierarchy, that should be the most
        # specific real place at the center, e.g. "TIRANE" itself rather
        # than a much bigger surrounding rural municipality that also
        # happens to contain the point). Deliberately does NOT stop just
        # because SOME record in `cities` already contains the center --
        # a large neighboring admin area's bbox can innocently contain the
        # center point too (observed directly: with a Tirana-centered view,
        # "ZALL BASTAR", a rural municipality northeast of the city, has a
        # bbox that also covers central Tirana's coordinates) without being
        # the place actually being viewed.
        near_center = self.data.cty_cache.query(
            self.center_lon - 0.02, self.center_lon + 0.02,
            self.center_lat - 0.02, self.center_lat + 0.02,
            min_area=0.0, limit=20, max_area=CITY_MAX_AREA_DEG2)
        near_center = [
            c for c in near_center
            if c.bbox[0] <= self.center_lon <= c.bbox[2] and c.bbox[1] <= self.center_lat <= c.bbox[3]
        ]
        if not near_center:
            return cities
        near_center.sort(key=lambda c: (c.bbox[2] - c.bbox[0]) * (c.bbox[3] - c.bbox[1]))
        winner = near_center[0]
        if any(c.index == winner.index for c in cities):
            return cities  # the most-specific center match is already represented
        rest = [c for c in cities if c.index != winner.index]
        return [winner] + rest[:max(0, MAX_CITY_LABELS - 1)]

    def _redraw(self):
        """Full redraw of the map view.

        **README §10 "v17 -> v18" rendering rework**: every road-point DOT
        and connected-roads LINE used to be its own real Tkinter canvas
        item (`canvas.create_oval()`/`canvas.create_line()`) -- at a
        typical dense real bbox with multiple layers pooled and "Draw
        connected roads" on, that's 30,000-60,000+ individual canvas
        items. Tkinter's canvas (backed by Tcl's single-threaded,
        non-batched, per-item canvas engine) is not built to manage that
        many discrete items -- the app became genuinely unresponsive
        ("Not Responding", ~4GB memory) while panning/zooming under that
        load, and this does NOT improve with faster CPU/disk since it's a
        toolkit architectural limit, not an I/O or raw-compute bottleneck.

        User's explicit, deliberate architectural decision (discussed and
        confirmed, not a workaround guessed at here): keep Tkinter as the
        app shell -- every dialog/checkbox/click-handler below is
        unchanged -- but replace the DRAWING mechanism for points/lines
        with rasterization into a single bitmap: every dot and every
        high-confidence connected-roads edge is drawn into one
        `PIL.Image` via `PIL.ImageDraw`, converted to one
        `ImageTk.PhotoImage`, and shown as exactly ONE
        `canvas.create_image()` item -- regardless of how many points/
        edges it contains. `self._current_photo` keeps a live Python
        reference to that PhotoImage (Tkinter garbage-collects a
        PhotoImage with no surviving reference -- a classic gotcha; the
        image would otherwise vanish from screen on the next GC pass).

        Explicitly EXCLUDED from rasterization, still drawn as normal,
        separate, lightweight canvas items ON TOP of the one bitmap image
        (always low-count -- tens, not tens-of-thousands -- and benefit
        from staying real/interactive Tkinter items): road/city text
        labels (`canvas.create_text`), the center/search marker, and the
        click-to-identify picked-point rings/numbers (`self.picked_points`).
        Click-to-identify itself (`find_nearest_point()`/
        `find_nearest_line_segment()`, see their own docstrings) was
        already implemented entirely against this same in-memory point/
        edge DATA, never by inspecting canvas item types/positions
        (no `find_withtag`/`find_closest` against oval/line items
        anywhere in this file) -- so it is completely unaffected by there
        no longer being individual oval/line canvas items to inspect.

        Real measured redraw timing (Sofia bbox, see README §10 "v17 ->
        v18" for the full numbers/methodology) dropped from ~0.4-0.5s
        (the old per-item canvas build, already the subject of the
        "v3 -> v4" pan-drag workaround below) to a small fraction of that
        for the SAME point/edge counts, since Pillow's C-level ImageDraw
        is vectorized/batched instead of paying Tcl per-item overhead
        30,000-60,000+ times over."""
        self.canvas.delete("all")
        if self.center_lon is None:
            self._current_photo = None
            self._current_image = None
            self._update_scale_bar()
            return
        w = max(self.canvas.winfo_width(), 1)
        h = max(self.canvas.winfo_height(), 1)
        # Cache for _to_canvas() (see __init__'s own comment, README §10
        # "v18 -> v19") -- every per-vertex/per-edge _to_canvas() call below
        # reads these instead of re-querying Tk.
        self._canvas_w, self._canvas_h = w, h

        # Single rasterization target for this redraw -- every dot/edge
        # below is drawn into this PIL image, never as its own canvas item.
        # RGB (not RGBA): the map background is fully opaque everywhere
        # (BG_COLOR), so there's no need for a real alpha channel here.
        img = Image.new("RGB", (w, h), BG_COLOR)
        draw = ImageDraw.Draw(img)

        placed = []  # [(name, x, y), ...] already-drawn labels, for de-dup

        def far_enough(name, x, y):
            for n2, x2, y2 in placed:
                if n2 == name and (x2 - x) ** 2 + (y2 - y) ** 2 < LABEL_DEDUP_PX ** 2:
                    return False
            return True

        connected_roads_on = self.connected_roads_var.get()

        road_label_candidates = []
        for feat in self.features:
            pts = feat["points"]
            if len(pts) < 2:
                continue
            ranges = feat.get("named_ranges") or [(0, len(pts) - 1, None)]

            # Connected-roads mode (README §10 "v9 -> v10"): look up this
            # feature's own cached resolve_topology_adjacency() result (by
            # layer/tile_id/feature_index, the same tags click-to-identify
            # already relies on -- v6 -> v7) and, ONLY if its confidence is
            # "high", draw its real edges as actual canvas.create_line()
            # segments IN ADDITION TO the usual per-vertex dots below
            # (README §10 "v16 -> v17": previously the dots for a
            # high-confidence feature were skipped entirely once its lines
            # were drawn -- the user explicitly asked for both together, so
            # every raw point stays visible for debugging even where a line
            # was also successfully derived). A feature with no cached
            # result yet (tile not decoded with want_adjacency, or
            # resolution failed/low-confidence) just doesn't get any lines
            # -- this is a per-FEATURE decision, never a guessed/low-
            # confidence line. `adj` is looked up once per feature, not
            # once per named sub-range, since a feature's adjacency graph
            # spans its whole point list, not just one named run. `adj` is
            # also reused below by _on_point_pick()'s edge-click fallback
            # (via find_nearest_line_segment()/_iter_high_confidence_edges(),
            # which apply this EXACT same found+confidence=="high" gate) so
            # an edge can only ever be picked if it's actually drawn here.
            adj = None
            if connected_roads_on and self.data is not None:
                layer = feat.get("layer")
                tile_id = feat.get("tile_id")
                f_idx = feat.get("feature_index")
                if layer is not None and tile_id is not None and f_idx is not None:
                    tlist = self.data.topo_caches.get(layer, {}).get(tile_id)
                    if tlist is not None and 0 <= f_idx < len(tlist):
                        cand = tlist[f_idx]
                        if cand.get("found") and cand.get("confidence") == "high":
                            adj = cand

            if adj is not None:
                # Real, derived connectivity -- iterate the graph's own
                # unique edges (not a naive consecutive-index walk: a
                # junction point can have 3+ real neighbors, so this is a
                # general graph, not necessarily a simple path).
                for a, b in adj["edges"]:
                    if a >= len(pts) or b >= len(pts):
                        continue  # defensive -- should not happen, never trust blindly
                    ax, ay = self._to_canvas(*pts[a])
                    bx, by = self._to_canvas(*pts[b])
                    edge_name = _name_at_point(feat.get("named_ranges"), a) or \
                        _name_at_point(feat.get("named_ranges"), b)
                    if edge_name:
                        line_color, line_width = ROAD_COLOR_MAJOR, 1.6
                    else:
                        line_color, line_width = ROAD_COLOR_UNNAMED, 1.0
                    # Rasterized into `img` (README §10 "v17 -> v18"), not a
                    # real canvas item -- see _redraw()'s own docstring.
                    # PIL's line width is an int pixel count (no fractional
                    # anti-aliased width like Tk's) -- round, floor at 1px.
                    draw.line([(ax, ay), (bx, by)], fill=line_color, width=max(1, round(line_width)))

            for start, end, name in ranges:
                seg = pts[start:end + 1]
                if len(seg) < 2:
                    continue
                coords = []
                for lon, lat in seg:
                    cx, cy = self._to_canvas(lon, lat)
                    coords.extend((cx, cy))
                n_vertices = end - start + 1
                if n_vertices >= 60:
                    radius = 1.6
                elif n_vertices >= 15:
                    radius = 1.3
                elif name is not None:
                    radius = 1.1
                else:
                    radius = 1.0
                # Dots, not connected lines: drawing each decoded vertex as
                # an independent point (instead of connecting consecutive
                # points with create_line) sidesteps the still-unsolved
                # segmentation problem entirely (README S3.6/S8) -- a
                # feature's point sequence can legitimately jump between
                # unrelated real road segments with no marker of where one
                # ends and the next begins, which previously rendered as
                # long, wrong-looking straight "teleport" lines. Plotting
                # points independently can never draw a line between two
                # unrelated points, since nothing is ever connected; dense
                # real road geometry still reads as a recognizable street
                # shape from the point density alone. User-requested change.
                #
                # Color (README §10 "v16 -> v17"): every dot is now the
                # single, unambiguous DOT_COLOR (red) -- replaces the old
                # per-importance ROAD_COLOR_MAJOR/MINOR/UNNAMED gray/gold
                # fills, per the user's explicit request ("make the points
                # red dots not gray ones").
                #
                # Drawn UNCONDITIONALLY now, even for a feature whose real
                # connectivity WAS resolved with high confidence above
                # (README §10 "v9 -> v10" used to skip dots here in that
                # case, to avoid "clutter"). User's explicit request this
                # session: "make the dots visible when roads are visible
                # also" -- so the user can see every raw decoded point
                # AND the derived connecting lines at once, which is exactly
                # the visibility the click-to-identify debugging workflow
                # (README §10 "v16 -> v17", edge click-to-identify) needs:
                # every point is inspectable, whether or not it ended up
                # part of a resolved edge.
                # Rasterized into `img` (README §10 "v17 -> v18"), not a
                # real canvas item per point -- see _redraw()'s own
                # docstring for why (this loop alone used to be tens of
                # thousands of individual canvas.create_oval() items at a
                # dense real bbox).
                for i in range(0, len(coords), 2):
                    px, py = coords[i], coords[i + 1]
                    draw.ellipse(
                        [px - radius, py - radius, px + radius, py + radius],
                        fill=DOT_COLOR)

                if name:
                    x0, y0 = coords[0], coords[1]
                    x1, y1 = coords[-2], coords[-1]
                    pix_len = math.hypot(x1 - x0, y1 - y0)
                    if pix_len >= MIN_LABEL_PIXEL_LEN:
                        mid = (start + end) // 2
                        mlon, mlat = pts[mid]
                        mx, my = self._to_canvas(mlon, mlat)
                        road_label_candidates.append((pix_len, name, mx, my))

        # Hand the finished rasterization off to Tk as ONE canvas item
        # (README §10 "v17 -> v18") -- everything drawn above (every dot,
        # every high-confidence connected-roads line) is now baked into
        # `img`; this is the ONLY canvas item this method creates for all
        # of that content, no matter how many points/edges it contains.
        # `anchor="nw"` places its (0, 0) pixel at canvas (0, 0), matching
        # _to_canvas()'s own coordinate system exactly. The PhotoImage
        # reference is kept on `self` (`self._current_photo`) -- Tkinter
        # does not keep its own strong reference to a PhotoImage, so
        # without this the image would be garbage-collected and vanish
        # from screen the moment this method returns. `self._current_image`
        # (the raw PIL Image, pre-PhotoImage-conversion) is ALSO kept, purely
        # so test_map_viewer.py can sample real pixel colors at known
        # (x, y) canvas coordinates directly (Image.getpixel()) instead of
        # inspecting Tk canvas items that no longer exist per-point/edge --
        # not read anywhere else in this file.
        self._current_image = img
        self._current_photo = ImageTk.PhotoImage(img)
        self.canvas.create_image(0, 0, image=self._current_photo, anchor="nw")

        # Draw the most visually-prominent (longest on-screen) runs' labels
        # first so they win the dedup slots over short, easily-repeated ones.
        road_label_candidates.sort(key=lambda t: -t[0])
        for _, name, mx, my in road_label_candidates:
            if not (-20 <= mx <= w + 20 and -20 <= my <= h + 20):
                continue
            if not far_enough(name, mx, my):
                continue
            self.canvas.create_text(mx, my, text=name, fill=ROAD_LABEL_COLOR,
                                     font=("Segoe UI", 8), anchor="center")
            placed.append((name, mx, my))

        # City/town labels -- queried fresh each redraw (CtyCache is cheap).
        if self.data is not None and self.data.cty_cache is not None:
            vb = self._visible_bbox()
            if vb is not None:
                lon_min, lon_max, lat_min, lat_max = vb
                min_area = city_min_area_for_scale(self.scale)
                cities = self.data.cty_cache.query(
                    lon_min, lon_max, lat_min, lat_max, min_area=min_area, limit=MAX_CITY_LABELS,
                    max_area=CITY_MAX_AREA_DEG2)
                cities = self._ensure_center_city_included(cities)
                for c in cities:
                    clon, clat = c.repr_point
                    cx, cy = self._to_canvas(clon, clat)
                    if not (0 <= cx <= w and 0 <= cy <= h):
                        continue
                    if not far_enough(c.name, cx, cy):
                        continue
                    # Small SQUARE marker (not circular) -- photo #4's dark-
                    # background city dots, adapted proportionately to this
                    # tool's light cream map theme (dark navy square reads
                    # clearly against BG_COLOR).
                    r = 3
                    self.canvas.create_rectangle(cx - r, cy - r, cx + r, cy + r, fill=CITY_DOT_COLOR, outline="")
                    lon_min_b, lat_min_b, lon_max_b, lat_max_b = c.bbox
                    area = (lon_max_b - lon_min_b) * (lat_max_b - lat_min_b)
                    is_big = area >= BIG_CITY_AREA_DEG2
                    font = ("Segoe UI", 11 if is_big else 9, "bold" if is_big else "normal")
                    self.canvas.create_text(cx + 6, cy, text=c.name, fill=CITY_LABEL_COLOR,
                                             font=font, anchor="w")
                    placed.append((c.name, cx, cy))

        # Center/search marker -- orange circle with a directional triangle
        # (photos #3/#4's "current position" marker style), drawn last (on
        # top). The triangle has no real heading data behind it (this tool
        # doesn't track a direction of travel) -- it's fixed pointing up,
        # purely for the visual silhouette match.
        mx, my = self._to_canvas(self.center_lon, self.center_lat)
        r = 7
        self.canvas.create_oval(mx - r - 5, my - r - 5, mx + r + 5, my + r + 5, outline=MARKER_FILL, width=1)
        self.canvas.create_oval(mx - r, my - r, mx + r, my + r, fill=MARKER_FILL, outline=MARKER_OUTLINE, width=2)
        tri = 5
        self.canvas.create_polygon(
            mx, my - tri,
            mx - tri * 0.8, my + tri * 0.6,
            mx + tri * 0.8, my + tri * 0.6,
            fill="white", outline=MARKER_OUTLINE, width=1)

        # Click-to-identify picks (README §10 "v6 -> v7", connecting line
        # added in "v7 -> v8") -- drawn LAST, on top of everything including
        # the center marker, since they're the user's active working set
        # for this session. Positioned from each pick's own stored
        # (lon, lat), not from self.features, so a mark/line stays
        # correctly placed across every future pan/zoom/reload regardless
        # of what tiles happen to be pooled at redraw time.
        #
        # Connecting line: drawn between CONSECUTIVE picks in the order the
        # user clicked them (self.picked_points' own list order, i.e. by
        # pick number), as immediate visual feedback for the ground-truth
        # connectivity workflow -- lets the user see and confirm the path
        # they're specifying before reporting it back in chat. Drawn first
        # (before the rings/labels below) so the rings sit visually on top.
        if len(self.picked_points) >= 2:
            line_coords = []
            for p in self.picked_points:
                px, py = self._to_canvas(p["lon"], p["lat"])
                line_coords.extend((px, py))
            self.canvas.create_line(*line_coords, fill=PICK_MARK_COLOR, width=2, dash=(4, 2))

        for p in self.picked_points:
            px, py = self._to_canvas(p["lon"], p["lat"])
            if not (-30 <= px <= w + 30 and -30 <= py <= h + 30):
                continue  # off-screen -- still in the panel/list, just not drawn
            ring_r = 6
            self.canvas.create_oval(
                px - ring_r, py - ring_r, px + ring_r, py + ring_r,
                outline=PICK_MARK_HALO, width=4)
            self.canvas.create_oval(
                px - ring_r, py - ring_r, px + ring_r, py + ring_r,
                outline=PICK_MARK_COLOR, width=2)
            label = str(p["number"])
            self.canvas.create_text(
                px + ring_r + 3, py - ring_r - 3, text=label, fill=PICK_MARK_HALO,
                font=("Segoe UI", 9, "bold"), anchor="w", width=0)
            self.canvas.create_text(
                px + ring_r + 2, py - ring_r - 4, text=label, fill=PICK_MARK_COLOR,
                font=("Segoe UI", 9, "bold"), anchor="w")

        self._update_scale_bar()

    def _on_drag_start(self, event):
        self._drag_start = (event.x, event.y, self.pan_x, self.pan_y)
        self._drag_last_xy = (event.x, event.y)

    def _on_drag_move(self, event):
        # Perf fix (README §10 "v3 -> v4", pan-drag): dragging used to call
        # the full _redraw() (delete + recreate every canvas item) on every
        # single mouse-move tick, which measured ~0.4-0.5s per redraw on a
        # moderately dense mp0-level view -- unusably choppy for a
        # continuous drag gesture. A pure pan never changes which pixel any
        # already-drawn point should be at relative to any other, so during
        # the drag we just shift every existing canvas item by the mouse's
        # incremental delta (canvas.move, a cheap coordinate-only update),
        # and only pay for a real, accurate _redraw() once the drag
        # actually stops (_on_drag_end) or a zoom/new-data event happens.
        #
        # README §10 "v17 -> v18": since the point/edge rasterization rework,
        # this same `canvas.move("all", ...)` now moves exactly ONE image
        # item (plus the small number of label/marker/pick items) instead of
        # tens of thousands of individual ovals/lines -- trivially cheap
        # regardless of how many points/edges are behind it, vs. the old
        # per-item move cost that scaled with point count. The one visible
        # tradeoff (unchanged from before, just now purely a bitmap-edge
        # effect instead of a point-count one): a moved-but-not-yet-redrawn
        # image shows slightly stale pixels/edges right at the canvas
        # boundary until the drag ends and a real _redraw() runs -- expected,
        # not a bug.
        if self._drag_start is None:
            return
        sx, sy, px, py = self._drag_start
        self.pan_x = px + (event.x - sx)
        self.pan_y = py + (event.y - sy)
        lx, ly = self._drag_last_xy
        dx, dy = event.x - lx, event.y - ly
        if dx or dy:
            self.canvas.move("all", dx, dy)
        self._drag_last_xy = (event.x, event.y)
        self._schedule_viewport_check()

    def _on_drag_end(self, event):
        # Reconcile: a real _redraw() from the final pan_x/pan_y, so item
        # positions are exact (not accumulated-move drift) and anything
        # newly revealed at the canvas edges gets drawn.
        self._drag_start = None
        if self.center_lon is not None:
            self._redraw()

    def _on_zoom(self, event, delta=None):
        """Step exactly one discrete real-world ZOOM_LEVELS_M entry per
        wheel tick (README §10 "v17 -> v18", user's explicit request for
        real-hardware-style fixed zoom steps instead of the previous
        continuous `scale *= 1.15`). `nearest_zoom_level_index()` finds
        which level the CURRENT scale is closest to, so this steps
        correctly even right after a jump (which opens at
        DEFAULT_ZOOM_SPAN_M) or after a test sets `self.scale` directly to
        an arbitrary value."""
        if self.center_lon is None:
            return
        delta = event.delta if delta is None else delta
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        idx = nearest_zoom_level_index(self.scale, w, h)
        if delta > 0:
            idx = min(idx + 1, len(ZOOM_LEVELS_M) - 1)  # zoom IN -> narrower span
        else:
            idx = max(idx - 1, 0)                       # zoom OUT -> wider span
        new_scale = scale_for_zoom_span_m(ZOOM_LEVELS_M[idx], w, h)
        ratio = new_scale / self.scale

        cx, cy = event.x - w / 2, event.y - h / 2
        # keep the point under the cursor fixed on screen: pan' =
        # pan*ratio + (mouse - canvas_center)*(1-ratio)
        self.pan_x = self.pan_x * ratio + cx * (1 - ratio)
        self.pan_y = self.pan_y * ratio + cy * (1 - ratio)
        self.scale = new_scale
        self._redraw()
        self._schedule_viewport_check()

    # ------------------------------------------- click-to-identify (v6 -> v7)

    def _on_point_pick(self, event):
        """Right-click handler (<Button-3>, see _build_widgets): convert the
        click to (lon, lat) via canvas_to_lonlat() (the exact inverse of
        _to_canvas()), then look up the nearest currently-rendered point
        via find_nearest_point() (a pure function -- see its own docstring
        for the pixel-distance metric and cutoff). On a hit: assign it the
        next running pick number, remember it in self.picked_points (so its
        mark survives future pans/zooms/redraws), append a row to the
        picked-points text panel, and redraw so the new ring+number shows
        immediately.

        README §10 "v16 -> v17": if nothing is within POINT_PICK_RADIUS_PX
        of a POINT, this now falls back to find_nearest_line_segment() --
        a click on (or very near) a rendered connected-roads LINE identifies
        the specific EDGE it landed on and adds BOTH its real endpoints as a
        linked pair (see _add_edge_pick() below), for debugging the
        topology/connectivity resolution (§3.6): the user can click a
        specific drawn line and get exactly which two points it connects,
        to report back whether that connection is right or wrong. Only a
        click that misses BOTH a point and a rendered edge is a true miss
        (plain status message, not an error -- clicking empty map space is
        an ordinary, expected outcome)."""
        if self.data is None or self.center_lon is None:
            self._set_status("No map loaded -- nothing to identify yet.")
            return
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        click_lon, click_lat = canvas_to_lonlat(
            event.x, event.y, self.center_lon, self.center_lat, self.scale, self.pan_x, self.pan_y, w, h)
        info = find_nearest_point(self.features, click_lon, click_lat, self.center_lat, self.scale)
        if info is not None:
            self._point_pick_counter += 1
            info = dict(info)
            info["number"] = self._point_pick_counter
            self.picked_points.append(info)
            self._append_picked_point_row(info)
            self._redraw()
            self._set_status(
                "Point #%d identified: layer=%s tile_id=%s feature=%s point=%s (%.6f, %.6f)%s -- "
                "see the picked-points panel below to copy its full info." % (
                    info["number"], info["layer"], info["tile_id"], info["feature_index"], info["point_index"],
                    info["lon"], info["lat"], (" name=%s" % info["name"]) if info["name"] else ""))
            return

        if self.connected_roads_var.get():
            edge = find_nearest_line_segment(
                self.features, self.data.topo_caches, click_lon, click_lat, self.center_lat, self.scale)
            if edge is not None:
                self._add_edge_pick(*edge)
                return

        self._set_status(
            "No rendered point or road segment within %dpx of that click -- try clicking closer to a dot "
            "or a connected-roads line." % int(POINT_PICK_RADIUS_PX))

    def _add_edge_pick(self, info_a, info_b):
        """Record a picked EDGE (README §10 "v16 -> v17", find_nearest_
        line_segment()'s result): adds BOTH endpoints as two new, normally-
        numbered picks (so they appear in the picked-points panel/canvas
        exactly like any other pick, reusing all the existing pick
        infrastructure -- rings, the pick-order connecting line, undo,
        clear), but tags each with the OTHER one's pick number as
        "edge_partner" and inserts a divider row in the panel -- so it's
        unambiguous, both on screen and in the copy/paste panel text, that
        these two specific points came from clicking one specific drawn
        road segment, not two independent point-clicks."""
        self._point_pick_counter += 1
        a = dict(info_a)
        a["number"] = self._point_pick_counter
        self._point_pick_counter += 1
        b = dict(info_b)
        b["number"] = self._point_pick_counter
        a["edge_partner"] = b["number"]
        b["edge_partner"] = a["number"]
        self.picked_points.append(a)
        self.picked_points.append(b)
        self.points_text.insert(
            "end", "-- edge pick: point #%d <-> point #%d (clicked a connected-road segment) --\n" % (
                a["number"], b["number"]))
        self._append_picked_point_row(a)
        self._append_picked_point_row(b)
        self._redraw()
        self._set_status(
            "Edge identified: connects point #%d (layer=%s tile_id=%s point=%s, %.6f, %.6f) <-> "
            "point #%d (layer=%s tile_id=%s point=%s, %.6f, %.6f) -- these two points are LINKED by a "
            "specific drawn road segment (not two independent clicks); see the picked-points panel." % (
                a["number"], a["layer"], a["tile_id"], a["point_index"], a["lon"], a["lat"],
                b["number"], b["layer"], b["tile_id"], b["point_index"], b["lon"], b["lat"]))

    @staticmethod
    def _format_picked_point_row(info):
        """Format one plain-text row for `info` (an identifying-info dict
        from find_nearest_point()/find_nearest_line_segment(), plus
        "number") -- kept as a single "|"-separated line per pick so the
        whole panel is easy to select/copy/paste verbatim into a chat
        message. README §10 "v16 -> v17": if `info` came from an edge click
        (carries an "edge_partner" pick number), the name column also shows
        which other pick number it's linked to, so a row stays
        self-explanatory even if it's copied out of context from the
        "-- edge pick: ... --" divider line _add_edge_pick() inserts above
        it."""
        name_field = info["name"] or "-"
        partner = info.get("edge_partner")
        if partner is not None:
            name_field = "%s [edge<->#%d]" % (name_field, partner)
        return "%-2d | %-5s | %-7s | %-11s | %-11s | %-16s | %-9s | %-10.6f | %-9.6f | %s\n" % (
            info["number"],
            info["layer"] or "-",
            info["tile_id"] if info["tile_id"] is not None else "-",
            info["tile_offset"] if info["tile_offset"] is not None else "-",
            info["feature_index"] if info["feature_index"] is not None else "-",
            info["feature_byte_offset"] if info["feature_byte_offset"] is not None else "-",
            info["point_index"],
            info["lon"], info["lat"],
            name_field,
        )

    def _append_picked_point_row(self, info):
        """Append one row (see _format_picked_point_row()) to the
        picked-points panel and scroll to show it."""
        self.points_text.insert("end", self._format_picked_point_row(info))
        self.points_text.see("end")

    def _rebuild_points_panel(self):
        """Fully redraw the picked-points text panel from self.picked_points
        -- used by on_undo_last_point() (and reusable for any future bulk
        edit) instead of trying to surgically delete one line from a Text
        widget, since the pick list is always small (tens of rows at most)
        and a full rebuild is simple and can't get the line indexing wrong.
        README §10 "v16 -> v17": re-inserts the "-- edge pick: ... --"
        divider line in front of the FIRST of an edge-linked pair (detected
        via each pick's own "edge_partner" tag), so the edge-click
        indication survives a rebuild (e.g. after an unrelated undo),
        not just the initial insert."""
        self.points_text.delete("1.0", "end")
        self.points_text.insert("end", POINTS_PANEL_HEADER)
        for i, p in enumerate(self.picked_points):
            partner = p.get("edge_partner")
            # Print the divider once, right before the FIRST of a pair --
            # i.e. skip it when the immediately-preceding row IS this pick's
            # own partner (that means we're at the SECOND half, already
            # introduced by the divider printed just above it).
            prev_number = self.picked_points[i - 1]["number"] if i > 0 else None
            if partner is not None and prev_number != partner:
                self.points_text.insert(
                    "end", "-- edge pick: point #%d <-> point #%d (clicked a connected-road segment) --\n" % (
                        p["number"], partner))
            self.points_text.insert("end", self._format_picked_point_row(p))
        self.points_text.see("end")

    def on_clear_points(self):
        """"Clear points" button: reset the running pick list/counter and
        the text panel back to just its header, and redraw so the marks
        (and the connecting line) disappear from the canvas immediately."""
        self.picked_points = []
        self._point_pick_counter = 0
        self.points_text.delete("1.0", "end")
        self.points_text.insert("end", POINTS_PANEL_HEADER)
        self._redraw()
        self._set_status("Cleared all picked points.")

    def on_undo_last_point(self):
        """"Undo last point" button: remove only the most recently picked
        point (not the whole set) -- for correcting a single mis-click
        without having to re-click everything from scratch. Also rewinds
        the running pick-number counter, so the next new pick reuses the
        removed point's number rather than leaving a gap (e.g. undo #7,
        then the next click becomes #7 again, not #8)."""
        if not self.picked_points:
            self._set_status("No picked points to undo.")
            return
        removed = self.picked_points.pop()
        self._point_pick_counter = self.picked_points[-1]["number"] if self.picked_points else 0
        self._rebuild_points_panel()
        self._redraw()
        self._set_status("Undid point #%d (layer=%s point=%s) -- %d point(s) remaining." % (
            removed["number"], removed["layer"], removed["point_index"], len(self.picked_points)))

    # ------------------------------------------------- layer visibility (v8 -> v9)

    def _get_allowed_layers(self):
        """The set of layers currently CHECKED in the "Show layers:" row --
        passed as `allowed_layers` to every MapData.ensure_area_loaded()
        call so an unchecked layer is excluded from the pooled/rendered set
        (README §10 "v8 -> v9"). As of "v16 -> v17" this is now the ONLY
        restriction on what gets pooled -- there is no more automatic,
        scale-based gate on top of it (see MapData.ensure_area_loaded()'s
        own docstring). All-checked (the default) returns the full
        ALL_LAYERS set, which is a no-op restriction -- every layer
        `available_layers()` reports gets pooled, at every scale."""
        return {layer for layer, var in self.layer_visible.items() if var.get()}

    def _on_layer_visibility_changed(self):
        """Checkbutton command: toggling ANY layer checkbox immediately
        reloads the current viewport so the visible layers update right
        away, without requiring a pan/zoom first. Reuses the exact same
        force-reload path the mp0-ready fold-in and jump/search already use
        (App._maybe_reload_viewport(force=True)) -- this only re-evaluates
        `available_layers() ∩ allowed_layers` (README §10 "v16 -> v17": no
        longer also intersected with a scale-dependent set), it never
        eagerly loads a layer that isn't actually available yet (e.g.
        re-checking mp0 before its own background geo-index build has
        finished still does not trigger mp0's own extraction/build or an
        mp0 tile fetch -- it just won't be in `available_layers()` yet)."""
        if self.data is None or self.center_lon is None:
            return  # nothing loaded yet -- the checkbox state is remembered for when it is
        self._maybe_reload_viewport(force=True)

    # --------------------------------------------- connected roads (v9 -> v10)

    def _on_connected_roads_changed(self):
        """Checkbutton command for "Draw connected roads" (README §10
        "v9 -> v10"): reuses the exact same force-reload path the
        layer-visibility checkboxes already use
        (App._maybe_reload_viewport(force=True)) rather than a plain
        self._redraw(), because turning connected-roads mode ON needs
        MapData.ensure_area_loaded()'s `want_adjacency` gate to actually
        run (so any currently-pooled tile that doesn't yet have a cached
        resolve_topology_adjacency() result gets it computed, in the
        background, before the next redraw) -- a plain redraw would just
        fall back to dots for every tile whose adjacency hasn't been
        resolved yet, silently doing nothing visible on the first toggle.
        Turning it OFF doesn't strictly need a reload (no new data is
        needed to fall back to dots), but reusing the same path keeps this
        one simple, consistent code path for both directions."""
        if self.data is None or self.center_lon is None:
            return  # nothing loaded yet -- the checkbox state is remembered for when it is
        self._maybe_reload_viewport(force=True)

    # ------------------------------------------- oscillation filter (v10 -> v11)

    def _on_hide_garbage_changed(self):
        """Checkbutton command for "Hide decode garbage" (README §10
        "v10 -> v11"): unlike the layer-visibility/connected-roads
        checkboxes, this doesn't just change which already-decoded points
        get POOLED or how they're DRAWN -- decode_features()'s own output
        for a given tile genuinely differs between trim_oscillation
        True/False (that's the whole point of the toggle), so any
        already-decoded tile is now stale. MapData.set_trim_oscillation()
        handles that (resets tile_caches/topo_caches to empty per-layer
        dicts, a one-time re-decode cost on toggle); this handler just
        calls it and then reuses the same force-reload path every other
        checkbox in this UI already uses, so the (now-empty) caches get
        repopulated under the new setting before the next redraw."""
        if self.data is None or self.center_lon is None:
            return  # nothing loaded yet -- the checkbox state is remembered for when it is
        self.data.set_trim_oscillation(self.hide_garbage_var.get())
        self._maybe_reload_viewport(force=True)

    # ------------------------------------------------- dynamic pan/zoom loading

    def _schedule_viewport_check(self, delay_ms=350):
        """Debounce: called on every drag-move/zoom tick, but only actually
        checks whether a reload is needed after `delay_ms` of no further
        pan/zoom activity -- avoids spamming background loads while the
        user is still actively dragging/scrolling."""
        if self._viewport_check_id is not None:
            try:
                self.root.after_cancel(self._viewport_check_id)
            except Exception:
                pass
        self._viewport_check_id = self.root.after(delay_ms, self._maybe_reload_viewport)

    def _maybe_reload_viewport(self, force=False):
        """Reload the current viewport's tiles if ANY of three things is
        true (README §10 "v5 -> v6", extended in "v8 -> v9", SIMPLIFIED in
        "v16 -> v17" -- see below): (a) the viewport has panned/zoomed
        outside the last-loaded (padded) bbox, (b) mp0 just finished
        building in the background (newly appearing in
        `data.available_layers()`) and isn't excluded by a checkbox, or (c)
        the user toggled a layer visibility checkbox, changing
        `_get_allowed_layers()`. The user also toggling "Draw connected
        roads" (README §10 "v9 -> v10") doesn't change the layer SET at
        all, so App._on_connected_roads_changed() calls this with
        `force=True` directly instead, the same as a checkbox toggle, since
        (b)/(c)'s own "did the layer SET change" check wouldn't otherwise
        notice a rendering-mode-only change.

        **REMOVED in "v16 -> v17"**: this used to ALSO reload when the user
        merely zoomed across a `SCALE_LAYER_THRESHOLDS` boundary (the old
        "(c)" trigger, `layers_for_scale(self.scale, ...)` producing a
        different cumulative set at the new scale) -- since
        `MapData.ensure_area_loaded()` no longer varies its pooled layer set
        by `scale` at all (user's explicit request: checkboxes are the ONLY
        control now), a pure scale change can no longer change which layers
        are wanted, so that trigger has nothing left to detect and was
        removed rather than left as permanently-dead code. (b) and (c)
        above are detected by the SAME check: recomputing
        `data.available_layers()` restricted to `_get_allowed_layers()`,
        and comparing it against `self._covered_layers` (the set the last
        SUCCESSFULLY-APPLIED load actually used) -- mp0 newly appearing in `available_layers()`,
        or the checked-layer set itself changing, can each make this
        differ; a scale-only change cannot any more. `force=True` skips the
        "already covered" short-circuit entirely (used right after a
        jump/search, right after mp0 finishes, and on every checkbox
        toggle, to re-check even when the bbox itself hasn't changed).

        **Staleness guard**: the "already covered"/"what area is loaded"
        check below uses `self._covered_bbox`/`self._covered_layers` (this
        App instance's own record of its last SUCCESSFULLY-APPLIED load),
        NOT `self.data.covered_bbox`/`covered_layers` -- those live on
        MapData and are simply overwritten, unconditionally, by whichever
        `ensure_area_loaded()` call happens to finish running most
        recently, with no ordering guarantee across overlapping calls (e.g.
        a debounced `_schedule_viewport_check()` reload left pending from
        an earlier pan/zoom, still sitting in Tk's `after()` queue, firing
        only once some MUCH LATER `root` event-loop turn finally drains it
        -- entirely possible if the app was busy with other work for a
        while). Trusting MapData's raw fields here would let that kind of
        late, superseded completion silently revert the CURRENT view's
        "what's loaded" bookkeeping to a stale, unrelated area. Guarding
        with `self._load_token` (bumped every time a NEW load actually
        starts below) and having `done()` discard its own result entirely
        if a newer load has since started closes this: only the most
        recently STARTED load's completion is ever applied, regardless of
        which BackgroundTask happens to finish first."""
        self._viewport_check_id = None
        if self.data is None or self.center_lon is None or self.busy or self._area_loading:
            return
        vb = self._visible_bbox()
        if vb is None:
            return
        scale = self.scale
        allowed_layers = self._get_allowed_layers()
        desired_layers = [
            l for l in ALL_LAYERS
            if l in self.data.available_layers() and l in allowed_layers
        ]
        already_covered = (
            self._covered_bbox is not None and
            bbox_contains(self._covered_bbox, vb) and
            self._covered_layers == desired_layers
        )
        if already_covered and not force:
            return  # already fully covered by loaded tiles from the scale-appropriate layer set

        self._area_loading = True
        self._load_token += 1
        my_token = self._load_token
        self._set_status("Panning/zooming -- loading more map tiles for the new view...")
        self.progress.start(12)

        want_adjacency = self.connected_roads_var.get()

        def do_load(progress):
            lon_min, lon_max, lat_min, lat_max = vb
            return self.data.ensure_area_loaded(
                lon_min, lon_max, lat_min, lat_max, scale, progress=progress,
                allowed_layers=allowed_layers, want_adjacency=want_adjacency)

        def done(result, error):
            if my_token != self._load_token:
                # Superseded by a newer load that started after this one --
                # discard: applying this would revert the view to a stale
                # area/feature set the user (or a later test step) already
                # moved past. `_area_loading` is intentionally left alone --
                # it belongs to whichever load is CURRENT, and either it's
                # already False (the newer one already finished) or the
                # newer one's own done() will clear it when IT finishes.
                return
            self._area_loading = False
            self.progress.stop()
            if error:
                self._set_status("Background tile load failed: %s" % error)
                return
            self._covered_bbox = result["bbox"]
            self._covered_layers = result["layers"]
            self.features = result["features"]
            self._redraw()
            n_tiles = sum(len(ids) for ids in result["tile_ids"].values())
            self._set_status(
                "View updated: %d tile(s) across %d layer(s) covering the area (%d newly decoded), "
                "%d road features." % (
                    n_tiles, len(result["layers"]), result["new_tiles"], len(self.features)))

        BackgroundTask(self.root, do_load, lambda msg: None, done).start()


# ---------------------------------------------------------------------------
# Address entry / letter-keyboard feature (README §10 "v11 -> v12"; hosted
# as embedded screen panels rather than separate OS windows as of "v12 ->
# v13" -- see AddressEntryDialog/SpellerDialog's own docstrings below)
# ---------------------------------------------------------------------------
# Reference photos this was built from (ground truth for the UI, not
# pixel-perfect -- see the task brief and README §10 "v11 -> v12" for the
# full verbatim description):
#   Photo 1 ("Address entry"): a screen with a back-arrow top-right, 4 rows
#   (Country/City/Street/Number, each a lighter label box + a dark value
#   box, Number's row also has an "Intersect." button), and a bottom row of
#   4 buttons: Save / POI / Map / Start.
#   Photo 2 (letter keyboard, shown for Country/City/Street): a growing
#   text field with a live match-count badge and a back/undo arrow, then a
#   QWERTY-ish-but-alphabetical letter grid ("A B C D E F G" / "H I J K L M
#   N" / "O P Q R S T U" / "V W X Y Z -" plus a few accented letters), a
#   numeric/symbol toggle, backspace, a keyboard-layout icon, an "ABC/ABV"
#   (Cyrillic) toggle, and "OK" -- CRITICALLY, letters that cannot lead to
#   any valid remaining match are greyed out/disabled, live, as the user
#   types.
#
# What's functional vs. decorative here (same "some buttons are real, some
# are just styled after the real unit" pattern this app already uses for
# its RADIO/MEDIA/PHONE/TONE/TRAFFIC bezel buttons):
#   FUNCTIONAL: Country/City/Street rows (open a live keyboard backed by
#   real cracked data, see below), the Number field (plain text entry),
#   the live per-letter enable/disable + match-count badge, OK/backspace/
#   undo, and "Start" (resolves the typed address to real coordinates and
#   jumps the main map there via App._jump_to() -- the same jump logic
#   "search a place, double-click a result" already uses).
#   DECORATIVE: "Save", "POI", "Map" (inside this dialog -- the bezel's own
#   MAP button already does something real), "Intersect.", the numeric/
#   symbol toggle, the keyboard-layout icon, and "ABC/ABV" (per the task's
#   own explicit guidance not to implement real Cyrillic input) -- each
#   reports what it is via the status bar/a small label rather than doing
#   nothing silently, matching this app's established bezel-button pattern.

# Keyboard rows, approximating reference photo #2's alphabetical (not true
# QWERTY) layout. The reference photo's row 3 reads "Ö P Q R S T U" (no
# plain "O" at all) -- reproduced here as "O" instead, a deliberate,
# disclosed deviation from pixel-fidelity: this project's own test data
# needs a working plain "O" to type real names (e.g. "SOFIA"), and the
# task's own guidance is "functionally faithful... not pixel-perfect",
# prioritizing the live enable/disable behavior over exact key placement.
# "Ö"/"ÃÄÆ" (the accented cluster photo #2 also shows) are kept as their
# own always-enabled decorative keys -- this project's data can't currently
# drive live accented-letter narrowing (see road_index_reader.py's
# accented-node-variant finding), and the explicit, documented fail-safe
# policy for this feature is to never confidently disable something we
# can't actually rule out.
SPELLER_KEYBOARD_ROWS = [
    ["A", "B", "C", "D", "E", "F", "G"],
    ["H", "I", "J", "K", "L", "M", "N"],
    ["O", "P", "Q", "R", "S", "T", "U"],
    ["V", "W", "X", "Y", "Z", "-", "Ö", "ÃÄÆ"],
]
SPELLER_DECORATIVE_KEYS = {"Ö", "ÃÄÆ"}  # never disabled -- see comment above

ADDR_LABEL_BG = "#0f2130"    # lighter/bordered label box (photo #1 style)
ADDR_VALUE_BG = "#050d14"    # dark value box (photo #1 style)


class AddressEntryDialog(tk.Frame):
    """"Address entry" screen (reference photo #1), opened by the "NAV"
    bezel button (App.on_bezel_nav()).

    **README §10 "v12 -> v13"**: this is an embedded PANEL living inside
    the simulated unit's own screen area (`App.screen_frame` -- the same
    glossy-black inset that otherwise only ever shows `canvas_frame` +
    `status_bar`), NOT a separate OS-level window. The explicit user
    correction that prompted this: *"this shouldnt be a new window,
    instead it should show on the nav screen"* -- a real head unit has
    exactly one screen, and different UI states (map / address entry /
    letter keyboard) replace each other WITHIN it, matching all 4
    reference photos this feature was built from (each shows ONE screen
    area, never two overlapping windows). Shown by `.place(relx=0, rely=0,
    relwidth=1, relheight=1)` + `.lift()` -- this overlays `canvas_frame`/
    `status_bar` cleanly without disturbing their own `.pack()` geometry
    (place() and pack() coexist fine in the same container; screen_frame's
    own size is still driven entirely by the packed canvas/status-bar
    children, unaffected by an overlay on top of them) -- and dismissed by
    plain `.destroy()`: since the map view was never hidden or rebuilt,
    only COVERED, destroying this overlay reveals it again immediately,
    with its center/zoom/pan/loaded features completely untouched -- no
    manual "restore the canvas" step is needed or performed.

    GUI-only glue -- all the real logic (live per-letter narrowing,
    address resolution) lives in MapData/road_index_reader.py/
    city_reader.py so it can be exercised directly by test_map_viewer.py
    without a display."""

    FIELDS = [("country", "Country"), ("city", "City/P.cd."), ("street", "Street")]

    def __init__(self, app):
        super().__init__(app.screen_frame, bg=SEARCH_PANEL_BG)
        self.app = app
        self.active_speller = None

        self.values = {"country": "", "city": "", "street": "", "number": ""}
        self.value_vars = {k: tk.StringVar(value="") for k in self.values}

        header = tk.Frame(self, bg=SEARCH_PANEL_BG)
        header.pack(fill="x", padx=10, pady=(10, 4))
        tk.Label(header, text="Address entry", bg=SEARCH_PANEL_BG, fg=SEARCH_PANEL_FG,
                 font=("Segoe UI", 13, "bold")).pack(side="left")
        tk.Button(header, text="←", command=self.destroy, bg=BEZEL_BUTTON_BG, fg=BEZEL_BUTTON_FG,
                  relief="raised", bd=1, width=3, cursor="hand2").pack(side="right")

        rows = tk.Frame(self, bg=SEARCH_PANEL_BG)
        rows.pack(fill="x", padx=10, pady=4)
        rows.grid_columnconfigure(0, weight=1)
        rows.grid_columnconfigure(1, weight=2)

        self.row_buttons = {}
        for i, (key, label) in enumerate(self.FIELDS):
            tk.Label(rows, text=label, bg=ADDR_LABEL_BG, fg=SEARCH_PANEL_FG, anchor="w",
                     font=("Segoe UI", 9), padx=8, pady=6).grid(row=i, column=0, sticky="nsew", pady=2, padx=(0, 4))
            btn = tk.Button(rows, textvariable=self.value_vars[key], anchor="w", bg=ADDR_VALUE_BG,
                             fg=SEARCH_PANEL_FG, font=("Segoe UI", 9), relief="flat", bd=0, padx=8, pady=6,
                             cursor="hand2", command=lambda k=key: self._open_speller(k))
            btn.grid(row=i, column=1, sticky="nsew", pady=2)
            self.row_buttons[key] = btn

        num_row = i + 1
        tk.Label(rows, text="Number", bg=ADDR_LABEL_BG, fg=SEARCH_PANEL_FG, anchor="w",
                 font=("Segoe UI", 9), padx=8, pady=6).grid(row=num_row, column=0, sticky="nsew", pady=2, padx=(0, 4))
        num_frame = tk.Frame(rows, bg=SEARCH_PANEL_BG)
        num_frame.grid(row=num_row, column=1, sticky="nsew", pady=2)
        num_entry = tk.Entry(num_frame, textvariable=self.value_vars["number"], bg=ADDR_VALUE_BG,
                              fg=SEARCH_PANEL_FG, insertbackground=SEARCH_PANEL_FG, relief="flat",
                              font=("Segoe UI", 9))
        num_entry.pack(side="left", fill="both", expand=True, ipady=4)
        tk.Button(num_frame, text="Intersect.", command=self._on_decorative("Intersect."),
                  bg=BEZEL_BUTTON_BG, fg=BEZEL_BUTTON_FG, relief="raised", bd=1,
                  font=("Segoe UI", 8), cursor="hand2").pack(side="left", padx=(6, 0))

        self.status_var = tk.StringVar(value="")
        tk.Label(self, textvariable=self.status_var, bg=SEARCH_PANEL_BG, fg=SEARCH_PANEL_FG_DIM,
                 font=("Segoe UI", 8), anchor="w", wraplength=430, justify="left").pack(
            fill="x", padx=10, pady=(6, 0))

        bottom = tk.Frame(self, bg=SEARCH_PANEL_BG)
        bottom.pack(fill="x", padx=10, pady=12, side="bottom")
        for text, cmd in [
            ("Save", self._on_decorative("Save")),
            ("POI", self._on_decorative("POI")),
            ("Map", self._on_decorative("Map")),
            ("Start", self._on_start),
        ]:
            b = self.app._make_pill_button(bottom, text, cmd)
            b.pack(side="left", expand=True, fill="x", padx=3)

        # Show this screen INSIDE the simulated unit's own screen area,
        # covering canvas_frame/status_bar exactly like a real head unit's
        # address-entry screen replaces its map screen (README §10
        # "v12 -> v13") -- never a second OS-level window.
        self.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.lift()

    def destroy(self):
        """Dismiss this screen, returning to whatever was showing
        underneath (the map view) -- since canvas_frame/status_bar were
        only ever COVERED, never hidden/rebuilt, they simply reappear the
        instant this overlay is gone, with the map's own state completely
        untouched. Also tears down any still-open SpellerDialog child
        screen first (normally already gone by the time a user can reach
        the back arrow or "Start" -- OK/backspace-to-empty already closes
        it -- but this is a cheap, harmless safety net against a stray
        overlay surviving this panel's own dismissal)."""
        sp = self.active_speller
        if sp is not None:
            try:
                if sp.winfo_exists():
                    sp.destroy()
            except tk.TclError:
                pass
        super().destroy()

    def _on_decorative(self, label):
        def handler():
            self.status_var.set("%s: decorative in this read-only map-data viewer." % label)
        return handler

    def _open_speller(self, field_key):
        data = self.app.data
        if field_key in ("country", "city") and (
                data.country_name_index is None or data.city_name_index is None):
            self.status_var.set("Address-entry data still loading -- try again in a moment.")
            return
        if field_key == "street" and data.rt_body is None:
            self.status_var.set("Address-entry data still loading -- try again in a moment.")
            return

        # Required-order scoping (README §10 "v13 -> v14"): the explicit
        # user correction that real nav UX cascades Country -> City ->
        # Street, never showing an unscoped list. City is scoped to the
        # selected Country and Street to the selected City (see MapData.
        # city_name_index_for_country()/street_name_index_for_city()), so
        # each field requires the previous one to already hold real text --
        # matching the real unit's own required entry order, which is easy
        # here since the fields are already presented top-to-bottom in this
        # exact order. Street only requires the City TEXT to be non-empty,
        # not that it already resolves to a real eeu.cty record -- if it
        # doesn't resolve, SpellerDialog._backing_index() degrades
        # gracefully to MapData.street_name_index_global (README §10
        # "v14 -> v15"), a still-EXACT/exhaustive global index, rather than
        # blocking the field outright or (as before "v14 -> v15") falling
        # back to the old, documented-partial `.rt`-trie walk.
        if field_key == "city" and not self.values.get("country", "").strip():
            self.status_var.set("Select a Country first.")
            return
        if field_key == "city" and data.resolve_country(self.values.get("country", "")) is None:
            self.status_var.set(
                "%r is not a recognized country -- pick one from the Country list first." %
                self.values.get("country", ""))
            return
        if field_key == "street" and not self.values.get("city", "").strip():
            self.status_var.set("Select a City first.")
            return

        def on_confirm(text):
            self.values[field_key] = text
            self.value_vars[field_key].set(text)

        # Stored on self (not just a local variable) so tests can reach the
        # live panel without relying on Tk widget-tree introspection, and
        # so this panel's own destroy() override (above) can tear it down
        # too if it's somehow still open. SpellerDialog is built as a
        # sibling tk.Frame in the SAME app.screen_frame (README §10
        # "v12 -> v13"), not a child of this dialog -- it shows ON TOP of
        # this panel (place()+lift(), same mechanism this panel itself
        # used to show over the map) and, on its own destroy() (OK, or
        # backspace-to-empty), simply reveals this Address Entry panel
        # again underneath -- no explicit "return to address entry" call
        # is needed, exactly mirroring how dismissing this panel itself
        # reveals the map underneath it. `country_name`/`city_name` (the
        # CURRENTLY confirmed values of the prior fields, README §10
        # "v13 -> v14") are passed through so the City/Street spellers can
        # scope their own live narrowing.
        self.active_speller = SpellerDialog(
            self.app, field_key, self.values.get(field_key, ""), on_confirm,
            country_name=self.values.get("country", ""),
            city_name=self.values.get("city", ""))
        return self.active_speller

    def _on_start(self):
        """"Start" (photo #1): resolve the typed City/Street to a real
        coordinate and jump the main map there -- reuses App._jump_to(),
        the SAME code path "search a place, double-click a result" and
        "enter lat/lon, Go" already use (MapData.resolve_address(), which
        in turn reuses MapProject.search()/CtyCache.search() -- the
        already-proven `.il`/`eeu.rd`/`eeu.cty` infrastructure, not the
        `.rt`/`.ct` tries, for this final step -- see resolve_address()'s
        own docstring for why)."""
        city = self.values.get("city", "").strip()
        street = self.values.get("street", "").strip()
        number = self.values.get("number", "").strip()
        if not city and not street:
            self.status_var.set("Start: enter at least a City or Street first.")
            return
        result = self.app.data.resolve_address(
            self.values.get("country", ""), city, street, number)
        if result is None:
            self.status_var.set("Start: could not resolve %r / %r to a real location." % (city, street))
            return
        self.app._update_breadcrumb_coords(result["lon"], result["lat"])
        self.app._jump_to(result["lon"], result["lat"])
        self.app._set_status("NAV Start: jumped to %s (%.5f, %.5f)." % (
            result["label"], result["lon"], result["lat"]))
        self.destroy()


class SpellerDialog(tk.Frame):
    """Letter-by-letter keyboard (reference photo #2), opened by clicking a
    Country/City/Street row in AddressEntryDialog.

    **README §10 "v12 -> v13"**: like AddressEntryDialog, this is an
    embedded panel -- a `tk.Frame` sibling of AddressEntryDialog inside the
    SAME `App.screen_frame`, shown via `.place(relx=0, rely=0, relwidth=1,
    relheight=1)` + `.lift()` (so it lands on top of AddressEntryDialog,
    which is itself on top of the map), never a separate OS window. Its
    own `.destroy()` (OK, backspace-to-empty, or the back-arrow button
    below) simply removes this overlay -- AddressEntryDialog was never
    hidden underneath it, only covered, so it's visible again immediately,
    with its own field values completely untouched except for whatever
    `on_confirm` explicitly writes back.

    The core feature: keys that cannot lead to any valid remaining match
    are disabled, recomputed LIVE after every keystroke from the real
    cracked data -- see `_recompute()` below, which is the only place this
    class talks to MapData/road_index_reader.py/city_reader.py; everything
    else here is plain Tk glue."""

    def __init__(self, app, field_key, initial_text, on_confirm, country_name="", city_name=""):
        super().__init__(app.screen_frame, bg=SEARCH_PANEL_BG)
        self.app = app
        self.field_key = field_key
        self.on_confirm = on_confirm
        # The CURRENTLY confirmed value of the field(s) above this one in
        # AddressEntryDialog (README §10 "v13 -> v14") -- `country_name` for
        # the City speller, `city_name` for the Street speller -- used ONLY
        # to scope this speller's own live narrowing (_backing_index()
        # below); never mutated here.
        self.country_name = country_name
        self.city_name = city_name
        self.text_var = tk.StringVar(value=(initial_text or "").upper())
        self.count_var = tk.StringVar(value="")
        self.key_buttons = {}

        header = tk.Frame(self, bg=SEARCH_PANEL_BG)
        header.pack(fill="x", padx=10, pady=(10, 0))
        tk.Label(header, text="%s entry" % field_key.capitalize(), bg=SEARCH_PANEL_BG,
                 fg=SEARCH_PANEL_FG, font=("Segoe UI", 13, "bold")).pack(side="left")
        tk.Button(header, text="←", command=self.destroy, bg=BEZEL_BUTTON_BG, fg=BEZEL_BUTTON_FG,
                  relief="raised", bd=1, width=3, cursor="hand2").pack(side="right")

        top = tk.Frame(self, bg=SEARCH_PANEL_BG)
        top.pack(fill="x", padx=10, pady=(10, 4))
        entry = tk.Entry(top, textvariable=self.text_var, bg=ADDR_VALUE_BG, fg=SEARCH_PANEL_FG,
                          insertbackground=SEARCH_PANEL_FG, relief="flat", font=("Segoe UI", 14),
                          state="readonly", readonlybackground=ADDR_VALUE_BG, justify="left")
        entry.pack(side="left", fill="both", expand=True, ipady=6)
        tk.Label(top, textvariable=self.count_var, bg=STATUS_BADGE_BG, fg="white",
                 font=("Segoe UI", 9, "bold"), padx=8, pady=4).pack(side="left", padx=(6, 0))
        tk.Button(top, text="⌫", command=self._backspace, bg=BEZEL_BUTTON_BG, fg=BEZEL_BUTTON_FG,
                  relief="raised", bd=1, width=3, cursor="hand2").pack(side="left", padx=(6, 0))

        grid = tk.Frame(self, bg=SEARCH_PANEL_BG)
        grid.pack(padx=10, pady=6)
        for r, row in enumerate(SPELLER_KEYBOARD_ROWS):
            for c, key in enumerate(row):
                b = tk.Button(grid, text=key, width=4, font=("Segoe UI", 11, "bold"),
                              command=lambda k=key: self._on_key(k),
                              bg=BEZEL_BUTTON_BG, fg=BEZEL_BUTTON_FG, activebackground=BEZEL_BUTTON_ACTIVE_BG,
                              disabledforeground="#5a5d63", relief="raised", bd=1, cursor="hand2")
                b.grid(row=r, column=c, padx=2, pady=2)
                self.key_buttons[key] = b

        bottom = tk.Frame(self, bg=SEARCH_PANEL_BG)
        bottom.pack(fill="x", padx=10, pady=(4, 10))
        tk.Button(bottom, text="$..% 0..9", command=self._decorative("Numeric/symbol keyboard"),
                  bg=BEZEL_BUTTON_BG, fg=BEZEL_BUTTON_FG, relief="raised", bd=1,
                  font=("Segoe UI", 8), cursor="hand2").pack(side="left")
        tk.Button(bottom, text="⌨", command=self._decorative("Keyboard layout"),
                  bg=BEZEL_BUTTON_BG, fg=BEZEL_BUTTON_FG, relief="raised", bd=1,
                  width=3, cursor="hand2").pack(side="left", padx=4)
        tk.Button(bottom, text="ABC/АБВ", command=self._decorative("Cyrillic input"),
                  bg=BEZEL_BUTTON_BG, fg=BEZEL_BUTTON_FG, relief="raised", bd=1,
                  font=("Segoe UI", 8), cursor="hand2").pack(side="left", padx=4)
        self.ok_button = self.app._make_pill_button(bottom, "OK", self._on_ok)
        self.ok_button.pack(side="right")

        self.status_var = tk.StringVar(value="")
        tk.Label(self, textvariable=self.status_var, bg=SEARCH_PANEL_BG, fg=SEARCH_PANEL_FG_DIM,
                 font=("Segoe UI", 8), wraplength=320, justify="left").pack(fill="x", padx=10, pady=(0, 8))

        self._recompute()

        # Show this keyboard screen on top of the Address Entry panel
        # (itself on top of the map), all still within the SAME simulated
        # screen area (README §10 "v12 -> v13") -- never a second window.
        self.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.lift()

    def _decorative(self, label):
        def handler():
            self.status_var.set("%s: decorative in this read-only map-data viewer." % label)
        return handler

    def _backing_index(self):
        """The exact PrefixNameIndex backing this speller's live narrowing.
        As of README §10 "v14 -> v15", this ALWAYS returns a real,
        exhaustive PrefixNameIndex for all three fields -- there is no
        longer a documented-partial-coverage trie fallback anywhere in this
        method (see `_recompute()`'s own docstring for what's left of that
        old code path and why it's kept).

        Country is always the full closed 35-entry list (nothing to scope
        it BY -- it's the first field). City is scoped to the currently
        selected Country via MapData.city_name_index_for_country() --
        AddressEntryDialog._open_speller() already refuses to open the City
        speller at all unless a real Country is selected (see its own
        docstring), so this should always resolve here in practice; the
        `or data.city_name_index` fallback is a defensive belt-and-suspenders
        for the unexpected case, not the intended common path (it degrades
        to the OLD, unscoped-but-still-exhaustive behavior rather than
        crashing).

        Street is scoped to the currently selected City via MapData.
        street_name_index_for_city() -- a city that fails to resolve (or
        resolves but has no nearby `.rd` coverage) returns None, and this
        now falls back to `data.street_name_index_global` (README §10
        "v14 -> v15"): a GLOBAL but still EXACT/exhaustive PrefixNameIndex
        over every distinct real `eeu.rd` street name on the whole disc --
        the exact same "no fallback to something merely best-effort" bar
        City's own `or data.city_name_index` fallback already meets. This
        replaces the old `.rt`-trie fail-safe path
        (`MapData.street_enabled_next_chars()`), whose real, documented
        partial coverage (README §3.7: a forest of shards reaching only
        ~5,100 of the real leaf strings) is no longer needed here."""
        data = self.app.data
        if self.field_key == "country":
            return data.country_name_index
        if self.field_key == "city":
            return data.city_name_index_for_country(self.country_name) or data.city_name_index
        if self.field_key == "street":
            return (data.street_name_index_for_city(self.city_name, country_rec=data.resolve_country(self.country_name))
                    or data.street_name_index_global)
        return None

    def _on_key(self, key):
        if key in ("Ö", "ÃÄÆ"):
            self.status_var.set("Accented/Cyrillic input is decorative in this build (see README §10).")
            return
        if key == "-":
            self.text_var.set(self.text_var.get() + "-")
        else:
            self.text_var.set(self.text_var.get() + key)
        self._recompute()

    def _backspace(self):
        cur = self.text_var.get()
        if cur:
            self.text_var.set(cur[:-1])
            self._recompute()
        else:
            self.destroy()

    def _on_ok(self):
        self.on_confirm(self.text_var.get())
        self.destroy()

    def _recompute(self):
        """The live, per-keystroke narrowing this whole feature is about --
        see README §10 "v11 -> v12" for the original design/validation
        writeup, "v13 -> v14" for the Country->City->Street SCOPING, and
        "v14 -> v15" for making Street's own last fallback exhaustive too.
        Country is backed by an exact `city_reader.PrefixNameIndex` over the
        full closed `eeu.ctr` list (no coverage gaps). City is backed by the
        SAME kind of exact PrefixNameIndex, but SCOPED to only the selected
        Country's own `eeu.cty` records (`MapData.
        city_name_index_for_country()`) instead of all 939,351, falling back
        to the unscoped-but-still-exhaustive `city_name_index` in the
        (expected-unreachable-in-practice) case no Country resolved. Street
        is normally backed by an exact PrefixNameIndex scoped to real
        `eeu.rd` street names inside the selected City's own (padded)
        bounding box (`MapData.street_name_index_for_city()`), falling back
        to the GLOBAL but still exact `MapData.street_name_index_global`
        (README §10 "v14 -> v15") when no City has resolved yet or the
        resolved City has no nearby `.rd` coverage -- as of this session,
        `_backing_index()` ALWAYS returns a real index for all three fields,
        so the `if index is not None:` branch below is now unconditionally
        taken by the live UI.

        The `else` branch below (calling `MapData.street_enabled_next_chars()`
        -> `road_index_reader.rt_enabled_next_chars()`, the real `.rt`
        character-trie walk) is DEFENSIVE dead code from the live UI's own
        point of view now -- `_backing_index()` can only return `None` if
        `street_name_index_global` itself returns `None`, which only happens
        if `self.app.data.rd_cache` is somehow unbuilt (not expected: Address
        Entry is only reachable once a map ISO, and therefore `rd_cache`, is
        already loaded). Kept rather than removed, both as a real safety net
        for that edge case and because `road_index_reader.
        rt_enabled_next_chars()` is itself still real, cracked, validated
        code (README §3.7) independently exercised by `test_map_viewer.py`'s
        own direct `.rt` fail-safe-design tests."""
        prefix = self.text_var.get()
        index = self._backing_index()
        if index is not None:
            enabled = index.enabled_next_chars(prefix)
            confident = True
            count = index.count_matches(prefix)
            count_text = str(count)
        else:
            data = self.app.data
            enabled, confident = data.street_enabled_next_chars(prefix)
            if not prefix:
                count_text = "?"
            else:
                lookup = rir.rt_lookup_prefix(data.rt_body, prefix)
                if lookup["matched"] != len(prefix) or lookup["node"] is None:
                    count_text = "0"
                else:
                    words = rir.rt_walk_strings(data.rt_body, lookup["node"], max_results=500)
                    count_text = ("%d+" % len(words)) if len(words) >= 500 else str(len(words))

        self.count_var.set(count_text)
        for key, btn in self.key_buttons.items():
            if key in SPELLER_DECORATIVE_KEYS:
                btn.configure(state="normal")
                continue
            k = key.upper()
            allow = (k in enabled) or (not confident)
            btn.configure(state="normal" if allow else "disabled")


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
