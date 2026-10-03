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
   Several decode to the confirmed real screen resolution, 800x480
   (e.g. real per-brand "Software update" splash screens: SEAT, Skoda).
   Not every GIF-shaped region decodes cleanly (interlacing/variant
   LZW flavors this reader doesn't special-case) -- callers should
   expect a mix of successes and skipped failures, not 100% recovery.

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


def find_embedded_images(data: bytes, window: tuple = (20_000, 50_000, 300_000, 1_000_000)):
    """Scan `data` for real embedded raster images. Currently only GIF
    is implemented (its 6-byte magic is long enough that every hit is
    real; PNG/BMP/JPEG signatures were tried and found to be
    essentially all coincidental collisions in this firmware -- not
    worth the false-positive rate). For each real GIF signature, tries
    increasingly large byte windows and lets Pillow decode it (Pillow
    reads only as many bytes as the real image data needs; the window
    is just an upper bound to slice from the full file). Returns an
    `ImageInfo` for every one that decodes successfully; GIFs that fail
    to decode (a real but unsupported LZW/interlacing variant) are
    silently skipped, not an error -- callers should not expect 100%
    recovery.

    Requires Pillow (`pip install Pillow`) -- imported lazily so this
    module can still be used for class-path/class-file discovery
    without it installed.
    """
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None  # these are real, known-small (<=800x480) images

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
                chunk = data[idx:idx + w]
                try:
                    candidate = Image.open(io.BytesIO(chunk))
                    candidate.load()
                    img = candidate
                    break
                except Exception:
                    continue
            if img is not None:
                results.append(ImageInfo(
                    offset=idx, format="GIF", width=img.size[0], height=img.size[1],
                    image=img.convert("RGB"),
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
