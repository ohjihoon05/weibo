# OpenClaw Skills Contract

**Feature**: 003-openclaw-marketing-auto

## Skill: weibo-queue (발행 대기열 관리)

### Commands
| Trigger | Action | Response |
|---------|--------|----------|
| "대기열 확인" / "queue status" | 대기 중인 콘텐츠 목록 조회 | 대기열 항목 목록 + 예정 시간 |
| "지금 발행" / "post now" | 대기열 최우선 항목 즉시 발행 | 발행 결과 (성공 URL 또는 에러) |
| "일정 변경" / "reschedule" | 대기열 항목 발행 시간 변경 | 변경 확인 |
| "대기열 삭제 {id}" | 특정 항목 대기열에서 제거 | 삭제 확인 |

### Localhost API (기존 봇 확장)
```
POST /api/queue/enqueue     → 콘텐츠 대기열 추가
GET  /api/queue/status       → 대기열 상태 조회
POST /api/queue/publish-now  → 즉시 발행
DELETE /api/queue/{id}       → 항목 제거
```

---

## Skill: weibo-benchmark (경쟁 벤치마킹)

### Commands
| Trigger | Action | Response |
|---------|--------|----------|
| "경쟁 계정 추가 {uid}" | 벤치마킹 대상 등록 | 등록 확인 + 계정 정보 |
| "경쟁 계정 목록" | 등록된 계정 조회 | 계정 목록 + 상태 |
| "경쟁 분석" / "benchmark" | 벤치마킹 리포트 요청 | 최근 주간 리포트 |
| "유사 계정 검색" | Weibo에서 일본 부동산 계정 검색 | 추천 계정 목록 |

### Localhost API
```
POST /api/competitors/add     → 경쟁 계정 추가
GET  /api/competitors/list    → 경쟁 계정 목록
GET  /api/benchmark/latest    → 최근 벤치마킹 리포트
POST /api/competitors/search  → 유사 계정 검색
```

---

## Skill: weibo-analytics (성과 분석)

### Commands
| Trigger | Action | Response |
|---------|--------|----------|
| "주간 리포트" / "weekly report" | 주간 성과 리포트 조회 | 발행 요약 + 포스트별 성과 |
| "최적 시간" / "best time" | 최적 발행 시간 분석 | 시간대별 평균 인게이지먼트 |
| "성과 확인 {bid}" | 특정 포스트 성과 조회 | 조회수/좋아요/댓글/공유 |

### Localhost API
```
GET /api/analytics/weekly      → 주간 성과 리포트
GET /api/analytics/best-time   → 최적 발행 시간 분석
GET /api/analytics/post/{bid}  → 포스트별 성과
```

---

## Skill: weibo-expert (전문가 콘텐츠)

### Commands
| Trigger | Action | Response |
|---------|--------|----------|
| "전문가 글 생성" / "generate expert" | 즉시 전문가 콘텐츠 생성 | 미리보기 텍스트 + 발행 확인 버튼 |
| "전문가 주제 목록" | 생성 가능한 주제 카테고리 조회 | 주제 목록 |

### Localhost API
```
POST /api/expert/generate  → 전문가 콘텐츠 생성
GET  /api/expert/topics    → 주제 목록 조회
```
