"""The pinned build's `l4 run --json` results for every file, read from the
shared l4-cache store (keyed by the file's source, its imports and the
compiler id), in l4trial.py's record shape.

  python3 baseline.py REPO OUT/results.jsonl
"""
import json, sys
from pathlib import Path
repo = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(repo / "tools"))
import l4run  # noqa: E402
cid = l4run.compiler_id(l4run.compiler())
with open(sys.argv[2], "w") as fh:
    for p in l4run.files():
        if l4run.tested_through(p):
            continue
        e = l4run.stored(l4run.key(p, cid))
        data = json.loads((e / "run").read_text())
        rec = {"file": str(p.relative_to(repo / "l4")), "l4_ok": bool(data.get("l4_ok", data.get("ok"))),
               "asserts_false": [r.get("range") for r in data.get("results", [])
                                 if r.get("kind") == "assertion" and str(r.get("value")).strip().lower() != "true"],
               "n_asserts": sum(1 for r in data.get("results", []) if r.get("kind") == "assertion"),
               "diagnostics": [d for d in data.get("diagnostics", []) if d.get("severity") in ("error", "warning")]}
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
print("cid", cid)
