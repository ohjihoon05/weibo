# Data Model: Weibo 쿠키 자동 갱신 시스템

**Feature**: 005-cookie-auto-refresh
**Date**: 2026-02-23

## Entities

### 1. Cookie Data (기존 — data/weibo_cookies.json)

기존 쿠키 저장 구조. 변경 없음.

| Field | Type | Description |
|-------|------|-------------|
| cookies | dict[str, str] | 쿠키 키-값 쌍 (SUB, SUBP, XSRF-TOKEN 등) |
| uid | str | Weibo 사용자 ID |
| updated_at | str (ISO 8601) | 쿠키 설정/갱신 시각 (UTC) |
| validated_at | str (ISO 8601) | 마지막 검증 시각 (UTC) |
| status | str | "valid" / "expired" / "unknown" |

**Identity**: 단일 파일, 하나의 쿠키 세트만 관리

### 2. CookieCloud Config (신규 — 환경 변수)

CookieCloud 연동 설정. 세 값 모두 존재해야 활성화.

| Field | Env Variable | Type | Required | Description |
|-------|-------------|------|----------|-------------|
| server | COOKIECLOUD_SERVER | str | Optional | 서버 URL (예: http://localhost:8088) |
| uuid | COOKIECLOUD_UUID | str | Optional | 동기화 식별자 |
| password | COOKIECLOUD_PASSWORD | str | Optional | 복호화 비밀번호 |

**Activation Rule**: `COOKIECLOUD_SERVER` AND `COOKIECLOUD_UUID` AND `COOKIECLOUD_PASSWORD` 모두 설정된 경우에만 CookieCloud 기능 활성화

### 3. Cookie Expiry Config (신규 — 환경 변수)

만료 임박 경고 임계치 설정.

| Field | Env Variable | Type | Default | Description |
|-------|-------------|------|---------|-------------|
| warning_hours | COOKIE_EXPIRY_WARNING_HOURS | int | 36 | 만료 임박 경고 기준 시간 |

### 4. Alert State (신규 — 인메모리, bot_data)

알림 중복 방지를 위한 런타임 상태. 영속 저장 안 함.

| Field | Key in bot_data | Type | Description |
|-------|----------------|------|-------------|
| last_warning_at | last_cookie_warning_at | datetime / None | 마지막 만료 임박 경고 발송 시각 |

**Lifecycle**: 봇 시작 시 None → 경고 발송 시 현재 시각으로 갱신 → 봇 재시작 시 리셋

## State Transitions

### Cookie Status Flow

```
[시작] → unknown
  │
  ├─ validate() → login=True  → valid
  │                                │
  │                    나이 > 36h? ──→ valid (expiring_soon) → 경고 알림
  │                                │
  │                                └─ valid (fresh) → 정상
  │
  ├─ validate() → login=False → expired
  │                                │
  │                    CookieCloud 설정? ──→ refresh 시도
  │                                │           │
  │                                │      성공 → valid + 성공 알림
  │                                │      실패 → expired + 긴급 알림
  │                                │
  │                                └─ 미설정 → expired + 긴급 알림
  │
  └─ validate() → 네트워크 실패 → unknown → 다음 주기 재시도
```

## Relationships

```
CookieManager (기존)
  ├── Cookie Data (기존 JSON 파일)
  ├── CookieCloud Config (신규 환경 변수) ── 선택적 연동
  └── Cookie Expiry Config (신규 환경 변수)

cookie_validation_job (기존 main.py)
  ├── CookieManager.validate_cookies()
  ├── CookieManager.get_cookie_age_hours()  [신규]
  ├── CookieManager.is_expiring_soon()      [신규]
  ├── CookieManager.refresh_cookies_via_cookiecloud()  [신규]
  └── Alert State (bot_data)                [신규]
```
