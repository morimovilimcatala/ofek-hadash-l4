"""Continuation lines that L4 groups differently from how they read.

In L4 a line that begins with an arithmetic operator takes the REST OF THAT
LINE as the operator's right operand:

    10 MINUS 3 MINUS 2              is 5, not 3: the second line is
        MINUS 1 MINUS 1             10 - 3 - 2 - (1 - 1)

So a continuation line must carry one operand, or a rest whose own
operators bind tighter than its leading one (`PLUS a DIVIDED BY b`). A
chain of PLUS or TIMES computes the same either way, but `l4 render`
shows the regrouped rest as one item, so it is flagged too.

    python3 tools/layout_lint.py [--fix]     # --fix splits same-operator chains
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PREC = {"PLUS": 1, "MINUS": 1, "+": 1, "-": 1, "TIMES": 2, "DIVIDED BY": 2, "*": 2, "/": 2}
NAME = {"+": "PLUS", "-": "MINUS", "*": "TIMES", "/": "DIVIDED BY"}
LEAD = re.compile(r"^(\s+)(PLUS|MINUS|TIMES|DIVIDED BY|[-+*/])\s")
OP = re.compile(r"(?<![`\w])(PLUS|MINUS|TIMES|DIVIDED BY)(?![`\w])|(?<=\s)[-+*/](?=\s)")


def top_ops(text: str) -> list[tuple[int, str]]:
    """Operators outside brackets, backticks and strings: (offset, op)."""
    masked = re.sub(r"`[^`]*`|\"[^\"]*\"", lambda m: "x" * len(m.group()), text)
    out, depth, i = [], 0, 0
    for m in OP.finditer(masked):
        pre = masked[:m.start()]
        if pre.count("(") - pre.count(")") == 0:
            out.append((m.start(), NAME.get(m.group(0), m.group(0))))
    return out


def scan(path: Path):
    """(line, kind, text): kind 'wrong' changes the value, 'render' only the prose."""
    for n, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
        code = line.split("--")[0]
        m = LEAD.match(code)
        if not m:
            continue
        lead = NAME.get(m.group(2), m.group(2))
        rest = code[m.end():]
        ops = [op for _, op in top_ops(rest)]
        bad = [op for op in ops if PREC[op] <= PREC[lead]]
        if not bad:
            continue
        same_assoc = all(op == lead for op in bad) and lead in ("PLUS", "TIMES")
        yield n, ("render" if same_assoc else "wrong"), line.strip()


def fix(path: Path) -> int:
    lines = path.read_text(encoding="utf-8").split("\n")
    changed = 0
    out = []
    for line in lines:
        code, sep, comment = line.partition("--")
        m = LEAD.match(code)
        if m:
            lead = NAME.get(m.group(2), m.group(2))
            rest = code[m.end():]
            ops = top_ops(rest)
            if ops and all(op == lead for _, op in ops) and lead in ("PLUS", "TIMES"):
                indent, parts, prev = m.group(1), [], 0
                for off, op in ops:
                    parts.append(rest[prev:off].strip())
                    prev = off + len(op)
                parts.append(rest[prev:].strip())
                for k, p in enumerate(parts):
                    tail = (" " + sep + comment) if (sep and k == len(parts) - 1) else ""
                    out.append(f"{indent}{m.group(2)} {p}{tail}")
                changed += 1
                continue
        out.append(line)
    if changed:
        path.write_text("\n".join(out), encoding="utf-8")
    return changed


def main(argv: list[str]) -> int:
    files = sorted((ROOT / "l4").rglob("*.l4"))
    if "--fix" in argv:
        print(sum(fix(f) for f in files), "line(s) split")
    bad = 0
    for f in files:
        for n, kind, text in scan(f):
            print(f"{kind:6} {f.relative_to(ROOT)}:{n}: {text}")
            bad += 1
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
