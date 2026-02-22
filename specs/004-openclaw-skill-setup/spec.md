# Feature Specification: OpenClaw 스킬 등록 및 자동화 크론 설정

**Feature Branch**: `004-openclaw-skill-setup`
**Created**: 2026-02-22
**Status**: Draft
**Input**: User description: "OpenClaw이 Weibo 마케팅을 자동으로 관리하도록 스킬 등록 및 크론 자동화 설정"

## Clarifications

### Session 2026-02-22

- Q: OpenClaw Telegram 봇을 Weibo 봇과 동일한 봇으로 사용할 것인가, 별도 봇으로 분리할 것인가? → A: OpenClaw 전용 별도 Telegram 봇 사용 (Weibo 봇과 분리)

## Context

기존 003 feature에서 Flask API(localhost:5000) + 4개 SKILL.md 파일을 생성했으나, OpenClaw(localhost:18789)에 실제로 등록되지 않은 상태. OpenClaw은 Raspberry Pi에 설치되어 실행 중이지만 Weibo 관련 스킬과 크론 잡이 없음.

현재 OpenClaw 상태:
- 6/49 번들 스킬만 ready (weibo 스킬 0개)
- 크론 잡 0개
- Telegram 채널 "configured, not enabled"

## User Scenarios & Testing

### User Story 1 - OpenClaw에 Weibo 스킬 등록 (Priority: P1)

운영자가 OpenClaw에게 "대기열 확인해줘"라고 말하면, OpenClaw이 weibo-queue 스킬을 사용하여 Flask API를 호출하고 결과를 알려준다.

**Why this priority**: 스킬이 등록되지 않으면 OpenClaw이 Weibo 관련 작업을 전혀 수행할 수 없음

**Independent Test**: OpenClaw에게 "Weibo 대기열 확인해줘"라고 요청 → Flask API 호출 → 대기열 상태 응답 수신

**Acceptance Scenarios**:

1. **Given** 4개 weibo 스킬이 OpenClaw에 등록된 상태, **When** "대기열 확인해줘"라고 요청, **Then** OpenClaw이 /api/queue/status를 호출하고 결과를 자연어로 전달
2. **Given** 스킬이 등록된 상태, **When** "경쟁 계정 목록 보여줘"라고 요청, **Then** OpenClaw이 /api/competitors를 호출하고 결과를 전달
3. **Given** 스킬이 등록된 상태, **When** "성과 리포트 보여줘"라고 요청, **Then** OpenClaw이 /api/analytics/report를 호출하고 결과를 전달
4. **Given** Flask API 서버가 꺼진 상태, **When** 스킬을 실행, **Then** 연결 실패 메시지를 사용자에게 알림

---

### User Story 2 - 크론 자동화 설정 (Priority: P1)

운영자가 설정 없이도 OpenClaw이 정기적으로 대기열 상태, 성과 데이터, 벤치마킹 결과를 확인하고 이상이 있으면 Telegram으로 알려준다.

**Why this priority**: 자동화 없이는 운영자가 매번 수동으로 확인 요청을 해야 함 - 프로젝트의 핵심 가치

**Independent Test**: 크론 설정 후 지정된 시간에 OpenClaw이 자동으로 API를 호출하고 Telegram으로 요약 전달

**Acceptance Scenarios**:

1. **Given** 크론 잡이 등록된 상태, **When** 매일 아침 9시(CST), **Then** OpenClaw이 대기열 상태 + 오늘 발행 예정 건수를 Telegram으로 알림
2. **Given** 크론 잡이 등록된 상태, **When** 매주 월요일 오전, **Then** OpenClaw이 주간 성과 요약을 Telegram으로 전달
3. **Given** 크론 잡이 등록된 상태, **When** API 호출 실패, **Then** OpenClaw이 "API 서버 응답 없음" 알림을 보냄

---

### User Story 3 - OpenClaw Telegram 채널 활성화 (Priority: P1)

OpenClaw 전용 별도 Telegram 봇을 활성화하여 운영자와 직접 소통할 수 있도록 한다. 이 봇은 Weibo 포스팅 봇과 분리되어 독립적으로 운영되며, 크론 잡 결과와 알림을 전달한다.

**Why this priority**: Telegram이 활성화되지 않으면 크론 자동화 결과를 전달할 방법이 없음

**Independent Test**: OpenClaw에게 Telegram으로 메시지를 보내면 응답이 오는지 확인

**Acceptance Scenarios**:

1. **Given** Telegram 채널이 활성화된 상태, **When** 운영자가 Telegram으로 OpenClaw에게 메시지, **Then** OpenClaw이 응답
2. **Given** Telegram이 활성화되고 크론이 설정된 상태, **When** 크론 실행 시간, **Then** Telegram으로 자동 알림 수신

---

### User Story 4 - OpenClaw Workspace에 Weibo 프로젝트 컨텍스트 추가 (Priority: P2)

OpenClaw이 Weibo 마케팅 프로젝트에 대한 배경 지식을 갖고 있어서 더 지능적인 응답과 분석을 제공한다.

**Why this priority**: 컨텍스트 없이도 스킬은 동작하지만, 컨텍스트가 있으면 더 유용한 분석과 제안이 가능

**Independent Test**: OpenClaw에게 "오늘 뭐 해야 해?"라고 물으면 대기열/성과/경쟁 상황을 종합적으로 판단하여 답변

**Acceptance Scenarios**:

1. **Given** Workspace에 프로젝트 컨텍스트가 등록된 상태, **When** "오늘의 마케팅 상황 알려줘", **Then** 대기열 + 성과 + 경쟁 데이터를 종합하여 자연어 브리핑 제공
2. **Given** 컨텍스트가 등록된 상태, **When** "이번 주 전략 제안해줘", **Then** 벤치마킹 데이터 기반 마케팅 제안 생성

---

### Edge Cases

- OpenClaw 게이트웨이가 재시작되면 크론 잡이 유지되는가?
- Flask API 서버가 다운된 상태에서 크론 잡이 실행되면 어떻게 처리하는가?
- OpenClaw 전용 봇과 Weibo 포스팅 봇이 별도 Telegram 봇으로 운영되므로 메시지 충돌은 없으나, 운영자가 두 봇의 알림을 혼동하지 않도록 메시지 포맷이 구분되어야 하는가?

## Requirements

### Functional Requirements

- **FR-001**: 4개 Weibo 스킬(weibo-queue, weibo-benchmark, weibo-analytics, weibo-expert)이 OpenClaw에 등록되어 `openclaw skills list`에서 "ready" 상태로 표시되어야 한다
- **FR-002**: 각 스킬은 localhost:5000 Flask API를 호출하여 실제 데이터를 반환해야 한다
- **FR-003**: OpenClaw 크론 스케줄러에 최소 2개 이상의 정기 작업이 등록되어야 한다 (일간 브리핑, 주간 리포트)
- **FR-004**: 크론 잡 실행 결과가 Telegram을 통해 운영자에게 전달되어야 한다
- **FR-005**: OpenClaw 전용 별도 Telegram 봇을 통해 Telegram 채널이 활성화되어 양방향 소통이 가능해야 한다 (Weibo 포스팅 봇과 분리 운영)
- **FR-006**: OpenClaw Workspace에 Weibo 프로젝트 관련 정보가 기록되어야 한다
- **FR-007**: Flask API 서버 연결 실패 시 OpenClaw이 에러를 감지하고 알림을 전달해야 한다

### Key Entities

- **OpenClaw Skill**: SKILL.md 파일 기반의 스킬 정의 (이름, 설명, 실행 명령어)
- **Cron Job**: 정기 실행 작업 (스케줄, 실행 명령, 대상 채널)
- **Workspace Context**: OpenClaw이 참조하는 프로젝트 배경 정보

## Success Criteria

### Measurable Outcomes

- **SC-001**: `openclaw skills list` 실행 시 4개 weibo 스킬이 모두 "ready" 상태로 표시된다
- **SC-002**: OpenClaw에게 자연어로 5가지 다른 Weibo 작업을 요청했을 때, 80% 이상(4/5) 올바른 API를 호출하고 결과를 반환한다
- **SC-003**: 크론 잡이 설정된 시간에 자동 실행되어 3일 연속 Telegram 알림이 정상 수신된다
- **SC-004**: OpenClaw Telegram 채널을 통해 양방향 대화가 가능하다
- **SC-005**: 설정 완료 후 운영자의 일일 수동 확인 작업이 자동화로 대체된다

## Assumptions

- OpenClaw 게이트웨이가 localhost:18789에서 상시 실행 중
- Flask API 서버가 Weibo 봇과 함께 localhost:5000에서 상시 실행 중
- OpenClaw CLI(openclaw) 명령어를 통해 스킬 등록 및 크론 설정이 가능
- Telegram 채널 활성화는 `openclaw doctor --fix` 또는 `openclaw channels` 명령어로 가능
- OpenClaw 크론 잡은 게이트웨이 재시작 후에도 유지됨 (jobs.json에 저장)
