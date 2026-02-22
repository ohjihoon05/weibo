# Tasks: OpenClaw 스킬 등록 및 자동화 크론 설정

**Input**: Design documents from `/specs/004-openclaw-skill-setup/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Organization**: Tasks are grouped by user story. US1+US3 can run in parallel, US2 depends on both, US4 is independent.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Verify prerequisites and prepare directories

- [x] T001 Verify OpenClaw gateway is running with `openclaw health` and confirm gateway on localhost:18789
- [x] T002 Verify Flask API is running with `curl -s http://localhost:5000/api/health`
- [x] T003 Create skills directory `mkdir -p ~/.openclaw/skills/` for custom skill registration

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: No foundational tasks needed — all prerequisites exist from feature 003

**⚠️ CRITICAL**: Phase 1 setup verification must pass before proceeding

**Checkpoint**: Prerequisites verified — user story implementation can now begin

---

## Phase 3: User Story 1 - OpenClaw에 Weibo 스킬 등록 (Priority: P1) 🎯 MVP

**Goal**: 4개 Weibo 스킬을 OpenClaw에 등록하여 `openclaw skills list`에서 "ready" 상태로 표시

**Independent Test**: `openclaw skills list | grep weibo` → 4개 모두 "✓ ready"

### Implementation for User Story 1

- [x] T004 [P] [US1] Update skills/weibo-queue/SKILL.md — add YAML frontmatter with name: weibo-queue, emoji: 📋, requires.bins: ["curl"], add --max-time 10 to all curl commands
- [x] T005 [P] [US1] Update skills/weibo-benchmark/SKILL.md — add YAML frontmatter with name: weibo-benchmark, emoji: 📊, requires.bins: ["curl"], add --max-time 10 to all curl commands
- [x] T006 [P] [US1] Update skills/weibo-analytics/SKILL.md — add YAML frontmatter with name: weibo-analytics, emoji: 📈, requires.bins: ["curl"], add --max-time 10 to all curl commands
- [x] T007 [P] [US1] Update skills/weibo-expert/SKILL.md — add YAML frontmatter with name: weibo-expert, emoji: 🧠, requires.bins: ["curl"], add --max-time 10 to all curl commands
- [x] T008 [US1] Create symlinks from ~/.openclaw/skills/ to project skills/ — `ln -sf /home/ohjihoon/weibo/skills/weibo-queue ~/.openclaw/skills/weibo-queue` (repeat for all 4 skills)
- [x] T009 [US1] Verify all 4 skills show "✓ ready" status with `openclaw skills list --json | grep weibo`

**Checkpoint**: 4개 weibo 스킬이 OpenClaw에 등록되어 에이전트가 사용 가능

---

## Phase 4: User Story 3 - OpenClaw Telegram 채널 활성화 (Priority: P1)

**Goal**: OpenClaw 전용 별도 Telegram 봇을 활성화하여 양방향 소통 가능

**Independent Test**: `openclaw channels list` → Telegram "enabled" 상태 표시

### Implementation for User Story 3

- [x] T010 [US3] Enable Telegram channel in OpenClaw — run `openclaw channels add --channel telegram --token BOT_TOKEN` to activate Telegram (별도 봇 @openclaw_weibo_bot)
- [x] T011 [US3] Verify Telegram channel is active with `openclaw channels list` — confirm Telegram shows "enabled"

**Checkpoint**: OpenClaw Telegram 채널 활성화 완료, 크론 잡 결과 전달 준비

---

## Phase 5: User Story 2 - 크론 자동화 설정 (Priority: P1)

**Goal**: 일간 브리핑 + 주간 리포트 크론 잡을 등록하여 자동 실행

**Independent Test**: `openclaw cron list` → 2개 잡 표시, `openclaw cron run weibo-daily-briefing` → Telegram 알림 수신

**Dependencies**: US1 (스킬 등록) + US3 (Telegram 활성화) 완료 필요

### Implementation for User Story 2

- [x] T012 [US2] Add daily briefing cron job — `openclaw cron add --name "weibo-daily-briefing" --cron "0 9 * * *" --tz "Asia/Shanghai" --session isolated --message "..." --deliver --to "7842337761" --channel telegram --best-effort-deliver`
- [x] T013 [US2] Add weekly report cron job — `openclaw cron add --name "weibo-weekly-report" --cron "0 9 * * 1" --tz "Asia/Shanghai" --session isolated --message "..." --deliver --to "7842337761" --channel telegram --best-effort-deliver`
- [x] T014 [US2] Verify cron jobs are listed with `openclaw cron list` — confirm 2 jobs shown as "enabled"
- [x] T015 [US2] Test daily briefing with `openclaw cron run --force {id}` — verified: Flask API 호출 → 대기열 상태 자연어 요약 생성 성공

**Checkpoint**: 크론 자동화 설정 완료 — 매일 09:00 CST 일간 브리핑, 매주 월요일 09:00 CST 주간 리포트

---

## Phase 6: User Story 4 - OpenClaw Workspace에 Weibo 프로젝트 컨텍스트 추가 (Priority: P2)

**Goal**: OpenClaw에게 Weibo 마케팅 프로젝트 배경 지식을 제공하여 더 지능적인 응답과 분석 가능

**Independent Test**: `openclaw agent --message "오늘 Weibo 마케팅 상황 알려줘"` → 종합 브리핑 응답

### Implementation for User Story 4

- [x] T016 [US4] Create ~/.openclaw/workspace/weibo-project.md — Weibo 마케팅 프로젝트 컨텍스트 파일 작성 (프로젝트 목적, Flask API 구조, 4개 스킬 사용법, 운영 일정, 자동화 흐름 포함)
- [x] T017 [US4] Verify context-based response — 크론 잡 실행으로 컨텍스트 기반 응답 검증 완료

**Checkpoint**: 워크스페이스 컨텍스트 추가 완료 — OpenClaw이 프로젝트 배경 지식 기반으로 응답

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: 자동화 스크립트 작성 및 전체 검증

- [x] T018 Create scripts/setup-openclaw.sh — 스킬 등록(심볼릭 링크), 크론 잡 등록, 워크스페이스 설정을 한번에 실행하는 자동화 스크립트 (재설정 시 사용)
- [x] T019 Run full quickstart.md validation — VS-1,3,5,7 검증 완료 (스킬 4/4 ready, 크론 2/2, Telegram enabled, Workspace OK)
- [x] T020 Verify end-to-end flow: 크론 잡 강제 실행 → OpenClaw 에이전트 → weibo-queue 스킬 → Flask API /api/queue/status → 자연어 요약 생성 성공

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup — no actual tasks
- **US1 Skills (Phase 3)**: Depends on Phase 1 — can start immediately after setup
- **US3 Telegram (Phase 4)**: Depends on Phase 1 — can start in parallel with US1
- **US2 Cron (Phase 5)**: Depends on US1 + US3 completion (skills must be registered, Telegram must be active)
- **US4 Workspace (Phase 6)**: Depends on Phase 1 only — can start in parallel with US1/US3
- **Polish (Phase 7)**: Depends on US1 + US2 + US3 + US4 completion

### User Story Dependencies

```
Phase 1: Setup
    ├──→ US1 (Skills)     ──┐
    ├──→ US3 (Telegram)   ──┼──→ US2 (Cron) ──→ Polish
    └──→ US4 (Workspace)  ──┘
```

- **US1** (P1): Can start after Phase 1 — No dependencies on other stories
- **US3** (P1): Can start after Phase 1 — No dependencies on other stories, can run parallel with US1
- **US2** (P1): BLOCKED by US1 + US3 — Cron needs skills registered and Telegram enabled for delivery
- **US4** (P2): Can start after Phase 1 — Independent of US1/US2/US3

### Parallel Opportunities

- T004, T005, T006, T007: All SKILL.md updates can run in parallel (different files)
- US1 (Phase 3) and US3 (Phase 4): Can run in parallel (independent)
- US4 (Phase 6): Can run in parallel with US1/US3

---

## Parallel Example: US1 Skills

```bash
# Launch all SKILL.md updates in parallel:
Task: "Update skills/weibo-queue/SKILL.md with YAML frontmatter"
Task: "Update skills/weibo-benchmark/SKILL.md with YAML frontmatter"
Task: "Update skills/weibo-analytics/SKILL.md with YAML frontmatter"
Task: "Update skills/weibo-expert/SKILL.md with YAML frontmatter"

# Then sequentially:
Task: "Create symlinks to ~/.openclaw/skills/"
Task: "Verify all 4 skills ready"
```

## Parallel Example: US1 + US3 Concurrent

```bash
# These two user stories can execute simultaneously:
# Worker A: US1 (Skills) — T004~T009
# Worker B: US3 (Telegram) — T010~T011
# Then: US2 (Cron) — T012~T015 after both complete
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup verification
2. Complete Phase 3: US1 — Register 4 skills
3. **STOP and VALIDATE**: `openclaw skills list` shows 4 ready weibo skills
4. Test: `openclaw agent --message "Weibo 대기열 확인해줘"` → 응답 확인

### Incremental Delivery

1. Setup → US1 (Skills) → Test → 스킬 동작 확인 (MVP!)
2. + US3 (Telegram) → Test → 채널 활성화 확인
3. + US2 (Cron) → Test → 자동화 크론 동작 확인
4. + US4 (Workspace) → Test → 컨텍스트 기반 응답 확인
5. Polish → 전체 검증 → 완료

---

## Notes

- 이 feature는 코드 작성이 아닌 **설정 및 등록 작업** — CLI 명령어 실행과 SKILL.md 파일 수정이 주요 작업
- OpenClaw 게이트웨이와 Flask API가 반드시 실행 중이어야 함
- Telegram 활성화에는 별도 봇 토큰이 필요 (Weibo 봇과 분리)
- 크론 잡은 `~/.openclaw/cron/jobs.json`에 저장되어 게이트웨이 재시작 후에도 유지
- 모든 curl 명령어에 `--max-time 10` 추가하여 연결 실패 시 빠른 에러 감지
