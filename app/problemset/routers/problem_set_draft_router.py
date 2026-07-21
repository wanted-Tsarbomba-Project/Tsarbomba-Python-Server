from fastapi import APIRouter

from schemas.problem_set_draft_schema import ChatRequest, ChatResponse
from services.problem_set_draft_service import ProblemSetDraftService

router = APIRouter(prefix="/problem-set-draft", tags=["problem-set-draft"])
service = ProblemSetDraftService()


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    return service.generate(request)
