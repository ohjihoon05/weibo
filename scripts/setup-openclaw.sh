#!/usr/bin/env bash
# setup-openclaw.sh — OpenClaw Weibo 스킬 등록 + 크론 + Telegram 자동화 스크립트
# 재설정이 필요할 때 이 스크립트를 실행하세요.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SKILLS_DIR="$HOME/.openclaw/skills"
WORKSPACE_DIR="$HOME/.openclaw/workspace"

echo "=== OpenClaw Weibo Setup ==="
echo "Project: $PROJECT_DIR"
echo ""

# 1. Prerequisites check
echo "[1/5] Prerequisites 확인..."
if ! openclaw health >/dev/null 2>&1; then
    echo "ERROR: OpenClaw 게이트웨이가 실행 중이 아닙니다."
    echo "  실행: openclaw gateway"
    exit 1
fi

if ! curl -s --max-time 5 http://localhost:5000/api/health >/dev/null 2>&1; then
    echo "WARNING: Flask API(localhost:5000)가 응답하지 않습니다."
    echo "  Weibo 봇을 먼저 실행하세요."
fi
echo "  OK"

# 2. Register skills (symlinks)
echo "[2/5] 스킬 등록 (심볼릭 링크)..."
mkdir -p "$SKILLS_DIR"
for skill in weibo-queue weibo-benchmark weibo-analytics weibo-expert; do
    ln -sf "$PROJECT_DIR/skills/$skill" "$SKILLS_DIR/$skill"
    echo "  $skill → $SKILLS_DIR/$skill"
done

# Verify
READY_COUNT=$(openclaw skills list 2>/dev/null | grep -c "weibo-" || true)
echo "  등록된 weibo 스킬: $READY_COUNT/4"

# 3. Telegram channel
echo "[3/5] Telegram 채널 확인..."
TG_STATUS=$(openclaw channels list 2>/dev/null | grep -i "telegram" || true)
if echo "$TG_STATUS" | grep -q "enabled"; then
    echo "  Telegram: 이미 활성화됨"
else
    echo "  WARNING: Telegram이 활성화되지 않았습니다."
    echo "  실행: openclaw channels add --channel telegram --token YOUR_BOT_TOKEN"
fi

# 4. Cron jobs
echo "[4/5] 크론 잡 설정..."
EXISTING=$(openclaw cron list 2>/dev/null | grep -c "weibo-" || true)
if [ "$EXISTING" -ge 2 ]; then
    echo "  크론 잡: 이미 $EXISTING개 등록됨 (건너뜀)"
else
    echo "  크론 잡을 수동으로 등록하세요:"
    echo '  openclaw cron add --name "weibo-daily-briefing" --cron "0 9 * * *" --tz "Asia/Shanghai" --session isolated --message "Weibo 대기열 상태와 오늘 발행 예정 건수를 확인해서 알려줘." --deliver --to "CHAT_ID" --channel telegram --best-effort-deliver'
    echo '  openclaw cron add --name "weibo-weekly-report" --cron "0 9 * * 1" --tz "Asia/Shanghai" --session isolated --message "이번 주 Weibo 성과 리포트와 벤치마킹 결과를 종합해서 알려줘." --deliver --to "CHAT_ID" --channel telegram --best-effort-deliver'
fi

# 5. Workspace context
echo "[5/5] Workspace 컨텍스트 확인..."
if [ -f "$WORKSPACE_DIR/weibo-project.md" ]; then
    echo "  weibo-project.md: 이미 존재"
else
    echo "  WARNING: $WORKSPACE_DIR/weibo-project.md 없음"
    echo "  프로젝트 컨텍스트를 수동으로 추가하세요."
fi

echo ""
echo "=== Setup 완료 ==="
openclaw skills list 2>/dev/null | grep -E "Skills|weibo"
echo ""
openclaw cron list 2>/dev/null | head -5
