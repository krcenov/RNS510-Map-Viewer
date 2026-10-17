import re, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from demangle import demangle

SRC = r"C:\Users\PC\Desktop\RNS510\tools\dbal_decompiled.c"
OUT_ROOT = r"C:\Users\PC\Desktop\RNS510\BASE\CUSTOM\CD_CUSTOM\DBAL"

with open(SRC, encoding='utf-8', errors='replace') as f:
    text = f.read()

HEADER_RE = re.compile(r'^// ={10,}\n// (\S+)  @ ([0-9a-fA-F]+)  size=(\d+)\n// ={10,}\n', re.MULTILINE)
PATH_RE = re.compile(r'"J:/siemens/source/([^"]+\.(?:cpp|c|h))"')

matches = list(HEADER_RE.finditer(text))
funcs = []
for i, m in enumerate(matches):
    start = m.end()
    end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
    body_text = text[start:end]
    addr = int(m.group(2), 16)
    pm = PATH_RE.search(body_text)
    funcs.append({
        'mangled': m.group(1),
        'addr': addr,
        'size': int(m.group(3)),
        'raw_body': body_text,
        'confirmed_path': pm.group(1) if pm else None,
    })

funcs.sort(key=lambda f: f['addr'])
print('parsed', len(funcs), 'functions')

# ---- demangle each ----
for f in funcs:
    f['dm'] = demangle(f['mangled'])

# ---- file assignment ----
# pass 1: confirmed path already set.
# pass 2: same-class fallback (any OTHER function of the same class/scope with a confirmed path)
scope_to_path = {}
for f in funcs:
    if f['confirmed_path'] and f['dm']['scope']:
        key = tuple(f['dm']['scope'])
        scope_to_path.setdefault(key, f['confirmed_path'])

for f in funcs:
    if not f['confirmed_path'] and f['dm']['scope']:
        key = tuple(f['dm']['scope'])
        if key in scope_to_path:
            f['assigned_path'] = scope_to_path[key]
            f['assign_method'] = 'same-class'
    if 'assigned_path' not in f:
        if f['confirmed_path']:
            f['assigned_path'] = f['confirmed_path']
            f['assign_method'] = 'confirmed'

# pass 3: address forward-fill
current = None
for f in funcs:
    if 'assigned_path' in f:
        current = f['assigned_path']
    elif current is not None:
        f['assigned_path'] = current
        f['assign_method'] = 'addr-fill'

# pass 4: remaining -> synthetic filename from class name (or 'misc' for free functions)
for f in funcs:
    if 'assigned_path' not in f:
        if f['dm']['scope']:
            f['assigned_path'] = 'inferred/' + f['dm']['scope'][-1] + '.cpp'
        else:
            f['assigned_path'] = 'inferred/misc.cpp'
        f['assign_method'] = 'synthetic'

from collections import Counter
c = Counter(f['assign_method'] for f in funcs)
print('assignment methods:', dict(c))

paths = Counter(f['assigned_path'] for f in funcs)
print('distinct output files:', len(paths))
for p, n in paths.most_common(10):
    print(' ', n, p)

import pickle
with open(r"C:\Users\PC\AppData\Local\Temp\claude\c--Users-PC-Desktop-RNS510\b36ea6fd-e6fc-4628-8258-2b448f26d38f\scratchpad\funcs.pkl", 'wb') as fh:
    pickle.dump(funcs, fh)
print('saved funcs.pkl')
