"""The findings page's edge cases (MMS-534): each is proved by the L4. Its
`asserts` are values its file #ASSERTs, and the page shows every case."""
import re
import sys
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

CASES = tomllib.loads((ROOT / "data" / "edge_cases.toml").read_text(encoding="utf-8"))["case"]


class EveryEdgeCaseIsAsserted(unittest.TestCase):
    def test_each_named_value_is_asserted_in_its_file(self):
        self.assertTrue(CASES)
        ids = [c["id"] for c in CASES]
        self.assertEqual(len(ids), len(set(ids)))
        for c in CASES:
            text = (ROOT / c["l4"]).read_text(encoding="utf-8")
            asserted = re.findall(r"^#ASSERT .*$", text, re.M)
            with self.subTest(case=c["id"]):
                self.assertTrue(c["asserts"])
                for name in c["asserts"]:
                    self.assertTrue(any(f"`{name}`" in line for line in asserted),
                                    f"{c['l4']} does not #ASSERT `{name}`")
                for k in ("title", "question", "answer", "why"):
                    self.assertTrue(re.search("[\u05d0-\u05ea]", c[k]), k)

    def test_a_named_contradiction_is_a_card(self):
        import json
        cards = {c["id"] for c in json.loads((ROOT / "data" / "contradictions.json").read_text(encoding="utf-8"))["items"]}
        for c in CASES:
            if c.get("contradiction"):
                self.assertIn(c["contradiction"], cards)

    def test_the_findings_page_shows_every_case(self):
        import build_site
        html, side = build_site.edge_cases_html({})
        self.assertIn('id="edge-cases"', html)
        self.assertIn("#edge-cases", side)
        for c in CASES:
            self.assertIn(f'id="{c["id"]}"', html)


if __name__ == "__main__":
    unittest.main()
