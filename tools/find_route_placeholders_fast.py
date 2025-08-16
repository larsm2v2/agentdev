# tools/find_route_placeholders_fast.py
import ast, sys, pathlib

p = sys.argv[1] if len(sys.argv) > 1 else "src/core/enhanced_email_librarian_server.py"
src = open(p, "r", encoding="utf-8").read()

try:
    mod = ast.parse(src)
except Exception as e:
    print("PARSE_ERROR", e)
    sys.exit(2)

def is_app_decorator(d):
    # match decorators like @self.app.get(...), @self.app.post(...)
    if isinstance(d, ast.Call):
        func = d.func
    else:
        func = d
    # attribute chain ends with .app.get or starts with self.app
    if isinstance(func, ast.Attribute):
        # func.value might be Attribute or Name
        val = func.value
        if isinstance(val, ast.Attribute):
            # e.g. self.app.get
            return getattr(val, "attr", "") == "app" or getattr(val, "id", "") == "app"
        if isinstance(val, ast.Name):
            return val.id == "self" and getattr(func, "attr", "") in ("get", "post", "put", "delete")
    return False

for node in ast.walk(mod):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.decorator_list:
        # check if any decorator is an app route
        if not any(is_app_decorator(d) or (isinstance(d, ast.Attribute) and getattr(d, "attr", "").startswith("app")) for d in node.decorator_list):
            continue
        # ignore docstring-only
        body = [n for n in node.body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str))]
        if not body or (len(body) == 1 and isinstance(body[0], ast.Pass)):
            decs = [ast.unparse(d) if hasattr(ast, "unparse") else "<decorator>" for d in node.decorator_list]
            print(f"{p}:{node.lineno}:{node.name}:{';'.join(decs)}")