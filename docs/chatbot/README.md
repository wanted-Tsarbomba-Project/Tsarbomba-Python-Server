# 챗봇 코드 강의 (한 파일씩 읽기)

> 이 서버의 **실제 챗봇 코드를 한 파일씩 읽으며** 이해하는 강의입니다.
> FastAPI 일반 개념이 처음이면 먼저 [../fastapi/README.md](../fastapi/README.md)를 보고 오세요.
> (이 강의는 그 개념을 이 프로젝트 코드에 적용해 읽습니다.)

---

## 한 요청의 일생 (전체 흐름)

```
Spring 백엔드 ── POST /chat (JSON) ──▶ FastAPI
   │
   ├ ChatRequest 로 자동 변환·검증            (4강 schema)
   ├ problem_set 유무로 모드 분기 + 프롬프트 조립 (6강 prompt_builder)
   ├ Gemini 스트리밍 호출                      (7강 gemini_client)
   └ 토큰을 SSE 프레임으로 실시간 흘림          (7강 sse)
        │
        ▼
   Spring 이 받아 사용자에게 전달
```

각 단계가 어느 파일인지 한 강씩 따라가며 읽는다.

---

## 강의 목차 (순서대로)

| 강 | 문서 | 다루는 파일 |
|----|------|------------|
| 1 | [01_packages_and_imports.md](01_packages_and_imports.md) | 폴더·모듈·import·`__init__.py` |
| 2 | [02_main_entrypoint.md](02_main_entrypoint.md) | `app/main.py` |
| 3 | [03_chat_router.md](03_chat_router.md) | `app/chatbot/api/chat_router.py` |
| 4 | [04_schema_dto.md](04_schema_dto.md) | `app/chatbot/schema/chat.py` |
| 5 | [05_config.md](05_config.md) | `app/core/config.py` |
| 6 | [06_prompt_builder.md](06_prompt_builder.md) | `app/chatbot/service/prompt_builder.py` + `templates/` |
| 7 | [07_gemini_client_and_sse.md](07_gemini_client_and_sse.md) | `app/chatbot/service/{gemini_client,sse}.py` |

---

## 학습 팁

- **순서대로 읽기**: 입구(router) → 데이터(schema) → 설정(config) → 로직(service) 순으로 쌓인다.
- **실제 파일을 옆에 띄워놓고** 강의와 대조하며 읽으면 가장 빠르다.
- 자바/Spring 대응이 필요하면 [../fastapi/01_fastapi_vs_spring.md](../fastapi/01_fastapi_vs_spring.md) 참고.
- 다 읽으면 직접 띄워보기: `uvicorn app.main:app --reload --port 8000` (→ [../fastapi/03_app_lifecycle.md](../fastapi/03_app_lifecycle.md))
