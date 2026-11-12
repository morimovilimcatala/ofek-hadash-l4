r"""The statutes the L4 encodes outside the corpus (MMS-516).

The corpus holds no copy of a statute (its standing decision 14); the client
asked for statutes in L4 anyway ("don't encode it in AKN, only in L4",
2026-10-20) — the Collective Agreements Law (MMS-516), the Budget
Foundations Law (MMS-528), the protective statutes of MMS-601 and the
others laws/ holds. Its words are pinned in laws/<name>.toml, a row per section with
the anchor of the live page of ספר החוקים הפתוח it is read from, and its rules
are l4/laws/<name>.l4, a `§§ \`N\`` block per section citing `@ref law:N`.
The site sets each section's text beside its block, as it does for a corpus
section.

Which statutes, and which of their sections, the corpus itself cites is
data/statute-citations.json (tools/statute_citations.py, MMS-601): each law's
page says where the corpus cites it, and laws/index.html lists every act the
corpus cites, with the sections the L4 has pinned marked.
"""
from __future__ import annotations

import re
import tomllib
import urllib.parse
from pathlib import Path

import statute_citations

ROOT = Path(__file__).resolve().parent.parent
TEXTS = ROOT / "laws"
L4 = ROOT / "l4" / "laws"
REF = re.compile(r"@ref\s+law:(\S+)")
BLOCK = re.compile(r"^§§ `([^`]+)`\s*$")


def all_laws() -> list[str]:
    return sorted(p.stem for p in TEXTS.glob("*.toml"))


def load(name: str) -> dict:
    return tomllib.loads((TEXTS / f"{name}.toml").read_text(encoding="utf-8"))


def l4_file(name: str) -> Path:
    return L4 / f"{name}.l4"


def blocks(name: str) -> tuple[list[tuple[int, str]], dict[str, list[tuple[int, str]]]]:
    """The file's lines before its first section block, and each section's
    block, as (line number, text)."""
    lines = l4_file(name).read_text(encoding="utf-8").splitlines()
    head: list[tuple[int, str]] = []
    out: dict[str, list[tuple[int, str]]] = {}
    cur = None
    for n, line in enumerate(lines, 1):
        m = BLOCK.match(line)
        if m:
            cur = m.group(1)
            out[cur] = []
        (out[cur] if cur else head).append((n, line))
    return head, out


def cited(name: str) -> set[str]:
    return set(REF.findall(l4_file(name).read_text(encoding="utf-8")))


def span(law: dict) -> str:
    """The sections a law's page holds, as a reader names them: a run
    "19–23", otherwise a list "21, 29, 32"."""
    nums = [s["num"] for s in law["section"]]
    if all(n.isdigit() for n in nums) and [int(n) for n in nums] == list(range(int(nums[0]), int(nums[-1]) + 1)):
        return f"{nums[0]}–{nums[-1]}" if len(nums) > 1 else nums[0]
    return ", ".join(nums)


def anchor(law: dict, num: str) -> str:
    """The live page's anchor for a section, as the corpus links acts."""
    return f'{law["url"]}#{urllib.parse.quote("סעיף_" + num)}'


def same_page(a: str, b: str) -> bool:
    """Whether two links name the same live page, however they are quoted."""
    def norm(u: str) -> str:
        return urllib.parse.unquote(u).split("#")[0].replace(" ", "_")
    return norm(a) == norm(b)


def corpus_citations(law: dict) -> dict | None:
    """The inventory's row for a law: the documents that cite it and the
    sections they cite by number (None if the corpus does not cite it)."""
    inv = statute_citations.load() or {"acts": []}
    return next((a for a in inv["acts"] if same_page(a["url"], law["url"])), None)


def pinned() -> dict[str, tuple[str, set[str]]]:
    """{the live page's title: (the law's name here, the sections pinned)}."""
    out = {}
    for n in all_laws():
        law = load(n)
        title = urllib.parse.unquote(law["url"].split("/wiki/", 1)[1]).replace("_", " ")
        out[title] = (n, {s["num"] for s in law["section"]})
    return out


def documents(n: int) -> str:
    return "מסמך אחד" if n == 1 else f"{n} מסמכים"


def citations_note(law: dict, esc) -> str:
    """Where the corpus cites a law: the documents, and the sections by number."""
    row = corpus_citations(law)
    if row is None:
        return '<p class="lede">הקורפוס אינו מקשר לחוק הזה.</p>'
    mine = {s["num"] for s in law["section"]}
    secs = []
    for s in row["sections"]:
        note = "" if s["anchored"] else ", בלי קישור"
        where = "" if s["num"] in mine else " — לא מקודד כאן"
        secs.append(f'{esc(s["num"])} ({documents(s["documents"])}{note}{where})')
    what = "את הסעיפים " if len(secs) > 1 else "את סעיף "
    by_num = ("; במספרם הוא מצטט " + what + ", ".join(secs)) if secs else \
        "; אף סעיף אינו מצוטט שם במספרו, רק החוק בשמו"
    return (f'<p class="lede">הקורפוס מקשר לחוק ב־{documents(row["documents"])}{by_num}. '
            '<a href="index.html">כל החוקים שהקורפוס מצטט</a>.</p>')


def cards_naming(name: str) -> list[str]:
    """The contradictions page's cards that set this law beside an
    instrument: a side that is the law, or a link to its page. The law's
    page says the contradictions page cites it only where one does."""
    import json
    data = ROOT / "data" / "contradictions.json"
    if not data.exists():
        return []
    page = f"laws/{name}.html"
    return [c["id"] for c in json.loads(data.read_text(encoding="utf-8"))["items"]
            if any(side.get("law") == name for side in c["sides"])
            or page in json.dumps(c, ensure_ascii=False)]


def page_body(name: str, *, code_html, esc) -> str:
    law = load(name)
    head, secs = blocks(name)
    cites = {s["num"]: s for s in (corpus_citations(law) or {"sections": []})["sections"]}
    rows = []
    shared = [(n, t) for n, t in head if t.strip() and not t.startswith(("--", "IMPORT", "§ "))]
    if shared:
        rows.append('<div class="row d1"><div class="txt" lang="he" dir="rtl"><span class="lawnote">'
                    f'הגדרה משותפת לסעיפים שלהלן: {esc(law["shared"])}</span></div>'
                    f'<div class="l4">{code_html(shared)}</div></div>')
    for s in law["section"]:
        block = secs.get(s["num"], [])
        rows.append(f'<div class="row d1" id="s{esc(s["num"])}"><div class="txt" lang="he" dir="rtl">'
                    f'<span class="num">{esc(s["num"])}.</span><span class="h">{esc(s["heading"])}</span> '
                    f'<a class="lawlink" href="{esc(anchor(law, s["num"]))}">בספר החוקים הפתוח</a>'
                    + (f'<span class="lawnote"> · מצוטט במספרו ב־{documents(cites[s["num"]]["documents"])} בקורפוס</span>'
                       if s["num"] in cites else "")
                    + f'<p>{esc(s["text"])}</p></div>'
                    f'<div class="l4">{code_html(block) if block else ""}</div></div>')
    return (f'<h1 lang="he" dir="rtl">{esc(law["title"])}</h1>'
            f'<p class="lede">{esc(law["about"])} — מקודד ב־L4, סעיף לצד סעיף. הקורפוס אינו מחזיק עותק של החוק: '
            f'הנוסח כאן נקרא מספר החוקים הפתוח, ונבדק מולו לאחרונה ב־{esc(law["text_as_of"])}. '
            + ('<a href="../contradictions.html">עמוד הסתירות</a> מצטט את הסעיפים האלה כשהוא אומר מי גובר.'
               if cards_naming(name) else "")
            + '</p>'
            + citations_note(law, esc) +
            '<div class="colheads"><div class="ch-l4">L4</div><div class="ch-text">הטקסט</div></div>'
            f'<div class="grid">{"".join(rows)}</div>')


def index_body(esc) -> str:
    """laws/index.html: every act the corpus cites, the documents that cite
    it, the sections it cites by number, and which of them the L4 pins."""
    inv = statute_citations.load() or {"acts": [], "corpus": ""}
    mine = pinned()
    rows = []
    for a in inv["acts"]:
        here = mine.get(a["title"])
        name = (f'<a href="{esc(here[0])}.html">{esc(a["title"])}</a>' if here else esc(a["title"]))
        secs = []
        for s in a["sections"]:
            label = f'{esc(s["num"])} ({s["documents"]}{"" if s["anchored"] else ", בלי קישור"})'
            secs.append(f'<a href="{esc(here[0])}.html#s{esc(s["num"])}">{label}</a>'
                        if here and s["num"] in here[1] else label)
        enc = ", ".join(esc(n) for n in sorted(here[1], key=lambda n: (len(n), n))) if here else "—"
        rows.append(f'<tr><td>{name} <a class="lawlink" href="{esc(a["url"])}" title="בספר החוקים הפתוח">↗</a></td>'
                    f'<td>{a["documents"]}</td><td>{a["citations"]}</td>'
                    f'<td>{"; ".join(secs) or "—"}</td><td>{enc}</td></tr>')
    encoded = sum(1 for a in inv["acts"] if a["title"] in mine)
    return ('<h1>החוקים שהקורפוס מצטט</h1>'
            '<p class="lede">הקורפוס אינו מחזיק עותק של חוק: כל אזכור של חוק בו הוא קישור לדף החי של החוק '
            'בספר החוקים הפתוח, ואזכור של סעיף נושא את העוגן של הסעיף. הטבלה נקראת מהקישורים האלה עצמם '
            f'(<code dir="ltr">data/statute-citations.json</code>, מתמונת הקורפוס <code dir="ltr">{esc(inv["corpus"][:8])}</code>): '
            'לכל חוק, כמה מסמכים מקשרים אליו, וכל סעיף שמצוטט במספרו וכמה מסמכים מצטטים אותו. '
            f'מתוך {len(inv["acts"])} החוקים, {encoded} מקודדים כאן ב־L4, וסעיף מקודד הוא קישור לדף החוק.</p>'
            '<div class="tablewrap"><table class="grid-table"><thead><tr><th>חוק</th><th>מסמכים</th>'
            '<th>קישורים</th><th>סעיפים שמצוטטים במספרם (מסמכים)</th><th>סעיפים מקודדים כאן</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')
