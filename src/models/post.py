from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
import uuid


class Status(str, Enum):
    pending_translation = "pending_translation"
    pending_approval = "pending_approval"
    approved = "approved"
    posting = "posting"
    posted = "posted"
    failed = "failed"


class Mode(str, Enum):
    preview = "preview"
    auto = "auto"


class Action(str, Enum):
    translate = "translate"
    upload_image = "upload_image"
    create_post = "create_post"


# Valid state transitions: current_status -> set of allowed next statuses
_VALID_TRANSITIONS: dict[str, set[str]] = {
    Status.pending_translation.value: {
        Status.pending_approval.value,
        Status.approved.value,
    },
    Status.pending_approval.value: {
        Status.approved.value,
        Status.pending_translation.value,
    },
    Status.approved.value: {
        Status.posting.value,
    },
    Status.posting.value: {
        Status.posted.value,
        Status.posting.value,
        Status.failed.value,
    },
}


@dataclass
class Post:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    listing_id: str = ""
    formatted_text: str = ""
    hashtags: list[str] = field(default_factory=list)
    image_paths: list[str] = field(default_factory=list)
    status: str = Status.pending_translation.value
    mode: str = Mode.preview.value
    weibo_post_id: str | None = None
    weibo_url: str | None = None
    telegram_chat_id: int = 0
    telegram_message_id: int | None = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    posted_at: str | None = None

    def transition_to(self, new_status: str) -> bool:
        """Validate and apply a state transition.

        Returns True if the transition is valid and the status was updated.
        Raises ValueError if the transition is not allowed.
        """
        allowed = _VALID_TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise ValueError(
                f"Invalid transition from '{self.status}' to '{new_status}'"
            )
        self.status = new_status
        return True

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Post:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class PostHistory:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    post_id: str = ""
    attempt_number: int = 1
    action: str = Action.translate.value
    success: bool = False
    error_message: str | None = None
    error_code: str | None = None
    weibo_response: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> PostHistory:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
