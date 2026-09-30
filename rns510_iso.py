"""
Reusable helpers for opening / editing / rewriting the VW RNS510 nav map ISO
(CD_8555.ISO, and presumably sibling discs of the same family).

Background: the disc is a UDF+ISO9660 "bridge" image. Its ISO9660 side is
100% standard and parses cleanly with stock pycdlib. Its UDF side is broken
starting at the very first File Identifier Descriptor of the root directory
(confirmed: pycdlib's parse_file_ident chokes immediately, entries_ok=0),
which is *original mastering behavior*, not something introduced by us --
the disc works fine in car head units and Windows Explorer, both of which
read the ISO9660 tree, not UDF. config/create_cd (the Continental/Navteq
disc-build script) contains nothing but flat `cp`/`mkdir` commands -- no
hashing, checksumming or signing step -- so there is no known cryptographic
integrity check on file/disc content to defeat.

Strategy used here: monkeypatch pycdlib's UDF directory walker to tolerate
(rather than raise on) the broken UDF structures so `PyCdlib.open()`
succeeds, then strip all UDF state before writing so the output is a clean,
standard ISO9660-only image (which is everything the head unit needs).

Usage:
    import rns510_iso as riso
    iso = riso.open_tolerant(r"C:\\path\\to\\CD_8555.ISO")
    # ... read/replace/add files via iso.get_file_from_iso_fp /
    #     iso.rm_file / iso.add_fp / iso.modify_file_in_place (pycdlib API) ...
    riso.strip_udf(iso)
    iso.write(r"C:\\path\\to\\new.iso")
    iso.close()

Verified round-trip (2026-09-16): opened CD_8555.ISO, stripped UDF, wrote
an unmodified copy -> new file is byte-identical size (6,479,642,624 bytes),
FILES.CFG matches original sha256 exactly, and DB/EEU.RD (590,208,521 bytes)
matches original sha256 exactly. The new ISO reopens with plain
pycdlib.PyCdlib().open() (no monkeypatch needed) and has_udf() == False.
"""

import collections
import fnmatch
import os
import pycdlib
from pycdlib import pycdlibexception
from pycdlib import udf as udfmod
from pycdlib import inode


def _tolerant_walk_udf_directories(self, extent_to_inode):
    """Drop-in replacement for PyCdlib._walk_udf_directories that treats an
    invalid/unparsable File Identifier Descriptor as end-of-directory
    padding instead of raising PyCdlibInvalidISO. This lets open() get past
    this disc's broken UDF tree; the resulting self.udf_root/etc. state is
    incomplete and should be discarded (see strip_udf) before any write().
    """
    part_start = self.udf_main_descs.partitions[0].part_start_location
    abs_file_entry_extent = part_start + self.udf_file_set.root_dir_icb.log_block_num
    self._seek_to_extent(abs_file_entry_extent)
    icbdata = self._cdfp.read(self.udf_file_set.root_dir_icb.extent_length)
    self.udf_root = udfmod.parse_file_entry(
        icbdata, abs_file_entry_extent,
        self.udf_file_set.root_dir_icb.log_block_num, None)

    udf_file_entries = collections.deque([self.udf_root])
    while udf_file_entries:
        udf_file_entry = udf_file_entries.popleft()
        if udf_file_entry is None:
            continue
        for desc in udf_file_entry.alloc_descs:
            abs_file_ident_extent = part_start + desc.log_block_num
            self._seek_to_extent(abs_file_ident_extent)
            self._cdfp.seek(desc.offset, 1)
            data = self._cdfp.read(desc.extent_length)
            offset = 0
            while offset < len(data):
                current_extent = (abs_file_ident_extent * self.logical_block_size + offset) // self.logical_block_size
                try:
                    file_ident, bytes_forward = udfmod.parse_file_ident(
                        data[offset:], current_extent, part_start, udf_file_entry)
                except pycdlibexception.PyCdlibInvalidISO:
                    break  # rest of this extent treated as padding/garbage
                offset += bytes_forward
                if file_ident.is_parent():
                    udf_file_entry.track_file_ident_desc(file_ident)
                    continue
                abs_fee = part_start + file_ident.icb.log_block_num
                self._seek_to_extent(abs_fee)
                icbdata2 = self._cdfp.read(file_ident.icb.extent_length)
                try:
                    next_entry = udfmod.parse_file_entry(
                        icbdata2, abs_fee, file_ident.icb.log_block_num, udf_file_entry)
                except pycdlibexception.PyCdlibInvalidISO:
                    next_entry = None
                udf_file_entry.track_file_ident_desc(file_ident)
                if next_entry is None:
                    continue
                file_ident.file_entry = next_entry
                next_entry.file_ident = file_ident
                if file_ident.is_dir():
                    udf_file_entries.append(next_entry)
                else:
                    if next_entry.get_data_length() > 0:
                        abs_file_data_extent = part_start + next_entry.alloc_descs[0].log_block_num
                    else:
                        abs_file_data_extent = 0
                    if self.eltorito_boot_catalog is not None and abs_file_data_extent == self.eltorito_boot_catalog.extent_location():
                        self.eltorito_boot_catalog.add_dirrecord(next_entry)
                    else:
                        if abs_file_data_extent in extent_to_inode:
                            ino = extent_to_inode[abs_file_data_extent]
                            if next_entry.get_data_length() > ino.data_length:
                                ino.data_length = next_entry.get_data_length()
                        else:
                            ino = inode.Inode()
                            ino.parse(abs_file_data_extent, next_entry.get_data_length(), self._cdfp, self.logical_block_size)
                            extent_to_inode[abs_file_data_extent] = ino
                            self.inodes.append(ino)
                        ino.linked_records.append((next_entry, False))
                        next_entry.inode = ino


_PATCHED = False


def _ensure_patched():
    global _PATCHED
    if not _PATCHED:
        pycdlib.PyCdlib._walk_udf_directories = _tolerant_walk_udf_directories
        _PATCHED = True


def open_tolerant(path):
    """Open the ISO, tolerating this disc family's broken UDF tree."""
    _ensure_patched()
    iso = pycdlib.PyCdlib()
    iso.open(path)
    return iso


def strip_udf(iso):
    """Remove all (broken/incomplete) UDF state so iso.write() emits a
    clean ISO9660-only image. Call this before iso.write()."""
    iso._has_udf = False
    iso.udf_root = None
    iso.udf_file_set_terminator = None


# Note on paths: this disc's directory records have NO ';1' version suffix
# (e.g. use '/FILES.CFG' and '/DB/EEU.RD', not '/FILES.CFG;1'). Directory
# names are upper-cased in the ISO9660 tree (e.g. '/DB', '/CONFIG').


def get_file_extent(iso, iso_path):
    """Resolve `iso_path` (e.g. '/DB/EEUZ.MP0') to its single contiguous
    (absolute_byte_offset, length) run inside `iso`'s own underlying image
    file, via pycdlib's get_file_byte_extents(). This is what makes
    direct, no-extraction reading possible: every file checked on this
    disc family so far -- including the largest, EEUZ.MP0 (2.14GB, single
    run) and EEU.RD (590MB, single run) -- is stored as ONE contiguous
    extent, so a downstream reader can seek(offset) into the raw .ISO
    file exactly like it would into a standalone extracted copy. Raises
    ValueError if the file is NOT a single contiguous run (not observed
    on this disc family, but ISO9660 does allow multi-extent files over
    ~4GB, and UDF allows multiple allocation descriptors in general) --
    direct reading isn't safe for those without extra logic this function
    deliberately does not add, so such a file must be extracted instead.
    """
    extents = iso.get_file_byte_extents(iso_path=iso_path)
    if len(extents) != 1:
        raise ValueError(
            "%s is not a single contiguous extent on this disc (%d runs) "
            "-- direct in-ISO reading isn't supported for it, extract it "
            "instead" % (iso_path, len(extents)))
    return extents[0]


class IsoFileRef:
    """A lightweight reference to one file's contiguous byte range inside
    an ISO image -- a drop-in substitute for a plain path string accepted
    by every research/map_compressed_reader.py reader function
    (decompress_tile, read_directory, build_geo_index, etc.) via that
    module's own `_open()` helper (duck-typed against `.image_path`/
    `.offset`/`.length` here -- this class is intentionally plain data,
    with no file-handling logic of its own, so it stays a trivial,
    dependency-free descriptor; `_open()` in map_compressed_reader.py is
    what actually turns one into a seek()/read() file-like handle).
    Lets those functions address a MAP_COMPRESSED layer (or
    eeu.rd/.il/.iof/.cty/...) directly inside the big ISO -- NO
    extraction to a temp file first. Construct via open_file_ref() below
    rather than directly."""
    __slots__ = ("image_path", "offset", "length")

    def __init__(self, image_path, offset, length):
        self.image_path = image_path
        self.offset = offset
        self.length = length

    def __repr__(self):
        return "IsoFileRef(%r, offset=%d, length=%d)" % (
            self.image_path, self.offset, self.length)


def open_file_ref(iso, iso_path, image_path):
    """Convenience: resolve `iso_path`'s extent via get_file_extent() and
    wrap it as an IsoFileRef against the ISO's own underlying image file
    (`image_path` -- the same path passed to open_tolerant()) for direct,
    no-extraction reading via research/map_compressed_reader.py."""
    offset, length = get_file_extent(iso, iso_path)
    return IsoFileRef(image_path, offset, length)


def find_file(iso, filename_pattern, start_path="/"):
    """Walk `iso`'s own real directory tree (pycdlib's `iso.walk()`, real
    ISO9660 records -- no assumption about which project-variant folder a
    file lives under) looking for a filename matching `filename_pattern`
    (`fnmatch`-style, e.g. `"FHDD*.FLI"` -- this disc family's own
    per-market/per-variant folder layout is NOT uniform: EU discs share
    one `APPS/SILVER_1/RNSMIDEC/PROG/`, North America discs instead have
    a PER-VARIANT `APPS/SILVER_1/<NARBY|NARPQTO|...>/PROG/`, see
    research/swl_5238_reader.py's own "2 real North America `FHDD6.FLI`
    builds" section -- a hardcoded path would silently miss those).
    Case-insensitive (this disc family's own filenames are inconsistently
    upper/lower-cased across builds, e.g. `A_HDD.FRG` vs `A_HDD.frg`,
    already documented elsewhere in this project).

    Returns the first matching REAL absolute ISO path found (e.g.
    `/APPS/SILVER_1/NARBY/PROG/FHDD6.FLI`), or None if nothing matches
    anywhere under `start_path`. Stops at the first match -- multiple
    real matches can exist (every NAR project-variant folder has its own
    copy, all byte-identical, see the same section above), and the
    caller only ever needs one."""
    pattern = filename_pattern.upper()
    for dirpath, _dirs, files in iso.walk(iso_path=start_path):
        for fname in files:
            # pycdlib's own ISO9660 filenames carry a ';1' version suffix
            # (e.g. 'FHDD6.FLI;1') -- strip it before matching, same real
            # convention this module's own "Note on paths" above already
            # flags for the (suffix-free) Joliet-style paths it otherwise
            # uses everywhere else.
            bare = fname.split(";")[0]
            if fnmatch.fnmatch(bare.upper(), pattern):
                # Return `fname` AS `iso.walk()` GAVE IT, ';1' and all when
                # present -- do NOT strip it. This module's own "Note on
                # paths" above ("this disc's directory records have NO
                # ';1' version suffix") describes the MAP disc family
                # (`CD_8555.ISO`) specifically, not every disc: tested
                # directly against a real SWL/firmware disc
                # (`RNS510_5238_MOD_C3_C4.iso`, plain ISO9660, no Rock
                # Ridge/Joliet/UDF at all) and `get_file_byte_extents()`
                # only succeeds WITH the `;1` there -- confirmed real,
                # per-disc mastering difference, not a bug in either
                # convention. `bare` (above) is ONLY for case-insensitive
                # pattern matching, never for the returned path.
                sep = "" if dirpath.endswith("/") else "/"
                return dirpath + sep + fname
    return None


class _IsoFileRefHandle:
    """Binary-file-like view over exactly one IsoFileRef's byte range.
    Used by open_ref_or_path() below for callers that already depend on
    this module (rns510_core.py) -- research/*.py readers stay
    dependency-free and duck-type an equivalent handle locally instead
    (see e.g. map_compressed_reader.py's own `_open()`)."""
    __slots__ = ("_ref", "_f", "_pos")

    def __init__(self, ref):
        self._ref = ref
        self._f = None
        self._pos = 0

    def __enter__(self):
        self._f = open(self._ref.image_path, "rb")
        self._f.seek(self._ref.offset)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._f.close()
        return False

    def seek(self, pos, whence=0):
        if whence == 1:
            pos = self._pos + pos
        elif whence == 2:
            pos = self._ref.length + pos
        self._pos = pos
        self._f.seek(self._ref.offset + pos)
        return self._pos

    def read(self, size=-1):
        remaining = max(0, self._ref.length - self._pos)
        n = remaining if size is None or size < 0 else min(size, remaining)
        data = self._f.read(n)
        self._pos += len(data)
        return data


def open_ref_or_path(path):
    """Return a context-manager binary handle for `path` -- a plain
    filesystem path (str/os.PathLike, opened normally) or an IsoFileRef
    (opened as a windowed view over its own byte range inside the
    underlying ISO image, via _IsoFileRefHandle). Lets a caller like
    rns510_core.MapProject support direct-from-ISO reading (read_only
    mode) with no change to its own seek()/read() call sites."""
    if isinstance(path, IsoFileRef):
        return _IsoFileRefHandle(path)
    return open(path, "rb")


def size_of(path):
    """Byte length of `path` -- os.path.getsize() for a plain path, or
    an IsoFileRef's own already-known `.length` (no stat() possible)."""
    if isinstance(path, IsoFileRef):
        return path.length
    return os.path.getsize(path)
