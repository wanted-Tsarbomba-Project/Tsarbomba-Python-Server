from dataclasses import dataclass

from app.core.config import get_settings
from app.learning.repository.vector_store import (
    SimilarProblemSet,
    VectorStoreEmptyError,
    learning_problem_set_vector_store,
)
from app.learning.schema.learning_recommendation import (
    Difficulty,
    LearningContext,
    LearningProfile,
    LearningRecommendationRequest,
    LearningRecommendationResponse,
    ProblemSetRecommendation,
    ReasonCode,
)
from app.learning.service.gemini_embedding import embed_texts
from app.learning.service.gemini_reason_generator import (
    GeminiReasonGenerationError,
    ReasonGenerationInput,
    ReviewEvidence,
    generate_recommendation_reasons,
)
from app.learning.service.scoring import (
    calculate_difficulty_fit,
    calculate_final_score,
    calculate_proficiency_score,
    determine_reason_code,
    determine_target_difficulty,
)


ALGORITHM_NAME = "GEMINI_EMBEDDING_PERSONALIZED"
MAX_EMBEDDING_TEXT_LENGTH = 1_500


@dataclass(frozen=True)
class _RankedCandidate:
    candidate: SimilarProblemSet
    raw_score: float
    reason_code: ReasonCode


def build_learning_context_text(context: LearningContext) -> str:
    parts = [f"강좌 제목: {context.course_title}"]
    if context.course_description:
        parts.append(f"강좌 설명: {context.course_description}")
    for lecture in context.lectures:
        parts.append(f"강의 제목: {lecture.title}")
        if lecture.description:
            parts.append(f"강의 설명: {lecture.description}")
    return "\n".join(parts)[:MAX_EMBEDDING_TEXT_LENGTH]


def build_recommendation_reason(
    reason_code: ReasonCode,
    course_title: str,
    candidate: SimilarProblemSet,
    profile: LearningProfile,
    proficiency_score: float | None,
    target_difficulty: Difficulty | None,
) -> str:
    problem_set_name = f"'{candidate.title}'"
    if reason_code == ReasonCode.COURSE_RELATED:
        return (
            f"'{course_title}' 강좌에서 학습한 내용과 연관성이 높은 "
            f"{problem_set_name} 문제 세트예요."
        )
    if reason_code == ReasonCode.REVIEW_WEAK_AREA:
        if profile.explanation_view_rate >= 30:
            return (
                "MAIN 문제에서 해설을 자주 확인했기 때문에, "
                f"{candidate.difficulty.value} 난이도의 {problem_set_name} 문제 세트를 "
                "직접 풀이를 보강하는 복습용으로 추천해요."
            )
        if proficiency_score is not None and proficiency_score < 50:
            return (
                "현재 학습 결과를 바탕으로 기초 보강이 필요해, "
                f"{candidate.difficulty.value} 난이도의 {problem_set_name} 문제 세트를 "
                "추천해요."
            )
    if reason_code == ReasonCode.LEVEL_MATCHED and target_difficulty is not None:
        return (
            f"현재 학습 수준에 적합한 {target_difficulty.value} 난이도의 "
            f"{problem_set_name} 문제 세트예요."
        )
    if reason_code == ReasonCode.NEXT_DIFFICULTY and target_difficulty is not None:
        return (
            f"현재 목표 난이도 {target_difficulty.value}보다 한 단계 높은 "
            f"{candidate.difficulty.value} 난이도의 {problem_set_name} 문제 세트에 "
            "다음 단계로 도전해요."
        )
    return (
        f"'{course_title}' 강좌에서 학습한 내용과 연관성이 높은 "
        f"{problem_set_name} 문제 세트예요."
    )


def determine_review_evidence(
    reason_code: ReasonCode,
    profile: LearningProfile,
    proficiency_score: float | None,
) -> ReviewEvidence:
    if reason_code != ReasonCode.REVIEW_WEAK_AREA:
        return ReviewEvidence.NONE
    if profile.explanation_view_rate >= 30:
        return ReviewEvidence.EXPLANATION_DEPENDENCY
    if proficiency_score is not None and proficiency_score < 50:
        return ReviewEvidence.LOW_PROFICIENCY
    return ReviewEvidence.NONE


def recommend_learning_problem_sets(
    request: LearningRecommendationRequest,
) -> LearningRecommendationResponse:
    settings = get_settings()
    if learning_problem_set_vector_store.count() == 0:
        raise VectorStoreEmptyError("learning problem-set ingestion is required")

    learning_text = build_learning_context_text(request.learning_context)
    learning_vector = embed_texts([learning_text])[0]

    excluded_ids = set(request.excluded_problem_set_ids)
    search_count = settings.learning_vector_candidate_count + len(excluded_ids)
    searched_candidates = learning_problem_set_vector_store.search_similar(
        query_embedding=learning_vector,
        problem_category_id=request.problem_category_id,
        result_count=search_count,
    )
    candidates = [
        candidate
        for candidate in searched_candidates
        if candidate.problem_set_id not in excluded_ids
    ][: settings.learning_vector_candidate_count]

    profile = request.learning_profile
    has_main_problems = profile.total_main_problem_count > 0
    proficiency_score = None
    target_difficulty = None
    if has_main_problems:
        proficiency_score = calculate_proficiency_score(
            direct_solve_rate=profile.direct_solve_rate,
            average_test_pass_rate=profile.average_test_pass_rate,
            explanation_view_rate=profile.explanation_view_rate,
            average_attempt_count=profile.average_attempt_count,
        )
        target_difficulty = determine_target_difficulty(proficiency_score)

    ranked: list[_RankedCandidate] = []
    for candidate in candidates:
        difficulty_fit = (
            calculate_difficulty_fit(target_difficulty, candidate.difficulty)
            if target_difficulty is not None
            else 0.0
        )
        raw_score = calculate_final_score(
            candidate.semantic_similarity,
            difficulty_fit,
            has_main_problems,
        )
        reason_code = determine_reason_code(
            has_main_problems=has_main_problems,
            explanation_view_rate=profile.explanation_view_rate,
            proficiency_score=proficiency_score,
            target_difficulty=target_difficulty,
            candidate_difficulty=candidate.difficulty,
        )
        ranked.append(
            _RankedCandidate(
                candidate=candidate,
                raw_score=raw_score,
                reason_code=reason_code,
            )
        )

    ranked.sort(
        key=lambda item: (
            -item.raw_score,
            -item.candidate.semantic_similarity,
            item.candidate.problem_set_id,
        )
    )

    selected = ranked[: request.recommendation_count]
    fallback_reasons = {
        item.candidate.problem_set_id: build_recommendation_reason(
            reason_code=item.reason_code,
            course_title=request.learning_context.course_title,
            candidate=item.candidate,
            profile=profile,
            proficiency_score=proficiency_score,
            target_difficulty=target_difficulty,
        )
        for item in selected
    }
    reason_inputs = [
        ReasonGenerationInput(
            problem_set_id=item.candidate.problem_set_id,
            problem_set_title=item.candidate.title,
            reason_code=item.reason_code,
            course_title=request.learning_context.course_title,
            target_difficulty=target_difficulty,
            candidate_difficulty=item.candidate.difficulty,
            review_evidence=determine_review_evidence(
                item.reason_code,
                profile,
                proficiency_score,
            ),
        )
        for item in selected
    ]
    generated_reasons: dict[int, str] = {}
    if reason_inputs:
        try:
            generated_reasons = generate_recommendation_reasons(reason_inputs)
        except GeminiReasonGenerationError:
            generated_reasons = {}

    recommendations = [
        ProblemSetRecommendation(
            problem_set_id=item.candidate.problem_set_id,
            score=round(item.raw_score, 4),
            reason_code=item.reason_code,
            recommendation_reason=generated_reasons.get(
                item.candidate.problem_set_id,
                fallback_reasons[item.candidate.problem_set_id],
            ),
        )
        for item in selected
    ]
    return LearningRecommendationResponse(
        algorithm=ALGORITHM_NAME,
        recommendations=recommendations,
    )
