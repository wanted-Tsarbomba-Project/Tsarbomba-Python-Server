from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core.config import Settings
from app.learning.api import learning_router
from app.learning.repository.vector_store import VectorStoreEmptyError
from app.learning.schema.learning_recommendation import Difficulty, ReasonCode
from app.learning.service import gemini_embedding
from app.learning.service.gemini_reason_generator import (
    ReasonGenerationInput,
    ReviewEvidence,
    _validate_individual_reasons,
)
from app.learning.service.problem_set_content import (
    MAX_EMBEDDING_TEXT_LENGTH,
    build_problem_set_embedding_text,
)


def test_reason_timeout_can_be_configured_below_default():
    settings = Settings(
        gemini_api_key="test-key",
        learning_reason_timeout_ms=5_000,
    )

    assert settings.learning_reason_timeout_ms == 5_000


def test_embedding_client_uses_configured_timeout(monkeypatch):
    monkeypatch.setattr(
        gemini_embedding,
        "get_settings",
        lambda: SimpleNamespace(
            gemini_api_key="test-key",
            learning_embedding_timeout_ms=5_000,
        ),
    )
    gemini_embedding._get_client.cache_clear()

    try:
        client = gemini_embedding._get_client()
        assert client._api_client._http_options.timeout == 5_000
    finally:
        gemini_embedding._get_client.cache_clear()


def test_empty_vector_store_is_already_mapped_to_503(monkeypatch):
    def raise_empty_error(_request):
        raise VectorStoreEmptyError("ingestion required")

    monkeypatch.setattr(
        learning_router,
        "recommend_learning_problem_sets",
        raise_empty_error,
    )

    with pytest.raises(HTTPException) as exc_info:
        learning_router.rank_final_problem_sets(object())

    assert exc_info.value.status_code == 503


def test_overlong_generated_reason_is_discarded_for_fallback():
    expected = ReasonGenerationInput(
        problem_set_id=1,
        problem_set_title="문제 세트",
        reason_code=ReasonCode.COURSE_RELATED,
        course_title="강좌",
        target_difficulty=None,
        candidate_difficulty=Difficulty.EASY,
        review_evidence=ReviewEvidence.NONE,
    )
    raw_reasons = [
        {
            "problemSetId": 1,
            "reasonCode": "COURSE_RELATED",
            "recommendationReason": "가" * 301,
        }
    ]

    assert _validate_individual_reasons(raw_reasons, [expected]) == {}


def test_difficulty_is_preserved_when_description_is_truncated():
    text = build_problem_set_embedding_text(
        title="긴 문제 세트",
        description="설명" * MAX_EMBEDDING_TEXT_LENGTH,
        difficulty="HARD",
    )

    assert len(text) == MAX_EMBEDDING_TEXT_LENGTH
    assert text.startswith("문제세트 제목: 긴 문제 세트\n난이도: HARD\n")
