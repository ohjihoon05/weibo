<!--
  Sync Impact Report
  ==================
  Version change: 1.1.0 → 1.2.0 (spec 002 analyze remediation)
  Modified principles: None
  Added sections: None
  Removed sections: None
  Modified sections:
    - Technology Constraints: "Weibo Open Platform 공식 API" → "m.weibo.cn 모바일 웹 API (쿠키 기반)"
    - Development Workflow: Replaced official API reference with m.weibo.cn cookie API
    - Open Risks: Updated to reflect cookie-based auth risks
  Templates requiring updates:
    - .specify/templates/plan-template.md ✅ no update needed
    - .specify/templates/spec-template.md ✅ no update needed
    - .specify/templates/tasks-template.md ✅ no update needed
  Follow-up TODOs: None
-->

# Weibo 부동산 자동 포스팅 시스템 Constitution

## Core Principles

### I. Pipeline Reliability

모든 기능은 핵심 파이프라인(Telegram → Claude API → Weibo)의 안정성을
최우선으로 MUST 보장한다.

- 각 단계(수신, 번역, 포스팅)는 독립적으로 실패 가능하며,
  실패 지점이 명확히 식별되어야 한다.
- 단계 간 데이터 전달은 검증 가능한 형식으로 이루어져야 한다.
- 파이프라인 중단 시 부분 완료 상태가 추적 가능해야 한다.

**근거**: 시스템의 핵심 가치는 Telegram 입력부터 Weibo 게시까지의
end-to-end 자동화이며, 파이프라인 어느 한 지점의 실패가
전체 시스템 신뢰도를 훼손한다.

### II. Security by Default

API 키, 토큰, 인증 정보는 MUST 환경변수로 관리하며,
소스코드에 절대 포함하지 않는다.

- Telegram Bot Token, Weibo API 자격증명, Claude API 키는
  환경변수 또는 별도 시크릿 관리 도구를 통해 주입한다.
- `.env` 파일은 MUST `.gitignore`에 포함한다.
- 로그에 토큰이나 API 키가 노출되지 않도록 MUST 마스킹한다.

**근거**: 외부 서비스(Weibo, Telegram, Claude) 연동 시
자격증명 유출은 계정 탈취 및 비용 발생으로 직결된다.

### III. User Safety & Approval

기본 동작은 미리보기 모드(`/preview`)로 MUST 설정하며,
사용자가 명시적으로 `/auto` 모드를 선택한 경우에만 즉시 포스팅한다.

- 번역 결과는 포스팅 전 사용자에게 Telegram으로 미리보기를 제공한다.
- 사용자 승인 없이 Weibo에 게시물이 올라가지 않는다(auto 모드 제외).
- `/auto` 모드 전환은 세션 단위(인메모리)로 적용하며, 봇 재시작 시
  기본값(`/preview`)으로 리셋된다. 영구 설정이 아니다.

**근거**: 부동산 매물 정보의 오역이나 잘못된 게시는
비즈니스 신뢰도에 직접적인 타격을 주므로 실수 방지가 최우선이다.

### IV. Translation Accuracy

AI 번역은 일본 부동산 전문 용어를 정확하게 MUST 처리하며,
简体中文 출력을 보장한다.

- 입력 언어(일본어/중국어/한국어) 자동 감지를 MUST 수행한다.
- 부동산 전문 용어(間取り, 管理費, 修繕積立金, 所有権 등)는
  중국 부동산 시장에서 통용되는 정확한 중국어 표현으로 번역한다.
- 매물 정보 템플릿(16개 필수 항목)에 맞춰 자동 포맷팅한다.
- JPY→CNY 환율 환산은 실시간 환율 데이터를 MUST 반영한다.

**근거**: 타깃 사용자(중국 바이어)가 신뢰할 수 있는 정보를
제공하려면 전문 용어의 정확한 번역과 일관된 포맷이 필수적이다.

### V. Graceful Error Handling

모든 외부 서비스 호출은 실패에 대비한 재시도 및 알림 메커니즘을
MUST 갖춘다.

- Weibo 포스팅 실패 시 최대 3회 재시도한다.
- 재시도 실패 시 사용자에게 Telegram으로 에러 메시지를 전송한다.
- 이미지 업로드 실패, 환율 API 오류, 번역 실패 등 각 실패 유형에
  대해 구체적인 에러 메시지를 제공한다.
- 모든 포스팅 이력(성공/실패)은 로컬에 MUST 저장한다.

**근거**: 외부 API(Weibo, 환율, Claude)는 본질적으로 불안정하며,
사용자에게 실패 사실을 즉시 알리지 않으면 매물 노출 기회를 잃는다.

### VI. Simplicity & Resource Efficiency

시스템은 라즈베리파이(Linux ARM) 환경에서 안정적으로 MUST
동작하며, 과도한 추상화를 지양한다.

- 하루 1~3건의 포스팅 볼륨에 맞는 경량 설계를 유지한다.
- 불필요한 데이터베이스, 메시지 큐, 캐시 레이어를 도입하지 않는다.
- 이미지는 Weibo 업로드 요구사항에 맞춰 자동 리사이즈하되,
  원본을 과도하게 처리하지 않는다.
- YAGNI 원칙: 현재 요구사항에 없는 기능을 선제적으로 구현하지 않는다.

**근거**: 라즈베리파이의 제한된 리소스(CPU, 메모리)와
저빈도 사용 패턴을 고려하면 단순한 설계가 유지보수성과
안정성 모두에서 유리하다.

## Technology Constraints

| 구성요소 | 기술 | 제약사항 |
|---------|------|---------|
| AI 모델 | Claude API (anthropic 라이브러리) | API 호출 비용 관리 필수 |
| 입력 | Telegram Bot API (python-telegram-bot) | 사진 최대 9장 (Weibo 제한 준수) |
| 출력 | m.weibo.cn 모바일 웹 API (쿠키 기반) | 쿠키 주기적 갱신 필요, OpenClaw 자동화 가능 |
| 환율 | 외부 환율 API | 실시간 JPY→CNY 환산 |
| 런타임 | 라즈베리파이 (Linux ARM) | 메모리/CPU 제한 고려 설계 |

**열린 리스크**:
- m.weibo.cn 쿠키 인증: 쿠키 유효기간이 수일~수주로 주기적 갱신 필요.
  OpenClaw 자동 갱신 또는 수동 /cookie 명령어로 관리.

## Development Workflow

- 기능 구현은 핵심 파이프라인(Telegram 수신 → Claude API 번역 → Weibo 포스팅)
  순서로 진행하며, 각 단계가 독립적으로 테스트 가능해야 한다.
- 환경변수 설정 가이드를 프로젝트 초기에 문서화한다.
- m.weibo.cn 모바일 웹 API(쿠키 기반)를 사용한다(spec 002 확정, 공식 API는 error 10014로 폐쇄).
- 커밋은 각 파이프라인 단계 완성 시점에 수행한다.
- 부동산 매물 포맷 템플릿 변경은 constitution 수정 없이
  설정 파일로 관리할 수 있도록 한다.

## Governance

이 Constitution은 프로젝트의 모든 설계 및 구현 결정에 우선한다.

- **수정 절차**: Constitution 변경은 변경 사유와 영향 범위를
  문서화한 후 적용한다. 의존 템플릿(plan, spec, tasks)의
  정합성을 반드시 검증한다.
- **버전 정책**: Semantic Versioning(MAJOR.MINOR.PATCH)을 따른다.
  - MAJOR: 원칙 삭제 또는 근본적 재정의
  - MINOR: 새 원칙 추가 또는 기존 원칙의 실질적 확장
  - PATCH: 문구 수정, 오타, 비의미적 개선
- **준수 검토**: 모든 PR/코드 리뷰 시 Constitution 원칙 준수 여부를
  확인한다. 원칙 위반이 불가피한 경우 사유를 명시적으로 기록한다.

**Version**: 1.2.0 | **Ratified**: 2026-02-22 | **Last Amended**: 2026-02-22
