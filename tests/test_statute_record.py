"""The per-instrument record of the protective statutes (MMS-601).

tools/statute_record.py reads, for every document of corpus/manifest.json and
every statute the statutes' root registers, whether the instrument meets the
statute's floor, falls short of it, was set aside (and why), or was never
checked. The record is read off the source, never written by hand; these
tests hold it to the source: every document of the manifest has a row, every
shortfall card and every #ASSERT that reads a statute is in it, and every
reason it gives for setting an instrument aside is one the source states.
"""
from __future__ import annotations

import json
import sys
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import statute_record as R  # noqa: E402

REC = R.build()
STATUTES = [s["module"] for s in REC["statutes"]]


def evidence(kind: str):
    """Every evidence item of a kind, with the unit and statute it is under."""
    for row, sec, cells in R.units(REC):
        for mod, c in cells.items():
            for e in c.get("evidence", []):
                if e["kind"] == kind:
                    yield row["doc"], sec, mod, c, e


def instrument_files() -> list[Path]:
    """Every L4 file an instrument's verdict could live in: not a statute,
    not the shared library and not a root's tests, and not a link."""
    out = []
    for p in sorted((ROOT / "l4").rglob("*.l4")):
        if p.is_symlink() or p.parent == R.L4 / "modules":
            continue
        rel = p.relative_to(R.L4).parts
        if rel[0] in ("laws", "lib"):
            continue
        if rel[0] == "tests" and R.tested_file(p) is not None and R.tested_file(p).parent == R.L4 / "lib":
            continue
        out.append(p)
    return out


class EveryDocumentHasARow(unittest.TestCase):

    def test_the_denominator_is_the_manifest(self):
        self.assertEqual([r["doc"] for r in REC["rows"]], [d["path"] for d in R.manifest()])

    def test_every_statute_the_root_registers_is_a_column(self):
        text = R.STATUTES_ROOT.read_text(encoding="utf-8")
        for m in STATUTES:
            self.assertIn(f'IS "{m}"', text)
        for r in REC["rows"]:
            with self.subTest(doc=r["doc"]):
                self.assertEqual(sorted(r["cells"]), sorted(STATUTES))
                for _, _, cells in R.units({"rows": [r], "statutes": REC["statutes"]}):
                    self.assertEqual(sorted(cells), sorted(STATUTES))

    def test_every_verdict_is_one_of_four(self):
        for row, sec, cells in R.units(REC):
            for mod, c in cells.items():
                self.assertIn(c["verdict"], R.VERDICTS, (row["doc"], sec, mod))
                if c["verdict"] == "not-weighed":
                    # a reason: the source's, or nothing on the subject
                    self.assertTrue(c.get("off_subject") or any(e["kind"] in ("marker", "data")
                                                                for e in c["evidence"]), (row["doc"], sec, mod))

    def test_every_statute_has_its_inventory(self):
        """What the batch searched the corpus for: the reason an instrument
        with none of it is recorded as having nothing on the subject."""
        for s in R.statutes():
            with self.subTest(statute=s["module"]):
                self.assertTrue(s["inventory"].get("terms"))
                self.assertTrue(s["inventory"].get("batch"))


class EveryShortfallIsInIt(unittest.TestCase):

    def test_every_statute_floor_card(self):
        cards = [c for c in json.loads(R.CARDS.read_text(encoding="utf-8"))["items"]
                 if c.get("rule") == "statute-floor"]
        self.assertTrue(cards)
        seen = {(e["card"], mod) for doc, sec, mod, c, e in evidence("card")}
        for c in cards:
            law = next(s for s in c["sides"] if s.get("type") == "law")["law"]
            with self.subTest(card=c["id"]):
                self.assertIn((c["id"], law), seen)
        for doc, sec, mod, c, e in evidence("card"):
            self.assertEqual(c["verdict"], "shortfall")

    def test_a_card_side_is_its_unit(self):
        """A card's instrument side lands on the document (and section) it
        names, never on a sectioned document's row without a section."""
        for doc, sec, mod, c, e in evidence("card"):
            with self.subTest(card=e["card"]):
                row = next(r for r in REC["rows"] if r["doc"] == doc)
                self.assertTrue(sec is None or sec in {u["section"] for u in row.get("sections", [])})
                if "sections" in row:
                    self.assertTrue(sec)


class EveryStatuteFloorAssertionIsInIt(unittest.TestCase):

    def test_every_assert_that_reads_a_statute(self):
        """An #ASSERT in an instrument's file (or its module's tests file)
        that reads a protective statute is in the record, at its line: none
        sits in a file the record does not reach."""
        recorded = {(e["file"], e["line"]) for *_, e in evidence("assert")}
        found = 0
        for p in instrument_files():
            src = R.parse(p)
            for line, text in src["asserts"]:
                if R.reads(p, text):
                    found += 1
                    with self.subTest(file=str(p.relative_to(ROOT)), line=line):
                        self.assertIn((str(p.relative_to(ROOT)), line), recorded)
        self.assertTrue(found)

    @unittest.skipUnless((R.BUILD_L4).exists(), "run `make l4` first")
    def test_every_one_holds(self):
        """`make l4` recorded each as satisfied: a "meets" is only as good as
        the check that says so."""
        for doc, sec, mod, c, e in evidence("assert"):
            with self.subTest(file=e["file"], line=e["line"]):
                self.assertIs(e["held"], True)

    def test_a_finding_s_assert_is_a_shortfall(self):
        """An #ASSERT that is a finding's evidence shows a defect, never that
        the instrument meets the floor."""
        for doc, sec, mod, c, e in evidence("assert"):
            if e.get("finding"):
                self.assertEqual(e["verdict"], "shortfall")
                self.assertEqual(c["verdict"], "shortfall")

    def test_the_closure_reaches_through_an_imported_rule(self):
        """The Oz LaTmura agreement's §24 asks §46's rule, which asks the
        Severance Pay Law's §14: it reads the law."""
        p = R.L4 / "agreements/oz-latmura/2011-08-14_oz-latmura_founding-agreement/oz-founding-24.l4"
        hits = set().union(*(R.reads(p, t) for _, t in R.parse(p)["asserts"]))
        self.assertIn("severance-pay-law", hits)

    def test_a_name_alone_does_not_read_a_statute(self):
        """An assertion named after a statute that computes nothing from it
        is not a verdict on it: the name is no marker."""
        self.assertEqual(R.reads(R.L4 / "circulars/2011-12_tashab_03.l4", "#ASSERT `the Women's Work Law`"), set())


class EverySetAsideSaysWhy(unittest.TestCase):

    def test_a_marker_names_a_registered_statute(self):
        names = {s["name"] for s in R.statutes()}
        n = 0
        for p in instrument_files():
            for line, name, why in R.parse(p)["marks"]:
                n += 1
                with self.subTest(file=str(p.relative_to(ROOT)), line=line):
                    self.assertIn(name, names)
                    self.assertTrue(why)
        self.assertTrue(n)

    def test_every_marker_is_in_it(self):
        recorded = {(e["file"], e["line"]) for *_, e in evidence("marker")}
        for p in instrument_files():
            for line, name, why in R.parse(p)["marks"]:
                with self.subTest(file=str(p.relative_to(ROOT)), line=line):
                    self.assertIn((str(p.relative_to(ROOT)), line), recorded)

    def test_the_data_file_holds_only_what_no_code_can(self):
        """A reason lives in data/statute-set-aside.toml only for a document
        with no L4 to carry it."""
        rows = tomllib.loads(R.SET_ASIDE.read_text(encoding="utf-8")).get("set_aside", [])
        docs = {d["path"] for d in R.manifest()}
        names = {s["name"] for s in R.statutes()}
        for a in rows:
            with self.subTest(doc=a["doc"]):
                self.assertIn(a["doc"], docs)
                self.assertIn(a["statute"], names)
                self.assertEqual(R.unit_files(a["doc"]), {})
                self.assertTrue(a["why"].strip())


if __name__ == "__main__":
    unittest.main()
