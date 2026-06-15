# 01. FastAPI는 프레임워크다 (Spring 자리)

## 가장 먼저 풀어야 할 오해

**FastAPI는 프레임워크다. REST API 같은 "통신 방식"이 아니다.**

| 구분 | 정체 | 같은 범주 |
|------|------|-----------|
| **FastAPI** | 파이썬 **웹 프레임워크** | Spring(Boot), Express, Django |
| **REST API** | **아키텍처 스타일 / 통신 규약** | GraphQL, gRPC, SOAP |

- **REST** = "HTTP로 자원을 어떻게 주고받을지"에 대한 설계 규칙(스타일). 코드가 아니다.
- **FastAPI** = 그 규칙을 따르는 서버를 실제로 만들어주는 도구(프레임워크).

비유: REST = 교통 규칙, FastAPI/Spring = 그 규칙대로 굴러가는 자동차.

> 정리: 이 서버는 **"FastAPI로 만든 (거의) REST 스타일 API 서버"** 다.
> FastAPI = 프레임워크(Spring 자리), REST = 그 위에서 구현하는 통신 스타일.

한 가지 더: FastAPI도 혼자 안 돈다. **FastAPI(프레임워크) + uvicorn(ASGI 서버)** 조합이다.
Spring Boot가 Tomcat을 내장하듯, 파이썬은 `uvicorn app.main:app` 으로 서버를 띄워 앱을 얹는다.
(→ [03_app_lifecycle.md](03_app_lifecycle.md))

---

## Spring ↔ FastAPI 1:1 대응 (실제 코드)

### ① 컨트롤러 / 라우터

**Spring 백엔드** — `chatbot/presentation/api/ChatMessageController.java`:

```java
@RestController
@RequestMapping("/api/v1/chat")
@RequiredArgsConstructor              // 생성자 DI (Lombok)
public class ChatMessageController {

    private final ChatMessageQueryUseCase chatMessageQueryUseCase;  // 주입됨

    @GetMapping("/{roomId}/messages")
    public ResponseEntity<...> listMessages(
            @PathVariable Long roomId,
            @AuthenticationPrincipal Long userId) {
        ...
    }
}
```

**우리 FastAPI** — `app/chatbot/api/chat_router.py`:

```python
router = APIRouter()

@router.post("/chat")
def chat(request: ChatRequest) -> StreamingResponse:
    ...
```

| Spring | FastAPI |
|--------|---------|
| `@RestController` 클래스 | `APIRouter()` 객체 |
| `@GetMapping`/`@PostMapping` | `@router.get`/`@router.post` |
| `@PathVariable` | 함수 인자 (path param) |
| `@RequestBody DTO` | `request: ChatRequest` 타입힌트 |

### ② 요청 DTO

**Spring** — `chatbot/presentation/api/request/ChatMessageRequest.java`:

```java
public record ChatMessageRequest(
        @NotBlank(message = "메시지를 입력해주세요.")
        String userMessage
) {}
```

**우리** — `app/chatbot/schema/chat.py` (Pydantic):

```python
class ChatRequest(BaseModel):
    user_message: str            # 필수 (Optional 아님)
    ...
```

`record` + `@NotBlank`(Bean Validation) 의 역할을 **Pydantic `BaseModel` + 타입힌트** 가 한다.
필수 필드면 안 보냈을 때 Spring은 `@Valid`가, FastAPI는 Pydantic이 **자동으로 검증 에러**를 낸다.
(→ DTO 자세히: [../chatbot/04_schema_dto.md](../chatbot/04_schema_dto.md))

---

## 데코레이터(`@`) vs 자바 어노테이션 — 핵심 차이

생긴 건 둘 다 `@`로 비슷한데 **동작이 다르다.**

| | 자바 `@GetMapping` | 파이썬 `@router.post` |
|--|-------------------|----------------------|
| 정체 | **메타데이터** (표식/메모) | **실제로 실행되는 함수** |
| 동작 | 프레임워크가 나중에 리플렉션으로 읽음 | 그 자리에서 **즉시 실행**됨 |

- 자바 어노테이션 = **포스트잇 메모**. 붙여만 두면 스프링이 나중에 읽어 처리. 어노테이션 자체는 아무 일도 안 함.
- 파이썬 데코레이터 = **진짜 함수 호출**. 서버가 뜰 때(파일 로딩 시) 즉시 실행돼서, 아래 함수를 라우터에 **등록**한다.

```python
@router.post("/chat")     # ← 서버 시작 시 즉시 실행 → "POST /chat 오면 이 함수" 라고 등록
def chat(request):        #    chat() 함수 자체는 이때 실행 안 됨
    ...                   #    실제 요청이 와야 그제서야 실행
```

> 즉 데코레이터가 한 일은 **"URL ↔ 함수 연결을 등록"** 이지 함수 실행이 아니다.
> 이 "등록 vs 실행" 감각은 [03_app_lifecycle.md](03_app_lifecycle.md)에서 더 깊이 다룬다.
