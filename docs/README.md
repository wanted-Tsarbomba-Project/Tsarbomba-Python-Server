# docs — tsarbomba ChatBot 기술결정문서 (Claude Context)

> 이 폴더는 **이 서버를 처음부터 똑같이 재구성**하기 위한 self-contained 기술결정문서 세트다.
> 새 Claude/개발자는 코드를 보기 전에 **이 문서들만 읽고도** 구조·결정·규약을 파악할 수 있어야 한다.
> 체계는 codebomba(LMS 백엔드) `docs/` 를 미러링한다: 경계(ARCHITECTURE) · 결정(adr) · 규약(CONVENTION).

---

## 읽는 순서

1. **[ARCHITECTURE.md](ARCHITECTURE.md)** — 서버 정체성, 시스템 위치, 도메인 맵, 요청 생애주기, 스택, 디렉토리. **여기서 시작.**
2. **[CONVENTION.md](CONVENTION.md)** — 레이어링·네이밍·API(snake vs camel)·스키마 전체·에러·로깅·테스트·설정 규약.
3. **[adr/](adr/)** — 되돌리기 어렵고 대안이 있던 결정 9건(왜 그렇게 했나).
4. **[prompt-engineering.md](prompt-engineering.md)** — 시스템 프롬프트/컨텍스트 엔지니어링 how-to 상세.

> 재구성 관점: ARCHITECTURE로 전체 골격 → CONVENTION으로 계약(스키마/에러/로깅) → adr로 각 결정의 이유 → prompt-engineering으로 프롬프트 본문 설계.

---

## owns-what (한 사실은 한 곳에만)

| 성질 | 어디에 |
|------|--------|
| 경계·도메인 맵·요청 흐름·엔드포인트 목록 | `ARCHITECTURE.md` |
| 결정·이유(대안이 있던 선택) | `adr/000N-*.md` (append-only, 바뀌면 새 ADR로 supersede) |
| 코딩·API·에러·로깅·테스트·설정 규약, 스키마 필드 | `CONVENTION.md` |
| 프롬프트 설계 원칙·튜터링 규칙·템플릿 how-to | `prompt-engineering.md` |
| 자주 바뀌는 구현 상세(패키지 트리 등) | **코드가 진실** — 문서에 박제하지 않음 |

---

## ADR 목차

| # | 제목 | 한 줄 |
|---|------|-------|
| [0001](adr/0001-domain-package-lightweight-layering.md) | 도메인=최상위 패키지 + 경량 계층 | `api/service/schema`만, 풀세트 DDD 안 씀 |
| [0002](adr/0002-config-and-no-di.md) | 설정 pull + DI 미채택 | pydantic-settings + `@lru_cache`, 포트-어댑터 안 씀 |
| [0003](adr/0003-sse-streaming-contract.md) | SSE 스트리밍 계약 | JSON 토큰 래핑 · 봉투 면제 · 에러=이벤트 |
| [0004](adr/0004-prompt-as-jinja-templates.md) | 프롬프트=Jinja2 템플릿 | 영어 실사용 + `ko/` 참조본, 하드코딩 금지 |
| [0005](adr/0005-prompt-context-caching-split.md) | 컨텍스트 분리(캐싱) | `system_instruction`(불변) vs `contents`(가변) |
| [0006](adr/0006-spring-boundary-contract.md) | Spring 경계 계약 | snake_case · 공유 `CHT-003` · `X-Trace-Id` · PII 미로깅 |
| [0007](adr/0007-recommendation-apriori.md) | 추천: 브루트포스 Apriori | LMS DB 직접 read · `/internal` camelCase · 503 |
| [0008](adr/0008-observability.md) | 관측 | Prometheus · 미들웨어 카디널리티 · 구조적 로깅 · trace 상관 |
| [0009](adr/0009-deployment-topology.md) | 배포 토폴로지 | Docker/ECR/EC2 compose · promtail→Loki · OIDC/SSM |

---

## 빠른 사실 (Quick facts)

- 스택: FastAPI + Python 3.12, Gemini(`google-genai`), Jinja2, pymysql, prometheus-client.
- 진입점: `app/main.py`. 실행: `uvicorn app.main:app --host 0.0.0.0 --port 8000`.
- 테스트: `pytest -q` (DB·Gemini·네트워크 없이 격리).
- 호출자: **Spring 백엔드만**(CORS `localhost:8080`만 허용). 프론트 직접 호출 없음.

---

## ⚠️ 알려진 불일치 (재구성 시 무엇이 진실인지)

> 코드/설정에 실재하는 불일치. **재구성 시 아래 "진실" 컬럼을 따른다.** (이 문서 세트는 코드를 바꾸지 않고 기록만 한다.)

| 항목 | 어긋난 값들 | 진실 / 판단 |
|------|-------------|-------------|
| 응답 길이 `default_max_length` | `core/config.py` 기본 **1000** · `.env.example`·과거 문서 **200** | **실제 유효값은 `.env`의 `DEFAULT_MAX_LENGTH`**(운영은 환경변수 주입). 코드 기본값(1000)은 `.env` 없을 때만. |
| Gemini 모델명 | `config.py` `gemini-2.5-flash-preview-05-20` · `.env.example` `gemini-2.5-flash` · (구 handoff "3.5") | **실제 유효값은 `.env`의 `GEMINI_MODEL`.** "3.5"는 오기. |
| 채팅 응답 필드 | 구 문서가 `ChatResponse{answer,is_answer_detected,retry_count,*_tokens}` 서술 | **이미 제거됨.** 현재는 SSE 스트림(`data/done/error`)만. 토큰 사용량은 `done` 이벤트 페이로드로만 전달 → [ADR-0003](adr/0003-sse-streaming-contract.md). |

> 이 표는 코드가 정합화되면 갱신/삭제한다. `.env`/`config.py`의 실제 값이 언제나 우선한다.
