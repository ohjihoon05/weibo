# Implementation Plan: Weibo 부동산 자동 포스팅 시스템

**Branch**: `001-weibo-auto-posting` | **Date**: 2026-02-22 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-weibo-auto-posting/spec.md`

## Summary

일본 부동산 매물 정보를 Telegram Bot으로 입력받아, AI(Claude API)로
중국어 번역·포맷팅 후 Weibo에 자동 포스팅하는 시스템.
Python 3.13 + python-telegram-bot + Pillow 기반으로
라즈베리파이에서 경량 운영한다. Weibo Open Platform 공식 API를
사용하며, 환율은 ExchangeRate-API(무료)로 실시간 환산한다.

## Technical Context

**Language/Version**: Python 3.13 (Raspberry Pi 기존 설치)
**Primary Dependencies**: python-telegram-bot v21.x, requests, Pillow, anthropic (Claude API)
**Storage**: JSON 파일 (로컬 파일시스템, DB 미사용)
**Testing**: pytest
**Target Platform**: Raspberry Pi 5 (Linux ARM, Debian Trixie, 16GB RAM)
**Project Type**: 장기 실행 서비스 (Telegram Bot long-polling)
**Performance Goals**: 매물 입력 후 5분 이내 포스팅 완료
**Constraints**: 라즈베리파이 리소스 제한, Weibo API 5MB 이미지 제한, 하루 1~3건
**Scale/Scope**: 단일 사용자, 하루 1~3건 포스팅

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 원칙 | 상태 | 검증 |
|------|------|------|
| I. Pipeline Reliability | ✅ Pass | 각 단계(수신→번역→포스팅) 독립 모듈, 실패 지점 명확 식별 |
| II. Security by Default | ✅ Pass | 모든 자격증명 환경변수 관리, .env → .gitignore |
| III. User Safety & Approval | ✅ Pass | 기본 미리보기 모드, InlineKeyboard 승인 버튼 |
| IV. Translation Accuracy | ✅ Pass | Claude API로 전문 용어 번역, 16개 항목 템플릿 포맷팅 |
| V. Graceful Error Handling | ✅ Pass | 재시도 3회, Telegram 에러 알림, PostHistory 로컬 저장 |
| VI. Simplicity & Resource Efficiency | ✅ Pass | DB 미사용, JSON 파일 저장, Pillow 경량 이미지 처리 |

**Post-Phase 1 Re-check**: 모든 원칙 위반 없음. Complexity Tracking 해당 사항 없음.

## Project Structure

### Documentation (this feature)

```text
specs/001-weibo-auto-posting/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0: Research findings
├── data-model.md        # Phase 1: Entity definitions
├── quickstart.md        # Phase 1: Setup guide
├── contracts/
│   ├── telegram-bot-commands.md
│   ├── weibo-api.md
│   └── exchange-rate-api.md
└── checklists/
    └── requirements.md
```

### Source Code (repository root)

```text
src/
├── __init__.py
├── main.py                  # 엔트리포인트, Bot 초기화 및 실행
├── config.py                # 환경변수 로드, 설정 관리
├── models/
│   ├── __init__.py
│   ├── property_listing.py  # PropertyListing 데이터 모델
│   └── post.py              # Post, PostHistory 데이터 모델
├── services/
│   ├── __init__.py
│   ├── telegram_handler.py  # Telegram 메시지 수신, MediaGroup 처리
│   ├── translator.py        # Claude API 번역 + 포맷팅
│   ├── weibo_client.py      # Weibo API 포스팅 (이미지 업로드 + 게시)
│   ├── exchange_rate.py     # 환율 조회 (fallback chain + cache)
│   ├── image_processor.py   # 이미지 리사이즈 (Pillow)
│   └── hashtag_generator.py # 해시태그 자동 생성
├── storage/
│   ├── __init__.py
│   └── json_store.py        # JSON 파일 기반 저장/조회
└── auth/
    ├── __init__.py
    └── weibo_oauth.py       # Weibo OAuth 토큰 발급 유틸리티

data/                        # 런타임 데이터 (gitignore)
├── posts/                   # 매물+포스팅 JSON 파일
├── history/                 # 포스팅 이력 JSONL 파일
├── images/                  # 임시 이미지 저장
└── exchange_rate.json       # 환율 캐시

tests/
├── unit/
│   ├── test_translator.py
│   ├── test_exchange_rate.py
│   ├── test_image_processor.py
│   └── test_hashtag_generator.py
└── integration/
    ├── test_telegram_flow.py
    └── test_weibo_posting.py
```

**Structure Decision**: 단일 프로젝트 구조. 라즈베리파이에서 하나의
프로세스로 실행되는 서비스이므로 모노리스 구조가 적합하다.
`src/services/`에 각 파이프라인 단계를 독립 모듈로 분리하여
Constitution 원칙 I(Pipeline Reliability)을 충족한다.

## Complexity Tracking

> Constitution Check 위반 없음. 해당 사항 없음.
