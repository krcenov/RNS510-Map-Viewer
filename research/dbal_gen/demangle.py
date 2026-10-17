"""GCC 2.x / cfront-style C++ demangler, scoped to what DBAL.OUT actually uses.

We don't need to reconstruct parameter types from the mangled suffix --
Ghidra's own decompiled signature already has real parameter types (it
derived them from the PowerPC calling convention, not from the mangling).
We only need the mangled name to recover: is this a plain function, a
free (non-member) function, a constructor, a destructor, or a method
(and if so, on which [possibly namespace-qualified] class, and is it const).
"""

import re

TYPE_PRIMITIVES = {
    'v': 'void', 'i': 'int', 'l': 'long', 's': 'short', 'c': 'char',
    'b': 'bool', 'f': 'float', 'd': 'double', 'w': 'wchar_t', 'e': '...',
}


def read_len_prefixed(s, pos):
    """s[pos:] starts with <digits><name of that many chars>. Returns (name, new_pos)."""
    m = re.match(r'\d+', s[pos:])
    if not m:
        return None, pos
    n = int(m.group())
    start = pos + len(m.group())
    name = s[start:start + n]
    return name, start + n


def read_qualified(s, pos):
    """s[pos] == 'Q'. Format: Q<N><len-prefixed>*N. Returns (['ns1','ns2',...,'Class'], new_pos)."""
    assert s[pos] == 'Q'
    n = int(s[pos + 1])
    pos += 2
    parts = []
    for _ in range(n):
        name, pos = read_len_prefixed(s, pos)
        parts.append(name)
    return parts, pos


def demangle(raw):
    """Returns a dict describing the symbol:
        {kind: 'plain'|'free'|'ctor'|'dtor'|'method'|'vtable'|'typeinfo_obj'|'typeinfo_func'|'unknown',
         scope: ['Namespace','Class'] or None,   # full qualification, last element is the class
         member: method/base name or None,
         const: bool,
         raw: original mangled text}
    """
    out = {'kind': None, 'scope': None, 'member': None, 'const': False, 'raw': raw}

    if raw.startswith('_vt$'):
        rest = raw[4:]
        scope, _ = (read_qualified(rest, 0) if rest.startswith('Q') else
                     ([read_len_prefixed(rest, 0)[0]], 0))
        out['kind'] = 'vtable'
        out['scope'] = scope
        return out

    if raw.startswith('__ti'):
        rest = raw[4:]
        scope, _ = (read_qualified(rest, 0) if rest.startswith('Q') else
                     ([read_len_prefixed(rest, 0)[0]], 0))
        out['kind'] = 'typeinfo_obj'
        out['scope'] = scope
        return out

    if raw.startswith('__tf'):
        rest = raw[4:]
        scope, _ = (read_qualified(rest, 0) if rest.startswith('Q') else
                     ([read_len_prefixed(rest, 0)[0]], 0))
        out['kind'] = 'typeinfo_func'
        out['scope'] = scope
        return out

    if raw.startswith('_$_'):
        rest = raw[3:]
        scope, _ = (read_qualified(rest, 0) if rest.startswith('Q') else
                     ([read_len_prefixed(rest, 0)[0]], 0))
        out['kind'] = 'dtor'
        out['scope'] = scope
        out['member'] = '~' + scope[-1]
        return out

    if '__' not in raw:
        out['kind'] = 'plain'
        out['member'] = raw
        return out

    idx = raw.index('__')
    base = raw[:idx]
    suffix = raw[idx + 2:]

    const = False
    if suffix[:1] == 'C' and suffix[1:2].isdigit():
        const = True
        suffix = suffix[1:]
    elif suffix[:1] == 'C' and suffix[1:2] == 'Q':
        const = True
        suffix = suffix[1:]

    if suffix[:1] == 'F':
        out['kind'] = 'free'
        out['member'] = base
        out['const'] = const
        return out

    if suffix[:1].isdigit():
        scope_name, _ = read_len_prefixed(suffix, 0)
        scope = [scope_name]
    elif suffix[:1] == 'Q':
        scope, _ = read_qualified(suffix, 0)
    else:
        out['kind'] = 'unknown'
        return out

    out['scope'] = scope
    out['const'] = const
    if base == '':
        out['kind'] = 'ctor'
        out['member'] = scope[-1]
    else:
        out['kind'] = 'method'
        out['member'] = base
    return out


if __name__ == '__main__':
    tests = [
        'getValueLong__C17DBFIntegerSpecial',
        '__10DBFIntegerP7DBFItemsR10DBFRawData',
        '_$_17DBFIntegerSpecial',
        '_vt$17DBFIntegerSpecial',
        '__ti17DBFIntegerSpecial',
        '__tf24FeaCoordReceiverInternal',
        'kd_pdecend__FUiPC6DBRectP17DB_KD_ParamStruct',
        'db_city_V000',
        'atoi',
        'isPossible__C8DBFIndexQ28DBFIndex17DBFIndexOperation',
        '_$_Q34dbal8phonemes17CPhonemeEUHandler',
        'init__Q34dbal8phonemes17CPhonemeEUHandler',
        'getPhonemeList__Q34dbal8phonemes17CPhonemeEUHandlerRQ34dbal8phonemes20PhonemeRetrievalInfo',
        'setCatalogListId__18CatalogListAllDatal',
        'gcc2_compiled.',
        'strlen__10DBFIntegerc',
        'db_road_data_r__FUlP6DBRectPvPFPC8roaddataPv_10ARR_RESULT32db_road_data_roundabout_handling',
    ]
    for t in tests:
        print(t, '->', demangle(t))
