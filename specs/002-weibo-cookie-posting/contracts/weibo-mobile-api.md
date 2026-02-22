# Contract: m.weibo.cn Mobile Web API

## Base URL

`https://m.weibo.cn`

## Authentication

모든 요청에 다음 헤더 필수:

| Header | Value | Source |
|--------|-------|--------|
| Cookie | `SUB=...; SUBP=...; XSRF-TOKEN=...` | 저장된 쿠키 |
| X-XSRF-TOKEN | `{st}` | `/api/config` 응답의 `data.st` |
| X-Requested-With | `XMLHttpRequest` | 고정값 |
| Referer | `https://m.weibo.cn/compose/` | 고정값 |
| User-Agent | 모바일 브라우저 UA | 고정값 |

## Endpoints

### GET /api/config

쿠키 유효성 검증 및 XSRF 토큰 획득.

**Request**: 헤더에 Cookie만 포함.

**Response (성공)**:
```json
{
  "ok": 1,
  "data": {
    "login": true,
    "st": "abc123def456",
    "uid": "1234567890"
  }
}
```

**Response (쿠키 만료)**:
```json
{
  "ok": 1,
  "data": {
    "login": false,
    "st": ""
  }
}
```

**사용 패턴**: 모든 write 요청 전에 호출하여 st 토큰을 획득하고 login 상태 확인.

---

### POST /api/statuses/uploadPic

이미지 업로드.

**Content-Type**: `multipart/form-data`

**Request Body**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| pic | binary | Yes | 이미지 파일 (JPEG, <5MB) |
| st | string | Yes | XSRF 토큰 |

**Response (성공)**:
```json
{
  "pic_id": "946308c5jw1dv288whtylj",
  "thumbnail_pic": "http://ww3.sinaimg.cn/thumbnail/946308c5jw1dv288whtylj.jpg",
  "bmiddle_pic": "http://ww3.sinaimg.cn/bmiddle/946308c5jw1dv288whtylj.jpg",
  "original_pic": "http://ww3.sinaimg.cn/large/946308c5jw1dv288whtylj.jpg"
}
```

**Response (에러)**:
```json
{
  "ok": 0,
  "msg": "error description"
}
```

---

### POST /api/statuses/update

게시물 작성.

**Content-Type**: `application/x-www-form-urlencoded`

**Request Body**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| content | string | Yes | 게시물 텍스트 (해시태그는 `#topic#` 형식) |
| st | string | Yes | XSRF 토큰 |
| picIds | string | No | 쉼표 구분 pic_id 문자열 |
| visible | int | No | 0=공개(기본), 1=나만보기, 6=친구 |

**Response (성공)**:
```json
{
  "ok": 1,
  "data": {
    "id": 4454572602912349,
    "idstr": "4454572602912349",
    "bid": "ImTGkcdDn",
    "created_at": "Sun Feb 22 14:30:00 +0800 2026",
    "text": "posted content...",
    "visible": {"type": 0, "list_id": 0},
    "pic_ids": ["abc123", "def456"],
    "user": {
      "id": 1234567890,
      "screen_name": "username"
    }
  }
}
```

**Response (에러)**:
```json
{
  "ok": 0,
  "msg": "error description",
  "errno": "100005"
}
```

**게시물 URL 구성**: `https://m.weibo.cn/detail/{bid}`

---

## Error Handling

| Condition | Detection | Action |
|-----------|-----------|--------|
| 쿠키 만료 | `/api/config`의 `data.login == false` | CookieExpiredError 발생, 사용자 알림 |
| st 토큰 만료 | 요청 실패 후 `/api/config` 재호출 | 자동 갱신 후 재시도 |
| Rate limit | HTTP 429 또는 에러 응답 | 지수 백오프 재시도 (2/4/8초, 최대 3회) |
| 중복 게시물 | 에러 응답에 "duplicate" 포함 | 타임스탬프 접미사 추가 후 재시도 |
| 이미지 업로드 실패 | uploadPic의 ok=0 | 재시도 후 실패 시 사용자 알림 |
| 네트워크 오류 | requests.RequestException | 재시도 후 실패 시 사용자 알림 |

## Rate Limits

- 공식 제한: 시간당 약 30건 포스팅
- 실사용: 하루 1~3건이므로 제한에 도달하지 않음
- 이미지 업로드 간 1~2초 딜레이 권장
