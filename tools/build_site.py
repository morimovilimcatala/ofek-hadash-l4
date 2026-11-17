"""Build the static site: the corpus text beside its L4, document by document.

    python3 tools/build_site.py      # after tools/l4run.py; writes build/site/

This file is the build (build(), the about page and the entry point); each
page type is a module of tools/pages/ (MMS-776), and every name they define
is re-exported here, so `import build_site` sees the whole site.

Pages, laid out like the corpus they encode:

  index.html                       the collections, and how much is encoded
  <collection>/<doc>.html          a sectioned document's contents (the takanon's
                                   chapters and sections, the base agreement's
                                   parts and articles)
  <collection>/<doc>/chapter-<n>.html   one chapter or part: each section's text | L4
  <collection>/<doc>/<num>.html         a redirect to the section on its chapter page
  <collection>/<doc>/<num>.render.html  L4's own rendering of that section
  <collection>/<doc>/<num>.prose.json   that section's prose views, fetched on the switch
  <collection>/<doc>.html          a whole document (a circular, an agreement
                                   not read by sections): its text | L4, row by row,
                                   and below its L4 its module's tests file, if it has
                                   one (l4/tests/<module>-tests.l4, MMS-607)
  root.html, <collection>/root.html, salary-root.html
                                   the roots (tools/roots.py): each one's code and tests
  <collection>.html               a collection's documents, by year or by family
  findings.html  findings.json     errors in the LAW that encoding exposed
  salary.html                      a redirect to calculator.html: the salary-structure
                                   diagram was dropped (the client, 2026-10-22)
  calculator.html                  §1.1's salary, computed in the browser by L4 (WASM)
  calculator-delta.html            a redirect: the simulator's gaps are a group of
                                   contradictions.html now (MMS-522)
  laws/<name>.html                 a statute the L4 encodes outside the corpus, each section
                                   beside its rules (laws/<name>.toml, l4/laws/<name>.l4)
  laws/index.html                  every statute the corpus cites, and the sections it cites
                                   by number (data/statute-citations.json, MMS-601)
  laws/record.html  statute-record.json
                                   every document of the manifest against every protective
                                   statute: meets, falls short, not weighed and why, or not
                                   checked (tools/statute_record.py, MMS-601); each document's
                                   page shows its row, each statute's page its documents
  contradictions.html              where one instrument contradicts another: every
                                   contradiction the root finds, generated from its report
                                   (MMS-521), with a crop of each page, the rule that
                                   decides and whether it was followed where a card is
                                   written by hand (data/contradictions.json); and where the
                                   ministry's simulator departs from the text, by cause
                                   (data/calculator-delta.json)
  coverage.html                    how much of the corpus is encoded
  diagnostics.html                 what the L4 checker reported, file by file; every
                                   tests file and the page that shows it, and in full
                                   any tests file no module page shows
  index.json                       every L4 segment with its corpus address

The site is in Hebrew (the client, 2026-10-10); the L4 source and its notes are in English, and the corpus's text is shown as it is.
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
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
from pages.checks import *  # noqa: E402,F401,F403
from pages.conventions import *  # noqa: E402,F401,F403


def about_page() -> str:
    body = f"""<h1>אודות</h1>
<p class="lede">האתר מציב את נוסח קורפוס אופק חדש — המסמכים שמסדירים את העסקת עובדי ההוראה —
ליד קידוד שלו בשפת L4, סעיף אחר סעיף.</p>
<h2>איך קוראים עמוד</h2>
<p>כל שורה היא פסקה אחת של הטקסט: מימין הטקסט כפי שהוא בקורפוס, ומשמאל הכללים שקודדו ממנו.
המתג <em>פרוזה</em> מחליף את הקוד בניסוח בשפה טבעית ש־<code>l4 render</code> מפיק מאותם כללים;
הניסוח הזה, כמו הקוד, באנגלית. תוצאות ה־<code>#ASSERT</code>, <code>#EVAL</code> ו־<code>#TRACE</code>
מופיעות מתחת לקוד שהן בודקות. מסמך שיש לו קובץ בדיקות משלו (<code dir="ltr">l4/tests/</code>) —
למשל הסכם שנבדק מול סבב השכר של המגזר הציבורי שלו — מציג אותו מתחת לקוד, כל בדיקה עם מה שהמהדר ענה;
<a href="diagnostics.html#tests-files">עמוד הבדיקות</a> מונה את כל קובצי הבדיקות ואת העמוד שמציג כל אחד. פסקה שאין בה כלל (רשימת מקורות, הערת תיקון) מסומנת
<em>ללא כלל</em> עם הנימוק; פסקה שאף קוד אינו מצטט מסומנת <em>לא קודד</em>.</p>
<h2>מה הקידוד מקבל כנתון</h2>
<ul>
<li>הטקסט הוא של הקורפוס. העתק שמור ב־<code>corpus/</code> ואינו נערך כאן.</li>
<li>טעות בעמוד המודפס שהקורפוס כבר הכריע בה — קריאת הקורפוס עומדת.</li>
<li>סכום שהטקסט אומר שנקבע במקום אחר (על ידי האוצר, בחוזר) הוא קלט, ולעולם לא מספר שהומצא.</li>
</ul>
<h2>מה הקידוד מוסיף</h2>
<p>היכן שהטקסט אינו מתיישב, הממצא עובר ל<a href="findings.html">ממצאי L4</a>
עם <code>#ASSERT</code> שמראה אותו, והקוד אומר איזו קריאה הוא מאמץ.</p>
<h2>למכונות</h2>
<p><a href="index.json">index.json</a> מפרט כל קטע L4 עם הכתובת בקורפוס שהוא מקודד
(<code dir="ltr">&lt;document&gt;#&lt;eId&gt;</code>); <a href="findings.json">findings.json</a> מפרט את הממצאים.</p>
<p>קוד מקור: <a href="{REPO}" dir="ltr">{esc(REPO.split('github.com/')[1])}</a>.</p>"""
    return page("about.html", f"אודות — {TITLE}", body, tab="about")


def build() -> int:
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "assets").mkdir(parents=True)
    for f in ASSETS.iterdir():
        if f.is_dir():
            shutil.copytree(f, OUT / "assets" / f.name)
        else:
            shutil.copy(f, OUT / "assets" / f.name)
    # a finding a weaker-against-stronger card cites lives on that card only
    # (contradictions.homes): it leaves the findings page, its counts and the
    # rows' flags; the whole register still backs the cards' evidence
    REGISTER[:] = load_findings()
    HOMES.clear()
    HOMES.update(contradictions.homes(CONTRA))
    findings = [f for f in REGISTER if f["id"] not in HOMES]
    FINDINGS_BY_KEY.clear()
    for f in findings:
        for k in f.get("keys", []):
            FINDINGS_BY_KEY.setdefault((finding_doc(f), k), []).append(f)
    all_views: dict[str, list[SectionView]] = {
        doc: [build_view(doc, s) for s in akn.sections(doc)] for doc in DOCUMENTS}
    NAV_VIEWS.clear()
    NAV_VIEWS.update(all_views)
    STATUTES.clear()
    STATUTES.update(statute_record.build())
    STATUTE_CELLS.clear()
    for r, sec, cells in statute_record.units(STATUTES):
        STATUTE_CELLS[(r["doc"], sec)] = cells
        if sec is not None:
            STATUTE_CELLS[(r["doc"], None)] = r["cells"]
    # a module with a tests file, by its file: its page shows them (a
    # root's page does so itself, in tools/roots.py)
    wanted = modules.wanted()[0]
    encoded = {str(v.l4.relative_to(ROOT)) for vs in all_views.values() for v in vs if v.l4}
    TESTED.clear()
    TESTED.update({f: n for n, p in wanted.items() if roots.tests_of(n).exists()
                   and (f := str(p.relative_to(ROOT))) in encoded})
    for doc in DOCUMENTS:
        views = all_views[doc]
        d = OUT / doc.removesuffix(".xml")
        if akn.is_whole(doc):
            v = views[0]
            (OUT / v.page).parent.mkdir(parents=True, exist_ok=True)
            (OUT / v.page).write_text(single_page(doc, v), encoding="utf-8")
            if v.src is not None:
                (OUT / v.render_href).write_text(render_page(v), encoding="utf-8")
                (OUT / v.prose_href).write_text(prose_json(v), encoding="utf-8")
            continue
        d.mkdir(parents=True, exist_ok=True)
        chapters = chapters_of(views)
        pages = [vs[0].page for vs in chapters]
        assert len(set(pages)) == len(pages), f"{doc}: two chapters share a page name"
        # the contents page sends an old #fragment on by the chapter eId
        # that begins it (the takanon was one page once; an agreement's
        # article eIds do not carry their part's)
        for vs in (chapters if doc.startswith("takanon/") else []):
            ch = vs[0].section.chapter_eid
            for v in vs:
                for k in [v.section.eid, *v.section.keys()]:
                    assert k == ch or k.startswith(ch + "__") or k.startswith(ch + "/"), \
                        f"{doc}: {k} is not under its chapter {ch}"
        (OUT / f"{doc.removesuffix('.xml')}.html").write_text(contents_page(doc, views), encoding="utf-8")
        for i, p in enumerate(pages):
            (OUT / p).write_text(chapter_page(doc, chapters, i), encoding="utf-8")
        # the per-section pages and the chapter list this site had first
        # now send the reader to the section's anchor on its chapter page
        (d / "index.html").write_text(redirect_page(f"{doc.removesuffix('.xml')}/index.html",
                                                    f"{doc.removesuffix('.xml')}.html", akn.title(doc)), encoding="utf-8")
        for v in views:
            (OUT / v.old_href).write_text(redirect_page(v.old_href, v.href, sec_ref(v.section)), encoding="utf-8")
            if v.src is not None:
                (OUT / v.render_href).write_text(render_page(v), encoding="utf-8")
                (OUT / v.prose_href).write_text(prose_json(v), encoding="utf-8")
    flat = [v for vs in all_views.values() for v in vs]
    by_file = {str(v.l4.relative_to(ROOT)): v for v in flat if v.l4}
    key_to_view = {}
    for v in flat:
        for k in v.section.keys():
            key_to_view.setdefault((v.doc, k), v)
    for coll in WORK_COLLECTIONS[1:]:
        vs = [v for d, views in all_views.items() if d.startswith(coll + "/") for v in views]
        if vs:
            (OUT / f"{coll}.html").write_text(collection_page(coll, vs), encoding="utf-8")
    (OUT / "index.html").write_text(index_page(all_views, findings), encoding="utf-8")
    (OUT / "findings.html").write_text(findings_page(findings, by_file, key_to_view), encoding="utf-8")
    # the salary-structure page was dropped (the client, 2026-10-22): its old
    # address goes to the calculator, or home where there is none
    (OUT / "salary.html").write_text(
        redirect_page("salary.html", "calculator.html" if CALCULATOR else "index.html",
                      "מחשבון שכר" if CALCULATOR else TITLE), encoding="utf-8")
    if CALCULATOR:
        (OUT / "calculator.html").write_text(calculator_page(all_views, findings), encoding="utf-8")
    if DELTA:
        (OUT / calculator_delta.HERE).write_text(
            redirect_page(calculator_delta.HERE, f"{contradictions.HERE}#{calculator_delta.GROUP}",
                          contradictions.TAB), encoding="utf-8")
    (OUT / "laws").mkdir(parents=True, exist_ok=True)
    for name in laws.all_laws():
        (OUT / "laws" / f"{name}.html").write_text(law_page(name), encoding="utf-8")
    (OUT / "laws" / "index.html").write_text(laws_index_page(), encoding="utf-8")
    (OUT / statute_record.HERE).write_text(statute_record_page(), encoding="utf-8")
    (OUT / "statute-record.json").write_text(json.dumps(STATUTES, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    real = {n: str(f.relative_to(ROOT)) for n, f in modules.wanted()[0].items()}

    def href_of(module: str) -> str | None:
        if module in laws.all_laws():  # a statute: its page beside its text
            return f"laws/{module}.html"
        v = by_file.get(real.get(module, ""))
        return v.href if v is not None else None
    for module, here, coll, heading, about in roots.ROOTS:
        (OUT / here).parent.mkdir(parents=True, exist_ok=True)
        see = (f' מחשבון השכר מריץ אותו: <a href="{rel("calculator.html", here)}">מחשבון שכר</a>.'
               if module == "salary-root" and CALCULATOR else "")
        body = roots.page_body(module, here, coll, heading, about, esc=esc, rel=rel,
                               code_html=l4src.numbered_html, href_of=href_of,
                               coll_name=coll_name, coll_href=coll_hub, see=see)
        (OUT / here).write_text(page(here, f"{heading} — {TITLE}", body, tab="docs",
                                     desc=about), encoding="utf-8")
    if CONTRA:
        (OUT / "assets" / "contradictions").mkdir(parents=True, exist_ok=True)
        for f in contradictions.crops(CONTRA):
            shutil.copyfile(contradictions.CROPS / f, OUT / "assets" / "contradictions" / f)
        (OUT / contradictions.HERE).write_text(contradictions_page(findings, by_file, key_to_view, href_of),
                                               encoding="utf-8")
    (OUT / "findings.json").write_text(findings_json(findings, by_file, key_to_view), encoding="utf-8")
    (OUT / "index.json").write_text(index_json(flat), encoding="utf-8")
    (OUT / "coverage.html").write_text(coverage_page(all_views), encoding="utf-8")
    (OUT / "diagnostics.html").write_text(diagnostics_page(flat, tests_homes(by_file)), encoding="utf-8")
    (OUT / "conventions.html").write_text(conventions_page(load_conventions(), by_file, findings), encoding="utf-8")
    (OUT / "about.html").write_text(about_page(), encoding="utf-8")
    (OUT / ".nojekyll").write_text("")
    done = sum(v.status == "done" for v in flat)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(flat)} sections, {done} encoded, {len(findings)} findings")
    return 0


if __name__ == "__main__":
    sys.exit(build())
