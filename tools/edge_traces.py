"""Findings, traced (MMS-534; the client: "Can we do Trace instead of ASSERT
in edge cases?").

A finding may name `trace` expressions — every finding of kind `edge-case`
does; this runs them with `#EVALTRACE` through the l4.wasm the calculator
runs (the pinned CLI captures no trace), on the finding's file and every
module it reaches, and returns each expression's value and its
step-by-step trace. The finding's evidence stays an #ASSERT in the file:
that is what the build checks; the trace is what the card shows.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import calculator

ROOT = Path(__file__).resolve().parent.parent


def traces(cases: list[dict]) -> dict[str, list[dict]] | None:
    """{case id: [{expr, value, traceText}]}, or None without node."""
    if not shutil.which("node"):
        return None
    spec = []
    for c in cases:
        if not c.get("trace"):
            continue
        f = ROOT / c["l4"]
        files = {}
        for name in calculator.import_closure(f):
            m = calculator.module_file(name, f.parent)
            if m is not None:
                files[name] = m.read_text(encoding="utf-8")
        spec.append({"id": c["id"], "main": f.read_text(encoding="utf-8"), "files": files, "exprs": c["trace"]})
    if not spec:
        return {}
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "spec.json").write_text(json.dumps(spec), encoding="utf-8")
        p = subprocess.run(["node", str(ROOT / "tools" / "edge_traces.mjs"), f"{d}/spec.json"],
                           capture_output=True, text=True, timeout=900)
    if p.returncode:
        raise RuntimeError(p.stderr)
    return json.loads(p.stdout.strip().splitlines()[-1])
