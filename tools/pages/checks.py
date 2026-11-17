"""index.json, the checks page (diagnostics) with every tests file, and the
coverage page.
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
from pages.documents import *  # noqa: E402,F401,F403
from pages.home import *  # noqa: E402,F401,F403
from pages.findings import *  # noqa: E402,F401,F403
from pages.sources import *  # noqa: E402,F401,F403

def index_json(flat: list[SectionView]) -> str:
    """One row per L4 segment (MMS-414): the file, the lines, the names it
    declares, its text, and the corpus addresses it encodes."""
    rows = []
    for v in flat:
        if v.src is None:
            continue
        for s in v.src.segments:
            rows.append({
                "file": str(v.l4.relative_to(ROOT)), "line": s.start, "end": s.end,
                "names": declared(s),
                "kind": "note" if s.note_only else ("rule" if s.keys else "support"),
                "note": s.note if s.note_only else None,
                "addresses": [address(v.doc, k) for k in s.keys],
                "text": "\n".join(s.lines),
            })
    return json.dumps({"source": REPO, "rules": rows}, ensure_ascii=False, indent=1)


def tests_index(homes: dict[Path, str | None], here: str) -> str:
    """Every tests file and the page that shows it (MMS-607). A file no
    module page shows — it names no module, or its module has no page — is
    shown here in full, so none is out of a reader's reach."""
    rows, orphans = [], []
    for t, home in homes.items():
        name = roots.tested_module(t)
        asserts = [r for r in roots.results(name) if r.get("kind") == "assertion"]
        held = sum(r.get("value") is True for r in asserts)
        cls = "okay" if held == len(asserts) and roots.results(name) else "notok"
        where = (f'<a href="{rel(home, here)}">{esc(home.split("#")[0])}</a>' if home else
                 f'<a href="#tests-{esc(name)}">בעמוד זה, למטה</a>')
        rows.append(f'<tr><td><code dir="ltr">{esc(str(t.relative_to(ROOT)))}</code></td><td>{where}</td>'
                    f'<td class="{cls}">{held} / {len(asserts)}</td></tr>')
        if home is None:
            orphans.append(roots.tests_block(
                name, name, esc=esc, code_html=l4src.numbered_html,
                where=" לקובץ הזה אין עמוד מודול באתר, ולכן הוא מוצג כאן."))
    return ('<h2 id="tests-files">קובצי הבדיקות</h2><p class="lede">הבדיקות של מודול יושבות בקובץ משלהן, '
            '<code dir="ltr">l4/tests/&lt;module&gt;-tests.l4</code>, ומוצגות מתחת לקוד שלו: '
            'בעמוד השורש, או בעמוד המסמך שהמודול מקודד. קובץ שאין לו עמוד כזה מוצג כאן.</p>'
            '<div class="scroll-x"><table class="diag"><thead><tr><th>קובץ</th><th>מוצג ב־</th>'
            '<th>#ASSERT מתקיימים</th></tr></thead><tbody>' + "".join(rows) + '</tbody></table></div>'
            + "".join(orphans))


def diagnostics_page(views: list[SectionView], homes: dict[Path, str | None]) -> str:
    rows = []
    for v in views:
        if v.src is None:
            continue
        diags = v.problems
        asserts = [r for r in v.run.get("results", []) if r.get("kind") == "assertion"]
        failed = [r for r in asserts if str(r.get("value")).strip().lower() != "true"]
        bad = len(diags) + len(failed) + len(v.unplaced)
        cls = "okay" if v.ok and not v.unplaced else "notok"
        detail = "".join(f'<li><code>{esc(d.get("severity", ""))} {esc(str(d.get("range", "")))} '
                         f'{esc(d.get("message", ""))}</code></li>' for d in diags)
        detail += "".join(f'<li>#ASSERT נכשל בשורה {line_of(r.get("range"))}</li>' for r in failed)
        detail += "".join(f'<li>הקוד מצטט מפתחות שאינם בחלק: <code>{esc(" ".join(s.keys))}</code></li>'
                          for s in v.unplaced)
        gaps = sum(1 for r in v.text_rows if r.key not in v.covered)
        rows.append(f'<tr><td><a href="{v.href}">{esc(sec_ref(v.section))}</a></td>'
                    f'<td><code>{esc(str(v.l4.relative_to(ROOT)))}</code></td>'
                    f'<td class="{cls}">{"תקין" if cls == "okay" else "שגיאה"}</td>'
                    f'<td>{len(asserts)}</td><td>{gaps}</td><td>{bad}</td></tr>'
                    + (f'<tr class="detail"><td colspan="6"><ul>{detail}</ul></td></tr>' if detail else ""))
    body = ('<h1>בדיקות</h1><p class="lede">מה שמהדר ה-L4 (<code>l4 run</code>) אומר על כל '
            'קובץ: שגיאות טיפוס ותחביר, וכל <code>#ASSERT</code> שנכשל. "פסקאות שלא צוטטו" '
            'סופר את פסקאות הטקסט שאף קטע קוד אינו מצטט. באתר תקין שתי העמודות האחרונות '
            'הן אפס.</p>'
            '<div class="scroll-x"><table class="diag"><thead><tr><th>חלק</th><th>קובץ</th><th>מצב</th><th>#ASSERT</th>'
            '<th>פסקאות שלא צוטטו</th><th>בעיות</th></tr></thead><tbody>'
            + "".join(rows) + "</tbody></table></div>"
            + tests_index(homes, "diagnostics.html"))
    return page("diagnostics.html", f"בדיקות — {TITLE}", body, tab="diagnostics")


# the corpus's own words for its "part" state (its coverage page's legend)
PARTIAL_LABEL = "קריאה או סריקה חלקית"


def held_in_part(manifest: list[dict]) -> set[str]:
    """The documents the corpus's coverage page draws as held in part.
    Each document's state and row are the corpus's own verdict, recorded by
    tools/sync_corpus.py; this repeats only its drawing rule, that copies of
    one date in one row count once and the best-read copy stands for them,
    so a scan missing a page beside a complete copy is not drawn as a gap."""
    rank = {"full": 0, "part": 1, "none": 2}
    def instrument(d):
        return (d.get("row"), d["date"]) if d.get("row") and d.get("date") else (d["path"],)
    best: dict = {}
    for d in manifest:
        k = instrument(d)
        best[k] = min(best.get(k, 9), rank.get(d.get("state"), 0))
    return {d["path"] for d in manifest
            if d.get("state") == "part" and best[instrument(d)] == rank["part"]}


def coverage_page(all_views: dict[str, list[SectionView]]) -> str:
    """What of the corpus is encoded. The denominator is the corpus's own
    document list (corpus/manifest.json), so a collection nobody has started
    shows as a row of nothing rather than not at all."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))["documents"]
    flat = [v for vs in all_views.values() for v in vs]
    t = {"rule": 0, "note": 0, "missing": 0}
    for v in flat:
        if v.src is not None:
            for k, n in tally(v).items():
                t[k] += n
    untouched = sum(len(v.text_rows) for v in flat if v.src is None)
    paras = t["rule"] + t["note"] + t["missing"] + untouched
    done = sum(v.status == "done" for v in flat)
    part = sum(v.status == "partial" for v in flat)
    n_docs_done = sum(all(v.status == "done" for v in vs) for vs in all_views.values())
    head = (f'<h1>כיסוי</h1>'
            f'<p class="lede">כמה מהקורפוס מקודד ב-L4. המכנה הוא רשימת המסמכים של הקורפוס עצמו '
            f'— {len(manifest)} מסמכים — ולא רק מה שהתחיל. מסמך מתחלק לסעיפים וסעיף לפסקאות; פסקה היא '
            f'<span class="sw read"></span> נקראה — קוד ה־L4 מצטט אותה, בכלל או בהערה שאומרת למה אין בה כלל, '
            f'<span class="sw missing"></span> לא צוטטה — בסעיף מקודד אך אין קוד שמצטט אותה, או '
            f'<span class="sw todo"></span> טרם קודדה — בסעיף שטרם קודד. '
            f'<span class="sw gap"></span> קריאה או סריקה חלקית — כך מסמן אותו דף הכיסוי של הקורפוס: חסרים בו עמודים, ואין עותק שלם.</p>'
            f'<div class="kpis">'
            f'<div><b>{n_docs_done}</b> / {len(manifest)}<span>מסמכים מקודדים במלואם</span></div>'
            + (f'<div><b>{len(DOCUMENTS) - n_docs_done}</b><span>מסמכים בעבודה</span></div>'
               if len(DOCUMENTS) > n_docs_done else "")
            + f'<div><b>{done}</b> / {len(flat)}<span>חלקים מקודדים במלואם</span></div>'
            f'<div><b>{part}</b><span>חלקים מקודדים בחלקם</span></div>'
            f'<div><b>{t["rule"] + t["note"]}</b> / {paras}<span>פסקאות שנקראו</span></div>'
            f'</div>')
    parts = [head]
    partial = held_in_part(manifest)

    def counts(v: SectionView) -> dict[str, int]:
        """A section's paragraphs as the strip shows them."""
        c = {"read": 0, "missing": 0, "todo": 0}
        for r in v.text_rows:
            if v.src is None:
                c["todo"] += 1
            elif v.kind_of.get(r.key) in ("rule", "note"):
                c["read"] += 1
            else:
                c["missing"] += 1
        return c

    def segs_of(c: dict[str, int], doc: str) -> str:
        # a document the corpus holds only in part gets a yellow cap
        cap = '<i class="gap"></i>' if doc in partial else ""
        return cap + "".join(f'<i class="{k}" style="flex:{m}"></i>' for k, m in c.items() if m)

    def gap_tip(doc: str) -> str:
        return " · " + PARTIAL_LABEL if doc in partial else ""

    def gap_class(doc: str) -> str:
        return " gap" if doc in partial else ""

    def cell(v: SectionView) -> str:
        n = max(len(v.text_rows), 1)
        name = v.section.num if not v.whole else Path(v.doc).stem
        # a paragraph is read or it is not: whether the L4 beside it is a
        # rule or a note saying why there is none is not coverage
        c = counts(v)
        if v.src is None:
            tip = f"{name} {v.section.heading}: טרם קודד ({len(v.text_rows)} פסקאות)"
            c = c if any(c.values()) else {"todo": 1}
        else:
            tip = f"{name} {v.section.heading}" + (f": {c['missing']} פסקאות לא צוטטו" if c["missing"] else "")
        doc = v.doc if v.whole else ""
        return (f'<a class="cell{gap_class(doc)}" href="{v.href}" '
                f'title="{esc(tip + gap_tip(doc))}" style="flex:{n}">{segs_of(c, doc)}</a>')

    def doc_cell(doc: str, vs: list[SectionView]) -> str:
        """A sectioned document as one cell: its paragraphs, read or not."""
        c = {"read": 0, "missing": 0, "todo": 0}
        for v in vs:
            for k, m in counts(v).items():
                c[k] += m
        n = max(sum(c.values()), 1)
        tip = (f"{Path(doc).stem} {akn.title(doc)}: {c['read']} מתוך {sum(c.values())} פסקאות נקראו"
               + gap_tip(doc))
        return (f'<a class="cell{gap_class(doc)}" href="{doc.removesuffix(".xml")}.html" '
                f'title="{esc(tip)}" style="flex:{n}">{segs_of(c, doc)}</a>')

    for doc, vs in all_views.items():
        # an agreement is one document among its collection's, not a section
        # of the page (the client, 2026-10-20): it is a cell in its family's
        # row below, and its own page has the chapter-by-chapter view
        if akn.is_whole(doc) or doc.startswith("agreements/"):
            continue
        parts.append(f'<h2 class="cov-doc"><a href="{doc.removesuffix(".xml")}.html">{he(akn.title(doc))}</a></h2>'
                     '<p class="meta">רצועה לכל פרק, תא לכל סעיף, ורוחבו כמספר פסקאות הסעיף. '
                     'רחפו לספירה; לחצו כדי לפתוח.</p>')
        chapters: dict[str, list[SectionView]] = {}
        for v in vs:
            chapters.setdefault(v.section.chapter_eid, []).append(v)
        rows = []
        for cvs in chapters.values():
            s0 = cvs[0].section
            rows.append(f'<div class="strip-row"><div class="strip-name">{he(chapter_name(s0))}</div>'
                        f'<div class="strip">{"".join(cell(v) for v in cvs)}</div></div>')
        parts.append(f'<div class="strips">{"".join(rows)}</div>')
        coll = doc.split("/")[0]
        pages = [v for d, pvs in all_views.items() if d.split("/")[0] == coll and is_site_page(d) for v in pvs]
        if pages:
            parts.append(f'<h3 class="cov-group" id="{SITE_ANCHOR}">{esc(SITE_GROUP)}</h3>'
                         '<p class="meta">אינם חלק מהתקנון: תא לכל דף, ורוחבו כמספר פסקאות הדף.</p>'
                         f'<div class="strips"><div class="strip-row"><div class="strip-name">{esc(SITE_GROUP)}</div>'
                         f'<div class="strip">{"".join(cell(v) for v in pages)}</div></div></div>')
    for coll in WORK_COLLECTIONS[1:]:
        cvs_all = [v for d, vs in all_views.items() if d.startswith(coll + "/") and akn.is_whole(d) for v in vs]
        if not cvs_all:
            continue
        family = by_folder(coll)
        row_of = {"agreements": "משפחת הסכמים", "tables": "קבוצת טבלאות"}.get(coll, "שנה")
        parts.append(f'<h2><a href="{coll}.html">{esc(coll_name(coll))}</a></h2>'
                     f'<p class="meta">רצועה לכל {row_of}, תא לכל מסמך, ורוחבו כמספר פסקאות המסמך.</p>')
        by_year: dict[str, list] = {}
        for v in cvs_all:
            by_year.setdefault(doc_group(v.doc) if family else school_year(v.doc), []).append((v.doc, cell(v)))
        # a sectioned document is one cell here: left out, an encoded agreement
        # made its family's row read as though none of it were encoded (the
        # client, 2026-10-20)
        for d, vs in all_views.items():
            if d.startswith(coll + "/") and not akn.is_whole(d):
                by_year.setdefault(doc_group(d) if family else school_year(d), []).append((d, doc_cell(d, vs)))
        keys = group_order(coll, by_year) if family else sorted(by_year)
        rows = [f'<div class="strip-row"><div class="strip-name">{esc(group_label(coll, y))}</div>'
                f'<div class="strip">{"".join(c for _, c in sorted(by_year[y]))}</div></div>'
                for y in keys]
        parts.append(f'<div class="strips">{"".join(rows)}</div>')
    names = dict(COLLECTIONS)
    by_coll: dict[str, list[dict]] = {}
    for d in manifest:
        by_coll.setdefault(d["collection"], []).append(d)
    parts.append('<h2>הקורפוס כולו, אוסף אחר אוסף</h2><div class="coll-table">')
    for coll, _ in COLLECTIONS:
        docs = by_coll.get(coll, [])
        if not docs:
            continue
        working = [d for d in docs if d["path"] in all_views]
        n_enc = sum(all(v.status == "done" for v in all_views[d["path"]]) for d in working)
        share = sum(sum(v.status == "done" for v in all_views[d["path"]]) / max(len(all_views[d["path"]]), 1)
                    for d in working) / len(docs)
        def li(d):
            return (f'<li class="{"work" if d["path"] in all_views else ""}">'
                    + (f'<a href="{d["path"].removesuffix(".xml")}.html">{he(d["title"])}</a>'
                       if d["path"] in all_views else
                       f'<a href="{CORPUS_SITE}/{esc(d["path"].removesuffix(".xml"))}.html">{he(d["title"])}</a>')
                    + f' <span class="date">{esc(d["date"] or "")}</span></li>')
        order = sorted(docs, key=lambda d: (d["path"] not in all_views, d["date"] or "", d["path"]))
        lis = "".join(li(d) for d in order if not is_site_page(d["path"]))
        site_lis = "".join(li(d) for d in order if is_site_page(d["path"]))
        if site_lis:
            lis += (f'</ul><p class="doclist-group">{esc(SITE_GROUP)}</p><ul class="doclist">{site_lis}')
        parts.append(
            f'<details class="coll-row"><summary><span class="cname">{esc(names.get(coll, coll))}</span>'
            f'<span class="bar"><i class="rule" style="width:{share * 100:.2f}%"></i></span>'
            f'<span class="cnum">{n_enc} מתוך {len(docs)} מסמכים מקודדים'
            + (f', {len(working) - n_enc} בעבודה' if len(working) > n_enc else "")
            + '</span></summary>'
            f'<ul class="doclist">{lis}</ul></details>')
    parts.append("</div>")
    return page("coverage.html", f"כיסוי — {TITLE}", "".join(parts), tab="coverage",
                desc="כמה מקורפוס אופק חדש מקודד ב-L4, מסמך אחר מסמך וסעיף אחר סעיף")
