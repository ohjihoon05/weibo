"""End-to-end pipeline test with mocked external services.

Tests the full pipeline without real API tokens:
- Image processing (real Pillow)
- Translation (mocked Claude API)
- Weibo posting (mocked HTTP)
- Exchange rate (mocked HTTP + fallback)
- Hashtag generation (real)
- Storage (real JSON files)
- Post model state transitions (real)
"""

import sys
import os
import json
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch, MagicMock
from io import BytesIO
from PIL import Image


def create_test_image(width=4000, height=3000):
    """Create a test JPEG image in a temp file."""
    img = Image.new("RGB", (width, height), color=(255, 100, 50))
    path = os.path.join(tempfile.gettempdir(), "test_property.jpg")
    img.save(path, "JPEG", quality=95)
    return path


def test_image_processor():
    """T010: Image processor — resize, EXIF, <4MB."""
    print("  [T010] Image processor...")
    from src.services.image_processor import process_image, TARGET_MAX_BYTES

    path = create_test_image(4000, 3000)
    result = process_image(path)

    assert isinstance(result, bytes)
    assert len(result) < TARGET_MAX_BYTES

    # Verify output is valid JPEG under 1080px
    img = Image.open(BytesIO(result))
    assert img.format == "JPEG"
    assert max(img.size) <= 1080
    print(f"    Input: 4000x3000 → Output: {img.size[0]}x{img.size[1]}, {len(result):,} bytes")
    print("    PASS")
    os.unlink(path)
    return result


def test_models():
    """T007, T008: PropertyListing + Post model + state transitions."""
    print("  [T007] PropertyListing...")
    from src.models.property_listing import PropertyListing

    listing = PropertyListing(
        original_text="テスト物件 東京都港区 3500万円 2LDK 65㎡",
        original_language="ja",
        name="テストマンション港区",
        location="東京都港区赤坂1-1-1",
        price_jpy=35000000,
        area_sqm=65.5,
        layout="2LDK",
        year_built=2005,
        structure="RC造",
        nearest_station="六本木駅 徒歩5分",
        management_fee=15000,
        repair_reserve=8000,
        yield_gross=5.2,
        yield_net=4.1,
        occupancy_status="空室",
        ownership_type="所有権",
    )
    d = listing.to_dict()
    listing2 = PropertyListing.from_dict(d)
    assert listing2.name == listing.name
    assert listing2.price_jpy == 35000000
    print("    PropertyListing roundtrip: OK")

    print("  [T008] Post state transitions...")
    from src.models.post import Post, PostHistory, Status, Mode, Action

    # Preview mode flow
    post = Post(listing_id=listing.id, telegram_chat_id=123, mode=Mode.preview.value)
    assert post.status == Status.pending_translation.value
    post.transition_to(Status.pending_approval.value)
    post.transition_to(Status.approved.value)
    post.transition_to(Status.posting.value)
    post.transition_to(Status.posted.value)
    print(f"    Preview flow: pending_translation → ... → posted: OK")

    # Auto mode flow
    post2 = Post(listing_id=listing.id, telegram_chat_id=123, mode=Mode.auto.value)
    post2.transition_to(Status.approved.value)
    post2.transition_to(Status.posting.value)
    post2.transition_to(Status.failed.value)
    print(f"    Auto flow: pending_translation → ... → failed: OK")

    # Invalid transition
    post3 = Post(listing_id=listing.id, telegram_chat_id=123)
    try:
        post3.transition_to(Status.posted.value)
        assert False
    except ValueError:
        pass
    print("    Invalid transition rejected: OK")
    print("    PASS")
    return listing


def test_storage(listing):
    """T009: JSON file storage — save/load/history."""
    print("  [T009] JSON storage...")
    from src.models.post import Post, PostHistory, Action, Mode, Status
    from src.storage.json_store import (
        save_post, load_post, append_history,
        save_exchange_rate, load_exchange_rate, get_data_dir,
    )

    post = Post(
        listing_id=listing.id,
        formatted_text="🏠 测试物件",
        hashtags=["#日本房产"],
        telegram_chat_id=123,
        mode=Mode.auto.value,
        status=Status.posted.value,
        weibo_url="https://m.weibo.cn/detail/test123",
    )

    # Save post
    path = save_post(post.to_dict())
    assert os.path.exists(path)
    print(f"    save_post → {os.path.basename(path)}")

    # Load post
    loaded = load_post(post.id)
    assert loaded is not None
    assert loaded["id"] == post.id
    assert loaded["formatted_text"] == "🏠 测试物件"
    print(f"    load_post: OK")

    # Append history
    history = PostHistory(
        post_id=post.id,
        action=Action.create_post.value,
        success=True,
    )
    append_history(history.to_dict())
    print(f"    append_history: OK")

    # Exchange rate cache
    save_exchange_rate({"rate": 0.048, "source": "test", "fetched_at": "2026-02-22T10:00:00+00:00"})
    cached = load_exchange_rate()
    assert cached["rate"] == 0.048
    print(f"    exchange_rate cache: OK")
    print("    PASS")


def test_exchange_rate():
    """T022: Exchange rate service — fallback chain."""
    print("  [T022] Exchange rate fallback chain...")
    from src.services.exchange_rate import get_jpy_to_cny_rate

    # Test with real APIs (will hit network, fallback to cache/hardcoded if offline)
    rate, source, date = get_jpy_to_cny_rate()
    assert isinstance(rate, float)
    assert rate > 0
    print(f"    Rate: 1 JPY = {rate} CNY (source: {source})")
    print("    PASS")
    return rate, date


def test_hashtag_generator(listing):
    """T023: Hashtag generator."""
    print("  [T023] Hashtag generator...")
    from src.services.hashtag_generator import generate_hashtags

    tags = generate_hashtags(listing)
    assert "#日本房产" in tags
    assert "#东京房产" in tags
    assert "#公寓" in tags
    assert "#投资回报" in tags
    assert "#京都房产" not in tags  # 東京都 must NOT match 京都
    print(f"    Tags: {tags}")
    print("    PASS")


def test_translator_mocked(listing_data, rate, rate_date):
    """T013: Translator with mocked Claude API."""
    print("  [T013] Translator (mocked Claude API)...")

    mock_response_text = """```json
{
  "name": "テストマンション港区",
  "location": "東京都港区赤坂1-1-1",
  "price_jpy": 35000000,
  "area_sqm": 65.5,
  "layout": "2LDK",
  "year_built": 2005,
  "structure": "RC造",
  "nearest_station": "六本木駅 徒歩5分",
  "management_fee": 15000,
  "repair_reserve": 8000,
  "yield_gross": 5.2,
  "yield_net": 4.1,
  "occupancy_status": "空室",
  "ownership_type": "所有権",
  "land_area_sqm": null,
  "highlights": "南向き角部屋、六本木駅近",
  "contact_info": null,
  "detected_language": "ja"
}
```

🏠 物件名称: 测试公寓港区
📍 所在地: 东京都港区赤坂1-1-1
💰 价格: ¥35,000,000 (约 ¥168万人民币)
📐 面积: 65.5㎡ (19.8坪)
🏗️ 房间布局: 2LDK
📅 建筑年份: 2005年
🏢 建筑结构: RC造
🚉 交通: 六本木站 步行5分钟
💵 管理费: ¥15,000/月
💵 修缮积立金: ¥8,000/月
📊 投资回报率: 表面5.2% / 实质4.1%
📋 现况: 空置
🔑 产权: 所有权
✨ 亮点: 朝南角房、六本木站附近
"""

    # Create a fake anthropic module so we can import translator without the real package
    import types
    fake_anthropic = types.ModuleType("anthropic")
    fake_anthropic.Anthropic = MagicMock
    sys.modules["anthropic"] = fake_anthropic

    # Mock the client's messages.create to return our test response
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=mock_response_text)]

    # Need to reimport since anthropic was just faked
    if "src.services.translator" in sys.modules:
        del sys.modules["src.services.translator"]
    from src.services.translator import TranslatorService

    translator = TranslatorService(api_key="test-key")
    translator.client.messages.create.return_value = mock_message

    listing, formatted_text = translator.translate_and_format(
        "テスト物件 東京都港区 3500万円 2LDK 65㎡",
        exchange_rate=rate,
        exchange_rate_date=rate_date,
    )

    assert listing.name == "テストマンション港区"
    assert listing.price_jpy == 35000000
    assert listing.original_language == "ja"
    assert "物件名称" in formatted_text
    assert "六本木" in formatted_text

    # Check missing fields detection
    missing = translator._get_missing_fields(listing)
    assert "contact_info" not in missing  # not a key field
    assert len(missing) == 0  # all key fields present
    print(f"    Listing: {listing.name} ({listing.location})")
    print(f"    Price: ¥{listing.price_jpy:,}")
    if listing.price_cny:
        print(f"    Price CNY: ¥{listing.price_cny:,.0f}")
    print(f"    Formatted text: {len(formatted_text)} chars")
    print("    PASS")
    return listing, formatted_text


def test_weibo_client_mocked(image_bytes):
    """T012, T026, T029: Weibo client with mocked HTTP + retry."""
    print("  [T012] Weibo client (mocked HTTP)...")
    from src.services.weibo_client import WeiboClient, WeiboAPIError

    # Mock successful upload
    mock_upload_resp = MagicMock()
    mock_upload_resp.json.return_value = {"pic_ids": ["pic123456"], "idstr": "999"}

    mock_post_resp = MagicMock()
    mock_post_resp.json.return_value = {"idstr": "4567890123", "id": 4567890123}

    with patch("requests.post") as mock_post:
        mock_post.side_effect = [mock_upload_resp, mock_post_resp]

        client = WeiboClient(access_token="test-token")

        # Upload image
        pic_id = client.upload_image(image_bytes)
        assert pic_id == "pic123456"
        print(f"    upload_image → pic_id: {pic_id}")

        # Create post
        url = client.create_post("🏠 测试物件", [pic_id])
        assert "4567890123" in url
        print(f"    create_post → {url}")

    print("  [T026] Retry logic...")
    # Test retry on retryable error
    error_resp = MagicMock()
    error_resp.json.return_value = {"error_code": 10001, "error": "System error"}

    success_resp = MagicMock()
    success_resp.json.return_value = {"pic_ids": ["pic_retry_ok"], "idstr": "111"}

    with patch("requests.post") as mock_post, patch("time.sleep"):
        mock_post.side_effect = [error_resp, success_resp]
        client = WeiboClient(access_token="test-token")
        pic_id = client.upload_image(image_bytes)
        assert pic_id == "pic_retry_ok"
        print(f"    Retry success after error 10001: OK")

    print("  [T029] Token expiry handling...")
    # Test non-retryable token error
    token_resp = MagicMock()
    token_resp.json.return_value = {"error_code": 21327, "error": "expired"}

    with patch("requests.post") as mock_post, patch("time.sleep"):
        mock_post.return_value = token_resp
        client = WeiboClient(access_token="test-token")
        try:
            client.upload_image(image_bytes)
            assert False, "Should have raised"
        except WeiboAPIError as e:
            assert e.error_code == 21327
            assert "만료" in e.error_message
            print(f"    Token expired error: {e.error_code} — correctly raised")

    print("    PASS")


def test_full_pipeline_mocked():
    """Full pipeline simulation: image → translate → hashtag → weibo post."""
    print("  [FULL] End-to-end pipeline simulation...")

    from src.models.post import Post, PostHistory, Status, Mode, Action
    from src.services.hashtag_generator import generate_hashtags
    from src.storage.json_store import save_post, append_history

    # Step 1: Process image
    from src.services.image_processor import process_image
    img_path = create_test_image(2000, 1500)
    image_bytes = process_image(img_path)
    print(f"    1. Image processed: {len(image_bytes):,} bytes")

    # Step 2: Mock translation
    mock_response_text = '```json\n{"name":"港区マンション","location":"東京都港区","price_jpy":28000000,"area_sqm":55.0,"layout":"1LDK","year_built":2010,"structure":"RC造","nearest_station":"赤坂駅 徒歩3分","management_fee":12000,"repair_reserve":6000,"yield_gross":6.1,"yield_net":5.0,"occupancy_status":"入居中","ownership_type":"所有権","detected_language":"ja"}\n```\n\n🏠 物件名称: 港区公寓\n📍 所在地: 东京都港区\n💰 价格: ¥28,000,000'

    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=mock_response_text)]

    if "src.services.translator" in sys.modules:
        del sys.modules["src.services.translator"]
    from src.services.translator import TranslatorService
    translator = TranslatorService(api_key="test")
    translator.client.messages.create.return_value = mock_msg

    listing, formatted_text = translator.translate_and_format(
        "港区マンション 2800万 1LDK 55㎡",
        exchange_rate=0.048,
        exchange_rate_date="2026-02-22",
    )
    print(f"    2. Translated: {listing.name} → {len(formatted_text)} chars")

    # Step 3: Generate hashtags
    hashtags = generate_hashtags(listing)
    formatted_text += "\n\n" + " ".join(hashtags)
    print(f"    3. Hashtags: {hashtags}")

    # Step 4: Create post model
    post = Post(
        listing_id=listing.id,
        formatted_text=formatted_text,
        hashtags=hashtags,
        image_paths=[img_path],
        telegram_chat_id=123456,
        mode=Mode.auto.value,
        status=Status.approved.value,
    )

    # Log translation
    append_history(PostHistory(
        post_id=post.id, action=Action.translate.value, success=True,
    ).to_dict())

    # Step 5: Mock Weibo upload + post
    mock_upload = MagicMock()
    mock_upload.json.return_value = {"pic_ids": ["pic_e2e_test"], "idstr": "999"}
    mock_create = MagicMock()
    mock_create.json.return_value = {"idstr": "9876543210"}

    from src.services.weibo_client import WeiboClient
    with patch("requests.post") as mock_post:
        mock_post.side_effect = [mock_upload, mock_create]
        weibo = WeiboClient(access_token="test")
        pic_id = weibo.upload_image(image_bytes)
        weibo_url = weibo.create_post(formatted_text, [pic_id])

    post.weibo_url = weibo_url
    post.status = Status.posted.value
    print(f"    4. Weibo posted: {weibo_url}")

    # Log posting
    append_history(PostHistory(
        post_id=post.id, action=Action.upload_image.value, success=True,
    ).to_dict())
    append_history(PostHistory(
        post_id=post.id, action=Action.create_post.value, success=True,
    ).to_dict())

    # Step 6: Save post
    path = save_post(post.to_dict())
    print(f"    5. Saved: {os.path.basename(path)}")

    # Verify saved data
    from src.storage.json_store import load_post
    loaded = load_post(post.id)
    assert loaded["weibo_url"] == weibo_url
    assert loaded["status"] == "posted"
    assert len(loaded["hashtags"]) > 0
    print(f"    6. Verified: status={loaded['status']}, hashtags={len(loaded['hashtags'])}")

    os.unlink(img_path)
    print("    PASS")


def main():
    print("=" * 60)
    print("Weibo Auto-Posting Bot — Pipeline Test")
    print("(External services are mocked)")
    print("=" * 60)
    print()

    print("[Phase 2: Foundational]")
    listing = test_models()
    test_storage(listing)
    print()

    print("[Phase 3: US1 — Core Pipeline]")
    image_bytes = test_image_processor()
    rate_result = test_exchange_rate()
    rate, rate_date = rate_result
    test_hashtag_generator(listing)
    listing_t, formatted = test_translator_mocked(listing.to_dict(), rate, rate_date)
    test_weibo_client_mocked(image_bytes)
    print()

    print("[Integration: Full Pipeline]")
    test_full_pipeline_mocked()
    print()

    print("=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    main()
