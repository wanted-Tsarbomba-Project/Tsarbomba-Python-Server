# 5강. config.py — 설정 관리

4강 Pydantic의 사촌이 나온다. Spring `application.yml` + `@ConfigurationProperties` 에 해당.
`app/core/config.py`:

```python
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    gemini_api_key: str
    gemini_model: str = "gemini-2.5-flash-preview-05-20"
    default_max_length: int = 1000

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
```

> 이 파일은 `core/`(공통)에 있다. chatbot·monitoring 어느 도메인이든 같은 설정을 쓰기 때문.

## ① `class Settings(BaseSettings)` — 4강의 사촌

| | `BaseModel` (4강) | `BaseSettings` (5강) |
|--|------------------|----------------------|
| 값 출처 | **JSON 요청** | **환경변수 / `.env` 파일** |
| 용도 | API 데이터 | 앱 설정 |

선언 방식(`이름: 타입`)은 똑같고, 값을 어디서 채우냐만 다르다.

## ② 필드 = 설정 항목 (필수/선택 규칙은 4강과 동일)

```python
gemini_api_key: str                                    # 기본값 없음 = 필수 (.env에 없으면 시작 시 에러)
gemini_model: str = "gemini-2.5-flash-preview-05-20"   # 기본값 있음 = 선택
default_max_length: int = 1000                         # 응답 최대 길이 기본 1000
```

API 키는 코드에 박으면 안 되니 **필수로 두고 외부(.env)에서 주입**. Spring `@Value("${gemini.api-key}")` 격.

## ③ `class Config: env_file = ".env"` — .env에서 읽기

```python
class Config:                  # class 안의 class — Pydantic 관용구 (Settings 동작 설정 블록)
    env_file = ".env"          # .env 파일을 읽어 위 필드를 채워라
    env_file_encoding = "utf-8"
```

프로젝트 루트 `.env` 예:
```
GEMINI_API_KEY=AIzaSy...실제키
GEMINI_MODEL=gemini-2.5-flash-preview-05-20
```

- 매칭: 필드 `gemini_api_key` ↔ 환경변수 `GEMINI_API_KEY` (대소문자 무시 매칭)
- `.env`는 **민감정보(키)라 git에 올리면 안 됨** (`.gitignore`). 코드(config.py)는 공유, 키 값(.env)은 각자.

## ④ `@lru_cache()` — 설정 싱글톤화

```python
@lru_cache()
def get_settings() -> Settings:
    return Settings()          # .env 읽어 Settings 객체 생성
```

`@lru_cache` = **"함수 결과를 기억(캐시)했다가, 또 부르면 다시 계산 않고 그대로 반환".**

```python
get_settings()  # 1번째: .env 읽고 객체 생성 → 기억
get_settings()  # 2번째 이후: 기억해둔 같은 객체 반환 (.env 안 읽음)
```

결과적으로 앱 전체에서 Settings 객체가 **딱 하나** = **싱글톤**.
Spring은 `@Bean`이 기본 싱글톤이라 신경 안 썼지만, 파이썬은 이렇게 직접 만든다.
3강에서 `settings = get_settings()` 를 매 요청 불러도 부담 없던 이유 = 캐시된 같은 객체라서.

> 데코레이터 복습: `@app.get`=등록, `@lru_cache`=캐싱. 데코레이터마다 하는 일이 다르다.
> `lru_cache`는 `functools`(파이썬 **표준 라이브러리**, 설치 불필요)에서 온다.

## 어디서 쓰이나

```python
settings = get_settings()
settings.gemini_api_key        # API 키
settings.gemini_model          # 모델명
settings.default_max_length    # 응답 길이
```

---

## 정리

1. `BaseSettings` = `.env`/환경변수에서 값 채우는 Pydantic (BaseModel의 설정용 사촌)
2. `이름: 타입 = 기본값` = 필수/선택 + 기본값
3. `class Config: env_file` = `.env` 읽기. 민감정보라 git 제외
4. `@lru_cache` = Settings 싱글톤화

→ 다음: [06_prompt_builder.md](06_prompt_builder.md) (프롬프트 조립)
