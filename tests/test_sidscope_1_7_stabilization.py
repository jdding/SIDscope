from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from verify_sidscope_1_7_stabilization import verify


class SIDScope17StabilizationTest(unittest.TestCase):
    def test_contract_and_public_surface_stabilization(self) -> None:
        result = verify()
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["schema_count"], 46)
        self.assertEqual(result["schema_resource_count"], 28)
        self.assertEqual(result["cli_result_schema_count"], 19)
        self.assertEqual(result["typed_negative_count"], 2)
        self.assertFalse(result["gpu_required"])


if __name__ == "__main__":
    unittest.main()
