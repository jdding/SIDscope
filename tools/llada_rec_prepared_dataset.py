#!/usr/bin/env python3
"""Dataset-neutral frozen-protocol input for the pinned LLaDA-Rec source."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from datasets import Dataset
from genrec.dataset import AbstractDataset


RUNTIME_SCHEMA = "genrec_dormant.diffgrm_private_runtime.v1"


class DormantPreparedLLaDADataset(AbstractDataset):
    """Official ``AbstractDataset`` backed by the frozen dormant runtime."""

    def __init__(self, config: dict[str, Any], runtime_manifest: str | Path):
        super().__init__(config)
        payload = json.loads(Path(runtime_manifest).read_text(encoding="utf-8"))
        if payload.get("schema") != RUNTIME_SCHEMA:
            raise ValueError("LLaDA-Rec runtime manifest schema mismatch")
        self.category = str(payload["domain"])
        self.cache_dir = str(Path(config["cache_dir"]).resolve())

        catalog = payload.get("catalog", [])
        if not catalog:
            raise ValueError("LLaDA-Rec runtime catalog cannot be empty")
        keys = [str(row["runtime_item_key"]) for row in catalog]
        normalized = [str(row["normalized_item_id"]) for row in catalog]
        if len(keys) != len(set(keys)) or len(normalized) != len(set(normalized)):
            raise ValueError("LLaDA-Rec runtime catalog identity is not unique")
        self.id_mapping["item2id"].update(
            {item: index for index, item in enumerate(keys, start=1)}
        )
        self.id_mapping["id2item"].extend(keys)
        self.item2meta = {
            str(row["runtime_item_key"]): str(row["metadata_text"]) for row in catalog
        }
        self.normalized_to_runtime = {
            str(row["normalized_item_id"]): str(row["runtime_item_key"])
            for row in catalog
        }
        self.runtime_to_normalized = {
            runtime: normalized_id
            for normalized_id, runtime in self.normalized_to_runtime.items()
        }

        split_data: dict[str, Dataset] = {}
        self.all_item_seqs = {}
        for split in ("train", "val", "test"):
            rows = payload.get("splits", {}).get(split, [])
            users: list[str] = []
            sequences: list[list[str]] = []
            for row in rows:
                sequence = [str(item) for item in row["item_seq"]]
                if len(sequence) < 2:
                    raise ValueError(
                        f"LLaDA-Rec {split} row must contain history and target"
                    )
                if any(item not in self.item2id for item in sequence):
                    raise ValueError(
                        f"LLaDA-Rec {split} row references an unknown catalog item"
                    )
                episode_id = str(row["episode_id"])
                users.append(episode_id)
                sequences.append(sequence)
                self.all_item_seqs[episode_id] = sequence
            if not sequences:
                raise ValueError(f"LLaDA-Rec {split} split cannot be empty")
            split_data[split] = Dataset.from_dict(
                {"user": users, "item_seq": sequences}
            )
        self.split_data = split_data

    def split(self) -> dict[str, Dataset]:
        return self.split_data
