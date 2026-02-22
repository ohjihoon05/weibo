# Data Model: Weibo Cookie 기반 포스팅 전환

## Entities

### WeiboCookies (신규)

m.weibo.cn 인증에 필요한 쿠키 데이터를 관리하는 엔티티.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| cookies | dict[str, str] | Yes | 쿠키 키-값 쌍 (SUB, SUBP, XSRF-TOKEN 등) |
| uid | str | No | 로그인된 사용자 ID (/api/config에서 획득) |
| updated_at | str (ISO 8601) | Yes | 쿠키 최종 갱신 시각 |
| validated_at | str (ISO 8601) | No | 최종 유효성 검증 시각 |
| status | str | Yes | 유효성 상태: "valid", "expired", "unknown" |

**필수 쿠키 필드**: SUB, SUBP, XSRF-TOKEN
**부가 쿠키 필드**: SSOLoginState, _T_WM, MLOGIN

**저장 위치**: `data/weibo_cookies.json`
**파일 권한**: 600 (소유자만 읽기/쓰기)

**상태 전이**:
```
unknown → valid (검증 성공)
unknown → expired (검증 실패)
valid → expired (검증 실패 또는 포스팅 시 인증 에러)
expired → valid (쿠키 갱신 성공)
```

### WeiboClient 공개 인터페이스 (변경)

기존 WeiboClient의 공개 인터페이스를 유지하되 내부 구현 변경.

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| upload_image | (image_bytes: bytes) → str | pic_id | 엔드포인트 변경: uploadPic |
| create_post | (text: str, pic_ids: list[str]) → str | weibo_url | 엔드포인트 변경: /api/statuses/update |
| create_text_post | (text: str) → str | weibo_url | create_post에 pic_ids=[] 위임 |

**변경 사항**:
- 생성자: `__init__(access_token)` → `__init__(cookie_manager)`
- 내부: 모든 요청에 쿠키 헤더 + X-XSRF-TOKEN 헤더 포함
- 내부: 요청 전 `/api/config` 호출하여 st 토큰 갱신
- 에러: WeiboAPIError는 m.weibo.cn 응답 형식에 맞게 조정
  - `ok=0` → 에러
  - `data.login=false` → 쿠키 만료

### Config 환경변수 (변경)

**제거**: WEIBO_APP_KEY, WEIBO_APP_SECRET, WEIBO_ACCESS_TOKEN, WEIBO_REDIRECT_URI
**유지**: TELEGRAM_BOT_TOKEN, CLAUDE_API_KEY
**추가 없음**: 쿠키는 파일 기반 (`data/weibo_cookies.json`), 환경변수 불필요

## Relationships

```
main.py
  ├── CookieManager (cookie_manager.py)
  │     ├── load_cookies() → WeiboCookies
  │     ├── save_cookies(WeiboCookies)
  │     ├── validate_cookies() → bool
  │     └── parse_cookie_string(raw) → dict
  │
  ├── WeiboClient (weibo_client.py)
  │     ├── uses CookieManager for cookie access
  │     ├── upload_image(bytes) → pic_id
  │     ├── create_post(text, pic_ids) → url
  │     └── create_text_post(text) → url
  │
  └── TelegramHandler (telegram_handler.py)
        ├── /cookie command → CookieManager.parse + save + validate
        └── /status command → CookieManager.validate + display
```
