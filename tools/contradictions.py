"""מקורות סותרים (contradictions.html, MMS-515; "סתירות בין מסמכים" until the
simulator joined it, MMS-522 — a calculator is not a document): where one instrument
says one thing and another instrument says another about the same pay or
right — an agreement and the circular that implements it, a circular and the
letter it executes, two circulars — with a picture of each side, the rule
that says which one wins, and whether that rule was followed.

The page is built from data/contradictions.json and the crops under
data/contradictions/. Every crop is the source's own pixels: a scanned page's
image at its native resolution, or a born-digital page rendered with
pdftoppm, said so in its caption. No crop is resampled or retouched; the
outline that points at the words is drawn by the page over the picture, from
the `marks` the cutting recorded. tests/test_contradictions.py holds each
quote to the corpus text, each crop to its file, and each finding to the
register.

What is PAID is a source like any document (the client, 2026-10-21: "in
general remove the קוים chips, since payslips are also a source"): the
payslips, described in general terms and never a person's figure (decision
17), and the ministry's simulator, which binds no one. Each is a side of the
card it speaks to, with its answer and whether that answer is the one the
governing rule gives (`agrees`); a paying source that departs from it makes
the card an error, graded. A source that has no answer to the question is
listed under the card (`silent`), not as a side. None of them changes a
reading.

A card that sets a circular against an agreement says which way the
circular departs (`direction`: more, less, the same — a circular that
prints the agreement's own figure, so the two stand or fall together against
a third source — or other than a sum paid), and what that means under §29 of
the Budget Foundations Law (MMS-602): giving less or the same, §29 is not in
play; giving more, the card carries `section_29`, the L4 boolean that applies
the encoded section and whether the excess is void.

The simulator also has a group of its own (tools/calculator_delta.py,
MMS-522): every place its computation departs from the text, produced by the
comparison rather than picked, under the simulator's own disclaimer that it
binds no one.

THE ROOT IS THE SOURCE OF THE ROWS IT CAN SPEAK FOR (MMS-521). Every
contradiction the root finds over its grid of cases is a row here, read off
`the contradictions report` that `make l4` records for l4/tests/root-tests.l4
(`root_report`): one row per item, instrument that governs and rule
(`root_rows`), listing each set of instruments that speak, how many cases it
settles and the first of them, with what each instrument says in it. A row
no hand-written card claims is a generated card (`generated`). A hand card
attaches to a row by its key (`root`: item, the module that governs, the
rule) and brings what the root cannot — the crops, what is paid, משמעות and
the prose; it cannot add a row, and its document sides are instruments the
row names. A card the root cannot speak for stays hand-written and says why
in `not_in_root` (NOT_IN_ROOT); tests/test_contradictions.py holds the page
to the root exactly.
"""
from __future__ import annotations

import hashlib
import html
import json

import l4src
from pathlib import Path

esc = html.escape

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "contradictions.json"
CROPS = ROOT / "data" / "contradictions"
HERE = "contradictions.html"
TAB = "מקורות סותרים"

TYPE = {"agreement": "הסכם קיבוצי", "circular": "חוזר", "letter": "מכתב", "takanon": "תקנון",
        "qa": "שאלות ותשובות", "table": "טבלת שכר", "law": "חוק",
        "payslip": "תלוש", "simulator": "סימולטור"}
# the sources that say what is PAID, not what the law is: no page of theirs is
# quoted or pictured, and each says whether it pays what the governing rule gives
PAYING = ("payslip", "simulator")


def types(c: dict) -> list[str]:
    """The kinds of source a contradiction sets against each other."""
    return sorted({s["type"] for s in c["sides"]}, key=list(TYPE).index)
SEV = {"high": "חמור", "medium": "בינוני", "low": "קל"}
KIND = {"render": "עמוד דיגיטלי, מרונדר ב־{dpi} dpi",
        "scan": "סריקה, ברזולוציה המקורית ({dpi} ppi)",
        "html": "דף מהעותק השמור של האתר (1.6.2026), כפי שהדפדפן מציג אותו, בצפיפות כפולה; תשובה מקופלת נפתחה כמו בלחיצה"}


def proofs(c: dict, evidence: dict[str, tuple[str, str]]) -> list[tuple[str, str]]:
    """The L4 booleans a contradiction rests on, as (file, name): those its
    findings name as their evidence, and its own `asserts` where no finding
    carries one. Each is #ASSERTed in its file, so a contradiction the code
    does not prove is not on the page, and a corrected text turns the build
    red (the client, 2026-10-21, MMS-533: "Every document contradiction
    should have an ASSERT")."""
    out = [evidence[f] for f in c.get("findings", []) if f in evidence]
    out += [(a["l4"], a["name"]) for a in c.get("asserts", [])]
    if c.get("section_29"):
        out.append((c["section_29"]["l4"], c["section_29"]["name"]))
    return list(dict.fromkeys(out))


# Which way a circular departs from the agreement it carries out (MMS-602).
# Where it gives LESS, the agreement governs — a circular never out-ranks an
# agreement — and §29 of the Budget Foundations Law is not in play: it voids
# what a budgeted or supported body gives BEYOND what was agreed or approved.
# Where it gives MORE, §29 can decide the card, and the card carries its
# `section_29`: the L4 boolean that applies the encoded section
# (l4/laws/budget-foundations-law.l4) and #ASSERTs the result, whether the
# excess is void, and why. `other` is a departure that is not a sum paid.
DIRECTION = {"more": "החוזר נותן יותר מההסכם", "less": "החוזר נותן פחות מההסכם",
             "same": "החוזר נותן כמו ההסכם",
             "other": "הסטייה אינה בסכום שמשולם"}
S29 = "laws/budget-foundations-law.html#s29"


def compares_circular_to_agreement(c: dict) -> bool:
    """A card that sets a circular against an agreement: it says which way
    the circular departs."""
    kinds = {s["type"] for s in c["sides"]}
    return "circular" in kinds and "agreement" in kinds


def direction_html(c: dict, *, prose) -> str:
    d = c.get("direction")
    if not d:
        return ""
    law = f'<a href="{S29}">סעיף 29 לחוק יסודות התקציב</a>'
    if d == "more":
        s = c["section_29"]
        verdict = ("לפי סעיף 29 העודף בטל, והסכום הוא של ההסכם." if s["voids"]
                   else "לפי סעיף 29 העודף אינו בטל, והחוזר עומד.")
        text = (f'החוזר נותן יותר מההסכם, והבעלויות שהוא ממוען אליהן הן גוף מתוקצב או גוף נתמך. לכן {law} בודק את העודף: '
                f'הוא עומד רק אם הוסכם או הונהג לגבי כלל עובדי המדינה, או אושר בידי שר האוצר. <b>{esc(verdict)}</b></p>'
                f'<p>{prose(s["note"])}')
    elif d == "same":
        text = (f'החוזר אינו סוטה מההסכם שהוא מבצע: הוא מדפיס את אותו סכום, ולכן שניהם עומדים או נופלים יחד מול המקור השלישי. '
                f'{law} אינו חל כאן — אין עודף על ההסכם.')
    else:
        why = ("הוא מבטל רק מה שגוף מתוקצב או גוף נתמך נותן מעבר למה שהוסכם או אושר, ולא תשלום נמוך מההסכם"
               if d == "less" else "החוזר אינו נותן שינוי בשכר או הטבה כספית מעבר להסכם")
        text = (f'<b>ההסכם גובר</b>: חוזר אינו גובר על ההסכם שהוא מבצע. {law} אינו חל כאן — {esc(why)}.')
    return (f'<div class="cx-mean cx-s29"><h4>כיוון הסטייה וסעיף 29</h4>'
            f'<p><span class="cx-dir dir-{d}">{esc(DIRECTION[d])}</span> {prose(c["direction_note"])}</p>'
            f'<p>{text}</p></div>')


def load() -> dict | None:
    return json.loads(DATA.read_text(encoding="utf-8")) if DATA.exists() else None


# A weaker source departing from a stronger one — a circular from the agreement
# or the letter it carries out, an answer on the site from the takanon, the
# takanon (or a table its site publishes) from a circular or an agreement —
# is a card on this page and not a
# finding (the client, 2026-10-22: "a weaker one departing from a stronger one
# has its own page, סתירה in finding means equal power"). Two circulars, or a
# document against itself, are of equal power and stay findings. A document
# that gives less than a statute is the same: the statute is stronger.
CROSS_RANK = ("agreement", "letter", "qa", "takanon", "law")


def homes(data: dict | None) -> dict[str, str]:
    """finding id -> the card it lives on, for every finding a card of a
    weaker-against-stronger group cites: these leave the findings page."""
    out: dict[str, str] = {}
    for c in (data or {}).get("items", []):
        if c.get("group") in CROSS_RANK:
            for f in c.get("findings", []):
                out.setdefault(f, c["id"])
    return out


# Why the root cannot speak for a card (MMS-521): the card stays hand-written
# and says so. Each reason is held to the card's sides by the tests: a card
# with a statute side is `statute-floor`; one with fewer than two sides the
# root weighs (takanon, agreement, circular) is `not-weighed`; the rest set
# two weighed instruments against each other on something no pay item of
# the shared vocabulary covers yet, or on no figure at all.
NOT_IN_ROOT = {
    "no-pay-item": "השורש עוד אינו שואל על כך: אף פריט שכר באוצר המילים המשותף אינו מכסה את מה "
                   "שהמסמכים חלוקים בו, ולכן הכרטיס כתוב ביד.",
    "text-only": "המחלוקת היא בתנאי, בהגדרה או בנוהל, ואין סכום של חודש שכר שנגזר ממנה ישירות: "
                 "לשורש, שעונה בסכומים לפריטי שכר, אין כאן מה להשוות, ולכן הכרטיס כתוב ביד.",
    "statute-floor": "חוק מגן מול מסמך: הזכות שהחוק נותן כאן אינה פריט שכר שהשורש שואל עליו, "
                     "ושורש החוקים המגינים שוקל את הרצפה רק לפריטי שכר. לכן הכרטיס כתוב ביד.",
    "not-weighed": "צד אחד אינו מסמך שהשורש שוקל — תשובה או טבלה באתר המשרד, מכתב, או מה שמשולם "
                   "בפועל (תלוש, סימולטור) — ולכן הכרטיס כתוב ביד.",
}
# the kinds of side the root weighs: what its collection roots register
WEIGHED = ("takanon", "agreement", "circular")

# Where a row the root generates sits on the page, by the rule that settles
# it (l4/lib/precedence.l4): the takanon against an agreement or a circular,
# a circular against the agreement it carries out, two agreements weighed
# by §23, two circulars by date. tests/test_contradictions.py holds that
# every rule the root reports is here.
RULE_GROUP = {
    "מבוא התקנון: הסכם קיבוצי גובר על התקנון": "takanon",
    "מבוא התקנון: הסכם קיבוצי, כפי שתוקן, גובר על התקנון": "takanon",
    "מבוא התקנון: חוזר מאוחר יותר גובר": "takanon",
    "מבוא התקנון: אף מסמך שגובר על התקנון אינו מדבר": "takanon",
    "חוזר אינו גובר על ההסכם שהוא מבצע": "agreement",
    "חוק הסכמים קיבוציים, סעיף 22: תנאי לטובת העובד עומד": "agreement",
    "חוק הסכמים קיבוציים, סעיף 23: ההוראה שלטובת העובד": "agreements",
    "חוזר מאוחר גובר על חוזר מוקדם בעניין אחד": "circulars",
}
REPORT = "`the contradictions report`"
GATE = ("l4/tests/root-tests.l4", "null `unresolved contradictions`")


def root_report() -> list[dict] | None:
    """The root's contradictions as `make l4` recorded them for its tests
    (l4/tests/root-tests.l4, `the contradictions report`): one entry per
    resolution, with the instruments that speak (modules), the one that
    governs, the rule, how many of the cases checked it settles, and the
    first of them — described, what each instrument says in it, and the
    answer that governs. None where `make l4` has recorded nothing."""
    import roots
    value = roots.evaluated("root", REPORT)
    if value is None:
        return None
    out = []
    for line in roots.strings(value):
        item, sources, governs, rule, n, case, claims, answer = (line.split(" | ") + [""] * 8)[:8]
        out.append({"item": item, "sources": sources.split(","), "governs": governs, "rule": rule,
                    "cases": int(n or 0), "example": case,
                    "says": dict(x.split("=", 1) for x in claims.split("; ") if x),
                    "answer": answer})
    return out


def root_key(x: dict) -> tuple[str, str, str]:
    """A row's key, and a card's `root`: the item, the module that governs,
    the rule."""
    return (x["item"], x["governs"], x["rule"])


def root_rows(report: list[dict]) -> list[dict]:
    """The rows the root speaks for: its resolutions by item, instrument
    that governs and rule, in the report's order."""
    rows: dict[tuple, dict] = {}
    for r in report:
        row = rows.setdefault(root_key(r), {"item": r["item"], "governs": r["governs"],
                                            "rule": r["rule"], "resolutions": []})
        row["resolutions"].append(r)
    for row in rows.values():
        row["sources"] = list(dict.fromkeys(m for r in row["resolutions"] for m in r["sources"]))
        row["cases"] = sum(r["cases"] for r in row["resolutions"])
        digest = hashlib.sha1(f'{row["item"]}|{row["rule"]}'.encode()).hexdigest()[:6]
        row["id"] = f'root-{row["governs"]}-{digest}'
    return list(rows.values())


def instruments() -> dict[str, tuple[str, str]]:
    """Every instrument the root weighs, module -> (title, kind of side), as
    the collection roots register them (tools/roots.py)."""
    import roots
    out: dict[str, tuple[str, str]] = {}
    for module, kind in (("takanon-root", "takanon"), ("agreements-root", "agreement"),
                         ("circulars-root", "circular"), ("statutes-root", "law")):
        for m, t in roots.registered(module):
            out.setdefault(m, (t, kind))
    return out


def generated(row: dict, inst: dict[str, tuple[str, str]]) -> dict:
    """The card of a row no hand-written card claims: its sides are the
    instruments that speak, each with what it says in the row's examples."""
    gov = inst.get(row["governs"], (row["governs"], ""))[0]
    others = [inst.get(m, (m, ""))[0] for m in row["sources"] if m != row["governs"]]
    sides = [{"type": inst.get(m, (m, "circular"))[1], "label": inst.get(m, (m, ""))[0], "module": m,
              "says": list(dict.fromkeys(r["says"][m] for r in row["resolutions"] if m in r["says"]))}
             for m in row["sources"]]
    return {"id": row["id"], "group": RULE_GROUP.get(row["rule"], "takanon"), "generated": True,
            "title": f'{row["item"]}: {gov} מול {" · ".join(others)}', "sides": sides}


def cards(data: dict, rows: list[dict] | None) -> list[tuple[dict, dict | None]]:
    """Every card on the page, with the root's row it shows: each hand card
    (attached to the row its `root` names, if any), then a generated card
    for every row no hand card claims."""
    by_key = {root_key(r): r for r in rows or []}
    out = [(c, by_key.get(root_key(c["root"])) if c.get("root") else None) for c in data["items"]]
    claimed = {root_key(c["root"]) for c in data["items"] if c.get("root")}
    inst = instruments() if rows else {}
    out += [(generated(r, inst), r) for r in rows or [] if root_key(r) not in claimed]
    return out


def crops(data: dict) -> list[str]:
    """Every crop file the page shows, for the build to copy."""
    out = [i["file"] for c in data["items"] for s in c["sides"] for i in s.get("images", [])]
    out += [r["image"]["file"] for r in data["rules"].values() if r.get("image")]
    return out


def figure(img: dict, alt: str, src: str) -> str:
    marks = "".join(
        f'<span class="cx-mark" style="right:{(1 - m[2]) * 100:.2f}%;top:{m[1] * 100:.2f}%;'
        f'width:{(m[2] - m[0]) * 100:.2f}%;height:{(m[3] - m[1]) * 100:.2f}%"></span>'
        for m in img.get("marks", []))
    w, h = img["size"]
    b = img["box_px"]
    page = f', עמוד {img["page"]}' if "page" in img else ""
    cap = (f'<bdi dir="ltr">{esc(img["source"])}</bdi>{page} · '
           + esc(KIND[img["kind"]].format(dpi=img["dpi"]))
           + f' · חיתוך <bdi dir="ltr">{b[0]},{b[1]}–{b[2]},{b[3]}</bdi> פיקסלים')
    # the outline sits in the same box as the picture, so a narrow screen scrolls both together
    return (f'<figure class="cx-fig"><div class="cx-scroll"><div class="cx-img" style="--w:{w}">'
            f'<a href="{esc(src)}" title="התמונה בגודלה המקורי"><img src="{esc(src)}" width="{w}" height="{h}" alt="{esc(alt)}" decoding="async"></a>{marks}'
            f'</div></div><figcaption>{cap}</figcaption></figure>')


def paying_side_html(s: dict) -> str:
    """A source that says what is paid: its answer, and whether it is the
    answer the governing rule gives."""
    mark = ("cx-agrees", "כמו הכלל הגובר") if s["agrees"] else ("cx-departs", "סוטה מהכלל הגובר")
    link = (f'<p class="cx-where"><a href="#{esc(s["delta"])}">בסימולטור מול הטקסט</a></p>'
            if s.get("delta") else "")
    return (f'<div class="cx-side cx-paying"><p class="cx-who"><span class="cx-type t-{esc(s["type"])}">'
            f'{esc(TYPE[s["type"]])}</span> <b>{esc(s["label"])}</b></p>'
            f'<p class="cx-says">{esc(s["says"])}</p><p class="{mark[0]}">{esc(mark[1])}</p>{link}</div>')


def side_html(s: dict, *, clause_link, src) -> str:
    if s["type"] in PAYING:
        return paying_side_html(s)
    # a statute is quoted from its pinned text (laws/<name>.toml) and links to
    # its page beside its L4; the corpus holds no copy of it, so no crop
    if s.get("law"):
        href, label = f'laws/{s["law"]}.html#s{s["section"]}', esc(s["label"])
    else:
        href, label = clause_link(s["doc"], s["key"]) if s.get("doc") else ("", esc(s["label"]))
    lab = f'<a href="{esc(href)}">{label}</a>' if href else label
    pic = "".join(figure(i, s["quote"], src(i["file"])) for i in s.get("images", []))
    return (f'<div class="cx-side"><p class="cx-who"><span class="cx-type t-{esc(s["type"])}">{esc(TYPE[s["type"]])}</span> '
            f'<b>{esc(s["label"])}</b></p><p class="cx-says">{esc(s["says"])}</p>{pic}'
            f'<blockquote class="cx-quote" lang="he" dir="rtl">{esc(s["quote"])}</blockquote>'
            f'<p class="cx-where">{lab}</p></div>')


def rule_html(r: dict, note: str, *, prose, src) -> str:
    pic = figure(r["image"], r["quote"], src(r["image"]["file"])) if r.get("image") else ""
    link = (f' · <a href="{esc(r["url"])}">{esc(r["url_label"])}</a>' if r.get("url") else "")
    link += f' · <a href="{esc(r["l4_page"])}">הסעיפים ב־L4</a>' if r.get("l4_page") else ""
    quote = (f'<blockquote class="cx-quote cx-rq" lang="he" dir="rtl">{esc(r["quote"])}</blockquote>'
             if r.get("quote") else "")
    return (f'<div class="cx-rule"><h4>מי גובר?</h4><p class="cx-rsrc"><b>{esc(r["title"])}</b>'
            f' — {esc(r["source"])}{link}</p>{pic}{quote}<p>{prose(note)}</p></div>')


def errors(data: dict) -> list[dict]:
    """The contradictions in which a paying source — a payslip, the
    simulator — departs from what the governing rule gives: errors, each
    graded."""
    return [c for c in data["items"] if any(s.get("agrees") is False for s in c["sides"])]


def meter(grades: list[str]) -> str:
    """The errors on the page by grade — the graded contradictions and the
    simulator's graded rows. Each key is also a filter: it shows the cards
    of that grade (the client, 2026-10-21: "I should be able to filter
    based on the severity chip")."""
    n = {k: grades.count(k) for k in SEV}
    segs = "".join(f'<span class="cx-mseg sev-{k}" style="flex:{n[k]}" title="{esc(SEV[k])}: {n[k]}"></span>'
                   for k in SEV if n[k])
    keys = "".join(f'<button type="button" class="cx-mkey sev-{k}" data-dim="sev" data-val="{k}" aria-pressed="false">'
                   f'<i></i>{esc(SEV[k])} <b>{n[k]}</b></button>' for k in SEV if n[k])
    return (f'<div class="cx-meter" aria-label="חומרת הטעויות"><p><b>{len(grades)}</b> מהסתירות הן טעויות — '
            f'מקור שמשלם סוטה בהן מהכלל הגובר. חומרתן (לחיצה מסננת):</p><div class="cx-mbar">{segs}</div>'
            f'<div class="cx-mkeys" role="group" aria-label="סינון לפי חומרה">{keys}</div></div>'
            if grades else "")


def body(data: dict, *, prose, clause_link, finding_ids: set[str], src,
         simulator: tuple[str, str, int, list[str]] | None = None,
         evidence: dict[str, tuple[str, str]] | None = None,
         rows: list[dict] | None = None, href_of=lambda m: None,
         root_href: str = "root.html") -> tuple[str, str]:
    """The page's main column and its sidebar. `clause_link(doc, key)` gives
    (href, label html) for a corpus row; `src(file)` the published URL of a
    crop; `prose` renders our Hebrew with its identifiers isolated;
    `simulator` the simulator's group as (section, sidebar entries, rows,
    the grades of its graded rows); `rows` the root's rows (`root_rows`,
    MMS-521: the one place that decides), None where `make l4` recorded no
    report; `href_of(module)` an instrument's page."""
    shown = cards(data, rows)
    items = [c for c, _ in shown]
    inst = instruments() if rows else {}
    sim_html, sim_side, sim_n, sim_grades = simulator or ("", "", 0, [])
    out = [f'<h1>{esc(data["title"])}</h1>', f'<p class="lede">{prose(data["lede"])}</p>',
           f'<div class="banner cx-how" lang="he">{prose(data["how"])}</div>']
    if rows is None:
        out.append('<div class="banner">דוח הסתירות של השורש עוד לא נרשם בבנייה הזו (<code dir="ltr">make l4</code>): '
                   'בעמוד רק הכרטיסים שנכתבו ביד.</div>')
    else:
        n_gen = sum(1 for c, _ in shown if c.get("generated"))
        out.append(f'<p class="lede cx-fromroot">כל סתירה שהשורש מוצא בין המסמכים שהוא שוקל היא כרטיס כאן, '
                   f'שנבנה מהדוח של <a href="{esc(root_href)}">השורש</a>: {len(rows)} סתירות כאלה, '
                   f'{len(rows) - n_gen} מהן עם תמונות והסבר שנכתבו ביד ו־{n_gen} כפי שהשורש מדווח אותן. '
                   'כרטיס שהשורש אינו יכול לדבר בו נכתב ביד, ואומר למה.</p>')
    # the chips filter the cards by the kinds of source they set against each
    # other; "was it followed" is not a filter of its own any more, because
    # what is paid is a source too (the client, 2026-10-21)
    rows = []
    kinds = {k: sum(k in types(c) for c in items) for k in TYPE}
    kinds["simulator"] += sim_n
    chips = "".join(f'<button type="button" class="cx-tchip" data-dim="types" data-val="{k}" aria-pressed="false">'
                    f'{esc(TYPE[k])} <b>{n}</b></button>' for k, n in kinds.items() if n)
    rows.append(f'<div class="cx-frow" role="group" aria-label="סוגי המקורות">'
                f'<span class="cx-sumh">מקורות:</span>{chips}</div>')
    out.append(f'<div class="cx-sum" aria-label="סינון לפי סוג המקור">'
               + "".join(rows)
               + f'<div class="cx-frow"><button type="button" class="cx-all" aria-pressed="true">הכול <b>{len(items) + sim_n}</b></button></div></div>')
    out.append(meter([c["severity"] for c in errors(data)] + list(sim_grades)))


    side = ['<li class="sn-group"><details open><summary>בעמוד</summary><ul>']
    for group in data["groups"]:
        cs = [(c, row) for c, row in shown if c["group"] == group["id"]]
        if not cs:
            continue
        out.append(f'<section class="cx-group" id="g-{esc(group["id"])}"><h2>{esc(group["title"])} <small>{len(cs)}</small></h2>')
        side.append(f'<li><a href="#g-{esc(group["id"])}">{esc(group["title"])}</a></li>')
        for c, row in cs:
            if c.get("generated"):
                out.append(generated_html(c, row, inst, href_of=href_of, root_href=root_href))
            else:
                out.append(card(c, data["rules"], prose=prose, clause_link=clause_link,
                                finding_ids=finding_ids, src=src, evidence=evidence,
                                row=row, inst=inst, root_href=root_href))
        out.append('</section>')
    if sim_html:
        out.append(sim_html)
        side.append(sim_side)
    out.append('<section id="rules"><h2>הכללים שמכריעים</h2>')
    for rid, r in data["rules"].items():
        pic = figure(r["image"], r["quote"], src(r["image"]["file"])) if r.get("image") else ""
        link = f' · <a href="{esc(r["url"])}">{esc(r["url_label"])}</a>' if r.get("url") else ""
        link += f' · <a href="{esc(r["l4_page"])}">הסעיפים ב־L4</a>' if r.get("l4_page") else ""
        if r.get("doc"):
            href, label = clause_link(r["doc"], r["key"])
            link += f' · <a href="{esc(href)}">{label}</a>'
        q = f'<blockquote class="cx-quote cx-rq" lang="he" dir="rtl">{esc(r["quote"])}</blockquote>' if r.get("quote") else ""
        out.append(f'<div class="cx-rulecard" id="rule-{esc(rid)}"><h3>{esc(r["title"])}</h3>'
                   f'<p class="cx-rsrc">{esc(r["source"])}{link}</p>{pic}{q}'
                   + (f'<p>{prose(r["note"])}</p>' if r.get("note") else "") + '</div>')
    out.append('</section>')
    side.append('<li><a href="#rules">הכללים שמכריעים</a></li>')
    side.append("</ul></details></li>")
    return "".join(out), "".join(side)


def root_html(row: dict, inst: dict[str, tuple[str, str]], href: str) -> str:
    """What the root decides on a row (MMS-521): the instrument that
    governs and the rule, and for each set of instruments that speak, in
    how many of the cases checked and the first of them, with what each
    says — read off the root's own report."""
    def title(m: str) -> str:
        return inst.get(m, (m, ""))[0]
    lis = []
    for r in row["resolutions"]:
        says = " · ".join(f'{esc(title(m))}: <bdi dir="ltr">{esc(a)}</bdi>' for m, a in r["says"].items())
        lis.append(f'<li><b>{esc(" · ".join(title(m) for m in r["sources"]))}</b> '
                   f'<small>({r["cases"]} מקרים)</small><br>לדוגמה — {esc(r["example"])}: {says}; '
                   f'גובר <bdi dir="ltr">{esc(r["answer"])}</bdi></li>')
    return (f'<div class="cx-mean cx-root"><h4>מה השורש מכריע</h4>'
            f'<p>בפריט <b>{esc(row["item"])}</b> השורש שואל כל מסמך שמדבר עליו, ומוצא את הסתירה הזו '
            f'ב־{row["cases"]} מהמקרים שהוא בודק. גובר <b>{esc(title(row["governs"]))}</b> — לפי '
            f'{esc(row["rule"])}.</p><ul>{"".join(lis)}</ul><p><a href="{esc(href)}">השורש</a></p></div>')


def gate_html() -> str:
    """The L4 that proves a row of the root: its tests' gate, which holds
    every contradiction resolved by name, and precedence agreeing."""
    f, n = GATE
    return (f'<p class="cx-proof">ההוכחה ב־L4: <bdi dir="ltr"><code class="hl">'
            f'{l4src.highlight(f"#ASSERT {n}")}</code></bdi> <small dir="ltr">{esc(f)}</small></p>')


def generated_html(c: dict, row: dict, inst: dict[str, tuple[str, str]], *, href_of, root_href: str) -> str:
    """A card the root generates (MMS-521), for a row no hand card claims:
    the instruments that speak, what each says in the root's examples, the
    rule and the instrument that governs, and the root's report."""
    pair = " ↔ ".join(dict.fromkeys(TYPE[s["type"]] for s in c["sides"]))
    sides = []
    for s in c["sides"]:
        h = href_of(s["module"])
        where = f'<p class="cx-where"><a href="{esc(h)}">הקוד ב־L4</a></p>' if h else ""
        says = " · ".join(s["says"])
        sides.append(f'<div class="cx-side"><p class="cx-who"><span class="cx-type t-{esc(s["type"])}">'
                     f'{esc(TYPE[s["type"]])}</span> <b>{esc(s["label"])}</b></p>'
                     f'<p class="cx-says">בדוגמאות של השורש: <bdi dir="ltr">{esc(says)}</bdi></p>{where}</div>')
    gov = inst.get(row["governs"], (row["governs"], ""))[0]
    return (f'<details class="cx-card sev-none cx-gen" id="{esc(c["id"])}" data-types="{esc(" ".join(types(c)))}" data-sev="none">'
            f'<summary><p class="cx-pair">{esc(pair)} <span class="cx-genmark">מהשורש</span></p>'
            f'<h3>{esc(c["title"])}</h3></summary>'
            f'<p class="cx-stake">הכרטיס הזה נבנה מהדוח של השורש: המסמכים שמדברים, מה כל אחד אומר במקרה '
            f'הראשון שבו הם חלוקים, והכלל שמכריע. אין בו תמונות והסבר שנכתבו ביד.</p>'
            f'<div class="cx-sides">{"".join(sides)}</div>'
            f'<div class="cx-rule"><h4>מי גובר?</h4><p class="cx-rsrc"><b>{esc(row["rule"])}</b> — סדר העדיפות '
            f'שבשורש · <a href="{esc(root_href)}">השורש</a></p></div>'
            f'<p class="cx-win">לפי הכלל גובר: <b>{esc(gov)}</b></p>'
            + root_html(row, inst, root_href) + gate_html() + '</details>')


def card(c: dict, rules: dict, *, prose, clause_link, finding_ids, src, evidence=None,
         row: dict | None = None, inst: dict | None = None, root_href: str = "root.html") -> str:
    sev = c.get("severity")
    badge = f'<span class="cx-sev sev-{sev}">טעות · {esc(SEV[sev])}</span>' if sev else ""
    pair = " ↔ ".join(TYPE[s["type"]] for s in c["sides"])
    way = (f'<span class="cx-dir dir-{c["direction"]}">{esc(DIRECTION[c["direction"]])}</span>'
           if c.get("direction") else "")
    links = []
    for f in c.get("findings", []):
        ref = f'<bdi dir="ltr" class="fref">{esc(f)}</bdi>'
        links.append(f'<a href="findings.html#{esc(f)}">{ref}</a>' if f in finding_ids else ref)
    winner = c.get("winner")
    sides = "".join(side_html(s, clause_link=clause_link, src=src) for s in c["sides"])
    # collapsed by default (the client, 2026-10-20): the summary line says what
    # is set against what and the grade; a tap opens the rest
    silent = (f'<p class="cx-silent">אין כאן תשובה: {esc(" ".join(c["silent"]))}</p>'
              if c.get("silent") else "")
    return (f'<details class="cx-card sev-{sev or "none"}" id="{esc(c["id"])}" data-types="{esc(" ".join(types(c)))}" data-sev="{sev or "none"}">'
            f'<summary><p class="cx-pair">{esc(pair)} {way} {badge}</p><h3>{esc(c["title"])}</h3></summary>'
            f'<p class="cx-stake">{prose(c["stake"])}</p>'
            f'<div class="cx-sides">{sides}</div>'
            + rule_html(rules[c["rule"]], c["rule_note"], prose=prose, src=src)
            + (f'<p class="cx-win">לפי הכלל גובר: <b>{esc(winner)}</b></p>' if winner else "")
            + direction_html(c, prose=prose)
            + (f'<p class="cx-sevwhy"><span class="cx-sev sev-{sev}">{esc(SEV[sev])}</span> {prose(c["severity_why"])}</p>'
               if sev else "") + silent
            # what an error means for a teacher (the client: "a משמעות section")
            + (f'<div class="cx-mean"><h4>משמעות</h4><p>{prose(c["meaning"])}</p></div>' if c.get("meaning") else "")
            + (root_html(row, inst or {}, root_href) if row else "")
            + (f'<p class="cx-noroot">{esc(NOT_IN_ROOT[c["not_in_root"]])}</p>'
               if c.get("not_in_root") in NOT_IN_ROOT else "")
            + (f'<p class="cx-links">{" · ".join(links)}</p>' if links else "")
            + (('<p class="cx-proof">ההוכחה ב־L4: ' + " · ".join(
                f'<bdi dir="ltr"><code class="hl">{l4src.highlight(f"#ASSERT `{n}`")}</code></bdi>'
                for _f, n in proofs(c, evidence or {}))
                + "</p>") if proofs(c, evidence or {}) else "")
            + (gate_html() if row else "")
            + '</details>')
