from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    question: str
    operator_id: int = Field(
        default=1,
        validation_alias=AliasChoices("operator_id", "operatorId"),
    )
    dataset_url: str = Field(
        validation_alias=AliasChoices("dataset_url", "datasetUrl"),
    )
    data_file_name: str | None = Field(
        default=None,
        validation_alias=AliasChoices("data_file_name", "dataFileName"),
    )
    topic: str
    category_name: str = Field(
        validation_alias=AliasChoices("category_name", "categoryName"),
    )
    difficulty: Literal["EASY", "MEDIUM", "HARD"] = "EASY"
    problem_count: int = Field(
        default=1,
        ge=1,
        le=3,
        validation_alias=AliasChoices("problem_count", "problemCount"),
    )
    sub_problem_count: int = Field(
        default=3,
        ge=1,
        le=10,
        validation_alias=AliasChoices("sub_problem_count", "subProblemCount"),
    )
    history: list[ChatMessage] = Field(default_factory=list)


class TestCaseDraft(BaseModel):
    testCode: str
    isHidden: bool = False
    timeoutMs: int = 3000


class ProblemDraft(BaseModel):
    title: str
    point: int
    content: str
    startCode: str | None = None
    hint: str
    explanation: str
    testCases: list[TestCaseDraft]


class ProblemSetDraft(BaseModel):
    title: str
    categoryName: str
    difficulty: Literal["EASY", "MEDIUM", "HARD"]
    description: str
    dataFileName: str
    problems: list[ProblemDraft]


class ProblemSetDraftEnvelope(BaseModel):
    answer: str
    draft: ProblemSetDraft


class ChatResponse(BaseModel):
    answer: str
    draft: dict[str, Any] | None = None
    used_tools: list[str]
