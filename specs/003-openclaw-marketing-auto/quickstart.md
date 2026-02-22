# Quickstart: OpenClaw 마케팅 자동화 셋업

**Feature**: 003-openclaw-marketing-auto

## Prerequisites

- 기존 Weibo 봇(002-weibo-cookie-posting)이 정상 작동 중
- Raspberry Pi에 OpenClaw이 설치되어 있음 (localhost:18789)
- `.env` 파일에 기존 환경변수 설정 완료

## 1. 기존 봇에 API 서버 추가

```bash
# 추가 의존성 설치
pip install flask

# 봇 실행 (기존과 동일)
cd /home/ohjihoon/weibo
python -m src
```

봇 시작 시 `localhost:5000`에 내부 API 서버가 함께 실행됩니다.

## 2. OpenClaw 스킬 설치

```bash
# 프로젝트 스킬 디렉토리에 복사
cp -r skills/ /home/ohjihoon/weibo/skills/
```

OpenClaw이 자동으로 workspace skills를 인식합니다.

## 3. 경쟁 계정 등록

Telegram에서 OpenClaw에게:
```
경쟁 계정 추가 1234567890
```
또는 `data/competitors.json`에 직접 추가.

## 4. 발행 대기열 사용

```
# 매물 포스트: 기존처럼 사진+텍스트 전송 → 자동으로 대기열에 추가
# 대기열 확인:
대기열 확인

# 즉시 발행:
지금 발행
```

## 5. 자동 스케줄

봇이 자동으로 실행하는 정기 작업:
- **발행 대기열 처리**: 설정된 최적 시간에 자동 실행
- **성과 수집**: 발행 후 2시간, 24시간, 7일 자동 수집
- **벤치마킹**: 주 1회 경쟁 계정 분석
- **전문가 콘텐츠**: 대기열 비어있을 때 자동 생성
- **주간 리포트**: 매주 월요일 오전 자동 전달
