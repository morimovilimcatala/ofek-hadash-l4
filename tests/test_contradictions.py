"""The contradictions page (contradictions.html, MMS-515) and its data.

Every side of a contradiction quotes the corpus verbatim at the row it names,
every crop it shows is a picture file of the size the data says, every
finding it names is in the register, and every contradiction whose rule was
not followed -- an error -- carries a severity grade and the reason for it.
"""
from __future__ import annotations

import json
import struct
import sys
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import akn             # noqa: E402
import contradictions  # noqa: E402

DATA = json.loads(contradictions.DATA.read_text(encoding="utf-8"))
# the sides that are documents: quoted from the corpus and pictured. A side
# that says what is PAID (a payslip, the simulator) is neither.
SIDES = [(c, s) for c in DATA["items"] for s in c["sides"]
         if s["type"] not in contradictions.PAYING]
PAYING = [(c, s) for c in DATA["items"] for s in c["sides"]
          if s["type"] in contradictions.PAYING]
# documents the corpus published after the vendored snapshot (corpus/SOURCE.toml);
# a re-sync that brings them in empties this set, and the test says so
NOT_VENDORED = {"letters/2016-07-10_mof-director-general_nesia-reform-letter.xml"}


def row_text(doc: str, key: str) -> str:
    for s in akn.sections(doc):
        for r in s.rows:
            if r.key == key or key in r.aliases:
                return " ".join(r.text.split())
    raise KeyError((doc, key))


def png_size(path: Path) -> tuple[int, int]:
    head = path.read_bytes()[:24]
    assert head[:8] == b"\x89PNG\r\n\x1a\n", path
    return struct.unpack(">II", head[16:24])


class EverySideQuotesTheCorpus(unittest.TestCase):

    def test_the_quote_is_the_row_it_names(self):
        for c, s in SIDES:
            if s.get("law"):
                continue  # quoted from the pinned statute: the next test
            if s["doc"] in NOT_VENDORED:
                continue
            with self.subTest(item=c["id"], key=s["key"]):
                self.assertIn(" ".join(s["quote"].split()), row_text(s["doc"], s["key"]))

    def test_a_statute_is_quoted_from_its_pinned_text(self):
        """A statute side (the corpus holds no copy of a statute) quotes the
        section as laws/<name>.toml pins it."""
        import laws
        for c, s in SIDES:
            if not s.get("law"):
                continue
            with self.subTest(item=c["id"], law=s["law"]):
                sec = next(x for x in laws.load(s["law"])["section"] if x["num"] == s["section"])
                self.assertIn(" ".join(s["quote"].split()), " ".join(sec["text"].split()))

    def test_the_documents_outside_the_snapshot_are_the_listed_ones(self):
        absent = {s["doc"] for _, s in SIDES
                  if not s.get("law") and not (ROOT / "corpus" / "akn" / s["doc"]).exists()}
        self.assertEqual(absent, NOT_VENDORED)

    def test_a_rule_quoted_from_the_corpus_is_its_row(self):
        for rid, r in DATA["rules"].items():
            if r.get("doc"):
                with self.subTest(rule=rid):
                    self.assertIn(" ".join(r["quote"].split()), row_text(r["doc"], r["key"]))

    def test_two_or_more_sides_each_its_own_document(self):
        """A contradiction has a side per source that gives its own answer —
        two, or three or more where that many sources disagree (the client,
        2026-10-21, MMS-521) — and no source twice. What is paid is a source
        too (the payslips, the simulator: "in general remove the קוים chips,
        since payslips are also a source"), so a document against its
        payment has two sides; at least one side is a document."""
        for c in DATA["items"]:
            with self.subTest(item=c["id"]):
                self.assertGreaterEqual(len(c["sides"]), 2)
                docs = [s.get("doc") or s["label"] for s in c["sides"]]
                self.assertEqual(len(docs), len(set(docs)))
                self.assertTrue(any(s["type"] not in contradictions.PAYING for s in c["sides"]))


class TheRootDecides(unittest.TestCase):
    """A card about an item the root asks (MMS-521) names it, and the
    page shows what the root decides on it, from the root's own report."""

    def test_a_cards_root_item_is_one_the_root_decides(self):
        import roots
        if not roots.current():
            self.skipTest("the roots' results are not current: `make roots`")
        decided = roots.rulings()
        named = [c for c in DATA["items"] if c.get("root_item")]
        self.assertTrue(named)
        for c in named:
            with self.subTest(item=c["id"]):
                self.assertIn(c["root_item"], decided)


class EveryCropIsItsFile(unittest.TestCase):

    def test_each_crop_exists_at_the_size_the_data_says(self):
        imgs = [i for _, s in SIDES for i in s.get("images", [])] + [
            r["image"] for r in DATA["rules"].values() if r.get("image")]
        self.assertTrue(imgs)
        for i in imgs:
            with self.subTest(file=i["file"]):
                self.assertEqual(list(png_size(contradictions.CROPS / i["file"])), i["size"])
                self.assertIn(i["kind"], contradictions.KIND)
                for m in i["marks"]:
                    self.assertTrue(0 <= m[0] < m[2] <= 1 and 0 <= m[1] < m[3] <= 1.01, m)

    def test_every_side_has_a_picture(self):
        for c, s in SIDES:
            if s.get("law"):
                continue  # a statute's words are its pinned text, linked to its page
            with self.subTest(item=c["id"]):
                self.assertTrue(s["images"])

    def test_no_file_in_the_folder_is_unused(self):
        used = set(contradictions.crops(DATA))
        self.assertEqual({p.name for p in contradictions.CROPS.glob("*.png")}, used)


class TheVerdicts(unittest.TestCase):

    def test_a_simulator_link_names_a_cause_the_simulator_group_has(self):
        delta = json.loads((ROOT / "data" / "calculator-delta.json").read_text(encoding="utf-8"))
        causes = {c["id"] for c in delta["causes"]}
        for c, s in PAYING:
            if s.get("delta"):
                with self.subTest(item=c["id"]):
                    self.assertEqual(s["type"], "simulator")
                    self.assertIn(s["delta"], causes)

    def test_a_paying_source_says_what_is_paid_and_whether_it_is_the_rule(self):
        for c, s in PAYING:
            with self.subTest(item=c["id"], source=s["type"]):
                self.assertTrue(s["says"].strip())
                self.assertIsInstance(s["agrees"], bool)
                self.assertNotIn("images", s)    # no page of a payslip is published

    def test_findings_and_rules_exist(self):
        ids = set()
        for f in (ROOT / "findings").rglob("*.toml"):
            ids |= {x["id"] for x in tomllib.loads(f.read_text(encoding="utf-8")).get("finding", [])}
        for c in DATA["items"]:
            with self.subTest(item=c["id"]):
                self.assertIn(c["rule"], DATA["rules"])
                self.assertIn(c["group"], {g["id"] for g in DATA["groups"]})
                for f in c.get("findings", []):
                    self.assertIn(f, ids)

    def test_a_weaker_source_departing_from_a_stronger_one_lives_on_its_card(self):
        """The client, 2026-10-22: "a weaker one departing from a stronger
        one has its own page, סתירה in finding means equal power". Every
        finding a weaker-against-stronger card cites is that card's, and the
        findings page leaves it out; two circulars stay findings."""
        homes = contradictions.homes(DATA)
        self.assertTrue(homes)
        groups = {c["id"]: c["group"] for c in DATA["items"]}
        for fid, cid in homes.items():
            self.assertIn(groups[cid], contradictions.CROSS_RANK)
        self.assertNotIn("circulars", contradictions.CROSS_RANK)
        self.assertNotIn("payment", contradictions.CROSS_RANK)
        import build_site
        page = (build_site.OUT / "findings.html")
        if page.exists():  # after `make site`
            html = page.read_text(encoding="utf-8")
            for fid in homes:
                with self.subTest(finding=fid):
                    self.assertNotIn(f'id="{fid}"', html)

    def test_an_error_is_graded_and_says_why(self):
        """An error is a card in which a paying source departs from what the
        governing rule gives; it, and only it, is graded."""
        errs = {c["id"] for c in contradictions.errors(DATA)}
        for c in DATA["items"]:
            with self.subTest(item=c["id"]):
                self.assertNotIn("practice", c)
                if c["id"] in errs:
                    self.assertIn(c.get("severity"), contradictions.SEV)
                    self.assertTrue(c.get("severity_why", "").strip())
                    # and says what it means for a teacher
                    self.assertTrue(c.get("meaning", "").strip())
                else:
                    self.assertNotIn("severity", c)

    def test_a_card_shows_every_side_when_three_disagree(self):
        """Three sources that give three answers are one contradiction with
        three sides, not three pairs (the client, 2026-10-21)."""
        import copy
        c = copy.deepcopy(next(c for c in DATA["items"] if len(c["sides"]) == 2
                               and not any(s["type"] in contradictions.PAYING for s in c["sides"])))
        third = copy.deepcopy(c["sides"][0])
        third.update(label="מסמך שלישי", type="takanon", images=[])
        c["sides"].append(third)
        html = contradictions.card(c, DATA["rules"], prose=lambda t: t,
                                   clause_link=lambda d, k: ("#", k), finding_ids=set(),
                                   src=lambda f: f)
        self.assertEqual(html.count('<div class="cx-side">'), 3)
        self.assertEqual(html.count(" ↔ "), 2)
        self.assertIn("מסמך שלישי", html)

    def test_the_page_outlines_the_words_and_shows_the_meter(self):
        html, _ = contradictions.body(DATA, prose=lambda t: t,
                                      clause_link=lambda d, k: ("#", k), finding_ids=set(),
                                      src=lambda f: f)
        # collapsed by default (the client, 2026-10-20)
        self.assertEqual(html.count('<details class="cx-card'), len(DATA["items"]))
        self.assertNotIn(' open>', html)
        self.assertIn('class="cx-meter"', html)
        self.assertIn('class="cx-mark"', html)
        self.assertEqual(html.count("<h4>מי גובר?</h4>"), len(DATA["items"]))
        # one filter row, by the kinds of source: no "was it followed" row,
        # since what is paid is a source (the client, 2026-10-21)
        self.assertEqual(html.count('class="cx-frow" role="group"'), 1)
        self.assertNotIn("קוים", html)
        for c in DATA["items"]:
            self.assertIn(f'data-types="{" ".join(contradictions.types(c))}"', html)


if __name__ == "__main__":
    unittest.main()


class EveryContradictionIsAsserted(unittest.TestCase):
    """The client, 2026-10-21 (MMS-533): "Every document contradiction should
    have an ASSERT". Each card rests on at least one L4 boolean — its
    findings' evidence or its own `asserts` — defined in its file and
    #ASSERTed there."""

    def test_every_card_names_an_asserted_boolean(self):
        import tomllib
        evidence = {}
        for f in (ROOT / "findings").rglob("*.toml"):
            for x in tomllib.loads(f.read_text(encoding="utf-8")).get("finding", []):
                if x.get("l4") and x.get("evidence"):
                    evidence[x["id"]] = (x["l4"], x["evidence"].strip("`"))
        for c in DATA["items"]:
            with self.subTest(card=c["id"]):
                found = contradictions.proofs(c, evidence)
                self.assertTrue(found, "no L4 boolean proves this contradiction")
                for file, name in found:
                    text = (ROOT / file).read_text(encoding="utf-8")
                    self.assertIn(f"#ASSERT `{name}`", text, f"{file} does not #ASSERT `{name}`")
