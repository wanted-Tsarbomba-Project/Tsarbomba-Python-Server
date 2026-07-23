# ADR-0002 — 설정은 pydantic-settings + `@lru_cache` pull, DI/포트-어댑터 미채택

> 상태: **accepted**
> 관련: [ADR-0001](0001-domain-package-lightweight-layering.md), [CONVENTION §8 설정](../CONVENTION.md)

## 맥락

- 설정값(Gemini 키·모델·DB 접속정보·응답 길이)을 어디서 어떻게 읽을지 정해야 한다.
- Spring 백엔드는 결합도를 낮추려 **DI + 포트/어댑터**(`AiChatClient` 인터페이스 ↔ `FastApiChatClient`/`MockAiChatClient`, `@Profile`로 교체)를 쓴다. FastAPI도 `Depends`로 같은 걸 할 수 있다. 따라할지 결정해야 했다.

## 결정

1. 설정은 `pydantic_settings.BaseSettings`(`Settings`)로 `.env`에서 읽는다. `SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")`.
2. `get_settings()`를 **`@lru_cache`** 로 감싸 프로세스당 1회만 로드(싱글톤화).
3. 필요할 때 `get_settings()`를 **직접 호출(pull)** 한다. FastAPI `Depends` 주입을 쓰지 않는다.
4. Gemini 클라이언트도 같은 패턴: `_get_client()` + `@lru_cache`(`gemini_client.py`).
5. **포트/어댑터·인터페이스 추상화를 두지 않는다.** Gemini를 직접 부른다.

## 근거

- 이 서버 규모에서 포트-어댑터의 실익(구현 교체)이 적다. Gemini를 다른 LLM으로 자주 갈아끼울 일이 없고, 테스트는 `monkeypatch`로 `_get_client`를 대체하면 충분하다(실제로 `test_stream_gemini.py`가 그렇게 함).
- `@lru_cache`가 싱글톤·지연초기화를 공짜로 준다. `Depends` 배선의 보일러플레이트가 없다.
- pull 방식은 읽기 쉽다: "필요한 곳에서 `get_settings()`" — import 목록만 봐도 의존이 드러난다.

## 비고

- 트레이드오프: `@lru_cache` 때문에 테스트에서 설정을 바꾸려면 `get_settings.cache_clear()` 또는 monkeypatch가 필요하다.
- Gemini↔다른 LLM 교체가 잦아지거나 mock 프로파일 분리가 필요해지면 그때 포트-어댑터를 도입한다(YAGNI까지 미룸).
- 민감정보는 `.env`(gitignore)에만, 공용엔 `.env.example` 자리표시자만 → [ADR-0009](0009-deployment-topology.md)(운영은 Secrets→환경변수 주입).
