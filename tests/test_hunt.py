"""What the analysis backends find, held exactly (tools/hunt.py, MMS-804).

`make hunt` runs `l4 lts`, `l4 explore`, `l4 verify`, `l4 prove`, `l4
coverage` and TLC over every file and writes build/hunt/summary.json. Each
count there is a ratchet: a new finding raises one and a fixed one lowers
it, and either is red until the number below moves in the same commit, with
the commit saying why. Two are held at zero outright: a trace whose
standing `l4 lts` and `l4 run` disagree on is a defect in one of them, and
an #ASSERT z3 refutes is a false claim in the file.
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import hunt  # noqa: E402

# Read off `make hunt` at l4-ide 9d26421 (MMS-804), at the default timeout
# (HUNT_TIMEOUT, 240 s a call; TLC's three times that). Each key is a line
# of `python3 tools/hunt.py`'s output. Two are tool defects rather than
# findings, filed on MMS-803: the one `explore: deadlocks` is the takanon
# §3.5 hearing, where `l4 explore` stops on an internal error; and the
# timeouts are calls that ran past the bound (edge-teacher-tests under
# verify, prove and coverage; TLC on eight models whose state space the
# bound does not reach), which a slower machine may add to.
HUNT_COUNTS: dict[str, int] = {
    "coverage: buckets proved impossible": 20058,
    "coverage: decisions": 4939,
    "coverage: files with a decision not covered": 400,
    "coverage: timeouts or errors": 3,
    "coverage: undecided": 0,
    "explore: breach unreachable": 235,
    "explore: contracts": 569,
    "explore: deadlocks": 1,
    "explore: explored completely": 31,
    "explore: fulfilment unreachable": 56,
    "explore: refused or stopped at a bound": 334,
    "explore: timeouts or errors": 0,
    "obligations: files": 293,
    "obligations: lts disagrees with run": 0,
    "obligations: timeouts or errors": 0,
    "obligations: traces": 717,
    "prove: obligations": 0,
    "prove: proved": 0,
    "prove: refuted": 0,
    "prove: timeouts or errors": 1,
    "prove: unknown": 0,
    "tla: contracts": 692,
    "tla: models": 643,
    "tla: models TLC did not finish": 0,
    "tla: models TLC finds an error in": 0,
    "tla: timeouts or errors": 8,
    "verify: dead-branch": 4,
    "verify: decisions analysed": 6804,
    "verify: files": 799,
    "verify: timeouts or errors": 1,
    "verify: unreachable-outcome": 41,
    "verify: unsat": 384,
    "verify: vacuous-guard": 115,
}


# The GitHub runner's own record (.github/workflows/hunt.yml, two cores),
# read off its latest run rather than predicted. It finds what the
# container finds; the slower machine only runs past the bound more often
# (TLC on 16 models, coverage on 5 files, explore on 1), and those calls'
# counts drop out of the totals. A cached result is kept per file, so either
# machine's record is stable until a file or the compiler changes; a change
# to a file many modules import re-hunts them all, and on the runner which
# of them runs past the bound can differ from the last time (MMS-807).
HUNT_COUNTS_CI: dict[str, int] = {
    **HUNT_COUNTS,
    "coverage: buckets proved impossible": 19781,
    "coverage: decisions": 4884,
    "coverage: files with a decision not covered": 398,
    "coverage: timeouts or errors": 5,
    "explore: contracts": 564,
    "explore: refused or stopped at a bound": 329,
    "explore: timeouts or errors": 1,
    "tla: models": 617,
    "tla: timeouts or errors": 16,
}


def expected_counts() -> dict[str, int]:
    return HUNT_COUNTS_CI if os.environ.get("GITHUB_ACTIONS") == "true" else HUNT_COUNTS

def summary() -> dict:
    return json.loads(hunt.SUMMARY.read_text(encoding="utf-8"))


class TheHunt(unittest.TestCase):
    """Read off build/hunt/summary.json, which `make hunt` writes. The site's
    deploy does not run the hunt (.github/workflows/hunt.yml does), so
    without that file the class skips, and says so."""

    @classmethod
    def setUpClass(cls):
        if not hunt.SUMMARY.exists():
            raise unittest.SkipTest("no build/hunt/summary.json: run `make hunt`")

    def test_every_count_is_held_exactly(self):
        self.maxDiff = None
        self.assertEqual(summary()["counts"], expected_counts())

    def test_every_hunter_ran(self):
        self.assertEqual(summary()["hunters"], list(hunt.HUNTERS))

    def test_it_ran_with_the_compiler_make_l4_ran_with(self):
        import l4run
        self.assertEqual(summary()["compiler"], l4run.compiler_id(l4run.compiler()))

    def test_lts_and_run_agree_on_every_trace(self):
        self.assertEqual(summary()["counts"].get("obligations: lts disagrees with run", 0), 0)

    def test_z3_refutes_no_assertion(self):
        self.assertEqual(summary()["counts"].get("prove: refuted", 0), 0)


class TheReadings(unittest.TestCase):
    """The hunters' parsing of the compiler's output, without the compiler."""

    def test_a_run_residual_reads_as_a_standing(self):
        self.assertEqual(hunt.standing_of_run_value("FULFILLED"), "fulfilled")
        self.assertEqual(hunt.standing_of_run_value("BREACHED BY `a` BECAUSE \"x\""), "breached")
        self.assertEqual(hunt.standing_of_run_value("DEONTIC BREACHED:\n  BREACH\n  BY `a`"), "breached")
        self.assertEqual(hunt.standing_of_run_value("PARTY `a` MUST `b`"), "inProgress")

    def test_prove_and_coverage_summaries_parse(self):
        m = hunt.PROVE_RE.search("coverage: 13 #ASSERT: 13 decided by evaluation, not re-proved; "
                                 "2 obligations: 1 proved, 0 refuted, 1 unknown")
        self.assertEqual(m.groups(), ("2", "1", "0", "1"))
        m = hunt.COVERAGE_RE.search("Coverage: 6 decisions covered (6 cover points, 12 buckets); "
                                    "12 witnessed by 16 inputs, at most 8 per bucket; 0 proved impossible; "
                                    "nothing undecided; every decision at leaf level")
        self.assertEqual(m.group(1), "6")
        self.assertEqual(hunt.COVERAGE_RE.search("Coverage: 1 decision covered (2 cover points)").group(1), "1")
        self.assertIsNone(hunt.COVERAGE_RE.search("Coverage: NOTHING COVERED; nothing skipped").group(1))
        self.assertEqual(hunt.count_in(r"(\\d+) undecided", "0 proved impossible; nothing undecided"), 0)

    def test_a_rule_that_takes_inputs_is_not_modelled(self):
        import tempfile
        text = ("GIVETH A DEONTIC Party `act`\nDECIDE `free` IS\n    PARTY `a` MUST `b`\n\n"
                "GIVEN x IS A NUMBER\nGIVETH A DEONTIC Party `act`\nDECIDE `bound` x IS\n    PARTY `a` MUST `b`\n")
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "x.l4"
            f.write_text(text, encoding="utf-8")
            self.assertEqual(hunt.input_free_contracts(f), ["free"])


if __name__ == "__main__":
    unittest.main()
