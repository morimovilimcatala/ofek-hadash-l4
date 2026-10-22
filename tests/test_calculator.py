"""The salary calculator (calculator.html): its form is read off §1.1's L4
and the shared vocabulary's case, its evaluator is the committed WebAssembly
build, and run in Node on the same files the page loads it gives the law's
month (l4/lib/salary-root.l4): §1.1's worked example where only the takanon
speaks, and the agreement's 2008 supplement where the agreement governs."""
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
        from the month a circular already encoded replaced them, and links it.
        The 2008 supplement is the root's answer now (MMS-525), not §1.1's,
        and is not marked."""
        s = spec()
        names = {c["name"] for c in s["components"]}
        self.assertEqual(set(s["superseded"]), {"2011 supplement"})
        for name, sup in s["superseded"].items():
            with self.subTest(component=name):
                self.assertIn(name, names)
                self.assertRegex(sup["from"], r"^\d{4}-\d{2}-01$")
                for b in sup["by"]:
                    self.assertTrue((ROOT / "l4" / b["href"].replace(".html", ".l4")).exists(), b["href"])


class Law(unittest.TestCase):
    """MMS-525: what the page asks salary-root, read off it."""

    def test_the_root_answers_the_2008_supplement_and_section_1_1_the_rest(self):
        s = spec()
        self.assertEqual({c["name"]: c["item"] for c in s["components"]},
                         {"combined salary": None, "3% supplement": None,
                          "2008 supplement": "the 2008 public-sector supplement",
                          "2011 supplement": None, "1994 supplement": None, "percentage allowances": None})

    def test_the_month_supplies_four_facts_and_the_form_asks_the_rest(self):
        law = spec()["law"]
        self.assertEqual([f["name"] for f in law["fromMonth"]],
                         ["the salary month", "in a population whose 5% step was put off",
                          "combined salary today", "supplement 2001 today"])
        vocab = calculator.VOCABULARY.read_text(encoding="utf-8").splitlines()
        every = [f["name"] for f in calculator.record_fields(vocab, calculator.CASE_RECORD)]
        self.assertEqual([f["name"] for f in law["fields"]] + [f["name"] for f in law["fromMonth"]],
                         [n for n in every if n not in {f["name"] for f in law["fromMonth"]}]
                         + [f["name"] for f in law["fromMonth"]])
        self.assertEqual(set(law["example"]), {f["name"] for f in law["fields"]})

    def test_every_pay_item_is_asked(self):
        law = spec()["law"]
        vocab = calculator.VOCABULARY.read_text(encoding="utf-8").splitlines()
        self.assertEqual([i["name"] for i in law["items"]], calculator.enum_ctors(vocab, calculator.ITEM_ENUM)[0])
        self.assertTrue(all(i["label"] for i in law["items"]))

    def test_the_page_ships_every_module_without_its_tests(self):
        s = spec()
        with tempfile.TemporaryDirectory() as d:
            shipped = calculator.ship(s, Path(d))
            files = json.loads((Path(d) / shipped["modules"]).read_text(encoding="utf-8"))
        reached = {n for n in calculator.import_closure(calculator.SALARY_ROOT)
                   if calculator.module_file(n, calculator.SALARY_ROOT.parent)}   # not the built-in libraries
        self.assertEqual(set(files), {"salary-root"} | reached)
        for name, text in files.items():
            with self.subTest(module=name):
                self.assertFalse([l for l in text.splitlines() if calculator.DIRECTIVE.match(l)])
                f = calculator.module_file(name, calculator.SALARY_ROOT.parent) or calculator.SALARY_ROOT
                self.assertEqual(len(text.split("\n")), len(f.read_text(encoding="utf-8").split("\n")))


class Artefact(unittest.TestCase):
    def test_the_wasm_is_the_pinned_commit_and_patch(self):
        build = tomllib.loads((WASM / "BUILD.toml").read_text(encoding="utf-8"))
        self.assertEqual(build["l4_commit"], (ROOT / "toolchain/L4_WASM_COMMIT").read_text().strip())
        patch = ROOT / build["patch"]
        self.assertEqual(build["patch_sha256"], hashlib.sha256(patch.read_bytes()).hexdigest(),
                         "the patch changed: rebuild with toolchain/build-wasm.sh")
        for name, digest in build["files"].items():
            self.assertEqual(hashlib.sha256((WASM / name).read_bytes()).hexdigest(), digest, name)


def wasm_runs(runs: list[dict]) -> list[dict]:
    """Each run's answer from one instance of the committed l4.wasm."""
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "runs.json").write_text(json.dumps(runs), encoding="utf-8")
        p = subprocess.run(["node", str(ROOT / "tests/wasm_eval.mjs"), f"{d}/runs.json"],
                           capture_output=True, text=True, timeout=300)
    if p.returncode:
        raise AssertionError(p.stderr)
    return [json.loads(l)["answer"] for l in p.stdout.splitlines()]


V = "DECLARE `box` HAS\n    `contents` IS A NUMBER\n"
A = "IMPORT v\n\nGIVETH A `box`\nDECIDE `a box of one` IS\n    `box` WITH `contents` IS 1\n"
B = "IMPORT v\n\nGIVEN x IS A `box`\nGIVETH A NUMBER\nDECIDE `what is in` x IS\n    x's `contents`{}\n"
MAIN = "IMPORT a\nIMPORT b\n\n#EVAL{} `what is in` `a box of one`\n"


@unittest.skipUnless(shutil.which("node"), "needs Node")
class SharedImport(unittest.TestCase):
    """MMS-535: a module two importers share (v, under a and b) loads in the
    wasm, as every instrument shares the vocabulary under the root; and the
    imports one call resolved are reused by the next only while the modules
    and the names imported are the same."""

    @classmethod
    def setUpClass(cls):
        files = {"v": V, "a": A, "b": B.format("")}
        cls.runs = wasm_runs([
            {"source": MAIN.format(""), "files": files},
            {"source": MAIN.format("TRACE"), "files": files},           # same imports: reused
            {"source": MAIN.format("TRACE"), "files": files},
            {"source": MAIN.format(""), "files": {**files, "b": B.format(" PLUS 1")}},  # b changed
        ])

    def value(self, i: int) -> str:
        r = self.runs[i]
        self.assertTrue(r["success"], r)
        return r["results"][0]["result"].strip()

    def test_the_shared_type_reaches_both_importers(self):
        self.assertEqual(self.value(0), "1")

    def test_a_second_call_on_the_same_imports(self):
        self.assertEqual(self.value(1), "1")
        self.assertIn("what is in", self.runs[1]["results"][0]["traceText"])

    def test_the_trace_is_the_same_on_every_call(self):
        self.assertEqual(self.runs[1]["results"][0]["traceText"], self.runs[2]["results"][0]["traceText"])

    def test_a_changed_module_is_checked_again(self):
        self.assertEqual(self.value(3), "2")


UPPER = {"in post-primary education": True, "in the upper division": True,
         "represented by the secondary teachers' organisation": True}


@unittest.skipUnless(shutil.which("node"), "needs Node")
class WorkedExample(unittest.TestCase):
    """1.1.l4's own example: a full-time teacher in March 2012, combined
    salary 10,000 and a 1994 supplement of 200, is paid 11,432, and 12,575.2
    with class education at 10% (the file #ASSERTs both); a State teacher in
    a primary school, where only the takanon speaks to the 2008 supplement,
    is paid that by the law too. In an upper division, represented by the
    secondary teachers' organisation, the agreement of 24.1.2008 governs the
    2008 supplement: 494.4, and the month 11,426.4
    (l4/tests/salary-root-tests.l4 asserts the same)."""

    @classmethod
    def setUpClass(cls):
        s = spec()
        ex = s["example"]
        cases = [{"fields": ex["fields"], "case": ex["case"], "allowances": []},
                 {"fields": ex["fields"], "case": ex["case"], "allowances": ex["allowances"]},
                 {"fields": {**ex["fields"], "position fraction of the month": "0.5"}, "case": ex["case"],
                  "allowances": [{"kind": "class education", "percent": "10"},
                                 {"kind": "MA or PhD degree", "percent": "12.5"}]},
                 {"fields": ex["fields"], "case": {**ex["case"], **UPPER}, "allowances": []}]
        with tempfile.TemporaryDirectory() as d:
            s = calculator.ship(s, Path(d))
            (Path(d) / "spec.json").write_text(json.dumps(s), encoding="utf-8")
            (Path(d) / "cases.json").write_text(json.dumps(cases), encoding="utf-8")
            p = subprocess.run(["node", str(ROOT / "tests/calc_node.mjs"), f"{d}/spec.json",
                                f"{d}/{s['modules']}", f"{d}/cases.json"],
                               capture_output=True, text=True, timeout=900)
        if p.returncode:
            raise AssertionError(p.stderr)
        cls.runs = [json.loads(l) for l in p.stdout.splitlines()]

    def test_no_allowances(self):
        r = self.runs[0]
        self.assertTrue(r["ok"], r)
        self.assertFalse(r["failed"], r["failed"])
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
        self.assertTrue(t["trace"]["steps"][0]["expr"].startswith("`the salary that governs`"))
        self.assertIn("12575.2", t["traceText"])

    def test_where_only_the_takanon_speaks_it_governs(self):
        it = self.runs[0]["items"]["the 2008 public-sector supplement"]
        self.assertEqual((it["answer"], it["module"], it["modules"], it["contradicted"]),
                         ("500", "takanon-1-1", ["takanon-1-1"], False))

    def test_where_the_agreement_speaks_it_governs(self):
        r = self.runs[3]
        c = next(c for c in r["components"] if c["name"] == "2008 supplement")
        self.assertEqual((c["value"], c["figure"]), ("494.4", "500"))
        self.assertEqual(r["total"]["value"], "11426.4")
        it = r["items"]["the 2008 public-sector supplement"]
        self.assertEqual(it["module"], "2008-01-24_oz-latmura_tosefet-sachar_reform-model")
        self.assertEqual(it["says"], ["500", "494.4"])
        self.assertTrue(it["contradicted"] and it["rule"] and it["title"])

    def test_every_pay_item_is_answered(self):
        names = [i["name"] for i in spec()["law"]["items"]]
        for r in self.runs:
            self.assertEqual(sorted(r["items"]), sorted(names))
            self.assertFalse([k for k, v in r["items"].items() if v["failed"]])
