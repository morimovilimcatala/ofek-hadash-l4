"""Build the static site: the corpus text beside its L4, document by document.

    python3 tools/build_site.py      # after tools/l4run.py; writes build/site/

Pages, laid out like the corpus they encode:

  index.html                       the collections, and how much is encoded
  takanon/<doc>.html               the takanon's contents: its chapters and sections
  takanon/<doc>/chapter-<n>.html   one chapter: each section's text | L4, row by row
  takanon/<doc>/<num>.html         a redirect to the section on its chapter page
  takanon/<doc>/<num>.render.html  L4's own rendering of that section
  takanon/<doc>/<num>.prose.json   that section's prose views, fetched on the switch
  <collection>/<doc>.html          a circular: its text | L4, row by row
  findings.html  findings.json     errors in the LAW that encoding exposed
  salary.html                      what §1.1's salary is made of, drawn from its L4
  calculator.html                  §1.1's salary, computed in the browser by L4 (WASM)
  coverage.html                    how much of the corpus is encoded
  diagnostics.html                 what the L4 checker reported, file by file
  index.json                       every L4 segment with its corpus address

The site is in English; the corpus's text is shown as it is, in Hebrew.
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
import l4src    # noqa: E402
import rule_graph  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "build" / "site"
L4_OUT = ROOT / "build" / "l4"
ASSETS = Path(__file__).resolve().parent / "assets"
FINDINGS = ROOT / "findings"           # one <section>.toml per section
MANIFEST = ROOT / "corpus" / "manifest.json"
MANIFEST_DOCS = json.loads(MANIFEST.read_text(encoding="utf-8"))["documents"]
CORPUS_SITE = "https://morimovilimcatala.github.io/ofek-hadash-corpus"
REPO = "https://github.com/morimovilimcatala/ofek-hadash-l4"
TITLE = "אופק חדש ב-L4"

# what is encoded, by the corpus document it encodes; the l4/ directory
# mirrors the corpus's akn/ path without the extension
# the collections in work: every document of them, by the corpus's own list
WORK_COLLECTIONS = ("takanon", "circulars", "circulars-sachar", "circulars-tnai-sherut")


def _documents() -> list[str]:
    docs = json.loads((Path(__file__).resolve().parent.parent / "corpus" / "manifest.json")
                      .read_text(encoding="utf-8"))["documents"]
    out = ["takanon/takanon-sherut-ovdei-horaa.xml"]
    # the department's web pages, which the corpus files beside the takanon
    out += sorted(d["path"] for d in docs
                  if d["collection"] == "takanon" and d["path"] not in out)
    out += sorted(d["path"] for d in docs
                  if d["collection"] in WORK_COLLECTIONS[1:])
    return out


DOCUMENTS = _documents()

# The takanon collection holds the takanon and the conditions-of-service
# department's web pages (its home page, the Q&A, the takanon's
# introduction, lists of circulars and procedures). They are not part of the
# takanon: each is a whole document, shown and counted as a group of its own
# under the collection.
SITE_GROUP = "דפי האתר של תחום תנאי שירות"
SITE_ANCHOR = "site-pages"


def is_site_page(doc: str) -> bool:
    return doc.split("/")[0] == "takanon" and akn.is_whole(doc)


def doc_num(doc: str) -> str:
    """The short number a list shows beside a whole document's title: a
    circular's number; none for a site page, whose title is its name."""
    stem = Path(doc).stem
    if doc.startswith("circulars/"):
        return stem.split("_", 1)[-1]
    return "" if is_site_page(doc) else stem[:10]

# the corpus's collections, so the reader sees what is not started as well
COLLECTIONS = [
    ("takanon", "תקנון שירות עובדי הוראה"),
    ("agreements", "הסכמים קיבוציים"),
    ("circulars", "חוזרים לבעלויות"),
    ("circulars-sachar", "חוזרי שכר"),
    ("circulars-tnai-sherut", "חוזרי תנאי שירות"),
    ("letters", "מכתבים"),
    ("takam", "הוראות תכ\"ם (החשב הכללי)"),
    ("tables", "טבלאות"),
]

# The two labels every finding carries (MMS-415). KIND is what is wrong with
# the law; STAGE is what caught it. The tool's message is the evidence, not
# the category: a gap is a gap whether a warning or an example exposed it.
KINDS = {
    "gap": ("פער", "מקרה שהמסמך אינו מכריע בו"),
    "overlap": ("חפיפה", "שני כללים למקרה אחד, או כלל שלעולם אינו חל"),
    "contradiction": ("סתירה", "מה שהמסמך קובע וכללו שלו אינו מניב, או שני סעיפים שאינם מתיישבים"),
    "undefined-term": ("מונח לא מוגדר", "מונח שבשימוש ואינו מוגדר"),
    "broken-reference": ("הפניה שבורה", "סעיף, נספח או מסמך שהטקסט מפנה אליו ואינו קיים"),
    "ambiguity": ("עמימות", "ניסוח שאפשר לקרוא בשתי דרכים"),
}
STAGES = {
    "writing": ("בכתיבת הכלל", "אי אפשר לכתוב את הטקסט כפי שהוא"),
    "compiling": ("בהידור", "הכללים אינם מתיישבים זה עם זה"),
    "examples": ("בהרצת הדוגמאות שבטקסט", "הכללים סותרים טבלה או דוגמה שהמסמך עצמו מביא"),
    "verification": ("באימות פורמלי", "פגם שאף דוגמה בודדת אינה מראה"),
}
REVIEW = {
    "unreviewed": "טרם נבדק על ידי עורך הדין",
    "lawyer-seen": "נבדק על ידי עורך הדין",
    "lawyer-agreed": "עורך הדין מסכים",
    "lawyer-disagreed": "עורך הדין חולק",
}

esc = html.escape


def he(text: str) -> str:
    """Corpus text, marked as Hebrew."""
    return f'<span lang="he" dir="rtl">{esc(text)}</span>'


def en(text: str) -> str:
    """Our own English (a note) inside the Hebrew site: isolated, so its
    punctuation and numbers keep their order."""
    return f'<bdi lang="en" dir="ltr">{esc(text)}</bdi>'


HEB = re.compile(r"[\u05d0-\u05ea]")
LAT = re.compile(r"[A-Za-z]")
IDENT = re.compile(r"`[^`]*`")
FID = re.compile(r"F-[0-9A-Za-z][0-9A-Za-z._\u05d0-\u05ea-]*[0-9A-Za-z\u05d0-\u05ea]")
LTR_RUN = re.compile(r"`[^`]*`|\bF-[0-9A-Za-z][0-9A-Za-z._\u05d0-\u05ea-]*[0-9A-Za-z\u05d0-\u05ea]|§[0-9][0-9A-Za-z\u05d0-\u05ea.()]*[0-9A-Za-z\u05d0-\u05ea)]|§[0-9]|#[A-Z]+")


def is_hebrew(text: str) -> bool:
    """A finding's prose is Hebrew when Hebrew letters outnumber Latin ones
    outside the L4 identifiers (`…`) it names."""
    bare = IDENT.sub("", text)
    return len(HEB.findall(bare)) > len(LAT.findall(bare))


def prose(text: str, link_ids: bool = False) -> str:
    """A finding's own words, in whichever language they are written. In
    Hebrew prose an L4 identifier, a section number ("§1.1ב") and a keyword
    ("#ASSERT") stay left to right, isolated."""
    if not is_hebrew(text):
        return en(text)
    out, last = [], 0
    for m in LTR_RUN.finditer(text):
        out.append(esc(text[last:m.start()]))
        run = m.group(0)
        fid = run.strip("`")
        if FID.fullmatch(fid):
            ref = f'<bdi dir="ltr" class="fref">{esc(fid)}</bdi>'
            out.append(f'<a href="#{esc(fid)}">{ref}</a>' if link_ids else ref)
            last = m.end()
            continue
        out.append(f'<bdi dir="ltr" lang="en"><code>{esc(run[1:-1])}</code></bdi>' if run.startswith("`")
                   else f'<bdi dir="ltr">{esc(run)}</bdi>')
        last = m.end()
    out.append(esc(text[last:]))
    return f'<span lang="he" dir="rtl">{"".join(out)}</span>'


READ_BY = {"Claude (L4 encoder)": "Claude (מקודד ה־L4)"}


def who(read_by: str) -> str:
    """Whose reading a finding is, in Hebrew where the site knows the name."""
    if read_by in READ_BY:
        return f'<span lang="he" dir="rtl">{esc(READ_BY[read_by])}</span>'
    return prose(read_by)


# ----------------------------------------------------------------- model

HEB_LATIN = dict(zip("אבגדהוזחטיכלמנסעפצקרשת",
                     "a b g d h v z ch t y k l m n s e p ts q r sh t".split()))


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
        return f"{self.dir}/{chapter_slug(self.section.chapter_num)}.html"

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
                        v.covered_by[r.key] = where[first].key
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
            cite = "§" + sec.num + "".join(("." if p[0].isdigit() else "") + p for p in parts)
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


# ------------------------------------------------------------------ pages

def rel(target: str, here: str) -> str:
    return "../" * here.count("/") + target


# every document's views, set by build() before any page is written, so each
# page can carry the same navigation tree
NAV_VIEWS: dict[str, list[SectionView]] = {}


def coll_docs(coll: str) -> list[str]:
    return [d for d in NAV_VIEWS if d.split("/")[0] == coll]


def coll_hub(coll: str) -> str:
    """A collection's overview: the contents page of its sectioned document
    (the takanon's), or the collection's own page."""
    sectioned = [d for d in coll_docs(coll) if not akn.is_whole(d)]
    return f"{sectioned[0].removesuffix('.xml')}.html" if sectioned else f"{coll}.html"


def coll_count(coll: str) -> int:
    """What a collection lists: a sectioned document's sections, and each
    whole document once."""
    return sum(len(NAV_VIEWS[d]) for d in coll_docs(coll))


def site_group_li(here: str, open_: bool) -> str:
    """The takanon collection's site pages, as one group of the sidebar."""
    vs = [v for d in coll_docs("takanon") if is_site_page(d) for v in NAV_VIEWS[d]]
    if not vs:
        return ""
    return (f'<li class="toc-ch"><details{" open" if open_ else ""}><summary>'
            f'<span class="ch" lang="he" dir="rtl">{esc(SITE_GROUP)}</span>'
            f'<span class="n">{len(vs)}</span></summary><ul>{"".join(doc_li(v, here) for v in vs)}</ul></details></li>')


def sec_li(v: SectionView, href: str) -> str:
    return (f'<li><a href="{href}" title="{esc(v.section.heading)}"><span class="secnum" dir="ltr">{esc(v.section.num)}</span>'
            f'<span class="sh" lang="he" dir="rtl">{esc(v.section.heading)}</span></a></li>')


def doc_li(v: SectionView, here: str) -> str:
    cur = ' aria-current="page"' if here == v.page else ""
    num = doc_num(v.doc)
    secnum = f'<span class="secnum" dir="ltr">{esc(num)}</span>' if num else ""
    return (f'<li><a href="{rel(v.page, here)}" title="{esc(v.section.heading)}"{cur}>{secnum}'
            f'<span class="sh" lang="he" dir="rtl">{esc(v.section.heading)}</span></a></li>')


def chapter_label(s: akn.Section) -> str:
    return (f'<span class="ch" lang="he" dir="rtl">פרק {esc(s.chapter_num)} · {esc(s.chapter_heading)}</span>')


def group_html(coll: str, label: str, here: str, items: list[str], open_: bool) -> str:
    return (f'<li class="sn-group"><details{" open" if open_ else ""}>'
            f'<summary>{esc(label.split(" — ")[0])}<span class="n">{coll_count(coll)}</span></summary>'
            f'<a class="sn-hub" href="{rel(coll_hub(coll), here)}">סקירה</a>'
            f'<ul>{"".join(items)}</ul></details></li>')


def tree_nav(here: str) -> str:
    """Every encoded document, grouped as the corpus groups them: the
    sidebar of a page that is not a document (the home page, coverage,
    diagnostics, about, a collection's overview)."""
    groups = []
    for coll, label in COLLECTIONS:
        docs = coll_docs(coll)
        if not docs:
            continue
        here_in = any(here.startswith(d.removesuffix(".xml")) for d in docs) or here == f"{coll}.html"
        items = []
        if any(not akn.is_whole(d) for d in docs):
            for d in docs:
                if akn.is_whole(d):
                    continue
                for vs in chapters_of(NAV_VIEWS[d]):
                    lis = "".join(sec_li(v, rel(v.href, here)) for v in vs)
                    items.append(f'<li class="toc-ch"><details><summary>{chapter_label(vs[0].section)}'
                                 f'<span class="n">{len(vs)}</span></summary><ul>{lis}</ul></details></li>')
            items.append(site_group_li(here, False))
        else:
            by_year: dict[str, list[SectionView]] = {}
            for d in docs:
                by_year.setdefault(school_year(d) if coll == "circulars" else "", []).extend(NAV_VIEWS[d])
            for year in sorted(by_year, reverse=True):
                vs = sorted(by_year[year], key=lambda v: v.doc)
                lis = "".join(doc_li(v, here) for v in vs)
                items.append(lis if not year else
                             f'<li class="toc-ch"><details><summary>{esc(year)}'
                             f'<span class="n">{len(vs)}</span></summary><ul>{lis}</ul></details></li>')
        groups.append(group_html(coll, label, here, items, here_in))
    return "".join(groups)


def doc_of(here: str) -> str | None:
    """The encoded document a page belongs to: its own page, a takanon
    chapter, or a section's rendering."""
    for d in NAV_VIEWS:
        base = d.removesuffix(".xml")
        if here in (f"{base}.html", f"{base}.render.html"):
            return d
    for d in NAV_VIEWS:
        if not akn.is_whole(d) and here.startswith(d.removesuffix(".xml") + "/"):
            return d
    return None


def doc_nav(here: str, doc: str) -> str:
    """A document page's sidebar: its own place first and open — the
    takanon's chapters with the current one's sections, or a circular among
    the circulars of its year — and the other collections closed below it.
    On a chapter page its sections link to their anchors, so the scrollspy
    in site.js can mark the one in view; site.js hangs the outline of the
    headed paragraphs under the current entry."""
    coll = doc.split("/")[0]
    label = dict(COLLECTIONS)[coll]
    items = []
    sectioned = [d for d in coll_docs(coll) if not akn.is_whole(d)]
    if sectioned:
        for vs in [vs for d in sectioned for vs in chapters_of(NAV_VIEWS[d])]:
            on_page = here == vs[0].page
            if on_page or any(here == v.render_href for v in vs):
                lis = "".join(sec_li(v, "#" + esc(v.section.eid) if on_page else rel(v.href, here)) for v in vs)
                items.append(f'<li class="toc-ch"><details open><summary>{chapter_label(vs[0].section)}'
                             f'<span class="n">{len(vs)}</span></summary><ul>{lis}</ul></details></li>')
            else:
                items.append(f'<li class="toc-ch"><a class="sn-leaf" href="{rel(vs[0].page, here)}">'
                             f'{chapter_label(vs[0].section)}<span class="n">{len(vs)}</span></a></li>')
        items.append(site_group_li(here, is_site_page(doc)))
    else:
        by_year: dict[str, list[SectionView]] = {}
        for d in coll_docs(coll):
            by_year.setdefault(school_year(d) if coll == "circulars" else "", []).extend(NAV_VIEWS[d])
        mine = school_year(doc) if coll == "circulars" else ""
        for year in sorted(by_year, reverse=True):
            vs = sorted(by_year[year], key=lambda v: v.doc)
            if year == mine:
                lis = "".join(doc_li(v, here) for v in vs)
                items.append(lis if not year else
                             f'<li class="toc-ch"><details open><summary>{esc(year)}'
                             f'<span class="n">{len(vs)}</span></summary><ul>{lis}</ul></details></li>')
            else:
                items.append(f'<li class="toc-ch"><a class="sn-leaf" href="{rel(coll + ".html", here)}#y-{esc(year)}">'
                             f'<span dir="ltr">{esc(year)}</span><span class="n">{len(vs)}</span></a></li>')
    groups = [group_html(coll, label, here, items, True)]
    for c, lab in COLLECTIONS:
        if c != coll and coll_docs(c):
            groups.append(other_group(c, lab, here))
    return "".join(groups)


def other_group(coll: str, label: str, here: str) -> str:
    """A collection the page is not in: one closed line, to its overview."""
    return (f'<li class="sn-group"><a class="sn-leaf" href="{rel(coll_hub(coll), here)}">'
            f'{esc(label.split(" — ")[0])}<span class="n">{coll_count(coll)}</span></a></li>')


def nav_html(here: str, inner: str | None = None) -> str:
    """The sidebar. What it shows depends on the page (the client,
    2026-10-11: "adapt the content, not the size"): a document page's own
    place (doc_nav), the findings page's own index (findings_nav), and
    elsewhere every collection (tree_nav)."""
    if not NAV_VIEWS:
        return ""
    if inner is None:
        doc = doc_of(here)
        inner = doc_nav(here, doc) if doc else tree_nav(here)
    return (f'<aside class="sidenav" id="sidenav" aria-label="עיון במסמכים">'
            f'<div class="sn-head"><span>עיון</span>'
            f'<button type="button" class="sn-close" aria-label="סגירה">×</button></div>'
            f'<ul class="sn-tree">{inner}</ul></aside>'
            f'<div class="sn-scrim" hidden></div>')


def page(here: str, title: str, body: str, *, tab: str = "", desc: str = "",
         wide: bool = False, sidebar: str | None = None) -> str:
    nav = [("index.html", "מסמכים", "docs"),
           ("findings.html", "ממצאים", "findings"),
           ("salary.html", "מבנה השכר", "salary"),
           *([("calculator.html", "מחשבון שכר", "calculator")] if CALCULATOR else []),
           ("coverage.html", "כיסוי", "coverage"),
           ("diagnostics.html", "בדיקות", "diagnostics"),
           ("about.html", "אודות", "about")]
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
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Frank+Ruhl+Libre:wght@400;500;700&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans+Hebrew:wght@400;500;600;700&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap">
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
    <button type="button" class="sn-open" aria-controls="sidenav" aria-expanded="false" aria-label="עיון במסמכים">
      <svg viewBox="0 0 20 20" width="20" height="20" aria-hidden="true"><path d="M3 5h14M3 10h14M3 15h14" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg></button>
    <a class="brand" href="{rel('index.html', here)}"><span class="mark">L4</span><span>אופק חדש ב-L4</span></a>
    <nav class="tabs-top">{links}</nav>
  </div>
</header>
<div class="shell">
{nav_html(here, sidebar)}
<main class="{'wide' if wide else ''}">
{body}
</main>
</div>
<footer class="foot">
  <div>הטקסט: <a href="{CORPUS_SITE}/">קורפוס אופק חדש</a>, כפי שפורסם. הקוד:
  <a href="{REPO}" dir="ltr">{esc(REPO.split('github.com/')[1])}</a>.</div>
  <div>הקידוד הוא קריאה של הטקסט ואינו בא במקומו.</div>
</footer>
</body>
</html>
"""


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
    if (v.doc, v.section.num) == SALARY:
        links.append(f'<a href="{rel("salary.html", here)}">מבנה השכר</a>')
        if CALCULATOR:
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
               f'<span class="secnum" dir="ltr">§{esc(sec.num)}</span>{esc(sec.heading)}</a></h2>'
               f'<div class="tsec-meta">{badge(v.status)}<span class="links">{"".join(links)}</span></div></div>')
            + f'{stats}</header>')
    if found:
        head += ('<div class="sec-findings"><h3>ממצאים בחלק זה</h3><ul>'
                 + "".join(f'<li><a href="{rel("findings.html", here)}#{esc(f["id"])}"><span class="kind-tag {f["kind"]}">'
                           f'{esc(KINDS[f["kind"]][0])}</span>{prose(f["title"])}</a></li>' for f in found)
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


def redirect_page(here: str, target: str, title: str) -> str:
    """A page that moved: sends the reader (and a search engine) on."""
    to = rel(target, here)
    return (f'<!doctype html><html lang="he" dir="rtl"><head><meta charset="utf-8"><title>{esc(title)}</title>'
            f'<meta http-equiv="refresh" content="0; url={esc(to)}"><link rel="canonical" href="{esc(to)}">'
            f'</head><body><p>הדף עבר אל <a href="{esc(to)}">{esc(title)}</a>.</p></body></html>')


def render_page(v: SectionView) -> str:
    """L4's own rendering, framed by the site so it is navigable."""
    m = re.search(r"<body[^>]*>(.*)</body>", v.render, re.S)
    inner = m.group(1) if m else v.render
    here = v.render_href
    body = (f'<header class="sec-head"><nav class="crumbs"><a href="{rel(v.href, here)}">→ {"" if v.whole else "§" + esc(v.section.num) + " "}זה לצד זה</a></nav>'
            f'<div class="title-row"><h1 lang="he" dir="rtl">'
            + ("" if v.whole else f'<span class="secnum" dir="ltr">§{esc(v.section.num)}</span>')
            + f'{esc(v.section.heading)}</h1></div>'
            f'<p class="lede">{"המסמך" if v.whole else "החלק"} כולו, כפי ש־<code>l4 render</code> כותב את הכללים בחזרה כפרוזה (באנגלית).</p></header>'
            f'<div class="render-frame" dir="ltr" lang="en">{inner or "<p>l4 render לא הפיק דבר לקובץ זה.</p>"}</div>')
    return page(here, f"§{v.section.num} — פרוזה (l4 render)", body, tab="docs")


def progress(vs: list[SectionView]) -> str:
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
        return ""
    total = max(sum(t.values()), 1)
    names = {"done": "מקודדות", "missing": "לא צוטטו", "todo": "טרם קודדו"}
    cls = {"done": "rule", "missing": "missing", "todo": "todo"}   # the sheet's colours
    legend = " · ".join(f'<span><i class="sw {cls[k]}"></i>{round(t[k] * 100 / total)}% {names[k]}</span>'
                        for k in ("done", "missing", "todo") if t[k])
    return ('<span class="pbar">' + "".join(
        f'<i class="{cls[k]}" style="width:{t[k] * 100 / total:.3f}%"></i>' for k in ("done", "missing") if t[k])
        + f'</span><span class="plegend">פסקאות: {legend}</span>')


def chapters_of(views: list[SectionView]) -> list[list[SectionView]]:
    """A sectioned document's sections, chapter by chapter, in order."""
    out: dict[str, list[SectionView]] = {}
    for v in views:
        out.setdefault(v.section.chapter_eid, []).append(v)
    return list(out.values())


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
            'for(var c in to)if(id===c||id.indexOf(c+"__")===0){location.replace(to[c]+h);return}'
            '})();</script>')


def contents_page(doc: str, views: list[SectionView]) -> str:
    """The takanon's contents: its chapters and sections, each linking to the
    chapter page that holds it (one page per chapter; the whole document on
    one page was 18MB). Its address is the one the whole document had, and a
    link into the old page by fragment is sent on to its chapter."""
    here = f"{doc.removesuffix('.xml')}.html"
    chapters = chapters_of(views)
    done = sum(v.status == "done" for v in views)
    part = sum(v.status == "partial" for v in views)
    nfind = len({f["id"] for v in views for r in v.section.rows for f in row_findings(v, r)})
    parts = []
    for vs in chapters:
        s0 = vs[0].section
        lis = "".join(
            f'<li class="{v.status}"><a href="{rel(v.href, here)}">{dot(v.status)}'
            f'<span class="secnum" dir="ltr">{esc(v.section.num)}</span>'
            f'<span class="sh" lang="he">{esc(v.section.heading)}</span></a></li>' for v in vs)
        parts.append(f'<section class="chapter" dir="rtl"><div class="chapter-head"><h2>'
                     f'<a href="{rel(vs[0].page, here)}" lang="he" dir="rtl">פרק {esc(s0.chapter_num)} · '
                     f'{esc(s0.chapter_heading)}</a></h2>'
                     f'<span class="ccount">{sum(v.status == "done" for v in vs)} מתוך {len(vs)} מקודדים</span></div>'
                     f'<ul class="secs">{lis}</ul></section>')
    head = (f'<header class="sec-head doc-head"><nav class="crumbs"><a href="{rel("index.html", here)}">מסמכים</a></nav>'
            f'<div class="title-row"><h1 lang="he" dir="rtl">{esc(akn.title(doc))}</h1></div>'
            f'<p class="lede">תקנון שירות עובדי הוראה של משרד החינוך, במלואו, '
            f'כפי שהקורפוס מפרסם אותו: {len(views)} סעיפים ב־{len(chapters)} פרקים, עמוד לכל פרק. כל פסקה '
            f'של הטקסט (מימין) עומדת ליד ה-L4 שמקודד אותה (משמאל).</p>'
            f'<div class="stats"><span><b>{done}</b> מתוך {len(views)} סעיפים מקודדים</span>'
            + (f'<span><b>{part}</b> בחלקם</span>' if part else "")
            + f'<a class="fcount" href="{rel("findings.html", here)}"><b>{nfind}</b> ממצאים</a>'
            f'<a href="{CORPUS_SITE}/{doc.removesuffix(".xml")}.html">בקורפוס ↗</a></div>'
            f'{progress(views)}</header>')
    pages = [v for d in NAV_VIEWS if is_site_page(d) for v in NAV_VIEWS[d]]
    if pages:
        lis = "".join(
            f'<li class="{v.status}"><a href="{rel(v.href, here)}">{dot(v.status)}'
            f'<span class="sh" lang="he">{esc(v.section.heading)}</span></a></li>' for v in pages)
        parts.append(f'<section class="chapter" id="{SITE_ANCHOR}" dir="rtl"><div class="chapter-head"><h2>{esc(SITE_GROUP)}</h2>'
                     f'<span class="ccount">{sum(v.status == "done" for v in pages)} מתוך {len(pages)} מקודדים</span></div>'
                     f'<p class="meta">{SITE_GROUP_LEDE}</p><ul class="secs docs">{lis}</ul></section>')
    return page(here, f"{akn.title(doc)} — {TITLE}", old_anchor_script(doc, views) + head + "".join(parts),
                tab="docs", desc="תקנון שירות עובדי הוראה: הפרקים והסעיפים, כל פסקה ליד קידוד ה-L4 שלה")


def chapter_page(doc: str, chapters: list[list[SectionView]], i: int) -> str:
    """One chapter of the takanon: each of its sections with its text beside
    its L4. The sidebar lists its sections (and follows the one in view)."""
    vs = chapters[i]
    s0 = vs[0].section
    here = vs[0].page
    contents = f"{doc.removesuffix('.xml')}.html"
    n_done = sum(v.status == "done" for v in vs)
    nfind = len({f["id"] for v in vs for r in v.section.rows for f in row_findings(v, r)})
    name = f"פרק {s0.chapter_num} · {s0.chapter_heading}"
    # a chapter the corpus holds as one block is its own section; it takes
    # the chapter's anchor itself
    chap_id = "" if any(v.section.eid == s0.chapter_eid for v in vs) else f' id="{esc(s0.chapter_eid)}"'
    head = (f'<header class="sec-head doc-head"{chap_id}><nav class="crumbs"><a href="{rel("index.html", here)}">מסמכים</a><span>/</span>'
            f'<a href="{rel(contents, here)}" lang="he" dir="rtl">{esc(akn.title(doc))}</a></nav>'
            f'<div class="title-row"><h1 lang="he" dir="rtl">{esc(name)}</h1></div>'
            f'<div class="stats"><span><b>{n_done}</b> מתוך {len(vs)} סעיפים מקודדים</span>'
            + (f'<a class="fcount" href="{rel("findings.html", here)}"><b>{nfind}</b> ממצאים</a>' if nfind else "")
            + f'<a href="{CORPUS_SITE}/{doc.removesuffix(".xml")}.html#{esc(s0.chapter_eid)}">בקורפוס ↗</a></div>'
            f'{progress(vs)}</header>')
    toolbar = (f'<div class="doc-toolbar"><span class="tb-label">הצגת ה-L4:</span>{SWITCH}'
               f'<span class="tb-where" aria-live="polite"></span>'
               f'<span class="tb-cols"><span>L4</span><span>טקסט</span></span></div>')
    blocks = "".join(section_block(v, here) for v in vs)

    def step(j: int, cls: str, label: str) -> str:
        if not 0 <= j < len(chapters):
            return ""
        c = chapters[j][0]
        return (f'<a class="{cls}" href="{rel(c.page, here)}"><small>{label}</small>'
                f'<span lang="he" dir="rtl">פרק {esc(c.section.chapter_num)} · {esc(c.section.chapter_heading)}</span></a>')
    prevnext = f'<nav class="prevnext">{step(i - 1, "prev", "הפרק הקודם")}{step(i + 1, "next", "הפרק הבא")}</nav>'
    body = head + f'<div class="doc-main">{toolbar}{blocks}</div>' + prevnext
    return page(here, f"{name} — {akn.title(doc)} — {TITLE}", body, tab="docs", wide=True,
                desc=f"תקנון שירות עובדי הוראה, {name}: כל פסקה ליד קידוד ה-L4 שלה")


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
    body = head + toolbar + section_block(v, here, headless=True)
    return page(here, f"{v.section.heading} — {TITLE}", body, tab="docs", wide=True,
                desc=f"{v.section.heading}: נוסח המסמך ליד קידוד ה-L4 שלו")


SITE_LEDE = ("דף מאתר תחום תנאי שירות עובדי הוראה במשרד החינוך, כפי שהקורפוס צילם אותו. "
             "הוא אינו חלק מהתקנון ואינו מחייב: תשובות, ניווט ופרטי קשר.")
SITE_GROUP_LEDE = ("דפים מאתר תחום תנאי שירות עובדי הוראה במשרד החינוך, כפי שהקורפוס צילם אותם. "
                   "הם אינם חלק מהתקנון ואינם מחייבים: תשובות, ניווט ופרטי קשר.")


def school_year(doc: str) -> str:
    return Path(doc).stem.split("_")[0][:7]


def collection_page(coll: str, views: list[SectionView]) -> str:
    """Every document of a collection, by year, newest first."""
    here = f"{coll}.html"
    by_year: dict[str, list[SectionView]] = {}
    for v in views:
        by_year.setdefault(school_year(v.doc), []).append(v)
    done = sum(v.status == "done" for v in views)
    parts = [f'<header class="sec-head"><nav class="crumbs"><a href="index.html">מסמכים</a></nav>'
             f'<div class="title-row"><h1>{esc(coll_name(coll))}</h1></div>'
             f'<div class="stats"><span><b>{done}</b> מתוך {len(views)} מסמכים מקודדים</span>'
             f'<a href="{CORPUS_SITE}/">בקורפוס ↗</a></div>{progress(views)}</header>']
    for year in sorted(by_year, reverse=True):
        vs = sorted(by_year[year], key=lambda v: v.doc)
        lis = "".join(
            f'<li class="{v.status}"><a href="{rel(v.href, here)}">{dot(v.status)}'
            f'<span class="secnum" dir="ltr">{esc(Path(v.doc).stem.split("_", 1)[-1])}</span>'
            f'<span class="sh" lang="he">{esc(v.section.heading)}</span></a></li>' for v in vs)
        parts.append(f'<section class="chapter" id="y-{esc(year)}" dir="rtl"><div class="chapter-head"><h2 dir="ltr">{esc(year)}</h2>'
                     f'<span class="ccount" dir="ltr">{sum(v.status == "done" for v in vs)} מתוך {len(vs)} מקודדים</span></div>'
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
                         f'<span class="cstate">טרם התחיל</span></li>')
            continue
        if coll == "takanon":
            pages = [v for d in docs if is_site_page(d) for v in all_views[d]]
            for d in [d for d in docs if not is_site_page(d)]:
                vs = all_views[d]
                n = sum(v.status == "done" for v in vs)
                cards.append(f'<li class="coll live wide"><a href="{d.removesuffix(".xml")}.html">'
                             f'<span class="cname">{esc(name)}</span>'
                             f'<span class="ctitle" lang="he" dir="rtl">{esc(akn.title(d))}</span>'
                             f'{progress(vs)}<span class="cstate">{n} מתוך {len(vs)} סעיפים מקודדים</span></a></li>')
            if pages:
                n = sum(v.status == "done" for v in pages)
                cards.append(f'<li class="coll live"><a href="{coll_hub(coll)}#{SITE_ANCHOR}">'
                             f'<span class="cname">{esc(SITE_GROUP)}</span>'
                             f'{progress(pages)}<span class="cstate">{n} מתוך {len(pages)} דפים מקודדים</span></a></li>')
            continue
        vs = [v for d in docs for v in all_views[d]]
        n = sum(v.status == "done" for v in vs)
        cards.append(f'<li class="coll live"><a href="{coll}.html">'
                     f'<span class="cname">{esc(name)}</span>'
                     f'{progress(vs)}<span class="cstate">{n} מתוך {len(vs)} מסמכים מקודדים</span></a></li>')
    body = (f'<section class="hero"><h1>הכללים של העסקת עובדי ההוראה, '
            f'כתובים כקוד לצד הטקסט.</h1>'
            f'<p class="lede">כל סעיף של <a href="{CORPUS_SITE}/">קורפוס אופק חדש</a> מופיע '
            f'פעמיים, פסקה אחר פסקה: הטקסט העברי, והכללים שנקראו ממנו בשפת '
            f'<a href="https://legalese.com/l4/">L4</a> — שפה למשפט שהמהדר שלה בודק כל כלל, '
            f'מריץ כל דוגמה ויודע לכתוב את הכללים בחזרה כפרוזה (באנגלית). הכול מקודד, לא רק השכר: '
            f'מי זכאי, באילו תנאים, מי חייב לעשות מה ועד מתי.</p>'
            f'<p class="lede">כתיבת החוק כקוד חושפת היכן הוא אינו מתיישב. המקומות האלה הם '
            f'<a href="findings.html">הממצאים</a>: כל אחד מהם מוכח, בקוד, שהוא בטקסט.</p>'
            f'<div class="kpis"><div><b>{done}</b><span>סעיפים ומסמכים מקודדים</span></div>'
            f'<div><b>{rules}</b><span>פסקאות עם כלל</span></div>'
            f'<div><a href="findings.html"><b>{len(findings)}</b><span>ממצאים בטקסט</span></a></div></div>'
            f'</section>'
            f'<h2 class="sect">אוספים</h2><ul class="colls">{"".join(cards)}</ul>')
    return page("index.html", TITLE, body, tab="docs",
                desc="תקנון שירות עובדי הוראה והחוזרים, לצד קידוד ה-L4 שלהם")


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
    """Every finding, grouped by the section or circular it is about, each
    folded to its title. A bar over them filters by kind, stage, collection
    and words (assets/site.js); a link to a finding opens it."""
    counts: dict[tuple[str, str], int] = {}
    for f in findings:
        counts[(f["kind"], f["stage"])] = counts.get((f["kind"], f["stage"]), 0) + 1
    # each cell of the matrix sets the filter to that kind and stage
    matrix = ('<div class="scroll-x"><table class="diag matrix"><thead><tr><th>סוג \\ שלב</th>'
              + "".join(f'<th title="{esc(d)}">{esc(t)}</th>' for t, d in STAGES.values())
              + "</tr></thead><tbody>"
              + "".join(f'<tr><th title="{esc(d)}">{esc(t)}</th>'
                        + "".join(f'<td>{f"<button type=button class=mcell data-kind={k} data-stage={st}>{counts[(k, st)]}</button>" if counts.get((k, st)) else ""}</td>'
                                  for st in STAGES) + "</tr>"
                        for k, (t, d) in KINDS.items())
              + "</tbody></table></div>")
    by_id = {f["id"]: f for f in findings}
    order: dict[int, int] = {}
    for i, v in enumerate(key_to_view.values()):
        order.setdefault(id(v), i)
    cols = dict(COLLECTIONS)
    groups: dict[tuple, dict] = {}
    for f in findings:
        doc = finding_doc(f)
        col = doc.split("/")[0]
        v = next((key_to_view[(doc, k)] for k in f.get("keys", []) if (doc, k) in key_to_view), None)
        if v is not None and not v.whole:
            gkey = (doc, v.section.num)
            label, href = f"§{v.section.num} {v.section.heading}", v.href
            num, short, gid = v.section.num, v.section.heading, f"in-{v.section.eid}"
        else:
            gkey = (doc,)
            label, href = akn.title(doc), f"{doc.removesuffix('.xml')}.html"
            stem = Path(doc).stem
            num = doc_num(doc)
            short, gid = (v.section.heading if v is not None else label), f"in-{stem}"
        g = groups.setdefault(gkey, {"label": label, "href": href, "col": col, "cards": [],
                                     "num": num, "short": short, "id": gid,
                                     "rank": (WORK_COLLECTIONS.index(col) if col in WORK_COLLECTIONS else 99,
                                              order.get(id(v), 10**9) if col == "takanon" else 0, doc)})
        ev = evidence_result(f, views_by_file)
        where, shown = [], set()
        for k in f.get("keys", []):
            kv = key_to_view.get((doc, k))
            if kv:
                # two paragraphs of one clause read the same; one link is enough
                label = cite_html(kv.section, k, "§" + kv.section.num, kv.doc)
                if label not in shown:
                    shown.add(label)
                    where.append(f'<a href="{kv.page}#{esc(k)}">{label}</a>')
        state = ('<span class="okay">ה־<bdi dir="ltr">#ASSERT</bdi> מתקיים: הפגם עדיין בטקסט</span>' if ev["held"] else
                 '<span class="notok">הראיה אינה מתקיימת — ראו בדיקות</span>')
        deps = "".join(f'<a href="#{esc(d)}"><bdi dir="ltr" class="fref">{esc(d)}</bdi></a> ' for d in f.get("depends_on", []) if d in by_id)
        stage, sgloss = STAGES[f["stage"]]
        paras = f["body"].strip().split("\n\n")
        body = (f'<div class="fbody" lang="he" dir="rtl">{"".join(f"<p>{prose(p, link_ids=True)}</p>" for p in paras)}</div>'
                if is_hebrew(f["body"]) else
                f'<div class="fbody" lang="en" dir="ltr">{"".join(f"<p>{esc(p)}</p>" for p in paras)}</div>')
        quote = (f'<blockquote lang="he" dir="rtl">{esc(f["quote"])}</blockquote>' if f.get("quote") else "")
        g["cards"].append(
            f'<details class="finding" id="{esc(f["id"])}" data-kind="{f["kind"]}" data-stage="{f["stage"]}" data-col="{col}">'
            f'<summary><span class="kind-tag {f["kind"]}">{esc(KINDS[f["kind"]][0])}</span>'
            f'<span class="ftitle">{prose(f["title"])}</span><span class="fid" dir="ltr">{esc(f["id"])}</span></summary>'
            f'<div class="fcard"><p class="fmeta"><span class="stage" title="{esc(sgloss)}">נתגלה {esc(stage)}</span> · '
            f'{" · ".join(where)}</p>{quote}{body}'
            f'<p class="reading"><strong>הקריאה שהקידוד מאמץ:</strong> {prose(f["reading"], link_ids=True)}</p>'
            + (f'<p class="deps">תלוי בקריאות של: {deps}</p>' if deps else "")
            + (f'<p class="ev"><a href="{ev["url"]}">הראיה ב-L4</a> · {state}</p>'
               + "".join(f'<pre class="msg" dir="ltr">{esc(m)}</pre>' for m in ev["messages"])
               if ev["url"] else "")
            + f'<p class="who">נקרא על ידי {who(f["read_by"])} · {esc(REVIEW[f["review"]])}</p>'
            + "</div></details>")
    ordered = sorted(groups.values(), key=lambda g: g["rank"])
    sections = "".join(
        f'<section class="fgroup" id="{esc(g["id"])}" data-col="{g["col"]}"><h2><a href="{g["href"]}" lang="he" dir="rtl">{esc(g["label"])}</a>'
        f' <small class="gcount">{len(g["cards"])}</small></h2>{"".join(g["cards"])}</section>'
        for g in ordered)
    # the sidebar here is this page's own index: every section and circular
    # that has findings, with its count, by collection (site.js keeps the
    # counts and the list in step with the filters)
    side = []
    for c in WORK_COLLECTIONS:
        gs = [g for g in ordered if g["col"] == c]
        if not gs:
            continue
        lis = "".join(
            f'<li><a href="#{esc(g["id"])}" title="{esc(g["label"])}"><span class="secnum" dir="ltr">{esc(g["num"])}</span>'
            f'<span class="sh" lang="he" dir="rtl">{esc(g["short"])}</span><span class="n">{len(g["cards"])}</span></a></li>'
            for g in gs)
        side.append(f'<li class="sn-group" data-col="{c}"><details open><summary>{esc(cols.get(c, c))}'
                    f'<span class="n">{sum(len(g["cards"]) for g in gs)}</span></summary><ul>{lis}</ul></details></li>')

    def chips(dim, items):
        return (f'<div class="chips" data-dim="{dim}" role="group">'
                + "".join(f'<button type="button" class="chip" data-v="{esc(v)}" aria-pressed="false">'
                          f'{esc(label)} <span class="n">{n}</span></button>' for v, label, n in items if n)
                + "</div>")
    n_kind = {k: sum(f["kind"] == k for f in findings) for k in KINDS}
    n_stage = {k: sum(f["stage"] == k for f in findings) for k in STAGES}
    n_col = {c: sum(finding_doc(f).split("/")[0] == c for f in findings) for c in WORK_COLLECTIONS}
    bar = ('<div class="ffilter" role="search">'
           '<input type="search" id="fq" placeholder="חיפוש בממצאים: מילה, מזהה, סעיף…" aria-label="חיפוש בממצאים">'
           '<div class="frow"><span class="flabel">סוג</span>'
           + chips("kind", [(k, KINDS[k][0], n_kind[k]) for k in KINDS]) + '</div>'
           '<div class="frow"><span class="flabel">שלב</span>'
           + chips("stage", [(k, STAGES[k][0], n_stage[k]) for k in STAGES]) + '</div>'
           '<div class="frow"><span class="flabel">אוסף</span>'
           + chips("col", [(c, cols.get(c, c), n_col[c]) for c in WORK_COLLECTIONS]) + '</div>'
           f'<div class="fstat">מוצגים <b id="fshown">{len(findings)}</b> מתוך {len(findings)}'
           '<span class="fbtns"><button type="button" id="fopen">פתיחת הכול</button>'
           '<button type="button" id="fclose">סגירת הכול</button>'
           '<button type="button" id="freset">ניקוי הסינון</button></span></div></div>')
    intro = ('<h1>ממצאי L4</h1><p class="lede">מה ש<strong>הכללים</strong> טועים בו כשכותבים אותם '
             'באופן פורמלי — לא מה שעמוד מדפיס בטעות (טעות דפוס שהקורפוס תיקן נלקחת '
             'כאן כמתוקנת). לכל ממצא שתי תוויות: <strong>הסוג</strong>, מה לא תקין בחוק, '
             'ו<strong>השלב</strong>, מה גילה אותו. שורה אחת לכל פגם, לא לכל הודעה. כל ממצא נשען על '
             '<code>#ASSERT</code> בקוד שמתקיים כל עוד הפגם בטקסט; אם הטקסט יתוקן, הבדיקה תיכשל והממצא '
             'יתיישן. ממצא הוא קריאה משפטית, ולכן הוא מציין של מי הקריאה והאם עורך הדין ראה אותו.</p>'
             '<p>הממצאים מקובצים לפי הסעיף או החוזר שהם עוסקים בו, וכל ממצא מקופל לכותרתו: '
             'לחיצה פותחת אותו. אפשר לסנן לפי סוג, שלב ואוסף, לחפש מילה, או ללחוץ על משבצת בטבלה.</p>'
             '<p><a href="findings.json">findings.json</a> — אותם ממצאים, למכונות, עם כתובות בקורפוס.</p>')
    body = (intro + matrix + bar
            + (f'<div class="findings">{sections}</div><p class="empty fnone" hidden>אין ממצאים שמתאימים לסינון.</p>'
               if sections else '<p class="empty">אין עדיין ממצאים.</p>'))
    return page("findings.html", f"ממצאי L4 — {TITLE}", body, tab="findings", sidebar="".join(side))


# The salary as the L4 computes it: §1.1's rule and what it is made of.
SALARY = ("takanon/takanon-sherut-ovdei-horaa.xml", "1.1")
SALARY_RULE = "salary of a teaching employee"


def salary_page(all_views: dict[str, list["SectionView"]]) -> str:
    """What the salary is made of, drawn from the L4 itself (tools/rule_graph.py):
    every rule §1.1's salary calls is a box, every input it leaves to the case
    an oval. Not an example: no figure is in it."""
    here = "salary.html"
    v = next((v for v in all_views.get(SALARY[0], []) if v.section.num == SALARY[1]), None)
    drawing = ""
    if v is not None and v.l4 is not None:
        src = rule_graph.dot(rule_graph.declarations(v.l4), SALARY_RULE,
                             rule_graph.clause_labeller(v.section, citations(v.section)))
        svg = rule_graph.svg(src)
        if svg:
            (OUT / "assets").mkdir(parents=True, exist_ok=True)
            (OUT / "assets" / "salary.svg").write_text(svg, encoding="utf-8")
            drawing = ('<div class="salary-box"><a href="assets/salary.svg" target="_blank" rel="noopener" '
                       'title="פתיחה בגודל מלא"><img src="assets/salary.svg" alt="מבנה השכר"></a></div>')
    sec = (f'<a href="{v.href}"><bdi dir="ltr">§{esc(v.section.num)}</bdi> {esc(v.section.heading)}</a>'
           if v is not None else "§1.1")
    body = ('<h1>מבנה השכר</h1>'
            f'<p class="lede">ממה מורכב שכרו של עובד הוראה, כפי שהקוד של {sec} מחשב אותו. '
            'הציור נגזר מן הקוד עצמו: כל תיבה היא כלל, והחצים מובילים מכל רכיב אל מה שהוא חלק ממנו, '
            'עד השכר שבצד ימין. בכל תיבה: מילות הסעיף שהכלל מקודד ומספרו, ומתחתיהן שם הכלל ב־L4. '
            'האליפסות הן הנתונים שהטקסט משאיר לנסיבות של העובד — השכר המשולב למשרה מלאה, החודש, '
            'היקף המשרה, הגמולים שהוא מחזיק — וכל אחת מחוברת למקום שבו נדרשת לראשונה.</p>'
            '<p>אין בציור סכומים: הוא מראה את המבנה, לא חישוב. כלל עזר שאינו מצטט סעיף משלו מופיע בשמו ב־L4 בלבד. '
            'הציור רחב; גוללים בו שמאלה, ולחיצה פותחת אותו בגודל מלא.</p>'
            + (drawing or '<p class="empty">הציור דורש GraphViz בעת הבנייה.</p>'))
    return page(here, f"מבנה השכר — {TITLE}", body, tab="salary")


# the calculator runs L4's evaluator built to WebAssembly (toolchain/build-wasm.sh);
# without the build there is no calculator, rather than one that cannot run
CALCULATOR = (ASSETS / "l4wasm" / "l4.wasm").exists()


def calculator_page(all_views: dict[str, list["SectionView"]], findings: list[dict]) -> str:
    """A form for §1.1's salary rule, evaluated in the browser by L4's own
    evaluator compiled to WebAssembly (tools/calculator.py)."""
    here = "calculator.html"
    v = next(v for v in all_views[SALARY[0]] if v.section.num == SALARY[1])
    s = calculator.spec(v.section, v.l4, {k: clause(v.section, k, k) for k in citations(v.section)})
    s = calculator.ship(s, v.l4, OUT / "assets")
    # the document is named: "§1.1 השכר" alone does not say which text it is
    link = (f'<a href="{v.href}">סעיף {esc(v.section.num)} ("{esc(v.section.heading)}") '
            f'ב{esc(akn.title(v.doc))}</a>')
    mine = [f for f in findings if f.get("l4") == str(v.l4.relative_to(ROOT))]
    body = calculator.body(s, link, mine, rel("findings.html", here))
    return page(here, f"מחשבון שכר — {TITLE}", body, tab="calculator",
                desc="השכר החודשי של עובד הוראה לפי סעיף 1.1 לתקנון, מחושב בדפדפן בקוד ה-L4 של האתר")


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
        detail += "".join(f'<li>#ASSERT נכשל בשורה {line_of(r.get("range"))}</li>' for r in failed)
        detail += "".join(f'<li>הקוד מצטט מפתחות שאינם בחלק: <code>{esc(" ".join(s.keys))}</code></li>'
                          for s in v.unplaced)
        gaps = sum(1 for r in v.text_rows if r.key not in v.covered)
        rows.append(f'<tr><td><a href="{v.href}">§{esc(v.section.num)}</a></td>'
                    f'<td><code>{esc(str(v.l4.relative_to(ROOT)))}</code></td>'
                    f'<td class="{cls}">{"תקין" if cls == "okay" else "שגיאה"}</td>'
                    f'<td>{len(asserts)}</td><td>{gaps}</td><td>{bad}</td></tr>'
                    + (f'<tr class="detail"><td colspan="6"><ul>{detail}</ul></td></tr>' if detail else ""))
    body = ('<h1>בדיקות</h1><p class="lede">מה שמהדר ה-L4 (<code>l4 run</code>) אומר על כל '
            'קובץ: שגיאות טיפוס ותחביר, וכל <code>#ASSERT</code> שנכשל. "פסקאות שלא צוטטו" '
            'סופר את פסקאות הטקסט שאף קטע קוד אינו מצטט. באתר תקין שתי העמודות האחרונות '
            'הן אפס.</p>'
            '<table class="diag"><thead><tr><th>חלק</th><th>קובץ</th><th>מצב</th><th>#ASSERT</th>'
            '<th>פסקאות שלא צוטטו</th><th>בעיות</th></tr></thead><tbody>'
            + "".join(rows) + "</tbody></table>")
    return page("diagnostics.html", f"בדיקות — {TITLE}", body, tab="diagnostics")


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
            f'<span class="sw todo"></span> טרם קודדה — בסעיף שטרם קודד.</p>'
            f'<div class="kpis">'
            f'<div><b>{n_docs_done}</b> / {len(manifest)}<span>מסמכים מקודדים במלואם</span></div>'
            + (f'<div><b>{len(DOCUMENTS) - n_docs_done}</b><span>מסמכים בעבודה</span></div>'
               if len(DOCUMENTS) > n_docs_done else "")
            + f'<div><b>{done}</b> / {len(flat)}<span>חלקים מקודדים במלואם</span></div>'
            f'<div><b>{part}</b><span>חלקים מקודדים בחלקם</span></div>'
            f'<div><b>{t["rule"] + t["note"]}</b> / {paras}<span>פסקאות שנקראו</span></div>'
            f'</div>')
    parts = [head]
    def cell(v: SectionView) -> str:
        n = max(len(v.text_rows), 1)
        name = v.section.num if not v.whole else Path(v.doc).stem
        if v.src is None:
            segs = '<i class="todo" style="flex:1"></i>'
            tip = f"{name} {v.section.heading}: טרם קודד ({len(v.text_rows)} פסקאות)"
        else:
            # a paragraph is read or it is not: whether the L4 beside it is a
            # rule or a note saying why there is none is not coverage
            c = tally(v)
            read = c["rule"] + c["note"]
            segs = "".join(f'<i class="{k}" style="flex:{n}"></i>'
                           for k, n in (("read", read), ("missing", c["missing"])) if n)
            tip = f"{name} {v.section.heading}" + (f": {c['missing']} פסקאות לא צוטטו" if c["missing"] else "")
        return (f'<a class="cell" href="{v.href}" title="{esc(tip)}" style="flex:{n}">{segs}</a>')

    for doc, vs in all_views.items():
        if akn.is_whole(doc):
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
            rows.append(f'<div class="strip-row"><div class="strip-name">פרק <bdi>{esc(s0.chapter_num)}</bdi> · '
                        f'{he(s0.chapter_heading)}</div><div class="strip">{"".join(cell(v) for v in cvs)}</div></div>')
        parts.append(f'<div class="strips">{"".join(rows)}</div>')
        coll = doc.split("/")[0]
        pages = [v for d, pvs in all_views.items() if d.split("/")[0] == coll and is_site_page(d) for v in pvs]
        if pages:
            parts.append(f'<h3 class="cov-group" id="{SITE_ANCHOR}">{esc(SITE_GROUP)}</h3>'
                         '<p class="meta">אינם חלק מהתקנון: תא לכל דף, ורוחבו כמספר פסקאות הדף.</p>'
                         f'<div class="strips"><div class="strip-row"><div class="strip-name">{esc(SITE_GROUP)}</div>'
                         f'<div class="strip">{"".join(cell(v) for v in pages)}</div></div></div>')
    for coll in WORK_COLLECTIONS[1:]:
        cvs_all = [v for d, vs in all_views.items() if d.startswith(coll + "/") for v in vs]
        if not cvs_all:
            continue
        parts.append(f'<h2><a href="{coll}.html">{esc(coll_name(coll))}</a></h2>'
                     '<p class="meta">רצועה לכל שנה, תא לכל מסמך, ורוחבו כמספר פסקאות המסמך.</p>')
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


def about_page() -> str:
    body = f"""<h1>אודות</h1>
<p class="lede">האתר מציב את נוסח קורפוס אופק חדש — המסמכים שמסדירים את העסקת עובדי ההוראה —
ליד קידוד שלו בשפת L4, סעיף אחר סעיף.</p>
<h2>איך קוראים עמוד</h2>
<p>כל שורה היא פסקה אחת של הטקסט: מימין הטקסט כפי שהוא בקורפוס, ומשמאל הכללים שקודדו ממנו.
המתג <em>פרוזה</em> מחליף את הקוד בניסוח בשפה טבעית ש־<code>l4 render</code> מפיק מאותם כללים;
הניסוח הזה, כמו הקוד, באנגלית. תוצאות ה־<code>#ASSERT</code>, <code>#EVAL</code> ו־<code>#TRACE</code>
מופיעות מתחת לקוד שהן בודקות. פסקה שאין בה כלל (רשימת מקורות, הערת תיקון) מסומנת
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
    findings = load_findings()
    FINDINGS_BY_KEY.clear()
    for f in findings:
        for k in f.get("keys", []):
            FINDINGS_BY_KEY.setdefault((finding_doc(f), k), []).append(f)
    all_views: dict[str, list[SectionView]] = {
        doc: [build_view(doc, s) for s in akn.sections(doc)] for doc in DOCUMENTS}
    NAV_VIEWS.clear()
    NAV_VIEWS.update(all_views)
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
        # that begins it
        for vs in chapters:
            ch = vs[0].section.chapter_eid
            for v in vs:
                for k in [v.section.eid, *v.section.keys()]:
                    assert k == ch or k.startswith(ch + "__"), f"{doc}: {k} is not under its chapter {ch}"
        (OUT / f"{doc.removesuffix('.xml')}.html").write_text(contents_page(doc, views), encoding="utf-8")
        for i, p in enumerate(pages):
            (OUT / p).write_text(chapter_page(doc, chapters, i), encoding="utf-8")
        # the per-section pages and the chapter list this site had first
        # now send the reader to the section's anchor on its chapter page
        (d / "index.html").write_text(redirect_page(f"{doc.removesuffix('.xml')}/index.html",
                                                    f"{doc.removesuffix('.xml')}.html", akn.title(doc)), encoding="utf-8")
        for v in views:
            (OUT / v.old_href).write_text(redirect_page(v.old_href, v.href, f"§{v.section.num}"), encoding="utf-8")
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
    (OUT / "salary.html").write_text(salary_page(all_views), encoding="utf-8")
    if CALCULATOR:
        (OUT / "calculator.html").write_text(calculator_page(all_views, findings), encoding="utf-8")
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
