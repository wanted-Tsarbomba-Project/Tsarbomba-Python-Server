# CONVENTION — 코딩·API·에러·로깅·테스트·설정 규약

> 이 서버에서 **매번 지키는 살아있는 규약**. "왜"는 [`adr/`](adr/), 전체 구조는 [`ARCHITECTURE.md`](ARCHITECTURE.md).
> 스키마 필드·에러 규격은 재구성의 계약이므로 여기에 전부 박제한다.

---

## 1. 레이어링 (도메인 내부)

각 도메인은 **경량 3계층**만 둔다 → [ADR-0001](adr/0001-domain-package-lightweight-layering.md).

```
app/<domain>/
├── api/        # FastAPI 라우터 (@router.post/get). 입출력 변환·HTTP 관심사만.
├── service/    # 비즈니스 로직 (프롬프트 조립, Gemini 호출, 알고리즘, DB 접근).
└── schema/     # Pydantic 모델 (요청/응답 DTO).
```

- `domain/`·`entity`·`value-object`·`repository 인터페이스`·`application` 같은 풀세트 DDD 계층은 **두지 않는다**(Spring 백엔드와 다름 — 이유는 ADR-0001).
- 도메인 간 직접 import 금지. 공유는 `core/config.py`와 `monitoring/metrics.py`뿐.
- DI 컨테이너(`Depends`) 대신 필요 시 `get_settings()`·`_get_client()`를 **직접 호출(pull)** → [ADR-0002](adr/0002-config-and-no-di.md).

---

## 2. 네이밍

- 파이썬 식별자·파일·JSON 내부 필드: **snake_case**.
- 함수/변수: 서술형(`build_system_prompt`, `find_active_problem_set_ids`). 모듈 내부 전용은 `_` 접두(`_build_contents`, `_get_client`).
- 상수: `UPPER_SNAKE`(`MIN_SUPPORT_COUNT`, `AI_RESPONSE_FAILED`, `EVENT_DONE`).
- Prometheus 메트릭: `python_*`, `recommendation_python_*` 접두(Spring 메트릭과 구분).

---

## 3. API 스타일 — 두 계약이 공존한다 (의도적)

이 서버는 **호출자에 맞춰 두 JSON 스타일**을 쓴다. 섞지 말 것.

| 도메인 | JSON 스타일 | 결정 주체 | 구현 |
|--------|-------------|-----------|------|
| `chatbot` (`/chat`) | **snake_case** | Spring `FastApiChatRequest`가 `@JsonProperty("user_message")`로 보냄 | Pydantic 필드명 그대로(`user_message`) |
| `recommendation` (`/internal/...`) | **camelCase** | Spring 표준 JSON(camel) | Pydantic `Field(alias="userId")` + `ConfigDict(validate_by_name/alias)`, 응답은 `response_model_by_alias=True` |

- chatbot이 snake_case인 이유: Spring 어댑터가 이 계약으로 직렬화하도록 고정되어 있고 필드명을 공유하기 때문 → [ADR-0006](adr/0006-spring-boundary-contract.md).
- recommendation이 camelCase인 이유: 일반 REST(내부 배치)라 Java/JSON 관례(camel)를 따르되 파이썬 내부는 snake로 두려고 alias 사용.

### 3.1 chatbot 요청 스키마 (`app/chatbot/schema/chat.py`) — 전부 snake_case

```
ChatRequest
├── user_message: str                                 # 필수
├── problem_set: ProblemSetInfo | None                # 있으면 문제풀이 모드
│     ├── problem_set_id: int
│     ├── title: str
│     └── description: str
├── problems: list[ProblemInfo] | None
│     ├── title: str
│     ├── content: str
│     ├── problem_type: str                           # "CODE" | "TEXT"
│     ├── answer: str | None                          # 채점 정답(직접노출 금지 대상)
│     ├── explanation: str | None                     # 해설(없을 수 있음)
│     └── submitted_answer: str | None                # 유저 제출답(없을 수 있음)
├── session_progress: SessionProgress | None
│     └── current_problem_number: int
├── dataset: DatasetInfo | None
│     └── meta_data: str                              # JSON 문자열. 계약: {"columns":[{"name","examples":[...]}]}
└── conversation_history: list[ConversationMessage] | None
      ├── role: str                                   # "user" | "ai"
      └── content: str
```

- 응답은 스키마 모델이 아니라 **SSE 스트림**이다(§4). 옛 `ChatResponse`는 제거됨 → [알려진 불일치](README.md).
- `dataset.meta_data`는 **문자열 안의 JSON**. `prompt_builder`가 파싱하며, 깨지면 조용히 빈 리스트로 폴백(§ prompt-engineering).

### 3.2 recommendation 스키마 (`app/recommendation/schema/recommendation.py`) — camelCase alias

```
요청 RecommendationGenerateRequest
└── recommendation_count: int  (alias recommendationCount, 기본 3, gt=0)

응답 RecommendationGenerateResponse
└── recommendations: [ UserProblemSetRecommendationResponse ]
      ├── user_id            (alias userId)
      └── problem_sets       (alias problemSets): [ ProblemSetRecommendationResponse ]
            ├── problem_set_id  (alias problemSetId)
            ├── support: float
            ├── confidence: float
            ├── lift: float
            ├── rank_no        (alias rankNo)
            └── algorithm: str  # "ASSOCIATION_RULE_BRUTE_FORCE"
```

---

## 4. SSE 응답 규격 (chatbot) — 상세는 [ADR-0003](adr/0003-sse-streaming-contract.md)

`text/event-stream`, 헤더 `Cache-Control: no-cache`, `X-Accel-Buffering: no`. 프레임 3종(`app/chatbot/service/sse.py`):

```
(event 없음)  data: {"t":"<토큰 조각>"}                                        # 본문 토큰, N회
event: done   data: {"promptTokens":12,"completionTokens":80,"totalTokens":92} # 정상 종료 1회
event: error  data: {"code":"CHT-003","message":"AI 응답 생성에 실패했습니다."}  # 스트림 중 실패 1회 후 종료
```

- **토큰 본문은 반드시 JSON으로 감싼다**(`{"t":...}`). 토큰 내 줄바꿈(`\n`)이 생텍스트면 SSE 프레임(빈 줄=종료)을 깨뜨리기 때문. `ensure_ascii=False`로 한글 유지.
- 정상 경로는 항상 HTTP **200**. Gemini 실패도 200 바디 안의 `event:error`로 온다 → 소비자는 **HTTP 상태가 아니라 이벤트 타입**으로 성공/실패 구분.
- `room` 이벤트(새 방 ID)는 **Spring이 붙인다** — 이 서버는 안 보낸다.

---

## 5. 에러 처리

두 도메인이 다른 방식을 쓴다(스트리밍이라 그렇다).

| 상황 | 처리 | 코드/상태 |
|------|------|-----------|
| 채팅 스트림 **도중** Gemini 예외 | `logger.exception` 후 `sse.error_frame` 1개 yield하고 종료 | `event:error`, `code=CHT-003`(Spring `ChatErrorCode.AI_RESPONSE_FAILED`와 **공유**) |
| 채팅 스트림 **시작 전** 검증 실패 | (현재 진입부 동기검증 없음) 발생 시 표준 HTTP 에러 유지 | Spring ADR-0004 봉투(스트림 시작 전이므로) |
| 추천 DB 조회 실패 | `repository`가 `RecommendationRepositoryError` raise → 라우터가 잡아 `HTTPException` | **503** Service Unavailable |
| 요청 스키마 불일치 | FastAPI/Pydantic 자동 | 422 Unprocessable Entity |

- 도메인 에러코드는 `{DOMAIN}-{NNN}`(Spring 컨벤션 공유). 현재 이 서버가 쓰는 것: `CHT-003`.
- **불가능한 시나리오용 방어 코드는 만들지 않는다**(YAGNI). 예: `dataset.meta_data` 파싱 실패는 빈 리스트 폴백으로 조용히 처리.

---

## 6. 로깅 → [ADR-0008](adr/0008-observability.md)

- **stdout으로 흘린다.** `app/main.py`가 `logging.basicConfig(level=INFO, stream=sys.stdout)`로 앱 로거(`app.*`)를 stdout에 연결(없으면 uvicorn이 자기 로거만 설정해 `logger.info`가 root에서 버려짐).
- **구조적 로그**: `event=<이름> key=value ...` 한 줄 포맷. 예:
  - `event=chatbot_chat_started history_len=.. user_message_length=.. trace_id=..`
  - `event=chatbot_gemini_failed code=CHT-003 trace_id=..`
  - `event=recommendation_python_generation_completed inputUsers=.. algorithmMs=.. ...`
- **PII 미로깅**: 유저 입력 원문·AI 응답 본문을 로그에 남기지 않는다. **길이(`user_message_length`)만** 남긴다.
- **trace 상관**: Spring이 `X-Trace-Id` 헤더로 보낸 값을 `trace_id=`로 박아 두 서비스 로그를 같은 ID로 엮는다. 헤더 없으면 `trace_id=None`.

---

## 7. 테스트

- **격리 우선**: DB·Gemini·네트워크 없이 순수 입출력만 검증(`tests/`).
  - `test_sse.py` — 프레임 직렬화기(줄바꿈·따옴표·중괄호 토큰이 프레임을 안 깨는지, `\n\n` 종료).
  - `test_stream_gemini.py` — 가짜 Gemini 청크를 `monkeypatch`로 주입해 토큰→done 순서·에러 프레임·빈 토큰 스킵 검증.
  - `test_http_metrics.py` — 미들웨어 라벨/측정.
- 외부 의존은 **monkeypatch로 대체**(`monkeypatch.setattr(gemini_client, "_get_client", …)`). 실제 API 키 불필요.
- 실행: `pytest -q`.

---

## 8. 설정 (`.env` → `core/config.py`) → [ADR-0002](adr/0002-config-and-no-di.md)

`pydantic_settings.BaseSettings`가 `.env`를 읽는다. `@lru_cache`로 프로세스당 한 번만 로드(싱글톤).

| 키(.env) | 필드 | 기본값(config) | 용도 |
|----------|------|----------------|------|
| `GEMINI_API_KEY` | `gemini_api_key: str` | (필수, 기본 없음) | Gemini 인증 |
| `GEMINI_MODEL` | `gemini_model: str` | `gemini-2.5-flash-preview-05-20` | 모델명 |
| `DEFAULT_MAX_LENGTH` | `default_max_length: int` | `1000` | 응답 길이 상한(프롬프트에 주입) |
| `DB_HOST` | `db_host: str` | `localhost` | 추천 DB 호스트 |
| `DB_PORT` | `db_port: int` | `3306` | 추천 DB 포트 |
| `DB_NAME` | `db_name: str` | `""` | 추천 DB 이름 |
| `DB_USERNAME` | `db_username: str` | `""` | 추천 DB 유저 |
| `DB_PASSWORD` | `db_password: str` | `""` | 추천 DB 비번 |

- **민감정보(`GEMINI_API_KEY`, `DB_PASSWORD`)는 `.env`에만**(gitignore). 공용 파일엔 `.env.example`에 자리만.
- ⚠️ `default_max_length`·`GEMINI_MODEL` 기본값이 `.env.example`/구문서와 어긋난다 → **`.env` 실제값이 진실** → [알려진 불일치](README.md).
- 접근: `get_settings().gemini_api_key` 처럼 pull. 테스트는 `get_settings.cache_clear()` 또는 monkeypatch로 우회.
