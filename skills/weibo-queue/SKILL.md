# Weibo 발행 대기열 관리

Weibo 발행 대기열을 관리합니다. 콘텐츠를 대기열에 추가하고, 예약 발행 상태를 확인하고, 즉시 발행하거나 삭제할 수 있습니다.

## Commands

### 대기열 현황 확인
```bash
curl -s http://localhost:5000/api/queue/status | python3 -m json.tool
```

### 대기 중인 항목 목록
```bash
curl -s http://localhost:5000/api/queue/items | python3 -m json.tool
```

### 콘텐츠 대기열 추가
```bash
curl -s -X POST http://localhost:5000/api/queue/enqueue \
  -H "Content-Type: application/json" \
  -d '{"text": "발행할 텍스트", "type": "listing"}' | python3 -m json.tool
```

### 즉시 발행
```bash
curl -s -X POST http://localhost:5000/api/queue/publish/{item_id} | python3 -m json.tool
```

### 대기열 항목 삭제
```bash
curl -s -X DELETE http://localhost:5000/api/queue/{item_id} | python3 -m json.tool
```

## Notes
- 대기열에 추가된 콘텐츠는 최적 시간(중국 시간 09:00, 20:00)에 자동 발행됩니다
- 하루 최대 2건까지 발행됩니다
