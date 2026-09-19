"""
postal_reader.py -- decodes eeu.pmp, eeu.pol, and eeu.pot, IDENTIFIED
this session: all 3 are genuinely empty on this disc (94-byte header,
zero body, zero records), same status as their family sibling
eeu.pcl (research/pcl_reader.py). But `eeu.mod`'s own schema
(research/mod_reader.py) gives each of them a real, informative
per-record field list -- enough to reconstruct what the whole
postal-code subsystem's intended design looked like, even with no
populated content to check it against.

============================================================================
The files themselves -- fully characterized, nothing left to decode
============================================================================
All 3 share the exact same 94-byte template as eeu.pcl (identical header
bytes except the `file_type` byte): file size == 94 exactly, `total_size`
(bytes[90:94]) also reads 94 (an exact match, not one of the 2 known
"stores body size instead" exceptions), `record_count_lo16`
(bytes[86:88]) reads 0. `file_type` (bytes[84:86]): eeu.pmp=65,
eeu.pol=61, eeu.pot=62 -- each unique, confirmed not the same numbering
as `files.cfg`'s own fileId (see pcl_reader.py's docstring for that
distinction).

`files.cfg`'s own comments: `34 = pol, 0, cached # postalcode list file`,
`35 = pot, 0, cached # postalcode tree file`,
`38 = pmp, 0, cached # postalcode merge postalcode file`.

============================================================================
What eeu.mod's schema reveals about each file's INTENDED design
============================================================================
Pulling each block's real (non-boilerplate) field list with
mod_reader.extract_blocks() gives a coherent picture of a 3-stage
postal-code lookup pipeline, none of it populated on this disc:

  eeu.pot (postalcodeTree) -- real fields: `key`,
  `nextSelectableCharTreeIndex`, `nextSelectableCharTreeCount`,
  `startDataListIndex`, `dataListCount`. This is BYTE-FOR-BYTE the same
  field-name template already found for `roadTree` (eeuz.rt) and
  `cityTree` (eeuz.ct) -- research/flat_compressed_reader.py,
  README S3.7/S3.8 -- i.e. eeu.pot was designed as a character-trie
  search index over postal-code STRINGS, using the exact same
  data structure already used for road-name and city-name
  autocomplete/search. Note the container differs even though the node
  schema is identical: eeuz.rt/eeuz.ct are FLAT_COMPRESSED, `eeu.pot` is
  plain NOT_COMPRESSED (per `files.cfg`'s own compressionType column).
  The exact byte-level encoding of this trie-node shape is itself still
  not fully cracked even for the POPULATED eeuz.rt/eeuz.ct
  (research/city_reader.py's own docstring: "the same still-uncracked
  variable-node structure as eeu(z).rt") -- so eeu.pot being empty loses
  nothing that was otherwise crackable this session either way.

  eeu.pol (postalcodeList) -- real fields: `postalcode`, `Latitude`,
  `Longitude`, `ListIdMain`. A real postal-code-to-coordinate lookup
  record: the postal code string itself, a representative point
  (the disc's usual /100000 int32 convention elsewhere), and a
  `ListIdMain` foreign key -- plausibly into the same kind of
  city/merge-list indices the .pmc/.pmm/.pmp trio manage (see below),
  though this specific link was NOT independently confirmed (no
  populated `eeu.pol` was available this session to check against).

  eeu.pmp (postalcodeListMergePostalcode) -- real field: a single
  `mergedListIndex`. Structurally the third sibling of the already-
  cracked eeu.pmc/eeu.pmm pair (research/pmc_reader.py) -- same "merge"
  naming convention, same lone-index shape. Together the 3 "merge"
  files (`.pmc` city-side, `.pmm` type/list separator, `.pmp`
  postalcode-side) read as a set of redirect/consolidation tables for
  cases where postal codes and cities don't map 1:1 (one postal code
  spanning multiple cities, or one city needing multiple postal-code
  entries) -- a real, sensible design, just never populated on this
  East-Europe V17 release.

Combined with eeu.pmc/eeu.pmm being a provable placeholder identity
array rather than real content (research/pmc_reader.py), the coherent
conclusion for the whole file family is: **the entire postal-code
subsystem (eeu.pol/.pot/.pmm/.pmc/.pmp) was designed and schema'd but
never populated on this specific disc.** Plausibly this East-Europe
dataset's country set didn't have licensed/available postal-code data at
build time, or the feature wasn't enabled for this particular release --
not independently confirmed (no other region/market disc was available
this session to compare against a populated postal-code subsystem).

============================================================================
Practical use
============================================================================
`read_postal_header(path)` decodes the shared header and confirms the
zero-body/zero-record status (True on this disc for all 3). There is no
body-decoding function here -- there is no body to decode. Field-name
reconstructions above come from `research/mod_reader.py`'s
`extract_blocks()`, not from these files' own (nonexistent) content.
"""

from research.aff_reader import decode_not_compressed_header, HEADER_SIZE

FILES_CFG = {
    "pol": (34, "postalcode list file"),
    "pot": (35, "postalcode tree file"),
    "pmp": (38, "postalcode merge postalcode file"),
}


def read_postal_header(path):
    """Decode one of eeu.pol/.pot/.pmp: returns (header_fields, body_bytes).
    On the reference disc, body_bytes is empty (b"") for all 3 -- a bare
    94-byte header, zero records."""
    with open(path, "rb") as f:
        data = f.read()
    return decode_not_compressed_header(data), data[HEADER_SIZE:]


def is_empty_placeholder(path):
    """True if this file is a bare 94-byte header with no body -- the
    reference disc's eeu.pol/.pot/.pmp all return True here."""
    header_fields, body = read_postal_header(path)
    return len(body) == 0 and header_fields["record_count_lo16"] == 0
