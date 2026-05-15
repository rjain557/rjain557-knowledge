"""Shared dataclass returned by all content extractors."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ExtractedContent:
    source_url: str
    source_type: str          # article | youtube | github | arxiv | pdf | other
    canonical_url: str
    title: str
    body_markdown: str
    author: str | None = None
    published_at: datetime | None = None
    transcript: str | None = None
    metadata: dict = field(default_factory=dict)
    raw_blob_path: str | None = None
    code_artifacts: list | None = None

    @property
    def is_empty(self) -> bool:
        return not self.body_markdown or len(self.body_markdown.strip()) < 50
