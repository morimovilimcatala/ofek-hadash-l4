"""Findings, traced (MMS-534; the client: "Can we do Trace instead of ASSERT
in edge cases?").

A finding may name `trace` expressions — every finding of kind `edge-case`
does; this runs them with `#EVALTRACE` through the l4.wasm the calculator
runs (the pinned CLI captures no trace), on the finding's file and every
module it reaches, and returns each expression's value and its
step-by-step trace. The finding's evidence stays an #ASSERT in the file:
that is what the build checks; the trace is what the card shows.

A trace evaluates its whole file and everything the file imports, so one
can take minutes (a Q&A edge case loads the takanon). Each is kept under
build/l4/traces/, keyed by the evaluator, the files and the expressions, as
tools/l4run.py keeps the checks: the site and the tests share one run, and
CI restores build/l4 from the last deploy, so a push re-traces only the
findings whose files it touched. Those that do run, run side by side.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import calculator

ROOT = Path(__file__).resolve().parent.parent
KEPT = ROOT / "build" / "l4" / "traces"
# what evaluates a trace: a change to any of them re-runs every trace
EVALUATOR = [ROOT / "tools" / "edge_traces.mjs", ROOT / "tools" / "assets" / "calc-core.mjs",
             ROOT / "tools" / "assets" / "l4wasm" / "l4.mjs", ROOT / "tools" / "assets" / "l4wasm" / "l4.wasm"]


def evaluator_id() -> str:
    h = hashlib.sha256()
    for f in EVALUATOR:
        h.update(f.read_bytes() if f.exists() else b"-")
    return h.hexdigest()


def spec_of(c: dict) -> dict:
    """What node is given for a case: its file, every module it reaches, and
    the expressions to trace."""
    f = ROOT / c["l4"]
    files = {}
    for name in calculator.import_closure(f):
        m = calculator.module_file(name, f.parent)
        if m is not None:
            files[name] = m.read_text(encoding="utf-8")
    return {"id": c["id"], "main": f.read_text(encoding="utf-8"), "files": files, "exprs": c["trace"]}


def key(spec: dict, evaluator: str) -> str:
    body = json.dumps([evaluator, spec["main"], sorted(spec["files"].items()), spec["exprs"]],
                      ensure_ascii=False)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def run(specs: list[dict]) -> dict[str, list[dict]]:
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "spec.json").write_text(json.dumps(specs), encoding="utf-8")
        p = subprocess.run(["node", str(ROOT / "tools" / "edge_traces.mjs"), f"{d}/spec.json"],
                           capture_output=True, text=True, timeout=1800)
    if p.returncode:
        raise RuntimeError(p.stderr)
    return json.loads(p.stdout.strip().splitlines()[-1])


def traces(cases: list[dict]) -> dict[str, list[dict]] | None:
    """{case id: [{expr, value, traceText}]}, or None without node."""
    if not shutil.which("node"):
        return None
    evaluator = evaluator_id()
    out: dict[str, list[dict]] = {}
    missing: list[tuple[dict, Path]] = []
    for c in cases:
        if not c.get("trace"):
            continue
        spec = spec_of(c)
        kept = KEPT / f"{key(spec, evaluator)}.json"
        if kept.exists():
            out[c["id"]] = json.loads(kept.read_text(encoding="utf-8"))
        else:
            missing.append((spec, kept))
    if missing:
        # one node per trace, a few at a time: each holds an evaluator of its own
        jobs = int(os.environ.get("TRACE_JOBS", min(4, os.cpu_count() or 2)))
        with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
            done = list(pool.map(lambda m: run([m[0]]), missing))
        KEPT.mkdir(parents=True, exist_ok=True)
        for (spec, kept), got in zip(missing, done):
            out[spec["id"]] = got[spec["id"]]
            kept.write_text(json.dumps(got[spec["id"]], ensure_ascii=False), encoding="utf-8")
    return out
