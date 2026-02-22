# Quickstart: Weibo 쿠키 자동 갱신 시스템

**Feature**: 005-cookie-auto-refresh
**Date**: 2026-02-23

## Verification Scenarios

### VS-1: 쿠키 나이 계산 (US1 기반)

**목적**: 쿠키 설정 후 경과 시간이 정확히 계산되는지 확인

```
1. 쿠키가 저장된 상태에서 CookieManager.get_cookie_age_hours() 호출
2. 반환값이 updated_at 기준 경과 시간(시간 단위)과 일치하는지 확인
3. updated_at이 없는 경우 None 또는 적절한 기본값 반환 확인
```

**Expected**: 경과 시간이 시간 단위 float로 반환됨

### VS-2: 만료 임박 경고 알림 (US1 기반)

**목적**: 쿠키가 유효하지만 오래되었을 때 경고 알림이 전송되는지 확인

```
1. 쿠키 updated_at을 현재 시각 - 40시간으로 설정
2. cookie_validation_job 실행
3. Telegram 경고 알림 전송 확인 (⏰ 이모지, 경과 시간 표시)
4. 다시 즉시 실행 → 24시간 이내 중복 경고 미전송 확인
```

**Expected**: 첫 실행에서만 경고 알림 1회 전송, 두 번째는 중복 방지로 스킵

### VS-3: 쿠키 만료 시 CookieCloud 자동 갱신 (US2 기반)

**목적**: 만료된 쿠키가 CookieCloud에서 자동 갱신되는지 확인

```
1. .env에 COOKIECLOUD_SERVER, COOKIECLOUD_UUID, COOKIECLOUD_PASSWORD 설정
2. CookieCloud 서버에 유효한 Weibo 쿠키가 동기화된 상태
3. 로컬 쿠키를 만료 상태로 설정
4. cookie_validation_job 실행
5. CookieCloud에서 쿠키를 가져와 갱신 → Telegram 성공 알림 확인
```

**Expected**: 쿠키가 자동 갱신되고 "🔄 CookieCloud에서 쿠키가 갱신되었습니다" 알림 수신

### VS-4: CookieCloud 미설정 시 폴백 (US1+US2 기반)

**목적**: CookieCloud 없이도 알림이 정상 동작하는지 확인

```
1. .env에 COOKIECLOUD_* 변수 미설정
2. 쿠키를 만료 상태로 설정
3. cookie_validation_job 실행
4. CookieCloud 시도 없이 즉시 수동 갱신 안내 알림 확인
```

**Expected**: CookieCloud 관련 에러 없이 "⚠️ 쿠키가 만료되었습니다. /cookie 명령어로..." 알림 전송

### VS-5: 깨진 코드 제거 확인 (US3 기반)

**목적**: 존재하지 않는 외부 서비스 호출이 제거되었는지 확인

```
1. CookieManager에서 refresh_cookies_via_openclaw() 메서드 부재 확인
2. 쿠키 만료 시 cookie_validation_job이 더 이상 localhost:18789/api/tasks 호출하지 않음
3. 60초 타임아웃 대기 없이 즉시 다음 단계로 진행
```

**Expected**: 코드에서 OpenClaw 관련 참조 완전 제거

### VS-6: CookieCloud 연결 실패 시 graceful 처리 (US2 기반)

**목적**: CookieCloud 서버 장애 시 시스템이 안정적으로 동작하는지 확인

```
1. COOKIECLOUD_SERVER를 존재하지 않는 주소로 설정
2. 쿠키를 만료 상태로 설정
3. cookie_validation_job 실행
4. 연결 실패 로그 기록 + 수동 갱신 안내 알림 전송 확인
5. 타임아웃이 합리적 시간(10초 이내) 내에 완료 확인
```

**Expected**: ConnectionError 로그 후 즉시 폴백 알림 전송, 시스템 정상 동작 유지

## Setup for Testing

### 환경 변수 (.env)

```env
# 기존 (필수)
TELEGRAM_BOT_TOKEN=...
CLAUDE_API_KEY=...
ADMIN_CHAT_ID=7842337761

# 신규 (선택적 — CookieCloud 연동)
COOKIECLOUD_SERVER=http://localhost:8088
COOKIECLOUD_UUID=your-uuid-here
COOKIECLOUD_PASSWORD=your-password-here

# 신규 (선택적 — 만료 경고 임계치)
COOKIE_EXPIRY_WARNING_HOURS=36
```

### CookieCloud 서버 설치 (선택)

```bash
# Raspberry Pi에서 Docker 사용
docker run -d -p 8088:8088 --name cookiecloud easychen/cookiecloud:latest

# 또는 Node.js 직접 실행
git clone https://github.com/easychen/CookieCloud.git
cd CookieCloud/api && npm install && node app.js
```

### 브라우저 확장 설정

1. Chrome/Firefox에서 CookieCloud 확장 프로그램 설치
2. 서버 URL, UUID, Password 입력
3. m.weibo.cn 로그인 후 동기화 실행
