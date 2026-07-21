import logging
from typing import Optional

from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse

from app.core.config import get_settings
from app.opschat.schema.ops_chat import OpsChatRequest
from app.opschat.service.ops_gemini_client import stream_ops_chat
from app.opschat.service.ops_prompt_builder import build_ops_system_prompt

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/ops-chat")
def ops_chat(
    request: OpsChatRequest,
    x_trace_id: Optional[str] = Header(default=None, alias="X-Trace-Id"),
) -> StreamingResponse:
    """관리자 운영 Q&A 챗봇. Spring(/api/admin/ops-chat)만 이 엔드포인트를 부른다.

    관리자 인증은 Spring 에서 끝난다 — 여기는 내부망 전용이라 인증 코드가 없다.
    (배포 시 SG 로 8000 포트를 Spring 박스에만 열어야 하는 전제)

    Flow:
    1. 시스템 프롬프트 조립 (현재 KST 시각 주입)
    2. Gemini function calling 루프 — 읽기 전용 도구로 service_event/ops_briefing 조회
    3. SSE 스트리밍 (data=토큰, status, done, error)

    유저 입력 원문은 로깅하지 않는다 — 길이만 남긴다 (chatbot 도메인과 동일 방침).
    """
    settings = get_settings()
    history_len = len(request.conversation_history or [])
    logger.info(
        "event=opschat_chat_started history_len=%s user_message_length=%s trace_id=%s",
        history_len, len(request.user_message or ""), x_trace_id,
    )
    system_prompt = build_ops_system_prompt(settings.default_max_length)

    return StreamingResponse(
        stream_ops_chat(request, system_prompt, x_trace_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
