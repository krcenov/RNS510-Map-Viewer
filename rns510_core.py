"""
rns510_core.py -- Core (non-GUI) logic for editing db/eeu.rd, db/eeu.il and
db/eeu.iof inside a VW RNS510 navigation map ISO (CD_8555.ISO and disc
family).

This module contains NO GUI code. rns510_gui.py is a thin tkinter wrapper
that calls into MapProject below. test_core.py exercises the same functions
directly against the real ISO to prove the logic works end to end.

-----------------------------------------------------------------------------
File formats (verified against CD_8555.ISO on 2026-09-16):

db/eeu.rd  (road/point records) -- 590,208,521 bytes on the reference disc
    94-byte header (opaque, preserved byte-for-byte), then fixed 67-byte
    records with no gaps:
        bytes[0:24]   binary header
            byte[0]      unknown/flags   (preserve on edit, zero on append)
            bytes[1:5]   unknown         (preserve on edit, zero on append)
            bytes[5:8]   unknown         (preserve on edit, zero on append)
            bytes[8:12]  longitude (segment's own min/start corner),
                         little-endian int32, degrees = v/100000
            bytes[12:16] latitude  (segment's own min/start corner),
                         little-endian int32, degrees = v/100000
            bytes[16:20] delta_long -- CRACKED (a later session): the
                         real field name eeu.mod's own schema gives this
                         position (research/mod_reader.py, token ['rd'] --
                         ...min_long, min_lat, delta_long, delta_lat,
                         name... -- matching this file's own real byte
                         layout position-for-position). Little-endian
                         int32, SAME /100000 degrees convention as
                         longitude/latitude above, but always
                         NON-NEGATIVE (0 violations across a real
                         20,000-record full-file random sample) --
                         i.e. a bounding-box WIDTH, not a signed vector:
                         this segment's real geographic extent is
                         [longitude, longitude+delta_long] x [latitude,
                         latitude+delta_lat]. Validated: the implied
                         segment diagonal (haversine-ish, cos(lat)
                         -corrected) has median 350m / mean 1.1km over
                         that same 20,000-record sample, with 96.8%
                         under 5km and 99.9% under 50km -- exactly the
                         real-world range of named road-segment lengths,
                         not noise. (preserve on edit -- editing a
                         record's own lon/lat without recomputing this
                         would silently move the segment's end corner
                         too; zero on append, giving a new road a
                         zero-area/point-like extent, same as before)
            bytes[20:24] delta_lat -- CRACKED, see delta_long directly
                         above (same field, same validation, same
                         caveats)
        bytes[24:67]  ASCII name, NUL-padded, 43 bytes
    record_index = (offset_in_file - 94) // 67

    eeu.mod's own real field name list for this table, in order (for a
    future session -- research/mod_reader.py's extract_blocks(), token
    ['rd']): cityAndCountryID, cityID, countryID, affixID, suffixID,
    prefixID, typeID, roadInfo, highway, preferred, explicate, ramp,
    "name type", interchange, min_long, min_lat, delta_long, delta_lat,
    name, phoneRoadOffset, roadListIdMain. The first 14 (cityAndCountryID
    through interchange) must pack into bytes[0:8] (byte[0] + bytes[1:5]
    + bytes[5:8]) -- mostly small IDs/single-bit flags by name, several
    plausibly from `eeu.cty`/`eeu.ctr`/`eeu.typ` (`typeID` is a strong
    candidate for an index into eeu.typ's own 2,574 real entries). NOT
    yet decoded: a quick test of every individual bit of byte[0] against
    whether the record's own name looks route-like (candidate `highway`
    flag, using research/iof_reader.py's is_route_like_name()) found
    zero correlation on any of the 8 bits (route-like fraction ~0.06
    regardless of bit value, over a 20,000-record sample) -- `highway`
    isn't simply one bit of byte[0] alone; the real packing of these 14
    fields across 8 bytes remains open. The firmware's own dbal/
    DBAL.OUT binaries (research/dbal_reader.py) confirm real compiled
    source files exist for this table (`db_road.cpp`/`db_road_list.cpp`/
    `db_road_cache.cpp`/`db_road_sel_char.cpp`) and one directly relevant
    accessor name (`db_road_NameListDataByIndex_V004`), but -- unlike
    eeu.si's rich `db_seg_*` per-field accessor catalog -- no further
    per-field road-classification accessors were found there to help
    pin down the byte[0:8] packing.

db/eeu.il  (name index -> eeu.rd record number) -- 39,355,546 bytes
    94-byte header (opaque, preserved byte-for-byte), then variable-length
    entries with no gaps:
        bytes[0:4]   little-endian uint32 = eeu.rd record index
        bytes[4:11]  unknown 7 bytes (best-effort copy of a nearby pattern
                     when appending -- NOT decoded)
        bytes[11:]   ASCII name, NUL-terminated
    IMPORTANT CORRECTION vs. the original task brief: the prefix on entry i
    refers to THAT SAME entry's name, not the following entry. Verified by
    decoding the first 20 real entries in eeu.il and cross-checking the
    eeu.rd record each one points at -- 20/20 exact name matches. (See
    probe_parse.py output captured during this build for the raw evidence.)
    Entries were observed to be in ascending alphabetical order by name in
    the sampled region; that is used only as a soft hint (to find a
    "nearby" template entry when appending), never relied on for
    correctness.

db/eeu.iof (parallel per-eeu.rd-record array) -- 52,854,580 bytes
    94-byte header, then fixed 6-byte records, same count as eeu.rd
    (confirmed: (52854580-94)/6 == (590208521-94)/67 == 8,809,081).
    Structure beyond a common "00 00 ?? 80 00 00" shape is not understood.
    Editing existing records is out of scope; appending copies a plausible
    default record so the array stays the same length as eeu.rd.
-----------------------------------------------------------------------------
"""

import os
import shutil
import struct
import tempfile

import rns510_iso as riso

HEADER_SIZE = 94

RD_RECORD_SIZE = 67
RD_HDR_SIZE = 24
RD_NAME_SIZE = 43  # 67 - 24

IOF_RECORD_SIZE = 6
IOF_DEFAULT_RECORD = b"\x00\x00\x00\x80\x00\x00"

ISO_RD_PATH = "/DB/EEU.RD"
ISO_IL_PATH = "/DB/EEU.IL"
ISO_IOF_PATH = "/DB/EEU.IOF"


class MapToolError(Exception):
    pass


class RoadRecord:
    """Decoded view of one eeu.rd record."""

    __slots__ = ("index", "raw_header", "name", "lon", "lat", "delta_lon", "delta_lat")

    def __init__(self, index, raw_header, name, lon, lat, delta_lon=0.0, delta_lat=0.0):
        self.index = index
        self.raw_header = raw_header  # 24 raw bytes, unknown fields intact
        self.name = name
        self.lon = lon
        self.lat = lat
        # this segment's real bounding-box extent (always >= 0 -- see this
        # module's own file-format docstring above, bytes[16:20]/[20:24]):
        # the segment spans [lon, lon+delta_lon] x [lat, lat+delta_lat]
        self.delta_lon = delta_lon
        self.delta_lat = delta_lat

    def __repr__(self):
        return "RoadRecord(index=%d, name=%r, lon=%s, lat=%s, delta_lon=%s, delta_lat=%s)" % (
            self.index, self.name, self.lon, self.lat, self.delta_lon, self.delta_lat)


def _decode_rd_record(index, data):
    if len(data) != RD_RECORD_SIZE:
        raise MapToolError("bad record length %d at index %d" % (len(data), index))
    header = data[:RD_HDR_SIZE]
    name = data[RD_HDR_SIZE:].split(b"\x00", 1)[0].decode("latin-1")
    lon = struct.unpack_from("<i", header, 8)[0] / 100000.0
    lat = struct.unpack_from("<i", header, 12)[0] / 100000.0
    delta_lon = struct.unpack_from("<i", header, 16)[0] / 100000.0
    delta_lat = struct.unpack_from("<i", header, 20)[0] / 100000.0
    return RoadRecord(index, header, name, lon, lat, delta_lon, delta_lat)


def _encode_rd_record(header24, name):
    if len(header24) != RD_HDR_SIZE:
        raise MapToolError("header must be exactly %d bytes" % RD_HDR_SIZE)
    name_bytes = name.encode("latin-1", errors="replace")
    if len(name_bytes) > RD_NAME_SIZE:
        raise MapToolError(
            "name %r is %d bytes, max %d bytes allowed" % (name, len(name_bytes), RD_NAME_SIZE))
    name_field = name_bytes + b"\x00" * (RD_NAME_SIZE - len(name_bytes))
    return header24 + name_field


def _set_lon_lat(header24, lon, lat):
    header = bytearray(header24)
    struct.pack_into("<i", header, 8, int(round(lon * 100000)))
    struct.pack_into("<i", header, 12, int(round(lat * 100000)))
    return bytes(header)


class MapProject:
    """
    Loads db/eeu.rd, db/eeu.il, db/eeu.iof from a source ISO into local
    working-copy files (never holds the whole disc, or the whole eeu.rd
    file, in memory), and offers search/edit/append/save operations.
    """

    def __init__(self, iso_path, workdir=None, read_only=False):
        """`read_only=True` (used by the map viewer's search-only
        MapProject, never by the editor GUI) skips extraction entirely --
        see load()'s own docstring, "direct-from-ISO reading" (README
        §4) -- and disables every edit/append/save method, since those
        need a real, mutable local file. Default False preserves the
        original extract-to-workdir behavior exactly, unchanged, for
        rns510_gui.py's editing flow."""
        self.iso_path = iso_path
        self._owns_workdir = workdir is None
        self.workdir = workdir or tempfile.mkdtemp(prefix="rns510_")
        os.makedirs(self.workdir, exist_ok=True)
        self.read_only = read_only
        self.rd_path = os.path.join(self.workdir, "eeu.rd")
        self.il_path = os.path.join(self.workdir, "eeu.il")
        self.iof_path = os.path.join(self.workdir, "eeu.iof")
        self._loaded = False

    # ---------------------------------------------------------------- load

    def load(self, progress=None):
        """Load the three DB files. In `read_only` mode, resolves each
        one's byte extent directly inside the ISO (an `rns510_iso.
        IsoFileRef`, see README §4 "direct-from-ISO reading") instead of
        extracting it to workdir -- every read call site below already
        goes through `riso.open_ref_or_path()`/`riso.size_of()`, which
        transparently support either a plain path or an IsoFileRef, so
        this is the only place the two modes actually differ. Default
        (non-read_only) mode is unchanged: extracts all three to
        workdir, since editing needs real, mutable local files."""
        if progress:
            progress("Opening ISO...")
        iso = riso.open_tolerant(self.iso_path)
        try:
            if self.read_only:
                for iso_path, attr in (
                    (ISO_RD_PATH, "rd_path"),
                    (ISO_IL_PATH, "il_path"),
                    (ISO_IOF_PATH, "iof_path"),
                ):
                    if progress:
                        progress("Locating %s in the ISO..." % iso_path)
                    setattr(self, attr, riso.open_file_ref(iso, iso_path, self.iso_path))
            else:
                for iso_path, local_path in (
                    (ISO_RD_PATH, self.rd_path),
                    (ISO_IL_PATH, self.il_path),
                    (ISO_IOF_PATH, self.iof_path),
                ):
                    if progress:
                        progress("Extracting %s..." % iso_path)
                    with open(local_path, "wb") as f:
                        iso.get_file_from_iso_fp(f, iso_path=iso_path)
        finally:
            iso.close()
        self._loaded = True
        if progress:
            progress("Loaded %d road records." % self.record_count())

    def _require_writable(self, op):
        if self.read_only:
            raise MapToolError(
                "%s: this MapProject was opened read_only=True (no local mutable "
                "copy was extracted) -- construct one with read_only=False (the "
                "default) to edit/append/save" % op)

    # ------------------------------------------------------------ queries

    def record_count(self):
        size = riso.size_of(self.rd_path)
        if (size - HEADER_SIZE) % RD_RECORD_SIZE != 0:
            raise MapToolError("eeu.rd size %d is not header + N*%d" % (size, RD_RECORD_SIZE))
        return (size - HEADER_SIZE) // RD_RECORD_SIZE

    def iof_record_count(self):
        size = riso.size_of(self.iof_path)
        return (size - HEADER_SIZE) // IOF_RECORD_SIZE

    def get_record(self, index):
        n = self.record_count()
        if not (0 <= index < n):
            raise MapToolError("record index %d out of range (0..%d)" % (index, n - 1))
        with riso.open_ref_or_path(self.rd_path) as f:
            f.seek(HEADER_SIZE + index * RD_RECORD_SIZE)
            data = f.read(RD_RECORD_SIZE)
        return _decode_rd_record(index, data)

    def search(self, query, limit=300):
        """
        Substring, case-insensitive search over eeu.il names. Returns
        (results, total_matches) where results is capped at `limit`
        RoadRecord objects (decoded from eeu.rd) and total_matches is the
        exact number of eeu.il entries that matched (even if more than
        `limit` were found -- only decoded/returned entries are capped, the
        counting scan is cheap since it's just a substring test).
        """
        query = query.strip().lower()
        if not query:
            return [], 0

        results = []
        total = 0
        with riso.open_ref_or_path(self.il_path) as ilf:
            ilf.seek(HEADER_SIZE)
            body = ilf.read()

        pos = 0
        blen = len(body)
        with riso.open_ref_or_path(self.rd_path) as rdf:
            while pos < blen:
                if pos + 11 > blen:
                    break
                prefix = body[pos:pos + 11]
                pos += 11
                end = body.find(b"\x00", pos)
                if end == -1:
                    break
                name_bytes = body[pos:end]
                pos = end + 1
                if query not in name_bytes.decode("latin-1").lower():
                    continue
                total += 1
                if len(results) < limit:
                    record_index = struct.unpack_from("<I", prefix, 0)[0]
                    n = self.record_count()
                    if record_index < n:
                        rdf.seek(HEADER_SIZE + record_index * RD_RECORD_SIZE)
                        data = rdf.read(RD_RECORD_SIZE)
                        results.append(_decode_rd_record(record_index, data))
        return results, total

    def find_template_prefix_extra(self, name):
        """
        Best-effort lookup of a "nearby" eeu.il entry's unknown 7-byte
        prefix suffix, to use as a template default when appending a new
        entry. eeu.il entries were observed sorted by name in the sampled
        region, so this returns the extra-7-bytes of the alphabetically
        closest entry found during a single linear scan. Falls back to
        seven zero bytes if eeu.il is empty/unreadable.
        """
        target = name.lower()
        best_extra = b"\x00" * 7
        best_name = None
        with riso.open_ref_or_path(self.il_path) as ilf:
            ilf.seek(HEADER_SIZE)
            body = ilf.read()
        pos = 0
        blen = len(body)
        while pos < blen:
            if pos + 11 > blen:
                break
            prefix = body[pos:pos + 11]
            pos += 11
            end = body.find(b"\x00", pos)
            if end == -1:
                break
            entry_name = body[pos:end].decode("latin-1")
            pos = end + 1
            if best_name is None or abs(len(entry_name) - len(target)) <= abs(len(best_name) - len(target)):
                if entry_name.lower() <= target or best_name is None:
                    best_extra = prefix[4:11]
                    best_name = entry_name
            if entry_name.lower() > target:
                # first entry alphabetically after target: good enough, stop
                best_extra = prefix[4:11]
                break
        return best_extra

    # ------------------------------------------------------------- edits

    def edit_record(self, index, new_name=None, new_lon=None, new_lat=None):
        """
        Patch an existing eeu.rd record in place (record size never
        changes -- the name field is fixed-width 43 bytes). All unknown
        header bytes are preserved untouched. Also best-effort updates any
        eeu.il entries that reference this record index so search stays
        consistent with the new name.
        """
        self._require_writable("edit_record")
        record = self.get_record(index)
        header = record.raw_header
        old_name = record.name
        if new_lon is not None or new_lat is not None:
            header = _set_lon_lat(
                header,
                new_lon if new_lon is not None else record.lon,
                new_lat if new_lat is not None else record.lat,
            )
        final_name = new_name if new_name is not None else old_name
        data = _encode_rd_record(header, final_name)

        with open(self.rd_path, "r+b") as f:
            f.seek(HEADER_SIZE + index * RD_RECORD_SIZE)
            f.write(data)

        if new_name is not None and new_name != old_name:
            self._update_il_entries_for_record(index, new_name)

        return self.get_record(index)

    def _update_il_entries_for_record(self, record_index, new_name):
        """
        Rewrite eeu.il, renaming every entry whose prefix references
        record_index to new_name. If no entry references it, append one
        (best-effort, flagged experimental to the caller/UI).
        """
        with open(self.il_path, "rb") as ilf:
            header = ilf.read(HEADER_SIZE)
            body = ilf.read()

        out = bytearray()
        pos = 0
        blen = len(body)
        found = False
        while pos < blen:
            if pos + 11 > blen:
                out += body[pos:]
                break
            prefix = body[pos:pos + 11]
            entry_start = pos
            pos += 11
            end = body.find(b"\x00", pos)
            if end == -1:
                out += body[entry_start:]
                break
            name_bytes = body[pos:end]
            pos = end + 1
            idx = struct.unpack_from("<I", prefix, 0)[0]
            if idx == record_index:
                found = True
                out += prefix
                out += new_name.encode("latin-1", errors="replace")
                out += b"\x00"
            else:
                out += prefix
                out += name_bytes
                out += b"\x00"

        if not found:
            extra = self.find_template_prefix_extra(new_name)
            new_prefix = struct.pack("<I", record_index) + extra
            out += new_prefix
            out += new_name.encode("latin-1", errors="replace")
            out += b"\x00"

        with open(self.il_path, "wb") as ilf:
            ilf.write(header)
            ilf.write(bytes(out))

        return found

    def append_record(self, name, lon, lat):
        """
        Append a brand-new eeu.rd record (unknown header bytes zero
        filled), a matching eeu.il entry (best-effort 7-byte template
        copied from a nearby entry), and a default eeu.iof entry to keep
        that array's length in sync. Returns the new record's index.

        EXPERIMENTAL: the road-name search tree, city/county tables and
        rendering tiles are not touched, so the new road may be findable
        via this tool's search but may not render or route on real
        hardware. Editing an existing record's name/coordinates is far
        more reliable than adding a new one.
        """
        self._require_writable("append_record")
        new_index = self.record_count()
        header = _set_lon_lat(b"\x00" * RD_HDR_SIZE, lon, lat)
        data = _encode_rd_record(header, name)
        with open(self.rd_path, "ab") as f:
            f.write(data)

        extra = self.find_template_prefix_extra(name)
        prefix = struct.pack("<I", new_index) + extra
        with open(self.il_path, "ab") as f:
            f.write(prefix)
            f.write(name.encode("latin-1", errors="replace"))
            f.write(b"\x00")

        with open(self.iof_path, "ab") as f:
            f.write(IOF_DEFAULT_RECORD)

        return new_index

    # -------------------------------------------------------------- save

    def build_output_iso(self, out_iso_path, progress=None):
        """
        Write a NEW ISO (never overwrites the source) with db/eeu.rd,
        db/eeu.il and db/eeu.iof replaced by the working-copy files, and
        everything else byte-for-byte identical to the source disc.
        """
        self._require_writable("build_output_iso")
        if os.path.abspath(out_iso_path) == os.path.abspath(self.iso_path):
            raise MapToolError("refusing to overwrite the source ISO -- choose a different output path")

        if progress:
            progress("Opening source ISO...")
        iso = riso.open_tolerant(self.iso_path)
        try:
            fps = []
            try:
                for local_path, iso_path in (
                    (self.rd_path, ISO_RD_PATH),
                    (self.il_path, ISO_IL_PATH),
                    (self.iof_path, ISO_IOF_PATH),
                ):
                    if progress:
                        progress("Staging %s for write..." % iso_path)
                    length = os.path.getsize(local_path)
                    fp = open(local_path, "rb")
                    fps.append(fp)
                    iso.update_file_contents_fp(fp, length, iso_path=iso_path)

                riso.strip_udf(iso)
                if progress:
                    progress("Writing %s (this can take several minutes for a multi-GB ISO)..." % out_iso_path)
                iso.write(out_iso_path)
            finally:
                for fp in fps:
                    fp.close()
        finally:
            iso.close()
        if progress:
            progress("Write complete: %s" % out_iso_path)

    def verify_output(self, out_iso_path, checks, progress=None):
        """
        Reopen out_iso_path fresh, re-extract eeu.rd, and confirm that each
        (record_index -> expected RoadRecord-like) check reads back
        exactly as expected. `checks` is a dict {record_index: (name, lon,
        lat)}. Returns (ok: bool, details: list[str]).
        """
        details = []
        ok = True
        if progress:
            progress("Reopening written ISO for verification...")
        iso = riso.open_tolerant(out_iso_path)
        try:
            verify_dir = tempfile.mkdtemp(prefix="rns510_verify_")
            verify_rd = os.path.join(verify_dir, "eeu.rd")
            with open(verify_rd, "wb") as f:
                iso.get_file_from_iso_fp(f, iso_path=ISO_RD_PATH)
        finally:
            iso.close()

        size = os.path.getsize(verify_rd)
        n = (size - HEADER_SIZE) // RD_RECORD_SIZE
        with open(verify_rd, "rb") as f:
            for index, (exp_name, exp_lon, exp_lat) in checks.items():
                if index >= n:
                    ok = False
                    details.append("index %d: OUT OF RANGE (file only has %d records)" % (index, n))
                    continue
                f.seek(HEADER_SIZE + index * RD_RECORD_SIZE)
                data = f.read(RD_RECORD_SIZE)
                rec = _decode_rd_record(index, data)
                name_ok = rec.name == exp_name
                lon_ok = abs(rec.lon - exp_lon) < 1e-5
                lat_ok = abs(rec.lat - exp_lat) < 1e-5
                if name_ok and lon_ok and lat_ok:
                    details.append("index %d: OK (name=%r lon=%s lat=%s)" % (index, rec.name, rec.lon, rec.lat))
                else:
                    ok = False
                    details.append(
                        "index %d: MISMATCH got name=%r lon=%s lat=%s, expected name=%r lon=%s lat=%s"
                        % (index, rec.name, rec.lon, rec.lat, exp_name, exp_lon, exp_lat))
        shutil.rmtree(verify_dir, ignore_errors=True)
        if progress:
            progress("Verification %s" % ("PASSED" if ok else "FAILED"))
        return ok, details

    def close(self):
        if self._owns_workdir:
            shutil.rmtree(self.workdir, ignore_errors=True)
