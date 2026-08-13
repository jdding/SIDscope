from __future__ import annotations

import unittest

from tools.verify_sidscope_d7_labeled_trace_release import (
    DEFAULT_METADATA,
    DEFAULT_RELEASE,
    verify,
)


class D7LabeledTraceReleaseTest(unittest.TestCase):
    def test_frozen_release_is_complete_and_deidentified(self) -> None:
        result = verify(DEFAULT_RELEASE, DEFAULT_METADATA)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["cases"], 5)
        self.assertEqual(result["rows"], 125000)
        self.assertEqual(result["traces"], 2500)


if __name__ == "__main__":
    unittest.main()
