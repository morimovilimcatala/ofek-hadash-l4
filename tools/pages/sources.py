"""The calculator, the contradictions page, the statutes' pages and the
statute record, and findings.json.
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
from pages.model import *  # noqa: E402,F401,F403
from pages.layout import *  # noqa: E402,F401,F403
from pages.documents import *  # noqa: E402,F401,F403
from pages.home import *  # noqa: E402,F401,F403
from pages.findings import *  # noqa: E402,F401,F403

def calculator_page(all_views: dict[str, list["SectionView"]], findings: list[dict]) -> str:
    """A form for §1.1's salary rule, evaluated in the browser by L4's own
    evaluator compiled to WebAssembly (tools/calculator.py)."""
    here = "calculator.html"
    v = next(v for v in all_views[SALARY[0]] if v.section.num == SALARY[1])
    s = calculator.spec(v.section, v.l4, {k: clause(v.section, k, k) for k in citations(v.section)},
                        href=lambda k: f"{v.page}#{k}")
    s = calculator.ship(s, OUT / "assets")
    # each instrument the root may name, by its module: its page on the site
    flat = [x for vs in all_views.values() for x in vs]
    by_file = {str(x.l4.relative_to(ROOT)): x for x in flat if x.l4}
    s["pages"] = {}
    for name, f in modules.wanted()[0].items():
        x = by_file.get(str(f.relative_to(ROOT)))
        if x is not None:
            s["pages"][name] = rel(x.href, here)
    s["contradictions"] = rel(contradictions.HERE, here)
    # the document is named: "§1.1 השכר" alone does not say which text it is
    link = (f'<a href="{v.href}">סעיף {esc(v.section.num)} ("{esc(v.section.heading)}") '
            f'ב{esc(akn.title(v.doc))}</a>')
    mine = [f for f in findings if f.get("l4") == str(v.l4.relative_to(ROOT))]
    body = calculator.body(s, link, mine, rel("findings.html", here),
                           code_href=rel(roots_page("salary-root"), here))
    return page(here, f"מחשבון שכר — {TITLE}", body, tab="calculator",
                desc="השכר החודשי של עובד הוראה לפי סעיף 1.1 לתקנון, מחושב בדפדפן בקוד ה-L4 של האתר")


def simulator_group(findings: list[dict], by_file: dict[str, "SectionView"], key_to_view) -> tuple[str, str, int]:
    """Where the ministry's simulator and the text part, by cause: a group of
    the contradictions page (tools/calculator_delta.py; the data is
    data/calculator-delta.json). (section, sidebar entries, rows, the
    grades of its graded rows)."""
    def clause_link(doc: str, key: str) -> tuple[str, str]:
        v = key_to_view.get((doc, key))
        if v is not None:
            return f"{v.page}#{key}", cite_html(v.section, key, sec_ref(v.section), doc)
        eid = key.split("/")[0]
        return (f"{CORPUS_SITE}/{doc.removesuffix('.xml')}.html#{eid}",
                f'<span class="cdoc">{esc(doc_label(doc))}</span> <bdi dir="ltr">{esc(key)}</bdi>')

    def l4_link(file: str) -> str:
        v = by_file.get(file)
        return v.href if v is not None else ""

    html, side = calculator_delta.section(
        DELTA, prose=prose, clause_link=clause_link, finding_ids={f["id"] for f in findings},
        conv_titles=CONVENTION_TITLES, l4_link=l4_link)
    rows = calculator_delta.group_rows(DELTA)
    return html, side, len(rows), [g for g in map(calculator_delta.grade, rows) if g]


def contradictions_page(findings: list[dict], by_file: dict[str, "SectionView"], key_to_view,
                        href_of=lambda m: None) -> str:
    """Where one instrument contradicts another (tools/contradictions.py):
    every contradiction the root finds, generated from its report
    (MMS-521), with the hand-written cards (data/contradictions.json, the
    crops data/contradictions/) attached to its rows or standing where the
    root cannot speak; and where the ministry's simulator departs from the
    text. `href_of(module)` is an instrument's page, from the site root."""
    here = contradictions.HERE
    report = contradictions.root_report()

    def clause_link(doc: str, key: str) -> tuple[str, str]:
        v = key_to_view.get((doc, key))
        if v is not None:
            return f"{v.page}#{key}", cite_html(v.section, key, sec_ref(v.section), doc)
        eid = key.split("/")[0]
        href = f"{CORPUS_SITE}/{doc.removesuffix('.xml')}.html#{eid}"
        if not (ROOT / "corpus" / "akn" / doc).exists():  # newer than the vendored snapshot
            return href, f'בקורפוס <bdi dir="ltr">{esc(key)}</bdi>'
        return href, f'<span class="cdoc">{esc(doc_label(doc))}</span> <bdi dir="ltr">{esc(key)}</bdi>'

    body, side = contradictions.body(
        CONTRA, prose=prose, clause_link=clause_link, finding_ids={f["id"] for f in findings},
        src=lambda f: rel(f"assets/contradictions/{f}", here),
        simulator=simulator_group(findings, by_file, key_to_view) if DELTA else None,
        evidence={f["id"]: (f["l4"], f["evidence"].strip("`")) for f in (REGISTER or findings) if f.get("l4") and f.get("evidence")},
        rows=contradictions.root_rows(report) if report is not None else None,
        href_of=lambda m: rel(h, here) if (h := href_of(m)) else None,
        root_href=rel(roots.ROOTS[0][1], here))
    return page(here, f"{contradictions.TAB} — {TITLE}", body, tab="contradictions",
                desc="היכן שמקור אחד סותר מקור אחר — מסמכים, תלושים וסימולטור השכר של המשרד: כל מקור ותשובתו, והכלל שמכריע", sidebar=side)


def law_page(name: str) -> str:
    """A statute the L4 encodes outside the corpus (tools/laws.py, MMS-516)."""
    here = f"laws/{name}.html"
    body = laws.page_body(name, code_html=l4src.numbered_html, esc=esc)
    if any(x["module"] == name for x in STATUTES.get("statutes", [])):
        body += statute_record.law_html(STATUTES, name, esc=esc, link=lambda t: rel(t, here),
                                        doc_href=doc_href, coll_name=coll_name)
    title = laws.load(name)["title"]
    return page(here, f"{title} — {TITLE}", body, desc=f"{title} ב־L4: סעיף לצד סעיף")


def statute_record_page() -> str:
    """Every document of the manifest against every protective statute
    (tools/statute_record.py, MMS-601)."""
    here = statute_record.HERE
    order = [c for c, _ in COLLECTIONS]
    body = statute_record.grid_html(STATUTES, esc=esc, link=lambda t: rel(t, here), doc_href=doc_href,
                                    coll_name=coll_name,
                                    coll_order=lambda cs: sorted(cs, key=lambda c: (order.index(c) if c in order else len(order), c)))
    return page(here, f"המסמכים מול החוקים המגינים — {TITLE}", body, wide=True,
                desc="כל מסמך בקורפוס מול כל חוק מגן: עומד ברצפה, נופל ממנה, לא נשקל ולמה, או לא נבדק")


def laws_index_page() -> str:
    """Every statute the corpus cites (tools/laws.py index_body, MMS-601)."""
    return page("laws/index.html", f"החוקים שהקורפוס מצטט — {TITLE}", laws.index_body(esc),
                desc="כל חוק שהקורפוס מקשר אליו, הסעיפים שהוא מצטט במספרם, ואילו מהם מקודדים ב־L4")


def findings_json(findings, views_by_file, key_to_view) -> str:
    rows = []
    for f in findings:
        ev = evidence_result(f, views_by_file)
        rows.append({
            "id": f["id"], "kind": f["kind"], "stage": f["stage"],
            "addresses": [address(finding_doc(f), k) for k in f["keys"] if (finding_doc(f), k) in key_to_view],
            "statement": f["title"], "body": f["body"].strip(), "reading": f["reading"],
            "quote": f.get("quote"), "depends_on": f.get("depends_on", []),
            "convention": f.get("convention"),
            "l4": {"file": f["l4"], "line": ev["line"], "evidence": f["evidence"]},
            "messages": ev["messages"], "message_count": len(ev["messages"]),
            "evidence_holds": ev["held"],
            "read_by": f["read_by"], "review": f["review"],
        })
    return json.dumps({"source": REPO, "findings": rows}, ensure_ascii=False, indent=1)
