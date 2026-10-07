"""Build the static site: the corpus text beside its L4, document by document.

    python3 tools/build_site.py      # after tools/l4run.py; writes build/site/

Pages, laid out like the corpus they encode:

  index.html                       the collections, and how much is encoded
  takanon/<doc>/index.html         a document's chapters and sections
  takanon/<doc>/<num>.html         one section: text | L4, row by row
  takanon/<doc>/<num>.render.html  L4's own rendering of that section
  findings.html  findings.json     errors in the LAW that encoding exposed
  coverage.html                    how much of the corpus is encoded
  diagnostics.html                 what the L4 checker reported, file by file
  index.json                       every L4 segment with its corpus address

The site is in English; the corpus's text is shown as it is, in Hebrew.
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
FINDINGS = ROOT / "findings"           # one <section>.toml per section
MANIFEST = ROOT / "corpus" / "manifest.json"
MANIFEST_DOCS = json.loads(MANIFEST.read_text(encoding="utf-8"))["documents"]
CORPUS_SITE = "https://morimovilimcatala.github.io/ofek-hadash-corpus"
REPO = "https://github.com/morimovilimcatala/ofek-hadash-l4"
TITLE = "Ofek Hadash in L4"

# what is encoded, by the corpus document it encodes; the l4/ directory
# mirrors the corpus's akn/ path without the extension
# the collections in work: every document of them, by the corpus's own list
WORK_COLLECTIONS = ("takanon", "circulars", "circulars-sachar", "circulars-tnai-sherut")


def _documents() -> list[str]:
    docs = json.loads((Path(__file__).resolve().parent.parent / "corpus" / "manifest.json")
                      .read_text(encoding="utf-8"))["documents"]
    out = ["takanon/takanon-sherut-ovdei-horaa.xml"]
    out += sorted(d["path"] for d in docs
                  if d["collection"] in WORK_COLLECTIONS[1:])
    return out


DOCUMENTS = _documents()

# the corpus's collections, so the reader sees what is not started as well
COLLECTIONS = [
    ("takanon", "Takanon — teaching staff service regulations"),
    ("agreements", "Collective agreements"),
    ("circulars", "Circulars"),
    ("circulars-sachar", "Salary circulars"),
    ("circulars-tnai-sherut", "Conditions-of-service circulars"),
    ("letters", "Letters"),
    ("takam", "Takshir (civil service regulations)"),
    ("tables", "Tables"),
]

# The two labels every finding carries (MMS-415). KIND is what is wrong with
# the law; STAGE is what caught it. The tool's message is the evidence, not
# the category: a gap is a gap whether a warning or an example exposed it.
KINDS = {
    "gap": ("Gap", "a case the instrument does not decide"),
    "overlap": ("Overlap", "two rules for one case, or a rule that can never apply"),
    "contradiction": ("Contradiction", "what the instrument states and its own rule does not produce, or two clauses that disagree"),
    "undefined-term": ("Undefined term", "a term used and never defined"),
    "broken-reference": ("Broken reference", "a clause, annex or instrument the text points to that is not there"),
    "ambiguity": ("Ambiguity", "wording that reads two ways"),
}
STAGES = {
    "writing": ("Writing the rule", "the text cannot be written down as it stands"),
    "compiling": ("Compiling", "the rules do not fit together"),
    "examples": ("Running the law's examples", "the rules contradict a table or example the instrument itself states"),
    "verification": ("Formal verification", "a flaw no single example shows"),
}
REVIEW = {
    "unreviewed": "not yet seen by the lawyer",
    "lawyer-seen": "seen by the lawyer",
    "lawyer-agreed": "the lawyer agrees",
    "lawyer-disagreed": "the lawyer disagrees",
}

esc = html.escape


def he(text: str) -> str:
    """Corpus text inside English chrome."""
    return f'<span lang="he" dir="rtl">{esc(text)}</span>'


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
    appendix: list = field(default_factory=list)   # code no paragraph is cited by

    @property
    def dir(self) -> str:
        return self.doc.removesuffix(".xml")

    @property
    def whole(self) -> bool:
        """A document that is one section (a circular), not a takanon section."""
        return akn.is_whole(self.doc)

    @property
    def page(self) -> str:
        """The document's one page; a section is an anchor on it, named by
        the same eId the corpus site uses, so links between the two match."""
        return f"{self.dir}.html"

    @property
    def href(self) -> str:
        return self.page if self.whole else f"{self.page}#{self.section.eid}"

    @property
    def old_href(self) -> str:
        """Where the section had a page of its own; a redirect now."""
        return f"{self.dir}/{self.section.num}.html"

    @property
    def render_href(self) -> str:
        return f"{self.dir}.render.html" if self.whole else f"{self.dir}/{self.section.num}.render.html"

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

    @property
    def problems(self) -> list[dict]:
        return [d for d in self.run.get("diagnostics", [])
                if d.get("severity") in ("error", "warning")]


def l4_path(doc: str, num: str) -> Path:
    if akn.is_whole(doc):
        return ROOT / "l4" / f"{doc.removesuffix('.xml')}.l4"
    return ROOT / "l4" / doc.removesuffix(".xml") / f"{num}.l4"


def under(key: str, anc: str) -> bool:
    return key == anc or key.startswith(anc + "__") or key.startswith(anc + "/")


def line_of(rng) -> int | None:
    """The first line of a range as `l4 run --json` prints it
    ("1.7.l4:93:1-49" for a result, "71:5-71:8" for a diagnostic)."""
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
    import l4run
    outs = l4run.outputs(v.l4)
    run = outs["run"]
    v.run = json.loads(run.read_text(encoding="utf-8")) if run.exists() else {
        "ok": False, "results": [], "diagnostics": [
            {"severity": "error", "message": "not run: tools/l4run.py has not been run on this file"}]}
    rend = outs["render"]
    v.render = rend.read_text(encoding="utf-8") if rend.exists() else ""
    for res in v.run.get("results", []):
        s = l4src.segment_at(v.src, line_of(res.get("range")) or -1)
        if s:
            s.results.append(res)
    for d in v.problems:
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
        if not s.keys:
            v.appendix.append(s)
            continue
        first = next((k for k in s.keys if k in where), None)
        if first is None or any(k not in where for k in s.keys):
            v.unplaced.append(s)
            if first is None:
                continue
        v.anchors.setdefault(where[first].key, []).append(s)
        for k in s.keys:
            for r in rows:
                if under(r.key, k) or k in r.aliases:
                    v.covered.add(r.key)
                    if v.kind_of.get(r.key) != "rule":
                        v.kind_of[r.key] = "note" if s.note_only else "rule"
    return v


def citations(sec: akn.Section) -> dict[str, str]:
    """Row key -> the clause as a reader cites it: §1.7.2ב, not an eId."""
    out, stack = {}, []
    for r in sec.rows:
        stack = stack[:r.depth]
        stack += [""] * (r.depth - len(stack))
        num = r.num.strip().rstrip(".)").lstrip("(")
        # a label that restates the section's own number adds nothing
        stack.append("" if r.num.startswith(sec.num) else num)
        parts = [p for p in stack if p]
        if sec.chapter_eid:
            cite = "§" + sec.num + "".join(("." if p.isdigit() else "") + p for p in parts)
        else:   # a whole document: its clauses are cited from its own numbering
            cite = "§" + "".join(("." if p.isdigit() and i else "") + p for i, p in enumerate(parts))
            if cite == "§":
                cite = {"preamble": "front matter", "conclusions": "sign-off",
                        "attachments": "attachments"}.get(r.key.split("/")[0].split("__")[0], "§")
        for k in [r.key, *r.aliases]:
            out.setdefault(k, cite)
    for k in list(out):
        last = k.rsplit("/", 1)[-1] if "/" in k else ""
        if re.fullmatch(r"p\d+", last):
            out[k] = out[k] + " ¶" + last[1:]
        elif re.fullmatch(r"t\d+", last):
            out[k] = out[k] + " table " + last[1:]
    return out


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
        self.lines = [0]
        for line in text.split("\n"):
            self.lines.append(self.lines[-1] + len(line) + 1)
        self.depth, self.start, self.term, self.in_term = 0, None, None, False
        self.feed(text)

    def _offset(self) -> int:
        line, col = self.getpos()
        return self.lines[line - 1] + col

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "li":
            if self.start is None and "clause" in (a.get("class") or "").split():
                self.start, self.depth, self.term = self._offset(), 1, ""
            elif self.start is not None:
                self.depth += 1
        if (self.start is not None and tag == "span" and a.get("class") == "term"
                and self.term == ""):
            self.in_term = True

    def handle_endtag(self, tag):
        if tag == "span":
            self.in_term = False
        if tag == "li" and self.start is not None:
            self.depth -= 1
            if self.depth == 0:
                end = self.text.find(">", self._offset()) + 1
                self.out.setdefault(_norm(self.term), []).append(self.text[self.start:end])
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
    return "../" * here.count("/") + target


def page(here: str, title: str, body: str, *, tab: str = "", desc: str = "",
         wide: bool = False) -> str:
    nav = [("index.html", "Documents", "docs"),
           ("findings.html", "Findings", "findings"),
           ("coverage.html", "Coverage", "coverage"),
           ("diagnostics.html", "Checks", "diagnostics"),
           ("about.html", "About", "about")]
    links = "".join(
        f'<a href="{rel(h, here)}"{" aria-current=page" if k == tab else ""}>{esc(t)}</a>'
        for h, t, k in nav)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc or title)}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Frank+Ruhl+Libre:wght@400;500;700&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap">
<link rel="icon" href="{rel('assets/favicon.svg', here)}" type="image/svg+xml">
<meta name="theme-color" content="#f6f4ef" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#14130f" media="(prefers-color-scheme: dark)">
<link rel="stylesheet" href="{rel('assets/site.css', here)}">
<link rel="stylesheet" href="{rel('assets/l4-render.css', here)}">
<script defer src="{rel('assets/site.js', here)}"></script>
</head>
<body>
<header class="top">
  <div class="top-in">
    <a class="brand" href="{rel('index.html', here)}"><span class="mark">L4</span><span>Ofek Hadash</span></a>
    <nav class="tabs-top">{links}</nav>
  </div>
</header>
<main class="{'wide' if wide else ''}">
{body}
</main>
<footer class="foot">
  <div>Text: the <a href="{CORPUS_SITE}/">Ofek Hadash corpus</a>, as published. Code:
  <a href="{REPO}">{esc(REPO.split('github.com/')[1])}</a>.</div>
  <div>The encoding is a reading of the text; it does not replace it.</div>
</footer>
</body>
</html>
"""


STATUS = {"done": "encoded", "partial": "partly encoded", "todo": "not encoded yet"}


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
        body = "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in row) + "</tr>" for row in r.cells)
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


def segment_html(v: SectionView, s: l4src.Segment, rendered: dict[int, str]) -> str:
    gh = f"{REPO}/blob/main/{v.l4.relative_to(ROOT)}#L{s.start}-L{s.end}"
    if s.note_only:
        return (f'<div class="seg note"><span class="note-label">no rule</span>'
                f'<span class="note-text">{esc(s.note)}</span></div>')
    others = "".join(f'<a class="also" href="#{esc(k)}">also covers <bdi dir="ltr">{esc(citations(v.section).get(k, k))}</bdi></a>'
                     for k in s.keys[1:])
    r = rendered.get(s.start)
    rend = (f'<div class="view rendered l4-doc" hidden>{r}</div>' if r else
            '<div class="view rendered empty" hidden>No rendering of its own: this is a type, '
            'a test, or part of a rule rendered beside another paragraph.</div>')
    notes = "".join(f'<div class="seg note"><span class="note-label">no rule</span>'
                    f'<span class="note-text">{esc(n)}</span></div>' for n in l4src.lead_notes(s.lines))
    return (f'{notes}<div class="seg">'
            f'<div class="view code-view">{l4src.numbered_html(l4src.for_reading(s.lines, s.start))}</div>'
            f'{rend}{results_html(s)}'
            f'<div class="seg-foot">{others}<a class="gh" href="{gh}">source L{s.start}–{s.end}</a></div>'
            f'</div>')


# (document, row key) -> findings. Keyed by DOCUMENT as well as row: every
# circular has an `art_1` and a `preamble`, so a key alone names a row in
# 210 documents at once.
FINDINGS_BY_KEY: dict[tuple[str, str], list[dict]] = {}


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
    l4/<doc>/<section>.l4 for a sectioned document, l4/<doc>.l4 for a whole one."""
    rel_ = Path(f["l4"]).relative_to("l4")
    parent = rel_.parent.as_posix() + ".xml"
    return parent if (akn.CORPUS / parent).exists() else rel_.with_suffix(".xml").as_posix()


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
    links = [f'<a href="{corpus}">corpus ↗</a>']
    if v.l4:
        links += [f'<a href="{REPO}/blob/main/{v.l4.relative_to(ROOT)}">source ↗</a>',
                  f'<a href="{rel(v.render_href, here)}">as prose</a>']
    stats = ""
    if v.src is not None:
        t = tally(v)
        checks = sum(len(s.results) for s in v.src.segments)
        stats = (f'<div class="stats">'
                 f'<span class="{"okay" if v.ok else "notok"}">{"✓ checks clean" if v.ok else "✗ l4 reports errors"}</span>'
                 f'<span><b>{t["rule"]}</b> with a rule</span>'
                 f'<span><b>{t["note"]}</b> with none</span>'
                 + (f'<span class="notok"><b>{t["missing"]}</b> not cited</span>' if t["missing"] else "")
                 + f'<span><b>{checks}</b> checks</span>'
                 + (f'<span class="fcount"><b>{len(found)}</b> finding{"s" * (len(found) != 1)}</span>' if found else "")
                 + '</div>')
    head = (f'<header class="tsec-head">'
            + ("" if headless else
               f'<div class="title-row"><h2 lang="he" dir="rtl"><a class="anchor" href="#{esc(sec.eid)}">'
               f'<span class="secnum" dir="ltr">§{esc(sec.num)}</span>{esc(sec.heading)}</a></h2>'
               f'<div class="tsec-meta">{badge(v.status)}<span class="links">{"".join(links)}</span></div></div>')
            + f'{stats}</header>')
    if found:
        head += ('<div class="sec-findings"><h3>Findings in this section</h3><ul>'
                 + "".join(f'<li><a href="{rel("findings.html", here)}#{esc(f["id"])}"><span class="kind-tag {f["kind"]}">'
                           f'{esc(KINDS[f["kind"]][0])}</span>{esc(f["title"])}</a></li>' for f in found)
                 + "</ul></div>")

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

    rendered = rendered_for(v)
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
        code = "".join(segment_html(v, s, rendered) for s in segs)
        if "gap" in cls:
            code = '<div class="seg missing">Not encoded — no rule cites this paragraph.</div>'
        alias = "".join(f'<span id="{esc(a)}"></span>' for a in r.aliases)
        fl = flags(r)
        out.append(f'<div class="{" ".join(cls)}" id="{esc(r.key)}">'
                   f'<div class="txt" lang="he" dir="rtl">{alias}{text_cell(r)}'
                   f'{f"<div class=flags dir=ltr>{fl}</div>" if fl else ""}</div>'
                   f'<div class="l4">{code}</div></div>')
    unplaced = ""
    if v.unplaced:
        unplaced = ('<div class="banner bad">Code cites keys that are not in this section: ' +
                    ", ".join(esc(" ".join(s.keys)) for s in v.unplaced) + "</div>")
    appendix = ""
    if v.appendix:
        appendix = ('<details class="appendix"><summary>Shared definitions, examples and checks '
                    f'<span class="meta">({len(v.appendix)})</span></summary>'
                    + "".join(segment_html(v, s, rendered) for s in v.appendix) + '</details>')
    return (f'<section class="tsec" id="{esc(sec.eid)}">{head}{unplaced}'
            f'<div class="grid">{"".join(out)}</div>{appendix}</section>')


def redirect_page(here: str, target: str, title: str) -> str:
    """A page that moved: sends the reader (and a search engine) on."""
    to = rel(target, here)
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{esc(title)}</title>'
            f'<meta http-equiv="refresh" content="0; url={esc(to)}"><link rel="canonical" href="{esc(to)}">'
            f'</head><body><p>Moved to <a href="{esc(to)}">{esc(title)}</a>.</p></body></html>')


def render_page(v: SectionView) -> str:
    """L4's own rendering, framed by the site so it is navigable."""
    m = re.search(r"<body[^>]*>(.*)</body>", v.render, re.S)
    inner = m.group(1) if m else v.render
    here = v.render_href
    body = (f'<header class="sec-head"><nav class="crumbs"><a href="{rel(v.href, here)}">← {"" if v.whole else "§" + esc(v.section.num) + " "}side by side</a></nav>'
            f'<div class="title-row"><h1 lang="he" dir="rtl">'
            + ("" if v.whole else f'<span class="secnum" dir="ltr">§{esc(v.section.num)}</span>')
            + f'{esc(v.section.heading)}</h1></div>'
            f'<p class="lede">The whole {"document" if v.whole else "section"} as <code>l4 render</code> writes the rules back out as prose.</p></header>'
            f'<div class="render-frame">{inner or "<p>l4 render produced nothing for this file.</p>"}</div>')
    return page(here, f"§{v.section.num} — l4 render", body, tab="docs")


def progress(vs: list[SectionView]) -> str:
    """A thin bar of the paragraphs by what the L4 does with them, and a
    legend saying so: unlabelled, a green-and-grey bar beside "110 of 110"
    reads as 77% done when it means 77% carry a rule."""
    t = {"rule": 0, "note": 0, "missing": 0, "todo": 0}
    for v in vs:
        if v.src is None:
            t["todo"] += len(v.text_rows)
        else:
            for k, n in tally(v).items():
                t[k] += n
    total = max(sum(t.values()), 1)
    names = {"rule": "carry a rule", "note": "read, no rule", "missing": "not cited", "todo": "not encoded yet"}
    pct = {k: round(t[k] * 100 / total) for k in t}
    legend = " · ".join(f'<span><i class="sw {k}"></i>{pct[k]}% {names[k]}</span>'
                        for k in ("rule", "note", "missing", "todo") if t[k])
    return ('<span class="pbar">' + "".join(
        f'<i class="{k}" style="width:{t[k] * 100 / total:.3f}%"></i>' for k in ("rule", "note", "missing") if t[k])
        + f'</span><span class="plegend">Paragraphs: {legend}</span>')


def document_page(doc: str, views: list[SectionView]) -> str:
    """The whole document on one page, as the corpus publishes it: a contents
    rail, then every section with its text beside its L4."""
    here = f"{doc.removesuffix('.xml')}.html"
    chapters: dict[str, list[SectionView]] = {}
    for v in views:
        chapters.setdefault(v.section.chapter_eid, []).append(v)
    done = sum(v.status == "done" for v in views)
    part = sum(v.status == "partial" for v in views)
    nfind = len({f["id"] for v in views for r in v.section.rows for f in row_findings(v, r)})
    toc = []
    for vs in chapters.values():
        s0 = vs[0].section
        lis = "".join(
            f'<li class="{v.status}"><a href="#{esc(v.section.eid)}">{dot(v.status)}'
            f'<span class="secnum" dir="ltr">{esc(v.section.num)}</span>'
            f'<span class="sh" lang="he">{esc(v.section.heading)}</span></a></li>' for v in vs)
        toc.append(f'<li class="toc-ch"><a href="#{esc(s0.chapter_eid)}" class="toc-chead" lang="he">'
                   f'פרק {esc(s0.chapter_num)} · {esc(s0.chapter_heading)}</a><ul>{lis}</ul></li>')
    body = []
    for vs in chapters.values():
        s0 = vs[0].section
        n_done = sum(v.status == "done" for v in vs)
        blocks = "".join(section_block(v, here) for v in vs)
        # a chapter the corpus holds as one block is its own section; it
        # takes the chapter's anchor itself
        chap_id = "" if any(v.section.eid == s0.chapter_eid for v in vs) else f' id="{esc(s0.chapter_eid)}"'
        body.append(f'<div class="chapter-band"{chap_id}><h2 lang="he" dir="rtl">פרק {esc(s0.chapter_num)} · '
                    f'{esc(s0.chapter_heading)}</h2><span class="ccount">{n_done} of {len(vs)} encoded</span></div>'
                    + blocks)
    switch = ('<div class="switch" role="group" aria-label="How to show the L4">'
              '<button type="button" data-view="code-view" aria-pressed="true">Code</button>'
              '<button type="button" data-view="rendered" aria-pressed="false">As prose</button></div>')
    head = (f'<header class="sec-head doc-head"><nav class="crumbs"><a href="{rel("index.html", here)}">Documents</a></nav>'
            f'<div class="title-row"><h1 lang="he" dir="rtl">{esc(akn.title(doc))}</h1></div>'
            f'<p class="lede">The teaching staff service regulations of the Ministry of Education, whole, '
            f'as the corpus publishes them: {len(views)} sections in {len(chapters)} chapters. Each paragraph '
            f'of the text (right) sits beside the L4 that encodes it (left).</p>'
            f'<div class="stats"><span><b>{done}</b> of {len(views)} sections encoded</span>'
            + (f'<span><b>{part}</b> partly</span>' if part else "")
            + f'<a class="fcount" href="{rel("findings.html", here)}"><b>{nfind}</b> findings</a>'
            f'<a href="{CORPUS_SITE}/{doc.removesuffix(".xml")}.html">In the corpus ↗</a></div>'
            f'{progress(views)}</header>')
    toolbar = (f'<div class="doc-toolbar"><span class="tb-label">L4 shown as</span>{switch}'
               f'<span class="tb-where" aria-live="polite"></span>'
               f'<span class="tb-cols"><span>L4</span><span>Text</span></span></div>')
    page_body = (head + '<div class="doc-layout">'
                 f'<aside class="toc" aria-label="Contents"><details open><summary>Contents</summary>'
                 f'<ul dir="rtl">{"".join(toc)}</ul></details></aside>'
                 f'<div class="doc-main">{toolbar}{"".join(body)}</div></div>')
    return page(here, f"{akn.title(doc)} — {TITLE}", page_body, tab="docs", wide=True,
                desc="The teaching staff service regulations, whole, each paragraph beside its L4 encoding")


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
    links = [f'<a href="{corpus}">In the corpus ↗</a>']
    if v.l4:
        links += [f'<a href="{REPO}/blob/main/{v.l4.relative_to(ROOT)}">Source ↗</a>',
                  f'<a href="{rel(v.render_href, here)}">Whole document as prose</a>']
    switch = ('<div class="switch" role="group" aria-label="How to show the L4">'
              '<button type="button" data-view="code-view" aria-pressed="true">Code</button>'
              '<button type="button" data-view="rendered" aria-pressed="false">As prose</button></div>')
    head = (f'<header class="sec-head"><nav class="crumbs"><a href="{rel("index.html", here)}">Documents</a><span>/</span>'
            f'<a href="{rel(coll + ".html", here)}">{esc(coll_name(coll))}</a></nav>'
            f'<div class="title-row"><h1 lang="he" dir="rtl">{esc(v.section.heading)}</h1>{badge(v.status)}</div>'
            f'<p class="meta"><span class="docid" dir="ltr">{esc(v.section.num)}</span>'
            + (f' · {esc(meta["date"])}' if meta.get("date") else "") + '</p>'
            f'<div class="links">{"".join(links)}</div></header>')
    toolbar = (f'<div class="doc-toolbar"><span class="tb-label">L4 shown as</span>{switch}'
               f'<span class="tb-where"></span><span class="tb-cols"></span></div>')
    body = head + toolbar + section_block(v, here, headless=True)
    return page(here, f"{v.section.heading} — {TITLE}", body, tab="docs", wide=True,
                desc=f"{v.section.heading}: the circular's text beside its L4 encoding")


def school_year(doc: str) -> str:
    return Path(doc).stem.split("_")[0][:7]


def collection_page(coll: str, views: list[SectionView]) -> str:
    """Every document of a collection, by year, newest first."""
    here = f"{coll}.html"
    by_year: dict[str, list[SectionView]] = {}
    for v in views:
        by_year.setdefault(school_year(v.doc), []).append(v)
    done = sum(v.status == "done" for v in views)
    parts = [f'<header class="sec-head"><nav class="crumbs"><a href="index.html">Documents</a></nav>'
             f'<div class="title-row"><h1>{esc(coll_name(coll))}</h1></div>'
             f'<div class="stats"><span><b>{done}</b> of {len(views)} documents encoded</span>'
             f'<a href="{CORPUS_SITE}/">In the corpus ↗</a></div>{progress(views)}</header>']
    for year in sorted(by_year, reverse=True):
        vs = sorted(by_year[year], key=lambda v: v.doc)
        lis = "".join(
            f'<li class="{v.status}"><a href="{rel(v.href, here)}">{dot(v.status)}'
            f'<span class="secnum" dir="ltr">{esc(Path(v.doc).stem.split("_", 1)[-1])}</span>'
            f'<span class="sh" lang="he">{esc(v.section.heading)}</span></a></li>' for v in vs)
        parts.append(f'<section class="chapter" dir="rtl"><div class="chapter-head"><h2 dir="ltr">{esc(year)}</h2>'
                     f'<span class="ccount" dir="ltr">{sum(v.status == "done" for v in vs)} of {len(vs)} encoded</span></div>'
                     f'<ul class="secs docs">{lis}</ul></section>')
    return page(here, f"{coll_name(coll)} — {TITLE}", "".join(parts), tab="docs")


def index_page(all_views: dict[str, list[SectionView]], findings: list[dict]) -> str:
    flat = [v for vs in all_views.values() for v in vs]
    done = sum(v.status == "done" for v in flat)
    rules = sum(tally(v)["rule"] for v in flat if v.src is not None)
    cards = []
    for coll, name in COLLECTIONS:
        docs = [d for d in DOCUMENTS if d.startswith(coll + "/")]
        if not docs:
            cards.append(f'<li class="coll todo"><span class="cname">{esc(name)}</span>'
                         f'<span class="cstate">not started</span></li>')
            continue
        if coll == "takanon":
            for d in docs:
                vs = all_views[d]
                n = sum(v.status == "done" for v in vs)
                cards.append(f'<li class="coll live wide"><a href="{d.removesuffix(".xml")}.html">'
                             f'<span class="cname">{esc(name)}</span>'
                             f'<span class="ctitle" lang="he" dir="rtl">{esc(akn.title(d))}</span>'
                             f'{progress(vs)}<span class="cstate">{n} of {len(vs)} sections encoded</span></a></li>')
            continue
        vs = [v for d in docs for v in all_views[d]]
        n = sum(v.status == "done" for v in vs)
        cards.append(f'<li class="coll live"><a href="{coll}.html">'
                     f'<span class="cname">{esc(name)}</span>'
                     f'{progress(vs)}<span class="cstate">{n} of {len(vs)} documents encoded</span></a></li>')
    body = (f'<section class="hero"><h1>The rules of Israeli teachers\' employment, '
            f'written as code beside the text.</h1>'
            f'<p class="lede">Each section of the <a href="{CORPUS_SITE}/">Ofek Hadash corpus</a> appears '
            f'twice, paragraph by paragraph: the Hebrew text, and the rules read from it in '
            f'<a href="https://legalese.com/l4/">L4</a> — a language for law whose compiler checks every rule, '
            f'runs every example and can write the rules back out as prose. Everything is encoded, not only pay: '
            f'who is entitled, under what conditions, who must do what and by when.</p>'
            f'<p class="lede">Writing law as code exposes where it does not hold together. Those places are the '
            f'<a href="findings.html">findings</a>: each one shown, in code, to be in the text.</p>'
            f'<div class="kpis"><div><b>{done}</b><span>sections and documents encoded</span></div>'
            f'<div><b>{rules}</b><span>paragraphs with a rule</span></div>'
            f'<div><a href="findings.html"><b>{len(findings)}</b><span>findings in the text</span></a></div></div>'
            f'</section>'
            f'<h2 class="sect">Collections</h2><ul class="colls">{"".join(cards)}</ul>')
    return page("index.html", TITLE, body, tab="docs",
                desc="The teaching staff service regulations beside their L4 encoding, section by section")


def load_findings() -> list[dict]:
    out = []
    for f in sorted(FINDINGS.rglob("*.toml"), key=lambda p: [int(x) if x.isdigit() else x
                                                            for x in re.split(r"(\d+)", p.stem)]):
        out += tomllib.loads(f.read_text(encoding="utf-8")).get("finding", [])
    return out


def address(doc: str, key: str) -> str:
    """A corpus address (MMS-414): `<akn path without .xml>#<eId>`, with
    `/p<N>` kept for a paragraph the corpus gives no eId of its own."""
    return f"{doc.removesuffix('.xml')}#{key}"


def evidence_result(f: dict, views_by_file: dict[str, SectionView]) -> dict:
    """Where the finding's #ASSERT is, and what `l4 run` said about it."""
    v = views_by_file.get(f.get("l4", ""))
    out = {"line": None, "url": "", "held": None, "messages": []}
    if v is None or v.src is None:
        return out
    ev = f.get("evidence", "")
    for n, line in enumerate(v.src.lines, 1):
        if line.lstrip().startswith("#ASSERT") and ev in line:
            out["line"], out["url"] = n, f"{REPO}/blob/main/{f['l4']}#L{n}"
            for res in v.run.get("results", []):
                if line_of(res.get("range")) == n:
                    val = res.get("value")
                    out["messages"].append(f"{line.strip()}  →  {val}")
                    out["held"] = str(val).strip().lower() == "true"
            break
    return out


def findings_page(findings, views_by_file, key_to_view) -> str:
    counts: dict[tuple[str, str], int] = {}
    for f in findings:
        counts[(f["kind"], f["stage"])] = counts.get((f["kind"], f["stage"]), 0) + 1
    matrix = ('<div class="scroll-x"><table class="diag matrix"><thead><tr><th>kind \\ stage</th>'
              + "".join(f'<th title="{esc(d)}">{esc(t)}</th>' for t, d in STAGES.values())
              + "</tr></thead><tbody>"
              + "".join(f'<tr><th title="{esc(d)}"><a href="#k-{k}">{esc(t)}</a></th>'
                        + "".join(f"<td>{counts.get((k, st), '')}</td>" for st in STAGES) + "</tr>"
                        for k, (t, d) in KINDS.items())
              + "</tbody></table></div>")
    by_id = {f["id"]: f for f in findings}
    groups = []
    for kind, (label, gloss) in KINDS.items():
        cards = []
        for f in (x for x in findings if x["kind"] == kind):
            ev = evidence_result(f, views_by_file)
            where = []
            for k in f.get("keys", []):
                v = key_to_view.get((finding_doc(f), k))
                if v:
                    where.append(f'<a href="{v.href}#{esc(k)}"><bdi dir="ltr">{esc(citations(v.section).get(k, "§" + v.section.num))}</bdi></a>')
            state = ('<span class="okay">the #ASSERT holds: the flaw is still in the text</span>' if ev["held"] else
                     '<span class="notok">the evidence does not hold — see Diagnostics</span>')
            deps = "".join(f'<a href="#{esc(d)}">{esc(d)}</a> ' for d in f.get("depends_on", []) if d in by_id)
            stage, sgloss = STAGES[f["stage"]]
            quote = (f'<blockquote lang="he" dir="rtl">{esc(f["quote"])}</blockquote>' if f.get("quote") else "")
            cards.append(
                f'<article class="finding" id="{esc(f["id"])}">'
                f'<h3><span class="fid">{esc(f["id"])}</span> {esc(f["title"])}</h3>'
                f'<p class="fmeta"><span class="stage" title="{esc(sgloss)}">caught {esc(stage.lower())}</span> · '
                f'{" · ".join(where)}</p>{quote}'
                f'<div class="fbody">{"".join(f"<p>{esc(p)}</p>" for p in f["body"].strip().split(chr(10) + chr(10)))}</div>'
                f'<p class="reading"><strong>Reading the encoding adopts:</strong> {esc(f["reading"])}</p>'
                + (f'<p class="deps">Depends on the readings of: {deps}</p>' if deps else "")
                + (f'<p class="ev"><a href="{ev["url"]}">The evidence in L4</a> · {state}</p>'
                   + "".join(f'<pre class="msg">{esc(m)}</pre>' for m in ev["messages"])
                   if ev["url"] else "")
                + f'<p class="who">Read by {esc(f["read_by"])} · {esc(REVIEW[f["review"]])}</p>'
                + "</article>")
        if cards:
            groups.append(f'<section id="k-{kind}"><h2>{esc(label)} <small>— {esc(gloss)}</small></h2>{"".join(cards)}</section>')
    intro = ('<h1>L4 findings</h1><p class="lede">What the RULES get wrong when they are written down '
             'formally — not what a page prints wrong (a typo the corpus has corrected is taken '
             'here as corrected). Every finding carries two labels: its '
             '<strong>kind</strong>, what is wrong with the law, and its <strong>stage</strong>, what caught it. '
             'One row per flaw, not per message. Each rests on an <code>#ASSERT</code> in the code that holds '
             'while the flaw is in the text; if the text is ever corrected, the check fails and the finding '
             'is stale. A finding is a legal reading, so it says whose reading it is and whether the lawyer '
             'has seen it.</p>'
             '<p><a href="findings.json">findings.json</a> — the same findings for machines, with corpus addresses.</p>')
    body = intro + matrix + ("".join(groups) or '<p class="empty">No findings yet.</p>')
    return page("findings.html", f"L4 findings — {TITLE}", body, tab="findings")


def findings_json(findings, views_by_file, key_to_view) -> str:
    rows = []
    for f in findings:
        ev = evidence_result(f, views_by_file)
        rows.append({
            "id": f["id"], "kind": f["kind"], "stage": f["stage"],
            "addresses": [address(finding_doc(f), k) for k in f["keys"] if (finding_doc(f), k) in key_to_view],
            "statement": f["title"], "body": f["body"].strip(), "reading": f["reading"],
            "quote": f.get("quote"), "depends_on": f.get("depends_on", []),
            "l4": {"file": f["l4"], "line": ev["line"], "evidence": f["evidence"]},
            "messages": ev["messages"], "message_count": len(ev["messages"]),
            "evidence_holds": ev["held"],
            "read_by": f["read_by"], "review": f["review"],
        })
    return json.dumps({"source": REPO, "findings": rows}, ensure_ascii=False, indent=1)


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


def diagnostics_page(views: list[SectionView]) -> str:
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
        detail += "".join(f'<li>#ASSERT failed at line {line_of(r.get("range"))}</li>' for r in failed)
        detail += "".join(f'<li>code cites keys not in the section: <code>{esc(" ".join(s.keys))}</code></li>'
                          for s in v.unplaced)
        gaps = sum(1 for r in v.text_rows if r.key not in v.covered)
        rows.append(f'<tr><td><a href="{v.href}">§{esc(v.section.num)}</a></td>'
                    f'<td><code>{esc(str(v.l4.relative_to(ROOT)))}</code></td>'
                    f'<td class="{cls}">{"ok" if cls == "okay" else "error"}</td>'
                    f'<td>{len(asserts)}</td><td>{gaps}</td><td>{bad}</td></tr>'
                    + (f'<tr class="detail"><td colspan="6"><ul>{detail}</ul></td></tr>' if detail else ""))
    body = ('<h1>Diagnostics</h1><p class="lede">What the L4 compiler (<code>l4 run</code>) says about each '
            'file: type and syntax errors, and any <code>#ASSERT</code> that fails. "Paragraphs not cited" '
            'counts the paragraphs of the text that no code segment cites. On a healthy site the last two '
            'columns are zero.</p>'
            '<table class="diag"><thead><tr><th>section</th><th>file</th><th>state</th><th>#ASSERTs</th>'
            '<th>paragraphs not cited</th><th>problems</th></tr></thead><tbody>'
            + "".join(rows) + "</tbody></table>")
    return page("diagnostics.html", f"Diagnostics — {TITLE}", body, tab="diagnostics")


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
    head = (f'<h1>Coverage</h1>'
            f'<p class="lede">How much of the corpus is encoded in L4. The denominator is the corpus\'s own '
            f'document list — {len(manifest)} documents — not only what has been started. A document '
            f'divides into sections and a section into paragraphs; a paragraph is '
            f'<span class="sw rule"></span> encoded as a rule, <span class="sw note"></span> read and found '
            f'to carry no rule (a source list, an amendment note — with the reason), '
            f'<span class="sw missing"></span> in an encoded section but cited by no code, or '
            f'<span class="sw todo"></span> in a section not encoded yet.</p>'
            f'<div class="kpis">'
            f'<div><b>{n_docs_done}</b> / {len(manifest)}<span>documents fully encoded</span></div>'
            + (f'<div><b>{len(DOCUMENTS) - n_docs_done}</b><span>documents in progress</span></div>'
               if len(DOCUMENTS) > n_docs_done else "")
            + f'<div><b>{done}</b> / {len(flat)}<span>sections fully encoded</span></div>'
            f'<div><b>{part}</b><span>sections partly encoded</span></div>'
            f'<div><b>{t["rule"] + t["note"]}</b> / {paras}<span>paragraphs read</span></div>'
            f'<div><b>{t["rule"]}</b><span>paragraphs with a rule</span></div>'
            f'</div>')
    parts = [head]
    def cell(v: SectionView) -> str:
        n = max(len(v.text_rows), 1)
        name = v.section.num if not v.whole else Path(v.doc).stem
        if v.src is None:
            segs = '<i class="todo" style="flex:1"></i>'
            tip = f"{name} {v.section.heading}: not encoded ({len(v.text_rows)} paragraphs)"
        else:
            c = tally(v)
            segs = "".join(f'<i class="{k}" style="flex:{c[k]}"></i>'
                           for k in ("rule", "note", "missing") if c[k])
            tip = (f"{name} {v.section.heading}: {c['rule']} with a rule, "
                   f"{c['note']} with no rule, {c['missing']} not cited")
        return (f'<a class="cell" href="{v.href}" title="{esc(tip)}" style="flex:{n}">{segs}</a>')

    for doc, vs in all_views.items():
        if akn.is_whole(doc):
            continue
        parts.append(f'<h2 class="cov-doc"><a href="{doc.removesuffix(".xml")}.html">{he(akn.title(doc))}</a></h2>'
                     '<p class="meta">One strip per chapter, one cell per section, its width the section\'s '
                     'paragraphs. Hover for the counts; click to open.</p>')
        chapters: dict[str, list[SectionView]] = {}
        for v in vs:
            chapters.setdefault(v.section.chapter_eid, []).append(v)
        rows = []
        for cvs in chapters.values():
            s0 = cvs[0].section
            rows.append(f'<div class="strip-row"><div class="strip-name">Chapter <bdi>{esc(s0.chapter_num)}</bdi> · '
                        f'{he(s0.chapter_heading)}</div><div class="strip">{"".join(cell(v) for v in cvs)}</div></div>')
        parts.append(f'<div class="strips">{"".join(rows)}</div>')
    for coll in WORK_COLLECTIONS[1:]:
        cvs_all = [v for d, vs in all_views.items() if d.startswith(coll + "/") for v in vs]
        if not cvs_all:
            continue
        parts.append(f'<h2><a href="{coll}.html">{esc(coll_name(coll))}</a></h2>'
                     '<p class="meta">One strip per year, one cell per document, its width the document\'s '
                     'paragraphs.</p>')
        by_year: dict[str, list[SectionView]] = {}
        for v in cvs_all:
            by_year.setdefault(school_year(v.doc), []).append(v)
        rows = [f'<div class="strip-row"><div class="strip-name">{esc(y)}</div>'
                f'<div class="strip">{"".join(cell(v) for v in sorted(by_year[y], key=lambda v: v.doc))}</div></div>'
                for y in sorted(by_year)]
        parts.append(f'<div class="strips">{"".join(rows)}</div>')
    names = dict(COLLECTIONS)
    by_coll: dict[str, list[dict]] = {}
    for d in manifest:
        by_coll.setdefault(d["collection"], []).append(d)
    parts.append('<h2>The whole corpus, collection by collection</h2><div class="coll-table">')
    for coll, _ in COLLECTIONS:
        docs = by_coll.get(coll, [])
        if not docs:
            continue
        working = [d for d in docs if d["path"] in all_views]
        n_enc = sum(all(v.status == "done" for v in all_views[d["path"]]) for d in working)
        share = sum(sum(v.status == "done" for v in all_views[d["path"]]) / max(len(all_views[d["path"]]), 1)
                    for d in working) / len(docs)
        lis = "".join(
            f'<li class="{"work" if d["path"] in all_views else ""}">'
            + (f'<a href="{d["path"].removesuffix(".xml")}.html">{he(d["title"])}</a>'
               if d["path"] in all_views else
               f'<a href="{CORPUS_SITE}/{esc(d["path"].removesuffix(".xml"))}.html">{he(d["title"])}</a>')
            + f' <span class="date">{esc(d["date"] or "")}</span></li>'
            for d in sorted(docs, key=lambda d: (d["path"] not in all_views, d["date"] or "", d["path"])))
        parts.append(
            f'<details class="coll-row"><summary><span class="cname">{esc(names.get(coll, coll))}</span>'
            f'<span class="bar"><i class="rule" style="width:{share * 100:.2f}%"></i></span>'
            f'<span class="cnum">{n_enc} of {len(docs)} documents encoded'
            + (f', {len(working) - n_enc} in progress' if len(working) > n_enc else "")
            + '</span></summary>'
            f'<ul class="doclist">{lis}</ul></details>')
    parts.append("</div>")
    return page("coverage.html", f"Coverage — {TITLE}", "".join(parts), tab="coverage",
                desc="How much of the Ofek Hadash corpus is encoded in L4, document by document and section by section")


def about_page() -> str:
    body = f"""<h1>About</h1>
<p class="lede">This site sets the text of the Ofek Hadash corpus — the instruments that govern
Israeli teachers' employment — beside an encoding of it in L4, section by section.</p>
<h2>Reading a section page</h2>
<p>Each row of the table is one paragraph of the text. On the left, the text as the corpus
holds it; on the right, the rules encoded from it. The <em>l4 render</em> switch replaces the
code with the natural-language rendering <code>l4 render</code> produces from the same rules.
The results of the file's <code>#ASSERT</code>, <code>#EVAL</code> and <code>#TRACE</code>
directives sit under the code they test. A paragraph that carries no rule (a list of sources,
an amendment note) is marked <em>No rule here</em> with the reason; one that no code cites is
marked <em>Not encoded</em>.</p>
<h2>What the encoding takes as given</h2>
<ul>
<li>The text is the corpus's. A copy is kept in <code>corpus/</code> and never edited here.</li>
<li>An error in the printed page that the corpus has already settled — the corpus's
reading stands.</li>
<li>An amount the text says is set elsewhere (by the Treasury, in a circular) is an input,
never a number made up.</li>
</ul>
<h2>What the encoding adds</h2>
<p>Where the text does not hold together, the finding goes to <a href="findings.html">L4 findings</a>
with an <code>#ASSERT</code> that shows it, and the code says which reading it adopts.</p>
<h2>For machines</h2>
<p><a href="index.json">index.json</a> lists every L4 segment with the corpus address it encodes
(<code>&lt;document&gt;#&lt;eId&gt;</code>); <a href="findings.json">findings.json</a> lists the findings.</p>
<p>Source: <a href="{REPO}">{esc(REPO.split('github.com/')[1])}</a>.</p>"""
    return page("about.html", f"About — {TITLE}", body, tab="about")


def build() -> int:
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "assets").mkdir(parents=True)
    for f in ASSETS.iterdir():
        shutil.copy(f, OUT / "assets" / f.name)
    findings = load_findings()
    FINDINGS_BY_KEY.clear()
    for f in findings:
        for k in f.get("keys", []):
            FINDINGS_BY_KEY.setdefault((finding_doc(f), k), []).append(f)
    all_views: dict[str, list[SectionView]] = {}
    for doc in DOCUMENTS:
        views = [build_view(doc, s) for s in akn.sections(doc)]
        all_views[doc] = views
        d = OUT / doc.removesuffix(".xml")
        if akn.is_whole(doc):
            v = views[0]
            (OUT / v.page).parent.mkdir(parents=True, exist_ok=True)
            (OUT / v.page).write_text(single_page(doc, v), encoding="utf-8")
            if v.src is not None:
                (OUT / v.render_href).write_text(render_page(v), encoding="utf-8")
            continue
        d.mkdir(parents=True, exist_ok=True)
        (OUT / f"{doc.removesuffix('.xml')}.html").write_text(document_page(doc, views), encoding="utf-8")
        # the per-section pages and the chapter list this site had first
        # now send the reader to the anchor on the one page
        (d / "index.html").write_text(redirect_page(f"{doc.removesuffix('.xml')}/index.html",
                                                    f"{doc.removesuffix('.xml')}.html", akn.title(doc)), encoding="utf-8")
        for v in views:
            (OUT / v.old_href).write_text(redirect_page(v.old_href, v.href, f"§{v.section.num}"), encoding="utf-8")
            if v.src is not None:
                (OUT / v.render_href).write_text(render_page(v), encoding="utf-8")
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
    (OUT / "findings.json").write_text(findings_json(findings, by_file, key_to_view), encoding="utf-8")
    (OUT / "index.json").write_text(index_json(flat), encoding="utf-8")
    (OUT / "coverage.html").write_text(coverage_page(all_views), encoding="utf-8")
    (OUT / "diagnostics.html").write_text(diagnostics_page(flat), encoding="utf-8")
    (OUT / "about.html").write_text(about_page(), encoding="utf-8")
    (OUT / ".nojekyll").write_text("")
    done = sum(v.status == "done" for v in flat)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(flat)} sections, {done} encoded, {len(findings)} findings")
    return 0


if __name__ == "__main__":
    sys.exit(build())
