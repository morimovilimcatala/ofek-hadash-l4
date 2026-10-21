"""Edge cases are a kind of finding (the client, 2026-10-21, MMS-534: "it
should be a סוג"), and a finding's `trace` is how the L4 computes it
("Can we do Trace instead of ASSERT in edge cases?")."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_site  # noqa: E402
import edge_traces  # noqa: E402

FINDINGS = build_site.load_findings()


class EdgeCases(unittest.TestCase):
    def test_edge_case_is_a_kind_and_every_one_is_traced(self):
        self.assertIn("edge-case", build_site.KINDS)
        edges = [f for f in FINDINGS if f["kind"] == "edge-case"]
        self.assertTrue(edges)
        for f in edges:
            with self.subTest(finding=f["id"]):
                self.assertTrue(f.get("trace"), "an edge case shows how it is computed")

    def test_every_trace_evaluates_and_shows_its_steps(self):
        traced = [f for f in FINDINGS if f.get("trace")]
        out = edge_traces.traces([{"id": f["id"], "l4": f["l4"], "trace": f["trace"]} for f in traced])
        if out is None:
            self.skipTest("node is not installed")
        for f in traced:
            with self.subTest(finding=f["id"]):
                got = out[f["id"]]
                self.assertEqual([t["expr"] for t in got], f["trace"])
                for t in got:
                    self.assertIsNotNone(t["value"], t["expr"])
                    self.assertIn("└", t["traceText"])


if __name__ == "__main__":
    unittest.main()
