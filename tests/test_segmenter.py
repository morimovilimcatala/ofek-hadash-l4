"""How a source is cut into segments, and how L4's own rendering is shown.
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


class RenderPageHeadings(unittest.TestCase):
    """`l4 render` numbers its headings by their order in the file; the
    render page drops that count, which reads as the corpus's numbering."""

    def test_the_renderer_ordinal_is_dropped(self):
        got = site_mod.without_render_ordinals(
            '<h2 id="sec_3" class="section">§ 3  1 עובדים קיימים</h2>'
            '<h2 id="sec_1" class="section">§ 1  Interpretation</h2>')
        self.assertEqual(got, '<h2 id="sec_3" class="section">1 עובדים קיימים</h2>'
                              '<h2 id="sec_1" class="section">Interpretation</h2>')

    def test_a_section_sign_in_prose_is_kept(self):
        prose = '<p>under § 3 of the agreement</p>'
        self.assertEqual(site_mod.without_render_ordinals(prose), prose)


if __name__ == "__main__":
    unittest.main()
