"""Every tariff the L4 writes out is the corpus table it cites, cell for cell
(MMS-685).

The editions of the Accountant-General's notice HOD.13.4.2.1 "לוח תעריפי
נסיעה בתחבורה ציבורית" are encoded in l4/takam/, their tables as DATA that
tools/tariff_l4.py writes from the corpus XML under a marker line per table
("-- tariff data akn:<key> (tools/tariff_l4.py)"). Nothing typed a tariff;
this holds every block to what the tool reads from the corpus today, and
every fare table of an encoded edition to a block, so a re-sync that moves a
cell, or a hand edit of a block, goes red.
"""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import tariff_l4  # noqa: E402


class TariffBlocksAreTheCorpusTables(unittest.TestCase):
    def test_every_block_is_what_the_tool_reads_from_the_corpus(self):
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "tariff_l4.py"), "--check"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_every_edition_the_corpus_holds_is_encoded(self):
        missing = [d for d in tariff_l4.notices() if not tariff_l4.l4_file(d).exists()]
        self.assertEqual(missing, [])

    def test_a_price_is_read_from_its_cell(self):
        self.assertEqual(tariff_l4.price("₪ 21.50"), "(JUST 21.5)")
        self.assertEqual(tariff_l4.price('13 ש"ח'), "(JUST 13)")
        self.assertEqual(tariff_l4.price("-"), "NOTHING")
        self.assertEqual(tariff_l4.price("1.4.16"), "NOTHING")
        with self.assertRaises(ValueError):
            tariff_l4.price('31 ש"ח (עבור חופשי יומי)')

    def test_a_distance_band_is_read_from_its_cell(self):
        self.assertEqual(tariff_l4.band('מ-15 עד 40 ק"מ'), ("15", "(JUST 40)"))
        self.assertEqual(tariff_l4.band("0-15"), ("0", "(JUST 15)"))
        self.assertEqual(tariff_l4.band("מעל 255"), ("255", "NOTHING"))
        self.assertEqual(tariff_l4.band("מ-225"), ("225", "NOTHING"))


if __name__ == "__main__":
    unittest.main()
