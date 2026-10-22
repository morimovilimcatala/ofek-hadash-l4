"""The checks the site's claims rest on.

Alignment: every key an L4 file cites is a row of its section, and every
text row of an encoded section is cited (by itself, an alias or an
ancestor) — the denominator is the section's own paragraphs.
Findings: every finding names real rows and is backed by an #ASSERT in the
file it names. Corpus: the snapshot is what SOURCE.toml says it is.
Toolchain: when build/l4 is present, every file checked clean and its
result is not stale.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
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


def views():
    for doc in site_mod.DOCUMENTS:
        for sec in akn.sections(doc):
            yield site_mod.build_view(doc, sec)


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


class Alignment(unittest.TestCase):
    def test_no_l4_file_without_a_section(self):
        known = {site_mod.l4_path(doc, s.num) for doc in site_mod.DOCUMENTS
                 for s in akn.sections(doc)}
        import laws
        statutes = {laws.l4_file(n) for n in laws.all_laws()}
        for f in (ROOT / "l4").rglob("*.l4"):
            if (f.name in ("common.l4", "conventions.l4") or f.name.endswith("-common.l4")
                    or f.parent.name in ("lib", "tests") or f.is_symlink() or f.parent.name == "modules"):
                continue
            if f in statutes:  # a statute outside the corpus: see StatutesOutsideTheCorpus
                continue
            self.assertIn(f, known, f"{f.relative_to(ROOT)} encodes no corpus section")

    def test_every_cited_key_is_a_row_of_its_section(self):
        for v in views():
            if v.src is None:
                continue
            with self.subTest(section=v.section.num):
                self.assertEqual([s.keys for s in v.unplaced], [],
                                 f"§{v.section.num} cites keys that are not in the section")

    def test_every_text_row_of_an_encoded_section_is_cited(self):
        for v in views():
            if v.src is None:
                continue
            with self.subTest(section=v.section.num):
                missing = [r.key for r in v.text_rows if r.key not in v.covered]
                self.assertEqual(missing, [], f"§{v.section.num}: paragraphs no segment cites")


class StatutesOutsideTheCorpus(unittest.TestCase):
    """A statute the L4 encodes though the corpus holds no copy (MMS-516):
    its pinned text and its L4 cite each other section for section."""

    def test_every_section_is_cited_and_every_citation_is_a_section(self):
        import laws
        self.assertTrue(laws.all_laws())
        for name in laws.all_laws():
            with self.subTest(law=name):
                law = laws.load(name)
                nums = [s["num"] for s in law["section"]]
                self.assertEqual(len(nums), len(set(nums)))
                self.assertEqual(laws.cited(name), set(nums))
                _, blocks = laws.blocks(name)
                self.assertEqual(list(blocks), nums, "a §§ block per section, in order")
                for s in law["section"]:
                    self.assertTrue(site_mod.is_hebrew(s["text"]) and s["heading"].strip())
                self.assertTrue(law["url"].startswith("https://he.wikisource.org/wiki/"))

    def test_a_file_that_imports_it_links_to_it(self):
        import laws
        for name in laws.all_laws():
            module = name.replace("-", "_")
            for f in (ROOT / "l4").rglob("*.l4"):
                if f.is_symlink() or f"IMPORT {module}\n" not in f.read_text(encoding="utf-8"):
                    continue
                link = f.parent / f"{module}.l4"
                with self.subTest(file=str(f.relative_to(ROOT))):
                    self.assertTrue(link.is_symlink())
                    self.assertEqual(link.resolve(), laws.l4_file(name).resolve())


class Layout(unittest.TestCase):
    def test_no_continuation_line_regroups_arithmetic(self):
        # a line that begins with an operator takes the rest of the line as
        # its right operand (tools/layout_lint.py); one operand per line
        import layout_lint
        found = [f"{f.relative_to(ROOT)}:{n} {kind}: {t}"
                 for f in sorted((ROOT / "l4").rglob("*.l4"))
                 for n, kind, t in layout_lint.scan(f)]
        self.assertEqual(found, [])

    def test_no_not_runs_on_into_and_or(self):
        # `IF NOT a AND b` is NOT (a AND b) (tools/layout_lint.py's scan_not);
        # it was the tool's alone until a new agreement shipped one
        import layout_lint
        found = [f"{f.relative_to(ROOT)}:{n}: {t}"
                 for f in sorted((ROOT / "l4").rglob("*.l4")) if not f.is_symlink()
                 for n, _, t in layout_lint.scan_not(f)]
        self.assertEqual(found, [])

    def test_no_bare_percentage_is_a_functions_argument(self):
        # `x \`increased by\` 12.5%` computes (x \`increased by\` 12.5)% at
        # the pinned compiler (MMS-510): the argument is written (12.5%)
        import layout_lint
        found = [f"{f.relative_to(ROOT)}:{n}: {t}"
                 for f in sorted((ROOT / "l4").rglob("*.l4")) if not f.is_symlink()
                 for n, _, t in layout_lint.scan_pct(f)]
        self.assertEqual(found, [])

    def test_the_percentage_check_sees_every_shape_that_computes_wrong(self):
        # each of these computed 3.24 for 24 instead of 27 (MMS-510), and
        # each of the second list computes right and is not refused
        import layout_lint
        import tempfile
        wrong = ["    x `increased by` 12.5%",
                 "`h` x MEANS x `inc by` 12.5% PLUS 0",
                 "    IF x EQUALS 24 THEN x `inc by` 12.5% ELSE 0",
                 "`q` x MEANS `grow` x 12.5%",
                 "`r` MEANS `the amount` `inc by` 12.5%",
                 "    `grow` x\n        12.5%"]
        right = ["    x `increased by` (12.5%)",
                 "    x PLUS 12.5%",
                 "    x DIVIDED BY 12.5%",
                 "`rate` MEANS 12.5%",
                 "    IF x AT LEAST 50% THEN 1 ELSE 0",
                 '    BECAUSE "beyond 140%" -- above 150%',
                 "`a teacher at 40%` MEANS 1"]
        for text, n in [(t, 1) for t in wrong] + [(t, 0) for t in right]:
            with self.subTest(text=text), tempfile.TemporaryDirectory() as d:
                f = Path(d) / "x.l4"
                f.write_text(text + "\n", encoding="utf-8")
                self.assertEqual(len(list(layout_lint.scan_pct(f))), n)


class Findings(unittest.TestCase):
    def setUp(self):
        self.findings = site_mod.load_findings()
        self.keys = {}
        for v in views():
            for k in v.section.keys():
                self.keys[(v.doc, k)] = v

    def test_findings_are_well_formed(self):
        ids = [f["id"] for f in self.findings]
        self.assertEqual(len(ids), len(set(ids)))
        for f in self.findings:
            with self.subTest(finding=f["id"]):
                self.assertIn(f["kind"], site_mod.KINDS)
                self.assertIn(f["stage"], site_mod.STAGES)
                self.assertIn(f["review"], site_mod.REVIEW)
                # every finding is graded, and says why (MMS-504)
                self.assertIn(f.get("severity"), site_mod.SEVERITY)
                self.assertTrue(site_mod.is_hebrew(f.get("severity_why", "")))
                for field in ("title", "body", "reading", "l4", "evidence", "keys", "read_by"):
                    self.assertTrue(f.get(field), field)
                for d in f.get("depends_on", []):
                    self.assertIn(d, ids, "depends on a finding that does not exist")
                # a key is a row of the finding's OWN document: every circular
                # has an art_1, so a key alone proves nothing
                for k in f["keys"]:
                    self.assertIn((site_mod.finding_doc(f), k), self.keys)
                self.assertTrue((ROOT / f["l4"]).exists(), f["l4"])

    def test_findings_are_written_in_hebrew(self):
        """The client, 2026-10-11: a finding shown in English "should be
        Hebrew". Its title, body and reading are Hebrew; an L4 identifier in
        backticks stays English and does not count. A sequence arrow points
        left, because the page is right to left."""
        for f in self.findings:
            for field in ("title", "body", "reading"):
                with self.subTest(finding=f["id"], field=field):
                    self.assertTrue(site_mod.is_hebrew(f[field]), "written in English")
                    self.assertNotIn("→", site_mod.IDENT.sub("", f[field]))

    def test_findings_never_cite_a_paragraph_by_our_count(self):
        """A "¶41" is the builder's running count of the unnumbered
        paragraphs in a clause (the /pN of a row key); nothing on the page
        prints it, so a reader cannot find it. A finding names the clause as
        the site labels it and quotes the paragraph's opening words instead.
        (An #ASSERT name in `evidence` is an L4 identifier and is not checked
        here.)"""
        for f in self.findings:
            for field in ("title", "body", "reading"):
                with self.subTest(finding=f["id"], field=field):
                    self.assertNotIn("¶", f[field], "a ¶N reader cannot find on the page")

    def test_every_finding_is_asserted_in_its_file(self):
        for f in self.findings:
            with self.subTest(finding=f["id"]):
                text = (ROOT / f["l4"]).read_text(encoding="utf-8")
                asserts = [l for l in text.splitlines()
                           if l.lstrip().startswith("#ASSERT") and f["evidence"] in l]
                self.assertTrue(asserts, f"no #ASSERT of {f['evidence']} in {f['l4']}")


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

    def test_every_directory_that_imports_it_links_it(self):
        # IMPORT resolves in the directory the file is run in, and a link to a
        # section (takanon-1-11.l4) is run in the link's directory
        for d in {f.parent for f in (ROOT / "l4").rglob("*.l4") if f.resolve() != self.MODULE.resolve()
                  and re.search(r"^IMPORT conventions$", f.read_text(encoding="utf-8"), re.M)}:
            with self.subTest(dir=str(d.relative_to(ROOT))):
                link = d / "conventions.l4"
                self.assertTrue(link.is_symlink(), "no conventions.l4 link")
                self.assertEqual(link.resolve(), self.MODULE.resolve())

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


# Type names declared in more than one module (test_a_type_name_is_declared_once):
# each is a pair the compiler will refuse to import into one file.
DECLARED_MORE_THAN_ONCE = 294


class OneNamespace(unittest.TestCase):
    """EVERY L4 MODULE HAS ONE NAME, AND IS REACHABLE BY IT FROM ANY FILE
    (the client, 2026-10-21, MMS-524: "go with unique names"). The pinned
    compiler finds an import by its bare file name, so two files under one
    name would make an import ambiguous, and l4/modules/, on every run's
    library path, is what lets a file import a module in another directory."""

    def test_no_two_files_share_a_name_and_l4_modules_matches_the_tree(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import modules
        self.assertEqual(modules.problems(), [],
                         "run python3 tools/modules.py --write (or rename the clashing file)")

    def test_a_type_name_is_declared_once(self):
        """Two modules declaring the same type name cannot be imported into
        one file: the compiler refuses "multiple definitions for the
        identifier". `Party` was six declarations and is one module now
        (l4/lib/parties.l4, MMS-532). The rest of the class is the yearly
        circulars, each re-declaring its series' types; the single entry
        point (MMS-521) has to import them together, so this count is a
        ratchet, held exactly, and only ever lowered."""
        declared = {}
        for f in (ROOT / "l4").rglob("*.l4"):
            if f.is_symlink() or "modules" in f.parts:
                continue
            for m in re.finditer(r"^DECLARE\s+(`[^`]+`|\w+)", f.read_text(encoding="utf-8"), re.M):
                declared.setdefault(m.group(1), []).append(f)
        self.assertEqual([f.relative_to(ROOT).as_posix() for f in declared["Party"]], ["l4/lib/parties.l4"])
        self.assertEqual(sum(1 for files in declared.values() if len(files) > 1), DECLARED_MORE_THAN_ONCE)

    def test_a_sectioned_documents_files_carry_its_prefix(self):
        for doc, prefix in akn.MODULE_PREFIX.items():
            d = ROOT / "l4" / doc.removesuffix(".xml")
            real = [f for f in d.glob("*.l4") if not f.is_symlink()]
            self.assertTrue(real)
            self.assertEqual([f.name for f in real if not f.name.startswith(prefix)], [])


class Toolchain(unittest.TestCase):
    def test_the_gate_refuses_a_compiler_warning_about_the_file(self):
        # the compiler's own `ok` stays true on a warning; the gate does not
        # (tools/l4run.py's verdict). An import's warning is its own file's.
        import l4run
        warn = {"severity": "warning", "file": "a.l4", "range": "1:1-1:2",
                "message": "AND and OR operators appear at the same indentation level"}
        held = {"kind": "assertion", "value": "TRUE"}
        self.assertTrue(l4run.verdict({"ok": True, "results": [held], "diagnostics": []}, "a.l4"))
        self.assertFalse(l4run.verdict({"ok": True, "results": [held], "diagnostics": [warn]}, "a.l4"))
        self.assertTrue(l4run.verdict({"ok": True, "results": [held], "diagnostics": [warn]}, "b.l4"))
        self.assertFalse(l4run.verdict({"ok": True, "results": [{"kind": "assertion", "value": "FALSE"}],
                                        "diagnostics": []}, "a.l4"))

    def test_every_file_checks_and_every_assert_holds(self):
        import l4run
        for f in l4run.files():
            if l4run.is_a_root_or_its_tests(f) and not l4run.roots_checked():
                continue  # checked on demand: `make roots`
            out = l4run.outputs(f)
            with self.subTest(file=str(f.relative_to(ROOT))):
                self.assertTrue(out["run"].exists(), "not run")
                data = json.loads(out["run"].read_text(encoding="utf-8"))
                self.assertTrue(data.get("ok"), data.get("diagnostics"))
                stale = out["key"].read_text() != l4run.key(f, l4run.compiler_id(l4run.compiler()))
                self.assertFalse(stale, "build/l4 is stale for this file: run `make l4`")


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


def _quote_text(s: str) -> str:
    """Whitespace-normalised, and NFC so that two spellings of one pointed
    letter (the takanon's "מרַכֵּז") compare as the same text."""
    return " ".join(unicodedata.normalize("NFC", s).replace("​", "").split())


def _row_text(r) -> str:
    """A row as a quote copies it: its number, its heading, then its text; a
    table's cells joined by " | " and its rows by " ‖ "."""
    body = (" ‖ ".join(" | ".join(c) for c in r.cells) if r.cells is not None else r.text)
    return _quote_text(" ".join(x for x in (r.num, r.heading, body) if x))


# The findings whose quote is not, today, in the rows their keys cite — each
# with the issue it waits on. Exact in both directions: a quote that starts
# to match goes red here until its line is removed. Never add a line to make
# the check pass; a quote we got wrong is fixed in the finding.
MISQUOTED = {
    # The corpus prints the sentence damaged, the quote is the page's: a
    # number or a sign moved by the RTL extraction (MMS-426, which MMS-478
    # was folded into; its bullet half shipped in the corpus's bfacfc2).
    "F-2008-09_tashsat_09-b": "MMS-426",
    "F-2019-20_tashaf_08-b": "MMS-426",
}


class FindingQuotes(unittest.TestCase):
    """A finding's `quote` is the Hebrew words at issue, verbatim from the
    corpus (MMS-477). Each passage (separated by " · ") must appear in the
    text of the rows the finding's keys cite — a key citing its row and the
    rows nested under it, as a cited ancestor covers its descendants in the
    coverage test — with "…" (or "...") marking an elision. Nothing else is
    forgiven: not a dropped footnote mark, not a repaired word order."""

    def test_every_quote_is_in_the_rows_it_cites(self):
        # per document, every row in reading order under each name it has
        rows: dict[str, list[tuple[int, str, object]]] = {}
        for doc in site_mod.DOCUMENTS:
            n = 0
            for sec in akn.sections(doc):
                for r in sec.rows:
                    n += 1
                    rows.setdefault(doc, []).extend((n, k, r) for k in [r.key] + r.aliases)
        failing = set()
        for f in site_mod.load_findings():
            doc = site_mod.finding_doc(f)
            cited = {}
            for k in f["keys"]:
                for n, kk, r in rows.get(doc, []):
                    if kk == k or kk.startswith(k + "/") or kk.startswith(k + "__"):
                        cited[n] = r
            hay = " ".join(_row_text(cited[n]) for n in sorted(cited))
            for part in f["quote"].split(" · "):
                for frag in re.split(r"…|\.\.\.", part):
                    if _quote_text(frag) and _quote_text(frag) not in hay:
                        failing.add(f["id"])
        self.assertEqual(sorted(failing), sorted(MISQUOTED))
        for fid, issue in MISQUOTED.items():
            self.assertRegex(issue, r"^MMS-\d+$", fid)


class FindingPlacement(unittest.TestCase):
    def test_a_page_shows_only_its_own_documents_findings(self):
        site_mod.FINDINGS_BY_KEY.clear()
        for f in site_mod.load_findings():
            for k in f["keys"]:
                site_mod.FINDINGS_BY_KEY.setdefault((site_mod.finding_doc(f), k), []).append(f)
        for (doc, _), fs in site_mod.FINDINGS_BY_KEY.items():
            for f in fs:
                self.assertEqual(site_mod.finding_doc(f), doc, f["id"])
        # and every finding is flagged on a row of its own document's page
        flagged = {f["id"] for v in views() for r in v.section.rows for f in site_mod.row_findings(v, r)}
        self.assertEqual(flagged, {f["id"] for f in site_mod.load_findings()})
        self.assertEqual(site_mod.finding_doc({"l4": "l4/circulars/2019-20_tashaf_01.l4"}),
                         "circulars/2019-20_tashaf_01.xml")
        self.assertEqual(site_mod.finding_doc({"l4": "l4/takanon/takanon-sherut-ovdei-horaa/1.7.l4"}),
                         "takanon/takanon-sherut-ovdei-horaa.xml")
        # the department's home page is "…gov.il.xml" and its other pages
        # sit in "…gov.il/": a finding on the Q&A is the Q&A's, not the home page's
        self.assertEqual(site_mod.finding_doc(
            {"l4": "l4/takanon/terms-service.education.gov.il/questions-and-answers.l4"}),
            "takanon/terms-service.education.gov.il/questions-and-answers.xml")


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


if __name__ == "__main__":
    unittest.main()
