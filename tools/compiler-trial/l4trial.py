"""Run one `l4` build over the repository's L4 files, the way tools/l4run.py
runs them (`l4 run --json --fixed-now=…` in the file's directory, l4/modules
on JL4_LIBRARY_PATH), and keep per file: wall time, peak RSS, the parsed
diagnostics, l4's ok, and the #ASSERT results. No render, no state-graph, no
cache: this is a measurement, not a build.

  python3 l4trial.py REPO EXE OUTDIR [--xdg DIR] [--jobs N] [FILE...]
"""
import argparse, json, os, subprocess, sys, threading, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("repo"); ap.add_argument("exe"); ap.add_argument("out")
ap.add_argument("--xdg"); ap.add_argument("--jobs", type=int, default=3)
ap.add_argument("--budget", type=float, default=12.0)
ap.add_argument("files", nargs="*")
a = ap.parse_args()
repo = Path(a.repo).resolve()
sys.path.insert(0, str(repo / "tools"))
import l4run, modules  # noqa: E402

out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
if a.files:
    targets = [Path(f).resolve() for f in a.files]
else:
    targets = [p for p in l4run.files() if not l4run.tested_through(p)]
jl = out / "results.jsonl"
seen = {}
if jl.exists():
    for ln in jl.read_text().splitlines():
        try:
            r = json.loads(ln); seen[r["file"]] = r
        except Exception:
            pass
targets = [p for p in targets if str(p.relative_to(repo / "l4")) not in seen]
order = sorted(targets, key=lambda p: (l4run.is_a_root(p), -l4run.estimated_gb(p)))
env = modules.env()
if a.xdg:
    env["XDG_DATA_HOME"] = a.xdg
lock = threading.Condition(); held = {"gb": 0.0, "n": 0}


def one(p: Path):
    need = min(l4run.estimated_gb(p), a.budget)
    with lock:
        lock.wait_for(lambda: held["n"] == 0 or held["gb"] + need <= a.budget)
        held["gb"] += need; held["n"] += 1
    try:
        t0 = time.monotonic()
        pr = subprocess.Popen([a.exe, "run", "--json", f"--fixed-now={l4run.FIXED_NOW}", p.name],
                              cwd=p.parent, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        so, se = pr.communicate()
        wall = time.monotonic() - t0
        # communicate() reaped it; peak RSS read from /proc is gone, so use
        # the rusage of children accumulated per thread is not separable —
        # fall back to wait4 is impossible after reaping. Record RSS via a
        # second, timed run only where asked (timings.py).
        try:
            data = json.loads(so)
        except json.JSONDecodeError:
            data = {"ok": False, "results": [], "diagnostics": [(so + se).strip() or f"rc {pr.returncode}"]}
        diags = l4run.diagnostics(data.get("diagnostics"))
        rel = str(p.relative_to(repo / "l4"))
        rec = {"file": rel, "wall": round(wall, 2), "rc": pr.returncode, "l4_ok": bool(data.get("ok")),
               "asserts_false": [r.get("range") for r in data.get("results", [])
                                 if r.get("kind") == "assertion" and str(r.get("value")).strip().lower() != "true"],
               "n_asserts": sum(1 for r in data.get("results", []) if r.get("kind") == "assertion"),
               "diagnostics": [d for d in diags if d.get("severity") in ("error", "warning")]}
        return rec
    finally:
        with lock:
            held["gb"] -= need; held["n"] -= 1
            if held["n"] == 0:
                held["gb"] = 0.0
            lock.notify_all()


res = list(seen.values())
wl = threading.Lock()
def one_rec(p):
    r = one(p)
    with wl, open(jl, "a") as fh:
        fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    return r
with ThreadPoolExecutor(a.jobs) as pool:
    for r in pool.map(one_rec, order):
        res.append(r)
        print(f"{'ok ' if r['l4_ok'] and not r['asserts_false'] and not r['diagnostics'] else 'BAD'} {r['wall']:7.1f}s {r['file']}", flush=True)
(out / "results.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
print("done", len(res))
