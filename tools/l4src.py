"""Split an .l4 file into the SEGMENTS the site sets beside the text.

The alignment is carried by the source itself, so it cannot drift from it:

  @ref akn:<key>            on a declaration: this rule encodes <key>
  -- akn:<key> <note>        a clause that carries no rule, and why

<key> is a row key from tools/akn.py — an eId, or "<eId>/p<N>". One marker
line may name several keys ("akn:A akn:B"); the segment is shown beside the
first and the others point at it.

A segment starts at its marker, backed up over the comment, annotation and
`§` lines directly above it (no blank line between), and runs to the next
segment's start. Lines before the first segment are the file's PREAMBLE —
imports and the vocabulary the section's rules share.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from pathlib import Path

KEY = re.compile(r"akn:([^\s\"';,]+)")
REF_LINE = re.compile(r'^\s*@ref\s+(.*)$')
NOTE_LINE = re.compile(r"^\s*--\s*akn:")
LEAD_LINE = re.compile(r"^\s*(--|@|§)")


@dataclass
class Segment:
    keys: list[str]
    start: int            # 1-based first line
    end: int              # 1-based last line (inclusive)
    lines: list[str]
    note_only: bool       # a "-- akn:" note, no rule
    results: list[dict] = field(default_factory=list)
    diagnostics: list[dict] = field(default_factory=list)

    @property
    def note(self) -> str:
        """The reason a no-rule clause carries no rule."""
        if not self.note_only:
            return ""
        text = " ".join(self.lines)
        text = re.sub(r"^\s*--\s*", "", text)
        text = KEY.sub("", text)
        text = re.sub(r"\s*--\s*", " ", text)
        return " ".join(text.split())


def lead_notes(lines: list[str]) -> list[str]:
    """The reasons of the `-- akn:` notes a segment carries above its code."""
    out, cur = [], None
    for line in lines:
        if NOTE_LINE.match(line):
            if cur is not None:
                out.append(cur)
            cur = KEY.sub("", re.sub(r"^\s*--\s*", "", line)).strip()
        elif cur is not None and line.strip().startswith("--"):
            cur += " " + re.sub(r"^\s*--\s*", "", line).strip()
        elif cur is not None:
            out.append(cur)
            cur = None
    if cur is not None:
        out.append(cur)
    return [" ".join(n.split()) for n in out]


@dataclass
class Source:
    path: Path
    lines: list[str]
    preamble: tuple[int, int]
    segments: list[Segment]

    def by_key(self) -> dict[str, Segment]:
        out = {}
        for s in self.segments:
            for k in s.keys:
                out.setdefault(k, s)
        return out


def marker_keys(line: str) -> list[str] | None:
    m = REF_LINE.match(line)
    if m:
        return KEY.findall(m.group(1))
    if NOTE_LINE.match(line):
        return KEY.findall(line)
    return None


def parse(path: Path) -> Source:
    lines = path.read_text(encoding="utf-8").split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    markers = [(i, k) for i, line in enumerate(lines)
               if (k := marker_keys(line))]
    starts = []
    for i, keys in markers:
        j = i
        while True:
            while (j - 1 >= 0 and LEAD_LINE.match(lines[j - 1])
                   and marker_keys(lines[j - 1]) is None):
                j -= 1
            # a `§` heading above a blank line heads the rule below it too
            k = j
            while k - 1 >= 0 and not lines[k - 1].strip():
                k -= 1
            if k < j and k - 1 >= 0 and lines[k - 1].lstrip().startswith("§"):
                j = k - 1
                continue
            break
        # lines running straight up into another marker are THAT marker's
        # continuation, not this one's lead
        if j - 1 >= 0 and marker_keys(lines[j - 1]) is not None:
            j = i
        starts.append((j, i, keys))
    segs = []
    for n, (start, mark, keys) in enumerate(starts):
        stop = starts[n + 1][0] if n + 1 < len(starts) else len(lines)
        while stop - 1 > mark and not lines[stop - 1].strip():
            stop -= 1
        note_only = bool(NOTE_LINE.match(lines[mark])) and all(
            l.strip() == "" or l.lstrip().startswith("--")
            for l in lines[mark:stop])
        segs.append(Segment(keys, start + 1, stop, lines[start:stop],
                            note_only))
    first = starts[0][0] if starts else len(lines)
    # 1-based [start, stop): the lines before the first segment
    return Source(path, lines, (1, first + 1), segs)


def segment_at(src: Source, line: int) -> Segment | None:
    for s in src.segments:
        if s.start <= line <= s.end:
            return s
    return None


# ---------------------------------------------------------------- highlight

TOKEN = re.compile(r"""
    (?P<comment>--.*$)
  | (?P<string>"(?:[^"\\]|\\.)*")
  | (?P<tick>`[^`]*`)
  | (?P<annot>@[a-z-]+)
  | (?P<directive>\#[A-Z]+)
  | (?P<section>§+)
  | (?P<number>\b\d[\d_]*(?:\.\d+)?%?)
  | (?P<keyword>\b[A-Z][A-Z]+(?:'S)?\b)
  | (?P<op>\^|\.\.\.?|'s\b)
""", re.VERBOSE)


def highlight(line: str) -> str:
    out, pos = [], 0
    for m in TOKEN.finditer(line):
        out.append(html.escape(line[pos:m.start()]))
        kind = m.lastgroup
        text = html.escape(m.group())
        if kind == "comment":
            # a marker's key is a link to the row it sits beside
            text = KEY.sub(lambda k: f'<a class="k" href="#{html.escape(k.group(1))}">'
                           f'akn:{html.escape(k.group(1))}</a>', html.escape(m.group()))
        out.append(f'<span class="t-{kind}">{text}</span>')
        pos = m.end()
    out.append(html.escape(line[pos:]))
    return "".join(out)


def code_html(lines: list[str], first: int) -> str:
    return numbered_html(list(enumerate(lines, first)))


def numbered_html(numbered: list[tuple[int, str]]) -> str:
    """One element per line, so a long line wraps under itself (keeping its
    indent) instead of running off the panel."""
    rows = []
    prev = None
    for n, line in numbered:
        if prev is not None and n != prev + 1:
            rows.append('<span class="line skip"><span class="ln"></span><span class="lc">⋯</span></span>')
        indent = len(line) - len(line.lstrip(" "))
        rows.append(f'<span class="line" style="--i:{indent}"><span class="ln" data-n="{n}"></span>'
                    f'<span class="lc">{highlight(line) or " "}</span></span>')
        prev = n
    return '<pre class="code" dir="ltr"><code>' + "".join(rows) + "</code></pre>"


def for_reading(lines: list[str], first: int) -> list[tuple[int, str]]:
    """A segment as the comparison shows it: without the lines that only
    serve the alignment (`@ref akn:…`, `§` headings) and without blank runs.
    The full source is a link away; nothing here changes a rule."""
    out: list[tuple[int, str]] = []
    in_note = False
    for n, line in enumerate(lines, first):
        t = line.strip()
        # a "-- akn:<key> <reason>" note and its continuation lines are shown
        # as the note's label, not as code
        if NOTE_LINE.match(line):
            in_note = True
            continue
        if in_note and t.startswith("--"):
            continue
        in_note = False
        if REF_LINE.match(line) and KEY.search(line) and not KEY.sub("", REF_LINE.match(line).group(1)).strip():
            continue
        if t.startswith("§"):
            continue
        if not t and (not out or not out[-1][1].strip()):
            continue
        out.append((n, line))
    while out and not out[-1][1].strip():
        out.pop()
    return out
