# Implementation Plan: Weibo 쿠키 자동 갱신 시스템

**Branch**: `005-cookie-auto-refresh` | **Date**: 2026-02-23 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/005-cookie-auto-refresh/spec.md`

## Summary

Weibo 쿠키 만료 전 사전 알림(Telegram) + CookieCloud 브라우저 확장 연동을 통한 반자동 쿠키 갱신 시스템. 기존 비작동 `refresh_cookies_via_openclaw()` 코드를 제거하고, 쿠키 나이 추적 + CookieCloud 클라이언트로 대체한다.

## Technical Context

**Language/Version**: Python 3.13 (Raspberry Pi 기존 설치)
**Primary Dependencies**: requests (기존), pycryptodome (신규 — AES-CBC 복호화), python-telegram-bot (기존)
**Storage**: JSON 파일 (data/weibo_cookies.json, 기존 패턴 유지) + 인메모리 (bot_data)
**Testing**: 수동 검증 (quickstart.md 시나리오)
**Target Platform**: Raspberry Pi (Linux ARM)
**Project Type**: Telegram 봇 서비스 (기존 확장)
**Performance Goals**: 쿠키 검증 주기 6시간, CookieCloud 요청 타임아웃 10초
**Constraints**: Raspberry Pi 메모리/CPU 제한, 외부 의존성 최소화
**Scale/Scope**: 단일 운영자, 단일 Weibo 계정

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Pipeline Reliability | ✅ PASS | 쿠키 갱신은 파이프라인 전제조건 — 안정성 향상 |
| II. Security by Default | ✅ PASS | CookieCloud 자격증명은 환경변수로 관리 (FR-010) |
| III. User Safety & Approval | ✅ PASS | 자동 갱신은 쿠키만 교체, 포스팅 승인 흐름 변경 없음 |
| IV. Translation Accuracy | N/A | 번역 기능 미접촉 |
| V. Graceful Error Handling | ✅ PASS | CookieCloud 실패 시 폴백 알림, 타임아웃 설정 |
| VI. Simplicity & Resource Efficiency | ✅ PASS | pycryptodome 1개 추가만, 인메모리 알림 상태, DB 미도입 |

**Post-Phase 1 Re-check**: 모든 게이트 통과. pycryptodome 추가는 CookieCloud 복호화에 필수이며, 대안(순수 Python 구현)은 복잡도 증가로 기각.

## Project Structure

### Documentation (this feature)

```text
specs/005-cookie-auto-refresh/
├── plan.md              # This file
├── research.md          # CookieCloud API, 암호화, 데이터 형식 조사
├── data-model.md        # 엔티티, 상태 전이, 관계도
├── quickstart.md        # 검증 시나리오 6개
└── tasks.md             # /speckit.tasks에서 생성
```

### Source Code (수정 대상)

```text
src/
├── config.py                    # [수정] COOKIECLOUD_*, COOKIE_EXPIRY_WARNING_HOURS 추가
├── main.py                      # [수정] cookie_validation_job 로직 개선
└── services/
    └── cookie_manager.py        # [수정] get_cookie_age_hours(), is_expiring_soon(),
                                 #        refresh_cookies_via_cookiecloud() 추가,
                                 #        refresh_cookies_via_openclaw() 제거
```

**Structure Decision**: 기존 프로젝트 구조를 그대로 사용. 신규 파일 생성 없이 기존 3개 파일만 수정.

## Complexity Tracking

> Constitution Check 위반 없음 — 이 섹션은 비어 있음
