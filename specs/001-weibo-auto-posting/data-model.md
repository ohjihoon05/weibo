# Data Model: Weibo 부동산 자동 포스팅 시스템

**Date**: 2026-02-22
**Branch**: `001-weibo-auto-posting`

## Entity: PropertyListing (매물)

부동산 매물 정보의 핵심 데이터 단위.
사용자가 Telegram으로 입력한 원문에서 AI가 추출·구조화한 결과.

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string (UUID) | Yes | 고유 식별자 |
| name | string | No | 物件名称 (매물명) |
| location | string | No | 所在地 (도도부현/시구정촌) |
| price_jpy | integer | No | 가격 (엔화, 단위: 원) |
| price_cny | float | No | 가격 (위안화 환산) |
| exchange_rate | float | No | 환산 시 적용된 환율 |
| exchange_rate_date | datetime | No | 환율 기준 일시 |
| area_sqm | float | No | 면적 (제곱미터) |
| area_tsubo | float | No | 면적 (坪) |
| layout | string | No | 間取り (1LDK, 2LDK 등) |
| year_built | integer | No | 건축년도 |
| structure | string | No | 구조 (RC/SRC/木造/철골) |
| nearest_station | string | No | 최근역 + 도보 시간 |
| management_fee | integer | No | 관리비 (월, 엔화) |
| repair_reserve | integer | No | 수선적립금 (월, 엔화) |
| yield_gross | float | No | 표면이율 (%) |
| yield_net | float | No | 실질이율 (%) |
| occupancy_status | string | No | 현황 (공실/입주중) |
| ownership_type | string | No | 소유권 형태 (所有権/借地権) |
| land_area_sqm | float | No | 토지면적 (일호건물) |
| highlights | string | No | 특징/매력 포인트 |
| contact_info | string | No | 연락처 |
| original_text | string | Yes | 사용자 입력 원문 |
| original_language | string | Yes | 감지된 입력 언어 (ja/zh/ko) |
| created_at | datetime | Yes | 생성 일시 |

### Validation Rules
- `price_jpy`가 존재하면 `price_cny`, `exchange_rate`,
  `exchange_rate_date`가 자동 생성된다.
- `area_sqm`과 `area_tsubo`는 상호 환산 가능 (1坪 ≈ 3.306㎡).
- 모든 필드가 optional인 이유: 자유 형식 입력에서 AI가 추출 가능한
  항목만 채우고, 나머지는 빈칸으로 미리보기에 표시.

---

## Entity: Post (포스팅)

Weibo에 게시할/게시된 하나의 게시물.
PropertyListing + 이미지 + 해시태그를 조합한 최종 산출물.

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string (UUID) | Yes | 고유 식별자 |
| listing_id | string (UUID) | Yes | 연결된 PropertyListing ID |
| formatted_text | string | Yes | 포맷팅된 중국어 게시물 본문 |
| hashtags | list[string] | Yes | 자동 생성된 해시태그 목록 |
| image_paths | list[string] | Yes | 처리된 이미지 로컬 경로 (0~9장) |
| status | enum | Yes | 포스팅 상태 |
| mode | enum | Yes | 포스팅 모드 |
| weibo_post_id | string | No | Weibo 게시물 ID (게시 후) |
| weibo_url | string | No | Weibo 게시물 URL (게시 후) |
| telegram_chat_id | integer | Yes | 요청한 Telegram 채팅 ID |
| telegram_message_id | integer | No | 미리보기 메시지 ID |
| created_at | datetime | Yes | 생성 일시 |
| posted_at | datetime | No | 실제 게시 일시 |

### Status Values
| Value | Description |
|-------|-------------|
| `pending_translation` | AI 번역/포맷팅 대기 중 |
| `pending_approval` | 미리보기 전송됨, 사용자 승인 대기 |
| `approved` | 사용자 승인됨, 포스팅 대기 |
| `posting` | Weibo 포스팅 진행 중 |
| `posted` | 포스팅 완료 |
| `failed` | 최종 실패 (재시도 소진) |

### Mode Values
| Value | Description |
|-------|-------------|
| `preview` | 미리보기 모드 (기본) |
| `auto` | 즉시 포스팅 모드 |

### State Transitions
```
pending_translation → pending_approval (미리보기 모드)
pending_translation → approved (자동 모드)
pending_approval → approved (사용자 "포스팅" 클릭)
pending_approval → pending_translation (사용자 "수정 요청" 클릭)
approved → posting
posting → posted (성공)
posting → posting (재시도 중, retry_count < 3)
posting → failed (재시도 소진)
```

---

## Entity: PostHistory (포스팅 이력)

모든 포스팅 시도의 감사 로그.
성공/실패 여부와 관계없이 모든 시도를 기록.

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string (UUID) | Yes | 고유 식별자 |
| post_id | string (UUID) | Yes | 연결된 Post ID |
| attempt_number | integer | Yes | 시도 번호 (1~3) |
| action | enum | Yes | 수행한 작업 |
| success | boolean | Yes | 성공 여부 |
| error_message | string | No | 실패 시 에러 메시지 |
| error_code | string | No | API 에러 코드 |
| weibo_response | string | No | Weibo API 응답 원문 |
| timestamp | datetime | Yes | 시도 일시 |

### Action Values
| Value | Description |
|-------|-------------|
| `translate` | AI 번역 수행 |
| `upload_image` | Weibo 이미지 업로드 |
| `create_post` | Weibo 게시물 생성 |

---

## Entity: ExchangeRateCache (환율 캐시)

환율 조회 결과의 로컬 캐시. API 장애 시 fallback으로 사용.

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| base_currency | string | Yes | 원본 통화 (JPY) |
| target_currency | string | Yes | 목표 통화 (CNY) |
| rate | float | Yes | 환율 |
| source | string | Yes | 데이터 소스 (exchangerate-api/frankfurter) |
| fetched_at | datetime | Yes | 조회 일시 |

---

## Relationships

```
PropertyListing 1 ←→ 1 Post
Post 1 ←→ N PostHistory
ExchangeRateCache (독립, 참조용)
```

## Storage Strategy

Constitution 원칙 VI(Simplicity)에 따라 데이터베이스를 사용하지 않는다.

- **PropertyListing + Post**: JSON 파일로 로컬 저장
  (`data/posts/YYYY-MM-DD_{id}.json`).
- **PostHistory**: JSON Lines 파일로 append-only 저장
  (`data/history/YYYY-MM.jsonl`).
- **ExchangeRateCache**: 단일 JSON 파일
  (`data/exchange_rate.json`).
- **이미지**: 원본과 처리 후 이미지를 임시 디렉토리에 저장,
  포스팅 완료 후 정리 가능.
