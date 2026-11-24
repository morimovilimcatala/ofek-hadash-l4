"""What the compiler accepts and a reader cannot see: the layout lint, the
undated obligations, a typed count of days against the Hours Law.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import subprocess
import tempfile
import tomllib
import unicodedata
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import akn      # noqa: E402
import l4src    # noqa: E402
import build_site as site_mod  # noqa: E402


class Layout(unittest.TestCase):
    def test_no_continuation_line_regroups_arithmetic(self):
        # a line that begins with an operator takes the rest of the line as
        # its right operand (tools/layout_lint.py); one operand per line
        import layout_lint
        found = [f"{f.relative_to(ROOT)}:{n} {kind}: {t}"
                 for f in sorted((ROOT / "l4").rglob("*.l4"))
                 for n, kind, t in layout_lint.scan(f)]
        self.assertEqual(found, [])

    def test_no_not_runs_on_into_and_or(self):
        # `IF NOT a AND b` is NOT (a AND b) (tools/layout_lint.py's scan_not);
        # it was the tool's alone until a new agreement shipped one
        import layout_lint
        found = [f"{f.relative_to(ROOT)}:{n}: {t}"
                 for f in sorted((ROOT / "l4").rglob("*.l4")) if not f.is_symlink()
                 for n, _, t in layout_lint.scan_not(f)]
        self.assertEqual(found, [])

    def test_no_bare_percentage_is_a_functions_argument(self):
        # `x \`increased by\` 12.5%` computes (x \`increased by\` 12.5)% at
        # the pinned compiler (MMS-510): the argument is written (12.5%)
        import layout_lint
        found = [f"{f.relative_to(ROOT)}:{n}: {t}"
                 for f in sorted((ROOT / "l4").rglob("*.l4")) if not f.is_symlink()
                 for n, _, t in layout_lint.scan_pct(f)]
        self.assertEqual(found, [])

    def test_the_percentage_check_sees_every_shape_that_computes_wrong(self):
        # each of these computed 3.24 for 24 instead of 27 (MMS-510), and
        # each of the second list computes right and is not refused
        import layout_lint
        import tempfile
        wrong = ["    x `increased by` 12.5%",
                 "`h` x MEANS x `inc by` 12.5% PLUS 0",
                 "    IF x EQUALS 24 THEN x `inc by` 12.5% ELSE 0",
                 "`q` x MEANS `grow` x 12.5%",
                 "`r` MEANS `the amount` `inc by` 12.5%",
                 "    `grow` x\n        12.5%"]
        right = ["    x `increased by` (12.5%)",
                 "    x PLUS 12.5%",
                 "    x DIVIDED BY 12.5%",
                 "`rate` MEANS 12.5%",
                 "    IF x AT LEAST 50% THEN 1 ELSE 0",
                 '    BECAUSE "beyond 140%" -- above 150%',
                 "`a teacher at 40%` MEANS 1"]
        for text, n in [(t, 1) for t in wrong] + [(t, 0) for t in right]:
            with self.subTest(text=text), tempfile.TemporaryDirectory() as d:
                f = Path(d) / "x.l4"
                f.write_text(text + "\n", encoding="utf-8")
                self.assertEqual(len(list(layout_lint.scan_pct(f))), n)


# `MUST … LEST` with no WITHIN and no BEFORE (tools/deadlines.py): the
# breach the rule names is never reached. What is left is where the text
# ties the time to an event with no length, holds a lead time before an
# event in a PROVIDED, or names no time at all (MMS-765). Raising it is a
# deadline lost; it is lowered by the commit that gives one a WITHIN.
UNDATED_OBLIGATIONS = 323


class Deadlines(unittest.TestCase):
    def test_undated_obligations_are_a_ratchet(self):
        import deadlines
        self.assertEqual(len(deadlines.sites()), UNDATED_OBLIGATIONS)

    def test_the_count_reads_a_clause_as_the_compiler_groups_it(self):
        # each text's MUST clauses, in order: (has a deadline, has a LEST)
        import deadlines
        cases = {
            "    PARTY a\n    MUST  b\n    LEST  BREACH BY a\n": [(False, True)],
            "    PARTY a\n    MUST  b\n    WITHIN 3\n    LEST  BREACH BY a\n": [(True, True)],
            "    PARTY a MUST b BEFORE 3 LEST BREACH BY a\n": [(True, True)],
            "    PARTY a\n    MUST  b\n": [(False, False)],
            # an inner clause under HENCE, in brackets and not
            "    PARTY a\n    MUST  b\n    HENCE (PARTY c MUST d WITHIN 2 LEST BREACH BY c)\n"
            "    LEST  BREACH BY a\n": [(False, True), (True, True)],
            "    PARTY a\n    MUST  b\n    WITHIN 1\n    HENCE PARTY c\n          MUST  d\n"
            "          LEST  BREACH BY c\n    LEST  BREACH BY a\n": [(True, True), (False, True)],
            # side by side
            "         (PARTY a MUST b)\n    RAND (PARTY c MUST d LEST BREACH BY c)\n": [(False, False), (False, True)],
            # a keyword in a string or a comment is no keyword
            '    PARTY a\n    MUST  b -- WITHIN 3\n    LEST  BREACH BY a BECAUSE "WITHIN 3"\n': [(False, True)],
        }
        for text, want in cases.items():
            with self.subTest(text=text):
                self.assertEqual([(due, lest) for _, due, lest in deadlines.clauses(text)], want)


class AWeekAgainstTheHoursLawCountsNamedDays(unittest.TestCase):
    """A week weighed against the Hours of Work and Rest Law is computed from
    the instrument's own days, or from a named input, never from a typed
    count (MMS-676). F-oz-founding-14-a took §20's breaks from `6 TIMES` a
    day while the Oz agreement's §9(ד), encoded and imported one line up,
    gives the teacher a free day: no Oz teacher works six days, and the
    finding was withdrawn. A definition that reads the law's week or its
    break may not multiply a bare number into it."""

    LAW = ("the longest working week section 3 allows",
           "the least break section 20 asks")
    TYPED = re.compile(r"(?<![\w`.])\d+(?:\.\d+)? TIMES ")

    def test_no_typed_count_of_days_or_hours(self):
        found, read = [], 0
        for f in sorted((ROOT / "l4").rglob("*.l4")):
            if f.is_symlink():
                continue
            for block in re.split(r"\n\s*\n", f.read_text(encoding="utf-8")):
                code = "\n".join(line for line in block.splitlines()
                                 if not line.lstrip().startswith("--"))
                if not any(name in code for name in self.LAW):
                    continue
                read += 1
                for hit in self.TYPED.finditer(code):
                    found.append((f.relative_to(ROOT).as_posix(), hit.group(0)))
        self.assertEqual(found, [])
        # A check that reads nothing refuses nothing: the definitions that
        # weigh a week or a day's break against the law are there to read.
        self.assertGreater(read, 5)


if __name__ == "__main__":
    unittest.main()
