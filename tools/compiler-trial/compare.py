"""New build vs pinned baseline: files that differ, distinct new messages."""
import collections, json, re, sys
base = {json.loads(l)["file"]: json.loads(l) for l in open(sys.argv[1])}
new = {json.loads(l)["file"]: json.loads(l) for l in open(sys.argv[2])}
print("files", len(base), len(new), "missing in new", sorted(set(base) - set(new))[:5])
def key(d):
    return (d.get("severity"), re.sub(r"`[^`]*`|\"[^\"]*\"|\d+", "…", d.get("message", ""))[:200])
cnt = collections.defaultdict(list)
st = collections.Counter()
for f, n in new.items():
    b = base.get(f, {"diagnostics": [], "l4_ok": True, "asserts_false": [], "n_asserts": 0})
    bk = {(d.get("severity"), d.get("message")) for d in b["diagnostics"]}
    for d in n["diagnostics"]:
        if (d.get("severity"), d.get("message")) not in bk:
            cnt[key(d)].append((f, d))
    if n["l4_ok"] != b["l4_ok"]: st["l4_ok changed"] += 1
    if n["asserts_false"]: st["files with a false assert"] += 1
    if n["n_asserts"] != b["n_asserts"]: st["assert count differs"] += 1; print("asserts", f, b["n_asserts"], n["n_asserts"])
    if n.get("rc"): st["nonzero rc"] += 1
print(dict(st), "new asserts total", sum(n["n_asserts"] for n in new.values()), "base", sum(b["n_asserts"] for b in base.values()))
for k, v in sorted(cnt.items(), key=lambda kv: -len(kv[1])):
    files = sorted({f for f, _ in v})
    print(f"\n{k[0]} x{len(v)} in {len(files)} files: {k[1]}\n  e.g. {files[0]} {v[0][1].get('range')}: {v[0][1].get('message')[:400]}")
walls = sorted(((n.get("wall", 0), f) for f, n in new.items()), reverse=True)
print("\nnew total wall (sum per file)", round(sum(w for w, _ in walls)), "s")
