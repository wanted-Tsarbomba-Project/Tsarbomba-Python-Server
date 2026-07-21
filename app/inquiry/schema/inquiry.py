from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class InquirySeverity(str, Enum):
    """Java InquirySeverity와 값을 동일하게 유지한다."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class InquiryDomain(str, Enum):
    """Java InquiryDomain과 값을 동일하게 유지한다."""

    ADMIN = "ADMIN"
    AUTH = "AUTH"
    BADGE = "BADGE"
    CHATBOT = "CHATBOT"
    COURSE = "COURSE"
    ENROLLMENT = "ENROLLMENT"
    PROBLEMS = "PROBLEMS"
    RANKING = "RANKING"
    RECOMMENDATION = "RECOMMENDATION"
    USER = "USER"
    LECTURE = "LECTURE"
    LEARNING = "LEARNING"
    ETC = "ETC"


class CorrectionExample(BaseModel):
    """Spring이 보내는 관리자 보정 사례 한 건. chatbot과 동일하게 snake_case 계약을 쓴다 (별도 alias 불필요)."""

    field_name: str
    ai_value: Optional[str] = None
    corrected_value: str
    reason: Optional[str] = None


class InquiryAnalyzeRequest(BaseModel):
    """POST /internal/inquiries/analyze 요청 바디."""

    inquiry_id: int
    user_id: int
    source_url: Optional[str] = None
    content: str
    correction_examples: list[CorrectionExample] = Field(default_factory=list)


class InquiryAnalysisResponse(BaseModel):
    """POST /internal/inquiries/analyze 응답 바디이자 Gemini 응답 파싱 스키마.

    둘 다 snake_case라 별도 모델로 나누지 않고 하나로 재사용한다
    (Gemini에게 이 스키마 그대로 응답하라고 프롬프트에서 요청함).
    """

    title: str
    summary: str
    severity: InquirySeverity
    domain: InquiryDomain
    estimated_url: Optional[str] = None
    recommended_action: str
    filtered: bool
