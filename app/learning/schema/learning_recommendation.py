from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator


NonEmptyTitle = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
]
OptionalDescription = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=2_000),
] | None
Percentage = Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)]
NonNegativeFloat = Annotated[float, Field(ge=0, allow_inf_nan=False)]


class AliasedModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class Difficulty(str, Enum):
    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"


class ReasonCode(str, Enum):
    COURSE_RELATED = "COURSE_RELATED"
    REVIEW_WEAK_AREA = "REVIEW_WEAK_AREA"
    LEVEL_MATCHED = "LEVEL_MATCHED"
    NEXT_DIFFICULTY = "NEXT_DIFFICULTY"


class LearningProfile(AliasedModel):
    total_main_problem_count: int = Field(ge=0, alias="totalMainProblemCount")
    correct_problem_count: int = Field(ge=0, alias="correctProblemCount")
    direct_solve_rate: Percentage = Field(alias="directSolveRate")
    explanation_view_count: int = Field(ge=0, alias="explanationViewCount")
    explanation_view_rate: Percentage = Field(alias="explanationViewRate")
    average_attempt_count: NonNegativeFloat = Field(alias="averageAttemptCount")
    average_test_pass_rate: Percentage = Field(alias="averageTestPassRate")

    @model_validator(mode="after")
    def validate_problem_counts(self) -> "LearningProfile":
        if self.correct_problem_count > self.total_main_problem_count:
            raise ValueError("correctProblemCount cannot exceed totalMainProblemCount")
        if self.explanation_view_count > self.total_main_problem_count:
            raise ValueError("explanationViewCount cannot exceed totalMainProblemCount")

        if self.total_main_problem_count == 0:
            remaining_metrics = (
                self.correct_problem_count,
                self.direct_solve_rate,
                self.explanation_view_count,
                self.explanation_view_rate,
                self.average_attempt_count,
                self.average_test_pass_rate,
            )
            if any(value != 0 for value in remaining_metrics):
                raise ValueError(
                    "all learning metrics must be zero when totalMainProblemCount is zero"
                )
        return self


class LectureContext(AliasedModel):
    title: NonEmptyTitle
    description: OptionalDescription = None


class LearningContext(AliasedModel):
    course_title: NonEmptyTitle = Field(alias="courseTitle")
    course_description: OptionalDescription = Field(default=None, alias="courseDescription")
    lectures: list[LectureContext] = Field(default_factory=list, max_length=100)


REQUEST_EXAMPLE = {
    "courseId": 20,
    "lectureId": 30,
    "problemCategoryId": 10,
    "excludedProblemSetIds": [1001],
    "recommendationCount": 2,
    "learningProfile": {
        "totalMainProblemCount": 10,
        "correctProblemCount": 6,
        "directSolveRate": 60.0,
        "explanationViewCount": 3,
        "explanationViewRate": 30.0,
        "averageAttemptCount": 2.4,
        "averageTestPassRate": 72.5,
    },
    "learningContext": {
        "courseTitle": "파이썬 기초",
        "courseDescription": "파이썬의 기본 문법을 학습합니다.",
        "lectures": [
            {
                "title": "반복문",
                "description": "for문과 while문의 사용법을 학습합니다.",
            },
            {
                "title": "리스트와 딕셔너리",
                "description": "리스트와 딕셔너리로 데이터를 처리합니다.",
            },
        ],
    },
}


class LearningRecommendationRequest(AliasedModel):
    course_id: int = Field(gt=0, alias="courseId")
    lecture_id: int = Field(gt=0, alias="lectureId")
    problem_category_id: int = Field(gt=0, alias="problemCategoryId")
    excluded_problem_set_ids: list[Annotated[int, Field(gt=0)]] = Field(
        default_factory=list,
        alias="excludedProblemSetIds",
        max_length=100,
    )
    recommendation_count: int = Field(default=2, ge=1, le=2, alias="recommendationCount")
    learning_profile: LearningProfile = Field(alias="learningProfile")
    learning_context: LearningContext = Field(alias="learningContext")

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={"example": REQUEST_EXAMPLE},
    )

    @model_validator(mode="after")
    def validate_unique_excluded_ids(self) -> "LearningRecommendationRequest":
        if len(self.excluded_problem_set_ids) != len(
            set(self.excluded_problem_set_ids)
        ):
            raise ValueError("excludedProblemSetIds values must be unique")
        return self


class ProblemSetRecommendation(AliasedModel):
    problem_set_id: int = Field(gt=0, alias="problemSetId")
    score: float = Field(ge=0, le=1, allow_inf_nan=False)
    reason_code: ReasonCode = Field(alias="reasonCode")
    recommendation_reason: str = Field(
        min_length=1,
        max_length=300,
        alias="recommendationReason",
    )


class LearningRecommendationResponse(AliasedModel):
    algorithm: str
    recommendations: list[ProblemSetRecommendation] = Field(max_length=2)
