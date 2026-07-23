# ADR-0004 — 시스템 프롬프트는 Jinja2 템플릿 파일, 영어 실사용 + `ko/` 참조본

> 상태: **accepted**
> 관련: [ADR-0005](0005-prompt-context-caching-split.md), [prompt-engineering.md](../prompt-engineering.md)

## 맥락

시스템 프롬프트는 이 서버 품질의 핵심(정답 노출 금지·튜터링·환각 방지)이고, 자주 다듬어진다. 프롬프트 텍스트를 어디에 두고 어떻게 조립할지, 언어를 무엇으로 할지 정해야 했다.

## 결정

1. **모든 프롬프트 텍스트는 `templates/*.j2`(Jinja2)에만 둔다.** Python 코드에 프롬프트 문자열을 하드코딩하지 않는다.
2. 템플릿 구성:
   - `system_base.j2` — 모든 모드 공통(역할·절대금지·응답포맷).
   - `system_problem.j2` — 문제풀이 모드. `{% include 'system_base.j2' %}` + 문제/정답/데이터셋/CODE·TEXT 피드백 가이드.
   - `system_free.j2` — 자유질문 모드. base include + 일반 어시스턴트 역할.
3. **모드 분기**: `prompt_builder.build_system_prompt()`가 `request.problem_set is not None` → `system_problem.j2`, 아니면 `system_free.j2`.
4. **실사용 템플릿은 영어**로 쓴다. `templates/ko/`에 동일 구조의 한국어 참조본을 둔다 — **Gemini 호출엔 쓰지 않고** 팀원이 의도를 이해하는 용도. 영어본 수정 시 `ko/`도 동기화.
5. 동적 데이터는 Jinja2 변수로 주입(`{{ problem_set.title }}`, `{{ max_length }}` 등). `trim_blocks=True, lstrip_blocks=True`.

## 근거

- 프롬프트를 코드에서 분리하면 다듬기·리뷰·diff가 쉽고, 프롬프트 구조가 매 요청 동일하게 고정된다(포맷 붕괴 방어).
- **영어 실사용 이유**: 한국어는 같은 의미에 영어 대비 2배+ 토큰을 쓴다. 시스템 프롬프트의 규칙/구조는 매 요청 반복되는 **고정 비용**이라 영어가 토큰을 아끼고 implicit caching 히트율을 높인다. DB에서 온 데이터(문제·정답)는 한국어 원문 유지, AI 응답은 프롬프트 지시로 한국어.
- `include`로 공통(base)을 한 곳에 두면 모드별 중복이 없다.

## 비고

- 섹션 배치(primacy/recency), 언어 정책, 튜터링 규칙, CODE/TEXT 피드백 상세는 [prompt-engineering.md](../prompt-engineering.md).
- 새 변수 추가 절차: ① `prompt_builder`의 `render(...)`에 변수 추가 → ② `.j2`에서 `{{ 변수 }}` 사용 → ③ `ko/` 참조본 반영.
- ⚠️ `ko/` 동기화는 사람이 지켜야 하는 규율(자동 검증 없음). PR 리뷰에서 영어/한국어 불일치를 확인.
