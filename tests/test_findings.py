"""Findings: every finding names real rows, quotes them, sits on its own
document's page, and is backed by an #ASSERT in the file it names.
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


def views():
    for doc in site_mod.DOCUMENTS:
        for sec in akn.sections(doc):
            yield site_mod.build_view(doc, sec)


class Findings(unittest.TestCase):
    def setUp(self):
        self.findings = site_mod.load_findings()
        self.keys = {}
        for v in views():
            for k in v.section.keys():
                self.keys[(v.doc, k)] = v

    def test_findings_are_well_formed(self):
        ids = [f["id"] for f in self.findings]
        self.assertEqual(len(ids), len(set(ids)))
        for f in self.findings:
            with self.subTest(finding=f["id"]):
                self.assertIn(f["kind"], site_mod.KINDS)
                self.assertIn(f["stage"], site_mod.STAGES)
                self.assertIn(f["review"], site_mod.REVIEW)
                # every finding is graded, and says why (MMS-504)
                self.assertIn(f.get("severity"), site_mod.SEVERITY)
                self.assertTrue(site_mod.is_hebrew(f.get("severity_why", "")))
                for field in ("title", "body", "reading", "l4", "evidence", "keys", "read_by"):
                    self.assertTrue(f.get(field), field)
                for d in f.get("depends_on", []):
                    self.assertIn(d, ids, "depends on a finding that does not exist")
                # a key is a row of the finding's OWN document: every circular
                # has an art_1, so a key alone proves nothing
                # assertTrue, not assertIn: assertIn prints the container, and
                # this one (every row of every section, each with its view)
                # ran the machine out of memory instead of naming the key.
                for k in f["keys"]:
                    self.assertTrue((site_mod.finding_doc(f), k) in self.keys,
                                    f"{k} is not a row of {site_mod.finding_doc(f)}")
                self.assertTrue((ROOT / f["l4"]).exists(), f["l4"])

    def test_findings_are_written_in_hebrew(self):
        """The client, 2026-10-11: a finding shown in English "should be
        Hebrew". Its title, body and reading are Hebrew; an L4 identifier in
        backticks stays English and does not count. A sequence arrow points
        left, because the page is right to left."""
        for f in self.findings:
            for field in ("title", "body", "reading"):
                with self.subTest(finding=f["id"], field=field):
                    self.assertTrue(site_mod.is_hebrew(f[field]), "written in English")
                    self.assertNotIn("→", site_mod.IDENT.sub("", f[field]))

    def test_findings_never_cite_a_paragraph_by_our_count(self):
        """A "¶41" is the builder's running count of the unnumbered
        paragraphs in a clause (the /pN of a row key); nothing on the page
        prints it, so a reader cannot find it. A finding names the clause as
        the site labels it and quotes the paragraph's opening words instead.
        (An #ASSERT name in `evidence` is an L4 identifier and is not checked
        here.)"""
        for f in self.findings:
            for field in ("title", "body", "reading"):
                with self.subTest(finding=f["id"], field=field):
                    self.assertNotIn("¶", f[field], "a ¶N reader cannot find on the page")

    def test_every_finding_is_asserted_in_its_file(self):
        for f in self.findings:
            with self.subTest(finding=f["id"]):
                text = (ROOT / f["l4"]).read_text(encoding="utf-8")
                asserts = [l for l in text.splitlines()
                           if l.lstrip().startswith("#ASSERT") and f["evidence"] in l]
                self.assertTrue(asserts, f"no #ASSERT of {f['evidence']} in {f['l4']}")


def _quote_text(s: str) -> str:
    """Whitespace-normalised, and NFC so that two spellings of one pointed
    letter (the takanon's "מרַכֵּז") compare as the same text."""
    return " ".join(unicodedata.normalize("NFC", s).replace("​", "").split())


def _row_text(r) -> str:
    """A row as a quote copies it: its number, its heading, then its text; a
    table's cells joined by " | " and its rows by " ‖ "."""
    body = (" ‖ ".join(" | ".join(c) for c in r.cells) if r.cells is not None else r.text)
    return _quote_text(" ".join(x for x in (r.num, r.heading, body) if x))


# The findings whose quote is not, today, in the rows their keys cite — each
# with the issue it waits on. Exact in both directions: a quote that starts
# to match goes red here until its line is removed. Never add a line to make
# the check pass; a quote we got wrong is fixed in the finding.
MISQUOTED: dict[str, str] = {}


class FindingQuotes(unittest.TestCase):
    """A finding's `quote` is the Hebrew words at issue, verbatim from the
    corpus (MMS-477). Each passage (separated by " · ") must appear in the
    text of the rows the finding's keys cite — a key citing its row and the
    rows nested under it, as a cited ancestor covers its descendants in the
    coverage test — with "…" (or "...") marking an elision. Nothing else is
    forgiven: not a dropped footnote mark, not a repaired word order."""

    def test_every_quote_is_in_the_rows_it_cites(self):
        # per document, every row in reading order under each name it has
        rows: dict[str, list[tuple[int, str, object]]] = {}
        for doc in site_mod.DOCUMENTS:
            n = 0
            for sec in akn.sections(doc):
                for r in sec.rows:
                    n += 1
                    rows.setdefault(doc, []).extend((n, k, r) for k in [r.key] + r.aliases)
        failing = set()
        for f in site_mod.load_findings():
            doc = site_mod.finding_doc(f)
            cited = {}
            for k in f["keys"]:
                for n, kk, r in rows.get(doc, []):
                    if kk == k or kk.startswith(k + "/") or kk.startswith(k + "__"):
                        cited[n] = r
            hay = " ".join(_row_text(cited[n]) for n in sorted(cited))
            for part in f["quote"].split(" · "):
                for frag in re.split(r"…|\.\.\.", part):
                    if _quote_text(frag) and _quote_text(frag) not in hay:
                        failing.add(f["id"])
        self.assertEqual(sorted(failing), sorted(MISQUOTED))
        for fid, issue in MISQUOTED.items():
            self.assertRegex(issue, r"^MMS-\d+$", fid)


class FindingPlacement(unittest.TestCase):
    def test_a_page_shows_only_its_own_documents_findings(self):
        site_mod.FINDINGS_BY_KEY.clear()
        for f in site_mod.load_findings():
            for k in f["keys"]:
                site_mod.FINDINGS_BY_KEY.setdefault((site_mod.finding_doc(f), k), []).append(f)
        for (doc, _), fs in site_mod.FINDINGS_BY_KEY.items():
            for f in fs:
                self.assertEqual(site_mod.finding_doc(f), doc, f["id"])
        # and every finding is flagged on a row of its own document's page
        flagged = {f["id"] for v in views() for r in v.section.rows for f in site_mod.row_findings(v, r)}
        self.assertEqual(flagged, {f["id"] for f in site_mod.load_findings()})
        self.assertEqual(site_mod.finding_doc({"l4": "l4/circulars/2019-20_tashaf_01.l4"}),
                         "circulars/2019-20_tashaf_01.xml")
        self.assertEqual(site_mod.finding_doc({"l4": "l4/takanon/takanon-sherut-ovdei-horaa/1.7.l4"}),
                         "takanon/takanon-sherut-ovdei-horaa.xml")
        # the department's home page is "…gov.il.xml" and its other pages
        # sit in "…gov.il/": a finding on the Q&A is the Q&A's, not the home page's
        self.assertEqual(site_mod.finding_doc(
            {"l4": "l4/takanon/terms-service.education.gov.il/questions-and-answers.l4"}),
            "takanon/terms-service.education.gov.il/questions-and-answers.xml")


if __name__ == "__main__":
    unittest.main()
