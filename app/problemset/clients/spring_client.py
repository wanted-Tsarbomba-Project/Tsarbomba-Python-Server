from typing import Any

import httpx

from app.problemset.core.config import get_settings


def spring_get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    settings = get_settings()

    try:
        response = httpx.get(
            f"{settings.spring_base_url.rstrip('/')}{path}",
            params=params,
            timeout=5.0,
        )
        response.raise_for_status()
        return response.json()
    except httpx.ConnectError:
        return {"error": "Spring 서버에 연결할 수 없습니다."}
    except httpx.TimeoutException:
        return {"error": "Spring 서버 응답이 지연되고 있습니다."}
    except httpx.HTTPStatusError as exc:
        return {
            "error": "Spring 서버 요청에 실패했습니다.",
            "status_code": exc.response.status_code,
            "body": _safe_response_body(exc.response),
        }
    except Exception as exc:
        return {
            "error": "Spring 서버 요청 중 알 수 없는 오류가 발생했습니다.",
            "exception_type": exc.__class__.__name__,
        }


def _safe_response_body(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text[:500]
