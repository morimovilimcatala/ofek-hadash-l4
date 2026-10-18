"""The words each cited row held when the L4 was written against it.

    python3 tools/cited_rows.py --write    # record them in corpus/cited-rows.tsv
    python3 tools/cited_rows.py            # list the cited rows whose words moved

A citation is checked to EXIST by the alignment tests; this checks that it
still names the same WORDS. A corpus re-sync that inserts a row (a reading
note, a table) renumbers every `/pN` after it, and each old citation then
resolves to its neighbour: every key exists, nothing is uncited, and the L4
silently encodes the wrong paragraph (MMS-470).

corpus/cited-rows.tsv holds, for every key an L4 segment (`@ref akn:` or a
`-- akn:` note) or a finding cites, a digest of that row's text. A key that
heads other rows (a clause cited as a whole) is digested with everything
under it. tools/sync_corpus.py writes the record from the corpus being
replaced, BEFORE it copies the new one, so the record is always of the text
the citations were written against; tests/test_sync.py then fails on every
cited key whose words changed and names the row the old words moved to.
After re-pointing those citations, re-record with --write.
"""
from __future__ import annotations

import hashlib
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import akn          # noqa: E402
import l4src        # noqa: E402
import build_site   # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RECORD = ROOT / "corpus" / "cited-rows.tsv"
HEADER = ("# The text each cited corpus row held when it was last recorded "
          "(tools/cited_rows.py; MMS-470).\n# document\tkey\tdigest\n")


def _digest(rows: list[akn.Row]) -> str:
    h = hashlib.sha256()
    for r in rows:
        # words, not spacing: a re-encoded link or line break that leaves the
        # words where they were is not a moved row
        h.update("\x1f".join("".join(t.split()) for t in (r.num, r.heading, r.text)).encode("utf-8") + b"\x1e")
    return h.hexdigest()[:16]


def section_digests(sec: akn.Section) -> dict[str, str]:
    """Every key of a section (row keys and aliases) -> the digest of the
    words it names: its own row, and for a key that heads others, all of
    them in order."""
    keys = {r.key for r in sec.rows}
    subtree: dict[str, list[akn.Row]] = {}
    for r in sec.rows:
        # the row itself and every row key it sits under (build_site.under:
        # a prefix ending where the key goes on with "__" or "/")
        for i in [len(r.key)] + [m for m in range(1, len(r.key))
                                 if r.key.startswith("__", m) or r.key[m] == "/"]:
            if r.key[:i] in keys:
                subtree.setdefault(r.key[:i], []).append(r)
    out = {k: _digest(rows) for k, rows in subtree.items()}
    for r in sec.rows:
        for a in r.aliases:
            out.setdefault(a, _digest([r]))
    return out


def document_digests(doc: str) -> dict[str, str]:
    out = {}
    for sec in akn.sections(doc):
        for k, d in section_digests(sec).items():
            out.setdefault(k, d)
    return out


def cited() -> set[tuple[str, str]]:
    """(document, key) for every key an L4 segment or a finding cites."""
    out = set()
    for doc in build_site.DOCUMENTS:
        # a document of a collection that has just joined the work is not
        # vendored until the sync that brings it: nothing cites it yet
        if not (akn.CORPUS / doc).exists():
            continue
        for sec in akn.sections(doc):
            path = build_site.l4_path(doc, sec.num)
            if not path.exists():
                continue
            for seg in l4src.parse(path).segments:
                out.update((doc, k) for k in seg.keys)
    for f in build_site.load_findings():
        doc = build_site.finding_doc(f)
        out.update((doc, k) for k in f.get("keys", []))
    return out


def current() -> dict[tuple[str, str], str]:
    """The digest each cited key names in the corpus as it stands."""
    by_doc: dict[str, dict[str, str]] = {}
    out = {}
    for doc, key in sorted(cited()):
        if doc not in by_doc:
            by_doc[doc] = document_digests(doc)
        digests = by_doc[doc]
        if key in digests:
            out[(doc, key)] = digests[key]
    return out


def read_record(path: Path = RECORD) -> dict[tuple[str, str], str]:
    out = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        doc, key, digest = line.split("\t")
        out[(doc, key)] = digest
    return out


def write_record(path: Path = RECORD) -> int:
    rec = current()
    path.write_text(HEADER + "".join(f"{d}\t{k}\t{g}\n" for (d, k), g in sorted(rec.items())),
                    encoding="utf-8")
    return len(rec)


def moved() -> list[str]:
    """One line per recorded, still-cited key whose words changed, naming
    where the recorded words are now (the same holder first)."""
    rec = read_record()
    now = current()
    out = []
    by_doc: dict[str, dict[str, str]] = {}
    for (doc, key), old in sorted(rec.items()):
        new = now.get((doc, key))
        if new is None or new == old:
            continue
        if doc not in by_doc:
            by_doc[doc] = document_digests(doc)
        digests = by_doc[doc]
        holder = key.rsplit("/", 1)[0]
        there = sorted((k for k, d in digests.items() if d == old),
                       key=lambda k: (k.rsplit("/", 1)[0] != holder, k))
        where = f"the recorded words are now at {', '.join(there)}" if there \
            else "no row holds the recorded words now"
        out.append(f"{doc.removesuffix('.xml')}: {key} names other words; {where}")
    return out


if __name__ == "__main__":
    if sys.argv[1:] == ["--write"]:
        print(f"recorded {write_record()} cited rows in {RECORD.relative_to(ROOT)}")
    else:
        lines = moved()
        print("\n".join(lines) or "every cited row names the words it was recorded with")
        sys.exit(1 if lines else 0)
