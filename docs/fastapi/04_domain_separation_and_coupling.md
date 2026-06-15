# 04. 도메인 분리 & 결합도 (+ 분리 결정 기록)

## 결합도란 — import 한 줄 = 의존 한 개

파일 맨 위 import 목록이 곧 "이 파일이 뭘 의존하는지" 명세서다.
**의존이 적을수록 결합도가 낮고, 테스트·교체·재사용이 쉬워진다.**

우리 코드의 모범 사례 — `app/chatbot/service/sse.py`:

```python
import json
from typing import Optional
# 끝. app/* 의존이 하나도 없다.
```

SSE 프레임 만드는 순수 함수만 모아, Gemini·FastAPI·네트워크에서 **떼어냈다(decoupling)**.
덕분에 `tests/test_sse.py` 가 외부 API 없이 단독으로 돈다.

반대로 `gemini_client.py`는 import가 많다 = 의존이 많다 (어쩔 수 없이 Gemini·설정에 묶임).
→ 의존 방향이 `gemini_client → sse` **한 방향**이고, sse는 gemini를 전혀 모른다. 이게 좋은 단방향 의존.

---

## ADR: 왜 chatbot / monitoring 으로 도메인을 나눴나

### 배경
원래 이 서버는 챗봇 하나만 위한 구조(`app/{api,service,schema}`)였다.
모니터링 도메인을 다른 팀원이 추가하게 되면서, **서로 코드를 안 건드리고 작업**할 수 있게
경계를 그어야 했다.

### 결정
**도메인을 최상위 패키지로 분리** (`app/chatbot/`, `app/monitoring/`),
공통 설정만 `app/core/` 에 둔다. 각 도메인 내부는 가벼운 계층(`api/service/schema`)을 유지한다.

```
app/
├── core/        # 공통 (config)
├── chatbot/     # 도메인 1  (api/service/schema)
└── monitoring/  # 도메인 2  (api/service/schema)  ← 팀원이 채움
```

### 근거
- 목표는 "도메인 분리(결합도↓)"지 "DDD 전술 패턴 풀세트"가 아니다. 팀원이 monitoring을
  chatbot 안 건드리고 붙이는 건 **패키지 경계**만으로 달성된다.
- 도메인이 형제로 나란히 있으면 "서로 import하면 안 된다"는 경계가 명확해진다.
- `app/` 한 겹만 열면 도메인이 다 보인다(스크리밍 아키텍처). `domain/` 한 겹 더 묶는 건 도메인이 많아질 때나 의미.

### monitoring 도메인 추가 절차 (팀원용)
1. `app/monitoring/service`, `app/monitoring/schema` 에 로직·DTO 작성
2. `app/monitoring/api/monitoring_router.py` 에 `@router.get(...)` 엔드포인트 추가
3. `app/main.py` 에 `app.include_router(monitoring_router)` 한 줄로 연결

> 현재 `monitoring_router.py` 는 `router = APIRouter()` 만 있는 빈 라우터이고, main.py에 **아직 연결 안 됨**.
> 엔드포인트를 만든 뒤 직접 연결하면 된다. (죽은 빈 연결을 미리 만들지 않는다)

---

## 왜 파이썬은 백엔드처럼 DDD 풀세트를 안 쓰나

너희 Spring 백엔드 `chatbot` 모듈은 **풀세트 DDD**(`presentation / application / domain / infrastructure`,
port + adapter)를 쓴다. 우리 FastAPI 서버는 일부러 그걸 따라가지 않는다. 이유:

| | 스프링(자바) | FastAPI(파이썬) |
|--|------------|----------------|
| 문화 | 구조·계층·패턴 중시 | **실용·간결 중시 (YAGNI)** |
| 타입 | 정적 → 계층 많아도 컴파일러가 잡아줌 | 동적 → 계층 늘리면 사람이 관리 |
| 빈약한 모델 문제 | entity 분리 압박 큼 | Pydantic에 메서드 붙이면 됨, 압박 적음 |

- 파이썬 커뮤니티(및 FastAPI 공식 권장 구조)는 도메인별 `router/service/schema(/model)` 정도로 나눈다.
  `entity/value-object/repository/application` 풀세트는 **드물게, 큰 데서**만 쓴다.
- 이 서버는 본질이 **외부 AI(Gemini) 호출**이라, 풍부한 도메인 모델로 키울 게 거의 없다.
  풀세트를 깔면 **빈 껍데기 계층**(엔티티 없는 domain/, 구현 하나뿐인 repository)만 늘어난다.
- 진짜 비즈니스 규칙이 복잡해질 때(정답 판정, 재시도, 점수 산정이 도메인 객체로 자랄 때) 도입하는 게 정석.

> 요약: 백엔드의 풀세트 DDD가 틀린 게 아니다 — 거긴 규칙이 복잡하니 맞다.
> 단지 **파이썬/이 서버 규모에선 기본값이 아니다.**

---

## DI / 포트-어댑터 — 백엔드는 쓰고, 우리는 안 쓴다

결합도를 더 낮추는 고급 기법이 **의존성 주입(DI) + 포트-어댑터**다.
백엔드는 이걸 제대로 쓴다. 우리는 (지금은) 안 쓴다. 실제 코드로 비교해보자.

### 백엔드 — 포트(interface) + 어댑터(구현) + DI

`chatbot/application/port/AiChatClient.java` (포트 = 추상):

```java
public interface AiChatClient {
    AiChatClientResponse call(ChatContext context);
}
```

`chatbot/infrastructure/client/FastApiChatClient.java` (어댑터 = 실제 구현):

```java
@Component
@RequiredArgsConstructor
@Profile("!mock")                         // mock 아닐 때만 활성
public class FastApiChatClient implements AiChatClient {
    private final WebClient webClient;    // ← 주입됨
    @Override public AiChatClientResponse call(ChatContext context) {
        ... webClient.post().uri("/chat") ...   // 우리 서버 호출
    }
}
```

그리고 `MockAiChatClient`(`@Profile("mock")`)가 또 다른 어댑터.
→ **프로파일만 바꾸면 진짜 호출 ↔ mock 을 갈아끼운다.** 호출하는 쪽(UseCase)은 `AiChatClient`
인터페이스만 알고 구현체는 모른다. 이게 결합도를 극단적으로 낮춘 형태(헥사고날).

### 우리 — DI 안 쓰고 직접 호출

`app/chatbot/api/chat_router.py`, `gemini_client.py`:

```python
settings = get_settings()   # 주입(inject)이 아니라 직접 호출(pull)
```

Spring처럼 `@Autowired`로 받는 게 아니라, 필요할 때 `get_settings()`를 직접 부른다.
(`@lru_cache`로 싱글톤화는 해둠 → [../chatbot/05_config.md](../chatbot/05_config.md))

> FastAPI도 DI 기능(`Depends`)이 있지만 이 서버는 안 쓴다. 규모상 포트-어댑터의 실익(구현 교체)이
> 적기 때문. Gemini를 다른 LLM으로 갈아끼울 일이 잦아지면 그때 도입하면 된다.

---

## 두 서버가 공유하는 것 (경계 계약)

도메인은 분리됐지만, 두 서버는 **경계에서 약속을 공유**한다:

1. **JSON 필드 계약 (snake_case)** — 백엔드 `FastApiChatRequest`(`@JsonProperty("user_message")`)가
   보내는 JSON을 우리 `ChatRequest`(`user_message`)가 받는다.
   → [../chatbot/04_schema_dto.md](../chatbot/04_schema_dto.md)
2. **에러코드** — 백엔드 `ChatErrorCode.AI_RESPONSE_FAILED = "CHT-003"` ↔ 우리
   `gemini_client.AI_RESPONSE_FAILED = "CHT-003"`(sse error 프레임).
   → [../chatbot/07_gemini_client_and_sse.md](../chatbot/07_gemini_client_and_sse.md)

이 "공유 계약"이 깨지면 (한쪽이 필드명/코드를 바꾸면) 연동이 깨진다. 변경 시 양쪽을 같이 본다.
