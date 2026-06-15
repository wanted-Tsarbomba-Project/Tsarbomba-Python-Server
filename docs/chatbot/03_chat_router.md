# 3강. chat_router.py — 실제 엔드포인트

`app/chatbot/api/chat_router.py`:

```python
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.chatbot.schema.chat import ChatRequest
from app.chatbot.service.prompt_builder import build_system_prompt
from app.chatbot.service.gemini_client import stream_gemini
from app.core.config import get_settings

router = APIRouter()


@router.post("/chat")
def chat(request: ChatRequest) -> StreamingResponse:
    settings = get_settings()
    history_len = len(request.conversation_history or [])
    print(f"[chat] user_message={request.user_message!r} history_len={history_len}")
    system_prompt = build_system_prompt(request, settings.default_max_length)

    return StreamingResponse(
        stream_gemini(request, system_prompt),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
```

## ① `router = APIRouter()` — 미니 app

`APIRouter`는 "엔드포인트만 모으는 작은 app". 여기 `/chat`을 등록해두면 main.py에서
`app.include_router(router)` 로 통째로 합쳐진다. Spring의 `@RestController` 클래스 한 개 = 이 라우터 파일 한 개.

## ② `@router.post("/chat")` — 등록

"POST /chat 오면 → `chat` 함수로 답해"를 등록. (`@app.get`은 GET, 여긴 POST)
Spring `@PostMapping("/chat")`.

## ③ `request: ChatRequest` — 타입힌트의 힘

```python
def chat(request: ChatRequest) -> StreamingResponse:
#     └파라미터┘ └타입┘        └리턴 타입┘
```

이 타입힌트 한 줄이:
1. 요청 본문(JSON)을 받아서
2. **자동으로 `ChatRequest` 객체로 변환**
3. **자동으로 검증** (필수 필드 없으면 422 자동 응답)
4. 코드에선 `request.user_message` 로 객체처럼 사용

Spring `@RequestBody` + `@Valid` 가 타입힌트 한 줄로 된다. (`ChatRequest` 구조 → 4강)

## ④ 함수 본문 — 요청마다 실행

```python
settings = get_settings()                                   # 설정 (5강)
history_len = len(request.conversation_history or [])        # None이면 빈 리스트
print(f"[chat] ... {request.user_message!r} ...")           # 로그 (f-string)
system_prompt = build_system_prompt(request, settings.default_max_length)  # 프롬프트 조립 (6강)
```

- `len(...)` = 길이 (자바 `.size()`)
- `... or []` = "있으면 그것, 없으면(None) 빈 리스트" (None에 len 쓰면 에러 → 방어)
- `print(...)` = 로그 (Spring `log.info`). `f"...{변수}..."` = f-string (값 끼워넣기). `!r` = 따옴표 포함 디버그 출력

## ⑤ `return StreamingResponse(...)` — 스트리밍 응답

```python
return StreamingResponse(
    stream_gemini(request, system_prompt),   # 토큰을 흘릴 제너레이터 (7강)
    media_type="text/event-stream",          # SSE 형식 선언
    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},  # 즉시 흘리게
)
```

`/health`는 dict 하나 던지면 끝이지만, `/chat`은 응답을 **토큰 단위로 찔끔찔끔 흘리는** 스트리밍이라
`StreamingResponse`를 쓴다. (스트리밍 자세히 → 7강)

## health 와 비교

| | `/health` (2강) | `/chat` (3강) |
|--|----------------|---------------|
| 메서드 | `@app.get` | `@router.post` |
| 입력 | 없음 | `request: ChatRequest` (자동 파싱+검증) |
| 출력 | dict → JSON (즉답) | StreamingResponse (스트리밍) |

뼈대는 같다: **URL을 함수에 등록 → 요청 오면 함수 실행 → 응답.** 입출력만 복잡해진 것.

> 이 `/chat`을 부르는 쪽이 Spring `FastApiChatClient` 다 (`webClient.post().uri("/chat")`).
> → 경계 설명: [../fastapi/04_domain_separation_and_coupling.md](../fastapi/04_domain_separation_and_coupling.md)

---

→ 다음: [04_schema_dto.md](04_schema_dto.md) (ChatRequest가 어떻게 생겼나)
