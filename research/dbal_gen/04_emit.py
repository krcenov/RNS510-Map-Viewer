import re, os, pickle
from collections import defaultdict

with open(r"C:\Users\PC\AppData\Local\Temp\claude\c--Users-PC-Desktop-RNS510\b36ea6fd-e6fc-4628-8258-2b448f26d38f\scratchpad\files_out.pkl", 'rb') as fh:
    D = pickle.load(fh)

files_out = D['files_out']
classes = D['classes']
funcs = D['funcs']
BAD_INSN_MARK = D['BAD_INSN_MARK']
OUT_ROOT = r"C:\Users\PC\Desktop\RNS510\BASE\CUSTOM\CD_CUSTOM\DBAL"

# ---------- whole-codebase text + real max call arity per flat name ----------
# max_call_arity is computed ONCE, from the RAW Ghidra decompile (see
# compute_arity.py), not from our own translated output -- it has to be
# available identically to BOTH this declaration-emitting stage and
# 03_translate.py's DEFINITION-emitting stage (a declaration padded with
# extra parameters the matching definition doesn't also have would be a
# flat conflicting-declaration error), and 03_translate.py runs first, so
# computing it from our own output here would be one step too late for
# that side. Real max per-flat-name argument count, scanned once from the
# ground truth: Ghidra sometimes under-recovers a function's own real
# parameter count (a trivial 1-line setter -- `this->field = param_2;
# return;` -- where its OWN incoming parameter isn't recognized as used,
# even though every real caller clearly passes one); padding both the
# definition and every declaration consistently fixes that direction
# symmetrically with the opposite (too-few-args-AT-one-call-site) fix
# already applied via params_with_safe_defaults() below.
all_text = '\n'.join('\n'.join(chunks) for chunks in files_out.values())
# Mask string/char literal CONTENTS (keep the quotes) before any of the
# regex scans below run against this text -- a debug/error message like
# `"... >= db_vid_seginfo_count (%i)\n"` contains what looks exactly like
# a real call (`identifier(`), and without this an unrelated string
# literal can make a plain int variable get misclassified and declared as
# a function in DBAL_externs.h (confirmed directly: this exact string in
# db_vid.cpp was the reason `db_vid_seginfo_count`, used everywhere else
# as `< db_vid_seginfo_count` / `db_vid_seginfo_count << 2`, got declared
# `extern int db_vid_seginfo_count(...);`). Same masking approach already
# used in 03_translate.py's own per-function global-reference scanner.
all_text = re.sub(r'"(?:[^"\\]|\\.)*"', lambda m: '"' + ' ' * (len(m.group()) - 2) + '"', all_text)
all_text = re.sub(r"'(?:[^'\\]|\\.)*'", lambda m: "'" + ' ' * (len(m.group()) - 2) + "'", all_text)
with open(r"C:\Users\PC\AppData\Local\Temp\claude\c--Users-PC-Desktop-RNS510\b36ea6fd-e6fc-4628-8258-2b448f26d38f\scratchpad\max_call_arity.pkl", 'rb') as fh:
    max_call_arity = pickle.load(fh)


def pad_to_arity(name, params):
    """params excludes `this` (free functions have no `this`; callers of
    this helper for wrappers pass the this-less tail). Appends extra
    `long paramExtraN = 0` slots if real call sites use more arguments
    than this declaration currently has room for."""
    need = max_call_arity.get(name, 0)
    have = len(params)
    if need <= have:
        return params
    return params + [f'long paramExtra{i} = 0' for i in range(have, need)]


# Default anything EXCEPT a bare, capitalized type name with no `*`/`&` --
# that shape (e.g. `DBRect`, `SegCoverStruct`) is the one real risk: a
# class/struct passed BY VALUE, which `= 0` isn't implicitly convertible
# to (no converting constructor exists on these generated classes). Every
# pointer, reference, and lowercase primitive/typedef (including ones not
# explicitly enumerated, like `size_t`) is safe to default -- `0`/NULL
# converts to all of them without error. The AnyPtr1/2/4/8 fat-pointer
# types (DBAL_FATPTR, see DBAL_types.h) have EXACTLY this bare-
# capitalized-name shape too, but ARE safe: they have their own `(long)`
# converting constructor, so `= 0` works fine -- explicitly exempted
# rather than widening the regex and risking a real by-value struct type
# slipping through.
_risky_byvalue_re = re.compile(r'^[A-Z][A-Za-z0-9_]*$')
_FATPTR_TYPE_NAMES = {'AnyPtr1', 'AnyPtr2', 'AnyPtr4', 'AnyPtr8'}


def _scalar_default_ok(typ):
    typ = typ.strip()
    if typ in _FATPTR_TYPE_NAMES:
        return True
    return not _risky_byvalue_re.match(typ)


class _ScalarDefaultShim:
    def match(self, typ):
        return _scalar_default_ok(typ)


_scalar_default_re = _ScalarDefaultShim()


def params_with_safe_defaults(params):
    """Ghidra sometimes recovers fewer arguments at one call site of a free
    function than the real definition takes (a known per-call-site decompiler
    accuracy limit, not something a rename/typedef pass can fix). Giving
    every trailing pointer/plain-scalar parameter a `=0` default lets a
    too-few-argument call still compile (and behave sanely: the original
    callee almost always already guards a NULL/0 trailing arg) without
    weakening the common, correctly-recovered call sites, which keep passing
    their real arguments as before."""
    # apply defaults back-to-front only while the type looks safe (pointer or
    # plain scalar) -- stop at the first parameter that doesn't, so defaults
    # stay a contiguous trailing run (required by C++).
    result = list(params)
    for i in range(len(result) - 1, -1, -1):
        t = result[i].strip()
        name_m = re.match(r'^(.*?)([A-Za-z_][A-Za-z0-9_]*)$', t)
        typ = name_m.group(1).strip() if name_m else ''
        if _scalar_default_re.match(typ):
            result[i] = t + ' = 0'
        else:
            break
    return result

# ---------- generate DBAL_freefuncs.h: forward declarations for every
# plain/free function, so cross-file calls between them resolve -----------
free_decl_lines = [
    '#pragma once',
    '// Auto-generated forward declarations for every free (non-member)',
    '// function translated from DBAL.OUT, so calls between them across',
    '// different .cpp files resolve without needing a project-wide build',
    '// order. Functions Ghidra itself could not fully disassemble (hit a',
    "// bad instruction and gave up) are NOT declared here -- they're not",
    '// defined anywhere either; real callers fall back to the permissive',
    '// extern in DBAL_externs.h.',
    '#include "DBAL_types.h"',
    '',
]
seen_free = set()
for f in sorted(funcs, key=lambda x: x['addr']):
    if f['dm']['kind'] not in ('plain', 'free', 'unknown', 'vtable', 'typeinfo_obj', 'typeinfo_func'):
        continue
    if BAD_INSN_MARK in f['body']:
        continue
    name = f['ghidra_name']
    if name in seen_free:
        continue
    seen_free.add(name)
    if name == 'gcc2_compiled_':
        # `gcc2_compiled.` is GCC2's own per-translation-unit marker symbol
        # (never really called -- it has no body worth running). Ghidra
        # itself appears to misattribute a real nearby call's target to this
        # symbol at ~96 call sites across this codebase (always with real
        # arguments, which a true `gcc2_compiled.` call never has) -- a
        # decompiler-side artifact, not something this translation can
        # resolve to the real intended callee without per-site manual
        # disassembly. Declared permissively so those sites still compile;
        # each one is a flagged "this call target is probably wrong" spot,
        # not a confirmed-correct call.
        free_decl_lines.append(f"{f['ret_type']} {name}(...);")
    else:
        _params = pad_to_arity(name, params_with_safe_defaults(f['params']))
        free_decl_lines.append(f"{f['ret_type']} {name}({', '.join(_params)});")

with open(os.path.join(OUT_ROOT, 'DBAL_freefuncs.h'), 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(free_decl_lines) + '\n')
print('DBAL_freefuncs.h:', len(seen_free), 'free functions declared')

# ---------- generate DBAL_wrappers.h: forward declarations for every
# method's flat-name compatibility wrapper (plain external linkage, defined
# once in its class's home file) -- same cross-file-visibility need as free
# functions above, just for method wrappers instead. ----------------------
wrapper_decl_lines = [
    '#pragma once',
    '// Auto-generated forward declarations for every method compatibility',
    "// wrapper (flat Ghidra name -> real Class::member()), so pre-existing",
    '// call sites in OTHER .cpp files can see them. Each wrapper is defined',
    '// exactly once, in its method\'s own home file -- plain external',
    '// linkage, not `static`, specifically so this works.',
    '#include "DBAL_types.h"',
    '',
]
seen_wrap = set()
for name, ret_type, params in D['wrapper_decls']:
    if name in seen_wrap:
        continue
    seen_wrap.add(name)
    # Defaulting even the leading `this` parameter looks wrong at first --
    # but some real call sites genuinely pass ZERO arguments to what should
    # be a 1-arg (at least `this`) method wrapper (e.g. `init__7DBFView()`),
    # a real per-call-site Ghidra recovery gap, not a guess on our part to
    # avoid. A defaulted-to-0 `this` is already a best-effort placeholder
    # for an unrecoverable call site either way; letting it compile (rather
    # than hard-erroring) keeps it consistent with every other recovered-
    # arity gap here.
    full_params = pad_to_arity(name, params_with_safe_defaults(params))
    wrapper_decl_lines.append(f"{ret_type} {name}({', '.join(full_params)});")

with open(os.path.join(OUT_ROOT, 'DBAL_wrappers.h'), 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(wrapper_decl_lines) + '\n')
print('DBAL_wrappers.h:', len(seen_wrap), 'method wrappers declared')

# ---------- generate DBAL_classes.h ----------
lines = []
lines.append('// Auto-generated minimal class declarations -- method signatures only.')
lines.append('// NO data members are declared: every method body in the matching .cpp')
lines.append('// still accesses its original fields via raw byte-offset casts on `this`')
lines.append('// (faithful to the decompiled ground truth -- the real struct layout for')
lines.append('// most of these classes has not been reconstructed yet). That means these')
lines.append('// classes are safe to use for calling/defining methods, but `sizeof()`,')
lines.append('// construction, and direct member access on them are NOT meaningful yet.')
lines.append('#pragma once')
lines.append('#include "DBAL_types.h"')
lines.append('')

for scope in sorted(classes.keys(), key=lambda s: (len(s), s)):
    members = classes[scope]
    nss = scope[:-1]
    indent = '    ' * len(nss)
    for ns in nss:
        lines.append('    ' * (len(indent) // 4) + f'namespace {ns} {{')
    lines.append(f'{indent}class {scope[-1]};')
    lines.append(f'{indent}class {scope[-1]} {{')
    lines.append(f'{indent}public:')
    # No dedup needed here: gen_dbal_cpp3.py already renamed any true
    # (member, const, param-types) collision to a unique name, so every
    # entry below is guaranteed distinct.
    for m in members:
        f = m['f']
        params_str = ', '.join(m['params_no_this'])
        const_kw = ' const' if m['const'] else ''
        lines.append(f"{indent}    {f['ret_type']} {m['member']}({params_str}){const_kw};  // {f['mangled']}")
    lines.append(f'{indent}}};')
    for ns in reversed(nss):
        lines.append('}')
    lines.append('')

classes_h = '\n'.join(lines)
print('DBAL_classes.h:', len(classes_h), 'bytes,', len(classes), 'classes')

os.makedirs(OUT_ROOT, exist_ok=True)
with open(os.path.join(OUT_ROOT, 'DBAL_classes.h'), 'w', encoding='utf-8') as fh:
    fh.write(classes_h)

# ---------- generate DBAL_types.h ----------
types_h = r'''#pragma once
// Auto-generated type shims matching Ghidra's decompiler output types, so the
// translated .cpp files below stay textually close to the original decompile
// (easy to diff/verify) while being valid, compilable C++.
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdlib.h>

typedef uint8_t  undefined;
typedef uint8_t  undefined1;
typedef uint16_t undefined2;
typedef uint32_t undefined4;
typedef uint64_t undefined8;

typedef uint8_t  byte;
typedef uint32_t uint;
typedef uint16_t ushort;
typedef uint8_t  uchar;
typedef uint32_t ulong;
typedef int64_t  longlong;
typedef uint64_t ulonglong;

// Ghidra's generic "pointer to executable code" type. The original calls
// through it with all sorts of different argument lists (it stands for
// whichever real function pointer -- vtable slot, callback, ... -- is in
// play at each call site), so it's declared as a variadic function pointer
// (legal in C/C++, the same mechanism printf's own pointer type relies on)
// rather than one fixed signature; that lets every real call site compile
// and run unchanged regardless of its own argument count.
typedef long (*code)(...);

// Ghidra's byte-concatenation intrinsics: CONCATxy(hi, lo) packs a high part
// of x bytes and a low part of y bytes into one (x+y)-byte value, hi in the
// high-order bits.
static inline uint16_t CONCAT11(uint8_t hi, uint8_t lo)  { return ((uint16_t)hi << 8)  | lo; }
static inline uint32_t CONCAT12(uint8_t hi, uint16_t lo) { return ((uint32_t)hi << 16) | lo; }
static inline uint32_t CONCAT13(uint8_t hi, uint32_t lo) { return ((uint32_t)hi << 24) | (lo & 0xFFFFFFu); }
static inline uint64_t CONCAT44(uint32_t hi, uint32_t lo) { return ((uint64_t)hi << 32) | lo; }

// "Fat pointer" wrapper types, one per undefined-family width. The ORIGINAL
// C-flavored pseudocode never had real pointer-type safety (any caller
// passing "N raw bytes of something" to any callee expecting the same was
// fine); standard C++ requires an EXACT pointer type match to pass one
// implicitly, which is the single largest remaining source of translation
// errors (see DBAL/PROVENANCE.md's compile-status section -- two earlier,
// narrower attempts at this: a blanket `void*` rewrite broke real functions
// that dereference/index such a parameter directly, since void* supports
// neither; a safety-checked version that only touched PROVABLY-never-
// dereferenced parameters was safe but barely moved the needle, since most
// of them genuinely ARE dereferenced). This type accepts ANY pointer
// implicitly (fixing the conversion errors at the root) while ALSO
// supporting direct dereference/indexing/pointer arithmetic AND explicit
// re-casts to any other pointer type, so it doesn't require proving
// anything about how a parameter is used first.
// Forward-declared so each DBAL_FATPTR expansion below can cross-convert
// from the other 3 widths directly (`AnyPtr4(const AnyPtr1&)`, etc.) --
// without this, converting AnyPtr4 -> AnyPtr1 would need TWO chained
// user-defined conversions (AnyPtr4 -> T* via its own conversion
// operator, then T* -> AnyPtr1 via the target's constructor), which C++
// never applies implicitly. A real, confirmed gap once same-width
// genericization started working: `param + 1` (AnyPtr4) passed to a
// parameter that's AnyPtr1 after a DIFFERENT call site's own narrower
// type was genericized.
struct AnyPtr1; struct AnyPtr2; struct AnyPtr4; struct AnyPtr8;

#define DBAL_FATPTR(NAME, ELEMTYPE) \
struct NAME { \
    void *p; \
    NAME() : p(0) {} \
    NAME(long v) : p((void *)v) {} \
    NAME(const AnyPtr1 &o); \
    NAME(const AnyPtr2 &o); \
    NAME(const AnyPtr4 &o); \
    NAME(const AnyPtr8 &o); \
    template<typename T> NAME(T *x) : p((void *)x) {} \
    template<typename T> operator T*() const { return (T *)p; } \
    ELEMTYPE &operator*() const { return *(ELEMTYPE *)p; } \
    ELEMTYPE &operator[](long i) const { return ((ELEMTYPE *)p)[i]; } \
    NAME operator+(long i) const { return NAME((void *)((char *)p + i * (long)sizeof(ELEMTYPE))); } \
    NAME operator-(long i) const { return NAME((void *)((char *)p - i * (long)sizeof(ELEMTYPE))); } \
    bool operator==(long v) const { return p == (void *)v; } \
    bool operator!=(long v) const { return p != (void *)v; } \
    template<typename T> bool operator==(T *x) const { return p == (void *)x; } \
    template<typename T> bool operator!=(T *x) const { return p != (void *)x; } \
    bool operator==(const NAME &o) const { return p == o.p; } \
    bool operator!=(const NAME &o) const { return p != o.p; } \
    operator bool() const { return p != 0; } \
};
DBAL_FATPTR(AnyPtr1, undefined1)
DBAL_FATPTR(AnyPtr2, undefined2)
DBAL_FATPTR(AnyPtr4, undefined4)
DBAL_FATPTR(AnyPtr8, undefined8)

// Cross-width constructor bodies, defined after all 4 structs are
// complete (each needs the OTHERS' `.p` member, which only exists once
// that struct's own full definition has been seen).
#define DBAL_FATPTR_XCTOR(NAME) \
inline NAME::NAME(const AnyPtr1 &o) : p(o.p) {} \
inline NAME::NAME(const AnyPtr2 &o) : p(o.p) {} \
inline NAME::NAME(const AnyPtr4 &o) : p(o.p) {} \
inline NAME::NAME(const AnyPtr8 &o) : p(o.p) {}
DBAL_FATPTR_XCTOR(AnyPtr1)
DBAL_FATPTR_XCTOR(AnyPtr2)
DBAL_FATPTR_XCTOR(AnyPtr4)
DBAL_FATPTR_XCTOR(AnyPtr8)
'''
with open(os.path.join(OUT_ROOT, 'DBAL_types.h'), 'w', encoding='utf-8') as fh:
    fh.write(types_h)

# ---------- write per-file .cpp ----------
written = []
for relpath, chunks in files_out.items():
    relpath = relpath.replace('libraries/dbal/', '')
    full = os.path.join(OUT_ROOT, relpath)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    depth = relpath.count('/')
    inc_prefix = '../' * depth
    header = (
        f'// Auto-translated from Ghidra decompilation of DBAL.OUT (GCC 2.x PowerPC '
        f'object,\n// original C++ source path inferred from embedded error-string '
        f'literals / address\n// proximity -- see DBAL_PROVENANCE.md). Functionally '
        f'faithful transliteration;\n// struct layouts are NOT reconstructed -- field '
        f'access still uses raw byte offsets.\n'
        f'#include "{inc_prefix}DBAL_types.h"\n'
        f'#include "{inc_prefix}DBAL_classes.h"\n'
        f'#include "{inc_prefix}DBAL_freefuncs.h"\n'
        f'#include "{inc_prefix}DBAL_wrappers.h"\n'
        f'#include "{inc_prefix}DBAL_externs.h"\n\n'
    )
    with open(full, 'w', encoding='utf-8') as fh:
        fh.write(header)
        fh.write('\n\n'.join(chunks))
        fh.write('\n')
    written.append(full)

print('wrote', len(written), 'files')

# ---------- generate DBAL_externs.h ----------
# Scan everything we just wrote for identifiers that are (a) used as a call
# `NAME(` or (b) used as data, but never defined as a function/class/typedef
# in this project -- these are the real external dependencies (oslib_* OS
# layer, libc, and global object instances like mapView_o/glob_mapdirID).
# (all_text itself was already built above, before the declaration passes.)
defined_funcs = set()
_SIG_LINE_RE = re.compile(r'^\s*(?:static inline\s+)?[A-Za-z_][A-Za-z0-9_ :*]*?\b([A-Za-z_][A-Za-z0-9_]*)\s*\(')
for relpath, chunks in files_out.items():
    for chunk in chunks:
        # A chunk's own real signature line is specifically its FIRST
        # non-comment, non-blank line (comment lines, then the Ret Name(...)
        # declaration, then the body). Scanning the WHOLE chunk text with
        # this same pattern is a real bug: a `return SOME_CALL(...);`
        # statement deep in a body matches it identically to a genuine
        # definition, which previously made `defined_funcs` wrongly
        # "swallow" any function merely CALLED-in-a-return-statement
        # (confirmed: broke `oslib_TaskException`'s own extern declaration
        # this way once bodies started containing `return OTHER_CALL(...);`
        # patterns). Only the chunk's own first real line counts.
        for line in chunk.split('\n'):
            s = line.strip()
            if not s or s.startswith('//') or s.startswith('/*') or s.startswith('*'):
                continue
            m = _SIG_LINE_RE.match(line)
            if m:
                defined_funcs.add(m.group(1))
            break

C_KEYWORDS = {
    'if', 'else', 'while', 'for', 'do', 'switch', 'case', 'default', 'break',
    'continue', 'return', 'goto', 'sizeof', 'struct', 'union', 'enum', 'typedef',
    'const', 'static', 'extern', 'void', 'int', 'char', 'short', 'long', 'float',
    'double', 'signed', 'unsigned', 'bool', 'true', 'false', 'class', 'public',
    'private', 'protected', 'this', 'namespace', 'inline', 'new', 'delete',
    'nullptr', 'NULL', 'virtual', 'template', 'typename', 'operator',
    'longlong', 'ulonglong',
}

called = set(re.findall(r'\b([A-Za-z_][A-Za-z0-9_]*)\s*\(', all_text))
called -= defined_funcs
called -= C_KEYWORDS
# real libc functions -- DBAL_types.h now pulls in <string.h> for these,
# so declaring our own generic/permissive extern for them too would
# conflict with the real, correctly-typed declaration. (NOT math.h/
# ctype.h/stdio.h -- tried, but math.h pulls in C++'s <cmath> which
# actively refuses to work in -ffreestanding mode; left as permissive
# externs instead rather than fighting the cross-compiler's own hosted-vs-
# freestanding split.) A blanket `^(str|mem|wcs)` prefix match was tried
# first and wrongly swept up `strtol`/`strtoul`/`strtod`/`strtoll`/etc --
# real functions, but declared in stdlib.h, not string.h, and hidden by
# -ffreestanding on this cross-compiler same as every other stdlib.h name
# (confirmed by isolated test) -- causing a "was not declared" error for
# THOSE instead. The fix is the opposite of narrowing to a hand-picked
# string.h whitelist (which missed `strtok_r`, a real GNU string.h
# extension, and broke EVERY file via the shared externs header): keep
# the broad prefix match, just also excluding stdlib.h's own `strto*`
# numeric-conversion family specifically.
_STDLIB_STR_PREFIXED = {
    'strtod', 'strtof', 'strtol', 'strtold', 'strtoll', 'strtoul', 'strtoull',
}
called = {
    c for c in called
    if not re.match(r'^(str|mem|wcs)[a-z0-9_]*$', c) or c in _STDLIB_STR_PREFIXED
}
# Any of DBAL_types.h's own placeholder type names, immediately followed
# by whitespace-then-paren, reads exactly like a call to this scanner --
# `code (*)(...)` already needed excluding `code` for this reason (the
# DBAL_FATPTR casts use it); a NEW instance just turned up from
# `fix_ambiguous_overload_refs`'s own disambiguating cast text
# (`(undefined4 (*)(AnyPtr4, AnyPtr4))name`), redeclaring the `undefined4`
# TYPEDEF as a conflicting FUNCTION in the shared externs header and
# breaking every file that includes it. Excluding the whole placeholder
# type-name family up front avoids chasing this one call site at a time.
called -= {
    'CONCAT11', 'CONCAT12', 'CONCAT13', 'CONCAT44', 'code',
    'undefined', 'undefined1', 'undefined2', 'undefined4', 'undefined8',
    'uint', 'ulong', 'ushort', 'uchar', 'byte', 'longlong', 'ulonglong',
}
# drop anything that's actually a member-call wrapper's own cast target (class names)
called -= set(c[-1] for c in classes.keys())
called -= seen_free  # already declared in DBAL_freefuncs.h

# Per-function used-but-never-locally-declared scan (gen_dbal_cpp3.py) --
# more robust than guessing from naming conventions, catches everything
# from `DAT_*`/`_o`-suffixed/`_fp_`-prefixed globals to plain names like
# `firstTime_144` that don't match any particular pattern.
data_tokens = set(D['global_data_refs'])
# RTTI/vtable symbols (`__ti<N><Class>`, `_vt_<N><Class>`/`_vt$<N><Class>`,
# and `__tf<N><Class>` where that specific one wasn't decompiled as a real
# function) are referenced as plain data (e.g. `&_vt_16ZlibDecompressor` in
# a constructor) but follow their own naming shape, not any of the generic
# patterns the per-function scan above already covers reliably -- add them
# directly.
data_tokens |= set(re.findall(r'\b(__ti\d[A-Za-z0-9_]*|_vt[_$]\d[A-Za-z0-9_]*|__tf\d[A-Za-z0-9_]*)\b', all_text))
data_tokens -= defined_funcs
data_tokens -= C_KEYWORDS
data_tokens -= set(classes.keys() and [c[-1] for c in classes.keys()])
data_tokens -= seen_free
data_tokens -= seen_wrap
# a name actually called somewhere (`name(`) is a function, not data -- avoid
# declaring the same identifier twice as two different kinds of entity.
data_tokens -= called

externs_h_lines = [
    '#pragma once',
    '// Auto-generated extern declarations for every identifier used but not',
    '// defined anywhere in this project -- the real OS/runtime layer',
    '// (oslib_*), libc, and global singleton objects DBAL.OUT depended on at',
    '// link time in the original firmware. Deliberately untyped/loosely typed',
    '// (old-style K&R declarations where possible) so every real call site',
    '// compiles without needing the true original signature -- replace with',
    '// real declarations/definitions as the actual runtime layer is rebuilt.',
    '#include "DBAL_types.h"',
    '',
    '#ifdef __cplusplus',
    'extern "C" {',
    '#endif',
    '',
]
for name in sorted(called):
    # C++ "()" means zero parameters (unlike C's unspecified-params meaning),
    # so a permissive stand-in must use C-style varargs "(...)" instead.
    externs_h_lines.append(f'extern int {name}(...);')
externs_h_lines.append('')
called_via_deref = set(re.findall(r'\(\*([A-Za-z_][A-Za-z0-9_]*)\)\s*\(', all_text))
# A global dereferenced WITHOUT being called (`*name` on its own, not
# `(*name)(args)`) is real data behind a pointer, not a function pointer
# -- e.g. `*_fp_db_fea_map` despite the `_fp_` naming convention most of
# its siblings earn by actually being called. Declaring it `AnyPtr4`
# (not plain `uint32_t`) makes that direct dereference valid again
# (`operator*()` gives back a real `undefined4&`) while staying
# consistent with the rest of this file's own fat-pointer approach.
deref_only_re_cache = {}


def is_directly_dereferenced(name):
    if name not in deref_only_re_cache:
        deref_only_re_cache[name] = re.compile(r'(?<![A-Za-z0-9_)])\*\s*' + re.escape(name) + r'\b')
    return bool(deref_only_re_cache[name].search(all_text))


subscript_re_cache = {}


def is_subscripted(name):
    if name not in subscript_re_cache:
        subscript_re_cache[name] = re.compile(re.escape(name) + r'\s*\[')
    return bool(subscript_re_cache[name].search(all_text))


# A handful of globals are indexed (`name[i]`) rather than dereferenced,
# which needs the SAME AnyPtrN treatment (plain uint32_t can't be
# subscripted either) but picking the WRONG width would silently change
# the real indexing stride -- not just a compile fix. Verified individually
# from their own usage elsewhere in the corpus (an explicit pointer cast or
# comparison pins the width unambiguously): `transCodes`/`pdb_page_next_free`
# are both also explicitly cast `(undefined4 *)`/`(int *)` and compared
# against `(int *)0x0` elsewhere, confirming 4-byte elements; the other 5
# are only ever read/written through `(byte)`/`(char)` casts or compared to
# a char literal (and `s_pucFakeParcel_3884`'s own name -- Ghidra's "puc" =
# pointer-to-unsigned-char -- independently confirms it), confirming 1-byte
# elements. Anything newly subscripted that ISN'T in this map (a future
# regen over a different decompile) falls through to AnyPtr1, since 5 of
# the 7 real cases found were byte-width -- the more common case, and
# consistent with Ghidra's own tendency to decompile unknown buffers as
# byte arrays -- but is NOT verified for a name not listed here.
_SUBSCRIPT_WIDTH_OVERRIDE = {
    'transCodes': 'AnyPtr4',
    'pdb_page_next_free': 'AnyPtr4',
    'pucScaleMaskArray_3849': 'AnyPtr1',
    'buf_325': 'AnyPtr1',
    's_pucFakeParcel_3884': 'AnyPtr1',
    'db_intersection_filter_matrix': 'AnyPtr1',
    'g_Utf8HelperChars': 'AnyPtr1',
}

# Globals whose address is taken and then used for STRIDED array-style
# access (`(&name)[idx]`, `&name + otherGlobal`, passed as a buffer base to
# strcpy/strncmp/...) rather than being dereferenced/subscripted directly
# on the name itself. A plain scalar of the right width is the RIGHT fix
# here (not an AnyPtrN wrapper): `&name` on a plain scalar already gives a
# correctly-sized, correctly-strided raw pointer for free, whereas AnyPtrN
# is a multi-byte CLASS wrapping a `void*` -- taking ITS address and
# striding by sizeof(AnyPtrN) would reach completely wrong offsets, a real
# behavioral bug, not just a compile fix. Verified individually: all of
# `DAT_000a2620`/`DAT_000a2484`/`DAT_000adb64`/`DAT_000c56e0`/
# `DAT_000a1a98`/`DAT_000ba870` are only ever used via `&name` passed to
# something expecting a byte/char buffer base (confirmed from the actual
# "cannot convert ... to 'undefined*'/'char*'" error at each site);
# `DAT_000bb2d4`/`county_cache`/`state_cache`/`maplist`/`sortValue` are
# each subscripted (via `(&name)[...]`) or added to with a SHORT value
# assigned through the result, confirming 2-byte elements (and for
# `DAT_000bb2d4` specifically, matching the exact 2-byte width its own
# "cannot convert to undefined2*" error already demands -- so the pointer
# arithmetic a few lines away, `&DAT_000bb2d4 + DAT_000bb2d0`, keeps
# scaling by the same 2 bytes it already relies on); `memory_zone_0`/
# `string_303`/`string_309`/`string_315`/`speedTable_6672` are each used
# as a `strcpy`/`strncmp`/char-buffer base.
_SCALAR_WIDTH_OVERRIDE = {
    'DAT_000a1a98': 'undefined1', 'DAT_000ba870': 'undefined1',
    'DAT_000a2620': 'undefined1', 'DAT_000a2484': 'undefined1',
    'DAT_000adb64': 'undefined1', 'DAT_000c56e0': 'undefined1',
    'memory_zone_0': 'undefined1', 'string_303': 'undefined1',
    'string_309': 'undefined1', 'string_315': 'undefined1',
    'speedTable_6672': 'undefined1', 'DAT_000b3274': 'undefined1',
    'DAT_000b7e60': 'undefined1', 'DAT_000b7f4c': 'undefined1',
    'DAT_000b8160': 'undefined1',
    'DAT_000bb2d4': 'undefined2', 'county_cache': 'undefined2',
    'state_cache': 'undefined2', 'maplist': 'undefined2',
    'sortValue': 'undefined2',
}

# Globals whose address is taken into a DOUBLE pointer (`undefined**`) --
# meaning the global itself is really a POINTER variable (the first
# pointer-sized slot of what's actually a small array of pointers), not a
# data value at all. Verified individually: `isoTransTable` is iterated
# as `undefined **ppuVar3 = &isoTransTable; ... *ppuVar3; ppuVar3[1];
# ppuVar3 = ppuVar3 + 2;` -- an unmistakable array-of-string-pointer-pairs
# pattern (a language-code translation table). `ARN_COR_Version` is passed
# directly (not via `&`) as a `%s` argument to a printf-style call
# elsewhere in the SAME corpus (`db_init.cpp`), which only makes sense if
# ARN_COR_Version's own value already IS a `char*` (a version string),
# confirming it's a pointer variable, not a scalar needing its address
# taken for some OTHER reason.
_PTR_SYMBOL_OVERRIDE = {
    'isoTransTable': 'undefined1 *',
    'ARN_COR_Version': 'undefined1 *',
}

TI_RE = re.compile(r'^__ti\d|^__tiQ\d')
for name in sorted(data_tokens):
    if name in called_via_deref:
        # used as `(*name)(args)` -- a function-pointer global (the `_fp_*`
        # naming convention several of these follow), not plain data.
        externs_h_lines.append(f'extern code {name};')
    elif name in _SCALAR_WIDTH_OVERRIDE:
        externs_h_lines.append(f'extern {_SCALAR_WIDTH_OVERRIDE[name]} {name};')
    elif name in _PTR_SYMBOL_OVERRIDE:
        externs_h_lines.append(f'extern {_PTR_SYMBOL_OVERRIDE[name]} {name};')
    elif TI_RE.match(name):
        # RTTI `__ti*` symbols: the real `__tf*` dispatch functions that use
        # them consistently return/compare them as `undefined8*` (8 bytes),
        # not plain 4-byte data -- declaring them narrower caused a real
        # "cannot convert uint32_t* to undefined8*" error at every such use.
        externs_h_lines.append(f'extern undefined8 {name};')
    elif is_directly_dereferenced(name):
        externs_h_lines.append(f'extern AnyPtr4 {name};')
    elif name in _SUBSCRIPT_WIDTH_OVERRIDE:
        externs_h_lines.append(f'extern {_SUBSCRIPT_WIDTH_OVERRIDE[name]} {name};')
    elif is_subscripted(name):
        externs_h_lines.append(f'extern AnyPtr1 {name};')
    else:
        externs_h_lines.append(f'extern uint32_t {name};')
externs_h_lines.append('')
externs_h_lines.append('#ifdef __cplusplus')
externs_h_lines.append('}')
externs_h_lines.append('#endif')

with open(os.path.join(OUT_ROOT, 'DBAL_externs.h'), 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(externs_h_lines) + '\n')

print('externs:', len(called), 'functions,', len(data_tokens), 'data symbols')
with open(r"C:\Users\PC\AppData\Local\Temp\claude\c--Users-PC-Desktop-RNS510\b36ea6fd-e6fc-4628-8258-2b448f26d38f\scratchpad\written_files.txt", 'w') as fh:
    fh.write('\n'.join(written))

# NOTE: the one-level-too-deep `code *paramN` fix (Ghidra's `code` is
# already a function pointer, so a PARAMETER holding a callback needs
# `code`, not `code *`) now lives in gen_dbal_cpp3.py's genericize_params,
# applied structurally to the parsed parameter list ONLY. A whole-file
# text-substitution version was tried here first and reverted: it also
# caught genuine LOCAL `code *pcVarN;` declarations fed by a real
# `*(code **)addr` double-dereference (a vtable-slot raw pointer, which
# legitimately needs to stay 2-level), breaking those (32 new errors) even
# though it fixed more than it broke overall. Parameters and locals look
# textually identical (`code *name`) but need opposite treatment, which
# only the structural, params-list-scoped fix in cpp3.py can tell apart.
