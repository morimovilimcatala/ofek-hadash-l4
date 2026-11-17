"""The frame of every page: the navigation tree, the page shell, links.
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

# ------------------------------------------------------------------ pages


# every document's views, set by build() before any page is written, so each
# page can carry the same navigation tree
NAV_VIEWS: dict[str, list[SectionView]] = {}


def coll_docs(coll: str) -> list[str]:
    return [d for d in NAV_VIEWS if d.split("/")[0] == coll]


def coll_hub(coll: str) -> str:
    """A collection's overview: the takanon's contents page, for the
    collection that is the takanon and its site pages; any other
    collection's own page, which lists a sectioned document of it (the base
    agreement) among the rest."""
    sectioned = [d for d in coll_docs(coll) if not akn.is_whole(d)]
    return f"{sectioned[0].removesuffix('.xml')}.html" if sectioned and coll == "takanon" else f"{coll}.html"


def coll_count(coll: str) -> int:
    """What a collection lists: the takanon's sections and each site page;
    elsewhere each document once, a sectioned agreement too."""
    if coll == "takanon":
        return sum(len(NAV_VIEWS[d]) for d in coll_docs(coll))
    return len(coll_docs(coll))


def site_group_li(here: str, open_: bool) -> str:
    """The takanon collection's site pages, as one group of the sidebar."""
    vs = [v for d in coll_docs("takanon") if is_site_page(d) for v in NAV_VIEWS[d]]
    if not vs:
        return ""
    return (f'<li class="toc-ch"><details{" open" if open_ else ""}><summary>'
            f'<span class="ch" lang="he" dir="rtl">{esc(SITE_GROUP)}</span>'
            f'<span class="n">{len(vs)}</span></summary><ul>{"".join(doc_li(v, here) for v in vs)}</ul></details></li>')


def sec_li(v: SectionView, href: str) -> str:
    return (f'<li><a href="{href}" title="{esc(v.section.heading)}"><span class="secnum" dir="{num_dir(v.section.num)}">{esc(v.section.num)}</span>'
            f'<span class="sh" lang="he" dir="rtl">{esc(v.section.heading)}</span></a></li>')


def doc_li(v: SectionView, here: str) -> str:
    cur = ' aria-current="page"' if here == v.page else ""
    num = doc_num(v.doc)
    secnum = f'<span class="secnum" dir="ltr">{esc(num)}</span>' if num else ""
    return (f'<li><a href="{rel(v.page, here)}" title="{esc(v.section.heading)}"{cur}>{secnum}'
            f'<span class="sh" lang="he" dir="rtl">{esc(v.section.heading)}</span></a></li>')


def chapter_label(s: akn.Section) -> str:
    return f'<span class="ch" lang="he" dir="rtl">{esc(chapter_name(s))}</span>'


def doc_entry(d: str, here: str) -> str:
    """One document in a sidebar list: a whole document's page, or a
    sectioned one's contents."""
    if akn.is_whole(d):
        return doc_li(NAV_VIEWS[d][0], here)
    contents = f"{d.removesuffix('.xml')}.html"
    cur = ' aria-current="page"' if here == contents else ""
    num = doc_num(d)
    return (f'<li><a href="{rel(contents, here)}" title="{esc(akn.title(d))}"{cur}>'
            + (f'<span class="secnum" dir="ltr">{esc(num)}</span>' if num else "")
            + f'<span class="sh" lang="he" dir="rtl">{esc(akn.title(d))}</span></a></li>')


def chapter_items(d: str, here: str, open_page: bool) -> list[str]:
    """A sectioned document's chapters for a sidebar: on one of its pages,
    the chapter shown is open with its sections (anchors on its own page);
    elsewhere every chapter is a closed list."""
    items = []
    for vs in chapters_of(NAV_VIEWS[d]):
        on_page = here == vs[0].page
        if not open_page:
            lis = "".join(sec_li(v, rel(v.href, here)) for v in vs)
            items.append(f'<li class="toc-ch"><details><summary>{chapter_label(vs[0].section)}'
                         f'<span class="n">{len(vs)}</span></summary><ul>{lis}</ul></details></li>')
        elif on_page or any(here == v.render_href for v in vs):
            lis = "".join(sec_li(v, "#" + esc(v.section.eid) if on_page else rel(v.href, here)) for v in vs)
            items.append(f'<li class="toc-ch"><details open><summary>{chapter_label(vs[0].section)}'
                         f'<span class="n">{len(vs)}</span></summary><ul>{lis}</ul></details></li>')
        else:
            items.append(f'<li class="toc-ch"><a class="sn-leaf" href="{rel(vs[0].page, here)}">'
                         f'{chapter_label(vs[0].section)}<span class="n">{len(vs)}</span></a></li>')
    return items


def root_link(coll: str, here: str) -> str:
    """A collection's root (MMS-521) in its sidebar group, beside the
    overview: the client, 2026-10-21, "the roots should be in the nav bar
    under their respective class"."""
    page = roots.page_for(coll)
    if not page:
        return ""
    cur = ' aria-current="page"' if here == page else ""
    return f'<a class="sn-hub" href="{rel(page, here)}"{cur}>שורש</a>'


def family_root_li(coll: str, family: str, here: str) -> str:
    """A family of agreements' own root (MMS-548), first in its group."""
    page_ = roots.family_page(family) if coll == "agreements" else None
    if not page_:
        return ""
    cur = ' aria-current="page"' if here == page_ else ""
    return f'<li><a class="sn-leaf" href="{rel(page_, here)}"{cur}>שורש</a></li>'


def group_html(coll: str, label: str, here: str, items: list[str], open_: bool) -> str:
    return (f'<li class="sn-group"><details{" open" if open_ else ""}>'
            f'<summary>{esc(label.split(" — ")[0])}<span class="n">{coll_count(coll)}</span></summary>'
            f'<a class="sn-hub" href="{rel(coll_hub(coll), here)}">סקירה</a>'
            f'{root_link(coll, here)}'
            f'<ul>{"".join(items)}</ul></details></li>')


def laws_group(here: str) -> str:
    """The statutes the L4 encodes outside the corpus (laws/), as one group
    of the sidebar: the client, 2026-10-21, "maybe the sidebar should have a
    חוקים section". Open on a statute's own page."""
    names = laws.all_laws()
    if not names:
        return ""
    lis = []
    for n in names:
        page_ = f"laws/{n}.html"
        cur = ' aria-current="page"' if here == page_ else ""
        title = laws.load(n)["title"]
        lis.append(f'<li><a href="{rel(page_, here)}" title="{esc(title)}"{cur}>'
                   f'<span class="sh" lang="he" dir="rtl">{esc(title)}</span></a></li>')
    open_ = here.startswith("laws/")
    cur = ' aria-current="page"' if here == "laws/index.html" else ""
    root_cur = ' aria-current="page"' if here == "laws/root.html" else ""
    rec_cur = ' aria-current="page"' if here == statute_record.HERE else ""
    return (f'<li class="sn-group"><details{" open" if open_ else ""}>'
            f'<summary>חוקים<span class="n">{len(names)}</span></summary>'
            f'<a class="sn-hub" href="{rel("laws/index.html", here)}"{cur}>החוקים שהקורפוס מצטט</a>'
            f'<a class="sn-hub" href="{rel("laws/root.html", here)}"{root_cur}>שורש החוקים המגינים</a>'
            f'<a class="sn-hub" href="{rel(statute_record.HERE, here)}"{rec_cur}>המסמכים מול החוקים המגינים</a>'
            f'<ul>{"".join(lis)}</ul></details></li>')


def tree_nav(here: str) -> str:
    """Every encoded document, grouped as the corpus groups them: the
    sidebar of a page that is not a document (the home page, coverage,
    diagnostics, about, a collection's overview)."""
    groups = []
    for coll, label in COLLECTIONS:
        docs = coll_docs(coll)
        if not docs:
            continue
        here_in = (any(here.startswith(d.removesuffix(".xml")) for d in docs) or here == f"{coll}.html"
                   or here == roots.page_for(coll) or here.startswith(f"{coll}/") and here.endswith("/root.html"))
        items = []
        if coll == "takanon":
            for d in docs:
                if not akn.is_whole(d):
                    items += chapter_items(d, here, False)
            items.append(site_group_li(here, False))
        else:
            by_year: dict[str, list[str]] = {}
            for d in docs:
                by_year.setdefault(doc_group(d), []).append(d)
            for year in group_order(coll, by_year):
                ds = sorted(by_year[year])
                lis = family_root_li(coll, year, here) + "".join(doc_entry(d, here) for d in ds)
                items.append(lis if not year else
                             f'<li class="toc-ch"><details{" open" if here == roots.family_page(year) else ""}><summary>{esc(group_label(coll, year))}'
                             f'<span class="n">{len(ds)}</span></summary><ul>{lis}</ul></details></li>')
        groups.append(group_html(coll, label, here, items, here_in))
    groups.append(laws_group(here))
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
    if coll == "takanon":
        for d in coll_docs(coll):
            if not akn.is_whole(d):
                items += chapter_items(d, here, True)
        items.append(site_group_li(here, is_site_page(doc)))
    else:
        # a sectioned agreement's own pages: its parts first, then the
        # collection's documents
        if not akn.is_whole(doc):
            items += chapter_items(doc, here, True)
        by_year: dict[str, list[str]] = {}
        for d in coll_docs(coll):
            by_year.setdefault(doc_group(d), []).append(d)
        mine = doc_group(doc)
        for year in group_order(coll, by_year):
            ds = sorted(by_year[year])
            if year == mine:
                lis = family_root_li(coll, year, here) + "".join(doc_entry(d, here) for d in ds)
                items.append(lis if not year else
                             f'<li class="toc-ch"><details open><summary>{esc(group_label(coll, year))}'
                             f'<span class="n">{len(ds)}</span></summary><ul>{lis}</ul></details></li>')
            else:
                items.append(f'<li class="toc-ch"><a class="sn-leaf" href="{rel(coll + ".html", here)}#y-{esc(year)}">'
                             f'<span dir="{"rtl" if by_folder(coll) else "ltr"}">{esc(group_label(coll, year))}</span>'
                             f'<span class="n">{len(ds)}</span></a></li>')
    groups = [group_html(coll, label, here, items, True)]
    for c, lab in COLLECTIONS:
        if c != coll and coll_docs(c):
            groups.append(other_group(c, lab, here))
    groups.append(laws_group(here))
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
    # the root (MMS-521) heads the tree: the one place to ask what the law gives
    root_page = roots.ROOTS[0][1]
    cur = ' aria-current="page"' if here == root_page else ""
    inner = (f'<li class="sn-group"><a class="sn-leaf" href="{rel(root_page, here)}"{cur}>'
             f'{esc(roots.ROOTS[0][3].split(" — ")[0])}</a></li>' + inner)
    return (f'<aside class="sidenav" id="sidenav" aria-label="עיון במסמכים">'
            f'<div class="sn-head"><span>עיון</span>'
            f'<button type="button" class="sn-close" aria-label="סגירה">×</button></div>'
            f'<ul class="sn-tree">{inner}</ul></aside>'
            f'<div class="sn-scrim" hidden></div>')


def page(here: str, title: str, body: str, *, tab: str = "", desc: str = "",
         wide: bool = False, sidebar: str | None = None) -> str:
    nav = [("index.html", "מסמכים", "docs"),
           ("findings.html", "ממצאים", "findings"),
           *([("calculator.html", "מחשבון שכר", "calculator")] if CALCULATOR else []),
           *([(contradictions.HERE, contradictions.TAB, "contradictions")] if CONTRA else []),
           ("conventions.html", "מוסכמות", "conventions"),
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
