"""The root and the collections' roots (MMS-521, tools/roots.py).

The root is the law's one entry point: its gate (`unresolved contradictions`)
is an #ASSERT the build already holds. What is held here is what the site
says about it — that every root has its page, that a collection root names
only instruments that are modules, and that the root's page shows every
resolution the module reports, read from the module and not typed.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import modules  # noqa: E402
import roots  # noqa: E402

SITE = ROOT / "build" / "site"


@unittest.skipUnless(roots.current(), "the roots' results are not current: `make roots`")
class Roots(unittest.TestCase):
    def test_every_root_is_a_module(self):
        names = modules.wanted()[0]
        for module, *_ in roots.ROOTS:
            with self.subTest(module=module):
                self.assertIn(module, names)

    def test_a_collection_root_registers_only_modules(self):
        names = modules.wanted()[0]
        for module, _, coll, *_ in roots.ROOTS:
            if not coll:
                continue
            reg = roots.registered(module)
            self.assertTrue(reg, f"{module} registers no instrument")
            for m, title in reg:
                with self.subTest(root=module, instrument=m):
                    self.assertIn(m, names)
                    self.assertTrue(title.strip())

    def test_the_gate_is_empty_and_the_report_is_whole(self):
        self.assertEqual(roots.evaluated("root", "`unresolved contradictions`"), "EMPTY")
        lines = roots.strings(roots.evaluated("root", "`the resolutions report`"))
        self.assertEqual(str(len(lines)), roots.evaluated("root", "count `the resolutions`"),
                         "a resolution the report leaves out")
        for line in lines:
            self.assertEqual(len(line.split(" | ")), 5, line)
            self.assertGreater(int(line.split(" | ")[4]), 0, f"a resolution that settles no case: {line}")

    @unittest.skipUnless((SITE / "root.html").exists(), "run `make site` first")
    def test_every_root_has_its_page_and_the_root_shows_every_resolution(self):
        for _, here, *_ in roots.ROOTS:
            with self.subTest(page=here):
                self.assertTrue((SITE / here).exists())
        page = (SITE / "root.html").read_text(encoding="utf-8")
        for line in roots.strings(roots.evaluated("root", "`the resolutions report`")):
            rule = line.split(" | ")[3]
            with self.subTest(rule=rule):
                self.assertIn(rule, page)


class TestsAreQuestions(unittest.TestCase):
    """A root's page shows its tests as questions with what the compiler
    answered, not as a dump of source (the client, 2026-10-22, MMS-553)."""

    def test_every_directive_is_in_a_question_with_its_answer(self):
        import re
        for module, *_ in roots.ROOTS:
            src = roots.tests_of(module)
            if not src.exists():
                continue
            lines = [n for n, l in enumerate(src.read_text(encoding="utf-8").splitlines(), 1)
                     if roots.DIRECTIVE.match(l.strip())]
            asked = [n for _, qs in roots.test_questions(module) for _, ds in qs for n, *_ in ds]
            with self.subTest(module=module):
                self.assertEqual(asked, lines)
                answered = {int(m.group(1)) for r in roots.results(module)
                            if (m := re.search(r":(\d+):", r.get("range", "")))}
                if answered:   # `make l4` has run
                    self.assertEqual(set(lines) - answered, set(), "a test the page shows with no answer")

    def test_a_continued_directive_is_one_expression(self):
        qs = [d for _, q in roots.test_questions("root") for _, ds in q for d in ds]
        self.assertTrue(any("EQUALS" in expr and expr.startswith("((") for _, _, expr in qs))
        self.assertFalse([expr for _, _, expr in qs if expr.count("(") != expr.count(")")])


if __name__ == "__main__":
    unittest.main()
