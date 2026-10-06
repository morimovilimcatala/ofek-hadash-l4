"""Run the L4 toolchain over every .l4 file and keep what it says.

For each file under l4/ this writes, to build/l4/<same path>:

  .run.json      `l4 run --json`  — diagnostics and every #EVAL/#ASSERT result
  .render.html   `l4 render`      — L4's own rendering of the rules as a document

A file's outputs are keyed by the bytes of every .l4 file in its directory
(a section imports its document's shared vocabulary) and by the compiler's
own identity, so a changed rule or a changed compiler is a different key
and a stale reading cannot be served.

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
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

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
    return sorted(L4_DIR.rglob("*.l4"))


def key(path: Path, cid: str) -> str:
    h = hashlib.sha256(cid.encode())
    for f in sorted(path.parent.glob("*.l4")):
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


def run_one(path: Path, exe: str, cid: str) -> tuple[Path, bool, bool]:
    out = outputs(path)
    k = key(path, cid)
    if out["key"].exists() and out["key"].read_text() == k:
        ok = json.loads(out["run"].read_text()).get("ok", False)
        return path, ok, False
    out["run"].parent.mkdir(parents=True, exist_ok=True)
    cwd = path.parent
    r = subprocess.run([exe, "run", "--json", f"--fixed-now={FIXED_NOW}",
                        path.name], cwd=cwd, capture_output=True, text=True)
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        data = {"file": path.name, "ok": False, "results": [],
                "diagnostics": [{"severity": "error",
                                 "message": (r.stdout + r.stderr).strip()}]}
    data["diagnostics"] = diagnostics(data.get("diagnostics"))
    out["run"].write_text(json.dumps(data, ensure_ascii=False, indent=1),
                          encoding="utf-8")
    rr = subprocess.run([exe, "render", "--format", "html",
                         f"--fixed-now={FIXED_NOW}", path.name],
                        cwd=cwd, capture_output=True, text=True)
    out["render"].write_text(rr.stdout if rr.returncode == 0 else "",
                             encoding="utf-8")
    out["key"].write_text(k)
    return path, bool(data.get("ok")), True


def main(argv: list[str]) -> int:
    exe = compiler()
    cid = compiler_id(exe)
    targets = [Path(a).resolve() for a in argv] or files()
    jobs = int(os.environ.get("JOBS", os.cpu_count() or 2))
    bad = []
    with ThreadPoolExecutor(jobs) as pool:
        for path, ok, fresh in pool.map(lambda p: run_one(p, exe, cid), targets):
            rel = path.relative_to(ROOT)
            print(f"{'ok ' if ok else 'ERR'} {'ran ' if fresh else 'kept'} {rel}")
            if not ok:
                bad.append(rel)
    if bad:
        print(f"\n{len(bad)} file(s) did not check or had a failing #ASSERT:")
        for b in bad:
            print("  ", b)
        return 1
    print(f"\n{len(targets)} file(s) check and every #ASSERT holds")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
