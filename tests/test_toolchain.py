"""Toolchain: the gate, the compiler pin, and — when build/l4 is present —
every file checked clean and its result not stale; the shared store.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import subprocess
import tempfile
import tomllib
import unicodedata
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import akn      # noqa: E402
import l4src    # noqa: E402
import build_site as site_mod  # noqa: E402


class Toolchain(unittest.TestCase):
    def test_the_gate_refuses_a_compiler_warning_about_the_file(self):
        # the compiler's own `ok` stays true on a warning; the gate does not
        # (tools/l4run.py's verdict). An import's warning is its own file's.
        import l4run
        warn = {"severity": "warning", "file": "a.l4", "range": "1:1-1:2",
                "message": "AND and OR operators appear at the same indentation level"}
        held = {"kind": "assertion", "value": "TRUE"}
        self.assertTrue(l4run.verdict({"ok": True, "results": [held], "diagnostics": []}, "a.l4"))
        self.assertFalse(l4run.verdict({"ok": True, "results": [held], "diagnostics": [warn]}, "a.l4"))
        self.assertTrue(l4run.verdict({"ok": True, "results": [held], "diagnostics": [warn]}, "b.l4"))
        self.assertFalse(l4run.verdict({"ok": True, "results": [{"kind": "assertion", "value": "FALSE"}],
                                        "diagnostics": []}, "a.l4"))

    def test_the_shelf_release_is_a_build_of_the_pin(self):
        # toolchain/fetch-l4.sh installs the release L4_SHELF names (MMS-558)
        pin = (ROOT / "toolchain/L4_COMMIT").read_text().strip()
        shelf = {}
        for line in (ROOT / "toolchain/L4_SHELF").read_text().splitlines():
            if line.strip() and not line.startswith("#"):
                k, v = line.split()
                shelf[k] = v
        self.assertRegex(shelf.get("tag", ""), rf"^unstable-\d{{8}}-{pin[:7]}(-[A-Za-z0-9._-]+)?$")
        for platform in ("linux-x64", "darwin-arm64"):
            self.assertRegex(shelf.get(platform, ""), r"^[0-9a-f]{64}$", platform)

    def test_the_site_installs_the_pin_from_the_shelf(self):
        wf = (ROOT / ".github/workflows/site.yml").read_text(encoding="utf-8")
        self.assertIn("toolchain/fetch-l4.sh", wf)
        self.assertNotIn("build-l4.sh", wf)

    def test_every_file_checks_and_every_assert_holds(self):
        import l4run
        for f in l4run.files():
            if l4run.is_a_root_or_its_tests(f) and not l4run.roots_checked():
                continue  # checked on demand: `make roots`
            out = l4run.outputs(f)
            with self.subTest(file=str(f.relative_to(ROOT))):
                self.assertTrue(out["run"].exists(), "not run")
                data = json.loads(out["run"].read_text(encoding="utf-8"))
                self.assertTrue(data.get("ok"), data.get("diagnostics"))
                stale = out["key"].read_text() != l4run.recorded_key(f, l4run.compiler_id(l4run.compiler()))
                self.assertFalse(stale, "build/l4 is stale for this file: run `make l4`")


class SharedStore(unittest.TestCase):
    """tools/l4run.py's store shared by every worktree (MMS-617): a run
    publishes its outputs under their key, whole, and another worktree's run
    copies them instead of compiling."""

    def test_an_entry_is_stored_whole_and_fetched(self):
        import l4run
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            saved = l4run.STORE
            l4run.STORE = d / "store"
            try:
                made = {p: d / "a" / f"x.{p}" for p in (*l4run.PARTS, "key")}
                made["run"].parent.mkdir()
                for p in l4run.PARTS:
                    made[p].write_text(f"<{p}>", encoding="utf-8")
                k = "ab" + "0" * 62
                self.assertFalse(l4run.fetch(made, k))
                l4run.publish(made, k)
                self.assertEqual(sorted(x.name for x in (d / "store" / "ab" / k).iterdir()),
                                 sorted(l4run.PARTS))
                self.assertEqual([x for x in (d / "store" / "ab").iterdir()
                                  if x.name.startswith(".tmp")], [])
                l4run.publish(made, k)      # a second publish leaves the entry as it is
                there = {p: d / "b" / f"x.{p}" for p in (*l4run.PARTS, "key")}
                self.assertTrue(l4run.fetch(there, k))
                for p in l4run.PARTS:
                    self.assertEqual(there[p].read_text(encoding="utf-8"), f"<{p}>")
                self.assertEqual(there["key"].read_text(), k)
                l4run.STORE = None          # L4_CACHE=off
                self.assertFalse(l4run.fetch(there, k))
            finally:
                l4run.STORE = saved


    def test_a_run_the_system_killed_is_neither_kept_nor_published(self):
        """A compiler run stopped by a signal (the out-of-memory killer, as
        on 2026-11-12, when four parallel agents and a bundle check shared
        the machine) says nothing about the file. It used to be recorded as
        an empty failure under the file's key and published to the store,
        so every later run in every worktree replayed it as an error."""
        import l4run
        from unittest import mock
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            src = d / "x.l4"
            src.write_text("IMPORT prelude\n", encoding="utf-8")
            outs = {p: d / "out" / f"x.{p}" for p in (*l4run.PARTS, "key")}
            # a run killed after printing part of its output still counts as
            # killed: its results are no verdict either
            killed = subprocess.CompletedProcess(
                [], -9, json.dumps({"ok": True, "results": [{"range": "x.l4:1:1"}],
                                    "diagnostics": []}), "")
            saved = l4run.STORE
            l4run.STORE = d / "store"
            try:
                with mock.patch.object(l4run, "outputs", return_value=outs), \
                     mock.patch.object(l4run, "key", return_value="cd" + "0" * 62), \
                     mock.patch.object(l4run, "rendered", return_value=False), \
                     mock.patch.object(l4run.subprocess, "run", return_value=killed):
                    _, ok, ran = l4run.run_one(src, "l4", "cid")
            finally:
                l4run.STORE = saved
            self.assertFalse(ok)
            self.assertTrue(ran)
            self.assertFalse(outs["key"].exists(), "a killed run is not kept")
            self.assertFalse((d / "store").exists(), "a killed run is not published")
            self.assertFalse(json.loads(outs["run"].read_text(encoding="utf-8"))["ok"])


if __name__ == "__main__":
    unittest.main()
