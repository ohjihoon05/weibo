# Weibo 경쟁 계정 벤치마킹

경쟁 Weibo 계정을 등록하고 벤치마킹 분석을 수행합니다.

## Commands

### 경쟁 계정 목록
```bash
curl -s http://localhost:5000/api/competitors | python3 -m json.tool
```

### 경쟁 계정 추가
```bash
curl -s -X POST http://localhost:5000/api/competitors \
  -H "Content-Type: application/json" \
  -d '{"uid": "1234567890", "note": "일본 부동산 계정"}' | python3 -m json.tool
```

### 경쟁 계정 제거
```bash
curl -s -X DELETE http://localhost:5000/api/competitors/{uid} | python3 -m json.tool
```

### 벤치마킹 리포트 조회
```bash
curl -s http://localhost:5000/api/benchmark | python3 -m json.tool
```

## Notes
- 벤치마킹은 매주 일요일 저녁 자동 실행됩니다
- 경쟁 계정 3-10개 등록을 권장합니다
