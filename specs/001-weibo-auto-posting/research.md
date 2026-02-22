# Research: Weibo 부동산 자동 포스팅 시스템

**Date**: 2026-02-22
**Branch**: `001-weibo-auto-posting`

## R1: Weibo API 접근 방식

### Decision: Weibo Open Platform 공식 API 사용

### Rationale
- `/2/statuses/upload_url_text.json` 엔드포인트가 텍스트 + 다중 이미지(최대 9장)
  포스팅을 지원하며, 프로젝트 요구사항과 정확히 일치한다.
- 하루 1~3건 포스팅은 API rate limit(150 req/hour, 30 posts/hour)에
  전혀 문제되지 않는다.
- Weibo는 중국 방화벽(GFW) 뒤에 있지 않으므로 일본에서
  VPN 없이 API 접근이 가능하다.
- 기존 Python 라이브러리(weibopy, sinaweibopy 등)는 모두 2020년 이후
  유지보수되지 않으므로, `requests` 기반 커스텀 래퍼(50~100줄)를 작성한다.

### 주요 제약사항
- **개발자 등록**: open.weibo.com에서 등록 필요 (2~3일 심사).
- **계정 인증**: 중국 핸드폰 번호가 사실상 필요. 모바일 앱 통한
  해외 등록이 상대적으로 용이.
- **앱 심사**: 미심사 앱은 토큰 유효기간 1일. 심사 통과 시 장기 토큰 획득.
- **IP 화이트리스트**: 라즈베리파이 IP를 앱 설정에 등록해야 함.

### API 엔드포인트
| 용도 | 엔드포인트 | 비고 |
|------|-----------|------|
| 이미지 업로드 | `upload.api.weibo.com/2/statuses/upload.json` | 개별 업로드 → pic_id 반환 |
| 다중이미지 포스팅 | `/2/statuses/upload_url_text.json` | pic_id 콤마 구분 전달 |
| 텍스트만 포스팅 | `/2/statuses/update.json` | 사진 없는 경우 |

### Rate Limits
| 항목 | 제한 |
|------|------|
| API 호출/시간 (사용자) | 150 req/hour |
| API 호출/시간 (IP) | 10,000 req/hour |
| 포스팅/시간 | 30 posts/hour |
| 이미지/포스트 | 최대 9장 |
| 이미지 크기 | 최대 5MB/장 |
| 이미지 형식 | JPEG, GIF, PNG |
| 텍스트 길이 | 2,000자 (피드에서 140자 이후 접힘) |

### Alternatives Considered
| 대안 | 판단 | 사유 |
|------|------|------|
| Selenium 브라우저 자동화 | 최후 수단 | CAPTCHA, MFA, DOM 변경으로 유지보수 부담 극대 |
| weibo_api (비공식 API) | 위험한 대안 | 세션쿠키 기반, MFA 수동 개입 필요, 작성자가 "불안정" 경고 |
| 기존 Python 라이브러리 | 비권장 | 모두 2020년 이후 미유지보수 |

### 핵심 리스크
앱 심사 과정이 최대 리스크. 해외 개인이 중국 비즈니스 주체 없이
심사 통과 가능한지 불확실. 실패 시 weibo_api(비공식) +
주기적 수동 재인증이 대안.

---

## R2: 환율 API (JPY → CNY)

### Decision: ExchangeRate-API (open access) + Frankfurter (fallback)

### Rationale
- ExchangeRate-API는 API 키 없이 open access 엔드포인트 제공.
  99.99% 이상 가동률. 월 1,500 req 무료(키 사용 시).
- 하루 1회 환율 조회면 충분 (부동산 가격 비교에 실시간 환율 불필요).
- Frankfurter는 무제한 무료, 키 불필요, ECB 데이터 기반 백업.

### Fallback 전략
```
1차: ExchangeRate-API (open.er-api.com)
2차: Frankfurter (api.frankfurter.dev)
3차: 로컬 캐시 (마지막 성공 환율 + 타임스탬프)
4차: 비상용 하드코딩 환율 (경고 표시)
```

### 캐시 정책
- 성공 시 로컬 파일에 환율 + 타임스탬프 저장.
- 48시간 미만: 정상 사용.
- 48시간~7일: 경고 표시와 함께 사용.
- 7일 초과: 비상 환율로 전환, 사용자에게 알림.

### Alternatives Considered
| 대안 | 판단 | 사유 |
|------|------|------|
| Open Exchange Rates | 비채택 | 무료 1,000 req/월, 히스토리 유료 |
| Fixer.io | 비채택 | 소유권 변경 이력, 장기 신뢰도 우려 |
| CurrencyFreaks | 비채택 | 무료 100 req/월로 너무 제한적 |

---

## R3: Telegram Bot 프레임워크

### Decision: python-telegram-bot v21.x + long-polling

### Rationale
- PyPI 최다 다운로드 Telegram Bot 라이브러리 (~30M downloads).
- v20+ 부터 완전 async (asyncio + httpx 기반).
- 풍부한 문서와 예제 (MediaGroup 처리, InlineKeyboard 등).
- Idle 메모리 사용량 25~40MB — RPi5 16GB에서 부담 없음.
- Long-polling은 공인 IP/SSL 불필요, 홈 네트워크 RPi에 적합.

### MediaGroup 처리 패턴
- 다중 사진 전송 시 Telegram은 사진마다 개별 update를 전송하되
  동일한 `media_group_id`를 공유.
- 2초 타임아웃으로 같은 그룹의 사진을 모아서 일괄 처리.
- `job_queue.run_once()` 패턴 사용.

### 승인 버튼 구현
- `InlineKeyboardMarkup` + `CallbackQueryHandler` 사용.
- "포스팅" / "수정 요청" 버튼을 미리보기 메시지에 첨부.

### Python 버전
- 현재 시스템: Python 3.13.5 (Debian Trixie).
- python-telegram-bot v21.x 완전 호환.
- `python3 -m venv` 사용 필수 (Debian 정책).

### 설치
```bash
pip install "python-telegram-bot[job-queue]"
```

### Alternatives Considered
| 대안 | 판단 | 사유 |
|------|------|------|
| aiogram | 비채택 | 대용량 트래픽용, 러시아어 문서 중심 |
| telethon | 비채택 | MTProto 기반 사용자 API, Bot용 과잉 |
| pyTelegramBotAPI | 비채택 | 스레딩 메모리 누수 이슈 보고됨 |

---

## R4: 이미지 처리

### Decision: Pillow (Python Imaging Library)

### Rationale
- OpenCV 대비 3~6배 작은 설치 크기, numpy 의존 없음.
- 내장 EXIF 처리 (`exif_transpose()`), JPEG 품질 제어.
- 리사이즈 전용 사용에 최적화된 간결한 API.

### 처리 전략
| 항목 | 설정 |
|------|------|
| 최대 크기 | 1080px (장변 기준) |
| 출력 형식 | JPEG quality 85 (필요 시 50까지 단계적 감소) |
| 목표 파일 크기 | 4MB 이하 (API 제한 5MB 대비 마진) |
| EXIF | 방향 적용 후 제거 (프라이버시 + 용량 절감) |
| 처리 방식 | 순차 처리 (이미지 1장씩, 피크 메모리 ~72MB) |
| GIF | v1에서는 리사이즈 없이 원본 전달 |

### Weibo 이미지 표시 특성
- Weibo는 업로드된 이미지를 서버측에서 200~500KB로 압축.
- 1080px 이상 업로드 시 추가 품질 이점 없음.
- 따라서 클라이언트측에서 1080px로 최적화 후 업로드가 효율적.

### 메모리 사용 (9장 순차 처리)
- 12MP 사진(4000x3000) RGB = ~36MB 비압축.
- 1장 처리 시 피크 ~72MB (입력 + 출력 버퍼).
- 순차 처리로 9장 모두 72MB 피크 유지 (RPi 512MB에서도 안전).

### Alternatives Considered
| 대안 | 판단 | 사유 |
|------|------|------|
| opencv-python-headless | 비채택 | 설치 크기 큼, numpy 필수, EXIF 수동 처리 |
| 2048px 해상도 | 비채택 | Weibo 서버측 압축으로 품질 이점 없음 |
| PNG 출력 | 비채택 | 사진 콘텐츠에 파일 크기 불리 |
| 병렬 처리 | 비채택 | 메모리 N배 증가, 9장 순차 처리 2~5초면 충분 |
