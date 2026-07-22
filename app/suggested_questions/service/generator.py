"""
빈도 상위 클러스터를 Gemini 에 넘겨:
  1) 정답구걸/노이즈 클러스터는 걸러내고 (게이트)
  2) 정당한 유형은 한국어 대표 질문 한 문장으로 만든다 (라벨링).
출력은 structured JSON 으로 강제한다(프리텍스트 파싱 불안정 방지).
"""
import json
import logging
from functools import lru_cache

from google import genai
from google.genai import types

from app.core.config import get_settings
from app.suggested_questions.service.clustering import QuestionCluster
from app.suggested_questions.service.prompt import build_label_prompt

logger = logging.getLogger(__name__)

CANDIDATE_MULTIPLIER = 2   # 빈도 상위 (2 x top_n) 클러스터를 후보로 LLM 에 투입
SAMPLE_PER_CLUSTER = 5     # 클러스터당 LLM 에 보여줄 샘플 질문 수

# Gemini structured output 스키마: {"questions": ["...", ...]}
_RESPONSE_SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "questions": types.Schema(
            type=types.Type.ARRAY,
            items=types.Schema(type=types.Type.STRING),
        ),
    },
    required=["questions"],
)


@lru_cache()
def _get_client() -> genai.Client:
    return genai.Client(api_key=get_settings().gemini_api_key)


def label_clusters(clusters: list[QuestionCluster], top_n: int) -> list[str]:
    """빈도 상위 클러스터 → 정제된 대표 질문 최대 top_n개.

    LLM 호출/파싱 실패 시 빈 목록(부분 성공 정책 — 그 문제만 DEFAULT 폴백으로 이어짐).
    """
    if not clusters:
        return []

    candidates = clusters[: top_n * CANDIDATE_MULTIPLIER]
    prompt = build_label_prompt(candidates, top_n, SAMPLE_PER_CLUSTER)

    try:
        client = _get_client()
        response = client.models.generate_content(
            model=get_settings().gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=_RESPONSE_SCHEMA,
            ),
        )
        data = json.loads(response.text)
        questions = data.get("questions", [])
    except Exception:
        logger.exception("event=suggested_questions_label_failed")
        return []

    cleaned = [str(question).strip() for question in questions if str(question).strip()]
    return cleaned[:top_n]
