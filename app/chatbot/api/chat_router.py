from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.chatbot.schema.chat import ChatRequest
from app.chatbot.service.prompt_builder import build_system_prompt
from app.chatbot.service.gemini_client import stream_gemini
from app.core.config import get_settings

router = APIRouter()


@router.post("/chat")
def chat(request: ChatRequest) -> StreamingResponse:
    """
    Spring Backend로부터 ChatRequest를 받아 Gemini 응답을 SSE로 스트리밍한다.

    Flow:
    1. 모드 분기 (문제풀이 / 자유질문)
    2. 시스템 프롬프트 조립 (Jinja2)
    3. Gemini 스트림 호출 → 토큰을 SSE 프레임으로 흘림 (event 없는 data=토큰, done, error)
    """
    settings = get_settings()
    history_len = len(request.conversation_history or [])
    print(f"[chat] user_message={request.user_message!r} history_len={history_len}")
    system_prompt = build_system_prompt(request, settings.default_max_length)

    return StreamingResponse(
        stream_gemini(request, system_prompt),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
