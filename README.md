# Weibo 부동산 자동 포스팅 시스템

일본 부동산 매물을 Telegram Bot으로 입력받아, AI(Claude API)로 중국어 번역·포맷팅 후 Weibo에 자동 포스팅하는 시스템.

## 요구사항

- Python 3.11+
- Raspberry Pi (Linux ARM) 또는 호환 환경

## 설치

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

`.env` 파일을 편집하여 아래 값을 입력:

| 변수 | 설명 | 발급 방법 |
|------|------|----------|
| TELEGRAM_BOT_TOKEN | Telegram Bot 토큰 | @BotFather에서 /newbot으로 생성 |
| WEIBO_APP_KEY | Weibo 앱 키 | open.weibo.com → 앱 생성 |
| WEIBO_APP_SECRET | Weibo 앱 시크릿 | open.weibo.com → 앱 설정 |
| WEIBO_ACCESS_TOKEN | Weibo OAuth 토큰 | 아래 3단계 참조 |
| WEIBO_REDIRECT_URI | OAuth 리다이렉트 URI | 앱 설정에서 등록한 URI |
| CLAUDE_API_KEY | Claude API 키 | console.anthropic.com |

### 3. Weibo OAuth 토큰 발급

```bash
python3 -m src.auth.weibo_oauth
```

브라우저에서 인증 후 authorization code를 터미널에 입력하면 access_token이 .env에 저장됩니다.

**참고**: 미심사 앱은 토큰 유효기간이 1일입니다. 매일 갱신이 필요합니다.

### 4. Weibo IP 화이트리스트

라즈베리파이의 공인 IP를 Weibo 앱 설정(open.weibo.com → 앱 관리 → IP Whitelist)에 등록해야 합니다.

## 실행

```bash
python3 -m src.main
```

## 사용법

1. Telegram에서 Bot을 찾아 `/start` 전송
2. 매물 사진(1~9장) + 텍스트를 전송
3. (미리보기 모드) 번역 결과 확인 → "포스팅" 버튼 클릭
4. Weibo 게시물 링크 수신

### Bot 명령어

| 명령어 | 설명 |
|--------|------|
| /start | Bot 시작/안내 |
| /preview | 미리보기 모드 (기본) |
| /auto | 즉시 포스팅 모드 |
| /status | 현재 모드 확인 |

## 프로젝트 구조

```
src/
├── __init__.py
├── __main__.py
├── config.py                   # 환경변수 로드 및 검증
├── main.py                     # 엔트리포인트, 파이프라인 로직
├── auth/
│   ├── __init__.py
│   └── weibo_oauth.py          # Weibo OAuth 토큰 발급
├── models/
│   ├── __init__.py
│   ├── post.py                 # Post, PostHistory 데이터 모델
│   └── property_listing.py     # 부동산 매물 데이터 모델
├── services/
│   ├── __init__.py
│   ├── exchange_rate.py        # JPY→CNY 환율 조회
│   ├── hashtag_generator.py    # 해시태그 자동 생성
│   ├── image_processor.py      # 이미지 처리
│   ├── telegram_handler.py     # Telegram Bot 핸들러
│   ├── translator.py           # Claude API 번역·포맷팅
│   └── weibo_client.py         # Weibo API 클라이언트
└── storage/
    ├── __init__.py
    └── json_store.py           # JSON 파일 기반 저장소
```

## 라이선스

Private
