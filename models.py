from dataclasses import dataclass, field
from typing import Any


@dataclass
class ContentItem:
    """Normalized representation shared by every collected source type."""

    title: str
    url: str
    source_name: str
    published: str
    summary: str
    source_type: str
    branch: str
    source_priority: str = "low"
    authors_or_org: str = ""
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    topics: list[str] = field(default_factory=list)
    score: float = 0.0
    score_reasons: list[str] = field(default_factory=list)
