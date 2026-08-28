"""Adapters and integration helpers for external SID artifacts."""

from __future__ import annotations

from importlib.util import find_spec
from pathlib import Path
from typing import Any, Callable


LATTE_TOKENIZER_OPTIONAL_DISTRIBUTIONS = (
    "faiss-cpu",
    "sentence-transformers",
)
LATTE_TOKENIZER_IMPORTS = {
    "faiss-cpu": "faiss",
    "sentence-transformers": "sentence_transformers",
}


def model_reference_kind(model_reference: str | Path) -> str:
    """Classify a model reference as a local path or a registry identifier."""

    return "local_path" if Path(model_reference).expanduser().exists() else "model_id"


def load_sentence_transformer(
    model_reference: str | Path,
    *,
    local_files_only: bool = True,
    loader: Callable[..., Any] | None = None,
    **loader_kwargs: Any,
) -> Any:
    """Load a SentenceTransformer without inferring its type from path text."""

    if loader is None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "SentenceTransformer support is optional; install SIDScope with "
                "`python3 -m pip install -e '.[latte]'`."
            ) from exc
        loader = SentenceTransformer

    return loader(
        str(Path(model_reference).expanduser())
        if model_reference_kind(model_reference) == "local_path"
        else str(model_reference),
        local_files_only=local_files_only,
        **loader_kwargs,
    )


def latte_tokenizer_runtime_status(
    module_finder: Callable[[str], Any] | None = None,
) -> dict[str, Any]:
    """Report the optional imports required by tokenizer-only Latte intake."""

    finder = module_finder or find_spec
    availability = {
        distribution: finder(module_name) is not None
        for distribution, module_name in LATTE_TOKENIZER_IMPORTS.items()
    }
    missing = [name for name, available in availability.items() if not available]
    return {
        "ready": not missing,
        "availability": availability,
        "missing_distributions": missing,
        "datasets_required": False,
        "scope": "tokenizer-only SID export and SIDScope intake",
    }


__all__ = [
    "LATTE_TOKENIZER_IMPORTS",
    "LATTE_TOKENIZER_OPTIONAL_DISTRIBUTIONS",
    "card",
    "dact",
    "diffgrm",
    "grid",
    "isd",
    "latte",
    "latte_tokenizer_runtime_status",
    "llada_rec",
    "lcrec",
    "letter",
    "load_sentence_transformer",
    "model_reference_kind",
    "resid",
    "rpg",
    "sanity",
]
