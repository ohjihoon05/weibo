# Data Model: OpenClaw 스킬 등록 및 자동화 크론 설정

**Feature**: 004-openclaw-skill-setup
**Date**: 2026-02-22

## Entities

### 1. OpenClaw Skill

OpenClaw에 등록된 스킬 정의. `~/.openclaw/skills/{name}/SKILL.md` 파일로 관리.

| Field | Type | Description | Required |
|-------|------|-------------|----------|
| name | string | 스킬 고유 이름 (디렉토리명과 일치) | Yes |
| description | string | 스킬 설명 (skills list에 표시) | Yes |
| emoji | string | 이모지 아이콘 | No |
| requires.bins | string[] | 필요한 CLI 바이너리 목록 | No |
| requires.env | string[] | 필요한 환경변수 목록 | No |
| body | markdown | 사용법, 명령어, 노트 (에이전트가 참조) | Yes |

**스킬 목록**:

| Skill Name | Emoji | Description | API Endpoints |
|-----------|-------|-------------|---------------|
| weibo-queue | 📋 | 발행 대기열 관리 | /api/queue/status, /api/queue/items, /api/queue/enqueue, /api/queue/publish/{id}, /api/queue/{id} |
| weibo-benchmark | 📊 | 경쟁 계정 벤치마킹 | /api/competitors, /api/competitors/benchmark |
| weibo-analytics | 📈 | 성과 분석 | /api/analytics/metrics, /api/analytics/report, /api/analytics/besttime |
| weibo-expert | 🧠 | 전문가 콘텐츠 생성 | /api/expert/recent, /api/expert/generate |

**상태 전이**:
- `missing` → `ready`: SKILL.md 파일이 `~/.openclaw/skills/`에 배치되고 requires 충족
- `ready` → `missing`: SKILL.md 삭제 또는 requires 미충족 (예: curl 제거)

### 2. Cron Job

OpenClaw 크론 스케줄러에 등록된 정기 작업. `~/.openclaw/cron/jobs.json`에 저장.

| Field | Type | Description | Required |
|-------|------|-------------|----------|
| name | string | 잡 고유 이름 | Yes |
| schedule | cron expr | 5-field cron 표현식 | Yes (또는 every) |
| timezone | string | IANA 타임존 | No (기본: system) |
| message | string | 에이전트에게 보낼 프롬프트 | Yes |
| agent | string | 타겟 에이전트 이름 | No (기본: main) |
| deliver | boolean | 결과를 채널로 전달 여부 | No |
| enabled | boolean | 활성화 상태 | Yes |

**크론 잡 목록**:

| Job Name | Schedule | Timezone | Message |
|----------|----------|----------|---------|
| weibo-daily-briefing | `0 9 * * *` | Asia/Shanghai | 대기열 상태 + 오늘 발행 예정 건수 확인 |
| weibo-weekly-report | `0 9 * * 1` | Asia/Shanghai | 주간 성과 + 벤치마킹 종합 리포트 |

### 3. Workspace Context

OpenClaw 에이전트가 참조하는 프로젝트 배경 정보. `~/.openclaw/workspace/` 디렉토리에 Markdown 파일로 저장.

| Field | Type | Description | Required |
|-------|------|-------------|----------|
| filename | string | 컨텍스트 파일명 (예: weibo-project.md) | Yes |
| content | markdown | 프로젝트 설명, API 구조, 운영 가이드 | Yes |

**내용 포함 항목**:
- 프로젝트 목적: 일본 부동산 매물 → Weibo 중국어 마케팅
- Flask API 구조 및 엔드포인트 요약
- 스킬 사용 가이드
- 운영 일정 및 자동화 흐름

### 4. Telegram Channel (OpenClaw 전용)

OpenClaw의 Telegram 채널 설정. `~/.openclaw/openclaw.json`의 `channels.telegram` 섹션.

| Field | Type | Description | Required |
|-------|------|-------------|----------|
| enabled | boolean | 채널 활성화 상태 | Yes |
| token | string | Telegram Bot Token (별도 봇) | Yes |
| chatId | string | 운영자 채팅 ID | Yes |

**Note**: Weibo 포스팅 봇(python-telegram-bot)과 분리된 별도 Telegram 봇 사용.

## Relationships

```
OpenClaw Gateway (localhost:18789)
├── Skills (4개)
│   ├── weibo-queue ──→ Flask API /api/queue/*
│   ├── weibo-benchmark ──→ Flask API /api/competitors/*
│   ├── weibo-analytics ──→ Flask API /api/analytics/*
│   └── weibo-expert ──→ Flask API /api/expert/*
├── Cron Jobs (2개)
│   ├── weibo-daily-briefing ──→ Agent (main) ──→ Skills ──→ Telegram
│   └── weibo-weekly-report ──→ Agent (main) ──→ Skills ──→ Telegram
├── Channels
│   ├── Discord (enabled)
│   └── Telegram (to be enabled - 별도 봇)
└── Workspace
    ├── SOUL.md (기존)
    └── weibo-project.md (신규)
```
