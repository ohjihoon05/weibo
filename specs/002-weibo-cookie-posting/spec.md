# Feature Specification: Weibo Cookie 기반 포스팅 전환

**Feature Branch**: `002-weibo-cookie-posting`
**Created**: 2026-02-22
**Status**: Draft
**Input**: User description: "Weibo 공식 API(statuses/update, statuses/upload)가 error 10014로 사실상 중단됨. m.weibo.cn 모바일 웹 API(쿠키 기반)로 포스팅 방식을 전환하고, OpenClaw 브라우저 자동화로 쿠키 취득/갱신을 자동화한다."

## Context

기존 spec 001에서 구현된 Weibo 포스팅 파이프라인은 Weibo Open Platform
공식 API(`statuses/update`, `statuses/upload`)를 사용하도록 설계되었으나,
2026년 현재 해당 엔드포인트들은 error 10014를 반환하며 사실상 폐쇄되었다.

중국 개발자 커뮤니티에서 검증된 대안은 **m.weibo.cn 모바일 웹 API**로,
쿠키 인증 기반으로 텍스트+다중 이미지 포스팅을 지원한다. 이 방식은
해시태그, 최대 9장 이미지 업로드를 모두 지원하며 기존 파이프라인의
모든 요구사항을 충족한다.

쿠키는 주기적 갱신이 필요하므로, 시스템에 이미 설치된 OpenClaw(v2026.1.30)의
브라우저 자동화(CDP) 기능을 활용하여 쿠키 취득 및 자동 갱신을 처리한다.

## Clarifications

### Session 2026-02-22

- Q: m.weibo.cn 이미지 업로드의 구체적 엔드포인트와 응답 형식은? → A: `POST /api/statuses/uploadPic` (multipart/form-data), 응답에서 `pic_id` 문자열 반환. 포스팅 시 `picIds` 파라미터에 쉼표 구분 문자열로 전달.
- Q: 쿠키 입력 방식 — Telegram 명령어 vs 파일 편집? → A: Telegram `/cookie` 명령어를 주 입력 방식으로 채택 (RPi 단일 운영자 환경에서 SSH 불필요). 파일 직접 편집(`data/weibo_cookies.json`)은 대안으로 유지.
- Q: Weibo 동일 텍스트 연속 게시 거부 정책에 대한 처리는? → A: Weibo는 동일 텍스트 연속 포스팅을 거부함. 시스템이 직전 게시물 내용과 비교하여 동일 시 경고 후 타임스탬프 접미사를 자동 추가.
- Q: 쿠키 파일 보안 처리 수준은? → A: 파일 권한 600(소유자만 읽기/쓰기), 로그 출력 시 쿠키 값 마스킹 의무화. 단일 사용자 RPi 환경이므로 암호화는 불필요(Constitution VI 준수).
- Q: 기존 weibo_oauth.py 모듈의 처리 방침은? → A: 공식 API 폐쇄로 OAuth 플로우가 무의미하므로 weibo_oauth.py를 제거한다. FR-008 범위를 weibo_client.py + weibo_oauth.py 양쪽 교체/제거로 확장.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - m.weibo.cn API로 Weibo 포스팅 (Priority: P1)

기존 파이프라인에서 Weibo 공식 API 호출 부분을 m.weibo.cn 모바일 웹 API로
교체하여, 사용자가 Telegram에서 매물 정보를 전송하면 실제로 Weibo에
게시물이 올라가도록 한다.

**Why this priority**: 현재 시스템의 Weibo 포스팅 기능이 완전히 동작하지
않으므로, 이 기능이 복구되지 않으면 전체 시스템의 핵심 가치가 없다.

**Independent Test**: 유효한 Weibo 쿠키를 수동으로 설정한 후,
텍스트+이미지를 m.weibo.cn API로 포스팅하여 Weibo 피드에 게시물이
나타나는지 확인한다.

**Acceptance Scenarios**:

1. **Given** 유효한 Weibo 쿠키가 시스템에 저장되어 있고 매물 정보가 준비된 상태,
   **When** 파이프라인이 Weibo 포스팅을 실행,
   **Then** m.weibo.cn API를 통해 텍스트+이미지가 게시되고 게시물 URL이 반환된다.

2. **Given** 이미지 3장과 해시태그가 포함된 매물 게시물,
   **When** m.weibo.cn API로 포스팅,
   **Then** 모든 이미지가 개별 업로드되어 `pic_id`를 획득하고,
   해시태그(`#topic#` 형식)가 게시물에 포함된다.

3. **Given** 쿠키가 만료된 상태,
   **When** 포스팅을 시도,
   **Then** 쿠키 만료 에러가 감지되고 사용자에게 쿠키 갱신이 필요하다는
   알림이 Telegram으로 전송된다.

4. **Given** 직전 게시물과 동일한 텍스트로 포스팅을 시도,
   **When** 중복 감지 로직이 실행,
   **Then** 사용자에게 중복 경고를 표시하고, 자동 모드에서는 타임스탬프
   접미사를 추가하여 포스팅한다.

---

### User Story 2 - 쿠키 설정 및 유효성 검증 (Priority: P2)

사용자가 Telegram `/cookie` 명령어로 Weibo 쿠키를 시스템에 설정하고,
시스템이 쿠키의 유효성을 자동 검증한다.

**Why this priority**: 자동 쿠키 갱신(US3) 이전에 수동으로라도
쿠키를 설정하여 시스템이 동작할 수 있어야 한다. 이것이 최소한의
운영 가능 상태이다.

**Independent Test**: 브라우저에서 Weibo 쿠키를 복사하여 Telegram
`/cookie` 명령어로 입력하고, `/status` 명령어로 쿠키 유효성이
확인되는지 테스트한다.

**Acceptance Scenarios**:

1. **Given** 사용자가 브라우저에서 Weibo 로그인 후 쿠키 문자열을 복사,
   **When** Telegram에서 `/cookie <쿠키문자열>` 명령어를 전송,
   **Then** 시스템이 쿠키를 파싱하여 `data/weibo_cookies.json`에 저장하고
   유효성 검증 결과를 응답한다.

2. **Given** 저장된 쿠키가 있는 상태,
   **When** 사용자가 `/status` 명령어를 실행하거나 시스템이 포스팅 전 검증,
   **Then** m.weibo.cn `/api/config` 엔드포인트를 호출하여 쿠키 유효 여부와
   로그인된 사용자 정보를 표시한다.

3. **Given** 유효하지 않은 쿠키가 설정된 상태,
   **When** 쿠키 유효성 검증을 수행,
   **Then** "쿠키가 만료되었거나 유효하지 않습니다"라는 메시지와 함께
   갱신 방법을 안내한다.

4. **Given** 사용자가 파일을 직접 편집하여 쿠키를 설정 (대안 방식),
   **When** 시스템이 다음 포스팅 또는 `/status` 실행 시 파일을 로드,
   **Then** 파일에서 쿠키를 정상적으로 로드하고 검증한다.

---

### User Story 3 - OpenClaw 자동 쿠키 갱신 (Priority: P3)

OpenClaw의 브라우저 자동화(CDP) 기능을 활용하여 Weibo 쿠키를
자동으로 취득하고 주기적으로 갱신한다. 사용자가 수동으로 쿠키를
관리할 필요가 없어진다.

**Why this priority**: 쿠키 수동 갱신은 번거롭지만 시스템 동작에는
지장이 없다(US2로 커버). 자동화는 운영 편의성 향상이므로 P3이다.

**Independent Test**: OpenClaw에 쿠키 갱신 스킬을 설정한 후,
쿠키가 만료 임박 상태일 때 자동으로 갱신되는지 확인한다.

**Acceptance Scenarios**:

1. **Given** OpenClaw가 실행 중이고 Weibo 계정 자격증명이 설정된 상태,
   **When** 시스템이 쿠키 갱신을 요청,
   **Then** OpenClaw가 브라우저를 자동으로 열어 Weibo에 로그인하고
   새 쿠키를 추출하여 시스템에 저장한다.

2. **Given** 저장된 쿠키의 남은 유효기간이 임계값(24시간) 이하,
   **When** 시스템이 주기적 검증을 수행,
   **Then** 자동으로 쿠키 갱신 프로세스를 트리거한다.

3. **Given** OpenClaw가 실행되지 않거나 자동 갱신에 실패,
   **When** 쿠키 갱신이 실패,
   **Then** 사용자에게 Telegram으로 수동 쿠키 갱신이 필요하다는
   알림을 전송하고 수동 갱신 방법을 안내한다.

---

### Edge Cases

- 쿠키에 포함된 XSRF 토큰(`st`)이 요청 중간에 만료되면 어떻게 되는가?
  → `st` 토큰은 약 15~20분마다 갱신된다. 포스팅 직전에 `/api/config`를
  호출하여 최신 `st` 토큰을 항상 가져온다.
- m.weibo.cn API가 rate limit을 적용하면 어떻게 되는가?
  → 하루 1~3건 포스팅이므로 현실적으로 rate limit에 도달하지 않으나,
  429 응답 시 지수 백오프 재시도를 수행한다.
- 이미지 업로드 시 m.weibo.cn이 특정 형식만 허용하면 어떻게 되는가?
  → 기존 이미지 프로세서(JPEG 변환, 리사이즈)를 재활용하여 호환성을 보장한다.
  이미지당 5MB 제한을 준수한다.
- OpenClaw가 브라우저 자동화 중 CAPTCHA를 만나면 어떻게 되는가?
  → 자동 갱신 실패로 처리하고, 사용자에게 수동 로그인 후 쿠키 설정을 안내한다.
- 쿠키 파일이 손상되거나 파싱 불가능한 상태이면 어떻게 되는가?
  → 파싱 실패 시 기존 쿠키를 백업하고 사용자에게 재설정을 요청한다.
- Weibo 계정이 잠기거나 제한되면 어떻게 되는가?
  → API 응답에서 계정 상태 에러를 감지하고 사용자에게 알린다.
- 직전 게시물과 동일한 텍스트로 포스팅하면 어떻게 되는가?
  → Weibo는 동일 텍스트 연속 게시를 거부한다. 시스템이 직전 게시물
  내용을 비교하여 동일 시 미리보기 모드에서는 사용자에게 경고하고,
  자동 모드에서는 타임스탬프 접미사를 추가하여 중복을 회피한다.
- 새 디바이스에서 Weibo 로그인 시 추가 인증(SMS/메시지 인증)이
  요구되면 어떻게 되는가?
  → OpenClaw 자동 갱신 실패로 처리하고, 사용자에게 브라우저에서
  수동 로그인 후 `/cookie` 명령어로 쿠키를 재설정하도록 안내한다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 시스템은 m.weibo.cn 모바일 웹 API(`POST /api/statuses/update`,
  `application/x-www-form-urlencoded`)를 통해 텍스트+이미지 게시물을
  포스팅할 수 있어야 한다. 필수 파라미터: `content`, `st`, `picIds`(이미지 시).
- **FR-002**: 시스템은 m.weibo.cn 이미지 업로드 엔드포인트
  (`POST /api/statuses/uploadPic`, `multipart/form-data`)를 통해 이미지를
  업로드하고 응답에서 `pic_id` 문자열을 획득할 수 있어야 한다.
  다중 이미지는 개별 업로드 후 `picIds`를 쉼표 구분 문자열로 결합한다.
- **FR-003**: 시스템은 포스팅 전 `GET /api/config` 엔드포인트를 호출하여
  XSRF 토큰(`st`)을 획득하고 `X-XSRF-TOKEN` 헤더와 요청 본문에 모두
  포함해야 한다. `st` 토큰은 약 15~20분마다 만료되므로 매 요청 전 갱신한다.
- **FR-004**: 시스템은 Weibo 쿠키를 로컬 파일(`data/weibo_cookies.json`)에
  저장하고 로드할 수 있어야 한다. 쿠키 파일은 파일 권한 600(소유자만
  읽기/쓰기)으로 생성한다.
- **FR-005**: 시스템은 쿠키 유효성을 `/api/config` 응답의 `data.login`
  필드로 검증할 수 있어야 한다. 필수 쿠키 필드: SUB, SUBP, XSRF-TOKEN.
- **FR-006**: 시스템은 쿠키 만료 또는 인증 실패 시 명확한 에러 메시지를
  사용자에게 전달해야 한다.
- **FR-007**: 시스템은 해시태그를 `#topic#` 형식으로 게시물 본문에 포함하여
  Weibo 토픽으로 인식되게 해야 한다.
- **FR-008**: 시스템은 기존 파이프라인(Telegram 수신 → 번역 → 포스팅)의
  `weibo_client.py`를 m.weibo.cn 쿠키 기반 클라이언트로 교체하고,
  `weibo_oauth.py`를 제거한다. 나머지 파이프라인 모듈은 변경하지 않는다.
- **FR-009**: 시스템은 OpenClaw의 브라우저 자동화를 통해 Weibo 쿠키를
  자동으로 취득할 수 있어야 한다.
- **FR-010**: 시스템은 저장된 쿠키의 유효기간을 주기적으로 검증하고,
  만료 임박 시 자동 갱신을 트리거해야 한다.
- **FR-011**: 자동 쿠키 갱신 실패 시 사용자에게 Telegram으로 수동 갱신
  안내를 전송해야 한다.
- **FR-012**: 기존 재시도 로직(최대 3회, 지수 백오프)을 m.weibo.cn API
  에러에 맞게 적용해야 한다.
- **FR-013**: 포스팅 성공 시 응답의 `bid` 필드를 사용하여 Weibo 게시물 URL
  (`https://m.weibo.cn/detail/{bid}`)을 생성하여 Telegram으로 전송해야 한다.
- **FR-014**: 사용자가 Telegram `/cookie <쿠키문자열>` 명령어로 Weibo 쿠키를
  설정할 수 있어야 한다. 시스템은 쿠키 문자열을 파싱하여 필수 필드
  (SUB, SUBP, XSRF-TOKEN)를 추출하고 저장한다.
- **FR-015**: 시스템은 직전 게시물과 동일한 텍스트의 연속 포스팅을 감지해야
  한다. 미리보기 모드에서는 사용자에게 경고하고, 자동 모드에서는
  타임스탬프 접미사를 자동 추가하여 Weibo의 중복 거부를 회피한다.
- **FR-016**: 시스템은 m.weibo.cn API 호출 시 적절한 HTTP 헤더를 포함해야
  한다: `X-Requested-With: XMLHttpRequest`, `Referer: https://m.weibo.cn/compose/`,
  모바일 브라우저 `User-Agent`.
- **FR-017**: 시스템은 로그 출력 시 쿠키 값(SUB, SUBP 등)을 MUST 마스킹해야
  한다(Constitution II 준수).

### Key Entities

- **Weibo 쿠키(WeiboCookie)**: m.weibo.cn 인증에 필요한 쿠키 데이터.
  필수 속성: SUB, SUBP, XSRF-TOKEN.
  부가 속성: SSOLoginState, 만료 시간, 로그인 사용자 ID(uid).
  쿠키 파일(`data/weibo_cookies.json`)에 JSON 형태로 저장되며,
  유효성 검증 상태(valid/expired/unknown)를 가진다.
  파일 권한 600으로 보호한다.
- **XSRF 토큰(st)**: 매 API 호출 전 `/api/config`에서 획득하는
  보안 토큰. 요청 헤더(`X-XSRF-TOKEN`)와 본문(`st` 파라미터)에 모두
  포함되어야 한다. 유효기간 약 15~20분이므로 캐싱하지 않고 매번 새로 취득한다.
- **이미지 ID(pic_id)**: `/api/statuses/uploadPic` 응답에서 반환되는
  영문+숫자 문자열 식별자. 포스팅 시 `picIds` 파라미터에 쉼표 구분
  문자열로 전달하여 게시물에 이미지를 첨부한다.
- **게시물 ID(bid)**: 포스팅 성공 응답에서 반환되는 Base62 인코딩 식별자.
  게시물 URL 생성에 사용: `https://m.weibo.cn/detail/{bid}`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 유효한 쿠키가 설정된 상태에서 텍스트+이미지 게시물이
  Weibo에 성공적으로 게시되고 게시물 URL이 반환된다.
- **SC-002**: 최대 9장의 이미지가 한 게시물에 정상적으로 업로드된다.
- **SC-003**: 해시태그가 Weibo 토픽으로 정상 인식된다
  (게시물에서 해시태그 클릭 시 토픽 페이지로 이동).
- **SC-004**: 쿠키 만료 시 사용자가 5분 이내에 Telegram 알림을 받는다.
- **SC-005**: 기존 파이프라인(Telegram → 번역 → 미리보기 → 포스팅)의
  동작 흐름이 API 전환 후에도 동일하게 유지된다.
- **SC-006**: OpenClaw 자동 쿠키 갱신 성공률이 수동 개입 없이 90% 이상이다
  (CAPTCHA 등 예외 상황 제외).
- **SC-007**: Telegram `/cookie` 명령어로 쿠키 설정 후 즉시 포스팅이
  가능하다(검증 포함 1분 이내).

## Assumptions

- m.weibo.cn 모바일 웹 API는 2026년 현재 중국 개발자 커뮤니티에서
  널리 사용되고 있으며, Weibo가 즉시 차단할 가능성은 낮다.
- 라즈베리파이(일본)에서 m.weibo.cn에 직접 접근 가능하다
  (기존 research에서 Weibo API 접근 확인됨).
- OpenClaw(v2026.1.30)가 시스템에 설치되어 있고 port 18789에서
  서비스 중이다. CDP 브라우저 자동화 기능을 사용할 수 있다.
- Weibo SUB 세션 쿠키의 유효기간은 일반적으로 수일~수주이며,
  XSRF 토큰(`st`)은 약 15~20분마다 만료된다.
- 하루 1~3건의 포스팅 빈도에서는 m.weibo.cn의 rate limit(시간당 약 30건)에
  도달하지 않는다.
- 사용자는 Weibo 계정을 이미 보유하고 있으며,
  최초 1회는 브라우저에서 수동 로그인 후 `/cookie` 명령어로 설정이 필요하다.
- 이미지 업로드 크기 제한은 건당 5MB이며, 기존 이미지 프로세서가
  이를 충족하는 결과물을 생성한다.
