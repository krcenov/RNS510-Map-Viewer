"""
cal_reader.py -- decodes eeu.cal, CRACKED this session (fully, no open
fields left): a multi-language name catalog for countries and continents
("Europe"), cross-referenced against both eeu.ctr (country identity) and
eeu.abc (which language each name is in). Previously entirely unexamined
-- only a candidate record size (48 bytes) had been derived from the
shared NOT_COMPRESSED header fields (aff_reader.py), not the content.

============================================================================
Record format -- CRACKED, validated at FULL scale (every one of 484
records, zero exceptions)
============================================================================
94-byte header (the record count, 484, comes straight from its own
now-cracked bytes[86:88] field -- see aff_reader.py), then 484 fixed
48-byte records, back-to-back:

    +0   uint16 LE  country_id   -- see below
    +2   uint8      is_continent -- 1 for the "Europe" pseudo-entries
                                     (country_id 0), 0 for every real
                                     country
    +3   uint8      lang_index   -- matches eeu.abc's own per-language
                                     "index" field (1-86) EXACTLY
    +4   bytes[40]  name         -- NUL-padded, the country/continent's
                                     name in that language, natural word
                                     order (not `.prl`'s `;`-demoted
                                     sort-key form)
    +44  bytes[4]   0xFFFFFFFF   -- constant on every single record
                                     checked (484/484) -- an unused/
                                     reserved sentinel, not real content

============================================================================
`country_id` -- CRACKED: alphabetical rank by ISO 3166-1 ALPHA-3 code
============================================================================
`country_id` 0 is reserved for 2 "Europe" pseudo-entries (`EUROPE` in
English, `ЕВРОПА` in Russian) -- not tied to any real eeu.ctr row.
`country_id` 1-34 are the disc's 34 UNIQUE alpha-3 codes (eeu.ctr,
README S3.11-adjacent, has 35 rows but lists Russia TWICE -- once
transliterated, once in Cyrillic, both `RUS` -- so 34 unique codes),
in exactly their ALPHABETICAL order: 1=ALB (Albania), 2=AUT (Austria),
3=BGR (Bulgaria), 4=BIH (Bosnia and Herzegovina), 5=BLR (Belarus),
6=CHE (Switzerland), 7=CZE, 8=DEU, 9=DNK, 10=EST, 11=FIN, 12=GRC, 13=HRV,
14=HUN, 15=ITA, 16=KOS, 17=LIE, 18=LTU, 19=LVA, 20=MDA, 21=MKD, 22=MNE,
23=NOR, 24=POL, 25=ROU, 26=RUS, 27=SMR, 28=SRB, 29=SVK, 30=SVN, 31=SWE,
32=TUR, 33=UKR, 34=VAT (Vatican City).

**Validated exhaustively, not sampled**: every one of the 35 distinct
`country_id` groups (0 through 34) in the real file was inspected in
full, and every single multi-language name in every group is a genuine,
correct real-world name for that exact country in some real language --
e.g. group 8 (Germany) contains `ALEMANHA` (Portuguese), `ALEMANIA`
(Spanish), `ALLEMAGNE` (French), `ALMANYA` (Turkish), `DEUTSCHLAND`
(German), `DUITSLAND` (Dutch), `GERMANIA` (Italian), `GERMANIYA`
(transliterated Russian/Bulgarian), `GERMANY` (English), `NEMECKO`/
`NĚMECKO` (Slovak/Czech), `NIEMCY` (Polish), `TYSKLAND` (Scandinavian) --
13 entries, all genuinely Germany, in 13 different languages. Group 21
(North Macedonia) alone has 40 entries, reflecting that country's real
historical naming controversy (many entries literally spell out "former
Yugoslav Republic of Macedonia" in different languages, e.g. `FORMER
YUGOSLAV REP.OF MACEDONIA`, `EHEMALIGE JUGOSLAW.REP.MAZEDONIEN`,
`B.JUGOSLOWIANSKA REPUB.MACEDONII`).

This `country_id` numbering is a THIRD, independent country-numbering
scheme on this disc -- distinct from both `eeu.ctr`'s own arbitrary row
order (README S3.11-adjacent: `SCHWEIZ`/Switzerland is row 0) and
`eeu.cty`'s own empirically-resolved `country_tag` field (README S3.8,
e.g. 375 for Albania) -- neither of which matches `eeu.cal`'s `country_id`
at all. Simple alphabetical-by-ISO-alpha-3 needed no cross-file lookup to
discover once `eeu.ctr`'s own alpha-3 field (already cracked) was sorted
and compared directly against the empirically-observed `eeu.cal` groups.

============================================================================
`lang_index` -- CRACKED: eeu.abc's own per-language index
============================================================================
Confirmed directly by cross-referencing real translations against
`eeu.abc`'s language table (README S3.11-adjacent, `research/
abc_reader.py`): `lang_index=24` ('eng') on the `EUROPE`/`ALBANIA`/
`AUSTRIA` English entries; `lang_index=66` ('rus') on the Cyrillic
`ЕВРОПА` entry; `lang_index=30` ('fre') on `ALBANIE`/`AUTRICHE`/
`ALLEMAGNE`; `lang_index=78` ('swe') on `ALBANIEN`; `lang_index=22`
('dut') on `ALBANIË`; `lang_index=80` ('tur') on `ARNAVUTLUK`
(Albania in Turkish); `lang_index=59` ('pol') on the Polish Macedonia
entry -- every cross-check confirmed correct, no exceptions found.

============================================================================
Practical use
============================================================================
`read_cal(path)` returns every record as (country_id, is_continent,
lang_index, name). Combine with `abc_reader.read_abc()`'s language table
(index -> language code) to get a real (country, language) -> localized
name lookup -- e.g. for the map viewer's Address Entry country list to
show a localized country name instead of whatever single name
`eeu.ctr` itself stores.
"""

import struct

HEADER_SIZE = 94
RECORD_SIZE = 48


def read_cal(path):
    """Decode the whole eeu.cal file. Returns a list of
    (country_id, is_continent, lang_index, name) tuples, one per record,
    in file order. `name` is bytes (mixed ASCII/UTF-8 depending on
    language -- decode with errors='replace' or per-language as needed)."""
    with open(path, "rb") as f:
        data = f.read()
    body = data[HEADER_SIZE:]
    n = len(body) // RECORD_SIZE
    records = []
    for i in range(n):
        rec = body[i * RECORD_SIZE:(i + 1) * RECORD_SIZE]
        country_id = struct.unpack_from("<H", rec, 0)[0]
        is_continent = rec[2]
        lang_index = rec[3]
        name = rec[4:44].split(b"\x00", 1)[0]
        records.append((country_id, is_continent, lang_index, name))
    return records
