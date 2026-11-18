"""Every finding card carries a button that copies a link to it (the client,
2026-11-18: "can you add a copy link to finding button?"). The link is the
page's own address with the card's id, which site.js opens on arrival."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_site  # noqa: E402

PAGE = build_site.OUT / "findings.html"


@unittest.skipUnless(PAGE.exists(), "run `make site` first")
class EveryFindingCopiesItsLink(unittest.TestCase):
    def test_each_card_has_a_button_naming_its_own_id(self):
        html = PAGE.read_text(encoding="utf-8")
        # a card nests the trace's own <details>, so a card runs to the next card
        cards = html.split('<details class="finding" id="')[1:]
        self.assertTrue(cards)
        for card in cards:
            fid = card.split('"', 1)[0]
            with self.subTest(finding=fid):
                self.assertIn(f'class="copy-link" data-id="{fid}"', card.split("</section>", 1)[0])

    def test_the_script_copies_the_address_with_the_id(self):
        js = (ROOT / "tools" / "assets" / "site.js").read_text(encoding="utf-8")
        self.assertIn('closest("button.copy-link")', js)
        self.assertIn('"#" + encodeURIComponent(b.dataset.id)', js)


if __name__ == "__main__":
    unittest.main()
