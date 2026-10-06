"""Refresh corpus/ from a checkout of the corpus repository.

    python3 tools/sync_corpus.py /path/to/TeachersSalaryCatala

Copies every file corpus/SOURCE.toml lists, rewrites the manifest of the
corpus's documents, and records the checkout's commit and the copies'
hashes. Nothing here edits a corpus file; a defect in one is fixed there.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import shutil
import subprocess
import sys
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AKN = "{http://docs.oasis-open.org/legaldocml/ns/akn/3.0}"


def manifest(src: Path) -> list[dict]:
    out = []
    for p in sorted((src / "akn").rglob("*.xml")):
        if "schema" in p.relative_to(src / "akn").parts:
            continue
        doc = ET.parse(p).getroot()[0]
        title = None
        for tag in ("docTitle", "longTitle", "shortTitle"):
            e = doc.find(f".//{AKN}{tag}")
            if e is not None:
                title = " ".join("".join(e.itertext()).split())
                break
        d = doc.find(f".//{AKN}FRBRWork/{AKN}FRBRdate")
        rel = p.relative_to(src / "akn")
        out.append({"path": str(rel), "collection": rel.parts[0],
                    "title": title or p.stem,
                    "date": d.get("date") if d is not None else None,
                    "name": doc.get("name")})
    return out


def main(src_dir: str) -> int:
    src = Path(src_dir).resolve()
    source = tomllib.loads((ROOT / "corpus/SOURCE.toml").read_text(encoding="utf-8"))
    commit = subprocess.run(["git", "-C", str(src), "rev-parse", "HEAD"],
                            capture_output=True, text=True, check=True).stdout.strip()
    lines = ["# The corpus snapshot this repository encodes. corpus/akn/ is a verbatim",
             "# copy of these files at this commit; tools/sync_corpus.py refreshes it.",
             f'repository = "{source["repository"]}"', f'commit = "{commit}"',
             f'synced = "{datetime.date.today().isoformat()}"', f'site = "{source["site"]}"', ""]
    for f in source["file"]:
        dst = ROOT / "corpus" / f["path"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src / f["path"], dst)
        digest = hashlib.sha256(dst.read_bytes()).hexdigest()
        lines += ["[[file]]", f'path = "{f["path"]}"', f'sha256 = "{digest}"', ""]
        print(("changed " if digest != f["sha256"] else "same    ") + f["path"])
    (ROOT / "corpus/SOURCE.toml").write_text("\n".join(lines), encoding="utf-8")
    docs = manifest(src)
    (ROOT / "corpus/manifest.json").write_text(json.dumps(
        {"source": f'{source["repository"]} akn/', "commit": commit, "documents": docs},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"manifest: {len(docs)} documents at {commit[:12]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
