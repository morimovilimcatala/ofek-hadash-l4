"""The home page: the collections, and how much is encoded.
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

def index_page(all_views: dict[str, list[SectionView]], findings: list[dict]) -> str:
    flat = [v for vs in all_views.values() for v in vs]
    done = sum(v.status == "done" for v in flat)
    rules = sum(tally(v)["rule"] for v in flat if v.src is not None)
    # the index's grid (MMS-553): the root first, then every collection with
    # the same bar, then the laws outside the corpus, and the collections
    # nobody has started in a muted row at the end
    cards, todo = [], []
    for coll, name in COLLECTIONS:
        docs = [d for d in DOCUMENTS if d.startswith(coll + "/")]
        if not docs:
            todo.append(f'<li class="coll todo"><span class="cname">{esc(name)}</span>'
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
                             f'{progress(vs, always=True)}<span class="cstate">{n} מתוך {len(vs)} סעיפים מקודדים</span></a></li>')
            if pages:
                n = sum(v.status == "done" for v in pages)
                cards.append(f'<li class="coll live"><a href="{coll_hub(coll)}#{SITE_ANCHOR}">'
                             f'<span class="cname">{esc(SITE_GROUP)}</span>'
                             f'{progress(pages, always=True)}<span class="cstate">{n} מתוך {len(pages)} דפים מקודדים</span></a></li>')
            continue
        vs = [v for d in docs for v in all_views[d]]
        n = sum(doc_status(all_views[d]) == "done" for d in docs)
        cards.append(f'<li class="coll live"><a href="{coll}.html">'
                     f'<span class="cname">{esc(name)}</span>'
                     f'{progress(vs, always=True)}<span class="cstate">{n} מתוך {len(docs)} מסמכים מקודדים</span></a></li>')
    root_card = (f'<li class="coll live wide root"><a href="{roots.ROOTS[0][1]}"><span class="cname">שורש</span>'
                 f'<span class="ctitle" lang="he" dir="rtl">{esc(roots.ROOTS[0][3])}</span>'
                 f'<span class="cstate">מקור אחד לכל שאלה</span></a></li>')
    law_cards = []
    for name in laws.all_laws():
        law = laws.load(name)
        law_cards.append(f'<li class="coll live"><a href="laws/{name}.html"><span class="cname">חוק</span>'
                         f'<span class="ctitle" lang="he" dir="rtl">{esc(law["title"])}</span>'
                         f'<span class="cstate">סעיפים {esc(laws.span(law))}, '
                         f'מחוץ לקורפוס</span></a></li>')
    law_cards.append('<li class="coll live"><a href="laws/index.html"><span class="cname">חוקים</span>'
                     '<span class="ctitle" lang="he" dir="rtl">החוקים שהקורפוס מצטט</span>'
                     '<span class="cstate">כל חוק וכל סעיף שמסמך בקורפוס מקשר אליו</span></a></li>')
    grid = (f'<h2 class="sect">השורש</h2><ul class="colls">{root_card}</ul>'
            f'<h2 class="sect">אוספים</h2><ul class="colls">{"".join(cards)}</ul>'
            + (f'<h2 class="sect">חוקים</h2><ul class="colls">{"".join(law_cards)}</ul>' if law_cards else "")
            + (f'<h2 class="sect">טרם התחילו</h2><ul class="colls todo-row">{"".join(todo)}</ul>' if todo else ""))
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
            + grid)
    return page("index.html", TITLE, body, tab="docs",
                desc="תקנון שירות עובדי הוראה והחוזרים, לצד קידוד ה-L4 שלהם")
