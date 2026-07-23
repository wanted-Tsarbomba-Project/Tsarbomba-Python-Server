# ADR-0006 — Spring↔FastAPI 경계 계약: snake_case JSON, 공유 에러코드, X-Trace-Id, PII 미로깅

> 상태: **accepted**
> 관련: [ADR-0003](0003-sse-streaming-contract.md), [ADR-0008](0008-observability.md), [CONVENTION §3](../CONVENTION.md)

## 맥락

이 서버는 독립 서비스가 아니라 Spring 백엔드(codebombalms) 전용 AI 마이크로서비스다. 두 서버는 프로세스가 다르지만 `/chat` 경계에서 약속을 공유해야 연동이 깨지지 않는다. 무엇을 계약으로 고정할지 정해야 했다.

## 결정

`/chat` 경계에서 아래 4가지를 **양쪽이 공유하는 계약**으로 고정한다.

1. **요청 JSON = snake_case.** Spring `FastApiChatRequest`가 `@JsonProperty("user_message")` 등으로 snake_case 직렬화하고, 이 서버 `ChatRequest`(Pydantic)가 같은 필드명으로 받는다. (필드 전체 목록은 [CONVENTION §3.1](../CONVENTION.md).)
2. **에러코드 공유.** AI 응답 실패는 `CHT-003`(`gemini_client.AI_RESPONSE_FAILED`) — Spring `ChatErrorCode.AI_RESPONSE_FAILED`와 코드·메시지 문자열까지 동일. SSE `event:error`로 전달.
3. **`X-Trace-Id` 전파.** Spring이 헤더로 상관 ID를 보내면(`FastApiChatClient`) 이 서버가 받아 로그에 `trace_id=`로 박는다. 헤더 없으면 `trace_id=None`.
4. **PII 미로깅.** 유저 입력 원문·AI 응답 본문은 로그에 남기지 않고 길이만(`user_message_length`).

호출 방향: **Spring → FastAPI 서버-투-서버**(WebClient). 프론트는 이 서버를 직접 부르지 않는다(CORS `localhost:8080`만 허용).

## 근거

- 두 서버가 필드명·에러코드를 공유하면 프론트/BE가 단일 규격으로 파싱·처리할 수 있다. 한쪽이 이름을 바꾸면 연동이 깨지므로 **변경 시 양쪽을 같이 본다**.
- snake_case인 이유: chatbot 경계는 Spring 어댑터가 그 계약으로 고정되어 있다(recommendation은 반대로 camelCase — 호출 성격이 달라서, [ADR-0007](0007-recommendation-apriori.md)).
- `X-Trace-Id`로 두 서비스 로그를 같은 ID로 엮으면 장애 추적이 한 화면에서 된다 → [ADR-0008](0008-observability.md).

## 비고

- Spring 측 활성화 토글: `application.yml`의 `spring.profiles.active`에서 `mock` 제거 시 `MockAiChatClient`(@Profile("mock")) → `FastApiChatClient`(@Profile("!mock")) 전환. mock 제거 후엔 이 서버가 반드시 떠 있어야 한다.
- ⚠️ **주의**: 옛 handoff 문서는 비스트리밍 응답(`ChatResponse{answer,is_answer_detected,...}`)을 서술했는데 그 계약은 폐기됐다. 현재 응답은 SSE 스트림뿐 → [ADR-0003](0003-sse-streaming-contract.md), [알려진 불일치](../README.md).
- 정상 경로 HTTP는 항상 200 — Spring은 이벤트 타입으로 성공/실패를 구분한다.
