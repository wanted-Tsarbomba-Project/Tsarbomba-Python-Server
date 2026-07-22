import logging
from functools import lru_cache

from google import genai
from google.genai import types
from pydantic import ValidationError

from app.core.config import get_settings
from app.inquiry.schema.inquiry import InquiryAnalysisResponse

logger = logging.getLogger(__name__)


class InquiryAnalysisError(Exception):
    """Gemini 호출 또는 응답 파싱 실패 시 발생한다."""


@lru_cache()
def _get_client() -> genai.Client:
    return genai.Client(api_key=get_settings().gemini_api_key)


def generate_analysis(prompt: str) -> InquiryAnalysisResponse:
    """조립된 프롬프트로 Gemini를 호출해 구조화된 JSON 분석 결과를 받는다."""
    settings = get_settings()
    client = _get_client()

    try:
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
    except Exception as exc:
        logger.exception("event=inquiry_gemini_call_failed")
        raise InquiryAnalysisError("Gemini 호출 실패") from exc

    try:
        # response.text는 안전 필터 등으로 유효한 텍스트가 없으면 ValueError를 던진다.
        # 아래에서 두 번 접근하면(파싱 실패 로깅 시) 같은 예외가 또 발생해 502 대신
        # 처리되지 않은 500으로 이어지므로, 먼저 지역 변수로 한 번만 안전하게 꺼내둔다.
        raw_text = response.text
    except ValueError as exc:
        logger.warning("event=inquiry_gemini_empty_response")
        raise InquiryAnalysisError("Gemini 응답에 유효한 텍스트가 없습니다") from exc

    try:
        return InquiryAnalysisResponse.model_validate_json(raw_text)
    except (ValueError, ValidationError) as exc:
        logger.warning("event=inquiry_gemini_parse_failed rawText=%s", raw_text)
        raise InquiryAnalysisError("Gemini 응답 파싱 실패") from exc
