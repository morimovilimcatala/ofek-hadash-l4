"""The root and the collections' roots as pages (MMS-521).

The root (l4/lib/root.l4) is the one place to ask what the law gives; the
collections' roots (takanon-root, agreements-root, circulars-root) register
the instruments of their collection and what each claims, and the root
imports them beside the precedence module. Each gets a page: the root's at
root.html, a collection root's inside its collection (circulars/root.html).

A page is read off the module's own source and what `make l4` recorded for
it (build/l4/lib/<module>.run.json): nothing on it is typed by hand. The
root's page shows the gate — `unresolved contradictions`, asserted empty —
and the resolutions, from the `the resolutions report` the module evaluates.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "l4" / "lib"
BUILD = ROOT / "build" / "l4" / "lib"

# (module, page, collection it sits in or "", its heading, what it is)
ROOTS = [
    ("root", "root.html", "",
     "השורש — מקור אחד לשאלה מה הדין נותן",
     "לכל פריט שכר, השורש מייבא כל מסמך שמדבר עליו, אוסף מה כל אחד אומר על המקרה, "
     "ושואל את סדר העדיפות — שמקודד פעם אחת — מי גובר ולפי איזה כלל. כל שאלה על הדין "
     "(המחשבון, עמוד הסתירות) שואלת את השורש, ולא מסמך אחד. היכן ששני מסמכים או יותר "
     "נותנים תשובות שונות זו סתירה, והבנייה אדומה עד שהשורש מכריע בה בשמו של כלל."),
    ("takanon-root", "takanon/root.html", "takanon",
     "שורש התקנון",
     "כל סעיף בתקנון שמדבר על פריט באוצר המילים המשותף, רשום פעם אחת כמסמך, ומה הוא אומר "
     "לכל מקרה. השורש מייבא אותו לצד שורשי ההסכמים והחוזרים."),
    ("agreements-root", "agreements/root.html", "agreements",
     "שורש ההסכמים",
     "כל הסכם קיבוצי שמדבר על פריט באוצר המילים המשותף, רשום פעם אחת כמסמך, ומה הוא אומר "
     "לכל מקרה. השורש מייבא אותו לצד שורשי התקנון והחוזרים."),
    ("circulars-root", "circulars/root.html", "circulars",
     "שורש החוזרים",
     "כל חוזר שמדבר על פריט באוצר המילים המשותף, רשום פעם אחת כמסמך, ומה הוא אומר לכל "
     "מקרה. השורש מייבא אותו לצד שורשי התקנון וההסכמים, וסדר העדיפות מכריע ביניהם — "
     "ובכלל זה החוזר המאוחר על המוקדם."),
]

STRING = re.compile(r'"((?:[^"\\]|\\.)*)"')


def page_for(coll: str) -> str | None:
    """The root page that sits in a collection, if there is one."""
    return next((here for _, here, c, _, _ in ROOTS if c == coll), None)


def results(module: str) -> list[dict]:
    f = BUILD / f"{module}.run.json"
    if not f.exists():
        return []
    return json.loads(f.read_text(encoding="utf-8")).get("results", [])


def strings(value: str) -> list[str]:
    """The strings of an L4 `LIST "a", "b"` value, unescaped."""
    return [s.replace('\\"', '"').replace("\\\\", "\\") for s in STRING.findall(value or "")]


def evaluated(module: str, name: str) -> str | None:
    """The value of the `#EVAL <name>` line of a module, as `make l4` recorded it."""
    src = (LIB / f"{module}.l4").read_text(encoding="utf-8").splitlines()
    line = next((i + 1 for i, l in enumerate(src) if l.strip() == f"#EVAL {name}"), None)
    for r in results(module):
        if r.get("kind") == "value" and line and re.search(rf":{line}:", r.get("range", "")):
            return r.get("value")
    return None


def registered(module: str) -> list[tuple[str, str]]:
    """The instruments a collection root includes, (module, title), as the
    root itself evaluates them: each instrument describes itself in its own
    file, so they are read from `make l4`'s results, not from source text."""
    src = (LIB / f"{module}.l4").read_text(encoding="utf-8")
    expr = next(l.strip()[len("#EVAL "):] for l in src.splitlines() if l.startswith("#EVAL map"))
    return [tuple(x.split(" | ", 1)) for x in strings(evaluated(module, expr) or "")]


def page_body(module: str, here: str, coll: str, heading: str, about: str, *,
              esc, rel, code_html, href_of, coll_name, coll_href) -> str:
    rs = results(module)
    asserts = [r for r in rs if r.get("kind") == "assertion"]
    held = sum(r.get("value") is True for r in asserts)
    crumbs = '<a href="{0}">מסמכים</a>'.format(rel("index.html", here))
    if coll:
        crumbs += f' / <a href="{rel(coll_href(coll), here)}">{esc(coll_name(coll))}</a>'
    parts = [f'<header class="sec-head"><nav class="crumbs">{crumbs}</nav>'
             f'<div class="title-row"><h1>{esc(heading)}</h1></div>'
             f'<div class="stats">'
             + (f'<span><b>{held}</b> מתוך {len(asserts)} בדיקות מתקיימות</span>' if asserts else '')
             + f'<code dir="ltr">l4/lib/{esc(module)}.l4</code></div></header>',
             f'<p class="lede">{esc(about)}</p>']
    if module == "root":
        unresolved = strings(evaluated("root", "`unresolved contradictions`") or "")
        cases = evaluated("root", "count `the cases checked`") or "?"
        state = ("אין סתירה שלא הוכרעה" if not unresolved
                 else f"{len(unresolved)} סתירות שלא הוכרעו — הבנייה אדומה")
        parts.append(f'<p class="lede"><b>{esc(state)}</b>, ב־{esc(cases)} המקרים שנבדקו. '
                     'הסתירות עצמן נשארות כבדיקות: אם מסמך יפסיק לחלוק, הבנייה תאדים שוב.</p>')
        links = " · ".join(f'<a href="{rel(h, here)}">{esc(t)}</a>' for m, h, c, t, _ in ROOTS if c)
        parts.append(f'<p class="lede">המסמכים רשומים בשורשי האוספים: {links}. '
                     f'סדר העדיפות: <code dir="ltr">l4/lib/precedence.l4</code>, בקוד שלהלן.</p>')
        rows = []
        for line in strings(evaluated("root", "`the resolutions report`") or ""):
            item, sources, governs, rule, n = (line.split(" | ") + [""] * 5)[:5]
            rows.append("<tr>" + "".join(f"<td>{esc(x)}</td>" for x in
                                        (item, sources.replace(" · ", " ‖ "), governs, rule, n)) + "</tr>")
        if rows:
            parts.append('<h2>ההכרעות</h2><div class="tablewrap"><table class="grid-table">'
                         '<thead><tr><th>פריט</th><th>המסמכים שחלוקים</th><th>גובר</th>'
                         '<th>לפי</th><th>מקרים</th></tr></thead>'
                         f'<tbody>{"".join(rows)}</tbody></table></div>')
    else:
        items = []
        for m, t in registered(module):
            h = href_of(m)
            items.append(f'<li><a href="{rel(h, here)}">{esc(t)}</a></li>' if h else f"<li>{esc(t)}</li>")
        parts.append('<h2>המסמכים הרשומים</h2><ul class="lede">' + "".join(items) + "</ul>"
                     f'<p class="lede">השורש: <a href="{rel("root.html", here)}">{esc(ROOTS[0][3])}</a>.</p>')
    blocks = [module] + (["precedence", "vocabulary"] if module == "root" else [])
    for b in blocks:
        lines = (LIB / f"{b}.l4").read_text(encoding="utf-8").splitlines()
        parts.append(f'<h2 dir="ltr"><code>l4/lib/{esc(b)}.l4</code></h2>'
                     f'<div class="l4">{code_html(list(enumerate(lines, 1)))}</div>')
    return "".join(parts)
