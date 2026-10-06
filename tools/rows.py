"""Print a section's rows with the keys an L4 file cites them by.

    python3 tools/rows.py 1.7            # one section
    python3 tools/rows.py 1.7 --todo     # only the rows its L4 does not cite yet
    python3 tools/rows.py --list         # every section, with its status

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
    secs = {s.num: s for s in akn.sections(DOC)}
    if not argv or argv[0] == "--list":
        for s in secs.values():
            v = build_site.build_view(DOC, s)
            print(f"{s.num:>6}  {v.status:8} {len(v.text_rows):4} ¶  {s.heading}")
        return 0
    sec = secs[argv[0]]
    v = build_site.build_view(DOC, sec)
    cite = build_site.citations(sec)
    todo = "--todo" in argv
    print(f"§{sec.num} {sec.heading}   eId {sec.eid}   file {build_site.l4_path(DOC, sec.num).relative_to(build_site.ROOT)}")
    for r in sec.rows:
        if todo and (r.kind != "text" or r.key in v.covered):
            continue
        mark = "  " if r.kind == "label" else ("ok" if r.key in v.covered else "--")
        alias = f"  (also {', '.join(r.aliases)})" if r.aliases else ""
        label = f"{r.num} {r.heading}".strip()
        text = r.text if r.kind == "text" else ""
        print(f"{mark} {'  ' * r.depth}{cite.get(r.key, '')}  [{r.key}]{alias}")
        if label or text:
            print(f"   {'  ' * r.depth}  {label} {text}".rstrip())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
