from fastapi import APIRouter, HTTPException, status

from app.learning.schema.learning_recommendation import (
    LearningRecommendationRequest,
    LearningRecommendationResponse,
)
from app.learning.service.gemini_embedding import GeminiEmbeddingError
from app.learning.repository.vector_store import VectorStoreUnavailableError
from app.learning.service.learning_recommendation_service import (
    recommend_learning_problem_sets,
)


router = APIRouter(
    prefix="/internal/learning",
    tags=["learning"],
)


@router.post(
    "/final-problem-sets/rank",
    response_model=LearningRecommendationResponse,
    response_model_by_alias=True,
)
def rank_final_problem_sets(
    request: LearningRecommendationRequest,
) -> LearningRecommendationResponse:
    try:
        return recommend_learning_problem_sets(request)
    except GeminiEmbeddingError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Gemini embedding service is unavailable",
        ) from exc
    except VectorStoreUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Learning problem-set index is unavailable; run ingestion first",
        ) from exc
