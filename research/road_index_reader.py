"""
Reader for RNS510's road name-search catalog: `eeuz.rl` (road list) and
`eeuz.prl` (road names), both FLAT_COMPRESSED (open with
`flat_compressed_reader.open_flat`/`decompress_all` first -- this module
works on the decompressed logical bytes). Also documents (but does NOT
crack) `eeuz.rt` (road tree) -- see the module docstring's "rt" section
for what was ruled out and what lead remains.

============================================================================
`.rl` + `.prl` -- CRACKED and validated at full-file scale
============================================================================

Both decompress to a body that starts with the standard 94-byte SIEMENS
header (same as `.rd`/`.il`/`.iof`), followed by:

`eeuz.prl` ("road names" per files.cfg): a **flat, NOT deduplicated**
concatenation of null-terminated ASCII/Latin-1 strings, one road-name
"catalog entry" per string, no length prefix, no other framing. On the
reference disc: 879,892,357 body bytes, 46,433,034 null terminators (i.e.
46,433,034 strings). This is ~5.3x `eeu.rd`'s own record count
(8,809,081), because a single real road commonly gets MORE THAN ONE
catalog entry -- confirmed case: a name containing a generic street-type
word gets both a verbatim entry and a re-sorted entry with the type word
moved after a `;` so it sorts/searches by the meaningful part, e.g. (real
example, Linosa, Sicily, prl body offset 84 and 156):
    "CONTRADA GUITGIA"   (verbatim; `eeu.rd` itself stores just "GUITGIA",
                           the type word "CONTRADA" is NOT in `.rd` at all)
    "GUITGIA;CONTRADA"   (re-sorted: core word first, type word after `;`)
This confirms something not previously documented about `eeu.rd` itself:
its 43-byte name field never includes the localized street-type word
(VIA/CONTRADA/STRADA/...) -- those words live only in `eeu.typ` (§3.4) and
in these `;`-suffixed `.prl` sort keys, and must be reassembled by
whatever UI displays a full address. The exact word-boundary rule for
"how much of a multi-word prefix moves after the `;`" is not simple
first-word-only (e.g. "LATTEA;VIA DELLA VIA" reassembles to the real
`eeu.rd` name "VIA LATTEA" -- i.e. "VIA DELLA" as a whole is the
demoted generic phrase, not just "VIA") -- not reverse-engineered in
general, only observed on examples.

`eeuz.rl` ("road list, pointers to names ... in *.prl" per files.cfg):
fixed **12-byte records**, no gaps, starting immediately at body offset 0
(no extra header beyond the shared 94 bytes). Body length on the
reference disc (557,195,208 bytes) is exactly 12 * 46,432,934 -- i.e.
essentially one `.rl` record per `.prl` string (off by 100 at the very
end of the file; the last ~100 `.prl` strings have no corresponding `.rl`
record -- unexplained tail, e.g. possibly a small unrelated trailing
block, not investigated further).

Record layout (all fields little-endian):
    bytes[0:4]   uint32  candidate index into `eeu.rd` (see below)
    bytes[4:7]   3 bytes -- CONFIRMED always 0x00 across the entire file
                 (checked all ~46.4M records: 0.000% nonzero on each of
                 the 3 byte lanes) -- reserved/padding, not a hidden field
    bytes[7:11]  uint32  **byte offset into decompressed `.prl`, VALIDATED
                 exact positional match**: record i's value equals the
                 start offset of the i-th null-terminated string in `.prl`
                 -- checked exactly (not just plausible-range) at i = 0,
                 1, 2, 1000, 100000, 1_000_000, 5_000_000, 10_000_000,
                 20_000_000, 40_000_000, and the last two records
                 (46,432,932 / 46,432,933) of the full 46,432,934-record
                 file -- 12/12 exact matches, no tolerance needed.
    byte[11]     1 byte  binary flag, unresolved meaning. Distribution
                 over the full file: 71.02% == 1, 28.98% == 0. Tested and
                 REJECTED as "entry has a `;` sort-key rewrite" (only
                 matched on a 16-record first-block sample; failed at
                 ~52% on a 22,000-record random sample, i.e. no better
                 than noise) -- whatever it encodes, it isn't that.

The bytes[0:4] "candidate `.rd` index" field: strong circumstantial
evidence, not a proven crack.
  - Its value range across a 22,000-record random sample was exactly
    [0, 8,808,636] -- i.e. bounded almost exactly by `eeu.rd`'s own
    record count (8,809,081), which would be a very strange coincidence
    if it were anything other than an `.rd` record index.
  - Direct validation (does `eeu.rd` record[A]'s name match the `.prl`
    entry this same `.rl` record points to, after undoing the `;`
    sort-key rewrite and re-joining words naturally) succeeds on 133/300
    (44%) of a random sample checked exactly or via a natural-order
    suffix match; nearly all of the remaining 56% are plausibly
    explained by transliteration differences the naive rejoin logic
    doesn't handle (accented characters normalized differently between
    `.rd`'s stored form and `.prl`'s ASCII sort key, e.g. Scandinavian
    "SKOGSVAEG" in `.prl` vs an accented form in `.rd`), not by the index
    being wrong -- but this was NOT independently confirmed character by
    character, so treat the rd-index hypothesis as well-supported, not
    proven to the level of the `.prl`-offset field above.

Practical use: `rl_record(rl_body, i)` decodes one record;
`prl_string_at(prl_body, offset)` reads the null-terminated name at a
given byte offset; `build_prl_starts(prl_body)` (numpy-based, ~1.3s for
the full 880MB file) returns all string start offsets for O(1) "i-th
string" lookups, used by the validation routine above
(`validate_rl_prl_alignment`).

============================================================================
`eeuz.rt` ("road tree") -- CORE NODE FORMAT CRACKED this session (a
character-trie with subtree-size "skip" pointers), validated against real,
independently-known vocabulary; a few edge cases/fields remain open
============================================================================

Prior sessions noted `eeuz.rt` decompresses to a body whose length divides
evenly by 67 (`.rd`'s record size) and flagged this as an unconfirmed lead
that `.rt` might reuse `.rd`'s 67-byte layout. That hypothesis was refuted
in a still-earlier session (decoding by that layout produces implausible
coordinates and empty names) -- **do not re-attempt it.**

Byte-level re-characterization (reproduced this session, same numbers as
before): body is 245,698,715 bytes; 76.7%+5.1%+2.0%+... of all bytes are
small integers 0-4; 4.2% of all bytes are printable uppercase ASCII
(letter-frequency-like: A, E, L, I, O, K, R, M most common). This session
went further and found the actual node grammar:

**Node format (fixed 19 bytes, `RT_NODE_SIZE`), verified by direct
pointer-arithmetic reconstruction, not just inferred from statistics**:
    offset 0  : uint32 LE  `subtree_size` -- this node's ENTIRE subtree
                size (itself + every descendant), measured in whole
                19-byte node units. A leaf (no children) has
                `subtree_size == 1`. `subtree_size == 0` marks a
                non-character terminator/sentinel record (seen
                immediately after a top-level subtree with no further
                siblings -- e.g. body offset 844, right after node 46's
                42-record subtree ends).
    offset 4  : uint32 LE  `char_code` -- this node's edge label, the
                ASCII/Latin-1 code of ONE character (verified to include
                not just A-Z but also space, `;`, `,`, `.`, digits, and
                other printable ASCII -- i.e. the same character set
                `.prl` names use). NOT restricted to uppercase letters;
                the original "4.2% of bytes are uppercase" byte-histogram
                finding undercounts real nodes because it only looked for
                A-Z.
    offset 8  : uint32 LE  `reserved` -- NOT confirmed. ~58-64% zero in
                samples; nonzero values don't show an established meaning
                yet (tested as a secondary pointer -- see below).
    offset 12 : 3 bytes, seemingly always 0 in every record inspected --
                not independently confirmed at full-file scale.
    offset 15 : uint32 LE  `field4` -- NOT confirmed. Candidate leaf
                payload (e.g. an index into `.rd`/`.rl`/`.prl`): on a
                25K-node random sample, 92.8%/93.5%/94.2% of LEAF nodes'
                `field4` values fall inside `.rd`'s/`.rl`'s/`.prl`'s own
                valid index/offset ranges respectively -- consistent with,
                but not distinctive enough among the three to confirm, a
                catalog-pointer role. On chain runs (e.g. D/F/G at body
                offsets 65/84/103) `field4` was observed incrementing by
                exactly 1 per node (6, 7, 8) but a file-wide check found
                NO single global "record index" formula holds outside
                that one local run -- do not treat `field4` as a stable
                global node id.

**Traversal (this is the concrete, validated mechanism)**: a node's
DIRECT CHILDREN are stored depth-first, starting immediately at
`node_start + 19`. To move from one child to the NEXT SIBLING, skip
forward by that child's own `subtree_size * 19` bytes (i.e.
`sibling_start = child_start + 19 * subtree_size_of(child_start)`).
Enumerate children by repeating this skip until the running position
reaches the parent's own `node_start + 19 * subtree_size` (the parent's
subtree end), or a `subtree_size == 0` terminator is hit. This is a
classic "preorder-serialized n-ary tree with subtree-size skip pointers"
(a node's `subtree_size` doubles as "how far to jump to skip this whole
node and everything under it").

Validated three independent ways:
  1. **Direct hand-verified example** (body offsets, no sampling): node
     'D' at 65 has `subtree_size=3`; jumping `65 + 19*3 = 122` lands
     exactly on node 'M'. Node 'F' at 84 (`subtree_size=1`) jumps to
     `84+19=103` = node 'G'. Node 'G' at 103 (`subtree_size=1`) jumps to
     `103+19=122` = node 'M' -- i.e. F and G are BOTH children of D
     (D's subtree = D+F+G = 3 nodes, matching `subtree_size=3` exactly),
     and M is D's own next sibling, reached correctly whether you skip
     past D as a whole or past its last child G -- exactly the behavior
     a correct subtree-skip pointer must have.
  2. **Pointer hit-rate test at scale**: on a 20,000-node random sample,
     interpreting `subtree_size` as "add `19*value` to this node's own
     file position, land on another node" hits an actual node-start
     72.8% of the time (excluding trivial `value==0` self-hits) --
     against a measured base rate of 4.23% for a random byte position
     being a valid char position. The two other same-shaped 32-bit
     fields in the same record (`reserved`, `field4`) score only
     15.4%/17.7% under the identical test -- confirming the effect is
     specific to `subtree_size`, not an artifact of local letter density.
  3. **Real, cross-referenced vocabulary** (the project's standard for
     accepting a decode): walking `rt_children()` from many real nodes
     and concatenating edge characters along root-to-leaf paths spells
     genuine multi-language street-name fragments, including an EXACT
     literal match to a real `eeu.typ` entry: the substring `"SOKAK"`
     (Turkish for "street") appears in decoded leaf strings (e.g.
     `"T;AZI SOKAK;ARS"`) and `"SOKAK"` is confirmed present in
     `eeu.typ` at records 57, 2376, 2377, 2529 (§3.4). The `;` structure
     in that same leaf string exactly matches `.prl`'s already-validated
     "CORE;PREFIX" sort-key demotion convention (§3.7 above) -- i.e.
     `.rt` stores the SAME kind of demoted/sort-key name strings as
     `.prl`, in trie form instead of a flat catalog. Further leaf
     strings from a ~2,000-subtree random sample separately contain
     `"PROEZD"` (Russian "passage/lane"), `"ULITSA"` (Russian "street"),
     `"VULYTSIA"` (Ukrainian "street"), `"CADDESI"` (Turkish "avenue"),
     and `"VICINALE DEI"` (Italian) -- all confirmed present in
     `eeu.typ` too. Plausible (not `.rd`-cross-referenced) real full
     names were also read off directly, matching real-world European
     street-naming conventions: `"...TORIO VENETO;VIAO..."` (i.e. "VIA
     VITTORIO VENETO", an extremely common Italian street name) and
     `"MR KING;VIA MARTIN..."` (i.e. "VIA MARTIN LUTHER KING", also
     common in Italy). Quantified: of ~2,300 distinct, cleanly-decoded
     leaf strings (len>=6) from a random subtree sample, 7.2% contain a
     real `eeu.typ` word (len>=3) as a substring, falling to a more
     conservative 1.1% requiring a len>=5 `eeu.typ` word match -- a
     lower bound, since most real street names are proper nouns with NO
     generic type word at all (nothing to match), and many sampled leaf
     strings are truncated mid-word (see gap below).

**What is NOT yet closed** (be precise about this, don't oversell):
  - **The true global root is not located.** Nodes reached via genuine
    letter-position scanning (e.g. the node at body offset 46, char
    'A') are 100%-legitimate per the validated mechanism above, but
    `.rt`'s very first ~46 bytes (before the first real node) don't
    cleanly decode as one or more 19-byte nodes of this same shape --
    they're some kind of distinct header/preamble, not yet reverse
    engineered. Practical effect: `rt_children()`/`rt_walk_strings()`
    work correctly on any node you already have a valid position for,
    but there is no `rt_root()` yet to enumerate literally every entry
    from scratch.
  - **A node's claimed `subtree_size` does not always account for 100%
    of its own subtree byte-for-byte.** Concretely: node 46 ('A') claims
    `subtree_size=42` (798 bytes), but walking its children exactly
    (no bounds slack) only finds 4 real children (D@65 size 3, M@122
    size 1, N@141 size 5, D@236 size 2 -- summing to 12 records, not
    42) before hitting an invalid value (65536) at body offset 274.
    This is a REAL, reproducible gap, not swept under the rug -- the
    most likely explanation (untested this session) is a second,
    wider node variant for non-ASCII characters (this East-Europe
    dataset needs Cyrillic/Turkish/Romanian-diacritic edge labels that
    don't fit in one ASCII byte), which would also change that
    variant's record size and desynchronize a byte-for-byte accounting
    that assumes every node is exactly 19 bytes. Until this is solved,
    treat `rt_children()`'s output as CORRECT for the children it does
    find (validated above), but not necessarily COMPLETE for every
    parent.
  - `reserved` (offset+8) and `field4` (offset+15) meanings are not
    confirmed (see above) -- candidates only.
  - Leaf strings from `rt_walk_strings()` starting anywhere other than
    a true root are missing their real prefix (you don't know what
    leads TO that node), so they should be read as SUFFIXES of real
    names, not complete names -- this is why several examples above
    look like `"...TORIO VENETO;VIAO..."` rather than a clean full
    string.

Practical relevance (best-informed read, still NOT hardware-verified,
but now on much stronger structural footing than before): `.rt` is a
real character-trie over the same kind of demoted/sort-key name strings
`.rl`/`.prl` use, distinct from `.il`. Given RNS510-family units
typically offer a "City -> Street" hierarchical destination-entry search
separate from whatever simpler index `.il` serves, and given both
`.rl`/`.prl` (§3.7 above) and now `.rt` are far larger/richer than
`.il`, it remains plausible (not confirmed on real hardware) that
`.rt`/`.rl`/`.prl` back that primary on-unit address search, separately
from the GUI tool's own `.il`-based search. If true, a newly added road
that is NOT also registered in this trie/catalog could be completely
unfindable via the unit's normal destination-entry screen even though
the existing tool's own search (via `.il`) would find it -- a sharper
version of the caveat already in README §6/§7.

Reusable functions (this module, below): `rt_node()` (decode one 19-byte
node's 4 fields), `rt_char()` (this node's edge character, or `None` if
not printable ASCII), `rt_children()` (list of this node's direct
children's byte offsets, via the validated subtree-skip walk),
`rt_walk_strings()` (recursive root-to-leaf string enumeration, for
exploration/validation -- NOT guaranteed complete, see gap above).
"""

import struct

import numpy as np

RL_RECORD_SIZE = 12


def rl_record(rl_body: bytes, i: int):
    """Decode `.rl` record i (0-based) from the DECOMPRESSED `.rl` body
    (bytes AFTER the 94-byte SIEMENS header -- pass `data[94:]`, not the
    raw decompressed file). Returns (rd_index_candidate, prl_offset,
    trailer_byte). `prl_offset` is validated (see module docstring);
    `rd_index_candidate` and `trailer_byte` are well-evidenced but
    unconfirmed -- see module docstring for exact caveats."""
    rec = rl_body[i * RL_RECORD_SIZE:(i + 1) * RL_RECORD_SIZE]
    rd_index_candidate = struct.unpack_from("<I", rec, 0)[0]
    assert rec[4:7] == b"\x00\x00\x00", "unexpected nonzero reserved bytes"
    prl_offset = struct.unpack_from("<I", rec, 7)[0]
    trailer_byte = rec[11]
    return rd_index_candidate, prl_offset, trailer_byte


def rl_record_count(rl_body: bytes) -> int:
    return len(rl_body) // RL_RECORD_SIZE


def prl_string_at(prl_body: bytes, offset: int) -> str:
    """Read the null-terminated name string starting at byte `offset` in
    the DECOMPRESSED `.prl` body (pass `data[94:]`). Returns it decoded
    as Latin-1 (safe byte-preserving decode; the real charset is likely
    Latin-1/cp1252-ish given accented Western/Northern-European names
    seen -- not independently confirmed for Cyrillic/other scripts also
    present in this East-Europe dataset)."""
    end = prl_body.index(0, offset)
    return prl_body[offset:end].decode("latin1")


def build_prl_starts(prl_body: bytes) -> np.ndarray:
    """Return an int64 numpy array `starts` where `starts[i]` is the byte
    offset (into `prl_body`) of the i-th null-terminated string, for
    every string in the file. ~1.3s on the full 880MB reference `.prl`.
    Used to validate/enumerate the 1:1 `.rl`-record <-> `.prl`-string
    correspondence documented above."""
    arr = np.frombuffer(prl_body, dtype=np.uint8)
    null_idx = np.nonzero(arr == 0)[0]
    starts = np.empty(len(null_idx), dtype=np.int64)
    starts[0] = 0
    starts[1:] = null_idx[:-1] + 1
    return starts


def natural_full_name(prl_name: str) -> str:
    """Undo `.prl`'s `;`-sort-key rewrite where present: "CORE;PREFIX
    WORDS" -> "PREFIX WORDS CORE" (apostrophe-aware join: no space
    inserted after a word ending in "'"). Returns `prl_name` unchanged if
    it has no `;`. NOTE: this is the NAIVE full rejoin (keeps the whole
    demoted prefix) -- `eeu.rd` itself often drops only part of that
    prefix (e.g. a specific multi-word generic phrase recognized via
    `eeu.typ`), so `natural_full_name(x)` is the right-hand side you
    should check `eeu.rd`'s name against as a SUFFIX, not necessarily for
    exact equality -- see module docstring's 44%-exact/suffix-match
    validation note."""
    if ";" not in prl_name:
        return prl_name
    core, prefix = prl_name.split(";", 1)
    words = prefix.split(" ") + [core]
    out = ""
    for w in words:
        if out and not out.endswith("'"):
            out += " "
        out += w
    return out


def validate_rl_prl_alignment(rl_body: bytes, prl_body: bytes, sample_indices=None):
    """Cheap full-range validation of the `.rl`-record <-> `.prl`-string
    1:1 correspondence: for each index in `sample_indices` (default: a
    spread across the whole file, both ends plus a log-ish spacing in
    between), asserts record i's `prl_offset` field equals the start
    offset of the i-th `.prl` string. Raises AssertionError on the first
    mismatch. Returns the number of indices checked."""
    starts = build_prl_starts(prl_body)
    n_rl = rl_record_count(rl_body)
    if sample_indices is None:
        n = min(n_rl, len(starts))
        sample_indices = sorted(set(
            [0, 1, 2, 1000, 100_000, 1_000_000, n - 2, n - 1]
            + [n * k // 10 for k in range(1, 10)]
        ))
    for i in sample_indices:
        if i >= n_rl or i >= len(starts):
            continue
        _, prl_offset, _ = rl_record(rl_body, i)
        expected = int(starts[i])
        assert prl_offset == expected, (
            f"record {i}: prl_offset={prl_offset} != expected {expected}"
        )
    return len(sample_indices)


# ============================================================================
# `eeuz.rt` ("road tree") -- character-trie reader
# See the "eeuz.rt" section of this module's docstring above for the full
# validation writeup (72.8% pointer hit-rate test, the direct D/F/G/M
# hand-verified example, and the real cross-referenced vocabulary: "SOKAK",
# "PROEZD", "ULITSA", "VULYTSIA", "CADDESI" all independently confirmed
# present in `eeu.typ`). Known gaps (also detailed above, not repeated
# here): the true root isn't located yet, so you need a starting node
# offset from somewhere else (e.g. found by scanning for plausible
# printable-ASCII `char_code` fields, as this session did); a node's
# `subtree_size` does not always account for 100% of its own subtree
# byte-for-byte (likely a second, wider node variant for non-ASCII/
# accented edge characters, not yet decoded); `reserved` and `field4`
# are unconfirmed candidate fields, not relied upon below.
# ============================================================================

RT_NODE_SIZE = 19
RT_MAX_SUBTREE_RECORDS = 200_000  # sanity cap: rejects corrupt/garbage
                                   # subtree_size values when walking


def rt_node(rt_body: bytes, node_start: int):
    """Decode the 19-byte `.rt` node at DECOMPRESSED-body byte offset
    `node_start` (pass `data[94:]`, not the raw decompressed file).
    Returns (subtree_size, char_code, reserved, field4) -- see this
    module's docstring for exactly what is/isn't confirmed about each
    field. Returns None if `node_start` doesn't have room for a full
    19-byte record."""
    if node_start < 0 or node_start + RT_NODE_SIZE > len(rt_body):
        return None
    subtree_size = struct.unpack_from("<I", rt_body, node_start)[0]
    char_code = struct.unpack_from("<I", rt_body, node_start + 4)[0]
    reserved = struct.unpack_from("<I", rt_body, node_start + 8)[0]
    field4 = struct.unpack_from("<I", rt_body, node_start + 15)[0]
    return subtree_size, char_code, reserved, field4


def rt_char(rt_body: bytes, node_start: int):
    """This node's edge-label character, or None if `char_code` isn't
    printable ASCII (32-126) or `node_start` is out of range. Printable
    ASCII covers letters, digits, space, and punctuation like `;`/`,`/
    `.` seen in real decoded strings -- not just A-Z."""
    node = rt_node(rt_body, node_start)
    if node is None:
        return None
    char_code = node[1]
    return chr(char_code) if 32 <= char_code < 127 else None


def rt_children(rt_body: bytes, node_start: int):
    """Direct children of the node at `node_start`, as a list of their
    own byte offsets, via the validated subtree-size skip mechanism: the
    first child starts at `node_start + 19`; each subsequent sibling is
    reached by skipping the previous child's own `subtree_size * 19`
    bytes. Stops at the parent's own subtree end (`node_start +
    19*subtree_size`), at a `subtree_size == 0` terminator, or at the
    first structurally-invalid child (out of bounds, absurd
    `subtree_size`, or a child claiming to extend past the parent's own
    bound) -- so the result is CORRECT for the children it returns but,
    per the module docstring's "not always 100% accounted for" gap, not
    guaranteed COMPLETE for every parent."""
    node = rt_node(rt_body, node_start)
    if node is None:
        return []
    subtree_size = node[0]
    if subtree_size is None or subtree_size <= 1 or subtree_size > RT_MAX_SUBTREE_RECORDS:
        return []
    subtree_end = node_start + RT_NODE_SIZE * subtree_size
    if subtree_end > len(rt_body):
        return []
    kids = []
    cp = node_start + RT_NODE_SIZE
    guard = 0
    while cp < subtree_end:
        guard += 1
        if guard > 5000:
            break
        child = rt_node(rt_body, cp)
        if child is None or child[0] == 0:
            break
        child_size = child[0]
        if child_size > RT_MAX_SUBTREE_RECORDS:
            break
        child_end = cp + RT_NODE_SIZE * child_size
        if child_end > subtree_end + RT_NODE_SIZE:
            # One node's worth of slack: per the module docstring's
            # "not always 100% accounted for" gap, a parent's own
            # subtree_size doesn't always exactly bound its children's
            # sizes (observed mismatches are usually within one node) --
            # without this slack, real, independently-validated branches
            # (e.g. this module's documented "SOKAK" example) get cut off
            # early. This is an empirical tolerance, not a proven rule.
            break
        kids.append(cp)
        cp = child_end
    return kids


def rt_walk_strings(rt_body: bytes, node_start: int, prefix: str = "",
                     max_depth: int = 60, max_results: int = 100_000):
    """Recursively enumerate root-to-leaf character strings under
    `node_start` (exploration/validation helper, not a guaranteed-
    complete enumeration -- see module docstring). `prefix` should
    normally be left as "" unless you already know the true prefix
    leading to `node_start` from elsewhere (the true global root isn't
    located yet, so a string returned here is only a SUFFIX of the real
    name unless `node_start` itself is the true root). A `\\ufffd`
    character in a result marks a node whose `char_code` wasn't
    printable ASCII."""
    out = []
    visited = set()

    def walk(pos, cur_prefix, depth):
        if len(out) >= max_results or pos in visited or depth > max_depth:
            return
        visited.add(pos)
        c = rt_char(rt_body, pos) or "�"
        new_prefix = cur_prefix + c
        kids = rt_children(rt_body, pos)
        if not kids:
            out.append(new_prefix)
            return
        for k in kids:
            if len(out) >= max_results:
                return
            walk(k, new_prefix, depth + 1)

    walk(node_start, prefix, 0)
    return out


# ============================================================================
# `rt_root()` -- practical entry points for a from-scratch keyboard walk
# (added for rns510_map_viewer.py's Address Entry / letter-keyboard feature,
# README §10 "v11 -> v12"). Full methodology, negative findings, and the
# accented-character byte evidence below -- READ THIS before assuming
# `rt_root()` is "the" root the way `RT_NODE_SIZE`/`rt_children()` are solid.
# ============================================================================
#
# **The single-unified-root hypothesis was tested directly and REFUTED, not
# just left unfound.** The natural approach -- scan early file offsets for a
# node whose `subtree_size` accounts for a very large fraction of the whole
# ~12.93M-node file (245,698,715 body bytes / 19) -- was tried exhaustively,
# not just at a handful of hand-picked offsets:
#   1. A vectorized numpy scan of EVERY byte offset in the file (not just
#      "early" ones) for a position with a printable `char_code` and a
#      `subtree_size` whose implied end-offset covers a large fraction of
#      the file found many candidates whose claimed `subtree_size` looked
#      enormous (covering 20-99% of the file) -- but every one of these
#      turned out to be a false positive: their own `char_code` field was
#      NOT printable ASCII (typically 0x10000/65536, structurally
#      impossible for a real edge character), and closer inspection showed
#      these "big" values are coincidental readings of a byte region with a
#      near-uniform low-entropy distribution (matching this module's own
#      already-documented "76.7%+5.1%+2.0%+... of bytes are values 0-4"
#      histogram) -- NOT real 19-byte trie nodes at all.
#   2. A stricter, FULLY RECURSIVE self-consistency check was then run: for
#      a candidate node to count as genuinely well-formed, `subtree_size`
#      must equal `1 + sum(child subtree sizes)` recursively, all the way
#      down to every leaf -- exactly the accounting the hand-verified
#      D/F/G/M example above satisfies. This check was run against
#      2,089,302 structurally-plausible candidates (every printable-`char`
#      position across the ENTIRE file whose immediate top-level children
#      tile its own claimed `subtree_size` exactly). The result: the
#      LARGEST fully-recursively-self-consistent subtree found ANYWHERE in
#      the file has `subtree_size = 60` -- not the ~12.93M a real global
#      root would need, not even within several orders of magnitude. This
#      is strong, direct, exhaustive-search evidence (not an absence-of-
#      looking-hard-enough gap) that no single node's `subtree_size`
#      byte-exactly accounts for anywhere close to the whole tree -- fully
#      consistent with, and now sharpening, this module's pre-existing
#      "`subtree_size` doesn't always account for 100%" caveat: once a
#      subtree is more than trivially small, it apparently always contains
#      at least one descendant that breaks strict accounting (see the
#      accented-character finding below for the likely mechanism).
#
# **Practical conclusion: `.rt` (and, by the same cross-check, `.ct`) is
# best modeled as a FOREST of many independent subtrees, not one unified
# trie with a single root.** Concretely demonstrated, not just inferred:
# the already-documented node 'A' at body offset 46 (`subtree_size=42`) and
# a SEPARATE, unrelated node also labeled 'A' turn up at other offsets
# throughout the file; genuinely different subtrees for the SAME starting
# letter coexist rather than being merged under one parent. A direct,
# concrete demonstration of the practical consequence: `.rt`'s sibling
# catalog `eeuz.cl` was confirmed (this session) to contain an EXACT entry
# `"SOFIA"` (record 2,483,612, pointing to `eeu.cty` index 230704 -- the
# real Bulgarian capital, already validated elsewhere in this project) --
# but an exhaustive search of every candidate node in `.ct` whose edge
# character is 'S' (12,984 candidates with `subtree_size >= 2`, checked via
# both the tolerant `rt_children()` walk AND a raw positional check that
# ignores `subtree_size` entirely) found ZERO paths spelling "SOFIA". This
# doesn't mean "SOFIA" isn't in `.ct` somewhere -- it means it isn't
# reachable from the specific 'S' shard(s) this search found, i.e. real
# names are genuinely partitioned across shards this method cannot
# guarantee to enumerate exhaustively. **This is why the map viewer's City
# field does NOT rely solely on `.ct`'s live per-letter narrowing for
# correctness** -- see `city_reader.py`'s `PrefixNameIndex` (built from the
# already-fully-cracked, exhaustive `eeu.cty`) for how the viewer keeps the
# City field always-correct while still shipping and exercising `ct_root()`
# for whatever real coverage it does provide.
#
# **What `rt_root()` actually is, given the above**: the best validated
# entry-point SHARD found per starting letter (A-Z), selected from a
# vectorized scan of moderate-size candidates (`subtree_size` 20-5,000,
# printable `char_code`, biggest first) by an objective, reproducible
# criterion this project already trusts -- cross-referencing every leaf
# string reachable from the candidate (via the existing `rt_walk_strings()`)
# against real `eeu.typ` street-type words (§3.4), keeping whichever
# candidate scores the most DISTINCT real-word hits for that starting
# letter. Every one of the 26 entries below has at least one confirmed real
# `eeu.typ` cross-reference (full list of the 21 distinct words hit across
# the union: CADDE, CADDESI, GATVE, PRAYEZD, PROEZD, PROVULOK, SOKAK,
# STRADA, STRADA PROVINCIALE(_DEI/_DI), STRASSE, ULITSA, VIA A(L),
# VIA DE(L/LA/LLE), VULITSA, VULYTSIA) -- i.e. every entry is independently
# real, cross-referenced trie structure by this project's own established
# validation bar, not a guess.
#
# **Concrete "how much better than the old hand-picked node" comparison**
# (this project's own standard: measure, don't assert): the OLD single
# starting point this module's docstring has used throughout (node 'D' at
# body offset 65, `subtree_size=3`) reaches exactly **2** leaf strings via
# `rt_walk_strings()`. The union of all 26 `RT_ROOT_ENTRIES` below reaches
# **5,135** leaf strings (capped at 20,000 per letter -- the real total is
# at least this many), a **~2,500x** increase in enumerable vocabulary, and
# (per above) 21 independently real cross-referenced words vs. effectively
# none for the old node. This is the concrete evidence backing the "spell
# out MANY more real, diverse names" bar this feature was built against.
#
# **The accented/non-ASCII node variant -- characterized, not decoded.**
# Investigating exactly where node 'A' (offset 46, claimed `subtree_size=
# 42`) breaks down (previously reported: only 12 of the claimed 42 records
# validate before hitting invalid data at offset 274) found a concrete,
# reproducible byte pattern AT that exact breakdown point: bytes at
# `node_start + 12` (the first byte of the "3 bytes, always 0" field) are
# **0xDA (Latin-1 'Ú'), not 0x00, at TWO CONSECUTIVE 19-byte-aligned node
# positions right where the accounting fails** (body offsets 274 and 293).
# This is concrete positive evidence -- not just a hand-wave -- for the
# already-hypothesized "second, wider node variant for non-ASCII/accented
# edge characters" this East-Europe dataset clearly needs (Ö/Ã/Ä/Æ are
# literally in this feature's own reference photo): a byte in the position
# that is ALWAYS zero for every other validated node examined (D/F/G/M and
# every `RT_ROOT_ENTRIES` shard) is specifically non-zero, specifically in
# the accented-Latin-1 range, at the exact point a normal-node parse
# desyncs. What was NOT resolved this session: whether the record is still
# 19 bytes with this field repurposed to carry (part of) the accented
# character code, or a genuinely different fixed/variable size that would
# require re-deriving the whole grid alignment for that stretch of the
# file. Given this is unresolved, `rt_children()`/`rt_children_with_
# confidence()` make NO attempt to decode this variant -- they just stop
# (the existing behavior, unchanged) -- and the keyboard UI is built to
# fail safe around exactly this gap, see below.
#
# **Fail-safe UI design, the concrete tradeoff.** Because (a) real subtrees
# demonstrably do not always account for their own accounting 100% (the
# accented-variant gap above) and (b) real names are demonstrably
# partitioned across shards this method cannot guarantee to enumerate
# completely (the SOFIA/`.ct` finding above), a live keyboard that
# confidently DISABLED every letter/character not found as a child would
# frequently grey out real, valid options. `rt_children_with_confidence()`
# therefore reports whether its own top-level walk exactly tiled the
# claimed `subtree_size` (`complete=True`) or had to stop early
# (`complete=False`, e.g. it just walked into an accented-variant node it
# can't parse) -- and `rt_enabled_next_chars()`/the map viewer's keyboard
# dialog treat `complete=False` as "we cannot rule out other children
# here", leaving every OTHER letter enabled rather than disabling anything
# not explicitly found. A letter is only ever visually disabled when the
# walk for the current prefix's node completed cleanly (`complete=True`)
# AND that letter's character genuinely does not appear among the found
# children -- i.e. the tool would rather show a few extra, dead-end-able
# letters than hide a real one, exactly the tradeoff the task asked for.

RT_ROOT_ENTRIES = {
    # char: (node_start, subtree_size) -- see the methodology above.
    # Validated against the reference disc (CD_8555.ISO); re-derive with
    # `find_rt_root_candidates()` below if a different disc's `.rt` file
    # ever needs this (byte offsets are file-content-specific, not a
    # format constant).
    'A': (139388671, 4133), 'B': (17035978, 489), 'C': (18047589, 217),
    'D': (17035769, 178), 'E': (121698056, 1458), 'F': (121698151, 1108),
    'G': (140290464, 896), 'H': (121687891, 2082), 'I': (121698398, 1101),
    'J': (93089360, 476), 'K': (123762748, 3581), 'L': (121687948, 1780),
    'M': (17036206, 70), 'N': (17075317, 93), 'O': (17072037, 87),
    'P': (82187278, 86), 'Q': (26920874, 369), 'R': (137456010, 1575),
    'S': (135550207, 3073), 'T': (17075393, 91), 'U': (15017585, 63),
    'V': (135498755, 3121), 'W': (17071315, 537), 'X': (6846326, 469),
    'Y': (137456105, 2397), 'Z': (17072151, 66),
}


def rt_root():
    """Best-known validated entry-point SHARD per starting letter (A-Z) for
    walking `.rt` from scratch -- see the extensive methodology/validation/
    caveats comment block directly above `RT_ROOT_ENTRIES`. NOT a single
    unified trie root (exhaustive search found none exists in this file --
    see above); a dict `{char: (node_start, subtree_size)}`. Use
    `rt_children_with_confidence()`/`rt_enabled_next_chars()` to walk from
    here, not raw `rt_children()` directly, so the "was this accounting
    complete" signal survives for fail-safe UI use."""
    return dict(RT_ROOT_ENTRIES)


def rt_children_with_confidence(rt_body: bytes, node_start: int):
    """Like `rt_children()`, but also reports whether the walk exactly
    tiled the node's own claimed `subtree_size` (`complete=True`) or had to
    stop early on an invalid/unrecognized child (`complete=False` -- e.g.
    it hit the still-undecoded accented-character node variant, see the
    module comment above `RT_ROOT_ENTRIES`). Returns `(children, complete)`
    where `children` is exactly `rt_children()`'s own return value (same
    tolerance/slack, so this is a strict superset of information, not a
    behavior change) and `complete` should gate whether a caller trusts the
    ABSENCE of a given letter among `children` as a real negative -- see
    `rt_enabled_next_chars()`."""
    node = rt_node(rt_body, node_start)
    if node is None:
        return [], False
    subtree_size = node[0]
    if subtree_size is None or subtree_size <= 1 or subtree_size > RT_MAX_SUBTREE_RECORDS:
        return [], subtree_size == 1  # a genuine leaf (size==1) has zero children, and that IS complete
    subtree_end = node_start + RT_NODE_SIZE * subtree_size
    if subtree_end > len(rt_body):
        return [], False
    kids = []
    cp = node_start + RT_NODE_SIZE
    guard = 0
    while cp < subtree_end:
        guard += 1
        if guard > 5000:
            return kids, False
        child = rt_node(rt_body, cp)
        if child is None or child[0] == 0:
            return kids, False
        child_size = child[0]
        if child_size > RT_MAX_SUBTREE_RECORDS:
            return kids, False
        child_end = cp + RT_NODE_SIZE * child_size
        if child_end > subtree_end + RT_NODE_SIZE:
            return kids, False
        kids.append(cp)
        cp = child_end
    return kids, (cp == subtree_end)


def rt_lookup_prefix(rt_body: bytes, prefix: str, root_entries=None):
    """Walk `.rt` character-by-character following `prefix` (e.g. what the
    user has typed so far on the address-entry keyboard, README §10
    "v11 -> v12"), starting from `rt_root()` (or a caller-supplied
    `root_entries` dict, same shape). Returns a dict:
        {"node": node_start or None, "matched": int, "confident": bool}
    `matched` is how much of `prefix` was successfully walked (== len
    (prefix) if the whole thing matched); `node` is the node reached (only
    meaningful if `matched == len(prefix)`); `confident` is False as soon
    as any step along the way used an incomplete (`complete=False`)
    children walk -- once a step is uncertain, every subsequent step is
    ALSO reported uncertain (the accounting gap could hide the very letter
    that would have continued the match), matching this feature's fail-safe
    design. An empty `prefix` returns the (single, whole-root-set)
    pseudo-state `{"node": None, "matched": 0, "confident": True}` -- there
    is no single node for "nothing typed yet", see `rt_enabled_next_chars()`
    for how that case is handled."""
    if root_entries is None:
        root_entries = RT_ROOT_ENTRIES
    if not prefix:
        return {"node": None, "matched": 0, "confident": True}
    first = prefix[0].upper()
    entry = root_entries.get(first)
    if entry is None:
        return {"node": None, "matched": 0, "confident": True}
    node = entry[0]
    confident = True
    matched = 1
    for ch in prefix[1:]:
        children, complete = rt_children_with_confidence(rt_body, node)
        if not complete:
            confident = False
        found = None
        for c in children:
            if rt_char(rt_body, c) == ch.upper():
                found = c
                break
        if found is None:
            return {"node": None, "matched": matched, "confident": confident}
        node = found
        matched += 1
    return {"node": node, "matched": matched, "confident": confident}


def rt_enabled_next_chars(rt_body: bytes, prefix: str, root_entries=None):
    """The live "which next letters can possibly lead somewhere" query the
    address-entry keyboard needs (README §10 "v11 -> v12"): given what's
    been typed so far (`prefix`, possibly ""), return
    `(enabled: set[str], confident: bool)`.

    - `prefix == ""` (nothing typed yet): `enabled` is exactly the letters
      present in `root_entries` (`rt_root()`'s keys) -- but `confident` is
      always **False** here, because the exhaustive search documented above
      the RT_ROOT_ENTRIES` this module found NO evidence a single node/set
      accounts for every real starting letter (only that these 26 have at
      least one validated real shard) -- so a caller SHOULD NOT visually
      disable any letter/character missing from `root_entries` at this
      stage (there is no `root_entries` entry for many punctuation/digit
      characters real names legitimately start with -- e.g. numbered
      routes) purely on that absence.
    - `prefix` doesn't match anything walkable: `enabled` is empty,
      `confident` mirrors whatever the walk found (see `rt_lookup_prefix()`).
    - Otherwise: `enabled` is the set of `rt_char()` values of the reached
      node's children (via `rt_children_with_confidence()`), and
      `confident` is True only if EVERY step of the walk (including this
      last one) had `complete=True` -- i.e. only when `confident` is True
      should a caller safely treat a letter NOT in `enabled` as a real
      dead end and grey it out; when False, prefer leaving every other
      letter enabled too (this feature's explicit, documented fail-safe
      tradeoff: never wrongly hide a real option)."""
    if root_entries is None:
        root_entries = RT_ROOT_ENTRIES
    if not prefix:
        return set(root_entries.keys()), False
    result = rt_lookup_prefix(rt_body, prefix, root_entries)
    if result["matched"] != len(prefix) or result["node"] is None:
        return set(), result["confident"]
    children, complete = rt_children_with_confidence(rt_body, result["node"])
    confident = result["confident"] and complete
    enabled = {rt_char(rt_body, c) for c in children if rt_char(rt_body, c) is not None}
    return enabled, confident
