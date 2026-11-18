"""Cliffs are a kind of finding (the client, 2026-11-18, MMS-780: "can you
add a new class of cliff findings?", then "only reversals are
interesting"): a threshold at which one unit more of an input that earns
more lowers the pay. A cliff names both sides, so each carries a `trace`
with at least the two results one unit apart, and one no outcome turns on
is refused, as an edge case is."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_site  # noqa: E402

FINDINGS = build_site.load_findings()


class Cliffs(unittest.TestCase):
    def test_cliff_is_a_kind_with_a_label_and_a_style(self):
        self.assertIn("cliff", build_site.KINDS)
        css = (ROOT / "tools" / "assets" / "site.css").read_text(encoding="utf-8")
        self.assertIn(".kind-tag.cliff", css)

    def test_every_cliff_traces_both_sides_of_its_step(self):
        cliffs = [f for f in FINDINGS if f["kind"] == "cliff"]
        self.assertTrue(cliffs)
        for f in cliffs:
            with self.subTest(finding=f["id"]):
                self.assertGreaterEqual(len(f.get("trace") or []), 2,
                                        "a cliff shows the result on both sides of the threshold")

    def test_a_cliff_is_a_finding_only_when_something_turns_on_it(self):
        for f in FINDINGS:
            if f["kind"] == "cliff":
                with self.subTest(finding=f["id"]):
                    self.assertNotEqual(f["severity"], "low")


if __name__ == "__main__":
    unittest.main()
