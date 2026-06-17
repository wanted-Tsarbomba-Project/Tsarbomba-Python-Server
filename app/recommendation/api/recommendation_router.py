from fastapi import APIRouter, HTTPException, status

from app.recommendation.schema.recommendation import (
    RecommendationGenerateRequest,
    RecommendationGenerateResponse,
)
from app.recommendation.service.recommendation_service import (
    generate_problem_set_recommendations,
)
from app.recommendation.service.repository import RecommendationRepositoryError

router = APIRouter(
    prefix="/internal/recommendations",
    tags=["recommendations"],
)


@router.post(
    "/problem-sets/generate",
    response_model=RecommendationGenerateResponse,
    response_model_by_alias=True,
)
def generate_recommendations(
    request: RecommendationGenerateRequest,
) -> RecommendationGenerateResponse:
    try:
        return generate_problem_set_recommendations(request.recommendation_count)
    except RecommendationRepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
