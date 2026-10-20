"""פערי הסימולטור (calculator-delta.html, MMS-513): where the Ministry of
Education's public salary simulator computes something other than the L4.

The page is built from data/calculator-delta.json and from nothing else. That
file holds only what the comparison found: the inputs of each example request,
the simulator's line and the L4's, the mapping from the simulator's fields and
pay codes to the L4 rules, the clauses that govern each difference with their
words verbatim from the corpus, and a classification. It holds none of the
simulator's code and none of its recorded traffic; the comparison that writes
it runs outside this repository, on a private extraction (MMS-512), and asks
the L4 evaluator for every figure in the L4 column. tests/test_calculator_delta.py
holds the file to that.

The simulator is the ministry's own non-binding tool. What it computes is
evidence of how the payer's software works -- the status quo of decision 17 --
and never a reading of the law.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

esc = html.escape

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "calculator-delta.json"
HERE = "calculator-delta.html"
TAB = "פערי הסימולטור"

CLASS_ORDER = ("simulator", "l4-bug", "ambiguous")
CLASS_SHORT = {"simulator": "הסימולטור סוטה", "l4-bug": "באג ב־L4", "ambiguous": "שתי קריאות", "quirk": "טעות של הסימולטור"}
CLASS_LETTER = {"l4-bug": "א", "simulator": "ב", "ambiguous": "ג"}
CLASS_GLOSS = {
    "l4-bug": "הקידוד שגוי מול הטקסט: הבאג נרשם לתיקון ב־L4.",
    "simulator": "הסימולטור מחשב אחרת ממה שהטקסט קובע. זו ראיה לנוהג, לא דין; היכן שהיא נוגעת לממצא, הדירוג המוצע מופיע.",
    "ambiguous": "הטקסט מאפשר את שתי התוצאות, או שההכרעה מחוץ לקורפוס; הממצא או המוסכמה שמכריעים ב־L4 מצוינים.",
}
SEV = {"high": "חמור", "medium": "בינוני", "low": "קל"}
STATUS = {"not-encoded": "לא מקודד", "not-comparable": "לא בר־השוואה"}


def load() -> dict | None:
    return json.loads(DATA.read_text(encoding="utf-8")) if DATA.exists() else None


def num(n) -> str:
    return f'<bdi dir="ltr">{n:,}</bdi>' if isinstance(n, int) else f'<bdi dir="ltr">{esc(str(n))}</bdi>'


def body(data: dict, *, prose, clause_link, finding_ids: set[str], conv_titles: dict[str, str],
         l4_link) -> tuple[str, str]:
    """The page's main column and its sidebar. `clause_link(doc, key)` gives
    (href, label html) for a corpus row; `l4_link(file)` the page of an L4
    file; `prose` renders our Hebrew with its identifiers isolated."""
    m = data["meta"]
    calcs = data["summary"]
    total_req = sum(c["requests"] for c in calcs.values())
    total_lines = sum(c["lines"] for c in calcs.values())
    total = {k: sum(c[k] for c in calcs.values()) for k in ("match", "delta", "not_encoded", "not_comparable")}

    out = [f'<h1>{esc(data["title"])}</h1>',
           '<p class="lede">היכן שסימולטור השכר של משרד החינוך מחשב דבר אחר מהקידוד שלנו לדיני השכר של עובדי ההוראה: '
           'כל שורת שכר שהסימולטור החזיר הושוותה, עד האגורה, לשורה שה־L4 מחשב מאותם נתונים, והפערים קובצו לפי הסיבה — '
           'כלל אחד שונה, לא שורה לכל בקשה.</p>',
           '<div class="banner dl-warn" lang="he"><strong>הסימולטור אינו מחייב.</strong> זהו כלי ציבורי של משרד החינוך '
           f'({esc(m["source"])}), שלפי הצהרתו רק מדמה שכר. מה שהוא מחשב מראה איך מחשבת התוכנה של המשלם — '
           'ראיה לנוהג, כמו תלוש — ולא את הדין, ולעולם אינו בוחר קידוד או קריאה. חוזר אינו גובר על הסכם, וגם הסימולטור לא.</div>']

    # --------------------------------------------------- what is compared
    out.append('<section id="what"><h2>מה הושווה</h2>'
               f'<p>הבקשות שנרשמו מהסימולטור ב־<bdi dir="ltr">{esc(m["captured"])}</bdi>, לחודש השכר '
               f'<bdi dir="ltr">{esc(m["salary_month"])}</bdi>, בארבעת המחשבונים: {num(total_req)} בקשות ו־{num(total_lines)} שורות שכר. '
               f'הקורפוס בגרסה <bdi dir="ltr"><code>{esc(m["corpus_commit"][:10])}</code></bdi>, '
               f'ה־L4 בגרסה <bdi dir="ltr"><code>{esc(m["l4_commit"])}</code></bdi>.</p>'
               f'<p>{prose(data["compose_note"])}</p><p>{prose(data["cap_note"])}</p>')
    rows = "".join(f'<tr><td><bdi dir="ltr"><code>{esc(f["field"])}</code></bdi></td><td>{esc(f["label"])}</td>'
                   f'<td>{prose(f["l4"])}</td></tr>' for f in data["mapping"]["fields"])
    out.append('<h3>שדות הטופס ← קלטי ה־L4</h3><div class="scroll-x"><table class="diag dl-map"><thead><tr>'
               '<th>שדה</th><th>בטופס</th><th>ב־L4</th></tr></thead><tbody>' + rows + '</tbody></table></div>')
    names = data["calculators"]
    hows = {"compared": "הושווה", "proration": "חלקיות המשרה בלבד"}
    rows = "".join(f'<tr><td><bdi dir="ltr">{esc(c["code"])}</bdi></td>'
                   f'<td>{esc(", ".join(names.get(x.strip(), x) for x in c["calc"].split(",")))}</td>'
                   f'<td>{esc(hows[c["how"]])}</td><td>{prose(c["l4"])}</td></tr>' for c in data["mapping"]["codes"])
    out.append('<h3>קודי השכר של הסימולטור ← כללי ה־L4</h3><div class="scroll-x"><table class="diag dl-map"><thead><tr>'
               '<th>קוד</th><th>מחשבון</th><th>מה נבדק</th><th>הכלל ב־L4</th></tr></thead><tbody>' + rows
               + '</tbody></table></div></section>')

    # --------------------------------------------------- summary
    rows = "".join(f'<tr><th>{esc(c["name"])}</th><td>{num(c["requests"])}</td><td>{num(c["lines"])}</td>'
                   f'<td class="okay">{num(c["match"])}</td><td class="notok">{num(c["delta"])}</td>'
                   f'<td>{num(c["not_encoded"])}</td><td>{num(c["not_comparable"])}</td>'
                   f'<td>{num(c["requests_with_material_delta"])}</td></tr>' for c in calcs.values())
    rows += (f'<tr class="dl-total"><th>סך הכול</th><td>{num(total_req)}</td><td>{num(total_lines)}</td>'
             f'<td class="okay">{num(total["match"])}</td><td class="notok">{num(total["delta"])}</td>'
             f'<td>{num(total["not_encoded"])}</td><td>{num(total["not_comparable"])}</td>'
             f'<td>{num(sum(c["requests_with_material_delta"] for c in calcs.values()))}</td></tr>')
    bc = data["by_class"]
    chips = "".join(f'<a class="dl-chip cls-{k}" href="#cls-{k}">{esc(CLASS_SHORT[k])} '
                    f'<b>{num(bc[k]["lines"])}</b> שורות · <b>{num(bc[k]["requests"])}</b> בקשות</a>'
                    for k in (*CLASS_ORDER, "quirk") if k in bc)
    out.append('<section id="summary"><h2>סיכום</h2>'
               '<div class="scroll-x"><table class="diag dl-sum"><thead><tr><th>מחשבון</th><th>בקשות</th><th>שורות</th>'
               '<th>תואמות</th><th>שונות</th><th>לא מקודדות</th><th>לא ברות השוואה</th><th>בקשות עם פער של ממש</th>'
               '</tr></thead><tbody>' + rows + '</tbody></table></div>'
               '<p class="dl-note">"שורות לא מקודדות" הן שורות שאין להן כלל ב־L4: זהו כיסוי, לא פער. '
               '"פער של ממש" — כל פער מלבד אגורות התוספת השקלית, העיגול, שיעור תוספת 2008 המודפס והשורה שנבלעת בשכר המינימום.</p>'
               f'<div class="dl-chips">{chips}</div></section>')

    # --------------------------------------------------- causes
    side = ['<li class="sn-group"><details open><summary>בעמוד</summary><ul>'
            '<li><a href="#what">מה הושווה</a></li><li><a href="#summary">סיכום</a></li>']
    for cls in CLASS_ORDER:
        cs = [c for c in data["causes"] if c["class"] == cls]
        if not cs:
            continue
        out.append(f'<section class="dl-class" id="cls-{cls}"><h2><span class="cls-tag cls-{cls}">'
                   f'({CLASS_LETTER[cls]})</span> {esc(data["classes"][cls])} <small>{len(cs)}</small></h2>'
                   f'<p class="dl-note">{esc(CLASS_GLOSS[cls])}</p>')
        side.append(f'<li><a href="#cls-{cls}">({CLASS_LETTER[cls]}) {esc(CLASS_SHORT[cls])}</a></li>')
        for c in cs:
            out.append(cause_card(c, prose=prose, clause_link=clause_link, finding_ids=finding_ids,
                                  conv_titles=conv_titles, l4_link=l4_link))
        out.append("</section>")

    # --------------------------------------------------- quirks
    out.append('<section id="quirks"><h2>הטעויות של הסימולטור עצמו</h2>'
               '<p class="dl-note">התנהגות שהיא באג של הכלי ולא קריאה של הטקסט. גם בה ה־L4 מחשב לפי הטקסט.</p>')
    for q in data["quirks"]:
        out.append(f'<details class="finding dl-cause" id="{esc(q["id"])}"><summary>'
                   f'<span class="cls-tag cls-quirk">באג</span><span class="ftitle">{prose(q["title"])}</span>'
                   f'<span class="dl-count">{num(q.get("requests", 0))} בקשות</span></summary><div class="fcard">'
                   f'<p>{prose(q["body"])}</p>{examples_html(q.get("examples", []))}</div></details>')
    out.append("</section>")
    side.append('<li><a href="#quirks">טעויות הסימולטור</a></li>')

    # --------------------------------------------------- coverage
    rows = []
    for c in data["coverage"]:
        codes = "، ".join(f'{esc(x["line"] or str(x["code"]))} <bdi dir="ltr">({x["code"]})</bdi>' for x in c["codes"][:6])
        more = f' ועוד {len(c["codes"]) - 6}' if len(c["codes"]) > 6 else ""
        rows.append(f'<tr><td><span class="dl-st {c["status"]}">{esc(STATUS[c["status"]])}</span></td>'
                    f'<th>{esc(c["title"])}</th><td>{prose(c["why"]) if c["why"] else ""}'
                    + (f'<div class="dl-codes">{codes}{more}</div>' if codes else "")
                    + f'</td><td class="n" data-l="שורות:">{num(c["lines"])}</td>'
                    f'<td class="n" data-l="בקשות:">{num(c["requests"])}</td></tr>')
    out.append('<section id="coverage"><h2>מה לא הושווה</h2>'
               '<p class="dl-note">שורה שאין לה כלל ב־L4 היא שאלה של כיסוי, ולא נספרת כפער. '
               'שורה שהסימולטור מחשב מקלט שהקורפוס אינו מגדיר אינה ברת השוואה.</p>'
               '<div class="scroll-x"><table class="diag dl-cov"><thead><tr><th></th><th>מה</th><th>למה</th>'
               '<th>שורות</th><th>בקשות</th></tr></thead><tbody>' + "".join(rows) + '</tbody></table></div></section>')
    side.append('<li><a href="#coverage">מה לא הושווה</a></li>')

    # --------------------------------------------------- the shekel supplement over two years
    sc = data.get("shekel_scan") or []
    if sc:
        rows = "".join(f'<tr><td>{num(r["year"])}</td><td>{num(r["grade"])}</td><td>{num(r["l4"])}</td>'
                       f'<td>{num(", ".join(r["simulator"]))}</td></tr>' for r in sc)
        out.append('<section id="shekel"><h2>התוספת השקלית 2016 בחודשי 2025–2026, במשרה מלאה</h2>'
                   '<p class="dl-note">הסכום לדרגה לפי תשפ"ה/7 (2025) ותשפ"ו/6 (2026), מול מה שהסימולטור משלם באותם חודשים.</p>'
                   '<div class="scroll-x"><table class="diag dl-scan"><thead><tr><th>שנה</th><th>דרגה</th><th>L4 (החוזר)</th>'
                   '<th>הסימולטור</th></tr></thead><tbody>' + rows + '</tbody></table></div></section>')
        side.append('<li><a href="#shekel">התוספת השקלית לאורך זמן</a></li>')
    side.append("</ul></details></li>")
    return "".join(out), "".join(side)


def examples_html(examples: list[dict]) -> str:
    if not examples:
        return ""
    items = []
    for e in examples:
        ins = "".join(f'<li><span class="k">{esc(k)}</span> <bdi>{esc(v)}</bdi></li>' for k, v in e["inputs"])
        outs = "".join(f'<li><span class="k">{esc(k)}</span> <bdi dir="ltr" class="amt">{esc(v)}</bdi></li>' for k, v in e["outputs"])
        head = f'{esc(e["calc"])}' + (f' · {esc(e["line"])} <bdi dir="ltr">({e["code"]})</bdi>' if e.get("line") else "")
        base = (f'<li><span class="k">שכר משולב + תוספת אופק 2022, משרה מלאה</span> <bdi dir="ltr" class="amt">{esc(e["base"])}</bdi></li>'
                if e.get("base") else "")
        items.append(f'<div class="dl-ex"><p class="dl-exh">{head}</p><ul class="dl-in">{ins}{base}</ul>'
                     f'<ul class="dl-out">{outs}</ul></div>')
    return '<div class="dl-exs">' + "".join(items) + "</div>"


def cause_card(c: dict, *, prose, clause_link, finding_ids, conv_titles, l4_link) -> str:
    cls = c["class"]
    count = (f'{num(c["lines"])} שורות · {num(c["requests"])} בקשות' if c["counted"]
             else ("לא נספר בטבלאות" if not c["lines"] else f'{num(c["requests"])} בקשות · לא נספר בטבלאות'))
    paras = "".join(f"<p>{prose(p)}</p>" for p in c["body"])
    clauses = []
    for q in c["clauses"]:
        href, label = clause_link(q["doc"], q["key"])
        lab = f'<a href="{esc(href)}">{label}</a>' if href else label
        clauses.append(f'<figure class="dl-clause"><blockquote lang="he" dir="rtl">{esc(q["quote"])}</blockquote>'
                       f'<figcaption>{lab}</figcaption></figure>')
    links = []
    for f in c["findings"]:
        if f in finding_ids:
            links.append(f'<a href="findings.html#{esc(f)}"><bdi dir="ltr" class="fref">{esc(f)}</bdi></a>')
        else:
            links.append(f'<bdi dir="ltr" class="fref">{esc(f)}</bdi>')
    for v in c["conventions"]:
        links.append(f'<a href="conventions.html#{esc(v)}">המוסכמה: {esc(conv_titles.get(v, v))}</a>')
    rules = []
    for r in c["l4"]:
        href = l4_link(r["file"])
        code = f'<bdi dir="ltr" lang="en"><code>{esc(r["rule"])}</code></bdi>'
        rules.append(f'<a href="{esc(href)}">{code}</a>' if href else code)
    sev = c.get("severity")
    sev_html = (f'<p class="fsev"><span class="sev-badge sev-{sev["grade"]}">מוצע: {esc(SEV[sev["grade"]])}</span> '
                f'{prose(sev["why"])}</p>' if sev else "")
    codes = (f' · קוד <bdi dir="ltr">{", ".join(str(x) for x in c["codes"])}</bdi>' if c.get("codes") else "")
    return (f'<details class="finding dl-cause" id="{esc(c["id"])}" open><summary>'
            f'<span class="cls-tag cls-{cls}">{esc(CLASS_SHORT[cls])}</span>'
            f'<span class="ftitle">{prose(c["title"])}</span><span class="dl-count">{count}{codes}</span></summary>'
            f'<div class="fcard">{sev_html}<div class="fbody" lang="he" dir="rtl">{paras}</div>'
            + examples_html(c["examples"])
            + ("<h4>הטקסט</h4>" + "".join(clauses) if clauses else "")
            + (f'<p class="dl-links">{" · ".join(links)}</p>' if links else "")
            + (f'<p class="dl-rules">הכלל ב־L4: {" · ".join(rules)}</p>' if rules else "")
            + "</div></details>")
