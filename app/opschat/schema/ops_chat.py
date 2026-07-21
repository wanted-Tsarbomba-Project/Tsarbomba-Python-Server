from typing import Optional
from pydantic import BaseModel, Field


class OpsConversationMessage(BaseModel):
    """관리자 운영 챗봇 대화 이력 한 건.

    chatbot 도메인의 ConversationMessage와 모양이 같지만 일부러 자체 정의한다
    (도메인 간 import 결합 회피 — docs/fastapi/04 원칙).
    """

    role: str  # "user" or "ai"
    content: str


class OpsChatRequest(BaseModel):
    """Spring 관리자 API(/api/admin/ops-chat)가 릴레이하는 요청 본문.

    운영 데이터는 요청에 싣지 않는다 — LLM이 function calling으로
    필요한 집계만 도구를 통해 조회한다 (읽기 전용).
    """

    user_message: str = Field(min_length=1)
    conversation_history: Optional[list[OpsConversationMessage]] = None
