# Contract: Weibo API Integration

**Date**: 2026-02-22

## Authentication

- **Method**: OAuth 2.0
- **Token**: 장기 access_token (앱 심사 통과 후)
- **Fallback**: 1일 토큰 (미심사 앱, 수동 갱신 필요)

## Endpoints

### 이미지 업로드

```
POST https://upload.api.weibo.com/2/statuses/upload.json
Content-Type: multipart/form-data

Parameters:
  access_token: string (required)
  status: string (required, 게시물 텍스트)
  pic: file (required, 이미지 파일)

Response:
  { "id": "...", "pic_ids": ["..."], ... }
```

**제약사항**:
- 이미지 최대 5MB
- JPEG, GIF, PNG만 지원
- 단일 이미지만 업로드 가능 (다중 이미지 시 개별 업로드)

### 다중 이미지 포스팅

```
POST https://api.weibo.com/2/statuses/upload_url_text.json

Parameters:
  access_token: string (required)
  status: string (required, URL-encoded 게시물 텍스트)
  pic_id: string (required, 콤마 구분 pic_id 목록)

Response:
  { "id": "...", "text": "...", ... }
```

**플로우**:
1. 이미지 N장을 개별 업로드 → 각각 `pic_id` 획득
2. `pic_id`들을 콤마로 연결하여 `upload_url_text` 호출
3. 결과에서 게시물 ID 및 URL 추출

### 텍스트만 포스팅

```
POST https://api.weibo.com/2/statuses/update.json

Parameters:
  access_token: string (required)
  status: string (required, URL-encoded 게시물 텍스트)

Response:
  { "id": "...", "text": "...", ... }
```

## Rate Limits

| 항목 | 제한 |
|------|------|
| 사용자당 API 호출 | 150/hour |
| IP당 API 호출 | 10,000/hour |
| 포스팅 빈도 | 30/hour |

## Error Codes (주요)

| Code | Description | 처리 방침 |
|------|-------------|----------|
| 10001 | System error | 재시도 |
| 10002 | Service unavailable | 재시도 |
| 20019 | Repeated content | 에러 알림 (중복 게시물) |
| 21327 | Token expired | 토큰 갱신 알림 |
| 21332 | Access token revoked | 재인증 알림 |

## IP Whitelist

라즈베리파이의 공인 IP를 Weibo 앱 설정의 IP Whitelist에 등록 필요.
동적 IP 사용 시 DDNS 또는 주기적 갱신 스크립트 필요.
