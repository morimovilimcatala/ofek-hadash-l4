"""Run the L4 toolchain over every .l4 file and keep what it says.

For each file under l4/ this writes, to build/l4/<same path>:

  .run.json      `l4 run --json`  — diagnostics and every #EVAL/#ASSERT result
  .render.html   `l4 render`      — L4's own rendering of the rules as a document
  .graph.dot     `l4 state-graph` — each regulative rule as a state diagram (GraphViz)

A root (l4/lib/*root.l4) gets the first only: it is checked, not rendered
(`is_a_root`).

A file's outputs are keyed by its own bytes, the bytes of every module it
imports, transitively, wherever it lives (MMS-524: any file may import any
other), and the compiler's own identity, so a changed rule or a changed
compiler is a different key and a stale reading cannot be served. Nothing
else can change what `l4 run` says about a file: its neighbours in the
directory are not keyed, so adding a document re-checks that document and
what imports it, not the whole collection (2026-10-21: a merge of one batch
re-checked ~35 agreements, 9–15 minutes).

Every run has l4/modules/ on JL4_LIBRARY_PATH (tools/modules.py): the
compiler finds an import by its bare name, and that directory holds every
module under its one name.

The compiler is `$L4` if set, else `l4` on PATH. toolchain/L4_COMMIT pins the
legalese/l4-ide revision it is built from (toolchain/build-l4.sh).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import modules  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
L4_DIR = ROOT / "l4"
OUT = ROOT / "build" / "l4"
FIXED_NOW = "2026-06-01T00:00:00Z"   # the corpus snapshot's date


def compiler() -> str:
    exe = os.environ.get("L4") or shutil.which("l4")
    if not exe:
        sys.exit("l4 not found: set $L4 or put it on PATH (toolchain/build-l4.sh)")
    return exe


def compiler_id(exe: str) -> str:
    h = hashlib.sha256(Path(exe).resolve().read_bytes()).hexdigest()[:16]
    return h


def files() -> list[Path]:
    """Every .l4 file, but a link: a link is another file's name for an
    IMPORT in a directory that is not its own (a section's `common.l4`, a
    collection's `conventions.l4`, a site page's `takanon-1-11.l4`), and its
    target is run where it lives."""
    return sorted(p for p in L4_DIR.rglob("*.l4")
                  if not p.is_symlink() and p.parent != modules.MODULES)


IMPORT_RE = re.compile(r"^IMPORT\s+`?([^`\n]+?)`?\s*$", re.M)


def imported(path: Path) -> set[Path]:
    """Every file `path` imports, transitively, resolved the compiler's way:
    beside the importing file, then in l4/modules/. A library the compiler
    carries (prelude, daydate) is no file here and is keyed by the compiler."""
    seen: set[Path] = set()
    todo = [path]
    while todo:
        f = todo.pop()
        for name in IMPORT_RE.findall(f.read_text(encoding="utf-8")):
            for cand in (f.parent / f"{name}.l4", modules.MODULES / f"{name}.l4"):
                if cand.exists():
                    real = cand.resolve()
                    if real not in seen:
                        seen.add(real)
                        todo.append(cand)
                    break
    return seen


def key(path: Path, cid: str) -> str:
    h = hashlib.sha256(cid.encode())
    for f in sorted({path.resolve()} | imported(path)):
        h.update(f.name.encode() + b"\0" + f.read_bytes() + b"\0")
    h.update(path.name.encode())
    return h.hexdigest()


def outputs(path: Path) -> dict[str, Path]:
    # by name, not with_suffix: a section file is "1.7.l4", and
    # with_suffix would read ".7" as the suffix and write "1.run.json"
    rel = path.relative_to(L4_DIR)
    stem = rel.name.removesuffix(".l4")
    d = OUT / rel.parent
    return {"run": d / f"{stem}.run.json",
            "render": d / f"{stem}.render.html",
            "graph": d / f"{stem}.graph.dot",
            "key": d / f"{stem}.key"}


BLOCK = re.compile(r"^File:\s*(?P<file>.*?)\n(?P<body>.*?)(?=^File:|\Z)", re.S | re.M)


def diagnostics(raw) -> list[dict]:
    """`l4 run --json` prints each diagnostic as the LSP's text block
    ("File: … Range: 71:5-71:8 … Severity: DiagnosticSeverity_Error …
    Message: …"); split them into {file, range, severity, message}."""
    out = []
    for item in raw or []:
        if isinstance(item, dict):
            out.append(item)
            continue
        text = str(item)
        blocks = list(BLOCK.finditer(text))
        if not blocks:
            out.append({"severity": "error", "range": None, "message": text.strip()})
            continue
        for b in blocks:
            body = b.group("body")
            rng = re.search(r"Range:\s*(\S+)", body)
            sev = re.search(r"Severity:\s*DiagnosticSeverity_(\w+)", body)
            msg = body.split("Message:", 1)[1] if "Message:" in body else body
            out.append({"file": b.group("file").strip(),
                        "range": rng.group(1) if rng else None,
                        "severity": (sev.group(1) if sev else "Error").lower(),
                        "message": "\n".join(l.strip() for l in msg.strip().splitlines()).strip()})
    return out


def own_warnings(data: dict, name: str) -> list[dict]:
    """The compiler's warnings about this file itself (an import's are its
    own file's to answer). A warning is refused like an error: the one kind
    the tree has carried is "AND and OR operators appear at the same
    indentation level", which is a grouping the reader cannot see."""
    return [d for d in data.get("diagnostics", [])
            if d.get("severity") == "warning" and d.get("file") in (None, name)]


def verdict(data: dict, name: str) -> bool:
    """The gate: the file checks, every #ASSERT holds, and the compiler
    warns about nothing in it."""
    return bool(data.get("l4_ok", data.get("ok"))) and all_asserts_hold(data) \
        and not own_warnings(data, name)


def all_asserts_hold(data: dict) -> bool:
    return all(str(r.get("value")).strip().lower() == "true"
               for r in data.get("results", []) if r.get("kind") == "assertion")


def is_a_root(path: Path) -> bool:
    """A root (l4/lib/*root.l4, MMS-521): it imports whole families of
    instruments, so each pass of the compiler over it takes minutes and
    gigabytes (the root: ~10 minutes, 4.6 GB, 2026-10-22). Its page is read
    off its source and its results (tools/roots.py); no text sits beside it
    for `l4 render`'s prose, and it declares no obligation for a state
    graph, so it is checked once and not rendered."""
    return path.parent == L4_DIR / "lib" and path.name.endswith("root.l4")


def run_one(path: Path, exe: str, cid: str) -> tuple[Path, bool, bool]:
    out = outputs(path)
    k = key(path, cid)
    if out["key"].exists() and out["key"].read_text() == k:
        ok = verdict(json.loads(out["run"].read_text()), path.name)
        if not out["graph"].exists():
            if is_a_root(path):
                out["graph"].write_text("", encoding="utf-8")
            else:
                write_graph(path, exe, out["graph"])
        return path, ok, False
    out["run"].parent.mkdir(parents=True, exist_ok=True)
    cwd = path.parent
    r = subprocess.run([exe, "run", "--json", f"--fixed-now={FIXED_NOW}",
                        path.name], cwd=cwd, capture_output=True, text=True, env=modules.env())
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        data = {"file": path.name, "ok": False, "results": [],
                "diagnostics": [{"severity": "error",
                                 "message": (r.stdout + r.stderr).strip()}]}
    data["diagnostics"] = diagnostics(data.get("diagnostics"))
    # l4's own `ok` stays true when an #ASSERT comes back FALSE or the
    # compiler warns; the gate here is all three (`verdict`)
    data["l4_ok"] = bool(data.get("ok"))
    data["ok"] = verdict(data, path.name)
    out["run"].write_text(json.dumps(data, ensure_ascii=False, indent=1),
                          encoding="utf-8")
    if is_a_root(path):
        out["render"].write_text("", encoding="utf-8")
        out["graph"].write_text("", encoding="utf-8")
    else:
        rr = subprocess.run([exe, "render", "--format", "html",
                             f"--fixed-now={FIXED_NOW}", path.name],
                            cwd=cwd, capture_output=True, text=True, env=modules.env())
        out["render"].write_text(rr.stdout if rr.returncode == 0 else "",
                                 encoding="utf-8")
        write_graph(path, exe, out["graph"])
    out["key"].write_text(k)
    return path, bool(data.get("ok")), True


def write_graph(path: Path, exe: str, dest: Path) -> None:
    """Every MUST/MAY/SHANT the file declares, as L4's own state diagram."""
    g = subprocess.run([exe, "state-graph", path.name], cwd=path.parent,
                       capture_output=True, text=True, env=modules.env())
    dest.write_text(g.stdout if g.returncode == 0 else "", encoding="utf-8")


# What a check costs is the source it compiles: the file and everything it
# imports. Measured on a Mac, 2026-10-22, as macOS's "peak memory footprint"
# (resident and compressed together, what Linux would hold in RAM):
#   the completion agreement of 2012 (0.26 MB imported)   1.7 GB
#   circular תש"ף/1 (0.38 MB)                              2.3 GB
#   the agreement of 19.3.2017 (0.74 MB)                   5.2 GB
#   the Ofek Hadash agreements' root (0.84 MB)             8.8 GB
#   the root (2.02 MB)                                    21.0 GB
# about 10 GB per MB. A fixed number of checks at once (5 GB each, then the
# roots one at a time) still stopped GitHub's 16 GB runner twice (exit 143;
# "the hosted runner lost communication"), so each check now reserves what
# it is estimated to need out of the machine's memory, and one that needs
# more than all of it runs alone (the workflow gives the runner swap for it).
GB_PER_MB_IMPORTED = 10.5
GB_BASE = 0.5


def estimated_gb(path: Path) -> float:
    size = sum(f.stat().st_size for f in imported(path) | {path.resolve()})
    return GB_BASE + GB_PER_MB_IMPORTED * size / 1e6


def memory_gb() -> float:
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2**30
    except (ValueError, OSError, AttributeError):
        return 8.0


def is_kept(path: Path, cid: str) -> bool:
    out = outputs(path)
    return out["key"].exists() and out["key"].read_text() == key(path, cid)


def main(argv: list[str]) -> int:
    exe = compiler()
    cid = compiler_id(exe)
    targets = [Path(a).resolve() for a in argv] or files()
    jobs = int(os.environ.get("JOBS", os.cpu_count() or 2))
    budget = float(os.environ.get("L4_MEMORY_GB", memory_gb() - 2))
    bad = []
    # the roots last, and the heaviest first among the rest, so that the
    # light checks fill the memory the heavy ones leave
    order = sorted(targets, key=lambda p: (is_a_root(p), -estimated_gb(p)))
    lock = threading.Condition()
    held = {"gb": 0.0}

    def check(p: Path):
        if is_kept(p, cid):
            return run_one(p, exe, cid)
        need = min(estimated_gb(p), budget)
        with lock:
            lock.wait_for(lambda: held["gb"] == 0 or held["gb"] + need <= budget)
            held["gb"] += need
        try:
            return run_one(p, exe, cid)
        finally:
            with lock:
                held["gb"] -= need
                lock.notify_all()

    with ThreadPoolExecutor(jobs) as pool:
        for path, ok, fresh in pool.map(check, order):
            rel = path.relative_to(ROOT)
            print(f"{'ok ' if ok else 'ERR'} {'ran ' if fresh else 'kept'} {rel}", flush=True)
            if not ok:
                bad.append(rel)
    if bad:
        print(f"\n{len(bad)} file(s) did not check, had a failing #ASSERT or a compiler warning:")
        for b in bad:
            print("  ", b)
        return 1
    print(f"\n{len(targets)} file(s) check, every #ASSERT holds and nothing warns")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
