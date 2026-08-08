from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SIDScopePaperTableTest(unittest.TestCase):
    def test_frozen_tables_rebuild_exactly(self) -> None:
        completed = subprocess.run(
            [sys.executable, "tools/verify_sidscope_paper_tables.py"],
            cwd=ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        self.assertIn("regeneration verification passed", completed.stdout)
        self.assertIn("Verified 10 tables", completed.stdout)


if __name__ == "__main__":
    unittest.main()
