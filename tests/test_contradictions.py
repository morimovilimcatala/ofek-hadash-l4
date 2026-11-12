"""The contradictions page (contradictions.html, MMS-515) and its data.

Every side of a contradiction quotes the corpus verbatim at the row it names,
every crop it shows is a picture file of the size the data says, every
finding it names is in the register, and every contradiction -- hand-written
or generated from the root -- carries a severity grade and the reason for it
(MMS-703); an error, a card whose paying source departs from the rule, is a
mark of its own.
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
NOT_VENDORED: set[str] = set()


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


def doc_of(module: str) -> str | None:
    """The corpus document an L4 module encodes: its file's own path, or
    the sectioned document its directory is (base-agreement-44 lives in
    the base agreement's directory)."""
    import modules
    f = modules.wanted()[0].get(module)
    if f is None:
        return None
    rel = f.relative_to(ROOT / "l4")
    for cand in (rel.with_suffix(".xml"), rel.parent.with_suffix(".xml")):
        if (ROOT / "corpus" / "akn" / cand).exists():
            return str(cand)
    return None


class TheRootIsTheSource(unittest.TestCase):
    """MMS-521: every contradiction the root finds is a card, generated from
    its report; a hand card attaches to a row by key and cannot add one; a
    card the root cannot speak for says why. The report is read from what
    `make l4` recorded for l4/tests/root-tests.l4 — the root is not
    evaluated again here."""

    @classmethod
    def setUpClass(cls):
        import roots
        if not roots.current():
            raise unittest.SkipTest("the roots' results are not current: `make l4`")
        cls.report = contradictions.root_report()
        assert cls.report is not None, "make l4 recorded no `the contradictions report`"
        cls.rows = contradictions.root_rows(cls.report)
        cls.shown = contradictions.cards(DATA, cls.rows)
        cls.count = int(roots.evaluated("root", "count `the contradictions`"))

    def test_the_report_holds_every_contradiction_the_root_finds(self):
        """Every contradiction is settled by a resolution (the gate), and
        the report has a line per resolution with the cases it settles: so
        they add up to every contradiction found."""
        import roots
        self.assertEqual(sum(r["cases"] for r in self.report), self.count)
        self.assertEqual(len(self.report), int(roots.evaluated("root", "count `the resolutions`")))
        for r in self.report:
            with self.subTest(item=r["item"], governs=r["governs"], sources=r["sources"]):
                self.assertGreater(r["cases"], 0, "a resolution that settles no case")
                self.assertIn(r["governs"], r["sources"])
                self.assertEqual(set(r["says"]), set(r["sources"]))
                self.assertGreaterEqual(len(set(r["says"].values())), 2, "an example with no disagreement")

    def test_every_generated_card_is_graded(self):
        """Every row no hand card claims is graded in
        data/contradiction-grades.json, and the table holds no row the root
        does not report unclaimed (MMS-703): a new row fails here until it
        is graded."""
        claimed = {contradictions.root_key(c["root"]) for c in DATA["items"] if c.get("root")}
        unclaimed = {contradictions.root_key(r) for r in self.rows} - claimed
        self.assertEqual(set(contradictions.row_grades()), unclaimed)
        for c, _ in self.shown:
            with self.subTest(card=c["id"]):
                self.assertIn(c.get("severity"), contradictions.SEV)

    def test_every_root_row_has_exactly_one_card(self):
        keys = [contradictions.root_key(row) for _, row in self.shown if row]
        self.assertEqual(sorted(keys), sorted(contradictions.root_key(r) for r in self.rows))

    def test_no_card_claims_a_row_the_root_does_not_report(self):
        rows = {contradictions.root_key(r) for r in self.rows}
        claimed = [contradictions.root_key(c["root"]) for c in DATA["items"] if c.get("root")]
        self.assertTrue(claimed)
        self.assertEqual(len(claimed), len(set(claimed)), "two cards claim one row")
        for k in claimed:
            with self.subTest(root=k):
                self.assertIn(k, rows)

    def test_an_attached_card_adds_no_document_the_row_does_not_name(self):
        """Crops, practice, משמעות and prose attach to a row; a document
        side is one of the instruments the root says speak in it."""
        rows = {contradictions.root_key(r): r for r in self.rows}
        for c in DATA["items"]:
            if not c.get("root"):
                continue
            docs = {doc_of(m) for m in rows[contradictions.root_key(c["root"])]["sources"]}
            for s in c["sides"]:
                if s["type"] in contradictions.PAYING:
                    continue
                with self.subTest(card=c["id"], side=s["label"]):
                    self.assertIn(s["doc"], docs)

    def test_a_card_the_root_cannot_speak_for_says_why(self):
        """Exactly one of `root` and `not_in_root`, and the reason is the
        one the card's sides show: a statute side is a statute floor; fewer
        than two sides the root weighs is a source it does not weigh; two
        weighed instruments it does not set against each other have no pay
        item for it yet, or disagree on no figure."""
        for c in DATA["items"]:
            with self.subTest(card=c["id"]):
                self.assertNotIn("root_item", c)
                self.assertEqual(bool(c.get("root")), not c.get("not_in_root"))
                why = c.get("not_in_root")
                if not why:
                    continue
                self.assertIn(why, contradictions.NOT_IN_ROOT)
                weighed = [s for s in c["sides"] if s["type"] in contradictions.WEIGHED]
                if any(s["type"] == "law" for s in c["sides"]):
                    self.assertEqual(why, "statute-floor")
                elif len(weighed) < 2:
                    self.assertEqual(why, "not-weighed")
                else:
                    self.assertIn(why, ("no-pay-item", "text-only"))

    def test_every_rule_the_root_reports_has_its_place(self):
        groups = {g["id"] for g in DATA["groups"]}
        for r in self.rows:
            with self.subTest(rule=r["rule"]):
                self.assertIn(contradictions.RULE_GROUP.get(r["rule"]), groups)

    def test_a_generated_card_is_the_rows_and_nothing_else(self):
        inst = contradictions.instruments()
        for c, row in self.shown:
            if not c.get("generated"):
                continue
            with self.subTest(card=c["id"]):
                self.assertEqual([s["module"] for s in c["sides"]], row["sources"])
                for s in c["sides"]:
                    self.assertEqual(s["type"], inst[s["module"]][1])
                html = contradictions.generated_html(c, row, inst, href_of=lambda m: None, root_href="root.html")
                self.assertIn(contradictions.esc(row["rule"]), html)
                self.assertIn(contradictions.esc(inst[row["governs"]][0]), html)
                self.assertEqual(html.count("<li>"), len(row["resolutions"]))

    def test_the_built_page_has_every_card(self):
        import build_site
        page = build_site.OUT / contradictions.HERE
        if not page.exists():
            self.skipTest("run `make site` first")
        html = page.read_text(encoding="utf-8")
        self.assertEqual(html.count('<details class="cx-card'), len(self.shown))
        for c, row in self.shown:
            with self.subTest(card=c["id"]):
                self.assertIn(f'id="{c["id"]}"', html)


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

    def test_every_card_is_graded_and_says_why(self):
        """The client, 2026-11-12 (MMS-703): "all סתירות should have a
        severity rating". Every hand card carries a grade on the MMS-506
        scale and the reason for it; an error -- a paying source departing
        from what the governing rule gives -- also says what it means for a
        teacher."""
        errs = {c["id"] for c in contradictions.errors(DATA)}
        self.assertTrue(errs)
        for c in DATA["items"]:
            with self.subTest(item=c["id"]):
                self.assertNotIn("practice", c)
                self.assertIn(c.get("severity"), contradictions.SEV)
                self.assertTrue(c.get("severity_why", "").strip())
                if c["id"] in errs:
                    self.assertTrue(c.get("meaning", "").strip())

    def test_a_card_takes_its_findings_grade_or_says_why_not(self):
        """A card that names findings is graded as the highest-graded of
        them, unless `severity_differs_from_finding` says why; and only a
        card that differs carries that field."""
        rank = {"low": 0, "medium": 1, "high": 2}
        sev = {}
        for f in (ROOT / "findings").rglob("*.toml"):
            for x in tomllib.loads(f.read_text(encoding="utf-8")).get("finding", []):
                sev[x["id"]] = x.get("severity")
        for c in DATA["items"]:
            graded = [sev[f] for f in c.get("findings", []) if sev.get(f)]
            with self.subTest(item=c["id"]):
                if graded and c["severity"] != max(graded, key=rank.get):
                    self.assertTrue(c.get("severity_differs_from_finding", "").strip(),
                                    f"graded {c['severity']}, its findings {max(graded, key=rank.get)}")
                else:
                    self.assertNotIn("severity_differs_from_finding", c)

    def test_a_generated_rows_grade_is_well_formed(self):
        """data/contradiction-grades.json: each entry names a row by the key
        a hand card attaches by, once, with a grade and its reason."""
        grades = json.loads(contradictions.GRADES.read_text(encoding="utf-8"))["rows"]
        self.assertTrue(grades)
        keys = [contradictions.root_key(g["root"]) for g in grades]
        self.assertEqual(len(keys), len(set(keys)))
        claimed = {contradictions.root_key(c["root"]) for c in DATA["items"] if c.get("root")}
        for g in grades:
            with self.subTest(root=contradictions.root_key(g["root"])):
                self.assertEqual(set(g["root"]), {"item", "governs", "rule"})
                self.assertIn(g["severity"], contradictions.SEV)
                self.assertTrue(g["severity_why"].strip())
                # a row a hand card claims is graded on the card
                self.assertNotIn(contradictions.root_key(g["root"]), claimed)

    def test_an_error_is_marked_apart_from_its_grade(self):
        """Every card shows its grade chip; "טעות" shows only where a paying
        source departs, so a grade never claims the card is a mistake."""
        for c in DATA["items"]:
            with self.subTest(item=c["id"]):
                html = contradictions.card(c, DATA["rules"], prose=lambda t: t,
                                           clause_link=lambda d, k: ("#", k), finding_ids=set(),
                                           src=lambda f: f)
                self.assertIn(f'<span class="cx-sev sev-{c["severity"]}">חומרה: ', html)
                self.assertIn(f'data-sev="{c["severity"]}"', html)
                self.assertEqual('<span class="cx-err">טעות</span>' in html, contradictions.is_error(c))

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
        # the meter counts every graded card and says how a grade is decided
        self.assertIn(contradictions.HOW_GRADED, html)
        self.assertIn(f'<b>{len(DATA["items"])}</b> סתירות מדורגות', html)
        self.assertNotIn('data-sev="none"', html)
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


class WhichWayTheCircularDeparts(unittest.TestCase):
    """MMS-602: a card that sets a circular against the agreement it carries
    out says which way the circular departs. Giving less, the agreement
    governs and §29 of the Budget Foundations Law is not in play; giving
    more, §29 is applied through the encoded section, and the result is the
    card's own #ASSERT."""

    def test_every_circular_against_an_agreement_says_which_way(self):
        named = [c for c in DATA["items"] if contradictions.compares_circular_to_agreement(c)]
        self.assertTrue(named)
        for c in DATA["items"]:
            with self.subTest(item=c["id"]):
                if contradictions.compares_circular_to_agreement(c):
                    self.assertIn(c.get("direction"), contradictions.DIRECTION)
                    self.assertTrue(c.get("direction_note", "").strip())
                else:
                    self.assertNotIn("direction", c)
                # only a circular that gives more is weighed under §29
                self.assertEqual("section_29" in c, c.get("direction") == "more")

    def test_more_applies_section_29_through_the_encoded_module(self):
        conventions = {x["id"]: x for x in tomllib.loads(
            (ROOT / "conventions.toml").read_text(encoding="utf-8"))["convention"]}
        for c in DATA["items"]:
            s = c.get("section_29")
            if not s:
                continue
            with self.subTest(item=c["id"]):
                self.assertIsInstance(s["voids"], bool)
                self.assertTrue(s["note"].strip())
                text = (ROOT / s["l4"]).read_text(encoding="utf-8")
                self.assertIn("IMPORT budget_foundations_law", text)
                self.assertIn(f"#ASSERT `{s['name']}`", text)
                self.assertIn(f"`{s['name']}` MEANS", text)
                # the reading is a pick put to the lawyer (decision 16)
                conv = conventions[s["convention"]]
                self.assertTrue(conv.get("lawyer"))
                self.assertIn({"l4": s["l4"], "rule": s["name"]}, conv["applies"])

    def test_the_card_says_what_section_29_does(self):
        for c in DATA["items"]:
            if not c.get("direction"):
                continue
            with self.subTest(item=c["id"]):
                html = contradictions.card(c, DATA["rules"], prose=lambda t: t,
                                           clause_link=lambda d, k: ("#", k), finding_ids=set(),
                                           src=lambda f: f)
                self.assertIn(contradictions.DIRECTION[c["direction"]], html)
                if c["direction"] == "same":
                    # a circular that copies the agreement is no §29 question:
                    # the box says what wins over both, and leaves §29 out
                    self.assertNotIn(contradictions.S29, html)
                    self.assertIn(f'{c["winner"]} גובר על שניהם', html)
                    continue
                self.assertIn(contradictions.S29, html)
                if c["direction"] in ("less", "other"):
                    self.assertIn("<b>ההסכם גובר</b>", html)
                    self.assertIn("אינו חל כאן", html)
