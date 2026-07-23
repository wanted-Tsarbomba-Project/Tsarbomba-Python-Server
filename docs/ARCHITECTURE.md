# Architecture — tsarbomba ChatBot (FastAPI AI 서버)

> 이 서버가 **무엇이고, 무엇을 소유하며, 바깥과 어떻게 통신하는지**의 단일 지도다.
> "왜 이렇게 정했나"의 결정·이유는 [`adr/`](adr/), 코딩·API 규약은 [`CONVENTION.md`](CONVENTION.md).
> 이 문서 + adr/ + CONVENTION 만으로 서버를 처음부터 재구성할 수 있어야 한다(재현 스펙).

---

## 1. 한 줄 정체성

**데이터 분석 학습용 AI 튜터 챗봇의 응답을 생성하는 FastAPI(Python 3.12) 서버.**
독립 서비스가 아니라 **Spring 백엔드(codebombalms) 전용 AI 마이크로서비스**다.

- 프론트가 **직접 호출하지 않는다.** Spring 백엔드만 호출한다.
  - 근거: `app/main.py`의 CORS가 `http://localhost:8080`(Spring) **한 곳만** 허용.
- 하는 일 2가지:
  1. **채팅 응답 생성** — Spring이 조립한 학습 컨텍스트를 받아 Gemini로 튜터 응답을 SSE 스트리밍.
  2. **문제집 추천 생성(배치)** — Spring이 트리거하면 LMS DB를 직접 읽어 연관규칙(Apriori)으로 사용자별 추천을 계산해 반환.

---

## 2. 시스템 위치 (외부 경계)

```
                 ┌─────────────────────────── 채팅 흐름 ───────────────────────────┐
  사용자 ──▶ Spring 백엔드(codebombalms) ──POST /chat (JSON, X-Trace-Id)──▶  이 서버  ──▶ Google Gemini
             (LMS, :8080)                    snake_case                    (:8000)        generate_content_stream
                    ◀────────────────── SSE (text/event-stream) ──────────────────┘        (토큰 스트림)

                 ┌────────────────────────── 추천 흐름(배치) ─────────────────────────┐
  Spring 배치 ──POST /internal/recommendations/problem-sets/generate (camelCase)──▶ 이 서버
                    ◀──────────────────── JSON 추천 결과 ────────────────────────────┘
                                                                             │ 직접 read (pymysql)
                                                                             ▼
                                                                     LMS MySQL (Spring과 동일 DB)
```

- **채팅**: Spring이 학습 컨텍스트(문제·정답·제출·데이터셋·대화이력)를 조립해 보내고, 이 서버는 **프롬프트 조립 + Gemini 호출 + SSE 중계**만 한다. 상태를 저장하지 않는다(stateless).
- **추천**: 이 서버가 **LMS MySQL을 직접 조회**한다(Spring API 경유 아님 — [ADR-0007](adr/0007-recommendation-apriori.md)). 결과만 Spring에 반환하고, 저장은 Spring이 한다.
- **관측**: 로그는 stdout → promtail(사이드카) → Loki(Spring과 동일). 메트릭은 `/metrics`(Prometheus).

> Spring 측 연동 코드: `chatbot/infrastructure/client/FastApiChatClient.java`(WebClient `POST /chat`), 에러코드·JSON 필드를 이 서버와 **공유**한다 → [ADR-0006](adr/0006-spring-boundary-contract.md).

---

## 3. 내부 구성 — 도메인 3 + core

패키지 = 도메인. `app/` 한 겹만 열면 도메인이 다 보인다(스크리밍 아키텍처). 도메인 내부는 `api/service/schema` 경량 계층 → [ADR-0001](adr/0001-domain-package-lightweight-layering.md).

| 도메인 | 소유(한 줄) | 진입 엔드포인트 | 핵심 파일 |
|--------|------------|-----------------|-----------|
| `chatbot` | AI 튜터 채팅 응답 생성(프롬프트 조립·Gemini·SSE) | `POST /chat` | `api/chat_router.py`, `service/{prompt_builder,gemini_client,sse}.py`, `schema/chat.py` |
| `recommendation` | 문제집 추천 배치 생성(LMS DB read·Apriori) | `POST /internal/recommendations/problem-sets/generate` | `service/{apriori,recommendation_service,repository}.py`, `api/recommendation_router.py`, `schema/recommendation.py` |
| `monitoring` | HTTP 메트릭 수집·노출(Prometheus) | `GET /metrics` | `http.py`(미들웨어), `metrics.py`, `api/monitoring_router.py` |
| `core` | 공통 설정(도메인 아님) | — | `config.py` |

- 도메인은 **서로 import하지 않는다.** 유일한 공유는 두 곳:
  - `core/config.py`(설정) — 모든 도메인이 pull.
  - `monitoring/metrics.py`(메트릭 객체) — `recommendation`이 자기 단계별 소요시간을 기록하려고 import.
- `app/main.py`가 세 라우터를 `include_router`로 조립하고, `HttpMetricsMiddleware`·CORS를 얹는다.

### 엔드포인트 전체 목록

| 메서드 | 경로 | 도메인 | 응답 | 비고 |
|--------|------|--------|------|------|
| POST | `/chat` | chatbot | `text/event-stream`(SSE) | 요청 snake_case. `X-Trace-Id` 헤더 수신 |
| POST | `/internal/recommendations/problem-sets/generate` | recommendation | JSON | 요청/응답 camelCase(alias) |
| GET | `/metrics` | monitoring | Prometheus text | 미들웨어 측정 제외 대상 |
| GET | `/health` | (main) | `{"status":"ok"}` | 배포 헬스체크 |

---

## 4. 요청 생애주기 A — 채팅 (`POST /chat`)

```
Spring ──POST /chat (JSON body: ChatRequest, header: X-Trace-Id)──▶ FastAPI
  │
  1. ChatRequest 로 파싱·검증                        app/chatbot/schema/chat.py (Pydantic)
  2. 로그: event=chatbot_chat_started (원문X, 길이만) app/chatbot/api/chat_router.py
  3. 모드 분기 → 시스템 프롬프트 조립                 app/chatbot/service/prompt_builder.py
  │     problem_set 있음 → system_problem.j2 (문제풀이)
  │     problem_set 없음 → system_free.j2  (자유질문)
  4. Gemini 스트림 호출                               app/chatbot/service/gemini_client.py
  │     _build_contents(): conversation_history(멀티턴) + 가변 컨텍스트(prefix)
  │     generate_content_stream(system_instruction=프롬프트, contents=…)
  5. 토큰마다 SSE 프레임 yield                        app/chatbot/service/sse.py
  │     data:{"t":토큰}  … (N회)
  │     event:done data:{promptTokens,completionTokens,totalTokens}  (정상 종료 1회)
  │     event:error data:{code:"CHT-003",message}  (도중 예외 시 1회 후 종료)
  ▼
StreamingResponse(media_type="text/event-stream",
                  headers={Cache-Control:no-cache, X-Accel-Buffering:no})
```

- **불변/가변 분리가 핵심**: 방 안에서 안 변하는 것(역할·금지·문제·정답·데이터셋)은 `system_instruction`으로, 변하는 것(대화이력·현재문제번호·user_message)은 `contents`로 → Gemini implicit caching 히트 → [ADR-0005](adr/0005-prompt-context-caching-split.md).
- **에러도 스트림 안의 이벤트**: 스트림이 시작되면 HTTP 200이 이미 커밋되어 상태코드로 에러를 못 알린다. 그래서 `event:error`로 보낸다 → [ADR-0003](adr/0003-sse-streaming-contract.md).
- 상세 SSE 규격·프롬프트 설계는 [ADR-0003](adr/0003-sse-streaming-contract.md)·[prompt-engineering.md](prompt-engineering.md).

---

## 5. 요청 생애주기 B — 추천 (`POST /internal/...generate`)

```
Spring 배치 ──POST …/problem-sets/generate {recommendationCount}──▶ FastAPI
  │
  1. RecommendationGenerateRequest 파싱 (camelCase alias)  schema/recommendation.py
  2. LMS MySQL 직접 조회 (pymysql, 2 쿼리)                  service/repository.py
  │     find_completed_problem_sets_by_user() → {user_id: {problem_set_id...}}
  │     find_active_problem_set_ids()          → {problem_set_id...}
  │     (DB 예외 → RecommendationRepositoryError → 503)
  3. 브루트포스 연관규칙 생성                              service/apriori.py
  │     빈발 아이템셋(support≥2, 크기≤4) → 규칙(support/confidence/lift)
  │     사용자별: 완료집합을 antecedent로 매칭, 미완료·활성 타깃만
  │     정렬키 (lift, confidence, support, antecedent크기) 내림차순 → 상위 N
  4. 응답 조립 + 단계별 메트릭·로그                        service/recommendation_service.py
  ▼
RecommendationGenerateResponse { recommendations:[{userId, problemSets:[{problemSetId,support,confidence,lift,rankNo,algorithm}]}] }
```

- 알고리즘·상수·SQL 상세는 [ADR-0007](adr/0007-recommendation-apriori.md).

---

## 6. 기술 스택 (`requirements.txt`)

| 목적 | 라이브러리 |
|------|-----------|
| 웹 프레임워크 | `fastapi` |
| ASGI 서버 | `uvicorn[standard]` |
| 검증·설정 | `pydantic`, `pydantic-settings`, `python-dotenv` |
| LLM | `google-genai`(Gemini) |
| 프롬프트 템플릿 | `jinja2` |
| DB(추천) | `pymysql`, `cryptography` |
| 메트릭 | `prometheus-client` |
| 테스트(dev) | `pytest`, `httpx` |

- Python **3.12**(`Dockerfile: python:3.12-slim`). 실행: `uvicorn app.main:app --host 0.0.0.0 --port 8000`.
- 설정은 `.env` → `core/config.py`(pydantic-settings) → [ADR-0002](adr/0002-config-and-no-di.md), 키 목록은 [CONVENTION.md §8](CONVENTION.md).

---

## 7. 디렉토리 규약

```
tsarbombaChatBot/
├── app/
│   ├── main.py                 # 앱 조립: 로깅·CORS·미들웨어·라우터 3개·/health
│   ├── core/config.py          # pydantic-settings + @lru_cache
│   ├── chatbot/
│   │   ├── api/chat_router.py   # POST /chat
│   │   ├── service/{prompt_builder,gemini_client,sse}.py
│   │   └── schema/chat.py       # ChatRequest 및 하위 모델
│   ├── recommendation/
│   │   ├── api/recommendation_router.py
│   │   ├── service/{apriori,recommendation_service,repository}.py
│   │   └── schema/recommendation.py
│   └── monitoring/
│       ├── api/monitoring_router.py  # GET /metrics
│       ├── http.py             # HttpMetricsMiddleware
│       └── metrics.py          # Prometheus 메트릭 정의
├── templates/                  # Jinja2 시스템 프롬프트 (영어 실사용 + ko/ 참조본)
│   ├── system_base.j2  system_problem.j2  system_free.j2
│   └── ko/…                     # 한국어 참조본(실사용 X)
├── tests/                      # 순수함수 격리 테스트(pytest)
├── deploy/                     # docker-compose.yml, promtail-config.yml, .env.example
├── .github/workflows/deploy.yml
├── Dockerfile  requirements.txt  .env(.example)
└── docs/                       # ← 이 문서 세트
```

**규칙**
- 새 도메인은 `app/<domain>/{api,service,schema}`로 형제 추가하고 `main.py`에서 `include_router` 한 줄로 연결.
- 도메인 간 직접 import 금지(공유는 `core`·`monitoring/metrics`만).
- 프롬프트 문자열은 Python에 하드코딩하지 않고 `templates/*.j2`에만 둔다 → [ADR-0004](adr/0004-prompt-as-jinja-templates.md).

---

## 8. 관련 문서

- 결정 전체: [`adr/`](adr/) (0001~0009)
- 규약(스키마·에러·로깅·테스트·설정): [`CONVENTION.md`](CONVENTION.md)
- 프롬프트 설계 상세: [`prompt-engineering.md`](prompt-engineering.md)
- 문서 체계·읽는 순서·알려진 불일치: [`README.md`](README.md)
