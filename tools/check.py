"""Run one .l4 file and print what l4 says, compactly.

    python3 tools/check.py l4/takanon/takanon-sherut-ovdei-horaa/1.7.l4

Prints `ok: True|False`, every error and warning (deduplicated), and every
#EVAL / #ASSERT / #TRACE result. The gate is `ok`: `l4 check` exits 0 even
when the file has errors.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import l4run  # noqa: E402


def main(path: str) -> int:
    f = Path(path).resolve()
    r = subprocess.run([l4run.compiler(), "run", "--json", f"--fixed-now={l4run.FIXED_NOW}", f.name],
                       cwd=f.parent, capture_output=True, text=True)
    try:
        d = json.loads(r.stdout)
    except json.JSONDecodeError:
        print(r.stdout, r.stderr)
        return 1
    print("ok:", d["ok"])
    seen = set()
    for x in l4run.diagnostics(d.get("diagnostics")):
        if x.get("severity") not in ("error", "warning"):
            continue
        key = (x.get("file"), x.get("range"), x["message"][:80])
        if key in seen:
            continue
        seen.add(key)
        print(f"{x['severity'].upper()} {x.get('file')} {x.get('range')}: {' '.join(x['message'].split())}")
    for res in d.get("results", []):
        val = str(res.get("value"))
        print(f"{res.get('kind')} {res.get('range')}: {val if len(val) < 300 else val[:300] + ' …'}")
    return 0 if d["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
