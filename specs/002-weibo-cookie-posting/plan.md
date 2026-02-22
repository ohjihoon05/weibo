# Implementation Plan: Weibo Cookie 기반 포스팅 전환

**Branch**: `002-weibo-cookie-posting` | **Date**: 2026-02-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-weibo-cookie-posting/spec.md`

## Summary

Weibo 공식 API(error 10014로 폐쇄)를 m.weibo.cn 모바일 웹 API(쿠키 기반)로
교체한다. 기존 `weibo_client.py`를 쿠키 기반 클라이언트로 재작성하고,
`weibo_oauth.py`를 제거한다. Telegram `/cookie` 명령어로 쿠키를 설정하고,
OpenClaw 브라우저 자동화로 쿠키 자동 갱신을 처리한다.

## Technical Context

**Language/Version**: Python 3.13 (기존 프로젝트와 동일)
**Primary Dependencies**: requests, python-telegram-bot[job-queue], Pillow, anthropic, python-dotenv (기존 그대로)
**Storage**: JSON 파일 (`data/weibo_cookies.json`, 기존 `data/posts/`, `data/history/`)
**Testing**: pytest + mocking (기존 테스트 패턴 유지)
**Target Platform**: Raspberry Pi 5 (Linux ARM64, Debian Trixie)
**Project Type**: CLI bot (Telegram long-polling)
**Performance Goals**: 1~3건/일 포스팅, 게시물당 5분 이내 처리
**Constraints**: 메모리 512MB (Docker limit), ARM64, 새 의존성 최소화
**Scale/Scope**: 단일 운영자, 단일 Weibo 계정

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Pipeline Reliability | ✅ PASS | weibo_client만 교체, 파이프라인 구조 유지. 실패 지점(쿠키 만료, 업로드 실패, 포스팅 실패) 명확히 분리. |
| II. Security by Default | ✅ PASS | 쿠키를 `data/weibo_cookies.json`(권한 600)에 저장, 로그 마스킹 적용, .gitignore에 data/ 이미 포함. |
| III. User Safety & Approval | ✅ PASS | 기존 preview/auto 모드 변경 없음. 중복 감지 시 preview에서 경고. |
| IV. Translation Accuracy | ✅ PASS | 번역 파이프라인 변경 없음. 해시태그 형식만 `#topic#`으로 조정. |
| V. Graceful Error Handling | ✅ PASS | 재시도 로직 유지(3회, 지수 백오프). 쿠키 만료 에러 감지 및 알림 추가. |
| VI. Simplicity | ✅ PASS | 새 의존성 없음. OpenClaw 연동은 HTTP API 1건 호출. DB/큐/캐시 미도입. |

## Project Structure

### Documentation (this feature)

```text
specs/002-weibo-cookie-posting/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── weibo-mobile-api.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 output (by /speckit.tasks)
```

### Source Code (변경 대상)

```text
src/
├── config.py                    # MODIFY: Weibo OAuth 환경변수 제거, 쿠키 관련 선택적 변수 추가
├── main.py                      # MODIFY: WeiboClient 초기화 변경 (access_token → cookies)
├── auth/
│   ├── __init__.py
│   └── weibo_oauth.py           # DELETE: OAuth 플로우 불필요
├── services/
│   ├── weibo_client.py          # REWRITE: m.weibo.cn 쿠키 기반 클라이언트
│   ├── cookie_manager.py        # NEW: 쿠키 저장/로드/검증/파싱
│   ├── telegram_handler.py      # MODIFY: /cookie, /status 명령어 추가
│   ├── hashtag_generator.py     # NO CHANGE (변환은 weibo_client에서 처리)
│   ├── translator.py            # NO CHANGE
│   ├── exchange_rate.py         # NO CHANGE
│   └── image_processor.py       # NO CHANGE
├── models/
│   ├── property_listing.py      # NO CHANGE
│   └── post.py                  # NO CHANGE
└── storage/
    └── json_store.py            # MODIFY: 쿠키 저장/로드 함수 추가

data/
├── weibo_cookies.json           # NEW: 쿠키 저장 파일 (runtime)
├── posts/                       # NO CHANGE
├── history/                     # NO CHANGE
└── logs/                        # NO CHANGE
```

**Structure Decision**: 기존 프로젝트 구조를 유지하며 최소한의 파일만 변경/추가.
새 모듈은 `cookie_manager.py` 1개만 추가. 기존 `weibo_client.py`는 동일 파일명으로
재작성하여 `main.py`의 import 변경을 최소화.

## Complexity Tracking

해당 없음. Constitution 위반 없음.
