# ADR-0005 — `system_instruction`(불변) vs `contents`(가변) 분리로 implicit caching 극대화

> 상태: **accepted**
> 관련: [ADR-0004](0004-prompt-as-jinja-templates.md), [prompt-engineering.md](../prompt-engineering.md)

## 맥락

Gemini는 요청 간 `system_instruction`이 동일하면 자동으로 캐시해 입력 토큰 비용을 크게 할인한다(implicit caching). 한 채팅방에서 매 요청 보내는 데이터 중 일부는 변하지 않고(문제·정답·데이터셋) 일부는 변한다(대화이력·현재문제·user_message). 무엇을 어디에 실을지 정해야 캐시가 산다.

## 결정

**같은 채팅방에서 안 변하는 데이터 → `system_instruction`, 변하는 데이터 → `contents`.**

| 데이터 | 변동 | 위치 |
|--------|------|------|
| 역할·금지·응답포맷 규칙 | 불변 | `system_instruction`(템플릿) |
| `problem_set`, 전체 `problems[]`+`answer`, `dataset` | 불변 | `system_instruction`(템플릿) |
| `conversation_history` | 매 요청 변동 | `contents`(네이티브 멀티턴 매핑) |
| `session_progress`(현재 문제 번호) | 문제 전환 시 변동 | `contents`(user_message prefix) |
| 제출답 요약(`submitted_answers`) | 변동 | `contents`(user_message prefix) |
| `user_message` | 매 요청 변동 | `contents` |

구현(`gemini_client._build_contents`):
- `conversation_history`를 Gemini `Content`로 매핑: `role="ai" → "model"`, 그 외 `"user"`.
- 가변 컨텍스트(현재 문제번호·제출답)는 **user_message 앞에 prefix**로 합쳐 하나의 user turn으로 넣는다.
- `generate_content_stream(model, contents, config=GenerateContentConfig(system_instruction=프롬프트))`.

## 근거

- `session_progress`를 `system_instruction`에 넣으면 문제 전환마다 캐시가 깨진다. user_message에 prefix로 합치면 **캐시 유지 + 더미 응답 불필요 + 단순**.
- `conversation_history`는 Gemini 네이티브 멀티턴 구조를 쓴다. 시스템 프롬프트에 텍스트로 우겨넣으면 role 구분이 약해지고 컨텍스트 윈도우를 낭비한다.
- 불변 블록(규칙+문제+정답+데이터셋)을 전부 `system_instruction`에 모으면, 같은 방의 후속 요청이 그 큰 블록을 캐시 히트시켜 비용을 아낀다.

## 비고

- 그래서 [ADR-0004](0004-prompt-as-jinja-templates.md)의 "고정 부분(영어 규칙)을 함부로 바꾸지 말라"가 중요하다 — 텍스트가 바뀌면 캐시가 깨진다. 동적 데이터는 변수라 값이 같으면 동일 텍스트라 캐시에 영향 없다.
- 사용량 메타(`usage_metadata`)는 스트림 청크에서 모아 `done` 이벤트로 전달 → [ADR-0003](0003-sse-streaming-contract.md).
