# Research: OpenClaw 기반 Weibo 마케팅 자동화

**Feature**: 003-openclaw-marketing-auto
**Date**: 2026-02-22

## 1. OpenClaw Telegram 통합

### Decision: OpenClaw Skills + 기존 python-telegram-bot 병행

### Rationale
- OpenClaw은 `SKILL.md` 기반 스킬 시스템으로 외부 스크립트 호출 가능
- 기존 python-telegram-bot을 유지하면서 OpenClaw을 AI 오버레이로 추가
- OpenClaw은 Telegram grammY 라이브러리 사용, `openclaw.json`으로 설정
- MCP(Model Context Protocol) 또는 localhost HTTP API로 기존 봇과 연동

### Integration Pattern
- 기존 봇에 경량 HTTP API 엔드포인트 추가 (localhost:5000)
- OpenClaw 스킬이 `curl`로 localhost API 호출
- 또는 MCP 서버로 Python 스크립트 직접 연결
- Workspace skills (`<project>/skills/`)가 최우선 로드

### Alternatives Rejected
- **OpenClaw만 사용 (기존 봇 제거)**: 기존 파이프라인이 이미 안정적이므로 리스크 높음
- **MCP만 사용**: 프로토콜 구현 복잡도 대비 이점 부족
- **Webhook**: 공개 URL 필요, Raspberry Pi에서 추가 설정 부담

### Risks
- OpenClaw 프로젝트 안정성 (창립자 OpenAI 합류, 재단 이관 예정)
- Node.js Gateway가 Raspberry Pi 메모리 추가 사용 (~100-200MB)
- → 완화: 기존 봇을 primary로 유지, OpenClaw은 optional enhancement

---

## 2. Weibo 경쟁 계정 스크래핑

### Decision: m.weibo.cn 모바일 웹 API 활용

### Rationale
- 기존 `weibo_client.py`와 동일한 API 체계 (m.weibo.cn)
- 인증 없이 공개 프로필 접근 가능 (쿠키 사용 시 안정성 향상)
- JSON 응답으로 파싱 용이

### Key Endpoints
| 용도 | Endpoint | 파라미터 |
|------|----------|---------|
| 사용자 타임라인 | `/api/container/getIndex` | `type=uid&value={uid}&containerid=107603{uid}&page={n}` |
| 포스트 상세 | `/statuses/show` | `id={mid_or_bid}` |
| 사용자 검색 | `/api/container/getIndex` | `containerid=100103type=3&q={keyword}&page={n}` |
| 댓글 조회 | `/api/comments/show` | `id={status_mid}&page={n}` |

### Rate Limits
- 쿠키 있을 때: 분당 ~20-30 요청
- 안전 임계: 요청 간 3-5초 딜레이, 일 ~500회
- → 경쟁 계정 5개 × 주 1회 = 매우 여유로운 사용량

### Alternatives Rejected
- **공식 Weibo Open API**: 승인 절차 필요, 검색 API 제한 (1000+ 사용자 앱 필요)
- **서드파티 서비스 (Piloterr, BrightData)**: 월 비용 발생, 외부 의존성
- **weibo-scraper PyPI**: 미유지보수, 제한된 기능

---

## 3. 자체 포스트 성과 데이터 수집

### Decision: m.weibo.cn statuses/show API + 주기적 수집

### Rationale
- 기존 `weibo_client.py`가 이미 `bid`를 반환하므로 추적 가능
- `statuses/show?id={bid}` → `reposts_count`, `comments_count`, `attitudes_count`
- 기존 `job_queue` 인프라 활용하여 2-4시간 간격 수집

### Data Fields
- `reposts_count` (공유), `comments_count` (댓글), `attitudes_count` (좋아요)
- `reads_count` (조회수): 일부 계정에서만 제공, 테스트 필요
- → 조회수 미지원 시 좋아요+댓글+공유를 인게이지먼트 지표로 사용

### Storage Pattern
- `data/metrics/YYYY-MM.jsonl` (기존 history와 동일 패턴)
- 포스트 발행 후 2시간, 24시간, 7일 시점에 수집

### Alternatives Rejected
- **Weibo 데이터 센터 (数据中心)**: 브라우저 자동화 필요, 과도한 복잡도
- **서드파티 분석 서비스**: 외부 의존성, 비용
- **Weibo Open API statuses/count**: 승인된 앱 필요

---

## 4. JSON 파일 기반 발행 대기열

### Decision: Atomic Write + fcntl 파일 잠금

### Rationale
- 기존 `json_store.py`와 일관된 패턴
- 추가 의존성 없음 (Python 표준 라이브러리)
- Raspberry Pi 단일 프로세스 환경에 적합
- `os.rename()` POSIX 원자성으로 크래시 안전성 확보

### Pattern
- `data/publish_queue.json`: 단일 JSON 파일
- `fcntl.flock`으로 advisory locking
- `tempfile` + `os.rename`으로 atomic write
- 상태: pending → processing → completed/failed
- 시작 시 `recover_stale_processing()`으로 크래시 복구

### Alternatives Rejected
- **persist-queue (PyPI)**: 하드 리셋 시 파일 손상 이슈 보고됨
- **SQLite (litequeue)**: 현재 볼륨(일 1-2건)에 과도한 오버헤드
- **Redis**: Raspberry Pi에 추가 서비스 부담, Constitution VI 위반
- **Python queue.Queue**: 비영속적, 재시작 시 손실
