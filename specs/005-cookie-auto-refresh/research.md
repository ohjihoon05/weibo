# Research: Weibo 쿠키 자동 갱신 시스템

**Feature**: 005-cookie-auto-refresh
**Date**: 2026-02-23

## R-001: CookieCloud API 프로토콜

### Decision
CookieCloud 서버의 GET/POST 엔드포인트를 사용하여 암호화된 쿠키를 가져오고, 로컬에서 복호화한다.

### Findings

**API 엔드포인트:**
- `GET {server_url}/get/{uuid}` — 암호화된 쿠키 데이터 반환
- 응답 형식: `{"encrypted": "U2FsdGVkX1...(base64)", "crypto_type": "legacy"}`

**기본 포트:** 8088 (Docker: `easychen/cookiecloud:latest`)

### Rationale
서버 측 복호화(POST with password)도 가능하나, 비밀번호가 네트워크를 타게 됨. 로컬 복호화가 보안상 우수.

### Alternatives Considered
- **서버 측 복호화**: POST body에 password 포함 → 네트워크 노출 위험 → 기각
- **PyCookieCloud 라이브러리**: 래퍼 라이브러리지만 추가 의존성 → 직접 구현이 단순하므로 기각

---

## R-002: CookieCloud 암호화 메커니즘

### Decision
두 가지 암호화 모드를 모두 지원한다: `legacy` (기본값) + `aes-128-cbc-fixed` (v0.3.0+)

### Findings

**공통 키 파생:**
```
passphrase = MD5(uuid + '-' + password).hexdigest()[:16]
```

**Mode A: legacy (CryptoJS OpenSSL 형식)**
- 키 파생: EVP_BytesToKey (MD5 기반) — passphrase + salt → 32-byte key + 16-byte IV
- 암호화: AES-256-CBC + PKCS7 padding
- 데이터 형식: `"Salted__" + salt(8 bytes) + ciphertext` → base64 인코딩
- 특징: 랜덤 salt 사용으로 매번 다른 출력

**Mode B: aes-128-cbc-fixed (v0.3.0+)**
- 키: passphrase 16 bytes를 직접 AES 키로 사용
- IV: 고정 zero IV (16 bytes of 0x00)
- 암호화: AES-128-CBC + PKCS7 padding
- 데이터 형식: 순수 ciphertext → base64 인코딩 (Salted__ 접두사 없음)

### Rationale
CookieCloud 브라우저 확장이 어느 모드를 사용할지 미리 알 수 없으므로, `crypto_type` 필드를 확인하여 동적으로 처리.

### Required Library
`pycryptodome` (pip install pycryptodome) — AES-CBC, PKCS7 unpadding 제공

---

## R-003: CookieCloud 복호화된 데이터 형식

### Decision
`.weibo.com` 및 관련 도메인(`.weibo.cn`, `m.weibo.cn`)의 쿠키를 필터링하여 SUB, SUBP, XSRF-TOKEN을 추출한다.

### Findings

**복호화 후 JSON 구조:**
```json
{
  "cookie_data": {
    ".weibo.com": [
      {"domain": ".weibo.com", "name": "SUB", "value": "...", "expirationDate": 1740000000, ...},
      {"domain": ".weibo.com", "name": "SUBP", "value": "...", ...}
    ],
    ".weibo.cn": [...],
    "m.weibo.cn": [...]
  },
  "local_storage_data": {...}
}
```

- `cookie_data`: 도메인별 쿠키 배열 (Chrome cookies API 형식)
- 각 쿠키 객체: `domain`, `name`, `value`, `expirationDate`, `httpOnly`, `secure`, `path`, `session`
- Weibo 관련 도메인: `.weibo.com`, `.weibo.cn`, `m.weibo.cn`, `passport.weibo.com` 등

### Extraction Logic
1. `cookie_data`에서 `weibo` 포함 도메인 필터
2. 각 도메인의 쿠키 배열에서 `name`으로 필요 쿠키 추출
3. 필수 쿠키 확인: `SUB`, `SUBP`, `XSRF-TOKEN`
4. 추가 쿠키도 포함 (ALF, MLOGIN 등 — 기존 패턴 유지)

---

## R-004: 쿠키 수명 및 만료 임박 임계치

### Decision
기본 만료 임박 임계치를 36시간으로 설정한다. 환경 변수로 조정 가능.

### Findings
- Weibo 쿠키 실제 수명: 연구에 따르면 1~3일 (불확실, Weibo 서버 정책에 따라 변동)
- ALF 쿠키의 `expirationDate` 타임스탬프: 약 30일 후로 설정되나, 실제 세션은 더 짧음
- `/api/config`의 `login` 필드가 `false`가 되는 시점이 실제 만료 시점

### Rationale
- 36시간 = 쿠키 설정 후 1.5일. 최단 수명(1일) 기준으로도 만료 12시간 전에 경고 가능
- `COOKIE_EXPIRY_WARNING_HOURS` 환경 변수로 운영자가 조정 가능하게 설정

---

## R-005: Alert 중복 방지 전략

### Decision
마지막 경고 시각을 인메모리(bot_data)에 저장하여 24시간 이내 중복 방지. 봇 재시작 시 리셋 허용.

### Rationale
- 영속 저장(파일/DB)은 과도한 복잡성 — Constitution Principle VI (Simplicity) 위반
- 봇 재시작은 드물고, 재시작 후 한 번 더 경고가 가는 것은 무해
- `bot_data["last_cookie_warning_at"]`에 datetime 저장, 검증 시 24시간 경과 확인

### Alternatives Considered
- **JSON 파일 영속화**: 간단하나 파일 I/O 불필요 → 기각
- **weibo_cookies.json에 필드 추가**: 쿠키 데이터와 알림 상태 혼합은 관심사 분리 위반 → 기각
