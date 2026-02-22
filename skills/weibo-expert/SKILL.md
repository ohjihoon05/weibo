---
name: weibo-expert
description: Weibo 전문가 콘텐츠 — 일본 부동산 전문 콘텐츠 자동 생성 및 관리
metadata: { "openclaw": { "emoji": "🧠", "requires": { "bins": ["curl"] } } }
---

# Weibo 전문가 콘텐츠

오사카/간사이 일본 부동산 전문가 콘텐츠를 자동 생성하고 관리합니다.

## Commands

### 최근 전문가 콘텐츠 목록
```bash
curl -s --max-time 10 http://localhost:5000/api/expert/recent | python3 -m json.tool
```

### 전문가 콘텐츠 생성 요청
```bash
curl -s --max-time 10 -X POST http://localhost:5000/api/expert/generate | python3 -m json.tool
```

## Notes
- 매물 포스트가 없는 날에 자동으로 전문가 콘텐츠가 생성됩니다
- 주제: 시장 동향, 투자 팁, 지역 소개, 세금/비자, 매매 절차
- 특정 매물의 가격, 주소, 사진 정보는 절대 포함되지 않습니다
