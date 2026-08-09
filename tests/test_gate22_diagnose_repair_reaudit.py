from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

TORCH_AVAILABLE = importlib.util.find_spec("torch") is not None

if TORCH_AVAILABLE:  # pragma: no branch - imports are exercised in full environments
    import pandas as pd

    from tools.run_v1_gate22_diagnose_repair_reaudit import reconstruct_interactions


@unittest.skipUnless(TORCH_AVAILABLE, "G22 mapping-repair tests require optional PyTorch")
class Gate22DiagnoseRepairReauditTest(unittest.TestCase):
    def test_reconstruct_interactions_preserves_declared_split(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = {}
            for split, target in (("train", 3), ("validation", 4), ("test", 5)):
                path = root / f"{split}.parquet"
                pd.DataFrame([{"user": 7, "history": [1, 2], "target": target}]).to_parquet(path)
                paths[split] = path
            interactions = reconstruct_interactions(paths)
        self.assertEqual(set(interactions["split"]), {"train", "validation", "test"})
        self.assertEqual(set(interactions["user_id"]), {"7"})
        self.assertEqual(set(interactions.loc[interactions["split"] == "test", "item_id"]), {1, 2, 5})


if __name__ == "__main__":
    unittest.main()
