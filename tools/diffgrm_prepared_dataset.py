#!/usr/bin/env python3
"""Dataset-neutral frozen-protocol input for the pinned DiffGRM source.
This module changes only DiffGRM's dataset construction boundary.  Semantic-ID
construction, tokenization, the masked model, and decoding remain upstream.
The private runtime manifest contains pseudonymous item keys and metadata text;
source item and user identities are never required after preparation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from datasets import Dataset
from genrec.dataset import AbstractDataset


RUNTIME_SCHEMA = "genrec_dormant.diffgrm_private_runtime.v1"


class DormantPreparedDataset(AbstractDataset):
    """An official ``AbstractDataset`` backed by a frozen prepared manifest."""

    def __init__(self, config: dict[str, Any], runtime_manifest: str | Path):
        super().__init__(config)
        path = Path(runtime_manifest)
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema") != RUNTIME_SCHEMA:
            raise ValueError("DiffGRM runtime manifest schema mismatch")
        self.category = str(payload["domain"])
        self.cache_dir = str(Path(config["cache_dir"]).resolve())

        catalog = payload.get("catalog", [])
        if not catalog:
            raise ValueError("DiffGRM runtime catalog cannot be empty")
        keys = [str(row["runtime_item_key"]) for row in catalog]
        if len(keys) != len(set(keys)):
            raise ValueError("DiffGRM runtime catalog contains duplicate keys")
        self.id_mapping["item2id"].update(
            {item: index for index, item in enumerate(keys, start=1)}
        )
        self.id_mapping["id2item"].extend(keys)
        self.item2meta = {
            str(row["runtime_item_key"]): str(row["metadata_text"]) for row in catalog
        }

        split_data: dict[str, Dataset] = {}
        for split in ("train", "val", "test"):
            rows = payload.get("splits", {}).get(split, [])
            users: list[str] = []
            sequences: list[list[str]] = []
            for row in rows:
                sequence = [str(item) for item in row["item_seq"]]
                if len(sequence) < 2:
                    raise ValueError(f"DiffGRM {split} row must contain history and target")
                if any(item not in self.item2id for item in sequence):
                    raise ValueError(f"DiffGRM {split} row references an unknown catalog item")
                users.append(str(row["episode_id"]))
                sequences.append(sequence)
            if not sequences:
                raise ValueError(f"DiffGRM {split} split cannot be empty")
            split_data[split] = Dataset.from_dict({"user": users, "item_seq": sequences})
        self.split_data = split_data
        self.all_item_seqs = {
            str(row["episode_id"]): [str(item) for item in row["item_seq"]]
            for split in ("train", "val", "test")
            for row in payload["splits"][split]
        }

    def split(self) -> dict[str, Dataset]:
        return self.split_data
