"""관리자 운영 Q&A 챗봇의 function calling 도구 모음.

원칙:
- 도구는 Spring 내부 API(/internal/ops/*)만 호출한다 — 파이썬은 MySQL 을 직접 조회하지 않는다.
  쿼리·스키마 지식과 권한 경계를 Spring 한 곳에 유지하기 위함 (2026-07-20, pymysql 직접 조회에서 전환).
- 인증: X-Internal-Token 공유 시크릿 (Spring 은 fail-closed — 토큰 미설정 시 전부 401).
- LIMIT 은 양쪽에서 캡 — 여기서 20 으로 자르고, Spring 어댑터도 20 으로 다시 자른다.
- created_at 은 KST 벽시계(앱 컨벤션). LLM 이 넘긴 명시적 start/end 만 사용한다
  (현재 KST 시각은 시스템 프롬프트가 제공).
- detail 컬럼은 개인정보 여지가 있어 Spring 계약(EventDetail)에서부터 제외돼 있다.
"""

import logging
from datetime import datetime
from functools import lru_cache
from typing import Any, Optional

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

MAX_LIMIT = 20
DEFAULT_LIMIT = 10


class ToolParamError(ValueError):
    """LLM이 넘긴 파라미터가 잘못됨 — 에러 메시지를 도구 결과로 되돌려 재시도를 유도한다."""


class ToolExecutionError(RuntimeError):
    """Spring 내부 API 등 실행 계층 실패."""


@lru_cache()
def _get_client() -> httpx.Client:
    settings = get_settings()
    return httpx.Client(
        base_url=settings.spring_base_url,
        headers={"X-Internal-Token": settings.internal_api_token},
        timeout=httpx.Timeout(connect=3.0, read=15.0, write=5.0, pool=5.0),
    )


def _parse_kst(value: Any, field: str) -> str:
    """'YYYY-MM-DD HH:MM[:SS]' / ISO 문자열 검증 후 Spring ISO_DATE_TIME 형식으로 정규화."""
    if not isinstance(value, str) or not value.strip():
        raise ToolParamError(f"{field}는 'YYYY-MM-DD HH:MM:SS' 형식 문자열이어야 합니다.")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("T", " "))
    except ValueError as exc:
        raise ToolParamError(
            f"{field} 형식이 잘못됐습니다: {value!r} (예: 2026-07-18 00:00:00)"
        ) from exc
    return parsed.strftime("%Y-%m-%dT%H:%M:%S")


def _parse_range(args: dict) -> tuple[str, str]:
    start = _parse_kst(args.get("start"), "start")
    end = _parse_kst(args.get("end"), "end")
    if start >= end:
        raise ToolParamError(f"start({start})는 end({end})보다 앞이어야 합니다.")
    return start, end


def _parse_limit(args: dict) -> int:
    raw = args.get("limit", DEFAULT_LIMIT)
    try:
        limit = int(raw)
    except (TypeError, ValueError) as exc:
        raise ToolParamError(f"limit은 정수여야 합니다: {raw!r}") from exc
    return max(1, min(limit, MAX_LIMIT))


def _base_params(args: dict) -> dict:
    """start/end 필수 + category/event_type 선택 필터 → Spring 쿼리 파라미터."""
    start, end = _parse_range(args)
    params = {"start": start, "end": end}
    if args.get("category"):
        params["category"] = str(args["category"])
    if args.get("event_type"):
        params["eventType"] = str(args["event_type"])
    return params


def _spring_get(path: str, params: Optional[dict] = None) -> dict:
    try:
        response = _get_client().get(path, params=params)
    except httpx.HTTPError as exc:
        logger.exception("event=opschat_tool_spring_unreachable path=%s", path)
        raise ToolExecutionError("운영 데이터 조회에 실패했습니다. (Spring 연결 실패)") from exc

    if response.status_code == 401:
        logger.error("event=opschat_tool_spring_unauthorized path=%s", path)
        raise ToolExecutionError(
            "내부 API 인증에 실패했습니다. INTERNAL_API_TOKEN 설정을 확인하세요."
        )
    if response.status_code == 400:
        # 파라미터 바인딩 실패 등 — LLM 에게 돌려 재시도 유도
        raise ToolParamError(f"조회 파라미터가 잘못됐습니다: {response.text[:200]}")
    if response.status_code != 200:
        logger.error(
            "event=opschat_tool_spring_failed path=%s status=%s", path, response.status_code
        )
        raise ToolExecutionError("운영 데이터 조회에 실패했습니다.")

    return response.json()


# ── 도구 실행 함수 5종 — Spring /internal/ops/* 1:1 매핑 ─────────────


def count_events(args: dict) -> dict:
    return _spring_get("/internal/ops/events/count", _base_params(args))


def event_timeline(args: dict) -> dict:
    return _spring_get("/internal/ops/events/timeline", _base_params(args))


def top_ips(args: dict) -> dict:
    params = _base_params(args)
    params["limit"] = _parse_limit(args)
    return _spring_get("/internal/ops/events/top-ips", params)


def recent_events(args: dict) -> dict:
    params = _base_params(args)
    params["limit"] = _parse_limit(args)
    return _spring_get("/internal/ops/events/recent", params)


def latest_briefing(args: dict) -> dict:
    result = _spring_get("/internal/ops/briefing/latest")
    if result.get("briefing") is None:
        return {"briefing": None, "message": "생성된 브리핑이 아직 없습니다."}
    return result


# ── Gemini function declaration + 디스패치 ──────────────────────────

_TIME_RANGE_PROPS = {
    "start": {
        "type": "string",
        "description": "조회 시작 시각 (KST, 'YYYY-MM-DD HH:MM:SS')",
    },
    "end": {
        "type": "string",
        "description": "조회 끝 시각 (KST, 'YYYY-MM-DD HH:MM:SS')",
    },
}

_FILTER_PROPS = {
    "category": {
        "type": "string",
        "description": (
            "이벤트 카테고리 필터. 값: http_anomaly, ops_metric, authn_attack, "
            "takeover, learning, enrollment, content, chatbot, reward"
        ),
    },
    "event_type": {
        "type": "string",
        "description": (
            "이벤트 타입 필터. 예: login_fail, suspicious_login, auth_401_spike, "
            "access_403, slow_request, http_5xx, concurrent_sample"
        ),
    },
}

_LIMIT_PROP = {
    "limit": {
        "type": "integer",
        "description": f"최대 결과 수 (기본 {DEFAULT_LIMIT}, 상한 {MAX_LIMIT})",
    }
}

TOOL_DECLARATIONS: list[dict] = [
    {
        "name": "count_events",
        "description": "기간 내 서비스 이벤트 건수를 event_type별로 집계한다. 총량 파악의 시작점.",
        "parameters": {
            "type": "object",
            "properties": {**_TIME_RANGE_PROPS, **_FILTER_PROPS},
            "required": ["start", "end"],
        },
    },
    {
        "name": "event_timeline",
        "description": "기간 내 이벤트 발생량을 시간(hour) 단위 추이로 보여준다. 급증 시점 탐지용.",
        "parameters": {
            "type": "object",
            "properties": {**_TIME_RANGE_PROPS, **_FILTER_PROPS},
            "required": ["start", "end"],
        },
    },
    {
        "name": "top_ips",
        "description": "기간 내 이벤트 발생 상위 IP 목록. 공격 의심 IP 식별용.",
        "parameters": {
            "type": "object",
            "properties": {**_TIME_RANGE_PROPS, **_FILTER_PROPS, **_LIMIT_PROP},
            "required": ["start", "end"],
        },
    },
    {
        "name": "recent_events",
        "description": "기간 내 개별 이벤트 상세 목록(최신순). uri·http_status·duration_ms·trace_id 포함.",
        "parameters": {
            "type": "object",
            "properties": {**_TIME_RANGE_PROPS, **_FILTER_PROPS, **_LIMIT_PROP},
            "required": ["start", "end"],
        },
    },
    {
        "name": "latest_briefing",
        "description": "가장 최근 생성된 일일 운영 브리핑(ops_briefing)을 조회한다.",
        "parameters": {"type": "object", "properties": {}},
    },
]

_EXECUTORS = {
    "count_events": count_events,
    "event_timeline": event_timeline,
    "top_ips": top_ips,
    "recent_events": recent_events,
    "latest_briefing": latest_briefing,
}


def execute_tool(name: str, args: Optional[dict]) -> dict:
    """도구 이름으로 디스패치 실행. 파라미터 오류는 LLM에게 그대로 돌려줘 재시도를 유도한다."""
    executor = _EXECUTORS.get(name)
    if executor is None:
        return {"error": f"알 수 없는 도구: {name}"}
    try:
        return executor(args or {})
    except ToolParamError as exc:
        return {"error": str(exc)}
