# tools/find_empty_functions.py
import ast, sys
p = sys.argv[1] if len(sys.argv) > 1 else 'src/core/enhanced_email_librarian_server.py'
src = open(p, encoding='utf-8').read()
mod = ast.parse(src)

def is_app_decorator(d):
    # return True if decorator like @self.app.get/post/put/delete
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

for node in ast.walk(mod):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        # detect if body has meaningful statements (not just docstring/pass)
        body = [n for n in node.body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str))]
        if not body or (len(body)==1 and isinstance(body[0], ast.Pass)):
            is_route = any(is_app_decorator(d) or (isinstance(d, ast.Attribute) and getattr(d,'attr','').startswith('app')) for d in node.decorator_list)
            print(f"{p}:{node.lineno}:{node.name}:{'route' if is_route else 'internal'}")
