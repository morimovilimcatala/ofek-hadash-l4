r"""The per-instrument record of the protective statutes (MMS-601).

    python3 tools/statute_record.py           # after tools/l4run.py; writes build/statute-record.json
    python3 tools/statute_record.py --print   # the totals, and the list for the next batches

For every document of corpus/manifest.json and every protective statute the
statutes' root registers (l4/lib/statutes-root.l4), one verdict:

  shortfall    a card on מקורות סותרים (data/contradictions.json, rule
               `statute-floor`) whose law side is the statute and whose other
               side is the instrument, or a finding in the instrument's
               register whose #ASSERT reads the statute;
  meets        an #ASSERT in the instrument's L4 (or its module's tests file)
               that reads the statute — a rule, a value or a type its module
               declares, named in the assertion or in a rule it reaches, in
               the same file or in a module the file imports — and that
               `make l4` recorded as holding;
  not-weighed  the encoding set it aside, and says why: a marker comment in
               the instrument's file,
                   -- not weighed against `the Hours of Work and Rest Law`: <why>
               naming the statute by its name in the statutes' root; or,
               where the instrument has no L4 to carry it, a row of
               data/statute-set-aside.toml; or nothing in it is on the
               statute's subject — none of the terms the batch searched the
               corpus for (laws/<name>.toml `inventory`) is in its text, and
               it does not cite the law (data/statute-citations.json);
  not-checked  none of these: the terms the batch searched for are in its
               text, and no verdict was recorded.

Nothing is written by hand into the record: it is read off the L4 source,
`make l4`'s results (build/l4/*.run.json), the findings register and the
cards. A sectioned document (the takanon, the base agreement, the Oz LaTmura
agreement) has a row and, under it, a row per section; the document's
verdict for a statute is the strongest of its sections' (shortfall, then
meets, then not-checked, then a reason it was not weighed), and a section is
on a statute's subject by its own text. A document the snapshot does not
vendor has no text, and is not checked.
"""
from __future__ import annotations

import json
import re
import sys
import tomllib
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import akn  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
L4 = ROOT / "l4"
LAWS_L4 = L4 / "laws"
LAWS_TEXT = ROOT / "laws"
STATUTES_ROOT = L4 / "lib" / "statutes-root.l4"
TESTS = L4 / "tests"
BUILD_L4 = ROOT / "build" / "l4"
OUT = ROOT / "build" / "statute-record.json"
MANIFEST = ROOT / "corpus" / "manifest.json"
CARDS = ROOT / "data" / "contradictions.json"
FINDINGS = ROOT / "findings"
SET_ASIDE = ROOT / "data" / "statute-set-aside.toml"

VERDICTS = ("shortfall", "meets", "not-weighed", "not-checked")

TICK = re.compile(r"`([^`]+)`")
DECL = re.compile(r"^(?:DECIDE\s+`([^`]+)`|`([^`]+)`\s+MEANS\b|DECLARE\s+`([^`]+)`)")
CTOR = re.compile(r"^\s+`([^`]+)`(?:\s+HAS\b|\s*$)")
IMPORT = re.compile(r"^IMPORT\s+`?([^`\s]+)`?\s*$")
MARK = re.compile(r"^\s*--\s*not weighed against\s+`([^`]+)`\s*:\s*(.*)$")
STATUTE = re.compile(r"^`([^`]+)`\s+MEANS\s*\n\s+`instrument`\s+WITH\s*\n\s+`module`\s+IS\s+\"([^\"]+)\"", re.M)


# ---------------------------------------------------------------- the statutes

@lru_cache(maxsize=None)
def statutes() -> list[dict]:
    """The protective statutes, in the statutes' root's order: its name there,
    its module, its title (laws/<module>.toml)."""
    text = STATUTES_ROOT.read_text(encoding="utf-8")
    names = dict((m, n) for n, m in STATUTE.findall(text))
    order = re.search(r"`the protective statutes` MEANS\s+LIST(.*?)(?:\n\s*\n|\n§)", text, re.S).group(1)
    out = []
    for name in TICK.findall(order):
        module = next(m for m, n in names.items() if n == name)
        law = tomllib.loads((LAWS_TEXT / f"{module}.toml").read_text(encoding="utf-8"))
        out.append({"name": name, "module": module, "title": law["title"],
                    "inventory": law.get("inventory", {})})
    return out


def link_name(module: str) -> str:
    """The name an instrument imports a statute by: a link in its own
    directory, the module's name with underscores."""
    return module.replace("-", "_")


@lru_cache(maxsize=None)
def exports(module: str) -> frozenset[str]:
    """What a statute's module declares: its rules, its values, its types and
    their cases."""
    return frozenset(parse(LAWS_L4 / f"{module}.l4")["defs"]) | frozenset(parse(LAWS_L4 / f"{module}.l4")["types"])


# ---------------------------------------------------------------- an L4 file

@lru_cache(maxsize=None)
def parse(path: Path) -> dict:
    """A file's imports, its top-level definitions (name -> the text of the
    declaration), its declared types and cases, its #ASSERTs (line, text)
    and its set-aside markers (line, statute name, why)."""
    lines = path.read_text(encoding="utf-8").split("\n")
    imports, defs, types, asserts, marks = [], {}, set(), [], []
    cur: str | None = None
    in_type = False
    i = 0
    while i < len(lines):
        line = lines[i]
        if m := MARK.match(line):
            why = [m.group(2).strip()]
            j = i + 1
            while j < len(lines) and lines[j].startswith("--") and not MARK.match(lines[j]) \
                    and lines[j].strip() != "--":
                why.append(lines[j][2:].strip())
                j += 1
            marks.append((i + 1, m.group(1), " ".join(" ".join(why).split())))
        if line and not line[0].isspace():
            cur, in_type = None, False
            if m := IMPORT.match(line):
                imports.append(m.group(1))
            elif line.startswith("#ASSERT"):
                text = [line]
                j = i + 1
                while j < len(lines) and lines[j][:1].isspace() and lines[j].strip():
                    text.append(lines[j])
                    j += 1
                asserts.append((i + 1, "\n".join(text)))
            elif m := DECL.match(line):
                name = next(g for g in m.groups() if g)
                if line.startswith("DECLARE"):
                    types.add(name)
                    in_type = True
                else:
                    cur = name
                    defs[cur] = line
        elif cur is not None:
            defs[cur] += "\n" + line
        elif in_type and (m := CTOR.match(line)):
            types.add(m.group(1))
        i += 1
    return {"imports": imports, "defs": defs, "types": types, "asserts": asserts, "marks": marks}


def resolve(path: Path, name: str) -> Path | None:
    """The file an IMPORT names: a link in the importer's own directory, or
    the module of that name (l4/modules/)."""
    for cand in (path.parent / f"{name}.l4", L4 / "modules" / f"{name}.l4"):
        if cand.exists():
            return cand.resolve()
    return None


def statute_of(path: Path) -> str | None:
    """The protective statute a file is, if it is one."""
    if path.parent != LAWS_L4:
        return None
    return path.stem if path.stem in {s["module"] for s in statutes()} else None


@lru_cache(maxsize=None)
def visible(path: Path) -> dict[str, Path]:
    """{name: the file that declares it} for every name a file sees: its own,
    then those of the modules it imports, transitively, nearest first. A
    statute's names are its own: what a statute imports is not followed."""
    out: dict[str, Path] = {}
    seen = {path}
    queue = [path]
    while queue:
        p = queue.pop(0)
        src = parse(p)
        names = set(src["defs"]) | (set(src["types"]) if statute_of(p) else set())
        for n in names:
            out.setdefault(n, p)
        if statute_of(p) and p != path:
            continue
        for imp in src["imports"]:
            q = resolve(p, imp)
            if q is not None and q not in seen:
                seen.add(q)
                queue.append(q)
    return out


def reads(path: Path, expr: str) -> set[str]:
    """The statutes an expression in a file reads: a name a statute's module
    declares, in the expression, or in the body of a rule it reaches — in the
    same file or in a module the file imports (the Oz agreement's §24 asks
    §46's rule, which asks the Severance Pay Law's §14)."""
    hits: set[str] = set()
    seen: set[tuple[Path, str]] = set()
    todo = [(path, t) for t in TICK.findall(expr)]
    while todo:
        where, t = todo.pop()
        if (where, t) in seen:
            continue
        seen.add((where, t))
        home = visible(where).get(t)
        if home is None:
            continue
        if (law := statute_of(home)) is not None:
            hits.add(law)
            continue
        todo += [(home, x) for x in TICK.findall(parse(home)["defs"][t]) if x != t]
    return hits


# ---------------------------------------------------------------- the units

def manifest() -> list[dict]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["documents"]


def unit_files(doc: str) -> dict[str, Path]:
    """{section: L4 file} for a document: "" for a whole document's one file;
    a sectioned document's section files by their number, and its shared
    helpers under their own stem."""
    if akn.is_whole(doc):
        p = L4 / f"{doc.removesuffix('.xml')}.l4"
        return {"": p} if p.exists() else {}
    d = L4 / doc.removesuffix(".xml")
    if not held_text(doc):
        return {}
    prefix = akn.module_prefix(doc)
    by_slug = {akn.file_name(s.num): s.num for s in akn.sections(doc)}
    out = {}
    for p in sorted(d.glob("*.l4")):
        if p.is_symlink():
            continue
        slug = p.stem.removeprefix(prefix)
        out[by_slug.get(slug, slug)] = p
    return out


@lru_cache(maxsize=None)
def tests_index() -> dict[str, Path]:
    """{the path of a module's file: its tests file}."""
    out = {}
    for t in TESTS.glob("*-tests.l4"):
        f = tested_file(t)
        if f is not None:
            out[str(f)] = t
    return out


def tested_file(tests: Path) -> Path | None:
    name = tests.name.removesuffix("-tests.l4")
    link = L4 / "modules" / f"{name}.l4"
    return link.resolve() if link.exists() else None


def run_of(path: Path) -> dict:
    out = BUILD_L4 / path.relative_to(L4).with_suffix(".run.json")
    return json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}


def held(path: Path, line: int) -> bool | None:
    """What `make l4` recorded about the #ASSERT on that line."""
    for d in run_of(path).get("diagnostics", []):
        rng = d.get("range", "")
        if rng.split(":", 1)[0] == str(line):
            msg = d.get("message", "")
            if msg == "assertion satisfied":
                return True
            if "assertion" in msg:
                return False
    return None


def held_text(doc: str) -> bool:
    """Whether the snapshot vendors the document's text (a collection nobody
    has started is listed in the manifest and not vendored)."""
    return (akn.CORPUS / doc).exists()


def section_text(doc: str) -> dict[str, str]:
    if not held_text(doc):
        return {}
    return {("" if akn.is_whole(doc) else s.num): " ".join(r.text for r in s.rows)
            for s in akn.sections(doc)}


def section_of_key(doc: str, key: str) -> str:
    if akn.is_whole(doc) or not held_text(doc):
        return ""
    for s in akn.sections(doc):
        if key in s.keys():
            return s.num
    return ""


# ---------------------------------------------------------------- the inventory

def term_re(term: str) -> re.Pattern:
    """A term the batch searched for, as a word of the text: Hebrew prefixes
    (ו, ה, ב, ל, מ, ש, כ) may stand before it; a term ending in * may run on,
    any other ends where the word ends."""
    run_on = term.endswith("*")
    body = re.escape(term.rstrip("*"))
    return re.compile(r"(?<![א-ת])[ובלמשהכ]{0,3}" + body + (r"" if run_on else r"(?![א-ת])"))


@lru_cache(maxsize=None)
def term_patterns(module: str) -> tuple[re.Pattern, ...]:
    s = next(s for s in statutes() if s["module"] == module)
    return tuple(term_re(t) for t in s["inventory"].get("terms", []))


def on_subject(module: str, text: str) -> list[str]:
    """The inventory's terms the text holds."""
    s = next(s for s in statutes() if s["module"] == module)
    text = text.replace("״", '"').replace("׳", "'")
    for ex in s["inventory"].get("exclude", []):
        text = term_re(ex).sub(" ", text)
    terms = s["inventory"].get("terms", [])
    return [t for t, p in zip(terms, term_patterns(module)) if p.search(text)]


@lru_cache(maxsize=None)
def citing(module: str) -> frozenset[str]:
    """The documents that cite the law (data/statute-citations.json)."""
    import laws
    row = laws.corpus_citations(laws.load(module))
    return frozenset(row["cited_by"]) if row else frozenset()


# ---------------------------------------------------------------- the record

def load_findings() -> list[dict]:
    out = []
    for f in sorted(FINDINGS.rglob("*.toml")):
        out += tomllib.loads(f.read_text(encoding="utf-8")).get("finding", [])
    return out


def build() -> dict:
    """The record: a row per document of the manifest, a cell per protective
    statute (and, for a sectioned document, the same per section)."""
    sts = statutes()
    by_name = {s["name"]: s["module"] for s in sts}
    modules_ = {s["module"] for s in sts}
    findings = load_findings()
    cards = [c for c in json.loads(CARDS.read_text(encoding="utf-8"))["items"]
             if c.get("rule") == "statute-floor"]
    card_of = {f: c["id"] for c in cards for f in c.get("findings", [])}
    set_aside = tomllib.loads(SET_ASIDE.read_text(encoding="utf-8")).get("set_aside", []) \
        if SET_ASIDE.exists() else []

    rows = []
    for d in manifest():
        doc = d["path"]
        files = unit_files(doc)
        texts = section_text(doc)
        units_: dict[str, dict] = {}

        def unit(sec: str) -> dict:
            return units_.setdefault(sec, {s["module"]: [] for s in sts})

        for sec, path in files.items():
            src = parse(path)
            rel = str(path.relative_to(ROOT))
            ev_of = {f["evidence"].strip("`"): f for f in findings if f.get("l4") == rel}
            places = [path] + ([tests_index()[str(path)]] if str(path) in tests_index() else [])
            for where in places:
                wrel = str(where.relative_to(ROOT))
                for line, text in parse(where)["asserts"]:
                    f = next((f for e, f in ev_of.items() if e and e in text), None)
                    for mod in sorted(reads(where, text)):
                        item = {"kind": "assert", "file": wrel, "line": line,
                                "assert": text.strip(), "held": held(where, line)}
                        if f is not None:
                            item.update(verdict="shortfall", finding=f["id"], card=card_of.get(f["id"]))
                        else:
                            item.update(verdict="meets")
                        unit(sec)[mod].append(item)
            for line, name, why in src["marks"]:
                if name not in by_name:
                    raise ValueError(f"{rel}:{line}: `{name}` is not a statute the statutes' root registers")
                unit(sec)[by_name[name]].append({"kind": "marker", "verdict": "not-weighed",
                                                 "file": rel, "line": line, "why": why})
        for c in cards:
            mod = next(x for x in c["sides"] if x.get("type") == "law")["law"]
            if mod not in modules_:
                raise ValueError(f"card {c['id']}: {mod} is not a statute the statutes' root registers")
            for side in c["sides"]:
                if side.get("doc") == doc:
                    unit(section_of_key(doc, side.get("key", "")))[mod].append(
                        {"kind": "card", "verdict": "shortfall", "card": c["id"], "title": c["title"],
                         "findings": c.get("findings", []), "key": side.get("key", "")})
        for a in set_aside:
            if a["doc"] == doc:
                unit(a.get("section", ""))[by_name[a["statute"]]].append(
                    {"kind": "data", "verdict": "not-weighed", "why": a["why"],
                     "file": str(SET_ASIDE.relative_to(ROOT))})

        sub = []
        for sec in sorted(set(units_) | set(texts) | set(files), key=_order(texts)) or [""]:
            u = unit(sec)
            if sec not in texts and sec not in files and not any(u.values()) and texts:
                continue
            # the citations are counted by document: a section of a sectioned
            # one is on the subject by its own text (each inventory names the law)
            cells = {s["module"]: _cell(u[s["module"]], s["module"], texts.get(sec, "") if texts else None,
                                        akn.is_whole(doc) and doc in citing(s["module"])) for s in sts}
            sub.append({"section": sec, "file": str(files[sec].relative_to(ROOT)) if sec in files else None,
                        "cells": cells})
        if akn.is_whole(doc):
            top = sub[0]["cells"]
        else:
            top = {s["module"]: _merge([(x["section"], x["cells"][s["module"]]) for x in sub]) for s in sts}
        row = {"doc": doc, "collection": d["collection"], "title": d["title"], "date": d.get("date") or "",
               "encoded": bool(files), "text": held_text(doc), "cells": top}
        if not akn.is_whole(doc):
            row["sections"] = sub
        rows.append(row)
    return {"statutes": [{k: s[k] for k in ("name", "module", "title")} | {"short": short(s["title"])}
                         for s in sts],
            "verdicts": list(VERDICTS), "rows": rows}


def short(title: str) -> str:
    """A statute's name as a column head: its title without "חוק" and the
    year; a family-absence law by its parenthesis."""
    name = title.split(",")[0].removeprefix("חוק ").strip()
    m = re.search(r"\(([^)]*)\)", name)
    return m.group(1) if m else name


def _order(texts: dict[str, str]):
    known = list(texts)

    def key(sec: str):
        return (0, known.index(sec), "") if sec in known else (1, 0, sec)
    return key


def _cell(evidence: list[dict], module: str, text: str | None, cites: bool) -> dict:
    """One unit's verdict on one statute: the strongest the evidence holds,
    or, with none, whether the text is on the statute's subject."""
    for v in ("shortfall", "meets", "not-weighed"):
        if any(e["verdict"] == v for e in evidence):
            return {"verdict": v, "evidence": evidence}
    if text is None:
        return {"verdict": "not-checked", "evidence": [], "no_text": True}
    terms = on_subject(module, text)
    if terms or cites:
        return {"verdict": "not-checked", "evidence": [], "terms": terms, "cites": cites}
    return {"verdict": "not-weighed", "evidence": [], "off_subject": True}


def _merge(cells: list[tuple[str, dict]]) -> dict:
    """A sectioned document's verdict on a statute: the strongest of its
    sections', with the sections that give each verdict."""
    by: dict[str, list[str]] = {}
    for sec, c in cells:
        by.setdefault(verdict_key(c), []).append(sec)
    for v in ("shortfall", "meets", "not-checked", "not-weighed"):
        if v in by:
            return {"verdict": v, "sections": {k: x for k, x in by.items() if k != "off-subject"}}
    return {"verdict": "not-weighed", "off_subject": True, "sections": {}}


def verdict_key(cell: dict) -> str:
    """The verdict as the pages draw it: an instrument with nothing on the
    statute's subject is drawn apart from one the encoding set aside."""
    return "off-subject" if cell.get("off_subject") else cell["verdict"]


def totals(rec: dict) -> dict[str, dict[str, int]]:
    from collections import Counter
    return {s["module"]: dict(Counter(verdict_key(r["cells"][s["module"]]) for r in rec["rows"]))
            for s in rec["statutes"]}


def units(rec: dict):
    """Every unit of the record: (row, section or None, its cells)."""
    for r in rec["rows"]:
        if "sections" in r:
            for u in r["sections"]:
                yield r, u["section"], u["cells"]
        else:
            yield r, None, r["cells"]


# ---------------------------------------------------------------- the pages

# how a verdict reads on the site; "off-subject" is a not-weighed whose
# reason is that nothing in the instrument is on the statute's subject
LABEL = {"shortfall": "נופל מהרצפה", "meets": "עומד ברצפה", "not-weighed": "לא נשקל",
         "off-subject": "אין בו מעניינו", "not-checked": "לא נבדק"}
GLYPH = {"shortfall": "✗", "meets": "✓", "not-weighed": "–", "off-subject": "·", "not-checked": "?"}
ORDER = ("shortfall", "meets", "not-weighed", "not-checked", "off-subject")
REPO = "https://github.com/morimovilimcatala/ofek-hadash-l4"
HERE = "laws/record.html"


def chip(v: str, n: int | None = None) -> str:
    return (f'<span class="sv sv-{v}"><span class="sv-g" aria-hidden="true">{GLYPH[v]}</span>'
            f'{LABEL[v]}{f" <b>{n}</b>" if n is not None else ""}</span>')


def first_line(text: str, n: int = 140) -> str:
    line = " ".join(text.split("\n")[0].split())
    return line if len(line) <= n else line[: n - 1] + "…"


def evidence_html(cell: dict, *, esc, link) -> str:
    """What a unit's verdict on a statute rests on: the assertions, the cards
    and findings, the reason it was set aside, or the terms that put it on
    the statute's subject."""
    items = []
    ev = cell.get("evidence", [])
    for e in ev:
        if e["kind"] == "card":
            items.append(f'<li>כרטיס ב<a href="{link("contradictions.html")}#{esc(e["card"])}">מקורות סותרים</a>: '
                         f'{esc(e["title"])}</li>')
    for e in ev:
        if e["kind"] == "assert":
            src = f'{REPO}/blob/main/{e["file"]}#L{e["line"]}'
            what = ("בדיקה שמתקיימת" if e["verdict"] == "meets" else "הבדיקה שמראה את החסר")
            if e["verdict"] == "shortfall":
                target = (f'{link("contradictions.html")}#{esc(e["card"])}' if e.get("card")
                          else f'{link("findings.html")}#{esc(e["finding"])}')
                what += f', ממצא <a href="{target}" dir="ltr">{esc(e["finding"])}</a>'
            if e.get("held") is not True:
                what += " — <b>make l4 לא רשם שהיא מתקיימת</b>"
            items.append(f'<li>{what}: <a class="st-code" href="{esc(src)}" dir="ltr" lang="en">'
                         f'<code>{esc(first_line(e["assert"]))}</code></a></li>')
    for e in ev:
        if e["kind"] == "marker":
            src = f'{REPO}/blob/main/{e["file"]}#L{e["line"]}'
            items.append(f'<li>הנימוק, בהערה בקוד (<a href="{esc(src)}">שורה {e["line"]}</a>): '
                         f'<span class="st-why" dir="ltr" lang="en">{esc(e["why"])}</span></li>')
        elif e["kind"] == "data":
            items.append(f'<li>{esc(e["why"])} <span class="lawnote">(<code dir="ltr">{esc(e["file"])}</code>)</span></li>')
    if not ev:
        if cell.get("no_text"):
            items.append('<li>נוסח המסמך אינו בתמונת הקורפוס שכאן, ולכן אי אפשר לומר אם עניינו נוגע לחוק.</li>')
        elif cell["verdict"] == "not-checked":
            bits = []
            if cell.get("terms"):
                bits.append("מונחי החיפוש של החוק שמופיעים בו: " + ", ".join(
                    f'<span lang="he">{esc(t)}</span>' for t in cell["terms"]))
            if cell.get("cites"):
                bits.append("הקורפוס מקשר בו לחוק")
            items.append(f'<li>{"; ".join(bits)} — ולא נרשמה הכרעה.</li>')
        elif cell.get("off_subject"):
            items.append('<li>אף אחד ממונחי החיפוש של החוק אינו מופיע בו, והוא אינו מצטט את החוק.</li>')
    return f'<ul class="st-ev">{"".join(items)}</ul>' if items else ""


def sections_html(cell: dict, *, esc, sec_href) -> str:
    """A sectioned document's verdict on a statute, by its sections."""
    out = []
    for v in ORDER:
        secs = cell.get("sections", {}).get(v)
        if not secs:
            continue
        refs = []
        for s in secs:
            h = sec_href(s)
            label = esc(s or "—")
            refs.append(f'<a href="{h}" dir="ltr">{label}</a>' if h else f'<span dir="ltr">{label}</span>')
        out.append(f'<li>{chip(v)} {", ".join(refs)}</li>')
    return f'<ul class="st-ev st-secs">{"".join(out)}</ul>' if out else ""


def box_html(rec: dict, cells: dict, *, esc, link, sec_href=None, what: str = "המסמך",
             box_id: str = "statutes") -> str:
    """An instrument's row: its verdict on every protective statute, and what
    each rests on. With `sec_href`, the cells are a sectioned document's,
    each listing its sections."""
    keys = {s["module"]: verdict_key(cells[s["module"]]) for s in rec["statutes"]}
    counts = {v: sum(1 for k in keys.values() if k == v) for v in ORDER}
    rows, off = [], []
    for s in rec["statutes"]:
        c, k = cells[s["module"]], keys[s["module"]]
        name = f'<a href="{link("laws/" + s["module"] + ".html")}">{esc(s["title"])}</a>'
        if k == "off-subject":
            off.append(f'<a href="{link("laws/" + s["module"] + ".html")}">{esc(s["short"])}</a>')
            continue
        detail = (sections_html(c, esc=esc, sec_href=sec_href) if sec_href is not None
                  else evidence_html(c, esc=esc, link=link))
        rows.append(f'<tr><th scope="row">{name}</th><td>{chip(k)}</td><td>{detail}</td></tr>')
    summary = "".join(chip(v, counts[v]) for v in ORDER if counts[v])
    table = (f'<div class="scroll-x"><table class="diag st-table"><thead><tr><th>החוק</th><th>הכרעה</th>'
             f'<th>על מה היא נשענת</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>' if rows else "")
    tail = (f'<p class="lawnote">אין ב{what} דבר מעניינם של: {", ".join(off)} '
            '(אף מונח מרשימת החיפוש של החוק אינו מופיע בו).</p>' if off else "")
    return (f'<details class="st-box" id="{esc(box_id)}"><summary><span class="st-title">מול החוקים המגינים</span>'
            f'{summary}</summary>'
            f'<p class="lawnote">בכל חוק מגן, אחת מארבע: נופל מהרצפה (כרטיס או ממצא), עומד ברצפה (בדיקה '
            f'שקוראת את החוק ומתקיימת), לא נשקל (ובאיזה נימוק), או לא נבדק. '
            f'<a href="{link(HERE)}">הטבלה כולה</a>.</p>'
            f'{table}{tail}</details>')


def law_html(rec: dict, module: str, *, esc, link, doc_href, coll_name) -> str:
    """A statute's page: the instruments weighed against it, by verdict."""
    s = next(x for x in rec["statutes"] if x["module"] == module)
    groups: dict[str, list[str]] = {v: [] for v in ORDER}
    for r in rec["rows"]:
        c = r["cells"][module]
        k = verdict_key(c)
        if k == "off-subject":
            groups[k].append(r["doc"])
            continue
        h = doc_href(r["doc"], None)
        title = (f'<a href="{link(h)}#statutes">{esc(r["title"])}</a>' if h else esc(r["title"]))
        meta = f'<span class="lawnote"> · {esc(coll_name(r["collection"]))}{" · " + esc(r["date"]) if r["date"] else ""}</span>'
        if "sections" in r:
            detail = sections_html(c, esc=esc, sec_href=lambda sec, d=r["doc"]: (
                link(doc_href(d, sec)) if doc_href(d, sec) else None))
        else:
            detail = evidence_html(c, esc=esc, link=link)
        groups[k].append(f'<li>{title}{meta}{detail}</li>')
    out = [f'<h2 id="record">המסמכים מול החוק</h2>'
           f'<p class="lede">כל מסמך ברשימת הקורפוס, ומה נקבע בו מול {esc(s["title"])}: '
           'נופל מהרצפה (כרטיס במקורות סותרים או ממצא), עומד ברצפה (בדיקה בקוד המסמך שקוראת את החוק ומתקיימת), '
           'לא נשקל (ובאיזה נימוק), או לא נבדק — מונחי החיפוש של החוק מופיעים בו ולא נרשמה הכרעה. '
           f'הרשומה נקראת מהקוד, מתוצאות <code>make l4</code>, מהממצאים ומהכרטיסים. '
           f'<a href="{link(HERE)}">כל המסמכים מול כל החוקים</a>.</p>']
    for v in ORDER:
        items = groups[v]
        if not items:
            continue
        if v == "off-subject":
            out.append(f'<h3>{chip(v, len(items))}</h3><p class="lawnote">אף מונח מרשימת החיפוש של החוק '
                       'אינו מופיע בהם, והם אינם מצטטים אותו: אין בהם דבר מעניינו.</p>')
            continue
        body = "".join(items)
        if v == "not-checked":
            out.append(f'<details class="st-group"><summary>{chip(v, len(items))}</summary><ul class="st-list">{body}</ul></details>')
        else:
            out.append(f'<h3>{chip(v, len(items))}</h3><ul class="st-list">{body}</ul>')
    inv = next(x for x in statutes() if x["module"] == module)["inventory"]
    if inv.get("terms"):
        out.append('<p class="lawnote">מונחי החיפוש (<code dir="ltr">laws/' + esc(module) + '.toml</code>): '
                   + ", ".join(f'<span lang="he">{esc(t)}</span>' for t in inv["terms"])
                   + (". לא נספרים: " + ", ".join(esc(t) for t in inv["exclude"]) if inv.get("exclude") else "")
                   + ".</p>")
    return "".join(out)


def grid_html(rec: dict, *, esc, link, doc_href, coll_name, coll_order) -> str:
    """The summary page: every document of the manifest against every
    protective statute, and the totals."""
    sts = rec["statutes"]
    tot = totals(rec)
    head = "".join(f'<th scope="col"><a href="{link("laws/" + s["module"] + ".html")}#record" '
                   f'title="{esc(s["title"])}">{esc(s["short"])}</a></th>' for s in sts)
    trows = []
    for v in ORDER:
        tds = "".join(f'<td>{tot[s["module"]].get(v, 0) or ""}</td>' for s in sts)
        trows.append(f'<tr><th scope="row">{chip(v)}</th>{tds}</tr>')
    totals_table = (f'<div class="scroll-x"><table class="diag st-grid st-totals"><thead><tr><th>הכרעה</th>{head}</tr></thead>'
                    f'<tbody>{"".join(trows)}</tbody></table></div>')
    rows_by: dict[str, list[dict]] = {}
    for r in rec["rows"]:
        rows_by.setdefault(r["collection"], []).append(r)
    body, quiet = [], []
    for coll in coll_order([*rows_by]):
        rs = []
        for r in sorted(rows_by[coll], key=lambda r: (r["date"], r["doc"])):
            keys = [verdict_key(r["cells"][s["module"]]) for s in sts]
            h = doc_href(r["doc"], None)
            name = (f'<a href="{link(h)}#statutes">{esc(r["title"])}</a>' if h else esc(r["title"]))
            if all(k == "off-subject" for k in keys):
                quiet.append(f'<li>{name}<span class="lawnote"> · {esc(coll_name(coll))}</span></li>')
                continue
            tds = "".join(f'<td class="sv-{k}">{GLYPH[k]}</td>' if k == "off-subject" else
                          f'<td class="sv-{k}" title="{LABEL[k]}">{GLYPH[k]}</td>' for k in keys)
            date = f'<span class="lawnote" dir="ltr"> {esc(r["date"])}</span>' if r["date"] else ""
            rs.append(f'<tr><th scope="row" class="st-doc">{name}{date}</th>{tds}</tr>')
        if rs:
            body.append(f'<tr class="st-coll"><th colspan="{len(sts) + 1}">{esc(coll_name(coll))}</th></tr>' + "".join(rs))
    legend = " ".join(chip(v) for v in ORDER)
    grid = (f'<div class="scroll-x st-gridwrap"><table class="diag st-grid"><thead><tr><th>מסמך</th>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')
    quiet_html = (f'<details class="st-group"><summary>{chip("off-subject", len(quiet))} — מסמכים שאין בהם דבר '
                  f'מעניינו של אף חוק מגן</summary><ul class="st-list">{"".join(quiet)}</ul></details>' if quiet else "")
    return ('<h1>המסמכים מול החוקים המגינים</h1>'
            '<p class="lede">לכל מסמך ברשימת הקורפוס (<code dir="ltr">corpus/manifest.json</code>) ולכל חוק מגן '
            f'שהשורש של החוקים רושם (<a href="{link("laws/root.html")}">שורש החוקים המגינים</a>), אחת מארבע: '
            'נופל מהרצפה — כרטיס בקבוצה "מסמך מול חוק" ב<a href="' + link("contradictions.html") + '#g-law">מקורות סותרים</a> '
            'או ממצא שהבדיקה שלו קוראת את החוק; עומד ברצפה — בדיקה (<code>#ASSERT</code>) בקוד המסמך שקוראת כלל או ערך '
            'של החוק, ו־<code>make l4</code> רשם שהיא מתקיימת; לא נשקל — והנימוק, בהערה בקוד המסמך או, כשאין לו קוד, '
            'ב־<code dir="ltr">data/statute-set-aside.toml</code>, או שאין בו דבר מעניינו של החוק: אף מונח מרשימת החיפוש '
            'שהסבב של החוק חיפש בקורפוס אינו מופיע בו; לא נבדק — המונחים מופיעים בו, ולא נרשמה הכרעה. '
            'דבר מכל זה אינו נכתב ביד: הרשומה נקראת מהקוד ומתוצאות הבדיקות '
            f'(<code dir="ltr">tools/statute_record.py</code>, וגם <a href="{link("statute-record.json")}">כ־JSON</a>). '
            'מסמך שמחולק לסעיפים (התקנון, הסכם הבסיס, הסכם עוז לתמורה) מקבל את ההכרעה החזקה מבין סעיפיו, ודף המסמך מפרט אותם.</p>'
            f'<h2>לפי חוק</h2>{totals_table}'
            f'<h2>לפי מסמך</h2><p class="lawnote">{legend}</p>{grid}{quiet_html}')


if __name__ == "__main__":
    rec = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(rec['rows'])} documents x {len(rec['statutes'])} statutes")
    if "--print" in sys.argv:
        for s in rec["statutes"]:
            print(f"  {s['module']}: {totals(rec)[s['module']]}")
        print("not checked, on the subject (the inventory's terms are in the text):")
        for r, sec, cells in units(rec):
            for s in rec["statutes"]:
                c = cells[s["module"]]
                if c["verdict"] == "not-checked" and not c.get("no_text"):
                    where = r["doc"] + (f" §{sec}" if sec else "")
                    print(f"  {s['module']}\t{where}\t{', '.join(c.get('terms', []))}"
                          + ("\t(cites the law)" if c.get("cites") else ""))
