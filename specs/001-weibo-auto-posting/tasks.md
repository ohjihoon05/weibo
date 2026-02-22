# Tasks: Weibo 부동산 자동 포스팅 시스템

**Input**: Design documents from `/specs/001-weibo-auto-posting/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: 테스트는 spec에서 명시적으로 요청하지 않았으므로 포함하지 않음.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup

**Purpose**: Project initialization and basic structure

- [x] T001 Create project directory structure per plan.md (`src/`, `src/models/`, `src/services/`, `src/storage/`, `src/auth/`, `data/posts/`, `data/history/`, `data/images/`, `tests/unit/`, `tests/integration/`)
- [x] T002 Initialize Python project with `requirements.txt` containing: `python-telegram-bot[job-queue]`, `requests`, `Pillow`, `anthropic`, `python-dotenv`
- [x] T003 [P] Create `.env.example` with all required environment variables (`TELEGRAM_BOT_TOKEN`, `WEIBO_APP_KEY`, `WEIBO_APP_SECRET`, `WEIBO_ACCESS_TOKEN`, `WEIBO_REDIRECT_URI`, `CLAUDE_API_KEY`)
- [x] T004 [P] Create `.gitignore` with: `.env`, `data/`, `venv/`, `__pycache__/`, `*.pyc`
- [x] T005 [P] Create `src/__init__.py`, `src/models/__init__.py`, `src/services/__init__.py`, `src/storage/__init__.py`, `src/auth/__init__.py` package init files

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T006 Implement config module loading environment variables via `python-dotenv` in `src/config.py` — expose `TELEGRAM_BOT_TOKEN`, `WEIBO_APP_KEY`, `WEIBO_APP_SECRET`, `WEIBO_ACCESS_TOKEN`, `WEIBO_REDIRECT_URI`, `CLAUDE_API_KEY` as validated settings; include `mask_sensitive(value: str) -> str` utility function for log masking (Constitution principle II)
- [x] T007 Implement PropertyListing dataclass in `src/models/property_listing.py` — 23 fields per data-model.md, include `from_dict()`/`to_dict()` serialization, area_sqm↔area_tsubo conversion method
- [x] T008 [P] Implement Post dataclass with Status and Mode enums in `src/models/post.py` — include state transition validation per data-model.md state diagram, PostHistory dataclass with Action enum
- [x] T009 [P] Implement JSON file-based storage in `src/storage/json_store.py` — `save_post()` to `data/posts/YYYY-MM-DD_{id}.json`, `append_history()` to `data/history/YYYY-MM.jsonl`, `load_post()`, `save_exchange_rate()`/`load_exchange_rate()` to `data/exchange_rate.json`

**Checkpoint**: Foundation ready — user story implementation can now begin

---

## Phase 3: User Story 1 — Telegram으로 매물 입력 및 Weibo 포스팅 (Priority: P1) MVP

**Goal**: 사용자가 Telegram에 사진+텍스트를 보내면 AI 번역 후 Weibo에 포스팅되는 end-to-end 파이프라인

**Independent Test**: Telegram에 매물 사진 1장 + 일본어 텍스트를 보내고, Weibo에 중국어 포맷팅 게시물이 올라가는지 확인

### Implementation for User Story 1

- [x] T010 [US1] Implement image processor in `src/services/image_processor.py` — Pillow 기반, `process_image(input_path) -> bytes` (EXIF transpose, RGB convert, thumbnail 1080px, JPEG quality 85→50 adaptive, target <4MB)
- [x] T011 [US1] Implement Weibo OAuth token utility in `src/auth/weibo_oauth.py` — OAuth2 authorization code flow: generate auth URL, exchange code for access_token, save to `.env`
- [x] T012 [US1] Implement Weibo API client in `src/services/weibo_client.py` — `upload_image(image_bytes) -> pic_id` via `upload.api.weibo.com/2/statuses/upload.json`, `create_post(text, pic_ids) -> weibo_url` via `/2/statuses/upload_url_text.json`, `create_text_post(text) -> weibo_url` via `/2/statuses/update.json`; include access_token management
- [x] T013 [US1] Implement translator service in `src/services/translator.py` — Claude API call with system prompt for: language auto-detection (ja/zh/ko), 简体中文 translation with real estate terminology, structured extraction into PropertyListing fields (16 items), formatted Chinese text output with emoji template per REQUIREMENTS.md section 4
- [x] T014 [US1] Implement Telegram handler in `src/services/telegram_handler.py` — register photo+text MessageHandler, MediaGroup collection with `media_group_id` + 2s `job_queue.run_once()` timeout, single photo handler, text-only handler, download photos via `bot.get_file()` to `data/images/`
- [x] T015 [US1] Implement main pipeline orchestration in `src/main.py` — initialize Bot with `ApplicationBuilder`, register handlers from telegram_handler, wire pipeline: receive message → download images → process images → translate text → create Post → upload to Weibo → send result link via Telegram; `auto` mode flow (no preview), long-polling `application.run_polling()`
- [x] T016 [US1] Handle edge case: text-only input (no photos) in `src/services/telegram_handler.py` — detect text-only message, skip image processing, use `create_text_post()` in weibo_client
- [x] T017 [US1] Handle edge case: photo count exceeding 9 in `src/services/telegram_handler.py` — truncate to first 9 photos, send warning message to user per telegram-bot-commands contract
- [x] T017a [US1] Handle edge case: missing required fields in `src/services/translator.py` — after AI extraction, detect missing PropertyListing fields (price, location 등), populate available fields only, flag missing fields in Post metadata for preview notification (spec.md edge case: "누락 항목은 빈칸 처리 후 미리보기에서 사용자에게 보완을 요청")

**Checkpoint**: User Story 1 완료 — Telegram → AI 번역 → Weibo 포스팅 end-to-end 동작 확인 가능

---

## Phase 4: User Story 2 — 미리보기 및 승인 후 포스팅 (Priority: P2)

**Goal**: 기본 미리보기 모드에서 번역 결과 확인 후 승인/수정 요청 가능

**Independent Test**: Telegram에 매물 전송 → 미리보기 수신 → "포스팅" 버튼 클릭 → Weibo 게시 확인

### Implementation for User Story 2

- [x] T018 [US2] Add preview mode state management in `src/services/telegram_handler.py` — `/preview` and `/auto` command handlers, per-chat in-memory mode storage via Python dict (default: preview, 봇 재시작 시 preview로 리셋), `/status` command to show current mode
- [x] T019 [US2] Implement preview message with inline keyboard in `src/services/telegram_handler.py` — format translated PropertyListing as preview message, attach InlineKeyboardMarkup with "포스팅" (`approve_{post_id}`) and "수정 요청" (`reject_{post_id}`) buttons, store pending Post with `pending_approval` status
- [x] T020 [US2] Implement callback query handler in `src/services/telegram_handler.py` — register CallbackQueryHandler, handle `approve_{post_id}`: change Post status to `approved` → trigger Weibo posting → send result, handle `reject_{post_id}`: prompt user for edits → reset Post to `pending_translation`
- [x] T021 [US2] Update main pipeline in `src/main.py` — branch flow based on mode: `preview` → send preview + wait for callback, `auto` → post immediately (existing flow); register `/start`, `/preview`, `/auto`, `/status` command handlers

**Checkpoint**: User Story 2 완료 — 미리보기/승인 플로우가 기본 모드로 동작

---

## Phase 5: User Story 3 — 해시태그 자동 생성 및 환율 환산 (Priority: P3)

**Goal**: 게시물에 관련 해시태그 자동 추가, JPY→CNY 실시간 환율 환산 표시

**Independent Test**: 매물 포스팅에 해시태그가 포함되고, 가격에 엔화+위안화가 함께 표시되는지 확인

### Implementation for User Story 3

- [x] T022 [P] [US3] Implement exchange rate service in `src/services/exchange_rate.py` — `get_jpy_to_cny_rate() -> float` with fallback chain: ExchangeRate-API (`open.er-api.com/v6/latest/JPY`) → Frankfurter (`api.frankfurter.dev/v1/latest?base=JPY&symbols=CNY`) → local cache → hardcoded fallback; cache via `json_store.save_exchange_rate()` with timestamp; stale threshold logic (48h/7d)
- [x] T023 [P] [US3] Implement hashtag generator in `src/services/hashtag_generator.py` — `generate_hashtags(listing: PropertyListing) -> list[str]`; base hashtags: #日本房产 #日本不动产 #海外投资; location-based: map prefecture to Chinese hashtag (e.g., 東京 → #东京房产); type-based: layout/structure → #公寓 #一户建 etc.; investment-based: if yield present → #投资回报
- [x] T024 [US3] Integrate exchange rate into translator in `src/services/translator.py` — before translation, fetch JPY→CNY rate, pass to AI prompt so price fields include both ¥ and 人民币, populate `price_cny`, `exchange_rate`, `exchange_rate_date` in PropertyListing
- [x] T025 [US3] Integrate hashtags into posting flow in `src/main.py` — after translation, call `generate_hashtags()`, append to `formatted_text`, store in Post.hashtags field

**Checkpoint**: User Story 3 완료 — 게시물에 해시태그 + 환율 환산 포함

---

## Phase 6: User Story 4 — 에러 처리 및 재시도 (Priority: P4)

**Goal**: 포스팅 실패 시 3회 재시도, 최종 실패 시 Telegram 에러 알림, 이력 로컬 저장

**Independent Test**: Weibo API 오류 시뮬레이션 → 재시도 → 최종 실패 시 Telegram 알림 + 이력 저장 확인

### Implementation for User Story 4

- [x] T026 [US4] Add retry logic to Weibo client in `src/services/weibo_client.py` — wrap `upload_image()` and `create_post()` with retry decorator/loop (max 3 attempts), exponential backoff (2s, 4s, 8s), log each attempt via PostHistory, handle retryable errors (10001, 10002) vs non-retryable (20019, 21327, 21332)
- [x] T027 [US4] Implement error notification in `src/services/telegram_handler.py` — `send_error_notification(chat_id, error_message)`: format per contract error messages, distinct messages for retry-in-progress ("포스팅 재시도 중... ({n}/3)") vs final failure ("Weibo 포스팅에 실패했습니다. 에러: {msg}"), translation failure, exchange rate warning
- [x] T028 [US4] Integrate PostHistory logging in `src/main.py` — log every pipeline step (translate, upload_image, create_post) to PostHistory via `json_store.append_history()`, record success/failure, error_message, error_code, weibo_response for each attempt
- [x] T029 [US4] Add token expiry handling in `src/services/weibo_client.py` — detect error codes 21327 (expired) and 21332 (revoked), send specific Telegram notification to user requesting re-authentication

**Checkpoint**: User Story 4 완료 — 모든 실패 시나리오에서 재시도 + 알림 + 이력 저장 동작

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: 전체 시스템 통합 검증 및 운영 준비

- [x] T030 [P] Create `README.md` with setup instructions — Weibo 개발자 등록, Telegram Bot 생성, OAuth 토큰 발급 절차 안내 (`.env.example`은 T003에서 이미 생성, README에서 참조만)
- [x] T031 [P] Add logging throughout pipeline in `src/main.py` — Python `logging` module, file handler to `data/logs/`, use `config.mask_sensitive()` (from T006) to mask tokens/API keys in log output per Constitution principle II
- [x] T032 Validate quickstart.md checklist — run through all validation items in `specs/001-weibo-auto-posting/quickstart.md`, verify each step works on Raspberry Pi

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 completion — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2 — core pipeline
- **US2 (Phase 4)**: Depends on Phase 3 (extends telegram_handler and main.py from US1)
- **US3 (Phase 5)**: Depends on Phase 3 (integrates into translator and main.py from US1)
- **US4 (Phase 6)**: Depends on Phase 3 (wraps weibo_client from US1)
- **Polish (Phase 7)**: Depends on all user stories

### User Story Dependencies

- **US1 (P1)**: Foundation (Phase 2) → MUST complete first, this is the MVP
- **US2 (P2)**: US1 required (extends handler/main flows from US1)
- **US3 (P3)**: US1 required (integrates into translation/posting pipeline)
- **US4 (P4)**: US1 required (wraps Weibo client with retry logic)
- **US2, US3, US4**: Can proceed in parallel after US1 is complete

### Within Each User Story

- Models before services
- Services before pipeline integration
- Core implementation before edge cases
- Story complete before moving to next priority

### Parallel Opportunities

- T003, T004, T005 (Phase 1 setup files) can run in parallel
- T008, T009 (Phase 2 models/storage) can run in parallel
- T022, T023 (Phase 5 exchange rate + hashtag services) can run in parallel
- T030, T031 (Phase 7 docs + logging) can run in parallel
- After US1 completes: US2, US3, US4 can start in parallel

---

## Parallel Example: Phase 1 Setup

```bash
# Launch all parallel setup tasks together:
Task: "Create .env.example in project root"
Task: "Create .gitignore in project root"
Task: "Create __init__.py package files"
```

## Parallel Example: After US1 Complete

```bash
# These three user stories can proceed in parallel:
Task: "US2 - Add preview mode and approval buttons"
Task: "US3 - Implement exchange rate and hashtag services"
Task: "US4 - Add retry logic and error notifications"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (config, models, storage)
3. Complete Phase 3: User Story 1 (end-to-end pipeline)
4. **STOP and VALIDATE**: Telegram → AI 번역 → Weibo 포스팅 동작 확인
5. Deploy on Raspberry Pi and test with real Weibo posting

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. US1 → Test end-to-end → **MVP deployed!**
3. US2 → Add preview/approval safety → More reliable posting
4. US3 → Add hashtags + exchange rate → Enhanced post quality
5. US4 → Add retry + error handling → Production-ready stability
6. Polish → Logging, docs → Operations-ready

### Key Notes

- US1 is the only story needed for a working MVP
- US2 should follow US1 closely (safety for real estate postings)
- US3 and US4 are independent enhancements after US1
- Total: 33 tasks across 7 phases
