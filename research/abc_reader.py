"""
abc_reader.py -- decodes eeu.abc, CRACKED this session: the "alphabet"
file (matching its own name) -- the full character repertoire used across
every language/script on this disc, plus a per-language table describing
which of 3 fixed "tier" flag-pairs each supported language has. Tiny
(897 bytes total) and never previously examined.

============================================================================
Layout
============================================================================
Standard 94-byte SIEMENS header, then:

    +0  uint16 LE  text_len   -- length in BYTES (not codepoints) of the
                                 UTF-8 character-repertoire string that
                                 follows
    +2  bytes      chars      -- text_len bytes, valid UTF-8, decoding to
                                 125 codepoints on the reference disc
    ...            language table -- a run of fixed 7-byte records,
                                 back-to-back to EOF (no trailer)

**Validated at full scale**: on the reference disc, `text_len` (199) bytes
of UTF-8 decode cleanly to exactly 125 codepoints (52 single-byte ASCII +
73 two-byte, +1 for a trailing NUL terminator = 199 bytes exactly), and
the remaining 602 body bytes (803 total body bytes - 2 - 199) parse as
EXACTLY 86 fixed 7-byte language-table records with ZERO leftover bytes.

============================================================================
The character repertoire
============================================================================
125 codepoints: space, basic punctuation (`&()+,-./:;'[]`), digits 0-9,
plain uppercase Latin A-Z, every accented/extended Latin uppercase letter
used by a European language on this disc (A-with-diacritics, C/D/E/L/N/
O/R/S/T/U/Y/Z-with-diacritics, AE/OE-style ligatures), the full uppercase
Cyrillic alphabet (Ё + А-Я), and a trailing NUL terminator. This is
exactly the uppercase glyph set every place/road name on this disc is
already known to use (README S3.1/S3.8 etc. -- names are consistently
uppercase) -- almost certainly what backs the on-screen spelling keyboard
(the firmware's own `AESpellerType` UI class, README S2.3) and/or the TTS
engine's input character validation, not itself a novel finding beyond
confirming the filename ("abc" = alphabet) describes its content exactly.

============================================================================
The language table -- CRACKED, validated at full scale
============================================================================
86 fixed 7-byte records, back-to-back:

    +0  bytes[3]  lang_code  -- 3-letter code, mostly real ISO 639-2/B
                                codes (bul, cze, eng, fre, ger, rus, ...)
    +3  uint8     flag_a
    +4  uint8     index      -- CRACKED: a plain ascending 1..86 counter,
                                record N's own position in the table
    +5  uint8     flag_b
    +6  uint8     index      -- always equal to +4's value (validated on
                                all 86 records, no exceptions)

52 distinct language codes, mostly real ISO 639-2/B abbreviations (`bul`
Bulgarian, `cze` Czech, `dan` Danish, `dut` Dutch, `eng` English, `fin`
Finnish, `fre` French, `ger` German, `gre` Greek, `hun` Hungarian, `ice`
Icelandic, `ita` Italian, `pol` Polish, `por` Portuguese, `rum` Romanian,
`rus` Russian, `spa` Spanish, `swe` Swedish, `tur` Turkish, `ukr`
Ukrainian, `wel` Welsh, `arm` Armenian, `aze` Azerbaijani, `baq` Basque,
`bel` Belarusian, `mne` Montenegrin, plus `und` = ISO 639-2's own real
"Undetermined" code) -- a handful of non-standard-looking 3-letter codes
also appear (`aaa`, `bet`, `grt`, `mat`, `rst`, `sct`, `ukt`) not
identified against any standard list, possibly disc/vendor-specific
extensions or script/dialect variants.

**`(flag_a, flag_b)` -- CRACKED behavior, meaning NOT cracked.** Exactly
3 distinct pairs occur in the whole file: `(2, 2)` (42 records), `(4, 8)`
(23 records), `(1, 5)` (21 records) -- no other combination appears.
32 of the 52 languages get MORE THAN ONE record (up to all 3 pairs, e.g.
`pol`/`scr` each have all three); the other 20 get exactly one. `(2, 2)`
is the most common single pair and the one most languages default to.
Plausible reading (not confirmed): a per-language "voice/TTS profile
tier" flag -- which of up to 3 distinct synthesis profiles/qualities are
available for that language -- but no independent evidence (e.g. cross-
referencing a real voice-file inventory) was available this session to
confirm it over any other 3-valued per-language property.

**UPDATE, a MUCH later session: `(4, 8)` CONFIRMED, directly, with real
embedded data -- it is the per-language PHONETIC/PRONUNCIATION-
TRANSCRIPTION index.** Found while investigating `mp0`'s own embedded
district-name string table (`research/map_compressed_reader.py`,
`extract_district_names()`): real name entries there are tagged with
this table's own `index` (e.g. `13^ZHK IZTOK` uses index 13 = `bul`).
A subset of entries near the Bulgaria/Turkey and Bulgaria/Greece border
tiles pair a plain name with a SECOND, syllable-broken phonetic string
using the NEXT language index up, joined by `$`, e.g. `80^UZUNHACI$
81^u|zun|ha|"dZ1` and `24^BULGARIA$25^bVl|"ge@|rI|@` (a real, correct
IPA-ish English pronunciation of "Bulgaria") and `24^TURKEY$25^"t3|ki`
(real English "Turkey"). Cross-referencing the index PAIRS used against
this file's own table: `tur` is `(80,81)` = `(1,5)`+`(4,8)`; `eng` is
`(24,25)` = `(2,2)`+`(4,8)`; `gre` is `(38,39)` = `(1,5)`+`(4,8)`;
`bul` is `(13,14)` = `(1,5)`+`(4,8)` (index 14 itself not directly
observed populated in the sample checked, but the SAME flag pattern).
**`(4, 8)` is confirmed, directly and repeatedly, as the phonetic/
pronunciation-transcription slot for whichever language it's paired
with** -- not a guess anymore. `(1, 5)` and `(2, 2)` both serve as
"plain display name" slots (confirmed via real, independently-decoded
name entries using both, e.g. `24^SOFIA AIRPORT CENTER` at `eng`'s
`(2,2)` index) -- which of the two a given language gets, and whether
they differ in any other way, is still open. Full writeup, including
the district-name-table discovery this rode in on:
`research/map_compressed_reader.py`'s `decode_topology()` docstring.

============================================================================
Practical use
============================================================================
`read_abc(path)` returns (chars, records) -- the decoded alphabet string
and the full language-table record list. This file is tiny (897 bytes),
safe to fully decode unconditionally.
"""

import struct

HEADER_SIZE = 94
RECORD_SIZE = 7


def read_abc(path):
    """Decode the whole eeu.abc file. Returns (chars, records) where
    `chars` is the decoded character-repertoire string and `records` is a
    list of (lang_code, flag_a, index, flag_b) tuples, one per language-
    table entry, in file order."""
    with open(path, "rb") as f:
        data = f.read()
    body = data[HEADER_SIZE:]
    text_len = struct.unpack_from("<H", body, 0)[0]
    chars = body[2:2 + text_len].decode("utf-8")

    pos = 2 + text_len
    records = []
    while pos + RECORD_SIZE <= len(body):
        code = body[pos:pos + 3].decode("ascii")
        flag_a, index, flag_b, index2 = body[pos + 3:pos + 7]
        assert index == index2, "the two 'index' bytes must always match"
        records.append((code, flag_a, index, flag_b))
        pos += RECORD_SIZE
    return chars, records
