# RNS510 Firmware & Map Reverse-Engineering / Editing Project

Personal reverse-engineering project on a VW RNS-510 navigation head unit, covering both
the application firmware and the navigation map database, working toward a tool that can
open a map ISO, edit its content (roads, POIs), and produce a new ISO the unit will load.

**All research findings, file-format documentation, and firmware reverse-engineering
live in the [project wiki](https://github.com/krcenov/RNS510-Map-Viewer/wiki)** — this
README only covers what's needed to run the tools. Start at the wiki's
[Home page](https://github.com/krcenov/RNS510-Map-Viewer/wiki/Home) for the full index.

**Status at a glance:** editing/adding roads by name + coordinates is fully working and
tested (road editor tool, below). Making a *newly added* road visible/routable on real
hardware is not yet verified — see the wiki's
[Road Editor Tool](https://github.com/krcenov/RNS510-Map-Viewer/wiki/Road-Editor-Tool)
page for the exact solid-vs-experimental breakdown before editing your own map.

---

## The two source materials

- **Firmware / software ISO**: a "SWL" (Software Loading) disc for the Continental/VDO
  "CP2" RNS510 platform — the application/OS software, not map data. See the wiki's
  [SWL Disc: Boot Chain and Build System](https://github.com/krcenov/RNS510-Map-Viewer/wiki/SWL-Disc-Boot-Chain-and-Build-System)
  and [Firmware Reversing](https://github.com/krcenov/RNS510-Map-Viewer/wiki/Firmware-Reversing)
  pages.
- **Map ISO**: `CD_8555.ISO` (~6.48GB) — a genuine official VW navigation map disc,
  "EU East V17", Navteq database EEU (East Europe) 2019Q1, VW part number `1T0051859AR`.
  This is what the editing tool works on. See the wiki's
  [Home page](https://github.com/krcenov/RNS510-Map-Viewer/wiki/Home) for the full,
  file-by-file format breakdown.

Maps and application software are separate products on this platform; the firmware ISO
never contains map data, and vice versa.

---

## Tools

Run with the `py` launcher (plain `python`/`python3` may not be on `PATH`).

### Map Viewer — `py rns510_map_viewer.py`

Read-only visualization/debugging GUI: renders the real map disc directly (roads, POIs,
Sirius TravelLink POIs, address search), built to validate the file-format findings
documented in the wiki. See the wiki's
[Map Viewer Tool](https://github.com/krcenov/RNS510-Map-Viewer/wiki/Map-Viewer-Tool) page
for the full feature list and version history.

### Road Editor — `py rns510_gui.py`

The actual editing tool: search/rename/move existing roads, add new ones, and save a new
ISO the unit can load. See the wiki's
[Road Editor Tool](https://github.com/krcenov/RNS510-Map-Viewer/wiki/Road-Editor-Tool) page
for exactly what's solid vs. experimental before trusting a real edit.

### SD card deployment

The RNS510 doesn't read a map ISO directly — a separate community tool, `maps-tool`,
prepares an SD card + bootstrap DVD from an edited ISO. See the wiki's
[ISO Container Handling](https://github.com/krcenov/RNS510-Map-Viewer/wiki/ISO-Container-Handling)
page for the real-world procedure.

---

## Repo layout

- `rns510_map_viewer.py` / `rns510_gui.py` — the two GUI tools above.
- `rns510_core.py` — shared map-format read/write logic (no GUI code).
- `rns510_iso.py` — ISO9660/UDF read/write helper shared by both tools.
- `research/` — reusable, documented format-reader modules (one per file format), plus
  `swl_5238_reader.py`, the firmware/SWL-disc research log.
- `test_map_viewer.py` / `test_core.py` — non-GUI functional tests, run against the real
  discs.

**Dependencies**: `pycdlib` (ISO9660/UDF), `Pillow` (rendering), `numpy` (POI decoding).
Everything else is Python stdlib (`tkinter`, `sqlite3`, `zlib`).

---

## Contributing / continuing this work

This is a personal research project, not a packaged product — no installer, no
guarantees. If you're picking up where this left off: read the wiki's
[Home page](https://github.com/krcenov/RNS510-Map-Viewer/wiki/Home) first, then
`research/swl_5238_reader.py`'s own module docstring for the full firmware-side research
narrative (the wiki summarizes and cross-links it, but doesn't reproduce every dead end).
