"""Shared test doubles."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FakeCorpus:
    """A stand-in for a built corpus: scanners only need roots and depth."""

    roots: list[Path] = field(default_factory=list)
    depth: str = "full"
    has_source: bool = True
    evidence_strength: str = "file:line citations available"

    def search_roots(self) -> list[Path]:
        return self.roots
