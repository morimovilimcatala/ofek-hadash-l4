"""The simulator's group of the contradictions page (contradictions.html#g-simulator;
a page of its own, calculator-delta.html, from MMS-513 until MMS-522) and its data.

data/calculator-delta.json is written outside this repository, by a
comparison that reads a private extraction of the ministry's simulator. What
may come in is what the page shows: inputs, outputs, mappings, clauses and
classifications. These checks hold the file to that -- no simulator code and
no recorded traffic -- and hold every cause to a classification and to the
corpus clause that governs it, quoted verbatim.
"""
from __future__ import annotations

import json
import re
import sys
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import akn               # noqa: E402
import calculator_delta  # noqa: E402

DATA = json.loads(calculator_delta.DATA.read_text(encoding="utf-8"))

# what code or a captured response would bring with it
CODE = re.compile(r"=>|\bfunction\b|\bconst\b|\blet\b|\bvar\b|\breturn\b|\bimport\b|\brequire\(|Math\.|"
                  r"\bawait\b|\bnew [A-Z]|sourceMappingURL|/api/|GetCalc|\.mjs\b|\.ts\b|"
                  r"\bSemel\b|\bScum\b|\bTeur\b|\bAhuzKamoot\b|\bpayload\b", re.I)
# the response's own keys, and the request's envelope
RAW_KEYS = {"Semel", "Scum", "Teur", "AhuzKamoot", "payload", "lines", "status", "key", "calc"}
MAX_EXAMPLES = 3


def strings(o, path=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from strings(k, path + "/key")
            yield from strings(v, f"{path}/{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from strings(v, f"{path}[{i}]")
    elif isinstance(o, str):
        yield path, o


def dicts(o):
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from dicts(v)
    elif isinstance(o, list):
        for v in o:
            yield from dicts(v)


def finding_ids() -> set[str]:
    out = set()
    for f in (ROOT / "findings").rglob("*.toml"):
        out |= {x["id"] for x in tomllib.loads(f.read_text(encoding="utf-8")).get("finding", [])}
    return out


def row_text(doc: str, key: str) -> str:
    for s in akn.sections(doc):
        for r in s.rows:
            if r.key == key or key in r.aliases:
                return " ".join(r.text.split())
    raise KeyError((doc, key))


class TheDataHoldsNoCode(unittest.TestCase):
    def test_no_string_is_code_or_a_captured_response(self):
        for path, s in strings(DATA):
            # the L4's own identifiers are named in backticks; they are ours
            bare = re.sub(r"`[^`]*`", "", s)
            self.assertIsNone(CODE.search(bare), f"{path}: {s[:120]}")
            self.assertLess(len(s), 2500, path)

    def test_no_object_is_a_response_line_or_a_request(self):
        for d in dicts(DATA):
            self.assertFalse(RAW_KEYS & set(d) and {"Semel", "Scum"} & set(d), d)
            self.assertFalse({"payload", "lines"} <= set(d), list(d))

    def test_examples_are_a_few_per_cause_not_the_capture(self):
        for c in DATA["causes"] + DATA["quirks"]:
            self.assertLessEqual(len(c.get("examples", [])), MAX_EXAMPLES, c["id"])
        self.assertLess(calculator_delta.DATA.stat().st_size, 400_000)


class EveryCause(unittest.TestCase):
    def test_has_a_classification(self):
        for c in DATA["causes"]:
            self.assertIn(c["class"], DATA["classes"], c["id"])
            self.assertIn(c["class"], calculator_delta.CLASS_ORDER, c["id"])

    def test_cites_a_clause_quoted_verbatim_from_the_corpus(self):
        for c in DATA["causes"]:
            self.assertTrue(c["clauses"], c["id"])
            for q in c["clauses"]:
                self.assertIn(q["quote"], row_text(q["doc"], q["key"]), (c["id"], q["key"]))

    def test_names_only_findings_and_conventions_that_exist(self):
        ids = finding_ids()
        conv = {x["id"] for x in tomllib.loads((ROOT / "conventions.toml").read_text(encoding="utf-8"))["convention"]}
        for c in DATA["causes"]:
            for f in c["findings"]:
                self.assertIn(f, ids, c["id"])
            for v in c["conventions"]:
                self.assertIn(v, conv, c["id"])

    def test_names_only_l4_rules_its_file_declares(self):
        for c in DATA["causes"]:
            for r in c["l4"]:
                text = (ROOT / r["file"]).read_text(encoding="utf-8")
                rule = re.escape(f"`{r['rule']}`")
                self.assertTrue(re.search(rf"(?m)^(?:DECIDE\b.*{rule}|{rule}\s+MEANS\b)", text), (c["id"], r))

    def test_a_proposed_grade_is_a_grade_and_says_why(self):
        for c in DATA["causes"]:
            if c.get("severity"):
                self.assertIn(c["severity"]["grade"], calculator_delta.SEV, c["id"])
                self.assertTrue(c["severity"]["why"], c["id"])

    def test_counts_add_up(self):
        for name, s in DATA["summary"].items():
            self.assertEqual(s["lines"], s["match"] + s["delta"] + s["not_encoded"] + s["not_comparable"], name)
        counted = sum(c["lines"] for c in DATA["causes"] if c["counted"])
        quirks = sum(q.get("lines", 0) for q in DATA["quirks"] if q["id"] in ("job0", "tafkid-needs-nigrar"))
        self.assertEqual(counted + quirks, sum(s["delta"] for s in DATA["summary"].values()))


class ThePage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        def clause_link(doc, key):
            return f"{doc}#{key}", f"<bdi>{key}</bdi>"
        cls.body, cls.side = calculator_delta.section(
            DATA, prose=lambda t: t, clause_link=clause_link, finding_ids=finding_ids(),
            conv_titles={}, l4_link=lambda f: f)

    def test_shows_every_cause_quirk_and_the_disclaimer(self):
        for c in calculator_delta.group_rows(DATA):
            self.assertIn(f'id="{c["id"]}"', self.body)
        # every row is a card the page's filters and links know
        self.assertEqual(self.body.count(" cx-card"), len(calculator_delta.group_rows(DATA)))
        self.assertIn("הסימולטור אינו מחייב", self.body)
        # the simulator's own words, verbatim (MMS-522)
        self.assertIn("מודול זה מדמה שכר בלבד ולפיכך אין משרד החינוך "
                      "מתחייב לתשלום שכר על פי התחשיב המופק ממודול זה.", self.body)
        for anchor in ("sim-what", "sim-summary", "sim-quirks", "sim-coverage"):
            self.assertIn(f'id="{anchor}"', self.body)
        self.assertIn(f'href="#{calculator_delta.GROUP}"', self.side)

    def test_links_every_finding_it_names(self):
        for c in DATA["causes"]:
            for f in c["findings"]:
                self.assertIn(f'href="findings.html#{f}"', self.body)

    def test_the_contradictions_page_holds_it_and_the_old_page_redirects(self):
        """No tab of its own (the client, 2026-10-21: "can we remove the
        simulator page?"); its rows are a group of סתירות בין מסמכים, and
        calculator-delta.html sends an old link there."""
        import build_site
        import contradictions
        self.assertTrue(build_site.DELTA)
        nav = build_site.page(contradictions.HERE, "t", "", tab="contradictions")
        self.assertNotIn(f'href="{calculator_delta.HERE}"', nav)
        self.assertIn(f'href="{contradictions.HERE}" aria-current=page', nav)
        html, side = contradictions.body(contradictions.load(), prose=lambda t: t,
                                         clause_link=lambda d, k: ("#", k), finding_ids=set(),
                                         src=lambda f: f,
                                         simulator=(self.body, self.side,
                                                    len(calculator_delta.group_rows(DATA))))
        self.assertIn(f'id="{calculator_delta.GROUP}"', html)
        self.assertIn('data-val="simulator"', html)
        # one page, two sets of cards: no anchor twice
        ids = re.findall(r' id="([^"]+)"', html)
        self.assertEqual(sorted(i for i in set(ids) if ids.count(i) > 1), [])
        moved = build_site.redirect_page(calculator_delta.HERE,
                                         f"{contradictions.HERE}#{calculator_delta.GROUP}", "t")
        self.assertIn(f'url={contradictions.HERE}#{calculator_delta.GROUP}', moved)
