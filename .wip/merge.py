"""Write the agents' applies/exceptions into conventions.toml, after each setting's basis."""
import json, sys, tomllib
from pathlib import Path
SP = Path(__file__).parent
ROOT = Path('/home/user/ofek-hadash-l4')
MANUAL = {
 "dates.start": [{"l4": "l4/takanon/takanon-sherut-ovdei-horaa/1.1.l4", "rule": "is on or after"}],
 "amounts.inputs": [{"l4": "l4/takanon/takanon-sherut-ovdei-horaa/1.1.l4", "rule": "full-position combined salary"},
                    {"l4": "l4/takanon/takanon-sherut-ovdei-horaa/1.1.l4", "rule": "1994 supplement per full position"}],
}
applies, exc = {}, {}
for k, v in MANUAL.items(): applies.setdefault(k, []).extend(v)
for f in sys.argv[1:]:
    d = json.load(open(SP / f))
    for k, v in d.get("applies", {}).items(): applies.setdefault(k, []).extend(v)
    for k, v in d.get("exceptions", {}).items(): exc.setdefault(k, []).extend(v)
q = lambda s: json.dumps(s, ensure_ascii=False)
text = (ROOT / "conventions.toml").read_text(encoding="utf-8")
ids = {s["id"] for s in tomllib.loads(text)["convention"]}
unknown = (set(applies) | set(exc)) - ids
assert not unknown, unknown
blocks = text.split("\n[[convention]]\n")
out = [blocks[0]]
for b in blocks[1:]:
    sid = tomllib.loads("[[convention]]\n" + b)["convention"][0]["id"]
    b = b.rstrip("\n").split("\n")
    b = [l for l in b if not l.startswith(("applies", "exceptions", "  {"))]  # idempotent
    seen = set(); rows = []
    for a in applies.get(sid, []):
        if not a.get("rule"): continue
        key = (a["l4"], a["rule"])
        if key not in seen: seen.add(key); rows.append(a)
    if rows:
        b.append("applies = [")
        b += [f'  {{ l4 = {q(a["l4"])}, rule = {q(a["rule"])} }},' for a in rows]
        b.append("]")
    if exc.get(sid):
        b.append("exceptions = [")
        b += ['  { l4 = ' + q(e["l4"]) + (', rule = ' + q(e["rule"]) if e.get("rule") else "")
              + ', value = ' + q(e["value"]) + ', why = ' + q(e["why"]) + ' },' for e in exc[sid]]
        b.append("]")
    out.append("\n".join(b) + "\n")
(ROOT / "conventions.toml").write_text("\n[[convention]]\n".join(out), encoding="utf-8")
print("applies:", sum(len(v) for v in applies.values()), "exceptions:", sum(len(v) for v in exc.values()))
