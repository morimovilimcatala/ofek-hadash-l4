"""The vendored corpus is the corpus repository's current text.

corpus/ is a snapshot of TeachersSalaryCatala's akn/ (corpus/SOURCE.toml names
the commit). Nothing else notices when the corpus moves on: a fixed sic, a
rebuilt document, a renumbered clause would stay invisible here while the L4
cites the old words. This compares every vendored file with a checkout of the
corpus repository and fails on any difference, so the cure is
`python3 tools/sync_corpus.py <checkout>`, then `make l4 && make test`.

The corpus repository is private, so CI cannot fetch it; the check runs where
a checkout sits beside this one (or where OFEK_CORPUS_REPO names one) and
SKIPS elsewhere, saying so.
"""
import hashlib
import os
import subprocess
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def committed(repo: Path, path: str) -> bytes | None:
    """The file as the corpus repository has COMMITTED it: a session at work
    there has uncommitted edits, and those are not the corpus yet."""
    r = subprocess.run(["git", "-C", str(repo), "show", f"HEAD:{path}"], capture_output=True)
    if r.returncode == 0:
        return r.stdout
    there = repo / path
    return there.read_bytes() if there.exists() and not (repo / ".git").exists() else None


def checkout() -> Path | None:
    for c in (os.environ.get("OFEK_CORPUS_REPO"), ROOT.parent / "TeachersSalaryCatala"):
        if c and (Path(c) / "akn").is_dir():
            return Path(c)
    return None


class CorpusIsCurrent(unittest.TestCase):
    def setUp(self):
        self.repo = checkout()
        if self.repo is None:
            self.skipTest("no checkout of the corpus repository beside this one "
                          "(set OFEK_CORPUS_REPO to check the snapshot is current)")
        self.source = tomllib.loads((ROOT / "corpus/SOURCE.toml").read_text(encoding="utf-8"))

    def test_every_vendored_file_is_the_corpus_file(self):
        stale = []
        for f in self.source["file"]:
            data = committed(self.repo, f["path"])
            if data is None:
                stale.append(f"{f['path']}: gone from the corpus")
            elif hashlib.sha256(data).hexdigest() != f["sha256"]:
                stale.append(f"{f['path']}: changed in the corpus")
        self.assertEqual([], stale, "corpus/ is behind the corpus repository: "
                         "run tools/sync_corpus.py, then make l4 && make test")

    def test_the_manifest_lists_the_corpus_documents(self):
        """manifest.json is the coverage page's denominator: a document the
        corpus added or dropped must show there."""
        import json
        listed = {d["path"] for d in json.loads((ROOT / "corpus/manifest.json").read_text(encoding="utf-8"))["documents"]}
        ls = subprocess.run(["git", "-C", str(self.repo), "ls-tree", "-r", "--name-only", "HEAD", "akn/"],
                            capture_output=True, text=True).stdout.split()
        there = {p.removeprefix("akn/") for p in ls if p.endswith(".xml") and "/schema/" not in p}
        self.assertEqual(([], []), (sorted(there - listed), sorted(listed - there)),
                         "(added, dropped) since the last sync: run tools/sync_corpus.py")

if __name__ == "__main__":
    unittest.main()
