"""What the corpus does not hold is stated, not guessed (MMS-538).

A document the corpus holds only in part — its coverage page's "part",
recorded per document in corpus/manifest.json by tools/sync_corpus.py —
has words the L4 cannot read. Its encoding says so: the spans it lacks are
`the text is missing` (l4/lib/vocabulary.l4, `why there is no answer`),
stated once as data, so a rule that reaches into them cannot pass for one
that reads them, and a lacuna cannot be declared where a page is missing.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import build_site  # noqa: E402


class WhatTheCorpusLacksIsStated(unittest.TestCase):

    def test_a_document_held_in_part_states_what_it_lacks(self):
        manifest = json.loads(build_site.MANIFEST.read_text(encoding="utf-8"))["documents"]
        partial = build_site.held_in_part(manifest)
        encoded = [d for d in partial
                   if (ROOT / "l4" / (d.removesuffix(".xml") + ".l4")).exists()]
        for doc in encoded:
            with self.subTest(doc=doc):
                src = (ROOT / "l4" / (doc.removesuffix(".xml") + ".l4")).read_text(encoding="utf-8")
                self.assertIn("`the text is missing`", src)

    def test_the_kinds_of_no_answer_are_declared_once(self):
        vocab = (ROOT / "l4" / "lib" / "vocabulary.l4").read_text(encoding="utf-8")
        for kind in ("the text is silent", "the text is missing", "not yet encoded",
                     "outside the corpus", "set elsewhere"):
            with self.subTest(kind=kind):
                self.assertIn(f"`{kind}`", vocab)


if __name__ == "__main__":
    unittest.main()
