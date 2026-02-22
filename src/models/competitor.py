"""Competitor data models for benchmarking.

CompetitorAccount represents a Weibo account being monitored.
CompetitorPost represents a single post scraped from a competitor.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
import uuid


@dataclass
class CompetitorAccount:
    uid: str = ""
    nickname: str = ""
    source: str = "manual"  # "manual" or "auto"
    active: bool = True
    added_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_scraped_at: str | None = None
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> CompetitorAccount:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class CompetitorPost:
    id: str = ""  # Weibo post mid
    competitor_uid: str = ""
    text: str = ""
    image_count: int = 0
    hashtags: list[str] = field(default_factory=list)
    reposts_count: int = 0
    comments_count: int = 0
    attitudes_count: int = 0
    created_at: str = ""
    scraped_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    @property
    def engagement(self) -> int:
        """Total engagement score."""
        return self.reposts_count + self.comments_count + self.attitudes_count

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> CompetitorPost:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
