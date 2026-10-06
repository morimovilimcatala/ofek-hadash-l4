"""Print a section's rows with the keys an L4 file cites them by.

    python3 tools/rows.py 1.7                            # a takanon section
    python3 tools/rows.py circulars/2016-17_tashaz_05    # a whole document
    python3 tools/rows.py 1.7 --todo     # only the rows its L4 does not cite yet
    python3 tools/rows.py --list         # every takanon section, with its status
    python3 tools/rows.py --list circulars   # every document of a collection

The keys are what `@ref akn:<key>` and `-- akn:<key> <reason>` take.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import akn          # noqa: E402
import build_site   # noqa: E402

DOC = build_site.DOCUMENTS[0]


def main(argv: list[str]) -> int:
    if not argv or argv[0] == "--list":
        coll = argv[1] if len(argv) > 1 else None
        if coll:
            for d in build_site.DOCUMENTS:
                if d.startswith(coll + "/"):
                    v = build_site.build_view(d, akn.sections(d)[0])
                    print(f"{d.removesuffix('.xml'):60} {v.status:8} {len(v.text_rows):4} ¶  {v.section.heading}")
            return 0
        for s in akn.sections(DOC):
            v = build_site.build_view(DOC, s)
            print(f"{s.num:>6}  {v.status:8} {len(v.text_rows):4} ¶  {s.heading}")
        return 0
    if "/" in argv[0]:
        doc = argv[0].removesuffix(".xml") + ".xml"
        sec = akn.sections(doc)[0]
        v = build_site.build_view(doc, sec)
    else:
        sec = {s.num: s for s in akn.sections(DOC)}[argv[0]]
        v = build_site.build_view(DOC, sec)
    cite = build_site.citations(sec)
    todo = "--todo" in argv
    print(f"{sec.num} {sec.heading}   file {build_site.l4_path(v.doc, sec.num).relative_to(build_site.ROOT)}")
    for r in sec.rows:
        if todo and (r.kind != "text" or r.key in v.covered):
            continue
        mark = "  " if r.kind == "label" else ("ok" if r.key in v.covered else "--")
        alias = f"  (also {', '.join(r.aliases)})" if r.aliases else ""
        label = f"{r.num} {r.heading}".strip()
        text = r.text if r.kind == "text" else ""
        if r.cells is not None:
            text = "TABLE " + " ‖ ".join(" | ".join(row) for row in r.cells)
        print(f"{mark} {'  ' * r.depth}{cite.get(r.key, '')}  [{r.key}]{alias}")
        if label or text:
            print(f"   {'  ' * r.depth}  {label} {text}".rstrip())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
