import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.monitoring.metrics import HTTP_REQUEST_DURATION_SECONDS, HTTP_REQUESTS_TOTAL

# domain 분류 기준: 각 도메인 라우터의 path prefix.
# app/chatbot -> "chatbot", app/recommendation -> "recommendation", 그 외(health, metrics 등) -> "system"
_DOMAIN_PREFIXES = (
    ("/internal/recommendations", "recommendation"),
    ("/chat", "chatbot"),
)

_EXCLUDED_PATHS = {"/metrics"}


def _resolve_domain(api: str) -> str:
    for prefix, domain in _DOMAIN_PREFIXES:
        if api.startswith(prefix):
            return domain
    return "system"


def _resolve_api(request: Request) -> str:
    # 라우팅이 끝난 뒤에는 scope["route"]에 매칭된 라우트가 담긴다.
    # path param이 생기더라도 카디널리티가 폭발하지 않도록 실제 값 대신 라우트 템플릿을 쓴다.
    route = request.scope.get("route")
    if route is not None and getattr(route, "path", None):
        return route.path
    return request.url.path


class HttpMetricsMiddleware(BaseHTTPMiddleware):
    """API별 HTTP 요청 수/소요시간을 domain, method, api, status label로 기록한다."""

    async def dispatch(self, request: Request, call_next):
        if request.url.path in _EXCLUDED_PATHS:
            return await call_next(request)

        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            duration = time.perf_counter() - start
            api = _resolve_api(request)
            labels = {
                "domain": _resolve_domain(api),
                "method": request.method,
                "api": api,
                "status": str(status_code),
            }
            HTTP_REQUESTS_TOTAL.labels(**labels).inc()
            HTTP_REQUEST_DURATION_SECONDS.labels(**labels).observe(duration)
