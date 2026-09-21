"""
test_map_viewer.py -- non-GUI functional test of rns510_map_viewer.py
against the real CD_8555.ISO, plus a basic GUI construction smoke test.

Run with:
    py test_map_viewer.py

Exercises everything the map-viewer upgrade added, driven directly so it
can be proven to work without clicking through a UI:
  - projection / viewport-bbox math (project_point, compute_visible_bbox,
    bbox_contains, pad_bbox)
  - zoom-dependent city importance thresholds (city_min_area_for_scale)
  - extracting the MAP_COMPRESSED layers + eeu.cty, building each fast
    layer's geo-index and the in-memory road-name (RdCache) and city
    (CtyCache) caches
  - unified road+city search (MapData.search_combined)
  - dynamic area loading (MapData.ensure_area_loaded): initial load, a
    simulated pan to a DIFFERENT area (new tiles decoded, old tiles stay
    cached), and road-name-index cache reuse when the new area is already
    covered
  - real road names actually attached to decoded geometry (not just
    unlabeled polylines) and a real city (Tirane/Tirana, already validated
    elsewhere in this project -- README §3.8) appearing in a viewport query
  - the actual App widget tree constructing without error, with NO layer
    dropdown/choice exposed anywhere in the UI
  - multi-layer pooling (README §10 "v4 -> v5"/"v5 -> v6"): mg1 wired up in
    LAYER_ISO_PATHS; opening an ISO does NOT block on mp0's slow geo-index
    build; MapData.available_layers() returns just the four fast layers
    before mp0 is ready and all five after; ensure_area_loaded() pools
    tiles/points from a scale-dependent CUMULATIVE set of layers for the
    same real bbox (verified to be an exact flat sum of each pooled layer's
    own decode output, not a combinatorial blow-up); and mp0's points get
    folded in ADDITIVELY (not a full layer swap) the moment its background
    geo-index finishes AND the current scale is high enough to want it
  - cumulative scale-stacking (README §10 "v5 -> v6", this session):
    layers_for_scale() returns exactly ["mg4"] at the lowest scale and
    grows monotonically/additively (never swaps a layer out) as scale
    increases; ensure_area_loaded()'s pooled point count increases with
    scale (real measured numbers); zooming back down to a low scale drops
    the finer layers' points again while their tiles stay cached (no
    re-decode on zooming back in); and the running App actually reloads/
    redraws end to end when the user zooms across a layer-set threshold,
    even when the viewport bbox itself hasn't escaped the last-loaded area
  - real App._redraw() wall-clock timing on a dense real area, both before
    and after mp0 becomes available, to check multi-layer pooling doesn't
    make interactive redraws uncomfortably slow
  - click-to-identify points (README §10 "v6 -> v7"): canvas_to_lonlat() is
    the exact inverse of project_point()+App._to_canvas()'s centering
    offset; find_nearest_point() correctly identifies a KNOWN real decoded
    point (picked via canvas coordinates computed from that point's own
    real (lon, lat) through the existing projection math) with the right
    layer/tile_id/feature_index/point_index/lon/lat, returns None for a
    click far from anything, and MapData.decode_tile() tags every decoded
    feature with enough info to trace a pooled/named feature back to its
    exact source tile; a real end-to-end App._on_point_pick() right-click
    simulation against a live Tirana-area view: a hit places a marked/
    numbered pick and appends a row to the picked-points panel, a miss
    does neither; and panning (<ButtonPress-1>/<B1-Motion>/
    <ButtonRelease-1>) is explicitly re-verified to still update
    pan_x/pan_y exactly as before, proving the new <Button-3> binding
    didn't disturb it
  - layer visibility checkboxes (README §10 "v8 -> v9"): MapData.ensure_area_loaded()'s
    new `allowed_layers` param, verified against the real ISO at the same
    Sofia bbox/scale sweep already used for v6's own reference numbers --
    `allowed_layers=None` (and, explicitly, `allowed_layers=set(ALL_LAYERS)`)
    reproduce the EXACT pre-existing v6 point counts (501/1,804/5,316/12,658
    at scale 500/1,500/4,000/10,000); excluding `mg1` at scale=10,000 drops
    the pooled total to EXACTLY the mg4+mg3+mg2 count already measured at
    scale=4,000; excluding `mp0` after it's ready and scale-eligible hides
    it entirely, and re-including it restores its exact point count via a
    pure cache hit (0 new tiles decoded); an empty allowed set pools
    nothing without crashing. A second, GUI-level check drives the actual
    running `App`: flipping a real `tk.BooleanVar` and calling the
    checkbox's own command (`App._on_layer_visibility_changed`) is
    confirmed to trigger a real `BackgroundTask` reload end to end, not
    just correct `MapData`-level logic
  - Address entry / letter-keyboard feature (README §10 "v11 -> v12"):
    `road_index_reader.rt_root()`/`city_reader.ct_root()` validated against
    the real ISO (offset-verified per-letter entries, a concrete "2,500x+
    more reachable leaves than the old hand-picked D-node" comparison, and
    a direct reproduction of the documented "SOFIA is not reachable from
    any found .ct shard" negative finding); `eeu.ctr` fully decoded (35/35
    countries, BALGARIA confirmed at index 19); live per-letter enable/
    disable progression for City ("S"->"SO"->"SOF"->"SOFI", confirming 'A'
    stays enabled so "SOFIA" can be completed, and confirming letters that
    cannot continue any real match are excluded) and for Street (the real
    `.rt` trie, including its fail-safe design: an unconfident/incomplete
    walk never disables a letter, and a genuine CONFIDENT dead end -- found
    via exhaustive DFS, since naively always taking a node's first child
    rarely reaches one -- correctly disables everything); `resolve_address()`
    resolving "SOFIA" to real Sofia coordinates; and a full GUI run of
    AddressEntryDialog/SpellerDialog (the "NAV" bezel button, live keyboard
    widget states, the match-count badge, and a real end-to-end "Start"
    jump via the same BackgroundTask path search/"Go" already use) -- which
    also caught and fixed a real, previously-latent bug: `App._jump_to()`
    was evaluating `self.canvas.winfo_width()/height()` and two
    `tk.BooleanVar.get()` reads on the BackgroundTask's WORKER thread, not
    the main thread -- harmless in practice via a live `mainloop()` but a
    reproducible hang under this test's scripted `root.update()` polling;
    fixed by computing all three on the main thread before the worker
    starts (see `App._jump_to()`'s own comment for the full story)
  - Address entry hosted as an embedded screen panel, not a separate OS
    window (README §10 "v12 -> v13"): AddressEntryDialog/SpellerDialog are
    now `tk.Frame` panels placed inside `App.screen_frame`, not
    `tk.Toplevel` windows -- verified by counting every real `tk.Toplevel`
    in the whole widget tree before/after opening Address Entry, opening
    the City speller, and the full "Start" jump (never increases), by
    confirming the panels are `tk.Frame` instances found among
    `app.screen_frame.winfo_children()` and actually mapped/visible there,
    and by confirming the map's own state (center/zoom/pan/feature count)
    is bit-for-bit unchanged by showing and then dismissing these panels
  - Country -> City -> Street scoping (README §10 "v13 -> v14"): the newly
    cracked `eeu.cty` country_tag field (`city_reader.build_country_tag_map()`)
    partitions ALL 939,351 records into exactly the 35 real `eeu.ctr`
    countries, validated against 16+ known real cities across the Balkans/
    Central Europe (including the geographically tight Kosovo/Serbia/
    Montenegro/North Macedonia cluster); `MapData.city_name_index_for_country()`
    is confirmed to return a MUCH smaller (thousands, not 939K) index for
    Bulgaria that contains SOFIA but not any Albanian city, and vice versa
    for Albania; `MapData.street_names_for_city()`/`street_name_index_for_city()`
    (real `eeu.rd` coordinates inside the selected city's own padded `eeu.cty`
    bbox) is confirmed to include a real Sofia street (VITOSHA) while
    excluding a real Tirana-only street, and vice versa; and a full GUI
    re-run of the NAV -> City speller flow confirms the on-screen widget
    states/match-count badge now reflect the SCOPED count once a Country is
    selected, plus the new required-order behavior (City refuses to open
    without a valid Country, Street refuses to open without City text)
  - Four debugging-workflow changes (README §10 "v16 -> v17"): road-point
    dots render in DOT_COLOR (red), not the old gray/gold ROAD_COLOR_*
    shades; a high-confidence connected-roads feature now draws its
    per-vertex dots AND its real derived lines together (not lines-only);
    right-clicking near a rendered connected-roads LINE (not just a point)
    identifies the specific edge and adds BOTH its real endpoints as a
    linked pick pair, verified against a known, human-verified real edge
    (mg2 tile_id 20597); and layer pooling (MapData.ensure_area_loaded()/
    App._maybe_reload_viewport()) is now controlled ONLY by the "Show
    layers" checkboxes, with no more automatic scale-based restriction on
    top -- verified by sweeping the same real Sofia bbox across every scale
    this file's tests have historically used and confirming the pooled
    layer set/point count no longer varies with scale, and that mp0 is
    pooled even at the lowest (most zoomed-out) scale once it's ready
"""

import math
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rns510_map_viewer as viewer

# eeu.cty names are UTF-8 and include non-ASCII letters (e.g. Tirane's real
# name "TIRANE" with U+00CB, see README §3.8) that the default Windows
# console codepage (cp1251/cp1252) can't encode -- reconfigure stdout so
# printing a real decoded name never crashes the test run itself.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ISO_PATH = r"C:\Users\krcenov\Downloads\Eu_East_ver17\CD_8555.ISO"

# A scale comfortably >= viewer.MP0_MIN_SCALE (15,000 px/deg) -- historically
# used throughout this file wherever a test wanted layers_for_scale() to
# return every FAST_LAYERS entry. As of README §10 "v16 -> v17",
# MapData.ensure_area_loaded() no longer uses `scale` to choose which layers
# to pool at all (see that method's own docstring) -- the ACTUAL value no
# longer matters for that purpose, but this constant (and passing it) is
# kept for readability/historical continuity at call sites where "before
# mp0 is ready" vs. "after" is still the thing being distinguished (mp0 is
# still gated on whether it's actually in `available_layers()`, unaffected
# by this change).
FULL_FAST_SCALE = 20000.0

T0 = time.time()


def log(msg):
    print("[%.1fs] %s" % (time.time() - T0, msg))


# --- README §10 "v17 -> v18" pixel-sampling helpers -------------------------
# The rendering rework replaces individual canvas.create_oval()/create_line()
# items (one per road point/edge) with a SINGLE rasterized PIL.Image, shown
# as one canvas.create_image() item (App._redraw() keeps it on
# `self._current_image`, pre-PhotoImage-conversion, specifically so tests can
# inspect it directly). These helpers replace the old canvas.type()/
# itemcget()/coords() introspection with real pixel-color sampling against
# ground-truth (lon, lat) -> canvas (x, y) projections.
def _hex_to_rgb(hexcolor):
    return tuple(int(hexcolor[i:i + 2], 16) for i in (1, 3, 5))


def _pixel_at(img, x, y):
    """RGB tuple at the given (possibly float, possibly slightly out-of-
    bounds) canvas coordinate in a PIL image, clamped to the image bounds."""
    w, h = img.size
    xi = min(max(int(round(x)), 0), w - 1)
    yi = min(max(int(round(y)), 0), h - 1)
    return img.getpixel((xi, yi))[:3]


def _color_matches(px, hexcolor, tol=6):
    target = _hex_to_rgb(hexcolor)
    return all(abs(px[i] - target[i]) <= tol for i in range(3))


def _color_near(img, x, y, hexcolor, tol=6, radius=1):
    """True if some pixel within `radius` of (x, y) matches `hexcolor`.

    PIL's ImageDraw.line() rasterizes a THIN (Bresenham-style) 1px-wide path
    -- the exact analytical midpoint of a diagonal segment does not
    necessarily fall on one of the specific pixels that path lit (unlike a
    dot, which is a real ellipse with radius >= 1px and therefore always
    covers its own exact center pixel). A small search radius accounts for
    this sub-pixel rounding without weakening the check's real intent
    (confirming a line was actually drawn near that location, in the right
    color)."""
    w, h = img.size
    xi, yi = int(round(x)), int(round(y))
    for dx in range(-radius, radius + 1):
        for dy in range(-radius, radius + 1):
            xx, yy = xi + dx, yi + dy
            if 0 <= xx < w and 0 <= yy < h and _color_matches(img.getpixel((xx, yy))[:3], hexcolor, tol):
                return True
    return False


def _count_color_pixels(img, hexcolor, tol=6):
    """Count of pixels in the whole image within `tol` of `hexcolor` on
    every channel -- vectorized with numpy since a full 1100x700 Python-level
    getdata() loop would be needlessly slow to run repeatedly in a test."""
    arr = np.asarray(img.convert("RGB"), dtype=np.int16)
    target = np.array(_hex_to_rgb(hexcolor), dtype=np.int16)
    mask = np.all(np.abs(arr - target) <= tol, axis=-1)
    return int(mask.sum())


def main():
    assert os.path.exists(ISO_PATH), "source ISO not found: %s" % ISO_PATH

    # --- 1. projection / viewport-bbox math sanity, no ISO needed ---------
    x, y = viewer.project_point(23.5, 44.0, 23.5, 44.0, 1000.0)
    assert x == 0.0 and y == 0.0, "center point must project to origin"
    x, y = viewer.project_point(23.6, 44.0, 23.5, 44.0, 1000.0)
    assert x > 0, "east of center must project to positive x"
    x, y = viewer.project_point(23.5, 44.1, 23.5, 44.0, 1000.0)
    assert y < 0, "north of center must project to negative (up) y"

    bbox = viewer.compute_visible_bbox(23.5, 44.0, 1000.0, 0.0, 0.0, 800, 600)
    lon_min, lon_max, lat_min, lat_max = bbox
    assert lon_min < 23.5 < lon_max, "center longitude must be inside its own visible bbox"
    assert lat_min < 44.0 < lat_max, "center latitude must be inside its own visible bbox"
    inner = viewer.compute_visible_bbox(23.5, 44.0, 4000.0, 0.0, 0.0, 800, 600)  # more zoomed in
    assert viewer.bbox_contains(bbox, inner), "a more-zoomed-in view must be contained in a wider one"
    assert not viewer.bbox_contains(inner, bbox), "the reverse must not hold"
    padded = viewer.pad_bbox(*bbox, pad_frac=0.5)
    assert viewer.bbox_contains(padded, bbox), "padding a bbox must still contain the original"
    log("projection / viewport-bbox math sanity checks passed")

    # --- 1a. discrete zoom levels (README §10 "v17 -> v18") ----------------
    assert viewer.ZOOM_LEVELS_M[0] == 500_000.0 and viewer.ZOOM_LEVELS_M[-1] == 25.0, \
        "zoom table must run from 500km (widest) to 25m (narrowest)"
    assert list(viewer.ZOOM_LEVELS_M) == sorted(viewer.ZOOM_LEVELS_M, reverse=True), \
        "zoom table must be strictly descending (widest to narrowest)"
    assert len(viewer.ZOOM_LEVELS_M) == 30, "expected exactly the 30 real-hardware-style levels requested"
    # A wider real-world span at the SAME canvas size must mean a SMALLER
    # scale (fewer pixels/degree needed to fit more real distance on screen).
    s_500km = viewer.scale_for_zoom_span_m(500_000.0, 1100, 700)
    s_5km = viewer.scale_for_zoom_span_m(5_000.0, 1100, 700)
    s_25m = viewer.scale_for_zoom_span_m(25.0, 1100, 700)
    assert s_500km < s_5km < s_25m, "scale must increase monotonically as the named span narrows"
    # Round-trip: the scale computed FOR a given level must itself be
    # recognized as the level nearest to that exact scale.
    for i, span_m in enumerate(viewer.ZOOM_LEVELS_M):
        s = viewer.scale_for_zoom_span_m(span_m, 1100, 700)
        assert viewer.nearest_zoom_level_index(s, 1100, 700) == i, \
            "scale_for_zoom_span_m(%r)'s own scale must round-trip to level index %d" % (span_m, i)
    # DEFAULT_ZOOM_SPAN_M must actually be the 5km level a jump opens at.
    assert viewer.DEFAULT_ZOOM_SPAN_M == 5_000.0, "user's explicit request: jumps must open at 5km"
    log("discrete zoom-level table (500km -> 25m, 30 real-hardware-style steps) and "
        "scale_for_zoom_span_m()/nearest_zoom_level_index() round-trip checks passed")

    # city importance thresholds must get stricter (smaller min-area) as scale increases
    a1 = viewer.city_min_area_for_scale(1000.0)
    a2 = viewer.city_min_area_for_scale(10000.0)
    a3 = viewer.city_min_area_for_scale(100000.0)
    assert a1 > a2 > a3, "zoomed-in views must surface smaller/less-important cities"
    log("city_min_area_for_scale monotonicity check passed")

    # --- 1b. layers_for_scale(): pure-function cumulative-growth/mp0-gating
    #         checks, no ISO needed (README §10 "v5 -> v6") -------------------
    assert viewer.layers_for_scale(500.0, viewer.FAST_LAYERS) == ["mg4"], \
        "at the lowest zoom (max zoomed out), only the coarsest layer must be included"
    prev = []
    for s in (500.0, 1500.0, 4000.0, 10000.0, 50000.0):
        cur = viewer.layers_for_scale(s, viewer.FAST_LAYERS)
        assert cur[:len(prev)] == prev, \
            "layers_for_scale() must be cumulative -- a previously-included layer must never be " \
            "dropped/swapped as scale increases (scale=%s: prev=%s, cur=%s)" % (s, prev, cur)
        assert len(cur) >= len(prev), "layer count must grow monotonically with scale"
        prev = cur
    assert prev == viewer.FAST_LAYERS, \
        "at the highest swept scale (mp0 not in `available`), the cumulative set must cap at FAST_LAYERS"
    # mp0 gating: only appended once BOTH the scale is high enough AND it's actually in `available`.
    assert viewer.HEAVY_LAYER not in viewer.layers_for_scale(50000.0, viewer.FAST_LAYERS), \
        "mp0 must never be requested when it's not present in `available`, even at max scale"
    assert viewer.layers_for_scale(50000.0, viewer.FAST_LAYERS + ["mp0"]) == viewer.FAST_LAYERS + ["mp0"], \
        "mp0 must be appended once both the scale is high enough and it's available"
    assert viewer.layers_for_scale(500.0, viewer.FAST_LAYERS + ["mp0"]) == ["mg4"], \
        "mp0 must NOT be included at a low (zoomed-out) scale even if it IS available"
    log("layers_for_scale() cumulative-growth / mp0-gating checks passed")

    # --- 1c. click-to-identify pure-function checks (README §10 "v6 -> v7"),
    #         no ISO needed: canvas_to_lonlat() must be the exact inverse of
    #         project_point()+App._to_canvas()'s centering/pan offset, and
    #         find_nearest_point() must correctly pick the nearest point
    #         within its pixel cutoff (and correctly return None past it) on
    #         a small synthetic feature list carrying the same
    #         layer/tile_id/tile_offset/tile_declen/feature_index/"offset"/
    #         named_ranges tags MapData.decode_tile()/road_naming.name_features()
    #         actually attach in the real pipeline. ------------------------
    c_lon, c_lat, c_scale = 23.4, 42.6, 5000.0
    canvas_w, canvas_h = 800, 600
    pan_x, pan_y = 13.0, -7.0
    for test_lon, test_lat in ((23.4, 42.6), (23.41, 42.61), (23.35, 42.55)):
        x, y = viewer.project_point(test_lon, test_lat, c_lon, c_lat, c_scale)
        cx, cy = canvas_w / 2 + x + pan_x, canvas_h / 2 + y + pan_y
        back_lon, back_lat = viewer.canvas_to_lonlat(cx, cy, c_lon, c_lat, c_scale, pan_x, pan_y, canvas_w, canvas_h)
        assert abs(back_lon - test_lon) < 1e-9 and abs(back_lat - test_lat) < 1e-9, \
            "canvas_to_lonlat() must be the exact inverse of project_point()+_to_canvas()'s offset " \
            "(round-trip mismatch for (%.5f,%.5f) -> (%.5f,%.5f))" % (test_lon, test_lat, back_lon, back_lat)
    log("canvas_to_lonlat() exact-inverse round-trip checks passed")

    synth_features = [
        {
            "points": [(23.4000, 42.6000), (23.4010, 42.6010), (23.4020, 42.6020)],
            "layer": "mg3", "tile_id": 4187, "tile_offset": 999000, "tile_declen": 2276,
            "feature_index": 2, "offset": 326,
            "named_ranges": [(0, 1, "TESTROAD"), (2, 2, None)],
        },
        {
            "points": [(23.6000, 42.8000)],
            "layer": "mg4", "tile_id": 55, "tile_offset": 12345, "tile_declen": 900,
            "feature_index": 0, "offset": 10,
            "named_ranges": [(0, 0, "FARROAD")],
        },
    ]
    hit = viewer.find_nearest_point(synth_features, 23.4010, 42.6010, c_lat, c_scale)
    assert hit is not None, "a click exactly on a synthetic point must be picked"
    assert hit["layer"] == "mg3" and hit["tile_id"] == 4187 and hit["tile_offset"] == 999000
    assert hit["feature_index"] == 2 and hit["feature_byte_offset"] == 326 and hit["point_index"] == 1
    assert abs(hit["lon"] - 23.4010) < 1e-9 and abs(hit["lat"] - 42.6010) < 1e-9
    assert hit["name"] == "TESTROAD", "point_index 1 falls in the (0,1,'TESTROAD') named range"
    hit_unnamed = viewer.find_nearest_point(synth_features, 23.4020, 42.6020, c_lat, c_scale)
    assert hit_unnamed is not None and hit_unnamed["point_index"] == 2 and hit_unnamed["name"] is None, \
        "point_index 2 falls in the (2,2,None) unnamed range -- must report name=None, not crash/omit it"
    miss = viewer.find_nearest_point(synth_features, 30.0, 50.0, c_lat, c_scale)
    assert miss is None, "a click far from every synthetic point must return None, not the nearest-anyway point"
    # a click a few pixels off the exact point, but still within the default
    # cutoff, must still resolve to that same point
    near_x, near_y = viewer.project_point(23.4010, 42.6010, c_lon, c_lat, c_scale)
    nudged_lon, nudged_lat = viewer.canvas_to_lonlat(
        canvas_w / 2 + near_x + 4, canvas_h / 2 + near_y + 4, c_lon, c_lat, c_scale, 0, 0, canvas_w, canvas_h)
    near_hit = viewer.find_nearest_point(synth_features, nudged_lon, nudged_lat, c_lat, c_scale)
    assert near_hit is not None and near_hit["point_index"] == 1 and near_hit["tile_id"] == 4187, \
        "a click a few pixels off an exact point (within POINT_PICK_RADIUS_PX) must still resolve to it"
    log("find_nearest_point() synthetic-feature identification/cutoff checks passed")

    # --- 2. load the FAST layers (mg4/mg3/mg2/mg1) + road-name/city caches,
    #        WITHOUT touching mp0 -- this is the "opening starts fast,
    #        doesn't block on mp0" requirement, checked for real (timed),
    #        not just asserted by design intent -----------------------------
    data = viewer.MapData(ISO_PATH)
    # NOTE (README §10 "v15 -> v16"): MapData.trim_oscillation's real default
    # flipped to False this session (the oscillation-garbage filter was found
    # net-negative for real dense-urban rendering, see the README section for
    # the full investigation). This single shared `data` instance backs the
    # large majority of this file's OTHER exact-point-count regression
    # assertions below (layer-stacking arithmetic, checkbox-restriction
    # logic, connected-roads edge counts, etc.) that were captured against
    # the OLD default and have nothing to do with the garbage filter itself
    # -- pinning it to True here keeps every one of those numbers exactly
    # reproducible without re-deriving dozens of hardcoded figures. The REAL
    # shipped default (False, MapData.__init__'s own) is verified
    # independently, on a fresh/unpinned instance, in the GUI section's
    # "Hide decode garbage" checkbox-removal check below -- the checkbox
    # itself was later removed entirely (user request), so `trim_oscillation`
    # is now a programmatic-only API, which is exactly what this direct
    # attribute assignment already exercises.
    data.trim_oscillation = True
    t0 = time.time()
    data.load(progress=log)
    dt_open = time.time() - t0
    log("MapData.load() (fast layers only) took %.1fs" % dt_open)

    for layer in viewer.FAST_LAYERS:
        d = data.directories[layer]
        gi = data.geo_indexes[layer]
        log("%s: %d tiles, geo_index resolved %d/%d" % (layer, d["num_tiles"], len(gi), d["num_tiles"]))
        assert d["num_tiles"] > 0
        assert len(gi) > 0.9 * d["num_tiles"], "%s geo-index coverage looks too low" % layer

    # mg1 specifically -- previously a real gap (missing from LAYER_ISO_PATHS
    # entirely). Confirm it's now wired up and actually resolves real tiles,
    # not just present in the dict.
    assert "mg1" in viewer.LAYER_ISO_PATHS and viewer.LAYER_ISO_PATHS["mg1"] == "/DB/EEUZ.MG1"
    assert data.directories["mg1"]["num_tiles"] > 50_000, "mg1 tile count looks too small for the real disc"
    log("mg1 wired up and geo-indexed: %d tiles, %d resolved" % (
        data.directories["mg1"]["num_tiles"], len(data.geo_indexes["mg1"])))

    # mp0 must NOT be touched by load() -- that's what keeps "Open Map ISO"
    # fast; it's built separately below via load_heavy_layer(), timed on its
    # own to show it really is the slow part being kept out of the critical
    # path, not merely assumed to be.
    assert "mp0" not in data.directories, "load() must not eagerly build the slow mp0 geo-index"
    assert data.mp0_ready is False and data.mp0_building is False
    assert dt_open < 60.0, "opening the ISO took too long -- mp0 may have leaked into the fast path"
    log("Confirmed: mp0 untouched by load() -- 'Open Map ISO' does not block on it")

    assert data.rd_cache is not None and data.rd_cache.record_count > 8_000_000, "RdCache looks too small"
    assert data.cty_cache is not None and data.cty_cache.record_count > 900_000, "CtyCache looks too small"
    log("RdCache: %d eeu.rd records, CtyCache: %d eeu.cty records in memory" % (
        data.rd_cache.record_count, data.cty_cache.record_count))

    # --- 2b. available_layers(): always the four fast layers before mp0's
    #         background geo-index finishes -- no more scale-dependent
    #         single-layer choice at all (README §10 "v4 -> v5") ----------
    assert data.available_layers() == viewer.FAST_LAYERS, \
        "before mp0 is ready, available_layers() must be exactly the four fast layers"
    log("available_layers() before mp0 ready: %s" % data.available_layers())

    # --- 3. unified search: a real road AND a real city -------------------
    hits, road_total, city_total, _poi_total = data.search_combined("TIMISOARA", limit=20)
    road_hits = [h for h in hits if h.kind == "road"]
    city_hits = [h for h in hits if h.kind == "city"]
    log("search('TIMISOARA') -> %d road hit(s)/%d total, %d city hit(s)/%d total" % (
        len(road_hits), road_total, len(city_hits), city_total))
    assert road_total > 0, "expected road matches for TIMISOARA"
    assert city_total > 0, "expected a city match for TIMISOARA"
    timisoara_city = next((h for h in city_hits if "TIMISOARA" in h.name.upper()), None)
    assert timisoara_city is not None, "expected a Timisoara city hit"
    log("city hit: %r at (%.5f, %.5f)" % (timisoara_city.name, timisoara_city.lon, timisoara_city.lat))

    # "TIRAN" as a substring also matches unrelated Italian places (e.g.
    # "SARTIRANA LOMELLINA"), so of all "TIRAN*" city hits pick the one
    # closest to Tirana's already-validated real-world coordinates
    # (README §3.8: real Tirana is 19.8189E/41.3275N) rather than assuming
    # string-match order -- this is what a real "did search find the right
    # place" check should do, not a coincidence-prone name filter.
    REAL_TIRANA = (19.8189, 41.3275)
    hits2, road_total2, city_total2, _poi_total2 = data.search_combined("TIRAN", limit=100)
    city_hits2 = [h for h in hits2 if h.kind == "city"]
    log("search('TIRAN') -> %d city hit(s)/%d total" % (len(city_hits2), city_total2))
    assert city_total2 > 0, "expected at least one Albanian 'Tiran*' city match"
    tirana = min(city_hits2, key=lambda h: (h.lon - REAL_TIRANA[0]) ** 2 + (h.lat - REAL_TIRANA[1]) ** 2)
    log("closest 'TIRAN*' hit to real Tirana: %r at (%.5f, %.5f), bbox=%s" % (
        tirana.name, tirana.lon, tirana.lat, tirana.extra.bbox))
    # cross-check against this project's previously-validated real-world value (README §3.8)
    assert abs(tirana.lon - REAL_TIRANA[0]) < 0.3 and abs(tirana.lat - REAL_TIRANA[1]) < 0.3, \
        "no 'TIRAN*' search hit is anywhere near Tirana's known real-world location"
    assert "TIRAN" in tirana.name.upper(), "closest-by-distance hit should still plausibly be named Tirana"

    # --- 4. dynamic area loading: initial load around Timisoara -----------
    # `scale` is still a required positional arg (README §10 "v5 -> v6"),
    # though as of "v16 -> v17" it no longer affects WHICH layers get
    # pooled (see ensure_area_loaded()'s own docstring) -- FULL_FAST_SCALE
    # is passed here mostly for historical continuity with this section.
    # mp0 isn't ready yet at this point regardless (see section 2b above),
    # so the pooled set is exactly FAST_LAYERS either way.
    span = viewer.DEFAULT_JUMP_SPAN_DEG
    t_lon, t_lat = timisoara_city.lon, timisoara_city.lat
    t0 = time.time()
    result = data.ensure_area_loaded(t_lon - span, t_lon + span, t_lat - span, t_lat + span, FULL_FAST_SCALE)
    dt_initial = time.time() - t0
    n_tiles = sum(len(ids) for ids in result["tile_ids"].values())
    log("ensure_area_loaded(Timisoara, scale=%.0f) -> layers=%s, %d tile(s) total, %d newly decoded, %d features, %.3fs" % (
        FULL_FAST_SCALE, result["layers"], n_tiles, result["new_tiles"], len(result["features"]), dt_initial))
    assert result["layers"] == viewer.FAST_LAYERS, \
        "at a street-level scale before mp0 is ready, every fast layer (and only those) must be pooled"
    assert set(result["tile_ids"].keys()) == set(viewer.FAST_LAYERS), \
        "tile_ids must report per-layer tile lists for every pooled layer"
    assert n_tiles > 0, "expected some tiles to cover the Timisoara area"
    assert len(result["features"]) > 0, "expected some decoded road features near a real city"
    assert result["new_tiles"] == n_tiles, "first load should decode every covering tile fresh, across all layers"

    total_points = sum(len(f["points"]) for f in result["features"])
    assert total_points > 20, "expected a non-trivial number of decoded vertices"

    # --- 5. real road names actually attached to the decoded geometry -----
    named_count = 0
    example_names = []
    for feat in result["features"]:
        for start, end, name in feat.get("named_ranges", ()):
            if name:
                named_count += 1
                if len(example_names) < 12:
                    example_names.append(name)
    log("named vertex-ranges near Timisoara: %d, example names: %s" % (named_count, example_names))
    assert named_count > 0, "expected at least some vertex ranges to resolve to real eeu.rd road names"

    # --- 6. re-querying the SAME area must reuse the cached road-name index
    bbox_before = data._rd_index_bbox
    t0 = time.time()
    result_same = data.ensure_area_loaded(
        t_lon - span * 0.3, t_lon + span * 0.3, t_lat - span * 0.3, t_lat + span * 0.3, FULL_FAST_SCALE)
    dt_cached = time.time() - t0
    assert data._rd_index_bbox == bbox_before, "road-name index should NOT rebuild for an already-covered sub-area"
    assert result_same["new_tiles"] == 0, "re-requesting an already-covered area shouldn't decode new tiles"
    log("re-query of a covered sub-area: %.3fs (vs %.3fs initial), 0 new tiles, road-name index reused" % (
        dt_cached, dt_initial))

    # --- 7. simulated PAN to a DIFFERENT real place: new tiles must load,
    #        while Timisoara's tiles remain cached (not re-decoded/evicted)
    #        -- checked per-LAYER, since each fast layer keeps its own cache
    cached_tile_ids_before = {layer: set(data.tile_caches[layer].keys()) for layer in viewer.FAST_LAYERS}
    hits3, _, _, _ = data.search_combined("PRAHA", limit=10)
    city_hits3 = [h for h in hits3 if h.kind == "city"]
    if city_hits3:
        target2 = city_hits3[0]
    else:
        road_hits3 = [h for h in hits3 if h.kind == "road"]
        assert road_hits3, "expected at least a road or city hit for PRAHA"
        target2 = road_hits3[0]
    t0 = time.time()
    result2 = data.ensure_area_loaded(
        target2.lon - span, target2.lon + span, target2.lat - span, target2.lat + span, FULL_FAST_SCALE)
    dt_pan = time.time() - t0
    n_tiles2 = sum(len(ids) for ids in result2["tile_ids"].values())
    log("simulated pan to %r (%.5f, %.5f) -> layers=%s, %d tile(s) total, %d newly decoded, %d features, %.3fs" % (
        target2.name, target2.lon, target2.lat, result2["layers"], n_tiles2, result2["new_tiles"],
        len(result2["features"]), dt_pan))
    assert result2["layers"] == viewer.FAST_LAYERS, "panning (mp0 still not ready) must keep pooling the same fast layers"
    assert result2["new_tiles"] > 0, "panning to a distant real place should decode new tiles"
    for layer in viewer.FAST_LAYERS:
        after_ids = set(data.tile_caches[layer].keys())
        assert cached_tile_ids_before[layer].issubset(after_ids), \
            "previously-decoded %s tiles must remain cached after panning away, not be evicted" % layer
    total_cached_before = sum(len(s) for s in cached_tile_ids_before.values())
    total_cached_after = sum(len(data.tile_caches[layer]) for layer in viewer.FAST_LAYERS)
    assert total_cached_after > total_cached_before, "tile cache must grow (across layers), not just replace"

    # --- 7b. real multi-layer UNION verification at a dense real area:
    #         Sofia, Bulgaria (the exact coordinates that originally
    #         motivated automatic layer selection, then this session's
    #         "show every layer at once" follow-up -- README §10). Proves
    #         (a) tiles/features from EVERY fast layer are present in one
    #         ensure_area_loaded() call, and (b) the pooled total is an
    #         EXACT flat sum of each layer's own decode output -- not a
    #         combinatorial blow-up, which is the concrete "don't
    #         over-engineer dedup, but this specific bug would be a real
    #         bug" sanity check the task asked for.
    SOFIA_LON, SOFIA_LAT = 23.40102, 42.65533
    half = 0.05
    sofia_fast = data.ensure_area_loaded(
        SOFIA_LON - half, SOFIA_LON + half, SOFIA_LAT - half, SOFIA_LAT + half, FULL_FAST_SCALE)
    assert set(sofia_fast["tile_ids"].keys()) == set(viewer.FAST_LAYERS), \
        "at a street-level scale (before mp0 is ready), a single ensure_area_loaded() call must return " \
        "tiles from every fast layer at once"
    per_layer_points = {}
    for layer in viewer.FAST_LAYERS:
        ids = sofia_fast["tile_ids"][layer]
        per_layer_points[layer] = sum(len(f["points"]) for tid in ids for f in data.tile_caches[layer].get(tid, ()))
    union_points = sum(len(f["points"]) for f in sofia_fast["features"])
    log("Sofia-area per-layer points: %s ; pooled union total: %d" % (per_layer_points, union_points))
    assert union_points == sum(per_layer_points.values()), \
        "the pooled union must be an EXACT flat sum of each layer's own decode output, not combinatorial"
    assert union_points > max(per_layer_points.values()), \
        "pooling all fast layers together must show strictly more points than any single layer alone"
    assert all(v > 0 for v in per_layer_points.values()), \
        "expected every fast layer to contribute at least some real points at this real, previously-documented area"

    # --- 7c. Layer pooling is now SCALE-INDEPENDENT -- checkboxes are the
    #         ONLY control (README §10 "v16 -> v17", superseding this
    #         session's own earlier "v5 -> v6" cumulative-scale-stacking
    #         model documented in the README's history). `layers_for_scale()`
    #         itself is UNCHANGED and still directly pure-function-tested in
    #         section 1b above, but MapData.ensure_area_loaded() no longer
    #         calls it to GATE what's pooled -- the pooled set is now
    #         exactly `available_layers()` restricted only by
    #         `allowed_layers` (checked boxes), regardless of `scale`.
    #         Verified directly against the real ISO: sweeping the SAME real
    #         Sofia bbox across every scale this project's tests have
    #         historically used (500 through 10,000 px/deg -- previously
    #         mg4-only through all-four-fast-layers) must now return the
    #         IDENTICAL layer set/point count at EVERY scale, not a
    #         monotonically growing one.
    scale_sweep = (500.0, 1500.0, 4000.0, 10000.0)
    sweep_results = []
    for s in scale_sweep:
        r = data.ensure_area_loaded(SOFIA_LON - half, SOFIA_LON + half, SOFIA_LAT - half, SOFIA_LAT + half, s)
        pts = sum(len(f["points"]) for f in r["features"])
        sweep_results.append((s, r["layers"], pts))
        log("Sofia-area sweep (v16 -> v17, scale no longer gates layers): scale=%.0f -> layers=%s, "
            "%d point(s) pooled" % (s, r["layers"], pts))
    first_scale, first_layers, first_pts = sweep_results[0]
    for s, layers, pts in sweep_results[1:]:
        assert layers == first_layers, \
            "layer pooling must no longer depend on scale (README §10 'v16 -> v17') -- scale=%.0f gave %s, " \
            "expected the same %s already pooled at scale=%.0f" % (s, layers, first_layers, first_scale)
        assert pts == first_pts, \
            "pooled point count must no longer depend on scale either, since the SAME (unrestricted) layer " \
            "set is used regardless of zoom (scale=%.0f: %d points, expected %d)" % (s, pts, first_pts)
    assert first_layers == viewer.FAST_LAYERS, \
        "before mp0 is ready, the unrestricted (all-checked) pool must be exactly the four fast layers, " \
        "at EVERY scale now -- not just a sufficiently-zoomed-in one"
    assert first_pts == union_points, \
        "the scale-independent pooled point count must equal the same flat-sum union already measured in 7b"
    log("confirmed (README §10 'v16 -> v17'): layer pooling no longer varies with scale -- %d points pooled "
        "identically at every scale from %.0f to %.0f" % (first_pts, scale_sweep[0], scale_sweep[-1]))

    # Tiles decoded during this sweep must genuinely be cached, not
    # re-decoded on a re-query at a different scale (scale never affected
    # WHICH tiles get decoded here, only -- previously -- which of them got
    # pooled; now not even that).
    rezoom = data.ensure_area_loaded(
        SOFIA_LON - half, SOFIA_LON + half, SOFIA_LAT - half, SOFIA_LAT + half, scale_sweep[0])
    assert rezoom["new_tiles"] == 0, \
        "re-querying the same bbox at an already-visited scale must be a pure cache hit -- no tiles re-decoded"
    log("confirmed: re-querying the same Sofia bbox is a pure cache hit regardless of scale")

    # --- 8. city label query: Tirana's own bbox must surface it -----------
    lon_min, lat_min, lon_max, lat_max = tirana.extra.bbox
    city_results = data.cty_cache.query(lon_min - 0.05, lon_max + 0.05, lat_min - 0.05, lat_max + 0.05,
                                         min_area=0.0, limit=50)
    names_found = [c.name for c in city_results]
    assert any("TIRAN" in n.upper() for n in names_found), \
        "querying Tirana's own bounding box should surface a Tirana-named city record"
    log("city viewport query around Tirana's bbox found %d cities, including: %s" % (
        len(city_results), [n for n in names_found if "TIRAN" in n.upper()]))

    # --- 8b. background mp0 ("street-level detail") loading + automatic,
    #         ADDITIVE fold-in -- the core "don't error/block if the user
    #         looks before it's ready; fold it into the SAME view (not a
    #         full swap) the moment it's ready" behavior, checked directly
    #         against the real ISO, not just described in a docstring -----
    assert data.available_layers() == viewer.FAST_LAYERS, "before mp0 is ready, available_layers() excludes mp0"

    t0 = time.time()
    ok = data.load_heavy_layer(progress=log)
    dt_mp0 = time.time() - t0
    assert ok and data.mp0_ready and not data.mp0_building
    log("load_heavy_layer() (mp0 extraction + geo-index) finished in %.1fs (vs %.1fs for all 4 fast layers + rd/cty caches)" % (
        dt_mp0, dt_open))
    assert dt_mp0 > dt_open, \
        "mp0's build should be the genuinely slow part this design keeps out of the fast 'Open Map ISO' path"

    assert data.available_layers() == viewer.FAST_LAYERS + ["mp0"], \
        "once mp0 is ready, available_layers() must include it alongside every fast layer"

    # README §10 "v16 -> v17": layer pooling is no longer scale-gated -- once
    # mp0 is ready (and not excluded by any checkbox, the default), it must
    # now be pooled even at the LOWEST (most zoomed-out) scale, not withheld
    # until the user zooms in to "street level" the way the old
    # SCALE_LAYER_THRESHOLDS-based gating (README §10 "v5 -> v6") required.
    # This is the real-ISO, MapData-level counterpart of the checkbox-only-
    # control change the user explicitly asked for.
    sofia_low_after_mp0 = data.ensure_area_loaded(
        SOFIA_LON - half, SOFIA_LON + half, SOFIA_LAT - half, SOFIA_LAT + half, scale_sweep[0])
    assert sofia_low_after_mp0["layers"] == viewer.ALL_LAYERS, \
        "mp0 being available (and checked, the default) must now be pooled at EVERY scale, including the " \
        "most zoomed-out one -- scale must no longer restrict which layers are considered (README §10 " \
        "'v16 -> v17')"
    low_scale_mp0_points = sum(len(f["points"]) for f in sofia_low_after_mp0["features"])
    assert low_scale_mp0_points > union_points, \
        "mp0's real content must be included in a zoomed-out view's pooled points now, not withheld until " \
        "the user zooms in to street level"
    log("confirmed (README §10 'v16 -> v17'): mp0 IS pooled at scale=%.0f (max zoomed-out in this sweep) once "
        "ready -- %d points (vs %d without mp0) -- no more waiting for street-level zoom" % (
            scale_sweep[0], low_scale_mp0_points, union_points))

    sofia_all = data.ensure_area_loaded(
        SOFIA_LON - half, SOFIA_LON + half, SOFIA_LAT - half, SOFIA_LAT + half, FULL_FAST_SCALE)
    assert set(sofia_all["tile_ids"].keys()) == set(viewer.FAST_LAYERS + ["mp0"]), \
        "the same bbox re-queried at a street-level scale after mp0 is ready must return tiles from all five layers"
    all_points = sum(len(f["points"]) for f in sofia_all["features"])
    mp0_ids = sofia_all["tile_ids"]["mp0"]
    mp0_points = sum(len(f["points"]) for tid in mp0_ids for f in data.tile_caches["mp0"].get(tid, ()))
    log("Sofia-area AFTER mp0 ready (scale=%.0f) -> layers=%s, mp0 alone contributes %d point(s), pooled "
        "total %d point(s) (was %d point(s) with just the 4 fast layers)" % (
            FULL_FAST_SCALE, sofia_all["layers"], mp0_points, all_points, union_points))
    assert mp0_points > 0, "expected mp0 to contribute real points at this real, previously-documented dense area"
    assert all_points > union_points, \
        "folding mp0 in must show MORE total points than the 4-fast-layer pool did, not replace it"
    assert all_points == union_points + mp0_points, \
        "mp0's fold-in must be purely ADDITIVE: the 4 fast layers' own tiles are cached/unchanged, only mp0 is new"
    assert len(data.tile_caches["mp0"]) > 0 and data.tile_caches["mp0"] is not data.tile_caches["mg1"], \
        "mp0 must have its own separate per-layer tile cache, not share mg1's tile_id numbering"

    # --- 8c. Layer visibility checkboxes: `allowed_layers` restriction
    #         (README §10 "v8 -> v9", now CHECKBOX-ONLY control per
    #         "v16 -> v17" -- scale is no longer part of this decision at
    #         all, already proven independently at every scale in 7c/8b
    #         above, so a single representative scale suffices here).
    #         `allowed_layers=None` (omitted, i.e. every checkbox checked)
    #         must pool EVERY available layer (all_points, the full 5-layer
    #         total already measured above) -- checked at the LOWEST scale
    #         in this file's sweep, deliberately, to prove the checkbox
    #         behavior doesn't depend on being zoomed in at all.
    CHECK_SCALE = scale_sweep[0]  # 500.0 -- max zoomed-out
    r_default = data.ensure_area_loaded(
        SOFIA_LON - half, SOFIA_LON + half, SOFIA_LAT - half, SOFIA_LAT + half, CHECK_SCALE)
    pts_default = sum(len(f["points"]) for f in r_default["features"])
    assert r_default["layers"] == viewer.ALL_LAYERS and pts_default == all_points, \
        "allowed_layers=None (default/all-checked) must pool every available layer (%d points) even at the " \
        "lowest scale (%.0f) -- checkbox-only control, no scale gating (README §10 'v16 -> v17')" % (
            all_points, CHECK_SCALE)
    log("allowed_layers=None (all-checked) at scale=%.0f (max zoomed out): layers=%s, %d points -- matches "
        "the full all_points total measured at street-level scale earlier, confirming scale no longer "
        "matters" % (CHECK_SCALE, r_default["layers"], pts_default))

    # Passing allowed_layers=set(ALL_LAYERS) (the literal "every checkbox
    # checked" GUI state) explicitly, not just omitting the argument, must
    # reproduce the exact same numbers -- proves the intersection is a
    # true no-op when nothing is unchecked, not merely that the default
    # argument value behaves specially.
    all_checked = viewer.ALL_LAYERS
    r_all_checked = data.ensure_area_loaded(
        SOFIA_LON - half, SOFIA_LON + half, SOFIA_LAT - half, SOFIA_LAT + half, CHECK_SCALE,
        allowed_layers=all_checked)
    pts_all_checked = sum(len(f["points"]) for f in r_all_checked["features"])
    assert pts_all_checked == all_points, \
        "allowed_layers=set(ALL_LAYERS) (every checkbox checked) must reproduce the same point count as " \
        "allowed_layers=None"
    log("confirmed: allowed_layers=None and allowed_layers=ALL_LAYERS (all boxes checked) are both "
        "identical -- %d points at scale=%.0f (max zoomed out)" % (pts_all_checked, CHECK_SCALE))

    # Unchecking mg1 must remove EXACTLY mg1's own contribution, regardless
    # of scale -- a strong, exact real-measured check, not just "some
    # points went away". mp0 stays checked/pooled here (it's ready and not
    # excluded), unlike the old scale-gated behavior where a low scale
    # would have excluded it anyway.
    allowed_no_mg1 = {"mg4", "mg3", "mg2", "mp0"}
    r_no_mg1 = data.ensure_area_loaded(
        SOFIA_LON - half, SOFIA_LON + half, SOFIA_LAT - half, SOFIA_LAT + half, CHECK_SCALE,
        allowed_layers=allowed_no_mg1)
    pts_no_mg1 = sum(len(f["points"]) for f in r_no_mg1["features"])
    log("unchecking mg1 at scale=%.0f (max zoomed out) -> layers=%s, %d point(s) (was %d with everything "
        "checked)" % (CHECK_SCALE, r_no_mg1["layers"], pts_no_mg1, all_points))
    assert r_no_mg1["layers"] == ["mg4", "mg3", "mg2", "mp0"], \
        "unchecking mg1 must restrict the pooled set to exactly the remaining checked+available layers, " \
        "regardless of scale"
    mg1_only_points = all_points - pts_no_mg1
    assert mg1_only_points > 0, \
        "unchecking mg1 must actually drop some real, measurable points -- mg1's own exact contribution"
    log("confirmed: unchecking mg1 drops exactly its own real contribution (%d points), independent of "
        "scale (README §10 'v16 -> v17')" % mg1_only_points)

    # Unchecking mp0 must exclude it even though it's ready and would
    # otherwise ALWAYS be pooled now (no more scale gate to rely on); re-
    # checking it must bring back exactly the same mp0 point count as
    # `sofia_all` above, via a pure cache hit (new_tiles==0), not a fresh
    # decode.
    r_no_mp0 = data.ensure_area_loaded(
        SOFIA_LON - half, SOFIA_LON + half, SOFIA_LAT - half, SOFIA_LAT + half, CHECK_SCALE,
        allowed_layers=set(viewer.FAST_LAYERS))  # mp0 deliberately excluded
    assert "mp0" not in r_no_mp0["layers"] and "mp0" not in r_no_mp0["tile_ids"], \
        "unchecking mp0 must prevent it from appearing even though it's ready and would otherwise always " \
        "be pooled now (no scale gate left to exclude it on its own)"
    pts_no_mp0 = sum(len(f["points"]) for f in r_no_mp0["features"])
    assert pts_no_mp0 == union_points, \
        "with mp0 unchecked, the pooled total (at ANY scale now) must equal the 4-fast-layer-only total " \
        "measured before mp0 was ever ready"
    log("confirmed: unchecking mp0 excludes it (%d points, same as the pre-mp0-ready 4-fast-layer total) "
        "even at the lowest scale, where it would otherwise always be pooled now" % pts_no_mp0)

    r_mp0_rechecked = data.ensure_area_loaded(
        SOFIA_LON - half, SOFIA_LON + half, SOFIA_LAT - half, SOFIA_LAT + half, CHECK_SCALE,
        allowed_layers=set(viewer.ALL_LAYERS))  # re-checked
    assert r_mp0_rechecked["new_tiles"] == 0, \
        "re-checking mp0 (its tiles were already decoded earlier in this test) must be a pure cache hit, " \
        "not a fresh decode/load"
    pts_mp0_rechecked = sum(len(f["points"]) for f in r_mp0_rechecked["features"])
    assert pts_mp0_rechecked == all_points, \
        "re-checking mp0 must restore the exact same pooled total as when it was originally included"
    log("confirmed: re-checking mp0 restores its %d points via a pure cache hit (0 new tiles decoded)" % mp0_points)

    # Sanity: an allowed_layers set that excludes EVERYTHING must pool
    # nothing at all, without raising.
    r_none = data.ensure_area_loaded(
        SOFIA_LON - half, SOFIA_LON + half, SOFIA_LAT - half, SOFIA_LAT + half, CHECK_SCALE,
        allowed_layers=set())
    assert r_none["layers"] == [] and r_none["features"] == [], \
        "an empty allowed_layers set must pool nothing, not raise or fall back to the unrestricted set"
    log("confirmed: allowed_layers=set() (hypothetically all boxes unchecked) pools nothing, no crash")

    log("layer-visibility allowed_layers checks PASSED (checkbox-only control, scale-independent, README §10 "
        "'v16 -> v17')")

    # --- 8d. Connected-roads ground-truth re-validation at the
    #         MapData/decode_tile() level (README §10 "v9 -> v10"): re-check,
    #         via the SAME code path the running App now uses for
    #         connected-roads rendering (MapData.decode_tile(...,
    #         want_adjacency=True) + MapData.topo_caches), the exact 2
    #         human-verified ground-truth tiles already validated at the
    #         resolve_topology_adjacency() level (README §3.6): mg2 tile_id
    #         20597 (203-point feature, 16/16 confirmed real edges,
    #         shift=1, confidence "high") and mp0 tile_id 91124 (306-point
    #         feature, 18 confirmed real edges/16 recoverable, shift=2,
    #         confidence "high"). This re-proves the VIEWER's own
    #         caching/tagging wiring (not just the underlying research
    #         module) reproduces the correct result -- the canvas-level
    #         check further below (inside the GUI section) then proves the
    #         RENDERED lines match this data.
    MG2_TILE_ID, MG2_N_POINTS = 20597, 203
    MG2_EDGE_SEQUENCE = [202, 190, 189, 185, 186, 188, 191, 192, 193, 195, 197, 199, 201, 200, 198, 196, 194]
    mg2_kept = data.decode_tile("mg2", MG2_TILE_ID, want_adjacency=True)
    mg2_feat = next((f for f in mg2_kept if len(f["points"]) == MG2_N_POINTS), None)
    assert mg2_feat is not None, "expected the known 203-point ground-truth feature in mg2 tile 20597"
    mg2_result = data.topo_caches["mg2"][MG2_TILE_ID][mg2_feat["feature_index"]]
    log("mg2 tile %d ground-truth feature: found=%s shift=%s confidence=%s median_edge_m=%s, %d edge(s) total" % (
        MG2_TILE_ID, mg2_result["found"], mg2_result["shift"], mg2_result["confidence"],
        mg2_result["median_edge_m"], len(mg2_result["edges"])))
    assert mg2_result["found"] and mg2_result["confidence"] == "high", \
        "mg2 tile 20597's ground-truth feature must resolve with high confidence"
    assert mg2_result["shift"] == 1, "mg2 tile 20597 must auto-detect shift=1, per README §3.6"
    mg2_expected_edges = {tuple(sorted((MG2_EDGE_SEQUENCE[i], MG2_EDGE_SEQUENCE[i + 1])))
                           for i in range(len(MG2_EDGE_SEQUENCE) - 1)}
    mg2_actual_edges = set(mg2_result["edges"])
    mg2_hits = mg2_expected_edges & mg2_actual_edges
    log("mg2 ground-truth edges recovered in the resolved graph: %d/%d" % (len(mg2_hits), len(mg2_expected_edges)))
    assert len(mg2_hits) == 16, \
        "expected all 16/16 confirmed real mg2 ground-truth edges in the resolved adjacency graph (got %d)" % len(mg2_hits)

    MP0_TILE_ID, MP0_N_POINTS = 91124, 306
    MP0_POINT_SEQUENCE = [221, 200, 183, 186, 190, 198, 218, 227, 244, 253, 259, 270, 274, 282, 277, 271, 264, 251, 240]
    mp0_kept = data.decode_tile("mp0", MP0_TILE_ID, want_adjacency=True)
    mp0_feat = next((f for f in mp0_kept if len(f["points"]) == MP0_N_POINTS), None)
    assert mp0_feat is not None, "expected the known 306-point ground-truth feature in mp0 tile 91124"
    mp0_result = data.topo_caches["mp0"][MP0_TILE_ID][mp0_feat["feature_index"]]
    log("mp0 tile %d ground-truth feature: found=%s shift=%s confidence=%s median_edge_m=%s, %d edge(s) total" % (
        MP0_TILE_ID, mp0_result["found"], mp0_result["shift"], mp0_result["confidence"],
        mp0_result["median_edge_m"], len(mp0_result["edges"])))
    assert mp0_result["found"] and mp0_result["confidence"] == "high", \
        "mp0 tile 91124's ground-truth feature must resolve with high confidence"
    assert mp0_result["shift"] == 2, "mp0 tile 91124 must auto-detect shift=2, per README §3.6"
    mp0_expected_edges = {tuple(sorted((MP0_POINT_SEQUENCE[i], MP0_POINT_SEQUENCE[i + 1])))
                           for i in range(len(MP0_POINT_SEQUENCE) - 1)}
    mp0_actual_edges = set(mp0_result["edges"])
    mp0_hits = mp0_expected_edges & mp0_actual_edges
    mp0_misses = mp0_expected_edges - mp0_actual_edges
    log("mp0 ground-truth edges recovered in the resolved graph: %d/%d, misses: %s" % (
        len(mp0_hits), len(mp0_expected_edges), sorted(mp0_misses)))
    assert len(mp0_hits) >= 16, \
        "expected at least 16/18 confirmed real mp0 ground-truth edges in the resolved adjacency graph (got %d)" % len(mp0_hits)
    log("ground-truth resolve_topology_adjacency() re-validation via MapData.decode_tile() PASSED")

    # --- 8f. Per-edge false-positive filter (map_compressed_reader.py
    #         `resolve_topology_adjacency()`'s new `max_edge_m` sanity
    #         filter): a real bug found via the map viewer's own new edge
    #         click-to-identify feature ("v16 -> v17") -- a user right-
    #         clicked 5 specific rendered connected-roads LINES in the
    #         Sofia area and reported their two endpoints were real,
    #         confirmed-unrelated points 692m-2,917m apart (real
    #         intersections/adjacent points are meters to tens of meters
    #         apart, never that far). Root cause (see
    #         resolve_topology_adjacency()'s own docstring for the full
    #         write-up): the shared-"link-id" mechanism used to accept an
    #         edge between ANY two points sharing a link-id value without
    #         checking the edge's own real-world plausibility -- 4/5 cases
    #         shared the literal value 0 (almost certainly a padding/
    #         sentinel value, the same role "0" plays elsewhere in this
    #         format, §3.6), the 5th shared a small non-zero value that
    #         also happened to be reused across unrelated points. Fixed by
    #         a new per-EDGE distance sanity filter (`max_edge_m`, default
    #         200m -- chosen with a large margin over the highest distance
    #         among EVERY human-verified real edge in this project's two
    #         ground-truth tiles, 104.2m) applied to the FINAL edge list,
    #         independent of the existing per-FEATURE median-based
    #         confidence gate (which is a robust statistic that a small
    #         minority of bad edges can survive within, exactly what
    #         happened here -- both bug tiles below still report
    #         "confidence": "high" for their whole feature).
    FALSE_EDGE_CASES = [
        ("mg2", 20602, 4, 253, "OBORISHTE <-> unnamed, reported ~1.7km apart"),
        ("mg1", 35191, 19, 119, "MARIN DRINOV <-> PROFESOR MILKO BICHEV, reported ~714m apart"),
        ("mg1", 35197, 217, 263, "unnamed <-> ORLANDOVTSI, reported ~2.9km apart"),
        ("mg2", 20602, 30, 84, "EVLOGI I HRISTO GEORGIEVI <-> unnamed, reported ~1.34km apart"),
        ("mg1", 35188, 45, 271, "YOSIF PETROV <-> unnamed, reported ~2.2km apart"),
    ]
    for layer, tile_id, a_idx, b_idx, desc in FALSE_EDGE_CASES:
        kept = data.decode_tile(layer, tile_id, want_adjacency=True)
        feat = next((f for f in kept if len(f["points"]) > max(a_idx, b_idx)), None)
        assert feat is not None, "%s tile %d: expected a feature with at least %d points" % (
            layer, tile_id, max(a_idx, b_idx) + 1)
        adj_result = data.topo_caches[layer][tile_id][feat["feature_index"]]
        bad_edge = (min(a_idx, b_idx), max(a_idx, b_idx))
        present = bad_edge in set(adj_result["edges"])
        log("false-edge check (%s): %s tile %d feature %d, edge %s -- confidence=%s, still present " \
            "after fix=%s (must be False), edges_dropped_implausible=%d" % (
                desc, layer, tile_id, feat["feature_index"], bad_edge, adj_result["confidence"], present,
                adj_result.get("edges_dropped_implausible", 0)))
        assert not present, \
            "%s: the reported false edge %s must be EXCLUDED by the new per-edge distance filter, but it's " \
            "still present in resolve_topology_adjacency()'s returned edges" % (desc, bad_edge)
        assert adj_result.get("edges_dropped_implausible", 0) > 0, \
            "%s: expected at least one edge to have been dropped by the implausible-distance filter for " \
            "this feature" % desc
    log("all 5 user-reported false connected-roads edges confirmed EXCLUDED by the new per-edge distance " \
        "filter (README §3.6/§10 'v16 -> v17') -- PASSED")

    # And confirm, once more explicitly at the MapData/viewer level (not
    # just the bare research-module level already shown above), that this
    # fix causes ZERO regression on both existing ground-truth tiles: both
    # must still resolve every one of their human-verified edges.
    mg2_kept_refresh = data.decode_tile("mg2", MG2_TILE_ID, want_adjacency=True)
    mg2_feat_refresh = next((f for f in mg2_kept_refresh if len(f["points"]) == MG2_N_POINTS), None)
    mg2_result_refresh = data.topo_caches["mg2"][MG2_TILE_ID][mg2_feat_refresh["feature_index"]]
    mg2_hits_refresh = mg2_expected_edges & set(mg2_result_refresh["edges"])
    assert len(mg2_hits_refresh) == 16, \
        "the per-edge distance filter must not regress the mg2 20597 ground truth (still expected 16/16, got %d)" % \
        len(mg2_hits_refresh)
    log("confirmed: mg2 tile 20597's 16/16 human-verified edges are UNCHANGED by the new per-edge filter " \
        "(dropped %d other, implausible edges instead)" % mg2_result_refresh.get("edges_dropped_implausible", 0))

    # --- 8e. Performance: real cost of `want_adjacency=True` at tile-decode
    #         time (README §10 "v9 -> v10" -- "measure, don't assume"). Two
    #         FRESH MapData instances, each loaded independently (so
    #         tile_caches/topo_caches start empty in each), decode the
    #         IDENTICAL Sofia-area bbox/scale -- isolating
    #         resolve_topology_adjacency()'s added per-tile cost from
    #         ordinary tile-decode cost, which a shared/warm cache would
    #         otherwise hide.
    data_adj_off = viewer.MapData(ISO_PATH)
    data_adj_off.load(progress=log)
    t0 = time.time()
    r_adj_off = data_adj_off.ensure_area_loaded(
        SOFIA_LON - half, SOFIA_LON + half, SOFIA_LAT - half, SOFIA_LAT + half, 10000.0,
        want_adjacency=False)
    dt_adj_off = time.time() - t0
    pts_adj_off = sum(len(f["points"]) for f in r_adj_off["features"])
    data_adj_off.close()

    data_adj_on = viewer.MapData(ISO_PATH)
    data_adj_on.load(progress=log)
    t0 = time.time()
    r_adj_on = data_adj_on.ensure_area_loaded(
        SOFIA_LON - half, SOFIA_LON + half, SOFIA_LAT - half, SOFIA_LAT + half, 10000.0,
        want_adjacency=True)
    dt_adj_on = time.time() - t0
    pts_adj_on = sum(len(f["points"]) for f in r_adj_on["features"])
    n_tiles_adj = sum(len(ids) for ids in r_adj_on["tile_ids"].values())
    data_adj_on.close()

    log("ensure_area_loaded() Sofia bbox scale=10000, fresh MapData each: want_adjacency=False -> %.3fs "
        "(%d points); want_adjacency=True -> %.3fs (%d points, %d tiles) -- extra cost of "
        "resolve_topology_adjacency() on every pooled tile: %.3fs (%.2fx)" % (
            dt_adj_off, pts_adj_off, dt_adj_on, pts_adj_on, n_tiles_adj,
            dt_adj_on - dt_adj_off, (dt_adj_on / dt_adj_off) if dt_adj_off > 0 else float("inf")))
    assert pts_adj_off == pts_adj_on, \
        "want_adjacency must not change which tiles/points are decoded, only whether adjacency is ALSO computed"
    log("want_adjacency=True/False tile-decode-time performance comparison PASSED")

    # --- 8h. Address entry / letter-keyboard feature (README §10
    #         "v11 -> v12"): rt_root()/ct_root() root-finding validation,
    #         live per-letter enable/disable against real data, country
    #         list, and end-to-end address resolution to real coordinates.
    import road_index_reader as rir
    import city_reader as cr
    import ctr_reader as ctrr
    import flat_compressed_reader as fcr
    import rns510_iso as riso

    # 8h-i. rt_root(): concrete "how much better than the old hand-picked
    # D-node" comparison, reproduced here (not just quoted from the
    # module's own docstring) against the SAME real ISO this whole suite
    # already uses.
    assert data.rt_body is None and not data.address_data_ready, \
        "address-entry data must not be loaded until load_address_entry_data() is explicitly called"
    log("(sanity) address-entry data not yet loaded on this MapData instance, as expected")

    t0 = time.time()
    data.load_address_entry_data(progress=log)
    log("load_address_entry_data() finished in %.1fs" % (time.time() - t0))
    assert data.address_data_ready
    assert data.rt_body is not None and len(data.rt_body) == 245698715, \
        "decompressed eeuz.rt body must match the exact reference-disc size documented in road_index_reader.py"

    old_leaves = rir.rt_walk_strings(data.rt_body, 65, max_results=100000, max_depth=60)
    root_entries = rir.rt_root()
    assert set(root_entries.keys()) == set("ABCDEFGHIJKLMNOPQRSTUVWXYZ"), \
        "rt_root() must have a validated entry for every letter A-Z"
    new_leaves = 0
    typ_hits_union = set()
    typ_words = set()
    # Build the same real eeu.typ cross-reference corpus road_index_reader.py's
    # own validation used, straight from the real ISO (not a hardcoded list).
    iso = riso.open_tolerant(ISO_PATH)
    try:
        import tempfile
        typ_tmp = tempfile.mktemp(suffix=".typ")
        with open(typ_tmp, "wb") as f:
            iso.get_file_from_iso_fp(f, iso_path="/DB/EEU.TYP")
    finally:
        iso.close()
    with open(typ_tmp, "rb") as f:
        typ_body = f.read()[94:]
    for i in range(len(typ_body) // 41):
        name = typ_body[i * 41:i * 41 + 40].split(b"\x00", 1)[0].decode("latin1").strip()
        if len(name) >= 4:
            typ_words.add(name)
    os.remove(typ_tmp)

    for ch, (node_start, subtree_size) in root_entries.items():
        assert rir.rt_char(data.rt_body, node_start) == ch, \
            "rt_root()'s entry for %r must actually decode to that character at its stored offset" % ch
        words = rir.rt_walk_strings(data.rt_body, node_start, max_results=20000, max_depth=60)
        new_leaves += len(words)
        blob = " ".join(w.upper() for w in words if "�" not in w)
        for tw in typ_words:
            if tw in blob:
                typ_hits_union.add(tw)
    log("rt_root() validation: old hand-picked D-node (offset 65) reaches %d leaf string(s); "
        "union of the 26 rt_root() entries reaches %d leaf string(s) (capped 20000/letter) -- a %.0fx increase; "
        "%d distinct real eeu.typ words cross-referenced across the union: %s" % (
            len(old_leaves), new_leaves, new_leaves / max(len(old_leaves), 1), len(typ_hits_union),
            sorted(typ_hits_union)))
    assert len(old_leaves) <= 5, "sanity: the old D-node's own reach should still be tiny, as documented"
    assert new_leaves > 1000 * max(len(old_leaves), 1), \
        "rt_root()'s union must reach dramatically (>1000x) more leaves than the old single D-node"
    assert len(typ_hits_union) >= 10, \
        "rt_root()'s union must cross-reference a healthy number of real eeu.typ words, not a fluke hit or two"

    # 8h-ii. ct_root(): same style of validation, against a freshly
    # extracted+decompressed eeuz.ct (MapData doesn't load this itself --
    # see load_address_entry_data()'s own docstring for why -- so this test
    # extracts it directly, the same way city_reader.py's own module
    # docstring numbers were derived).
    iso = riso.open_tolerant(ISO_PATH)
    try:
        ct_tmp = tempfile.mktemp(suffix=".ct")
        with open(ct_tmp, "wb") as f:
            iso.get_file_from_iso_fp(f, iso_path="/DB/EEUZ.CT")
    finally:
        iso.close()
    ct_doc = fcr.open_flat(ct_tmp)
    ct_body = fcr.decompress_all(ct_doc)[94:]
    os.remove(ct_tmp)
    assert len(ct_body) == 16454990, "decompressed eeuz.ct body must match the documented reference-disc size"
    ct_entries = cr.ct_root()
    assert set(ct_entries.keys()) == set("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    for ch, (node_start, subtree_size) in ct_entries.items():
        assert rir.rt_char(ct_body, node_start) == ch, \
            "ct_root()'s entry for %r must actually decode to that character at its stored offset" % ch
    ct_leaves = sum(len(rir.rt_walk_strings(ct_body, ns, max_results=20000, max_depth=60))
                     for ns, _ in ct_entries.values())
    log("ct_root() validation: all 26 letters have a real, offset-verified entry; union reaches %d leaf "
        "string(s) (capped 20000/letter)." % ct_leaves)
    assert ct_leaves > 1000, "ct_root()'s union should reach a substantial number of real leaf strings"

    # 8h-iii. The documented real, load-bearing negative finding: "SOFIA" is
    # a confirmed real eeuz.cl entry but is NOT reachable from ANY found
    # 'S'-starting .ct shard -- reproduced directly here (not just quoted),
    # confirming why the viewer's City field does NOT rely on ct_root().
    s_node, s_size = ct_entries["S"]
    s_words = rir.rt_walk_strings(ct_body, s_node, max_results=5000, max_depth=40)
    assert not any("SOFIA" in w.upper() for w in s_words), \
        "this is a documented negative finding (see city_reader.py's ct_root() docstring) -- if this now " \
        "passes, ct_root()'s 'S' entry changed and the PrefixNameIndex-based design rationale should be re-checked"
    log("confirmed (again, directly): 'SOFIA' is genuinely not reachable from ct_root()'s own 'S' shard -- "
        "this is exactly why City uses PrefixNameIndex over eeu.cty, not the .ct trie, for live narrowing")

    # 8h-iv. eeu.ctr (country list) -- fully cracked, small, exhaustive.
    countries = data.countries
    assert len(countries) == 35, "reference disc must have exactly 35 eeu.ctr records"
    balgaria = [c for c in countries if c.name == "BALGARIA"]
    assert len(balgaria) == 1 and balgaria[0].index == 19 and balgaria[0].iso3 == "BGR" and balgaria[0].iso2 == "BG", \
        "BALGARIA (the exact value shown in this feature's reference photo) must decode correctly"
    log("eeu.ctr: 35/35 countries decoded, BALGARIA confirmed at index 19 (BGR/BG) -- matches the reference photo")

    # 8h-v. Live enabled-letters progression for City, THE concrete
    # validation example this feature was built against: type "S", "SO",
    # "SOF", "SOFI" against the real, already-cracked eeu.cty data and
    # confirm the enabled letter set only ever narrows to real completions,
    # with 'A' remaining enabled all the way to "SOFI" (so the user can
    # complete "SOFIA"), and the final "SOFIA" resolving to real Sofia
    # coordinates (already independently validated elsewhere in this
    # project, README §3.8: ~23.32E/42.70N).
    idx = data.city_name_index
    prev_count = None
    for p in ("S", "SO", "SOF", "SOFI"):
        enabled = idx.enabled_next_chars(p)
        count = idx.count_matches(p)
        assert count > 0, "each real prefix of SOFIA must have at least one match"
        if prev_count is not None:
            assert count <= prev_count, "typing another letter must never INCREASE the match count"
        prev_count = count
        log("city live narrowing: prefix=%r -> %d match(es), enabled next letters (sample): %s" % (
            p, count, sorted(enabled)[:12]))
    assert "A" in idx.enabled_next_chars("SOFI"), \
        "'A' must remain enabled after typing SOFI, so the real name SOFIA can still be completed"
    assert idx.count_matches("SOFIA") >= 1, "SOFIA itself must be a real, resolvable match"
    # A letter that provably cannot continue any real match must be excluded.
    dead_letters = set("BCDGHJKMQUVWXZ") - idx.enabled_next_chars("SOFI")
    assert dead_letters, "at least some letters must be confidently disabled after 'SOFI' -- otherwise this " \
        "test isn't exercising real narrowing at all"
    log("city live narrowing: confirmed letters NOT leading to any real completion of 'SOFI' are excluded, "
        "e.g. %s" % sorted(dead_letters)[:8])

    addr = data.resolve_address("BALGARIA", "SOFIA", "", "")
    assert addr is not None and addr["matched_city"] == "SOFIA"
    REAL_SOFIA = (23.3241, 42.6977)
    assert abs(addr["lon"] - REAL_SOFIA[0]) < 0.3 and abs(addr["lat"] - REAL_SOFIA[1]) < 0.3, \
        "resolving 'SOFIA' must land near Sofia's real, already-validated coordinates (got %r)" % (
            (addr["lon"], addr["lat"]),)
    log("resolve_address('BALGARIA','SOFIA','','') -> (%.5f, %.5f) -- matches real Sofia -- PASSED" % (
        addr["lon"], addr["lat"]))

    # 8h-vi. Country field: same style of live narrowing over the small,
    # exhaustive eeu.ctr list.
    cidx = data.country_name_index
    assert cidx.count_matches("BALGARIA") == 1
    for p in ("B", "BA", "BAL"):
        en = cidx.enabled_next_chars(p)
        log("country live narrowing: prefix=%r -> %d match(es), enabled: %s" % (
            p, cidx.count_matches(p), sorted(en)))
    assert "G" in cidx.enabled_next_chars("BAL"), "'G' must be enabled after 'BAL' so BALGARIA can be completed"

    # 8h-vii. Street field: live narrowing backed by the real `.rt` trie,
    # including the documented fail-safe behavior (an INCOMPLETE walk must
    # never result in a letter being disabled) and a real CONFIDENT dead
    # end (a genuine leaf node, reached via a validated rt_root() shard,
    # where confident=True and enabled is empty).
    root_enabled, root_confident = data.street_enabled_next_chars("")
    assert root_enabled == set("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    assert root_confident is False, \
        "the empty-prefix state must be reported UNCONFIDENT (no single root covers every real starting " \
        "letter/character -- see road_index_reader.py's RT_ROOT_ENTRIES docstring) so a caller never " \
        "disables a character just for being absent from rt_root()'s own keys"
    log("street live narrowing: root state confirmed unconfident (fail-safe design) with all 26 letters enabled")

    # Walk one real, validated shard down to an actual leaf (subtree_size==1)
    # to exercise a genuine CONFIDENT dead end.
    def _find_confident_leaf(node, prefix, depth, max_depth=25):
        """Depth-first search for ANY root-to-leaf path where EVERY step's
        children walk is complete=True -- i.e. a genuinely, confidently
        dead-end prefix, not just a node whose own last hop happened to be
        clean. Trying only the first child at each step (rather than this
        full DFS) turned out NOT to reliably find one within a reasonable
        depth -- a real finding worth keeping in mind: confidently-complete
        FULL paths are less common than a single-hop check would suggest,
        consistent with the accented-node-variant gap being widespread
        rather than confined to a few isolated spots."""
        children, complete = rir.rt_children_with_confidence(data.rt_body, node)
        if not children:
            return (prefix, complete)
        if not complete or depth >= max_depth:
            return None
        for c in children:
            ch = rir.rt_char(data.rt_body, c) or "?"
            result = _find_confident_leaf(c, prefix + ch, depth + 1, max_depth)
            if result and result[1]:
                return result
        return None

    found_leaf_prefix = None
    for ch, (node_start, subtree_size) in root_entries.items():
        result = _find_confident_leaf(node_start, ch, 0)
        if result and result[1]:
            found_leaf_prefix = result[0]
            break
    assert found_leaf_prefix is not None, "expected to find at least one confident leaf among the 26 rt_root() shards"
    leaf_enabled, leaf_confident = data.street_enabled_next_chars(found_leaf_prefix)
    assert leaf_confident is True and leaf_enabled == set(), \
        "a genuine, cleanly-walked leaf node must report confident=True and an EMPTY enabled set -- every " \
        "letter should be disabled here, this is a real (not uncertain) dead end"
    log("street live narrowing: confirmed a real CONFIDENT dead end at prefix %r (every letter correctly "
        "disabled) -- PASSED" % found_leaf_prefix)

    log("Address entry (README §10 'v11 -> v12') non-GUI tests PASSED")

    # --- 8h-viii. Country -> City scoping (README §10 "v13 -> v14"): the
    #         explicit user correction that real nav UX never shows a city
    #         from the wrong country. Validates city_reader.
    #         build_country_tag_map()'s crack of eeu.cty's country_tag field
    #         directly against the real ISO -- both the raw mapping itself
    #         (many known real cities, not just Sofia) and MapData's own
    #         country-scoped PrefixNameIndex.
    assert data.country_tag_map is not None and len(data.country_tag_map) == 35, \
        "build_country_tag_map() must assign exactly one real eeu.ctr country to each of the 35 real " \
        "eeu.cty country_tag values found on the reference disc"
    assert len(set(c.index for c in data.country_tag_map.values())) == 35, \
        "the 35 tag->country assignments must be a true bijection (35 distinct countries), not several " \
        "tags piled onto one lucky nearest-centroid match"

    KNOWN_CITY_COUNTRY = [
        (220303, "TIRANË", "SHQIPËRIA"),
        (226966, "TIMISOARA", "ROMÂNIA"),
        (230704, "SOFIA", "BALGARIA"),
        (349791, "IASI", "ROMÂNIA"),
        (351905, "CHISINAU", "MOLDOVA"),
        (70926, "LJUBLJANA", "SLOVENIJA"),
        (76995, "ZAGREB", "HRVATSKA"),
        (80757, "SARAJEVO", "BOSNA I HERCEGOVINA"),
        (168764, "WIEN", "ÖSTERREICH"),
        (171155, "PRAHA", "ČESKO"),
        (182482, "BRATISLAVA", "SLOVENSKO"),
        (184320, "BUDAPEST", "MAGYARORSZÁG"),
        (220579, "PODGORICA", "CRNA GORA"),
        (221813, "SKOPJE", "P.JUGOSLOVENSKA REPUB.MAKEDONIJA"),
        (224601, "BEOGRAD", "SRBIJA"),
        (311970, "WARSZAWA", "POLSKA"),
    ]
    cty_body = data.cty_cache.body
    for rec_idx, name, expect_country in KNOWN_CITY_COUNTRY:
        rec = cr.cty_record(cty_body, rec_idx)
        assert rec.name.strip().upper() == name, \
            "sanity: record %d must still be %r on this reference disc (got %r)" % (rec_idx, name, rec.name)
        got = data.country_tag_map.get(rec.country_tag)
        assert got is not None and got.name == expect_country, \
            "known real city %r (eeu.cty record %d, country_tag=%d) must resolve to its real country %r, " \
            "got %r" % (name, rec_idx, rec.country_tag, expect_country, got.name if got else None)
    log("Country->City tag crack: %d/%d known real cities (spanning Albania/Romania/Bulgaria/Moldova/"
        "Slovenia/Croatia/Bosnia/Austria/Czechia/Slovakia/Hungary/Montenegro/North Macedonia/Serbia/Poland) "
        "correctly resolve to their real eeu.ctr country via country_tag -- including the geographically "
        "tight Kosovo/Serbia/Montenegro/North Macedonia Balkan cluster, where a wrong nearest-centroid "
        "assignment would be easy to get away with unnoticed -- PASSED" % (
            len(KNOWN_CITY_COUNTRY), len(KNOWN_CITY_COUNTRY)))

    bg_index = data.city_name_index_for_country("BALGARIA")
    al_index = data.city_name_index_for_country("SHQIPËRIA")
    assert bg_index is not None and al_index is not None
    global_count = len(data.city_name_index._sorted)
    assert len(bg_index._sorted) < global_count / 10, \
        "Bulgaria-scoped City index (%d names) must be dramatically smaller than the global %d-name index" % (
            len(bg_index._sorted), global_count)
    assert bg_index.count_matches("SOFIA") >= 1, "Bulgaria-scoped index must still find real Sofia"
    assert bg_index.count_matches("TIRAN") == 0, \
        "Bulgaria-scoped index must NOT offer Albania's Tirana -- this is the whole point of the scoping fix"
    assert al_index.count_matches("TIRAN") >= 1, "Albania-scoped index must find real Tirana"
    assert al_index.count_matches("SOFIA") == 0, \
        "Albania-scoped index must NOT offer Bulgaria's Sofia"
    assert data.resolve_country("NOT A REAL COUNTRY") is None
    assert data.city_name_index_for_country("NOT A REAL COUNTRY") is None, \
        "an unresolvable country must not silently produce SOME index (scoped or not)"
    log("MapData.city_name_index_for_country(): 'BALGARIA' scoped to %d names (vs. %d global, a %.0fx "
        "reduction) containing real SOFIA but NOT Tirana; 'SHQIPËRIA' scoped to %d names containing real "
        "TIRANË but NOT Sofia -- PASSED" % (
            len(bg_index._sorted), global_count, global_count / len(bg_index._sorted), len(al_index._sorted)))

    # --- 8h-ix. City -> Street scoping (README §10 "v13 -> v14"): a
    #         selected city's own real eeu.cty bounding box (padded), joined
    #         against real eeu.rd coordinates via the already-built RdCache
    #         -- an exact, always-correct candidate list, not the old
    #         globally-unscoped `.rt` trie walk.
    bg_rec = data.resolve_country("BALGARIA")
    al_rec = data.resolve_country("SHQIPËRIA")
    sofia_rec = data.resolve_city_record("SOFIA", country_rec=bg_rec)
    tirana_rec = data.resolve_city_record("TIRANË", country_rec=al_rec)
    assert sofia_rec is not None and sofia_rec.index == 230704
    assert tirana_rec is not None and tirana_rec.index == 220303

    sofia_streets = set(n.upper() for n in data.street_names_for_city(sofia_rec))
    tirana_streets = set(n.upper() for n in data.street_names_for_city(tirana_rec))
    assert len(sofia_streets) > 100, "a real capital city should have well over 100 distinct nearby street names"
    REAL_SOFIA_STREET = "VITOSHA"  # real, well-known Sofia street (Vitosha Boulevard)
    REAL_TIRANA_ONLY_STREET = "RAMAZAN SHIJAKU"  # real Tirana street, confirmed absent from Sofia's own list
    assert REAL_SOFIA_STREET in sofia_streets, \
        "real Sofia street %r must be found within Sofia's own (padded) bbox" % REAL_SOFIA_STREET
    assert REAL_TIRANA_ONLY_STREET in tirana_streets, \
        "sanity: %r must be a real street found within Tirana's own (padded) bbox" % REAL_TIRANA_ONLY_STREET
    assert REAL_TIRANA_ONLY_STREET not in sofia_streets, \
        "a real Tirana-only street must be correctly EXCLUDED from Sofia's scoped street set"
    assert REAL_SOFIA_STREET not in tirana_streets, \
        "a real Sofia-only street must be correctly EXCLUDED from Tirana's scoped street set"

    sofia_street_idx = data.street_name_index_for_city("SOFIA", country_rec=bg_rec)
    assert sofia_street_idx is not None
    assert sofia_street_idx.count_matches(REAL_SOFIA_STREET) >= 1
    assert sofia_street_idx.count_matches(REAL_TIRANA_ONLY_STREET) == 0
    assert data.street_name_index_for_city("A CITY THAT DOES NOT EXIST", country_rec=bg_rec) is None, \
        "an unresolvable city must not silently produce SOME street index"
    log("City->Street bbox scoping: Sofia's scoped street set (%d names) includes real street %r and "
        "correctly EXCLUDES real Tirana-only street %r (and vice versa for Tirana's own %d-name scoped "
        "set) -- PASSED" % (len(sofia_streets), REAL_SOFIA_STREET, REAL_TIRANA_ONLY_STREET, len(tirana_streets)))

    log("Country->City->Street scoping (README §10 'v13 -> v14') non-GUI tests PASSED")

    # --- 8h-x. Street's remaining `.rt`-trie fallback made EXHAUSTIVE
    #         (README §10 "v14 -> v15"): the ONLY gap the old "v13 -> v14"
    #         summary left in place -- street_name_index_for_city() returning
    #         None (unresolvable city, or a resolvable city with zero nearby
    #         `.rd` coverage) used to fall through to street_enabled_next_chars()'s
    #         real but documented-partial `.rt` trie (README §3.7: a forest
    #         of shards reaching only ~5,100 of the real leaf strings). This
    #         validates MapData.street_name_index_global directly: lazy
    #         build timing, and a concrete real street PROVEN unreachable via
    #         the old trie path but reachable via the new global index.
    assert data._street_name_index_global is None, \
        "street_name_index_global must not be built until first accessed (lazy, README §10 'v14 -> v15')"
    t0 = time.time()
    global_idx = data.street_name_index_global
    dt_build = time.time() - t0
    assert global_idx is not None and len(global_idx._sorted) > 1_000_000, \
        "the global street index must be a real, large, exhaustive index over eeu.rd's own distinct names"
    log("MapData.street_name_index_global: first access built a %d-name exhaustive PrefixNameIndex in %.2fs "
        "(one-time cost, dominated by RdCache.distinct_names()'s numpy.unique() pass over all %d eeu.rd "
        "records) -- PASSED" % (len(global_idx._sorted), dt_build, data.rd_cache.record_count))
    t0 = time.time()
    global_idx_cached = data.street_name_index_global
    dt_cached = time.time() - t0
    assert global_idx_cached is global_idx, "a second access must reuse the SAME cached index object, not rebuild"
    assert dt_cached < 0.01, "a cached re-access must be effectively instant (got %.4fs)" % dt_cached
    log("MapData.street_name_index_global: second access reused the cached object in %.4fs (vs %.2fs to build) "
        "-- confirms build-once/cache-forever, same policy as every other lazy index in this class" % (
            dt_cached, dt_build))

    # The concrete exhaustiveness proof: REAL_SOFIA_STREET ("VITOSHA",
    # already used and validated above as a real Sofia street) is directly
    # confirmed UNREACHABLE via the old `.rt`-trie prefix walk (the exact
    # function street_enabled_next_chars()/_recompute()'s old fallback
    # branch used) -- not just asserted, walked step by step -- while being
    # fully present in the new global index.
    rt_lookup = rir.rt_lookup_prefix(data.rt_body, REAL_SOFIA_STREET, rir.rt_root())
    rt_reachable = rt_lookup["matched"] == len(REAL_SOFIA_STREET) and rt_lookup["node"] is not None
    assert not rt_reachable, \
        "sanity/regression guard: %r is expected to be a real, documented case the OLD `.rt` trie cannot " \
        "fully spell (matched only %d/%d characters) -- if this now passes, `.rt`'s coverage changed and " \
        "this test's own exhaustiveness claim should be re-checked" % (
            REAL_SOFIA_STREET, rt_lookup["matched"], len(REAL_SOFIA_STREET))
    assert global_idx.count_matches(REAL_SOFIA_STREET) >= 1, \
        "the new global index must find the real street the old trie cannot reach"
    log("Exhaustiveness PROVEN, not assumed: real street %r is confirmed UNREACHABLE via the OLD `.rt`-trie "
        "prefix walk (rt_lookup_prefix matched only %d of %d characters before failing) but IS found in the "
        "NEW global PrefixNameIndex (%d match(es)) -- this is exactly the gap README §10 'v14 -> v15' closes" % (
            REAL_SOFIA_STREET, rt_lookup["matched"], len(REAL_SOFIA_STREET),
            global_idx.count_matches(REAL_SOFIA_STREET)))

    # _backing_index()'s actual wiring, at the MapData level: a nonsense
    # city name must make street_name_index_for_city() return None, and
    # _backing_index()'s "or data.street_name_index_global" must then take
    # over -- reproduced here directly via the same two calls
    # SpellerDialog._backing_index() itself makes (the GUI section below
    # re-drives this through the real widgets, this checks the underlying
    # data contract in isolation first).
    NONSENSE_CITY = "ZZZQQXNOTAREALCITY999"
    assert data.street_name_index_for_city(NONSENSE_CITY, country_rec=bg_rec) is None, \
        "sanity: this nonsense city text must not resolve to any real eeu.cty record"
    fallback_idx = data.street_name_index_for_city(NONSENSE_CITY, country_rec=bg_rec) or data.street_name_index_global
    assert fallback_idx is global_idx, \
        "the 'or street_name_index_global' fallback must kick in for an unresolvable city, exactly mirroring " \
        "the already-established 'or city_name_index' pattern used for City"
    assert fallback_idx.count_matches(REAL_SOFIA_STREET) >= 1
    log("Fallback wiring confirmed at the MapData level: an unresolvable city name (%r) makes "
        "street_name_index_for_city() return None, and 'or street_name_index_global' correctly takes over, "
        "still finding real street %r -- PASSED" % (NONSENSE_CITY, REAL_SOFIA_STREET))

    log("Street exhaustive-fallback (README §10 'v14 -> v15') non-GUI tests PASSED")

    log("MapData tests PASSED")

    # --- 9. GUI smoke test: build the widget tree AND actually drive
    #        App._redraw() with real loaded data, then inspect what
    #        landed on the canvas (not just "didn't crash") -----------
    import tkinter as tk
    from tkinter import ttk
    root = tk.Tk()
    try:
        app = viewer.App(root)
        root.update_idletasks()
        log("App widget tree constructed OK (title=%r)" % root.title())

        # "Hide decode garbage" checkbox REMOVAL check (later session, user
        # request: "remove the hide decode garbage mechanism, i keep it
        # always off because it doesnt help" -- the oscillation filter had
        # already been found net-negative for real dense-urban rendering,
        # see MapData.trim_oscillation's own comment for the concrete
        # Sofia-area evidence). Confirms a fresh App genuinely has no
        # checkbox/handler left for it -- a real regression test against
        # accidentally re-adding UI for a mechanism confirmed unhelpful.
        assert not hasattr(app, "hide_garbage_var") and not hasattr(app, "hide_garbage_cb") \
            and not hasattr(app, "_on_hide_garbage_changed"), \
            "the removed 'Hide decode garbage' checkbox/handler must not reappear on a fresh App"
        log("Confirmed: fresh App has no 'Hide decode garbage' checkbox/handler (removed, MapData.trim_oscillation "
            "remains a programmatic-only API)")

        # No layer dropdown/choice anywhere in the widget tree -- the
        # explicit ask this session was "I don't need to choose a layer".
        def all_widgets(w):
            yield w
            for c in w.winfo_children():
                yield from all_widgets(c)
        combo_texts = [str(w) for w in all_widgets(root) if isinstance(w, ttk.Combobox)]
        assert not combo_texts, "a layer dropdown/Combobox is still present in the UI: %s" % combo_texts
        assert not hasattr(app, "layer_var"), "App must not keep a user-facing layer selection variable"
        log("Confirmed: no layer dropdown/Combobox anywhere in the widget tree")

        app.data = data
        app.center_lon, app.center_lat = tirana.lon, tirana.lat
        app.pan_x = app.pan_y = 0.0
        # mp0 is already ready by this point (loaded in section 8b) --
        # FULL_FAST_SCALE pools all 5 layers here, reproducing the same
        # "street-level, everything pooled" scenario this GUI check has
        # always exercised (README §10 "v4 -> v5"'s 59,663-oval Tirana data
        # point), just reached via an explicit scale now instead of it being
        # the only possible behavior.
        area = data.ensure_area_loaded(
            tirana.lon - 0.15, tirana.lon + 0.15, tirana.lat - 0.15, tirana.lat + 0.15, FULL_FAST_SCALE)
        app.features = area["features"]
        # NOTE: root.update_idletasks() alone does NOT realize real window
        # geometry (winfo_width()/height() stay at Tk's 1x1 stub without an
        # actual mainloop) -- root.update() does. This matters here only
        # because this test drives the canvas without ever calling
        # mainloop(); the real app (run via `py rns510_map_viewer.py`)
        # always has a live, mapped window by the time a user can click
        # Search, so it never sees this stub size.
        app.canvas.config(width=1100, height=700)
        root.update()
        app.scale = app._initial_scale(app.features, 0.15)
        app._redraw()
        root.update()

        lines = app.canvas.find_withtag("all")
        texts = [i for i in lines if app.canvas.type(i) == "text"]
        text_values = [app.canvas.itemcget(i, "text") for i in texts]
        images = [i for i in lines if app.canvas.type(i) == "image"]
        n_ovals = sum(1 for i in lines if app.canvas.type(i) == "oval")
        log("_redraw() near Tirana produced %d canvas items: %d text label(s), %d image(s), %d oval(s)" % (
            len(lines), len(texts), len(images), n_ovals))
        log("label text drawn: %s" % text_values)
        # README §10 "v17 -> v18" rendering rework: every road point/edge is
        # now rasterized into ONE PIL image, shown as exactly ONE
        # canvas.create_image() item -- replacing what used to be tens of
        # thousands of individual canvas.create_oval()/create_line() items
        # (root cause of the real "Not Responding"/~4GB-memory unresponsive-
        # ness bug this rework fixes). The only REAL canvas ovals left are
        # the center/search marker's own two (an outer halo ring + a filled
        # circle -- see _redraw()'s "Center/search marker" block); no more
        # per-point ovals at all.
        assert len(images) == 1, \
            "expected exactly ONE rasterized bitmap canvas.create_image() item, got %d" % len(images)
        assert n_ovals == 2, \
            "expected exactly 2 real canvas ovals (the center/search marker only -- road-point dots are now " \
            "rasterized pixels, not real canvas items), got %d" % n_ovals
        assert any("TIRAN" in t.upper() for t in text_values), \
            "expected a real 'Tirana'-ish text label actually drawn on the canvas, not just decoded data"
        log("canvas actually renders real road+city labels near Tirana -- PASSED")

        # --- Dot color check (README §10 "v16 -> v17", re-verified against
        #     the rasterized bitmap as of "v17 -> v18"): every road-point dot
        #     must be rasterized in the new red DOT_COLOR, not the old gray/
        #     gold ROAD_COLOR_MAJOR/MINOR/UNNAMED shades. User's verbatim
        #     request: "make the points red dots not gray ones". Momentarily
        #     turn OFF connected-roads mode so every point's own projected
        #     pixel can only ever be a DOT (never overwritten by some OTHER
        #     feature's LINE landing on the exact same rasterized pixel --
        #     a real, new possible interaction once dots and lines share one
        #     bitmap instead of being independent, non-overwriting canvas
        #     items) -- isolates this check to exactly what the old
        #     per-oval-fill check proved, restored right after.
        assert app._current_image is not None, "expected _redraw() to keep the rasterized image on self._current_image"
        was_connected_dotcheck = app.connected_roads_var.get()
        app.connected_roads_var.set(False)
        app._redraw()
        root.update()
        img_dots_only = app._current_image
        sample_pts = []
        for f in app.features:
            for lon, lat in f["points"]:
                cx, cy = app._to_canvas(lon, lat)
                if 0 <= cx < 1100 and 0 <= cy < 700:
                    sample_pts.append((cx, cy))
            if len(sample_pts) >= 300:
                break
        assert sample_pts, "expected at least one on-screen real road point to sample"
        mismatches = [(x, y, _pixel_at(img_dots_only, x, y)) for (x, y) in sample_pts
                      if not _color_matches(_pixel_at(img_dots_only, x, y), viewer.DOT_COLOR)]
        assert not mismatches, \
            "every real road-point pixel must be rasterized in DOT_COLOR (%s) with connected-roads off -- " \
            "found %d mismatch(es), e.g. %r" % (viewer.DOT_COLOR, len(mismatches), mismatches[:3])
        old_gray_shades = {viewer.ROAD_COLOR_MAJOR.lower(), viewer.ROAD_COLOR_MINOR.lower(),
                            viewer.ROAD_COLOR_UNNAMED.lower()}
        assert viewer.DOT_COLOR.lower() not in old_gray_shades, \
            "DOT_COLOR must not coincidentally equal one of the old gray/gold road-line colors"
        dr, dg, db = _hex_to_rgb(viewer.DOT_COLOR)
        assert dr > 150 and dg < 100 and db < 100 and abs(dg - db) < 40, \
            "DOT_COLOR must read as unambiguously RED (high R, low+balanced G/B), not orange/pink: %s" % (
                viewer.DOT_COLOR,)
        log("confirmed: all %d sampled real road points are rasterized in red DOT_COLOR (%s) at their exact "
            "projected pixel, not gray/gold -- PASSED" % (len(sample_pts), viewer.DOT_COLOR))
        app.connected_roads_var.set(was_connected_dotcheck)
        app._redraw()
        root.update()

        # --- Connected-roads ground-truth RASTERIZED-IMAGE rendering check
        #     (README §10 "v9 -> v10", re-verified against the bitmap
        #     rasterization as of "v17 -> v18"). Section 8d above already
        #     proved resolve_topology_adjacency() (via MapData.decode_tile(
        #     ..., want_adjacency=True)) recovers the right edges for BOTH
        #     human-verified ground-truth tiles (mg2 tile_id 20597, 16/16
        #     edges; mp0 tile_id 91124, 16/18 edges) -- that only proves the
        #     DATA is right. This block proves the RUNNING APP actually
        #     RASTERIZES those edges/points as real colored pixels at the
        #     correct location (not just that _redraw() runs without
        #     crashing), by rendering each ground-truth feature ALONE (so
        #     every non-background pixel on the bitmap can only have come
        #     from it) and sampling `App._current_image` (the raw PIL.Image
        #     _redraw() keeps for exactly this purpose) at the exact pixel
        #     position App._to_canvas() computes for each real point, and at
        #     the midpoint for each expected edge's two endpoints. Reuses
        #     mg2_feat/mg2_result/MG2_EDGE_SEQUENCE and mp0_feat/mp0_result/
        #     MP0_POINT_SEQUENCE from section 8d above (same `data` instance
        #     -- those tiles were already decoded with want_adjacency=True
        #     there, so app.data.topo_caches already has real cached results
        #     for them; app.data is `data` itself, see above).
        saved_center = (app.center_lon, app.center_lat)
        saved_pan = (app.pan_x, app.pan_y)
        saved_scale = app.scale
        saved_features = app.features

        def _check_ground_truth_canvas_lines(feat, result, point_sequence, label):
            assert app.connected_roads_var.get(), \
                "'Draw connected roads' must be CHECKED (the default) for this check to be meaningful"
            pts = feat["points"]
            lons = [p[0] for p in pts]
            lats = [p[1] for p in pts]
            app.center_lon = (min(lons) + max(lons)) / 2.0
            app.center_lat = (min(lats) + max(lats)) / 2.0
            app.pan_x = app.pan_y = 0.0
            cos_lat = math.cos(math.radians(app.center_lat)) or 1e-9
            span_lon = max(max(lons) - min(lons), 1e-6) * cos_lat
            span_lat = max(max(lats) - min(lats), 1e-6)
            app.scale = 0.4 * min(1100, 700) / max(span_lon, span_lat)
            # Render ONLY this one feature -- isolates every non-background
            # rasterized pixel as necessarily coming from ITS resolved
            # adjacency/points, so a pixel-sample check is already meaningful
            # on its own, not just the endpoint-matching below.
            app.features = [feat]
            app._redraw()
            root.update()

            # README §10 "v17 -> v18": exactly ONE rasterized image item now
            # (plus the 2 real center-marker ovals) -- no more one canvas
            # line/oval per edge/point.
            images = [i for i in app.canvas.find_withtag("all") if app.canvas.type(i) == "image"]
            n_ovals_present = sum(1 for i in app.canvas.find_withtag("all") if app.canvas.type(i) == "oval")
            assert len(images) == 1, "%s: expected exactly one rasterized image item, got %d" % (label, len(images))
            assert n_ovals_present == 2, \
                "%s: expected exactly 2 real ovals (center marker only -- points/lines are rasterized, not " \
                "real canvas items), got %d" % (label, n_ovals_present)
            img = app._current_image
            assert img is not None, "%s: expected _redraw() to keep the rasterized image on self._current_image" % label

            # Every real point of this feature must be rasterized as a
            # DOT_COLOR pixel at its exact projected canvas coordinate --
            # README §10 "v16 -> v17" requires a dot for EVERY point even
            # when lines are ALSO drawn for a high-confidence feature, and
            # rendering this feature ALONE means no other feature's line/dot
            # can land on the same pixel, so this is precise, not statistical.
            n_pts_checked = 0
            for lon, lat in pts:
                px, py = app._to_canvas(lon, lat)
                if 0 <= px < 1100 and 0 <= py < 700:
                    assert _color_matches(_pixel_at(img, px, py), viewer.DOT_COLOR), \
                        "%s: expected a red DOT_COLOR pixel at real point (%.6f, %.6f) -> canvas (%.1f, %.1f)" % (
                            label, lon, lat, px, py)
                    n_pts_checked += 1
            assert n_pts_checked > 0, "%s: expected at least one on-screen point to sample" % label
            log("%s: confirmed all %d/%d on-screen real points rasterized as DOT_COLOR pixels at their exact "
                "projected coordinates" % (label, n_pts_checked, len(pts)))

            # Every edge in the FULL resolved adjacency graph (not just the
            # human-verified subset below) SHOULD rasterize as a real line
            # pixel near its midpoint, in the correct color (ROAD_COLOR_MAJOR
            # for a named run, ROAD_COLOR_UNNAMED otherwise) -- the direct
            # rasterized-pixel equivalent of the old canvas.coords() endpoint
            # check. Unlike that old check (a plain per-item COUNT, with no
            # geometric verification at all), this one actually samples real
            # pixels -- but at this feature's dense whole-view framing (200+
            # points across a small on-screen area, by design so the WHOLE
            # feature fits at once) some edges' own midpoints can legitimately
            # land under a DIFFERENT, unrelated point's own dot (drawn after
            # all lines, same as _redraw() draws it) -- an occlusion, not a
            # missing edge -- so this is reported/spot-checked, not a hard
            # 100% requirement; the STRICT, unoccluded requirement is the
            # curated human-verified subset below (picked in "v9 -> v10"
            # specifically to be unambiguous), same as the original test.
            n_edges_on_screen = 0
            n_edges_confirmed = 0
            for a, b in result["edges"]:
                if a >= len(pts) or b >= len(pts):
                    continue
                ax, ay = app._to_canvas(*pts[a])
                bx, by = app._to_canvas(*pts[b])
                mx, my = (ax + bx) / 2.0, (ay + by) / 2.0
                if not (0 <= mx < 1100 and 0 <= my < 700):
                    continue
                n_edges_on_screen += 1
                edge_name = viewer._name_at_point(feat.get("named_ranges"), a) or \
                    viewer._name_at_point(feat.get("named_ranges"), b)
                expected_color = viewer.ROAD_COLOR_MAJOR if edge_name else viewer.ROAD_COLOR_UNNAMED
                if _color_near(img, mx, my, expected_color) or _color_near(img, mx, my, viewer.DOT_COLOR):
                    n_edges_confirmed += 1
            assert n_edges_on_screen == 0 or n_edges_confirmed > 0, \
                "%s: expected AT LEAST SOME on-screen resolved-graph edges (%d) rasterized as real pixels near " \
                "their midpoint, got 0" % (label, n_edges_on_screen)
            log("%s: confirmed %d/%d on-screen resolved edges rasterized as real pixels near their midpoint " \
                "(some near-misses are expected at this dense whole-feature zoom, when an edge's own midpoint " \
                "happens to land under an unrelated point's dot -- see the strict, unoccluded human-verified " \
                "check right below) -- %d total edges in the graph" % (
                    label, n_edges_confirmed, n_edges_on_screen, len(result["edges"])))

            # Now confirm the specific HUMAN-VERIFIED ground-truth edges
            # (point_sequence) -- same "confirmed" semantics/return value the
            # old canvas.coords()-based check had, backed by real pixel
            # sampling of the rasterized bitmap.
            #
            # README §10 "v17 -> v18", a real, honestly-found limitation of
            # bitmap rasterization vs. the old vector canvas items: at the
            # whole-feature framing used above, many real edges here are only
            # 1-2 SCREEN PIXELS long (this tile's 200+ points packed densely
            # into a small on-screen area) -- entirely covered by their own
            # two endpoint dots once rasterized (dots are drawn ON TOP of
            # lines, same z-order _redraw() always used). A real
            # canvas.create_line() item's coords() stayed independently
            # queryable no matter what visually overlapped it; a rasterized
            # PIXEL does not carry that information once painted over. This
            # is a genuine visual characteristic of the new rendering (a
            # human eye would ALSO not see that tiny line segment, hidden
            # under its own two dots), not a test artifact -- so, exactly
            # like the edge-click-to-identify test further below (which hit
            # this identical real framing issue first), each curated edge is
            # re-framed TIGHTLY on just its own two endpoints (pushing every
            # OTHER point/dot far outside this view) before sampling its
            # midpoint, which is exactly how a user would actually inspect
            # one specific edge in practice (zoom in on it).
            expected_edges = {tuple(sorted((point_sequence[i], point_sequence[i + 1])))
                               for i in range(len(point_sequence) - 1)}
            confirmed = 0
            for a, b in expected_edges:
                if a >= len(pts) or b >= len(pts):
                    continue
                lon_a, lat_a = pts[a]
                lon_b, lat_b = pts[b]
                app.center_lon = (lon_a + lon_b) / 2.0
                app.center_lat = (lat_a + lat_b) / 2.0
                app.pan_x = app.pan_y = 0.0
                cos_lat_e = math.cos(math.radians(app.center_lat)) or 1e-9
                span_lon_e = max(abs(lon_a - lon_b), 1e-7) * cos_lat_e
                span_lat_e = max(abs(lat_a - lat_b), 1e-7)
                app.scale = 0.35 * min(1100, 700) / max(span_lon_e, span_lat_e)
                app._redraw()
                root.update()
                img_e = app._current_image
                ax, ay = app._to_canvas(lon_a, lat_a)
                bx, by = app._to_canvas(lon_b, lat_b)
                mx, my = (ax + bx) / 2.0, (ay + by) / 2.0
                if not (0 <= mx < 1100 and 0 <= my < 700):
                    continue
                edge_name = viewer._name_at_point(feat.get("named_ranges"), a) or \
                    viewer._name_at_point(feat.get("named_ranges"), b)
                expected_color = viewer.ROAD_COLOR_MAJOR if edge_name else viewer.ROAD_COLOR_UNNAMED
                if _color_near(img_e, mx, my, expected_color, radius=2):
                    confirmed += 1
            log("%s: %d/%d human-verified ground-truth edges confirmed rasterized as real line pixels at the " \
                "correct midpoint/color (each re-framed tightly on its own two endpoints)" % (
                    label, confirmed, len(expected_edges)))
            return confirmed

        MG2_EDGE_SEQUENCE = [202, 190, 189, 185, 186, 188, 191, 192, 193, 195, 197, 199, 201, 200, 198, 196, 194]
        mg2_confirmed = _check_ground_truth_canvas_lines(mg2_feat, mg2_result, MG2_EDGE_SEQUENCE, "mg2 tile 20597")
        assert mg2_confirmed == 16, \
            "expected all 16/16 confirmed real mg2 ground-truth edges rasterized as real line pixels (got %d)" % mg2_confirmed

        mp0_confirmed = _check_ground_truth_canvas_lines(mp0_feat, mp0_result, MP0_POINT_SEQUENCE, "mp0 tile 91124")
        assert mp0_confirmed >= 16, \
            "expected at least 16/18 confirmed real mp0 ground-truth edges rasterized as real line pixels (got %d)" % mp0_confirmed

        log("Connected-roads ground-truth RASTERIZED-IMAGE rendering check PASSED for BOTH tiles (real pixel "
            "colors sampled from App._current_image at exact correct locations, confirmed -- not just that the " \
            "underlying adjacency data is right)")

        # Plain event stand-in used by every simulated click below (both this
        # edge-click block and the point click-to-identify block further
        # down, which defines its own identical local `class FakeEvent` --
        # harmless redefinition, same name, same shape).
        class FakeEvent:
            pass

        # --- Edge click-to-identify (README §10 "v16 -> v17"): right-
        #     clicking ON (near) a rendered connected-road LINE must
        #     identify which two points that specific edge connects, adding
        #     BOTH as linked picks -- reusing the SAME human-verified
        #     ground-truth tile (mg2 tile_id 20597, from section 8d/above)
        #     for the same rigor as the existing point click-to-identify
        #     test. Render just this one feature again (so every line on
        #     screen is necessarily one of its own resolved edges), pick a
        #     KNOWN real, human-verified resolved edge (one of the 16/16
        #     confirmed real edges from MG2_EDGE_SEQUENCE, not just any
        #     resolved-graph edge), compute the EXACT canvas midpoint of its
        #     two endpoints, simulate a real <Button-3> click there, and
        #     confirm BOTH endpoints are identified with the correct
        #     layer/tile_id/feature_index/point_index/lon/lat, plus the
        #     edge_partner linkage.
        #
        #     Framing: zoom in TIGHTLY on just this one edge's own two
        #     endpoints (not the whole 203-point feature, unlike the
        #     ground-truth line-rendering check above) -- a real finding
        #     while writing this test: at the whole-feature framing, this
        #     tile's 203 points are packed only ~1-2 screen pixels apart, so
        #     an edge's own midpoint often lands within POINT_PICK_RADIUS_PX
        #     of some OTHER nearby point (not a bug -- find_nearest_point()
        #     correctly finds A point within radius, just not necessarily
        #     the edge's own endpoint), which resolves as an ordinary
        #     single-point pick and never reaches the edge fallback at all.
        #     Framing tightly on the target edge's own two points instead
        #     (picked as the human-verified edge with the largest real-
        #     world span, for a comfortable margin) pushes every other real
        #     point's projected screen position far outside the pick
        #     radius, so the midpoint click can only plausibly hit this one
        #     edge -- exactly the "click a specific line to debug it"
        #     real-world usage this feature is built for.
        app.on_clear_points()
        pts_mg2 = mg2_feat["points"]
        mg2_expected_edges_ct = {tuple(sorted((MG2_EDGE_SEQUENCE[i], MG2_EDGE_SEQUENCE[i + 1])))
                                  for i in range(len(MG2_EDGE_SEQUENCE) - 1)}
        confirmed_edges_ct = sorted(mg2_expected_edges_ct & set(mg2_result["edges"]))
        assert confirmed_edges_ct, "expected at least one human-verified edge in the resolved graph"

        def _edge_span_deg(e):
            ia, ib = e
            lon_a, lat_a = pts_mg2[ia]
            lon_b, lat_b = pts_mg2[ib]
            return abs(lon_a - lon_b) + abs(lat_a - lat_b)

        a_idx, b_idx = max(confirmed_edges_ct, key=_edge_span_deg)
        lon_a, lat_a = pts_mg2[a_idx]
        lon_b, lat_b = pts_mg2[b_idx]
        app.center_lon = (lon_a + lon_b) / 2.0
        app.center_lat = (lat_a + lat_b) / 2.0
        app.pan_x = app.pan_y = 0.0
        cos_lat_mg2 = math.cos(math.radians(app.center_lat)) or 1e-9
        span_lon_mg2 = max(abs(lon_a - lon_b), 1e-7) * cos_lat_mg2
        span_lat_mg2 = max(abs(lat_a - lat_b), 1e-7)
        app.scale = 0.35 * min(1100, 700) / max(span_lon_mg2, span_lat_mg2)
        app.connected_roads_var.set(True)
        app.features = [mg2_feat]
        app._redraw()
        root.update()

        ax_mg2, ay_mg2 = app._to_canvas(*pts_mg2[a_idx])
        bx_mg2, by_mg2 = app._to_canvas(*pts_mg2[b_idx])
        mid_ev = FakeEvent()
        mid_ev.x, mid_ev.y = (ax_mg2 + bx_mg2) / 2.0, (ay_mg2 + by_mg2) / 2.0
        picks_before_edge = len(app.picked_points)
        app._on_point_pick(mid_ev)
        assert len(app.picked_points) == picks_before_edge + 2, \
            "right-clicking the midpoint of a real rendered edge must add exactly TWO new picks (both endpoints)"
        pick_a, pick_b = app.picked_points[-2], app.picked_points[-1]
        picked_indices = {pick_a["point_index"], pick_b["point_index"]}
        log("edge click-to-identify: clicked midpoint of real edge (points %d<->%d) -> picked point_index=%s" % (
            a_idx, b_idx, picked_indices))
        assert picked_indices == {a_idx, b_idx}, \
            "edge click must identify EXACTLY the two real endpoint point_index values of the clicked edge " \
            "(expected {%d, %d}, got %s)" % (a_idx, b_idx, picked_indices)
        picked_by_idx = {pick_a["point_index"]: pick_a, pick_b["point_index"]: pick_b}
        for expected_idx in (a_idx, b_idx):
            p = picked_by_idx[expected_idx]
            exp_lon, exp_lat = pts_mg2[expected_idx]
            assert abs(p["lon"] - exp_lon) < 1e-6 and abs(p["lat"] - exp_lat) < 1e-6, \
                "picked edge endpoint (lon, lat) must match the real decoded point exactly"
            assert p["layer"] == "mg2" and p["tile_id"] == MG2_TILE_ID and \
                p["feature_index"] == mg2_feat["feature_index"], \
                "picked edge endpoint must carry the correct real layer/tile_id/feature_index"
        assert pick_a.get("edge_partner") == pick_b["number"] and pick_b.get("edge_partner") == pick_a["number"], \
            "both picks from an edge click must record each other as their edge_partner -- so it's " \
            "unambiguous these two points came from clicking a specific edge, not two independent clicks"
        panel_text_edge = app.points_text.get("1.0", "end")
        assert "edge pick" in panel_text_edge.lower() and "edge<->#" in panel_text_edge, \
            "the picked-points panel must clearly indicate an edge-click pair (divider line + inline tag), " \
            "not just two anonymous rows"
        log("edge click-to-identify: midpoint click on a KNOWN real mg2 tile %d edge (points %d<->%d) correctly "
            "identified BOTH endpoints, marked as edge-linked in the panel -- PASSED" % (MG2_TILE_ID, a_idx, b_idx))

        # A click that lands on neither a point nor a rendered edge (with
        # connected-roads mode on) must still be a harmless miss.
        far_ev_edge = FakeEvent()
        far_ev_edge.x, far_ev_edge.y = -900, -900
        picks_before_edge_miss = len(app.picked_points)
        app._on_point_pick(far_ev_edge)
        assert len(app.picked_points) == picks_before_edge_miss, \
            "a click far from every rendered point AND every rendered edge must add nothing"
        log("edge-click miss case (empty space, connected-roads on) correctly added nothing -- PASSED")

        app.on_clear_points()
        app.connected_roads_var.set(True)

        # --- Toggle OFF: must reproduce the exact pre-existing dot-only
        #     rendering for the SAME feature (zero rasterized line pixels,
        #     real per-vertex dot pixels instead) even though a high-
        #     confidence adjacency result is already cached for it -- proves
        #     the checkbox is a clean, fully reversible rendering-only
        #     toggle, not a data-affecting one. README §10 "v17 -> v18": no
        #     more real per-item canvas ovals/lines to count -- sample the
        #     rasterized image instead: zero ROAD_COLOR_MAJOR/UNNAMED line
        #     pixels, and a DOT_COLOR pixel at every real point.
        # Explicitly re-frame on mg2_feat's own WHOLE bbox (same formula
        # _check_ground_truth_canvas_lines used) rather than relying on
        # whatever center/scale the edge-click-to-identify test above left
        # behind (a tight zoom on ONE specific edge) -- this section needs
        # every one of the feature's real points verifiably on-screen to
        # sample, not just the two near a leftover pick.
        mg2_lons = [p[0] for p in mg2_feat["points"]]
        mg2_lats = [p[1] for p in mg2_feat["points"]]
        app.center_lon = (min(mg2_lons) + max(mg2_lons)) / 2.0
        app.center_lat = (min(mg2_lats) + max(mg2_lats)) / 2.0
        app.pan_x = app.pan_y = 0.0
        cos_lat_off = math.cos(math.radians(app.center_lat)) or 1e-9
        span_lon_off = max(max(mg2_lons) - min(mg2_lons), 1e-6) * cos_lat_off
        span_lat_off = max(max(mg2_lats) - min(mg2_lats), 1e-6)
        app.scale = 0.4 * min(1100, 700) / max(span_lon_off, span_lat_off)
        app.connected_roads_var.set(False)
        app.features = [mg2_feat]
        app._redraw()
        root.update()
        images_off = [i for i in app.canvas.find_withtag("all") if app.canvas.type(i) == "image"]
        n_ovals_off = sum(1 for i in app.canvas.find_withtag("all") if app.canvas.type(i) == "oval")
        assert len(images_off) == 1, "expected exactly one rasterized image item with connected-roads off"
        assert n_ovals_off == 2, \
            "expected exactly 2 real canvas ovals (center marker only) with connected-roads off, got %d" % n_ovals_off
        img_off = app._current_image
        n_line_px_off = (_count_color_pixels(img_off, viewer.ROAD_COLOR_MAJOR) +
                         _count_color_pixels(img_off, viewer.ROAD_COLOR_UNNAMED))
        assert n_line_px_off == 0, \
            "unchecking 'Draw connected roads' must rasterize zero line-colored pixels (found %d)" % n_line_px_off
        n_dot_px_off = 0
        for lon, lat in mg2_feat["points"]:
            px, py = app._to_canvas(lon, lat)
            if 0 <= px < 1100 and 0 <= py < 700:
                assert _color_matches(_pixel_at(img_off, px, py), viewer.DOT_COLOR), \
                    "unchecking 'Draw connected roads' must still rasterize a DOT_COLOR pixel at every real point"
                n_dot_px_off += 1
        assert n_dot_px_off >= 1, "expected at least one on-screen point to sample with connected-roads off"
        log("connected-roads checkbox OFF reproduces exact dot-only rasterization (%d points sampled, 0 line " \
            "pixels) for the same feature that rasterized %d resolved edges when checked -- toggle confirmed " \
            "fully reversible" % (n_dot_px_off, len(mg2_result["edges"])))
        app.connected_roads_var.set(True)

        # Restore the Tirana-area view state for the click-to-identify tests
        # that follow, which expect app.features/center/scale to still be
        # the live Tirana-area load from earlier in this GUI section.
        app.center_lon, app.center_lat = saved_center
        app.pan_x, app.pan_y = saved_pan
        app.scale = saved_scale
        app.features = saved_features
        app._redraw()
        root.update()

        # --- Click-to-identify, end to end against real decoded/named data
        #     (README §10 "v6 -> v7"): pick a KNOWN real point (the first
        #     vertex of the first named feature in the currently-loaded
        #     Tirana-area `app.features`) by computing the EXACT canvas (x,y)
        #     that point projects to (via the same project_point()+centering
        #     math _to_canvas() uses), simulating a real <Button-3> event at
        #     that pixel, and checking App._on_point_pick()'s result against
        #     the feature dict's own real layer/tile_id/feature_index/
        #     point_index/lon/lat/name -- not just that SOME pick occurred.
        assert app.features, "expected at least one real decoded feature near Tirana to test picking against"
        # Pick a coordinate that is PROVABLY UNIQUE across the whole pooled
        # `app.features` set (all 5 layers, since mp0 already finished
        # loading by this point in the test) before using it as the pick
        # target -- coarser and finer generalization levels of the SAME
        # real road legitimately share exact anchor/shape points (that's
        # the whole point of v4->v5's multi-layer pooling), so a coordinate
        # that happens to be duplicated across layers would make
        # find_nearest_point()'s result depend on pooling order, not a bug
        # in the picker. A point known to be unique removes that ambiguity
        # so this test can assert an exact layer/tile/feature/point match.
        from collections import Counter
        coord_counts = Counter()
        for f in app.features:
            for lon, lat in f["points"]:
                coord_counts[(round(lon, 6), round(lat, 6))] += 1
        target_feat = target_pt_idx = None
        for f in app.features:
            if f.get("layer") is None:
                continue
            for idx, (lon, lat) in enumerate(f["points"]):
                if coord_counts[(round(lon, 6), round(lat, 6))] != 1:
                    continue
                # Also require it to be on-screen at the current view, same
                # requirement the old fixed-index-0 target needed -- picked
                # here rather than asserted separately so an off-screen
                # unique point doesn't abort the whole check.
                tpx, tpy = app._to_canvas(lon, lat)
                if 0 <= tpx <= 1100 and 0 <= tpy <= 700:
                    target_feat, target_pt_idx = f, idx
                    break
            if target_feat is not None:
                break
        assert target_feat is not None, \
            "expected at least one on-screen decoded point with a coordinate unique across the whole pooled " \
            "feature set"
        target_lon, target_lat = target_feat["points"][target_pt_idx]
        expected_name = None
        for start, end, nm in target_feat.get("named_ranges") or ():
            if start <= target_pt_idx <= end:
                expected_name = nm
                break
        log("click-to-identify target: layer=%s tile_id=%s feature_index=%s point_index=%d (%.6f, %.6f) name=%r" % (
            target_feat.get("layer"), target_feat.get("tile_id"), target_feat.get("feature_index"),
            target_pt_idx, target_lon, target_lat, expected_name))
        # Every decode_tile()-produced feature must carry these tags now --
        # confirms MapData.decode_tile()'s tagging (not just the pure
        # find_nearest_point() logic tested in section 1c) actually ran on
        # real ISO data.
        assert target_feat.get("layer") in viewer.ALL_LAYERS, "real decoded feature missing a valid 'layer' tag"
        assert target_feat.get("tile_id") is not None, "real decoded feature missing a 'tile_id' tag"
        assert target_feat.get("tile_offset") is not None and target_feat.get("tile_declen") is not None, \
            "real decoded feature missing tile_offset/tile_declen tags"
        assert target_feat.get("feature_index") is not None, "real decoded feature missing a 'feature_index' tag"

        px, py = app._to_canvas(target_lon, target_lat)
        assert 0 <= px <= 1100 and 0 <= py <= 700, \
            "test setup check: the target point must actually be on-screen at the current view"

        class FakeEvent:
            pass

        ev = FakeEvent()
        ev.x, ev.y = px, py
        picks_before = len(app.picked_points)
        app._on_point_pick(ev)
        assert len(app.picked_points) == picks_before + 1, \
            "a right-click exactly on a real rendered point must add exactly one new pick"
        picked = app.picked_points[-1]
        log("click-to-identify result: %r" % picked)
        assert picked["number"] == 1, "first pick this session must be numbered #1"
        assert picked["layer"] == target_feat["layer"]
        assert picked["tile_id"] == target_feat["tile_id"]
        assert picked["tile_offset"] == target_feat["tile_offset"]
        assert picked["tile_declen"] == target_feat["tile_declen"]
        assert picked["feature_index"] == target_feat["feature_index"]
        assert picked["point_index"] == target_pt_idx
        assert abs(picked["lon"] - target_lon) < 1e-6 and abs(picked["lat"] - target_lat) < 1e-6, \
            "picked (lon, lat) must match the real decoded point to within float tolerance"
        assert picked["name"] == expected_name, "picked name must match road_naming's own named_ranges result"

        panel_text = app.points_text.get("1.0", "end")
        assert "#" in panel_text and "1  |" in panel_text, \
            "the picked-points text panel must contain a row for pick #1"
        assert (target_feat["layer"] or "") in panel_text and str(target_feat["tile_id"]) in panel_text, \
            "the picked-points panel row must show the real layer/tile_id, readable/copyable as plain text"
        if expected_name:
            assert expected_name in panel_text, "the picked-points panel row must show the real matched name"
        log("real click-to-identify: known point correctly identified end to end, panel row confirmed -- PASSED")

        # --- Connecting line + undo-last-point (README §10 "v7 -> v8") ----
        # Find a SECOND on-screen point with a coordinate unique across the
        # whole pooled feature set (same reasoning as the first target
        # above), pick it, and confirm: (a) a dashed connecting line now
        # exists on the canvas (none did with only one pick), (b)
        # on_undo_last_point() removes exactly the second pick (not the
        # first), restores the pick count/panel/line to their one-pick
        # state, and rewinds the running counter so the NEXT pick reuses
        # the undone point's number rather than skipping it.
        target_feat2 = target_pt_idx2 = None
        for f in app.features:
            if f.get("layer") is None:
                continue
            for idx, (lon, lat) in enumerate(f["points"]):
                if (f is target_feat and idx == target_pt_idx) or coord_counts[(round(lon, 6), round(lat, 6))] != 1:
                    continue
                tpx, tpy = app._to_canvas(lon, lat)
                if 0 <= tpx <= 1100 and 0 <= tpy <= 700:
                    target_feat2, target_pt_idx2 = f, idx
                    break
            if target_feat2 is not None:
                break
        assert target_feat2 is not None, "expected a second distinct on-screen unique point to test the connecting line/undo"
        lon2, lat2 = target_feat2["points"][target_pt_idx2]
        px2, py2 = app._to_canvas(lon2, lat2)

        def n_lines_in_picks_area():
            return sum(1 for i in app.canvas.find_withtag("all") if app.canvas.type(i) == "line")

        assert n_lines_in_picks_area() == 0, "with only 1 pick, no connecting line should exist yet"

        ev2 = FakeEvent()
        ev2.x, ev2.y = px2, py2
        app._on_point_pick(ev2)
        assert len(app.picked_points) == 2, "second real click must add a second pick"
        assert app.picked_points[-1]["number"] == 2, "second pick this session must be numbered #2"
        assert n_lines_in_picks_area() >= 1, "with 2+ picks, a connecting line must be drawn between them"
        log("connecting line drawn after 2nd pick -- PASSED")

        app.on_undo_last_point()
        assert len(app.picked_points) == 1, "on_undo_last_point() must remove exactly one (the most recent) pick"
        assert app.picked_points[0]["point_index"] == target_pt_idx, \
            "on_undo_last_point() must leave the FIRST pick untouched, not remove the wrong one"
        assert n_lines_in_picks_area() == 0, "back to 1 pick, the connecting line must be gone again"
        panel_after_undo = app.points_text.get("1.0", "end")
        assert panel_after_undo.count("\n") < panel_text.count("\n") + 2, \
            "on_undo_last_point() must actually remove the undone row from the panel, not just the in-memory list"

        # Rewound counter: the NEXT pick must reuse #2, not jump to #3.
        app._on_point_pick(ev2)
        assert app.picked_points[-1]["number"] == 2, \
            "on_undo_last_point() must rewind the pick counter so the next new pick reuses the undone number"
        log("on_undo_last_point() correctly removed only the last pick and rewound the counter -- PASSED")

        # A click far from any rendered point must be a harmless no-op: no
        # new pick, no crash, just an (implicit) status message.
        far_ev = FakeEvent()
        far_ev.x, far_ev.y = -500, -500  # off in unrendered space, no point anywhere near here
        picks_before2 = len(app.picked_points)
        app._on_point_pick(far_ev)
        assert len(app.picked_points) == picks_before2, "a click far from every rendered point must not add a pick"
        log("click-to-identify miss case (empty space) correctly added nothing -- PASSED")

        # "Clear points" must reset both the in-memory list and the panel.
        app.on_clear_points()
        assert app.picked_points == [], "on_clear_points() must empty the picked-points list"
        cleared_text = app.points_text.get("1.0", "end")
        assert (target_feat["layer"] or "") not in cleared_text or "layer" in cleared_text, \
            "on_clear_points() must remove previously-picked rows (only the header may remain)"
        log("on_clear_points() correctly reset the picked-points list/panel -- PASSED")

        # --- Panning explicitly re-verified after adding the <Button-3>
        #     click-to-identify binding (README §10 "v6 -> v7"): drag a
        #     known pixel distance and confirm pan_x/pan_y update by exactly
        #     that delta, exactly as before this session's changes. This is
        #     the concrete "didn't break panning" proof the task asked for,
        #     not just an assertion that the old bindings are still attached.
        app.pan_x = app.pan_y = 0.0328  # arbitrary non-zero starting pan, to catch an accidental reset-to-0 bug
        start_pan_x, start_pan_y = app.pan_x, app.pan_y
        press_ev = FakeEvent()
        press_ev.x, press_ev.y = 300, 200
        app._on_drag_start(press_ev)
        move_ev = FakeEvent()
        move_ev.x, move_ev.y = 340, 175  # +40 x, -25 y
        app._on_drag_move(move_ev)
        assert app.pan_x == start_pan_x + 40 and app.pan_y == start_pan_y - 25, \
            "dragging must update pan_x/pan_y by exactly the mouse delta -- click-to-identify must not have " \
            "disturbed panning (pan_x=%.4f pan_y=%.4f)" % (app.pan_x, app.pan_y)
        release_ev = FakeEvent()
        release_ev.x, release_ev.y = 340, 175
        app._on_drag_end(release_ev)
        assert app.pan_x == start_pan_x + 40 and app.pan_y == start_pan_y - 25, \
            "pan_x/pan_y must be unchanged by the final _redraw() a drag-release triggers"
        assert app._drag_start is None, "drag state must be cleared on release, same as before this session"
        log("panning explicitly re-verified working (pan_x/pan_y updated by exact drag delta) after adding "
            "the <Button-3> click-to-identify binding -- PASSED")

        # --- Discrete real-hardware-style zoom steps (README §10
        #     "v17 -> v18", user's explicit request): the mouse wheel must
        #     step through ZOOM_LEVELS_M exactly one level per tick, from
        #     wherever `self.scale` currently sits, and clamp (not wrap or
        #     crash) at either end of the table.
        app.canvas.config(width=1100, height=700)
        root.update()
        zoom_w, zoom_h = app.canvas.winfo_width(), app.canvas.winfo_height()
        app.pan_x = app.pan_y = 0.0
        app.scale = viewer.scale_for_zoom_span_m(viewer.DEFAULT_ZOOM_SPAN_M, zoom_w, zoom_h)  # as if just jumped
        zoom_ev = FakeEvent()
        zoom_ev.x, zoom_ev.y = zoom_w // 2, zoom_h // 2  # centered -- isolates the scale change from panning
        app._on_zoom(zoom_ev, delta=120)  # zoom IN one step: 5km -> 4km
        expected_4km = viewer.scale_for_zoom_span_m(4_000.0, zoom_w, zoom_h)
        assert abs(app.scale - expected_4km) < 1e-6, \
            "one zoom-IN tick from the 5km level must land exactly on the 4km level's scale, got %r (expected %r)" % (
                app.scale, expected_4km)
        app._on_zoom(zoom_ev, delta=-120)  # zoom back OUT one step: 4km -> 5km
        expected_5km = viewer.scale_for_zoom_span_m(viewer.DEFAULT_ZOOM_SPAN_M, zoom_w, zoom_h)
        assert abs(app.scale - expected_5km) < 1e-6, \
            "one zoom-OUT tick back from 4km must land exactly on the 5km level's scale again, got %r" % app.scale
        log("discrete zoom step (5km <-> 4km, one real ZOOM_LEVELS_M level per wheel tick) confirmed -- PASSED")

        # Clamp at the narrowest (25m) end -- must NOT crash or overshoot
        # past the table.
        app.scale = viewer.scale_for_zoom_span_m(25.0, zoom_w, zoom_h)
        app._on_zoom(zoom_ev, delta=120)
        assert abs(app.scale - viewer.scale_for_zoom_span_m(25.0, zoom_w, zoom_h)) < 1e-6, \
            "zooming IN past the narrowest real level (25m) must clamp there, not overshoot"
        # Clamp at the widest (500km) end.
        app.scale = viewer.scale_for_zoom_span_m(500_000.0, zoom_w, zoom_h)
        app._on_zoom(zoom_ev, delta=-120)
        assert abs(app.scale - viewer.scale_for_zoom_span_m(500_000.0, zoom_w, zoom_h)) < 1e-6, \
            "zooming OUT past the widest real level (500km) must clamp there, not overshoot"
        log("discrete zoom clamps correctly at both the 25m and 500km table ends -- PASSED")

        # Cursor-centered zoom math must still hold with discrete steps: a
        # wheel tick NOT centered on screen must move pan_x/pan_y so the
        # point under the cursor stays visually fixed (same formula as
        # before this session, just against a discrete new_scale now).
        app.pan_x = app.pan_y = 0.0
        app.scale = viewer.scale_for_zoom_span_m(viewer.DEFAULT_ZOOM_SPAN_M, zoom_w, zoom_h)
        off_center_ev = FakeEvent()
        off_center_ev.x, off_center_ev.y = zoom_w // 4, zoom_h // 4  # off-center
        pre_scale = app.scale
        app._on_zoom(off_center_ev, delta=120)
        ratio_check = app.scale / pre_scale
        cx_check = off_center_ev.x - zoom_w / 2
        cy_check = off_center_ev.y - zoom_h / 2
        expected_pan_x = cx_check * (1 - ratio_check)
        expected_pan_y = cy_check * (1 - ratio_check)
        assert abs(app.pan_x - expected_pan_x) < 1e-6 and abs(app.pan_y - expected_pan_y) < 1e-6, \
            "an off-center zoom tick must still keep the point under the cursor visually fixed " \
            "(pan_x=%r pan_y=%r, expected %r/%r)" % (app.pan_x, app.pan_y, expected_pan_x, expected_pan_y)
        app.pan_x = app.pan_y = 0.0
        app.scale = saved_scale
        log("cursor-centered zoom-to-point math confirmed unchanged under the new discrete stepping -- PASSED")

        # Shrink the canvas for the next two GUI checks (restored to 1100x700
        # right after) -- a real, honest consequence of README §10
        # "v16 -> v17" found while writing THIS test: at the full 1100x700
        # canvas size, scale=500 (this file's "max zoomed out" reference
        # scale) computes a visible bbox roughly 2 degrees wide -- and with
        # every layer now unconditionally pooled (no more scale gate), that
        # means potentially thousands of NEW mp0 tiles to decode (with
        # adjacency) for a single reload, which does not reliably finish
        # inside a reasonable test timeout. This is a real, concrete
        # illustration of the disclosed performance tradeoff this session's
        # change accepts (see README §10 "v16 -> v17"'s own limitations
        # section) -- a genuinely huge zoomed-out viewport with every layer
        # checked is now expensive, by design, and a user hitting this in
        # practice should uncheck heavier layers. For THIS test's own
        # purpose (proving mp0 pools at a low scale, and that a scale-only
        # change no longer triggers a reload), a small canvas keeps the
        # exercised area close to the already-cached Sofia bbox from
        # sections 7c/8b/8c above, so the real background reload below
        # completes quickly without changing what's being proven.
        app.canvas.config(width=50, height=50)
        root.update()

        # Also turn OFF "Draw connected roads" for these next few checks
        # (scale-independence, layer-visibility checkbox, hide-garbage) --
        # a second, real bottleneck found while writing THIS test, distinct
        # from the canvas-size fix above: `_maybe_reload_viewport()` passes
        # `want_adjacency=self.connected_roads_var.get()` (True by default)
        # to `ensure_area_loaded()`, and for a tile that's already decoded
        # (in `tile_caches`, from an EARLIER call in this same test file
        # that used `want_adjacency=False` -- sections 7c/8b/8c all pool
        # this same Sofia area without adjacency) but has no cached
        # adjacency result yet, `ensure_area_loaded()` falls back to
        # `MapData.get_tile_adjacency()`, which -- per its own docstring's
        # explicit disclosure -- "genuinely re-reads and re-decodes the
        # tile's raw bytes" from scratch, a real, already-documented
        # per-tile inefficiency. Previously this was cheap to hit because
        # the OLD scale gate (README §10 "v5 -> v6") kept the touched-tile
        # set tiny at a low scale; with "v16 -> v17" removing that gate, a
        # `want_adjacency=True` reload over this same Sofia area now has to
        # run that slow fallback for potentially hundreds of already-cached
        # tiles across every layer -- observed directly while writing this
        # test: measured over 7 real minutes of continuous CPU activity
        # without finishing. None of the three checks below (scale-
        # independence, layer-visibility, hide-garbage) are testing
        # connected-roads correctness -- that's separately and already
        # covered by the ground-truth canvas-rendering checks above and the
        # dedicated connected-roads redraw-timing section further below, both
        # of which explicitly manage this same variable themselves -- so
        # turning it off here avoids an orthogonal, already-tested feature's
        # real cost entirely, restored to True again once these three
        # checks finish.
        app.connected_roads_var.set(False)

        # --- GUI end-to-end check: layer pooling is scale-INDEPENDENT in the
        #     RUNNING App too (README §10 "v16 -> v17"), not just at the
        #     MapData level (already proven in sections 7c/8b above). Proves
        #     (a) the running App pools mp0 even at the LOWEST scale once
        #     it's ready and checked -- the concrete "mp0 no longer waits
        #     for street-level zoom" behavior the user asked for -- and (b)
        #     a pure scale change, with the viewport still fully covered and
        #     no checkbox touched, no longer triggers a background reload at
        #     all, since the pooled layer set can no longer change from
        #     scale alone (the old "v5 -> v6" scale-threshold reload trigger
        #     has nothing left to detect).
        def pump_until(cond, timeout=180.0, interval=0.05):
            t0 = time.time()
            while not cond():
                if time.time() - t0 > timeout:
                    raise AssertionError("timed out waiting for a background viewport reload to finish")
                root.update()
                time.sleep(interval)

        # NOTE on the resets below: root-caused directly (real bug, not just
        # a test artifact) -- a debounced `_schedule_viewport_check()`
        # reload left pending from an earlier pan/zoom simulation elsewhere
        # in this GUI section can still be sitting in Tk's `after()` queue
        # at this point, with its own worker thread running or about to
        # run. Forcibly clearing `busy`/`_area_loading` here does NOT stop
        # that pending call -- it still runs to completion and its done()
        # still fires eventually, on its own schedule, whenever the queue
        # is drained (observed directly: well after the Sofia load below
        # has already finished). Before App._maybe_reload_viewport() grew a
        # staleness guard (`self._load_token`, see its own docstring) for
        # exactly this, that late completion would silently overwrite
        # `self._covered_bbox`/`features` with its own unrelated (Tirana-
        # area) result, clobbering the Sofia load's already-correct one.
        # The token guard now makes any such stale completion a no-op
        # regardless of when it actually drains, so resetting these flags
        # to force the load below to actually start is safe again.
        app.center_lon, app.center_lat = SOFIA_LON, SOFIA_LAT
        app.pan_x = app.pan_y = 0.0
        app.busy = False
        app._area_loading = False
        app._covered_bbox = None
        app._covered_layers = None
        assert all(var.get() for var in app.layer_visible.values()), \
            "setup check: every layer checkbox must start CHECKED (default, unchanged)"
        app.scale = 500.0  # the LOWEST scale this file's sweeps use -- maximally zoomed out
        # Pin+capture the canvas pixel size *synchronously, right before*
        # triggering the load below -- `_maybe_reload_viewport()` calls
        # `_visible_bbox()` (using whatever `winfo_width()/height()` reports
        # at that exact instant) before ever returning control here, so this
        # is the only way to know for certain what size the load's own bbox
        # was actually computed against. Real window geometry on this OS is
        # not guaranteed stable across the many real seconds of background
        # I/O the load below takes (observed directly: the WM can settle the
        # packed widgets' natural size differently once other UI text --
        # e.g. the status bar's "View updated: ..." message set by `done()`
        # -- changes length and triggers a geometry recompute), so capturing
        # this *after* `pump_until()` returns is NOT the same value and was
        # the actual bug in an earlier version of this fix (confirmed
        # directly: re-pinning to a post-load-read size still failed this
        # same assertion, because the load's own bbox had already been
        # computed against a different, earlier size).
        root.update()
        low_canvas_w = app.canvas.winfo_width()
        low_canvas_h = app.canvas.winfo_height()
        app._maybe_reload_viewport(force=True)
        assert app._area_loading, \
            "the forced initial load at the Sofia coordinates must actually start a background load"
        pump_until(lambda: not app._area_loading)
        low_layers = app._covered_layers
        low_points = sum(len(f["points"]) for f in app.features)
        low_covered_bbox = app._covered_bbox
        log("GUI end-to-end (v16 -> v17): scale=%.0f (max zoomed out) -> covered_layers=%s, %d point(s)" % (
            app.scale, low_layers, low_points))
        assert low_layers == viewer.ALL_LAYERS, \
            "the running App must pool EVERY available layer (including mp0, already ready by this point) " \
            "at the LOWEST scale now -- scale must no longer restrict which layers are considered"
        # NOTE: this reload's own (small, see the canvas-shrink comment
        # above) viewport bbox is not necessarily byte-identical to the
        # fixed half=0.05 Sofia bbox sections 7c/8b/8c measured `all_points`
        # against, so an EXACT point-count match isn't guaranteed here --
        # what this DOES prove, robustly, is that mp0 contributed real,
        # substantial points to the running App's pooled features at the
        # lowest scale, which is the actual behavior under test.
        mp0_tiles_in_low = app.data.active_tile_ids.get("mp0", ())
        assert mp0_tiles_in_low, \
            "mp0 must have real tiles actively pooled (active_tile_ids['mp0']) at the lowest scale now"
        low_mp0_points = sum(
            len(f["points"]) for tid in mp0_tiles_in_low for f in app.data.tile_caches["mp0"].get(tid, ()))
        assert low_mp0_points > 0, \
            "mp0's real content must be included in the running App's pooled points at the lowest scale, " \
            "not withheld until the user zooms in to street level"
        log("confirmed: mp0 pooled in the running App even fully zoomed out (%d mp0 points across %d tiles), "
            "no longer gated on zoom level (README §10 'v16 -> v17')" % (low_mp0_points, len(mp0_tiles_in_low)))

        # Zoom IN with the viewport otherwise unchanged (still fully covered
        # by the padded bbox already loaded above) and NO checkbox touched:
        # since the pooled layer set can no longer differ by scale alone,
        # no reload should fire at all.
        app.scale = 10000.0
        # NOTE (root-caused directly, not theoretical): `App.__init__` pins
        # the TOPLEVEL to a fixed "self.root.geometry('1150x760')" -- so the
        # canvas's own `.config(width=..., height=...)` request (the
        # "shrink the canvas" comment above) was never really controlling
        # its rendered size at all, fill+expand-packed inside that fixed
        # window. What DOES change the canvas's actual allocated pixels,
        # confirmed directly by instrumenting this exact assertion, is the
        # STATUS BAR text: `_set_status()` is called with a genuinely
        # different, longer/shorter message both while the load above was
        # running ("Panning/zooming...") and once it finished ("View
        # updated: N tile(s)..."), and since the window's total size is
        # fixed, a wider status label leaves LESS leftover fill space for
        # the canvas -- so `winfo_width()/height()` legitimately differ
        # between "right after the load above" and "right now", with no
        # test bug and no bad app behavior involved. Re-`.config()`-ing the
        # canvas cannot fight this (proven directly: it does not reliably
        # take hold either, same root cause). So this check -- which exists
        # to prove a pure MATH property ("a same-center zoom-in nests
        # inside the wider padded bbox already loaded") -- computes the new
        # viewport with `compute_visible_bbox()` directly against the exact
        # `low_canvas_w`/`low_canvas_h` the load above actually used,
        # instead of re-reading `winfo_width()/height()` live and hoping
        # the status bar hasn't nudged them since.
        new_vb = viewer.compute_visible_bbox(
            app.center_lon, app.center_lat, app.scale, app.pan_x, app.pan_y, low_canvas_w, low_canvas_h)
        assert viewer.bbox_contains(low_covered_bbox, new_vb), \
            "test setup check: the more-zoomed-in viewport must already be covered by the wider load above " \
            "(same canvas size, same center/pan, only scale changed -- a pure zoom-in must always nest)"
        app._maybe_reload_viewport()  # force=False
        assert not app._area_loading, \
            "changing scale alone, with the viewport still covered and no checkbox touched, must NOT trigger " \
            "a reload any more -- the pooled layer set no longer depends on scale (README §10 'v16 -> v17')"
        assert app._covered_layers == low_layers, "covered_layers must be unchanged by a scale-only move"
        log("confirmed: a pure scale change (viewport still covered, no checkbox touched) no longer triggers "
            "a background reload -- the old scale-threshold reload trigger has nothing left to detect")

        # --- GUI end-to-end layer-visibility checkbox test (README §10
        #     "v8 -> v9"): proves toggling a real Tk BooleanVar and calling
        #     the checkbox's own command (App._on_layer_visibility_changed)
        #     drives a real background reload through the RUNNING App --
        #     not just correct MapData-level `allowed_layers` logic (already
        #     proven in section 8c above). Scale is left at 10,000 (still
        #     zoomed in from the block above) purely to show checkbox
        #     behavior is unaffected by whatever scale happens to be active.
        app._maybe_reload_viewport(force=True)
        assert app._area_loading, "the forced reload before this check must actually start a background load"
        pump_until(lambda: not app._area_loading)
        before_layers = app._covered_layers
        before_points = sum(len(f["points"]) for f in app.features)
        assert before_layers == viewer.ALL_LAYERS, \
            "setup check: expected every available layer (mp0 included, scale no longer restricts anything) " \
            "pooled before toggling any checkbox"
        assert all(var.get() for var in app.layer_visible.values()), \
            "setup check: every layer checkbox must start CHECKED (default, unchanged v6 behavior)"
        log("GUI checkbox test setup: scale=%.0f -> layers=%s, %d point(s)" % (
            app.scale, before_layers, before_points))

        app.layer_visible["mg1"].set(False)
        app._on_layer_visibility_changed()
        assert app._area_loading, "unchecking a layer checkbox must trigger a real background reload"
        pump_until(lambda: not app._area_loading)
        after_uncheck_layers = app._covered_layers
        after_uncheck_points = sum(len(f["points"]) for f in app.features)
        log("GUI checkbox test: unchecked mg1 -> layers=%s, %d point(s) (was %d)" % (
            after_uncheck_layers, after_uncheck_points, before_points))
        assert after_uncheck_layers == ["mg4", "mg3", "mg2", "mp0"], \
            "unchecking mg1's checkbox must remove exactly mg1 from the running App's pooled layers -- mp0 " \
            "stays pooled, since only mg1 was unchecked and scale no longer excludes it"
        assert after_uncheck_points < before_points, \
            "unchecking mg1 must actually shrink app.features's real, measured point count"

        app.layer_visible["mg1"].set(True)
        app._on_layer_visibility_changed()
        assert app._area_loading, "re-checking a layer checkbox must also trigger a real background reload"
        pump_until(lambda: not app._area_loading)
        after_recheck_layers = app._covered_layers
        after_recheck_points = sum(len(f["points"]) for f in app.features)
        log("GUI checkbox test: re-checked mg1 -> layers=%s, %d point(s)" % (
            after_recheck_layers, after_recheck_points))
        assert after_recheck_layers == before_layers, "re-checking mg1 must restore the original layer set"
        assert after_recheck_points == before_points, \
            "re-checking mg1 must restore the exact original point count"
        log("GUI end-to-end layer-visibility checkbox test PASSED (App -> BackgroundTask -> "
            "MapData.ensure_area_loaded(allowed_layers=...) reload actually fires on a checkbox toggle, " \
            "scale-independent, README §10 'v16 -> v17')")

        # Restore the normal canvas size for every GUI check below.
        app.canvas.config(width=1100, height=700)
        root.update()

        # --- MapData.set_trim_oscillation() direct test (README §10
        #     "v10 -> v11"; its own UI checkbox was REMOVED in a later
        #     session -- user request: "remove the hide decode garbage
        #     mechanism, i keep it always off because it doesnt help" --
        #     so this now calls the MapData-level API directly instead of
        #     going through App, exercising exactly what's left reachable:
        #     toggling this must change decode_tile()'s OWN output for the
        #     same tiles (trim_oscillation True vs False is a different
        #     decode, not just a different pool/render choice), proving
        #     set_trim_oscillation() actually invalidates the stale
        #     tile_caches/topo_caches rather than serving cached-under-the-
        #     old-setting data. `app.data` is the shared `data` instance
        #     this whole GUI section deliberately pins to
        #     `trim_oscillation = True` (see the comment where `data` is
        #     constructed) so its many other exact-point-count assertions
        #     stay reproducible -- toggle away from and back to that
        #     pinned value, via a real background reload each time
        #     (`_maybe_reload_viewport(force=True)`, the same force-reload
        #     path every remaining overlay checkbox in the UI still uses).
        assert app.data.trim_oscillation is True, "the shared `data` instance must still be pinned to True here"
        app.data.set_trim_oscillation(False)
        app._maybe_reload_viewport(force=True)
        assert app._area_loading, "set_trim_oscillation(False) + force reload must trigger a real background reload"
        pump_until(lambda: not app._area_loading)
        assert app.data.trim_oscillation is False, "MapData.trim_oscillation must actually flip to False"
        after_raw_points = sum(len(f["points"]) for f in app.features)

        app.data.set_trim_oscillation(True)
        app._maybe_reload_viewport(force=True)
        assert app._area_loading, "set_trim_oscillation(True) + force reload must trigger a real background reload"
        pump_until(lambda: not app._area_loading)
        assert app.data.trim_oscillation is True
        after_refiltered_points = sum(len(f["points"]) for f in app.features)
        log("MapData.set_trim_oscillation() test: filtered=%d point(s) -> raw/unfiltered=%d point(s) (delta=%d)" % (
            after_refiltered_points, after_raw_points, after_raw_points - after_refiltered_points))
        assert after_raw_points != after_refiltered_points, \
            "toggling the oscillation filter must actually change the real decoded point count for the same area " \
            "(if it doesn't, the caches were not properly invalidated)"
        log("MapData.set_trim_oscillation() direct test PASSED (real re-decode with the new trim_oscillation "
            "setting, caches correctly invalidated -- no UI involved, since the checkbox that used to drive this "
            "was removed)")

        # Restore "Draw connected roads" to its normal default (True) for
        # every GUI check below -- see the comment where it was turned off,
        # above.
        app.connected_roads_var.set(True)

        # --- Performance: real App._redraw() wall-clock timing on a dense
        #     real area (the same Sofia bbox measured above), merging just
        #     the 4 fast layers (the pre-mp0-ready pool captured in
        #     `sofia_fast`) vs all 5 including mp0 (`sofia_all`) -- README
        #     §10 "v4 -> v5" asks this to be MEASURED, not assumed. Reuses
        #     the already-decoded feature pools from sections 7b/8b rather
        #     than re-decoding tiles, so this isolates _redraw()'s own cost
        #     from tile-decode cost.
        app.center_lon, app.center_lat = SOFIA_LON, SOFIA_LAT
        app.pan_x = app.pan_y = 0.0

        # README §10 "v17 -> v18": also confirm the canvas-item-count side of
        # the rendering rework at this same real, dense Sofia bbox -- exactly
        # ONE rasterized image item regardless of point count, vs. the OLD
        # one-oval-per-point behavior this section used to report (its
        # `n_ovals_fast`/`n_ovals_all` variable names/log lines are kept
        # below for continuity with README §10 "v4 -> v5"'s original numbers,
        # now measuring rasterized DOT_COLOR pixel counts instead of real
        # canvas ovals).
        app.features = sofia_fast["features"]
        app.scale = app._initial_scale(app.features, half)
        t0 = time.time()
        app._redraw()
        root.update()
        dt_redraw_fast = time.time() - t0
        n_points_fast = sum(len(f["points"]) for f in app.features)
        images_fast = [i for i in app.canvas.find_withtag("all") if app.canvas.type(i) == "image"]
        n_real_ovals_fast = sum(1 for i in app.canvas.find_withtag("all") if app.canvas.type(i) == "oval")
        n_ovals_fast = _count_color_pixels(app._current_image, viewer.DOT_COLOR)
        assert len(images_fast) == 1 and n_real_ovals_fast == 2, \
            "expected exactly 1 rasterized image + 2 marker ovals as real canvas items (got %d image(s), %d " \
            "oval(s))" % (len(images_fast), n_real_ovals_fast)
        log("_redraw() Sofia-area, 4 FAST layers only (%d points, %d DOT_COLOR pixel(s), 1 image canvas item): "
            "%.3fs" % (n_points_fast, n_ovals_fast, dt_redraw_fast))

        app.features = sofia_all["features"]
        app.scale = app._initial_scale(app.features, half)
        t0 = time.time()
        app._redraw()
        root.update()
        dt_redraw_all = time.time() - t0
        n_points_all = sum(len(f["points"]) for f in app.features)
        images_all = [i for i in app.canvas.find_withtag("all") if app.canvas.type(i) == "image"]
        n_real_ovals_all = sum(1 for i in app.canvas.find_withtag("all") if app.canvas.type(i) == "oval")
        n_ovals_all = _count_color_pixels(app._current_image, viewer.DOT_COLOR)
        assert len(images_all) == 1 and n_real_ovals_all == 2, \
            "expected exactly 1 rasterized image + 2 marker ovals as real canvas items (got %d image(s), %d " \
            "oval(s))" % (len(images_all), n_real_ovals_all)
        log("_redraw() Sofia-area, ALL 5 layers incl. mp0 (%d points, %d DOT_COLOR pixel(s), 1 image canvas " \
            "item): %.3fs" % (n_points_all, n_ovals_all, dt_redraw_all))
        assert dt_redraw_all < 5.0, \
            "full 5-layer _redraw() took unexpectedly long (%.2fs) -- a per-viewport point cap/downsample " \
            "may be needed (see README §10 'v4 -> v5'/'v17 -> v18')" % dt_redraw_all
        log("Real _redraw() timing measured (see README §10 'v4 -> v5'/'v17 -> v18' for the recorded before/after "
            "numbers -- the bitmap rasterization rework should make this dramatically faster than the old " \
            "one-canvas-item-per-point/edge approach at the SAME point counts)")

        # --- Performance: real App._redraw() wall-clock timing with
        #     connected-roads mode ON vs OFF (README §10 "v9 -> v10",
        #     "measure, don't assume") -- DISTINCT from section 8e's
        #     already-measured DECODE-time cost of resolve_topology_
        #     adjacency() itself: this isolates the _redraw()-time cost the
        #     checkbox adds/removes (drawing real lines for high-confidence
        #     features vs. dots for everything) on the SAME already-decoded/
        #     already-adjacency-cached dataset, at two different zoom levels
        #     on the same real, dense Sofia-area bbox used throughout this
        #     file. Calling ensure_area_loaded(..., want_adjacency=True)
        #     again on the SAME `data` instance (tiles already cached from
        #     sofia_fast/sofia_all above) exercises get_tile_adjacency()'s
        #     lazy per-tile fallback path (a tile decoded before
        #     connected-roads mode needed it) as a side effect -- real
        #     coverage of that path, not just the fresh-decode path already
        #     covered by section 8e.
        def _count_high_confidence(features, data_obj):
            n = 0
            for f in features:
                layer, tid, fidx = f.get("layer"), f.get("tile_id"), f.get("feature_index")
                if layer is None or tid is None or fidx is None:
                    continue
                tlist = data_obj.topo_caches.get(layer, {}).get(tid)
                if tlist is not None and 0 <= fidx < len(tlist) and tlist[fidx].get("confidence") == "high":
                    n += 1
            return n

        def _measure_connected_roads_redraw(bbox_features_result, scale, label):
            app.features = bbox_features_result["features"]
            app.scale = scale
            n_high = _count_high_confidence(app.features, data)
            n_total = len(app.features)

            app.connected_roads_var.set(True)
            t0 = time.time()
            app._redraw()
            root.update()
            dt_on = time.time() - t0
            # README §10 "v17 -> v18": no more one real canvas line/oval per
            # edge/point to count -- sample the rasterized image for
            # line-colored pixels (either shade means SOME line was drawn)
            # and DOT_COLOR pixels instead. Real canvas items are checked
            # once, cheaply, outside the loop this function is called from.
            img_on = app._current_image
            n_lines_on = (_count_color_pixels(img_on, viewer.ROAD_COLOR_MAJOR) +
                          _count_color_pixels(img_on, viewer.ROAD_COLOR_UNNAMED))
            n_ovals_on = _count_color_pixels(img_on, viewer.DOT_COLOR)

            app.connected_roads_var.set(False)
            t0 = time.time()
            app._redraw()
            root.update()
            dt_off = time.time() - t0
            img_off = app._current_image
            n_lines_off = (_count_color_pixels(img_off, viewer.ROAD_COLOR_MAJOR) +
                           _count_color_pixels(img_off, viewer.ROAD_COLOR_UNNAMED))
            n_ovals_off = _count_color_pixels(img_off, viewer.DOT_COLOR)

            log("%s: %d point(s), %d/%d feature(s) high-confidence -- connected-roads ON: %.3fs "
                "(%d line px, %d dot px); OFF: %.3fs (%d line px, %d dot px)" % (
                    label, sum(len(f["points"]) for f in app.features), n_high, n_total,
                    dt_on, n_lines_on, n_ovals_on, dt_off, n_lines_off, n_ovals_off))
            assert n_lines_off == 0, \
                "%s: connected-roads OFF must rasterize zero line-colored pixels regardless of cached data" % label
            if n_high == 0:
                assert n_lines_on == 0, "%s: no high-confidence features but line pixels were rasterized ON" % label
            else:
                assert n_lines_on > 0, "%s: high-confidence features present but zero line pixels rasterized ON" % label
            app.connected_roads_var.set(True)
            return dt_on, dt_off

        # Re-load the SAME bboxes already used above, this time asking for
        # adjacency to be resolved/cached too. README §10 "v16 -> v17": a
        # low `scale` no longer implies "fast layers only" (mp0 is already
        # ready by this point in the test and would now be pooled too,
        # regardless of scale) -- `allowed_layers=set(FAST_LAYERS)` is now
        # the only way to isolate the 4-fast-layer-only scenario, so it's
        # passed explicitly here instead of relying on a low scale.
        sofia_fast_adj = data.ensure_area_loaded(
            SOFIA_LON - half, SOFIA_LON + half, SOFIA_LAT - half, SOFIA_LAT + half, 1500.0,
            allowed_layers=set(viewer.FAST_LAYERS), want_adjacency=True)
        dt_on_fast, dt_off_fast = _measure_connected_roads_redraw(
            sofia_fast_adj, app._initial_scale(sofia_fast_adj["features"], half),
            "Sofia, fast layers only (checkbox-restricted)")

        sofia_all_adj = data.ensure_area_loaded(
            SOFIA_LON - half, SOFIA_LON + half, SOFIA_LAT - half, SOFIA_LAT + half, FULL_FAST_SCALE,
            want_adjacency=True)
        dt_on_all, dt_off_all = _measure_connected_roads_redraw(
            sofia_all_adj, app._initial_scale(sofia_all_adj["features"], half), "Sofia, all 5 layers incl. mp0 (scale=20000)")

        assert dt_on_fast < 5.0 and dt_on_all < 5.0, \
            "connected-roads-ON _redraw() took unexpectedly long -- may need a rendering-time mitigation"
        log("Real _redraw() connected-roads ON-vs-OFF timing measured at 2 zoom levels (see README §10 "
            "'v9 -> v10' for the honest before/after numbers and whether a mitigation was actually needed)")

        # --- 10. Address entry / letter-keyboard GUI (README §10
        #         "v11 -> v12", re-hosted as an embedded screen PANEL
        #         instead of a separate OS window in "v12 -> v13" -- the
        #         user's explicit correction: "this shouldnt be a new
        #         window, instead it should show on the nav screen"): the
        #         "NAV" bezel button, AddressEntryDialog, SpellerDialog, and
        #         a real end-to-end "Start" jump to a resolved address, all
        #         driven against the real ISO's already-loaded `data`
        #         (address_data_ready is True from section 8h above, so
        #         this exercises the SYNCHRONOUS "data already ready" branch
        #         of on_bezel_nav() directly; the lazy-background-load
        #         branch is exercised implicitly by section 8h itself
        #         calling load_address_entry_data() the same way
        #         on_bezel_nav()'s BackgroundTask does).
        assert app.data.address_data_ready

        def count_toplevels():
            # AddressEntryDialog/SpellerDialog used to be tk.Toplevel
            # (separate OS windows); as of "v12 -> v13" they're tk.Frame
            # panels embedded in app.screen_frame. This counts EVERY real
            # tk.Toplevel anywhere in the whole widget tree (there should be
            # none at all in this test, and showing/hiding these panels
            # must never create one) -- the concrete, real-evidence check
            # for "no separate window is created", not just a code-reading
            # claim.
            return sum(1 for w in all_widgets(root) if isinstance(w, tk.Toplevel))

        baseline_toplevels = count_toplevels()
        # Snapshot of everything that makes up "the map's own state" --
        # showing (and later dismissing) the Address Entry / Speller panels
        # must leave every one of these completely untouched, since the
        # panels only ever COVER the map screen, never rebuild or clear it.
        saved_map_state = (app.center_lon, app.center_lat, app.scale, app.pan_x, app.pan_y, len(app.features))

        before_screen_children = set(app.screen_frame.winfo_children())
        app.on_bezel_nav()
        root.update()

        assert count_toplevels() == baseline_toplevels, \
            "opening Address Entry via the NAV bezel button must NOT create any new tk.Toplevel window " \
            "(README §10 'v12 -> v13': it must show ON the simulated nav screen, not in a separate window)"
        new_panels = [w for w in app.screen_frame.winfo_children()
                      if w not in before_screen_children and isinstance(w, viewer.AddressEntryDialog)]
        assert len(new_panels) == 1, \
            "on_bezel_nav() must show exactly one AddressEntryDialog panel embedded in app.screen_frame " \
            "when data is ready"
        panel = new_panels[0]
        assert isinstance(panel, tk.Frame) and not isinstance(panel, tk.Toplevel), \
            "AddressEntryDialog must be a tk.Frame panel, not a tk.Toplevel window"
        assert panel.winfo_ismapped(), \
            "the Address Entry panel must actually be visible (placed) within the simulated screen area"
        assert (app.center_lon, app.center_lat, app.scale, app.pan_x, app.pan_y, len(app.features)) == saved_map_state, \
            "showing the Address Entry panel on top of the map must not disturb the map's own center/zoom/pan/features"

        panel.destroy()
        root.update()
        assert count_toplevels() == baseline_toplevels
        assert panel not in app.screen_frame.winfo_children(), \
            "dismissing the Address Entry panel must actually remove the overlay"
        assert (app.center_lon, app.center_lat, app.scale, app.pan_x, app.pan_y, len(app.features)) == saved_map_state, \
            "dismissing the Address Entry panel must restore the map view exactly as it was -- since the map " \
            "canvas/status bar were only ever covered, never rebuilt, this should be automatic"
        log("NAV bezel button confirmed to show a real, embedded AddressEntryDialog PANEL within the simulated "
            "screen area -- NO separate tk.Toplevel window created, and the map's own state (center/zoom/pan/"
            "feature count) survived showing and dismissing it byte-for-byte (README §10 'v12 -> v13')")

        addr_dlg = viewer.AddressEntryDialog(app)
        root.update()
        assert addr_dlg.value_vars["city"].get() == "", "Address entry fields must start empty"

        # Required-order scoping (README §10 "v13 -> v14"): City must refuse
        # to open before a valid Country is selected -- real nav UX never
        # offers a city list before the country is known.
        no_country_sp = addr_dlg._open_speller("city")
        assert no_country_sp is None, "City speller must NOT open before a Country is selected"
        assert "country" in addr_dlg.status_var.get().lower(), \
            "refusing to open City must explain why via the status label"
        log("Address entry required order confirmed: City speller refuses to open with no Country selected "
            "(status: %r) -- PASSED" % addr_dlg.status_var.get())

        addr_dlg.values["country"] = "BALGARIA"
        addr_dlg.value_vars["country"].set("BALGARIA")

        # Drive the City speller exactly like a user would: click letters
        # one at a time, checking the SAME live enable/disable state
        # section 8h-viii already validated at the MapData level -- this
        # proves the WIDGETS (not just the underlying index) reflect it
        # correctly, and that they reflect the BULGARIA-SCOPED index (README
        # §10 "v13 -> v14"), not the old global 939,351-record one.
        bg_scoped_idx = data.city_name_index_for_country("BALGARIA")
        assert len(bg_scoped_idx._sorted) < len(data.city_name_index._sorted) / 10, \
            "sanity: the Bulgaria-scoped index must be dramatically smaller than the global one"
        sp = addr_dlg._open_speller("city")
        root.update()
        assert isinstance(sp, viewer.SpellerDialog), "clicking the City row must open a SpellerDialog"
        assert isinstance(sp, tk.Frame) and not isinstance(sp, tk.Toplevel), \
            "SpellerDialog must be a tk.Frame panel, not a tk.Toplevel window"
        assert sp in app.screen_frame.winfo_children(), \
            "SpellerDialog must be embedded in app.screen_frame (the same simulated screen), not a separate window"
        assert sp.winfo_ismapped(), "the City speller panel must actually be visible on top of Address entry"
        assert count_toplevels() == baseline_toplevels, \
            "opening the City speller must NOT create any new tk.Toplevel window either"
        for letter in "SOFI":
            assert sp.key_buttons[letter]["state"] == "normal", \
                "key %r must be enabled at this point in typing SOFIA" % letter
            sp._on_key(letter)
            root.update()
        assert sp.text_var.get() == "SOFI"
        assert sp.count_var.get() == str(bg_scoped_idx.count_matches("SOFI")), \
            "the on-screen match-count badge must reflect the real live SCOPED count, not the global one"
        assert bg_scoped_idx.count_matches("SOFI") < data.city_name_index.count_matches("SOFI"), \
            "sanity: the scoped 'SOFI' count must be smaller than the unscoped, whole-file count -- otherwise " \
            "this isn't actually exercising the scoping fix"
        # A letter that cannot lead anywhere from "SOFI" WITHIN BULGARIA must
        # be a DISABLED button, not just excluded from some internal set --
        # check the actual Tk widget state.
        dead = sorted(set("BCDGJKMQUVWXZ") - bg_scoped_idx.enabled_next_chars("SOFI"))
        assert dead, "expected at least one confidently-dead letter after 'SOFI'"
        assert sp.key_buttons[dead[0]]["state"] == "disabled", \
            "letter %r cannot lead to any real completion of 'SOFI' and must be a disabled button" % dead[0]
        assert sp.key_buttons["A"]["state"] == "normal", "'A' must stay enabled so SOFIA can be completed"
        sp._on_key("A")
        root.update()
        assert sp.text_var.get() == "SOFIA"
        sp._on_ok()
        root.update()
        assert not sp.winfo_exists(), "OK must close the SpellerDialog"
        assert addr_dlg.value_vars["city"].get() == "SOFIA", \
            "confirming the speller must write the typed value back into the Address entry row"
        log("SpellerDialog (City) confirmed: live per-letter enable/disable matches the real BULGARIA-SCOPED "
            "underlying data at every step (badge count %s, dramatically smaller than the global count), OK "
            "writes 'SOFIA' back to Address entry -- PASSED" % sp.count_var.get())

        # Street speller, scoped to the just-confirmed City (README §10
        # "v13 -> v14"): required-order check (refuses to open with no City
        # text), then a real letter-by-letter drive confirming the on-screen
        # widgets reflect the SOFIA-scoped street list, not the old global
        # `.rt`-trie walk -- including a real, exact match-count badge
        # (this scoped path is a genuine PrefixNameIndex, unlike the trie's
        # own "N+" approximate count for the unscoped fallback).
        addr_dlg.values["street"] = ""
        saved_city_value = addr_dlg.values["city"]
        addr_dlg.values["city"] = ""
        no_city_sp = addr_dlg._open_speller("street")
        assert no_city_sp is None, "Street speller must NOT open before City has any text"
        assert "city" in addr_dlg.status_var.get().lower()
        no_city_status = addr_dlg.status_var.get()
        addr_dlg.values["city"] = saved_city_value  # restore "SOFIA" for the real scoped test below
        root.update()
        log("Address entry required order confirmed: Street speller refuses to open with no City text "
            "(status: %r) -- PASSED" % no_city_status)

        sofia_street_idx = data.street_name_index_for_city("SOFIA", country_rec=data.resolve_country("BALGARIA"))
        assert sofia_street_idx is not None
        street_sp = addr_dlg._open_speller("street")
        root.update()
        assert isinstance(street_sp, viewer.SpellerDialog), "clicking the Street row (with a City set) must open a SpellerDialog"
        for letter in "VITOS":
            street_sp._on_key(letter)
            root.update()
        assert street_sp.text_var.get() == "VITOS"
        assert street_sp.count_var.get() == str(sofia_street_idx.count_matches("VITOS")), \
            "the Street speller's match-count badge must reflect the real Sofia-scoped count"
        assert sofia_street_idx.count_matches("VITOS") >= 1, \
            "sanity: 'VITOS' must be a real prefix match within Sofia's own scoped street set (VITOSHA)"
        assert "H" in street_sp.key_buttons and street_sp.key_buttons["H"]["state"] == "normal", \
            "'H' must stay enabled after 'VITOS' so VITOSHA can be completed"
        street_sp.destroy()
        root.update()
        log("SpellerDialog (Street) confirmed: live per-letter narrowing and the exact match-count badge "
            "reflect the real Sofia-SCOPED street list (VITOSHA reachable) -- PASSED")

        # "Start": resolve the typed City to a real coordinate and jump the
        # main map there -- reuses App._jump_to(), the SAME BackgroundTask
        # path "search a place, double-click a result" already uses.
        def pump_until(cond, timeout=30.0, interval=0.05):
            t0 = time.time()
            while not cond():
                if time.time() - t0 > timeout:
                    raise AssertionError("timed out waiting for the NAV 'Start' background jump to finish")
                root.update()
                time.sleep(interval)

        # Connected-roads adjacency is a real, disclosed per-tile cost
        # (measured elsewhere in this file at ~34x a plain decode -- see the
        # v16->v17 section above) that has nothing to do with what THIS
        # check verifies (that "Start" resolves the address and jumps the
        # map there); leaving it on made a real jump to a not-yet-cached
        # area pool enough tiles, each paying that adjacency cost, to blow
        # past a short pump_until timeout on real hardware. Same
        # save/disable/restore idiom already used above for the same reason.
        was_connected_navstart = app.connected_roads_var.get()
        app.connected_roads_var.set(False)
        app.center_lon = app.center_lat = None
        addr_dlg._on_start()
        assert app.busy, "'Start' must kick off a real background area load, same as any other jump"
        pump_until(lambda: not app.busy)
        app.connected_roads_var.set(was_connected_navstart)
        root.update()
        REAL_SOFIA = (23.3241, 42.6977)
        assert app.center_lon is not None and abs(app.center_lon - REAL_SOFIA[0]) < 0.3 and \
            abs(app.center_lat - REAL_SOFIA[1]) < 0.3, \
            "'Start' must have jumped the main map to real Sofia coordinates, got (%r, %r)" % (
                app.center_lon, app.center_lat)
        assert not addr_dlg.winfo_exists(), "'Start' must close the Address entry dialog on success"
        assert count_toplevels() == baseline_toplevels, \
            "the whole NAV -> City speller -> Start flow must never have created a tk.Toplevel window"
        assert not any(isinstance(w, (viewer.AddressEntryDialog, viewer.SpellerDialog))
                        for w in app.screen_frame.winfo_children()), \
            "'Start' must leave no Address Entry/Speller panel behind -- the map screen must be fully restored"
        assert app.canvas.winfo_ismapped(), "the map canvas must be visible again once Address Entry is dismissed"
        log("NAV 'Start' confirmed: real end-to-end BackgroundTask jump to resolved address (%.5f, %.5f), "
            "matching real Sofia coordinates -- AddressEntryDialog panel closed on success, map screen fully "
            "restored, no tk.Toplevel window ever created -- PASSED" % (
                app.center_lon, app.center_lat))

        # Decorative buttons (Save/POI/Map inside this dialog, Intersect.,
        # and the speller's numeric/keyboard-layout/Cyrillic toggles) must
        # not raise and must report themselves via the status label, same
        # established pattern as the bezel's own decorative buttons.
        addr_dlg2 = viewer.AddressEntryDialog(app)
        root.update()
        addr_dlg2._on_decorative("Save")()
        assert "decorative" in addr_dlg2.status_var.get().lower()
        # Street requires City text first (README §10 "v13 -> v14" required
        # order) -- set a real city so this purely-decorative-controls check
        # can still reach a real, opened Street speller.
        addr_dlg2.values["city"] = "SOFIA"
        addr_dlg2.value_vars["city"].set("SOFIA")
        sp2 = addr_dlg2._open_speller("street")
        root.update()
        sp2._decorative("Numeric/symbol keyboard")()
        assert "decorative" in sp2.status_var.get().lower()
        sp2._on_key("Ö")
        assert sp2.key_buttons["Ö"]["state"] == "normal", "the always-enabled decorative accented keys must never be disabled"
        sp2.destroy()
        addr_dlg2.destroy()
        root.update()
        assert count_toplevels() == baseline_toplevels, \
            "the entire Address Entry / Speller test flow must never have created a single tk.Toplevel window"
        log("Decorative Address entry / speller controls (Save/POI/Map/Intersect./numeric-toggle/Cyrillic-toggle) "
            "confirmed non-crashing and self-reporting, same pattern as the bezel's own decorative buttons -- PASSED")

        # --- Street's exhaustive fallback (README §10 "v14 -> v15"),
        #     driven through the REAL widgets: type a nonsense/unresolvable
        #     city into the City field, then open the Street speller and
        #     confirm it falls back to the GLOBAL exhaustive index (not the
        #     old `.rt`-trie walk) and can still fully narrow down to a real
        #     street the trie itself cannot reach (VITOSHA, already proven
        #     unreachable via `.rt` in the non-GUI section above).
        addr_dlg3 = viewer.AddressEntryDialog(app)
        root.update()
        addr_dlg3.values["country"] = "BALGARIA"
        addr_dlg3.value_vars["country"].set("BALGARIA")
        NONSENSE_CITY = "ZZZQQXNOTAREALCITY999"
        addr_dlg3.values["city"] = NONSENSE_CITY
        addr_dlg3.value_vars["city"].set(NONSENSE_CITY)
        assert data.resolve_city_record(NONSENSE_CITY, country_rec=data.resolve_country("BALGARIA")) is None, \
            "sanity: this city text must not resolve to any real eeu.cty record"

        street_sp3 = addr_dlg3._open_speller("street")
        root.update()
        assert isinstance(street_sp3, viewer.SpellerDialog), \
            "Street speller must still open with non-empty (even if unresolvable) City text -- README §10 " \
            "'v13 -> v14' only requires City to have SOME text, not that it resolves"
        # _backing_index() must resolve to the SAME object as
        # MapData.street_name_index_global -- i.e. the exhaustive fallback,
        # not the old `.rt`-trie path -- confirmed both by identity and by
        # the live match-count badge/enabled-letters actually matching the
        # global index's own numbers at every step.
        backing = street_sp3._backing_index()
        assert backing is data.street_name_index_global, \
            "with an unresolvable city, the Street speller's backing index must be the exhaustive global " \
            "index, not None/the old trie path"
        for letter in "VITOS":
            assert street_sp3.key_buttons[letter]["state"] == "normal", \
                "%r must be enabled while spelling VITOSHA via the global fallback index" % letter
            street_sp3._on_key(letter)
            root.update()
        assert street_sp3.text_var.get() == "VITOS"
        assert street_sp3.count_var.get() == str(data.street_name_index_global.count_matches("VITOS")), \
            "the match-count badge must reflect the real GLOBAL index count while using this fallback"
        global_vitos_count = data.street_name_index_global.count_matches("VITOS")
        sofia_vitos_count = data.street_name_index_for_city("SOFIA", country_rec=data.resolve_country("BALGARIA")).count_matches("VITOS")
        assert global_vitos_count >= sofia_vitos_count, \
            "sanity: the unscoped global count must be at least as large as Sofia's own scoped count"
        assert "H" in street_sp3.key_buttons and street_sp3.key_buttons["H"]["state"] == "normal", \
            "'H' must stay enabled after 'VITOS' via the global fallback index, so VITOSHA can be completed"
        street_sp3._on_key("H")
        street_sp3._on_key("A")
        root.update()
        assert street_sp3.text_var.get() == "VITOSHA"
        assert data.street_name_index_global.count_matches("VITOSHA") >= 1
        street_sp3.destroy()
        addr_dlg3.destroy()
        root.update()
        assert count_toplevels() == baseline_toplevels, \
            "the exhaustive-fallback flow must not have created any tk.Toplevel window either"
        log("Street exhaustive fallback confirmed end-to-end through the REAL widgets: an unresolvable city "
            "text (%r) makes the Street speller fall back to MapData.street_name_index_global (identity-"
            "checked, not just behaviorally similar), and live per-letter narrowing/match-count correctly "
            "spells out real street %r all the way -- a name the OLD `.rt`-trie fallback provably could NOT "
            "reach (see the non-GUI section above) -- PASSED" % (NONSENSE_CITY, "VITOSHA"))
    finally:
        root.destroy()
    data.close()
    log("GUI smoke test PASSED")

    log("ALL TESTS PASSED")


if __name__ == "__main__":
    main()
