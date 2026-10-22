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

The simulator also has a group of its own (tools/calculator_delta.py,
MMS-522): every place its computation departs from the text, produced by the
comparison rather than picked, under the simulator's own disclaimer that it
binds no one.
"""
from __future__ import annotations

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
    return list(dict.fromkeys(out))


def load() -> dict | None:
    return json.loads(DATA.read_text(encoding="utf-8")) if DATA.exists() else None


# A weaker source departing from a stronger one — a circular from the agreement
# or the letter it carries out, an answer on the site from the takanon, the
# takanon from a circular or an agreement — is a card on this page and not a
# finding (the client, 2026-10-22: "a weaker one departing from a stronger one
# has its own page, סתירה in finding means equal power"). Two circulars, or a
# document against itself, are of equal power and stay findings.
CROSS_RANK = ("agreement", "letter", "qa", "takanon")


def homes(data: dict | None) -> dict[str, str]:
    """finding id -> the card it lives on, for every finding a card of a
    weaker-against-stronger group cites: these leave the findings page."""
    out: dict[str, str] = {}
    for c in (data or {}).get("items", []):
        if c.get("group") in CROSS_RANK:
            for f in c.get("findings", []):
                out.setdefault(f, c["id"])
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
         root: dict[str, list[list[str]]] | None = None,
         root_href: str = "root.html") -> tuple[str, str]:
    """The page's main column and its sidebar. `clause_link(doc, key)` gives
    (href, label html) for a corpus row; `src(file)` the published URL of a
    crop; `prose` renders our Hebrew with its identifiers isolated;
    `simulator` the simulator's group as (section, sidebar entries, rows,
    the grades of its graded rows); `root` the root's resolutions by the
    name of their item (MMS-521: the one place that decides), each as
    [sources, governs, rule, cases]."""
    items = data["items"]
    sim_html, sim_side, sim_n, sim_grades = simulator or ("", "", 0, [])
    out = [f'<h1>{esc(data["title"])}</h1>', f'<p class="lede">{prose(data["lede"])}</p>',
           f'<div class="banner cx-how" lang="he">{prose(data["how"])}</div>']
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
        cs = [c for c in items if c["group"] == group["id"]]
        if not cs:
            continue
        out.append(f'<section class="cx-group" id="g-{esc(group["id"])}"><h2>{esc(group["title"])} <small>{len(cs)}</small></h2>')
        side.append(f'<li><a href="#g-{esc(group["id"])}">{esc(group["title"])}</a></li>')
        for c in cs:
            out.append(card(c, data["rules"], prose=prose, clause_link=clause_link,
                            finding_ids=finding_ids, src=src, evidence=evidence,
                            root=root or {}, root_href=root_href))
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


def root_html(item: str, lines: list[list[str]], href: str) -> str:
    """What the root decides on the card's item: every set of instruments
    that disagree on it, which governs and by which rule, and in how many of
    the cases it checks — read off the root's own report (MMS-521)."""
    # one line for each instrument that governs by one rule, naming what it
    # governs over, so eight circulars set against one agreement read once
    groups: dict[tuple[str, str], tuple[list[str], int]] = {}
    for sources, governs, rule, n in lines:
        over, total = groups.get((governs, rule), ([], 0))
        over += [t for t in sources.split(" · ") if t != governs and t not in over]
        groups[(governs, rule)] = (over, total + int(n or 0))
    lis = "".join(f'<li>גובר <b>{esc(governs)}</b> על {esc(" · ".join(over))} — לפי {esc(rule)} '
                  f'<small>({total} מקרים)</small></li>'
                  for (governs, rule), (over, total) in groups.items())
    return (f'<div class="cx-mean cx-root"><h4>מה השורש מכריע</h4>'
            f'<p>בפריט <b>{esc(item)}</b> השורש שואל כל מסמך שמדבר עליו, ומכריע בכל מחלוקת לפי סדר העדיפות:</p>'
            f'<ul>{lis}</ul><p><a href="{esc(href)}">השורש</a></p></div>')


def card(c: dict, rules: dict, *, prose, clause_link, finding_ids, src, evidence=None,
         root: dict | None = None, root_href: str = "root.html") -> str:
    sev = c.get("severity")
    badge = f'<span class="cx-sev sev-{sev}">טעות · {esc(SEV[sev])}</span>' if sev else ""
    pair = " ↔ ".join(TYPE[s["type"]] for s in c["sides"])
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
            f'<summary><p class="cx-pair">{esc(pair)} {badge}</p><h3>{esc(c["title"])}</h3></summary>'
            f'<p class="cx-stake">{prose(c["stake"])}</p>'
            f'<div class="cx-sides">{sides}</div>'
            + rule_html(rules[c["rule"]], c["rule_note"], prose=prose, src=src)
            + (f'<p class="cx-win">לפי הכלל גובר: <b>{esc(winner)}</b></p>' if winner else "")
            + (f'<p class="cx-sevwhy"><span class="cx-sev sev-{sev}">{esc(SEV[sev])}</span> {prose(c["severity_why"])}</p>'
               if sev else "") + silent
            # what an error means for a teacher (the client: "a משמעות section")
            + (f'<div class="cx-mean"><h4>משמעות</h4><p>{prose(c["meaning"])}</p></div>' if c.get("meaning") else "")
            + (root_html(c["root_item"], (root or {})[c["root_item"]], root_href)
               if c.get("root_item") and (root or {}).get(c["root_item"]) else "")
            + (f'<p class="cx-links">{" · ".join(links)}</p>' if links else "")
            + (('<p class="cx-proof">ההוכחה ב־L4: ' + " · ".join(
                f'<bdi dir="ltr"><code class="hl">{l4src.highlight(f"#ASSERT `{n}`")}</code></bdi>'
                for _f, n in proofs(c, evidence or {}))
                + "</p>") if proofs(c, evidence or {}) else "")
            + '</details>')
