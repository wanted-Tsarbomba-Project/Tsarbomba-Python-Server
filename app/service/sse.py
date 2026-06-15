"""SSE(text/event-stream) 프레임 직렬화기.

순수 함수 모음 — Gemini/네트워크 의존 없이 격리 테스트 가능.
토큰 본문은 JSON으로 감싼다. 토큰에 줄바꿈(\\n)이 들어가도 SSE 프레임(빈 줄=이벤트 종료)이
깨지지 않게 하기 위함이다.
"""

import json

# Spring/도메인과 공유하는 SSE 이벤트 타입
EVENT_DONE = "done"
EVENT_ERROR = "error"


def _frame(data: str, event: str | None = None) -> str:
    """단일 SSE 프레임 문자열을 만든다. data는 이미 직렬화된 한 줄 문자열이어야 한다."""
    prefix = f"event: {event}\n" if event else ""
    return f"{prefix}data: {data}\n\n"


def token_frame(text: str) -> str:
    """본문 토큰 프레임. event 이름 없음, data에 {"t": text} JSON."""
    return _frame(json.dumps({"t": text}, ensure_ascii=False))


def done_frame(usage: dict) -> str:
    """완료 프레임. 토큰 사용량 메타를 싣는다."""
    return _frame(json.dumps(usage, ensure_ascii=False), event=EVENT_DONE)


def error_frame(code: str, message: str) -> str:
    """스트림 중 에러 프레임."""
    return _frame(
        json.dumps({"code": code, "message": message}, ensure_ascii=False),
        event=EVENT_ERROR,
    )
