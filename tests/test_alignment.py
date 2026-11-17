"""Alignment: every key an L4 file cites is a row of its section, and every
text row of an encoded section is cited (by itself, an alias or an
ancestor) — the denominator is the section's own paragraphs. A statute
outside the corpus is held to its pinned text the same way.
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


class Alignment(unittest.TestCase):
    def test_no_l4_file_without_a_section(self):
        known = {site_mod.l4_path(doc, s.num) for doc in site_mod.DOCUMENTS
                 for s in akn.sections(doc)}
        import laws
        statutes = {laws.l4_file(n) for n in laws.all_laws()}
        for f in (ROOT / "l4").rglob("*.l4"):
            # what mirrors no corpus document: the conventions, the shared
            # vocabulary, the roots, the tests, the modules a collection
            # shares, reference material and the one namespace (MMS-776)
            if (f.name == "conventions.l4" or f.relative_to(ROOT / "l4").parts[0]
                    in ("lib", "roots", "tests", "shared", "reference", "modules")):
                continue
            if f in statutes:  # a statute outside the corpus: see StatutesOutsideTheCorpus
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


class StatutesOutsideTheCorpus(unittest.TestCase):
    """A statute the L4 encodes though the corpus holds no copy (MMS-516):
    its pinned text and its L4 cite each other section for section."""

    def test_every_section_is_cited_and_every_citation_is_a_section(self):
        import laws
        self.assertTrue(laws.all_laws())
        for name in laws.all_laws():
            with self.subTest(law=name):
                law = laws.load(name)
                nums = [s["num"] for s in law["section"]]
                self.assertEqual(len(nums), len(set(nums)))
                self.assertEqual(laws.cited(name), set(nums))
                _, blocks = laws.blocks(name)
                self.assertEqual(list(blocks), nums, "a §§ block per section, in order")
                for s in law["section"]:
                    self.assertTrue(site_mod.is_hebrew(s["text"]) and s["heading"].strip())
                self.assertTrue(law["url"].startswith("https://he.wikisource.org/wiki/"))

    def test_its_page_says_the_contradictions_page_cites_it_only_where_a_card_does(self):
        """A law's page once told every reader that the contradictions page
        cites its sections, whether any card did or not (the Contracts Law,
        MMS-529, is named by none)."""
        import laws
        claim = "מצטט את הסעיפים האלה"
        seen = set()
        for name in laws.all_laws():
            body = laws.page_body(name, code_html=lambda b: "", esc=lambda t: t)
            with self.subTest(law=name):
                self.assertEqual(claim in body, bool(laws.cards_naming(name)))
            seen.add(claim in body)
        self.assertEqual(seen, {True, False})
        self.assertEqual(laws.cards_naming("contracts-law"), [])

    def test_a_file_imports_it_by_its_module_name(self):
        # one name per module (MMS-776): `collective-agreements-law`, the
        # file's own name, which l4/modules/ links; the underscore aliases
        # a directory once kept beside its files are gone
        import laws
        for name in laws.all_laws():
            self.assertEqual((ROOT / "l4/modules" / f"{name}.l4").resolve(), laws.l4_file(name).resolve())
            alias = name.replace("-", "_")
            for f in (ROOT / "l4").rglob("*.l4"):
                if f.is_symlink():
                    continue
                with self.subTest(file=str(f.relative_to(ROOT)), law=name):
                    self.assertNotRegex(f.read_text(encoding="utf-8"), rf"(?m)^IMPORT\s+`?{alias}`?\s*$")


if __name__ == "__main__":
    unittest.main()
