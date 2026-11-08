"""Which statutes, and which of their sections, the corpus cites (MMS-601).

data/statute-citations.json is read off the corpus snapshot's own links to
ספר החוקים הפתוח (tools/statute_citations.py); the laws pages and
laws/index.html show it. It is held to the corpus here, so a re-sync that
adds or drops a citation goes red until it is re-recorded.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import laws                # noqa: E402
import statute_citations   # noqa: E402

# Of the laws the L4 pins (laws/*.toml), the sections the corpus cites by
# number that are not pinned, as "<law>:<section>". A ratchet, held exactly:
# pinning one removes it here, and nothing is added to it but a new
# citation the corpus makes of a law already pinned.
CITED_NOT_PINNED = {
    "collective-agreements-law:8", "collective-agreements-law:9",
    "collective-agreements-law:13", "collective-agreements-law:25",
    "national-insurance-law:22",
}

# The laws the L4 pins though no document of the corpus links to their live
# page, held exactly. A protective statute is compared with every
# instrument that rules on its subject, cited or not (MMS-601): the takanon's
# §1.25.3.1 quotes the Sick Pay Law's definition of an illness without
# naming it. A link the corpus adds moves a law out of this set.
PINNED_NOT_LINKED = {"sick-pay-law"}


class TheInventoryIsTheCorpus(unittest.TestCase):

    def test_the_record_is_current(self):
        self.assertEqual(statute_citations.load(), statute_citations.inventory(),
                         "python3 tools/statute_citations.py --write")

    def test_every_act_links_to_the_live_page(self):
        inv = statute_citations.load()
        self.assertTrue(inv["acts"])
        for a in inv["acts"]:
            with self.subTest(act=a["title"]):
                self.assertTrue(a["url"].startswith(statute_citations.WIKI))
                self.assertEqual(a["documents"], len(a["cited_by"]))
                for s in a["sections"]:
                    self.assertLessEqual(s["documents"], a["documents"])
                    self.assertTrue(set(r["doc"] for r in s["rows"]) <= set(a["cited_by"]))

    def test_a_section_printed_after_the_act_without_a_link_is_read(self):
        # "חוק הגנת השכר, תשי"ח - 1985, סעיף 20": a section citation the
        # corpus's linker did not anchor
        m = statute_citations.AFTER.match(', תשי"ח - 1985, סעיף 20.')
        self.assertEqual(m.group(1), "20")
        self.assertEqual(statute_citations.AFTER.match(', תשי"ד / 1954, סעיף 7 (ג)').group(1), "7")
        self.assertIsNone(statute_citations.AFTER.match(', בסעיף 14.1.31'))

    def test_every_pinned_law_is_found_in_the_record_by_its_page(self):
        """Every pinned law but the ones the corpus does not link, which
        are named."""
        unlinked = {name for name in laws.all_laws()
                    if laws.corpus_citations(laws.load(name)) is None}
        self.assertEqual(unlinked, PINNED_NOT_LINKED)

    def test_the_cited_sections_not_pinned_are_the_ratchet(self):
        missing = set()
        for name in laws.all_laws():
            law = laws.load(name)
            mine = {s["num"] for s in law["section"]}
            for s in (laws.corpus_citations(law) or {"sections": []})["sections"]:
                if s["num"] not in mine:
                    missing.add(f"{name}:{s['num']}")
        self.assertEqual(missing, CITED_NOT_PINNED)


if __name__ == "__main__":
    unittest.main()
