"""The findings page: errors in the LAW that encoding exposed.
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


def msg_html(m: str) -> str:
    """An evidence line as `l4 run` reports it, "<the #ASSERT line>  →  <value>",
    with the L4 highlighted as the site's code panels are."""
    code, arrow, value = m.rpartition("  →  ")
    if not arrow:
        return l4src.highlight(m)
    return f'{l4src.highlight(code)}  →  <span class="w">{esc(value)}</span>'


def findings_page(findings, views_by_file, key_to_view) -> str:
    """Every finding, grouped by the section or circular it is about, each
    folded to its title. A bar over them filters by kind, stage, collection
    and words (assets/site.js); a link to a finding opens it."""
    traced = edge_traces.traces([{"id": f["id"], "l4": f["l4"], "trace": f["trace"]}
                                 for f in findings if f.get("trace")]) or {}
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
            label, href = f"{sec_ref(v.section)} {v.section.heading}", v.href
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
                                              order.get(id(v), 10**9) if v is not None and not v.whole else 0, doc)})
        ev = evidence_result(f, views_by_file)
        where, shown = [], set()
        for k in f.get("keys", []):
            kv = key_to_view.get((doc, k))
            if kv:
                # two paragraphs of one clause read the same; one link is enough
                label = cite_html(kv.section, k, sec_ref(kv.section), kv.doc)
                if label not in shown:
                    shown.add(label)
                    where.append(f'<a href="{kv.page}#{esc(k)}">{label}</a>')
        state = ('<span class="okay">ה־<bdi dir="ltr">#ASSERT</bdi> מתקיים: הפגם עדיין בטקסט</span>' if ev["held"] else
                 '<span class="notok">הראיה אינה מתקיימת — ראו בדיקות</span>')
        deps = "".join(f'<a href="{f"#{d}" if d in by_id else f"{contradictions.HERE}#{HOMES[d]}"}"><bdi dir="ltr" class="fref">{esc(d)}</bdi></a> '
                       for d in f.get("depends_on", []) if d in by_id or d in HOMES)
        stage, sgloss = STAGES[f["stage"]]
        paras = f["body"].strip().split("\n\n")
        body = (f'<div class="fbody" lang="he" dir="rtl">{"".join(f"<p>{prose(p, link_ids=True)}</p>" for p in paras)}</div>'
                if is_hebrew(f["body"]) else
                f'<div class="fbody" lang="en" dir="ltr">{"".join(f"<p>{esc(p)}</p>" for p in paras)}</div>')
        quote = (f'<blockquote lang="he" dir="rtl">{esc(f["quote"])}</blockquote>' if f.get("quote") else "")
        g["cards"].append(
            f'<details class="finding" id="{esc(f["id"])}" data-kind="{f["kind"]}" data-stage="{f["stage"]}" data-col="{col}" data-sev="{f["severity"]}">'
            f'<summary><span class="sev-dot sev-{f["severity"]}" title="חומרה {esc(SEVERITY[f["severity"]][0])}"></span>'
            f'<span class="kind-tag {f["kind"]}">{esc(KINDS[f["kind"]][0])}</span>'
            f'<span class="ftitle">{prose(f["title"])}</span><span class="fid" dir="ltr">{esc(f["id"])}</span></summary>'
            f'<div class="fcard"><p class="fsev"><span class="sev-badge sev-{f["severity"]}">חומרה {esc(SEVERITY[f["severity"]][0])}</span> '
            f'{prose(f["severity_why"])}</p>'
            f'<p class="fmeta"><span class="stage" title="{esc(sgloss)}">נתגלה {esc(stage)}</span> · '
            f'{" · ".join(where)}</p>{quote}{body}'
            f'<p class="reading"><strong>הקריאה שהקידוד מאמץ:</strong> {prose(f["reading"], link_ids=True)}</p>'
            + (f'<p class="conv">לפי המוסכמה: <a href="conventions.html#{esc(f["convention"])}">'
               f'{esc(CONVENTION_TITLES.get(f["convention"], f["convention"]))}</a></p>' if f.get("convention") else "")
            + (f'<p class="deps">תלוי בקריאות של: {deps}</p>' if deps else "")
            + (f'<p class="ev"><a href="{ev["url"]}">הראיה ב-L4</a> · {state}</p>'
               + "".join(f'<pre class="msg hl" dir="ltr">{msg_html(m)}</pre>' for m in ev["messages"])
               if ev["url"] else "")
            + trace_html(traced.get(f["id"], []))
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
    n_sev = {k: sum(f["severity"] == k for f in findings) for k in SEVERITY}
    total = len(findings) or 1
    # the meter: a bar in three parts sized by the counts; each part is a
    # button that filters to its grade, as a cell of the matrix does
    meter = ('<div class="sevmeter"><h2>חומרה</h2><div class="sevbar" role="group" aria-label="חומרת הממצאים">'
             + "".join(f'<button type="button" class="sevseg sev-{k}" data-sev="{k}" style="flex-grow:{n_sev[k]}" '
                       f'title="{esc(t)}: {n_sev[k]} — {esc(d)}"></button>'
                       for k, (t, d) in SEVERITY.items() if n_sev[k])
             + '</div><ul class="sevlegend">'
             + "".join(f'<li><span class="sev-dot sev-{k}"></span>{esc(t)} <b dir="ltr">{n_sev[k]}</b> '
                       f'<small dir="ltr">{round(100 * n_sev[k] / total)}%</small> <span class="sevgloss">{esc(d)}</span></li>'
                       for k, (t, d) in SEVERITY.items())
             + '</ul><p class="sevnote">הדירוג לפי ההשפעה בעולם: ממצא חמור רק אם בית משפט צפוי לשנות את המצב הקיים — את האופן שבו המשרד מיישם את הטקסט, כפי שחוזריו מתעדים אותו. הדירוג הוא קריאה שלנו, כמו הקריאה שבממצא עצמו, וטרם נבדק על ידי עורך הדין.</p></div>')
    bar = ('<div class="ffilter" role="search">'
           '<input type="search" id="fq" placeholder="חיפוש בממצאים: מילה, מזהה, סעיף…" aria-label="חיפוש בממצאים">'
           '<div class="frow"><span class="flabel">חומרה</span>'
           + chips("sev", [(k, SEVERITY[k][0], n_sev[k]) for k in SEVERITY]) + '</div>'
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
    body = (intro + meter + matrix + bar
            + (f'<div class="findings">{sections}</div><p class="empty fnone" hidden>אין ממצאים שמתאימים לסינון.</p>'
               if sections else '<p class="empty">אין עדיין ממצאים.</p>'))
    return page("findings.html", f"ממצאי L4 — {TITLE}", body, tab="findings", sidebar="".join(side))


def trace_html(traces: list[dict]) -> str:
    """How the L4 computes a finding's values, step by step: its `trace`
    expressions run with #EVALTRACE (tools/edge_traces.py; the client,
    2026-10-21: "Can we do Trace instead of ASSERT in edge cases?")."""
    if not traces:
        return ""
    items = "".join(
        f'<div class="trace-one"><p dir="ltr" class="hl"><code>{l4src.highlight(t["expr"])}</code> = '
        f'<b>{esc(str(t["value"]))}</b></p>'
        f'<pre class="msg hl trace-text" dir="ltr">{"<br>".join(l4src.highlight(l) for l in t["traceText"].splitlines())}</pre></div>'
        for t in traces)
    return f'<details class="trace"><summary>איך ה־L4 מחשב את זה (מעקב)</summary>{items}</details>'
