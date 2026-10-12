"""The checks the site's claims rest on.

Alignment: every key an L4 file cites is a row of its section, and every
text row of an encoded section is cited (by itself, an alias or an
ancestor) — the denominator is the section's own paragraphs.
Findings: every finding names real rows and is backed by an #ASSERT in the
file it names. Corpus: the snapshot is what SOURCE.toml says it is.
Toolchain: when build/l4 is present, every file checked clean and its
result is not stale.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
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


class Corpus(unittest.TestCase):
    def test_snapshot_matches_source_record(self):
        src = tomllib.loads((ROOT / "corpus/SOURCE.toml").read_text(encoding="utf-8"))
        for f in src["file"]:
            data = (ROOT / "corpus" / f["path"]).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), f["sha256"], f["path"])

    def test_every_document_in_work_is_in_the_manifest(self):
        docs = {d["path"] for d in json.loads(
            (ROOT / "corpus/manifest.json").read_text(encoding="utf-8"))["documents"]}
        for doc in site_mod.DOCUMENTS:
            self.assertIn(doc, docs)

    def test_section_numbers_are_unique(self):
        # a section's number is its file name and its page
        for doc in site_mod.DOCUMENTS:
            nums = [s.num for s in akn.sections(doc)]
            self.assertEqual(len(nums), len(set(nums)), doc)


class Alignment(unittest.TestCase):
    def test_no_l4_file_without_a_section(self):
        known = {site_mod.l4_path(doc, s.num) for doc in site_mod.DOCUMENTS
                 for s in akn.sections(doc)}
        for f in (ROOT / "l4").rglob("*.l4"):
            if f.name == "common.l4" or f.parent.name == "lib" or f.is_symlink():
                continue
            self.assertIn(f, known, f"{f.relative_to(ROOT)} encodes no corpus section")

    def test_every_cited_key_is_a_row_of_its_section(self):
        for v in views():
            if v.src is None:
                continue
            with self.subTest(section=v.section.num):
                self.assertEqual([s.keys for s in v.unplaced], [],
                                 f"§{v.section.num} cites keys that are not in the section")

    def test_every_text_row_of_an_encoded_section_is_cited(self):
        for v in views():
            if v.src is None:
                continue
            with self.subTest(section=v.section.num):
                missing = [r.key for r in v.text_rows if r.key not in v.covered]
                self.assertEqual(missing, [], f"§{v.section.num}: paragraphs no segment cites")


class Layout(unittest.TestCase):
    def test_no_continuation_line_regroups_arithmetic(self):
        # a line that begins with an operator takes the rest of the line as
        # its right operand (tools/layout_lint.py); one operand per line
        import layout_lint
        found = [f"{f.relative_to(ROOT)}:{n} {kind}: {t}"
                 for f in sorted((ROOT / "l4").rglob("*.l4"))
                 for n, kind, t in layout_lint.scan(f)]
        self.assertEqual(found, [])


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
                for field in ("title", "body", "reading", "l4", "evidence", "keys", "read_by"):
                    self.assertTrue(f.get(field), field)
                for d in f.get("depends_on", []):
                    self.assertIn(d, ids, "depends on a finding that does not exist")
                # a key is a row of the finding's OWN document: every circular
                # has an art_1, so a key alone proves nothing
                for k in f["keys"]:
                    self.assertIn((site_mod.finding_doc(f), k), self.keys)
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


@unittest.skipUnless((ROOT / "build/l4").exists(), "run `make l4` first")
class Toolchain(unittest.TestCase):
    def test_every_file_checks_and_every_assert_holds(self):
        import l4run
        for f in l4run.files():
            out = l4run.outputs(f)
            with self.subTest(file=str(f.relative_to(ROOT))):
                self.assertTrue(out["run"].exists(), "not run")
                data = json.loads(out["run"].read_text(encoding="utf-8"))
                self.assertTrue(data.get("ok"), data.get("diagnostics"))
                stale = out["key"].read_text() != l4run.key(f, l4run.compiler_id(l4run.compiler()))
                self.assertFalse(stale, "build/l4 is stale for this file: run `make l4`")


class Segmenter(unittest.TestCase):
    def parse(self, text: str) -> l4src.Source:
        with tempfile.NamedTemporaryFile("w", suffix=".l4", delete=False, encoding="utf-8") as fh:
            fh.write(text)
        return l4src.parse(Path(fh.name))

    def test_lead_comments_join_the_rule_they_head(self):
        src = self.parse("IMPORT prelude\n\n§§ `2`\n-- the days table\n@ref akn:A\nx MEANS 1\n\n"
                         "-- akn:B NOT A RULE: sources\n")
        a, b = src.segments
        self.assertEqual((a.keys, a.start, a.end), (["A"], 3, 6))
        self.assertFalse(a.note_only)
        self.assertEqual((b.keys, b.note_only), (["B"], True))
        self.assertEqual(src.preamble, (1, 3))

    def test_a_heading_above_a_blank_line_heads_the_rule_below(self):
        src = self.parse("@ref akn:A\nx MEANS 1\n\n§§ `2`\n\n@ref akn:B\ny MEANS 2\n")
        a, b = src.segments
        self.assertEqual((a.start, a.end), (1, 2))
        self.assertEqual(b.start, 4)

    def test_a_note_does_not_lend_its_continuation_to_the_next(self):
        src = self.parse("-- akn:A first\n-- still A\n-- akn:B second\n")
        self.assertEqual([s.keys for s in src.segments], [["A"], ["B"]])
        self.assertEqual(src.segments[0].end, 2)

    def test_code_after_a_note_is_not_the_notes(self):
        src = self.parse("-- akn:A sources\n\n`example` MEANS 1\n#ASSERT `example` EQUALS 1\n")
        note, rest = src.segments
        self.assertEqual((note.keys, note.note_only, note.end), (["A"], True, 1))
        self.assertEqual((rest.keys, rest.start), ([], 3))

    def test_a_heading_ends_the_rule_above_it(self):
        src = self.parse("@ref akn:A\nx MEANS 1\n\n§§ `next`\n\nhelper MEANS 2\n")
        rule, shared = src.segments
        self.assertEqual((rule.keys, rule.end), (["A"], 2))
        self.assertEqual((shared.keys, shared.start), ([], 4))

    def test_a_heading_is_not_part_of_the_note_below_it(self):
        src = self.parse("§ `Circular 9`\n\n-- akn:A The letterhead; no rule.\n")
        self.assertEqual(src.segments[0].note, "The letterhead; no rule.")

    def test_one_marker_may_cite_several_keys(self):
        src = self.parse("@ref akn:A akn:B__x\ny MEANS 2\n")
        self.assertEqual(src.segments[0].keys, ["A", "B__x"])


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
MISQUOTED = {
    # The corpus prints the sentence damaged, the quote is the page's
    # (MMS-478): a bullet glyph inside it, or a number moved by the RTL
    # extraction.
    "F-2008-09_tashsat_09-b": "MMS-478",
    "F-2008-09_tashsat_09-c": "MMS-478",
    "F-2008-09_tashsat_10-d": "MMS-478",
    "F-2009-10_tasha_05-d": "MMS-478",
    "F-2011-12_tashab_11-a": "MMS-478",
    "F-2011-12_tashab_12-a": "MMS-478",
    "F-2011-12_tashab_12-d": "MMS-478",
    "F-2019-20_tashaf_08-b": "MMS-478",
    # A table cell the corpus publishes flattened and scrambled (MMS-424);
    # the quote reads the cell off the page.
    "F-2022-23_tashpag_01-g": "MMS-424",
    "F-2024-25_tashpah_10-b": "MMS-424",
    "F-2025-26_tashpo_02-j": "MMS-424",
}


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


class SitePages(unittest.TestCase):
    """The takanon collection's other documents are the department's web
    pages: whole documents, read row by row, and a group of their own."""

    def pages(self):
        return [d for d in site_mod.DOCUMENTS if site_mod.is_site_page(d)]

    def test_the_collection_is_in_work_whole(self):
        takanon = {d["path"] for d in site_mod.MANIFEST_DOCS if d["collection"] == "takanon"}
        self.assertEqual(takanon, {d for d in site_mod.DOCUMENTS if d.startswith("takanon/")})
        self.assertEqual(akn.SECTIONED & takanon, {"takanon/takanon-sherut-ovdei-horaa.xml"})
        self.assertTrue(self.pages())
        for d in self.pages():
            self.assertTrue(akn.is_whole(d), d)

    def test_every_page_reads_into_text_rows_with_unique_keys(self):
        for d in self.pages():
            with self.subTest(doc=d):
                (sec,) = akn.sections(d)
                text = [r for r in sec.rows if r.kind == "text"]
                self.assertTrue(text)
                keys = [r.key for r in sec.rows]
                self.assertEqual(len(keys), len(set(keys)))

    def test_a_page_is_its_own_document_not_the_home_page(self):
        site_mod.NAV_VIEWS.clear()
        site_mod.NAV_VIEWS.update({d: [site_mod.build_view(d, s) for s in akn.sections(d)]
                                   for d in site_mod.DOCUMENTS if d.startswith("takanon/")})
        for d in self.pages():
            self.assertEqual(site_mod.doc_of(d.removesuffix(".xml") + ".html"), d)
        self.assertEqual(site_mod.coll_hub("takanon"), "takanon/takanon-sherut-ovdei-horaa.html")


class Citations(unittest.TestCase):
    def test_every_row_of_every_document_has_a_label(self):
        # a table row is keyed "<holder>/t<N>"; the label code once assumed
        # every key with a "/" was a paragraph and crashed the site on it
        tables = 0
        for doc in site_mod.DOCUMENTS:
            for sec in akn.sections(doc):
                labels = site_mod.citations(sec)
                for r in sec.rows:
                    for k in [r.key, *r.aliases]:
                        self.assertIn(k, labels, f"{doc}: {k}")
                    if r.cells is not None:
                        tables += 1
                        self.assertIn(" table ", labels[r.key])
        self.assertGreater(tables, 0)


if __name__ == "__main__":
    unittest.main()
