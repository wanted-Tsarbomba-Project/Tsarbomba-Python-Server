import logging
from time import perf_counter

from app.inquiry.client.gemini_client import generate_analysis
from app.inquiry.metrics import INQUIRY_ANALYSIS_STAGE_DURATION
from app.inquiry.schema.inquiry import InquiryAnalysisResponse, InquiryAnalyzeRequest
from app.inquiry.service.prompt_builder import build_analysis_prompt

logger = logging.getLogger(__name__)


def analyze_inquiry(request: InquiryAnalyzeRequest) -> InquiryAnalysisResponse:
    total_started_at = perf_counter()

    started_at = perf_counter()
    prompt = build_analysis_prompt(request)
    _record_stage_duration("prompt_build", perf_counter() - started_at)

    started_at = perf_counter()
    result = generate_analysis(prompt)
    gemini_call_seconds = perf_counter() - started_at
    _record_stage_duration("gemini_call", gemini_call_seconds)

    total_seconds = perf_counter() - total_started_at
    _record_stage_duration("total", total_seconds)

    logger.info(
        "event=inquiry_python_analysis_completed inquiryId=%s correctionExampleCount=%s "
        "geminiCallMs=%.3f totalMs=%.3f",
        request.inquiry_id,
        len(request.correction_examples),
        gemini_call_seconds * 1000,
        total_seconds * 1000,
    )

    if result.estimated_url:
        return result

    return result.model_copy(update={"estimated_url": request.source_url})


def _record_stage_duration(stage: str, duration_seconds: float) -> None:
    INQUIRY_ANALYSIS_STAGE_DURATION.labels(stage=stage).observe(duration_seconds)
