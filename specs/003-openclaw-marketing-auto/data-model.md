# Data Model: OpenClaw 기반 Weibo 마케팅 자동화

**Feature**: 003-openclaw-marketing-auto
**Date**: 2026-02-22

## Entities

### 1. QueueItem (발행 대기열 항목)

발행 대기열의 개별 콘텐츠 항목.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string (UUID) | Yes | 고유 식별자 |
| type | enum | Yes | `listing` (매물) 또는 `expert` (전문가 콘텐츠) |
| text | string | Yes | 원본 텍스트 (매물: 일본어, 전문가: 중국어) |
| image_paths | list[string] | No | 이미지 파일 경로 목록 (0-9장) |
| scheduled_at | datetime | Yes | 예정 발행 시각 (UTC) |
| status | enum | Yes | `pending` → `processing` → `completed` / `failed` |
| queued_at | datetime | Yes | 대기열 등록 시각 |
| started_at | datetime | No | 처리 시작 시각 |
| completed_at | datetime | No | 완료 시각 |
| error | string | No | 실패 시 에러 메시지 |
| post_id | string | No | 발행 성공 시 Post.id 참조 |
| telegram_chat_id | int | No | 원본 메시지의 Telegram chat ID |

**State Transitions**:
```
pending → processing → completed
                    → failed → pending (재시도 시)
```

**Validation Rules**:
- `type=listing`이면 `text`는 비어있지 않아야 함
- `type=expert`이면 `image_paths`는 비어있어야 함 (텍스트 전용)
- `scheduled_at`은 미래 시각이어야 함 (등록 시점 기준)
- 한 날짜에 pending 항목은 최대 5건

---

### 2. CompetitorAccount (경쟁 계정)

벤치마킹 대상 Weibo 계정 정보.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| uid | string | Yes | Weibo 사용자 UID |
| nickname | string | Yes | 표시 이름 |
| source | enum | Yes | `manual` (운영자 등록) 또는 `auto` (자동 검색) |
| active | bool | Yes | 모니터링 활성화 여부 |
| added_at | datetime | Yes | 등록 시각 |
| last_scraped_at | datetime | No | 마지막 수집 시각 |
| note | string | No | 운영자 메모 |

**Validation Rules**:
- `uid`는 유일해야 함
- `active=false`인 계정은 스크래핑 대상에서 제외

---

### 3. CompetitorPost (경쟁 계정 포스트)

경쟁 계정에서 수집한 개별 포스트 데이터.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string | Yes | Weibo 포스트 mid |
| competitor_uid | string | Yes | CompetitorAccount.uid 참조 |
| text | string | Yes | 포스트 텍스트 |
| image_count | int | Yes | 첨부 이미지 수 |
| hashtags | list[string] | No | 사용된 해시태그 |
| reposts_count | int | Yes | 공유 수 |
| comments_count | int | Yes | 댓글 수 |
| attitudes_count | int | Yes | 좋아요 수 |
| created_at | datetime | Yes | 포스트 작성 시각 |
| scraped_at | datetime | Yes | 수집 시각 |

---

### 4. PerformanceMetric (성과 데이터)

자체 발행 포스트의 시계열 성과 지표.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string (UUID) | Yes | 고유 식별자 |
| post_id | string | Yes | Post.id 참조 (기존 모델) |
| bid | string | Yes | Weibo 포스트 bid |
| reposts_count | int | Yes | 공유 수 |
| comments_count | int | Yes | 댓글 수 |
| attitudes_count | int | Yes | 좋아요 수 |
| collected_at | datetime | Yes | 수집 시각 |

**Collection Schedule**: 발행 후 2시간, 24시간, 7일

---

### 5. BenchmarkReport (벤치마킹 리포트)

주간 경쟁 분석 결과.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string (UUID) | Yes | 고유 식별자 |
| period_start | date | Yes | 분석 기간 시작 |
| period_end | date | Yes | 분석 기간 종료 |
| competitors_analyzed | int | Yes | 분석된 경쟁 계정 수 |
| top_posts | list[dict] | Yes | 기간 내 인기 포스트 상위 10건 |
| hashtag_analysis | dict | Yes | 해시태그 빈도 및 효과 분석 |
| posting_pattern | dict | Yes | 발행 시간대/빈도 패턴 |
| recommendations | list[string] | Yes | 개선 제안 사항 |
| created_at | datetime | Yes | 리포트 생성 시각 |

---

### 6. ExpertContent (전문가 콘텐츠)

자동 생성된 일본 부동산 전문가 콘텐츠.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string (UUID) | Yes | 고유 식별자 |
| topic | string | Yes | 콘텐츠 주제 (시장 동향, 투자 팁 등) |
| text_zh | string | Yes | 생성된 중국어 텍스트 |
| hashtags | list[string] | Yes | 자동 생성된 해시태그 |
| status | enum | Yes | `generated` → `queued` → `posted` |
| generated_at | datetime | Yes | 생성 시각 |
| queue_item_id | string | No | QueueItem.id 참조 |

**Validation Rules**:
- `text_zh`에 특정 매물 가격, 주소 등 실제 물건 정보가 포함되면 안 됨
- 주제는 오사카/간사이 지역 중심이어야 함

## Relationships

```
QueueItem ──→ Post (발행 성공 시)
CompetitorAccount ──→ CompetitorPost (1:N)
Post ──→ PerformanceMetric (1:N, 시계열)
ExpertContent ──→ QueueItem (1:1, 발행 시)
BenchmarkReport ──→ CompetitorPost (참조)
```

## Storage Layout

```
data/
├── publish_queue.json       # QueueItem 목록 (활성 대기열)
├── competitors.json         # CompetitorAccount 목록
├── competitors/             # CompetitorPost 데이터
│   └── YYYY-MM.jsonl       # 월별 수집 이력
├── metrics/                 # PerformanceMetric 데이터
│   └── YYYY-MM.jsonl       # 월별 성과 수집
├── reports/                 # BenchmarkReport 데이터
│   └── YYYY-WW.json        # 주간 벤치마킹 리포트
├── expert_content/          # ExpertContent 데이터
│   └── YYYY-MM.jsonl       # 월별 생성 이력
├── posts/                   # 기존 Post 데이터 (변경 없음)
├── history/                 # 기존 이력 데이터 (변경 없음)
└── weibo_cookies.json       # 기존 쿠키 (변경 없음)
```
