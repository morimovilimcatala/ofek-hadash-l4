"""Every salary table the L4 writes out is the corpus table it cites, cell
for cell, read by POSITION (MMS-620).

A salary table is encoded as data (`a published table`, tables-common.l4)
and its #ASSERTs check the cells against the rules that make them; nothing
held the data to the corpus text it was copied from. Until MMS-613 (the
corpus's b4e5e6a) the corpus could not be read by position: a row's step
and seniority shared a cell ("2% 2"), and a header's "1" or "דרגה 1" sat
one column off, so each file's note said how its columns had been read
around the misplacement. Since then the corpus places each column by the
page's word boxes, and a table is read the way the page prints it: the
header row names the grades (letters א to ד for a deputy's table), the
first column is the seniority or complexity level, a column the header
names no grade in is the step column, and a row headed "ותק" carries the
steps to each grade. A level printed with every cell blank (a deputy's
school has no level 1) is a row the L4 leaves out.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import akn      # noqa: E402
import build_site as site_mod  # noqa: E402

LETTERS = {"א": 1, "א+": 1.5, "ב": 2, "ב+": 2.5, "ג": 3, "ג+": 3.5, "ד": 4}

# The tables this holds, by document and row key. A table whose @ref names
# one corpus table and whose rows the L4 writes in full is held here; the
# count is exact, so a table that joins or leaves it is said.
CHECKED = 42


def number(s: str) -> float:
    return float(s.replace(",", "").replace("%", "").strip())


def l4_table(block: str):
    """(rates, rows) of one `a published table` as the L4 writes it."""
    rates = {float(g): float(v) for g, v in re.findall(r"`a published rate` ([\d.]+) \(([\d.]+)%\)", block)}
    rows = []
    for m in re.finditer(r"`a published row` (\d+) (?:NOTHING|\(JUST \(([\d.]+)%\)\)) \(LIST ([^)]*\))", block):
        cells = {float(g): float(v) for g, v in re.findall(r"`cell` ([\d.]+) ([\d.]+)", m.group(3))}
        rows.append((int(m.group(1)), float(m.group(2)) if m.group(2) else None, cells))
    return rates, rows


def corpus_table(cells: list[list[str]]):
    """(rates, rows) of a corpus table, each cell by its column."""
    grade = {}
    for i, h in enumerate(cells[0][1:], 1):
        h = h.strip()
        if h in LETTERS:
            grade[i] = LETTERS[h]
        elif re.fullmatch(r"\d+(\.5)?", h):
            grade[i] = float(h)
    step = [i for i in range(1, len(cells[0])) if i not in grade]
    rates, rows = {}, []
    for r in cells[1:]:
        if r[0].strip() == "ותק":
            rates = {grade[i]: number(c) for i, c in enumerate(r) if i in grade and c.strip()}
            continue
        if not any(c.strip() for c in r[1:]):
            continue        # a level the page prints with every cell blank
        steps = [number(r[i]) for i in step if r[i].strip()]
        rows.append((int(r[0]), steps[0] if steps else None,
                     {grade[i]: number(c) for i, c in enumerate(r) if i in grade and c.strip()}))
    return rates, rows


def published_tables():
    """(file, document, key, the L4's block) for every `a published table`
    whose @ref names exactly one corpus table."""
    out = []
    for doc in site_mod.DOCUMENTS:
        if not doc.startswith("tables/"):
            continue
        for sec in akn.sections(doc):
            path = site_mod.l4_path(doc, sec.num)
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            for m in re.finditer(r"@ref ([^\n]*)\n`[^`]+` MEANS\n( +`a published table` [^\n]*\n(?: {5,}[^\n]*\n)*)", text):
                tables = [k.removeprefix("akn:") for k in m.group(1).split() if re.search(r"/t\d+$", k)]
                if len(tables) == 1:
                    out.append((path.relative_to(ROOT), doc, tables[0], m.group(2)))
    return out


class PublishedTablesAreTheCorpusCells(unittest.TestCase):
    def test_every_cell_step_and_rate_is_the_corpus_tables_by_position(self):
        tables = published_tables()
        checked = 0
        for path, doc, key, block in tables:
            rows = {r.key: r for sec in akn.sections(doc) for r in sec.rows}
            with self.subTest(file=str(path), table=key):
                self.assertIn(key, rows)
                mine = l4_table(block)
                self.assertTrue(mine[1], "no rows read off the L4 block")
                self.assertEqual(mine, corpus_table(rows[key].cells))
                checked += 1
        self.assertEqual(checked, CHECKED, [f"{p}:{k}" for p, _, k, _ in tables])


if __name__ == "__main__":
    unittest.main()
