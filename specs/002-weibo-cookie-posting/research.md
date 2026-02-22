# Research: Weibo Cookie 기반 포스팅 전환

## Decision 1: m.weibo.cn 포스팅 API 엔드포인트

**Decision**: `POST https://m.weibo.cn/api/statuses/update` 사용

**Rationale**: 중국 개발자 커뮤니티(CSDN, GitHub, 掘金)에서 가장 널리
사용되는 방법. 공식 API(statuses/update.json)가 error 10014로 폐쇄된
이후 사실상 유일한 프로그래밍 포스팅 방법.

**Alternatives considered**:
- `statuses/share` (공식 API) — URL 필수, 해시태그 불가, 이미지 1장 제한. 부적합.
- Selenium/Playwright 직접 자동화 — 과도한 리소스, RPi에서 비실용적.
- OpenClaw 전체 파이프라인 — 기존 Python 봇 파이프라인 폐기 필요. 과도한 변경.

## Decision 2: 이미지 업로드 방식

**Decision**: `POST https://m.weibo.cn/api/statuses/uploadPic` (multipart/form-data)

**Rationale**: m.weibo.cn 모바일 웹에서 사용하는 내부 업로드 엔드포인트.
개별 이미지를 업로드하면 `pic_id` 문자열이 반환되며, 포스팅 시
`picIds` 파라미터에 쉼표 구분 문자열로 결합하여 전달.

**Alternatives considered**:
- `upload_pic.json` (공식 API) — OAuth access_token 필요, 공식 API 폐쇄와 동일 상황.
- Base64 인코딩 전송 — m.weibo.cn에서 지원하지 않음.

## Decision 3: XSRF 토큰 획득 방식

**Decision**: `GET https://m.weibo.cn/api/config` 에서 `data.st` 필드 추출

**Rationale**: 가장 간결하고 안정적인 방법. 동시에 로그인 상태(`data.login`)와
사용자 ID(`data.uid`)도 확인 가능하여 쿠키 유효성 검증에 활용.

**Alternatives considered**:
- compose 페이지 HTML 파싱 — 불필요한 HTML 다운로드, 정규식 의존.
- XSRF-TOKEN 쿠키에서 직접 추출 — 쿠키와 st가 항상 동기화되지 않을 수 있음.

## Decision 4: 쿠키 저장 형식

**Decision**: `data/weibo_cookies.json`에 JSON 형태로 저장

```json
{
  "cookies": {
    "SUB": "...",
    "SUBP": "...",
    "XSRF-TOKEN": "...",
    "SSOLoginState": "..."
  },
  "uid": "1234567890",
  "updated_at": "2026-02-22T10:30:00+09:00",
  "validated_at": "2026-02-22T10:30:00+09:00",
  "status": "valid"
}
```

**Rationale**: 기존 프로젝트의 JSON 파일 기반 저장 패턴과 일관성 유지.
단일 사용자이므로 별도 DB 불필요(Constitution VI).
파일 권한 600으로 보안 확보(Constitution II).

**Alternatives considered**:
- .env 파일에 쿠키 저장 — 쿠키 문자열이 길고 여러 필드, JSON이 더 적합.
- SQLite — 과도한 설계(Constitution VI 위반).

## Decision 5: 해시태그 형식 변환

**Decision**: 기존 `#tag` 형식을 `#tag#` 형식으로 변환

**Rationale**: Weibo는 `#토픽#` (양쪽 #) 형식을 토픽으로 인식.
기존 `hashtag_generator.py`의 출력을 포맷팅 시점에서 변환하면 됨.
생성기 자체는 `#tag` 형태로 유지하고, weibo_client에서 포스팅 전
`#tag` → `#tag#`로 변환.

**Alternatives considered**:
- 해시태그 생성기 자체를 `#tag#` 출력으로 변경 — Telegram 미리보기에서
  불필요한 이중 # 표시. 생성기는 범용 유지가 좋음.

## Decision 6: OpenClaw 쿠키 갱신 연동 방식

**Decision**: OpenClaw REST API (port 18789) + Custom Skill (SKILL.md)

**Rationale**: OpenClaw는 이미 시스템에 설치되어 있고 CDP 브라우저
자동화를 지원. Custom Skill로 "Weibo 로그인 후 쿠키 추출" 동작을
정의하면, Python 봇에서 HTTP 호출 한 번으로 쿠키 갱신을 트리거 가능.

**Alternatives considered**:
- Playwright/Puppeteer 직접 실행 — RPi에 추가 의존성 설치 필요, 메모리 부담.
- 수동 갱신만 지원 — 운영 편의성 저하, 하지만 US3는 P3이므로 MVP에서는 수동만 가능.

## Decision 7: 게시물 URL 구성

**Decision**: 응답의 `bid` 필드로 `https://m.weibo.cn/detail/{bid}` 생성

**Rationale**: Weibo는 Base62 인코딩된 `bid`를 사용하여 짧은 URL 생성.
`id`(numeric)도 사용 가능하지만 `bid`가 더 짧고 일관적.
기존 `weibo_client.py`의 `_extract_url`은 `idstr`을 사용했으나,
m.weibo.cn API 응답에는 `bid`가 반환됨.

**Alternatives considered**:
- `https://weibo.com/{uid}/{bid}` (데스크톱 URL) — uid 추가 필요, 모바일 URL이 더 범용적.
- `id` 기반 URL — 숫자가 길어 URL이 비실용적.

## Decision 8: 기존 코드 변경 범위

**Decision**: 최소 변경 원칙 — weibo_client.py 재작성, config.py/main.py/telegram_handler.py 수정, weibo_oauth.py 삭제, cookie_manager.py 신규

**Rationale**:
- `weibo_client.py`: 동일 파일명 유지 → `WeiboClient` 클래스의 공개 인터페이스
  (`upload_image`, `create_post`, `create_text_post`)를 유지하여 main.py 변경 최소화.
- `config.py`: WEIBO_APP_KEY, WEIBO_APP_SECRET, WEIBO_ACCESS_TOKEN, WEIBO_REDIRECT_URI
  4개 환경변수 제거. 쿠키는 파일 기반이므로 환경변수 불필요.
- `main.py`: WeiboClient 초기화 시 access_token 대신 cookie_manager 전달.
- `telegram_handler.py`: `/cookie`, `/status` 명령어 핸들러 추가.
- `hashtag_generator.py`: 변경 불필요 — 해시태그 변환은 weibo_client에서 처리.

**Alternatives considered**:
- 별도 파일명으로 새 클라이언트 생성 — import 변경이 더 많아짐.
- main.py에 쿠키 로직 직접 추가 — 관심사 분리 위반.
