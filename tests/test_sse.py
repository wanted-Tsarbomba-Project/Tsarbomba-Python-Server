import json

from app.service import sse


def _parse(frame: str):
    """SSE 프레임 한 개를 (event, data_dict)로 파싱. 프레임 무결성도 검증."""
    assert frame.endswith("\n\n"), "프레임은 빈 줄(\\n\\n)로 끝나야 한다"
    lines = frame[:-2].split("\n")
    event = None
    data = None
    for line in lines:
        if line.startswith("event: "):
            event = line[len("event: "):]
        elif line.startswith("data: "):
            data = line[len("data: "):]
    assert data is not None
    return event, json.loads(data)


def test_token_frame_basic():
    event, payload = _parse(sse.token_frame("안녕"))
    assert event is None  # 본문 토큰은 event 이름 없음
    assert payload == {"t": "안녕"}


def test_token_frame_with_newline_does_not_break_framing():
    # 토큰에 줄바꿈이 들어가도 프레임이 깨지면 안 된다 (JSON 인코딩 핵심 케이스)
    code = "def foo():\n    return 1"
    frame = sse.token_frame(code)
    # data 줄은 단 하나여야 한다 (raw \n이 새 줄을 만들지 않음)
    body = frame[:-2]
    assert body.count("\n") == 0
    event, payload = _parse(frame)
    assert payload["t"] == code


def test_token_frame_with_quotes_and_braces():
    text = 'df.query("a > 1") -> {result}'
    _, payload = _parse(sse.token_frame(text))
    assert payload["t"] == text


def test_done_frame_carries_usage():
    usage = {"promptTokens": 12, "completionTokens": 80, "totalTokens": 92}
    event, payload = _parse(sse.done_frame(usage))
    assert event == "done"
    assert payload == usage


def test_error_frame():
    event, payload = _parse(sse.error_frame("CHT-003", "AI 응답 생성에 실패했습니다."))
    assert event == "error"
    assert payload == {"code": "CHT-003", "message": "AI 응답 생성에 실패했습니다."}
