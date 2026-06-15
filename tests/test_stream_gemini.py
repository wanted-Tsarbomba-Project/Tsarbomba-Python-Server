import json

from app.schema.chat import ChatRequest
from app.service import gemini_client


class _FakeChunk:
    def __init__(self, text, usage_metadata=None):
        self.text = text
        self.usage_metadata = usage_metadata


class _FakeUsage:
    def __init__(self, p, c, t):
        self.prompt_token_count = p
        self.candidates_token_count = c
        self.total_token_count = t


class _FakeModels:
    def __init__(self, chunks=None, raise_exc=None):
        self._chunks = chunks or []
        self._raise = raise_exc

    def generate_content_stream(self, **kwargs):
        if self._raise:
            raise self._raise
        return iter(self._chunks)


class _FakeClient:
    def __init__(self, models):
        self.models = models


def _install(monkeypatch, models):
    monkeypatch.setattr(gemini_client, "_get_client", lambda: _FakeClient(models))


def _frames(monkeypatch, models):
    _install(monkeypatch, models)
    req = ChatRequest(user_message="hi")
    return list(gemini_client.stream_gemini(req, "system"))


def _data(frame):
    line = [l for l in frame[:-2].split("\n") if l.startswith("data: ")][0]
    return json.loads(line[len("data: "):])


def test_streams_tokens_then_done(monkeypatch):
    chunks = [
        _FakeChunk("안"),
        _FakeChunk("녕", usage_metadata=_FakeUsage(12, 80, 92)),
    ]
    frames = _frames(monkeypatch, _FakeModels(chunks=chunks))

    # 토큰 2개 + done 1개
    assert _data(frames[0]) == {"t": "안"}
    assert _data(frames[1]) == {"t": "녕"}
    assert frames[2].startswith("event: done\n")
    assert _data(frames[2]) == {"promptTokens": 12, "completionTokens": 80, "totalTokens": 92}


def test_done_defaults_when_no_usage(monkeypatch):
    frames = _frames(monkeypatch, _FakeModels(chunks=[_FakeChunk("x")]))
    assert _data(frames[-1]) == {"promptTokens": 0, "completionTokens": 0, "totalTokens": 0}


def test_emits_error_frame_on_exception(monkeypatch):
    frames = _frames(monkeypatch, _FakeModels(raise_exc=RuntimeError("boom")))
    assert len(frames) == 1
    assert frames[0].startswith("event: error\n")
    assert _data(frames[0])["code"] == "CHT-003"


def test_skips_empty_text_chunks(monkeypatch):
    chunks = [_FakeChunk(""), _FakeChunk(None), _FakeChunk("실제")]
    frames = _frames(monkeypatch, _FakeModels(chunks=chunks))
    token_frames = [f for f in frames if not f.startswith("event:")]
    assert len(token_frames) == 1
    assert _data(token_frames[0]) == {"t": "실제"}
