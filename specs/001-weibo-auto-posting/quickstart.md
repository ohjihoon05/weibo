# Quickstart: Weibo 부동산 자동 포스팅 시스템

**Branch**: `001-weibo-auto-posting`

## Prerequisites

1. **Raspberry Pi** (Linux ARM, Python 3.11+)
2. **Telegram Bot Token** — @BotFather에서 생성
3. **Weibo 개발자 계정** — open.weibo.com에서 등록
4. **Weibo App Key + App Secret** — 웹 앱 생성 후 획득

## Setup

### 1. 프로젝트 클론 및 가상환경

```bash
git clone <repo-url>
cd weibo
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. 환경변수 설정

```bash
cp .env.example .env
```

`.env` 파일 편집:
```env
# Telegram
TELEGRAM_BOT_TOKEN=your-bot-token

# Weibo
WEIBO_APP_KEY=your-app-key
WEIBO_APP_SECRET=your-app-secret
WEIBO_ACCESS_TOKEN=your-access-token
WEIBO_REDIRECT_URI=your-redirect-uri

# Claude API (via OpenClaw)
CLAUDE_API_KEY=your-claude-api-key
```

### 3. Weibo OAuth 토큰 발급

```bash
python3 -m src.auth.weibo_oauth
```

브라우저에서 인증 후 access_token이 `.env`에 저장됨.

### 4. Bot 실행

```bash
python3 -m src.main
```

## 사용법

1. Telegram에서 Bot을 찾아 `/start` 전송
2. 매물 사진(1~9장) + 텍스트를 전송
3. (미리보기 모드) 번역 결과 확인 → "포스팅" 버튼 클릭
4. Weibo 게시물 링크 수신

### 모드 전환
- `/preview` — 미리보기 모드 (기본)
- `/auto` — 즉시 포스팅 모드

## Validation Checklist

- [ ] Telegram Bot이 사진 + 텍스트 수신 가능
- [ ] AI 번역이 정확한 중국어 출력 생성
- [ ] 부동산 템플릿 포맷팅 정상 동작
- [ ] 환율 환산 정상 동작 (JPY → CNY)
- [ ] 미리보기가 Telegram으로 전송됨
- [ ] 승인 버튼 클릭 시 Weibo에 포스팅됨
- [ ] 포스팅 완료 시 링크 전송됨
- [ ] 포스팅 실패 시 재시도 + 에러 알림
- [ ] 해시태그 자동 생성됨
