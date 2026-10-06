"""Build the static site: the corpus text beside its L4, document by document.

    python3 tools/build_site.py            # after tools/l4run.py, writes build/site/

Pages, laid out like the corpus they encode:

  index.html                       the collections, and how much is encoded
  takanon/<doc>/index.html         a document's chapters and sections
  takanon/<doc>/<num>.html         one section: text | L4, row by row
  takanon/<doc>/<num>.render.html  L4's own rendering of that section
  findings.html                    errors in the TEXT that encoding it exposed
  sic.html                         the corpus's sic marks, carried as given
  diagnostics.html                 what the L4 checker reported, file by file
"""
from __future__ import annotations

import html
import json
import re
import shutil
import sys
import tomllib
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import akn      # noqa: E402
import l4src    # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "build" / "site"
L4_OUT = ROOT / "build" / "l4"
ASSETS = Path(__file__).resolve().parent / "assets"
FINDINGS = ROOT / "findings" / "findings.toml"
MANIFEST = ROOT / "corpus" / "manifest.json"
CORPUS_SITE = "https://morimovilimcatala.github.io/ofek-hadash-corpus"
REPO = "https://github.com/morimovilimcatala/ofek-hadash-l4"
TITLE = "L4 — מאגר אופק חדש"

# what is encoded, by the corpus document it encodes; the l4/ directory
# mirrors the corpus's akn/ path without the extension
DOCUMENTS = ["takanon/takanon-sherut-ovdei-horaa.xml"]

# the corpus's collections, in its own order, so the reader sees what is
# not started as well as what is
COLLECTIONS = [
    ("takanon", "תקנון שירות עובדי הוראה"),
    ("agreements", "הסכמים קיבוציים"),
    ("circulars", "חוזרים"),
    ("circulars-sachar", "חוזרי שכר"),
    ("circulars-tnai-sherut", "חוזרי תנאי שירות"),
    ("letters", "מכתבים"),
    ("takam", "תקשי\"ר"),
    ("tables", "טבלאות"),
]

KINDS = {
    "overlap": "חפיפה — שני כללים לאותו מקרה",
    "conflict": "סתירה — שני סעיפים, שתי תוצאות",
    "gap": "פער — מקרה שאין לו כלל",
    "dangling-reference": "הפניה שאינה מגיעה ליעדה",
    "undefined-term": "מונח שלא הוגדר",
    "arithmetic": "חשבון שאינו מתיישב",
    "numbering": "מספור",
    "ambiguity": "עמימות — יותר מקריאה אחת",
}

esc = html.escape


# ----------------------------------------------------------------- model

@dataclass
class SectionView:
    doc: str                      # corpus-relative xml path
    section: akn.Section
    l4: Path | None
    src: l4src.Source | None = None
    run: dict = field(default_factory=dict)
    render: str = ""
    anchors: dict = field(default_factory=dict)    # row key -> [segments]
    covered: set = field(default_factory=set)      # row keys covered
    kind_of: dict = field(default_factory=dict)    # row key -> "rule" | "note"
    unplaced: list = field(default_factory=list)   # segments citing no row

    @property
    def dir(self) -> str:
        return self.doc.removesuffix(".xml")

    @property
    def href(self) -> str:
        return f"{self.dir}/{self.section.num}.html"

    @property
    def text_rows(self):
        return [r for r in self.section.rows if r.kind == "text"]

    @property
    def status(self) -> str:
        if self.src is None:
            return "todo"
        if any(r.key not in self.covered for r in self.text_rows) or self.unplaced:
            return "partial"
        return "done"

    @property
    def ok(self) -> bool:
        return bool(self.run.get("ok"))


def l4_path(doc: str, num: str) -> Path:
    return ROOT / "l4" / doc.removesuffix(".xml") / f"{num}.l4"


def under(key: str, anc: str) -> bool:
    return key == anc or key.startswith(anc + "__") or key.startswith(anc + "/")


def line_of(rng) -> int | None:
    """The first line of a range as `l4 run --json` prints it."""
    if not rng:
        return None
    m = re.search(r":(\d+):\d+", str(rng)) or re.match(r"(\d+):\d+", str(rng))
    return int(m.group(1)) if m else None


def build_view(doc: str, sec: akn.Section) -> SectionView:
    v = SectionView(doc, sec, l4_path(doc, sec.num))
    if not v.l4.exists():
        v.l4 = None
        return v
    v.src = l4src.parse(v.l4)
    rel = v.l4.relative_to(ROOT / "l4")
    base = L4_OUT / rel.parent / rel.stem
    run = base.with_suffix(".run.json")
    v.run = json.loads(run.read_text(encoding="utf-8")) if run.exists() else {
        "ok": False, "results": [], "diagnostics": [
            {"severity": "error", "message": "not run: tools/l4run.py has not been run on this file"}]}
    rend = base.with_suffix(".render.html")
    v.render = rend.read_text(encoding="utf-8") if rend.exists() else ""
    for res in v.run.get("results", []):
        s = l4src.segment_at(v.src, line_of(res.get("range")) or -1)
        if s:
            s.results.append(res)
    for d in v.run.get("diagnostics", []):
        s = l4src.segment_at(v.src, line_of(d.get("range")) or -1)
        if s:
            s.diagnostics.append(d)
    rows = sec.rows
    where = {}
    for r in rows:
        where.setdefault(r.key, r)
        for a in r.aliases:
            where.setdefault(a, r)
    for s in v.src.segments:
        first = next((k for k in s.keys if k in where), None)
        if first is None:
            v.unplaced.append(s)
            continue
        v.anchors.setdefault(where[first].key, []).append(s)
        for k in s.keys:
            for r in rows:
                if under(r.key, k) or k in r.aliases:
                    v.covered.add(r.key)
                    if v.kind_of.get(r.key) != "rule":
                        v.kind_of[r.key] = "note" if s.note_only else "rule"
    return v


def tally(v: SectionView) -> dict[str, int]:
    """The section's text paragraphs by what the L4 does with them."""
    out = {"rule": 0, "note": 0, "missing": 0}
    for r in v.text_rows:
        out[v.kind_of.get(r.key, "missing")] += 1
    return out


# ------------------------------------------------------- L4's own rendering

class _Clauses(HTMLParser):
    """Pull each top-level <li class="clause …"> out of `l4 render`'s HTML,
    keyed by the name in its <span class="term">."""

    def __init__(self, text: str):
        super().__init__(convert_charrefs=False)
        self.text, self.out = text, {}
        self.depth = 0
        self.start = None
        self.term = None
        self.in_term = False
        self.feed(text)

    def _offset(self) -> int:
        line, col = self.getpos()
        lines = self.text.split("\n")
        return sum(len(l) + 1 for l in lines[:line - 1]) + col

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "li":
            if self.start is None and "clause" in (a.get("class") or "").split():
                self.start, self.depth, self.term = self._offset(), 1, ""
            elif self.start is not None:
                self.depth += 1
        if self.start is not None and tag == "span" and a.get("class") == "term" and self.term == "":
            self.in_term = True

    def handle_endtag(self, tag):
        if tag == "span":
            self.in_term = False
        if tag == "li" and self.start is not None:
            self.depth -= 1
            if self.depth == 0:
                end = self.text.find(">", self._offset()) + 1
                frag = self.text[self.start:end]
                self.out.setdefault(_norm(self.term), []).append(frag)
                self.start = None

    def handle_data(self, data):
        if self.in_term:
            self.term += data


def _norm(name: str) -> str:
    return re.sub(r"[\s`“”\"]+", " ", name).strip().lower()


DECL = re.compile(r"""^\s*(?:DECIDE\s+)?`([^`]+)`|^\s*DECLARE\s+(`[^`]+`|\S+)
                      |^\s*ASSUME\s+(`[^`]+`|\S+)|^\s*([A-Za-z_][\w']*)\s+(?:MEANS|IS)\b""",
                  re.VERBOSE)


def declared(seg: l4src.Segment) -> list[str]:
    out = []
    for line in seg.lines:
        if line.lstrip().startswith(("--", "@", "#", "GIVEN", "GIVETH", "§", "IMPORT")):
            continue
        if line[:1].isspace() and not line.lstrip().startswith("DECIDE"):
            continue
        m = DECL.match(line)
        if m:
            name = next(g for g in m.groups() if g)
            out.append(_norm(name.strip("`")))
    return out


def rendered_for(v: SectionView) -> dict[int, str]:
    """segment start line -> L4's rendering of what that segment declares."""
    if not v.render or v.src is None:
        return {}
    clauses = _Clauses(v.render).out
    out = {}
    for s in v.src.segments:
        frags = [f for n in declared(s) for f in clauses.get(n, [])]
        if frags:
            out[s.start] = '<ol class="clauses">' + "".join(frags) + "</ol>"
    return out


# ------------------------------------------------------------------ pages

def rel(target: str, here: str) -> str:
    depth = here.count("/")
    return "../" * depth + target


def page(here: str, title: str, body: str, *, tab: str = "", desc: str = "") -> str:
    nav = [("index.html", "מסמכים", "docs"),
           ("findings.html", "ממצאי L4", "findings"),
           ("coverage.html", "כיסוי", "coverage"),
           ("sic.html", "כך במקור", "sic"),
           ("diagnostics.html", "אבחון", "diagnostics"),
           ("about.html", "על האתר", "about")]
    links = "".join(
        f'<a href="{rel(h, here)}"{" aria-current=page" if k == tab else ""}>{esc(t)}</a>'
        for h, t, k in nav)
    return f"""<!doctype html>
<html lang="he" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc or title)}">
<link rel="stylesheet" href="{rel('assets/site.css', here)}">
<link rel="stylesheet" href="{rel('assets/l4-render.css', here)}">
<script defer src="{rel('assets/site.js', here)}"></script>
</head>
<body>
<header class="top">
  <a class="brand" href="{rel('index.html', here)}">L4 · אופק חדש</a>
  <nav class="tabs-top">{links}</nav>
</header>
<main>
{body}
</main>
<footer class="foot">
  הטקסט — <a href="{CORPUS_SITE}/">מאגר אופק חדש</a>, כפי שפורסם; הקוד — <a href="{REPO}">{esc(REPO.split('github.com/')[1])}</a>.
  הקידוד הוא קריאה של הטקסט ואינו מחליף אותו.
</footer>
</body>
</html>
"""


def chip(status: str) -> str:
    label = {"done": "מקודד", "partial": "חלקי", "todo": "טרם קודד"}[status]
    return f'<span class="chip {status}">{label}</span>'


def text_cell(r: akn.Row) -> str:
    if r.kind == "label":
        head = f' <span class="h">{esc(r.heading)}</span>' if r.heading else ""
        return f'<span class="num">{esc(r.num)}</span>{head}'
    parts = []
    for run in r.runs:
        if run.sic:
            parts.append(f'<span class="sic" title="כך במקור: {esc(run.sic)}">'
                         f'{esc(run.text)}</span><sup class="sic-mark">[כך במקור]</sup>')
        else:
            parts.append(esc(run.text))
    return "".join(parts)


def results_html(seg: l4src.Segment) -> str:
    if not seg.results and not seg.diagnostics:
        return ""
    items = []
    for res in seg.results:
        kind = res.get("kind", "")
        val = res.get("value")
        sval = val if isinstance(val, str) else json.dumps(val, ensure_ascii=False)
        bad = kind.lower().startswith("assert") and str(sval).lower() not in ("true", "passed", "ok")
        items.append(f'<li class="res{" bad" if bad else ""}"><span class="rk">#{esc(kind.upper())}</span> '
                     f'<span class="rl">שורה {line_of(res.get("range"))}</span> '
                     f'<code dir="ltr">{esc(str(sval))[:400]}</code></li>')
    for d in seg.diagnostics:
        items.append(f'<li class="res bad"><span class="rk">{esc(d.get("severity", ""))}</span> '
                     f'<code dir="ltr">{esc(d.get("message", ""))[:600]}</code></li>')
    return '<ul class="results">' + "".join(items) + "</ul>"


def segment_html(v: SectionView, s: l4src.Segment, rendered: dict[int, str]) -> str:
    gh = f"{REPO}/blob/main/{v.l4.relative_to(ROOT)}#L{s.start}-L{s.end}"
    if s.note_only:
        return (f'<div class="seg note"><span class="note-label">אין כאן כלל</span> '
                f'{esc(s.note)} <a class="gh" href="{gh}" title="בקוד המקור">L{s.start}</a></div>')
    others = "".join(f'<a class="also" href="#{esc(k)}">גם {esc(k.split("__")[-1])}</a>'
                     for k in s.keys[1:])
    r = rendered.get(s.start)
    rend = (f'<div class="view rendered l4-doc" hidden>{r}</div>' if r else
            '<div class="view rendered empty" hidden>L4 אינו מציג את הקטע הזה כסעיף נפרד '
            '(הצהרת טיפוס, בדיקה או חלק מכלל שהוצג במקום אחר).</div>')
    return (f'<div class="seg">'
            f'<div class="seg-bar"><a class="gh" href="{gh}">שורות {s.start}–{s.end}</a>{others}</div>'
            f'<div class="view code-view">{l4src.code_html(s.lines, s.start)}</div>'
            f'{rend}{results_html(s)}</div>')


def section_page(v: SectionView, prev_next) -> str:
    sec = v.section
    here = v.href
    corpus = f"{CORPUS_SITE}/{v.dir}.html#{sec.eid}"
    head = (f'<nav class="crumbs"><a href="{rel("index.html", here)}">מסמכים</a> › '
            f'<a href="index.html">{esc(akn.title(v.doc))}</a> › '
            f'<span>פרק {esc(sec.chapter_num)} {esc(sec.chapter_heading)}</span></nav>'
            f'<h1><span class="secnum">{esc(sec.num)}</span> {esc(sec.heading)} {chip(v.status)}</h1>'
            f'<p class="meta"><a href="{corpus}">הסעיף במאגר</a>')
    if v.l4:
        head += (f' · <a href="{REPO}/blob/main/{v.l4.relative_to(ROOT)}">קוד המקור ({esc(v.l4.name)})</a>'
                 f' · <a href="{esc(sec.num)}.render.html">התצוגה של L4 כמסמך</a>')
    head += "</p>"
    pn = '<nav class="prevnext">' + "".join(
        f'<a class="{cls}" href="{esc(x.section.num)}.html">{lab} {esc(x.section.num)} {esc(x.section.heading)}</a>'
        for x, cls, lab in prev_next if x) + "</nav>"

    if v.src is None:
        rows = "".join(
            f'<div class="row {r.kind} d{min(r.depth, 6)}" id="{esc(r.key)}"><div class="txt">{text_cell(r)}</div></div>'
            for r in sec.rows)
        body = (head + '<p class="banner">הסעיף טרם קודד. מוצג כאן הטקסט שלו כפי שהוא במאגר.</p>'
                + f'<div class="grid only-text">{rows}</div>' + pn)
        return page(here, f"{sec.num} {sec.heading} — {TITLE}", body, tab="docs")

    rendered = rendered_for(v)
    pre_lines = v.src.lines[v.src.preamble[0] - 1:v.src.preamble[1] - 1]
    preamble = ""
    if any(l.strip() for l in pre_lines):
        preamble = (f'<details class="preamble" open><summary>אוצר המילים של הסעיף '
                    f'(ייבוא, טיפוסים והנחות)</summary>'
                    f'{l4src.code_html(pre_lines, v.src.preamble[0])}</details>')
    out = []
    for r in sec.rows:
        segs = v.anchors.get(r.key, [])
        cls = [r.kind, f"d{min(r.depth, 6)}"]
        if r.kind == "text" and r.key not in v.covered:
            cls.append("gap")
        elif r.key in v.covered and not segs:
            cls.append("covered")
        code = "".join(segment_html(v, s, rendered) for s in segs)
        if "gap" in cls:
            code = '<div class="seg missing">לא מקודד — אף כלל אינו מפנה לפסקה הזו</div>'
        ids = " ".join(esc(a) for a in r.aliases)
        alias = "".join(f'<span id="{esc(a)}"></span>' for a in r.aliases)
        out.append(f'<div class="{" ".join(cls)}" id="{esc(r.key)}" data-aliases="{ids}">'
                   f'<div class="txt">{alias}{text_cell(r)}</div><div class="l4">{code}</div></div>')
    unplaced = ""
    if v.unplaced:
        unplaced = ('<div class="banner bad">קטעי קוד שמפנים למפתח שאינו בסעיף: ' +
                    ", ".join(esc(" ".join(s.keys)) for s in v.unplaced) + "</div>")
    ok = ('<span class="okay">L4 בודק את הקובץ וכל ה־#ASSERT מתקיימים</span>' if v.ok else
          '<span class="notok">L4 מדווח על שגיאה בקובץ — ראו <a href="../../diagnostics.html">אבחון</a></span>')
    switch = ('<div class="switch" role="group" aria-label="תצוגת הצד של L4">'
              '<button type="button" data-view="code-view" aria-pressed="true">קוד</button>'
              '<button type="button" data-view="rendered" aria-pressed="false">L4 מעובד</button></div>')
    body = (head + f'<p class="status">{ok}</p>' + unplaced +
            f'<div class="colheads"><div>הטקסט</div><div>L4 {switch}</div></div>' +
            preamble + f'<div class="grid">{"".join(out)}</div>' + pn)
    return page(here, f"{sec.num} {sec.heading} — {TITLE}", body, tab="docs",
                desc=f"סעיף {sec.num} בתקנון שירות עובדי הוראה, בטקסט ובקידוד L4")


def render_page(v: SectionView) -> str:
    """L4's own rendering, framed by the site so it is navigable."""
    m = re.search(r"<body[^>]*>(.*)</body>", v.render, re.S)
    inner = m.group(1) if m else v.render
    here = v.href.replace(".html", ".render.html")
    body = (f'<nav class="crumbs"><a href="{esc(v.section.num)}.html">← חזרה להשוואה</a></nav>'
            f'<h1><span class="secnum">{esc(v.section.num)}</span> {esc(v.section.heading)} — '
            f'כפי ש־<code>l4 render</code> מציג אותו</h1>'
            f'<div class="render-frame" dir="ltr">{inner}</div>')
    return page(here, f"{v.section.num} — l4 render", body, tab="docs")


def document_page(doc: str, views: list[SectionView]) -> str:
    here = f"{doc.removesuffix('.xml')}/index.html"
    chapters: dict[str, list[SectionView]] = {}
    for v in views:
        chapters.setdefault(v.section.chapter_eid, []).append(v)
    done = sum(v.status == "done" for v in views)
    part = sum(v.status == "partial" for v in views)
    parts = [f'<nav class="crumbs"><a href="{rel("index.html", here)}">מסמכים</a></nav>',
             f'<h1>{esc(akn.title(doc))}</h1>',
             f'<p class="meta"><a href="{CORPUS_SITE}/{doc.removesuffix(".xml")}.html">המסמך במאגר</a> · '
             f'{len(views)} סעיפים: {done} מקודדים, {part} חלקית, {len(views) - done - part} טרם.</p>']
    for vs in chapters.values():
        s0 = vs[0].section
        lis = "".join(
            f'<li><a href="{esc(v.section.num)}.html"><span class="secnum">{esc(v.section.num)}</span> '
            f'{esc(v.section.heading)}</a> {chip(v.status)}</li>' for v in vs)
        parts.append(f'<section class="chapter"><h2>פרק {esc(s0.chapter_num)} {esc(s0.chapter_heading)}</h2>'
                     f'<ul class="secs">{lis}</ul></section>')
    return page(here, f"{akn.title(doc)} — {TITLE}", "".join(parts), tab="docs")


def index_page(all_views: dict[str, list[SectionView]]) -> str:
    rows = []
    for coll, name in COLLECTIONS:
        docs = [d for d in DOCUMENTS if d.startswith(coll + "/")]
        if not docs:
            rows.append(f'<li class="coll todo"><span>{esc(name)}</span> {chip("todo")}</li>')
            continue
        for d in docs:
            vs = all_views[d]
            done = sum(v.status == "done" for v in vs)
            rows.append(f'<li class="coll"><a href="{d.removesuffix(".xml")}/index.html">{esc(akn.title(d))}</a> '
                        f'<span class="count">{done} / {len(vs)} סעיפים מקודדים</span></li>')
    body = (f'<h1>קידוד L4 של מאגר אופק חדש</h1>'
            f'<p class="lede">כל סעיף מוצג פעמיים, זה לצד זה: הטקסט כפי שהוא ב'
            f'<a href="{CORPUS_SITE}/">מאגר</a>, והכללים שקראנו בו כתובים ב־'
            f'<a href="https://legalese.com/l4/">L4</a> — שפת תכנות למשפט שהמהדר שלה בודק טיפוסים, '
            f'מריץ את הדוגמאות ומציג את הכללים כמסמך. כשהקידוד נתקל בטקסט שאינו מתיישב — שני כללים לאותו מקרה, '
            f'מקרה שאין לו כלל, הפניה שאינה מגיעה ליעדה — הממצא נרשם ב<a href="findings.html">ממצאי L4</a>, '
            f'עם הקוד שמראה אותו.</p>'
            f'<ul class="colls">{"".join(rows)}</ul>')
    return page("index.html", TITLE, body, tab="docs",
                desc="הטקסט של תקנון שירות עובדי הוראה לצד קידוד L4 שלו, סעיף אחר סעיף")


def load_findings() -> list[dict]:
    if not FINDINGS.exists():
        return []
    return tomllib.loads(FINDINGS.read_text(encoding="utf-8")).get("finding", [])


def evidence_result(f: dict, views_by_file: dict[str, SectionView]) -> tuple[str, bool | None]:
    v = views_by_file.get(f.get("l4", ""))
    if v is None or v.src is None:
        return "", None
    ev = f.get("evidence", "")
    for n, line in enumerate(v.src.lines, 1):
        if line.lstrip().startswith("#ASSERT") and ev in line:
            for res in v.run.get("results", []):
                if line_of(res.get("range")) == n:
                    return f"{REPO}/blob/main/{f['l4']}#L{n}", True
            return f"{REPO}/blob/main/{f['l4']}#L{n}", None
    return "", False


def findings_page(findings, views_by_file, key_to_view) -> str:
    cards = []
    for f in findings:
        url, held = evidence_result(f, views_by_file)
        where = []
        for k in f.get("keys", []):
            v = key_to_view.get(k)
            if v:
                where.append(f'<a href="{v.href}#{esc(k)}">§{esc(v.section.num)}</a>')
        state = ("<span class=\"okay\">ה־#ASSERT מתקיים: הליקוי עדיין בטקסט</span>" if held else
                 "<span class=\"notok\">אין ראיה ב־L4 — ראו אבחון</span>")
        cards.append(
            f'<article class="finding" id="{esc(f["id"])}">'
            f'<h2><span class="fid">{esc(f["id"])}</span> {esc(f["title"])}</h2>'
            f'<p class="fmeta"><span class="kind">{esc(KINDS.get(f.get("kind", ""), f.get("kind", "")))}</span> · '
            f'{" · ".join(where)} · {state}</p>'
            f'<div class="fbody">{"".join(f"<p>{esc(p)}</p>" for p in f["body"].strip().split(chr(10) + chr(10)))}</div>'
            + (f'<p class="reading"><strong>הקריאה שהקידוד נוקט:</strong> {esc(f["reading"])}</p>' if f.get("reading") else "")
            + (f'<p class="ev"><a href="{url}">הראיה ב־L4</a>: <code dir="ltr">{esc(f["evidence"])}</code></p>' if url else "")
            + "</article>")
    intro = ('<h1>ממצאי L4</h1><p class="lede">מה שהקידוד מצא בטקסט עצמו. כל ממצא נשען על '
             '<code>#ASSERT</code> בקוד שמתקיים כל עוד הליקוי בטקסט — אם הטקסט יתוקן, הבדיקה תיכשל '
             'והממצא יסומן כמיושן. שגיאות הקלדה שהמאגר כבר הכריע בהן ("כך במקור") אינן כאן: '
             'הקידוד מקבל את הכרעת המאגר כנתונה (<a href="sic.html">כך במקור</a>).</p>')
    if not cards:
        cards.append('<p class="empty">אין עדיין ממצאים.</p>')
    return page("findings.html", f"ממצאי L4 — {TITLE}", intro + "".join(cards), tab="findings")


def sic_page(all_views) -> str:
    items = []
    for doc, vs in all_views.items():
        for v in vs:
            for r in v.section.rows:
                for run in r.runs:
                    if run.sic:
                        items.append(f'<li><a href="{v.href}#{esc(r.key)}">§{esc(v.section.num)}</a> '
                                     f'<span class="sic">{esc(run.text)}</span> — {esc(run.sic)}</li>')
    intro = ('<h1>כך במקור</h1><p class="lede">טעויות שהעמוד המודפס עצמו נושא, כפי שהמאגר '
             f'<a href="{CORPUS_SITE}/sic.html">סימן והכריע</a>. כאן ההכרעה נלקחת כנתונה: הטקסט מוצג '
             'עם הסימון, והקידוד קורא את מה שהמאגר קבע שהטקסט אומר. ממצא חדש שהקידוד מעלה נרשם '
             'ב<a href="findings.html">ממצאי L4</a>, לא כאן.</p>')
    if items:
        body = intro + f'<ul class="sics">{"".join(items)}</ul>'
    else:
        body = intro + ('<p class="empty">במסמכים שקודדו עד כה המאגר אינו מסמן אף "כך במקור". '
                        'כשיסמן, הסימון יופיע כאן ובטקסט שליד הקוד.</p>')
    return page("sic.html", f"כך במקור — {TITLE}", body, tab="sic")


def diagnostics_page(views: list[SectionView]) -> str:
    rows = []
    for v in views:
        if v.src is None:
            continue
        diags = v.run.get("diagnostics", [])
        asserts = [r for r in v.run.get("results", []) if str(r.get("kind", "")).lower().startswith("assert")]
        nbad = len(diags) + len(v.unplaced)
        cls = "okay" if v.ok and not v.unplaced else "notok"
        detail = "".join(f'<li><code dir="ltr">{esc(d.get("severity", ""))} {esc(str(d.get("range", "")))} '
                         f'{esc(d.get("message", ""))}</code></li>' for d in diags)
        detail += "".join(f'<li>קטע קוד מפנה למפתח שאינו בסעיף: <code dir="ltr">{esc(" ".join(s.keys))}</code></li>'
                          for s in v.unplaced)
        gaps = sum(1 for r in v.text_rows if r.key not in v.covered)
        rows.append(f'<tr><td><a href="{v.href}">§{esc(v.section.num)}</a></td>'
                    f'<td dir="ltr"><code>{esc(str(v.l4.relative_to(ROOT)))}</code></td>'
                    f'<td class="{cls}">{"תקין" if cls == "okay" else "שגיאה"}</td>'
                    f'<td>{len(asserts)}</td><td>{gaps}</td><td>{nbad}</td></tr>'
                    + (f'<tr class="detail"><td colspan="6"><ul>{detail}</ul></td></tr>' if detail else ""))
    body = ('<h1>אבחון</h1><p class="lede">מה שהמהדר של L4 (<code>l4 run</code>) אומר על כל קובץ: '
            'שגיאות טיפוס ותחביר, ו־<code>#ASSERT</code> שנכשל. "פסקאות חסרות" הן פסקאות הטקסט שאף קטע '
            'קוד אינו מפנה אליהן. בעמוד תקין כל העמודות האדומות אפס.</p>'
            '<table class="diag"><thead><tr><th>סעיף</th><th>קובץ</th><th>מצב</th><th>#ASSERT</th>'
            '<th>פסקאות חסרות</th><th>שגיאות</th></tr></thead><tbody>'
            + "".join(rows) + "</tbody></table>")
    return page("diagnostics.html", f"אבחון — {TITLE}", body, tab="diagnostics")


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
    head = (f'<h1>כיסוי</h1>'
            f'<p class="lede">כמה מן המאגר מקודד ב־L4. המכנה הוא רשימת המסמכים של המאגר עצמו — '
            f'{len(manifest)} מסמכים — ולא רק מה שהתחלנו בו. מסמך מתחלק לסעיפים, וסעיף לפסקאות; '
            f'פסקה היא <span class="sw rule"></span> כלל מקודד, <span class="sw note"></span> פסקה שנקבע '
            f'שאין בה כלל (אסמכתאות, הערות תיקון — עם הסיבה), <span class="sw missing"></span> פסקה '
            f'בסעיף מקודד שאף קוד אינו מפנה אליה, או <span class="sw todo"></span> פסקה בסעיף שטרם קודד.</p>'
            f'<div class="kpis">'
            f'<div><b>{len(DOCUMENTS)}</b> / {len(manifest)}<span>מסמכים בעבודה</span></div>'
            f'<div><b>{done}</b> / {len(flat)}<span>סעיפים מקודדים במלואם</span></div>'
            f'<div><b>{part}</b><span>סעיפים חלקית</span></div>'
            f'<div><b>{t["rule"] + t["note"]}</b> / {paras}<span>פסקאות שנקראו</span></div>'
            f'<div><b>{t["rule"]}</b><span>פסקאות עם כלל</span></div>'
            f'</div>')
    parts = [head]
    # the documents in work, a strip per chapter, a cell per section
    for doc, vs in all_views.items():
        parts.append(f'<h2><a href="{doc.removesuffix(".xml")}/index.html">{esc(akn.title(doc))}</a></h2>')
        chapters: dict[str, list[SectionView]] = {}
        for v in vs:
            chapters.setdefault(v.section.chapter_eid, []).append(v)
        rows = []
        for cvs in chapters.values():
            s0 = cvs[0].section
            cells = []
            for v in cvs:
                n = max(len(v.text_rows), 1)
                if v.src is None:
                    segs = f'<i class="todo" style="flex:{n}"></i>'
                    tip = f"{v.section.num} {v.section.heading}: טרם קודד ({len(v.text_rows)} פסקאות)"
                else:
                    c = tally(v)
                    segs = "".join(f'<i class="{k}" style="flex:{c[k]}"></i>' for k in ("rule", "note", "missing") if c[k])
                    tip = (f"{v.section.num} {v.section.heading}: {c['rule']} כלל, {c['note']} ללא כלל, "
                           f"{c['missing']} חסרות")
                cells.append(f'<a class="cell" href="{v.href}" title="{esc(tip)}" style="flex:{n}">'
                             f'{segs}<span class="lab">{esc(v.section.num)}</span></a>')
            rows.append(f'<div class="strip-row"><div class="strip-name">פרק {esc(s0.chapter_num)} '
                        f'{esc(s0.chapter_heading)}</div><div class="strip">{"".join(cells)}</div></div>')
        parts.append(f'<div class="strips">{"".join(rows)}</div>')
    # every corpus document, by collection
    names = dict(COLLECTIONS)
    by_coll: dict[str, list[dict]] = {}
    for d in manifest:
        by_coll.setdefault(d["collection"], []).append(d)
    parts.append('<h2>כל המאגר, אוסף אחר אוסף</h2><div class="coll-table">')
    for coll, _ in COLLECTIONS:
        docs = by_coll.get(coll, [])
        if not docs:
            continue
        working = [d for d in docs if d["path"] in all_views]
        pct = 0
        for d in working:
            vs = all_views[d["path"]]
            pct += sum(v.status == "done" for v in vs) / max(len(vs), 1)
        share = pct / len(docs)
        lis = "".join(
            f'<li class="{"work" if d["path"] in all_views else ""}">'
            + (f'<a href="{d["path"].removesuffix(".xml")}/index.html">{esc(d["title"])}</a>'
               if d["path"] in all_views else
               f'<a href="{CORPUS_SITE}/{esc(d["path"].removesuffix(".xml"))}.html">{esc(d["title"])}</a>')
            + f' <span class="date">{esc(d["date"] or "")}</span></li>'
            for d in sorted(docs, key=lambda d: (d["path"] not in all_views, d["date"] or "", d["path"])))
        parts.append(
            f'<details class="coll-row"><summary><span class="cname">{esc(names.get(coll, coll))}</span>'
            f'<span class="bar"><i class="rule" style="width:{share * 100:.2f}%"></i></span>'
            f'<span class="cnum">{len(working)} / {len(docs)} מסמכים בעבודה</span></summary>'
            f'<ul class="doclist">{lis}</ul></details>')
    parts.append("</div>")
    return page("coverage.html", f"כיסוי — {TITLE}", "".join(parts), tab="coverage",
                desc="כמה ממאגר אופק חדש מקודד ב־L4, מסמך אחר מסמך וסעיף אחר סעיף")


def about_page() -> str:
    body = f"""<h1>על האתר</h1>
<p class="lede">האתר מציב את הטקסט של מאגר אופק חדש ליד קידוד שלו ב־L4, סעיף אחר סעיף.</p>
<h2>איך לקרוא עמוד סעיף</h2>
<p>כל שורה בטבלה היא פסקה בטקסט. מימינה — הטקסט כפי שהוא במאגר; משמאלה — הכללים שקודדו ממנה.
הכפתור "L4 מעובד" מחליף את הקוד בתצוגה ש־<code>l4 render</code> מפיק מאותם כללים, בשפה טבעית.
פסקה שאין בה כלל (רשימת אסמכתאות, הערת תיקון) מסומנת "אין כאן כלל" עם הסיבה; פסקה שאף קטע קוד
אינו מפנה אליה מסומנת "לא מקודד".</p>
<h2>מה הקידוד מקבל כנתון</h2>
<ul>
<li>הטקסט הוא של המאגר — עותק שלו נשמר ב־<code>corpus/</code> ואינו נערך כאן.</li>
<li>טעות שהמאגר סימן "כך במקור" — הכרעת המאגר נלקחת כנתונה.</li>
<li>סכומים ותעריפים שהטקסט אומר שנקבעים במקום אחר (חוזרי שכר, האוצר) הם קלט, לא מספר שהומצא.</li>
</ul>
<h2>מה הקידוד מוסיף</h2>
<p>כשהטקסט אינו מתיישב עם עצמו, הממצא נרשם ב<a href="findings.html">ממצאי L4</a> עם
<code>#ASSERT</code> שמראה אותו, והקידוד אומר במפורש איזו קריאה הוא נוקט.</p>
<p>הקוד ב־<a href="{REPO}">{esc(REPO.split('github.com/')[1])}</a>.</p>"""
    return page("about.html", f"על האתר — {TITLE}", body, tab="about")


def build() -> int:
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "assets").mkdir(parents=True)
    for f in ASSETS.iterdir():
        shutil.copy(f, OUT / "assets" / f.name)
    all_views: dict[str, list[SectionView]] = {}
    for doc in DOCUMENTS:
        views = [build_view(doc, s) for s in akn.sections(doc)]
        all_views[doc] = views
        d = OUT / doc.removesuffix(".xml")
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(document_page(doc, views), encoding="utf-8")
        for i, v in enumerate(views):
            pn = [(views[i - 1] if i else None, "prev", "→"),
                  (views[i + 1] if i + 1 < len(views) else None, "next", "←")]
            (OUT / v.href).write_text(section_page(v, pn), encoding="utf-8")
            if v.src is not None:
                (OUT / v.href.replace(".html", ".render.html")).write_text(
                    render_page(v), encoding="utf-8")
    flat = [v for vs in all_views.values() for v in vs]
    by_file = {str(v.l4.relative_to(ROOT)): v for v in flat if v.l4}
    key_to_view = {}
    for v in flat:
        for k in v.section.keys():
            key_to_view.setdefault(k, v)
    (OUT / "index.html").write_text(index_page(all_views), encoding="utf-8")
    (OUT / "findings.html").write_text(findings_page(load_findings(), by_file, key_to_view), encoding="utf-8")
    (OUT / "coverage.html").write_text(coverage_page(all_views), encoding="utf-8")
    (OUT / "sic.html").write_text(sic_page(all_views), encoding="utf-8")
    (OUT / "diagnostics.html").write_text(diagnostics_page(flat), encoding="utf-8")
    (OUT / "about.html").write_text(about_page(), encoding="utf-8")
    (OUT / ".nojekyll").write_text("")
    done = sum(v.status == "done" for v in flat)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(flat)} sections, {done} encoded")
    return 0


if __name__ == "__main__":
    sys.exit(build())
