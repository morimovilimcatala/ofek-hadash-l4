"""The root and the collections' roots as pages (MMS-521).

The root (l4/roots/root.l4) is the one place to ask what the law gives; the
collections' roots (takanon-root, agreements-root, circulars-root) register
the instruments of their collection and what each claims, and the root
imports them beside the precedence module. Each gets a page: the root's at
root.html, a collection root's inside its collection (circulars/root.html).

A page is read off the module's own source and what `make l4` recorded for
it (build/l4/roots/<module>.run.json): nothing on it is typed by hand. The
root's page shows the gate — `unresolved contradictions`, asserted empty —
and the resolutions, from the `the resolutions report` the module evaluates.

Every module's tests file (l4/tests/<module>-tests.l4) is rendered the same
way, by `tests_block`, below that module's code (MMS-607): a root's on its
page here, an agreement's or a circular's on that document's own page, and
one whose module has no page on the checks page (tools/build_site.py,
diagnostics.html). Each block carries `data-tests` naming its file, which
is how tests/test_roots.py holds that no tests file goes unshown.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# the roots and the precedence between collections (l4/roots/, MMS-776);
# the shared vocabulary they speak stays in l4/lib/
ROOTS_DIR = ROOT / "l4" / "roots"
LIB = ROOT / "l4" / "lib"
BUILD = ROOT / "build" / "l4" / "roots"
# the modules a collection shares, which mirror no corpus document
# (l4/shared/<collection>/, MMS-776): each is a module of its collection, and
# a collection's root imports them with its documents
SHARED = ROOT / "l4" / "shared"
# a root's tests sit beside it (l4/tests/<module>-tests.l4, the client,
# 2026-10-22): every #EVAL and #ASSERT about it, and what its page reads
TESTS = ROOT / "l4" / "tests"
TESTS_BUILD = ROOT / "build" / "l4" / "tests"


def source_of(module: str) -> str:
    """Where a module a root page shows lives: a root, or the precedence
    module, in l4/roots/; the vocabulary in l4/lib/."""
    d = ROOTS_DIR if (ROOTS_DIR / f"{module}.l4").exists() else LIB
    return (d / f"{module}.l4").relative_to(ROOT).as_posix()


def tests_of(module: str) -> Path:
    return TESTS / f"{module}-tests.l4"


def tests_files() -> list[Path]:
    """Every tests file (l4/tests/ holds nothing else)."""
    return sorted(TESTS.glob("*-tests.l4"))


def tested_module(tests: Path) -> str:
    """The module a tests file is named after (l4run's `tested_through`)."""
    return tests.name.removesuffix("-tests.l4")

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
     "לכל מקרה. בין הסכמים של אותם צדדים באותו עניין המאוחר מחליף את המוקדם (סעיף 19 לחוק "
     "הסכמים קיבוציים), ובין הסכמים שחלים זה לצד זה ההוראה שלטובת העובד גוברת (סעיף 23). "
     "השורש מייבא אותו לצד שורשי התקנון והחוזרים."),
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
    ("teachers-general-root", "agreements/teachers-general/root.html", "agreements",
     "שורש ההסכמים הכלליים לעובדי הוראה",
     "כל הסכם כללי של עובדי ההוראה שמדבר על פריט באוצר המילים המשותף, רשום פעם אחת כמסמך, "
     "ומה הוא אומר לכל מקרה. בין הסכמים של אותם צדדים באותו עניין, המאוחר שמדבר בחודש "
     "השכר מחליף את המוקדם (סעיף 19 לחוק הסכמים קיבוציים). שורש ההסכמים מייבא אותו לצד "
     "שורשי שאר המשפחות."),
    # the public-sector framework agreements, a family of their own (the
    # client, 2026-11-15, MMS-538)
    ("framework-agreements-root", "agreements/framework/root.html", "agreements",
     "שורש הסכמי המסגרת במגזר הציבורי",
     "כל הסכם מסגרת במגזר הציבורי שמדבר על פריט באוצר המילים המשותף, רשום פעם אחת כמסמך, "
     "ומה הוא אומר לכל מקרה. השורש מייבא את כל הסכמי המסגרת; עדיין אף אחד מהם אינו עונה על "
     "פריט באוצר המילים, ולכן אין בו מסמך רשום. שורש ההסכמים מייבא אותו לצד שורשי שאר המשפחות."),
    # the protective statutes (l4/laws/), whose floor the root weighs last
    # (MMS-601); not a collection of the corpus, so it sits beside the laws
    ("statutes-root", "laws/root.html", "",
     "שורש החוקים המגינים",
     "החוקים שקובעים רצפה שהסכם, חוזר או התקנון אינם יורדים ממנה — חוק שכר מינימום, חוק הגנת השכר "
     "וחוק פיצויי פיטורים — והרצפה שכל אחד קובע לכל פריט. השורש שוקל אותה אחרונה, מעל המסמך שסדר "
     "העדיפות השאיר גובר: היכן שהחוק נותן יותר, החוק גובר (סעיף 21 לחוק הסכמים קיבוציים)."),
    # the month by the law (MMS-525): what the calculator asks. It sits in
    # no collection and registers no instrument; its page carries its code
    # and its tests (MMS-607)
    ("salary-root", "salary-root.html", "",
     "שורש השכר — החודש לפי הדין",
     "מה שמחשבון השכר שואל: לכל רכיב של סעיף 1.1 לתקנון, הרכיב שגובר — תשובת השורש היכן "
     "שפריט שכר עומד ברכיב, והסכום של סעיף 1.1 עצמו היכן שאין — ולמה: המסמך שגובר, הכלל, "
     "ומה כל מסמך אומר. המחשבון מריץ את הקוד הזה בדפדפן."),
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
    """What `make l4` recorded of a module's tests file."""
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


def tests_block(module: str, heading: str, *, esc, code_html, where: str = "",
                banner: bool = True) -> str:
    """A module's tests file, below the module's code (the client,
    2026-10-22: the tests sit beside the module in the repository, and on
    its page below it): what each test asks, the expression, what the
    compiler answered, and the file's source one click away. `heading`
    names the module in the lede; `where` is a sentence the lede adds, for
    a file shown away from its module's code; `banner` says so when `make
    l4` has recorded nothing for the file (a root's page says it above)."""
    rs = results(module)
    asserts = [r for r in rs if r.get("kind") == "assertion"]
    held = sum(r.get("value") is True for r in asserts)
    path = f"l4/tests/{module}-tests.l4"
    t = tests_of(module).read_text(encoding="utf-8").splitlines()
    state = (f'{held} מתוך {len(asserts)} בדיקות מתקיימות' if asserts else "אין בדיקות")
    stale = '' if rs or not banner else '<div class="banner">קובץ הבדיקות הזה עוד לא נבדק בבנייה הזו.</div>'
    return (f'<section class="tests-of" id="tests-{esc(module)}" data-tests="{esc(path)}">'
            f'<h2>הבדיקות</h2><p class="lede">מה שואלים את {esc(heading)}, ומה הוא עונה: '
            f'{esc(state)}. בכל כרטיס: מה הבדיקה שואלת, הביטוי, ומה המהדר ענה. '
            f'הבדיקות יושבות בקובץ משלהן, לצד הקובץ ולא בתוכו.{where}</p>'
            + stale + tests_html(module, esc)
            + f'<details class="tsrc"><summary>קוד הבדיקות: <code dir="ltr">{esc(path)}</code></summary>'
            f'<div class="l4">{code_html(list(enumerate(t, 1)))}</div></details></section>')


def page_body(module: str, here: str, coll: str, heading: str, about: str, *,
              esc, rel, code_html, href_of, coll_name, coll_href, see: str = "") -> str:
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
             + f'<code dir="ltr">{esc(source_of(module))}</code></div></header>',
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
        links = " · ".join(f'<a href="{rel(h, here)}">{esc(t)}</a>' for m, h, c, t, _ in ROOTS
                           if (c and not is_family(h)) or m == "statutes-root")
        parts.append(f'<p class="lede">המסמכים רשומים בשורשי האוספים: {links}. '
                     f'סדר העדיפות: <code dir="ltr">l4/roots/precedence.l4</code>, בקוד שלהלן.</p>')
        salary = next((h, t) for m, h, _, t, _ in ROOTS if m == "salary-root")
        parts.append(f'<p class="lede">השכר החודשי לפי הדין, רכיב אחר רכיב, נשאל מכאן: '
                     f'<a href="{rel(salary[0], here)}">{esc(salary[1])}</a>.</p>')
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
    elif module == "salary-root":
        # a root that registers no instrument (salary-root) asks the root;
        # the protective statutes' root, in no collection either, registers
        # its statutes and is listed below
        parts.append(f'<p class="lede">הוא שואל את השורש: '
                     f'<a href="{rel("root.html", here)}">{esc(ROOTS[0][3])}</a>.{see}</p>')
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
        lines = (ROOT / source_of(b)).read_text(encoding="utf-8").splitlines()
        parts.append(f'<h2 dir="ltr"><code>{esc(source_of(b))}</code></h2>'
                     f'<div class="l4">{code_html(list(enumerate(lines, 1)))}</div>')
        if b == module and tests_of(module).exists():
            parts.append(tests_block(module, heading, esc=esc, code_html=code_html, banner=False))
    return "".join(parts)


# ---------------------------------------------------------------------------
# The circulars' root is GENERATED (MMS-538, step 4): it imports every module
# of the circulars collection, l4/circulars/, so the root holds the whole
# collection rather than a hand-kept list. Of all they declare it names only
# what is unique in that scope — each module's `instrument` description
# (`circular <number>`) and its `<prefix> according to circular <number>`
# answers — because a name two of them declare fails "multiple definitions"
# once it is used.
#
#     python3 tools/roots.py --write-circulars-root   # rewrite l4/roots/circulars-root.l4
#     python3 tools/roots.py --check-circulars-root   # exit 1 if it is stale
#
# tests/test_roots.py holds the file to this output, so a circular that
# gains an answer or an instrument description is in the root in the same
# commit.

CIRCULARS = ROOT / "l4" / "circulars"
CIRCULARS_ROOT = ROOTS_DIR / "circulars-root.l4"

# What each circular answer is about: the prefix of `<prefix> according to
# circular <number>`, and the pay item of the shared vocabulary it answers.
# A prefix not listed here stops the generator, so a new kind of answer is a
# deliberate line here.
CIRCULAR_ANSWER_ITEMS = {
    "the 2008 supplement": "the 2008 public-sector supplement",
    "the pedagogical coordinator's rate": "the pedagogical coordinator's allowance rate",
    "the mentor's rate": "the mentor's allowance rate",
    "the junior-division head's allowance": "the junior-division head's allowance",
    "the role allowances counted": "the role allowances counted",
    "the 2011 supplement": "the 2011 public-sector supplement",
    "the 1994 supplement": "the 1994 supplement of a full position",
    "the Ofek 2022 supplement of a full position": "the Ofek 2022 supplement of a full position",
}
# a note said above an item's claims
CIRCULAR_ITEM_NOTES = {
    "the role allowances counted": "only תשפ\"ו/1's \"at most two\" is encoded as a rule so far (MMS-552)",
}

_INSTRUMENT = re.compile(r"^(`circular [^`]+`) MEANS\n\s+`instrument` WITH", re.M)
_ANSWER = re.compile(r"^DECIDE `(.+) according to (circular [^`]+)` c IS", re.M)
_VOCAB_ITEMS = re.compile(r"^DECLARE `pay item` IS ONE OF\n((?:[ \t]+.*\n|\n)*)", re.M)


def circular_modules() -> list[Path]:
    """Every module of the circulars collection: the circulars of
    l4/circulars/ and the modules they share, l4/shared/circulars/."""
    return sorted(list(CIRCULARS.glob("*.l4")) + list((SHARED / "circulars").glob("*.l4")),
                  key=lambda f: f.name)


def circulars_speaking() -> list[tuple[str, str, list[tuple[str, str]]]]:
    """(module, its instrument's name, [(pay item, answer name)]) for every
    circular that describes itself as an instrument, in module order (the
    school year, then the number). A circular with answers and no
    instrument, or more than one, or an answer about no listed item, stops it."""
    out = []
    for f in circular_modules():
        text = f.read_text(encoding="utf-8")
        inst = _INSTRUMENT.findall(text)
        answers = _ANSWER.findall(text)
        if not inst and not answers:
            continue
        if len(inst) != 1:
            raise SystemExit(f"{f.name}: {len(inst)} instrument descriptions and {len(answers)} answers")
        rows = []
        for prefix, who in answers:
            if f"`{who}`" != inst[0]:
                raise SystemExit(f"{f.name}: an answer according to {who}, but it describes {inst[0]}")
            if prefix not in CIRCULAR_ANSWER_ITEMS:
                raise SystemExit(f"{f.name}: no pay item for `{prefix} according to …` (CIRCULAR_ANSWER_ITEMS)")
            rows.append((CIRCULAR_ANSWER_ITEMS[prefix], f"`{prefix} according to {who}`"))
        out.append((f.name.removesuffix(".l4"), inst[0], rows))
    return out


def vocabulary_items() -> list[str]:
    """The `pay item`s of the shared vocabulary, in its order."""
    body = _VOCAB_ITEMS.search((LIB / "vocabulary.l4").read_text(encoding="utf-8")).group(1)
    return re.findall(r"^\s+`([^`]+)`\s*$", body, re.M)


def circulars_root_source() -> str:
    speaking = circulars_speaking()
    names = [inst for _, inst, _ in speaking]
    if len(set(names)) != len(names):
        raise SystemExit("two circulars describe themselves under one name")
    items = vocabulary_items()
    claims: dict[str, list[tuple[str, str]]] = {}
    for _, inst, rows in speaking:
        for item, answer in rows:
            claims.setdefault(item, []).append((inst, answer))
    unknown = sorted(set(claims) - set(items))
    if unknown:
        raise SystemExit(f"not pay items of the vocabulary: {unknown}")
    out = [
        "-- The circulars' root (MMS-521). GENERATED by tools/roots.py",
        "-- (--write-circulars-root, MMS-538): do not edit it by hand.",
        "--",
        "-- It imports the whole collection (l4/circulars/, l4/shared/circulars/), and",
        "-- includes as instruments the circulars that describe themselves as one",
        "-- (each in its own file, an `instrument` record of the shared vocabulary,",
        "-- l4/lib/vocabulary.l4), with what each claims for a case on the items it",
        "-- speaks to (its `<item> according to circular <number>` answers). Of all",
        "-- the collection declares it names only those, which are unique in it: a",
        "-- name two circulars declare fails \"multiple definitions\" once it is used.",
        "-- It is a `collection root` (l4/roots/precedence.l4) and applies the",
        "-- circulars' own precedence: the later circular replaces the earlier on",
        "-- the same point. The root (l4/roots/root.l4) sets this collection's ruling",
        "-- against the takanon's and the agreements'.",
        "",
        "IMPORT prelude",
        "IMPORT precedence",
    ]
    out += [f"IMPORT `{f.name.removesuffix('.l4')}`" for f in circular_modules()]
    out += [
        "",
        "§ `שורש החוזרים — מה החוזרים אומרים על כל פריט`",
        "",
        "§§ `המסמכים`",
        "",
        "-- Each instrument describes itself in its own file (an `instrument` record",
        "-- of the shared vocabulary). This root includes the circulars:",
        "`the circulars' instruments` MEANS",
        "    LIST " + ",\n         ".join(names),
        "",
        "§§ `מה החוזרים אומרים, לפי פריט`",
        "",
        "GIVEN i IS A `pay item`, c IS A `teaching case`",
        "GIVETH A LIST OF `claim`",
        "DECIDE `the circulars' claims on` i c IS",
        "    CONSIDER i",
    ]
    for item in items:
        if item not in claims:
            continue
        if item in CIRCULAR_ITEM_NOTES:
            out.append(f"    -- {CIRCULAR_ITEM_NOTES[item]}")
        lines = [f"`the claim of` {inst} ({answer} c)" for inst, answer in claims[item]]
        out.append(f"    WHEN `{item}` THEN")
        out.append("        catMaybes (LIST " + ",\n                        ".join(lines) + ")")
    out += [
        "    OTHERWISE EMPTY",
        "",
        "§§ `חוזר מאוחר גובר על מוקדם`",
        "",
        "GIVEN a IS A `claim`, b IS A `claim`",
        "GIVETH A `claim`",
        "DECIDE `the more recent circular's claim` a b IS",
        "    IF DATE_SERIAL (b's `by`'s `issued`) GREATER THAN DATE_SERIAL (a's `by`'s `issued`) THEN b ELSE a",
        "",
        "-- Among circulars that speak, the most recent replaces the others on the same",
        "-- point (convention precedence.later-circular); one alone governs as the",
        "-- only one that speaks. Of claims issued on the same latest day, the last",
        "-- in the list (the higher number) governs, unless the list's first is",
        "-- among them.",
        "GIVEN claims IS A LIST OF `claim`",
        "GIVETH A MAYBE `ruling`",
        "DECIDE `the ruling among circulars` claims IS",
        "    CONSIDER claims",
        "    WHEN EMPTY THEN NOTHING",
        "    WHEN t FOLLOWED BY ts THEN",
        "        JUST (`the ruling for`",
        "                  (foldr (GIVEN c, acc YIELD `the more recent circular's claim` acc c) t ts)",
        "                  (IF null ts THEN `the only instrument that speaks` ELSE `a later circular replaces an earlier one`))",
        "",
        "`the circulars' root` MEANS",
        "    `collection root` WITH",
        "        `the collection`  IS \"החוזרים לבעלויות\"",
        "        `its instruments` IS `the circulars' instruments`",
        "        `what each says`  IS `the circulars' claims on`",
        "        `its ruling`      IS (GIVEN i, c YIELD `the ruling among circulars` (`the circulars' claims on` i c))",
    ]
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# Each family of agreements imports its whole family (MMS-538), as the
# circulars' root imports its collection. A family root's instruments and
# claims stay written by hand — the agreements' answers are not one shape
# (an amendment's claim waits for its month, the salary tables are their
# own instrument) — so only its IMPORT block is generated: prelude,
# precedence, every module of l4/agreements/<family>/, then any import of a
# module outside the family the hand-written part asks for, kept as it was.
#
#     python3 tools/roots.py --write-agreement-imports
#     python3 tools/roots.py --check-agreement-imports

AGREEMENTS = ROOT / "l4" / "agreements"
# family directory -> its root module
FAMILY_ROOTS = {
    "ofek-hadash": "ofek-hadash-root",
    "oz-latmura": "oz-latmura-root",
    "teachers-general": "teachers-general-root",
    "framework": "framework-agreements-root",
}
_IMPORT = re.compile(r"^IMPORT\s+`?([^`\s]+)`?\s*$", re.M)


def family_modules(family: str) -> list[str]:
    """Every module of a family: the files under l4/agreements/<family>/ and
    the modules the family shares, l4/shared/agreements/<family>/."""
    return sorted(f.name.removesuffix(".l4") for f in family_files(family))


def family_files(family: str) -> list[Path]:
    return sorted(list((AGREEMENTS / family).rglob("*.l4"))
                  + list((SHARED / "agreements" / family).rglob("*.l4")))


def family_root_source(family: str) -> str:
    return imports_source(ROOTS_DIR / f"{FAMILY_ROOTS[family]}.l4", family_modules(family))


def imports_source(path: Path, modules: list[str]) -> str:
    """The root at `path` with its one IMPORT block regenerated: prelude,
    precedence, every module of its collection, then any import of a module
    outside the collection the hand-written part asks for, kept as it was."""
    lines = path.read_text(encoding="utf-8").split("\n")
    at = [i for i, l in enumerate(lines) if _IMPORT.match(l)]
    if not at or at != list(range(at[0], at[-1] + 1)):
        raise SystemExit(f"{path.name}: its imports are not one block")
    mine = set(modules)
    kept = [m for m in (_IMPORT.match(lines[i]).group(1) for i in at)
            if m not in mine and m not in ("prelude", "precedence")]
    block = ["IMPORT prelude", "IMPORT precedence"] + [f"IMPORT `{m}`" for m in sorted(mine)] + \
            [f"IMPORT `{m}`" for m in kept]
    return "\n".join(lines[:at[0]] + block + lines[at[-1] + 1:])


# ---------------------------------------------------------------------------
# The takanon's root imports the whole takanon (MMS-538): every module under
# l4/takanon/ — its sections and the department's site pages published with
# it — by the name it is imported by (a dotted name as `takanon-<dashed>`,
# tools/modules.py). Its instruments and claims stay written by hand, as the
# agreements' do; only the IMPORT block is generated.
#
#     python3 tools/roots.py --write-takanon-imports
#     python3 tools/roots.py --check-takanon-imports

TAKANON = ROOT / "l4" / "takanon"
TAKANON_ROOT = ROOTS_DIR / "takanon-root.l4"


def takanon_modules() -> list[str]:
    """Every module of the takanon collection, by its importable name: its
    sections, the site pages, and the helpers they share
    (l4/shared/takanon/)."""
    out = []
    for f in takanon_files():
        name = f.name.removesuffix(".l4")
        out.append("takanon-" + name.replace(".", "-") if "." in name else name)
    return sorted(out)


def takanon_files() -> list[Path]:
    return sorted(list(TAKANON.rglob("*.l4")) + list((SHARED / "takanon").rglob("*.l4")))


def takanon_root_source() -> str:
    return imports_source(TAKANON_ROOT, takanon_modules())


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["--write-circulars-root"]:
        CIRCULARS_ROOT.write_text(circulars_root_source(), encoding="utf-8")
    elif sys.argv[1:] == ["--check-circulars-root"]:
        if CIRCULARS_ROOT.read_text(encoding="utf-8") != circulars_root_source():
            raise SystemExit("l4/roots/circulars-root.l4 is stale: python3 tools/roots.py --write-circulars-root")
    elif sys.argv[1:] == ["--write-agreement-imports"]:
        for fam, mod in FAMILY_ROOTS.items():
            (ROOTS_DIR / f"{mod}.l4").write_text(family_root_source(fam), encoding="utf-8")
    elif sys.argv[1:] == ["--check-agreement-imports"]:
        stale = [m for f, m in FAMILY_ROOTS.items()
                 if (ROOTS_DIR / f"{m}.l4").read_text(encoding="utf-8") != family_root_source(f)]
        if stale:
            raise SystemExit(f"stale imports in {stale}: python3 tools/roots.py --write-agreement-imports")
    elif sys.argv[1:] == ["--write-takanon-imports"]:
        TAKANON_ROOT.write_text(takanon_root_source(), encoding="utf-8")
    elif sys.argv[1:] == ["--check-takanon-imports"]:
        if TAKANON_ROOT.read_text(encoding="utf-8") != takanon_root_source():
            raise SystemExit("stale imports in takanon-root: python3 tools/roots.py --write-takanon-imports")
    else:
        raise SystemExit("usage: tools/roots.py --write-circulars-root | --check-circulars-root"
                         " | --write-agreement-imports | --check-agreement-imports"
                         " | --write-takanon-imports | --check-takanon-imports")
