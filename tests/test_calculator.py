"""The salary calculator (calculator.html): its form is read off §1.1's L4,
its evaluator is the committed WebAssembly build, and run in Node on the same
files the page loads it reproduces the worked example 1.1.l4 asserts."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import akn          # noqa: E402
import build_site   # noqa: E402
import calculator   # noqa: E402

L4 = ROOT / "l4/takanon/takanon-sherut-ovdei-horaa/1.1.l4"
WASM = ROOT / "tools/assets/l4wasm"


def spec() -> dict:
    sec = next(s for s in akn.sections(build_site.SALARY[0]) if s.num == build_site.SALARY[1])
    return calculator.spec(sec, L4, build_site.citations(sec))


class Form(unittest.TestCase):
    def test_the_form_is_the_records_fields_and_the_enums_allowances(self):
        s = spec()
        text = L4.read_text(encoding="utf-8")
        self.assertEqual([f["name"] for f in s["fields"]],
                         [f["name"] for f in calculator.record_fields(text.splitlines(), calculator.MONTH_RECORD)])
        kinds, _ = calculator.enum_ctors(text.splitlines(), calculator.ALLOWANCE_ENUM)
        self.assertEqual([k["name"] for k in s["allowance"]["kinds"]], kinds)
        for x in s["fields"] + s["allowance"]["kinds"] + s["components"]:
            self.assertTrue(x["label"] and x["cite"].startswith("§1.1"), x)

    def test_a_fields_citation_says_which_text_and_what_the_clause_is(self):
        """The client, 2026-10-12: "§1.1ב · §1.1ג" alone "tell me nothing".
        A field cites each clause by its own words and its number, under the
        document's name, and links to it."""
        sec = next(s for s in akn.sections(build_site.SALARY[0]) if s.num == build_site.SALARY[1])
        s = calculator.spec(sec, L4, build_site.citations(sec), href=lambda k: "p.html#" + k)
        keys = {r.key for r in sec.rows} | {a for r in sec.rows for a in r.aliases}
        for f in s["fields"]:
            self.assertTrue(f["refs"], f["name"])
            for r in f["refs"]:
                self.assertTrue(r["words"] and r["num"].startswith("§1.1"), r)
                self.assertIn(r["href"].split("#", 1)[1], keys, r)
        html = calculator.form_html(s)
        self.assertEqual(html.count('<span class="cite">בתקנון: '), len(s["fields"]) + 1)
        month = next(f for f in s["fields"] if f["name"] == "month")
        self.assertEqual([r["words"] for r in month["refs"]], ["תוספת 3%", "תוספת 2008", "תוספת 2011"])

    def test_the_components_are_what_the_salary_rule_adds_up(self):
        self.assertEqual([c["name"] for c in spec()["components"]],
                         ["combined salary", "3% supplement", "2008 supplement", "2011 supplement",
                          "1994 supplement", "percentage allowances"])


    def test_a_component_later_circulars_rerate_names_them(self):
        """MMS-514: §1.1 alone gives a month after the later circulars the
        2008 supplement at 5% and the 2011 at 4%; the page marks those lines
        from the month a circular already encoded replaced them, and links it."""
        s = spec()
        names = {c["name"] for c in s["components"]}
        self.assertEqual(set(s["superseded"]), {"2008 supplement", "2011 supplement"})
        for name, sup in s["superseded"].items():
            with self.subTest(component=name):
                self.assertIn(name, names)
                self.assertRegex(sup["from"], r"^\d{4}-\d{2}-01$")
                for b in sup["by"]:
                    self.assertTrue((ROOT / "l4" / b["href"].replace(".html", ".l4")).exists(), b["href"])


class Artefact(unittest.TestCase):
    def test_the_wasm_is_the_pinned_commit_and_patch(self):
        build = tomllib.loads((WASM / "BUILD.toml").read_text(encoding="utf-8"))
        self.assertEqual(build["l4_commit"], (ROOT / "toolchain/L4_COMMIT").read_text().strip())
        patch = ROOT / build["patch"]
        self.assertEqual(build["patch_sha256"], hashlib.sha256(patch.read_bytes()).hexdigest(),
                         "the patch changed: rebuild with toolchain/build-wasm.sh")
        for name, digest in build["files"].items():
            self.assertEqual(hashlib.sha256((WASM / name).read_bytes()).hexdigest(), digest, name)


@unittest.skipUnless(shutil.which("node"), "needs Node")
class WorkedExample(unittest.TestCase):
    """1.1.l4's own example: a full-time teacher in March 2012, combined
    salary 10,000 and a 1994 supplement of 200, is paid 11,432, and 12,575.2
    with class education at 10% (the file #ASSERTs both)."""

    @classmethod
    def setUpClass(cls):
        s = {**spec(), "l4": str(L4.relative_to(ROOT))}
        ex = s["example"]
        cases = [{"fields": ex["fields"], "allowances": []},
                 {"fields": ex["fields"], "allowances": ex["allowances"]},
                 {"fields": {**ex["fields"], "position fraction of the month": "0.5"},
                  "allowances": [{"kind": "class education", "percent": "10"},
                                 {"kind": "MA or PhD degree", "percent": "12.5"}]}]
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "spec.json").write_text(json.dumps(s), encoding="utf-8")
            (Path(d) / "cases.json").write_text(json.dumps(cases), encoding="utf-8")
            p = subprocess.run(["node", str(ROOT / "tests/calc_node.mjs"), f"{d}/spec.json", f"{d}/cases.json"],
                               capture_output=True, text=True, timeout=300)
        if p.returncode:
            raise AssertionError(p.stderr)
        cls.runs = [json.loads(l) for l in p.stdout.splitlines()]

    def test_no_allowances(self):
        r = self.runs[0]
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["total"]["value"], "11432")
        self.assertEqual({c["name"]: c["value"] for c in r["components"]},
                         {"combined salary": "10000", "3% supplement": "300", "2008 supplement": "500",
                          "2011 supplement": "432", "1994 supplement": "200", "percentage allowances": "0"})

    def test_class_education_at_ten_percent(self):
        r = self.runs[1]
        self.assertEqual(r["total"]["value"], "12575.2")
        self.assertEqual([(a["name"], a["rate"], a["value"]) for a in r["allowances"]],
                         [("class education", "10%", "1143.2")])

    def test_half_position(self):
        # class education is paid as for a full position, the MA allowance
        # in proportion: 5,000 + 150 + 250 + 216 + 100 + 1,143.2 + 714.5
        r = self.runs[2]
        self.assertEqual([a["value"] for a in r["allowances"]], ["1143.2", "714.5"])
        self.assertEqual(r["total"]["value"], "7573.7")

    def test_the_trace_is_l4s(self):
        t = self.runs[1]["total"]
        self.assertEqual(t["trace"]["value"], "12575.2")
        self.assertTrue(t["trace"]["steps"][0]["expr"].startswith("`salary of a teaching employee`"))
        self.assertIn("12575.2", t["traceText"])
