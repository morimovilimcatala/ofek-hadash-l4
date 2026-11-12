"""The ministry's simulator described in L4 (MMS-523): l4/simulator/, its
tests file, and data/simulator-validation.json, which tools/simulator_check.py
writes by running the module on every recorded request of the private
extraction (MMS-512).

The module describes what the simulator computes and never the law, so no
rule of ours may import it: only its own tests file does. The validation
file holds counts and the residual lines, not the recording.
"""
from __future__ import annotations

import json
import re
import sys
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import simulator_check  # noqa: E402

SIM = ROOT / "l4" / "simulator"
DATA = json.loads(simulator_check.OUT.read_text(encoding="utf-8"))
IMPORT_RE = re.compile(r"^IMPORT\s+`?([^`\n]+?)`?\s*$", re.M)
# the recorded response's own keys, and the request's envelope
RAW_KEYS = {"Semel", "Scum", "Teur", "AhuzKamoot", "payload", "lines", "status", "key", "calc"}


def keys(o):
    if isinstance(o, dict):
        for k, v in o.items():
            yield k
            yield from keys(v)
    elif isinstance(o, list):
        for v in o:
            yield from keys(v)


class NoRuleOfOursImportsIt(unittest.TestCase):
    def test_only_its_tests_file_imports_a_simulator_module(self):
        names = {f.name.removesuffix(".l4") for f in SIM.glob("*.l4")}
        self.assertEqual(names, {"educalc-ofek-hadash"})
        importers = sorted(
            str(f.relative_to(ROOT)) for f in (ROOT / "l4").rglob("*.l4")
            if not f.is_symlink() and f.parent != SIM
            and names & set(IMPORT_RE.findall(f.read_text(encoding="utf-8"))))
        self.assertEqual(importers, ["l4/tests/educalc-ofek-hadash-tests.l4"])

    def test_it_says_on_its_face_that_it_is_the_simulator_not_the_law(self):
        head = (SIM / "educalc-ofek-hadash.l4").read_text(encoding="utf-8")[:600]
        self.assertIn("THE MINISTRY'S SIMULATOR, NOT THE LAW", head)


class TheValidationRecord(unittest.TestCase):
    def test_it_counts_every_recorded_request(self):
        # the extraction holds 6,260 Ofek Hadash responses for 2026-09
        self.assertEqual(DATA["requests"], 6260)
        self.assertEqual(DATA["module"], "l4/simulator/educalc-ofek-hadash.l4")

    def test_the_residuals_are_the_lines_the_counts_miss(self):
        missed = sum(c["lines"] - c["exact"] for c in DATA["codes"].values())
        self.assertEqual(missed, len(DATA["residuals"]))
        for r in DATA["residuals"]:
            a, b = Decimal(r["simulator"]), Decimal(r["l4"])
            self.assertNotEqual(a, b)
            self.assertEqual(Decimal(r["difference"]), b - a)
            self.assertEqual(r["kind"], "one agora" if abs(b - a) == Decimal("0.01") else "more")
            self.assertTrue(set(r["inputs"]) <= set(simulator_check.FIELDS))

    def test_requests_reproduced_is_exact(self):
        # a ratchet, exact (the corpus repo's MMS-165 rule): a rule that
        # reproduces more lines lowers the residuals and must say so here
        self.assertEqual(DATA["requests_reproduced"], REPRODUCED)
        self.assertEqual(len(DATA["residuals"]), RESIDUALS)

    def test_it_holds_no_recorded_response(self):
        self.assertFalse(RAW_KEYS & set(keys(DATA)))


# What tools/simulator_check.py measured over the recording (MMS-523).
REPRODUCED = None
RESIDUALS = None


if __name__ == "__main__":
    unittest.main()
