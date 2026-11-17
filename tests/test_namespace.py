"""One codebase, one namespace (MMS-524, MMS-612, MMS-775): every module has
one name, a name is declared once where one import reaches both, and an
agreement stands on its own rules.
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


# Type names declared in more than one module (test_a_type_name_is_declared_once):
# each is a pair the compiler will refuse to import into one file.
DECLARED_MORE_THAN_ONCE = 0

# Constructor names (the cases of a `DECLARE … IS ONE OF`) declared in more
# than one module (test_a_constructor_name_is_declared_once). Two of them
# imported into one file compile while the type around each use decides
# which is meant, and fail "multiple definitions" where it does not.
CONSTRUCTOR_DECLARED_MORE_THAN_ONCE = 0

_NAME = re.compile(r"`[^`]+`|[A-Za-z_][\w']*")


def constructors(text: str) -> list[str]:
    """Every constructor a file declares: the names after `IS ONE OF` on
    its own line, or the lines indented one step under it (a `HAS` after a
    name, a deeper field line, a comment or an `@ref`/`@desc` is not one)."""
    out: list[str] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        m = re.match(r"^DECLARE\s.*?\bIS ONE OF\b(.*)$", lines[i])
        i += 1
        if not m:
            continue
        if m.group(1).strip():
            out += _NAME.findall(m.group(1))
            continue
        step = None
        while i < len(lines):
            line = lines[i]
            s = line.strip()
            if s and not s.startswith("--"):
                indent = len(line) - len(line.lstrip())
                if indent == 0:
                    break
                step = step or indent
                if indent == step and not s.startswith("@"):
                    out.append(_NAME.match(s).group(0))
            i += 1
    return out


# The scoped check (MMS-612), test_no_name_is_declared_twice_where_one_import_reaches_both.
# Names declared in more than one module that one module of the scope
# imports together, outside the chain: each a use away from "multiple
# definitions". Identifiers are type and value names; constructors are counted
# apart, as above.
SCOPED_IDENTIFIERS_DECLARED_TWICE = 0
SCOPED_CONSTRUCTORS_DECLARED_TWICE = 0

# The same count over the scope the roots will reach once each collection's
# root imports its whole collection (MMS-538, MMS-775): every module of
# l4/circulars/, of each family under l4/agreements/ (the framework
# agreements' family included, MMS-538's root of their own) and of the
# takanon, with what each imports. Each name counted is a use away from
# "multiple definitions" in a whole-collection root; MMS-775 brought both
# to zero before the roots import whole collections.
FULL_SCOPE_IDENTIFIERS_DECLARED_TWICE = 0
FULL_SCOPE_CONSTRUCTORS_DECLARED_TWICE = 0

_DEF_LINE = re.compile(r"^(?:DECIDE\s+[A-Za-z_][\w']*\s+(`[^`]+`)"
                       r"|DECIDE\s+(`[^`]+`|[A-Za-z_][\w']*)"
                       r"|(`[^`]+`|[A-Za-z_][\w']*)\s+MEANS\b"
                       r"|DECLARE\s+(`[^`]+`|[A-Za-z_][\w']*))", re.M)


def declared_names(text: str) -> dict[str, bool]:
    """Every top-level name a file declares — a type, a value (a DECIDE, an
    infix DECIDE's backticked name, a MEANS) or a constructor — and whether
    it is a constructor there. A local (an indented WHERE) is not one."""
    out = {m.group(m.lastindex): False for m in _DEF_LINE.finditer(text)}
    for c in constructors(text):
        out.setdefault(c, True)
    return out


def import_graph() -> tuple[dict[str, Path], dict[Path, list[Path]]]:
    """{module name: file} and {file: the files it imports}, through the one
    namespace l4/modules/ gives every name (tools/modules.py)."""
    import modules
    names, _ = modules.wanted()
    files = set(names.values())
    graph = {f: [names[i] for i in re.findall(r"^IMPORT\s+`?([^`\s]+)`?", f.read_text(encoding="utf-8"), re.M)
                 if i in names] for f in files}
    return names, graph


def collection_graph(graph: dict[Path, list[Path]]) -> tuple[dict[Path, list[Path]], list[Path]]:
    """The import graph with each collection root importing its whole
    collection (FULL_SCOPE_*), and the roots it starts from. The framework
    agreements have no root on main yet; a stand-in node is their family's."""
    lib, l4 = ROOT / "l4/roots", ROOT / "l4"

    def real(d: Path) -> list[Path]:
        # a collection's documents and the modules it shares (l4/shared/,
        # MMS-776), which are the collection's too
        shared = l4 / "shared" / d.relative_to(l4)
        return sorted(f.resolve() for f in [*d.rglob("*.l4"), *shared.rglob("*.l4")] if not f.is_symlink())

    g = {k: list(v) for k, v in graph.items()}
    g[(lib / "circulars-root.l4").resolve()] += real(l4 / "circulars")
    g[(lib / "takanon-root.l4").resolve()] += real(l4 / "takanon")
    families = {d.name: d for d in sorted((l4 / "agreements").iterdir()) if d.is_dir()}
    roots = sorted(f.resolve() for f in lib.glob("*root.l4"))
    for name, d in families.items():
        root = lib / f"{name}-root.l4"
        if not root.exists():
            root = lib / f"{name}-agreements-root.l4"
        root = root.resolve() if root.exists() else root
        if root not in g:
            g[root] = []
            g[(lib / "agreements-root.l4").resolve()].append(root)
            roots.append(root)
        g[root] += real(d)
    for targets in list(g.values()):
        for t in targets:
            g.setdefault(t, [])
    return g, roots


def names_declared_twice(graph: dict[Path, list[Path]], decl: dict[Path, dict[str, bool]],
                         scope: set[Path]) -> dict[str, set[Path]]:
    """{name: the modules declaring it} for every name two modules declare
    that one module of `scope` reaches together."""
    twice: dict[str, set[Path]] = {}
    for m in scope:
        by: dict[str, set[Path]] = {}
        for f in reach(graph, m):
            for n in decl[f]:
                by.setdefault(n, set()).add(f)
        for n, fs in by.items():
            if len(fs) > 1:
                twice.setdefault(n, set()).update(fs)
    return twice


def tables_modules() -> list[Path]:
    """The tables collection's modules: its tables and the modules they share
    (l4/shared/tables/, MMS-776)."""
    return sorted(f.resolve() for d in (ROOT / "l4/tables", ROOT / "l4/shared/tables")
                  for f in d.rglob("*.l4"))


def reach(graph: dict[Path, list[Path]], start: Path) -> set[Path]:
    seen, todo = set(), [start]
    while todo:
        f = todo.pop()
        if f not in seen:
            seen.add(f)
            todo += graph.get(f, [])
    return seen


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
        (l4/lib/parties.l4, MMS-532), and a type another module declares
        too carries its document's name (MMS-775). The single entry point
        (MMS-521) imports them together, so this count is a ratchet, held
        exactly, and only ever lowered."""
        declared = {}
        for f in (ROOT / "l4").rglob("*.l4"):
            if f.is_symlink() or "modules" in f.parts:
                continue
            for m in re.finditer(r"^DECLARE\s+(`[^`]+`|\w+)", f.read_text(encoding="utf-8"), re.M):
                declared.setdefault(m.group(1), []).append(f)
        self.assertEqual([f.relative_to(ROOT).as_posix() for f in declared["Party"]], ["l4/lib/parties.l4"])
        self.assertEqual(sum(1 for files in declared.values() if len(files) > 1), DECLARED_MORE_THAN_ONCE)

    def test_a_constructor_name_is_declared_once(self):
        """The same, for the names a type is ONE OF. `the State` was a
        `Party` (l4/lib/parties.l4) and a Budget Foundations Law `employing
        body` both, and imports are transitive, so a file that imported the
        2011 framework agreement (which imports the law) and named a party
        could not be written (MMS-603). The law's is `the State as an
        employing body` now. The modules every collection reaches — the
        shared vocabulary under l4/lib/ and the statutes under l4/laws/ —
        declare no constructor any other module declares; across the rest,
        the count is a ratchet, held exactly, and only ever lowered."""
        declared: dict[str, set[str]] = {}
        for f in (ROOT / "l4").rglob("*.l4"):
            if f.is_symlink() or "modules" in f.parts:
                continue
            for c in constructors(f.read_text(encoding="utf-8")):
                declared.setdefault(c, set()).add(f.relative_to(ROOT).as_posix())
        shared = ("l4/lib/", "l4/laws/")
        self.assertEqual(sorted(c for c, files in declared.items()
                                if sum(f.startswith(shared) for f in files) > 1), [])
        self.assertEqual(sum(1 for files in declared.values() if len(files) > 1),
                         CONSTRUCTOR_DECLARED_MORE_THAN_ONCE)

    FOUNDING = "2007-09-10_ofek-hadash_reform-founding-agreement"
    # where the chain starts: base §47 imports the agreement of 21.2.2008,
    # and the agreement of 24.11.2010 (which the completion agreement of
    # 29.2.2012 imports) the deferral of 17.6.2009, each of which imports
    # the founding agreement
    CHAIN_STARTS = ("base-agreement-47", "2010-11-24_teachers_wage-update-advancement")

    def test_no_name_is_declared_twice_where_one_import_reaches_both(self):
        """Imports are transitive, so a module that imports one module
        imports every name that one reaches. The scope is every module a
        root (l4/roots/*root.l4), the chain or a module of the tables
        collection (l4/tables/ and l4/shared/tables/, which any instrument that prices a cell
        imports: MMS-616) reaches; within it, two modules
        that one import reaches together and that declare the same name fail
        "multiple definitions" wherever a use does not fix the type (MMS-612:
        the founding agreement of 10.9.2007 reused ~214 of the base
        agreement's names on purpose, and base §47 reaches both, so the
        completion agreement could not import the agreement of 24.11.2010).
        THE CHAIN — the modules on an import path from base §47 or from
        24.11.2010 down to the founding agreement — declares no name that
        any module it is imported with declares; across the rest of the
        scope, the names declared twice are a ratchet, held exactly, and
        only ever lowered."""
        names, graph = import_graph()
        decl = {f: declared_names(f.read_text(encoding="utf-8")) for f in graph}
        founding = names[self.FOUNDING]
        starts = [names[s] for s in self.CHAIN_STARTS]
        roots = sorted((ROOT / "l4/roots").glob("*root.l4"))
        self.assertTrue(roots)
        tables = tables_modules()
        self.assertTrue(tables)
        self.assertTrue(all(f in graph for f in tables))
        scope = set().union(*(reach(graph, s) for s in [*roots, *starts, *tables]))
        chain = {f for s in starts for f in reach(graph, s) if founding in reach(graph, f)}
        self.assertEqual({f.name.removesuffix(".l4") for f in chain},
                         {"base-agreement-47", "2008-02-21_teachers_tosefet-2008_wage-supplement",
                          "2009-06-17_teachers_wage-update-deferral",
                          "2010-11-24_teachers_wage-update-advancement", self.FOUNDING})
        twice = names_declared_twice(graph, decl, scope)
        in_chain = sorted(f"{n}: {', '.join(sorted(f.name for f in fs))}"
                          for n, fs in twice.items() if fs & chain)
        self.assertEqual(in_chain, [])
        rest = {n: fs for n, fs in twice.items() if not fs & chain}
        ctor = {n for n, fs in rest.items() if all(decl[f][n] for f in fs)}
        self.assertEqual(len(rest) - len(ctor), SCOPED_IDENTIFIERS_DECLARED_TWICE)
        self.assertEqual(len(ctor), SCOPED_CONSTRUCTORS_DECLARED_TWICE)

    def test_names_declared_twice_where_whole_collections_are_imported(self):
        """The scoped count above, over the graph a whole-collection root
        reaches (collection_graph): all of l4/circulars/, each family of
        agreements, the takanon. A name two circulars declare with different
        meanings carries its document (`… of circular תשפ"ד/3`); a name with
        one meaning is declared once and imported (MMS-775). A ratchet, held
        exactly, and only ever lowered."""
        names, graph = import_graph()
        graph, roots = collection_graph(graph)
        decl = {f: declared_names(f.read_text(encoding="utf-8")) if f.exists() else {} for f in graph}
        starts = [names[s] for s in self.CHAIN_STARTS]
        tables = tables_modules()
        scope = set().union(*(reach(graph, s) for s in [*roots, *starts, *tables]))
        self.assertTrue({f for f in graph if f.parent == (ROOT / "l4/circulars").resolve()} <= scope)
        twice = names_declared_twice(graph, decl, scope)
        ctor = {n for n, fs in twice.items() if all(decl[f][n] for f in fs)}
        self.assertEqual(len(twice) - len(ctor), FULL_SCOPE_IDENTIFIERS_DECLARED_TWICE)
        self.assertEqual(len(ctor), FULL_SCOPE_CONSTRUCTORS_DECLARED_TWICE)

    def test_the_name_reader_sees_every_shape(self):
        src = ("DECIDE `a` x IS 1\nDECIDE d `is on or after` e IF TRUE\nb MEANS 2\n`c` MEANS 3\n"
               "DECLARE `t` IS ONE OF `k`, l\nGIVEN x IS A NUMBER\nDECIDE f x IS\n    y\n    WHERE\n"
               "        z MEANS 4\n")
        self.assertEqual(declared_names(src), {"`a`": False, "`is on or after`": False, "b": False,
                                               "`c`": False, "`t`": False, "f": False,
                                               "`k`": True, "l": True})

    def test_the_constructor_reader_sees_every_shape(self):
        src = ("DECLARE a IS ONE OF `x`, y\n"
               "DECLARE b IS ONE OF\n    -- a note\n    @desc d\n    `p` HAS `f` IS A NUMBER\n"
               "    `q` HAS\n        `g` IS A STRING\n    @ref akn:k\n\n    r\n\n§§ `2`\n"
               "DECLARE c HAS\n    `h` IS A NUMBER\n")
        self.assertEqual(constructors(src), ["`x`", "y", "`p`", "`q`", "r"])

    def test_a_sectioned_documents_files_carry_its_prefix(self):
        for doc, prefix in akn.MODULE_PREFIX.items():
            d = ROOT / "l4" / doc.removesuffix(".xml")
            real = [f for f in d.glob("*.l4") if not f.is_symlink()]
            self.assertTrue(real)
            self.assertEqual([f.name for f in real if not f.name.startswith(prefix)], [])


# An agreement may import a circular or a takanon section only where the
# agreement's own words send the reader there: each pair below is
# (the agreement's module, the module it imports), with why. Held exactly.
AGREEMENT_IMPORTS_OF_WEAKER_INSTRUMENTS = {
    ("2016-02-22_ofek-hadash_hascam-2016_tables-and-sheklit", "2016-02-22_sachar_2016-1-13_maanak-hora"):
        "§5(ג) grants 1,000 'על פי המפורט בהוראות חוזר הממונה על השכר 2016-1-13': "
        "the agreement sends the grant's details to the circular",
    ("1978-01-13_teachers_shelach-teachers-agreement", "takanon-1-25"):
        "4(יג) gives the guide the high schools' calendar of recesses, which the agreement "
        "does not state; the Annual Leave Law check reads its summer from the takanon's §1.25.2",
}


class AgreementsStandOnTheirOwnRules(unittest.TestCase):
    """AN AGREEMENT DOES NOT REST ON A WEAKER INSTRUMENT'S ENCODING
    (MMS-663). A circular never out-ranks an agreement, and the cross-
    reference rule runs one way (MMS-521): a circular or the takanon that
    applies an agreement's rule imports the agreement's module. Four
    agreements had it backwards, importing a circular, or the takanon's
    §6.17, that printed the same words, so a later amendment or misreading
    of the weaker text would have moved the agreement's rule. An agreement
    that imports a circular or a takanon section does so only for what its
    own text sends there, named in AGREEMENT_IMPORTS_OF_WEAKER_INSTRUMENTS;
    the takanon's shared vocabulary (`common`) is no section."""

    @staticmethod
    def weaker(target: Path) -> bool:
        rel = target.relative_to(ROOT / "l4").parts
        if rel[0] == "shared":   # a module a collection shares is the collection's (MMS-776)
            rel = rel[1:]
        if rel[0].startswith("circulars"):
            return True
        return rel[0] == "takanon" and target.name != "common.l4"

    def imports(self):
        out = set()
        modules = ROOT / "l4/modules"
        for f in sorted((ROOT / "l4/agreements").rglob("*.l4")):
            if f.is_symlink():
                continue
            for name in re.findall(r"^IMPORT\s+`?([^`\s]+)`?\s*$", f.read_text(encoding="utf-8"), re.M):
                link = next((p for p in (f.parent / f"{name}.l4", modules / f"{name}.l4") if p.exists()), None)
                if link is not None and self.weaker(link.resolve()):
                    out.add((f.stem, name))
        return out

    def test_an_agreement_imports_no_circular_or_takanon_section_for_its_own_rule(self):
        found = self.imports()
        self.assertEqual(sorted(found - set(AGREEMENT_IMPORTS_OF_WEAKER_INSTRUMENTS)), [],
                         "move the rule into the agreement and have the circular import it")
        # the record is exact: an entry no agreement uses any more is stale
        self.assertEqual(sorted(set(AGREEMENT_IMPORTS_OF_WEAKER_INSTRUMENTS) - found), [])
        self.assertEqual(len(AGREEMENT_IMPORTS_OF_WEAKER_INSTRUMENTS), 2)
        for pair, why in AGREEMENT_IMPORTS_OF_WEAKER_INSTRUMENTS.items():
            self.assertTrue(why.strip(), pair)

    def test_the_reader_sees_a_circular_and_a_takanon_section(self):
        l4 = ROOT / "l4"
        self.assertTrue(self.weaker(l4 / "circulars/2018-19_tashat_02.l4"))
        self.assertTrue(self.weaker(l4 / "circulars-sachar/2016-02-22_sachar_2016-1-13_maanak-hora.l4"))
        self.assertTrue(self.weaker((l4 / "modules/takanon-6-17.l4").resolve()))
        self.assertFalse(self.weaker((l4 / "modules/common.l4").resolve()))
        self.assertFalse(self.weaker(l4 / "agreements/teachers-general/1978-01-13_teachers_shelach-teachers-agreement.l4"))


if __name__ == "__main__":
    unittest.main()
