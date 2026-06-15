# 4강. schema/chat.py — Pydantic DTO

3강에서 "`request: ChatRequest` 한 줄로 파싱·검증 자동"이라 했다. 그게 가능한 이유가 이 파일.
Spring의 DTO/record 모음집에 해당. `app/chatbot/schema/chat.py`:

```python
from typing import Optional
from pydantic import BaseModel


class ProblemSetInfo(BaseModel):
    problem_set_id: int
    title: str
    description: str


class ProblemInfo(BaseModel):
    title: str
    content: str
    problem_type: str  # "CODE" or "TEXT"
    answer: Optional[str] = None
    explanation: str
    submitted_answer: Optional[str] = None


class SessionProgress(BaseModel):
    current_problem_number: int


class DatasetInfo(BaseModel):
    meta_data: str


class ConversationMessage(BaseModel):
    role: str  # "user" or "ai"
    content: str


class ChatRequest(BaseModel):
    user_message: str
    problem_set: Optional[ProblemSetInfo] = None
    problems: Optional[list[ProblemInfo]] = None
    session_progress: Optional[SessionProgress] = None
    dataset: Optional[DatasetInfo] = None
    conversation_history: Optional[list[ConversationMessage]] = None
```

## ① `class X(BaseModel)` — Pydantic 모델

`(BaseModel)` = 상속(자바 `extends`). 상속하면 **JSON↔객체 변환·검증 능력이 공짜.**

```java
// 자바
public record ProblemSetInfo(int problemSetId, String title, String description) {}
```
```python
# 파이썬 — 필드 이름:타입만 적으면 끝 (getter/setter/생성자 자동)
class ProblemSetInfo(BaseModel):
    problem_set_id: int
    title: str
    description: str
```

`record` + Bean Validation(`@NotNull`/`@Valid`)을 합친 게 Pydantic. 그래서 "schema(검증 포함 DTO)"라 부른다.

## ② 필드 = `이름: 타입` (타입이 곧 검증 규칙)

| 파이썬 | 자바 |
|--------|------|
| `int` | `int`/`Integer` |
| `str` | `String` |
| `float` | `double` |
| `bool` | `boolean` |

`problem_set_id: int` 인데 JSON에 `"abc"`(문자)가 오면 → Pydantic이 **자동 422**. 이게 3강의 "자동 검증".

## ③ `Optional[...] = None` — 선택 필드 (핵심 패턴)

```python
answer: Optional[str] = None
```

- `Optional[str]` = "문자열이거나 **없을(None) 수 있다**". `None` = 자바 `null`.
- `= None` = 기본값 (안 보내면 None).

**필수 vs 선택 구분이 중요:**

```python
user_message: str                              # ← Optional 없음 = 필수 (안 오면 검증 실패)
problem_set: Optional[ProblemSetInfo] = None   # ← 선택 (없어도 됨)
```

이 "있냐 없냐"가 6강에서 **모드 분기**(problem_set 있으면 문제풀이, 없으면 자유질문)로 쓰인다.

## ④ `list[...]` & ⑤ 중첩 모델

```python
problems: Optional[list[ProblemInfo]] = None   # ProblemInfo들의 리스트 (자바 List<ProblemInfo>)
problem_set: Optional[ProblemSetInfo] = None   # 모델 안에 모델 (중첩)
```

그래서 JSON도 중첩 구조로 오고, Pydantic이 객체 트리로 변환 → `request.problem_set.title` 로 접근.

---

## ★ 두 서버가 공유하는 JSON 계약 (중요)

이 `ChatRequest`가 받는 JSON은 **Spring 백엔드가 보낸다.**
백엔드 `chatbot/infrastructure/client/FastApiChatRequest.java`:

```java
@Getter @Builder
@JsonInclude(JsonInclude.Include.NON_NULL)   // null 필드는 JSON에서 제외
public class FastApiChatRequest {
    @JsonProperty("user_message")            // ← snake_case 로 직렬화
    private String userMessage;
    @JsonProperty("problem_set")
    private ProblemSetDto problemSet;
    @JsonProperty("conversation_history")
    private List<MessageDto> conversationHistory;
    ...
}
```

| Spring (`FastApiChatRequest`) | 우리 (`ChatRequest`) |
|-------------------------------|----------------------|
| `@JsonProperty("user_message")` | `user_message: str` |
| `@JsonProperty("problem_set")` | `problem_set: Optional[ProblemSetInfo]` |
| `@JsonInclude(NON_NULL)` (null 제외) | `Optional[...] = None` (없으면 None) |

> **이게 경계 계약이다.** 백엔드가 자바 camelCase(`userMessage`)를 `@JsonProperty`로 snake_case(`user_message`)
> JSON으로 바꿔 보내고, 우리가 그 이름 그대로 받는다. 한쪽이 필드명을 바꾸면 연동이 깨지니 **양쪽을 같이 본다.**
> (→ [../fastapi/04_domain_separation_and_coupling.md](../fastapi/04_domain_separation_and_coupling.md))

---

## 정리

1. `class X(BaseModel)` = Pydantic DTO (JSON↔객체 변환·검증 자동)
2. `이름: 타입` = 필드 + 검증 규칙
3. `Optional[T] = None` = 선택 필드 / 없으면 필수. `None` = 자바 `null`

→ 다음: [05_config.md](05_config.md) (설정은 어디서 오나)
