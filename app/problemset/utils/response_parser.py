import json
from typing import Any

from app.problemset.schemas.problem_set_draft_schema import ProblemSetDraftEnvelope


def parse_gemini_response(response: Any) -> tuple[str, dict[str, Any] | None]:
    parsed = getattr(response, "parsed", None)
    if isinstance(parsed, ProblemSetDraftEnvelope):
        return parsed.answer, parsed.draft.model_dump()
    if isinstance(parsed, dict):
        answer = str(parsed.get("answer") or "문제세트 초안이 생성되었습니다.")
        draft = parsed.get("draft")
        return answer, draft if isinstance(draft, dict) else None

    return parse_model_answer(getattr(response, "text", None) or "")


def parse_model_answer(text: str) -> tuple[str, dict[str, Any] | None]:
    if not text.strip():
        return "Gemini 응답이 비어 있습니다.", None

    cleaned = _strip_markdown_json_block(text)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return text, None

    if not isinstance(parsed, dict):
        return text, None

    answer = str(parsed.get("answer") or "문제세트 초안이 생성되었습니다.")
    draft = parsed.get("draft")
    return answer, draft if isinstance(draft, dict) else None


def _strip_markdown_json_block(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```json"):
        return stripped.removeprefix("```json").removesuffix("```").strip()
    if stripped.startswith("```"):
        return stripped.removeprefix("```").removesuffix("```").strip()
    return stripped
