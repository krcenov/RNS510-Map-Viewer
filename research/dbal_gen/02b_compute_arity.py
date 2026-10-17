import re, pickle

SRC = r"C:\Users\PC\Desktop\RNS510\tools\dbal_decompiled.c"
with open(SRC, encoding='utf-8', errors='replace') as f:
    text = f.read()

# Strip comment lines (// ... and the /* ... */ warning blocks) so we only
# scan real C code for call sites -- same raw flat identifiers (Ghidra's own
# $/.→_ sanitization already applied) that research/dbal_gen's later stages
# use as each function's `ghidra_name`.
text = re.sub(r'^//.*$', '', text, flags=re.MULTILINE)
text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)


def split_params_top(s):
    depth = 0
    cur = []
    parts = []
    for ch in s:
        if ch in '([<':
            depth += 1
        elif ch in ')]>':
            depth -= 1
        if ch == ',' and depth == 0:
            parts.append(''.join(cur))
            cur = []
        else:
            cur.append(ch)
    tail = ''.join(cur).strip()
    if tail or parts:
        parts.append(tail)
    return [p for p in parts if p.strip()]


def find_match_paren(s, open_idx):
    depth = 0
    for i in range(open_idx, len(s)):
        if s[i] == '(':
            depth += 1
        elif s[i] == ')':
            depth -= 1
            if depth == 0:
                return i
    return -1


max_call_arity = {}
call_re = re.compile(r'\b([A-Za-z_][A-Za-z0-9_]*)\s*\(')
pos = 0
n = len(text)
while True:
    m = call_re.search(text, pos)
    if not m:
        break
    name = m.group(1)
    open_idx = m.end() - 1
    close_idx = find_match_paren(text, open_idx)
    if close_idx == -1:
        pos = m.end()
        continue
    args_text = text[open_idx + 1:close_idx]
    n_args = len(split_params_top(args_text))
    if n_args > max_call_arity.get(name, 0):
        max_call_arity[name] = n_args
    pos = m.end()

print('distinct names with call sites:', len(max_call_arity))
with open(r"C:\Users\PC\AppData\Local\Temp\claude\c--Users-PC-Desktop-RNS510\b36ea6fd-e6fc-4628-8258-2b448f26d38f\scratchpad\max_call_arity.pkl", 'wb') as f:
    pickle.dump(max_call_arity, f)
print('saved')
