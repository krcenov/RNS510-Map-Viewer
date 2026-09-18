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
