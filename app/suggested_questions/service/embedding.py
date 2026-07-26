"""
Gemini 임베딩 API로 질문을 벡터로 바꾼다.
chatbot/gemini_client.py 와 같은 방식으로 client 를 만든다(도메인 간 import 금지라 복제).
"""
import logging
from functools import lru_cache

from google import genai

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Gemini 임베딩 모델. text-embedding-004는 현재 API 세대(v1beta)에서 제거됨 → gemini-embedding-001 사용.
EMBEDDING_MODEL = "gemini-embedding-001"


@lru_cache()
def _get_client() -> genai.Client:
    return genai.Client(api_key=get_settings().gemini_api_key)


def embed_questions(questions: list[str]) -> list[list[float]]:
    """질문 목록 → 임베딩 벡터 목록. 반환[i] 는 questions[i] 의 벡터."""
    if not questions:
        return []

    client = _get_client()
    response = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=questions,
    )
    logger.info("event=suggested_questions_embedded count=%d", len(questions))
    return [list(embedding.values) for embedding in response.embeddings]
