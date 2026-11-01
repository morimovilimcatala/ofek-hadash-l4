"""Every statute the corpus cites, and every section of it (MMS-601).

    python3 tools/statute_citations.py --write   # record it in data/statute-citations.json
    python3 tools/statute_citations.py           # exit 1 if the record is stale

The corpus holds no copy of a statute (its standing decision 14): an act
citation is a link to the law's live page of ספר החוקים הפתוח on
he.wikisource, and a citation of a section of it carries the page's anchor,
`#סעיף_N`, where the page has one. So the corpus itself says which laws and
which sections it cites, and this reads it off the snapshot in corpus/akn/:
for each act, the documents that cite it, and for each section, the
documents and the rows (the eId of the nearest element that has one).

A section printed after the act's name with no anchor of its own — "חוק
הגנת השכר, תשי"ח - 1985, סעיף 20" — is a section citation too, and is
recorded as one, marked `anchored: false`: the corpus's linker anchors only
"סעיף N ל<act>".

The record is the denominator of the statutes' work: the laws pages read it
(tools/laws.py), and tests/test_statute_citations.py holds it to the corpus,
so a re-sync that adds a citation goes red until it is re-recorded. Which
of the cited sections the L4 encodes is not recorded here: the pages join
it with laws/*.toml, so it can never drift from what is pinned.
"""
from __future__ import annotations

import json
import re
import sys
import tomllib
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "corpus" / "akn"
RECORD = ROOT / "data" / "statute-citations.json"
WIKI = "https://he.wikisource.org/wiki/"
NS = "{http://docs.oasis-open.org/legaldocml/ns/akn/3.0}"
# what may stand between an act's name and a section number printed after
# it: the year ("התשמ"ז-1987", "תשי"ח - 1985", "תשי"ד / 1954") and its commas
AFTER = re.compile(r'^\s*,?\s*(?:ה?תש[א-ת"״׳\']+\s*[-–—/]?\s*\d{4}\s*)?,?\s*סעיף\s+(\d+[א-ת]?)(?!\d|\.\d)')


def act_of(href: str) -> tuple[str, str | None]:
    """(the act's page title, the section its anchor names or None)."""
    page, _, anchor = urllib.parse.unquote(href[len(WIKI):]).partition("#")
    sec = anchor.removeprefix("סעיף_") if anchor.startswith("סעיף_") else None
    return page.replace("_", " "), sec


def citations() -> list[dict]:
    """Every act citation in the corpus snapshot, as {act, section,
    anchored, doc, eId}."""
    out = []
    for f in sorted(CORPUS.rglob("*.xml")):
        doc = f.relative_to(CORPUS).as_posix()
        root = ET.parse(f).getroot()
        parent = {c: p for p in root.iter() for c in p}

        def holder(e) -> str:
            while e is not None:
                if e.get("eId"):
                    return e.get("eId")
                e = parent.get(e)
            return ""

        for e in root.iter(f"{NS}ref"):
            href = e.get("href", "")
            if not href.startswith(WIKI):
                continue
            act, sec = act_of(href)
            anchored = sec is not None
            if not anchored:
                m = AFTER.match(e.tail or "")
                sec = m.group(1) if m else None
            out.append({"act": act, "section": sec, "anchored": anchored, "doc": doc, "eId": holder(e)})
    return out


def snapshot() -> str:
    return tomllib.loads((ROOT / "corpus" / "SOURCE.toml").read_text(encoding="utf-8"))["commit"]


def inventory() -> dict:
    cites = citations()
    acts: dict[str, dict] = {}
    for c in cites:
        a = acts.setdefault(c["act"], {"title": c["act"], "url": WIKI + urllib.parse.quote(c["act"].replace(" ", "_")),
                                       "documents": set(), "citations": 0, "sections": {}})
        a["documents"].add(c["doc"])
        a["citations"] += 1
        if c["section"]:
            s = a["sections"].setdefault(c["section"], {"num": c["section"], "anchored": False,
                                                         "documents": set(), "rows": []})
            s["anchored"] = s["anchored"] or c["anchored"]
            s["documents"].add(c["doc"])
            row = {"doc": c["doc"], "eId": c["eId"]}
            if row not in s["rows"]:
                s["rows"].append(row)
    rows = []
    for a in acts.values():
        secs = sorted(a["sections"].values(), key=lambda s: (-len(s["documents"]), s["num"]))
        rows.append({"title": a["title"], "url": a["url"], "documents": len(a["documents"]),
                     "citations": a["citations"], "cited_by": sorted(a["documents"]),
                     "sections": [{"num": s["num"], "anchored": s["anchored"], "documents": len(s["documents"]),
                                   "rows": sorted(s["rows"], key=lambda r: (r["doc"], r["eId"]))} for s in secs]})
    rows.sort(key=lambda a: (-a["documents"], a["title"]))
    return {"about": "Every statute the corpus cites (a link to its live page on ספר החוקים הפתוח), "
                     "the documents that cite it, and every section it cites by number; "
                     "written by tools/statute_citations.py from corpus/akn/ — do not edit by hand.",
            "corpus": snapshot(), "acts": rows}


def render(inv: dict) -> str:
    return json.dumps(inv, ensure_ascii=False, indent=1) + "\n"


def load() -> dict | None:
    return json.loads(RECORD.read_text(encoding="utf-8")) if RECORD.exists() else None


def main(argv: list[str]) -> int:
    text = render(inventory())
    if "--write" in argv:
        RECORD.write_text(text, encoding="utf-8")
        return 0
    if not RECORD.exists() or RECORD.read_text(encoding="utf-8") != text:
        print("data/statute-citations.json is stale: python3 tools/statute_citations.py --write", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
