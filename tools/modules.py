"""l4/modules/: every L4 module, linked once, by the one name it is imported by.

    python3 tools/modules.py           # list what is missing, stale or ambiguous
    python3 tools/modules.py --write   # make l4/modules/ match

WHY (MMS-524, measured 2026-10-21 on the pinned compiler, l4-ide 838c92e).
The compiler finds `IMPORT `x`` by the bare file name x.l4: in the importing
file's directory, the working directory, then $JL4_LIBRARY_PATH. A file it
reaches through a link resolves ITS imports from the link's directory, not
its own. So for any file to import any other, which is what the one codebase
needs (MMS-521), every module has to sit, under its own name, in one
directory that is on the library path, and every name has to mean one file.
That directory is l4/modules/; tools/l4run.py and tools/check.py run every
file with JL4_LIBRARY_PATH pointing at it.

A module is every real .l4 file under l4/, by its file name (the client
chose unique names over patching the compiler, so a name two files share is
an error here, and tests/test_repo.py holds it), and every name a directory
already links to a module (`common` is the takanon's helpers, `conventions`
the conventions module, `takanon-1-28` takanon §1.28,
`collective_agreements_law` the statute). Such an alias must name the same
file wherever it is used.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
L4 = ROOT / "l4"
MODULES = L4 / "modules"


def wanted() -> tuple[dict[str, Path], list[str]]:
    """{module name: the real file it means}, and every name that means two
    files (an error)."""
    names: dict[str, Path] = {}
    clashes: list[str] = []

    def add(name: str, target: Path) -> None:
        target = target.resolve()
        if name in names and names[name] != target:
            clashes.append(f"{name}: {names[name].relative_to(ROOT)} and {target.relative_to(ROOT)}")
        names.setdefault(name, target)

    for f in sorted(L4.rglob("*.l4")):
        if f.parent == MODULES:
            continue
        if not f.is_symlink():
            add(f.name.removesuffix(".l4"), f)
    for f in sorted(L4.rglob("*.l4")):
        if f.parent == MODULES or not f.is_symlink():
            continue
        add(f.name.removesuffix(".l4"), f)
    return names, clashes


def problems() -> list[str]:
    names, clashes = wanted()
    out = [f"two files under one name: {c}" for c in clashes]
    have = {p.name.removesuffix(".l4"): p for p in MODULES.glob("*.l4")} if MODULES.exists() else {}
    for name, target in sorted(names.items()):
        link = have.get(name)
        if link is None:
            out.append(f"missing: {name}")
        elif not link.is_symlink() or link.resolve() != target:
            out.append(f"wrong: {name} -> {link.resolve() if link.exists() else 'nothing'}, wants {target.relative_to(ROOT)}")
    for name in sorted(set(have) - set(names)):
        out.append(f"stale: {name}")
    return out


def write() -> None:
    names, clashes = wanted()
    if clashes:
        raise SystemExit("two files under one name:\n  " + "\n  ".join(clashes))
    MODULES.mkdir(exist_ok=True)
    for p in MODULES.glob("*.l4"):
        if p.name.removesuffix(".l4") not in names:
            p.unlink()
    for name, target in names.items():
        link = MODULES / f"{name}.l4"
        rel = os.path.relpath(target, MODULES)
        if link.is_symlink() and os.readlink(link) == rel:
            continue
        if link.exists() or link.is_symlink():
            link.unlink()
        link.symlink_to(rel)


def env() -> dict[str, str]:
    """The environment every l4 run gets: the module directory on the
    library path."""
    return {**os.environ, "JL4_LIBRARY_PATH": str(MODULES)}


if __name__ == "__main__":
    if "--write" in sys.argv[1:]:
        write()
    found = problems()
    print("\n".join(found) if found else f"l4/modules: {len(wanted()[0])} modules, each under one name")
    sys.exit(1 if found else 0)
