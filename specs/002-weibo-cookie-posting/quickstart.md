# Quickstart: Weibo Cookie 기반 포스팅 전환

## Prerequisites

- 기존 spec 001 구현이 완료된 상태 (Python 3.13, 모든 의존성 설치됨)
- Weibo 계정 보유 (m.weibo.cn에 로그인 가능)
- 브라우저 접근 가능 (최초 쿠키 획득용)

## Setup

### 1. 쿠키 획득 (최초 1회, 수동)

1. 브라우저에서 `https://m.weibo.cn` 접속 후 로그인
2. DevTools (F12) → Network 탭
3. 아무 요청의 `Cookie` 헤더 복사
4. Telegram에서 봇에 `/cookie <복사한 쿠키 문자열>` 전송
5. 봇이 "쿠키 설정 완료" 응답 확인

### 2. 쿠키 유효성 확인

```
/status
```

→ 로그인 상태, uid, 쿠키 갱신 시각 표시

### 3. 테스트 포스팅

기존과 동일하게 Telegram에 매물 정보 + 사진 전송.
미리보기 모드에서 확인 후 "포스팅" 버튼 클릭.

## Integration Scenarios

### Scenario 1: 정상 포스팅 (US1)

```
Input: Telegram 매물 사진 + 텍스트
Expected:
  1. 번역 + 포맷팅 (기존과 동일)
  2. /api/config 호출 → st 토큰 + 로그인 확인
  3. 이미지 개별 업로드 → pic_id 수집
  4. /api/statuses/update 호출 → bid 반환
  5. Telegram에 https://m.weibo.cn/detail/{bid} 전송
```

### Scenario 2: 쿠키 만료 시 (US1 + US2)

```
Input: 포스팅 시도
Expected:
  1. /api/config 호출 → login=false 감지
  2. Telegram에 "쿠키가 만료되었습니다. /cookie 명령어로 갱신해주세요." 전송
  3. 사용자가 /cookie <새 쿠키> 전송
  4. 쿠키 파싱 + 저장 + 검증
  5. 포스팅 재시도
```

### Scenario 3: /cookie 명령어 (US2)

```
Input: /cookie SUB=xxx; SUBP=yyy; XSRF-TOKEN=zzz; ...
Expected:
  1. 쿠키 문자열 파싱 → SUB, SUBP, XSRF-TOKEN 추출
  2. data/weibo_cookies.json에 저장 (권한 600)
  3. /api/config 호출하여 유효성 검증
  4. "쿠키 설정 완료. 유효합니다. (uid: 1234567890)" 응답
```

### Scenario 4: /status 명령어 (US2)

```
Input: /status
Expected:
  쿠키가 있는 경우:
    "🔑 Weibo 쿠키 상태: ✅ 유효
     👤 UID: 1234567890
     🕐 갱신: 2026-02-22 10:30:00"

  쿠키가 없는 경우:
    "⚠️ Weibo 쿠키가 설정되지 않았습니다.
     /cookie <쿠키문자열> 명령어로 설정해주세요."
```

### Scenario 5: 중복 게시물 감지 (US1)

```
Input: 직전과 동일한 텍스트로 포스팅
Expected:
  미리보기 모드: "⚠️ 직전 게시물과 동일한 내용입니다." 경고 표시
  자동 모드: 타임스탬프 접미사 자동 추가 후 포스팅
```

## Verification

```bash
# 봇 실행 (Docker)
docker compose up -d

# 로그 확인
docker compose logs -f weibo-bot

# 쿠키 파일 확인
cat data/weibo_cookies.json

# 포스팅 이력 확인
ls -la data/history/
```
