"""Obligations whose breach no time can reach (MMS-765).

`PARTY p MUST a LEST BREACH …` with no `WITHIN` and no `BEFORE` has no
deadline, so the LEST branch can never be taken: the obligation is owed for
ever and the breach the text names is unreachable. Where the cited text
states a date or a period, the rule carries it as a `WITHIN` (a fixed date
as `WITHIN 0 OF (days from …)`, the way takanon 5.4 does); where it ties the
time to an event with no length, or gives no time at all, the rule stays as
it is, and this module counts what is left so the count moves only down
(tests/test_repo.py, `Deadlines`).

A clause is read off the layout, the way the compiler groups it: its
keywords (`WITHIN`, `BEFORE`, `LEST`) are on the MUST's own line or begin a
line at the clause's column, at the MUST's bracket depth. A keyword on a
deeper line, or in deeper brackets, belongs to a clause nested in it. The
reading was checked against `l4 ast` (each regulative's `due` and `lest`)
on 2026-11-15, and agreed on every file that parses on its own.

    python3 tools/deadlines.py            # every site, file:line
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOKEN = re.compile(r"(?<![`\w])(PARTY|MUST|MAY|SHANT|WITHIN|BEFORE|HENCE|LEST|RAND|ROR)(?![`\w])|[()\[\]]")


def mask(line: str) -> str:
    """The line with strings, backtick names and its comment blanked."""
    out, i, n = [], 0, len(line)
    while i < n:
        ch = line[i]
        if ch in "`\"":
            j = i + 1
            while j < n and line[j] != ch:
                j += 2 if ch == '"' and line[j] == "\\" else 1
            out.append(" " * (min(j, n - 1) - i + 1))
            i = j + 1
            continue
        if line.startswith("--", i):
            break
        out.append(ch)
        i += 1
    return "".join(out).ljust(n)


def tokens(text: str):
    """(line, column, depth, token, first on its line, masked line) per keyword."""
    depth = 0
    for n, raw in enumerate(text.split("\n"), 1):
        line = mask(raw)
        for m in TOKEN.finditer(line):
            t = m.group(0)
            if t in "([":
                depth += 1
            elif t in ")]":
                depth -= 1
            else:
                yield n, m.start(), depth, t, line[:m.start()].strip() == "", line


def clauses(text: str):
    """Every MUST clause: (line, has a deadline, has a LEST)."""
    toks = list(tokens(text))
    lines = text.split("\n")
    for i, (ln, col, d, t, lead, masked) in enumerate(toks):
        if t != "MUST":
            continue
        # the clause's column: the MUST's, when it begins its line; else its
        # PARTY's on the same line; else the line's own indent
        k = col
        if not lead:
            party = [pc for pl, pc, pd, pt, _, _ in toks[:i]
                     if pl == ln and pt == "PARTY" and pd == d]
            k = party[-1] if party else len(masked) - len(masked.lstrip())
        due = lest = False
        stop_same_line = False
        for ln2, c2, d2, t2, lead2, _ in toks[i + 1:]:
            if d2 < d:
                break
            if ln2 != ln:
                head = mask(lines[ln2 - 1])
                indent = len(head) - len(head.lstrip())
                if head.strip() and indent < k and d2 == d:
                    break
            if d2 != d:
                continue
            if ln2 == ln:
                if t2 in ("PARTY", "MUST", "MAY", "SHANT", "RAND", "ROR"):
                    stop_same_line = True
                if stop_same_line:
                    continue
            elif not (lead2 and c2 == k):
                continue
            if lead2 and c2 == k and t2 in ("RAND", "ROR", "PARTY", "MUST", "MAY", "SHANT"):
                break
            if t2 in ("WITHIN", "BEFORE"):
                due = True
            elif t2 == "LEST":
                lest = True
        yield ln, due, lest


def undated(path: Path):
    """Lines of the MUST … LEST clauses in a file with no WITHIN or BEFORE."""
    return [ln for ln, due, lest in clauses(path.read_text(encoding="utf-8"))
            if lest and not due]


def files():
    return [f for f in sorted((ROOT / "l4").rglob("*.l4")) if not f.is_symlink()]


def sites():
    return [(f.relative_to(ROOT).as_posix(), ln) for f in files() for ln in undated(f)]


if __name__ == "__main__":
    found = sites()
    for f, ln in found:
        print(f"{f}:{ln}")
    print(len(found), file=sys.stderr)
