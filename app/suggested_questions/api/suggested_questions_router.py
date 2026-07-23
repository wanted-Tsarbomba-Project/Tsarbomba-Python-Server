"""
추천 질문 '생성' 엔드포인트 (배치 생성용, Spring 스케줄러가 호출).
라우터는 얇게: 문제별로 파이프라인(임베딩 → 군집 → 라벨)을 돌리고 모아 반환.
한 문제가 실패해도 다른 문제는 정상 반환(부분 성공).
"""
import logging

from fastapi import APIRouter

from app.suggested_questions.schema.suggested_questions import (
    ProblemSuggestedQuestions,
    SuggestedQuestionsGenerateRequest,
    SuggestedQuestionsGenerateResponse,
)
from app.suggested_questions.service.clustering import cluster_questions
from app.suggested_questions.service.embedding import embed_questions
from app.suggested_questions.service.generator import label_clusters

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/internal/suggested-questions",
    tags=["suggested-questions"],
)

# 문제당 원시 질문 상한(너무 많으면 임베딩 비용↑·군집 품질↓). Spring 도 수집 시 캡하지만 방어적으로 한 번 더.
MAX_QUESTIONS_PER_PROBLEM = 150
MIN_QUESTION_LENGTH = 2   # 'ㄱㄱ' 같은 껍데기 노이즈 제거


@router.post(
    "/generate",
    response_model=SuggestedQuestionsGenerateResponse,
    response_model_by_alias=True,
)
def generate_suggested_questions(
    request: SuggestedQuestionsGenerateRequest,
) -> SuggestedQuestionsGenerateResponse:
    problems = [
        ProblemSuggestedQuestions(
            problem_set_id=problem.problem_set_id,
            problem_id=problem.problem_id,
            questions=_generate_for_problem(problem.questions, request.top_n),
        )
        for problem in request.problems
    ]
    return SuggestedQuestionsGenerateResponse(problems=problems)


def _generate_for_problem(raw_questions: list[str], top_n: int) -> list[str]:
    """한 문제: 껍데기 노이즈 제거 → 임베딩 → 군집 → 라벨. 실패 시 빈 목록."""
    questions = [
        question.strip()
        for question in raw_questions
        if len(question.strip()) >= MIN_QUESTION_LENGTH
    ][:MAX_QUESTIONS_PER_PROBLEM]

    if not questions:
        return []

    try:
        embeddings = embed_questions(questions)
        clusters = cluster_questions(questions, embeddings)
        return label_clusters(clusters, top_n)
    except Exception:
        logger.exception("event=suggested_questions_generate_failed")
        return []
