"""Read the vendored corpus snapshot (corpus/akn/) into what the site shows.

The corpus is the source of the TEXT; this repository never edits it. A
section is read into ROWS, one per thing the reader sees: a numbered or
headed element's label, and each <p>. Every row has a KEY, which is what an
L4 file cites to sit beside it:

  * an element's eId — its label row (which, when the label is a bare number,
    is also the row of its first <p>), or, with no label, its first <p>
  * "<eId>/p<N>" — the N-th <p> (1-based) held directly by that element,
    for the clauses the corpus publishes as running paragraphs without an
    eId of their own (§1.23 is one)

A sic mark is the corpus's: its <noteRef class="sic"> and the <note> it
points to are carried through as given, never re-read here (README, "The
corpus decides the text").
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "corpus" / "akn"
AKN = "{http://docs.oasis-open.org/legaldocml/ns/akn/3.0}"

# elements that carry a number or heading of their own in this corpus
STRUCTURE = {"chapter", "section", "subsection", "paragraph", "subparagraph",
             "clause", "point", "hcontainer", "article", "part", "list",
             "item", "indent"}


@dataclass
class Run:
    """A stretch of a row's text; `sic` is the corpus note on the stretch."""
    text: str
    sic: str | None = None


@dataclass
class Row:
    key: str
    depth: int
    kind: str                      # "label" | "text"
    num: str = ""
    heading: str = ""
    runs: list[Run] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "".join(r.text for r in self.runs)


@dataclass
class Section:
    eid: str
    num: str
    heading: str
    chapter_eid: str
    chapter_num: str
    chapter_heading: str
    rows: list[Row]

    @property
    def slug(self) -> str:
        return self.num

    def keys(self) -> set[str]:
        out = set()
        for r in self.rows:
            out.add(r.key)
            out.update(r.aliases)
        return out


def squash(s: str) -> str:
    return " ".join(s.replace("​", "").split())


def tag(e) -> str:
    return e.tag.replace(AKN, "")


def label_of(e) -> tuple[str, str]:
    num = e.find(AKN + "num")
    head = e.find(AKN + "heading")
    return (squash("".join(num.itertext())) if num is not None else "",
            squash("".join(head.itertext())) if head is not None else "")


@lru_cache(maxsize=None)
def load(relative: str):
    return ET.parse(CORPUS / relative).getroot()


def sic_notes(root) -> dict[str, str]:
    return {n.get("eId"): squash("".join(n.itertext()))
            for n in root.iter(AKN + "note") if n.get("class") == "sic"}


def runs_of(p, notes: dict[str, str]) -> list[Run]:
    """The text of a <p>, split where the corpus marks a sic.

    The corpus puts <noteRef class="sic" href="#note"> right after the words
    the page prints wrongly; the run before it is what the mark is about."""
    out: list[Run] = []

    def walk(e):
        if e.text:
            out.append(Run(e.text))
        for ch in e:
            if tag(ch) == "noteRef" and ch.get("class") == "sic":
                note = notes.get((ch.get("href") or "").lstrip("#"), "כך במקור")
                if out:
                    out[-1].sic = note
                else:
                    out.append(Run("", note))
            elif tag(ch) == "note":
                pass
            else:
                walk(ch)
            if ch.tail:
                out.append(Run(ch.tail))
    walk(p)
    # collapse whitespace across runs without losing the sic boundaries
    merged: list[Run] = []
    for r in out:
        t = re.sub(r"\s+", " ", r.text.replace("​", ""))
        if merged and merged[-1].sic is None and r.sic is None:
            merged[-1].text += t
        else:
            merged.append(Run(t, r.sic))
    if merged:
        merged[0].text = merged[0].text.lstrip()
        merged[-1].text = merged[-1].text.rstrip()
    return [r for r in merged if r.text or r.sic]


def section_rows(sec, notes) -> list[Row]:
    rows: list[Row] = []

    def walk(e, holder: str, depth: int, counter: dict):
        for ch in e:
            t = tag(ch)
            if t in ("num", "heading", "note"):
                continue
            if t == "p":
                counter[holder] = counter.get(holder, 0) + 1
                key = f"{holder}/p{counter[holder]}"
                row = Row(key, depth, "text", runs=runs_of(ch, notes))
                if not row.text.strip() and not any(r.sic for r in row.runs):
                    continue
                # a numbered clause and its first paragraph are one row: the
                # number is printed before the words, and a rule citing the
                # clause sits beside them
                last = rows[-1] if rows else None
                if (counter[holder] == 1 and last is not None and last.kind == "label"
                        and last.key == holder and not last.heading):
                    last.kind, last.runs = "text", row.runs
                    last.aliases.append(key)
                    continue
                # an element with no label of its own is cited by its eId
                # and lands on its first paragraph
                if counter[holder] == 1 and holder not in labelled:
                    row.aliases.append(holder)
                rows.append(row)
                continue
            eid = ch.get("eId")
            if eid and t in STRUCTURE:
                num, head = label_of(ch)
                if num or head:
                    labelled.add(eid)
                    rows.append(Row(eid, depth, "label", num, head))
                walk(ch, eid, depth + 1, counter)
            else:
                walk(ch, holder, depth, counter)

    labelled: set[str] = set()
    walk(sec, sec.get("eId"), 0, {})
    return rows


# the corpus repeats the portal's breadcrumb as each section's first block
BREADCRUMB = re.compile(r"^תחום תנאי שירות עובדי הוראה תקנון שירות עובדי הוראה")


def sections(relative: str) -> list[Section]:
    root = load(relative)
    notes = sic_notes(root)
    out = []
    for chap in root.iter(AKN + "chapter"):
        cnum, chead = label_of(chap)
        secs = [s for s in chap if tag(s) == "section"]
        if not secs:
            # a chapter the corpus holds as one block (9, 10, 11, 14)
            secs = [chap]
        for s in secs:
            num, head = label_of(s)
            rows = section_rows(s, notes)
            rows = [r for r in rows if not BREADCRUMB.match(r.text)]
            if s is chap:
                num, head = cnum, chead
                rows = [r for r in rows if r.key != s.get("eId")]
            out.append(Section(s.get("eId"), num, head, chap.get("eId"),
                               cnum, chead, rows))
    return out


def title(relative: str) -> str:
    root = load(relative)
    lt = root.find(f".//{AKN}longTitle")
    return squash("".join(lt.itertext())) if lt is not None else relative
