import anthropic
import json
import logging

from src.models.property_listing import PropertyListing

logger = logging.getLogger(__name__)


class TranslatorService:
    """Claude API-based translator service for Japanese real estate listings."""

    SYSTEM_PROMPT = """你是一位专业的日本房产营销专家，专门为中国买家撰写房产推广文案。

重要规则：
- 你的所有输出必须是简体中文（Simplified Chinese）
- 绝对不要用日语、韩语或英语回复
- 你是在撰写微博（Weibo）房产推广帖子，语气要专业且有吸引力
- 必须严格按照下面的格式输出

步骤：
1. 识别输入语言（日语、中文或韩语）
2. 提取房产信息
3. 用简体中文输出JSON块和格式化文案

你必须先输出JSON块，然后输出格式化文案。

JSON块（未知字段用null）：
```json
{
  "name": "房产名称",
  "location": "所在地",
  "price_jpy": 35000000,
  "area_sqm": 65.5,
  "layout": "2LDK",
  "year_built": 2005,
  "structure": "RC",
  "nearest_station": "东京站 步行5分钟",
  "management_fee": 15000,
  "repair_reserve": 8000,
  "yield_gross": 5.2,
  "yield_net": 4.1,
  "occupancy_status": "空室",
  "ownership_type": "所有权",
  "land_area_sqm": null,
  "highlights": "朝南、转角房",
  "contact_info": null,
  "detected_language": "ja"
}
```
{IF_EXCHANGE_RATE}
格式化文案（必须是简体中文，用emoji）：
🏠 房产名称：[name]
📍 所在地：[location]
💰 价格：¥[price]（约[cny_price]万人民币）
📐 面积：[area]㎡（[tsubo]坪）
🏗️ 户型：[layout]
📅 建筑年份：[year]年
🏢 建筑结构：[structure]
🚉 交通：[station]
💵 管理费：¥[mgmt_fee]/月
💵 修缮基金：¥[repair]/月
📊 投资回报率：表面[gross]% / 实质[net]%
📋 现况：[status]
🔑 产权：[ownership]
📐 土地面积：[land_area]㎡
✨ 亮点：[highlights]
📞 联系方式：[contact]

在文案最后加一段简短的专业点评（2-3句话），突出投资价值或居住优势。"""

    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)

    def translate_and_format(
        self,
        text: str,
        exchange_rate: float | None = None,
        exchange_rate_date: str | None = None,
    ) -> tuple[PropertyListing, str]:
        """Translate and format a Japanese real estate listing into Simplified Chinese.

        Args:
            text: The raw property listing text (Japanese, Chinese, or Korean).
            exchange_rate: Optional JPY-to-CNY exchange rate (e.g. 0.0485).
            exchange_rate_date: Optional date string for the exchange rate.

        Returns:
            A tuple of (PropertyListing, formatted_text).
        """
        # Build the system prompt with optional exchange rate info
        if exchange_rate is not None:
            rate_insert = (
                f"\nExchange rate: 1 JPY = {exchange_rate} CNY"
                f" (as of {exchange_rate_date})."
                f" Include CNY conversion for all JPY prices.\n"
            )
        else:
            rate_insert = ""

        system_prompt = self.SYSTEM_PROMPT.replace("{IF_EXCHANGE_RATE}", rate_insert)

        # Embed instructions in user message because CLIProxyAPI drops the
        # system parameter.  Wrapping in [INSTRUCTIONS] tags keeps it clear.
        user_message = (
            f"[INSTRUCTIONS]\n{system_prompt}\n[/INSTRUCTIONS]\n\n"
            f"以下是需要处理的房产信息：\n{text}"
        )

        # Call Claude API
        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": user_message}],
        )

        response_text = response.content[0].text

        # Parse the response
        extracted_json = None
        formatted_text = response_text

        # Try to extract JSON block between ```json and ``` markers
        json_start = response_text.find("```json")
        if json_start != -1:
            json_body_start = response_text.index("\n", json_start) + 1
            json_end = response_text.find("```", json_body_start)
            if json_end != -1:
                json_str = response_text[json_body_start:json_end].strip()
                try:
                    extracted_json = json.loads(json_str)
                except json.JSONDecodeError:
                    logger.warning(
                        "Failed to parse JSON block from response, "
                        "attempting partial extraction"
                    )

                # Extract formatted text: everything after the closing ```
                remaining = response_text[json_end + 3 :].strip()
                if remaining:
                    formatted_text = remaining
                else:
                    formatted_text = response_text

        # Build PropertyListing from extracted fields
        if extracted_json is not None:
            listing = self._build_listing(
                extracted_json, text, exchange_rate
            )
        else:
            # No JSON found — create a minimal PropertyListing
            logger.warning(
                "No JSON block found in response, creating minimal PropertyListing"
            )
            listing = PropertyListing(
                original_text=text,
                original_language="ja",
            )

        return listing, formatted_text

    def _build_listing(
        self,
        data: dict,
        original_text: str,
        exchange_rate: float | None,
    ) -> PropertyListing:
        """Create a PropertyListing from extracted JSON fields.

        Missing fields are left as None — we do NOT fail on incomplete data (T017a).
        """
        price_jpy = data.get("price_jpy")
        area_sqm = data.get("area_sqm")

        # Calculate derived fields
        price_cny = None
        if exchange_rate is not None and price_jpy is not None:
            price_cny = price_jpy * exchange_rate

        area_tsubo = None
        if area_sqm is not None:
            area_tsubo = area_sqm / 3.306

        listing = PropertyListing(
            name=data.get("name"),
            location=data.get("location"),
            price_jpy=price_jpy,
            price_cny=price_cny,
            area_sqm=area_sqm,
            area_tsubo=area_tsubo,
            layout=data.get("layout"),
            year_built=data.get("year_built"),
            structure=data.get("structure"),
            nearest_station=data.get("nearest_station"),
            management_fee=data.get("management_fee"),
            repair_reserve=data.get("repair_reserve"),
            yield_gross=data.get("yield_gross"),
            yield_net=data.get("yield_net"),
            occupancy_status=data.get("occupancy_status"),
            ownership_type=data.get("ownership_type"),
            land_area_sqm=data.get("land_area_sqm"),
            highlights=data.get("highlights"),
            contact_info=data.get("contact_info"),
            original_text=original_text,
            original_language=data.get("detected_language", "ja"),
        )

        return listing

    def _get_missing_fields(self, listing: PropertyListing) -> list[str]:
        """Check key fields and return a list of field names that are None."""
        key_fields = [
            "name",
            "location",
            "price_jpy",
            "area_sqm",
            "layout",
            "year_built",
            "structure",
            "nearest_station",
        ]
        missing = []
        for field in key_fields:
            if getattr(listing, field, None) is None:
                missing.append(field)
        return missing
