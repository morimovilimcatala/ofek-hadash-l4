"""The conventions register and the one conventions module: every ambiguity
follows a convention, and no file keeps its own copy of one.
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


@unittest.skipUnless((ROOT / "build/l4").exists(), "run `make l4` first")
class Conventions(unittest.TestCase):
    """conventions.toml (MMS-485): the rules of reading the encoding follows
    where the text does not decide. Each names the rules that apply it, and
    each such rule is a definition in the file named — so the page cannot
    describe a rule that was renamed or removed."""

    HEBREW = re.compile(r"[\u0590-\u05FF]")

    def setUp(self):
        self.reg = site_mod.load_conventions()
        self.relied_on = {f.get("convention") for f in site_mod.load_findings()}

    def defines(self, path: str, name: str) -> bool:
        text = (ROOT / path).read_text(encoding="utf-8")
        n = re.escape(name)
        # a DECIDE may put its first parameter before the name ("DECIDE d `is on
        # or after` e"); a record field is a definition too, and so is a
        # section GIVEN's input (what ASSUME declared until l4-ide retired it)
        return bool(re.search(rf"^(?:DECIDE\s+(?:\w+\s+)?`{n}`|`{n}`\s+MEANS|DECLARE\s+`{n}`|ASSUME\s+`{n}`)"
                              rf"|^\s+(?:GIVEN\s+)?`{n}`\s+IS AN?\s", text, re.M))

    def test_the_register_is_well_formed(self):
        groups = [g["id"] for g in self.reg.get("group", [])]
        self.assertEqual(len(groups), len(set(groups)))
        ids = [st["id"] for st in self.reg.get("convention", [])]
        self.assertEqual(len(ids), len(set(ids)))
        for st in self.reg.get("convention", []):
            with self.subTest(convention=st["id"]):
                self.assertIn(st["group"], groups)
                self.assertIn(st["basis"], site_mod.BASIS)
                for field in ("title", "value", "detail"):
                    self.assertRegex(st[field], self.HEBREW, f"{field} is shown on a Hebrew page")
                # a convention nothing applies is a claim about nothing: it names
                # the rules that apply it, or findings name it as their reading's,
                # or the corpus places that apply it
                self.assertTrue(st.get("applies") or st["id"] in self.relied_on
                                or st.get("corpus"),
                                "no rule applies it, no finding relies on it, no corpus place")
                # a pick put to the lawyer names the issue that asks him
                # (the client, 2026-10-17)
                if "lawyer" in st:
                    self.assertRegex(st["lawyer"], r"^MMS-\d+$")
                for place in st.get("corpus", []):
                    self.assertRegex(place["doc"], r"^[\w./-]+\.xml$")
                    self.assertRegex(place.get("how", ""), self.HEBREW, "a corpus place says how")
                    self.assertRegex(place.get("name", "א"), self.HEBREW)

    def test_every_ambiguity_follows_a_convention(self):
        """The client, 2026-10-14: "all ambiguities decisions should follow a
        convention". A finding of kind `ambiguity` names, in `convention`, the
        convention its reading applies; a reading decided case by case is the
        thing this refuses. Any other finding that names one names a real one."""
        known = {st["id"] for st in self.reg.get("convention", [])}
        for f in site_mod.load_findings():
            with self.subTest(finding=f["id"]):
                if f["kind"] == "ambiguity":
                    self.assertTrue(f.get("convention"), "an ambiguity's reading follows no convention")
                if f.get("convention"):
                    self.assertIn(f["convention"], known)

    def test_every_rule_it_names_is_defined_where_it_says(self):
        for st in self.reg.get("convention", []):
            for a in st.get("applies", []) + st.get("exceptions", []):
                with self.subTest(convention=st["id"], l4=a["l4"], rule=a.get("rule")):
                    self.assertTrue((ROOT / a["l4"]).exists())
                    if a.get("rule"):
                        self.assertTrue(self.defines(a["l4"], a["rule"]), "no such definition")
            for e in st.get("exceptions", []):
                with self.subTest(convention=st["id"], exception=e["l4"]):
                    self.assertRegex(e["value"], self.HEBREW)
                    self.assertTrue(e.get("why"), "an exception says why it differs")


class ConventionsModule(unittest.TestCase):
    """l4/conventions.l4 (MMS-488): each convention that is a computation is
    one definition there, named by the convention's `code` and pinned by its
    own #ASSERTs, and rules that apply it call it. The client asked
    whether the conventions "get l4 code, or are they only prose"; before
    this the half-up "to the agora" was defined fifteen times, once per
    circular, and `is on or after` sixteen. A copy can drift from the
    convention it claims to apply, so the copies may not grow back."""

    MODULE = ROOT / "l4/conventions.l4"
    # the hand-written forms of what the module defines: L4's ROUND takes a
    # half to the even neighbour, which is not rounding.half, and the TRUNC
    # and FLOOR idioms are the module's rounding written out again
    IDIOMS = {
        "ROUND": re.compile(r"\bROUND\b"),
        "half up to the agora": re.compile(r"\bTRUNC \(.*PLUS 0\.005\) 2\b"),
        "half up to a whole": re.compile(r"\bTRUNC \(.*PLUS 0\.5\) 0\b|\bFLOOR \(.*PLUS 0\.5\)"),
    }

    def setUp(self):
        self.reg = site_mod.load_conventions()
        self.text = self.MODULE.read_text(encoding="utf-8")
        self.names = site_mod.module_names(self.text)
        self.files = {f: f.read_text(encoding="utf-8") for f in sorted((ROOT / "l4").rglob("*.l4"))
                      if not f.is_symlink() and f != self.MODULE}

    @staticmethod
    def definitions(text: str) -> dict[str, str]:
        """Each name a file defines, and its definition's paragraph."""
        out = {}
        for m in re.finditer(r"^(?:DECIDE\s+(?:\w+\s+)?`([^`]+)`|`([^`]+)`\s+MEANS)[^\n]*(?:\n(?!\s*\n)[^\n]*)*",
                             text, re.M):
            out.setdefault(m.group(1) or m.group(2), m.group())
        return out

    def test_there_is_one_conventions_module_and_one_name_for_it(self):
        # every file imports it through l4/modules/ (MMS-776): no directory
        # keeps a conventions.l4 of its own, link or copy
        self.assertEqual([f.relative_to(ROOT).as_posix() for f in (ROOT / "l4").rglob("conventions.l4")
                          if f.parent.name != "modules"], ["l4/conventions.l4"])
        self.assertEqual((ROOT / "l4/modules/conventions.l4").resolve(), self.MODULE.resolve())
        self.assertTrue(any(re.search(r"^IMPORT conventions$", t, re.M) for t in self.files.values()))

    def test_a_computed_convention_names_its_definitions(self):
        known = {st["id"] for st in self.reg.get("convention", [])}
        for st in self.reg.get("convention", []):
            for name in st.get("code", []):
                with self.subTest(convention=st["id"], name=name):
                    self.assertIn(name, self.names, "not defined in l4/conventions.l4")
        # and a section of the module is headed by the convention it encodes
        for sec in re.findall(r"^§§ `([^`]+)`", self.text, re.M):
            if "." in sec:
                self.assertIn(sec, known, f"§§ {sec} heads no convention")

    def test_no_file_keeps_its_own_copy(self):
        copies = [f"{f.relative_to(ROOT)}: {n}" for f, text in self.files.items()
                  for n in self.names if n in self.definitions(text)]
        self.assertEqual(copies, [], "defined in l4/conventions.l4: IMPORT conventions and call it")

    def test_no_file_writes_the_module_out_by_hand(self):
        found = []
        for f, text in self.files.items():
            for n, line in enumerate(text.split("\n"), 1):
                code = line.split("--")[0]
                for kind, pat in self.IDIOMS.items():
                    if pat.search(code):
                        found.append(f"{f.relative_to(ROOT)}:{n} {kind}: {line.strip()}")
        self.assertEqual(found, [])

    def test_every_definition_in_the_module_is_called(self):
        for n in self.names:
            with self.subTest(name=n):
                self.assertTrue(any(f"`{n}`" in t for t in self.files.values()), "nothing calls it")

    def calls(self, path: str, rule: str, code: list[str]) -> bool:
        """Whether `rule` in `path` calls one of `code`, itself or through
        rules of its own file."""
        defs = self.definitions((ROOT / path).read_text(encoding="utf-8"))
        seen, todo = set(), [rule]
        while todo:
            r = todo.pop()
            if r in seen or r not in defs:
                continue
            seen.add(r)
            if any(f"`{n}`" in defs[r] for n in code):
                return True
            todo += [x for x in defs if x != r and f"`{x}`" in defs[r]]
        return False

    def test_a_computed_convention_is_the_code_its_rules_run(self):
        """A convention with `code` is applied by at least one of the rules it
        names calling that code — so what the page shows beside the prose is
        what the rules run, not a description of it. (Not every rule it
        names calls it: a table that rows share is read by
        thresholds.shared-bound's code and thresholds.until's alike, where
        the two agree; a rule that applies one in data, such as a band
        printed to 65 and 11 months, has nothing to call.)"""
        for st in self.reg.get("convention", []):
            code = st.get("code", [])
            if code:
                with self.subTest(convention=st["id"]):
                    self.assertTrue(any(self.calls(a["l4"], a["rule"], code) for a in st.get("applies", [])),
                                    f"no rule it names calls {code}")


if __name__ == "__main__":
    unittest.main()
