"""
문제별 '추천 질문 생성' API 의 요청/응답 DTO.
recommendation 스키마처럼 camelCase alias(내부 배치 계약).
Spring 이 문제별 원시 질문을 모아 보내면(Option A), 정제된 대표 질문을 돌려준다.
"""
from pydantic import BaseModel, ConfigDict, Field


class ProblemQuestions(BaseModel):
    problem_set_id: int = Field(alias="problemSetId")
    problem_id: int = Field(alias="problemId")
    questions: list[str]  # 원시 USER 질문(노이즈 포함)

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class SuggestedQuestionsGenerateRequest(BaseModel):
    problems: list[ProblemQuestions]
    top_n: int = Field(default=5, ge=1, le=5, alias="topN")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class ProblemSuggestedQuestions(BaseModel):
    problem_set_id: int = Field(alias="problemSetId")
    problem_id: int = Field(alias="problemId")
    questions: list[str]  # 정제된 대표 질문(최대 top_n, 없으면 빈 목록)

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class SuggestedQuestionsGenerateResponse(BaseModel):
    problems: list[ProblemSuggestedQuestions]
