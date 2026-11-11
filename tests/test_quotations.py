"""A row prints a quotation's marks, as the corpus reader prints them (MMS-661).

The corpus keeps a quotation's marks in the `startQuote`/`endQuote`
attributes of <quotedText> and <quotedStructure>, not in the element's text,
and its reader (`akn_serve`) prints them back. A row read with `itertext()`
alone loses them, and every amending sentence on the site then read
"במקום המלים מ-4.25% ל-6.25% יבוא מ-4% ל-6.25%", the strings it replaces run
into the sentence around them. `akn.printed` reads them back for every row.

The first class always runs: words the corpus reader prints, pinned, and the
whole class of rows counted from the XML. The second holds every such row to
the reader's own rendering, where a checkout of the corpus repository sits
beside this one (or where OFEK_CORPUS_REPO names one), and SKIPS elsewhere,
saying so — the corpus repository is private and CI cannot fetch it.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import akn                    # noqa: E402
import build_site             # noqa: E402

AMENDMENT = "agreements/framework/2011-04-11_framework-agreement_public-sector_amendment.xml"
DEFERRAL = "agreements/framework/2010-06-07_framework-agreement_public-sector_havraa-reduction-deferral.xml"
TOSEFET = "agreements/framework/2011-01-12_framework-agreement_public-sector_tosefet-2011.xml"


def row(doc: str, key: str) -> akn.Row:
    for s in akn.sections(doc):
        for r in s.rows:
            if r.key == key or key in r.aliases:
                return r
    raise KeyError((doc, key))


def quoting_paragraphs():
    """(document, <p>) for every paragraph of a document the site shows that
    holds a quotation carrying a mark — the outermost <p>, which is the
    row's: a <quotedStructure>'s own paragraphs are read into it."""
    for doc in build_site.DOCUMENTS:
        if not (akn.CORPUS / doc).exists():
            continue
        root = akn.load(doc)
        inner = {q for p in root.iter(akn.AKN + "p") for q in p.iter(akn.AKN + "p") if q is not p}
        for p in root.iter(akn.AKN + "p"):
            if p not in inner and any(e.get("startQuote") or e.get("endQuote") for e in p.iter()):
                yield doc, p


def row_words(p, notes) -> str:
    return "".join(r.text for r in akn.runs_of(p, notes))


class ARowPrintsItsQuotationMarks(unittest.TestCase):

    def test_an_amending_sentence_reads_as_the_reader_prints_it(self):
        # the corpus reader's words for this paragraph, as its page prints them
        self.assertEqual(
            row(AMENDMENT, "art_2__para_d__subpara_2").text,
            'האמור בסעיף 10.4 יכונה "10.4(א)", ובמקום המלים '
            '"מ-4.25% ל-6.25% (שישה אחוזים ועשרים וחמש מאיות האחוז)" יבוא '
            '"מ-4% ל-6.25% (שישה אחוזים ועשרים וחמש מאיות האחוז)".')

    def test_a_quoted_clause_has_its_marks_against_its_first_and_last_words(self):
        """A <quotedStructure> is a block on the reader's page, its opening
        mark on its first clause's line and its closing mark on its last:
        on one line they stand against those words, a space outside them."""
        text = row(DEFERRAL, "art_4__para_a").text
        self.assertTrue(text.startswith('במקום האמור בסעיף 4.2 יבוא: "4.2 '), text)
        self.assertTrue(text.endswith('לעובדים המועסקים בשירות המדינה."'), text)

    def test_a_quotation_the_page_leaves_open_stays_open(self):
        """The corpus records an opening mark and no closing one where the
        page prints none; the row adds none."""
        text = row(TOSEFET, "att_3__hc_1__hc_1__para_4").text
        self.assertIn('יבוא: "6. "קרן פנסיה צוברת ותיקה"', " ".join(text.split()))
        self.assertTrue(text.endswith("כהגדרתן בחוק קופות גמל."), text)

    def test_every_mark_reaches_a_row(self):
        """The class, counted from the XML: every paragraph holding a marked
        quotation is a row's text, with each of its marks — the quotation
        characters its words print plus one per mark the corpus moved into
        an attribute."""
        n = 0
        texts: dict[str, set[str]] = {}
        for doc, p in quoting_paragraphs():
            if doc not in texts:
                texts[doc] = {r.text for s in akn.sections(doc) for r in s.rows}
            words = row_words(p, akn.sic_notes(akn.load(doc)))
            marks = sum(bool(e.get(a)) for e in p.iter() for a in ("startQuote", "endQuote"))
            plain = "".join(p.itertext())
            with self.subTest(doc=doc, words=words[:60]):
                self.assertIn(words, texts[doc])
                for mark in {e.get(a) for e in p.iter() for a in ("startQuote", "endQuote") if e.get(a)}:
                    self.assertEqual(words.count(mark) - plain.count(mark),
                                     sum(e.get(a) == mark for e in p.iter()
                                         for a in ("startQuote", "endQuote")))
                self.assertGreater(marks, 0)
            n += 1
        self.assertGreater(n, 0, "no row carries a quotation: the corpus moved")


def checkout() -> Path | None:
    for c in (os.environ.get("OFEK_CORPUS_REPO"), ROOT.parent / "TeachersSalaryCatala"):
        if c and (Path(c) / "tools" / "akn_serve.py").is_file():
            return Path(c)
    return None


class _Text(HTMLParser):
    """The words of the reader's HTML: its text, without the eId label it
    prints under a quoted clause (`<div class="eid">`), which is an address
    and not the page's words."""
    VOID = {"br", "img", "hr", "wbr", "input", "meta", "link"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.skip = 0

    def handle_starttag(self, t, attrs):
        if t in self.VOID:
            return
        if self.skip:
            self.skip += 1
        elif "eid" in (dict(attrs).get("class") or "").split():
            self.skip = 1

    def handle_endtag(self, t):
        if self.skip and t not in self.VOID:
            self.skip -= 1

    def handle_data(self, d):
        if not self.skip:
            self.out.append(d)


class TheCorpusReaderPrintsTheSameWords(unittest.TestCase):
    """Every row holding a marked quotation, against the corpus reader's own
    rendering of its paragraph: the same words in the same order, spacing
    aside. The reader's sic mark is left out, because the site does not show
    sic marks (the client, 2026-10-06)."""

    @classmethod
    def setUpClass(cls):
        repo = checkout()
        if repo is None:
            raise unittest.SkipTest("no checkout of the corpus repository beside this one "
                                    "(set OFEK_CORPUS_REPO to hold the rows to its reader)")
        sys.path.insert(0, str(repo / "tools"))
        spec = importlib.util.spec_from_file_location("akn_serve", repo / "tools" / "akn_serve.py")
        cls.reader = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.reader)

    def printed(self, p) -> str:
        t = _Text()
        t.feed(self.reader.render_node(p))
        return "".join(t.out).replace("[כך במקור]", "")

    def test_every_quoting_row_is_the_readers_words(self):
        n = 0
        for doc, p in quoting_paragraphs():
            ours = row_words(p, akn.sic_notes(akn.load(doc)))
            with self.subTest(doc=doc, words=ours[:60]):
                self.assertEqual("".join(ours.split()), "".join(self.printed(p).split()))
            n += 1
        self.assertGreater(n, 0)


if __name__ == "__main__":
    unittest.main()
