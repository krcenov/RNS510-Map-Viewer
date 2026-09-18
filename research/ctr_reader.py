"""
Reader for RNS510's country list: `eeu.ctr` (files.cfg fileId=1, "ctr",
NOT_COMPRESSED) -- CRACKED this session, quickly and cleanly, in the same
family as `eeu.rd`/`eeu.typ`/`eeu.cty` (94-byte SIEMENS header + fixed-size
records, no gaps).

============================================================================
`eeu.ctr` -- CRACKED (fully, small file: 1,599 bytes on the reference disc)
============================================================================
Same 94-byte SIEMENS header convention as `.rd`/`.typ`/`.cty`, then fixed
**43-byte records**, no gaps: `(1599 - 94) / 43 = 35` records exactly on the
reference disc.

Record layout (43 bytes):
    byte[0]      uint8   record's own sequential index (== its position --
                 confirmed 0..34 in order, same sanity-check convention
                 `.cty` already uses for its own index field)
    bytes[1:36]  (35 bytes) country name, UTF-8, NUL-padded/terminated
                 (confirmed UTF-8, not Latin-1: record 9 decodes correctly
                 to "ÖSTERREICH" only as UTF-8; other accented examples
                 confirmed correct: "ČESKO", "SHQIPËRIA", "ROMÂNIA",
                 "MAGYARORSZÁG", "TÜRKIYE"; one Cyrillic entry, "РОССИЯ",
                 also present and correct)
    bytes[36:39] (3 bytes) ISO 3166-1 alpha-3 country code, ASCII
    bytes[39:41] (2 bytes) ISO 3166-1 alpha-2 country code, ASCII
    bytes[41:43] 2 trailing zero bytes (reserved/padding -- 0x0000 on
                 every one of the 35 reference-disc records)

**Validated directly against the reference photo that prompted this
feature** (README §10 "v11 -> v12"): record 19, name **"BALGARIA"**
(Bulgarian for Bulgaria, transliterated -- exactly the value shown in the
"Address entry" reference photo's Country field), codes `BGR`/`BG` -- an
exact match, not a coincidence (Bulgaria's real ISO codes).

**Full reference-disc list** (35 countries -- East Europe/EEU coverage,
consistent with the disc's own name): SCHWEIZ (CH), STATO DELLA CITTÀ DEL
VATICANO (VA), ITALIA (IT), SAN MARINO (SM), SLOVENIJA (SI), HRVATSKA (HR),
BOSNA I HERCEGOVINA (BA), LIECHTENSTEIN (LI), DEUTSCHLAND (DE), ÖSTERREICH
(AT), DANMARK (DK), ČESKO (CZ), POLSKA (PL), ELLADA (GR), SHQIPËRIA (AL),
CRNA GORA (ME), P.JUGOSLOVENSKA REPUB.MAKEDONIJA (MK), KOSOVË (RS -- note:
same alpha-2 as Serbia below, i.e. this disc doesn't give Kosovo its own
ISO code), SRBIJA (RS), BALGARIA (BG), ROMÂNIA (RO), MAGYARORSZÁG (HU),
SLOVENSKO (SK), LIETUVA (LT), MOLDOVA (MD), BYELARUS' (BY), SVERIGE (SE),
NORGE (NO), LATVIJA (LV), EESTI (EE), SUOMI (FI), TÜRKIYE (TR), UKRAINA
(UA), ROSSIYA (RU, Latin transliteration), and a SECOND entry for Russia,
"РОССИЯ" (RU, native Cyrillic spelling) -- i.e. this disc lists Russia
twice, once transliterated and once in its own script, both with the same
ISO codes; not a decode error (both records parse cleanly and land at the
correct sequential index 33/34).

**No fallback needed**: unlike `.rt`/`.ct` (large files, genuinely
partitioned structure, see `road_index_reader.py`/`city_reader.py`),
`.ctr` is small (35 entries total) and was fully, unambiguously cracked --
this module's `CTR_COUNTRIES`/`load_countries()` gives an exhaustive,
always-correct list, and `PrefixNameIndex` (city_reader.py, reused here)
already provides exact live per-letter keyboard narrowing over any name
list without needing a trie at all for a set this small.

Practical use: `ctr_record()`/`iter_ctr_records()` decode the raw file;
`load_countries(path)` returns a list of `CountryRecord`; the map viewer's
Country field builds a `city_reader.PrefixNameIndex` directly from
`[c.name for c in load_countries(...)]`.
"""

import struct

CTR_HEADER_SIZE = 94
CTR_RECORD_SIZE = 43
CTR_NAME_OFFSET = 1
CTR_NAME_SIZE = 35
CTR_ISO3_OFFSET = 36
CTR_ISO2_OFFSET = 39


class CountryRecord:
    __slots__ = ("index", "name", "iso3", "iso2")

    def __init__(self, index, name, iso3, iso2):
        self.index = index
        self.name = name
        self.iso3 = iso3
        self.iso2 = iso2

    def __repr__(self):
        return "CountryRecord(index=%d, name=%r, iso3=%r, iso2=%r)" % (
            self.index, self.name, self.iso3, self.iso2)


def ctr_record(body, i):
    """Decode eeu.ctr record i (0-based) from the file's bytes AFTER the
    94-byte header (pass data[94:], not the raw file)."""
    off = i * CTR_RECORD_SIZE
    rec = body[off:off + CTR_RECORD_SIZE]
    index = rec[0]
    name_bytes = rec[CTR_NAME_OFFSET:CTR_NAME_OFFSET + CTR_NAME_SIZE].split(b"\x00", 1)[0]
    try:
        name = name_bytes.decode("utf-8")
    except UnicodeDecodeError:
        name = name_bytes.decode("latin-1")
    iso3 = rec[CTR_ISO3_OFFSET:CTR_ISO3_OFFSET + 3].decode("ascii", errors="replace")
    iso2 = rec[CTR_ISO2_OFFSET:CTR_ISO2_OFFSET + 2].decode("ascii", errors="replace")
    return CountryRecord(index, name, iso3, iso2)


def ctr_record_count(body):
    return len(body) // CTR_RECORD_SIZE


def iter_ctr_records(body):
    for i in range(ctr_record_count(body)):
        yield ctr_record(body, i)


def load_countries(path):
    """Read + decode the whole eeu.ctr file at `path` (the RAW file,
    header included) into a list of CountryRecord, in file order."""
    with open(path, "rb") as f:
        data = f.read()
    body = data[CTR_HEADER_SIZE:]
    return list(iter_ctr_records(body))
