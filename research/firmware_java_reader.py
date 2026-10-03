"""
Reader for the real embedded Java application layer inside `FHDD6.FLI`
(the APPS/RNSMIDEC firmware image documented on the wiki's "Firmware
Reversing" / "Embedded Java Application Layer" pages). The real JVM is
Wind River's Jeode EVM (licensed from Insignia Solutions), PersonalJava
1.1.1 / EmbeddedJava 1.0.3 compatible, running real OSGi bundles.

Everything here scans the firmware bytes directly, at call time -- no
pre-extracted assets are shipped in this repo. Callers (e.g. a viewer
GUI) should load `FHDD6.FLI` themselves and pass its bytes in.

Three independent things can be recovered straight from the raw bytes:

1. Real Java class-path strings (`find_java_class_paths`) -- JVM
   constant-pool UTF8 entries referencing class names, shaped like
   `Lvdo/rns/app/...;` or `Lwdg/...;`. ~2,800 distinct paths found on
   the reference firmware; these are just names (confirms what classes
   exist and the package architecture), not executable code.

2. Real, standalone `.class` files (`find_class_files`) -- a small
   number of real classes (interfaces, enums, tiny stub
   implementations) survive as genuine, individually-parseable
   `CAFEBABE`-prefixed class files (17 on the reference firmware). The
   bulk of the ~2,800-class application does NOT survive this way --
   it's almost certainly pre-linked/"romized" into Jeode's own
   (undocumented) bundle format, which this module does not attempt to
   crack. `find_class_files` parses the REAL class-file structure
   (constant pool, fields, methods, attributes) to find each class's
   true end -- class files don't declare their own length -- so it
   only returns genuinely well-formed classes, not the much larger set
   of coincidental 4-byte `CAFEBABE` collisions elsewhere in the file.

3. Real embedded raster images (`find_embedded_images`) -- the unit's
   own real UI screens/assets, stored as plain GIF files (PNG/BMP
   signature hits in this file are all coincidental collisions, not
   real images -- GIF's 6-byte magic is long enough to avoid that).
   8 of 11 real `GIF87a`/`GIF89a` hits decode on the reference
   firmware, all to the confirmed real screen resolution, 800x480
   (real per-brand "Software update" splash screens). Several of these
   needed a recovery fallback (`_recover_gif_with_corrected_gct`) for a
   real, recurring corruption -- a wrong color-table-size field in the
   header -- the same general kind of localized few-byte corruption
   documented for the streamed Java classes below, just in a different
   format; without it only 4 of 11 decoded. The remaining 3 full-screen
   failures have a deeper corruption in the actual compressed LZW data,
   not just the header, and 2 small (100x50) icon-shaped hits remain
   unrecovered -- callers should expect a mix of successes and skipped
   failures, not 100% recovery.

4. Real classes embedded as streamed ZIP/JAR entries
   (`find_streamed_zip_classes`) -- separately from (2), a real OSGi
   bundle packaging mechanism exists (`vdo/rio/impl/fwk/BundleManifest`/
   `Archive` classes reference real `META-INF/MANIFEST.MF` and standard
   OSGi manifest headers), and some class entries survive as genuine
   streamed (general-purpose flag bit 3 set, sizes deferred) DEFLATE-
   compressed ZIP local file header + data pairs, independent of the
   plain standalone class files in (2) -- a validated 7 found on the
   reference firmware this way, including real implementation classes
   (not just tiny interfaces/enums) like `DefaultBTAudioPlayer.class`.
   **Only some of these currently decompile correctly** (1 of 7 on the
   reference firmware) -- the DEFLATE stream reaches a structurally
   valid end-of-stream (`eof=True`) for all of them, but several
   produce a class file CFR can't parse (corrupted-looking constant
   pool / bytecode). Rigorously ruled out, in order: a shared preset
   dictionary (output is byte-identical with several real candidate
   dictionaries AND with none at all); a wrong wbits/offset (only raw
   deflate at the exact computed offset decodes at all); a decoder
   implementation bug (Python's zlib and Java's own
   java.util.zip.Inflater, run on the exact same compressed bytes,
   produce byte-for-byte identical output); and a premature BFINAL bit
   (this project's own earlier working theory) -- a from-scratch,
   instrumented, bit-level raw-DEFLATE decoder (independent of
   zlib/Inflater, logging every block header and LZ77 symbol) shows
   every one of these entries is exactly ONE single, legitimately
   BFINAL=1 block from the first 3 bits of the stream -- there is no
   hidden 2nd block, and decoding itself is 100% clean and in-bounds
   end to end. The corruption is already present inside the correctly
   -decompressed bytes themselves (e.g. two literal bytes 'e', 0x00
   appearing mid-string in an otherwise perfectly real UTF8 class-path
   constant), which a lossless decoder could only emit if they were
   genuinely present in the compressor's input -- ruling out a
   decompression bug entirely. It's reproducible byte-for-byte across
   unrelated firmware builds (same class, same corrupted bytes, same
   offset, in both `5238_MOD_C3_C4` and the much older `3890` release),
   ruling out storage bit-rot. The damage is small and localized, not
   systemic -- e.g. Mp3ActionEvent.class's entire 30-entry constant
   pool decodes perfectly; CFR's out-of-range constant-pool-index
   errors (seen in the 15,000-30,000 range across different classes)
   trace to inside the method bytecode that follows, not the constant
   pool, hinting these may be leftover references into Jeode's larger
   shared/global romizer string table rather than random noise -- see
   the wiki page for the full diagnosis and a concrete next step. Like
   `find_class_files`, raw `PK\x03\x04` signature hits are
   mostly coincidental collisions (123 raw hits; loosening every filter
   still only finds 7 that fully validate, though checking the OTHER
   30 candidates' names shows they're real too -- e.g.
   `ClimateControlAdapter.class`, `DvdPlayer.class` -- just blocked by
   this same decompression issue) -- this function validates each
   candidate (plausible filename bytes, successful immediate
   decompression) before returning it, the same discipline used for
   class-file recovery.

Usage:
    with open("FHDD6.FLI", "rb") as f:
        data = f.read()

    classpaths = find_java_class_paths(data)
    classes = find_class_files(data)          # list[ClassFileInfo]
    images = find_embedded_images(data)        # list[ImageInfo], .image is a PIL Image
"""

import io
import re
import struct
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# 1. Real Java class-path strings
# ---------------------------------------------------------------------------

_CLASSPATH_RE = re.compile(rb"L(?:vdo|wdg)/[A-Za-z0-9_/]{3,80}")


def find_java_class_paths(data: bytes) -> set[str]:
    """Scan `data` for real JVM class-signature strings (`Lvdo/...`/
    `Lwdg/...`, the 2 real top-level packages this application uses).
    Returns a set of distinct path strings (without the leading `L`),
    e.g. `"vdo/rns/app/nav/std/..."`. Pure string-level discovery --
    does not imply the class's own bytecode is recoverable (most
    aren't -- see `find_class_files`)."""
    return {m.group(0)[1:].decode("ascii") for m in _CLASSPATH_RE.finditer(data)}


# ---------------------------------------------------------------------------
# 2. Real, standalone .class files
# ---------------------------------------------------------------------------

# tag -> fixed constant-pool entry size in bytes (after the 1-byte tag),
# excluding the variable-length Utf8 (tag 1) case handled separately.
_CONSTANT_SIZES = {
    7: 2, 9: 4, 10: 4, 11: 4, 8: 2, 3: 4, 4: 4, 5: 8, 6: 8, 12: 4,
    15: 3, 16: 2, 18: 4, 19: 2, 20: 2,
}


@dataclass
class ClassFileInfo:
    start: int
    end: int
    data: bytes
    major: int
    minor: int
    cp_count: int
    fields_count: int
    methods_count: int


class _ClassParseError(Exception):
    pass


def _parse_class_at(data: bytes, start: int) -> ClassFileInfo:
    pos = start

    def u1():
        nonlocal pos
        v = data[pos]
        pos += 1
        return v

    def u2():
        nonlocal pos
        v = struct.unpack_from(">H", data, pos)[0]
        pos += 2
        return v

    def u4():
        nonlocal pos
        v = struct.unpack_from(">I", data, pos)[0]
        pos += 4
        return v

    if data[pos:pos + 4] != b"\xca\xfe\xba\xbe":
        raise _ClassParseError("bad magic")
    pos += 4
    minor = u2()
    major = u2()
    if not (45 <= major <= 55):
        raise _ClassParseError(f"implausible major version {major}")

    cp_count = u2()
    i = 1
    while i < cp_count:
        tag = u1()
        if tag == 1:
            length = u2()  # already advances pos past the length field itself
            pos += length  # now skip the UTF8 payload on top
        elif tag in _CONSTANT_SIZES:
            pos += _CONSTANT_SIZES[tag]
            if tag in (5, 6):
                i += 1
        else:
            raise _ClassParseError(f"unknown constant pool tag {tag} at index {i}")
        i += 1

    pos += 2 + 2 + 2  # access_flags, this_class, super_class
    interfaces_count = u2()
    pos += 2 * interfaces_count

    def skip_attributes():
        nonlocal pos
        count = u2()
        for _ in range(count):
            pos += 2  # attribute_name_index
            length = u4()  # already advances pos past the length field itself
            pos += length  # now skip the attribute's own payload on top
        return count

    fields_count = u2()
    for _ in range(fields_count):
        pos += 2 + 2 + 2
        skip_attributes()

    methods_count = u2()
    for _ in range(methods_count):
        pos += 2 + 2 + 2
        skip_attributes()

    skip_attributes()

    return ClassFileInfo(
        start=start, end=pos, data=data[start:pos],
        major=major, minor=minor, cp_count=cp_count,
        fields_count=fields_count, methods_count=methods_count,
    )


def find_class_files(data: bytes, max_size: int = 2_000_000) -> list[ClassFileInfo]:
    """Scan `data` for every real, well-formed, standalone Java class
    file. Tries to parse a complete class structure at every
    `CAFEBABE` occurrence; most are coincidental 4-byte collisions and
    are silently discarded (they fail with an implausible version or
    an invalid constant-pool tag). Returns only genuinely well-formed
    classes, each `max_size` bytes or smaller."""
    magic = b"\xca\xfe\xba\xbe"
    results = []
    search_from = 0
    while True:
        idx = data.find(magic, search_from)
        if idx == -1:
            break
        search_from = idx + 1
        try:
            info = _parse_class_at(data, idx)
        except (_ClassParseError, struct.error, IndexError):
            continue
        if 0 < info.end - info.start <= max_size:
            results.append(info)
    return results


# ---------------------------------------------------------------------------
# 3. Real embedded images (GIF)
# ---------------------------------------------------------------------------

@dataclass
class ImageInfo:
    offset: int
    format: str
    width: int
    height: int
    image: object  # PIL.Image.Image, deferred import so this module has no hard PIL dependency


def _gif_header(data: bytes, idx: int):
    width, height, packed, bg, aspect = struct.unpack_from("<HHBBB", data, idx + 6)
    return width, height, packed, bg, aspect


def _recover_gif_with_corrected_gct(data: bytes, idx: int, width: int, height: int, packed: int,
                                     bg: int, aspect: int, search_span: int = 20_000):
    """Some real GIFs in this firmware have a corrupted Logical Screen
    Descriptor `packed` byte -- specifically a wrong global-color-table
    -size field (consistent with the same kind of localized few-bit
    corruption seen elsewhere in this firmware, e.g. in the streamed
    Java classes -- see this module's docstring item 4). The declared
    size claims more color-table bytes than are actually there, so the
    real image descriptor (`0x2C` + left=0,top=0,w=width,h=height --
    every real example here is a single full-screen frame) sits earlier
    than where the header says to look. This locates that real
    boundary by content instead of trusting the declared size, rebuilds
    a corrected header + real-length color table, and returns the fixed
    bytes (or None if no plausible image descriptor is found nearby)."""
    if not (packed >> 7) & 1:
        return None  # no global color table declared -- not this kind of corruption

    search_start = idx + 13
    found_desc_at = None
    for off in range(search_start, min(search_start + search_span, len(data) - 9)):
        if data[off] != 0x2C:
            continue
        left, top, w, h, _ipacked = struct.unpack_from("<HHHHB", data, off + 1)
        if left == 0 and top == 0 and w == width and h == height:
            found_desc_at = off
            break
    if found_desc_at is None:
        return None

    real_gct_bytes = found_desc_at - search_start
    if real_gct_bytes <= 0 or real_gct_bytes % 3 != 0:
        return None
    n_colors = real_gct_bytes // 3
    size_field = 0
    while 2 ** (size_field + 1) < n_colors:
        size_field += 1
    pad_bytes = (2 ** (size_field + 1) - n_colors) * 3

    new_packed = (1 << 7) | ((packed >> 4 & 7) << 4) | size_field
    header = data[idx:idx + 6] + struct.pack("<HHBBB", width, height, new_packed, bg, aspect)
    gct = data[search_start:found_desc_at] + b"\x00" * pad_bytes
    return header + gct + data[found_desc_at:]


def find_embedded_images(data: bytes, window: tuple = (20_000, 50_000, 300_000, 1_000_000)):
    """Scan `data` for real embedded raster images. Currently only GIF
    is implemented (its 6-byte magic is long enough that every hit is
    real; PNG/BMP/JPEG signatures were tried and found to be
    essentially all coincidental collisions in this firmware -- not
    worth the false-positive rate). For each real GIF signature, tries
    increasingly large byte windows and lets Pillow decode it (Pillow
    reads only as many bytes as the real image data needs; the window
    is just an upper bound to slice from the full file). If that fails,
    falls back to `_recover_gif_with_corrected_gct` -- a real, generic
    fix for one specific, recurring kind of corruption in this firmware
    (a wrong color-table-size field in the header), which alone doubled
    the number of real, full-screen splash images recovered from the
    reference firmware (4 -> 8 of 11 real `GIF89a`/`GIF87a` hits).
    Returns an `ImageInfo` for every one that decodes successfully;
    GIFs that still fail after that (a deeper, genuine corruption in
    the compressed LZW data itself, not just the header) are silently
    skipped, not an error -- callers should not expect 100% recovery.

    Requires Pillow (`pip install Pillow`) -- imported lazily so this
    module can still be used for class-path/class-file discovery
    without it installed.
    """
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None  # these are real, known-small (<=800x480) images

    def _try_decode(chunk: bytes):
        try:
            candidate = Image.open(io.BytesIO(chunk))
            candidate.load()
            return candidate
        except Exception:
            return None

    results = []
    for sig in (b"GIF87a", b"GIF89a"):
        search_from = 0
        while True:
            idx = data.find(sig, search_from)
            if idx == -1:
                break
            search_from = idx + 1
            img = None
            for w in window:
                img = _try_decode(data[idx:idx + w])
                if img is not None:
                    break
            if img is None:
                width, height, packed, bg, aspect = _gif_header(data, idx)
                fixed = _recover_gif_with_corrected_gct(data, idx, width, height, packed, bg, aspect)
                if fixed is not None:
                    img = _try_decode(fixed[:max(window)])
            if img is not None:
                results.append(ImageInfo(
                    offset=idx, format="GIF", width=img.size[0], height=img.size[1],
                    image=img.convert("RGB"),
                ))
    return results


# ---------------------------------------------------------------------------
# 4. Real classes embedded as streamed ZIP/JAR entries
# ---------------------------------------------------------------------------

@dataclass
class StreamedClassInfo:
    offset: int
    name: str
    data: bytes          # the decompressed bytes; starts with CAFEBABE
    fully_valid: bool     # True if this also parses as a complete, well-formed
                          # class file (see note below) -- some currently don't


def _is_plausible_zip_name(name_bytes: bytes) -> bool:
    if not name_bytes:
        return False
    try:
        s = name_bytes.decode("ascii")
    except UnicodeDecodeError:
        return False
    return all(32 <= ord(c) < 127 for c in s) and ("/" in s or "." in s)


def find_streamed_zip_classes(data: bytes, max_window: int = 1_000_000) -> list[StreamedClassInfo]:
    """Scan `data` for real classes stored as streamed (general-purpose
    flag bit 3 set, sizes deferred to a trailing data descriptor) DEFLATE
    ZIP entries -- see this module's own docstring, item 4, for the full
    story. Raw `PK\\x03\\x04` signature hits are mostly coincidental (not
    every one is a real local file header), so each candidate is
    validated: plausible filename bytes, successful immediate raw-DEFLATE
    decompression reaching a real end-of-stream, and a `CAFEBABE` magic
    number in the result. Returns one `StreamedClassInfo` per validated
    real entry -- `fully_valid` says whether the decompressed bytes ALSO
    parse as a complete class file (via the same parser `find_class_files`
    uses); several currently don't (see docstring item 4 for why) and are
    still returned (with `fully_valid=False`) since the entry and its
    real filename are themselves genuine findings even when the content
    isn't fully recovered yet."""
    import struct
    import zlib

    results = []
    search_from = 0
    while True:
        idx = data.find(b"PK\x03\x04", search_from)
        if idx == -1:
            break
        search_from = idx + 1
        try:
            (sig, ver, flags, method, mtime, mdate, crc32, comp_size, uncomp_size,
             name_len, extra_len) = struct.unpack_from("<IHHHHHIIIHH", data, idx)
        except struct.error:
            continue
        if not (0 < name_len <= 120) or not (0 <= extra_len <= 200):
            continue
        name_bytes = data[idx + 30:idx + 30 + name_len]
        if not _is_plausible_zip_name(name_bytes):
            continue
        if method != 8:
            continue  # only DEFLATE handled; method 0 (stored) not seen in practice here
        data_start = idx + 30 + name_len + extra_len
        d = zlib.decompressobj(-15)
        try:
            out = d.decompress(data[data_start:data_start + max_window])
            out += d.flush()
        except zlib.error:
            continue
        if not d.eof or out[:4] != b"\xca\xfe\xba\xbe":
            continue
        try:
            info = _parse_class_at(out, 0)
            fully_valid = info.end == len(out)
        except (_ClassParseError, struct.error, IndexError):
            fully_valid = False
        results.append(StreamedClassInfo(
            offset=idx, name=name_bytes.decode("ascii"), data=out, fully_valid=fully_valid,
        ))
    return results


if __name__ == "__main__":
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "FHDD6.FLI"
    with open(path, "rb") as f:
        data = f.read()

    paths = find_java_class_paths(data)
    print(f"real Java class-path strings: {len(paths)}")

    classes = find_class_files(data)
    print(f"real standalone .class files: {len(classes)}")

    images = find_embedded_images(data)
    print(f"real decodable embedded images: {len(images)}")
    for im in images:
        print(f"  offset=0x{im.offset:x} {im.width}x{im.height}")

    streamed = find_streamed_zip_classes(data)
    print(f"real streamed-ZIP classes: {len(streamed)} ({sum(s.fully_valid for s in streamed)} fully valid)")
    for s in streamed:
        print(f"  offset=0x{s.offset:x}  {s.name}  ({len(s.data)} bytes)  fully_valid={s.fully_valid}")
