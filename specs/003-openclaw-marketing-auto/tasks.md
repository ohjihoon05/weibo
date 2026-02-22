# Tasks: OpenClaw 기반 Weibo 마케팅 자동화 관리 시스템

**Input**: Design documents from `/specs/003-openclaw-marketing-auto/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/openclaw-skills.md

**Tests**: 테스트는 스펙에서 명시적으로 요청되지 않았으므로 생략. 각 Phase checkpoint에서 수동 검증.

**Organization**: 태스크는 user story 단위로 그룹화하여 독립적 구현/테스트 가능.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 병렬 실행 가능 (다른 파일, 의존성 없음)
- **[Story]**: 해당 user story (US1~US6)
- 정확한 파일 경로 포함

## Path Conventions

- **단일 프로젝트**: `src/`, `tests/` at repository root
- 기존 002 코드베이스 위에 확장

---

## Phase 1: Setup

**Purpose**: 신규 모듈을 위한 디렉토리 구조 생성 및 의존성 추가

- [x] T001 requirements.txt에 flask 의존성 추가
- [x] T002 [P] 신규 data 디렉토리 생성: data/metrics/, data/competitors/, data/reports/, data/expert_content/
- [x] T003 [P] src/api/ 디렉토리 및 src/api/__init__.py 생성
- [x] T004 [P] src/config.py에 신규 설정 추가: PUBLISH_TIMES (발행 시간대), BENCHMARK_DAY (벤치마킹 요일), REPORT_DAY (리포트 요일), EXPERT_TOPICS (전문가 주제 목록)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 모든 user story가 의존하는 핵심 인프라 - 발행 대기열과 스토리지 확장

**CRITICAL**: 이 Phase가 완료되어야 user story 구현 시작 가능

- [x] T005 src/models/queue_item.py에 QueueItem dataclass 생성 (id, type, text, image_paths, scheduled_at, status, queued_at, started_at, completed_at, error, post_id, telegram_chat_id)
- [x] T006 src/storage/publish_queue.py에 JsonPublishQueue 클래스 구현 (fcntl 잠금 + atomic write: enqueue, dequeue, complete, fail, get_pending_count, cleanup, recover_stale_processing)
- [x] T007 src/storage/json_store.py에 신규 저장 함수 추가: append_metrics(), load_metrics(), save_competitors(), load_competitors(), append_competitor_posts(), save_report()
- [x] T008 [P] 대기열 발행 전 쿠키 유효성 검사 로직 설계: src/services/scheduler.py에서 발행 직전 쿠키 만료 감지 → cookie_manager.refresh() 자동 호출 → 성공 시 발행 계속, 실패 시 대기열 일시 중단 + Telegram 알림 ("쿠키 갱신 실패, 수동 갱신 필요") (FR-009 커버)

**Checkpoint**: 대기열 인프라 완성 - user story 구현 시작 가능

---

## Phase 3: User Story 1 - OpenClaw 통한 콘텐츠 발행 관리 (Priority: P1) MVP

**Goal**: 여러 건의 콘텐츠를 대기열에 저장하고 최적 시간대(중국 시간 09:00, 20:00)에 순차 발행

**Independent Test**: 3-4건의 콘텐츠를 Telegram으로 한꺼번에 전송 → 설정된 시간에 순차 발행되는지 확인

### Implementation for User Story 1

- [x] T009 [US1] src/services/scheduler.py 생성: 초기 고정 시간대 설정 (중국 시간 09:00, 20:00), 다음 발행 시간 계산 함수, 대기열에서 항목 꺼내 기존 파이프라인 실행하는 process_queue() 함수. T008의 쿠키 유효성 검사 로직을 발행 직전에 통합
- [x] T010 [US1] src/services/telegram_handler.py 수정: 신규 /queue 명령어 추가 (대기열 모드 토글), handle_photo/handle_text에서 queue 모드일 때 즉시 발행 대신 대기열 등록, /qstatus 명령어로 대기열 현황 조회
- [x] T011 [US1] src/main.py 수정: scheduler 주기적 job 등록 (30분 간격으로 대기열 확인 및 발행 시간 체크), 봇 시작 시 recover_stale_processing() 호출
- [x] T012 [US1] src/services/telegram_handler.py에 대기열 관리 인라인 키보드 추가: "지금 발행", "일정 변경", "삭제" 버튼과 콜백 핸들러

**Checkpoint**: 대기열 기반 예약 발행 동작 확인 - MVP 완성

---

## Phase 4: User Story 2 - 경쟁 계정 벤치마킹 (Priority: P1)

**Goal**: 경쟁 계정 등록/자동 검색, 포스트 수집, 주간 벤치마킹 리포트 생성

**Independent Test**: 경쟁 계정 3-5개 등록 후 분석 리포트가 Telegram으로 수신되는지 확인

### Implementation for User Story 2

- [x] T013 [P] [US2] src/models/competitor.py 생성: CompetitorAccount dataclass (uid, nickname, source, active, added_at, last_scraped_at, note) 및 CompetitorPost dataclass (id, competitor_uid, text, image_count, hashtags, reposts_count, comments_count, attitudes_count, created_at, scraped_at)
- [x] T014 [US2] src/services/weibo_scraper.py 생성: get_user_posts(uid, page) - m.weibo.cn /api/container/getIndex 호출, search_users(keyword, page) - containerid=100103type=3 검색, get_post_detail(mid) - /statuses/show 호출. 요청 간 3-5초 딜레이 적용. 에러 핸들링: HTTP 에러/타임아웃 시 최대 3회 재시도 (exponential backoff), 계정 비공개/삭제 감지 시 자동 비활성화 + Telegram 알림, 모든 스크래핑 결과를 data/logs/에 기록
- [x] T015 [US2] src/services/benchmark_analyzer.py 생성: 경쟁 계정 포스트 수집 → 인기 포스트 TOP 10, 해시태그 빈도 분석, 발행 시간대 패턴, 인게이지먼트 평균 계산 → 주간 벤치마킹 리포트 dict 생성 → Telegram 메시지 포맷팅
- [x] T016 [US2] src/services/telegram_handler.py에 경쟁 계정 명령어 추가: /competitor add {uid}, /competitor list, /competitor remove {uid}, /competitor search {keyword}, /benchmark (리포트 요청)
- [x] T017 [US2] src/main.py에 주간 벤치마킹 job 등록 (매주 일요일 저녁, 경쟁 계정 포스트 수집 + 리포트 생성 + Telegram 전달)

**Checkpoint**: 경쟁 계정 벤치마킹 리포트 자동 생성 확인

---

## Phase 5: User Story 3 - 전문가 콘텐츠 자동 생성 (Priority: P1)

**Goal**: 매물 없는 날에 오사카/간사이 일본 부동산 전문가 콘텐츠 자동 생성 및 발행

**Independent Test**: 매물을 올리지 않고 하루 대기 → 전문가 콘텐츠가 자동 생성되어 대기열에 등록되는지 확인

### Implementation for User Story 3

- [x] T018 [P] [US3] src/models/expert_content.py 생성: ExpertContent dataclass (id, topic, text_zh, hashtags, status, generated_at, queue_item_id). 주제 enum: MARKET_TREND, INVESTMENT_TIP, AREA_GUIDE, TAX_VISA, PURCHASE_PROCESS
- [x] T019 [US3] src/services/expert_generator.py 생성: Claude API 호출로 전문가 콘텐츠 생성. 시스템 프롬프트에 (1) 오사카/간사이 지역 중심, (2) 简体中文 출력, (3) 특정 매물 가격/주소/사진 정보 절대 포함 금지 (FR-013), (4) 200자 이내 Weibo 포맷 명시. 주제 로테이션 (최근 사용하지 않은 주제 우선). 에러 핸들링: Claude API 호출 실패 시 최대 2회 재시도, 연속 실패 시 당일 전문가 콘텐츠 건너뛰고 Telegram 알림, 생성된 콘텐츠에 금칙어(가격, 주소 등) 포함 여부 사후 검증 → 포함 시 폐기 + 재생성
- [x] T020 [US3] src/services/scheduler.py 수정: process_queue()에서 대기열 비어있고 당일 발행 목표 미달 시 expert_generator 호출 → 생성된 콘텐츠를 대기열에 자동 등록. preview 모드일 때는 운영자 확인 요청 (Constitution III 준수)
- [x] T021 [US3] src/services/hashtag_generator.py 수정: 전문가 콘텐츠용 해시태그 세트 추가 (#大阪房产 #关西投资 #日本房产知识 #海外置业 등 오사카/간사이 특화)

**Checkpoint**: 매물 없는 날 전문가 콘텐츠 자동 발행 확인 - P1 전체 완성

---

## Phase 6: User Story 4 - 발행 시간 최적화 (Priority: P2)

**Goal**: 벤치마킹 데이터와 자체 성과 기반으로 최적 발행 시간 동적 계산

**Independent Test**: 2주 이상 발행 데이터 축적 후 "최적 시간 분석" 요청 시 시간대별 분석 결과 수신 확인

**Dependencies**: US2 (벤치마킹 데이터), US5 (성과 데이터) 축적 후 효과 극대화. 단, 초기에는 고정 시간으로 동작하므로 독립 구현 가능.

### Implementation for User Story 4

- [x] T022 [US4] src/services/scheduler.py 수정: calculate_optimal_times() 함수 추가 - 경쟁 계정 발행 시간대 패턴 (data/competitors/), 자체 포스트 성과 데이터 (data/metrics/) 분석하여 최적 2개 시간 슬롯 계산. 데이터 부족 시 기본값 (09:00, 20:00 CST) 유지
- [x] T023 [US4] src/services/telegram_handler.py에 /besttime 명령어 추가: 시간대별 평균 인게이지먼트 분석 결과를 텍스트 + 간단한 막대 차트로 Telegram 전달

**Checkpoint**: 데이터 기반 동적 시간 배정 동작 확인

---

## Phase 7: User Story 5 - 성과 추적 및 리포팅 (Priority: P2)

**Goal**: 발행 포스트 성과 자동 수집, 주간 리포트 Telegram 전달

**Independent Test**: 10건 이상 포스트 발행 후 주간 리포트 자동 수신 확인

### Implementation for User Story 5

- [x] T024 [US5] src/services/metrics_collector.py 생성: collect_post_metrics(bid) - m.weibo.cn /statuses/show?id={bid} 호출하여 reposts_count, comments_count, attitudes_count 수집. collect_recent_posts() - data/posts/ 최근 20건의 bid 추출 후 순차 수집 (3초 딜레이). 결과를 data/metrics/YYYY-MM.jsonl에 저장. 에러 핸들링: API 호출 실패 시 최대 3회 재시도, 수집 실패한 포스트는 다음 주기에 재수집 대상으로 마킹, 쿠키 만료 감지 시 수집 중단 + Telegram 알림
- [x] T025 [US5] src/services/benchmark_analyzer.py 수정: generate_weekly_report() 함수 추가 - 주간 발행 건수, 포스트별 성과 순위, 매물 유형별(지역, 가격대, 구조) 반응 분석, 전주 대비 성장률 계산 → Telegram 메시지 포맷팅
- [x] T026 [US5] src/main.py에 성과 수집 job 등록: 발행 후 2시간, 24시간, 7일 시점에 해당 포스트의 성과를 수집하는 스케줄 (data-model.md 기준). 주간 리포트 job (매주 월요일 09:00 CST) 등록. 구현: 포스트 발행 성공 시 3개의 one-shot job을 APScheduler에 등록
- [x] T027 [US5] src/services/telegram_handler.py에 /report 명령어 추가: 최근 주간 리포트 즉시 조회

**Checkpoint**: 성과 자동 수집 + 주간 리포트 Telegram 전달 확인

---

## Phase 8: User Story 6 - 해시태그 및 콘텐츠 포맷 최적화 (Priority: P3)

**Goal**: 벤치마킹 + 성과 데이터 기반으로 해시태그 전략 및 콘텐츠 포맷 개선안 자동 제안

**Independent Test**: 1개월 데이터 축적 후 월간 최적화 분석 수신 확인

**Dependencies**: US2 (벤치마킹), US5 (성과 데이터) 축적 필요

### Implementation for User Story 6

- [x] T028 [US6] src/services/benchmark_analyzer.py 수정: generate_optimization_suggestions() 함수 추가 - 경쟁 계정 인기 해시태그 vs 자체 해시태그 효과 비교, 콘텐츠 길이/이미지 수별 성과 상관관계 분석, 개선 제안 목록 생성
- [x] T029 [US6] src/main.py에 월간 최적화 분석 job 등록 (매월 1일)
- [x] T030 [US6] src/services/telegram_handler.py에 /optimize 명령어 추가: 최적화 제안 즉시 조회

**Checkpoint**: 데이터 기반 최적화 제안 자동 생성 확인

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: OpenClaw 스킬 연동, 내부 API, 전체 통합 검증

- [x] T031 [P] src/api/routes.py에 Flask 내부 API 서버 구현: /api/queue/* (대기열 CRUD), /api/competitors/* (경쟁 계정 CRUD), /api/analytics/* (성과/리포트), /api/expert/* (전문가 콘텐츠). localhost:5000 바인딩
- [x] T032 [P] src/main.py에 Flask API 서버를 별도 스레드로 시작하는 코드 추가
- [x] T033 [P] skills/weibo-queue/SKILL.md 생성: 대기열 관리 스킬 (curl로 localhost:5000/api/queue/* 호출)
- [x] T034 [P] skills/weibo-benchmark/SKILL.md 생성: 벤치마킹 스킬 (curl로 localhost:5000/api/competitors/*, /api/benchmark/* 호출)
- [x] T035 [P] skills/weibo-analytics/SKILL.md 생성: 성과 분석 스킬 (curl로 localhost:5000/api/analytics/* 호출)
- [x] T036 [P] skills/weibo-expert/SKILL.md 생성: 전문가 콘텐츠 스킬 (curl로 localhost:5000/api/expert/* 호출)
- [x] T037 전체 통합 테스트: 매물 포스트 대기열 → 전문가 콘텐츠 자동 채움 → 최적 시간 발행 → 성과 수집 → 주간 리포트 전체 플로우 검증
- [x] T038 quickstart.md 검증: 셋업 가이드대로 신규 환경에서 전체 기능 동작 확인

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 의존성 없음 - 즉시 시작 가능
- **Foundational (Phase 2)**: Setup 완료 필요 - 모든 user story 차단
- **US1 (Phase 3)**: Foundational 완료 후 시작 - **MVP**
- **US2 (Phase 4)**: Foundational 완료 후 시작 - US1과 병렬 가능
- **US3 (Phase 5)**: US1 완료 필요 (대기열 + 스케줄러 활용)
- **US4 (Phase 6)**: US1 완료 필요 (스케줄러 확장). US2/US5 데이터 축적 후 효과 극대화
- **US5 (Phase 7)**: Foundational 완료 후 시작 - US1/US2와 병렬 가능
- **US6 (Phase 8)**: US2 + US5 완료 필요 (분석 데이터 의존)
- **Polish (Phase 9)**: 모든 user story 완료 후

### User Story Dependencies

```
Setup → Foundational → US1 (MVP) ──→ US3 → US4
                     → US2 ─────────────────→ US6
                     → US5 ─────────────────→ US6
                                              ↓
                                           Polish
```

### Within Each User Story

- Models → Services → Telegram 핸들러 → main.py job 등록
- 기존 코드 수정은 신규 코드 생성 이후

### Parallel Opportunities

- Phase 1: T002, T003, T004 병렬
- Phase 2: T005와 T006은 순차 (T006이 T005 의존), T007과 T008은 T005와 병렬
- US1과 US2 병렬 가능 (다른 파일, 다른 기능)
- US1과 US5 병렬 가능
- Phase 9: T031~T036 모두 병렬 (각각 독립 파일)

---

## Parallel Example: User Story 1 + User Story 2

```bash
# Foundational 완료 후, 두 스토리를 동시에 시작:

# US1 - 발행 대기열
Task: "T009 [US1] src/services/scheduler.py 생성"
Task: "T010 [US1] src/services/telegram_handler.py 수정 - 대기열 모드"

# US2 - 벤치마킹 (동시 진행 가능)
Task: "T013 [US2] src/models/competitor.py 생성"
Task: "T014 [US2] src/services/weibo_scraper.py 생성"
```

---

## Parallel Example: Polish Phase

```bash
# 모든 스킬 파일을 동시에 생성:
Task: "T033 skills/weibo-queue/SKILL.md"
Task: "T034 skills/weibo-benchmark/SKILL.md"
Task: "T035 skills/weibo-analytics/SKILL.md"
Task: "T036 skills/weibo-expert/SKILL.md"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1: Setup (T001-T004)
2. Phase 2: Foundational (T005-T008)
3. Phase 3: User Story 1 (T009-T012)
4. **STOP and VALIDATE**: 대기열 기반 예약 발행이 정상 동작하는지 확인
5. 매일 콘텐츠를 미리 보내놓으면 최적 시간에 자동 발행됨

### Incremental Delivery

1. Setup + Foundational → 인프라 준비
2. US1 → 대기열 발행 (MVP!)
3. US2 → 경쟁 벤치마킹 추가
4. US3 → 전문가 콘텐츠 자동 채움
5. US5 → 성과 추적 + 리포팅
6. US4 → 발행 시간 동적 최적화
7. US6 → 해시태그/포맷 최적화
8. Polish → OpenClaw 스킬 연동

각 단계마다 독립적으로 가치를 제공하며, 이전 단계를 깨뜨리지 않음.

---

## Notes

- [P] 태스크 = 다른 파일, 의존성 없음 → 병렬 실행 가능
- [Story] 라벨 = 해당 user story 추적용
- 기존 002 코드는 최대한 변경하지 않고 확장
- Weibo API 호출 시 항상 3-5초 딜레이 준수 (rate limit)
- 전문가 콘텐츠 생성 시 매물 정보 포함 금지 (FR-011, FR-013) 프롬프트에 명시
- Constitution III 준수: preview 모드 기본, 전문가 콘텐츠도 동일 모드 적용
- Constitution V 준수: 모든 외부 API 호출에 재시도/알림/로깅 포함 (T014, T019, T024)
