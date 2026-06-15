# 6강. prompt_builder.py — 모드 분기 + 템플릿

역할: **ChatRequest를 받아 Gemini에 줄 시스템 프롬프트(지시문)를 조립한다.**
`app/chatbot/service/prompt_builder.py`:

```python
import json
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

from app.chatbot.schema.chat import ChatRequest

# templates/ 디렉토리 기준으로 Jinja2 환경 설정 (app/chatbot/service → 프로젝트 루트)
_TEMPLATES_DIR = Path(__file__).parent.parent.parent.parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    trim_blocks=True,
    lstrip_blocks=True,
)


def build_system_prompt(request: ChatRequest, max_length: int) -> str:
    if request.problem_set is not None:
        return _build_problem_prompt(request, max_length)
    return _build_free_prompt(max_length)
```

## 왜 필요한가

Gemini에 사용자 질문만 던지면 평범한 챗봇이다. **"너는 데이터 분석 튜터다, 정답은 직접 알려주지 마"**
같은 시스템 프롬프트를 같이 줘야 우리 서비스가 된다. 그 지시문을 **상황에 맞게** 만드는 게 이 파일.

## ① Jinja2 — 템플릿 엔진 (≈ Thymeleaf)

```python
from jinja2 import Environment, FileSystemLoader
```

Jinja2 = "틀(템플릿)에 값을 끼워 최종 문자열을 만드는" 도구. **Thymeleaf와 같은 역할**, HTML 대신 프롬프트 텍스트를 만든다.
프롬프트를 코드에 박지 않고 `templates/*.j2` 파일로 빼서 따로 수정 가능 (결합도↓).

## ② 템플릿 경로 계산

```python
_TEMPLATES_DIR = Path(__file__).parent.parent.parent.parent / "templates"
```

- `__file__` = 이 파일(`app/chatbot/service/prompt_builder.py`) 경로
- `.parent` 한 번 = 한 칸 위로. 네 번 올라가면 프로젝트 루트 → 거기 `templates/`

```
app/chatbot/service/prompt_builder.py
   .parent           = app/chatbot/service
   .parent.parent    = app/chatbot
   .parent×3         = app
   .parent×4         = 프로젝트 루트  → / "templates"
```

> ⚠️ 도메인 분리로 파일이 `app/chatbot/service/`로 깊어지면서 `.parent`가 하나 늘었다 (원래 3개 → 4개).

`_env` = templates 폴더를 아는 Jinja2 엔진. (`trim_blocks`/`lstrip_blocks` = 출력 공백 정리)
> `_` 접두사 = "모듈 내부 전용"(관습적 private). 파이썬엔 진짜 private이 없어 약속으로 표시.

## ③ `build_system_prompt` — 모드 분기 (심장)

```python
if request.problem_set is not None:
    return _build_problem_prompt(request, max_length)   # 문제풀이 모드
return _build_free_prompt(max_length)                   # 자유질문 모드
```

4강의 `Optional`이 빛나는 곳:
- `problem_set is not None` (문제 정보 있음) → 문제풀이 프롬프트
- 없으면(None) → 자유질문 프롬프트

> `is not None` = 자바 `!= null`. 파이썬은 None 비교에 `==` 대신 `is`를 쓰는 게 관용.

## ④ `_build_free_prompt` — 쉬운 쪽

```python
def _build_free_prompt(max_length: int) -> str:
    template = _env.get_template("system_free.j2")   # 틀 로드
    return template.render(max_length=max_length)    # 값 끼워 문자열 완성
```

`render` = Thymeleaf의 "모델에 값 담아 렌더링". 템플릿 안 `{{ max_length }}` 자리에 실제 값이 박힌다.

## ⑤ `_build_problem_prompt` — 복잡한 쪽 (볼 만한 두 군데)

**(a) 기본값 패턴**
```python
current_problem_number = 1
if request.session_progress:
    current_problem_number = request.session_progress.current_problem_number
```
"일단 1, session_progress 있으면 그 값으로 덮어쓰기." (`if x:` = None이면 자동 거짓)

**(b) JSON 문자열 파싱 + 예외 처리**
```python
dataset_columns: list[str] = []
if request.dataset:
    try:
        dataset_columns = json.loads(request.dataset.meta_data)  # JSON 문자열 → 리스트
    except (json.JSONDecodeError, TypeError):
        dataset_columns = []                                     # 깨진 JSON이면 빈 리스트
```
- `json.loads` = JSON 문자열 → 파이썬 객체 (반대 `json.dumps`)
- `try/except` = 자바 `try/catch`. `except (A, B)` = "A 또는 B 잡기"

## ⑥ Jinja2 템플릿 문법 (`templates/`)

```jinja
{{ problem_set.title }}       값 끼워넣기 (render로 넘긴 값)
{% for p in problems %}       반복 (Thymeleaf th:each)
{% if loop.index == ... %}    조건 (th:if)
{% include 'system_base.j2' %}  공통 템플릿 포함
```

연결: 파이썬에서 `template.render(problem_set=request.problem_set, ...)` → 템플릿 `{{ problem_set.title }}`에 꽂힘.

```
build_system_prompt
├ problem_set 있음 → system_problem.j2 (문제·정답·피드백 가이드)
└ problem_set 없음 → system_free.j2    (자유 대화)
        둘 다 system_base.j2(공통 규칙) include
```

> 설계 포인트: `system_problem.j2`는 정답(`answer`)을 프롬프트에 넣되 "직접 노출 말고 유도하라"고 지시한다.
> 정답 노출 실패가 7강의 에러코드 `CHT-003` 맥락. 프롬프트 컨벤션 자세히 → [../prompt_engineering_convention.md](../prompt_engineering_convention.md)

---

## 정리

Jinja2(≈Thymeleaf), `Path(__file__).parent...`(경로 계산), `_`(내부 전용), `is not None`/`if x:`(Optional 검사),
`json.loads`(JSON 파싱), `try/except`(예외), `.render(키=값)`(템플릿 주입).

→ 다음: [07_gemini_client_and_sse.md](07_gemini_client_and_sse.md) (Gemini 스트리밍 — 클라이맥스)
