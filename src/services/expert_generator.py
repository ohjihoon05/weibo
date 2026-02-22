"""Expert content generator using Claude API.

Generates Japanese real estate expert content in Chinese for Weibo.
Focuses on Osaka/Kansai region. Never generates specific property
information (FR-011, FR-013 compliance).
"""

import logging
import re
import random
from datetime import datetime

import anthropic

from src.config import CLAUDE_API_KEY, EXPERT_TOPICS, EXPERT_CONTENT_MAX_LENGTH
from src.models.expert_content import ExpertContent, ExpertTopic, ExpertContentStatus
from src.storage.json_store import load_expert_content, append_expert_content

logger = logging.getLogger(__name__)

MAX_RETRIES = 2

# Forbidden terms that indicate specific property info (FR-013)
FORBIDDEN_TERMS = [
    "万円", "万日元", "万人民币",  # Specific prices
    "丁目", "番地", "号室",         # Specific addresses
    "号楼", "栋", "号房",           # Unit numbers
    "㎡", "平米", "平方米",         # Specific areas (in listing context)
]

# Topic descriptions for Claude prompt
TOPIC_PROMPTS = {
    ExpertTopic.MARKET_TREND.value: "大阪/关西地区房地产市场最新动态和趋势分析",
    ExpertTopic.INVESTMENT_TIP.value: "日本房地产投资回报率分析和实用投资建议",
    ExpertTopic.AREA_GUIDE.value: "大阪近郊热门地区介绍（交通、生活环境、发展前景）",
    ExpertTopic.TAX_VISA.value: "外国人在日本购房相关的税务、签证、法律知识",
    ExpertTopic.PURCHASE_PROCESS.value: "日本房地产交易流程和注意事项详解",
}

SYSTEM_PROMPT = """你是一位专注于大阪/关西地区的日本房地产专家。你在微博上为中国投资者提供专业的日本房地产知识。

写作要求：
1. 使用简体中文
2. 内容控制在200字以内，适合微博发布
3. 专注于大阪和关西地区（大阪、京都、神户、奈良周边）
4. 提供有价值的信息和见解
5. 语气专业但亲切，适合社交媒体
6. 可以使用适当的emoji增加可读性

严格禁止：
- 不得提及任何具体楼盘名称、地址、价格、面积
- 不得编造具体数据（如具体收益率数字、具体价格）
- 不得推荐或暗示任何特定物件
- 只提供一般性的市场信息、趋势分析和投资知识
"""


class ExpertGenerator:
    """Generates expert content using Claude API."""

    def __init__(self, api_key: str | None = None):
        self._client = anthropic.Anthropic(api_key=api_key or CLAUDE_API_KEY)

    def generate(self, topic: str | None = None) -> ExpertContent | None:
        """Generate expert content for the given topic.

        Uses topic rotation if no topic specified (picks least recently used).

        Args:
            topic: Optional ExpertTopic value. If None, auto-selects.

        Returns:
            ExpertContent object or None if generation fails.
        """
        if topic is None:
            topic = self._select_topic()

        topic_desc = TOPIC_PROMPTS.get(topic, TOPIC_PROMPTS[ExpertTopic.MARKET_TREND.value])

        for attempt in range(MAX_RETRIES + 1):
            try:
                text = self._call_claude(topic_desc)
                if not text:
                    logger.warning("Claude returned empty response (attempt %d)", attempt + 1)
                    continue

                # FR-013: Validate no forbidden terms
                if self._contains_forbidden(text):
                    logger.warning("Generated content contains forbidden terms, regenerating (attempt %d)", attempt + 1)
                    continue

                # Truncate if too long
                if len(text) > EXPERT_CONTENT_MAX_LENGTH:
                    text = text[:EXPERT_CONTENT_MAX_LENGTH]

                # Generate hashtags
                hashtags = self._generate_hashtags(topic)

                # Append hashtags to text
                hashtag_str = " ".join(hashtags)
                full_text = f"{text}\n\n{hashtag_str}"

                content = ExpertContent(
                    topic=topic,
                    text_zh=full_text,
                    hashtags=hashtags,
                )

                # Persist
                append_expert_content(content.to_dict())
                logger.info("Generated expert content: topic=%s, length=%d", topic, len(full_text))
                return content

            except anthropic.APIError as exc:
                logger.error("Claude API error (attempt %d/%d): %s", attempt + 1, MAX_RETRIES + 1, exc)
                if attempt >= MAX_RETRIES:
                    return None
            except Exception as exc:
                logger.exception("Expert generation error (attempt %d): %s", attempt + 1, exc)
                if attempt >= MAX_RETRIES:
                    return None

        return None

    def _call_claude(self, topic_desc: str) -> str:
        """Call Claude API to generate content."""
        message = self._client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"请写一条关于以下主题的微博：{topic_desc}",
                }
            ],
        )
        return message.content[0].text.strip() if message.content else ""

    def _contains_forbidden(self, text: str) -> bool:
        """Check if text contains forbidden property-specific terms."""
        for term in FORBIDDEN_TERMS:
            if term in text:
                logger.debug("Forbidden term found: %s", term)
                return True
        return False

    def _select_topic(self) -> str:
        """Select the least recently used topic."""
        recent = load_expert_content()
        recent_topics = [e.get("topic") for e in recent[-10:]]

        # Find topics not recently used
        available = [t for t in EXPERT_TOPICS if t not in recent_topics]
        if not available:
            available = list(EXPERT_TOPICS)

        return random.choice(available)

    @staticmethod
    def _generate_hashtags(topic: str) -> list[str]:
        """Generate hashtags for expert content."""
        base_tags = ["#日本房产", "#大阪房产", "#海外置业"]

        topic_tags = {
            ExpertTopic.MARKET_TREND.value: ["#关西投资", "#日本房产知识"],
            ExpertTopic.INVESTMENT_TIP.value: ["#投资回报", "#海外投资"],
            ExpertTopic.AREA_GUIDE.value: ["#关西生活", "#大阪生活"],
            ExpertTopic.TAX_VISA.value: ["#日本签证", "#海外购房"],
            ExpertTopic.PURCHASE_PROCESS.value: ["#日本买房", "#购房指南"],
        }

        tags = base_tags + topic_tags.get(topic, [])
        return tags
