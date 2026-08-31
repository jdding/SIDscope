"""Semantic identities used by deterministic artifact producers.

Component producer versions are intentionally independent from the package
version. Packaging-only releases therefore do not invalidate immutable
evidence; a component version changes only with generated artifact semantics.
"""

CONTRACT_PRODUCER_VERSION = "1.2.0.dev0"
EVALUATION_PRODUCER_VERSION = "1.2.0.dev0"
EVIDENCE_PRODUCER_VERSION = "1.2.0.dev0"

__all__ = [
    "CONTRACT_PRODUCER_VERSION",
    "EVALUATION_PRODUCER_VERSION",
    "EVIDENCE_PRODUCER_VERSION",
]
