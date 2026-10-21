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
SIDES = [(c, s) for c in DATA["items"] for s in c["sides"]]
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
            if s["doc"] in NOT_VENDORED:
                continue
            with self.subTest(item=c["id"], key=s["key"]):
                self.assertIn(" ".join(s["quote"].split()), row_text(s["doc"], s["key"]))

    def test_the_documents_outside_the_snapshot_are_the_listed_ones(self):
        absent = {s["doc"] for _, s in SIDES if not (ROOT / "corpus" / "akn" / s["doc"]).exists()}
        self.assertEqual(absent, NOT_VENDORED)

    def test_a_rule_quoted_from_the_corpus_is_its_row(self):
        for rid, r in DATA["rules"].items():
            if r.get("doc"):
                with self.subTest(rule=rid):
                    self.assertIn(" ".join(r["quote"].split()), row_text(r["doc"], r["key"]))

    def test_two_or_more_sides_each_its_own_document(self):
        """A contradiction between documents has a side per document that
        gives its own answer — two, or three or more where that many sources
        disagree (the client, 2026-10-21, MMS-521) — and no document twice;
        one between a document and what is paid has the document alone (the
        payment is a payslip's or the simulator's, and no picture of it is
        published)."""
        for c in DATA["items"]:
            with self.subTest(item=c["id"]):
                if c["group"] == "payment":
                    self.assertEqual(len(c["sides"]), 1)
                    self.assertIn("no", {v["followed"] for v in c["practice"].values()})
                    continue
                self.assertGreaterEqual(len(c["sides"]), 2)
                docs = [s.get("doc") or s["label"] for s in c["sides"]]
                self.assertEqual(len(docs), len(set(docs)))


class EveryCropIsItsFile(unittest.TestCase):

    def test_each_crop_exists_at_the_size_the_data_says(self):
        imgs = [i for _, s in SIDES for i in s["images"]] + [
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
            with self.subTest(item=c["id"]):
                self.assertTrue(s["images"])

    def test_no_file_in_the_folder_is_unused(self):
        used = set(contradictions.crops(DATA))
        self.assertEqual({p.name for p in contradictions.CROPS.glob("*.png")}, used)


class TheVerdicts(unittest.TestCase):

    def test_a_simulator_link_names_a_cause_the_delta_page_has(self):
        delta = json.loads((ROOT / "data" / "calculator-delta.json").read_text(encoding="utf-8"))
        causes = {c["id"] for c in delta["causes"]}
        for c in DATA["items"]:
            if c.get("delta"):
                with self.subTest(item=c["id"]):
                    self.assertIn(c["delta"], causes)

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

    def test_an_error_is_graded_and_says_why(self):
        for c in DATA["items"]:
            with self.subTest(item=c["id"]):
                p = c["practice"]
                # the payslips and the simulator are separate evidence
                self.assertEqual(set(p), {src for src, _ in contradictions.SOURCES})
                for v in p.values():
                    self.assertIn(v["followed"], contradictions.FOLLOWED)
                    self.assertTrue(v["text"].strip())
                if any(v["followed"] in ("no", "partly") for v in p.values()):
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
        c = copy.deepcopy(next(c for c in DATA["items"] if c["group"] != "payment"))
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
        # one filter row per source, and one by the kinds of document
        self.assertEqual(html.count('class="cx-frow" role="group"'), 3)
        for c in DATA["items"]:
            self.assertIn(f'data-types="{" ".join(contradictions.types(c))}"', html)


if __name__ == "__main__":
    unittest.main()
