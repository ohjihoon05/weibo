"""ExpertContent model for auto-generated expert content.

Represents Japanese real estate expert content auto-generated
by Claude API for days without property listings.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
import uuid


class ExpertTopic(str, Enum):
    MARKET_TREND = "MARKET_TREND"          # 오사카/간사이 부동산 시장 동향
    INVESTMENT_TIP = "INVESTMENT_TIP"      # 일본 부동산 투자 수익률/팁
    AREA_GUIDE = "AREA_GUIDE"              # 오사카 근교 지역 소개
    TAX_VISA = "TAX_VISA"                  # 외국인 세금/비자 정보
    PURCHASE_PROCESS = "PURCHASE_PROCESS"  # 일본 부동산 매매 절차 안내


class ExpertContentStatus(str, Enum):
    generated = "generated"
    queued = "queued"
    posted = "posted"


@dataclass
class ExpertContent:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    topic: str = ExpertTopic.MARKET_TREND.value
    text_zh: str = ""
    hashtags: list[str] = field(default_factory=list)
    status: str = ExpertContentStatus.generated.value
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    queue_item_id: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> ExpertContent:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def mark_queued(self, queue_item_id: str) -> None:
        self.status = ExpertContentStatus.queued.value
        self.queue_item_id = queue_item_id

    def mark_posted(self) -> None:
        self.status = ExpertContentStatus.posted.value
