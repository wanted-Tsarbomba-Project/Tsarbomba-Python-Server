# 02. 프로젝트 구조 & 의존성

## 폴더 = 패키지, 파일 = 모듈

자바와 가장 먼저 부딪히는 차이다.

| 자바 | 파이썬 |
|------|--------|
| `package com.wanted...;` 선언 | **폴더 자체가 패키지** (선언 없음) |
| 파일 1개 = 클래스 1개 (보통) | **파일 1개 = 모듈** (함수·클래스 여러 개 OK) |
| `import com.wanted.app.Chat;` | `from app.chatbot.schema.chat import ChatRequest` |

파이썬은 **폴더 경로가 곧 import 경로**다:

```python
from app.chatbot.service.sse import token_frame
#    └─폴더─┘└─폴더─┘└─폴더─┘└파일┘   └함수┘
```

### `__init__.py`는 뭐냐

폴더마다 들어있는 (대개 빈) 파일. **"이 폴더는 패키지다"라고 파이썬에게 알리는 표식.**
이게 있어야 `from app.chatbot...` import가 동작한다. 자바엔 없는 개념이고, 보통 빈 파일이다.

### import 두 형태 (둘 다 우리 코드에 있음)

```python
from fastapi import FastAPI        # FastAPI만 콕 집어 가져옴 → FastAPI() 로 사용
from app.chatbot.service import sse  # sse 모듈 통째로 → sse.token_frame() 로 사용
```

후자처럼 모듈째 가져오면 `sse.token_frame()` 으로 **출처가 코드에 드러나** 읽기 좋다.

> **import 한 줄 = 의존성 한 개.** 파일 맨 위 import 목록이 곧 "이 파일이 뭘 의존하는지" 명세서다.
> 이 관점이 결합도 이야기로 이어진다 → [04_domain_separation_and_coupling.md](04_domain_separation_and_coupling.md)

---

## 의존성 관리: 외부 라이브러리는 어떻게 들어오나

`pydantic` 같은 외부 라이브러리는 **3단계**로 존재한다 (자바와 1:1):

```
requirements.txt   →   pip install   →   venv/.../pydantic/   →   import pydantic
  "필요하다" 선언        다운로드          실제 코드 저장             코드에서 사용
  (build.gradle)       (gradle build)    (gradle 캐시)            (import)
```

1. **`requirements.txt`** = 의존성 선언서 (= `build.gradle`)
   ```
   fastapi
   uvicorn[standard]
   pydantic
   ...
   ```
2. **`pip install`** = 다운로드 → `venv/` 안에 설치
3. **`import`** = 사용

### venv (가상환경) — 자바엔 없는 개념

`venv` = **이 프로젝트 전용 라이브러리 격리 공간**.
파이썬은 기본적으로 라이브러리가 전역 설치돼 프로젝트끼리 버전이 충돌한다.
그걸 막으려고 프로젝트마다 `venv/` 폴더에만 라이브러리를 깔아 격리한다.

```
이 프로젝트 venv/  →  pydantic 2.x (여기만)
다른 프로젝트 venv/ →  pydantic 1.x (충돌 안 남)
```

> 그래서 명령도 `venv/bin/python`, `venv/bin/pip` 처럼 venv 것을 쓴다.
> ⚠️ 현재 venv는 **Python 3.9** 기준이다. `str | None`(3.10+) 같은 신문법은 못 쓰고
> `Optional[str]`(3.9 호환)을 쓴다. (`app/chatbot/service/sse.py` 가 그 예)

---

## 우리 서버의 도메인 구조 (현재)

```
app/
├── main.py                      # 앱 진입점 (라우터 합치기, CORS)
├── core/                        # 공통 (도메인 중립)
│   └── config.py                #   설정 (.env)
├── chatbot/                     # 도메인 1: 챗봇
│   ├── api/chat_router.py       #   엔드포인트  (= presentation)
│   ├── service/                 #   비즈니스 로직
│   │   ├── prompt_builder.py
│   │   ├── gemini_client.py
│   │   └── sse.py
│   └── schema/chat.py           #   DTO
└── monitoring/                  # 도메인 2: 모니터링 (스켈레톤)
    ├── api/monitoring_router.py
    ├── service/
    └── schema/
templates/                       # Jinja2 프롬프트 (.j2) — app 밖
tests/                           # 테스트 — app 밖
```

**도메인(chatbot/monitoring)을 최상위에 두는 방식**이다. `app/` 만 열어도 "어떤 도메인이 있나"가 바로 보인다.

---

## 우리 구조 vs 백엔드 DDD 구조 (중요한 대비)

너희 **Spring 백엔드는 도메인마다 풀세트 DDD** 를 쓴다. 예) `chatbot` 모듈:

```
com/wanted/codebombalms/chatbot/
├── presentation/      # 컨트롤러, 요청/응답 DTO
│   └── api/{request,response}
├── application/       # 유스케이스, 포트(interface)
│   ├── usecase/
│   ├── port/          #   AiChatClient (interface)
│   └── model/
├── domain/            # 엔티티, 도메인 예외
│   └── exception/     #   ChatErrorCode
└── infrastructure/    # 외부 연동 구현
    └── client/        #   FastApiChatClient, WebClientConfig, MockAiChatClient
```

우리 FastAPI 서버는 **이걸 그대로 따라가지 않고** 가벼운 계층(`api/service/schema`)만 쓴다.
**왜 그런지 — 즉 "파이썬에서 DDD 풀세트를 안 쓰는 이유" 는** 다음 문서에서 결정 기록과 함께 설명한다:
→ [04_domain_separation_and_coupling.md](04_domain_separation_and_coupling.md)
