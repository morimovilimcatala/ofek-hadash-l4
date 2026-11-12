"""Run the suite in parallel, one test class per process (MMS-617).

`make test` used to run the suite in one process: 122 tests in about 16
minutes on a four-core container, most of it a few classes that run the
compiler, the calculator's wasm or a walk of the import graph. The classes
do not share state (each reads the tree; a case that writes uses its own
temporary directory), so each runs in a process of its own and as many run
at once as there are cores.

What it reports is what the serial run reports: every test, once. The
classes are taken from unittest's own discovery, and the run fails unless the
tests the processes ran add up to the number discovery counts, so a class
cannot fall out of the run unnoticed. A class that skips itself in setUpClass
(a check that needs something the machine does not have: the corpus
repository's reader for test_quotations on the CI runner) runs no test and
reports one skip; its discovered tests are counted as run and skipped, and
the class is named, so a skip is visible and never a lost class. Failures are
printed in full.

The slowest classes start first, by the times the last run recorded in
build/run_tests_times.json, so that a long class is not left to start last.

    python3 tools/run_tests.py            # JOBS workers, default: the cores
    python3 tools/run_tests.py -j 2
    python3 -m unittest discover -s tests # the serial run, unchanged
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"
TIMES = ROOT / "build" / "run_tests_times.json"

RAN = re.compile(r"^Ran (\d+) tests? in", re.M)
COUNTS = re.compile(r"(failures|errors|skipped|expected failures|unexpected successes)=(\d+)")


def classes() -> tuple[list[str], int, dict[str, int]]:
    """Every TestCase class discovery finds, as `module.Class`, how many
    tests discovery counts in all, and how many in each class."""
    sys.path.insert(0, str(TESTS))
    suite = unittest.TestLoader().discover(str(TESTS))
    names: list[str] = []
    per: dict[str, int] = {}

    def walk(s):
        for t in s:
            if isinstance(t, unittest.TestSuite):
                walk(t)
            else:
                if isinstance(t, unittest.loader._FailedTest):   # an import error
                    sys.exit(f"discovery failed: {t.id()}")
                n = f"{type(t).__module__}.{type(t).__qualname__}"
                if n not in names:
                    names.append(n)
                per[n] = per.get(n, 0) + 1
    walk(suite)
    return names, suite.countTestCases(), per


def run(name: str) -> dict:
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(
        filter(None, [str(TESTS), os.environ.get("PYTHONPATH")])))
    t0 = time.monotonic()
    r = subprocess.run([sys.executable, "-m", "unittest", name], cwd=ROOT, env=env,
                       capture_output=True, text=True)
    out = r.stdout + r.stderr
    m = RAN.search(out)
    counts = {k: int(v) for k, v in COUNTS.findall(out.rsplit("\nRan ", 1)[-1])}
    return {"name": name, "ok": r.returncode == 0, "ran": int(m.group(1)) if m else 0,
            "counts": counts, "seconds": time.monotonic() - t0, "output": out}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-j", "--jobs", type=int,
                    default=int(os.environ.get("JOBS", os.cpu_count() or 2)))
    args = ap.parse_args(argv)
    names, expected, per = classes()
    try:
        times = json.loads(TIMES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        times = {}
    names.sort(key=lambda n: -times.get(n, 0.0))
    t0 = time.monotonic()
    results = []
    with ThreadPoolExecutor(args.jobs) as pool:
        for res in pool.map(run, names):
            # skipped in setUpClass: no test ran, one skip reported
            if res["ok"] and res["ran"] == 0 and res["counts"].get("skipped", 0) > 0:
                res["ran"] = per[res["name"]]
                res["counts"]["skipped"] = per[res["name"]]
                res["note"] = "  (skipped in setUpClass)"
            results.append(res)
            print(f"{'ok ' if res['ok'] else 'ERR'} {res['seconds']:6.1f}s {res['ran']:3} "
                  f"{res['name']}{res.get('note', '')}", flush=True)
    wall = time.monotonic() - t0
    TIMES.parent.mkdir(parents=True, exist_ok=True)
    TIMES.write_text(json.dumps({r["name"]: round(r["seconds"], 1) for r in results},
                                indent=1, sort_keys=True), encoding="utf-8")
    bad = [r for r in results if not r["ok"]]
    for r in bad:
        print(f"\n{'=' * 70}\n{r['name']}\n{'=' * 70}\n{r['output']}")
    ran = sum(r["ran"] for r in results)
    total = {}
    for r in results:
        for k, v in r["counts"].items():
            total[k] = total.get(k, 0) + v
    tail = ", ".join(f"{k}={v}" for k, v in sorted(total.items()))
    print(f"\nRan {ran} tests in {wall:.1f}s ({len(names)} classes, {args.jobs} at a time)")
    if ran != expected:
        print(f"FAILED: discovery counts {expected} tests and the processes ran {ran}")
        return 1
    if bad:
        print(f"FAILED ({tail})")
        return 1
    print(f"OK{f' ({tail})' if tail else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
