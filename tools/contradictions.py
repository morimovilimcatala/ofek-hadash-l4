"""סתירות בין מסמכים (contradictions.html, MMS-515): where one instrument
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

Whether a rule was followed is evidence of practice: a ministry document, the
ministry's simulator (calculator-delta.html), or the payslips described in
general terms. It never changes a reading.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

esc = html.escape

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "contradictions.json"
CROPS = ROOT / "data" / "contradictions"
HERE = "contradictions.html"
TAB = "סתירות בין מסמכים"

TYPE = {"agreement": "הסכם קיבוצי", "circular": "חוזר", "letter": "מכתב", "takanon": "תקנון",
        "qa": "שאלות ותשובות", "table": "טבלת שכר", "law": "חוק", "payment": "התשלום בפועל"}


def types(c: dict) -> list[str]:
    """The kinds of thing a contradiction sets against each other; a
    document against its payment counts the payment as one."""
    out = [s["type"] for s in c["sides"]] + (["payment"] if c["group"] == "payment" else [])
    return sorted(set(out), key=list(TYPE).index)
SEV = {"high": "חמור", "medium": "בינוני", "low": "קל"}
FOLLOWED = {"yes": ("קוים", "fol-yes"), "no": ("לא קוים", "fol-no"),
            "partly": ("קוים בחלקו", "fol-part"), "unknown": ("לא ידוע", "fol-unk"),
            "none": ("אין כלל", "fol-unk")}
SOURCES = (("payslips", "בתלוש"), ("simulator", "בסימולטור"))
KIND = {"render": "עמוד דיגיטלי, מרונדר ב־{dpi} dpi",
        "scan": "סריקה, ברזולוציה המקורית ({dpi} ppi)",
        "html": "דף מהעותק השמור של האתר (1.6.2026), כפי שהדפדפן מציג אותו, בצפיפות כפולה; תשובה מקופלת נפתחה כמו בלחיצה"}


def load() -> dict | None:
    return json.loads(DATA.read_text(encoding="utf-8")) if DATA.exists() else None


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


def side_html(s: dict, *, clause_link, src) -> str:
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
    """The contradictions whose rule was not followed, on a payslip or in the
    simulator: errors, each graded."""
    return [c for c in data["items"]
            if any(v["followed"] in ("no", "partly") for v in c["practice"].values())]


def meter(errs: list[dict]) -> str:
    n = {k: sum(c["severity"] == k for c in errs) for k in SEV}
    total = len(errs) or 1
    segs = "".join(f'<span class="cx-mseg sev-{k}" style="flex:{n[k]}" title="{esc(SEV[k])}: {n[k]}"></span>'
                   for k in SEV if n[k])
    keys = "".join(f'<span class="cx-mkey sev-{k}"><i></i>{esc(SEV[k])} <b>{n[k]}</b></span>' for k in SEV)
    return (f'<div class="cx-meter" aria-label="חומרת הטעויות"><p><b>{len(errs)}</b> מתוך הסתירות הן טעויות — '
            f'הכלל שמכריע בהן לא קוים. חומרתן:</p><div class="cx-mbar">{segs}</div><div class="cx-mkeys">{keys}</div></div>'
            if errs else "")


def body(data: dict, *, prose, clause_link, finding_ids: set[str], src) -> tuple[str, str]:
    """The page's main column and its sidebar. `clause_link(doc, key)` gives
    (href, label html) for a corpus row; `src(file)` the published URL of a
    crop; `prose` renders our Hebrew with its identifiers isolated."""
    items = data["items"]
    out = [f'<h1>{esc(data["title"])}</h1>', f'<p class="lede">{prose(data["lede"])}</p>',
           f'<div class="banner cx-how" lang="he">{prose(data["how"])}</div>']
    # the chips filter the cards by whether the rule was followed, on the
    # payslips and in the simulator separately (the client, 2026-10-20)
    rows = []
    for dim, label in SOURCES:
        counts = {k: sum(c["practice"][dim]["followed"] == k for c in items) for k in FOLLOWED}
        chips = "".join(f'<button type="button" class="cx-fol {FOLLOWED[k][1]}" data-dim="{dim}" data-val="{k}" '
                        f'aria-pressed="false">{esc(FOLLOWED[k][0])} <b>{n}</b></button>'
                        for k, n in counts.items() if n)
        rows.append(f'<div class="cx-frow" role="group" aria-label="{esc(label)}">'
                    f'<span class="cx-sumh">קוים {esc(label)}:</span>{chips}</div>')
    # and by the kinds of document the contradiction sets against each other
    kinds = {k: sum(k in types(c) for c in items) for k in TYPE}
    chips = "".join(f'<button type="button" class="cx-tchip" data-dim="types" data-val="{k}" aria-pressed="false">'
                    f'{esc(TYPE[k])} <b>{n}</b></button>' for k, n in kinds.items() if n)
    rows.insert(0, f'<div class="cx-frow" role="group" aria-label="סוגי המסמכים">'
                   f'<span class="cx-sumh">מסמכים:</span>{chips}</div>')
    out.append(f'<div class="cx-sum" aria-label="סינון לפי: האם הכלל קוים — כל שורה מסננת בנפרד, והשתיים מצטרפות">'
               + "".join(rows)
               + f'<div class="cx-frow"><button type="button" class="cx-all" aria-pressed="true">הכול <b>{len(items)}</b></button></div></div>')
    out.append(meter(errors(data)))


    side = ['<li class="sn-group"><details open><summary>בעמוד</summary><ul>']
    for group in data["groups"]:
        cs = [c for c in items if c["group"] == group["id"]]
        if not cs:
            continue
        out.append(f'<section class="cx-group" id="g-{esc(group["id"])}"><h2>{esc(group["title"])} <small>{len(cs)}</small></h2>')
        side.append(f'<li><a href="#g-{esc(group["id"])}">{esc(group["title"])}</a></li>')
        for c in cs:
            out.append(card(c, data["rules"], prose=prose, clause_link=clause_link,
                            finding_ids=finding_ids, src=src))
        out.append('</section>')
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


def card(c: dict, rules: dict, *, prose, clause_link, finding_ids, src) -> str:
    sev = c.get("severity")
    badge = f'<span class="cx-sev sev-{sev}">טעות · {esc(SEV[sev])}</span>' if sev else ""
    pair = " ↔ ".join([TYPE[s["type"]] for s in c["sides"]] + ([TYPE["payment"]] if c["group"] == "payment" else []))
    links = []
    for f in c.get("findings", []):
        ref = f'<bdi dir="ltr" class="fref">{esc(f)}</bdi>'
        links.append(f'<a href="findings.html#{esc(f)}">{ref}</a>' if f in finding_ids else ref)
    if c.get("delta"):
        links.append(f'<a href="calculator-delta.html#{esc(c["delta"])}">פערי הסימולטור</a>')
    p = c["practice"]
    winner = c.get("winner")
    sides = "".join(side_html(s, clause_link=clause_link, src=src) for s in c["sides"])
    return (f'<article class="cx-card sev-{sev or "none"}" id="{esc(c["id"])}" data-types="{esc(" ".join(types(c)))}" data-payslips="{esc(p["payslips"]["followed"])}" data-simulator="{esc(p["simulator"]["followed"])}">'
            f'<header><p class="cx-pair">{esc(pair)} {badge}</p><h3>{esc(c["title"])}</h3>'
            f'<p class="cx-stake">{prose(c["stake"])}</p></header>'
            f'<div class="cx-sides">{sides}</div>'
            + rule_html(rules[c["rule"]], c["rule_note"], prose=prose, src=src)
            + (f'<p class="cx-win">לפי הכלל גובר: <b>{esc(winner)}</b></p>' if winner else "")
            + '<div class="cx-prac"><h4>האם הכלל קוים?</h4>'
            + "".join(f'<p><span class="cx-src">{esc(label)}</span> '
                      f'<span class="cx-fol {FOLLOWED[p[dim]["followed"]][1]}">{esc(FOLLOWED[p[dim]["followed"]][0])}</span> '
                      f'{prose(p[dim]["text"])}</p>' for dim, label in SOURCES)
            + (f'<p class="cx-sevwhy"><span class="cx-sev sev-{sev}">{esc(SEV[sev])}</span> {prose(c["severity_why"])}</p>'
               if sev else "") + '</div>'
            # what an error means for a teacher (the client: "a משמעות section")
            + (f'<div class="cx-mean"><h4>משמעות</h4><p>{prose(c["meaning"])}</p></div>' if c.get("meaning") else "")
            + (f'<p class="cx-links">{" · ".join(links)}</p>' if links else "")
            + '</article>')
