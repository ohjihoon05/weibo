# Contract: Exchange Rate API

**Date**: 2026-02-22

## Primary: ExchangeRate-API (Open Access)

```
GET https://open.er-api.com/v6/latest/JPY

Response:
{
  "result": "success",
  "base_code": "JPY",
  "rates": {
    "CNY": 0.0500,
    ...
  },
  "time_last_update_utc": "..."
}
```

**특성**:
- API 키 불필요
- 일 1회 갱신
- Rate limit: ~1 req/hour (open access)

## Secondary: Frankfurter

```
GET https://api.frankfurter.dev/v1/latest?base=JPY&symbols=CNY

Response:
{
  "base": "JPY",
  "date": "2026-02-22",
  "rates": {
    "CNY": 0.0498
  }
}
```

**특성**:
- API 키 불필요
- 무제한 요청
- ECB 데이터 기반, 일 1회 갱신 (16:00 CET)

## Fallback Chain

1. ExchangeRate-API 호출 → 성공 시 캐시 저장 + 반환
2. 실패 → Frankfurter 호출 → 성공 시 캐시 저장 + 반환
3. 실패 → 로컬 캐시 로드 (7일 이내 데이터)
4. 캐시 없음/만료 → 비상 하드코딩 환율 + 사용자 경고

## Cache Format

```json
{
  "rate": 0.0500,
  "source": "exchangerate-api",
  "fetched_at": "2026-02-22T10:00:00Z"
}
```

저장 위치: `data/exchange_rate.json`
