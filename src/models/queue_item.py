"""QueueItem model for the publish queue.

Represents a single content item waiting to be published to Weibo.
Supports two content types: 'listing' (manual property posts) and
'expert' (auto-generated expert content).
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
import uuid


class QueueItemType(str, Enum):
    listing = "listing"
    expert = "expert"


class QueueItemStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


@dataclass
class QueueItem:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: str = QueueItemType.listing.value
    text: str = ""
    image_paths: list[str] = field(default_factory=list)
    scheduled_at: str = ""  # ISO format UTC
    status: str = QueueItemStatus.pending.value
    queued_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None
    post_id: str | None = None
    telegram_chat_id: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> QueueItem:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def mark_processing(self) -> None:
        self.status = QueueItemStatus.processing.value
        self.started_at = datetime.utcnow().isoformat()

    def mark_completed(self, post_id: str) -> None:
        self.status = QueueItemStatus.completed.value
        self.completed_at = datetime.utcnow().isoformat()
        self.post_id = post_id

    def mark_failed(self, error: str) -> None:
        self.status = QueueItemStatus.failed.value
        self.completed_at = datetime.utcnow().isoformat()
        self.error = error

    def reset_to_pending(self) -> None:
        """Reset a failed item back to pending for retry."""
        self.status = QueueItemStatus.pending.value
        self.started_at = None
        self.completed_at = None
        self.error = None
