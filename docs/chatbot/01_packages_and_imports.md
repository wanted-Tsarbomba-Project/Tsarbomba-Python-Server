# 1강. 폴더·파일 = 패키지·모듈

> 이 강은 [../fastapi/02_project_structure.md](../fastapi/02_project_structure.md)와 내용이 겹친다.
> 거긴 일반 개념, 여긴 이 프로젝트 코드 기준으로 읽는다.

## 자바 vs 파이썬

| 자바 | 파이썬 |
|------|--------|
| `package ...;` 선언 | **폴더 자체가 패키지** (선언 없음) |
| 파일 1개 = 클래스 1개 | **파일 1개 = 모듈** (함수·클래스 여러 개 OK) |
| `import com.wanted.app.Chat;` | `from app.chatbot.schema.chat import ChatRequest` |

파이썬은 **폴더 경로가 곧 import 경로**다.

## 우리 프로젝트 트리

```
app/
├── __init__.py
├── main.py
├── core/
│   ├── __init__.py
│   └── config.py
├── chatbot/
│   ├── __init__.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── chat_router.py
│   ├── service/
│   │   ├── __init__.py
│   │   ├── prompt_builder.py
│   │   ├── gemini_client.py
│   │   └── sse.py
│   └── schema/
│       ├── __init__.py
│       └── chat.py
└── monitoring/         # 다른 팀원 도메인 (스켈레톤)
    ├── __init__.py
    ├── api/monitoring_router.py
    ├── service/__init__.py
    └── schema/__init__.py
```

import할 때 이 경로가 그대로 쓰인다:

```python
from app.chatbot.service.sse import token_frame
#    └─폴더─┘└─폴더─┘└─폴더─┘└파일┘   └함수┘
```

## `__init__.py`는 뭐냐

폴더마다 있는 (대개 빈) 파일. **"이 폴더는 패키지다"라는 표식.**
이게 있어야 `from app.chatbot...` import가 동작한다. 보통 빈 파일이다 (우리 것도 다 빔).

## import 두 형태 (둘 다 우리 코드에 있음)

```python
from fastapi import FastAPI            # FastAPI만 콕 집어 가져옴
from app.chatbot.service import sse    # sse 모듈 통째로 → sse.token_frame() 으로 사용
```

`app/chatbot/service/gemini_client.py` 에서 `from app.chatbot.service import sse` 한 뒤
`sse.token_frame(...)` 으로 쓰는 게 후자 방식. 이렇게 하면 "이건 sse 모듈 함수"가 코드에 드러난다.

> **import 한 줄 = 의존성 한 개.** 파일 맨 위 import 목록 = "이 파일이 뭘 의존하는지" 명세서.

---

## 정리

- 폴더 = 패키지, 파일 = 모듈 (파일 안에 함수·클래스 여러 개 가능)
- import 경로 = 실제 폴더 경로
- `__init__.py` = "여긴 패키지" 표식 (보통 빈 파일)

→ 다음: [02_main_entrypoint.md](02_main_entrypoint.md) (앱이 어떻게 시작되나)
