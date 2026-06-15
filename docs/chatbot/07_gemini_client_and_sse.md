# 7강. gemini_client.py + sse.py — 스트리밍 (클라이맥스)

새 개념 둘: **제너레이터(`yield`)** 와 **스트리밍**.

## 먼저: 스트리밍이 뭐고 왜

```
[일반]  질문 → (몇 초 대기) → 답변 전체 한 방에
[스트림] 질문 → 답 답변 변이 토 토큰 단위로 실시간
```

ChatGPT가 글자 하나씩 나오는 그것. 사용자 대기 체감이 준다. 이 서버가 도입한 게 이거.

## 핵심: 제너레이터와 `yield` (자바엔 없음)

```python
def stream_gemini(...) -> Iterator[str]:
    ...
    yield sse.token_frame(chunk.text)   # return이 아니라 yield
```

| `return` | `yield` |
|----------|---------|
| 값 1개 주고 **함수 끝** | 값 1개 주고 **잠깐 멈춤, 또 줄 수 있음** |
| 한 방에 다 줌 | 하나씩 흘려보냄 |

`yield` 들어간 함수 = **제너레이터**. 호출해도 바로 안 돌고, "값을 하나씩 꺼내 쓸 수 있는 흐름"을 준다.

```python
for frame in stream_gemini(...):   # yield할 때마다 frame을 하나씩 받음
    보내기(frame)                   # 받는 즉시 사용자에게 전송
```

비유: `return`=한 상 차리기, `yield`=만드는 족족 한 접시씩 내가기.

---

## gemini_client.py — `app/chatbot/service/gemini_client.py`

### ① 상수 & 로거

```python
logger = logging.getLogger(__name__)                  # Spring의 private static Logger
AI_RESPONSE_FAILED = "CHT-003"                         # 에러코드 상수
AI_RESPONSE_FAILED_MESSAGE = "AI 응답 생성에 실패했습니다."
```

대문자 = 상수 관습(파이썬엔 `final` 없음). 이 `CHT-003`은 **백엔드와 공유** (아래 ★).

### ② `_get_client` — Gemini 클라이언트 싱글톤

```python
@lru_cache()
def _get_client() -> genai.Client:
    return genai.Client(api_key=get_settings().gemini_api_key)
```

5강 `@lru_cache` 패턴 그대로. 클라이언트를 한 번만 만들어 재사용.

### ③ `_build_contents` — 대화 기록을 Gemini 형식으로

```python
for msg in request.conversation_history:
    role = "model" if msg.role == "ai" else "user"   # 삼항: A if 조건 else B
    contents.append(types.Content(role=role, parts=[types.Part(text=msg.content)]))
```

- `A if 조건 else B` = 파이썬 삼항 (자바 `조건 ? A : B` 와 **순서 반대**)
- 우리 DTO는 `"ai"`, Gemini는 `"model"` → 이름 변환
- `.append` = 리스트 추가 (자바 `add`)

### ④ 리스트 컴프리헨션 (파이썬 시그니처 문법)

```python
submitted = [
    f"Problem #{i + 1} ({p.title}): {p.submitted_answer}"
    for i, p in enumerate(request.problems)
    if p.submitted_answer
]
```

```
[ 만들것  for 변수 in 대상  if 조건 ]
   map식      반복           filter
```

자바 Stream `filter`+`map`+`collect`를 한 줄로. `enumerate` = 순회하며 인덱스(`i`)도 같이 줌.

### ⑤ 컨텍스트 합치기

```python
current_text = "\n\n".join(prefix_parts) + "\n\n" + request.user_message
```
`"구분자".join(리스트)` = 자바 `String.join` (단 구분자가 앞). 시스템 프롬프트(불변)와 분리해
변하는 맥락만 user_message에 붙임 → **Gemini 프롬프트 캐시 히트 유지(비용·속도 이득).**

### ⑥ `stream_gemini` — 제너레이터 (심장)

```python
def stream_gemini(request, system_prompt) -> Iterator[str]:
    settings = get_settings()
    client = _get_client()
    contents = _build_contents(request)

    usage = None
    try:
        stream = client.models.generate_content_stream(   # 스트리밍 호출 (일반은 generate_content)
            model=settings.gemini_model,
            contents=contents,
            config=types.GenerateContentConfig(system_instruction=system_prompt),
        )
        for chunk in stream:                       # Gemini가 토큰 덩어리를 흘림
            if chunk.text:
                yield sse.token_frame(chunk.text)  # 받는 족족 SSE로 흘림
            if getattr(chunk, "usage_metadata", None) is not None:
                usage = chunk.usage_metadata       # 사용량 챙김
        yield sse.done_frame(_usage_payload(usage))  # 끝 신호 + 사용량
    except Exception:
        logger.exception("Gemini 스트리밍 중 예외")
        yield sse.error_frame(AI_RESPONSE_FAILED, AI_RESPONSE_FAILED_MESSAGE)  # 에러 프레임
```

- `generate_content_stream` = 스트리밍 버전. `chunk`(토큰 덩어리)가 올 때마다 즉시 `yield`
- `getattr(chunk, "usage_metadata", None)` = "있으면 그 값, 없으면 None" (속성 안전 접근)
- `except Exception` = 모든 예외 잡기. 도중 죽어도 깔끔한 error 프레임 보내고 종료
- **return이 하나도 없고 전부 `yield`** = "값을 흘려보내는 흐름"

---

## sse.py — `app/chatbot/service/sse.py` (순수 함수, 결합도 모범)

`import json` + `Optional` 뿐, Gemini·FastAPI를 전혀 모름 → 단독 테스트 가능.

```python
EVENT_DONE = "done"
EVENT_ERROR = "error"

def _frame(data: str, event: Optional[str] = None) -> str:
    prefix = f"event: {event}\n" if event else ""
    return f"{prefix}data: {data}\n\n"          # SSE: data:내용\n\n (빈 줄=이벤트 끝)

def token_frame(text: str) -> str:               # 본문 토큰
    return _frame(json.dumps({"t": text}, ensure_ascii=False))

def done_frame(usage: dict) -> str:              # 완료 + 사용량
    return _frame(json.dumps(usage, ensure_ascii=False), event=EVENT_DONE)

def error_frame(code: str, message: str) -> str: # 에러
    return _frame(json.dumps({"code": code, "message": message}, ensure_ascii=False),
                  event=EVENT_ERROR)
```

- `json.dumps` = 파이썬 객체 → JSON 문자열 (6강 `loads`의 반대). `ensure_ascii=False` = 한글 그대로.
- `Optional[str]` = "str 또는 None" (4강과 같음, 3.9 호환 표기. `str | None`은 3.10+라 못 씀)
- **왜 토큰을 JSON으로 감싸나?** 토큰에 줄바꿈(`\n`)이 들어가면 SSE 프레임(빈 줄=이벤트 끝)이 깨진다.
  JSON으로 감싸면 `\n`이 안전하게 escape됨. (파일 docstring에 명시)

---

## ★ 공유 에러코드 — 백엔드와의 계약

우리 `AI_RESPONSE_FAILED = "CHT-003"` 은 **백엔드와 공유**된다.
백엔드 `chatbot/domain/exception/ChatErrorCode.java`:

```java
public enum ChatErrorCode implements ErrorCode {
    CHAT_ROOM_NOT_FOUND("CHT-001", "채팅방을 찾을 수 없습니다."),
    CHAT_ROOM_FORBIDDEN("CHT-002", "채팅방에 접근 권한이 없습니다."),
    AI_RESPONSE_FAILED("CHT-003", "AI 응답 생성에 실패했습니다.");
}
```

우리가 `error_frame("CHT-003", ...)`로 내보내면 백엔드가 같은 코드로 처리한다. **양쪽 같이 본다.**
(→ [../fastapi/04_domain_separation_and_coupling.md](../fastapi/04_domain_separation_and_coupling.md))

---

## 전체 흐름

```
chat_router (3강)
  └ StreamingResponse( stream_gemini(...) )   ← 제너레이터를 넘김
       │  yield 할 때마다 한 프레임씩
  stream_gemini
    1. _build_contents() 대화 조립
    2. generate_content_stream() Gemini 스트림
    3. chunk마다 → sse.token_frame() → yield
    4. 끝 → sse.done_frame() / 에러 → sse.error_frame()
       │
       ▼  "data: {...}\n\n" 문자열
  FastAPI → Spring 백엔드 → 사용자에게 실시간 전송
```

## 🎉 강의 완주

요청 들어와 응답 나갈 때까지 전 구간을 다 읽었다. 직접 띄워보기:
```
uvicorn app.main:app --reload --port 8000
```
다음 단계: `tests/`(test_sse, test_stream_gemini) 읽으며 각 부품 검증법 보기,
또는 [../fastapi/04_domain_separation_and_coupling.md](../fastapi/04_domain_separation_and_coupling.md)의 DI 리팩터링 실습.
