"""운영 Q&A 챗봇 — Gemini function calling 루프 + SSE 스트리밍.

흐름:
  질문 → Gemini 스트림 호출(tools 선언)
    ├─ function_call 나오면: status 프레임 송출 → 도구 실행(읽기 전용) → 결과를
    │  대화에 붙이고 다음 라운드 (최대 MAX_TOOL_ROUNDS 회)
    └─ 텍스트가 나오면: 토큰 프레임으로 실시간 스트리밍 → done 프레임(누적 사용량)

SSE 프레임 계약 (Spring 릴레이 → FE 공유):
  - (이벤트명 없음) data: {"t": "토큰"}          — 본문 토큰
  - event: status  data: {"tool": ..., "message": ...} — 도구 실행 안내
  - event: done    data: {"promptTokens": ...}   — 완료 + 누적 토큰 사용량
  - event: error   data: {"code": "OPS-001", "message": ...}

프레임 직렬화기는 chatbot/service/sse.py 와 모양이 같지만 status 프레임이 추가로 필요해
자체 정의한다 (도메인 간 import 결합 회피 — docs/fastapi/04 원칙).
"""

import json
import logging
from functools import lru_cache
from typing import Iterator, Optional

from google import genai
from google.genai import types

from app.core.config import get_settings
from app.opschat.schema.ops_chat import OpsChatRequest
from app.opschat.service import tools as ops_tools

logger = logging.getLogger(__name__)

# 도메인 에러코드 (Spring 쪽 릴레이 구현 시 공유)
OPS_RESPONSE_FAILED = "OPS-001"
OPS_RESPONSE_FAILED_MESSAGE = "운영 챗봇 응답 생성에 실패했습니다."

# 도구 호출 라운드 상한 — 무한 루프/토큰 폭주 방지
MAX_TOOL_ROUNDS = 4

_STATUS_MESSAGES = {
    "count_events": "이벤트 건수 집계 중...",
    "event_timeline": "시간대별 추이 조회 중...",
    "top_ips": "상위 IP 조회 중...",
    "recent_events": "이벤트 상세 조회 중...",
    "latest_briefing": "최신 브리핑 조회 중...",
}

EVENT_STATUS = "status"
EVENT_DONE = "done"
EVENT_ERROR = "error"


# ── SSE 프레임 직렬화 (순수 함수 — 격리 테스트 가능) ────────────────


def _frame(data: str, event: Optional[str] = None) -> str:
    prefix = f"event: {event}\n" if event else ""
    return f"{prefix}data: {data}\n\n"


def token_frame(text: str) -> str:
    return _frame(json.dumps({"t": text}, ensure_ascii=False))


def status_frame(tool_name: str) -> str:
    message = _STATUS_MESSAGES.get(tool_name, f"{tool_name} 실행 중...")
    return _frame(
        json.dumps({"tool": tool_name, "message": message}, ensure_ascii=False),
        event=EVENT_STATUS,
    )


def done_frame(usage: dict) -> str:
    return _frame(json.dumps(usage, ensure_ascii=False), event=EVENT_DONE)


def error_frame(code: str, message: str) -> str:
    return _frame(
        json.dumps({"code": code, "message": message}, ensure_ascii=False),
        event=EVENT_ERROR,
    )


# ── Gemini 연동 ─────────────────────────────────────────────────────


@lru_cache()
def _get_client() -> genai.Client:
    return genai.Client(api_key=get_settings().gemini_api_key)


def _build_contents(request: OpsChatRequest) -> list[types.Content]:
    contents: list[types.Content] = []
    if request.conversation_history:
        for msg in request.conversation_history:
            role = "model" if msg.role == "ai" else "user"
            contents.append(
                types.Content(role=role, parts=[types.Part(text=msg.content)])
            )
    contents.append(
        types.Content(role="user", parts=[types.Part(text=request.user_message)])
    )
    return contents


def _build_config(system_prompt: str) -> types.GenerateContentConfig:
    tool = types.Tool(function_declarations=ops_tools.TOOL_DECLARATIONS)
    return types.GenerateContentConfig(
        system_instruction=system_prompt,
        tools=[tool],
    )


def _accumulate_usage(total: dict, usage_metadata) -> None:
    if usage_metadata is None:
        return
    total["promptTokens"] += usage_metadata.prompt_token_count or 0
    total["completionTokens"] += usage_metadata.candidates_token_count or 0
    total["totalTokens"] += usage_metadata.total_token_count or 0


def stream_ops_chat(
    request: OpsChatRequest, system_prompt: str, trace_id: Optional[str] = None
) -> Iterator[str]:
    """function calling 루프를 돌며 SSE 프레임 문자열을 흘린다."""
    settings = get_settings()
    client = _get_client()
    contents = _build_contents(request)
    config = _build_config(system_prompt)
    total_usage = {"promptTokens": 0, "completionTokens": 0, "totalTokens": 0}

    try:
        # 라운드 0 = 첫 호출, 이후 도구 결과를 붙일 때마다 +1 (상한 MAX_TOOL_ROUNDS)
        for round_no in range(MAX_TOOL_ROUNDS + 1):
            stream = client.models.generate_content_stream(
                model=settings.gemini_model,
                contents=contents,
                config=config,
            )

            calls: list = []
            model_parts: list[types.Part] = []
            usage = None
            for chunk in stream:
                if chunk.text:
                    yield token_frame(chunk.text)
                if chunk.function_calls:
                    calls.extend(chunk.function_calls)
                # 모델 턴 파트를 원본 그대로 보존 — Gemini 3.5는 function_call 파트의
                # thought_signature를 다음 요청에서 요구한다 (재조립하면 유실 → 400)
                if chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts:
                    model_parts.extend(chunk.candidates[0].content.parts)
                if getattr(chunk, "usage_metadata", None) is not None:
                    usage = chunk.usage_metadata
            _accumulate_usage(total_usage, usage)

            if not calls:
                # 도구 호출 없음 = 최종 답변 스트리밍 완료
                yield done_frame(total_usage)
                return

            if round_no == MAX_TOOL_ROUNDS:
                logger.warning(
                    "event=opschat_tool_rounds_exceeded rounds=%s trace_id=%s",
                    round_no, trace_id,
                )
                yield error_frame(
                    OPS_RESPONSE_FAILED,
                    "조회 단계가 너무 깊어요. 질문 범위를 좁혀서 다시 시도해주세요.",
                )
                return

            # 모델의 도구 호출 턴을 원본 파트 그대로 대화에 기록 (thought_signature 보존)
            contents.append(types.Content(role="model", parts=model_parts))

            # 도구 실행 → 결과 턴 추가 (status 프레임으로 진행 상황 노출)
            response_parts: list[types.Part] = []
            for fc in calls:
                args = dict(fc.args) if fc.args else {}
                yield status_frame(fc.name)
                logger.info(
                    "event=opschat_tool_called tool=%s round=%s trace_id=%s",
                    fc.name, round_no, trace_id,
                )
                result = ops_tools.execute_tool(fc.name, args)
                response_parts.append(
                    types.Part.from_function_response(
                        name=fc.name, response={"result": result}
                    )
                )
            contents.append(types.Content(role="tool", parts=response_parts))

    except ops_tools.ToolExecutionError:
        logger.exception(
            "event=opschat_tool_execution_failed code=%s trace_id=%s",
            OPS_RESPONSE_FAILED, trace_id,
        )
        yield error_frame(OPS_RESPONSE_FAILED, "운영 데이터 조회에 실패했습니다.")
    except Exception:
        logger.exception(
            "event=opschat_gemini_failed code=%s trace_id=%s",
            OPS_RESPONSE_FAILED, trace_id,
        )
        yield error_frame(OPS_RESPONSE_FAILED, OPS_RESPONSE_FAILED_MESSAGE)
