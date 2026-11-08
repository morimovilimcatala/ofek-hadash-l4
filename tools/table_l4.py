"""Write a corpus salary table out as L4 data (`a published table`,
l4/tables/tables-common.l4), cell for cell, so that nobody types one.

    python3 tools/table_l4.py [--grid] <document> <row key> <name> <title> <code|-> <d.m.yyyy>

prints the definition, cell by cell or, with --grid, as `a published grid`
(the grades once, each row's amounts in their order: cheaper to check, so
the form for a document with many tables, MMS-629), to be pasted under the
`@ref` that cites the table in the file that encodes the document. A step
the page prints as no number ("#REF!") is no step. The table is read by
POSITION, as
tests/test_tables.py reads it back: the header row names the grades — a
number, a half grade ("1.5"), a letter of a principal's or deputy's table
(א … ד, א+ … ג+: 1 … 4, 1.5 … 3.5, the base agreement's numbering) or a
scale's grade ("דרגות 34", "דרגות 34+": 34 and 34.5, the "+" the stay
supplement, which sits between the grade and the next); the first column
is the seniority or complexity level; a column the header names no grade
in is the row's step ("2%"); a row headed "ותק", or a row with no label
whose cells are percentages, carries the step to each grade. A one-row
table that prints no label is row 0. A cell the corpus marks "[לא קריא]"
is left out of its row, and the tool says which (stderr): the file that
cites the table says so with `the text is missing`.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import akn  # noqa: E402

LETTERS = {"א": 1, "א+": 1.5, "ב": 2, "ב+": 2.5, "ג": 3, "ג+": 3.5, "ד": 4}
ILLEGIBLE = "לא קריא"
AMOUNT = re.compile(r"\d{1,3}(,\d{3})*(\.\d+)?|\d+(\.\d+)?")


def grade_of(head: str) -> float | None:
    h = " ".join(head.split())
    if h in LETTERS:
        return LETTERS[h]
    if re.fullmatch(r"\d+(\.5)?", h):
        return float(h)
    m = re.fullmatch(r"דרגות (\d+)(\+?)", h)
    if m:
        return int(m.group(1)) + (0.5 if m.group(2) else 0)
    return None


def number(s: str) -> float:
    return float(s.replace(",", "").replace("%", "").strip())


def is_rates_row(r: list[str]) -> bool:
    return r[0].strip() == "ותק" or (not r[0].strip() and any("%" in c for c in r[1:]))


def read(cells: list[list[str]]):
    """(rates, rows, illegible) of a corpus table: rates {grade: rate},
    rows [(label, step or None, {grade: amount as printed})], and the
    (label, grade) of every cell marked illegible."""
    grade = {i: g for i, h in enumerate(cells[0]) if i and (g := grade_of(h)) is not None}
    step = [i for i in range(1, len(cells[0])) if i not in grade]
    rates, rows, illegible = {}, [], []
    body = cells[1:]
    for r in body:
        if is_rates_row(r):
            # a step the page prints as no number (a spreadsheet's "#REF!",
            # marked [כך במקור]) is no step: the grade has none
            rates = {grade[i]: number(c) for i, c in enumerate(r)
                     if i in grade and re.fullmatch(r"[\d.]+%", c.strip())}
            continue
        if not any(c.strip() for c in r[1:]):
            continue        # a level the page prints with every cell blank
        label = r[0].strip()
        if not label and len([x for x in body if not is_rates_row(x)]) == 1:
            label = "0"
        steps = [number(r[i]) for i in step if r[i].strip()]
        row = {}
        for i, c in enumerate(r):
            if i not in grade or not c.strip():
                continue
            if ILLEGIBLE in c:
                illegible.append((int(label), grade[i]))
                continue
            row[grade[i]] = c.strip()
        rows.append((int(label), steps[0] if steps else None, row))
    return rates, rows, illegible


def fmt(x: float) -> str:
    return f"{x:g}"


def amount(s: str) -> str:
    return s.replace(",", "")


def l4(cells, name: str, title: str, code: str, day: str) -> str:
    rates, rows, _ = read(cells)
    d, m, y = day.split(".")
    code_l4 = "NOTHING" if code == "-" else f"(JUST {code})"
    lines = [f"`{name}` MEANS",
             f'    `a published table` "{title}" {code_l4} (DATE_FROM_DMY {int(d)} {int(m)} {y})']
    if rates:
        lines.append("        (LIST " + ", ".join(f"`a published rate` {fmt(g)} ({fmt(r)}%)" for g, r in rates.items()) + ")")
    else:
        lines.append("        EMPTY")
    out = []
    for label, st, row in rows:
        rate = "NOTHING" if st is None else f"(JUST ({fmt(st)}%))"
        cs = ", ".join(f"`cell` {fmt(g)} {amount(v)}" for g, v in row.items())
        out.append(f"`a published row` {label} {rate} (LIST {cs})")
    lines.append("        (LIST " + (",\n              ".join(out)) + ")")
    return "\n".join(lines)


def l4_grid(cells, name: str, title: str, code: str, day: str) -> str:
    """The same table as `a published grid`: the grades once, each row's
    amounts in grade order from the first grade it prints. A row whose
    cells skip a grade cannot be written this way and is refused."""
    rates, rows, _ = read(cells)
    grades = sorted({g for _, _, row in rows for g in row})
    d, m, y = day.split(".")
    code_l4 = "NOTHING" if code == "-" else f"(JUST {code})"
    lines = [f"`{name}` MEANS",
             f'    `a published grid` "{title}" {code_l4} (DATE_FROM_DMY {int(d)} {int(m)} {y})']
    if rates:
        lines.append("        (LIST " + ", ".join(f"`a published rate` {fmt(g)} ({fmt(r)}%)" for g, r in rates.items()) + ")")
    else:
        lines.append("        EMPTY")
    lines.append("        (LIST " + ", ".join(fmt(g) for g in grades) + ")")
    out = []
    for label, st, row in rows:
        gs = sorted(row)
        first = grades.index(gs[0])
        if gs != grades[first:first + len(gs)]:
            raise ValueError(f"{name}: row {label} skips a grade: {gs}")
        rate = "NOTHING" if st is None else f"(JUST ({fmt(st)}%))"
        out.append(f"`amounts` {label} {rate} {fmt(gs[0])} (LIST {', '.join(amount(row[g]) for g in gs)})")
    lines.append("        (LIST " + (",\n              ".join(out)) + ")")
    return "\n".join(lines)


def table(document: str, key: str):
    for sec in akn.sections(document):
        for r in sec.rows:
            if r.key == key:
                return r.cells
    raise KeyError(f"{document}: no table {key}")


def main(argv: list[str]) -> int:
    grid = "--grid" in argv
    document, key, name, title, code, day = [a for a in argv if a != "--grid"]
    cells = table(document, key)
    _, _, illegible = read(cells)
    if illegible:
        print(f"{key}: {len(illegible)} cells marked illegible, left out: {illegible}", file=sys.stderr)
    print((l4_grid if grid else l4)(cells, name, title, code, day))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
