# Tasks: Weibo 쿠키 자동 갱신 시스템

**Input**: Design documents from `/specs/005-cookie-auto-refresh/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Organization**: Tasks are grouped by user story. US3 is foundational (blocks US1/US2). US1 is MVP. US2 builds on US1.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 의존성 설치 및 공유 설정 추가

- [x] T001 Install pycryptodome dependency — `pip install pycryptodome` on Raspberry Pi (CookieCloud AES-CBC 복호화용)
- [x] T002 Add CookieCloud and cookie expiry config variables to src/config.py — COOKIECLOUD_SERVER, COOKIECLOUD_UUID, COOKIECLOUD_PASSWORD (optional env vars), COOKIE_EXPIRY_WARNING_HOURS (default 36)

---

## Phase 2: User Story 3 — 깨진 자동 갱신 코드 정리 (Priority: P1)

**Goal**: 비작동 `refresh_cookies_via_openclaw()` 제거하여 불필요한 60초 타임아웃 대기 해소. US1/US2의 전제 조건.

**Independent Test**: 쿠키 만료 시 localhost:18789 호출 없이 즉시 다음 단계로 진행 확인 (VS-5)

### Implementation for User Story 3

- [x] T003 [US3] Remove `refresh_cookies_via_openclaw()` method from src/services/cookie_manager.py — 전체 메서드 삭제 (lines 205-261), "OpenClaw integration" 주석 섹션 포함
- [x] T004 [US3] Update `cookie_validation_job()` in src/main.py — `cm.refresh_cookies_via_openclaw()` 호출 제거, 쿠키 만료 시 즉시 수동 갱신 안내 알림만 전송하도록 단순화 (기존 lines 445-463)

**Checkpoint**: 쿠키 만료 시 OpenClaw 호출 없이 즉시 알림 전송. 60초 대기 제거 확인.

---

## Phase 3: User Story 1 — 쿠키 만료 사전 알림 (Priority: P1) 🎯 MVP

**Goal**: 쿠키가 만료되기 전에 Telegram으로 경고 알림을 보내 사전 대응 가능하게 함

**Independent Test**: 쿠키 나이가 36시간 초과 시 Telegram에 경고 알림 도착 확인 (VS-1, VS-2)

### Implementation for User Story 1

- [x] T005 [US1] Add `get_cookie_age_hours()` method to CookieManager in src/services/cookie_manager.py — `updated_at` 필드 기준 경과 시간(float, 시간 단위) 반환. updated_at 없으면 None 반환
- [x] T006 [US1] Add `is_expiring_soon()` method to CookieManager in src/services/cookie_manager.py — `get_cookie_age_hours()` > `threshold_hours` (기본값 config.COOKIE_EXPIRY_WARNING_HOURS) 여부 반환
- [x] T007 [US1] Enhance `cookie_validation_job()` in src/main.py with proactive alert logic — 쿠키 유효 시: `is_expiring_soon()` 체크 → True면 경고 알림 전송 (⏰ 이모지, 경과 시간 표시, /cookie 안내). 중복 방지: `bot_data["last_cookie_warning_at"]` 확인하여 24시간 이내 재전송 방지. 쿠키 만료 시: 갱신 방법 안내 포함 긴급 알림 (⚠️ 이모지)
- [x] T008 [US1] Verify proactive alert end-to-end — 봇 재시작 후 cookie_validation_job 실행하여 알림 흐름 확인 (VS-2 시나리오)

**Checkpoint**: 쿠키 유효+오래됨 → 경고 알림, 쿠키 만료 → 긴급 알림, 중복 방지 동작. CookieCloud 없이도 완전 독립 동작.

---

## Phase 4: User Story 2 — CookieCloud 연동으로 반자동 갱신 (Priority: P2)

**Goal**: CookieCloud 서버에서 최신 쿠키를 자동으로 가져와 갱신. 쿠키 만료 시 수동 개입 최소화.

**Independent Test**: CookieCloud 서버에 Weibo 쿠키 동기화 상태에서 만료된 쿠키가 자동 갱신되는지 확인 (VS-3)

### Implementation for User Story 2

- [x] T009 [US2] Implement CookieCloud decryption functions in src/services/cookie_manager.py — `_decrypt_cookiecloud_legacy()` (AES-256-CBC, EVP_BytesToKey, Salted__ prefix) + `_decrypt_cookiecloud_fixed()` (AES-128-CBC, zero IV) + `_decrypt_cookiecloud()` (crypto_type 분기). research.md R-002의 알고리즘 구현
- [x] T010 [US2] Implement `refresh_cookies_via_cookiecloud()` method in src/services/cookie_manager.py — GET {server}/get/{uuid} 호출 → 암호화 데이터 수신 → 복호화 → cookie_data에서 weibo 도메인 필터 → SUB/SUBP/XSRF-TOKEN 추출 → save_cookies() → validate_cookies() → 성공/실패 반환. 타임아웃 10초, ConnectionError/복호화 실패 등 graceful handling
- [x] T011 [US2] Add `is_cookiecloud_configured()` helper to CookieManager in src/services/cookie_manager.py — config.COOKIECLOUD_SERVER, COOKIECLOUD_UUID, COOKIECLOUD_PASSWORD 세 값 모두 존재 여부 확인
- [x] T012 [US2] Integrate CookieCloud into `cookie_validation_job()` in src/main.py — 쿠키 만료 시: `is_cookiecloud_configured()` 확인 → True면 `refresh_cookies_via_cookiecloud()` 시도 → 성공 시 "🔄 CookieCloud에서 쿠키가 갱신되었습니다" 알림 → 실패 시 기존 수동 갱신 안내 알림. CookieCloud 미설정 시: 즉시 수동 갱신 안내 알림
- [x] T013 [US2] Verify CookieCloud integration end-to-end — CookieCloud 설정/미설정 양쪽 시나리오 확인 (VS-3, VS-4, VS-6)

**Checkpoint**: CookieCloud 설정 시 자동 갱신, 미설정 시 기존 알림만 동작. 연결 실패 시 graceful 폴백.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: 서비스 재시작 및 전체 검증

- [x] T014 Restart weibo-bot systemd service — `sudo systemctl restart weibo-bot` 후 정상 구동 확인
- [x] T015 Run full quickstart.md validation — VS-1~VS-6 시나리오 전체 검증 (CookieCloud 미설정 상태에서 VS-1,2,4,5 우선 확인)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **US3 (Phase 2)**: Depends on Phase 1 — BLOCKS US1 and US2 (깨진 코드 제거가 선행 필수)
- **US1 (Phase 3)**: Depends on US3 completion — cookie_validation_job의 기반 흐름이 정리된 후 사전 알림 로직 추가
- **US2 (Phase 4)**: Depends on US1 completion — cookie_validation_job에 CookieCloud 분기 추가
- **Polish (Phase 5)**: Depends on US1 + US2 completion

### User Story Dependencies

```
Phase 1: Setup (config, dependency)
    └──→ US3 (깨진 코드 제거) ──→ US1 (사전 알림) ──→ US2 (CookieCloud) ──→ Polish
```

- **US3** (P1): Setup 완료 후 즉시 시작 — 모든 스토리의 전제 조건
- **US1** (P1): US3 완료 후 시작 — cookie_validation_job 새 흐름 구현
- **US2** (P2): US1 완료 후 시작 — cookie_validation_job에 CookieCloud 분기 추가

### Within Each User Story

- cookie_manager.py 메서드 먼저 → main.py 통합 후 → 검증
- 같은 파일 수정이므로 병렬화 제한적 (순차 실행 권장)

---

## Implementation Strategy

### MVP First (US3 + US1 Only)

1. Complete Phase 1: pycryptodome 설치 + config 변수 추가
2. Complete Phase 2: US3 — refresh_cookies_via_openclaw() 제거
3. Complete Phase 3: US1 — 쿠키 나이 추적 + 사전 알림
4. **STOP and VALIDATE**: 봇 재시작 → 쿠키 만료 임박 경고 동작 확인
5. CookieCloud 없이도 즉시 운영 가치 제공

### Full Feature Delivery

1. MVP 완료 (US3 + US1)
2. + US2 (CookieCloud) → CookieCloud 서버 설정 후 자동 갱신 검증
3. Polish → 전체 검증 → systemd 재시작 → 완료

---

## Notes

- 이 feature는 **기존 3개 파일 수정만** 수행 (신규 파일 생성 없음)
- 수정 파일이 겹치므로 (cookie_manager.py, main.py) 태스크 간 병렬화가 제한적
- pycryptodome은 US2에서만 사용되지만, Setup에서 미리 설치하여 import 오류 방지
- CookieCloud 미설정 상태에서도 US1 (사전 알림)은 완전 독립 동작해야 함
- 봇 재시작 시 `last_cookie_warning_at` 리셋됨 — 경고가 1회 더 전송될 수 있으나 무해
