"""The salary calculator (calculator.html): a form for §1.1's
`salary of a teaching employee`, evaluated in the browser by L4 itself.

Nothing here computes a salary. The page ships §1.1's own L4 file and the
`common` and `conventions` modules it imports; on "חישוב" the browser
appends the form's values and an `#EVALTRACE` to that source and runs it
through the L4 evaluator
compiled to WebAssembly (tools/assets/l4wasm/, built by
toolchain/build-wasm.sh). There is no second implementation of the rules.

What this module reads off the L4 file at build time, so a renamed field,
allowance or rule changes the form with it: the fields of the `salary month`
record and their types, the `percentage allowance` enum, the `allowance
held` record, the components the salary rule adds up, and the parameter
order of the rules the page calls. What it adds is the Hebrew: a label per
field and the corpus row each field and allowance stands for, from which the
clause citation (§1.1א) and the allowance's own Hebrew name are taken. A
test holds the Hebrew tables to exactly the names the L4 declares.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

import rule_graph

esc = html.escape

ROOT_RULE = "salary of a teaching employee"
ALLOWANCE_RULE = "percentage allowance amount"
MONTH_RECORD = "salary month"
HELD_RECORD = "allowance held"
ALLOWANCE_ENUM = "percentage allowance"
# the file's own worked example, which the "דוגמה מהקוד" button fills in
EXAMPLE = "a full-time teacher in March 2012"
EXAMPLE_ALLOWANCE = "class education at 10%"
POPULATION_ENUM = "postponed population"

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
        "imports": re.findall(r"^IMPORT\s+(\S+)", text, re.M),
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
        "example": {"fields": ex, "allowances": [{"kind": ex_held[kind_field], "percent": pct}]},
    }


def ship(s: dict, l4: Path, assets: Path) -> dict:
    """Copy the L4 the page runs — §1.1's file and every import that is a
    file beside it (`prelude` is built into the evaluator) — to
    assets/calc/, and say in the spec where it is."""
    d = assets / "calc"
    d.mkdir(parents=True, exist_ok=True)
    (d / l4.name).write_text(l4.read_text(encoding="utf-8"), encoding="utf-8")
    files = {}
    for name in s["imports"]:
        f = l4.parent / f"{name}.l4"
        if f.exists():
            (d / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
            files[name] = f"calc/{f.name}"
    return {**s, "source": f"calc/{l4.name}", "files": files}


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


def body(s: dict, section_link: str, findings: list[dict], findings_href: str) -> str:
    data = json.dumps(s, ensure_ascii=False).replace("</", "<\\/")
    fl = "".join(
        f'<li><a href="{findings_href}#{esc(f["id"])}"><bdi dir="ltr">{esc(f["id"])}</bdi></a> — '
        f'{esc(f["title"])}{" <em>(טרם נבדק בידי עורך הדין)</em>" if f.get("review") == "unreviewed" else ""}</li>'
        for f in findings)
    return (
        '<h1>מחשבון שכר</h1>'
        f'<p class="lede">השכר החודשי של עובד הוראה לפי {section_link} בלבד: השכר המשולב, תוספת 3%, '
        'תוספת 2008, תוספת 2011, תוספת "הסכם הוראה 94" והתוספות האחוזיות שמזינים. '
        'לא נכללים כאן תשלומים שנתיים ורכיבים שנקבעים בסעיפים אחרים (הבראה, ביגוד, נסיעות, טלפון ועוד).</p>'
        '<ul class="calc-notes">'
        '<li><strong>השכר המשולב מוזן ביד.</strong> הוא נקבע בטבלאות השכר, לפי ותק ודרגה, והטבלאות אינן מקודדות. '
        'כך גם תוספת "הסכם הוראה 94" ושיעור כל תוספת אחוזית: הטקסט קובע אותם במקום אחר, והמחשבון אינו ממציא אותם.</li>'
        '<li><strong>החישוב הוא הקוד של האתר.</strong> הדפדפן מריץ את קובץ ה־L4 של §1.1 כפי שהוא מוצג באתר, '
        'במעריך של L4 עצמו שהודר ל־WebAssembly: אין כאן מימוש שני של הכללים. '
        'לכל רכיב מצוין הסעיף שהוא מקודד, ומתחת לתוצאה — עקבות החישוב כפי ש־L4 מדפיס אותם.</li>'
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
