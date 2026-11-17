"""The vendored corpus and how the site reads it: the snapshot is what
SOURCE.toml says it is, every document in work is in the manifest, every
row has a label, and the agreements read part by part.
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


class Agreements(unittest.TestCase):
    """The agreements collection is in work: every agreement the corpus
    publishes is a document here, and the base agreement is read part by
    part, article by article, its preamble and sign-off a section each."""

    BASE = "agreements/ofek-hadash/2008-12-25_ofek-hadash_base-agreement.xml"

    def test_every_agreement_is_in_work_and_vendored(self):
        listed = {d["path"] for d in site_mod.MANIFEST_DOCS if d["collection"] == "agreements"}
        self.assertTrue(listed)
        self.assertEqual(listed, {d for d in site_mod.DOCUMENTS if d.startswith("agreements/")})
        # the snapshot holds every document of every collection in work, and
        # nothing else (tools/sync_corpus.py)
        vendored = {f["path"].removeprefix("akn/") for f in tomllib.loads(
            (ROOT / "corpus/SOURCE.toml").read_text(encoding="utf-8"))["file"]}
        self.assertEqual(vendored, set(site_mod.DOCUMENTS))

    def test_the_base_agreement_reads_by_article(self):
        self.assertFalse(akn.is_whole(self.BASE))
        secs = akn.sections(self.BASE)
        self.assertEqual((secs[0].eid, secs[-1].eid), ("preamble", "conclusions"))
        self.assertEqual([s.num for s in secs[1:-1]], [str(n) for n in range(1, 161)])
        self.assertTrue(all(s.chapter_eid.startswith("part_") for s in secs[1:-1]))
        # a frame section's file and page are named in ASCII
        # (and prefixed, so every module's name is unique: MMS-524)
        self.assertEqual(site_mod.l4_path(self.BASE, secs[0].num).name, "base-agreement-preamble.l4")
        keys = [k for s in secs for k in s.keys()]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(site_mod.citations(secs[0])["preamble/p3"], "פתיח ¶3")

    OZ = "agreements/oz-latmura/2011-08-14_oz-latmura_founding-agreement.xml"

    def test_the_oz_agreement_reads_by_article_and_annex(self):
        """The Oz LaTmura agreement of 14.8.2011 (MMS-569): its preamble,
        63 articles, sign-off, and each of its fourteen annexes a section,
        the annexes under a chapter of their own, cited by their label and
        filed in ASCII; and after them the nine letters it encloses, which
        the corpus gives no label (MMS-588), each a section named by its
        place among them. Sectioning it keeps every row the whole document
        read, in the same order."""
        self.assertFalse(akn.is_whole(self.OZ))
        secs = akn.sections(self.OZ)
        nums = [s.num for s in secs]
        self.assertEqual(nums[:65], ["פתיח", *[str(n) for n in range(1, 64)], "חתימה"])
        annexes, letters = secs[65:79], secs[79:]
        self.assertEqual(len(annexes), 14)
        self.assertTrue(all(s.chapter_eid == "attachments" and s.num.startswith(akn.ANNEX) for s in annexes))
        self.assertEqual(site_mod.l4_path(self.OZ, "נספח א'1").name, "oz-founding-annex-a1.l4")
        self.assertEqual([s.num for s in letters], [f"{akn.LETTER}{n}" for n in range(1, 10)])
        self.assertEqual([s.eid for s in letters], [f"att_{n}" for n in range(15, 24)])
        self.assertEqual(site_mod.l4_path(self.OZ, letters[2].num).name, "oz-founding-letter-3.l4")
        self.assertEqual(site_mod.sec_ref(letters[0]), "מכתב נלווה 1")
        self.assertTrue(letters[0].heading.startswith("מכתב מנכ\"ל משרד החינוך"))
        self.assertEqual(site_mod.sec_ref(annexes[0]), "נספח א'")
        self.assertEqual(site_mod.num_dir(annexes[0].num), "rtl")
        self.assertEqual(site_mod.num_dir("1.7א"), "ltr")
        whole = akn.whole_section(self.OZ)
        self.assertEqual([r.text for r in whole.rows if r.kind == "text"],
                         [r.text for s in secs for r in s.rows if r.kind == "text"])
        keys = [k for s in secs for k in s.keys()]
        self.assertEqual(len(keys), len(set(keys)))

    SEPT_2016 = "agreements/ofek-hadash/2016-09-30_ofek-hadash_september-2016-agreement.xml"

    def test_a_line_between_annexes_is_read_where_the_corpus_sets_it(self):
        """An <attachment> may hold an <interstitial> instead of an annex's
        <doc> (MMS-634, MMS-641): the 30.9.2016 agreement prints the heading
        of the supervisors' tables between annexes 22 and 23 of ב, ג and ד.
        Its line is keyed like any unlabelled element's, by the
        interstitial's eId, and sits between the two annexes' rows."""
        rows = akn.sections(self.SEPT_2016)[0].rows
        keys = [r.key for r in rows]
        for n, (before, after) in enumerate((("att_29", "att_30"), ("att_59", "att_60"),
                                             ("att_89", "att_90")), 1):
            i = keys.index(f"interstitial_{n}__body/p1")
            self.assertEqual(rows[i].text, "טבלאות שכר לעובדי הוראה בתפקידי פיקוח ומטה")
            self.assertEqual(rows[i].aliases, [f"interstitial_{n}__body"])
            self.assertTrue(keys[i - 1].startswith(before + "__"), keys[i - 1])
            self.assertTrue(keys[i + 1].startswith(after + "__"), keys[i + 1])
        self.assertFalse([k for k in keys if k.startswith("attachments/")])


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

    def test_a_row_under_a_printed_path_is_labelled_inside_it(self):
        """A subsection that prints its path from the section ("1.25.1" in
        §1.25) is a level of the label: every row under it is labelled by
        that path and then its own number, never as the section's sibling
        (MMS-657: §1.25.1's third general rule read "§1.25.3", and the
        first paragraph of §1.9.1 read "§1.9.1", the subsection itself)."""
        checked = 0
        for doc in site_mod.DOCUMENTS:
            for sec in akn.sections(doc):
                if not sec.chapter_eid:
                    continue
                own = sec.num.strip().rstrip(".")
                labels = site_mod.citations(sec)
                path = None
                for r in sec.rows:
                    num = r.num.strip().rstrip(".)").lstrip("(")
                    if r.depth == 0:
                        path = num if own and num.startswith(own + ".") else None
                    if path is None:
                        continue
                    label = site_mod.COUNTER.sub("", labels[r.key])
                    with self.subTest(doc=doc, key=r.key):
                        self.assertTrue(label == "§" + path or label.startswith("§" + path + ".")
                                        or label.startswith("§" + path) and not label[len(path) + 1].isdigit(),
                                        f"{label} is not inside §{path}")
                        if r.depth > 0 and num:
                            self.assertNotEqual(label, "§" + path, "a numbered row under it reads as the subsection")
                    checked += 1
        self.assertGreater(checked, 1000)
        # the case the issue named
        sec = next(s for s in akn.sections("takanon/takanon-sherut-ovdei-horaa.xml") if s.num == "1.25")
        self.assertEqual(site_mod.clause(sec, "chp_1ב__sec_1_25__ssec_1_25_1__hc_1__para_3", ""), "§1.25.1.3")


if __name__ == "__main__":
    unittest.main()
