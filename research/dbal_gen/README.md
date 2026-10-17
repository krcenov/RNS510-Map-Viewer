# DBAL.OUT decompile -> demangled C++ pipeline

Run in order: `demangle.py` has no entry point (a module, tested via
`py demangle.py` which runs its own self-tests), then
`01_parse_and_assign_files.py` -> `02_parse_decls.py` ->
`02b_compute_arity.py` -> `03_translate.py` -> `04_emit.py`. Produces
`BASE/CUSTOM/CD_CUSTOM/DBAL/` — see that directory's own `PROVENANCE.md`
for what the output actually is, how to read it, and its current honest
compile status.

**Not yet cleaned up for general reuse**: paths are currently hardcoded
(the Ghidra decompile input at `tools/dbal_decompiled.c`, a few pickled
intermediate hand-off files under a session-specific scratch directory,
the output root). Treat this as a reference/history of exactly how
`DBAL/` was generated, not a one-command tool yet — rerunning it on a
different machine or a newer `DBAL.OUT` decompile means fixing those
paths first (search each file for its own hardcoded path at the top).

Stages:
- `01_parse_and_assign_files.py` — splits the Ghidra decompile into one
  record per function, demangles each name (via `demangle.py`), and
  assigns each to its real original `.cpp` file (confirmed from embedded
  error-string paths where present, else inferred by address proximity to
  the nearest confirmed function, else a synthetic per-class filename).
- `02_parse_decls.py` — parses each function's own declaration (Ghidra's
  own C name, return type, parameter list) and body out of its raw text.
- `02b_compute_arity.py` — scans the RAW Ghidra decompile (not our own
  translated output -- it has to be ready before 03_translate.py's own
  definition-emitting pass runs, and computing it from our own later
  output would be one step too late) for every flat name's own real
  maximum call-site argument count. Ghidra sometimes under-recovers a
  function's own parameter count (a trivial 1-line setter where its own
  incoming parameter isn't recognized as used, even though real callers
  clearly pass one); 03_translate.py and 04_emit.py both pad declarations
  AND definitions to this count, consistently, using this file's output.
- `03_translate.py` — the real translation: builds each class's member
  list, demangles method/ctor/dtor bodies into real `Class::member()`
  definitions (rewriting the `this`-pointer-arithmetic-preserving casts,
  fixing `code*` indirect calls, Ghidra's `NAME._N_M_` byte-range-access
  syntax, padding under-recovered arity, and skipping functions Ghidra
  itself couldn't fully disassemble), and emits one compatibility wrapper
  per method so pre-existing flat-name call sites elsewhere keep working.
- `04_emit.py` — writes the per-file `.cpp` output plus the shared
  `DBAL_types.h`/`DBAL_classes.h`/`DBAL_freefuncs.h`/`DBAL_wrappers.h`/
  `DBAL_externs.h` headers (the last two scanning the whole translated
  output for anything still undeclared and generating permissive
  `extern`s for it).
