from fastapi import APIRouter, HTTPException, status

from app.inquiry.client.gemini_client import InquiryAnalysisError
from app.inquiry.schema.inquiry import InquiryAnalysisResponse, InquiryAnalyzeRequest
from app.inquiry.service.inquiry_service import analyze_inquiry

router = APIRouter(
    prefix="/internal/inquiries",
    tags=["inquiries"],
)


@router.post("/analyze", response_model=InquiryAnalysisResponse)
def analyze(request: InquiryAnalyzeRequest) -> InquiryAnalysisResponse:
    try:
        return analyze_inquiry(request)
    except InquiryAnalysisError as exc:
        # 502: 내 버그가 아니라 내가 의존하는 Gemini가 실패했다는 의미 (수업 관례)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
