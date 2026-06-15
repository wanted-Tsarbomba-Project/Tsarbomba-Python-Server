# 2강. main.py — 앱이 어떻게 시작되나

Spring의 `@SpringBootApplication` 메인 클래스에 해당. `app/main.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.chatbot.api.chat_router import router

app = FastAPI(
    title="tsarbomba ChatBot API",
    description="데이터 분석 튜터링 AI 챗봇 서버",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
```

## ① `app = FastAPI(...)` — 앱은 "객체"다

Spring은 어노테이션 하나로 마법처럼 앱이 구성되지만, **FastAPI는 앱 객체를 직접 만든다.**
`app`은 그냥 변수다. 앞으로 모든 설정을 이 `app`에 하나씩 붙여나간다.

## ② `add_middleware(CORSMiddleware, ...)` — 공통 관문

미들웨어 = 모든 요청이 거쳐가는 관문 (Spring `Filter`/`Interceptor`).
**CORS가 `localhost:8080`(Spring 백엔드)만 허용** → 이 서버가 Spring 전용인 근거.
`["*"]` 는 "전부"(모든 메서드/헤더 허용) 와일드카드.

## ③ `include_router(router)` — 라우터 연결

엔드포인트들을 `app/chatbot/api/chat_router.py` 에 모아놓고 여기서 앱에 **꽂는다**.
main.py가 비대해지지 않게 기능별로 라우터를 나눈 것. (Spring이 `@RestController`를 여러 개로 나누는 이유와 같음)

## ④ `@app.get("/health")` — 데코레이터로 엔드포인트 등록

```python
@app.get("/health")        # "GET /health 오면 아래 함수로 답해" 라고 등록
def health_check():
    return {"status": "ok"} # dict를 return → FastAPI가 자동 JSON 변환
```

- Spring `@GetMapping("/health")` 와 같은 역할.
- `/health` 는 **헬스체크** (서버 살아있나 확인용, Spring `actuator/health`와 같은 목적).
- ⚠️ 데코레이터(`@`)는 **함수를 실행하는 게 아니라 등록**한다.
  (자바 어노테이션=메모 / 파이썬 데코레이터=실제 실행되는 코드인데 그 내용이 "등록")
  → 자세히: [../fastapi/01_fastapi_vs_spring.md](../fastapi/01_fastapi_vs_spring.md)

## 짚을 점: main.py엔 실행 코드가 없다

이 파일은 `app` 객체를 **만들어 두기만** 한다. 실행은 밖에서 uvicorn이 한다:

```
uvicorn app.main:app --reload --port 8000
        └파일┘ └이 변수┘
```

Spring Boot가 Tomcat을 자동으로 띄우는 것과 달리, 파이썬은 서버(uvicorn)와 앱(FastAPI)이
분리돼 있어 실행 명령을 직접 준다.
→ 실행 시 코드가 도는 순서: [../fastapi/03_app_lifecycle.md](../fastapi/03_app_lifecycle.md)

---

→ 다음: [03_chat_router.md](03_chat_router.md) (실제 /chat 엔드포인트)
