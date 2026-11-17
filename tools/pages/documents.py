"""A document's pages: a section's rows beside its L4, a sectioned document's
contents and chapters, a whole document, a collection.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
import subprocess
import sys
import textwrap
import tomllib
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import akn      # noqa: E402
import calculator  # noqa: E402
import calculator_delta  # noqa: E402
import edge_traces  # noqa: E402
import contradictions  # noqa: E402
import laws  # noqa: E402
import modules  # noqa: E402
import roots  # noqa: E402
import l4src    # noqa: E402
import statute_record  # noqa: E402
from pages.common import *  # noqa: E402,F401,F403
from pages.model import *  # noqa: E402,F401,F403
from pages.layout import *  # noqa: E402,F401,F403

STATUS = {"done": "מקודד", "partial": "מקודד בחלקו", "todo": "טרם קודד"}


def dot(status: str) -> str:
    return f'<span class="dot {status}" title="{STATUS[status]}" aria-label="{STATUS[status]}"></span>'


def badge(status: str) -> str:
    return f'<span class="badge {status}">{STATUS[status]}</span>'


def text_cell(r: akn.Row) -> str:
    num = f'<span class="num">{esc(r.num)}</span>' if r.num else ""
    head = f'<span class="h">{esc(r.heading)}</span>' if r.heading else ""
    if r.kind == "label":
        return num + head
    if r.cells is not None:
        spans = r.spans or [[(1, 1)] * len(row) for row in r.cells]

        def td(c: str, span: tuple[int, int]) -> str:
            attrs = "".join(f' {name}="{n}"' for name, n in zip(("rowspan", "colspan"), span) if n > 1)
            return f"<td{attrs}>{esc(c)}</td>"
        body = "".join("<tr>" + "".join(td(c, sp) for c, sp in zip(row, srow)) + "</tr>"
                       for row, srow in zip(r.cells, spans))
        return f'<div class="ctable"><table>{body}</table></div>'
    # a corpus sic mark is the corpus's: its correction is taken as given and
    # the text is shown plain (the client, 2026-10-06: no כך במקור on this site)
    return num + head + f'<span class="t">{"".join(esc(run.text) for run in r.runs)}</span>'


def results_html(seg: l4src.Segment) -> str:
    if not seg.results and not seg.diagnostics:
        return ""
    items = []
    for res in seg.results:
        kind = str(res.get("kind", ""))
        val = res.get("value")
        sval = val if isinstance(val, str) else json.dumps(val, ensure_ascii=False)
        label = {"assertion": "assert", "value": "eval"}.get(kind, kind)
        if kind == "value" and "\n" in str(sval):
            label = "trace"
        bad = kind == "assertion" and str(sval).strip().lower() != "true"
        shown = "holds" if kind == "assertion" and not bad else str(sval)
        items.append(f'<li class="res {label}{" bad" if bad else ""}"><span class="rk">{esc(label)}</span>'
                     f'<span class="rl">L{line_of(res.get("range"))}</span>'
                     f'<code>{esc(shown)[:600]}</code></li>')
    for d in seg.diagnostics:
        items.append(f'<li class="res bad"><span class="rk">{esc(d.get("severity", ""))}</span>'
                     f'<code>{esc(d.get("message", ""))[:600]}</code></li>')
    return '<ul class="results">' + "".join(items) + "</ul>"


def segment_html(v: SectionView, s: l4src.Segment, graphs: dict[str, str] | None = None) -> str:
    gh = f"{REPO}/blob/main/{v.l4.relative_to(ROOT)}#L{s.start}-L{s.end}"
    if s.note_only:
        return (f'<div class="seg note"><span class="note-label">ללא כלל</span>'
                f'<span class="note-text" lang="en" dir="ltr">{esc(s.note)}</span></div>')
    others = "".join(f'<a class="also" href="#{esc(k)}">מכסה גם {row_label(v.section, k)}</a>'
                     for k in s.keys[1:])
    # filled from the section's prose_json on the first switch to prose
    rend = f'<div class="view rendered" data-s="{s.start}" hidden></div>'
    notes = "".join(f'<div class="seg note"><span class="note-label">ללא כלל</span>'
                    f'<span class="note-text" lang="en" dir="ltr">{esc(n)}</span></div>' for n in l4src.lead_notes(s.lines))
    # an obligation (MUST / MAY / SHANT) as L4 draws it: `l4 state-graph`
    diagram = "".join(
        f'<details class="graph" dir="rtl"><summary>תרשים המצבים של החובה</summary>'
        f'<div class="graph-box" dir="ltr"><a href="{esc(graphs[n])}" target="_blank" rel="noopener" '
        f'title="פתיחה בגודל מלא"><img loading="lazy" src="{esc(graphs[n])}" '
        f'alt="{esc(n)}: state diagram"></a></div></details>'
        for n in dict.fromkeys(declared(s)) if graphs and n in graphs)
    return (f'{notes}<div class="seg" dir="ltr">'
            f'<div class="view code-view">{l4src.numbered_html(l4src.for_reading(s.lines, s.start))}</div>'
            f'{rend}{diagram}{results_html(s)}'
            f'<div class="seg-foot">{others}<a class="gh" href="{gh}">קוד מקור, שורות {s.start}–{s.end}</a></div>'
            f'</div>')


# (document, row key) -> findings. Keyed by DOCUMENT as well as row: every
# circular has an `art_1` and a `preamble`, so a key alone names a row in
# 210 documents at once.
FINDINGS_BY_KEY: dict[tuple[str, str], list[dict]] = {}
# every finding, and those that live on a card of מקורות סותרים (id -> card)
REGISTER: list[dict] = []
HOMES: dict[str, str] = {}


def row_findings(v, r) -> list[dict]:
    """A row's findings, by its key or any alias (a clause's number and its
    first paragraph are one row, citable either way)."""
    out = []
    for k in (r.key, *r.aliases):
        for f in FINDINGS_BY_KEY.get((v.doc, k), []):
            if f not in out:
                out.append(f)
    return out


def finding_doc(f: dict) -> str:
    """The corpus document a finding is about, from the L4 file it names:
    l4/<doc>/<section>.l4 for a sectioned document, l4/<doc>.l4 for a whole one.
    Evidence that cannot sit in the module itself — it imports an instrument
    the module's import chain must not reach (F-hh-2009-c, MMS-686) — sits in
    the module's tests file, l4/tests/<module>-tests.l4, and the finding is
    the module's document's."""
    l4 = Path(f["l4"])
    if l4.parent == Path("l4/tests") and l4.name.endswith("-tests.l4"):
        module = ROOT / "l4" / "modules" / l4.name.replace("-tests.l4", ".l4")
        l4 = module.resolve().relative_to(ROOT)
    rel_ = l4.relative_to("l4")
    parent = rel_.parent.as_posix() + ".xml"
    # the department's home page is "…gov.il.xml" and its other pages sit in
    # "…gov.il/": a parent that exists is the document only if it is sectioned
    if (akn.CORPUS / parent).exists() and not akn.is_whole(parent):
        return parent
    return rel_.with_suffix(".xml").as_posix()


def section_block(v: SectionView, here: str, headless: bool = False) -> str:
    """One section of the document page: its head, its findings, and the
    text beside the L4, row by row."""
    sec = v.section
    corpus = f"{CORPUS_SITE}/{v.dir}.html#{sec.eid}"
    found = []
    for r in sec.rows:
        for f in row_findings(v, r):
            if f not in found:
                found.append(f)
    links = [f'<a href="{corpus}">בקורפוס ↗</a>']
    if (v.doc, v.section.num) == SALARY and CALCULATOR:
        links.append(f'<a href="{rel("calculator.html", here)}">מחשבון שכר</a>')
    if v.l4:
        links += [f'<a href="{REPO}/blob/main/{v.l4.relative_to(ROOT)}">קוד מקור ↗</a>',
                  f'<a href="{rel(v.render_href, here)}">כפרוזה</a>']
    stats = ""
    if v.src is not None:
        t = tally(v)
        checks = sum(len(s.results) for s in v.src.segments)
        stats = (f'<div class="stats">'
                 f'<span class="{"okay" if v.ok else "notok"}">{"✓ הבדיקות תקינות" if v.ok else "✗ l4 מדווח על שגיאות"}</span>'
                 + (f'<span class="notok"><b>{t["missing"]}</b> לא צוטטו</span>' if t["missing"] else "")
                 + f'<span><b>{checks}</b> בדיקות</span>'
                 + (f'<span class="fcount"><b>{len(found)}</b> {"ממצאים" if len(found) != 1 else "ממצא"}</span>' if found else "")
                 + '</div>')
    head = (f'<header class="tsec-head">'
            + ("" if headless else
               f'<div class="title-row"><h2 lang="he" dir="rtl"><a class="anchor" href="#{esc(sec.eid)}">'
               f'<span class="secnum" dir="{num_dir(sec.num)}">{esc(sec_ref(sec))}</span>{esc(sec.heading)}</a></h2>'
               f'<div class="tsec-meta">{badge(v.status)}<span class="links">{"".join(links)}</span></div></div>')
            + f'{stats}</header>')
    if found:
        head += ('<div class="sec-findings"><h3>ממצאים בחלק זה</h3><ul>'
                 + "".join(f'<li><a href="{rel("findings.html", here)}#{esc(f["id"])}"><span class="kind-tag {f["kind"]}">'
                           f'{esc(KINDS[f["kind"]][0])}</span>{prose(f["title"])}</a></li>' for f in found)
                 + "</ul></div>")
    head += (statutes_box(v.doc, None, here) if v.whole else
             statutes_box(v.doc, sec.num, here, box_id=f"statutes-{sec.eid}"))

    def flags(r):
        fs = row_findings(v, r)
        return "".join(f'<a class="flag {f["kind"]}" href="{rel("findings.html", here)}#{esc(f["id"])}" '
                       f'title="{esc(f["title"])}">{esc(f["id"])}</a>' for f in fs)

    if v.src is None:
        rows = "".join(
            f'<div class="row {r.kind} d{min(r.depth, 6)}" id="{esc(r.key)}">'
            f'<div class="txt" lang="he" dir="rtl">{text_cell(r)}</div></div>'
            for r in sec.rows)
        return (f'<section class="tsec todo" id="{esc(sec.eid)}">{head}'
                f'<div class="grid only-text">{rows}</div></section>')

    prose_at = f' data-prose="{esc(rel(v.prose_href, here))}"' if rendered_for(v) else ""
    graphs = {n: rel(p, here) for n, p in state_graphs(v).items()}
    out = []
    for r in sec.rows:
        segs = v.anchors.get(r.key, [])
        cls = ["row", r.kind, f"d{min(r.depth, 6)}"]
        if r.kind == "text" and r.key not in v.covered:
            cls.append("gap")
        elif r.key in v.covered and not segs:
            cls.append("covered")
        if segs and all(s.note_only for s in segs):
            cls.append("noted")
        code = "".join(segment_html(v, s, graphs) for s in segs)
        if "covered" in cls and v.covered_by.get(r.key, r.key) != r.key:
            # covered by a segment that sits beside an earlier row (a note
            # on the whole preamble, a rule citing a list's head): say so
            # here, or the row reads as if nothing covered it
            at = v.covered_by[r.key]
            link = f'<a href="#{esc(at)}">{row_label(v.section, at)}</a>'
            code = (f'<div class="seg cont note"><span class="note-label">ללא כלל</span>'
                    f'<span class="cont-text">כלול בהערה שליד {link}</span></div>'
                    if v.kind_of.get(r.key) == "note" else
                    f'<div class="seg cont"><span class="cont-text">מקודד בכלל שליד {link}</span></div>')
        if "gap" in cls:
            code = '<div class="seg missing">לא קודד — אין כלל שמצטט פסקה זו.</div>'
        alias = "".join(f'<span id="{esc(a)}"></span>' for a in r.aliases)
        fl = flags(r)
        out.append(f'<div class="{" ".join(cls)}" id="{esc(r.key)}">'
                   f'<div class="txt" lang="he" dir="rtl">{alias}{text_cell(r)}'
                   f'{f"<div class=flags dir=ltr>{fl}</div>" if fl else ""}</div>'
                   f'<div class="l4">{code}</div></div>')
    unplaced = ""
    if v.unplaced:
        unplaced = ('<div class="banner bad">הקוד מצטט מפתחות שאינם בחלק זה: ' +
                    ", ".join(esc(" ".join(s.keys)) for s in v.unplaced) + "</div>")
    appendix = ""
    if v.appendix:
        appendix = ('<details class="appendix"><summary>הגדרות משותפות, דוגמאות ובדיקות '
                    f'<span class="meta">({len(v.appendix)})</span></summary>'
                    + "".join(segment_html(v, s, graphs) for s in v.appendix) + '</details>')
    return (f'<section class="tsec" id="{esc(sec.eid)}"{prose_at}>{head}{unplaced}'
            f'<div class="grid">{"".join(out)}</div>{appendix}</section>')


# the per-instrument record of the protective statutes (tools/statute_record.py,
# MMS-601), read off the L4 and `make l4`'s results by build(): every
# document of the manifest, and every section of a sectioned one, against
# every statute the statutes' root registers
STATUTES: dict = {}
STATUTE_CELLS: dict[tuple[str, str | None], dict] = {}


def doc_href(doc: str, sec: str | None) -> str | None:
    """The site's page of a document, or of a section of a sectioned one;
    None for a document the site has no page for."""
    if doc not in NAV_VIEWS:
        return None
    if sec is None:
        return f"{doc.removesuffix('.xml')}.html"
    v = next((v for v in NAV_VIEWS[doc] if v.section.num == sec), None)
    return v.href if v is not None else None


def statutes_box(doc: str, sec: str | None, here: str, box_id: str = "statutes") -> str:
    """An instrument's row of the record, on its page."""
    cells = STATUTE_CELLS.get((doc, sec))
    if cells is None:
        return ""
    sectioned = sec is None and not akn.is_whole(doc)

    def sec_href(num: str) -> str | None:
        h = doc_href(doc, num)
        return rel(h, here) if h else None
    return statute_record.box_html(STATUTES, cells, esc=esc, link=lambda t: rel(t, here),
                                   sec_href=sec_href if sectioned else None,
                                   what="הסעיף" if sec else "המסמך", box_id=box_id)


# a module's tests file (l4/tests/<module>-tests.l4) by the module's file:
# the page of the document or section that file encodes shows it below its
# code, as a root's page does (MMS-607). Filled by build().
TESTED: dict[str, str] = {}


def module_tests(v: SectionView) -> str:
    """The tests file of the module `v` encodes, below its code, or ""."""
    name = TESTED.get(str(v.l4.relative_to(ROOT))) if v.l4 else None
    if name is None:
        return ""
    return roots.tests_block(name, v.section.heading if v.whole else sec_ref(v.section),
                             esc=esc, code_html=l4src.numbered_html)


def roots_page(module: str) -> str:
    return next(here for m, here, *_ in roots.ROOTS if m == module)


def tests_homes(by_file: dict[str, SectionView]) -> dict[Path, str | None]:
    """Where each tests file is shown: its root's page, the page of the
    document or section its module encodes, or None — a file that names no
    module, or whose module has no page, which the checks page shows in
    full."""
    real = {n: str(f.relative_to(ROOT)) for n, f in modules.wanted()[0].items()}
    root_pages = {m: here for m, here, *_ in roots.ROOTS}
    out: dict[Path, str | None] = {}
    for t in roots.tests_files():
        name = roots.tested_module(t)
        v = by_file.get(real.get(name, ""))
        out[t] = (root_pages[name] + f"#tests-{name}" if name in root_pages else
                  f"{v.page}#tests-{name}" if v is not None and TESTED.get(real[name]) == name else None)
    return out


def redirect_page(here: str, target: str, title: str) -> str:
    """A page that moved: sends the reader (and a search engine) on."""
    to = rel(target, here)
    return (f'<!doctype html><html lang="he" dir="rtl"><head><meta charset="utf-8"><title>{esc(title)}</title>'
            f'<meta http-equiv="refresh" content="0; url={esc(to)}"><link rel="canonical" href="{esc(to)}">'
            f'</head><body><p>הדף עבר אל <a href="{esc(to)}">{esc(title)}</a>.</p></body></html>')


# `l4 render` (since l4-ide 2818cc2) numbers its section headings by their
# order in the file, "§ 3  1 עובדים קיימים" for the text's section 1. That
# count is not the corpus's numbering, and beside it a reader takes it for
# one, so the site drops it and keeps the heading the L4 wrote.
RENDER_ORDINAL = re.compile(r'(<h[1-6]\b[^>]*\bclass="section"[^>]*>)\s*§\s*\d+\s+')


def without_render_ordinals(markup: str) -> str:
    return RENDER_ORDINAL.sub(r"\1", markup)


def render_page(v: SectionView) -> str:
    """L4's own rendering, framed by the site so it is navigable."""
    m = re.search(r"<body[^>]*>(.*)</body>", v.render, re.S)
    inner = without_render_ordinals(m.group(1) if m else v.render)
    here = v.render_href
    body = (f'<header class="sec-head"><nav class="crumbs"><a href="{rel(v.href, here)}">→ {"" if v.whole else esc(sec_ref(v.section)) + " "}זה לצד זה</a></nav>'
            f'<div class="title-row"><h1 lang="he" dir="rtl">'
            + ("" if v.whole else f'<span class="secnum" dir="{num_dir(v.section.num)}">{esc(sec_ref(v.section))}</span>')
            + f'{esc(v.section.heading)}</h1></div>'
            f'<p class="lede">{"המסמך" if v.whole else "החלק"} כולו, כפי ש־<code>l4 render</code> כותב את הכללים בחזרה כפרוזה (באנגלית).</p></header>'
            f'<div class="render-frame" dir="ltr" lang="en">{inner or "<p>l4 render לא הפיק דבר לקובץ זה.</p>"}</div>')
    return page(here, f"{sec_ref(v.section)} — פרוזה (l4 render)", body, tab="docs")


def progress(vs: list[SectionView], always: bool = False) -> str:
    """How much of the text is encoded, and only while something is not:
    "77% carry a rule, 23% carry none" told the reader nothing they could use
    (the client, 2026-10-11), and a finished collection's "N of N" line says
    all there is. A paragraph read and given a note counts as encoded."""
    t = {"done": 0, "missing": 0, "todo": 0}
    for v in vs:
        if v.src is None:
            t["todo"] += len(v.text_rows)
        else:
            for k, n in tally(v).items():
                t["done" if k in ("rule", "note") else k] += n
    if not (t["missing"] or t["todo"]):
        # the index's cards all carry a bar (MMS-553): a finished one is full
        return '<span class="pbar"><i class="rule" style="width:100%"></i></span>' if always else ""
    total = max(sum(t.values()), 1)
    names = {"done": "מקודדות", "missing": "לא צוטטו", "todo": "טרם קודדו"}
    cls = {"done": "rule", "missing": "missing", "todo": "todo"}   # the sheet's colours
    legend = " · ".join(f'<span><i class="sw {cls[k]}"></i>{round(t[k] * 100 / total)}% {names[k]}</span>'
                        for k in ("done", "missing", "todo") if t[k])
    return ('<span class="pbar">' + "".join(
        f'<i class="{cls[k]}" style="width:{t[k] * 100 / total:.3f}%"></i>' for k in ("done", "missing") if t[k])
        + f'</span><span class="plegend">פסקאות: {legend}</span>')


SWITCH = ('<div class="switch" role="group" aria-label="איך להציג את ה-L4">'
          '<button type="button" data-view="code-view" aria-pressed="true">קוד</button>'
          '<button type="button" data-view="rendered" aria-pressed="false">פרוזה (אנגלית)</button></div>')


def old_anchor_script(doc: str, views: list[SectionView]) -> str:
    """The takanon was one page, and a link into it carried the clause as a
    fragment, which never reaches the server: this sends such a link on to
    the chapter that now holds the clause. Every id on the old page began
    with its chapter's eId (build() checks that it still does)."""
    here = f"{doc.removesuffix('.xml')}.html"
    to = {vs[0].section.chapter_eid: rel(vs[0].page, here) for vs in chapters_of(views)}
    return ('<script>(function(){var h=location.hash,id;if(!h)return;'
            'try{id=decodeURIComponent(h.slice(1))}catch(e){return}'
            f'var to={json.dumps(to, ensure_ascii=False)};'
            'for(var c in to)if(id===c||id.indexOf(c+"__")===0||id.indexOf(c+"/")===0){location.replace(to[c]+h);return}'
            '})();</script>')


def contents_page(doc: str, views: list[SectionView]) -> str:
    """A sectioned document's contents — the takanon's chapters and sections,
    the base agreement's parts and articles — each linking to the chapter
    page that holds it (one page per chapter; the whole takanon on one page
    was 18MB). Its address is the one the whole document had, and a link
    into the old page by fragment is sent on to its chapter."""
    here = f"{doc.removesuffix('.xml')}.html"
    coll = doc.split("/")[0]
    takanon = coll == "takanon"
    chapters = chapters_of(views)
    done = sum(v.status == "done" for v in views)
    part = sum(v.status == "partial" for v in views)
    nfind = len({f["id"] for v in views for r in v.section.rows for f in row_findings(v, r)})
    parts = []
    for vs in chapters:
        s0 = vs[0].section
        lis = "".join(
            f'<li class="{v.status}"><a href="{rel(v.href, here)}">{dot(v.status)}'
            f'<span class="secnum" dir="{num_dir(v.section.num)}">{esc(v.section.num)}</span>'
            f'<span class="sh" lang="he">{esc(v.section.heading)}</span></a></li>' for v in vs)
        parts.append(f'<section class="chapter" dir="rtl"><div class="chapter-head"><h2>'
                     f'<a href="{rel(vs[0].page, here)}" lang="he" dir="rtl">{esc(chapter_name(s0))}</a></h2>'
                     f'<span class="ccount">{sum(v.status == "done" for v in vs)} מתוך {len(vs)} מקודדים</span></div>'
                     f'<ul class="secs">{lis}</ul></section>')
    crumb = ("" if takanon else
             f'<span>/</span><a href="{rel(coll_hub(coll), here)}">{esc(coll_name(coll))}</a>')
    meta = doc_meta(doc)
    articles = [v for v in views if not akn.unnumbered(v.section.num)]
    annexes = [v for v in views if v.section.num.startswith(akn.ANNEX)]
    letters = [v for v in views if v.section.num.startswith(akn.LETTER)]
    lede = (f'תקנון שירות עובדי הוראה של משרד החינוך, במלואו, '
            f'כפי שהקורפוס מפרסם אותו: {len(views)} סעיפים ב־{len(chapters)} פרקים, עמוד לכל פרק.'
            if takanon else
            f'ההסכם הקיבוצי מיום {esc(".".join(str(int(x)) for x in reversed((meta.get("date") or "").split("-"))) if meta.get("date") else "")}, '
            f'כפי שהקורפוס מפרסם אותו: המבוא, '
            f'{len(articles)} סעיפים ב־{len({v.section.chapter_eid for v in articles})} פרקים, והחתימה'
            + (f' ו־{len(annexes)} נספחים' if annexes else "")
            + (f' ו־{len(letters)} מכתבים נלווים' if letters else "") + '; עמוד לכל פרק.')
    head = (f'<header class="sec-head doc-head"><nav class="crumbs"><a href="{rel("index.html", here)}">מסמכים</a>{crumb}</nav>'
            f'<div class="title-row"><h1 lang="he" dir="rtl">{esc(akn.title(doc))}</h1></div>'
            f'<p class="lede">{lede} כל פסקה '
            f'של הטקסט (מימין) עומדת ליד ה-L4 שמקודד אותה (משמאל).</p>'
            f'<div class="stats"><span><b>{done}</b> מתוך {len(views)} סעיפים מקודדים</span>'
            + (f'<span><b>{part}</b> בחלקם</span>' if part else "")
            + f'<a class="fcount" href="{rel("findings.html", here)}"><b>{nfind}</b> ממצאים</a>'
            f'<a href="{CORPUS_SITE}/{doc.removesuffix(".xml")}.html">בקורפוס ↗</a></div>'
            f'{progress(views)}</header>')
    head += statutes_box(doc, None, here)
    pages = [v for d in NAV_VIEWS if is_site_page(d) for v in NAV_VIEWS[d]] if takanon else []
    if pages:
        lis = "".join(
            f'<li class="{v.status}"><a href="{rel(v.href, here)}">{dot(v.status)}'
            f'<span class="sh" lang="he">{esc(v.section.heading)}</span></a></li>' for v in pages)
        parts.append(f'<section class="chapter" id="{SITE_ANCHOR}" dir="rtl"><div class="chapter-head"><h2>{esc(SITE_GROUP)}</h2>'
                     f'<span class="ccount">{sum(v.status == "done" for v in pages)} מתוך {len(pages)} מקודדים</span></div>'
                     f'<p class="meta">{SITE_GROUP_LEDE}</p><ul class="secs docs">{lis}</ul></section>')
    return page(here, f"{akn.title(doc)} — {TITLE}", old_anchor_script(doc, views) + head + "".join(parts),
                tab="docs", desc=f"{akn.title(doc)}: הפרקים והסעיפים, כל פסקה ליד קידוד ה-L4 שלה")


def chapter_page(doc: str, chapters: list[list[SectionView]], i: int) -> str:
    """One chapter of the takanon: each of its sections with its text beside
    its L4. The sidebar lists its sections (and follows the one in view)."""
    vs = chapters[i]
    s0 = vs[0].section
    here = vs[0].page
    contents = f"{doc.removesuffix('.xml')}.html"
    n_done = sum(v.status == "done" for v in vs)
    nfind = len({f["id"] for v in vs for r in v.section.rows for f in row_findings(v, r)})
    name = chapter_name(s0)
    coll = doc.split("/")[0]
    crumb = ("" if coll == "takanon" else
             f'<a href="{rel(coll_hub(coll), here)}">{esc(coll_name(coll))}</a><span>/</span>')
    # a chapter the corpus holds as one block is its own section; it takes
    # the chapter's anchor itself
    chap_id = "" if any(v.section.eid == s0.chapter_eid for v in vs) else f' id="{esc(s0.chapter_eid)}"'
    head = (f'<header class="sec-head doc-head"{chap_id}><nav class="crumbs"><a href="{rel("index.html", here)}">מסמכים</a><span>/</span>'
            f'{crumb}<a href="{rel(contents, here)}" lang="he" dir="rtl">{esc(akn.title(doc))}</a></nav>'
            f'<div class="title-row"><h1 lang="he" dir="rtl">{esc(name)}</h1></div>'
            f'<div class="stats"><span><b>{n_done}</b> מתוך {len(vs)} סעיפים מקודדים</span>'
            + (f'<a class="fcount" href="{rel("findings.html", here)}"><b>{nfind}</b> ממצאים</a>' if nfind else "")
            + f'<a href="{CORPUS_SITE}/{doc.removesuffix(".xml")}.html#{esc(s0.chapter_eid)}">בקורפוס ↗</a></div>'
            f'{progress(vs)}</header>')
    toolbar = (f'<div class="doc-toolbar"><span class="tb-label">הצגת ה-L4:</span>{SWITCH}'
               f'<span class="tb-where" aria-live="polite"></span>'
               f'<span class="tb-cols"><span>L4</span><span>טקסט</span></span></div>')
    blocks = "".join(section_block(v, here) + module_tests(v) for v in vs)

    def step(j: int, cls: str, label: str) -> str:
        if not 0 <= j < len(chapters):
            return ""
        c = chapters[j][0]
        return (f'<a class="{cls}" href="{rel(c.page, here)}"><small>{label}</small>'
                f'<span lang="he" dir="rtl">{esc(chapter_name(c.section))}</span></a>')
    prevnext = f'<nav class="prevnext">{step(i - 1, "prev", "הפרק הקודם")}{step(i + 1, "next", "הפרק הבא")}</nav>'
    body = head + f'<div class="doc-main">{toolbar}{blocks}</div>' + prevnext
    return page(here, f"{name} — {akn.title(doc)} — {TITLE}", body, tab="docs", wide=True,
                desc=f"{akn.title(doc)}, {name}: כל פסקה ליד קידוד ה-L4 שלה")


def doc_meta(doc: str) -> dict:
    for d in MANIFEST_DOCS:
        if d["path"] == doc:
            return d
    return {"path": doc, "title": akn.title(doc), "date": None, "collection": doc.split("/")[0]}


def coll_name(coll: str) -> str:
    return dict(COLLECTIONS).get(coll, coll)


def single_page(doc: str, v: SectionView) -> str:
    """A document that is one section — a circular — on a page of its own,
    at the corpus's own path."""
    here = v.page
    meta = doc_meta(doc)
    coll = doc.split("/")[0]
    corpus = f"{CORPUS_SITE}/{v.dir}.html"
    links = [f'<a href="{corpus}">בקורפוס ↗</a>']
    if v.l4:
        links += [f'<a href="{REPO}/blob/main/{v.l4.relative_to(ROOT)}">קוד מקור ↗</a>',
                  f'<a href="{rel(v.render_href, here)}">המסמך כולו כפרוזה</a>']
    switch = SWITCH
    site = is_site_page(doc)
    group = (f'<span>/</span><a href="{rel(coll_hub(coll), here)}#{SITE_ANCHOR}">{esc(SITE_GROUP)}</a>'
             if site else "")
    head = (f'<header class="sec-head"><nav class="crumbs"><a href="{rel("index.html", here)}">מסמכים</a><span>/</span>'
            f'<a href="{rel(coll_hub(coll), here)}">{esc(coll_name(coll))}</a>{group}</nav>'
            f'<div class="title-row"><h1 lang="he" dir="rtl">{esc(v.section.heading)}</h1>{badge(v.status)}</div>'
            + (f'<p class="lede">{SITE_LEDE}</p>' if site else "")
            + f'<p class="meta"><span class="docid" dir="ltr">{esc(v.section.num)}</span>'
            + (f' · {"צולם ב־" if site else ""}{esc(meta["date"])}' if meta.get("date") else "") + '</p>'
            f'<div class="links">{"".join(links)}</div></header>')
    toolbar = (f'<div class="doc-toolbar"><span class="tb-label">הצגת ה-L4:</span>{switch}'
               f'<span class="tb-where"></span><span class="tb-cols"></span></div>')
    body = head + toolbar + section_block(v, here, headless=True) + module_tests(v)
    return page(here, f"{v.section.heading} — {TITLE}", body, tab="docs", wide=True,
                desc=f"{v.section.heading}: נוסח המסמך ליד קידוד ה-L4 שלו")


SITE_LEDE = ("דף מאתר תחום תנאי שירות עובדי הוראה במשרד החינוך, כפי שהקורפוס צילם אותו. "
             "הוא אינו חלק מהתקנון ואינו מחייב: תשובות, ניווט ופרטי קשר.")
SITE_GROUP_LEDE = ("דפים מאתר תחום תנאי שירות עובדי הוראה במשרד החינוך, כפי שהקורפוס צילם אותם. "
                   "הם אינם חלק מהתקנון ואינם מחייבים: תשובות, ניווט ופרטי קשר.")


def doc_status(vs: list[SectionView]) -> str:
    """A document's state from its sections': done when every one is."""
    if all(v.status == "done" for v in vs):
        return "done"
    return "partial" if any(v.src is not None for v in vs) else "todo"


def collection_page(coll: str, views: list[SectionView]) -> str:
    """Every document of a collection, by year, newest first — or, for the
    agreements, by family. A sectioned document is one entry, to its
    contents."""
    here = f"{coll}.html"
    by_doc: dict[str, list[SectionView]] = {}
    for v in views:
        by_doc.setdefault(v.doc, []).append(v)
    by_year: dict[str, list[str]] = {}
    for d in by_doc:
        by_year.setdefault(doc_group(d) if by_folder(coll) else school_year(d), []).append(d)
    done = sum(doc_status(vs) == "done" for vs in by_doc.values())
    parts = [f'<header class="sec-head"><nav class="crumbs"><a href="index.html">מסמכים</a></nav>'
             f'<div class="title-row"><h1>{esc(coll_name(coll))}</h1></div>'
             f'<div class="stats"><span><b>{done}</b> מתוך {len(by_doc)} מסמכים מקודדים</span>'
             f'<a href="{CORPUS_SITE}/">בקורפוס ↗</a>'
             + (f'<a href="{rel(roots.page_for(coll), here)}">שורש האוסף</a>' if roots.page_for(coll) else '')
             + f'</div>{progress(views)}</header>']

    def entry(d: str) -> str:
        vs = by_doc[d]
        st = doc_status(vs)
        href = vs[0].href if akn.is_whole(d) else f"{d.removesuffix('.xml')}.html"
        num = doc_num(d) if by_folder(coll) else Path(d).stem.split("_", 1)[-1]
        title = vs[0].section.heading if akn.is_whole(d) else akn.title(d)
        return (f'<li class="{st}"><a href="{rel(href, here)}">{dot(st)}'
                f'<span class="secnum" dir="ltr">{esc(num)}</span>'
                f'<span class="sh" lang="he">{esc(title)}</span></a></li>')
    for year in group_order(coll if by_folder(coll) else "", by_year):
        ds = sorted(by_year[year])
        lis = "".join(entry(d) for d in ds)
        ndone = sum(doc_status(by_doc[d]) == "done" for d in ds)
        hdir = "rtl" if by_folder(coll) else "ltr"
        parts.append(f'<section class="chapter" id="y-{esc(year)}" dir="rtl"><div class="chapter-head"><h2 dir="{hdir}">{esc(group_label(coll, year))}</h2>'
                     f'<span class="ccount" dir="ltr">{ndone} מתוך {len(ds)} מקודדים</span></div>'
                     + (f'<p class="meta"><a href="{rel(fp, here)}">שורש המשפחה</a></p>'
                        if coll == "agreements" and (fp := roots.family_page(year)) else '')
                     + f'<ul class="secs docs">{lis}</ul></section>')
    return page(here, f"{coll_name(coll)} — {TITLE}", "".join(parts), tab="docs")
