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
# a root's tests sit beside it (l4/tests/<module>-tests.l4, the client,
# 2026-10-22): every #EVAL and #ASSERT about it, and what its page reads
TESTS = ROOT / "l4" / "tests"
TESTS_BUILD = ROOT / "build" / "l4" / "tests"


def tests_of(module: str) -> Path:
    return TESTS / f"{module}-tests.l4"

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
    # one root per family of agreements, as the corpus groups them (MMS-548:
    # the client, 2026-10-22, "Maybe אופק חדש should have its own root as
    # well?"); the agreements' root gathers them
    ("ofek-hadash-root", "agreements/ofek-hadash/root.html", "agreements",
     "שורש הסכמי אופק חדש",
     "כל הסכם של רפורמת אופק חדש שמדבר על פריט באוצר המילים המשותף, רשום פעם אחת כמסמך, "
     "ומה הוא אומר לכל מקרה. שורש ההסכמים מייבא אותו לצד שורשי שאר המשפחות."),
    ("oz-latmura-root", "agreements/oz-latmura/root.html", "agreements",
     "שורש הסכמי עוז לתמורה",
     "כל הסכם של ארגון המורים ורפורמת עוז לתמורה שמדבר על פריט באוצר המילים המשותף, רשום "
     "פעם אחת כמסמך, ומה הוא אומר לכל מקרה. שורש ההסכמים מייבא אותו לצד שורשי שאר המשפחות."),
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


def family_page(family: str) -> str | None:
    """The root page of a family of agreements (agreements/<family>/root.html)."""
    return next((here for _, here, _, _, _ in ROOTS if here == f"agreements/{family}/root.html"), None)


def is_family(here: str) -> bool:
    return here.count("/") == 2


def current() -> bool:
    """Whether the root's tests were checked against the files as they are
    now: the roots are checked on demand (`make roots`), and a build that
    skipped them carries an earlier check's results."""
    import l4run
    try:
        return l4run.is_kept(tests_of("root").resolve(), l4run.compiler_id(l4run.compiler()))
    except (SystemExit, OSError):
        return False


def results(module: str) -> list[dict]:
    """What `make l4` recorded of a root's tests."""
    f = TESTS_BUILD / f"{module}-tests.run.json"
    if not f.exists():
        return []
    return json.loads(f.read_text(encoding="utf-8")).get("results", [])


def strings(value: str) -> list[str]:
    """The strings of an L4 `LIST "a", "b"` value, unescaped."""
    return [s.replace('\\"', '"').replace("\\\\", "\\") for s in STRING.findall(value or "")]


def evaluated(module: str, name: str) -> str | None:
    """The value of the `#EVAL <name>` line of a root's tests, as `make l4`
    recorded it."""
    src = tests_of(module).read_text(encoding="utf-8").splitlines()
    want = f"#EVAL {name}"
    line = next((i + 1 for i, l in enumerate(src) if l.strip() == want), None)
    for r in results(module):
        if r.get("kind") != "value":
            continue
        # by the line's own text where the check recorded it, which survives
        # an edit that moves it; by its number otherwise
        if r.get("line") == want or ("line" not in r and line and re.search(rf":{line}:", r.get("range", ""))):
            return r.get("value")
    return None


def registered(module: str) -> list[tuple[str, str]]:
    """The instruments a collection root includes, (module, title), as the
    root itself evaluates them: each instrument describes itself in its own
    file, so they are read from `make l4`'s results, not from source text."""
    src = tests_of(module).read_text(encoding="utf-8")
    expr = next(l.strip()[len("#EVAL "):] for l in src.splitlines() if l.startswith("#EVAL map"))
    return [tuple(x.split(" | ", 1)) for x in strings(evaluated(module, expr) or "")]


def rulings() -> dict[str, list[list[str]]]:
    """The root's resolutions by the name of their item, each as [the
    titles of the instruments that disagree, the one that governs, the
    rule, the cases it settles], as the root itself reports them."""
    out: dict[str, list[list[str]]] = {}
    for line in strings(evaluated("root", "`the resolutions report`") or ""):
        item, *rest = (line.split(" | ") + [""] * 5)[:5]
        out.setdefault(item, []).append(rest)
    return out


DIRECTIVE = re.compile(r"^#(EVAL|ASSERT|EVALTRACE)\s+(.*)$")
SECTION = re.compile(r"^§+\s+`([^`]*)`")


def test_questions(module: str) -> list[tuple[str, list[tuple[str, list[tuple[int, str, str]]]]]]:
    """A root's tests as the questions they ask (MMS-553): [(section,
    [(question, [(line, kind, expression)])])]. A question is the comment
    block above a run of #EVAL/#ASSERT lines, through any helper code
    between them; a new comment starts the next question. The section is
    the `§§` heading they sit under. A directive's indented continuation
    lines are part of its expression."""
    out: list = []
    comment: list[str] = []
    fresh = False        # the comment has not been asked of yet
    last = None          # the directive whose continuation lines may follow
    for n, line in enumerate(tests_of(module).read_text(encoding="utf-8").splitlines(), 1):
        s = line.strip()
        if last is not None and s and line[:1].isspace() and not s.startswith("--"):
            last[2] = last[2] + " " + s
            continue
        last = None
        m = SECTION.match(s)
        if m:
            out.append((m.group(1), []))
            comment, fresh = [], False
            continue
        if s.startswith("--"):
            if not fresh:
                comment, fresh = [], True
            comment.append(s.lstrip("-").strip())
            continue
        d = DIRECTIVE.match(s)
        if d:
            if not out:
                out.append(("", []))
            qs = out[-1][1]
            if fresh or not qs:
                qs.append((" ".join(comment), []))
                fresh = False
            last = [n, d.group(1), d.group(2)]
            qs[-1][1].append(last)
    return [(sec, [(q, [tuple(x) for x in ds]) for q, ds in qs]) for sec, qs in out if qs]


def answer_html(r: dict | None, kind: str, esc) -> str:
    """What `make l4` recorded for one directive."""
    if r is None:
        return '<li class="res bad"><span class="rk">אין תוצאה</span></li>'
    if kind == "ASSERT":
        ok = r.get("value") is True
        return (f'<li class="res{"" if ok else " bad"}"><span class="rk">{"מתקיים" if ok else "נכשל"}</span></li>')
    v = str(r.get("value", ""))
    short = v if len(v) <= 240 else v[:240] + " …"
    body = (f'<code dir="ltr">{esc(short)}</code>' if short == v else
            f'<details class="tval"><summary><code dir="ltr">{esc(short)}</code></summary>'
            f'<code dir="ltr">{esc(v)}</code></details>')
    return f'<li class="res eval"><span class="rk">ערך</span>{body}</li>'


def tests_html(module: str, esc) -> str:
    """The tests as cards: what each asks, the expression, what the
    compiler answered. The source stays one click away (below)."""
    by_line: dict[int, dict] = {}
    for r in results(module):
        m = re.search(r":(\d+):", r.get("range", ""))
        if m:
            by_line[int(m.group(1))] = r
    parts = []
    for sec, qs in test_questions(module):
        if sec:
            parts.append(f'<h3>{esc(sec)}</h3>')
        for q, ds in qs:
            items = []
            for n, kind, expr in ds:
                items.append(f'<li class="tq-expr"><span class="rl">{n}</span>'
                             f'<code dir="ltr">{esc(expr)}</code></li>'
                             + answer_html(by_line.get(n), kind, esc))
            ask = f'<p class="tq-ask" dir="ltr">{esc(q)}</p>' if q else ""
            parts.append(f'<div class="tcard">{ask}<ul class="results">{"".join(items)}</ul></div>')
    return "".join(parts)


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
    # the roots are checked in every build again (MMS-551, at l4-ide
    # unstable); a page says so only where a root has no results
    if not rs:
        parts.append('<div class="banner">השורש הזה עוד לא נבדק בבנייה הזו.</div>')
    if module == "root":
        unresolved = strings(evaluated("root", "`unresolved contradictions`") or "")
        cases = evaluated("root", "count `the cases checked`") or "?"
        state = ("אין סתירה שלא הוכרעה" if not unresolved
                 else f"{len(unresolved)} סתירות שלא הוכרעו — הבנייה אדומה")
        parts.append(f'<p class="lede"><b>{esc(state)}</b>, ב־{esc(cases)} המקרים שנבדקו. '
                     'הסתירות עצמן נשארות כבדיקות: אם מסמך יפסיק לחלוק, הבנייה תאדים שוב.</p>')
        links = " · ".join(f'<a href="{rel(h, here)}">{esc(t)}</a>' for m, h, c, t, _ in ROOTS if c and not is_family(h))
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
        if module == "agreements-root":
            fams = " · ".join(f'<a href="{rel(h, here)}">{esc(t)}</a>' for m, h, c, t, _ in ROOTS if is_family(h))
            parts.append(f'<p class="lede">כל משפחת הסכמים רושמת את הסכמיה בשורש משלה: {fams}.</p>')
        if is_family(here):
            parts.append(f'<p class="lede">שורש ההסכמים מייבא אותו: <a href="{rel(page_for("agreements"), here)}">שורש ההסכמים</a>.</p>')
        parts.append('<h2>המסמכים הרשומים</h2><ul class="lede">' + "".join(items) + "</ul>"
                     f'<p class="lede">השורש: <a href="{rel("root.html", here)}">{esc(ROOTS[0][3])}</a>.</p>')
    blocks = [module] + (["precedence", "vocabulary"] if module == "root" else [])
    for b in blocks:
        lines = (LIB / f"{b}.l4").read_text(encoding="utf-8").splitlines()
        parts.append(f'<h2 dir="ltr"><code>l4/lib/{esc(b)}.l4</code></h2>'
                     f'<div class="l4">{code_html(list(enumerate(lines, 1)))}</div>')
        if b == module and tests_of(module).exists():
            # the tests sit beside the module in the repository, and on its
            # page below it (the client, 2026-10-22)
            t = tests_of(module).read_text(encoding="utf-8").splitlines()
            state = (f'{held} מתוך {len(asserts)} בדיקות מתקיימות' if asserts else "אין בדיקות")
            parts.append(f'<h2>הבדיקות</h2><p class="lede">מה שואלים את {esc(heading)}, ומה הוא עונה: '
                         f'{esc(state)}. בכל כרטיס: מה הבדיקה שואלת, הביטוי, ומה המהדר ענה. '
                         f'הבדיקות יושבות בקובץ משלהן, לצד הקובץ ולא בתוכו.</p>'
                         + tests_html(module, esc)
                         + f'<details class="tsrc"><summary>קוד הבדיקות: '
                         f'<code dir="ltr">l4/tests/{esc(module)}-tests.l4</code></summary>'
                         f'<div class="l4">{code_html(list(enumerate(t, 1)))}</div></details>')
    return "".join(parts)
