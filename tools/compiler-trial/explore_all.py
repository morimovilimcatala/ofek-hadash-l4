"""`l4 explore` over every DEONTIC rule in the repository, without touching it.

For each file declaring one, a wrapper in OUT/wrap/ imports the file's module
(by its l4/modules name) and names one zero-input `trial N` per instance:
  - a rule with no inputs: itself;
  - a rule whose inputs are all BOOLEAN (up to 3): every combination;
  - a rule whose inputs are all Party: `the teaching employee` and `the State`.
Any other rule is listed as not explored (its inputs have no finite set to
try, or would need a sample). A file's own #TRACEs are explored as well, in
the file's own directory. Results: OUT/explore.json.

  python3 deontic.py REPO > OUT/deontic.json      # the inventory it reads
  python3 explore_all.py REPO EXE XDG OUT [--jobs N]
  python3 explore_dig.py OUT/explore.jsonl          # the summary

XDG is the XDG_DATA_HOME whose jl4/libraries holds the build's own prelude
(a trial build installed beside the pinned one must not read the pinned
build's libraries). Written for MMS-759; a trial, not part of the build.
"""
import itertools, json, os, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

repo, exe, xdg, out = Path(sys.argv[1]).resolve(), sys.argv[2], sys.argv[3], Path(sys.argv[4])
jobs = int(sys.argv[sys.argv.index("--jobs") + 1]) if "--jobs" in sys.argv else 3
L4 = repo / "l4"; MOD = L4 / "modules"
inv = json.load(open(out / "deontic.json"))
env = dict(os.environ, JL4_LIBRARY_PATH=str(MOD), XDG_DATA_HOME=xdg)
(out / "wrap").mkdir(parents=True, exist_ok=True)

link = {}
for l in MOD.iterdir():
    if l.is_symlink():
        link[l.resolve()] = l.name.removesuffix(".l4")


def ty(t):
    return t.split("@")[0].strip()


def instances(r):
    ins = r["inputs"]; ts = [ty(t) for _, t in ins]
    if not ins:
        return [("", "none")]
    if all(t == "BOOLEAN" for t in ts) and len(ts) <= 3:
        return [(" " + " ".join(c), "bool") for c in itertools.product(["TRUE", "FALSE"], repeat=len(ts))]
    if all(t == "Party" for t in ts):
        return [(" " + " ".join([p] * len(ts)), "party") for p in ("`the teaching employee`", "`the State`")]
    return []


def run(cmd, cwd, timeout=900):
    try:
        p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return -9, "", "timeout"


def explore_file(f):
    rows = [r for r in inv if r["file"] == f]
    src = L4 / f
    res = {"file": f, "rules": len(rows), "trials": [], "skipped": [], "trace": None, "errors": []}
    mod = link.get(src.resolve())
    trials = []
    for r in rows:
        inst = instances(r)
        if not inst:
            res["skipped"].append({"name": r["name"], "inputs": r["inputs"]})
        for args, kind in inst:
            trials.append({"rule": r["name"], "args": args.strip(), "kind": kind, "line": r["line"]})
    direct = [t for t in trials if t["kind"] == "none"]
    wrapped = [t for t in trials if t["kind"] != "none"]
    if direct:
        # a rule with no inputs is explored in its own file, which needs no import
        cmd = [exe, "explore", src.name, "--json", "--max-states", "3000"]
        for t in direct:
            t["trial"] = t["rule"].strip("`")
            cmd += ["--contract", t["trial"]]
        rc, so, se = run(cmd, src.parent)
        res["rc"] = rc
        try:
            graphs = {g["contract"].strip("`"): g for g in json.loads(so)}
        except Exception:
            graphs = {}
            res["errors"].append("direct: " + (se or so)[-1500:])
        for t in direct:
            t["graph"] = graphs.get(t["trial"])
    if wrapped and (L4 / "modules" / f"takanon-{mod.replace('.', '-')}.l4").exists() if mod else False:
        mod = f"takanon-{mod.replace('.', '-')}"
    if wrapped and mod:
        w = out / "wrap" / (re.sub(r"[^A-Za-z0-9]+", "_", f) + ".l4")
        body = ["IMPORT prelude", "IMPORT parties", f"IMPORT `{mod}`", ""]
        for i, t in enumerate(wrapped):
            t["trial"] = f"trial {i}"
            body.append(f"DECIDE `trial {i}` IS {t['rule']}{(' ' + t['args']) if t['args'] else ''}")
        w.write_text("\n".join(body) + "\n", encoding="utf-8")
        cmd = [exe, "explore", w.name, "--json", "--max-states", "3000"]
        for t in wrapped:
            cmd += ["--contract", t["trial"]]
        rc, so, se = run(cmd, w.parent)
        res["rc_wrapped"] = rc
        try:
            graphs = {g["contract"].strip("`"): g for g in json.loads(so)}
        except Exception:
            graphs = {}
            res["errors"].append("wrapped: " + (se or so)[-1500:])
        for t in wrapped:
            t["graph"] = graphs.get(t["trial"])
    elif wrapped:
        res["errors"].append("no l4/modules link")
    res["trials"] = trials
    if "#TRACE" in src.read_text(encoding="utf-8"):
        rc, so, se = run([exe, "explore", src.name, "--json", "--max-states", "3000"], src.parent)
        try:
            res["trace"] = {"rc": rc, "graphs": json.loads(so)}
        except Exception:
            res["trace"] = {"rc": rc, "error": (se or so)[-1500:]}
    return res


files = sorted({r["file"] for r in inv})
if len(sys.argv) > 5 and sys.argv[5] == "--only":
    files = [f for f in files if f in sys.argv[6].split(",")]
import threading
jl = out / "explore.jsonl"; seen = {}
if jl.exists():
    for ln in jl.read_text().splitlines():
        try:
            r = json.loads(ln); seen[r["file"]] = r
        except Exception:
            pass
files = [f for f in files if f not in seen]
done = list(seen.values()); wl = threading.Lock()
def rec(f):
    r = explore_file(f)
    with wl, open(jl, "a") as fh:
        fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    return r
with ThreadPoolExecutor(jobs) as pool:
    for r in pool.map(rec, files):
        done.append(r)
        n = sum(1 for t in r["trials"] if t.get("graph"))
        print(f"{r['file']}: {n}/{len(r['trials'])} explored, {len(r['skipped'])} skipped, trace={'yes' if r['trace'] else 'no'} {r.get('rc')} {('ERR ' + r['errors'][0][:200]) if r['errors'] else ''}", flush=True)
(out / "explore.json").write_text(json.dumps(done, ensure_ascii=False, indent=1))
