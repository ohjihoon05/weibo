# Quickstart: OpenClaw 스킬 등록 및 자동화 크론 설정

**Feature**: 004-openclaw-skill-setup
**Date**: 2026-02-22

## Prerequisites

- OpenClaw 게이트웨이 실행 중: `openclaw health`
- Flask API 실행 중: `curl -s http://localhost:5000/api/health`
- Weibo 봇 프로세스 실행 중

## Verification Scenarios

### VS-1: 스킬 등록 확인

```bash
# 4개 weibo 스킬이 모두 ready 상태인지 확인
openclaw skills list | grep -E "weibo-(queue|benchmark|analytics|expert)"

# 기대 결과:
# ✓ ready   │ 📋 weibo-queue      │ ...
# ✓ ready   │ 📊 weibo-benchmark  │ ...
# ✓ ready   │ 📈 weibo-analytics  │ ...
# ✓ ready   │ 🧠 weibo-expert     │ ...
```

### VS-2: 스킬 동작 확인

```bash
# OpenClaw 에이전트에게 직접 요청
openclaw agent --message "Weibo 대기열 상태를 확인해줘"

# 기대: OpenClaw이 weibo-queue 스킬을 사용하여 /api/queue/status 호출 후 결과 전달
```

### VS-3: 크론 잡 등록 확인

```bash
# 크론 잡 목록 확인
openclaw cron list

# 기대 결과:
# weibo-daily-briefing  │ 0 9 * * *   │ enabled
# weibo-weekly-report   │ 0 9 * * 1   │ enabled
```

### VS-4: 크론 잡 수동 실행 테스트

```bash
# 일간 브리핑 즉시 실행
openclaw cron run weibo-daily-briefing

# 기대: OpenClaw이 대기열 + 발행 예정 건수를 조회하여 Telegram으로 전달
```

### VS-5: Telegram 채널 확인

```bash
# Telegram 채널 상태 확인
openclaw channels list

# 기대: Telegram 채널이 "enabled" 상태로 표시
```

### VS-6: Telegram 양방향 소통 확인

1. OpenClaw Telegram 봇에게 메시지 전송: "대기열 확인해줘"
2. 기대: OpenClaw이 weibo-queue 스킬을 사용하여 응답

### VS-7: Workspace 컨텍스트 확인

```bash
# Workspace 파일 존재 확인
ls ~/.openclaw/workspace/weibo-project.md

# OpenClaw에게 컨텍스트 기반 질문
openclaw agent --message "오늘 Weibo 마케팅 상황을 브리핑해줘"

# 기대: 대기열 + 성과 + 경쟁 데이터를 종합한 자연어 브리핑
```

### VS-8: Flask API 장애 시나리오

```bash
# Flask API 중단 시뮬레이션 (봇 프로세스 중지 후)
openclaw agent --message "Weibo 대기열 상태 확인해줘"

# 기대: "Flask API 서버에 연결할 수 없습니다" 류의 에러 메시지
```

## Troubleshooting

| 증상 | 원인 | 해결 |
|------|------|------|
| 스킬이 missing 상태 | frontmatter 형식 오류 또는 심볼릭 링크 깨짐 | SKILL.md YAML 검증, 링크 경로 확인 |
| 크론 잡 미실행 | 게이트웨이 미실행 또는 잡 disabled | `openclaw health`, `openclaw cron enable {name}` |
| Telegram 미응답 | 채널 미활성화 또는 봇 토큰 오류 | `openclaw channels status`, `openclaw doctor --fix` |
| API 호출 실패 | Flask API 미실행 | `curl localhost:5000/api/health`, 봇 프로세스 재시작 |
