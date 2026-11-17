"""A section as the site shows it (SectionView): its text rows, its L4
segments, what cites what, and L4's own rendering and state graphs.
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

# ----------------------------------------------------------------- model

HEB_LATIN = akn.HEB_LATIN


def chapter_slug(num: str) -> str:
    """A chapter page's file name: "1א'" -> "chapter-1a". Not the bare
    number: a chapter that is one section ("9") has that number's redirect
    page already."""
    return "chapter-" + "".join(HEB_LATIN.get(c, c) for c in num if c.isalnum())


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
    covered_by: dict = field(default_factory=dict) # row key -> the row its segment sits beside
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
    def doc_page(self) -> str:
        """The document's own page: a circular's text | L4, or the takanon's
        contents."""
        return f"{self.dir}.html"

    @property
    def page(self) -> str:
        """The page the section is on: a circular's own page, or the takanon
        chapter that holds it (one page each: the whole takanon was 18MB).
        A section is an anchor there, named by the same eId the corpus site
        uses, so links between the two match."""
        if self.whole:
            return self.doc_page
        return f"{self.dir}/{chapter_slug(self.section.chapter_num or self.section.chapter_eid)}.html"

    @property
    def href(self) -> str:
        return self.page if self.whole else f"{self.page}#{self.section.eid}"

    @property
    def old_href(self) -> str:
        """Where the section had a page of its own; a redirect now."""
        return f"{self.dir}/{self.section.slug}.html"

    @property
    def render_href(self) -> str:
        return f"{self.dir}.render.html" if self.whole else f"{self.dir}/{self.section.slug}.render.html"

    @property
    def prose_href(self) -> str:
        """The section's prose views, fetched when the reader first asks for
        them (prose_json; site.js), not carried hidden in every page."""
        return self.render_href.removesuffix(".render.html") + ".prose.json"

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
    return ROOT / "l4" / doc.removesuffix(".xml") / f"{akn.module_prefix(doc)}{akn.file_name(num)}.l4"


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
                        v.covered_by[r.key] = where[first].key
    return v


def citations(sec: akn.Section) -> dict[str, str]:
    """Row key -> the clause as a reader cites it: §1.7.2ב, not an eId."""
    out, stack = {}, []
    for r in sec.rows:
        stack = stack[:r.depth]
        stack += [""] * (r.depth - len(stack))
        num = r.num.strip().rstrip(".)").lstrip("(")
        # a label that restates the section's own number adds nothing, and
        # one that prints its path from the section ("1.25.1" in §1.25)
        # keeps only what follows it: not dropped, or the paragraphs under
        # it read as the section's own (§1.25.3 for §1.25.1's third, MMS-657)
        own = sec.num.strip().rstrip(".")
        if own and num == own:
            num = ""
        elif own and num.startswith(own + "."):
            num = num[len(own) + 1:]
        elif r.num.startswith(sec.num):
            num = ""
        stack.append(num)
        # a level that prints its whole path ("2.1" under "2", "1.א.3" under
        # "1.א") restates its parent, so the parent is dropped, not repeated
        parts: list[str] = []
        for p in (p for p in stack if p):
            if parts and p.startswith(parts[-1] + "."):
                parts[-1] = p
            else:
                parts.append(p)
        # a number continues the path with a dot, whether it is one level
        # ("2") or several printed together ("4.5"): §1.15.4.5, not §1.154.5
        if sec.chapter_eid:
            cite = sec_ref(sec) + "".join(("." if p[0].isdigit() else "") + p for p in parts)
        else:   # a whole document: its clauses are cited from its own numbering
            cite = "§" + "".join(("." if p[0].isdigit() and i else "") + p for i, p in enumerate(parts))
            if cite == "§":
                cite = {"preamble": "פתיח", "conclusions": "חתימה",
                        "attachments": "נספחים"}.get(r.key.split("/")[0].split("__")[0], "")
        for k in [r.key, *r.aliases]:
            out.setdefault(k, cite)
    for k in list(out):
        last = k.rsplit("/", 1)[-1] if "/" in k else ""
        if re.fullmatch(r"p\d+", last):
            out[k] = out[k] + " ¶" + last[1:]
        elif re.fullmatch(r"t\d+", last):
            out[k] = out[k] + " table " + last[1:]
    return out


COUNTER = re.compile(r" (?:¶|table )\d+$")
HEB_YEARS = {"tashsaz": 'תשס"ז', "tashsach": 'תשס"ח', "tashsat": 'תשס"ט', "tasha": 'תש"ע',
             "tashaa": 'תשע"א', "tashab": 'תשע"ב', "tashag": 'תשע"ג', "tashad": 'תשע"ד',
             "tashae": 'תשע"ה', "tashav": 'תשע"ו', "tashaz": 'תשע"ז', "tashach": 'תשע"ח',
             "tashat": 'תשע"ט', "tashaf": 'תש"פ', "tashpa": 'תשפ"א', "tashpab": 'תשפ"ב',
             "tashpag": 'תשפ"ג', "tashpad": 'תשפ"ד', "tashpah": 'תשפ"ה', "tashpo": 'תשפ"ו',
             "tashsa": 'תשס"א'}


def doc_label(doc: str) -> str:
    """The document as a reader names it: "התקנון", "חוזר תשפ"ג/7",
    "חוזר שכר 2023-1-8". Read off the corpus path, whose names are regular;
    a path of no known shape falls back to the document's title."""
    coll, stem = doc.split("/")[0], Path(doc).stem
    if coll == "takanon":
        return f"דף האתר: {akn.title(doc)}" if is_site_page(doc) else "התקנון"
    m = re.fullmatch(r"[\d-]+_(?:tnai-sherut_)?([a-z]+)_(\d+)(_clarif)?(?:_.*)?", stem)
    if coll in ("circulars", "circulars-tnai-sherut") and m and m[1] in HEB_YEARS:
        name = f"{HEB_YEARS[m[1]]}/{int(m[2])}"
        kind = "חוזר תנאי שירות" if coll == "circulars-tnai-sherut" else "חוזר"
        return f"הבהרה לחוזר {name}" if m[3] else f"{kind} {name}"
    m = re.fullmatch(r"[\d-]+_sachar_([\d]+-\d+-\d+)_.*", stem)
    if coll == "circulars-sachar" and m:
        return f"חוזר שכר {m[1]}"
    return akn.title(doc)


def clause(sec: akn.Section, key: str, fallback: str) -> str:
    """The clause a row sits in, as the text numbers it: §1.15.4.5. An
    unnumbered paragraph or table is cited by its clause alone -- the "¶150"
    citations() appends is our own running count, which nothing on the page
    prints, so it is no use to a reader."""
    c = citations(sec).get(key)
    return COUNTER.sub("", c) if c else fallback


def cite_html(sec: akn.Section, key: str, fallback: str, doc: str | None = None) -> str:
    """A clause label for a page, left to right; with `doc`, preceded by the
    document's name, for a link read away from that document's own page."""
    return ((f'<span class="cdoc">{esc(doc_label(doc))}</span> ' if doc else "")
            + f'<bdi dir="ltr">{esc(clause(sec, key, fallback))}</bdi>')


def row_label(sec: akn.Section, key: str) -> str:
    """A link's label for a row of the same page: its clause, or where the
    text numbers nothing, the row's first words in quotation marks."""
    if clause(sec, key, ""):
        return cite_html(sec, key, "")
    words = next((r.text for r in sec.rows if r.key == key or key in r.aliases), "").split()
    if not words:
        return "למעלה"
    return f'<bdi lang="he" dir="rtl">{esc("«" + " ".join(words[:5]) + ("…" if len(words) > 5 else "") + "»")}</bdi>'


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


DIGRAPH = re.compile(r"^digraph \{.*?^\}", re.S | re.M)
GRAPH_LABEL = re.compile(r'graph \[[^\]]*?label=(?:"((?:[^"\\]|\\.)*)"|([^\s,\]]+))', re.S)
GRAPHS = OUT / "assets" / "graphs"


EDGE_LABEL = re.compile(r'(\d+ -> \d+ \[label=")((?:[^"\\]|\\.)*)(")')


def wrap_edge_labels(dot: str, width: int = 34) -> str:
    """An action's label is one long line, so a diagram of three moves comes
    out a metre wide; wrapping the labels is presentation only."""
    def wrap(m):
        text = m.group(2).replace("\\n", " ")
        lines = textwrap.wrap(text, width, break_long_words=False, break_on_hyphens=False) or [text]
        return m.group(1) + "\\n".join(lines) + m.group(3)
    return EDGE_LABEL.sub(wrap, dot)


def state_graphs(v: "SectionView") -> dict[str, str]:
    """rule name -> the site path of its state diagram (an SVG drawn by
    GraphViz from `l4 state-graph`, which l4run.py keeps beside the run).
    Nothing when GraphViz is not installed: the page then shows no diagram."""
    if v.l4 is None or not shutil.which("dot"):
        return {}
    rel_ = v.l4.relative_to(ROOT / "l4")
    dot = ROOT / "build" / "l4" / rel_.parent / (rel_.name.removesuffix(".l4") + ".graph.dot")
    if not dot.exists():
        return {}
    out = {}
    for m in DIGRAPH.finditer(dot.read_text(encoding="utf-8")):
        lab = GRAPH_LABEL.search(m.group(0))
        if not lab:
            continue
        src = wrap_edge_labels(m.group(0))
        name = hashlib.sha1(src.encode()).hexdigest()[:16] + ".svg"
        svg = GRAPHS / name
        if not svg.exists():
            GRAPHS.mkdir(parents=True, exist_ok=True)
            r = subprocess.run(["dot", "-Tsvg"], input=src, capture_output=True, text=True)
            if r.returncode != 0:
                continue
            svg.write_text(r.stdout, encoding="utf-8")
        out[_norm((lab.group(1) or lab.group(2)).replace('\\"', '"'))] = f"assets/graphs/{name}"
    return out


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


def prose_json(v: SectionView) -> str:
    """segment start line -> its prose view, for the page that shows the
    section. A rendered term links to its definition; where that is not in
    this section's own views it is on the section's render page."""
    frags = rendered_for(v)
    ids = {i for f in frags.values() for i in re.findall(r'\bid="([^"]*)"', f)}
    out_page = rel(v.render_href, v.page)

    def link(m):
        return m.group(0) if html.unescape(m.group(1)) in ids else f'href="{esc(out_page)}#{m.group(1)}"'
    return json.dumps({str(k): re.sub(r'href="#([^"]*)"', link, f) for k, f in frags.items()},
                      ensure_ascii=False, separators=(",", ":"))


def chapters_of(views: list[SectionView]) -> list[list[SectionView]]:
    """A sectioned document's sections, chapter by chapter, in order."""
    out: dict[str, list[SectionView]] = {}
    for v in views:
        out.setdefault(v.section.chapter_eid, []).append(v)
    return list(out.values())
