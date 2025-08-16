# tools/find_incomplete_functions.py
import ast, sys, re
from pathlib import Path
p = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('src/core/enhanced_email_librarian_server.py')
src = p.read_text(encoding='utf-8')
mod = ast.parse(src)
lines = src.splitlines()

def is_app_decorator(d):
    try:
        func = d.func if isinstance(d, ast.Call) else d
        if isinstance(func, ast.Attribute):
            val = func.value
            if isinstance(val, ast.Attribute):
                return getattr(val, 'attr', '') == 'app'
            if isinstance(val, ast.Name):
                return val.id == 'self' and getattr(func, 'attr','') in ('get','post','put','delete')
    except Exception:
        return False
    return False

candidates = []
for node in ast.walk(mod):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        start = getattr(node, 'lineno', None)
        end = getattr(node, 'end_lineno', None)
        if not start or not end:
            continue
        snippet = '\n'.join(lines[start-1:end])
        # count non-blank, non-comment lines
        nonblank = [ln for ln in snippet.splitlines() if ln.strip()!='' and not ln.strip().startswith('#')]
        # remove leading docstring line if present
        if nonblank and re.match(r"^[ru]*[f]?['\"]{3}", nonblank[0].lstrip()):
            # drop first line of docstring
            nonblank = nonblank[1:]
        meaningful_lines = len([ln for ln in nonblank if ln.strip()!='pass'])
        total_lines = end - start + 1
        has_todo = bool(re.search(r"TODO|placeholder|not implemented|pass", snippet, re.I))
        has_ellipsis = '...' in snippet
        has_pass = any(re.match(r"^\s*pass\s*$", ln) for ln in snippet.splitlines())
        is_route = any(is_app_decorator(d) or (isinstance(d, ast.Attribute) and getattr(d,'attr','').startswith('app')) for d in node.decorator_list)
        preview = '\\n'.join([ln.strip() for ln in snippet.splitlines()[:3]])
        score = meaningful_lines
        # heuristic: candidate if very short or has TODO or ellipsis or pass-only
        incomplete = (meaningful_lines < 6) or has_todo or has_ellipsis or (has_pass and meaningful_lines<=2)
        if incomplete:
            candidates.append((start, node.name, 'route' if is_route else 'internal', meaningful_lines, total_lines, has_todo, has_ellipsis, has_pass, preview))

out = Path('tools/incomplete_report.txt')
with out.open('w', encoding='utf-8') as f:
    for it in sorted(candidates):
        f.write(f"{p}:{it[0]}:{it[1]}:{it[2]}:meaningful={it[3]}:total={it[4]}:todo={it[5]}:ellipsis={it[6]}:has_pass={it[7]}\n  preview: {it[8]}\n\n")
print(f"Wrote {out}")
