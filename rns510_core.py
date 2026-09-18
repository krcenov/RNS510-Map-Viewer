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
            bytes[8:12]  longitude, little-endian int32, degrees = v/100000
            bytes[12:16] latitude,  little-endian int32, degrees = v/100000
            bytes[16:20] unknown         (preserve on edit, zero on append)
            bytes[20:24] unknown         (preserve on edit, zero on append)
        bytes[24:67]  ASCII name, NUL-padded, 43 bytes
    record_index = (offset_in_file - 94) // 67

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

    __slots__ = ("index", "raw_header", "name", "lon", "lat")

    def __init__(self, index, raw_header, name, lon, lat):
        self.index = index
        self.raw_header = raw_header  # 24 raw bytes, unknown fields intact
        self.name = name
        self.lon = lon
        self.lat = lat

    def __repr__(self):
        return "RoadRecord(index=%d, name=%r, lon=%s, lat=%s)" % (
            self.index, self.name, self.lon, self.lat)


def _decode_rd_record(index, data):
    if len(data) != RD_RECORD_SIZE:
        raise MapToolError("bad record length %d at index %d" % (len(data), index))
    header = data[:RD_HDR_SIZE]
    name = data[RD_HDR_SIZE:].split(b"\x00", 1)[0].decode("latin-1")
    lon = struct.unpack_from("<i", header, 8)[0] / 100000.0
    lat = struct.unpack_from("<i", header, 12)[0] / 100000.0
    return RoadRecord(index, header, name, lon, lat)


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

    def __init__(self, iso_path, workdir=None):
        self.iso_path = iso_path
        self._owns_workdir = workdir is None
        self.workdir = workdir or tempfile.mkdtemp(prefix="rns510_")
        os.makedirs(self.workdir, exist_ok=True)
        self.rd_path = os.path.join(self.workdir, "eeu.rd")
        self.il_path = os.path.join(self.workdir, "eeu.il")
        self.iof_path = os.path.join(self.workdir, "eeu.iof")
        self._loaded = False

    # ---------------------------------------------------------------- load

    def load(self, progress=None):
        """Extract the three DB files from the source ISO into workdir."""
        if progress:
            progress("Opening ISO...")
        iso = riso.open_tolerant(self.iso_path)
        try:
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

    # ------------------------------------------------------------ queries

    def record_count(self):
        size = os.path.getsize(self.rd_path)
        if (size - HEADER_SIZE) % RD_RECORD_SIZE != 0:
            raise MapToolError("eeu.rd size %d is not header + N*%d" % (size, RD_RECORD_SIZE))
        return (size - HEADER_SIZE) // RD_RECORD_SIZE

    def iof_record_count(self):
        size = os.path.getsize(self.iof_path)
        return (size - HEADER_SIZE) // IOF_RECORD_SIZE

    def get_record(self, index):
        n = self.record_count()
        if not (0 <= index < n):
            raise MapToolError("record index %d out of range (0..%d)" % (index, n - 1))
        with open(self.rd_path, "rb") as f:
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
        with open(self.il_path, "rb") as ilf:
            ilf.seek(HEADER_SIZE)
            body = ilf.read()

        pos = 0
        blen = len(body)
        with open(self.rd_path, "rb") as rdf:
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
        with open(self.il_path, "rb") as ilf:
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
