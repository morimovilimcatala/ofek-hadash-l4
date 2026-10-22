"""The salary calculator (calculator.html): a month's salary by the law,
evaluated in the browser by L4 itself (MMS-525; the client, 2026-10-22: "if
a teacher wants to know his salary he wants to know the law, he doesn't care
about the underlying documents").

The page asks l4/lib/salary-root.l4: §1.1's components, each the root's
governing answer where the root has a pay item for it and §1.1's figure
where it has none yet, and why — the instrument that governs, the rule of
precedence, what every instrument that speaks says. Nothing here computes a
salary. The page ships salary-root and every module it reaches, without
their own tests (`#EVAL`, `#ASSERT`: `make roots` runs those); on "חישוב"
the browser writes the form's values as a small L4 program that imports
salary-root, and runs it through the L4 evaluator compiled to WebAssembly
(tools/assets/l4wasm/, built by toolchain/build-wasm.sh). There is no
second implementation of the rules.

What this module reads off the L4 file at build time, so a renamed field,
allowance or rule changes the form with it: the fields of the `salary month`
record and their types, the `percentage allowance` enum, the `allowance
held` record, the components the salary rule adds up, and the parameter
order of the rules the page calls. What it adds is the Hebrew: a label per
field and the corpus row each field and allowance stands for, from which the
clause citation (§1.1א) and the allowance's own Hebrew name are taken. A
test holds the Hebrew tables to exactly the names the L4 declares.

§1.1 alone is not a month's pay after the circulars that re-rate its 2008
and 2011 supplements: `SUPERSEDED` says from which month and by which, and
the page marks those lines rather than composing the circulars (MMS-514),
for a component the root does not answer yet. The case's facts, which
§1.1 does not ask about and the other instruments do, are the `teaching
case` of the shared vocabulary (l4/lib/vocabulary.l4): `CASE_FIELDS_HE` and
`CHOICES_HE` are their Hebrew, held by a test to the names the L4 declares.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

import rule_graph

esc = html.escape

ROOT_RULE = "salary of a teaching employee"
REPO = Path(__file__).resolve().parent.parent
SALARY_ROOT = REPO / "l4" / "lib" / "salary-root.l4"
SALARY_TESTS = REPO / "l4" / "tests" / "salary-root-tests.l4"
VOCABULARY = REPO / "l4" / "lib" / "vocabulary.l4"
LAW_RULE = "the salary that governs"
COMPONENT_RULE = "the component that governs"
FIGURE_RULE = "§1.1's figure for"
PAY_ITEM_OF = "the pay item of"
CASE_OF_MONTH = "the case of the month"
CASE_RECORD = "teaching case"
CASE_EXAMPLE = "a State teacher in a primary school"
ITEM_ENUM = "pay item"
ITEM_NAME_RULE = "the name of the item"
# what the page asks salary-root about each pay item, by what it shows
ITEM_RULES = {
    "answer": "the item's answer in the month",
    "module": "the module that governs the item",
    "title": "the title that governs the item",
    "rule": "the rule that governs the item",
    "modules": "the modules that speak to the item",
    "titles": "the titles that speak to the item",
    "says": "what each says of the item",
    "contradicted": "the item is contradicted in the month",
}
ALLOWANCE_RULE = "percentage allowance amount"
MONTH_RECORD = "salary month"
HELD_RECORD = "allowance held"
ALLOWANCE_ENUM = "percentage allowance"
# the file's own worked example, which the "דוגמה מהקוד" button fills in
EXAMPLE = "a full-time teacher in March 2012"
EXAMPLE_ALLOWANCE = "class education at 10%"
POPULATION_ENUM = "postponed population"

# Later circulars, already encoded, re-rate two of §1.1's components; §1.1
# itself was last updated on 2.2.2010 and its own heading says newer
# circulars prevail. From these months the page marks the component as
# §1.1's figure, not the month's (MMS-514), and names what replaced it.
SUPERSEDED = {
    "2008 supplement": ("2008-12-01", [("תשס\"ט/3", "circulars/2008-09_tashsat_03.html"),
                                       ("תש\"ע/2", "circulars/2009-10_tasha_02.html")]),
    "2011 supplement": ("2013-04-01", [("תשע\"ג/6", "circulars/2012-13_tashag_06.html"),
                                       ("תשע\"ג/9", "circulars/2012-13_tashag_09.html")]),
}

P = "chp_1א___sec_1_1__hc_2"
F1, F2, F3 = P + "__para_f__subpara_1", P + "__para_f__subpara_2", P + "__para_f__subpara_3"

# The record's fields: the Hebrew a reader is asked, and the rows of §1.1
# that need the value (whose citations the form shows).
FIELDS_HE: dict[str, tuple[str, list[str]]] = {
    "month": ("חודש השכר", [P + "__para_b", P + "__para_c", P + "__para_d"]),
    "full-position combined salary": ("השכר המשולב למשרה מלאה (₪)", [P + "__para_a"]),
    "position fraction of the month": ("חלקיות המשרה (1 = משרה מלאה)", [P + "__para_a"]),
    "is a principal": ("מנהל/ת", [P + "__para_e/p2"]),
    "in a population whose 5% step was postponed":
        ("מאוכלוסייה שיישום שלב ה־5% של תוספת 2008 נדחה לה", [P + "__para_c__hc_1/p2"]),
    "1994 supplement per full position": ('תוספת "הסכם הוראה 94" למשרה מלאה (₪)', [P + "__para_e"]),
}
FIELD_HINTS = {
    "full-position combined salary": "לפי טבלת השכר, הוותק והדרגה (סעיף 1.29). טבלאות השכר אינן מקודדות, ולכן הסכום מוזן כאן.",
    "position fraction of the month": "למשל 0.5 לחצי משרה, 1.2 למשרה ועוד חמישית.",
    "is a principal": "משנה את תוספת 1994 רק בחודשים שלפני 1.9.2001.",
    "1994 supplement per full position": "הסכום מתעדכן עם תוספות היוקר (§1.1ה) ואינו מקודד, ולכן מוזן כאן.",
    "month": "יום כלשהו בחודש. החודש קובע אילו שיעורים של תוספות 3%, 2008 ו־2011 חלים.",
}

# Each allowance of the enum: the row of §1.1ו that lists it.
ALLOWANCE_ROWS: dict[str, str] = {
    "class education": F1 + "/p2",
    "subject, laboratory, grade-level and social coordination": F1 + "/p3",
    "split position": F1 + "/p4",
    "boarding-school supervision": F1 + "/p5",
    "security officer": F1 + "/p6",
    "training": F1 + "/p7",
    "seminar coordination and guidance": F1 + "/p8",
    "technical coordination in vocational centres": F1 + "/p9",
    "management": F1 + "/p10",
    "counselling": F1 + "/p11",
    "matriculation preparation": F1 + "/p12",
    "further training": F2 + "/p2",
    "subject and qualifications": F2 + "/p3",
    "special education": F2 + "/p4",
    "seminars": F2 + "/p5",
    "MA or PhD degree": F2 + "/p6",
    "supervision and guidance": F3 + "/p2",
    "out-of-school activity with pupils": F3 + "/p3",
    "incentives": F3 + "__cls_e__pnt_1",
    "jubilee grant": F3 + "__cls_e__pnt_2",
    "framework agreement": F3 + "__cls_f",
}

# The facts of the case §1.1 does not ask about: the Hebrew a reader is
# asked. The month's own facts (the month, the 5% step's population, the
# combined salary and תוספת 2001 of today) come from §1.1's month, as
# salary-root's `the case of the month` says, and are not asked twice.
CASE_FIELDS_HE: dict[str, str] = {
    "employer": "המעסיק",
    "in post-primary education": "מועסק/ת בחינוך העל־יסודי",
    "in the upper division": "מועסק/ת בחטיבה העליונה",
    "represented by the secondary teachers' organisation": "מיוצג/ת בידי ארגון המורים בבתי הספר העל־יסודיים",
    "combined salary in December 2007": "השכר המשולב בדצמבר 2007 (₪)",
    "supplement 2001 in December 2007": "תוספת 2001 בדצמבר 2007 (₪)",
    "the kind of school": "סוג בית הספר",
    "the interns the teacher mentors": "מספר המתמחים שהמורה חונך/ת (0 אם אין)",
    "the classes in each grade": "מספר הכיתות בכל שכבה, בחטיבה שבראשה או שאותה מרכזים",
    "the roles the teacher holds": "מספר התפקידים שבעדם משולם גמול תפקיד (0 אם אין)",
    "a further role approved by the district manager": "מנהל/ת המחוז אישר/ה גמול תפקיד מעבר לשני",
}
CASE_HINTS = {
    "combined salary in December 2007": "חלק מההסכמים מחשבים את תוספת 2008 על השכר של דצמבר 2007.",
    "the kind of school": "חוזרי הבעלויות פונים לבתי ספר מסוגים אלה בלבד.",
}
# each choice of an enum field, in Hebrew
CHOICES_HE: dict[str, dict[str, str]] = {
    "the teacher's employer": {
        "employed by the State": "המדינה",
        "employed by a local authority": "רשות מקומית",
        "employed by another owning body": "בעלות אחרת (רשת, תאגיד)",
    },
    "the kind of school in the case": {
        "a recognised unofficial special-education school": "בית ספר לחינוך מיוחד, מוכר שאינו רשמי",
        "a Ma'ayan HaChinuch HaTorani or Chinuch Atzmai primary school": "בית ספר יסודי של מעיין החינוך התורני או של החינוך העצמאי",
        "a recognised unofficial special-education kindergarten": "גן לחינוך מיוחד, מוכר שאינו רשמי",
        "another school": "בית ספר אחר",
    },
}

FIELD_LINE = re.compile(r"^\s+`([^`]+)`\s+IS\s+AN?\s+(.+?)\s*(?:@desc\s+(.*))?$")
CTOR_LINE = re.compile(r"^\s+`([^`]+)`\s*$|^\s+([A-Za-z][\w ]*?)\s*$")
SEE = re.compile(r"\s*\(ראה[^)]*\)\s*")


def _block(lines: list[str], head: re.Pattern) -> tuple[int, list[str]]:
    """The indented lines under the first line matching `head`."""
    for i, line in enumerate(lines):
        if head.match(line):
            out = []
            for l in lines[i + 1:]:
                if l.strip() and not l[:1].isspace():
                    break
                if l.strip():
                    out.append(l)
            return i, out
    raise KeyError(head.pattern)


def record_fields(lines: list[str], name: str) -> list[dict]:
    """`DECLARE <name> HAS` → [{name, type, desc}]."""
    _, body = _block(lines, re.compile(rf"^DECLARE\s+`{re.escape(name)}`\s+HAS\b"))
    out = []
    for l in body:
        m = FIELD_LINE.match(l)
        if m:
            t = m.group(2).strip()
            out.append({"name": m.group(1), "type": t.strip("`"), "desc": (m.group(3) or "").strip()})
    return out


def enum_ctors(lines: list[str], name: str) -> tuple[list[str], list[str]]:
    """`DECLARE <name> IS ONE OF` → (constructors, the akn keys of its @ref)."""
    i, body = _block(lines, re.compile(rf"^DECLARE\s+`{re.escape(name)}`\s+IS\s+ONE\s+OF\b"))
    refs = []
    for l in reversed(lines[:i]):
        if not l.startswith("@"):
            break
        if l.startswith("@ref"):
            refs = rule_graph.REF.findall(l)
    out = []
    for l in body:
        m = CTOR_LINE.match(l)
        if m:
            out.append(m.group(1) or m.group(2))
    return out, refs


def params(lines: list[str], rule: str) -> list[dict]:
    """The GIVEN parameters of `rule`, in order, and checks that the rule is
    applied prefix (`f a b`), the only shape the page writes a call in."""
    for i, l in enumerate(lines):
        m = re.match(rf"^DECIDE\s+`{re.escape(rule)}`(.*?)\s+IS\b", l)
        if not m:
            continue
        given: list[dict] = []
        j = i
        while j > 0 and lines[j - 1].strip() and not lines[j].startswith("GIVEN"):
            j -= 1
        for g in (lines[j:i] if lines[j].startswith("GIVEN") else []):
            g = re.sub(r"@desc.*$", "", g).strip()
            g = re.sub(r"^GIVEN\s+", "", g)
            if g.startswith("GIVETH") or not g:
                continue
            for part in g.split(","):
                pm = re.match(r"^\s*(`[^`]+`|\w+)\s+IS\s+(?:AN?\s+)?(.+?)\s*$", part)
                if pm:
                    given.append({"name": pm.group(1).strip("`"), "type": pm.group(2).replace("`", "")})
        head = [t.strip("`") for t in re.findall(r"`[^`]+`|\S+", m.group(1))]
        assert head == [p["name"] for p in given], f"{rule}: not a prefix rule over its GIVENs ({head})"
        return given
    raise KeyError(rule)


def literal(v: str):
    """An L4 literal of the example, as the form holds it."""
    v = v.strip()
    m = re.fullmatch(r"DATE_FROM_DMY\s+(\d+)\s+(\d+)\s+(\d+)", v)
    if m:
        d, mo, y = map(int, m.groups())
        return f"{y:04d}-{mo:02d}-{d:02d}"
    if v in ("TRUE", "FALSE"):
        return v == "TRUE"
    if v.startswith("`") and v.endswith("`"):
        return v.strip("`")
    assert re.fullmatch(r"\d+(\.\d+)?%?", v), v
    return v


def example(lines: list[str], name: str) -> dict:
    """`<name>` MEANS `record` WITH  field IS value … → {field: value}."""
    _, body = _block(lines, re.compile(rf"^`{re.escape(name)}`\s+MEANS\b"))
    out = {}
    for l in body:
        m = re.match(r"^\s+`([^`]+)`\s+IS\s+(.+?)\s*$", l)
        if m:
            out[m.group(1)] = literal(m.group(2))
    return out


def cases(lines: list[str], rule: str) -> list[tuple[str, str]]:
    """`DECIDE <rule> … IS CONSIDER …` → [(constructor, what its WHEN gives)]."""
    _, body = _block(lines, re.compile(rf"^DECIDE\s+`{re.escape(rule)}`"))
    return re.findall(r"^\s+WHEN\s+`([^`]+)`\s+THEN\s+(.+?)\s*$", "\n".join(body), re.M)


def law(components: list[dict]) -> dict:
    """What the page asks salary-root, read off it, the vocabulary and the
    tests beside it: the case's fields, which of §1.1's components the root
    answers and by which pay item, the root's other items, and the example
    case."""
    root = SALARY_ROOT.read_text(encoding="utf-8").splitlines()
    vocab = VOCABULARY.read_text(encoding="utf-8").splitlines()
    # §1.1's rule for each component, and the pay item the root answers it by
    figure = {re.sub(r"\s+m$", "", v).strip("`"): k for k, v in cases(root, FIGURE_RULE)}
    item_of = {k: re.fullmatch(r"JUST\s+`([^`]+)`", v).group(1) for k, v in cases(root, PAY_ITEM_OF)}
    for c in components:
        c["ctor"] = figure.get(c["name"])
        c["item"] = item_of.get(c["ctor"])
    assert {c["ctor"] for c in components} - {None} == set(figure.values()), "§1.1's figure for: not §1.1's components"
    # the case: every field of `teaching case` but those the month supplies
    _, body = _block(root, re.compile(rf"^DECIDE\s+`{re.escape(CASE_OF_MONTH)}`"))
    set_by = dict(re.findall(r"^\s+`([^`]+)`\s+IS\s+(.+?)\s*$", "\n".join(body), re.M))
    fields = record_fields(vocab, CASE_RECORD)
    assert set(set_by) == {f["name"] for f in fields}, "the case of the month does not set every field"
    from_month = [f["name"] for f in fields if not set_by[f["name"]].startswith("c's ")]
    asked = [f for f in fields if f["name"] not in from_month]
    assert set(CASE_FIELDS_HE) == {f["name"] for f in asked}, "CASE_FIELDS_HE does not match the L4 record"
    for f in asked:
        f.update(label=CASE_FIELDS_HE[f["name"]], hint=CASE_HINTS.get(f["name"], ""))
        if f["type"] not in ("NUMBER", "BOOLEAN", "DATE"):
            ctors, _ = enum_ctors(vocab, f["type"])
            assert set(CHOICES_HE[f["type"]]) == set(ctors), f"CHOICES_HE does not match {f['type']}"
            f["choices"] = [{"name": k, "label": CHOICES_HE[f["type"]][k]} for k in ctors]
    items, _ = enum_ctors(vocab, ITEM_ENUM)
    names = {k: v.strip('"') for k, v in cases(vocab, ITEM_NAME_RULE)}
    assert set(names) == set(items), "the name of the item does not name every item"
    tests = SALARY_TESTS.read_text(encoding="utf-8").splitlines()
    ex = example(tests, CASE_EXAMPLE)
    return {
        "module": SALARY_ROOT.name.removesuffix(".l4"),
        "rule": LAW_RULE, "component": COMPONENT_RULE, "figure": FIGURE_RULE,
        "caseRecord": CASE_RECORD, "caseOfMonth": CASE_OF_MONTH,
        "fields": asked,
        "fromMonth": [{"name": f["name"], "type": f["type"]} for f in fields if f["name"] in from_month],
        "items": [{"name": i, "label": names[i], "component": next((c["name"] for c in components if c["item"] == i), None)}
                  for i in items],
        "itemRules": ITEM_RULES,
        "example": {k: v for k, v in ex.items() if k not in from_month},
    }


def spec(section, l4: Path, cites: dict[str, str], href=lambda key: "") -> dict:
    """Everything the page needs to know about §1.1's L4, read off the file.
    `href(key)` is the link to a row on the section's own page."""
    text = l4.read_text(encoding="utf-8")
    lines = text.splitlines()
    rows = {}
    for r in section.rows:
        rows.setdefault(r.key, r)
        for a in r.aliases:
            rows.setdefault(a, r)
    label = rule_graph.clause_labeller(section, cites)
    decls = rule_graph.declarations(l4)

    def cite(keys: list[str]) -> str:
        return " · ".join(dict.fromkeys(cites[k] for k in keys))

    # a citation a reader can use: the clause's own words ("תוספת 3%") with
    # its number and a link to it, never the number alone, which says
    # nothing to someone who has not got the takanon open beside them
    def refs(keys: list[str]) -> list[dict]:
        out, seen = [], set()
        for k in keys:
            words, num = label("", [k])
            num = num or cites[k]
            if num in seen:
                continue
            seen.add(num)
            out.append({"words": words, "num": num, "href": href(k)})
        return out

    fields = record_fields(lines, MONTH_RECORD)
    assert set(FIELDS_HE) == {f["name"] for f in fields}, "FIELDS_HE does not match the L4 record"
    for f in fields:
        he, keys = FIELDS_HE[f["name"]]
        f.update(label=he, cite=cite(keys), refs=refs(keys), hint=FIELD_HINTS.get(f["name"], ""))
    pops, pop_refs = enum_ctors(lines, POPULATION_ENUM)
    pop_rows = [k for k in pop_refs if "subpara" in k]
    assert len(pop_rows) == len(pops), "the populations' rows do not match the enum"

    kinds, _ = enum_ctors(lines, ALLOWANCE_ENUM)
    assert set(ALLOWANCE_ROWS) == set(kinds), "ALLOWANCE_ROWS does not match the L4 enum"
    held = record_fields(lines, HELD_RECORD)
    kind_field = next(f["name"] for f in held if f["type"] == ALLOWANCE_ENUM)
    rate_field = next(f["name"] for f in held if f["type"] == "NUMBER")

    def allowance_label(k: str) -> str:
        t = " ".join(rows[ALLOWANCE_ROWS[k]].text.split())
        return rule_graph.HEAD_SPLIT.split(SEE.sub(" ", t).strip(), maxsplit=1)[0].strip()

    # the components: what the salary rule adds up, in its own order; a
    # component with no @ref of its own is cited by the nearest rule it
    # calls that has one (`3% supplement` by `3% supplement rate`)
    def nearest_refs(n: str) -> list[str]:
        seen, todo = set(), [n]
        while todo:
            x = todo.pop(0)
            if x in seen or x not in decls:
                continue
            seen.add(x)
            if decls[x]["refs"]:
                return decls[x]["refs"]
            _, edges, _ = rule_graph.walk(decls, x)
            todo += [b for a, b in edges if a == x and not b.startswith("in:")]
        return []

    _, edges, _ = rule_graph.walk(decls, ROOT_RULE)
    components = []
    for a, b in edges:
        if a == ROOT_RULE and not b.startswith("in:"):
            words, c = label(b, nearest_refs(b))
            near = nearest_refs(b)
            components.append({"name": b, "label": words, "cite": c, "params": params(lines, b),
                               "href": href(near[0]) if near else ""})
    root_words, root_cite = label(ROOT_RULE, decls[ROOT_RULE]["refs"])
    ex = example(lines, EXAMPLE)
    assert set(ex) == {f["name"] for f in fields}, "the worked example does not fill the record"
    ex_held = example(lines, EXAMPLE_ALLOWANCE)
    ex_rate = ex_held[rate_field]
    pct = ex_rate[:-1] if ex_rate.endswith("%") else str(round(float(ex_rate) * 100, 10)).removesuffix(".0")
    return {
        "file": l4.name,
        "imports": import_closure(l4),
        "lines": len(lines),
        "record": MONTH_RECORD,
        "fields": fields,
        "populations": [" ".join(rows[k].text.split()) for k in pop_rows],
        "allowance": {
            "record": HELD_RECORD, "kindField": kind_field, "rateField": rate_field,
            "rule": ALLOWANCE_RULE, "params": params(lines, ALLOWANCE_RULE),
            "kinds": [{"name": k, "label": allowance_label(k), "cite": cites[ALLOWANCE_ROWS[k]],
                       "href": href(ALLOWANCE_ROWS[k])} for k in kinds],
        },
        "root": {"name": ROOT_RULE, "label": root_words, "cite": root_cite,
                 "params": params(lines, ROOT_RULE),
                 "href": href(decls[ROOT_RULE]["refs"][0]) if decls[ROOT_RULE]["refs"] else ""},
        "components": components,
        "law": (lw := law(components)),
        # a component the root answers is the law's, not §1.1's: no mark
        "superseded": {k: {"from": f, "by": [{"label": l, "href": h} for l, h in by]}
                       for k, (f, by) in SUPERSEDED.items()
                       if not next(c for c in components if c["name"] == k)["item"]},
        "example": {"fields": ex, "case": lw["example"],
                    "allowances": [{"kind": ex_held[kind_field], "percent": pct}]},
    }


MODULES = Path(__file__).resolve().parent.parent / "l4" / "modules"


def module_file(name: str, beside: Path) -> Path | None:
    """The file an `IMPORT name` reaches: the module directory every run
    puts on the library path (MMS-524), else the importing file's own
    directory; None for a library built into the evaluator (`prelude`)."""
    for f in (MODULES / f"{name.strip('`')}.l4", beside / f"{name.strip('`')}.l4"):
        if f.exists():
            return f
    return None


def import_closure(l4: Path) -> list[str]:
    """Every module §1.1 reaches, its own imports first and theirs after:
    a module a shared vocabulary moved into another file (`parties`,
    MMS-532) is still shipped, which a list of §1.1's own imports missed."""
    order, queue = [], re.findall(r"^IMPORT\s+(\S+)", l4.read_text(encoding="utf-8"), re.M)
    while queue:
        name = queue.pop(0).strip("`")
        if name in order:
            continue
        order.append(name)
        f = module_file(name, l4.parent)
        if f is not None:
            queue += re.findall(r"^IMPORT\s+(\S+)", f.read_text(encoding="utf-8"), re.M)
    return order


DIRECTIVE = re.compile(r"^#[A-Z]+\b")
# a line that starts a new declaration, not one that continues a directive
DECL_START = re.compile(r"^\s*(GIVEN|GIVETH|DECIDE|DECLARE|IMPORT|MEANS|ASSUME|@|§|--)")


def without_tests(text: str) -> str:
    """A module as the page ships it: its own tests (`#EVAL`, `#ASSERT`,
    and the lines that continue one) left out, each kept as an empty line
    so that every other line keeps its number. The page does not run them;
    `make l4` and `make roots` do. Measured on the root (MMS-525, in Node):
    112 s to a first answer with them, 44 s without."""
    out, inside = [], False
    for line in text.split("\n"):
        if DIRECTIVE.match(line):
            inside = True
            out.append("")
        elif inside and line[:1].isspace() and line.strip() and not DECL_START.match(line):
            out.append("")
        else:
            inside = False
            out.append(line)
    return "\n".join(out)


def ship(s: dict, assets: Path) -> dict:
    """Write the L4 the page runs — salary-root and every module it reaches
    (`prelude` is built into the evaluator), without their tests — to
    assets/calc/modules.json, each under the name it is imported by, and
    say in the spec where it is."""
    d = assets / "calc"
    d.mkdir(parents=True, exist_ok=True)
    files = {s["law"]["module"]: without_tests(SALARY_ROOT.read_text(encoding="utf-8"))}
    for name in import_closure(SALARY_ROOT):
        f = module_file(name, SALARY_ROOT.parent)
        if f is not None:
            files[name] = without_tests(f.read_text(encoding="utf-8"))
    (d / "modules.json").write_text(json.dumps(files, ensure_ascii=False), encoding="utf-8")
    return {**s, "modules": "calc/modules.json", "imports": list(files)}


HEB = re.compile(r"([\u05d0-\u05ea])")


def cite_text(cite: str) -> str:
    """A citation as plain text that keeps its order inside Hebrew: each
    one isolated left to right (LRI…PDI), and a left-to-right mark after
    each Hebrew letter, so "§1.1ה ¶2" does not reorder to "§1.12¶ ה"."""
    return " · ".join("\u2066" + HEB.sub("\\1\u200e", c) + "\u2069" for c in cite.split(" · "))


def refs_html(refs: list[dict]) -> str:
    """"בתקנון: תוספת 3% §1.1ב · תוספת 2008 §1.1ג": each clause by its own
    words and its number, linked to it on the section's page."""
    items = []
    for r in refs:
        inner = (f'{esc(r["words"])} ' if r["words"] else "") + f'<bdi dir="ltr">{esc(r["num"])}</bdi>'
        items.append(f'<a href="{esc(r["href"])}">{inner}</a>' if r["href"] else inner)
    return '<span class="cite">בתקנון: ' + " · ".join(items) + "</span>"


def form_html(s: dict) -> str:
    """The form, server-rendered: one control per field of the record, in
    the record's order, and the list of allowances."""
    out = []
    for f in s["fields"]:
        fid = "f-" + re.sub(r"\W+", "-", f["name"]).strip("-")
        name = esc(f["name"])
        meta = refs_html(f["refs"]) + f'<code class="l4n" dir="ltr">{name}</code>'
        hint = f'<span class="hint">{esc(f["hint"])}</span>' if f["hint"] else ""
        if f["name"] == "in a population whose 5% step was postponed":
            hint += ('<details class="pops"><summary>ארבע האוכלוסיות</summary><ol>'
                     + "".join(f'<li lang="he">{esc(p)}</li>' for p in s["populations"]) + "</ol></details>")
        if f["type"] == "BOOLEAN":
            out.append(f'<div class="fld chk"><label><input type="checkbox" id="{fid}" data-field="{name}"> '
                       f'{esc(f["label"])}</label>{meta}{hint}</div>')
            continue
        attrs = ('type="date" required' if f["type"] == "DATE" else
                 'type="text" inputmode="decimal" dir="ltr" required autocomplete="off"')
        out.append(f'<div class="fld"><label for="{fid}">{esc(f["label"])}</label>{meta}'
                   f'<input id="{fid}" {attrs} data-field="{name}">{hint}</div>')
    out.append(case_html(s))
    a = s["allowance"]
    opts = "".join(f'<option value="{esc(k["name"])}">{esc(k["label"])}</option>' for k in a["kinds"])
    pct = next(c for c in s["components"] if c["name"] == "percentage allowances")
    out.append(
        '<fieldset class="allow"><legend>תוספות אחוזיות</legend>'
        + refs_html([{"words": pct["label"], "num": pct["cite"], "href": pct["href"]}]) +
        f'<code class="l4n" dir="ltr">{esc(a["record"])}</code>'
        '<p class="hint">כל תוספת שהעובד מחזיק בחודש, ושיעורה — שנקבע בסעיף של התוספת עצמה ואינו מקודד כאן.</p>'
        '<ol class="allow-list"></ol>'
        f'<template id="allow-row"><li class="arow"><select aria-label="התוספת">{opts}</select>'
        '<span class="rate"><input type="text" inputmode="decimal" dir="ltr" aria-label="שיעור באחוזים" '
        'placeholder="10" autocomplete="off"><span>%</span></span>'
        '<button type="button" class="del" aria-label="הסרת התוספת">×</button></li></template>'
        '<button type="button" class="add">+ הוספת תוספת</button></fieldset>')
    return "".join(out)


def case_html(s: dict) -> str:
    """The facts of the case §1.1 does not ask about and the other
    instruments do: one control per field of `teaching case` the month does
    not supply, in the record's order."""
    lw = s["law"]
    out = []
    for f in lw["fields"]:
        fid = "c-" + re.sub(r"\W+", "-", f["name"]).strip("-")
        name = esc(f["name"])
        meta = f'<code class="l4n" dir="ltr">{name}</code>'
        hint = f'<span class="hint">{esc(f["hint"])}</span>' if f["hint"] else ""
        if f["type"] == "BOOLEAN":
            out.append(f'<div class="fld chk"><label><input type="checkbox" id="{fid}" data-case="{name}"> '
                       f'{esc(f["label"])}</label>{meta}{hint}</div>')
        elif f.get("choices"):
            # the example's choice is the default: a select shows its first
            # option otherwise, which is no more likely than the others
            ex = lw["example"].get(f["name"])
            opts = "".join(f'<option value="{esc(c["name"])}"{" selected" if c["name"] == ex else ""}>'
                           f'{esc(c["label"])}</option>' for c in f["choices"])
            out.append(f'<div class="fld"><label for="{fid}">{esc(f["label"])}</label>{meta}'
                       f'<select id="{fid}" data-case="{name}">{opts}</select>{hint}</div>')
        else:
            out.append(f'<div class="fld"><label for="{fid}">{esc(f["label"])}</label>{meta}'
                       f'<input id="{fid}" type="text" inputmode="decimal" dir="ltr" required autocomplete="off" '
                       f'data-case="{name}">{hint}</div>')
    return ('<fieldset class="case"><legend>עובדות שהדין שואל עליהן</legend>'
            f'<code class="l4n" dir="ltr">{esc(lw["caseRecord"])}</code>'
            '<p class="hint">התקנון אינו שואל עליהן. ההסכמים והחוזרים ששורש הדין שואל — כן: '
            'מי המעסיק, באיזה חינוך ובאיזו חטיבה, ומה התפקידים.</p>'
            + "".join(out) + '</fieldset>')


def body(s: dict, section_link: str, findings: list[dict], findings_href: str) -> str:
    data = json.dumps(s, ensure_ascii=False).replace("</", "<\\/")
    fl = "".join(
        f'<li><a href="{findings_href}#{esc(f["id"])}"><bdi dir="ltr">{esc(f["id"])}</bdi></a> — '
        f'{esc(f["title"])}{" <em>(טרם נבדק בידי עורך הדין)</em>" if f.get("review") == "unreviewed" else ""}</li>'
        for f in findings)
    return (
        '<h1>מחשבון שכר</h1>'
        '<p class="lede">השכר החודשי של עובד הוראה לפי הדין: לכל רכיב, מה שהדין נותן אחרי שנשקל כל מסמך '
        'שמדבר עליו — התקנון, ההסכמים הקיבוציים והחוזרים — לפי סדר העדיפות ביניהם. '
        f'הרכיבים הם אלה שמונה {section_link}: השכר המשולב, תוספת 3%, תוספת 2008, תוספת 2011, '
        'תוספת "הסכם הוראה 94" והתוספות האחוזיות שמזינים. '
        'לא נכללים כאן תשלומים שנתיים ורכיבים שנקבעים בסעיפים אחרים (הבראה, ביגוד, נסיעות, טלפון ועוד).</p>'
        '<ul class="calc-notes">'
        '<li><strong>התשובה היא של הדין; המסמכים הם הנימוק.</strong> לכל רכיב מוצג הסכום שהדין נותן. '
        'מתחתיו, בלחיצה, המסמך שגובר ולפי איזה כלל, ומה אומר כל מסמך אחר שמדבר על הרכיב.</li>'
        '<li><strong>רכיב ששורש הדין עוד אינו עונה עליו מסומן.</strong> הסכום שלו הוא של סעיף 1.1 בלבד, '
        'בלי מה שמסמכים מאוחרים אומרים עליו.</li>'
        '<li><strong>השכר המשולב מוזן ביד.</strong> הוא נקבע בטבלאות השכר, לפי ותק ודרגה, והטבלאות אינן מקודדות. '
        'כך גם תוספת "הסכם הוראה 94" ושיעור כל תוספת אחוזית: הטקסט קובע אותם במקום אחר, והמחשבון אינו ממציא אותם.</li>'
        '<li><strong>החישוב הוא הקוד של האתר.</strong> הדפדפן מריץ את קוד ה־L4 של האתר — שורש הדין וכל המסמכים שהוא מייבא — '
        'במעריך של L4 עצמו שהודר ל־WebAssembly: אין כאן מימוש שני של הכללים. '
        'הטעינה הראשונה אורכת כחצי דקה עד דקה; מתחת לתוצאה מוצגות עקבות החישוב כפי ש־L4 מדפיס אותן.</li>'
        f'<li><strong>הקריאות הן ממצאים שטרם נבדקו.</strong> היכן שהטקסט אינו מכריע, הקוד מאמץ קריאה, '
        f'ועורך הדין טרם בדק אותה:<ul class="calc-findings">{fl}</ul></li>'
        '</ul>'
        '<form class="calc" novalidate>'
        f'<div class="calc-form">{form_html(s)}</div>'
        '<div class="calc-go"><button type="submit" class="go" disabled>חישוב</button>'
        '<button type="button" class="example">דוגמה מהקוד</button>'
        '<span class="status" role="status" aria-live="polite">טוען את L4…</span></div>'
        '</form>'
        '<section class="calc-out" hidden aria-live="polite"></section>'
        '<noscript><p class="empty">המחשבון מריץ את L4 בדפדפן, ודורש JavaScript.</p></noscript>'
        f'<script type="application/json" id="calc-spec">{data}</script>'
        '<link rel="stylesheet" href="assets/calculator.css">'
        '<script type="module" src="assets/calculator.js"></script>')
