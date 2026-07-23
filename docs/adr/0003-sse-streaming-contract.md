# ADR-0003 — 채팅 응답은 SSE 스트리밍, 토큰 JSON 래핑, 에러=스트림 이벤트

> 상태: **accepted**
> 관련: Spring `chatbot` **ADR-0005**(스트리밍 응답 표준 — 봉투 면제), [ADR-0006](0006-spring-boundary-contract.md), [CONVENTION §4](../CONVENTION.md)

## 맥락

Gemini 응답을 **다 만든 뒤 JSON 한 방(`ChatResponse`)** 으로 주던 `/chat`은, 답이 길거나 느리면 학습자가 완성될 때까지 **빈 화면**을 봐야 했다. Spring→브라우저까지 전 구간을 실시간 스트리밍으로 통일하기로 했고, 이 서버는 그중 FastAPI 구간이다.
동시에 Spring 공통 표준(ADR-0004)은 모든 응답을 `ApiResponse` **봉투**로 감싸도록 요구한다. 봉투는 "완성된 본문 1덩어리"를 감싸는 구조라 토큰 스트림엔 씌울 수 없다.

## 결정

**`/chat`은 SSE(`text/event-stream`)로 토큰을 즉시 흘리고, 봉투 표준에서 면제한다.** 대신 아래 규격을 고정한다.

- **전송**: `StreamingResponse(media_type="text/event-stream")` + 헤더 `Cache-Control: no-cache`, `X-Accel-Buffering: no`(프록시 버퍼링 방지).
- **본문 토큰**: event 이름 없는 프레임, `data:`에 **JSON** `{"t":"<조각>"}`. `ensure_ascii=False`.
- **완료**: `event: done`, `data:` = `{"promptTokens","completionTokens","totalTokens}`(사용량 메타). 정상 종료 1회.
- **스트림 중 에러**: `event: error`, `data:` = `{"code":"CHT-003","message":...}`. 1회 후 종료. (`done` 대신 옴)
- **스트림 시작 전 검증 에러**: 아직 200/헤더가 커밋되지 않았으므로 표준 HTTP 에러 봉투 유지(ADR-0004). 즉 **봉투 면제는 "스트림 시작 이후"에만**.

구현: `gemini_client.stream_gemini()`가 `generate_content_stream`을 돌며 토큰마다 `sse.token_frame`, 끝에 `sse.done_frame`, 예외 시 `sse.error_frame` 후 종료.

## 근거

- **토큰을 JSON으로 감싸는 이유**: SSE는 빈 줄(`\n\n`)이 이벤트 종료다. Gemini 코드블록 토큰의 `\n`을 생텍스트 `data:`에 넣으면 프레임이 둘로 쪼개져 파싱이 깨진다. `json.dumps`가 `\n`을 이스케이프 두 글자로 바꿔 한 줄로 유지한다.
- **에러를 이벤트로 보내는 이유**: 스트림이 시작되면 `200 OK`+`text/event-stream` 헤더가 이미 커밋된 뒤라, 그 후 발생한 에러를 다른 상태코드 JSON으로 되돌릴 수 없다. 그래서 에러도 스트림 안의 이벤트다.
- **봉투 면제가 임의 일탈이 아닌 이유**: Spring ADR-0005가 스트리밍용 단일 공통 규칙을 세워 예측 가능성을 지킨다. 이 서버는 그 표준의 FastAPI 구현이다.
- `sse.py`는 `app/*` 의존이 없는 **순수 함수 모음**이라 Gemini·네트워크 없이 격리 테스트가 된다(`test_sse.py`).

## 비고

- 정상 경로는 항상 HTTP **200**. Gemini 실패도 200 바디의 `event:error`로 온다 → **소비자는 이벤트 타입으로 성공/실패를 구분**해야 한다(HTTP 상태 아님).
- `room` 이벤트(새 방 ID)는 **Spring이** 앞에 붙인다. 이 서버는 안 보낸다.
- `X-Accel-Buffering: no`는 응답 헤더만 제공한다. 실제 nginx `proxy_buffering off`는 인프라 책임.
- 옛 `ChatResponse`의 `is_answer_detected`/`retry_count`/토큰 필드는 **제거됨**(미구현 죽은 필드). 사용량은 이제 `done` 이벤트로만 → [알려진 불일치](../README.md).
- 에러코드 `CHT-003`은 Spring `ChatErrorCode.AI_RESPONSE_FAILED`와 문자열까지 공유 → [ADR-0006](0006-spring-boundary-contract.md).
