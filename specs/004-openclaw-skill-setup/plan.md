# Implementation Plan: OpenClaw 스킬 등록 및 자동화 크론 설정

**Branch**: `004-openclaw-skill-setup` | **Date**: 2026-02-22 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/004-openclaw-skill-setup/spec.md`

## Summary

OpenClaw(localhost:18789)에 4개 Weibo 스킬을 등록하고, 크론 자동화를 설정하며, Telegram 채널을 활성화하여 Weibo 마케팅 운영을 자동화한다. 기존 Flask API(localhost:5000)는 이미 가동 중이며, OpenClaw CLI와 `~/.openclaw/skills/` 디렉토리를 통해 스킬을 등록한다.

## Technical Context

**Language/Version**: Bash/Shell scripts + OpenClaw CLI (2026.1.30) + YAML frontmatter Markdown
**Primary Dependencies**: OpenClaw CLI (`openclaw`), `clawhub`, `curl`
**Storage**: `~/.openclaw/skills/` (스킬 정의), `~/.openclaw/cron/jobs.json` (크론 잡), `~/.openclaw/workspace/` (워크스페이스)
**Testing**: `openclaw skills list --json`, `openclaw cron list`, `openclaw doctor`, manual Telegram 확인
**Target Platform**: Raspberry Pi (Linux ARM) - OpenClaw 게이트웨이 로컬 실행 중
**Project Type**: CLI configuration + infrastructure setup (코드 작성이 아닌 설정 및 등록 작업)
**Performance Goals**: N/A (설정 작업이므로 런타임 성능 목표 없음)
**Constraints**: OpenClaw 게이트웨이가 localhost:18789에서 실행 중이어야 함, Flask API가 localhost:5000에서 실행 중이어야 함
**Scale/Scope**: 4개 스킬 등록, 2~3개 크론 잡, 1개 Telegram 채널, 1개 워크스페이스 컨텍스트

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Pipeline Reliability | ✅ PASS | 스킬은 Flask API를 통해 기존 파이프라인에 접근. API 실패 시 에러 메시지 전달 |
| II. Security by Default | ✅ PASS | API 키/토큰은 OpenClaw config에 저장, 소스코드에 포함하지 않음. Telegram 봇 토큰은 openclaw config에만 저장 |
| III. User Safety & Approval | ✅ PASS | OpenClaw 스킬은 읽기 전용 API만 호출 (queue status, analytics, competitors). 포스팅은 기존 봇의 /preview, /auto 모드에 의존 |
| IV. Translation Accuracy | ✅ PASS | 번역 기능에 영향 없음 - OpenClaw은 결과만 조회/전달 |
| V. Graceful Error Handling | ✅ PASS | Flask API 연결 실패 시 에러 감지 및 알림 전달 (FR-007) |
| VI. Simplicity & Resource Efficiency | ✅ PASS | 새 프로세스 추가 없음. OpenClaw 게이트웨이 기존 프로세스 활용. SKILL.md + cron config만 추가 |

**Gate Result**: ALL PASS - 위반 사항 없음

## Project Structure

### Documentation (this feature)

```text
specs/004-openclaw-skill-setup/
├── plan.md              # This file
├── research.md          # Phase 0 output - OpenClaw CLI research
├── data-model.md        # Phase 1 output - entities
├── quickstart.md        # Phase 1 output - verification scenarios
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
skills/
├── weibo-queue/
│   └── SKILL.md         # 기존 파일 → YAML frontmatter 추가
├── weibo-benchmark/
│   └── SKILL.md         # 기존 파일 → YAML frontmatter 추가
├── weibo-analytics/
│   └── SKILL.md         # 기존 파일 → YAML frontmatter 추가
└── weibo-expert/
    └── SKILL.md         # 기존 파일 → YAML frontmatter 추가

scripts/
└── setup-openclaw.sh    # 스킬 등록 + 크론 설정 + Telegram 활성화 자동화 스크립트
```

**Structure Decision**: 기존 `skills/` 디렉토리의 SKILL.md 파일에 YAML frontmatter를 추가하고, `~/.openclaw/skills/`로 심볼릭 링크를 생성하여 OpenClaw에 등록한다. 별도의 소스 코드 작성이 아닌 설정 파일 수정 + CLI 명령어 실행 작업이다.

## Implementation Approach

### Phase 1: SKILL.md 포맷 업그레이드

기존 4개 SKILL.md 파일에 OpenClaw 호환 YAML frontmatter를 추가한다:

```yaml
---
name: weibo-queue
description: Weibo 발행 대기열 관리 - 상태 확인, 콘텐츠 추가, 즉시 발행
metadata: { "openclaw": { "emoji": "📋", "requires": { "bins": ["curl"] } } }
---
```

### Phase 2: OpenClaw 스킬 등록

`~/.openclaw/skills/`에 심볼릭 링크를 생성하여 OpenClaw이 인식하도록 한다:

```bash
ln -sf /home/ohjihoon/weibo/skills/weibo-queue ~/.openclaw/skills/weibo-queue
ln -sf /home/ohjihoon/weibo/skills/weibo-benchmark ~/.openclaw/skills/weibo-benchmark
ln -sf /home/ohjihoon/weibo/skills/weibo-analytics ~/.openclaw/skills/weibo-analytics
ln -sf /home/ohjihoon/weibo/skills/weibo-expert ~/.openclaw/skills/weibo-expert
```

### Phase 3: Telegram 채널 활성화

OpenClaw 전용 별도 Telegram 봇 활성화:

```bash
openclaw channels add telegram
openclaw channels login telegram
```

### Phase 4: 크론 잡 등록

```bash
# 일간 브리핑 (매일 09:00 CST)
openclaw cron add --name "weibo-daily-briefing" \
  --cron "0 9 * * *" --tz "Asia/Shanghai" \
  --message "Weibo 대기열 상태와 오늘 발행 예정 건수를 확인해서 알려줘" \
  --deliver --best-effort-deliver

# 주간 리포트 (매주 월요일 09:00 CST)
openclaw cron add --name "weibo-weekly-report" \
  --cron "0 9 * * 1" --tz "Asia/Shanghai" \
  --message "이번 주 Weibo 성과 리포트와 경쟁 계정 벤치마킹 결과를 종합해서 알려줘" \
  --deliver --best-effort-deliver
```

### Phase 5: Workspace 컨텍스트 추가

`~/.openclaw/workspace/` 디렉토리에 Weibo 프로젝트 정보 파일 추가.

## Complexity Tracking

위반 사항 없음 - 추가 정당화 불필요.
