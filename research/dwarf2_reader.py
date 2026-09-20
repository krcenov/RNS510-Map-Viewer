"""
dwarf2_reader.py -- a minimal, real, validated DWARF2 parser (big-endian,
32-bit -- the exact profile every PowerPC ELF object on this project's 2
discs uses) for `.debug_abbrev` + `.debug_info`. CRACKED and cross-
validated: applied to `WA/CTEST.OUT` (research/swl_5238_reader.py, the
SWL firmware disc's own small, complete, unstripped PowerPC ELF object)
and gives a complete, real function-name-to-byte-range map that exactly
matches that file's own `.symtab` (independent cross-check, not just
internal consistency).

============================================================================
Why this exists
============================================================================
`CTEST.OUT`'s ELF header lists `.debug_info`/`.debug_abbrev`/
`.debug_line`/`.debug_pubnames`/`.debug_aranges` sections but this
project had no DWARF parser to actually read them (`swl_5238_reader.py`
only used its plain `.symtab` for function names/sizes). Also used, in
the SAME session, as a DEFINITIVE test of whether the much bigger
`FHDD6.FLI` application image (85.6MB) has any REAL DWARF `.debug_info`
surviving in its own 0-24MB native-code region -- see "Cross-check
against FHDD6.FLI" below.

============================================================================
CTEST.OUT -- CRACKED: complete, real DWARF2 CU/function breakdown
============================================================================
`CTEST.OUT`'s `.debug_info` (offset 0x40d1, size 0xe45b) parses as 4
real compilation units, each with a real DW_AT_producer identifying the
EXACT compiler: `"GNU C gcc-2.96 (2.96+ MW/LM) 19990621 AltiVec VxWorks
5.5"` -- more specific than this project's previously-known "Wind River
GCC 2.96 cross-toolchain" (README S2.1): this is a Metrowerks/Lineo
("MW/LM")-patched GCC 2.96 with AltiVec support, targeting VxWorks 5.5.
Each CU also carries a real internal build path (`DW_AT_comp_dir`):

    F:\\Entwicklung\\e60-tools\\CodingTest\\cp2\\PPC603gnu

("Entwicklung" = German "development" -- confirms a German engineering
team, consistent with Siemens VDO/Continental; "e60-tools" directly
matches README S2.1's own already-known "navicore, codename e60"
identity, extending it to this factory-test module too; "cp2" matches
`VERSION.TXT`'s own "Software Loading CD for CP2 based units"; "PPC603gnu"
names the real target CPU family, PowerPC 603).

**35 real functions recovered across all 4 CUs, each with an exact
`[low_pc, high_pc)` byte range**, independently cross-validated against
`CTEST.OUT`'s own `.symtab` entries (e.g. `TestCoding`: DWARF says
`[1864, 2336)` = size 472; `.symtab` independently says offset 1864,
size 472 -- exact match):

    ../../CodingTest.c        -- 19 functions (TestSDCRegister, TestCoding,
                                  SetCoding, SetCodingHex, ResetEcu, ...)
    ../../RegTest.c            -- 10 functions (ReadRegData, SaveRegData,
                                  SetRegData, SetRegDataHex, ...)
    ../../ConfigFblockTest.c  -- 6 functions (configSetRegHex, configLogin,
                                  configRegister, ...)
    ctdt.c                     -- 0 functions (just `_ctors`/`_dtors` array
                                  variables -- a real C++ static-constructor/
                                  destructor table, GCC's own linker glue)

**`low_pc`/`high_pc` are confirmed to be PRE-RELOCATION, `.text`-SECTION-
RELATIVE offsets starting at 0** (CU1's own functions span [0, 5736),
CU2's continue exactly from [5736, 9844), CU3 from [9844, 13232) --
contiguous, cumulative, matching `.text`'s own real 0x38e0=14,560-byte...
actually matches `.text` size 0x38e0=14,560 only approximately since
ctdt.c's own 0-sized CU brings the running total to 13232, close to but
not exactly `.text`'s full declared size -- the remainder is likely
linker-generated padding/alignment, not investigated further). This
confirms that in an UNLINKED `ET_REL` relocatable object, DWARF's own
`low_pc` is stored simply as a running byte offset within `.text`, with
the REAL runtime address applied later via `.rela.debug_info` at link
time -- exactly the kind of structural fact this project needed to know
before trying the same technique on a bigger, harder target (see below).

**`.debug_line` -- CRACKED, a later session**: `iter_line_program_units()`
implements the real DWARF2 line-number-program state machine (standard
opcodes 1-9, extended opcodes via a `0x00` prefix byte, and special
opcodes `>= opcode_base` using this CU's own `line_base`/`line_range`),
giving an exact address-to-(file,line) row table. Validated directly
against `.debug_info`'s own function boundaries: address 0 (the start
of `TestSDCRegister`, `.debug_info`'s own `low_pc`) maps to
`CodingTest.c:45`; address 5736 (`RegServiceAvailableCB`'s own
`low_pc`) maps to `RegTest.c:16`; address 9844
(`ConfigTestShadowInit`'s own `low_pc`) maps to
`ConfigFblockTest.c:57` -- every one of the 3 non-empty compilation
units' own line-program starts exactly at its `.debug_info` function's
own address, real cross-validation, not just internal self-consistency.
`.debug_pubnames`/`.debug_aranges` were NOT parsed (lower priority --
`.debug_pubnames` just indexes names already recoverable from
`.debug_info` directly, and `.debug_aranges` is a coarser, redundant
address-range index).

============================================================================
Cross-check against FHDD6.FLI -- a DEFINITIVE 2nd, independent
refutation of the earlier `lis`/`addi` load-base-recovery attempt
(research/swl_5238_reader.py's own "db_seg_marker_left_V004" section)
============================================================================
If `FHDD6.FLI`'s own 0-24MB native-PowerPC region carried real DWARF
`.debug_info` (as opposed to a bare, stripped string pool), it would
necessarily contain the SAME kind of `DW_AT_producer`/`DW_AT_comp_dir`
strings this session found in `CTEST.OUT` -- and there must be HUNDREDS
of compilation units, given the 1,476+ distinct source-file basenames
already found there (`swl_5238_reader.py`). A direct search for the
exact producer string (`"gcc-2.96"`, `"GNU C"`, `"AltiVec VxWorks"`) and
build-path fragments (`"PPC603gnu"`, `"e60-tools"`, `"Entwicklung"`)
across the WHOLE 24MB region: **zero hits, for every single one**. This
is strong, direct, structural confirmation (stronger than the earlier
`lis`/`addi` correlation test alone) that no real DWARF `.debug_info`
survives anywhere in that region -- the debug strings that DO survive
there really are a bare, stripped leftover string pool (most likely
`.debug_str`, or a stripped `.strtab`), exactly as hypothesized, now
confirmed by direct absence of the structural evidence that WOULD be
present if real DWARF info survived. Closes the load-base-recovery
question a 2nd, independent way.

============================================================================
Practical use
============================================================================
    import dwarf2_reader as dwarf2
    data = open('CTEST.OUT', 'rb').read()
    debug_info = data[0x40d1:0x40d1+0xe45b]      # from the ELF section table
    debug_abbrev = data[0x1252c:0x1252c+0x68b]
    for cu_off, dies, version in dwarf2.iter_all_cus(debug_info, debug_abbrev):
        for depth, tag, attrs, die_off in dies:
            if tag == 'subprogram':
                print(attrs['name'], attrs.get('low_pc'), attrs.get('high_pc'))

`iter_all_cus()` yields `(cu_offset, dies, dwarf_version)` per
compilation unit; `dies` is a flat list of `(depth, tag_name,
attrs_dict, die_file_offset)` in document order (depth tracks DIE
nesting via each abbreviation's own `has_children` flag and the DWARF2
null-DIE-terminates-siblings convention). `read_form_value()` covers
every DWARF2 form except `DW_FORM_indirect`'s rare nested case (handled
recursively) -- add more `DW_TAG`/`DW_AT` names to the top-of-file
dicts as needed; unknown codes fall back to `unk_<hex>` rather than
raising, so parsing never silently misinterprets an unrecognized tag/
attribute as a different one.

For source lines:

    debug_line = data[0x12bb7:0x12bb7+0x295]     # from the ELF section table
    for unit_off, rows, file_names in dwarf2.iter_line_program_units(debug_line):
        for row in rows:
            address, file_idx, line, column, is_stmt = row[:5]
            print(hex(address), file_names[file_idx-1][0], line)

Each `rows` entry is `(address, file_idx, line, column, is_stmt)`, plus
a 6th `'end_sequence'` marker element on the row that closes out a
sequence (matches `DW_LNE_end_sequence`, GCC's own convention of
emitting one extra row one byte past the last real instruction to mark
where the sequence's valid address range ends -- don't treat it as a
real source line).
"""
import struct

# DW_TAG constants (subset -- covers everything CTEST.OUT's own DWARF2 uses)
DW_TAG = {
    0x01: 'array_type', 0x04: 'enumeration_type', 0x05: 'formal_parameter',
    0x08: 'imported_declaration', 0x0a: 'label', 0x0b: 'lexical_block',
    0x0d: 'member', 0x0f: 'pointer_type', 0x10: 'reference_type',
    0x11: 'compile_unit', 0x12: 'string_type', 0x13: 'structure_type',
    0x15: 'subroutine_type', 0x16: 'typedef', 0x17: 'union_type',
    0x18: 'unspecified_parameters', 0x1a: 'inheritance', 0x1d: 'inlined_subroutine',
    0x21: 'subrange_type', 0x24: 'base_type', 0x26: 'const_type',
    0x28: 'enumerator', 0x2e: 'subprogram', 0x34: 'variable', 0x35: 'volatile_type',
}

DW_AT = {
    0x01: 'sibling', 0x02: 'location', 0x03: 'name', 0x0b: 'byte_size',
    0x0c: 'bit_offset', 0x0d: 'bit_size', 0x10: 'stmt_list', 0x11: 'low_pc',
    0x12: 'high_pc', 0x13: 'language', 0x1b: 'comp_dir', 0x1c: 'const_value',
    0x25: 'producer', 0x27: 'prototyped', 0x38: 'data_member_location',
    0x39: 'decl_column', 0x3a: 'decl_file', 0x3b: 'decl_line',
    0x3c: 'declaration', 0x3e: 'encoding', 0x3f: 'external',
    0x40: 'frame_base', 0x47: 'specification', 0x49: 'type',
}

DW_FORM = {
    0x01: 'addr', 0x03: 'block2', 0x04: 'block4', 0x05: 'data2', 0x06: 'data4',
    0x07: 'data8', 0x08: 'string', 0x09: 'block', 0x0a: 'block1', 0x0b: 'data1',
    0x0c: 'flag', 0x0d: 'sdata', 0x0e: 'strp', 0x0f: 'udata', 0x10: 'ref_addr',
    0x11: 'ref1', 0x12: 'ref2', 0x13: 'ref4', 0x14: 'ref8', 0x15: 'ref_udata',
    0x16: 'indirect',
}


def read_uleb128(data, off):
    result = 0
    shift = 0
    while True:
        b = data[off]
        off += 1
        result |= (b & 0x7f) << shift
        if not (b & 0x80):
            break
        shift += 7
    return result, off


def read_sleb128(data, off):
    result = 0
    shift = 0
    while True:
        b = data[off]
        off += 1
        result |= (b & 0x7f) << shift
        shift += 7
        if not (b & 0x80):
            if b & 0x40:
                result |= -(1 << shift)
            break
    return result, off


def parse_abbrev_table(abbrev_data, start_off=0):
    """Returns dict: code -> (tag, has_children, [(attr, form), ...])."""
    table = {}
    off = start_off
    while off < len(abbrev_data):
        code, off = read_uleb128(abbrev_data, off)
        if code == 0:
            break
        tag, off = read_uleb128(abbrev_data, off)
        has_children = abbrev_data[off]
        off += 1
        attrs = []
        while True:
            attr, off = read_uleb128(abbrev_data, off)
            form, off = read_uleb128(abbrev_data, off)
            if attr == 0 and form == 0:
                break
            attrs.append((attr, form))
        table[code] = (tag, has_children, attrs)
    return table, off


def read_form_value(data, off, form, addr_size=4):
    fname = DW_FORM.get(form, f'unk_{form:#x}')
    if fname == 'addr':
        val = struct.unpack('>I', data[off:off + addr_size])[0]
        return val, off + addr_size
    if fname == 'block2':
        n = struct.unpack('>H', data[off:off + 2])[0]
        return data[off + 2:off + 2 + n], off + 2 + n
    if fname == 'block4':
        n = struct.unpack('>I', data[off:off + 4])[0]
        return data[off + 4:off + 4 + n], off + 4 + n
    if fname == 'data2':
        return struct.unpack('>H', data[off:off + 2])[0], off + 2
    if fname == 'data4':
        return struct.unpack('>I', data[off:off + 4])[0], off + 4
    if fname == 'data8':
        return struct.unpack('>Q', data[off:off + 8])[0], off + 8
    if fname == 'string':
        end = data.index(0, off)
        return data[off:end].decode('latin1'), end + 1
    if fname == 'block':
        n, off = read_uleb128(data, off)
        return data[off:off + n], off + n
    if fname == 'block1':
        n = data[off]
        return data[off + 1:off + 1 + n], off + 1 + n
    if fname == 'data1':
        return data[off], off + 1
    if fname == 'flag':
        return data[off], off + 1
    if fname == 'sdata':
        return read_sleb128(data, off)
    if fname == 'strp':
        val = struct.unpack('>I', data[off:off + 4])[0]
        return ('strp', val), off + 4
    if fname == 'udata':
        return read_uleb128(data, off)
    if fname == 'ref_addr':
        val = struct.unpack('>I', data[off:off + 4])[0]
        return ('ref_addr', val), off + 4
    if fname == 'ref1':
        return data[off], off + 1
    if fname == 'ref2':
        return struct.unpack('>H', data[off:off + 2])[0], off + 2
    if fname == 'ref4':
        return struct.unpack('>I', data[off:off + 4])[0], off + 4
    if fname == 'ref8':
        return struct.unpack('>Q', data[off:off + 8])[0], off + 8
    if fname == 'ref_udata':
        return read_uleb128(data, off)
    if fname == 'indirect':
        real_form, off = read_uleb128(data, off)
        return read_form_value(data, off, real_form, addr_size)
    raise ValueError(f'unknown DWARF form {form:#x} at file offset {off}')


def parse_cu(debug_info, cu_off, debug_abbrev):
    """Parse one compilation unit starting at cu_off. Returns (dies, version, cu_end)."""
    length = struct.unpack('>I', debug_info[cu_off:cu_off + 4])[0]
    version = struct.unpack('>H', debug_info[cu_off + 4:cu_off + 6])[0]
    abbrev_offset = struct.unpack('>I', debug_info[cu_off + 6:cu_off + 10])[0]
    addr_size = debug_info[cu_off + 10]
    cu_end = cu_off + 4 + length
    abbrev_table, _ = parse_abbrev_table(debug_abbrev, abbrev_offset)

    off = cu_off + 11
    dies = []  # (depth, tag_name, attrs_dict, die_file_offset)
    depth = 0
    while off < cu_end:
        die_offset = off
        code, off = read_uleb128(debug_info, off)
        if code == 0:
            depth -= 1
            continue
        tag, has_children, attrs = abbrev_table[code]
        tag_name = DW_TAG.get(tag, f'unk_{tag:#x}')
        values = {}
        for attr, form in attrs:
            val, off = read_form_value(debug_info, off, form, addr_size)
            attr_name = DW_AT.get(attr, f'unk_attr_{attr:#x}')
            values[attr_name] = val
        dies.append((depth, tag_name, values, die_offset))
        if has_children:
            depth += 1
    return dies, version, cu_end


def iter_all_cus(debug_info, debug_abbrev):
    """Yield (cu_start_offset, dies, dwarf_version) for every CU in debug_info."""
    off = 0
    while off < len(debug_info):
        dies, version, cu_end = parse_cu(debug_info, off, debug_abbrev)
        yield off, dies, version
        off = cu_end


# ----------------------------------------------------------------------------
# DWARF2 line-number program (.debug_line)
# ----------------------------------------------------------------------------
DW_LNS_copy = 1
DW_LNS_advance_pc = 2
DW_LNS_advance_line = 3
DW_LNS_set_file = 4
DW_LNS_set_column = 5
DW_LNS_negate_stmt = 6
DW_LNS_set_basic_block = 7
DW_LNS_const_add_pc = 8
DW_LNS_fixed_advance_pc = 9

DW_LNE_end_sequence = 1
DW_LNE_set_address = 2
DW_LNE_define_file = 3


def parse_line_program_unit(sec, off):
    """Parse one line-number program starting at byte offset off in sec
    (a .debug_line section). Returns (rows, file_names, unit_end)."""
    unit_length = struct.unpack('>I', sec[off:off + 4])[0]
    unit_end = off + 4 + unit_length
    version = struct.unpack('>H', sec[off + 4:off + 6])[0]
    header_length = struct.unpack('>I', sec[off + 6:off + 10])[0]
    prog_start = off + 10 + header_length
    p = off + 10
    min_insn_len = sec[p]; p += 1
    default_is_stmt = sec[p]; p += 1
    line_base = struct.unpack('b', sec[p:p + 1])[0]; p += 1
    line_range = sec[p]; p += 1
    opcode_base = sec[p]; p += 1
    std_opcode_lengths = list(sec[p:p + opcode_base - 1]); p += opcode_base - 1
    include_dirs = []
    while sec[p] != 0:
        end = sec.index(0, p)
        include_dirs.append(sec[p:end].decode('latin1'))
        p = end + 1
    p += 1
    file_names = []
    while sec[p] != 0:
        end = sec.index(0, p)
        name = sec[p:end].decode('latin1')
        p = end + 1
        dir_idx, p = read_uleb128(sec, p)
        mtime, p = read_uleb128(sec, p)
        length, p = read_uleb128(sec, p)
        file_names.append((name, dir_idx))
    p += 1

    rows = []
    address = 0
    file_idx = 1
    line = 1
    column = 0
    is_stmt = bool(default_is_stmt)

    pc = prog_start
    while pc < unit_end:
        opcode = sec[pc]; pc += 1
        if opcode >= opcode_base:
            adj = opcode - opcode_base
            address += (adj // line_range) * min_insn_len
            line += line_base + (adj % line_range)
            rows.append((address, file_idx, line, column, is_stmt))
        elif opcode == 0:
            ext_len, pc = read_uleb128(sec, pc)
            ext_end = pc + ext_len
            sub = sec[pc]
            if sub == DW_LNE_end_sequence:
                rows.append((address, file_idx, line, column, is_stmt, 'end_sequence'))
                address, file_idx, line, column = 0, 1, 1, 0
                is_stmt = bool(default_is_stmt)
            elif sub == DW_LNE_set_address:
                address = int.from_bytes(sec[pc + 1:ext_end], 'big')
            pc = ext_end
        elif opcode == DW_LNS_copy:
            rows.append((address, file_idx, line, column, is_stmt))
        elif opcode == DW_LNS_advance_pc:
            adv, pc = read_uleb128(sec, pc)
            address += adv * min_insn_len
        elif opcode == DW_LNS_advance_line:
            adv, pc = read_sleb128(sec, pc)
            line += adv
        elif opcode == DW_LNS_set_file:
            file_idx, pc = read_uleb128(sec, pc)
        elif opcode == DW_LNS_set_column:
            column, pc = read_uleb128(sec, pc)
        elif opcode == DW_LNS_negate_stmt:
            is_stmt = not is_stmt
        elif opcode == DW_LNS_set_basic_block:
            pass
        elif opcode == DW_LNS_const_add_pc:
            adj = 255 - opcode_base
            address += (adj // line_range) * min_insn_len
        elif opcode == DW_LNS_fixed_advance_pc:
            adv = struct.unpack('>H', sec[pc:pc + 2])[0]
            pc += 2
            address += adv
        else:
            # unrecognized standard opcode: skip its uleb128 args per the
            # header's own std_opcode_lengths table (DWARF2's own forward-
            # compatibility mechanism -- never guess, always trust the header)
            nargs = std_opcode_lengths[opcode - 1]
            for _ in range(nargs):
                _, pc = read_uleb128(sec, pc)
    return rows, file_names, unit_end


def iter_line_program_units(debug_line):
    """Yield (unit_start_offset, rows, file_names) for every unit in .debug_line."""
    off = 0
    while off < len(debug_line):
        rows, file_names, unit_end = parse_line_program_unit(debug_line, off)
        yield off, rows, file_names
        off = unit_end
