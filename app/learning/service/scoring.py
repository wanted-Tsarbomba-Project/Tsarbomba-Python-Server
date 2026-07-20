import math

from app.learning.schema.learning_recommendation import Difficulty, ReasonCode


SEMANTIC_WEIGHT_WITH_MAIN = 0.60
DIFFICULTY_WEIGHT_WITH_MAIN = 0.40
REVIEW_EXPLANATION_RATE_THRESHOLD = 30.0
LOW_PROFICIENCY_THRESHOLD = 50.0
HARD_PROFICIENCY_THRESHOLD = 80.0

ATTEMPT_SCORE_THRESHOLDS = (
    (1.5, 100.0),
    (2.5, 70.0),
    (3.5, 40.0),
)

DIFFICULTY_ORDER = {
    Difficulty.EASY: 0,
    Difficulty.MEDIUM: 1,
    Difficulty.HARD: 2,
}


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        raise ValueError("vectors must not be empty")
    if len(left) != len(right):
        raise ValueError("vectors must have the same length")

    dot_product = math.fsum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(math.fsum(value * value for value in left))
    right_norm = math.sqrt(math.fsum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0

    similarity = dot_product / (left_norm * right_norm)
    return max(0.0, min(1.0, similarity))


def calculate_attempt_score(average_attempt_count: float) -> float:
    for upper_bound, score in ATTEMPT_SCORE_THRESHOLDS:
        if average_attempt_count <= upper_bound:
            return score
    return 10.0


def calculate_proficiency_score(
    direct_solve_rate: float,
    average_test_pass_rate: float,
    explanation_view_rate: float,
    average_attempt_count: float,
) -> float:
    attempt_score = calculate_attempt_score(average_attempt_count)
    return (
        direct_solve_rate * 0.50
        + average_test_pass_rate * 0.25
        + (100.0 - explanation_view_rate) * 0.15
        + attempt_score * 0.10
    )


def determine_target_difficulty(proficiency_score: float) -> Difficulty:
    if proficiency_score < LOW_PROFICIENCY_THRESHOLD:
        return Difficulty.EASY
    if proficiency_score < HARD_PROFICIENCY_THRESHOLD:
        return Difficulty.MEDIUM
    return Difficulty.HARD


def calculate_difficulty_fit(
    target_difficulty: Difficulty,
    candidate_difficulty: Difficulty,
) -> float:
    difference = abs(
        DIFFICULTY_ORDER[target_difficulty] - DIFFICULTY_ORDER[candidate_difficulty]
    )
    return {0: 1.0, 1: 0.6, 2: 0.2}[difference]


def calculate_final_score(
    semantic_similarity: float,
    difficulty_fit: float,
    has_main_problems: bool,
) -> float:
    if not has_main_problems:
        return semantic_similarity
    return (
        semantic_similarity * SEMANTIC_WEIGHT_WITH_MAIN
        + difficulty_fit * DIFFICULTY_WEIGHT_WITH_MAIN
    )


def determine_reason_code(
    has_main_problems: bool,
    explanation_view_rate: float,
    proficiency_score: float | None,
    target_difficulty: Difficulty | None,
    candidate_difficulty: Difficulty,
) -> ReasonCode:
    if not has_main_problems:
        return ReasonCode.COURSE_RELATED
    if proficiency_score is None or target_difficulty is None:
        raise ValueError("proficiency and target difficulty are required with MAIN problems")

    is_target_difficulty = candidate_difficulty == target_difficulty
    needs_review = (
        explanation_view_rate >= REVIEW_EXPLANATION_RATE_THRESHOLD
        or proficiency_score < LOW_PROFICIENCY_THRESHOLD
    )
    if needs_review and is_target_difficulty:
        return ReasonCode.REVIEW_WEAK_AREA

    if DIFFICULTY_ORDER[candidate_difficulty] == DIFFICULTY_ORDER[target_difficulty] + 1:
        return ReasonCode.NEXT_DIFFICULTY
    if is_target_difficulty:
        return ReasonCode.LEVEL_MATCHED
    return ReasonCode.COURSE_RELATED
