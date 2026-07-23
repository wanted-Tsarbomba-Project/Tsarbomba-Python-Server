# 프롬프트 / 컨텍스트 엔지니어링 (how-to)

> 시스템 프롬프트의 **설계 원칙·튜터링 규칙·템플릿 구조** 상세. 결정 요지는 [ADR-0004](adr/0004-prompt-as-jinja-templates.md)(Jinja2 템플릿)·[ADR-0005](adr/0005-prompt-context-caching-split.md)(컨텍스트 분리).
> 이 문서는 `templates/*.j2` 실물과 `app/chatbot/service/{prompt_builder,gemini_client}.py`를 기준으로 한다.

---

## 1. 핵심 원칙

이 서버는 **데이터 분석 학습용 AI 튜터**다.

- **절대 정답을 직접 알려주지 않는다**(채점 문제의 answer를 그대로/유사하게 노출 금지).
- 유저의 사고 과정을 유도한다.
- 제공된 컨텍스트(문제·데이터셋·제출답)에 **근거해서만** 말한다.
- 모르면 모른다고 한다(환각 방지) — "정확하지 않을 수 있어요".

---

## 2. 템플릿 구조 (`templates/`)

```
templates/
├── system_base.j2      # 공통: 역할·절대금지·답변법·톤/포맷   (모든 모드가 include)
├── system_problem.j2   # 문제풀이 모드: base + 문제/정답/피드백가이드/데이터셋/그라운딩
├── system_free.j2      # 자유질문 모드: base + 일반 어시스턴트 역할
└── ko/                 # 한국어 참조본(실사용 X — 의도 이해용). 영어본 수정 시 동기화.
```

### 모드 분기 (`prompt_builder.build_system_prompt`)

```python
if request.problem_set is not None:   # 문제풀이
    return _build_problem_prompt(request, max_length)
return _build_free_prompt(max_length) # 자유질문
```

### `system_problem.j2` 렌더 결과의 실제 섹션 순서

1. **(base)** `[ROLE]` — 데이터 분석 튜터. 질문한 걸 답하되 채점 문제의 최종답은 주지 않는다.
2. **(base)** `[ABSOLUTE FORBIDDEN RULES]` — ← **primacy**(최상단, 후속 토큰이 강하게 참조).
   - 정답 직접/부분/유사 노출 금지 · 빈 칭찬 금지 · 없는 정보 날조 금지 · 이미 준 힌트 반복 금지 · 거절/역할 서두 금지.
3. **(base)** `[HOW TO ANSWER]` — 최신 메시지에만 답, 이미 준 피드백 재진술 금지, 고정 구조 강요 없음, 인사/오프토픽/온토픽 분류.
4. **(base)** `[TONE & FORMAT]` — 한국어 존댓말, 마크다운 강조 금지(plain text), `{{ max_length }}`자 이내.
5. `[PROBLEM SET]` — `title`, `description`.
6. `[ALL PROBLEMS]` — 문제별 `title/content/type`, `explanation`(내부참조용, 직접노출 금지), `answer`(없으면 "(No model answer provided)"), `(CURRENT)` 마커.
7. `[CURRENT PROBLEM FOCUS: #n]` — 현재 문제에 집중.
8. `[FEEDBACK GUIDE]` — 제출답 유무 × CODE/TEXT 분기(§4).
9. `[DATASET INFORMATION]` — `dataset_columns` 있을 때만. 컬럼명+예시값 목록.
10. `[GROUNDING RULES]` — ← **recency**(최하단). 목록에 있는 컬럼만 언급, 불확실하면 모른다고, 날조 금지.

> 배치 의도: 가장 중요한 **금지 규칙을 최상단(primacy)**, **그라운딩을 최하단(recency)** 에 둔다. 정답(answer)은 금지 규칙의 대상으로 문제 블록 안에 함께 제공된다.

---

## 3. 언어·캐싱 정책 → 상세 [ADR-0004](adr/0004-prompt-as-jinja-templates.md)·[ADR-0005](adr/0005-prompt-context-caching-split.md)

| 구분 | 언어 | 이유 |
|------|------|------|
| 시스템 프롬프트(규칙·구조) | **영어** | 토큰 절약 + implicit caching 히트율 |
| DB에서 온 데이터(문제·정답) | **한국어 원문** | 원본 유지 |
| AI 응답 | **한국어 존댓말** | 프롬프트가 "Respond in Korean" 지시 |

- **불변(system_instruction) vs 가변(contents)**: 방 안에서 안 변하는 규칙·문제·정답·데이터셋은 `system_instruction`, 변하는 대화이력·현재문제번호·제출답요약·user_message는 `contents`로 → 캐시 유지([ADR-0005](adr/0005-prompt-context-caching-split.md)).
- ⚠️ **고정 부분(영어 규칙 텍스트)을 함부로 바꾸지 말 것** — 텍스트가 바뀌면 캐시가 깨진다. 동적 데이터는 변수라 같은 값이면 캐시에 영향 없음.

---

## 4. 튜터링 규칙 (피드백 방식)

### 4.1 CODE 타입 — 의도 비교

AI는 코드를 실행할 수 없다. `submitted_answer`가 있으면 **의도 비교**로 피드백한다.

```
1. 정답 코드(answer)의 의도 파악      (예: df.shape = 행/열 개수)
2. 제출 코드(submitted_answer)의 의도  (예: df.head() = 미리보기)
3. 두 의도의 gap 식별
4. gap을 좁히는 방향으로 유도 (정답 코드 자체는 말하지 않음)
```

### 4.2 TEXT 타입 — 핵심 개념 기반

```
1. 정답(answer)의 핵심 개념/키워드 추출
2. 제출답이 어떤 개념을 포함/누락했는지 판별
3. 누락 개념 방향으로 유도 (질문은 선택)
4. 정답에 없는 개념은 도입하지 않음
```

### 4.3 제출답이 없을 때

- CODE: 어떤 종류의 함수/메서드를 찾아볼지 방향만.
- TEXT: 핵심 키워드·비교 관점으로 사고 시작점 제공.

### 4.4 데이터셋 활용 — grounding + 힌트 재료

- **Grounding**: 제공된 컬럼만 언급(없는 컬럼 날조 방지).
- **힌트 재료**: 예시값으로 데이터 타입/형식을 추론해 관련 컬럼으로 유도(dtype은 명시 안 하고 예시값으로만 전달).

---

## 5. `dataset.meta_data` 파싱 (`prompt_builder._build_problem_prompt`)

DB에서 **JSON 문자열**로 온다. 계약: `{"columns":[{"name": ..., "examples":[...]}]}` (BE `DatasetMetadataExtractor`가 업로드 시 CSV에서 추출).

```python
parsed = json.loads(request.dataset.meta_data)
columns = parsed.get("columns", []) if isinstance(parsed, dict) else []
dataset_columns = [
    {"name": c.get("name", ""), "examples": c.get("examples", [])}
    for c in columns if isinstance(c, dict) and c.get("name")
]
# 파싱 실패(JSONDecodeError/TypeError/AttributeError) → 조용히 [] 폴백 (방어코드 최소화)
```

템플릿 렌더:

```jinja2
{% for col in dataset_columns %}
- {{ col.name }}{{ " (e.g. " ~ (col.examples | join(", ")) ~ ")" if col.examples else "" }}
{% endfor %}
```

---

## 6. 응답 포맷

- 한국어 존댓말, **plain text**(마크다운 강조·백틱 금지 — `df.shape`처럼 그대로).
- 길이: `{{ max_length }}`자 이내. 값은 `settings.default_max_length`(= `.env`의 `DEFAULT_MAX_LENGTH`).
  - ⚠️ 코드 기본값 1000 vs 구문서/`.env.example` 200 불일치 → **`.env` 실제값이 진실** → [알려진 불일치](README.md).
- 빈 칭찬/추임새 금지. 힌트+유도만(단, 고정 "힌트+질문" 템플릿을 강요하진 않음).
- 이미 준 힌트 반복 금지 — 다른 각도로.

---

## 7. 자유질문 모드 (`system_free.j2`)

- base include + `[MODE: FREE QUESTION]` + `[BEHAVIOR]`.
- 일반 데이터 분석 어시스턴트. 개념은 더 자유롭게 설명하되 "이대로 해" 식 직답은 지양, 불확실하면 모른다고.
- 문제/정답/데이터셋이 없어 `system_instruction`이 단순하다.
- (향후) 자유질문 모드에 RAG를 붙여 자사 자료 기반 답변 예정 — 도입 시 `system_free.j2`에 검색결과 주입 블록 추가.

---

## 8. 프롬프트 수정 절차

1. 영어 템플릿 `templates/*.j2` 수정.
2. `templates/ko/*.j2` 참조본 동기화.
3. 로컬 테스트(동일 payload로 응답 품질 확인).
4. PR — 리뷰어가 영어/한국어 일치 확인.

새 변수 추가: ① `prompt_builder`의 `render(...)`에 변수 추가 → ② `.j2`에서 `{{ 변수 }}` → ③ `ko/` 반영.
**프롬프트 문자열을 Python에 하드코딩하지 않는다**(모든 텍스트는 `.j2`에만).
