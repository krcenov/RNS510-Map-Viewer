"""
test_core.py -- non-GUI functional test of rns510_core.MapProject against
the real CD_8555.ISO. Run with:

    py test_core.py

Exercises: load/extract, search, edit-existing-record, append-new-record,
save-as-new-ISO, and round-trip verification -- the same functions the GUI
(rns510_gui.py) calls, just driven directly so it can be proven end to end
without clicking through a UI.
"""

import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rns510_core as core

ISO_PATH = r"C:\Users\krcenov\Downloads\Eu_East_ver17\CD_8555.ISO"
WORKDIR = os.path.join(tempfile.gettempdir(), "rns510_test_work")
OUT_ISO = os.path.join(WORKDIR, "test_output.iso")


def log(msg):
    print("[%.1fs] %s" % (time.time() - T0, msg))


T0 = time.time()


def main():
    assert os.path.exists(ISO_PATH), "source ISO not found: %s" % ISO_PATH
    os.makedirs(WORKDIR, exist_ok=True)

    proj = core.MapProject(ISO_PATH, workdir=WORKDIR)
    proj.load(progress=log)

    n = proj.record_count()
    log("record_count = %d" % n)
    assert n == 8809081, "unexpected record count: %d" % n
    assert proj.iof_record_count() == n, "eeu.iof record count does not match eeu.rd"

    # --- 1. search ---------------------------------------------------
    query = "AGIAS MARINAS"
    results, total = proj.search(query, limit=50)
    log("search(%r) -> %d shown / %d total" % (query, len(results), total))
    assert total > 0, "expected at least one match for %r" % query
    for r in results[:5]:
        log("  match: %r" % r)

    target = results[0]
    log("editing existing record index=%d name=%r lon=%s lat=%s" % (
        target.index, target.name, target.lon, target.lat))

    # --- 2. edit an existing record -----------------------------------
    edited_name = target.name + " EDITED"
    edited_lon = target.lon + 0.001
    edited_lat = target.lat + 0.001
    updated = proj.edit_record(target.index, new_name=edited_name, new_lon=edited_lon, new_lat=edited_lat)
    log("after edit (in-memory workcopy): %r" % updated)
    assert updated.name == edited_name
    assert abs(updated.lon - edited_lon) < 1e-5
    assert abs(updated.lat - edited_lat) < 1e-5

    # confirm re-read from the working-copy file matches too
    reread = proj.get_record(target.index)
    assert reread.name == edited_name
    log("re-read from working-copy eeu.rd confirms edit: %r" % reread)

    # confirm eeu.il now finds the new name for that record
    il_results, il_total = proj.search("EDITED", limit=10)
    found_in_il = any(r.index == target.index and r.name == edited_name for r in il_results)
    log("post-edit il search for 'EDITED' -> %d results, found_expected=%s" % (il_total, found_in_il))
    assert found_in_il, "eeu.il was not updated to reflect the renamed record"

    # --- 3. append a brand new road ------------------------------------
    new_name = "CLAUDE TEST ROAD"
    new_lon = 23.5
    new_lat = 35.2
    new_index = proj.append_record(new_name, new_lon, new_lat)
    log("appended new record index=%d name=%r lon=%s lat=%s" % (new_index, new_name, new_lon, new_lat))
    assert new_index == n, "new record should be appended at old record_count position"
    assert proj.record_count() == n + 1
    assert proj.iof_record_count() == n + 1

    fetched_new = proj.get_record(new_index)
    log("re-read new record: %r" % fetched_new)
    assert fetched_new.name == new_name
    assert abs(fetched_new.lon - new_lon) < 1e-5
    assert abs(fetched_new.lat - new_lat) < 1e-5

    new_search_results, new_search_total = proj.search("CLAUDE TEST ROAD", limit=10)
    found_new = any(r.index == new_index and r.name == new_name for r in new_search_results)
    log("post-append search finds new road: %s (total=%d)" % (found_new, new_search_total))
    assert found_new

    # --- 4. save as new ISO ---------------------------------------------
    if os.path.exists(OUT_ISO):
        os.remove(OUT_ISO)
    proj.build_output_iso(OUT_ISO, progress=log)
    assert os.path.exists(OUT_ISO)
    log("output ISO size = %d bytes" % os.path.getsize(OUT_ISO))

    # --- 5. round-trip verification ---------------------------------------
    checks = {
        target.index: (edited_name, edited_lon, edited_lat),
        new_index: (new_name, new_lon, new_lat),
    }
    ok, details = proj.verify_output(OUT_ISO, checks, progress=log)
    for line in details:
        log("  verify: " + line)
    log("ROUND-TRIP VERIFICATION: %s" % ("PASS" if ok else "FAIL"))
    assert ok, "round-trip verification failed"

    proj.close()
    log("ALL TESTS PASSED")


if __name__ == "__main__":
    main()
