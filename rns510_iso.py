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
