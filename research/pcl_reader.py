"""
pcl_reader.py -- decodes eeu.pcl, IDENTIFIED this session: genuinely
empty on this disc (94 bytes, header only, zero body), with its real
name and purpose confirmed not from its own bytes (there are none to
examine) but from the disc's own plain-text `files.cfg` (disc root, not
part of the `db/` compressed-data model): file id 27, extension `pcl`,
compressionType 0 (NOT_COMPRESSED, matching the real file -- no
`eeuz.pcl` exists), comment "phoneme cluster list".

============================================================================
The file itself -- fully characterized, nothing left to decode
============================================================================
94-byte header (aff_reader.decode_not_compressed_header()), zero body
bytes -- confirmed directly, not inferred: file size is exactly 94, and
bytes[90:94] (`total_size`) also reads 94, an EXACT match to the header's
own size (this is *not* one of the 2 known exceptions -- eeu.iof/eeu.mod
-- that store the body size instead of the header-inclusive total).
bytes[86:88] (`record_count_lo16`) reads 0, consistent. bytes[84:86]
(`file_type`) reads 48 -- confirmed NOT the same numbering scheme as
`files.cfg`'s own fileId (e.g. eeu.rd's header `file_type` is 4, but
`files.cfg` assigns it fileId 0 -- two independent numbering schemes,
never cross-checked against each other before this file).

============================================================================
Why eeu.mod (research/mod_reader.py) couldn't identify this file
============================================================================
eeu.mod's 1,605-string schema dump has no table block for `eeu.pcl` at
all (re-confirmed here: every `pcl` occurrence in the file is a *prefix*
inside compound field names -- `pcl_cnt`, `maxPclId`, `pcl_dir`,
`pcl_hndl_list`, `pcl_hndl`, `pcl_offs`, `max_pcl_id`, `pcl_handle` -- all
belonging to the UNRELATED "Ordinary Map File" MAP_COMPRESSED tile
schema, where "parcel" is an internal spatial-subdivision/index concept
for locating shapes inside a tile. No standalone NUL-delimited `pcl`
token exists anywhere in eeu.mod.

============================================================================
The real answer: the disc's own files.cfg
============================================================================
`files.cfg` is a literal fileId -> extension -> compressionType ->
one-line-comment table for all 39 logical file types the database
*format* supports (`numFileIds = 39`) -- not just the ~30-odd this
specific EU-East disc actually populates. Its entry for id 27:

    27 = pcl, 0, cached		# phoneme cluster list

This places eeu.pcl in the same phonetic/TTS-support family as eeu.abc
(character repertoire), eeuz.pca (phoneme catalog -- id 26, immediately
before pcl in the table), eeuz.pct (phoneme CITY list -- id 28,
immediately after), and eeuz.prd (phoneme ROAD list -- id 29): a
"phoneme cluster" is a standard TTS/phonetics term for a grouped sequence
of phonemes (e.g. a syllable onset/coda consonant cluster), so this
file's role was almost certainly a lookup table of valid/known phoneme
clusters for the TTS engine's own pronunciation or syllabification rules
-- conceptually adjacent to, but distinct from, eeuz.pca's catalog of
individual phonemes. Not independently confirmed against real content
(there is none on this disc to check).

Cross-checking files.cfg further also surfaced 3 file-id entries this
project had never encountered on disc at all: `7 = ptp` ("point types"),
`15 = pdx` ("poi index file"), `16 = pti` ("point types international")
-- none of eeu.ptp/eeu.pdx/eeu.pti/eeuz.ptp/eeuz.pdx/eeuz.pti exist
anywhere under db/ on this disc, not even as empty 94-byte placeholders
like eeu.pcl/.pmp/.pol/.pot -- a real distinction between "declared by
the format, file not even created this release" (ptp/pdx/pti) and
"declared, file created but left empty" (pcl/pmp/pol/pot). Not pursued
further this session.

============================================================================
Bottom line
============================================================================
eeu.pcl's identity is now fully established straight from the disc's own
authoring metadata, not inference -- a real, named, NOT_COMPRESSED
"phoneme cluster list" table the map-authoring tool simply never
populated for this specific EU East V17 release. There is no byte-level
format left to reverse-engineer.
"""

from research.aff_reader import decode_not_compressed_header, HEADER_SIZE

FILES_CFG_ID = 27
FILES_CFG_COMMENT = "phoneme cluster list"


def read_pcl(path):
    """Decode eeu.pcl: returns (header_fields, body_bytes). On the
    reference disc, body_bytes is empty (b"") -- the file is exactly the
    94-byte header and nothing else."""
    with open(path, "rb") as f:
        data = f.read()
    return decode_not_compressed_header(data), data[HEADER_SIZE:]


def is_empty_placeholder(path):
    """True if this eeu.pcl is a bare 94-byte header with no body, same
    check used to confirm the reference disc's copy is unpopulated."""
    header_fields, body = read_pcl(path)
    return len(body) == 0 and header_fields["record_count_lo16"] == 0
