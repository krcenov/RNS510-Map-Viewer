import re, os, sys, pickle
from collections import defaultdict

with open(r"C:\Users\PC\AppData\Local\Temp\claude\c--Users-PC-Desktop-RNS510\b36ea6fd-e6fc-4628-8258-2b448f26d38f\scratchpad\funcs.pkl", 'rb') as fh:
    funcs = pickle.load(fh)

OUT_ROOT = r"C:\Users\PC\Desktop\RNS510\BASE\CUSTOM\CD_CUSTOM\DBAL"


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


def parse_decl(raw_body):
    """Return (ghidra_name, ret_type, params_text_list, body_text_incl_braces, leading_comment)."""
    idx = raw_body.index('\n{\n')
    decl_part = raw_body[:idx]
    body_part = raw_body[idx + 1:]  # starts with "{\n"

    leading_comment = ''
    m = re.match(r'^\s*(/\*.*?\*/\s*)+', decl_part, re.DOTALL)
    if m:
        leading_comment = m.group(0).strip()
        decl_part = decl_part[m.end():]

    decl_part = decl_part.strip()
    paren = decl_part.index('(')
    pre = decl_part[:paren].strip()
    toks = pre.split()
    name = toks[-1]
    ret_type = ' '.join(toks[:-1]) if len(toks) > 1 else 'void'

    depth = 0
    close = None
    for i in range(paren, len(decl_part)):
        if decl_part[i] == '(':
            depth += 1
        elif decl_part[i] == ')':
            depth -= 1
            if depth == 0:
                close = i
                break
    params_text = decl_part[paren + 1:close]
    params = split_params(params_text)
    if params == ['void'] or params == ['']:
        params = []

    return name, ret_type, params, body_part.strip(), leading_comment


name_type_re = re.compile(r'^(.*?)([A-Za-z_][A-Za-z0-9_]*)$')


def param_name(p):
    m = name_type_re.match(p.strip())
    return m.group(2) if m else p


def param_type(p):
    m = name_type_re.match(p.strip())
    return m.group(1).strip() if m else ''


by_file = defaultdict(list)
all_scopes = defaultdict(list)  # scope tuple -> list of (kind, member, ret_type, params(no this), const, ghidra_name)
wrappers = defaultdict(list)    # file -> list of wrapper decl strings

n_parse_fail = 0
for f in funcs:
    try:
        name, ret_type, params, body, lead = parse_decl(f['raw_body'])
    except Exception as e:
        n_parse_fail += 1
        f['parse_error'] = str(e)
        continue
    f['ghidra_name'] = name
    f['ret_type'] = ret_type
    f['params'] = params
    f['body'] = body
    f['lead_comment'] = lead

print('parse failures:', n_parse_fail, '/', len(funcs))

with open(r"C:\Users\PC\AppData\Local\Temp\claude\c--Users-PC-Desktop-RNS510\b36ea6fd-e6fc-4628-8258-2b448f26d38f\scratchpad\funcs2.pkl", 'wb') as fh:
    pickle.dump(funcs, fh)
