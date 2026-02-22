# Research: OpenClaw 스킬 등록 및 자동화 크론 설정

**Feature**: 004-openclaw-skill-setup
**Date**: 2026-02-22

## R1: OpenClaw 스킬 등록 방법

**Decision**: `~/.openclaw/skills/{skill-name}/SKILL.md` 경로에 스킬 파일을 배치하면 자동 인식

**Rationale**:
- OpenClaw은 `~/.openclaw/skills/` 디렉토리를 자동 스캔하여 스킬을 발견
- 테스트로 `~/.openclaw/skills/test-skill/SKILL.md` 생성 후 `openclaw skills list`에서 "✓ ready" 확인
- source 표시: "openclaw-managed" (번들 스킬은 "openclaw-bundled")
- 프로젝트의 `skills/` 디렉토리에서 심볼릭 링크로 연결하면 코드와 설정이 동기화됨

**Alternatives considered**:
- `npx clawhub install`: 레지스트리 발행이 필요하여 로컬 스킬에 부적합
- `openclaw config set skills.dirs`: 지원하지 않는 설정 키 (`Unrecognized key: "dirs"`)
- 직접 복사: 동기화 문제 발생 가능, 심볼릭 링크가 더 나음

## R2: SKILL.md 파일 포맷

**Decision**: YAML frontmatter + Markdown body 형식

**Rationale**:
- 번들 스킬(weather, github 등) 분석으로 확인된 표준 형식
- 필수 필드: `name`, `description`, `metadata.openclaw`
- `metadata.openclaw.requires.bins`: 필요한 CLI 바이너리 (예: `curl`)
- `metadata.openclaw.emoji`: 스킬 목록에서 표시될 이모지
- 기존 프로젝트 SKILL.md 파일에는 frontmatter가 없어서 추가 필요

**Reference format** (weather 스킬 기반):
```yaml
---
name: skill-name
description: Short description
metadata: { "openclaw": { "emoji": "📋", "requires": { "bins": ["curl"] } } }
---
```

## R3: 크론 잡 등록 방법

**Decision**: `openclaw cron add` CLI 명령어로 등록

**Rationale**:
- 크론 표현식 지원: `--cron "0 9 * * *"` + `--tz "Asia/Shanghai"`
- 간격 지원: `--every "1h"`
- 결과 전달: `--deliver` (채널로 출력 전달), `--best-effort-deliver` (전달 실패 시 무시)
- 관리: `openclaw cron enable/disable {name}`, `openclaw cron run {name}` (즉시 실행)
- 잡은 `~/.openclaw/cron/jobs.json`에 저장되어 게이트웨이 재시작 후에도 유지

**Key options**:
- `--name`: 잡 이름 (필수)
- `--message`: 에이전트에게 보낼 메시지
- `--agent`: 타겟 에이전트 (기본값: main)
- `--model`: 모델 오버라이드 (기본값: config의 primary)
- `--thinking`: 사고 레벨 (off/minimal/low/medium/high)

## R4: Telegram 채널 활성화

**Decision**: `openclaw channels add telegram` + `openclaw channels login` 으로 활성화

**Rationale**:
- 현재 상태: "Telegram configured, not enabled yet"
- `openclaw doctor` 출력에서 fix 가능 항목으로 표시됨
- `openclaw doctor --fix`로도 활성화 가능
- 별도의 Telegram 봇 토큰이 필요 (Weibo 봇과 분리 운영 - clarification 결과)
- `openclaw channels list`로 상태 확인, `openclaw channels logs`로 로그 확인

**Alternatives considered**:
- `openclaw doctor --fix`: 자동으로 모든 문제 해결하지만 제어가 어려움
- 수동 config 편집: 가능하지만 CLI 사용이 더 안전하고 검증됨

## R5: Workspace 컨텍스트 구성

**Decision**: `~/.openclaw/workspace/` 디렉토리에 Weibo 프로젝트 컨텍스트 Markdown 파일 추가

**Rationale**:
- OpenClaw의 workspace는 `~/.openclaw/workspace/`에 위치
- 이미 `SOUL.md`가 존재 (에이전트 성격/정체성 정의)
- 프로젝트별 컨텍스트 파일을 추가하면 에이전트가 배경 지식으로 참조
- Weibo 마케팅 프로젝트의 목적, API 구조, 스킬 사용법을 기술

**Alternatives considered**:
- SOUL.md에 직접 추가: 기존 에이전트 성격 정의와 섞여 관리 어려움
- 별도 워크스페이스 생성: OpenClaw은 단일 워크스페이스만 지원

## R6: Flask API 건강 검사 통합

**Decision**: 스킬 내 curl 명령어에 타임아웃 설정 + 크론 잡에서 에러 감지

**Rationale**:
- curl에 `--max-time 10` 옵션으로 연결 타임아웃 설정
- curl 실패 시 exit code가 0이 아니므로 OpenClaw 에이전트가 에러 인식
- `--best-effort-deliver` 옵션으로 Telegram 전달 실패 시에도 크론 잡 중단 방지
- OpenClaw 에이전트 자체가 LLM이므로 에러 메시지를 해석하여 자연어로 전달

**Alternatives considered**:
- 별도 헬스체크 스킬: YAGNI - 기존 스킬 내 curl로 충분
- 외부 모니터링 도구: 과도한 인프라 추가
