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
        return InquiryAnalysisResponse.model_validate_json(response.text)
    except (ValueError, ValidationError) as exc:
        logger.warning("event=inquiry_gemini_parse_failed rawText=%s", response.text)
        raise InquiryAnalysisError("Gemini 응답 파싱 실패") from exc
