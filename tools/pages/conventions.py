"""The conventions page: the rules of reading, and the code of each that is
a computation.
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
from pages.sources import *  # noqa: E402,F401,F403
from pages.checks import *  # noqa: E402,F401,F403

# ---------------------------------------------------------- the conventions
# The rules of reading the encoding follows where the text does not decide —
# how a figure is rounded when the text names no rounding, whether a period's
# last day is in it, which of two provisions prevails — written once, in
# conventions.toml, each with the L4 rules that apply it (the client,
# 2026-10-13/14, MMS-485: a read-only view of what "we decided implicitly",
# "all ambiguities decisions should follow a convention", "maybe it should be
# called conventions … each convention could link to the ambiguities it
# affects"). A finding names its convention; the page reads the link off the
# finding, so it is written once. tests/test_conventions.py holds every rule named
# here to a definition in the file named.
BASIS = {"text": "הטקסט קובע", "ours": "בחירת הקידוד"}
# A pick on a question put to the lawyer (the client, 2026-10-17): provisional
# until he has reviewed it, and he may revert it.
LAWYER = "ממתין לעיון עורך הדין"


def corpus_title(doc: str) -> str:
    """A corpus document's title, from the vendored snapshot when it holds
    the file, and its file name otherwise (the snapshot holds what the L4
    encodes; a pick may be applied in an agreement it does not)."""
    path = ROOT / "corpus/akn" / doc
    return akn.title(doc) if path.exists() else Path(doc).stem

# A convention that is a computation is code too (MMS-488): one definition
# in l4/conventions.l4 for each name its `code` lists, imported by every rule
# that applies it. The page sets that definition, and the #ASSERTs that pin
# it, beside the prose; tests/test_conventions.py refuses a local copy.
CONVENTIONS_L4 = ROOT / "l4" / "conventions.l4"
MODULE_DEF = re.compile(r"^(?:DECIDE\s+(?:\w+\s+)?`([^`]+)`|`([^`]+)`\s+MEANS)", re.M)


def module_names(text: str) -> list[str]:
    """The names a module defines, in its order."""
    return [a or b for a, b in MODULE_DEF.findall(text)]


def definition_block(lines: list[str], name: str) -> tuple[int, int]:
    """The 1-based lines (first, last) of `name`'s definition in a module:
    its paragraph (the comment, GIVEN and GIVETH above it included) and the
    paragraphs of #ASSERTs right after it."""
    n = re.escape(name)
    pat = re.compile(rf"^(?:DECIDE\s+(?:\w+\s+)?`{n}`|`{n}`\s+MEANS)")
    i = next(i for i, l in enumerate(lines) if pat.match(l))
    j = i
    while j > 0 and lines[j - 1].strip():
        j -= 1
    k = i
    while k + 1 < len(lines) and lines[k + 1].strip():
        k += 1
    while True:
        a = k + 1
        while a < len(lines) and not lines[a].strip():
            a += 1
        b = a
        while b < len(lines) and lines[b].strip():
            b += 1
        if a < b and all(l.startswith(("#ASSERT", "#EVAL")) for l in lines[a:b]):
            k = b - 1
        else:
            break
    return j + 1, k + 1


def module_callers(name: str) -> list[str]:
    """The L4 files, other than the module, that call `name`."""
    tick = f"`{name}`"
    return sorted(str(f.relative_to(ROOT)) for f in (ROOT / "l4").rglob("*.l4")
                  if not f.is_symlink() and f != CONVENTIONS_L4
                  and tick in f.read_text(encoding="utf-8"))


def conventions_page(reg: dict, by_file: dict[str, "SectionView"], findings: list[dict]) -> str:
    here = "conventions.html"
    relying: dict[str, list[dict]] = {}
    for f in findings:
        if f.get("convention"):
            relying.setdefault(f["convention"], []).append(f)

    def where(a: dict) -> str:
        v = by_file.get(a["l4"])
        name = f'<code class="rule" dir="ltr">{esc(a["rule"])}</code>' if a.get("rule") else ""
        # a whole document's one "section" is numbered by its slug: no § for it
        num = "" if v is None or akn.is_whole(v.doc) else f' <bdi dir="{num_dir(v.section.num)}">{esc(sec_ref(v.section))}</bdi>'
        sec = (f'<a href="{rel(v.href, here)}">{esc(akn.title(v.doc))}{num}</a>'
               if v is not None else f'<code dir="ltr">{esc(a["l4"])}</code>')
        why = f' <span class="why">— {esc(a["why"])}</span>' if a.get("why") else ""
        return f"{sec}{why}{name}"

    def finding_list(fs: list[dict], head: str) -> str:
        """The findings a convention decides, as links. The first few show;
        a long list folds the rest."""
        if not fs:
            return ""
        # the document is named: sibling circulars share a finding's title
        item = lambda f: (f'<li><span class="kind-tag {f["kind"]}">{esc(KINDS[f["kind"]][0])}</span>'
                          f'<a href="{rel("findings.html", here)}#{esc(f["id"])}">{prose(f["title"])}</a>'
                          f'<span class="conv-doc">{esc(akn.title(finding_doc(f)))}</span></li>')
        shown, rest = fs[:5], fs[5:]
        return (f'<div class="conv-find"><p class="conv-find-h">{head} ({len(fs)})</p><ul>{"".join(map(item, shown))}</ul>'
                + (f'<details><summary>עוד {len(rest)}</summary><ul>{"".join(map(item, rest))}</ul></details>' if rest else "")
                + "</div>")

    import l4run
    mod_lines = CONVENTIONS_L4.read_text(encoding="utf-8").split("\n") if CONVENTIONS_L4.exists() else []
    run = l4run.outputs(CONVENTIONS_L4)["run"]
    mod_results = json.loads(run.read_text(encoding="utf-8")).get("results", []) if run.exists() else []

    def code_html(c: dict) -> str:
        """The convention's own definitions in the module, as code, with the
        #ASSERTs that pin them and the files that call them."""
        names = c.get("code", [])
        if not names:
            return ""
        blocks, held, total, files = [], 0, 0, set()
        for name in names:
            s, e = definition_block(mod_lines, name)
            blocks.append((s, e))
            for r in mod_results:
                if r.get("kind") == "assertion" and s <= (line_of(r.get("range")) or 0) <= e:
                    total += 1
                    held += str(r.get("value")).strip().lower() == "true"
            files.update(module_callers(name))
        numbered = [(n, mod_lines[n - 1]) for s, e in blocks for n in range(s, e + 1)]
        gh = f"{REPO}/blob/main/l4/conventions.l4#L{blocks[0][0]}-L{blocks[-1][1]}"
        assert_tag = '<code dir="ltr">#ASSERT</code>'
        tally = (f'<span class="set-asserts">כל ה־{assert_tag} מתקיימים ({total})</span>'
                 if total and held == total else
                 f'<span class="set-asserts bad">{total - held} מתוך {total} {assert_tag} אינם מתקיימים</span>'
                 if total else f'<span class="set-asserts bad">ה־{assert_tag} לא הורצו</span>')
        callers = "".join(f"<li>{where({'l4': f})}</li>" for f in sorted(files))
        return (f'<div class="set-code"><p class="set-code-h">בקוד: '
                f'<a href="{gh}" dir="ltr">l4/conventions.l4</a> {tally}</p>'
                f'{l4src.numbered_html(numbered)}'
                + (f'<details><summary>נקראת מ־{len(files)} קבצים</summary>'
                   f'<ul class="set-where">{callers}</ul></details>' if files else "")
                + "</div>")

    groups = []
    for g in reg.get("group", []):
        rows = []
        for c in [x for x in reg.get("convention", []) if x["group"] == g["id"]]:
            apps = c.get("applies", [])
            exc = c.get("exceptions", [])
            fs = relying.get(c["id"], [])
            amb = [f for f in fs if f["kind"] == "ambiguity"]
            other = [f for f in fs if f["kind"] != "ambiguity"]
            places = c.get("corpus", [])
            details = ""
            if places:
                details += ('<details><summary>היכן הקורפוס מחיל אותה'
                            f' ({len(places)})</summary><ul class="set-where">'
                            + "".join(f'<li><a href="{CORPUS_SITE}/{esc(pl["doc"].removesuffix(".xml"))}.html'
                                      + (f'#{esc(pl["eId"])}' if pl.get("eId") else "") + '">'
                                      + f'{esc(pl.get("name") or corpus_title(pl["doc"]))} ↗</a>'
                                      + (f' <span class="why">— {esc(pl["how"])}</span>' if pl.get("how") else "")
                                      + "</li>" for pl in places)
                            + "</ul></details>")
            if apps or exc:
                details += ('<details><summary>הכללים שמחילים אותה'
                           + (f' ({len(apps)})' if apps else "")
                           + (f' · חריגים ({len(exc)})' if exc else "") + '</summary>'
                           + (f'<ul class="set-where">{"".join(f"<li>{where(a)}</li>" for a in apps)}</ul>' if apps else "")
                           + ('<p class="set-exc-h">כאן הטקסט עצמו עונה אחרת:</p><ul class="set-where exc">'
                              + "".join(f'<li><span class="set-val alt">{esc(e["value"])}</span> '
                                        + where(e) + "</li>" for e in exc) + "</ul>" if exc else "")
                           + "</details>")
            rows.append(
                f'<div class="set-row" id="{esc(c["id"])}">'
                f'<div class="set-q"><div class="set-label">{esc(c["title"])}</div>'
                f'<div class="set-detail">{esc(c["detail"])}</div>'
                f'{code_html(c)}'
                f'{finding_list(amb, "העמימויות שהמוסכמה מכריעה")}'
                f'{finding_list(other, "ממצאים נוספים שהקריאה בהם נשענת עליה")}{details}</div>'
                f'<div class="set-a"><span class="set-val">{esc(c["value"])}</span>'
                f'<span class="set-basis {esc(c["basis"])}">{BASIS[c["basis"]]}</span>'
                + (f'<span class="set-lawyer">{LAWYER}</span>' if c.get("lawyer") else "")
                + '</div></div>')
        if rows:
            groups.append(f'<section class="set-group"><h2>{esc(g["title"])}</h2>{"".join(rows)}</section>')
    asked = [c for c in reg.get("convention", []) if c.get("lawyer")]
    review = ('<section class="set-review"><h2>לעיון עורך הדין</h2>'
              '<p>שאלות שחיכו לעורך הדין קיבלו כאן תשובה זמנית, כדי שהעבודה לא תיעצר: '
              'הקידוד והקורפוס נוהגים לפיה עד שהוא יעיין בה. כל אחת מהן ניתנת לשינוי, '
              'ושינוי משנה את כל המקומות שהיא מונה.</p><ul>'
              + "".join(f'<li><a href="#{esc(c["id"])}">{esc(c["title"])}</a> — '
                        f'<span class="set-val alt">{esc(c["value"])}</span></li>' for c in asked)
              + "</ul></section>") if asked else ""
    body = ('<h1>מוסכמות</h1>'
            '<p class="lede">כללי הקריאה שהקידוד נוהג לפיהם במקום שהטקסט אינו מכריע — איך מעגלים סכום כשהטקסט אינו '
            'אומר, האם היום האחרון של תקופה נכלל בה, מה פירוש "מעל", איזו הוראה גוברת — כתובים כאן פעם אחת, '
            'כל אחד עם הכללים ב־L4 שמחילים אותו. העמוד מתאר את הקוד, ואינו משנה אותו.</p>'
            '<p>בכל שורה: השאלה, התשובה שהקידוד נותן, ומי הכריע — הטקסט עצמו, או הקידוד. '
            'כל עמימות שהקידוד נתקל בה מוכרעת לפי אחת המוסכמות, ומתחת לכל מוסכמה מופיעות העמימויות שהיא מכריעה. '
            'מקום שבו הטקסט עצמו עונה אחרת מופיע תחת <em>חריגים</em>, עם המילים שמכריעות.</p>'
            '<p>מוסכמה שהיא חישוב — עיגול, יום ראשון ואחרון של תקופה, "מעל", "עד", גבול משותף בטבלה, '
            '"לכל N", חלק משרה, "יגדל ב־X%" — כתובה גם כקוד: הגדרה אחת ב־'
            '<code dir="ltr">l4/conventions.l4</code>, עם ה־<code dir="ltr">#ASSERT</code> שמקבעים את פעולתה, '
            'והכללים שמחילים אותה מייבאים אותה משם ואינם מעתיקים אותה. הקוד מופיע ליד הניסוח.</p>'
            '<p class="banner">הבחירות שהקידוד עשה כאן זמניות: הן נבחרו כדי שהקריאה תהיה אחידה, '
            'וניתן לשנות כל אחת מהן. שינוי מוסכמה משנה את כל הכללים שמחילים אותה.</p>'
            + review
            + ("".join(groups) or '<p class="empty">אין עדיין מוסכמות רשומות.</p>'))
    return page(here, f"מוסכמות — {TITLE}", body, tab="conventions",
                desc="כללי הקריאה שקידוד ה-L4 נוהג לפיהם במקום שהטקסט אינו מכריע: עיגול, גבולות תאריכים, ספים ועדיפות בין הוראות")
