# 03. 앱 생명주기 — 서버가 어떻게 뜨나

## main.py: 앱은 "객체"다

Spring과 가장 큰 사고방식 차이. Spring은 `@SpringBootApplication`이 마법처럼 앱을 구성하지만,
**FastAPI는 앱 객체를 내 손으로 만들고, 설정을 하나씩 붙인다.**

`app/main.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.chatbot.api.chat_router import router

app = FastAPI(title="tsarbomba ChatBot API", ...)   # ① 앱 객체 생성

app.add_middleware(                                  # ② 공통 관문 (= Filter/Interceptor)
    CORSMiddleware,
    allow_origins=["http://localhost:8080"],         #    Spring 백엔드만 허용
    allow_methods=["*"], allow_headers=["*"],
)

app.include_router(router)                            # ③ 엔드포인트 묶음 꽂기

@app.get("/health")                                  # ④ 헬스체크 등록
def health_check():
    return {"status": "ok"}
```

- **① `app = FastAPI(...)`** = 그냥 객체 생성 (`new FastAPI()`). 앞으로 모든 설정을 이 `app`에 붙인다.
- **② `add_middleware`** = 모든 요청이 거쳐가는 공통 관문. CORS가 `localhost:8080`(Spring) 한 곳만 허용 → 이 서버가 Spring 전용인 근거.
- **③ `include_router`** = 기능별로 나눈 라우터(`chat_router`)를 앱에 합침.
- **④ `@app.get(...)`** = `{"status":"ok"}`(dict)를 return하면 FastAPI가 **자동 JSON 변환**. Spring `actuator/health`와 같은 목적.

> main.py엔 자바의 `main()` 같은 "실행" 코드가 없다. **`app` 객체를 만들어 두기만** 한다.
> 실행은 밖에서 uvicorn이 한다 ↓

---

## `uvicorn app.main:app --reload --port 8000` 실행 시 무슨 일이 벌어지나

### 0. 명령어 해석

```
uvicorn  app.main:app   --reload   --port 8000
         └파일┘ └변수┘    파일바뀌면    8000포트로
                         자동재시작     서버 열기
```

`app.main:app` = "`app/main.py`를 열어 그 안의 `app` 변수를 가져와라" (콜론 앞=파일, 뒤=변수).

### 1. import 연쇄 (★ 자바와 결정적 차이)

uvicorn이 main.py를 **import**하는 순간, **파이썬은 그 파일을 위에서 아래로 한 줄씩 실행한다.**

> ⚠️ 자바는 클래스 안 코드가 호출돼야 실행되지만,
> **파이썬은 파일을 import 하면 함수 바깥 코드가 즉시 전부 실행된다.**

```
uvicorn
 └ main.py 실행 시작
    ├ import chat_router       ← 여기서 옆길로
    │   ├ import gemini_client (실행됨)
    │   ├ import prompt_builder(실행됨)
    │   └ @router.post("/chat") 데코레이터 실행 → "/chat은 chat함수" 등록
    └ chat_router 끝 → main.py 계속 ↓
```

import가 import를 부르는 도미노가 일어난다.

### 2. main.py 나머지 실행 (조립 단계)

`app = FastAPI()` → `add_middleware` → `include_router` → `@app.get` 까지 실행.
**여기까지가 "조립".** 함수 *안*(`def chat`, `def health_check`)의 내용은 **아직 실행 안 됨.**
"이런 URL이 이 함수에 연결됐다"고 **등록만** 된 상태.

> 비유: 식당을 *여는* 중. 메뉴판(라우터) 걸고, 문(CORS) 열었다. 근데 **요리(`def chat` 내용)는 주문 와야 만든다.**

### 3~4. uvicorn이 완성된 `app`을 받아 8000 포트에서 대기

```
INFO: Uvicorn running on http://127.0.0.1:8000
INFO: Application startup complete.
```

여기서 "위→아래 실행"은 **끝**. 서버는 무한 대기.

### 5. 요청이 오면 — 비로소 함수 안이 실행됨

`POST /chat` 도착 → 등록표 보고 `chat()` **함수 내용이 그제서야 실행** → 응답 → 다시 대기.

---

## 핵심 정리: 두 시점

| 시점 | 무슨 코드가 도나 |
|------|-----------------|
| **서버 시작 (위→아래 1회)** | import 연쇄 + 함수 **바깥** 코드 (app 생성, 라우터 등록) |
| **요청 올 때마다** | 해당 엔드포인트 **함수 안** 코드 (`def chat` 내용) |

`--reload` = 파일이 바뀌면 1~4단계를 자동 재실행 (개발용, 운영에선 끔).

이 **"import 하면 즉시 실행 / 함수 안은 호출돼야 실행"** 구분이 파이썬 읽기의 핵심 감각이다.

---

## 누가 이 서버를 부르나 (경계)

이 서버를 띄워두면, **Spring 백엔드**가 호출한다.
`chatbot/infrastructure/client/WebClientConfig.java`:

```java
@Configuration
public class WebClientConfig {
    @Bean
    public WebClient webClient() {
        return WebClient.builder()
                .baseUrl(fastApiProperties.getUrl())   // ← 이 서버 주소
                .build();
    }
}
```

그리고 `FastApiChatClient` 가 `webClient.post().uri("/chat")` 로 호출한다.
즉 백엔드의 `baseUrl`이 이 서버(uvicorn이 연 host:port)를 가리켜야 연결된다.
(연결 토글·프로파일은 [`../handoff_fastapi_connect.md`](../handoff_fastapi_connect.md))
