"""
speech_reader.py -- documents `speech/` (disc root, not under `db/`):
the actual TEXT-TO-SPEECH ENGINE resources -- as opposed to the
phoneme/pronunciation DATA this project already extensively cracked
(`eeu.abc`, `eeuz.pca`, `eeuz.prd`, `eeuz.pct`, `eeu.pcl`). CRACKED at
the "what is this and who made it" level via real, readable embedded
metadata; the actual voice/synthesis binary formats are proprietary
third-party formats, NOT decoded.

Found via `config/create_cd` (research/create_cd_reader.py). Sourced
from a DIFFERENT, much OLDER internal server path than the map data
itself (`\\\\rbfs02p2\\did02377\\db1\\db\\a3\\speech\\vw\\20061102\\...`,
dated 2006) -- a long-lived, slowly-updated shared speech-resource
component reused across many map releases, not rebuilt per-disc.

============================================================================
`SpeechRes.xml` -- CRACKED (plain, readable XML)
============================================================================
A real resource-deployment manifest, not proprietary: lists, per
`<language>` (`deDE`, `enGB`, `csCZ`, `esES`, `frFR`, `itIT`, `nlNL`,
`ptPT` -- matching the 8 `parts/uvo_*.zip` files exactly), which ZIP
part provides it, plus real user-data file-mask patterns under
`data/speech/` (`recog/*/SpeakerProfiles/*/*.cfg`,
`recog/*/SpeakerProfiles/*/*.voc`) -- confirming this head unit supports
real SPEECH RECOGNITION with per-user trainable speaker profiles, not
just speech OUTPUT (TTS).

============================================================================
`parts/uvo_<locale>_01.zip` (8 files, ~9-13.5MB each) -- CRACKED
(archive listing + all embedded text/header metadata); voice binary
formats NOT decoded
============================================================================
Standard ZIP archives (`zipfile` opens them directly), each containing:

    data/speech/synth/kj0ca0b16_0.pil   -- ~4.8MB, proprietary binary
    data/speech/synth/svox.bin          -- ~6.3MB, proprietary binary
    data/speech/synth/svoxppb0.txt      -- 81 bytes, plain text
    data/speech/synth/SVOXKEYS.txt      -- 143 bytes, plain text
    data/speech/uvo/<locale>/Fem_1_32/VSI1/vsi.img  -- ~5.3MB, proprietary binary

**Confirms the real TTS engine vendor is SVOX** (SVOX AG, a real,
well-known commercial speech-synthesis company later acquired by
Nuance/Cerence) -- `svox.bin`'s own header is plain ASCII: `OS VxWorks
PLANG 1 DAY 1 MONTH 1 YEAR 1970 FIXADDR 0 FILETYPE BIN MAJVERS 3`.
**This is the first confirmation in this whole project of the actual
embedded real-time OS**: VxWorks (a real, widely-used automotive/
embedded RTOS) -- previously only a PowerPC native code REGION was
known from the firmware investigation (README S2.4), not the OS running
on it.

**`SVOXKEYS.txt` is a real license-key string, dated and attributed**:
`P 10 6 2005 AS 3.0 Siemens_VDO CP2 9 DABFSNIPC` (followed by a long
key/checksum string) -- directly confirms Siemens VDO licensed SVOX's
engine on 10 June 2005, tying this whole speech subsystem to the same
"Siemens VDO" corporate lineage already established from the firmware's
own `vdo.nav.*` package namespace (README S2.5) and `eeu.mod`/
`EDB/POI/POI.DB3`'s own `Arriba`/`arriba2` codebase identity
(research/poi_db_reader.py).

`svoxppb0.txt` is a small, real text-normalization rule file (`WORD
"_" ""`, etc. -- defines how punctuation/special characters are
silenced by the synthesizer, "ppb" plausibly "punctuation/pre-
processing bank").

**`vsi.img`'s own header is also plain, readable text**: `vsii` magic +
`UTF-8` encoding + a real per-locale voice identifier (`enGBFemale`) +
named SOUND EVENTS (`beep`, `navi_specific`, `tone_error`,
`tone_sds_error`) alongside an `mp4`-tagged audio container reference --
confirming this ZIP bundles system TONES/BEEPS together with the actual
synthesized-voice audio data, not pure TTS output alone.

None of `kj0ca0b16_0.pil`/`svox.bin`/`vsi.img`'s own binary payload
(voice models, phoneme inventories, compiled audio) was reverse-
engineered -- these are real, proprietary third-party (SVOX) formats;
cracking them was not attempted this session.

============================================================================
Practical use
============================================================================
`SpeechRes.xml` and `svoxppb0.txt`/`SVOXKEYS.txt` are plain text, read
directly. The `parts/uvo_*.zip` files are standard ZIP archives -- use
Python's built-in `zipfile` module directly; no custom parsing code is
provided or needed for the archive structure itself.
"""
