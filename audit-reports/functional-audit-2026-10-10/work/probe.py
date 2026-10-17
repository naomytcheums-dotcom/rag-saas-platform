"""Read-only evidence finder: for each feature id, regex over backend, frontend, migrations and tests.
Prints counts + best files so a human/agent can then read the code and assign a verified status."""
import os, re, sys, json, collections
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
def walk(roots, exts):
    out = []
    for r in roots:
        for dp, dn, fn in os.walk(os.path.join(ROOT, r)):
            dn[:] = [d for d in dn if d not in ("node_modules", ".next", "__pycache__", ".venv")]
            out += [os.path.join(dp, f) for f in fn if f.endswith(exts)]
    return out
_cache = {}
def load(files):
    for f in files:
        if f not in _cache:
            try: _cache[f] = open(f, encoding="utf-8", errors="ignore").read()
            except Exception: _cache[f] = ""
BACK = walk(["api"], (".py",)); FRONT = walk(["frontend/app", "frontend/components", "frontend/lib"], (".ts", ".tsx"))
TESTS = walk(["tests"], (".py",)) + [f for f in walk(["frontend"], (".test.ts", ".test.tsx"))]
SDK = walk(["sdks"], (".py", ".ts", ".tsx", ".vue"))
for grp in (BACK, FRONT, TESTS, SDK): load(grp)
def rel(f): return os.path.relpath(f, ROOT).replace(os.sep, "/")
def hits(files, rx):
    c = collections.Counter()
    r = re.compile(rx, re.I)
    for f in files:
        n = len(r.findall(_cache[f]))
        if n: c[rel(f)] = n
    return c
def probe(fid, code_rx, test_rx=None, front_rx=None):
    b = hits(BACK, code_rx); fr = hits(FRONT, front_rx or code_rx); t = hits(TESTS, test_rx or code_rx)
    top = lambda c, k: ",".join(f"{p}({n})" for p, n in c.most_common(k))
    print(f"{fid}| B{len(b)} F{len(fr)} T{len(t)}| back: {top(b,3)} | front: {top(fr,2)} | tests: {top(t,2)}")
if __name__ == "__main__":
    spec = json.load(open(sys.argv[1], encoding="utf-8"))
    for fid, v in spec.items():
        probe(fid, v[0], v[1] if len(v) > 1 else None, v[2] if len(v) > 2 else None)
