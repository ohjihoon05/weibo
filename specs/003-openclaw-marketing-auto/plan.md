# Implementation Plan: OpenClaw 기반 Weibo 마케팅 자동화

**Branch**: `003-openclaw-marketing-auto` | **Date**: 2026-02-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-openclaw-marketing-auto/spec.md`

## Summary

기존 Weibo 쿠키 기반 포스팅 시스템(002) 위에 OpenClaw을 Telegram 통합 허브로 추가하여, 발행 대기열 관리, 경쟁 계정 벤치마킹, 전문가 콘텐츠 자동 생성, 성과 분석 및 리포팅 기능을 구현한다. 오사카 근교 일본 부동산을 중국인 대상으로 판매하는 Weibo 계정의 마케팅을 자동화한다.

## Technical Context

**Language/Version**: Python 3.13 (Raspberry Pi 기존 설치)
**Primary Dependencies**: python-telegram-bot[job-queue], requests, Pillow, anthropic, python-dotenv, flask (신규 - 내부 API)
**Storage**: JSON 파일 (data/ 디렉토리, 기존 패턴 유지)
**Testing**: pytest
**Target Platform**: Raspberry Pi (Linux ARM)
**Project Type**: Telegram bot / automation service
**Performance Goals**: 하루 1-2건 포스팅, 주 1회 벤치마킹, 2-4시간 간격 성과 수집
**Constraints**: Raspberry Pi 메모리/CPU 제한, m.weibo.cn 쿠키 인증, Weibo 분당 20-30 요청 제한
**Scale/Scope**: 단일 운영자, 경쟁 계정 3-10개, 일 1-2건 발행

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Pipeline Reliability | PASS | 기존 파이프라인 유지, 대기열이 실패 지점 추가 → fcntl 잠금 + atomic write로 보장 |
| II. Security by Default | PASS | 신규 API 키 없음, 기존 .env 패턴 유지, localhost API만 노출 |
| III. User Safety & Approval | PASS | preview 모드 기본 유지, 전문가 콘텐츠도 동일 preview/auto 모드 적용 |
| IV. Translation Accuracy | PASS | 매물 번역은 기존 파이프라인 그대로, 전문가 콘텐츠는 중국어 직접 생성 (번역 아님) |
| V. Graceful Error Handling | PASS | 대기열 실패 시 retry, 스크래핑 실패 시 알림, 모든 작업 이력 저장 |
| VI. Simplicity & Resource Efficiency | PASS | JSON 파일 저장, 추가 DB/MQ 없음, Flask 경량 서버, YAGNI 준수 |

**Post-Design Re-check**:
- III 추가 확인: 전문가 콘텐츠 자동 생성 시 auto 모드면 즉시 발행, preview 모드면 운영자 확인 후 발행 → Constitution 준수
- FR-011/FR-013 (매물 정보 자동 생성 금지): 전문가 콘텐츠 생성 프롬프트에 명시적 금칙어 목록 포함하여 보장

## Project Structure

### Documentation (this feature)

```text
specs/003-openclaw-marketing-auto/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 research output
├── data-model.md        # Phase 1 data model
├── quickstart.md        # Phase 1 setup guide
├── contracts/           # Phase 1 interface contracts
│   └── openclaw-skills.md
└── tasks.md             # Phase 2 output (via /speckit.tasks)
```

### Source Code (repository root)

```text
src/
├── __main__.py              # 기존 (변경 없음)
├── main.py                  # 기존 + 신규 job 등록, API 서버 시작
├── config.py                # 기존 + 신규 설정 (발행 시간, 벤치마킹 주기)
├── api/                     # 신규: 내부 HTTP API (OpenClaw 연동용)
│   ├── __init__.py
│   └── routes.py            # queue, competitors, analytics, expert 엔드포인트
├── models/
│   ├── post.py              # 기존 (변경 없음)
│   ├── property_listing.py  # 기존 (변경 없음)
│   ├── queue_item.py        # 신규: 발행 대기열 항목
│   ├── competitor.py        # 신규: 경쟁 계정 + 포스트
│   └── expert_content.py    # 신규: 전문가 콘텐츠
├── services/
│   ├── telegram_handler.py  # 기존 + 대기열 모드 핸들러 추가
│   ├── weibo_client.py      # 기존 (변경 없음)
│   ├── weibo_scraper.py     # 신규: 경쟁 계정 스크래핑
│   ├── metrics_collector.py # 신규: 성과 데이터 수집
│   ├── benchmark_analyzer.py # 신규: 벤치마킹 분석 + 리포트 생성
│   ├── expert_generator.py  # 신규: 전문가 콘텐츠 생성
│   ├── scheduler.py         # 신규: 최적 시간 계산 + 대기열 처리
│   ├── cookie_manager.py    # 기존 (변경 없음)
│   ├── translator.py        # 기존 (변경 없음)
│   ├── exchange_rate.py     # 기존 (변경 없음)
│   ├── hashtag_generator.py # 기존 (변경 없음)
│   └── image_processor.py   # 기존 (변경 없음)
├── storage/
│   ├── json_store.py        # 기존 (변경 없음)
│   └── publish_queue.py     # 신규: JSON 기반 발행 대기열
└── auth/                    # 기존 (변경 없음)

skills/                      # 신규: OpenClaw 스킬
├── weibo-queue/
│   └── SKILL.md
├── weibo-benchmark/
│   └── SKILL.md
├── weibo-analytics/
│   └── SKILL.md
└── weibo-expert/
    └── SKILL.md

data/                        # 기존 구조 확장
├── posts/                   # 기존 (변경 없음)
├── history/                 # 기존 (변경 없음)
├── images/                  # 기존 (변경 없음)
├── logs/                    # 기존 (변경 없음)
├── weibo_cookies.json       # 기존 (변경 없음)
├── exchange_rate.json       # 기존 (변경 없음)
├── publish_queue.json       # 신규: 발행 대기열
├── competitors.json         # 신규: 경쟁 계정 목록
├── competitors/             # 신규: 경쟁 계정 포스트
│   └── YYYY-MM.jsonl
├── metrics/                 # 신규: 성과 데이터
│   └── YYYY-MM.jsonl
├── reports/                 # 신규: 벤치마킹 리포트
│   └── YYYY-WW.json
└── expert_content/          # 신규: 전문가 콘텐츠 이력
    └── YYYY-MM.jsonl

tests/
├── test_pipeline.py         # 기존
├── test_publish_queue.py    # 신규
├── test_weibo_scraper.py    # 신규
├── test_metrics_collector.py # 신규
├── test_benchmark_analyzer.py # 신규
├── test_expert_generator.py # 신규
├── test_scheduler.py        # 신규
└── integration/             # 기존
```

**Structure Decision**: 기존 `src/` 구조를 유지하면서 `services/`, `models/`, `storage/`에 신규 모듈 추가. OpenClaw 스킬은 프로젝트 루트 `skills/` 디렉토리에 배치. Constitution VI(Simplicity) 준수하여 별도 프레임워크 도입 없음.

## Implementation Phases

### Phase 1: 발행 대기열 + 스케줄러 (P1 - Story 1)

**목표**: 여러 건의 콘텐츠를 대기열에 저장하고 최적 시간에 순차 발행

1. `src/storage/publish_queue.py` - JSON 기반 atomic 대기열 구현
2. `src/models/queue_item.py` - QueueItem 데이터 모델
3. `src/services/scheduler.py` - 최적 시간 계산 (초기: 고정 시간 → 데이터 축적 후 동적)
4. `src/services/telegram_handler.py` 수정 - 즉시 발행 대신 대기열 등록 모드 추가
5. `src/main.py` 수정 - scheduler job 등록 (대기열 처리 주기)
6. `src/config.py` 수정 - 발행 시간대 설정 추가

**초기 최적 시간 (데이터 축적 전)**:
- 1차: 중국 시간 09:00 (출근 시간)
- 2차: 중국 시간 20:00 (저녁 여유 시간)

### Phase 2: 경쟁 계정 벤치마킹 (P1 - Story 2)

**목표**: 경쟁 계정 등록/검색, 포스트 수집, 벤치마킹 리포트 생성

1. `src/models/competitor.py` - CompetitorAccount, CompetitorPost 데이터 모델
2. `src/services/weibo_scraper.py` - m.weibo.cn API 스크래핑 (타임라인, 사용자 검색)
3. `src/services/benchmark_analyzer.py` - 수집 데이터 분석 + 주간 리포트 생성
4. `src/main.py` 수정 - 주간 벤치마킹 job 등록
5. Telegram 명령어 추가: 경쟁 계정 등록/목록/분석 요청

**Rate Limit 준수**: 요청 간 3-5초 딜레이, 일 최대 500 요청

### Phase 3: 전문가 콘텐츠 자동 생성 (P1 - Story 3)

**목표**: 매물 없는 날에 오사카/간사이 부동산 전문가 콘텐츠 자동 생성

1. `src/models/expert_content.py` - ExpertContent 데이터 모델
2. `src/services/expert_generator.py` - Claude API로 전문가 콘텐츠 생성
   - 주제 풀: 오사카 시장 동향, 투자 수익률, 지역 소개, 세금/비자, 매매 절차
   - 프롬프트에 FR-013 금칙어 명시 (특정 매물 정보 생성 금지)
   - preview/auto 모드 기존 로직 그대로 적용
3. `src/services/scheduler.py` 수정 - 대기열 비어있을 때 전문가 콘텐츠 자동 트리거
4. 해시태그: 기존 hashtag_generator 패턴 + 오사카/간사이 특화 태그

### Phase 4: 성과 수집 + 리포팅 (P2 - Story 4, 5)

**목표**: 자체 포스트 성과 자동 수집, 주간 리포트 Telegram 전달

1. `src/services/metrics_collector.py` - statuses/show API로 성과 수집
2. `data/metrics/YYYY-MM.jsonl` - 성과 데이터 저장
3. 주간 리포트 생성 + Telegram 전달 (매주 월요일 오전)
4. `src/main.py` 수정 - 성과 수집 job (2-4시간 간격), 주간 리포트 job

### Phase 5: 최적화 제안 + OpenClaw 스킬 (P2-P3 - Story 4, 6)

**목표**: 데이터 기반 해시태그/시간 최적화, OpenClaw 스킬 셋업

1. `src/services/scheduler.py` 수정 - 성과 데이터 기반 최적 시간 동적 계산
2. 해시태그 효과 분석 + 변경 제안
3. `src/api/routes.py` - 내부 HTTP API (Flask, localhost:5000)
4. `skills/` - OpenClaw 스킬 파일 (SKILL.md) 4개

## Complexity Tracking

> 해당 없음 - Constitution 위반 사항 없음
