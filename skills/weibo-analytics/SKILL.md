# Weibo 성과 분석

발행된 포스트의 성과(좋아요, 댓글, 리포스트)를 분석하고 주간 리포트를 조회합니다.

## Commands

### 최근 성과 데이터
```bash
curl -s http://localhost:5000/api/analytics/metrics | python3 -m json.tool
```

### 주간 성과 리포트
```bash
curl -s http://localhost:5000/api/analytics/report | python3 -m json.tool
```

### 최적 발행 시간 분석
```bash
curl -s http://localhost:5000/api/analytics/besttime | python3 -m json.tool
```

## Notes
- 성과 데이터는 발행 후 2시간, 24시간, 7일 시점에 자동 수집됩니다
- 주간 리포트는 매주 월요일 오전 자동 생성됩니다
