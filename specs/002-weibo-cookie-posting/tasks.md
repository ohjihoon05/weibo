# Tasks: Weibo Cookie 기반 포스팅 전환

**Input**: Design documents from `/specs/002-weibo-cookie-posting/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/weibo-mobile-api.md

**Tests**: Not explicitly requested. Test tasks omitted.

**Organization**: Tasks are grouped by user story (US1=P1, US2=P2, US3=P3).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to

---

## Phase 1: Setup (Cleanup & Preparation)

**Purpose**: 기존 OAuth 기반 코드 제거, 프로젝트 정리

- [x] T001 Delete OAuth module: remove src/auth/weibo_oauth.py (공식 API 폐쇄로 불필요)
- [x] T002 Update src/config.py: remove WEIBO_APP_KEY, WEIBO_APP_SECRET, WEIBO_ACCESS_TOKEN, WEIBO_REDIRECT_URI from required vars. Keep only TELEGRAM_BOT_TOKEN and CLAUDE_API_KEY

**Checkpoint**: OAuth 관련 코드 제거 완료. 기존 봇은 Weibo 포스팅 없이 번역/미리보기까지 동작.

---

## Phase 2: Foundational (Core Cookie Infrastructure)

**Purpose**: 쿠키 관리 모듈 — 모든 user story의 전제 조건

**⚠️ CRITICAL**: US1/US2/US3 모두 이 모듈에 의존

- [x] T003 Create src/services/cookie_manager.py: CookieManager class with `__init__(cookie_file_path)`, `load_cookies() -> dict | None`, `save_cookies(cookies: dict, uid: str)`, `parse_cookie_string(raw: str) -> dict` (SUB, SUBP, XSRF-TOKEN 추출), `validate_cookies() -> tuple[bool, str | None]` (/api/config 호출하여 login 상태 확인, st 토큰 반환), `get_cookie_header() -> str` (Cookie 헤더 문자열 생성), `get_status() -> dict` (status, uid, updated_at 반환). 파일 저장 시 권한 600 설정. 쿠키 값 로그 출력 시 mask_sensitive() 적용
- [x] T004 [P] Update src/storage/json_store.py: add `save_cookie_data(data: dict, path: str)` and `load_cookie_data(path: str) -> dict | None` functions. save 시 os.chmod(path, 0o600) 적용

**Checkpoint**: CookieManager가 쿠키 파싱, 저장, 로드, 검증을 독립적으로 수행 가능.

---

## Phase 3: User Story 1 - m.weibo.cn API로 Weibo 포스팅 (Priority: P1) 🎯 MVP

**Goal**: 기존 WeiboClient를 m.weibo.cn 쿠키 기반으로 교체하여 실제 포스팅이 동작하도록 한다

**Independent Test**: 유효한 쿠키를 수동으로 data/weibo_cookies.json에 설정 → Telegram에서 매물 전송 → Weibo에 게시물 확인

### Implementation for User Story 1

- [x] T005 [US1] Rewrite src/services/weibo_client.py: WeiboClient class with `__init__(cookie_manager: CookieManager)`. Internal method `_get_st_token() -> str` calls GET /api/config, checks data.login==true, returns data.st (raise CookieExpiredError if login==false). Method `_build_headers(st: str) -> dict` returns headers dict with Cookie, X-XSRF-TOKEN, X-Requested-With, Referer, User-Agent per contracts/weibo-mobile-api.md. Keep WeiboAPIError exception class. Keep _retry_request() logic (3 retries, 2/4/8s backoff). Add CookieExpiredError subclass of WeiboAPIError for cookie expiry
- [x] T006 [US1] Implement upload_image() in src/services/weibo_client.py: POST /api/statuses/uploadPic with multipart/form-data (pic=image_bytes, st=st_token). Extract pic_id from response. Add 1s delay between uploads (time.sleep). Handle ok=0 error responses
- [x] T007 [US1] Implement create_post() and create_text_post() in src/services/weibo_client.py: POST /api/statuses/update with application/x-www-form-urlencoded (content=text, st=st_token, picIds=comma-separated pic_ids). Extract bid from response data. Return URL as https://m.weibo.cn/detail/{bid}. create_text_post delegates to create_post with empty pic_ids
- [x] T008 [US1] Add hashtag format conversion in src/services/weibo_client.py: before posting, convert hashtag format from `#tag` to `#tag#` in content text. Use regex to find `#(\S+)` patterns that are NOT already `#tag#` and convert. This keeps hashtag_generator.py unchanged
- [x] T009 [US1] Add duplicate content detection in src/services/weibo_client.py: store last posted content text in memory (class attribute). Before posting, compare new content with last. If identical, append timestamp suffix ` (YYYY-MM-DD HH:MM)` to content. Return a `duplicate_detected: bool` flag so caller can warn user
- [x] T010 [US1] Update src/main.py: replace `from src.config import WEIBO_ACCESS_TOKEN` with cookie_manager import. Initialize CookieManager(cookie_file_path="data/weibo_cookies.json"). Initialize WeiboClient(cookie_manager) instead of WeiboClient(WEIBO_ACCESS_TOKEN). Update pipeline_callback and approve_callback to handle CookieExpiredError: send "쿠키가 만료되었습니다. /cookie 명령어로 갱신해주세요." message. Remove WEIBO_ACCESS_TOKEN from startup log
- [x] T011 [US1] Update pipeline_callback in src/main.py: in auto mode, when duplicate_detected is True from weibo_client, log warning. In preview_pipeline_callback, when duplicate_detected, add "⚠️ 직전 게시물과 동일한 내용입니다." to preview message

**Checkpoint**: 유효한 쿠키가 있으면 Telegram → 번역 → Weibo 포스팅 → URL 반환까지 전체 파이프라인 동작.

---

## Phase 4: User Story 2 - 쿠키 설정 및 유효성 검증 (Priority: P2)

**Goal**: Telegram /cookie 명령어로 쿠키 설정, /status 명령어로 유효성 확인

**Independent Test**: Telegram에서 /cookie SUB=...; SUBP=...; XSRF-TOKEN=... 전송 → 유효성 검증 응답 → /status로 상태 확인

### Implementation for User Story 2

- [x] T012 [US2] Add /cookie command handler in src/services/telegram_handler.py: new async function `cookie_command(update, context)`. Extract cookie string from message text after "/cookie ". Call cookie_manager.parse_cookie_string(raw) to extract fields. Validate required fields (SUB, SUBP, XSRF-TOKEN) present. Call cookie_manager.save_cookies(). Call cookie_manager.validate_cookies() to verify against /api/config. Reply with success (uid, status) or error message. Register as CommandHandler("cookie", cookie_command) in get_handlers()
- [x] T013 [US2] Add /status command handler in src/services/telegram_handler.py: new async function `status_command(update, context)`. Call cookie_manager.get_status(). If no cookies: reply "⚠️ Weibo 쿠키가 설정되지 않았습니다. /cookie <쿠키문자열> 명령어로 설정해주세요." If cookies exist: call cookie_manager.validate_cookies(). Reply with formatted status: cookie status emoji (✅/❌), uid, last updated time. Register as CommandHandler("status", status_command) in get_handlers()
- [x] T014 [US2] Wire cookie_manager into telegram_handler.py: telegram_handler needs access to cookie_manager instance. Update main.py to pass cookie_manager via app.bot_data["cookie_manager"]. In /cookie and /status handlers, retrieve cookie_manager from context.bot_data["cookie_manager"]

**Checkpoint**: /cookie로 쿠키 설정 → /status로 확인 → 포스팅 가능 상태.

---

## Phase 5: User Story 3 - OpenClaw 자동 쿠키 갱신 (Priority: P3)

**Goal**: OpenClaw 브라우저 자동화로 쿠키 자동 취득/갱신

**Independent Test**: 쿠키 만료 임박 시 OpenClaw가 자동으로 갱신하고 새 쿠키가 저장되는지 확인

### Implementation for User Story 3

- [x] T015 [US3] Add OpenClaw integration method to src/services/cookie_manager.py: new method `refresh_cookies_via_openclaw() -> bool`. Send HTTP POST to OpenClaw API (localhost:18789) requesting Weibo login + cookie extraction skill. Parse response for new cookies. Save new cookies via save_cookies(). Return True on success, False on failure. Handle connection errors (OpenClaw not running) gracefully
- [x] T016 [US3] Add periodic cookie validation job in src/main.py: use python-telegram-bot's job_queue to schedule periodic cookie check (every 6 hours). Job calls cookie_manager.validate_cookies(). If login=false or approaching expiry (check updated_at > 24h ago), attempt cookie_manager.refresh_cookies_via_openclaw(). On refresh failure, send Telegram notification to user with manual refresh instructions
- [x] T017 [US3] Add auto-refresh fallback notification in src/main.py: when OpenClaw refresh fails (connection error, CAPTCHA, MFA required), send Telegram message: "⚠️ 자동 쿠키 갱신에 실패했습니다. 브라우저에서 m.weibo.cn에 로그인한 후 /cookie 명령어로 쿠키를 설정해주세요."

**Checkpoint**: 쿠키 자동 갱신 동작. 실패 시 수동 갱신 안내.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: 보안, 로깅, Docker 업데이트

- [x] T018 [P] Verify log masking in src/services/cookie_manager.py and src/services/weibo_client.py: ensure all cookie values (SUB, SUBP, XSRF-TOKEN) are masked via mask_sensitive() before any logger call. Audit all logger.info/warning/error calls that might contain cookie data
- [x] T019 [P] Update .env.example (if exists) or create: remove WEIBO_APP_KEY, WEIBO_APP_SECRET, WEIBO_ACCESS_TOKEN, WEIBO_REDIRECT_URI entries. Add comment explaining cookie-based auth (no env var needed, use /cookie command) — N/A: no .env.example exists
- [x] T020 [P] Update Dockerfile if needed: ensure data/ directory creation includes weibo_cookies.json parent. Verify ENTRYPOINT still works with updated config.py (fewer required env vars) — N/A: no Dockerfile exists
- [x] T021 Run syntax check on all modified files: python -m py_compile for src/config.py, src/main.py, src/services/weibo_client.py, src/services/cookie_manager.py, src/services/telegram_handler.py, src/storage/json_store.py. Verify no import errors with python -c "from src.main import main"

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 (config.py cleanup)
- **Phase 3 (US1)**: Depends on Phase 2 (cookie_manager required)
- **Phase 4 (US2)**: Depends on Phase 2 (cookie_manager required). Can run parallel with US1
- **Phase 5 (US3)**: Depends on Phase 2 (cookie_manager required). Can run parallel with US1/US2
- **Phase 6 (Polish)**: Depends on all user story phases

### User Story Dependencies

- **US1 (P1)**: Depends on Phase 2. Core posting pipeline — MVP
- **US2 (P2)**: Depends on Phase 2. Independent of US1 (but both use cookie_manager)
- **US3 (P3)**: Depends on Phase 2. Independent of US1/US2 (adds auto-refresh on top)

### Within Each User Story

- T005 → T006 → T007 (WeiboClient core → upload → post)
- T008, T009 after T007 (enhancements to posting)
- T010 → T011 (main.py wiring → duplicate detection in callbacks)
- T012, T013 parallel (independent /cookie and /status handlers)
- T014 after T012, T013 (wiring requires handlers to exist)

### Parallel Opportunities

**Wave 1** (Phase 1+2):
```
T001 + T002 (parallel — different files)
then T003 + T004 (parallel — different files)
```

**Wave 2** (US1 + US2 + US3 in parallel after Phase 2):
```
US1: T005 → T006 → T007 → T008, T009 (parallel) → T010 → T011
US2: T012, T013 (parallel) → T014
US3: T015 → T016 → T017
```

**Wave 3** (Polish):
```
T018 + T019 + T020 (all parallel) → T021
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1: Setup (T001-T002)
2. Phase 2: Foundational (T003-T004)
3. Phase 3: US1 (T005-T011)
4. **STOP and VALIDATE**: 수동으로 쿠키를 data/weibo_cookies.json에 설정 후 포스팅 테스트
5. 동작 확인 후 US2 (Telegram 명령어) 진행

### Incremental Delivery

1. Setup + Foundational → 쿠키 인프라 준비
2. US1 → 포스팅 동작 확인 (MVP!)
3. US2 → /cookie, /status 명령어로 운영 편의성 확보
4. US3 → OpenClaw 자동 갱신으로 완전 자동화
5. Polish → 보안/로깅 감사, Docker 업데이트

---

## Notes

- 기존 WeiboClient의 공개 인터페이스 (upload_image, create_post, create_text_post) 유지하여 main.py 변경 최소화
- 새 의존성 없음 — requests로 m.weibo.cn API 호출
- hashtag_generator.py 자체는 변경 불필요 — weibo_client에서 포스팅 시 #tag → #tag# 변환
- 쿠키 파일은 data/weibo_cookies.json (runtime generated, .gitignore에 data/ 이미 포함)
