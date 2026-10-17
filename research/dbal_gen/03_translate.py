import re, os, sys, pickle
from collections import defaultdict

with open(r"C:\Users\PC\AppData\Local\Temp\claude\c--Users-PC-Desktop-RNS510\b36ea6fd-e6fc-4628-8258-2b448f26d38f\scratchpad\funcs2.pkl", 'rb') as fh:
    funcs = pickle.load(fh)

with open(r"C:\Users\PC\AppData\Local\Temp\claude\c--Users-PC-Desktop-RNS510\b36ea6fd-e6fc-4628-8258-2b448f26d38f\scratchpad\max_call_arity.pkl", 'rb') as fh:
    MAX_CALL_ARITY = pickle.load(fh)


def pad_params_to_arity(name, params):
    """Mirrors 04_emit.py's own pad_to_arity() exactly (same MAX_CALL_ARITY
    source) -- a definition padded with extra parameters its own matching
    declaration doesn't also have (or vice versa) is a flat conflicting-
    declaration error, so both sides MUST agree. No defaults here (this is
    the definition, not the declaration) -- just enough extra named
    parameters, silently unused in the body, to match the real call sites'
    own maximum argument count."""
    need = MAX_CALL_ARITY.get(name, 0)
    have = len(params)
    if need <= have:
        return params
    return params + [f'long paramExtra{i}' for i in range(have, need)]


OUT_ROOT = r"C:\Users\PC\Desktop\RNS510\BASE\CUSTOM\CD_CUSTOM\DBAL"

IDENT_RE = lambda name: re.compile(r'(?<![A-Za-z0-9_])' + re.escape(name) + r'(?![A-Za-z0-9_])')

_name_type_re = re.compile(r'^(.*?)([A-Za-z_][A-Za-z0-9_]*)$')


def param_name(p):
    m = _name_type_re.match(p.strip())
    return m.group(2) if m else p


def param_type(p):
    m = _name_type_re.match(p.strip())
    return m.group(1).strip() if m else 'int'


def split_params(s):
    """Top-level comma split, respecting () [] <> nesting."""
    parts = []
    depth = 0
    cur = []
    for ch in s:
        if ch in '([<':
            depth += 1
        elif ch in ')]>':
            depth -= 1
        if ch == ',' and depth == 0:
            parts.append(''.join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    tail = ''.join(cur).strip()
    if tail:
        parts.append(tail)
    return parts


def find_matching_paren(s, open_idx):
    """s[open_idx] == '('. Returns index of its matching ')'."""
    depth = 0
    for i in range(open_idx, len(s)):
        if s[i] == '(':
            depth += 1
        elif s[i] == ')':
            depth -= 1
            if depth == 0:
                return i
    return -1


CODE_CALL_RE = re.compile(r'\(\*(\*?)\(code (\*\*?)\)\(')


def fix_code_calls(text):
    """C (and Ghidra's own pseudo-C) allows calling through an arbitrary
    function-pointer-typed expression regardless of how many arguments are
    passed; real C++ requires the function pointer's own type to match the
    call exactly. `code` is Ghidra's generic "pointer to executable code"
    placeholder with no parameter list of its own, so every indirect call
    through it (`(**(code **)(EXPR))(ARGS)` / `(*(code *)(EXPR))(ARGS)`)
    needs a per-call-site cast to a function pointer type with the right
    ARITY. Every argument/return slot is typed `long` (this is a 32-bit
    target where int/long/pointer are all one register-width value, so this
    is a safe, behavior-preserving stand-in, not a semantic change) -- this
    recovers compilability without needing to know each callback's real,
    specific signature."""
    out = []
    pos = 0
    while True:
        m = CODE_CALL_RE.search(text, pos)
        if not m:
            out.append(text[pos:])
            break
        out.append(text[pos:m.start()])
        stars = m.group(2)  # '*' or '**'
        cast_open = m.end() - 1  # the '(' right before EXPR
        cast_close = find_matching_paren(text, cast_open)
        expr = text[cast_open + 1:cast_close]
        # the whole "(**(code**)(EXPR)" sits inside one more grouping paren
        # (needed so the deref binds before the call) -- skip past ITS close
        # too before looking for the call's own '('.
        after_expr = text[cast_close + 1:]
        if not after_expr.lstrip().startswith(')'):
            out.append(text[m.start():cast_close + 1])
            pos = cast_close + 1
            continue
        skip1 = len(after_expr) - len(after_expr.lstrip())
        group_close = cast_close + 1 + skip1  # index of the outer ')'
        rest = text[group_close + 1:]
        rest_stripped = rest.lstrip()
        skipped = len(rest) - len(rest_stripped)
        if not rest_stripped.startswith('('):
            # not actually followed by a call -- leave untouched
            out.append(text[m.start():group_close + 1])
            pos = group_close + 1
            continue
        call_open = group_close + 1 + skipped
        call_close = find_matching_paren(text, call_open)
        args_text = text[call_open + 1:call_close]
        args = split_params(args_text) if args_text.strip() else []
        argtypes = ', '.join(['long'] * len(args)) if args else 'void'
        fnptr_type = f'long (*)({argtypes})' if stars == '*' else f'long (**)({argtypes})'
        # rebuild: (*(fnptr_type)(EXPR))(ARGS)   or   (**(fnptr_type)(EXPR))(ARGS)
        prefix = '(*' + ('*' if stars == '**' else '')
        out.append(f'{prefix}({fnptr_type})({expr}))({args_text})')
        pos = call_close + 1
    return ''.join(out)


BYTE_RANGE_RE = re.compile(r'\b([A-Za-z_][A-Za-z0-9_]*)\._(\d+)_(\d+)_')
_WIDTH_TO_UINT = {1: 'uint8_t', 2: 'uint16_t', 4: 'uint32_t', 8: 'uint64_t'}


def fix_byte_range_access(text):
    """Ghidra's own `NAME._N_M_` notation ("the M-byte sub-range starting at
    byte offset N of NAME") isn't valid C or C++ syntax at all -- it's purely
    an artifact of the decompiler's own internal display for a value it
    represents as a synthetic/overlapping-fields struct (seen here on the
    `__ti*` RTTI symbols, declared as plain scalars in DBAL_externs.h, and a
    few locally-declared buffer variables). Rewriting it to an explicit
    pointer-cast read is the literal, type-accurate equivalent."""
    def repl(m):
        name, off, width = m.group(1), int(m.group(2)), int(m.group(3))
        uint_t = _WIDTH_TO_UINT.get(width, 'uint8_t')
        return f'(*({uint_t} *)((char *)&{name} + {off}))'
    return BYTE_RANGE_RE.sub(repl, text)


_BARE_LIBC_SHADOW_RE = re.compile(r'(?<![.>:\w])\b(strlen)\(')


def fix_libc_name_shadowing(text):
    """A handful of classes (DBFInteger, DBFDataItemAggregate,
    DBFBitComponent, ...) declare their OWN member function also named
    `strlen` (a thin getter wrapping the real one) -- its body's own bare
    call to `strlen(...)` is unambiguously meant for the real C library
    function (that's its entire job), but unqualified name lookup inside a
    member function finds the enclosing class's OWN member of the same
    name FIRST and never falls through to consider the free function at
    all (regardless of signature), which is exactly why the real original
    source must have qualified this call too -- not a behavior change,
    just restoring the qualification any such original source was
    necessarily already written with. Qualifying every bare call to one of
    these common libc names with `::` is always correct for a GENUINE
    call to the real library function, and never fires on an actual member
    call (`obj->strlen(...)`/`obj.strlen(...)`/already-qualified
    `::strlen(...)`), since those all have a `.`/`>`/`:`/word-char directly
    before the name that this regex's negative lookbehind excludes."""
    return _BARE_LIBC_SHADOW_RE.sub(lambda m: '::' + m.group(1) + '(', text)


# `add_roadId__FPC8roaddataPv` is really TWO distinct, same-named
# functions: `db_intersection.cpp`'s own `int(AnyPtr4, int)` (@0x00031654)
# and `dbaccess.cpp`'s own `undefined4(AnyPtr4, AnyPtr4)` (@0x00084e6c) --
# both originally file-scope `static` functions in different translation
# units that happened to share a name, which GCC2/cfront mangling doesn't
# disambiguate (no internal-linkage suffix) and this pipeline's flat-name
# model assumes is globally unique. The free-function forward-declaration
# in `DBAL_freefuncs.h` can only carry ONE of the two shapes; whichever
# file does NOT match it (confirmed: db_intersection.cpp's shape won)
# compiles fine for its OWN definition (a different-signature same-name
# free function is a valid, if confusing, C++ overload) but fails at its
# OWN call site that passes the bare name as a VALUE (not a call) into a
# generic `undefined4` parameter -- with two overloads in scope, there is
# no single address to decay to without an explicit cast naming the
# intended one. Verified a one-off: the only such flat-name collision
# found in the corpus, so a small hardcoded, hand-verified table (same
# style as the other individually-confirmed overrides in 04_emit.py)
# rather than a general mechanism.
_AMBIGUOUS_OVERLOAD_CAST = {
    'add_roadId__FPC8roaddataPv': 'undefined4 (*)(AnyPtr4, AnyPtr4)',
}


def fix_ambiguous_overload_refs(body, own_file):
    if 'dbaccess.cpp' not in own_file:
        return body
    for name, cast in _AMBIGUOUS_OVERLOAD_CAST.items():
        body = re.sub(
            r'\b' + re.escape(name) + r'\b(?!\s*\()',
            f'(({cast}){name})', body)
    return body


VOID_DISCARD_RE = re.compile(
    r'\n(?P<indent>[ \t]*)(?P<expr>(?:\([^\n;]*?\)|[A-Za-z_][A-Za-z0-9_]*)\s*\([^\n;]*\))\s*;\s*\n[ \t]*return;\s*\n\}\s*\Z'
)


_CALL_TARGET_NAME_RE = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*)\s*\(')


def classify_code_star_name(name, body, _visiting=None):
    """A `code *NAME` (parameter OR local) is Ghidra's generic spelling for
    BOTH of two genuinely different things that happen to look identical in
    its own text, and only this specific NAME's own usage within the body
    can tell them apart:

    1. A real callback: NAME directly HOLDS a function pointer, and real
       call sites pass a concrete function (e.g. `Sort(n, someCmpFn)`) or
       is itself assigned a bare function name (`NAME = someFunc;`).
       Ghidra's `code *` here is one indirection level too deep (`code`
       already IS a function pointer) -- needs flattening to plain `code`
       (confirmed safe: -fpermissive downgrades the resulting signature
       mismatch to a warning, same path already proven for the `_fp_*`
       globals).

    2. A raw vtable-slot address: NAME is fed by an actual double
       dereference (`*(code **)(obj + off)`, the standard vtable-call
       idiom), itself double-dereferenced (`**NAME`), or assigned from /
       compared against an explicit `(code *)`-cast expression (the
       cast's OWN target type already says 2-level, in NAME's own words)
       -- genuinely 2-level, matches Ghidra's `code *` exactly as written,
       must NOT be touched (confirmed by real regressions: flattening
       `db_kd.cpp`'s `pcVar10 = *(code **)(param_3 + 0x48);`, and
       `CPhonemeNAFileReaderHandler.cpp`'s `pcVar7 = (code *)param_5[4];`,
       both broke once flattened on OTHER evidence alone).

       NOTE: calling through NAME with exactly one dereference
       (`(*NAME)(args)`) is NOT usable as evidence either way -- dropping
       it as a signal (an earlier version of this function treated it as
       1-level evidence) was itself a necessary correction: dereferencing
       either a 1-level `code` (yields the function back, a legal no-op
       round-trip) or a 2-level `code *` (yields the 1-level function
       pointer) and calling it both compile and behave identically, so
       this syntax alone proves nothing about which level NAME really is.

    Evidence for (2) wins outright over evidence for (1), since storing a
    2-level address into something later treated as 1-level would be a
    real (if rare) behavioral ambiguity we're not positioned to resolve
    either way; only flatten when (1)'s evidence is present and (2)'s is
    not. A null/`0x0`/`NULL` operand on an explicit `(code *)` cast does
    NOT count as (2)'s evidence (confirmed: `db_road_sel_char.cpp`'s
    `pcVar2 = (code *)0x0;` is one of several assignments to a NAME that
    is otherwise unambiguously 1-level elsewhere in the same body -- a
    null check/clear doesn't actually tell you the real level, unlike a
    cast of a real address). Absent either kind of evidence, the safe
    default is to leave NAME untouched (matches Ghidra's own text, never
    introduces a NEW error for a case we have no evidence about)."""
    double_re = re.compile(
        r'\*\*\s*' + re.escape(name) + r'\b'            # **NAME
        r'|' + re.escape(name) + r'\s*=\s*\*\s*\(\s*code\s*\*\*'  # NAME = *(code **)...
    )
    if double_re.search(body):
        return 'keep'
    # An explicit `(code *)` cast sharing NAME's own statement (bounded by
    # `;`/`{`/`}` on both sides, so an `if (...)  {` CONDITION -- which
    # has no terminating `;` of its own before its `{` -- never bleeds
    # into matching code deep inside its own body) -- either assigned
    # straight across or compared against -- is 2-level evidence, unless
    # the cast is applied to a trivial null/zero (see docstring).
    for stmt_m in re.finditer(r'[^;{}]*\(\s*code\s*\*\s*\)[^;{}]*;', body):
        stmt = stmt_m.group(0)
        if not re.search(r'\b' + re.escape(name) + r'\b', stmt):
            continue
        if re.search(r'\(\s*code\s*\*\s*\)\s*(?:0x0\b|0\b|NULL\b|nullptr\b)', stmt):
            continue
        return 'keep'
    # A parameter with NO internal evidence of its own (never reassigned,
    # never cast) but called through with exactly one dereference
    # (`(*NAME)(args)`) -- this is NOT proof of 1-level on its own (the
    # docstring explains why calling through either level looks
    # identical), but it IS the only signal available for the common
    # "pure callback parameter, never touched beyond being called"
    # shape (`DuCacheindexBase::Sort(code *param_2) { ...
    # (*param_2)(args); }`, where real call sites pass a bare function
    # directly) -- checked LAST, after every real 2-level signal above
    # has already had first refusal, so it only ever decides cases those
    # couldn't.
    single_call_re = re.compile(r'\(\s*\*\s*' + re.escape(name) + r'\s*\)\s*\(')
    bare_assign_re = re.compile(
        r'\b' + re.escape(name) + r'\s*=\s*([A-Za-z_][A-Za-z0-9_]*)\s*;')
    m = bare_assign_re.search(body)
    if m and m.group(1) not in ('0', 'NULL', 'nullptr'):
        return 'flatten'
    if single_call_re.search(body):
        return 'flatten'
    # NAME itself has no direct evidence either way, but if it's assigned
    # straight across into ANOTHER name (`other = NAME;`, no cast/deref in
    # between) and THAT name recursively classifies as 1-level, NAME is
    # really the exact same value flowing through unchanged and must
    # match -- otherwise the two independently-"safe" per-name defaults
    # disagree with each other, which is itself a real, confirmed
    # regression: `db_kd.cpp`'s `db_kd_search`, a parameter `param_8`
    # (code *, no direct evidence of its own) flows via plain assignment
    # into a local `local_48` that IS unambiguously 1-level (bare-function
    # assigned elsewhere) -- so `local_48` flattens on its own evidence
    # while `param_8` defaulted to "keep" with none, breaking the
    # assignment between them. `_visiting` guards against a (not observed,
    # but structurally possible) alias cycle.
    _visiting = _visiting or set()
    if name not in _visiting:
        alias_re = re.compile(r'\b([A-Za-z_][A-Za-z0-9_]*)\s*=\s*' + re.escape(name) + r'\s*;')
        m2 = alias_re.search(body)
        if m2:
            other = m2.group(1)
            if classify_code_star_name(other, body, _visiting | {name}) == 'flatten':
                return 'flatten'
    return 'keep'


_CODE_STAR_LOCAL_DECL_RE = re.compile(r'\bcode\s*\*\s*([A-Za-z_][A-Za-z0-9_]*)\s*;')


def fix_code_star_locals(body):
    """Local-variable counterpart of genericize_params' `code *` handling
    (see classify_code_star_name) -- Ghidra's own text for a local
    "function pointer holder" looks IDENTICAL (`code *pcVarN;`) whether it
    genuinely needs to stay 2-level (fed by a real vtable-slot double
    dereference) or is one level too deep (assigned a bare concrete
    function directly, or called through with a single `(*pcVarN)(args)`)
    -- same per-NAME evidence check, just applied to a LOCAL declaration
    statement in body text instead of a parsed parameter."""
    flattened = set()
    def repl(m):
        name = m.group(1)
        if classify_code_star_name(name, body) == 'flatten':
            flattened.add(name)
            return f'code {name};'
        return m.group(0)
    body = _CODE_STAR_LOCAL_DECL_RE.sub(repl, body)
    # A NAME just flattened to 1-level may still have an explicit
    # `(code *)`-cast NULL assigned into it elsewhere in the SAME body
    # (`pcVar2 = (code *)0x0;`) -- the null-operand case is specifically
    # EXCLUDED from classify_code_star_name's own 2-level evidence (a
    # null check/clear doesn't prove the real level, see its docstring),
    # so NAME correctly flattens on its OTHER, real evidence -- but the
    # cast's own TEXT is still 2-level and now mismatches the declaration
    # it used to match. Dropping the now-stray extra star only for
    # NAMEs actually flattened above (never touches a genuinely-2-level
    # NAME's own null-check, which still needs to stay `(code **)`-wide
    # to match its own unflattened declaration).
    for name in flattened:
        body = re.sub(
            r'\b' + re.escape(name) + r'(\s*=\s*)\(\s*code\s*\*\s*\)(\s*(?:0x0|0|NULL|nullptr)\b)',
            lambda m, name=name: f'{name}{m.group(1)}(code){m.group(2)}',
            body)
    return fix_code_star_conflicting_bare_assign(body)


def fix_code_star_conflicting_bare_assign(body):
    """`db_upack.cpp`'s `pcVar1` (and a few siblings) is a genuinely
    inconsistent case classify_code_star_name's docstring documents as
    unfixable as a simple flatten/keep choice: the SAME 2-level (`code *`)
    local is fed BOTH a real vtable-slot double-dereference (`pcVar1 =
    *(code **)addr;`, needs 2-level -- correctly kept) AND a bare,
    compile-time-known function directly (`pcVar1 = count__C8DBFIndex;`,
    which decays to a 1-level pointer -- the actual mismatch). Simply
    casting the bare function's OWN address to a 2-level pointer would
    reinterpret its entry-point bytes as if they held ANOTHER address and
    dereferencing it (`*pcVar1`, which real call sites do) would read
    the function's own machine code as data -- genuinely wrong, not just
    a type mismatch.

    The fix that preserves real behavior: give the bare function a real,
    addressable 2-level-COMPATIBLE home -- a `static code` slot holding
    its address -- and point the local at THAT slot instead of at the
    function directly. `&slot` is a real, valid `code*`, and dereferencing
    it correctly yields the function pointer again, exactly like the
    vtable-fetched branch's own address does. One static slot per distinct
    callee name, declared immediately above its own assignment (named
    deterministically from the callee, so repeated assignments to the same
    callee across the function reuse the identical slot text safely)."""
    bare_assign_re = re.compile(
        r'\b([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([A-Za-z_][A-Za-z0-9_]*)\s*;')

    def repl(m):
        name, callee = m.group(1), m.group(2)
        decl_re = re.compile(r'\bcode\s*\*\s*' + re.escape(name) + r'\s*;')
        if not decl_re.search(body) or callee in ('0', 'NULL', 'nullptr'):
            return m.group(0)
        if classify_code_star_name(name, body) != 'keep':
            return m.group(0)
        slot = f'__codeslot_{callee}'
        return f'{{ static code {slot} = {callee}; {name} = &{slot}; }}'
    return bare_assign_re.sub(repl, body)


def fix_void_discarded_return(body, ret_type, definitely_void_names=frozenset()):
    """Several `void`-returning functions' own real decompiled body is just
    one discarded call expression (almost always an indirect vtable/callback
    dispatch, `(**(code**)(...))(args);`) immediately before a bare
    `return;` -- Ghidra's own control-flow analysis missed that the real
    PowerPC code actually returns that inner call's result (a known
    decompiler weakness around indirect-call tail patterns), which is
    exactly why real callers throughout this codebase consistently try to
    use a "void" result as a value. Promoting the body to `return EXPR;` and
    the declared return type from `void` to `long` (matching `code`'s own
    return type) recovers the real, intended value instead of just
    papering over the resulting type errors -- and is harmless for any
    caller that never used the result in the first place.

    BUT: when the discarded expression is a plain named call (not an
    indirect vtable dispatch) to one of OUR OWN functions that is itself
    genuinely, structurally void (no discard pattern of its own -- a real
    leaf setter with nothing to recover), promoting the CALLER here would
    just relocate the exact same "void value not ignored" error one level
    up (`return trulyVoidSetter(...);` from a now-`long`-returning function
    is just as illegal as assigning its result). `definitely_void_names` is
    the precomputed set of such leaves; calls to anything else (an indirect
    dispatch, or a plain-named EXTERNAL function we don't control, which is
    always declared permissively anyway) are promoted as before."""
    if ret_type.strip() != 'void':
        return body, ret_type
    m = VOID_DISCARD_RE.search(body)
    if not m:
        return body, ret_type
    expr = m.group('expr')
    if not expr.lstrip().startswith('('):
        name_m = _CALL_TARGET_NAME_RE.match(expr.lstrip())
        if name_m and name_m.group(1) in definitely_void_names:
            return body, ret_type
    new_body = body[:m.start()] + f"\n{m.group('indent')}return {m.group('expr')};\n}}"
    return new_body, 'long'


_CODE_STAR_PARAM_RE = re.compile(r'^(?:const\s+)?code\s*\*$')
_GENERIC_PTR_BASE_RE = re.compile(r'^(?:const\s+)?undefined(\d*)\s*\*$')
_FATPTR_NAME = {'': 'AnyPtr1', '1': 'AnyPtr1', '2': 'AnyPtr2', '4': 'AnyPtr4', '8': 'AnyPtr8'}

# "Real" semantically-typed pointers (int*, char*, uint*, ...) cause the
# exact same class of conversion error as undefined*/code (e.g. the now
# much-reduced but still-present `undefined1* -> int*`), and the SAME
# fat-pointer mechanism fixes them the same way -- the earlier concern
# that void* genericization would silently change element-indexed
# arithmetic no longer applies here, since AnyPtrN's own operator[]/
# operator* preserve each width's real element size. Reused by WIDTH
# (not a separate wrapper per semantic type): `int`/`uint`/`long`/`ulong`
# are all 4 bytes on this target, `short`/`ushort` 2, `char`/`uchar`/
# `byte`/`bool` 1 -- AnyPtr4/AnyPtr2/AnyPtr1 already cover them exactly.
_TYPED_PTR_WIDTH_RE = re.compile(
    r'^(?:const\s+)?(int|uint|long|ulong|short|ushort|char|uchar|byte|bool)\s*\*$')
_TYPED_PTR_WIDTH = {
    'int': '4', 'uint': '4', 'long': '4', 'ulong': '4',
    'short': '2', 'ushort': '2',
    'char': '1', 'uchar': '1', 'byte': '1', 'bool': '1',
}


def genericize_params(params, body):
    """Pointer parameters typed as one of Ghidra's own `undefined*`
    placeholders (`undefined1*`, `undefined4*`, ...) are the single
    largest real source of compile errors in this translation -- NOT
    because the underlying code is wrong, but because the ORIGINAL
    C-flavored pseudocode never had real pointer-type safety (every
    caller/callee pair agreeing on "this is N raw bytes of something" was
    enough), while standard C++ requires an EXACT pointer type match to
    pass one implicitly.

    Two earlier, narrower attempts at this are documented in
    DBAL/PROVENANCE.md: a blanket `void*` rewrite broke every function
    that dereferences/indexes such a parameter directly (void* supports
    neither, not even under the GNU void*-arithmetic extension); a
    safety-checked version restricted to PROVABLY-never-dereferenced
    parameters was safe but barely moved the needle, since most of them
    genuinely ARE dereferenced in their own body.

    This version uses a "fat pointer" wrapper instead (DBAL_FATPTR in
    DBAL_types.h: AnyPtr1/2/4/8, one per width) that accepts ANY pointer
    type implicitly (a templated single-argument constructor -- fixes the
    conversion errors at the root, same as `void*` would) while ALSO
    supporting direct dereference (`*param`), indexing (`param[i]`),
    pointer arithmetic (`param + i`), and explicit re-casts to any other
    pointer type (a templated conversion operator) -- so unlike `void*`,
    it does not require proving anything about how the parameter is used
    first. No safety check needed; applies to every `undefined*` pointer
    parameter uniformly. `code*` is deliberately NOT touched here (it is
    a pointer to a function pointer, not a data pointer -- doesn't fit
    this pattern, and already handled separately)."""
    out = []
    for p in params:
        name = param_name(p)
        typ = param_type(p).strip()
        m = _GENERIC_PTR_BASE_RE.match(typ)
        if m:
            out.append(f'{_FATPTR_NAME[m.group(1)]} {name}')
            continue
        m2 = _TYPED_PTR_WIDTH_RE.match(typ)
        if m2:
            out.append(f'{_FATPTR_NAME[_TYPED_PTR_WIDTH[m2.group(1)]]} {name}')
            continue
        m3 = _CODE_STAR_PARAM_RE.match(typ)
        if m3 and classify_code_star_name(name, body) == 'flatten':
            # `code *paramN` -- see classify_code_star_name's docstring.
            # Evidence-based per-NAME check (not a blanket rule in either
            # direction): a blanket "always flatten parameters" version was
            # tried first and regressed on parameters that are genuinely
            # fed a real 2-level vtable-slot address within their OWN body
            # (same failure mode as the local-variable case the docstring
            # describes, just on a parameter instead of a local).
            out.append(f'code {name}')
            continue
        out.append(p)
    return out


def ns_open(scope):
    if not scope or len(scope) < 2:
        return '', ''
    nss = scope[:-1]
    return ''.join(f'namespace {n} {{ ' for n in nss), ' }' * len(nss)


# ---------- pass 0: genericize undefined* pointer params to fat pointers ----------
# See genericize_params()'s own docstring above for the two earlier,
# narrower attempts this supersedes. Must happen BEFORE pass 1 (which
# snapshots params_no_this into `classes` for DBAL_classes.h) so every
# consumer -- class declarations, free-function/wrapper declarations, AND
# the actual definitions emitted below -- sees the SAME already-
# genericized params consistently.
for f in funcs:
    if f['dm']['kind'] in ('method', 'ctor', 'dtor') and f['params']:
        f['params'] = [f['params'][0]] + genericize_params(f['params'][1:], f['body'])
    else:
        f['params'] = genericize_params(f['params'], f['body'])

# ---------- pass 1: collect per-class member lists (declarations) ----------
classes = defaultdict(list)  # scope-tuple -> list of member dicts
free_names_seen = set()

for f in funcs:
    dm = f['dm']
    kind = dm['kind']
    if kind in ('method', 'ctor', 'dtor'):
        scope = tuple(dm['scope'])
        if kind == 'ctor':
            member = dm['scope'][-1] + '_ctor'
        elif kind == 'dtor':
            member = dm['scope'][-1] + '_dtor'
        else:
            member = dm['member']
        params_no_this = f['params'][1:] if f['params'] else []
        classes[scope].append({
            'f': f, 'member': member, 'const': dm['const'],
            'params_no_this': params_no_this,
        })

print('distinct classes/scopes:', len(classes))

# C++ can't overload on return type alone. A few mangled names genuinely
# collide that way (Ghidra inferred a DIFFERENT return type, at a different
# address, for what demangles to the same class/member/const/param-types --
# almost certainly a real overload Ghidra's own signature recovery missed a
# parameter on, not something we can safely second-guess the body of). Give
# every collision after the first a unique member name instead of touching
# return types -- that would risk mismatching the body's own `return`
# statements. The rename is applied consistently to the class declaration,
# the definition, and the forwarding wrapper (all keyed off `m['member']`).
seen_keys = {}
for scope, members in classes.items():
    for m in members:
        key = (scope, m['member'], m['const'], tuple(param_type(p) for p in m['params_no_this']))
        n = seen_keys.get(key, 0)
        seen_keys[key] = n + 1
        if n > 0:
            m['member'] = f"{m['member']}_overload{n + 1}"
            m['f']['dm']['member_override'] = m['member']

# ---------- pass 2: emit ----------
files_out = defaultdict(list)       # relative path (no ext) -> list of text chunks (method defs + wrappers, in addr order)
files_classes = defaultdict(set)    # relative path -> set of scope tuples defined there (first occurrence wins "home" file)
scope_home_file = {}

for f in sorted(funcs, key=lambda x: x['addr']):
    dm = f['dm']
    path = f['assigned_path']
    if dm['kind'] in ('method', 'ctor', 'dtor'):
        scope = tuple(dm['scope'])
        if scope not in scope_home_file:
            scope_home_file[scope] = path

for scope, path in scope_home_file.items():
    files_classes[path].add(scope)

MANIFEST = []
WRAPPER_DECLS = []
BAD_INSN_MARK = 'Bad instruction - Truncating control flow'

# Precompute, BEFORE promoting any caller, which of our own functions
# REMAIN genuinely void after every promotion decision settles -- see
# fix_void_discarded_return's docstring for why a caller must not be
# promoted over a call to one of these.
#
# A single pass over "does f's OWN body even look promotable" isn't
# enough: whether f itself gets promoted can depend on whether ITS OWN
# callee gets promoted, which can cascade (confirmed by a real
# regression -- `PhonemeRetrievalInfo::setSegment` LOOKS promotable, its
# own body ending in a discarded call to `PhonemeKey::setSegment` then
# bare `return;`, but that promotion is correctly REFUSED because
# `PhonemeKey::setSegment` is a genuine terminal void leaf -- yet a
# single static pre-pass has no way to know that refusal happened before
# deciding whether `PhonemeRetrievalInfo::setSegment` itself counts as
# "definitely void" for ITS OWN callers, like `createDummyInfo`, which
# got wrongly promoted over calling it as a result). Iterating to a
# fixed point resolves the whole cascade: start by ASSUMING every
# syntactically-promotable void function WILL promote (optimistic), then
# repeatedly walk back any whose own discarded call target is itself
# still void, until nothing changes.
_void_funcs_by_name = {
    f['ghidra_name']: f for f in funcs
    if f['ret_type'].strip() == 'void' and f['ghidra_name']
}
# promotable[name] = None if that function has no discard-then-return
# shape at all (a genuine leaf, always stays void); otherwise the named
# callee it discards (None here means an INDIRECT call, e.g. a vtable
# dispatch, which fix_void_discarded_return ALWAYS promotes regardless
# of callee -- it only ever refuses promotion for a NAMED callee that is
# itself confirmed to stay void).
_promotable = {}
for _name, _f in _void_funcs_by_name.items():
    _m = VOID_DISCARD_RE.search(_f['body'])
    if _m is None:
        _promotable[_name] = None
        continue
    _expr = _m.group('expr').lstrip()
    if _expr.startswith('('):
        _promotable[_name] = ('indirect', None)
    else:
        _call_m = _CALL_TARGET_NAME_RE.match(_expr)
        _promotable[_name] = ('named', _call_m.group(1) if _call_m else None)
# Start from the confirmed leaves (no discard shape at all) and grow:
# a function that discards a NAMED call to something ALREADY confirmed
# to stay void inherits that and stays void too. Indirect-call discards
# never join -- they always promote, per fix_void_discarded_return.
DEFINITELY_VOID_NAMES = {n for n, p in _promotable.items() if p is None}
_changed = True
while _changed:
    _changed = False
    for _name, _p in _promotable.items():
        if _p is None or _name in DEFINITELY_VOID_NAMES:
            continue
        _kind, _callee = _p
        if _kind == 'named' and _callee in DEFINITELY_VOID_NAMES:
            DEFINITELY_VOID_NAMES.add(_name)
            _changed = True
DEFINITELY_VOID_NAMES = frozenset(DEFINITELY_VOID_NAMES)

# A handful of genuinely/structurally void functions (no discard-then-
# return pattern of their OWN, so fix_void_discarded_return leaves them
# alone) are STILL used as a value by some OTHER caller elsewhere in the
# corpus (`uVar1 = __rs__10DBFRawDataRUc(...);`) -- Ghidra decompiled
# different call sites of the SAME function inconsistently (a known
# decompiler weakness, same root cause as fix_void_discarded_return's own
# cases, just discovered from the CALLER's side instead of the callee's
# own body shape). Promoting the return type and appending a trailing
# `return 0;` (the real value doesn't survive decompilation faithfully at
# all here -- an acknowledged, documented loss of fidelity, same honesty
# standard as the rest of this pipeline) fixes every such caller at once.
ALL_BODIES_TEXT = '\n'.join(f['body'] for f in funcs)
_used_as_value_re_cache = {}


def is_used_as_value(name):
    if name not in _used_as_value_re_cache:
        _used_as_value_re_cache[name] = re.compile(
            r'(?:=|return)\s*\b' + re.escape(name) + r'\b\s*\(')
    return bool(_used_as_value_re_cache[name].search(ALL_BODIES_TEXT))


def fix_void_used_as_value(body, ret_type, name):
    if ret_type.strip() != 'void' or not name or not is_used_as_value(name):
        return body, ret_type
    stripped = body.rstrip()
    if not stripped.endswith('}'):
        return body, ret_type
    new_body = stripped[:-1].rstrip() + '\n  return 0;\n}'
    return new_body, 'undefined4'


for f in sorted(funcs, key=lambda x: x['addr']):
    dm = f['dm']
    path = f['assigned_path']
    kind = dm['kind']
    body = fix_byte_range_access(f['body'])
    body = fix_libc_name_shadowing(body)
    body = fix_ambiguous_overload_refs(body, f['assigned_path'])
    body = fix_code_star_locals(body)
    body, f['ret_type'] = fix_void_discarded_return(body, f['ret_type'], DEFINITELY_VOID_NAMES)
    body, f['ret_type'] = fix_void_used_as_value(body, f['ret_type'], f['ghidra_name'])
    comment = f"// original mangled: {f['mangled']}  @ 0x{f['addr']:08x}  size={f['size']}"
    if f['lead_comment']:
        comment += '\n' + f['lead_comment']

    if BAD_INSN_MARK in body:
        # Ghidra itself couldn't disassemble this function fully (hit a bad/
        # unrecognized instruction and gave up) -- what's left isn't a
        # faithful decompilation, so emitting it as the real definition
        # would silently misrepresent the original behavior. Skip it (any
        # real caller falls back to DBAL_externs.h's permissive extern
        # declaration) rather than emit something we know is wrong.
        chunk = (
            f"{comment}\n"
            f"// NOT emitted: Ghidra's own decompilation hit an "
            f"undisassemblable instruction here and gave up (real body "
            f"unrecoverable from this binary) -- see DBAL_externs.h for the "
            f"permissive extern standing in for any real caller.\n"
        )
        files_out[path].append(chunk)
        MANIFEST.append((f['addr'], f['mangled'], path, kind, 'SKIPPED (bad instruction)'))
        continue

    if kind in ('plain', 'free', 'unknown'):
        if f['ghidra_name'] == 'gcc2_compiled_':
            # Declared `(...)` (variadic) in DBAL_freefuncs.h instead of its
            # own real `(void)` body -- see that declaration's own comment.
            # Skip the per-instance body here too so the two don't conflict
            # (an incompatible redeclaration) and so this trivial, never-
            # really-called marker isn't defined ~9 separate times across
            # different files.
            chunk = (
                f"{comment}\n"
                f"// NOT emitted here: gcc2_compiled_ is declared (...) in "
                f"DBAL_freefuncs.h instead -- see its own comment there.\n"
            )
            files_out[path].append(chunk)
            MANIFEST.append((f['addr'], f['mangled'], path, kind, 'SKIPPED (gcc2_compiled_ marker)'))
            continue
        _def_params = pad_params_to_arity(f['ghidra_name'], f['params'])
        chunk = f"{comment}\n{f['ret_type']} {f['ghidra_name']}({', '.join(_def_params)})\n{body}\n"
        files_out[path].append(chunk)
        MANIFEST.append((f['addr'], f['mangled'], path, kind, None))
        continue

    if kind in ('vtable', 'typeinfo_obj', 'typeinfo_func'):
        # typeinfo_func DOES appear as a real decompiled function (confirmed) -- emit as a
        # free function under its class's home file, flat-named (no wrapper needed, nothing
        # else calls it by a renamed identifier).
        _def_params = pad_params_to_arity(f['ghidra_name'], f['params'])
        chunk = f"{comment}\n{f['ret_type']} {f['ghidra_name']}({', '.join(_def_params)})\n{body}\n"
        files_out[path].append(chunk)
        MANIFEST.append((f['addr'], f['mangled'], path, kind, None))
        continue

    # method / ctor / dtor
    scope = tuple(dm['scope'])
    if kind == 'ctor':
        member = dm['scope'][-1] + '_ctor'
    elif kind == 'dtor':
        member = dm['scope'][-1] + '_dtor'
    else:
        member = dm['member']
    member = dm.get('member_override', member)

    params_no_this = f['params'][1:] if f['params'] else []
    this_param = f['params'][0] if f['params'] else None  # e.g. "int param_1" or "DBFIntegerSpecial *param_1"
    this_name = None
    if this_param:
        m = re.match(r'^(.*?)([A-Za-z_][A-Za-z0-9_]*)$', this_param)
        this_name = m.group(2) if m else None

    qualified_class = '::'.join(scope)
    const_kw = ' const' if dm['const'] else ''
    ret_type = f['ret_type']

    new_body = body
    if this_name:
        # `this` is a typed ClassName* (sizeof unknown -- no data members
        # declared), but the ORIGINAL param_1 was typed (usually `int`, or a
        # differently-sized pointer) and every use of it is raw byte-level
        # address arithmetic (`param_1 + 0x2c` etc). Substituting a bare
        # `this` would silently change that arithmetic's scale (or fail to
        # compile, for an incomplete type) -- casting back to the exact
        # original type on every use preserves the original semantics
        # exactly, since it's numerically the same address either way.
        #
        # Substituted into a REAL LOCAL VARIABLE (declared at the top of
        # the body), not a bare cast EXPRESSION repeated at every use: a
        # handful of functions directly REASSIGN param_1 (`param_1 =
        # EXPR;`), not just read it -- a known PowerPC ABI coincidence
        # where the `this`-pointer register (r3) is ALSO the function's
        # own return-value register, so Ghidra's decompile sometimes uses
        # the same slot for both roles, and the real original C param_1
        # was a genuine by-value parameter, freely reassignable, same as
        # any other. A cast expression is never an lvalue (a real,
        # confirmed `lvalue required` error); a plain local, initialized
        # once to the same numeric value, can be freely read AND
        # reassigned for the rest of the function -- functionally
        # identical to the expression form for the (large majority)
        # read-only cases, and correct for the read-write ones too.
        this_orig_type = param_type(this_param)
        if this_orig_type.strip() in ('float', 'double'):
            # Ghidra occasionally mis-assigns the FIRST parameter slot
            # (always `this`, a pointer, in reality) to a floating-point
            # type -- a known PowerPC decompiler confusion around mixed
            # integer/float ABI parameter passing (floats/doubles pass in
            # a separate register file from `this`'s own GPR, so Ghidra's
            # naive by-index parameter-slot guess can mismatch), confirmed
            # directly: `FeaCoordReceiverInternal::init`'s raw Ghidra
            # signature types BOTH its first two parameters `double`, yet
            # the body clearly uses pointer arithmetic on the others. The
            # round-trip cast exists specifically to preserve byte-offset
            # ARITHMETIC through a numerically-equal cast -- meaningless
            # (and not even compilable) for a non-arithmetic float/double
            # type, so there is no real original semantics to preserve
            # here; falling back to a plain integer type is the most
            # honest "preserve the raw address, drop the bogus float
            # reinterpretation" choice.
            subst_type, init_expr = 'long', '(long)this'
        elif (_CODE_STAR_PARAM_RE.match(this_orig_type.strip())
              and classify_code_star_name(this_name, body) == 'flatten'):
            # Same one-level-too-deep `code *` confusion genericize_params
            # resolves for ordinary parameters/locals (see
            # classify_code_star_name), just on `this` itself -- Ghidra
            # occasionally attributes the leading parameter slot (always
            # `this` in reality, for a real method) as a callback instead,
            # confirmed directly: `DBFViewmodel::init`'s own body calls
            # through it with a single dereference (`(*_param_1_val)
            # (_12DBFViewmodel_datamodel)`), and real callers elsewhere
            # pass a concrete, 1-level function pointer as the first
            # argument. `(code)(void*)this` (a function-pointer result
            # from an object-pointer cast) is a GCC-supported conditional
            # extension, confirmed to compile clean under -fpermissive.
            subst_type, init_expr = 'code', '(code)(void*)this'
        else:
            subst_type, init_expr = this_orig_type, f'({this_orig_type})(void*)this'
        shadow_name = f'_{this_name}_val'
        new_body = IDENT_RE(this_name).sub(shadow_name, new_body)
        brace_pos = new_body.index('{')
        new_body = (new_body[:brace_pos + 1] +
                    f'\n  {subst_type} {shadow_name} = {init_expr};' +
                    new_body[brace_pos + 1:])

    param_decl_str = ', '.join(params_no_this)
    def_chunk = (
        f"{comment}\n"
        f"{ret_type} {qualified_class}::{member}({param_decl_str}){const_kw}\n"
        f"{new_body}\n"
    )

    home = scope_home_file[scope]
    files_out[path].append(def_chunk)
    MANIFEST.append((f['addr'], f['mangled'], path, kind, f"{qualified_class}::{member}"))

    # compatibility wrapper using the ORIGINAL ghidra flat name, so every untouched call site
    # elsewhere in the dump keeps working unchanged. Plain external linkage
    # (NOT static) with its signature forward-declared in DBAL_wrappers.h --
    # a `static` wrapper would only be callable from its own .cpp file, which
    # is wrong for almost every real caller (they live in other files).
    if this_name and f['ghidra_name']:
        # The wrapper's OWN `this` parameter is safe to genericize too
        # (unlike the real method definition's, which keeps its original
        # type for the this_orig_type byte-arithmetic cast above) --
        # the wrapper does nothing with it except cast straight to
        # `(ClassName*)` and call through, no arithmetic at all, so
        # genericizing here can't change that cast's behavior. This is
        # where most remaining `undefined1* -> undefined4*`-family
        # errors were actually coming from: every wrapper's own `this`
        # parameter was still the ORIGINAL exact type.
        # Real body text (not empty) so genericize_params' `code *` branch
        # can evidence-check this_name the same way the real method's own
        # this-substitution just did above -- both need the SAME decision
        # for the SAME variable (its own body is the only place that
        # evidence exists; the wrapper itself never dereferences this_name
        # at all, just forwards it).
        wrapper_this = genericize_params([f['params'][0]], f['body'])[0]
        if param_type(wrapper_this).strip() in ('float', 'double'):
            # Same Ghidra PowerPC mixed-ABI mistyping as the real method's
            # own this_orig_type handling above (`this` -- always a
            # pointer -- occasionally gets typed as a floating parameter
            # instead): a C-style cast straight to `(ClassName *)` from a
            # `double`/`float` parameter is illegal (no bit-reinterpret,
            # unlike an integer type), which is exactly what this
            # wrapper's own `((ClassName*)this_name)->...` cast needs to
            # do a few lines below. `long` keeps the real numeric address
            # value castable to a pointer, same fix as the method body's.
            wrapper_this = f'long {param_name(wrapper_this)}'
        wrapper_full_params = [wrapper_this] + f['params'][1:]
        # Padded consistently with 04_emit.py's own DBAL_wrappers.h
        # declaration (same MAX_CALL_ARITY source) -- extra params are
        # silently unused in the body, not forwarded to the real method
        # call, since we don't know what the real, undiscovered parameter
        # was actually for.
        wrapper_params = ', '.join(pad_params_to_arity(f['ghidra_name'], wrapper_full_params))
        call_args = ', '.join(param_name(p) for p in params_no_this)
        wrap_chunk = (
            f"// compatibility shim for pre-existing call sites using the original flat name\n"
            f"{f['ret_type']} {f['ghidra_name']}({wrapper_params})\n"
            f"{{\n"
            f"    return (({qualified_class} *){this_name})->{member}({call_args});\n"
            f"}}\n"
        )
        files_out[path].append(wrap_chunk)
        WRAPPER_DECLS.append((f['ghidra_name'], f['ret_type'], wrapper_full_params))

print('distinct output files:', len(files_out))

# ---------- collect true file-scope globals used-but-never-locally-declared ----------
# More robust than guessing from naming conventions (DAT_*, *_o, _fp_*, ...):
# for every function, Ghidra always declares ALL of its own locals as
# "TYPE name;" lines right after the opening brace, one blank line before the
# first real statement. Any identifier used in the body that ISN'T one of
# those declared locals, a parameter, a keyword, or a called function name is
# a real external reference (a file-scope static/global DBAL.OUT itself
# depended on, e.g. `firstTime_144`, `_fp_db_map_dir`).
DECL_LINE_RE = re.compile(r'^\s*[A-Za-z_][A-Za-z0-9_ ]*?([A-Za-z_][A-Za-z0-9_]*)\s*(?:\[[^\]]*\])?\s*;\s*$')
IDENT_USE_RE = re.compile(r'\b([A-Za-z_][A-Za-z0-9_]*)\b')
C_KEYWORDS_LOCAL = {
    'if', 'else', 'while', 'for', 'do', 'switch', 'case', 'default', 'break',
    'continue', 'return', 'goto', 'sizeof', 'struct', 'union', 'enum',
    'const', 'static', 'void', 'int', 'char', 'short', 'long', 'float',
    'double', 'signed', 'unsigned', 'bool', 'true', 'false',
    # Ghidra / DBAL_types.h type names -- never real data symbols.
    'byte', 'uint', 'ushort', 'uchar', 'ulong', 'code', 'size_t',
    'undefined', 'undefined1', 'undefined2', 'undefined4', 'undefined8',
}

global_data_refs = set()
for f in funcs:
    if BAD_INSN_MARK in f.get('body', ''):
        continue
    body = f.get('body', '')
    if not body.startswith('{'):
        continue
    # declaration block: lines from after "{" that still look like "TYPE
    # name;" declarations, or are blank. Stop at the FIRST line that looks
    # like a real statement instead -- functions with no local variables at
    # all (straight to a real statement right after "{", no blank-line
    # separator) would otherwise make this loop swallow the whole body as
    # "still declarations" and never actually scan it for global refs.
    lines = body.split('\n')
    declared = set()
    i = 1
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped == '':
            i += 1
            continue
        m = DECL_LINE_RE.match(lines[i])
        if not m:
            break
        declared.add(m.group(1))
        i += 1
    declared |= {param_name(p) for p in f.get('params', [])}
    rest_text = '\n'.join(lines[i:])
    # mask string/char literal contents so words inside them (error messages,
    # debug text) never get mistaken for identifiers.
    rest_text = re.sub(r'"(?:[^"\\]|\\.)*"', lambda m: '"' + ' ' * (len(m.group()) - 2) + '"', rest_text)
    rest_text = re.sub(r"'(?:[^'\\]|\\.)*'", lambda m: "'" + ' ' * (len(m.group()) - 2) + "'", rest_text)
    for m in IDENT_USE_RE.finditer(rest_text):
        name = m.group(1)
        end = m.end()
        is_call = rest_text[end:].lstrip().startswith('(')
        if is_call:
            continue  # function calls handled separately in gen_dbal_cpp4.py
        if name in declared or name in C_KEYWORDS_LOCAL:
            continue
        if not name.startswith(('param_', 'local_', 'uVar', 'iVar', 'bVar', 'sVar', 'pbVar', 'puVar',
                                 'pcVar', 'piVar', 'cVar', 'lVar', 'auStack', 'aiStack', 'acStack', 'abStack')):
            global_data_refs.add(name)

print('globals used-but-not-locally-declared:', len(global_data_refs))

with open(r"C:\Users\PC\AppData\Local\Temp\claude\c--Users-PC-Desktop-RNS510\b36ea6fd-e6fc-4628-8258-2b448f26d38f\scratchpad\files_out.pkl", 'wb') as fh:
    pickle.dump({'files_out': dict(files_out), 'classes': dict(classes),
                 'scope_home_file': scope_home_file, 'manifest': MANIFEST,
                 'funcs': funcs, 'BAD_INSN_MARK': BAD_INSN_MARK,
                 'global_data_refs': global_data_refs,
                 'wrapper_decls': WRAPPER_DECLS}, fh)
print('saved files_out.pkl')
