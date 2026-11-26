"""Run L4's analysis backends over every file and keep what they find (MMS-804).

mengwong's bug hunt (24-25 November 2026, ofek-hadash-l4 PR #1) ran the
compiler's own backends over this repository, one "hunter" per family, and
found eight bugs that `l4 run` alone could not see. This is those hunters,
as a check: each runs on every file it applies to, and the suite holds
what they find exactly (tests/test_hunt.py), so a new finding, or a finding
that goes away, is seen.

  obligations  `l4 lts --json` on every file with a #TRACE: what each trace
               owes, discharges and breaches. Each trace's standing must be
               the one `l4 run` gives the same trace (build/l4, `make l4`).
  explore      `l4 explore --json` on the same files: every position each
               traced contract can reach. Counted per contract: explored
               completely or not, deadlocks (a state that is not terminal
               and has no way out), and whether fulfilment and a breach can
               be reached at all.
  verify       `l4 verify --format json` on every file: the boolean decision
               skeleton's unsatisfiable rules, dead branches, vacuous guards
               and unreachable outcomes, counted by kind.
  prove        `l4 prove` on every file (z3): an #ASSERT the evaluator
               cannot decide because it reads a section GIVEN is proved or
               refuted for every input. A refutation is a false claim.
  coverage     `l4 coverage` on every file: each decision's buckets, and the
               ones no input can realise.
  tla          `l4 explore --emit` writes each regulative rule that takes
               no inputs as a TLA+ model, and TLC (the TLA+ model checker,
               tla2tools.jar, toolchain/fetch-tla.sh) checks it, with
               deadlock checking off: a model TLC finds an error in is
               counted.

The hunters the report also ran and this does not: the four proof
assistants (Lean, Rocq, F*, Dafny), which are on draft branches of l4-ide
and in no build; DMN on the KIE and Camunda engines; the payee-lever and
pay-loop probes, which are files of the report's and are filed as findings
when they are read (MMS-799); and a blind re-encoding, which is a person's
work, not a check.

Each file's result is kept under build/hunt/<path>.json, keyed as
`make l4` keys its own (tools/l4run.py `key`: the file, every module it
imports, and the compiler) plus this tool's version, so a rerun computes
only what changed. Roots and their tests are left out: each imports a whole
collection, and every file it imports is hunted on its own.

  python3 tools/hunt.py              # every file; then build/hunt/summary.json
  python3 tools/hunt.py FILE ...     # those files only (no summary)
  HUNTERS=verify,prove python3 tools/hunt.py   # some hunters only
  HUNT_REDO=coverage python3 tools/hunt.py      # run these again, keep the rest

The compiler is l4run's (`$L4`, else `l4` on PATH); z3 is `$Z3_EXE` or `z3`
on PATH; TLC is `$TLA2TOOLS` (default build/tla2tools.jar, fetched by
toolchain/fetch-tla.sh) run with `java`; without it, `tla` is not run.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import l4run  # noqa: E402
import modules  # noqa: E402

ROOT = l4run.ROOT
OUT = ROOT / "build" / "hunt"
SUMMARY = OUT / "summary.json"
VERSION = "4"
HUNTERS = ("obligations", "explore", "verify", "prove", "coverage", "tla")
TIMEOUT = int(os.environ.get("HUNT_TIMEOUT", "240"))
TLA2TOOLS = Path(os.environ.get("TLA2TOOLS", ROOT / "build" / "tla2tools.jar"))
# explore's bounds: at its default of 256 instants per act a contract with
# two open MAYs and no deadline ran past five minutes at 9d26421; a bound hit
# is counted ("refused or stopped at a bound"), never read as a finding
EXPLORE_BOUNDS = ["--max-states", "2000", "--max-depth", "40", "--max-instants", "32"]


def selected() -> tuple[str, ...]:
    """The hunters to run: $HUNTERS, else every one, but `tla` only where
    TLC is installed (toolchain/fetch-tla.sh)."""
    want = os.environ.get("HUNTERS")
    if want:
        return tuple(h for h in HUNTERS if h in want.split(","))
    return tuple(h for h in HUNTERS if h != "tla" or tlc_available())


def hunted(path: Path) -> bool:
    return not l4run.is_a_root_or_its_tests(path)


def has(path: Path, directive: str) -> bool:
    return re.search(rf"^{re.escape(directive)}\b", path.read_text(encoding="utf-8"), re.M) is not None


def run(args: list[str], cwd: Path, timeout: int = TIMEOUT) -> tuple[int | None, str, str]:
    """(exit status, stdout, stderr); the status is None on a timeout."""
    try:
        r = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                           env=modules.env(), timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return None, "", f"timed out after {timeout}s"


def standing_of_run_value(value: str) -> str:
    """A trace's standing as `l4 run` prints its residual."""
    v = value.strip()
    if v == "FULFILLED":
        return "fulfilled"
    if v.startswith(("BREACHED", "DEONTIC BREACHED")):   # 9d26421 prints the latter
        return "breached"
    return "inProgress"


def run_traces(path: Path) -> dict[int, str]:
    """Each #TRACE's standing by its line, from `make l4`'s results."""
    out = l4run.outputs(path)["run"]
    if not out.exists():
        return {}
    data = json.loads(out.read_text(encoding="utf-8"))
    traces = {}
    for r in data.get("results", []):
        if not r.get("line", "").startswith("#TRACE"):
            continue
        m = re.search(r":(\d+):\d+", r.get("range", ""))
        if m and "value" in r:
            traces[int(m.group(1))] = standing_of_run_value(r["value"])
    return traces


def hunt_obligations(path: Path, exe: str) -> dict:
    if not has(path, "#TRACE"):
        return {"applies": False}
    code, out, err = run([exe, "lts", "--json", path.name], path.parent)
    if code is None:
        return {"applies": True, "timeout": True}
    try:
        traces = json.loads(out)
    except json.JSONDecodeError:
        return {"applies": True, "error": (err or out).strip()[:400]}
    by_run = run_traces(path)
    disagree = []
    for t in traces:
        mine = t.get("standing", {}).get("status")
        theirs = by_run.get(t.get("line"))
        if theirs is not None and mine != theirs:
            disagree.append({"line": t.get("line"), "lts": mine, "run": theirs})
    return {"applies": True, "traces": len(traces),
            "standings": {s: sum(1 for t in traces if t.get("standing", {}).get("status") == s)
                          for s in ("fulfilled", "breached", "inProgress")},
            "disagreements": disagree}


def hunt_explore(path: Path, exe: str) -> dict:
    if not has(path, "#TRACE"):
        return {"applies": False}
    code, out, err = run([exe, "explore", "--json", *EXPLORE_BOUNDS, path.name], path.parent)
    if code is None:
        return {"applies": True, "timeout": True}
    try:
        contracts = json.loads(out)
    except json.JSONDecodeError:
        return {"applies": True, "exit": code, "error": (err or out).strip()[:400]}
    rows = []
    for c in contracts:
        states, transitions = c.get("states", []), c.get("transitions", [])
        leaving = {t["from"] for t in transitions}
        residuals = [s.get("residual", "") for s in states]
        cov = c.get("coverage", {})
        rows.append({
            "contract": c.get("contract"),
            "states": len(states),
            "complete": bool(cov.get("complete")),
            # reachability and deadlocks are read only off a graph the
            # explorer finished: a refused act or a hit bound leaves states
            # with no way out that are only unexplored
            "settled": bool(cov.get("frontierExhausted")) and not cov.get("refused") and not cov.get("stops"),
            "refused": len(cov.get("refused", [])),
            "deadlocks": sum(1 for s in states if not s.get("terminal") and s["id"] not in leaving),
            "fulfilment reachable": any(r.strip() == "FULFILLED" for r in residuals),
            "breach reachable": any(r.strip().startswith("BREACHED") for r in residuals),
        })
    return {"applies": True, "exit": code, "contracts": rows}


def hunt_verify(path: Path, exe: str) -> dict:
    code, out, err = run([exe, "verify", "--format", "json", path.name], path.parent)
    if code is None:
        return {"applies": True, "timeout": True}
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return {"applies": True, "exit": code, "error": (err or out).strip()[:400]}
    kinds: dict[str, int] = {}
    analysed = 0
    for d in data.get("decisions", []):
        analysed += bool(d.get("analysed"))
        for f in d.get("findings", []):
            kinds[f.get("kind", "?")] = kinds.get(f.get("kind", "?"), 0) + 1
    return {"applies": True, "decisions": len(data.get("decisions", [])),
            "analysed": analysed, "findings": kinds}


PROVE_RE = re.compile(r"(\d+) obligations: (\d+) proved, (\d+) refuted, (\d+) unknown")


def hunt_prove(path: Path, exe: str) -> dict:
    if not has(path, "#ASSERT"):
        return {"applies": False}
    code, out, err = run([exe, "prove", path.name], path.parent)
    if code is None:
        return {"applies": True, "timeout": True}
    m = PROVE_RE.search(out)
    if not m:
        return {"applies": True, "exit": code, "error": (err or out).strip()[-400:]}
    refuted = [ln.strip()[:300] for ln in out.splitlines() if ln.lstrip().startswith("refuted")]
    return {"applies": True, "exit": code,
            "verdicts": {"obligations": int(m.group(1)), "proved": int(m.group(2)),
                         "refuted": int(m.group(3)), "unknown": int(m.group(4))},
            "refuted": refuted}


COVERAGE_RE = re.compile(r"^Coverage: (?:(\d+) decisions? covered|NOTHING COVERED)", re.M)


def count_in(pattern: str, text: str) -> int:
    m = re.search(pattern, text)
    return int(m.group(1)) if m else 0


def hunt_coverage(path: Path, exe: str) -> dict:
    code, out, err = run([exe, "coverage", path.name], path.parent)
    if code is None:
        return {"applies": True, "timeout": True}
    m = COVERAGE_RE.search(out)
    if not m:
        return {"applies": True, "exit": code, "error": (err or out).strip()[-400:]}
    line = out[m.start():].splitlines()[0]
    return {"applies": True, "exit": code, "decisions": int(m.group(1) or 0),
            "unrealisable": count_in(r"(\d+) proved impossible", line),
            "undecided": count_in(r"(\d+) undecided", line),
            "not covered": "NOT COVERED" in line}


def tlc_available() -> bool:
    return TLA2TOOLS.exists() and shutil.which("java") is not None


DEONTIC_RULE_RE = re.compile(r"^GIVETH A DEONTIC[^\n]*\n(?:DECIDE `([^`]+)` IS|`([^`]+)` MEANS)", re.M)


def input_free_contracts(path: Path) -> list[str]:
    """The regulative rules the file declares that take no inputs: `l4
    explore --emit` models a contract from its outset, and one that takes
    inputs can be modelled only by splitting the file per trace (the bug
    hunt's T2), which this does not do."""
    text = path.read_text(encoding="utf-8")
    names = []
    for m in DEONTIC_RULE_RE.finditer(text):
        head = text[max(0, text.rfind("\n\n", 0, m.start())):m.start()]
        if "GIVEN" not in head:
            names.append(m.group(1) or m.group(2))
    return names


def hunt_tla(path: Path, exe: str) -> dict:
    contracts = input_free_contracts(path)
    if not contracts:
        return {"applies": False}
    if not tlc_available():
        return {"applies": True, "error": f"no TLC: {TLA2TOOLS} or java missing"}
    args = [a for name in contracts for a in ("--contract", name)]
    models = []
    with tempfile.TemporaryDirectory() as d:
        # one call per file: explore loads the module once and writes one
        # model per contract, <base>_<n>.tla in the order they were named
        code, out, err = run([exe, "explore", "--emit", d, *EXPLORE_BOUNDS, *args, path.name],
                             path.parent, timeout=TIMEOUT * 3)
        if code is None:
            return {"applies": True, "timeout": True, "contracts": len(contracts)}
        for tla in sorted(Path(d).glob("*.tla")):
            cfg = tla.with_suffix(".cfg")
            if not cfg.exists():
                continue
            c, o, e = run(["java", "-XX:+UseParallelGC", "-cp", str(TLA2TOOLS), "tlc2.TLC",
                           "-deadlock", "-workers", "1", "-config", cfg.name, tla.name], Path(d))
            text = o + e
            models.append({
                "model": tla.stem,
                "timeout": c is None,
                "error": c is not None and "No error has been found" not in text,
                "message": next((ln for ln in text.splitlines() if ln.startswith("Error:")), "")[:300],
            })
    return {"applies": True, "exit": code, "contracts": len(contracts), "models": models}


HUNT = {"obligations": hunt_obligations, "explore": hunt_explore, "verify": hunt_verify,
        "prove": hunt_prove, "coverage": hunt_coverage, "tla": hunt_tla}


def out_path(path: Path) -> Path:
    return OUT / path.relative_to(l4run.L4_DIR).with_suffix(".json")


def hunt_one(path: Path, exe: str, cid: str, hunters: tuple[str, ...]) -> tuple[Path, dict]:
    dest = out_path(path)
    k = hashlib.sha256((l4run.key(path, cid) + VERSION).encode()).hexdigest()
    kept = json.loads(dest.read_text(encoding="utf-8")) if dest.exists() else {}
    if kept.get("key") != k:
        kept = {"key": k}
    for h in os.environ.get("HUNT_REDO", "").split(","):
        kept.pop(h, None)
    for h in hunters:
        if h not in kept:
            kept[h] = HUNT[h](path, exe)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".tmp")
    tmp.write_text(json.dumps(kept, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    tmp.replace(dest)
    return path, kept


def summarise(results: dict[str, dict]) -> dict:
    """The counts tests/test_hunt.py holds exactly."""
    s: dict[str, int] = {}

    def add(name: str, n: int = 1) -> None:
        s[name] = s.get(name, 0) + n

    for r in results.values():
        o = r.get("obligations", {})
        if o.get("applies"):
            add("obligations: files")
            add("obligations: traces", o.get("traces", 0))
            add("obligations: lts disagrees with run", len(o.get("disagreements", [])))
            add("obligations: timeouts or errors", int(bool(o.get("timeout") or o.get("error"))))
        e = r.get("explore", {})
        if e.get("applies"):
            add("explore: timeouts or errors", int(bool(e.get("timeout") or e.get("error"))))
            for c in e.get("contracts", []):
                add("explore: contracts")
                add("explore: explored completely", int(c["complete"]))
                add("explore: refused or stopped at a bound", int(not c["settled"]))
                if c["settled"]:
                    add("explore: deadlocks", c["deadlocks"])
                    add("explore: fulfilment unreachable", int(not c["fulfilment reachable"]))
                    add("explore: breach unreachable", int(not c["breach reachable"]))
        v = r.get("verify", {})
        if v.get("applies"):
            add("verify: files")
            add("verify: timeouts or errors", int(bool(v.get("timeout") or v.get("error"))))
            add("verify: decisions analysed", v.get("analysed", 0))
            for kind, n in v.get("findings", {}).items():
                add(f"verify: {kind}", n)
        p = r.get("prove", {})
        if p.get("applies"):
            add("prove: timeouts or errors", int(bool(p.get("timeout") or p.get("error"))))
            for verdict, n in p.get("verdicts", {}).items():
                add(f"prove: {verdict}", n)
        c = r.get("coverage", {})
        if c.get("applies"):
            add("coverage: timeouts or errors", int(bool(c.get("timeout") or c.get("error"))))
            add("coverage: decisions", c.get("decisions", 0))
            add("coverage: files with a decision not covered", int(bool(c.get("not covered"))))
            add("coverage: buckets proved impossible", c.get("unrealisable", 0))
            add("coverage: undecided", c.get("undecided", 0))
        t = r.get("tla", {})
        if t.get("applies"):
            add("tla: timeouts or errors", int(bool(t.get("timeout") or t.get("error"))))
            add("tla: contracts", t.get("contracts", 0))
            for m in t.get("models", []):
                add("tla: models")
                add("tla: models TLC finds an error in", int(m["error"]))
                add("tla: models TLC did not finish", int(m["timeout"]))
    return dict(sorted(s.items()))


def main(argv: list[str]) -> int:
    exe = l4run.compiler()
    cid = l4run.compiler_id(exe)
    hunters = selected()
    whole = not argv
    paths = [Path(a).resolve() for a in argv] if argv else [p for p in l4run.files() if hunted(p)]
    jobs = int(os.environ.get("JOBS", os.cpu_count() or 2))
    results: dict[str, dict] = {}
    with ThreadPoolExecutor(jobs) as pool:
        for path, r in pool.map(lambda p: hunt_one(p, exe, cid, hunters), paths):
            results[path.relative_to(ROOT).as_posix()] = r
    summary = summarise(results)
    for k, v in summary.items():
        print(f"{v:8d}  {k}")
    if whole:
        SUMMARY.parent.mkdir(parents=True, exist_ok=True)
        SUMMARY.write_text(json.dumps({"compiler": cid, "hunters": list(hunters), "files": len(results),
                                       "counts": summary}, indent=1, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
