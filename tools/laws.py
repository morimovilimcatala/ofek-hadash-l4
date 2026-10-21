r"""The statutes the L4 encodes outside the corpus (MMS-516).

The corpus holds no copy of a statute (its standing decision 14); the client
asked for statutes in L4 anyway ("don't encode it in AKN, only in L4",
2026-10-20) — the Collective Agreements Law (MMS-516) and the Budget
Foundations Law (MMS-528). Its words are pinned in laws/<name>.toml, a row per section with
the anchor of the live page of ספר החוקים הפתוח it is read from, and its rules
are l4/laws/<name>.l4, a `§§ \`N\`` block per section citing `@ref law:N`.
The site sets each section's text beside its block, as it does for a corpus
section.
"""
from __future__ import annotations

import re
import tomllib
import urllib.parse
from pathlib import Path

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


def page_body(name: str, *, code_html, esc) -> str:
    law = load(name)
    head, secs = blocks(name)
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
                    f'<p>{esc(s["text"])}</p></div>'
                    f'<div class="l4">{code_html(block) if block else ""}</div></div>')
    return (f'<h1 lang="he" dir="rtl">{esc(law["title"])}</h1>'
            f'<p class="lede">{esc(law["about"])} — מקודד ב־L4, סעיף לצד סעיף. הקורפוס אינו מחזיק עותק של החוק: '
            f'הנוסח כאן נקרא מספר החוקים הפתוח, ונבדק מולו לאחרונה ב־{esc(law["text_as_of"])}. '
            '<a href="contradictions.html">עמוד הסתירות</a> מצטט את הסעיפים האלה כשהוא אומר מי גובר.</p>'
            '<div class="colheads"><div class="ch-l4">L4</div><div class="ch-text">הטקסט</div></div>'
            f'<div class="grid">{"".join(rows)}</div>')
