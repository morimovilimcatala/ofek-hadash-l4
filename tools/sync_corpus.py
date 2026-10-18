"""Refresh corpus/ from a checkout of the corpus repository.

    python3 tools/sync_corpus.py /path/to/TeachersSalaryCatala

First records, in corpus/cited-rows.tsv, the words every cited row holds in
the corpus being replaced (tools/cited_rows.py); then copies every document
of the collections in work (tools/build_site.py's WORK_COLLECTIONS) as the
checkout has committed it, removes a vendored file the corpus no longer
has, rewrites the manifest of the corpus's documents, and records the
checkout's commit and the copies' hashes. A cited row whose
words the new corpus moved fails tests/test_sync.py, which names where they
went: re-point the citation, then `python3 tools/cited_rows.py --write`. Nothing here edits a corpus file; a defect in one is fixed there.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import subprocess
import sys
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AKN = "{http://docs.oasis-open.org/legaldocml/ns/akn/3.0}"


def committed(src: Path, path: str) -> bytes:
    """A file as the corpus repository has COMMITTED it. A session at work
    in the checkout has uncommitted edits, and those are not the corpus yet;
    tests/test_sync.py compares against the same commit."""
    if (src / ".git").exists():
        return subprocess.run(["git", "-C", str(src), "show", f"HEAD:{path}"],
                              capture_output=True, check=True).stdout
    return (src / path).read_bytes()


def committed_documents(src: Path) -> list[str]:
    if (src / ".git").exists():
        ls = subprocess.run(["git", "-C", str(src), "ls-tree", "-r", "--name-only", "HEAD", "akn/"],
                            capture_output=True, text=True, check=True).stdout.split()
    else:
        ls = [p.relative_to(src).as_posix() for p in (src / "akn").rglob("*.xml")]
    # in the order the manifest has always listed them: by path component
    return sorted((p for p in ls if p.endswith(".xml") and "/schema/" not in p),
                  key=lambda p: Path(p).parts)


def manifest(src: Path) -> list[dict]:
    out = []
    for path in committed_documents(src):
        p = Path(path)
        doc = ET.fromstring(committed(src, path))[0]
        title = None
        for tag in ("docTitle", "longTitle", "shortTitle"):
            e = doc.find(f".//{AKN}{tag}")
            if e is not None:
                title = " ".join("".join(e.itertext()).split())
                break
        d = doc.find(f".//{AKN}FRBRWork/{AKN}FRBRdate")
        rel = p.relative_to("akn")
        out.append({"path": str(rel), "collection": rel.parts[0],
                    "title": title or p.stem,
                    "date": d.get("date") if d is not None else None,
                    "name": doc.get("name")})
    return out


def main(src_dir: str) -> int:
    src = Path(src_dir).resolve()
    # Record the words every cited row holds in the corpus being REPLACED,
    # so a row the new corpus renumbers is caught by tests/test_sync.py
    # instead of resolving silently to its neighbour (MMS-470).
    import cited_rows
    print(f"recorded {cited_rows.write_record()} cited rows before the sync")
    source = tomllib.loads((ROOT / "corpus/SOURCE.toml").read_text(encoding="utf-8"))
    commit = subprocess.run(["git", "-C", str(src), "rev-parse", "HEAD"],
                            capture_output=True, text=True, check=True).stdout.strip()
    lines = ["# The corpus snapshot this repository encodes. corpus/akn/ is a verbatim",
             "# copy of these files at this commit; tools/sync_corpus.py refreshes it.",
             f'repository = "{source["repository"]}"', f'commit = "{commit}"',
             f'synced = "{datetime.date.today().isoformat()}"', f'site = "{source["site"]}"', ""]
    # what is vendored is every document of a collection in work: a
    # collection joins the snapshot by joining WORK_COLLECTIONS, and a
    # document the corpus adds to one arrives with the next sync
    before = {f["path"]: f["sha256"] for f in source["file"]}
    wanted = [p for p in committed_documents(src)
              if Path(p).relative_to("akn").parts[0] in cited_rows.build_site.WORK_COLLECTIONS]
    for path in wanted:
        dst = ROOT / "corpus" / path
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(committed(src, path))
        digest = hashlib.sha256(dst.read_bytes()).hexdigest()
        lines += ["[[file]]", f'path = "{path}"', f'sha256 = "{digest}"', ""]
        print(("new     " if path not in before else
               "changed " if digest != before[path] else "same    ") + path)
    for path in sorted(set(before) - set(wanted)):
        (ROOT / "corpus" / path).unlink(missing_ok=True)
        print("gone    " + path)
    (ROOT / "corpus/SOURCE.toml").write_text("\n".join(lines), encoding="utf-8")
    docs = manifest(src)
    (ROOT / "corpus/manifest.json").write_text(json.dumps(
        {"source": f'{source["repository"]} akn/', "commit": commit, "documents": docs},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"manifest: {len(docs)} documents at {commit[:12]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
