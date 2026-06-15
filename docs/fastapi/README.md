# FastAPI 아키텍처 가이드 (Spring 개발자용 온보딩)

> 이 문서 묶음은 **Spring/Java 경험은 있지만 FastAPI·파이썬이 처음**인 팀원이
> 이 서버를 혼자 파악하고 작업을 시작할 수 있게 만든 온보딩 레퍼런스입니다.

---

## 이 서버가 뭐냐 (한 줄)

**데이터 분석 학습용 AI 튜터 챗봇의 응답을 생성하는 FastAPI(파이썬) 서버.**
혼자 도는 게 아니라 **Spring 백엔드 전용 AI 마이크로서비스**다.

```
사용자 ──▶ Spring 백엔드(LMS) ──POST /chat──▶ 이 FastAPI 서버 ──▶ Gemini
                  (codebombalms)                 (tsarbomba ChatBot)
```

- 프론트가 직접 부르지 않는다. **Spring 백엔드만** 호출한다.
- 근거(코드로 증명됨):
  - `app/main.py` 의 CORS 가 `http://localhost:8080`(Spring) 한 곳만 허용
  - Spring 백엔드 `chatbot/infrastructure/client/FastApiChatClient.java` 가
    `webClient.post().uri("/chat")` 로 이 서버를 **서버-투-서버**로 호출
  - 두 서버가 에러코드(`CHT-003`)와 JSON 필드(snake_case)를 **공유**

> 연결 방법·활성화 토글은 [`../handoff_fastapi_connect.md`](../handoff_fastapi_connect.md) 참고.

---

## 읽는 순서

| # | 문서 | 내용 |
|---|------|------|
| 1 | [01_fastapi_vs_spring.md](01_fastapi_vs_spring.md) | FastAPI는 프레임워크(=Spring 자리), REST는 통신 스타일. 데코레이터 vs 어노테이션 |
| 2 | [02_project_structure.md](02_project_structure.md) | 폴더=패키지, import=의존, venv, 의존성 관리. 우리 도메인 구조 vs 백엔드 DDD 구조 |
| 3 | [03_app_lifecycle.md](03_app_lifecycle.md) | 앱이 어떻게 뜨나. `uvicorn`으로 올릴 때 코드가 도는 순서 |
| 4 | [04_domain_separation_and_coupling.md](04_domain_separation_and_coupling.md) | 결합도, 도메인 분리(chatbot/monitoring) 결정 기록, 왜 파이썬은 DDD 풀세트를 안 쓰나 |

개념을 잡았으면, **실제 챗봇 코드를 한 파일씩 읽는 강의**로:
→ [../chatbot/README.md](../chatbot/README.md)

---

## 한눈에 보는 Spring ↔ FastAPI

| Spring (Java) | FastAPI (Python) | 비고 |
|---------------|------------------|------|
| 프레임워크 Spring Boot | 프레임워크 FastAPI | 같은 범주 |
| 내장 Tomcat | uvicorn (ASGI 서버) | 앱과 서버가 분리됨 |
| `@RestController` | `APIRouter` | |
| `@PostMapping("/chat")` | `@router.post("/chat")` | 데코레이터 = 등록 |
| `@RequestBody DTO` + `@Valid` | `request: ChatRequest` (Pydantic) | 타입힌트로 파싱+검증 자동 |
| `record` / Lombok DTO | Pydantic `BaseModel` | |
| `application.yml` | `.env` + `pydantic-settings` | |
| `build.gradle` | `requirements.txt` | 의존성 선언 |
| Gradle 캐시 | `venv/` | 라이브러리 설치 위치 |

> 자세한 대응과 실제 백엔드 코드 인용은 [01_fastapi_vs_spring.md](01_fastapi_vs_spring.md).
